import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import buildcache
from decode import decode_payload
from mutations import MUTATIONS
from node import rpc
from ratelimit import RateLimiter, rate_limit_dependency
from scenarios import SCENARIOS, SCENARIOS_BY_ID
from sources import SOURCES

logger = logging.getLogger("btcplayground")

app = FastAPI(title="My BTC Playground")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# --- request body size cap -------------------------------------------------
# Every request this API accepts is a tiny JSON object (a scenario id or a
# build token) -- there is no legitimate reason for a body over ~1KB.
MAX_BODY_BYTES = 1024


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            too_big = int(content_length) > MAX_BODY_BYTES
        except ValueError:
            too_big = True
        if too_big:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
    return await call_next(request)


# --- rate limits -------------------------------------------------------
# /build and /submit each do real work against the one shared node; /scenarios
# and /node-status are cheap but still capped against a scripted loop.
build_limiter = RateLimiter(max_requests=60, window_seconds=60)
status_limiter = RateLimiter(max_requests=120, window_seconds=60)

limit_build = rate_limit_dependency(build_limiter)
limit_status = rate_limit_dependency(status_limiter)


# --- request schemas -----------------------------------------------------
# Patterns match exactly what this API ever hands out itself (snake_case
# scenario ids from scenarios.py, url-safe tokens from buildcache.store) --
# anything else is rejected before it reaches any handler logic.
SCENARIO_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
BUILD_ID_PATTERN = r"^[A-Za-z0-9_-]{16,64}$"


class ScenarioRequest(BaseModel):
    model_config = {"extra": "forbid"}
    scenario_id: str = Field(pattern=SCENARIO_ID_PATTERN)


class SubmitRequest(BaseModel):
    model_config = {"extra": "forbid"}
    build_id: str = Field(pattern=BUILD_ID_PATTERN)


@app.get("/scenarios", dependencies=[Depends(limit_status)])
def list_scenarios():
    return SCENARIOS


@app.get("/node-status", dependencies=[Depends(limit_status)])
def node_status():
    try:
        info = rpc("getblockchaininfo", wallet=None)
    except Exception:
        logger.exception("getblockchaininfo failed")
        raise HTTPException(status_code=502, detail="node unreachable")
    return {
        "chain": info["chain"],
        "blocks": info["blocks"],
        "bestblockhash": info["bestblockhash"],
    }


@app.post("/build", dependencies=[Depends(limit_build)])
def build_scenario(req: ScenarioRequest):
    scenario = SCENARIOS_BY_ID.get(req.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario_id: {req.scenario_id}")

    try:
        result = MUTATIONS[scenario["mutation"]]()
        payload_structured = decode_payload(result["payload_hex"], scenario["kind"], result["baseline_hex"])
    except Exception:
        logger.exception("build failed for scenario_id=%s", scenario["id"])
        raise HTTPException(status_code=502, detail="could not build payload against the node right now")

    build_id = buildcache.store(scenario["id"], result["payload_hex"])

    return {
        "build_id": build_id,
        "scenario_id": scenario["id"],
        "kind": scenario["kind"],
        "payload_hex": result["payload_hex"],
        "baseline_hex": result["baseline_hex"],
        "payload_structured": payload_structured,
        "build_calls": result["build_calls"],
    }


@app.post("/submit", dependencies=[Depends(limit_build)])
def submit_scenario(req: SubmitRequest):
    entry = buildcache.get(req.build_id)
    if entry is None:
        raise HTTPException(status_code=410, detail="build expired or not found -- click Build Payload again")

    scenario = SCENARIOS_BY_ID.get(entry["scenario_id"])
    if scenario is None:
        raise HTTPException(status_code=404, detail="unknown scenario for this build")

    payload_hex = entry["payload_hex"]

    if scenario["kind"] == "block":
        method = "getblocktemplate"
        params = [{"mode": "proposal", "data": payload_hex}]
    else:
        method = "testmempoolaccept"
        params = [[payload_hex]]

    try:
        start = time.perf_counter()
        raw_result = rpc(method, params)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    except Exception:
        logger.exception("submit failed for scenario_id=%s", scenario["id"])
        raise HTTPException(status_code=502, detail="could not validate against the node right now")

    if scenario["kind"] == "block":
        verdict = raw_result if raw_result else None
    else:
        first = raw_result[0]
        verdict = None if first["allowed"] else first["reject-reason"]

    source = SOURCES.get(verdict) if verdict else None

    return {
        "rpc_request": {"method": method, "params": params},
        "rpc_response": raw_result,
        "elapsed_ms": elapsed_ms,
        "verdict": verdict,
        "accepted": verdict is None,
        "source": source,
        "rule_type": scenario["rule_type"],
    }
