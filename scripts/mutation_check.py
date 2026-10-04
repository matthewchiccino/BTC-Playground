#!/usr/bin/env python3
"""Do the unit tests actually test? Break the code on purpose, expect red.

For each deliberate bug below, copy backend/ to a scratch dir, apply the one
edit, run the unit tier, and require that it FAILS. A bug the suite does not
catch (or a pattern that no longer matches the source) is reported and the
script exits non-zero.

Not in CI: the patterns track source text, so they need updating when that
text moves. Run it after meaningful changes to tests/ or to the code under test:

    .venv/bin/python scripts/mutation_check.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")

# (file, original text, broken text, what real bug this simulates)
MUTATIONS = [
    ("ratelimit.py", 'forwarded.split(",")[-1]', 'forwarded.split(",")[0]', "trust the client-supplied first X-Forwarded-For entry"),
    ("ratelimit.py", "len(hits) >= self.max_requests", "len(hits) > self.max_requests", "off-by-one in the rate limit"),
    ("buildcache.py", 'entry["expires_at"] < time.time()', 'entry["expires_at"] > time.time()', "build tokens never expire"),
    ("main.py", 'editable["min"] <= override_value <= editable["max"]', "True", "override bounds not enforced"),
    ("main.py", 'method = "getblocktemplate"', 'method = "submitblock"', "/submit reaches a state-changing RPC"),
    ("main.py", "MAX_BODY_BYTES = 1024", "MAX_BODY_BYTES = 10**9", "request body cap removed"),
    ("main.py", 'raise HTTPException(status_code=503, detail="node unreachable")', "pass", "/health reports ok when the node is down"),
    ("decode.py", "ser_uint256(u)[::-1].hex()", "ser_uint256(u).hex()", "hashes shown in the wrong byte order"),
    ("decode.py", "value != baseline_value", "value == baseline_value", "diff highlighting inverted"),
    ("scenarios.py", '"expected_reject_reason": "bad-txns-nonfinal"', '"expected_reject_reason": "bad-txns-typo"', "catalog string with no source entry"),
    ("scenarios.py", '"field": "locktime"', '"field": "lock_time"', "editable field name typo"),
    ("sources.py", '"lines": [4193, 4195]', '"lines": [4195, 4193]', "reversed citation line range"),
    ("gen_sources.py", "(if|for|while|switch|catch|else)", "(while|switch)", "scanner mistakes if/for blocks for functions"),
]


def run_unit_tests(workdir: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=workdir, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    failures = 0
    for filename, original, broken, description in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "backend")
            shutil.copytree(BACKEND, work, ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".sources_cache", "fixtures.json"))
            path = os.path.join(work, filename)
            text = open(path).read()
            if original not in text:
                print(f"STALE   {description}: pattern not found in {filename} (update this script)")
                failures += 1
                continue
            open(path, "w").write(text.replace(original, broken, 1))
            if run_unit_tests(work):
                print(f"MISSED  {description}  [{filename}]")
                failures += 1
            else:
                print(f"caught  {description}")
    print(f"\n{len(MUTATIONS) - failures}/{len(MUTATIONS)} deliberate bugs caught")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
