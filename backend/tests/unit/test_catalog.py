"""Contract tests for the scenario catalog.

Prose conventions ("add one entry and one mutation, nothing else") are easy
for a contributor -- human or agent -- to violate quietly. These tests turn
each convention into a failure with a message that says what to fix, so the
rule is enforced rather than merely documented. See docs/adding-a-scenario.md.
"""
import inspect
import re

import pytest

import main
from mutations import FIXTURES, MUTATIONS
from scenarios import SCENARIOS, SCENARIOS_BY_ID
from sources import COMMIT, SOURCES

REQUIRED = {"id", "title", "summary", "kind", "fixture_key", "mutation", "expected_reject_reason",
            "rule_type", "explanation", "reference", "editable"}
SUMMARY_MAX_CHARS = 70
IDS = [s["id"] for s in SCENARIOS]


def test_scenario_ids_are_unique():
    assert len(IDS) == len(set(IDS))
    assert set(SCENARIOS_BY_ID) == set(IDS)


@pytest.mark.parametrize("s", SCENARIOS, ids=IDS)
class TestEachScenario:
    def test_has_required_keys_and_valid_enums(self, s):
        assert REQUIRED <= set(s), f"missing keys: {REQUIRED - set(s)}"
        assert s["kind"] in {"block", "tx"}
        assert s["rule_type"] in {"consensus", "policy"}

    def test_id_is_accepted_by_the_api_schema(self, s):
        assert re.fullmatch(main.SCENARIO_ID_PATTERN, s["id"])

    def test_mutation_is_registered(self, s):
        assert s["mutation"] in MUTATIONS, "add the function to MUTATIONS in mutations.py"

    def test_rejection_string_has_a_source_entry_of_the_same_rule_type(self, s):
        reason = s["expected_reject_reason"]
        assert reason in SOURCES, f"add {reason!r} to sources.py (and verify it with `make test-sources`)"
        assert SOURCES[reason]["rule_type"] == s["rule_type"]

    def test_summary_is_one_short_plain_sentence(self, s):
        # Shown in the home page list, where the long explanation was too much.
        summary = s["summary"]
        assert len(summary) <= SUMMARY_MAX_CHARS, f"summary is {len(summary)} chars; keep it under {SUMMARY_MAX_CHARS}"
        assert summary.endswith(".") and summary.count(".") == 1, "summary must be exactly one sentence"
        assert not set(summary) & {"\u2014", "\u2013", ";"}, "no dashes or semicolons in the summary"

    def test_explanation_reference_placeholder_matches_reference(self, s):
        has_placeholder = "{ref}" in s["explanation"]
        assert has_placeholder == (s["reference"] is not None)
        if s["reference"]:
            assert s["reference"]["label"] and s["reference"]["url"].startswith("https://")

    def test_fixture_key_exists_in_fixtures(self, s):
        if s["fixture_key"] is not None:
            assert s["fixture_key"] in FIXTURES["utxos"]

    def test_editable_field_is_a_real_optional_parameter_of_the_mutation(self, s):
        # main.py calls MUTATIONS[...](**{editable["field"]: value}); a typo here
        # would only surface as a 502 at request time.
        params = inspect.signature(MUTATIONS[s["mutation"]]).parameters
        field = s["editable"]["field"]
        assert field in params
        assert params[field].default is None

    def test_editable_spec_is_well_formed(self, s):
        e = s["editable"]
        assert e["type"] in {"int", "hex", "choice"} and e["label"]
        if e["type"] == "int":
            assert e["min"] <= e["max"] and e["step"] >= 1
        elif e["type"] == "hex":
            assert e["length"] == 64, "main.ScenarioRequest.override_hex only accepts 64 hex chars"
        else:
            values = [o["value"] for o in e["options"]]
            assert len(values) >= 2 and len(values) == len(set(values))
            assert all(o["label"] for o in e["options"])

    def test_hint_uses_only_the_supported_placeholder(self, s):
        hint = s["editable"].get("hint")
        assert hint, "every editable scenario needs a hint (the UI renders it under the input)"
        assert set(re.findall(r"\{(\w*)\}", hint)) <= {"hint_value"}


def test_every_mutation_belongs_to_a_scenario():
    assert set(MUTATIONS) == {s["mutation"] for s in SCENARIOS}


def test_int_override_bounds_fit_the_api_schema():
    ceiling = 100_000_000_000  # main.ScenarioRequest.override_value_sats le=
    for s in SCENARIOS:
        e = s["editable"]
        if e["type"] == "int":
            assert 0 <= e["min"] and e["max"] <= ceiling


@pytest.mark.parametrize("key", list(SOURCES), ids=list(SOURCES))
class TestEachSource:
    """Offline checks. The real cross-check against Core's source is the
    network tier (tests/network/test_sources.py)."""

    def test_permalink_is_pinned_and_matches_lines(self, key):
        entry = SOURCES[key]
        start, end = entry["lines"]
        assert 1 <= start <= end
        assert COMMIT in entry["permalink"] and entry["permalink"].endswith(f"#L{start}-L{end}")
        assert entry["permalink"].startswith("https://github.com/bitcoin/bitcoin/blob/")

    def test_snippet_contains_the_rejection_string(self, key):
        assert f'"{key}"' in SOURCES[key]["snippet"]

    def test_alternate_sites_are_well_formed(self, key):
        for alt in SOURCES[key].get("also_produced_by", []):
            start, end = alt["lines"]
            assert alt["permalink"].endswith(f"#L{start}-L{end}") and COMMIT in alt["permalink"]
            assert alt["note"]
