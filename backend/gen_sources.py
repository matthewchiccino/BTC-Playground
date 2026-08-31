"""Scans Bitcoin Core's source tree at the pinned commit for every call site
that produces a validation/policy rejection string, and diffs the result
against the hand-maintained catalog in sources.py.

Two modes:
    python3 gen_sources.py scan   -- fetch + scan, write sources_candidates.json
    python3 gen_sources.py diff   -- compare that JSON against sources.py

This does NOT compile anything and does NOT need a local git clone -- it
enumerates files via GitHub's tree API and fetches each one individually via
raw.githubusercontent.com, the same way every source snippet in sources.py
was originally hand-verified during this project's build.

The function-name attribution is a heuristic (backward brace-counting to
find the enclosing block, then checking whether what encloses it looks like
a function signature or a control-flow block). It is not a C++ parser and
will occasionally get a name wrong or say "<unknown>" -- that's an accepted
tradeoff for not needing a compiled AST. Treat `scan` output as candidates
to review, not ground truth; `diff` is what surfaces what actually needs a
human look.
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from sources import COMMIT, SOURCES, _permalink

TREE_API = f"https://api.github.com/repos/bitcoin/bitcoin/git/trees/{COMMIT}?recursive=1"
RAW_URL = "https://raw.githubusercontent.com/bitcoin/bitcoin/{sha}/{path}"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".sources_cache", COMMIT)
CANDIDATES_PATH = os.path.join(os.path.dirname(__file__), "sources_candidates.json")

SRC_FILE_RE = re.compile(r"^src/.*\.(cpp|h)$")


# --- fetching ---------------------------------------------------------

def _cache_path(path: str) -> str:
    return os.path.join(CACHE_DIR, path.replace("/", "__"))


def list_source_files() -> list[str]:
    resp = requests.get(TREE_API, timeout=30)
    resp.raise_for_status()
    tree = resp.json()["tree"]
    return [e["path"] for e in tree if e["type"] == "blob" and SRC_FILE_RE.match(e["path"])]


def fetch_lines(path: str) -> list[str]:
    cache_file = _cache_path(path)
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return f.read().splitlines()

    resp = requests.get(RAW_URL.format(sha=COMMIT, path=path), timeout=15)
    resp.raise_for_status()
    text = resp.text
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(text)
    return text.splitlines()


# --- function-boundary heuristic --------------------------------------

CONTROL_KEYWORD_RE = re.compile(r"^\s*(if|for|while|switch|catch|else)\b")
FUNC_SIG_RE = re.compile(
    r"([A-Za-z_]\w*(?:::~?[A-Za-z_]\w*)?)\s*\([^;{}]*\)\s*"
    r"(?:const)?\s*(?:override)?\s*(?:noexcept)?\s*\{?\s*$"
)


LINE_COMMENT_RE = re.compile(r"//.*$")


def _strip_line_comment(line: str) -> str:
    return LINE_COMMENT_RE.sub("", line)


def _match_signature(text: str) -> str | None:
    """text is a single logical statement (comment-stripped). Return the
    function name if it looks like a function signature, None if it's a
    control-flow construct or unrecognizable."""
    stripped = text.strip()
    if not stripped or CONTROL_KEYWORD_RE.match(stripped):
        return None
    m = FUNC_SIG_RE.search(stripped)
    return m.group(1) if m else None


def find_enclosing_function(lines: list[str], match_idx: int) -> str:
    """lines is 0-indexed; match_idx is the 0-indexed line of the hit."""
    j = match_idx - 1
    scan_floor = max(0, match_idx - 400)

    while j >= scan_floor:
        depth = 0
        brace_line = None
        k = j
        while k >= scan_floor:
            for ch in reversed(lines[k]):
                if ch == "}":
                    depth += 1
                elif ch == "{":
                    depth -= 1
                    if depth < 0:
                        brace_line = k
                        break
            if brace_line is not None:
                break
            k -= 1

        if brace_line is None:
            return "<unknown>"

        brace_text = _strip_line_comment(lines[brace_line]).strip()

        # Case 1: the brace shares its line with real content (K&R style,
        # e.g. "if (...) {" or "void Foo(...) {") -- decide from that alone.
        if brace_text and brace_text != "{":
            name = _match_signature(brace_text)
            if name:
                return name
            if CONTROL_KEYWORD_RE.match(brace_text) or not brace_text.endswith("{"):
                j = brace_line - 1
                continue
            # falls through to Case 2 below for lines like "SomeClass {"
            # that don't cleanly resolve -- treat as not-a-function, widen.
            j = brace_line - 1
            continue

        # Case 2: bare "{" on its own line (Allman style, Core's usual
        # top-level function convention) -- the signature is above it.
        # Walk upward one logical line at a time; stop as soon as the line
        # we're about to add is itself the tail of a prior, unrelated
        # statement (ends in ; { or } once comments are stripped), or blank.
        sig_lines = []
        b = brace_line - 1
        while b >= scan_floor and len(sig_lines) < 6:
            prev = _strip_line_comment(lines[b])
            s = prev.strip()
            if not s:
                break
            if s.endswith((";", "{", "}")):
                break
            sig_lines.insert(0, prev)
            b -= 1
        sig_text = "\n".join(sig_lines)
        name = _match_signature(sig_text)
        if name:
            return name

        # Neither case resolved -- this brace wasn't a function. Widen
        # outward and keep searching above it.
        j = brace_line - 1

    return "<unknown>"


# --- idiom detection ----------------------------------------------------

INVALID_CALL_RE = re.compile(
    r"\.Invalid\(\s*[\w:]+::\w+\s*,\s*"
    r'(?:"((?:[^"\\]|\\.)*)"'
    r'|strprintf\(\s*"((?:[^"\\]|\\.)*)")'
)
REASON_ASSIGN_RE = re.compile(r'\breason\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')


def _clean_prefix(raw: str) -> str:
    prefix = raw.split("%", 1)[0]
    return re.sub(r"[\s(:,\-]+$", "", prefix)


BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/")


def scan_file(path: str, lines: list[str], candidates: dict):
    joined_window = 8  # lines to join, to catch multi-line calls

    for i, line in enumerate(lines):
        if ".Invalid(" in line:
            window = "\n".join(lines[i : i + joined_window])
            window = BLOCK_COMMENT_RE.sub("", window)  # e.g. /*reject_reason=*/
            m = INVALID_CALL_RE.search(window)
            if m:
                literal, fmt = m.group(1), m.group(2)
                idiom = "a"
                if literal is not None:
                    key = literal
                else:
                    idiom = "c"
                    key = _clean_prefix(fmt)
                func = find_enclosing_function(lines, i)
                candidates.setdefault(key, []).append(
                    {
                        "file": path,
                        "function": func,
                        "lines": [i + 1, i + 1],
                        "permalink": _permalink(path, i + 1, i + 1),
                        "idiom": idiom,
                    }
                )

        m2 = REASON_ASSIGN_RE.search(line)
        if m2:
            func = find_enclosing_function(lines, i)
            candidates.setdefault(m2.group(1), []).append(
                {
                    "file": path,
                    "function": func,
                    "lines": [i + 1, i + 1],
                    "permalink": _permalink(path, i + 1, i + 1),
                    "idiom": "b",
                }
            )


# --- CLI modes ------------------------------------------------------------

def cmd_scan(args):
    start = time.time()
    print(f"Listing src/**/*.{{cpp,h}} at {COMMIT[:10]}...")
    paths = list_source_files()
    if args.paths:
        prefixes = tuple(args.paths.split(","))
        paths = [p for p in paths if p.startswith(prefixes)]
    print(f"{len(paths)} files to scan ({args.workers} workers)...")

    candidates: dict[str, list] = {}
    cache_hits = 0
    fetched = 0

    def _job(path):
        was_cached = os.path.exists(_cache_path(path))
        lines = fetch_lines(path)
        return path, lines, was_cached

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_job, p): p for p in paths}
        for n, fut in enumerate(as_completed(futures), 1):
            path, lines, was_cached = fut.result()
            if was_cached:
                cache_hits += 1
            else:
                fetched += 1
            scan_file(path, lines, candidates)
            if n % 100 == 0:
                print(f"  {n}/{len(paths)}...")

    out = {
        "_meta": {
            "commit": COMMIT,
            "files_scanned": len(paths),
            "cache_hits": cache_hits,
            "fetched": fetched,
            "elapsed_s": round(time.time() - start, 1),
        },
        "candidates": dict(sorted(candidates.items())),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    total_matches = sum(len(v) for v in candidates.values())
    print(
        f"Done in {out['_meta']['elapsed_s']}s. {len(paths)} files, "
        f"{total_matches} matches, {len(candidates)} unique keys. "
        f"(cache hits: {cache_hits}, fetched: {fetched})"
    )
    print(f"Wrote {args.out}")


def cmd_diff(args):
    if not os.path.exists(args.candidates):
        print(f"No {args.candidates} found -- run `scan` first.", file=sys.stderr)
        sys.exit(1)
    with open(args.candidates, encoding="utf-8") as f:
        data = json.load(f)
    candidates = data["candidates"]

    bad = False
    for key, entry in SOURCES.items():
        cands = candidates.get(key, [])
        entry_file = entry["file"]
        entry_start, entry_end = entry["lines"]

        def _contained(c):
            return c["file"] == entry_file and entry_start <= c["lines"][0] <= entry_end

        if not cands:
            print(f"VANISHED      {key}")
            bad = True
            continue

        contained = [c for c in cands if _contained(c)]

        if len(cands) == 1:
            c = cands[0]
            if _contained(c):
                print(f"MATCH         {key}")
            elif c["file"] == entry_file:
                print(f"LINES MOVED   {key}  committed={entry_start}-{entry_end} candidate_line={c['lines'][0]}")
                bad = True
            else:
                print(f"SITE MISMATCH {key}  committed={entry_file}:{entry_start}-{entry_end} candidate={c['file']}:{c['lines'][0]} ({c['function']})")
                bad = True
        elif contained:
            print(f"MATCH+ALT({len(cands)}) {key}  -- committed site confirmed, plus other real candidate(s):")
            for c in cands:
                tag = "[current]" if _contained(c) else ""
                print(f"    - {c['file']}:{c['lines'][0]} {c['function']} {tag}")
        else:
            print(f"AMBIGUOUS({len(cands)}) {key}  -- none of these match the committed site, needs a look")
            for c in cands:
                print(f"    - {c['file']}:{c['lines'][0]} {c['function']}")
            if args.fail_on_ambiguous:
                bad = True

    known_keys = set(SOURCES)
    new_keys = [k for k in candidates if k not in known_keys]
    print(f"\nNew reject strings not yet cataloged: {len(new_keys)} (see {args.candidates} for the list)")

    sys.exit(1 if bad else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_scan = sub.add_parser("scan", help="scan Core's source tree, write candidates JSON")
    p_scan.add_argument("--out", default=CANDIDATES_PATH)
    p_scan.add_argument("--paths", default=None, help="comma-separated path prefixes to restrict the scan to")
    p_scan.add_argument("--workers", type=int, default=16)
    p_scan.set_defaults(func=cmd_scan)

    p_diff = sub.add_parser("diff", help="diff candidates JSON against sources.py")
    p_diff.add_argument("--candidates", default=CANDIDATES_PATH)
    p_diff.add_argument("--fail-on-ambiguous", action="store_true")
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
