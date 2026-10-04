"""HTTP surface, with the node mocked out.

Two things are under test: input validation (this app accepts user-supplied
numbers and hex and feeds them toward a shared node) and the guarantee that
/submit only ever calls the two read-only validation RPCs, on bytes this
process built itself.
"""
import pytest
from fastapi.testclient import TestClient

import buildcache
import main
from scenarios import SCENARIOS_BY_ID
from sources import SOURCES

from helpers import block_hex, tx_hex

READ_ONLY_METHODS = {"getblocktemplate", "testmempoolaccept"}


@pytest.fixture(autouse=True)
def clean_state():
    for limiter in (main.build_limiter, main.status_limiter):
        limiter._hits.clear()
    buildcache._cache.clear()
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def calls(monkeypatch):
    """Replace every mutation with a recorder returning real, decodable hex."""
    seen = []

    def make(scenario):
        def fake(**kwargs):
            seen.append((scenario["id"], kwargs))
            make_hex = block_hex if scenario["kind"] == "block" else tx_hex
            return {
                "payload_hex": make_hex(),
                "baseline_hex": make_hex(),
                "build_calls": ["fake"],
                "editable_value": 1,
                "hint_value": 99,
            }
        return fake

    fakes = {s["mutation"]: make(s) for s in SCENARIOS_BY_ID.values()}
    monkeypatch.setattr(main, "MUTATIONS", fakes)
    return seen


def build(client, scenario_id, **overrides):
    return client.post("/build", json={"scenario_id": scenario_id, **overrides})


class TestBuildValidation:
    def test_unknown_scenario_is_404(self, client, calls):
        assert build(client, "does_not_exist").status_code == 404

    @pytest.mark.parametrize("bad_id", ["Bad-ID", "1abc", "", "a" * 65, "../etc"])
    def test_malformed_scenario_id_is_rejected_by_schema(self, client, calls, bad_id):
        assert build(client, bad_id).status_code == 422

    def test_unexpected_fields_are_forbidden(self, client, calls):
        assert build(client, "dust_output", payload_hex="00").status_code == 422

    def test_no_override_calls_mutation_with_no_arguments(self, client, calls):
        assert build(client, "dust_output").status_code == 200
        assert calls == [("dust_output", {})]

    def test_int_override_is_forwarded_under_the_catalog_field_name(self, client, calls):
        assert build(client, "dust_output", override_value_sats=294).status_code == 200
        assert calls == [("dust_output", {"value_sats": 294})]

    @pytest.mark.parametrize("sats,status", [(0, 422), (1, 200), (2000, 200), (2001, 422)])
    def test_int_override_enforces_catalog_bounds_inclusively(self, client, calls, sats, status):
        # dust_output is declared min=1, max=2000 in scenarios.py
        assert build(client, "dust_output", override_value_sats=sats).status_code == status

    def test_wrong_override_type_for_scenario_is_422(self, client, calls):
        assert build(client, "dust_output", override_hex="ab" * 32).status_code == 422
        assert calls == []

    def test_two_overrides_at_once_is_422(self, client, calls):
        r = build(client, "dust_output", override_value_sats=5, override_choice="x")
        assert r.status_code == 422 and calls == []

    def test_choice_override_must_be_a_listed_option(self, client, calls):
        assert build(client, "double_spend", override_choice="made_up").status_code == 422
        assert build(client, "double_spend", override_choice="spendable_a").status_code == 200
        assert calls == [("double_spend", {"utxo_key": "spendable_a"})]

    @pytest.mark.parametrize("value", ["ab" * 31, "zz" * 32, "ab" * 33])
    def test_hex_override_must_be_exactly_64_hex_chars(self, client, calls, value):
        assert build(client, "bad_merkle_root", override_hex=value).status_code == 422

    def test_valid_hex_override_is_forwarded(self, client, calls):
        assert build(client, "bad_merkle_root", override_hex="ab" * 32).status_code == 200
        assert calls == [("bad_merkle_root", {"merkle_root_hex": "ab" * 32})]

    def test_override_on_scenario_without_editable_field_is_400(self, client, calls, monkeypatch):
        bare = {**SCENARIOS_BY_ID["dust_output"], "editable": None}
        monkeypatch.setattr(main, "SCENARIOS_BY_ID", {"dust_output": bare})
        assert build(client, "dust_output", override_value_sats=5).status_code == 400

    def test_body_over_1kb_is_413(self, client, calls):
        r = client.post("/build", content=b"x" * 2000, headers={"content-type": "application/json"})
        assert r.status_code == 413


class TestBuildResponse:
    def test_shape(self, client, calls):
        body = build(client, "dust_output").json()
        assert set(body) >= {"build_id", "scenario_id", "kind", "payload_hex", "baseline_hex",
                             "payload_structured", "build_calls", "editable", "editable_value", "hint_value"}
        assert body["kind"] == "tx" and body["hint_value"] == 99
        assert body["editable"]["hint"]

    def test_mutation_failure_is_502_and_does_not_leak_details(self, client, monkeypatch):
        def boom(**_):
            raise RuntimeError("secret internal rpc detail")
        monkeypatch.setattr(main, "MUTATIONS", {s["mutation"]: boom for s in SCENARIOS_BY_ID.values()})
        r = build(client, "dust_output")
        assert r.status_code == 502
        assert "secret" not in r.text


class TestSubmit:
    def submit(self, client, build_id):
        return client.post("/submit", json={"build_id": build_id})

    def test_block_scenario_uses_proposal_mode_and_maps_the_source(self, client, calls, monkeypatch):
        seen = []
        monkeypatch.setattr(main, "rpc", lambda m, p=None, **kw: seen.append((m, p)) or "bad-cb-amount")
        built = build(client, "coinbase_oversubsidy").json()
        r = self.submit(client, built["build_id"]).json()
        assert seen == [("getblocktemplate", [{"mode": "proposal", "data": built["payload_hex"]}])]
        assert r["verdict"] == "bad-cb-amount" and r["accepted"] is False
        assert r["source"] == SOURCES["bad-cb-amount"] and r["rule_type"] == "consensus"

    def test_tx_scenario_uses_testmempoolaccept(self, client, calls, monkeypatch):
        seen = []

        def fake(m, p=None, **kw):
            seen.append(m)
            return [{"allowed": False, "reject-reason": "dust"}]

        monkeypatch.setattr(main, "rpc", fake)
        built = build(client, "dust_output").json()
        r = self.submit(client, built["build_id"]).json()
        assert seen == ["testmempoolaccept"]
        assert r["verdict"] == "dust" and r["rule_type"] == "policy" and r["source"]["function"]

    @pytest.mark.parametrize("scenario_id", list(SCENARIOS_BY_ID))
    def test_every_scenario_only_ever_uses_read_only_rpcs(self, client, calls, monkeypatch, scenario_id):
        seen = []
        monkeypatch.setattr(main, "rpc", lambda m, p=None, **kw: seen.append(m) or (
            None if SCENARIOS_BY_ID[scenario_id]["kind"] == "block" else [{"allowed": True}]))
        built = build(client, scenario_id).json()
        self.submit(client, built["build_id"])
        assert set(seen) <= READ_ONLY_METHODS and seen

    def test_accepted_payload_has_no_verdict_or_source(self, client, calls, monkeypatch):
        monkeypatch.setattr(main, "rpc", lambda *a, **k: None)
        built = build(client, "coinbase_oversubsidy").json()
        r = self.submit(client, built["build_id"]).json()
        assert r["accepted"] is True and r["verdict"] is None and r["source"] is None

    def test_unmapped_verdict_still_returns_with_no_source(self, client, calls, monkeypatch):
        monkeypatch.setattr(main, "rpc", lambda *a, **k: "some-new-core-string")
        built = build(client, "coinbase_oversubsidy").json()
        r = self.submit(client, built["build_id"]).json()
        assert r["verdict"] == "some-new-core-string" and r["source"] is None

    def test_unknown_or_expired_build_is_410(self, client):
        assert self.submit(client, "A" * 22).status_code == 410

    def test_client_cannot_supply_its_own_bytes(self, client, calls):
        r = client.post("/submit", json={"build_id": "A" * 22, "payload_hex": "00"})
        assert r.status_code == 422

    @pytest.mark.parametrize("bad", ["short", "has spaces in it!!", "x" * 65])
    def test_malformed_build_id_is_rejected_by_schema(self, client, bad):
        assert self.submit(client, bad).status_code == 422

    def test_node_failure_is_502(self, client, calls, monkeypatch):
        def down(*a, **k):
            raise ConnectionError("node down")
        monkeypatch.setattr(main, "rpc", down)
        built = build(client, "dust_output").json()
        assert self.submit(client, built["build_id"]).status_code == 502


class TestHealthAndStatus:
    def test_health_ok(self, client, monkeypatch):
        monkeypatch.setattr(main, "rpc", lambda *a, **k: 123)
        assert client.get("/health").json() == {"status": "ok"}

    def test_health_is_503_when_node_is_unreachable(self, client, monkeypatch):
        def down(*a, **k):
            raise ConnectionError("refused")
        monkeypatch.setattr(main, "rpc", down)
        assert client.get("/health").status_code == 503

    def test_health_is_never_rate_limited(self, client, monkeypatch):
        # An orchestrator polls this forever; a 429 here would defeat restart-on-failure.
        monkeypatch.setattr(main, "rpc", lambda *a, **k: 1)
        assert all(client.get("/health").status_code == 200 for _ in range(main.status_limiter.max_requests + 30))

    def test_scenarios_endpoint_serves_the_catalog(self, client):
        assert [s["id"] for s in client.get("/scenarios").json()] == list(SCENARIOS_BY_ID)

    def test_status_endpoints_are_rate_limited(self, client, monkeypatch):
        monkeypatch.setattr(main.status_limiter, "max_requests", 2)
        codes = [client.get("/scenarios").status_code for _ in range(3)]
        assert codes == [200, 200, 429]

    def test_node_status_passes_through_chain_info(self, client, monkeypatch):
        monkeypatch.setattr(main, "rpc", lambda *a, **k: {"chain": "regtest", "blocks": 5, "bestblockhash": "ff", "extra": 1})
        assert client.get("/node-status").json() == {"chain": "regtest", "blocks": 5, "bestblockhash": "ff"}

    def test_node_status_is_502_when_node_down(self, client, monkeypatch):
        def down(*a, **k):
            raise ConnectionError()
        monkeypatch.setattr(main, "rpc", down)
        assert client.get("/node-status").status_code == 502


class TestCors:
    def test_dev_origin_is_allowed(self, client):
        r = client.options("/build", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_foreign_origin_is_not(self, client):
        r = client.options("/build", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in r.headers
