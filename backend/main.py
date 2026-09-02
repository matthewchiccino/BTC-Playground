import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import buildcache
from decode import decode_payload
from mutations import FIXTURES, MUTATIONS
from node import rpc
from ratelimit import RateLimiter, rate_limit_dependency
from scenarios import SCENARIOS, SCENARIOS_BY_ID
from sources import SOURCES

# Without this, "btcplayground" has no handler of its own, propagates to
# an unconfigured root logger, and Python's last-resort handler silently
# eats everything below WARNING -- so logger.exception() calls further
# down would technically fire but never actually show up in `docker logs`.
# uvicorn configures its own uvicorn/uvicorn.error/uvicorn.access loggers
# separately and doesn't touch root, so this doesn't fight with that.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("btcplayground")

app = FastAPI(title="BTC Playground")

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
    # One optional override per editable field type. Coarse schema-level
    # bounds/patterns here; the real per-scenario min/max/options (from
    # scenarios.py) are enforced in the handler.
    override_value_sats: int | None = Field(default=None, ge=0, le=100_000_000_000)
    override_hex: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    override_choice: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")


class SubmitRequest(BaseModel):
    model_config = {"extra": "forbid"}
    build_id: str = Field(pattern=BUILD_ID_PATTERN)


@app.get("/health")
def health():
    """Liveness probe, not user-facing: attempts one cheap RPC call and
    returns 200/503. No rate limit -- a container orchestrator hits this
    every ~30s for the life of the process, and rate-limiting it defeats
    the point of a restart-on-failure policy. Deliberately separate from
    /node-status, which is rate-limited, richer, and meant for the UI.
    """
    try:
        rpc("getblockcount", wallet=None)
    except Exception:
        logger.exception("health check RPC failed")
        raise HTTPException(status_code=503, detail="node unreachable")
    return {"status": "ok"}


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


@app.get("/node-info", dependencies=[Depends(limit_status)])
def node_info():
    """Static setup details (from fixtures.json, written once by
    setup_chain.py) plus a couple of live fields -- for the "About: The
    Node" page, not the lightweight polling strip."""
    try:
        start = time.perf_counter()
        netinfo = rpc("getnetworkinfo", wallet=None)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    except Exception:
        logger.exception("getnetworkinfo failed")
        raise HTTPException(status_code=502, detail="node unreachable")

    return {
        "subversion": netinfo["subversion"],
        "protocol_version": netinfo["protocolversion"],
        "elapsed_ms": elapsed_ms,
        "network": FIXTURES["network"],
        "frozen_tip_hash": FIXTURES["frozen_tip_hash"],
        "frozen_tip_height": FIXTURES["frozen_tip_height"],
        "mining_address": FIXTURES["mining_address"],
        "utxos": FIXTURES["utxos"],
    }


@app.post("/build", dependencies=[Depends(limit_build)])
def build_scenario(req: ScenarioRequest):
    scenario = SCENARIOS_BY_ID.get(req.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario_id: {req.scenario_id}")

    editable = scenario.get("editable")
    overrides = {
        "int": req.override_value_sats,
        "hex": req.override_hex,
        "choice": req.override_choice,
    }
    provided = [(t, v) for t, v in overrides.items() if v is not None]

    kwargs = {}
    if provided:
        if len(provided) > 1:
            raise HTTPException(status_code=422, detail="only one override field may be set")
        if not editable:
            raise HTTPException(status_code=400, detail=f"scenario {scenario['id']} has no editable field")
        override_type, override_value = provided[0]
        if override_type != editable["type"]:
            raise HTTPException(
                status_code=422,
                detail=f"scenario {scenario['id']} expects a {editable['type']}-type override",
            )
        if override_type == "int" and not (editable["min"] <= override_value <= editable["max"]):
            raise HTTPException(
                status_code=422,
                detail=f"{editable['field']} must be between {editable['min']} and {editable['max']}",
            )
        if override_type == "choice":
            valid_values = {o["value"] for o in editable["options"]}
            if override_value not in valid_values:
                raise HTTPException(status_code=422, detail=f"{editable['field']} must be one of {sorted(valid_values)}")
        kwargs[editable["field"]] = override_value

    try:
        result = MUTATIONS[scenario["mutation"]](**kwargs)
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
        "editable": editable,
        "subsidy_sats": result.get("subsidy_sats"),
        "editable_value": result.get("editable_value"),
        "hint_value": result.get("hint_value"),
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
