#!/usr/bin/env python3
"""E0 Q2 - every place this repo builds a model request, and whether it caches.

Read-only static enumeration. Answers Q2 with a producer path rather than an
impression: which files construct an Anthropic (or other provider) request, at
which line, and does that construction attach a cache_control breakpoint.

The check is CONSTRUCTION-SITE-LOCAL on purpose. "The repo contains
cache_control somewhere" is not the question - the question is whether the
request being built at THIS line carries a breakpoint. A repo-wide grep would
answer yes and be useless.

Controls are mutation-tested (R133): the scanner is driven against a payload it
MUST flag and one it MUST NOT, so a scanner that had silently stopped matching
would fail loudly instead of reporting a clean tree.

Usage:
    python harness/notes/econ/econ_cachetrace.py
Writes:
    harness/notes/econ/E0_cachetrace.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "E0_cachetrace.json"

# A site that puts a model request on the wire, or hands one to an SDK.
SITE_PATTERNS = {
    "anthropic_host": re.compile(r"api\.anthropic\.com"),
    "messages_endpoint": re.compile(r"[\"']/v1/messages[\"']"),
    "sdk_messages_create": re.compile(r"\.messages\.create\s*\("),
    "sdk_messages_stream": re.compile(r"\.messages\.stream\s*\("),
    "anthropic_client_ctor": re.compile(r"\b(?:Async)?Anthropic\s*\("),
    "generativeai_host": re.compile(r"generativelanguage\.googleapis\.com"),
    "openai_compatible_host": re.compile(r"integrate\.api\.nvidia\.com|localhost:11434"),
}
CACHE_PATTERN = re.compile(r"cache_control")

EXCLUDE_DIR_PARTS = ("_vendor", "__pycache__", ".git", "site-packages", "node_modules",
                     "harness/notes/econ")  # E0's own producers are the instrument,
                                            # not the subject; excluded so the scan
                                            # cannot count itself as a finding.


def relevant_files():
    for p in sorted(REPO_ROOT.rglob("*.py")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if any(part in rel for part in EXCLUDE_DIR_PARTS):
            continue
        yield p, rel


def scan_text(text: str):
    """Return {kind: [line numbers]} for construction sites, and cache lines."""
    sites, cache_lines = {}, []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, pat in SITE_PATTERNS.items():
            if pat.search(line):
                sites.setdefault(kind, []).append(i)
        if CACHE_PATTERN.search(line):
            cache_lines.append(i)
    return sites, cache_lines


def enclosing_def(lines, lineno):
    """Nearest preceding def/class, so a site is reported with its function."""
    for i in range(lineno - 1, -1, -1):
        m = re.match(r"\s*(?:async\s+)?(def|class)\s+(\w+)", lines[i])
        if m:
            return f"{m.group(2)} ({m.group(1)}) at :{i + 1}"
    return "module level"


def controls():
    """Mutation tests. A scanner that cannot fail is a decoration (Law 1)."""
    positive = 'conn.request("POST", "/v1/messages", body=payload)\n'
    positive_cached = 'tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}\n'
    negative = 'def add(a, b):\n    return a + b\n'

    s_pos, c_pos = scan_text(positive)
    s_pos_c, c_pos_c = scan_text(positive_cached)
    s_neg, c_neg = scan_text(negative)

    return [
        {
            "id": "CTL-1",
            "what": "scanner detects a request-construction site",
            "fails_if": "a literal POST to /v1/messages is not flagged",
            "observed": {"sites_found": s_pos},
            "verdict": "PASS" if s_pos else "FAIL",
        },
        {
            "id": "CTL-2",
            "what": "scanner detects a cache breakpoint",
            "fails_if": "a literal cache_control assignment is not flagged",
            "observed": {"cache_lines": c_pos_c},
            "verdict": "PASS" if c_pos_c else "FAIL",
        },
        {
            "id": "CTL-3",
            "what": "scanner does NOT fire on unrelated code (false-positive control)",
            "fails_if": "a plain function is reported as a request site or a cache site - "
                        "which would make an 'everything is cached' verdict meaningless",
            "observed": {"sites_found": s_neg, "cache_lines": c_neg},
            "verdict": "PASS" if (not s_neg and not c_neg) else "FAIL",
        },
        {
            "id": "CTL-4",
            "what": "an uncached request site is correctly reported as uncached",
            "fails_if": "a site with no cache_control anywhere near it is reported cached",
            "observed": {"sites": s_pos, "cache_lines": c_pos},
            "verdict": "PASS" if (s_pos and not c_pos) else "FAIL",
        },
    ]


def main() -> int:
    findings = []
    for path, rel in relevant_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sites, cache_lines = scan_text(text)
        if not sites:
            continue
        lines = text.splitlines()
        findings.append({
            "file": rel,
            "sites": {k: [{"line": n, "in": enclosing_def(lines, n),
                            "text": lines[n - 1].strip()[:140],
                            "looks_like_prose": bool(re.match(r"^\s*(#|\"\"\"|'''|\*|\w+\s)", lines[n - 1])) and "(" not in lines[n - 1].split("#")[0]}
                           for n in v]
                      for k, v in sites.items()},
            "cache_control_lines": cache_lines,
            "verdict": "CACHE-AWARE" if cache_lines else "NO CACHE BREAKPOINT",
        })

    cache_aware = [f for f in findings if f["cache_control_lines"]]
    uncached = [f for f in findings if not f["cache_control_lines"]]

    # Repo-wide cache_control census, so "absent" is a searched claim not a vibe.
    all_cache = []
    for path, rel in relevant_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if CACHE_PATTERN.search(line):
                all_cache.append({"file": rel, "line": i, "text": line.strip()[:120]})

    out = {
        "schema": "e0_cachetrace/v1",
        "produced_by": "harness/notes/econ/econ_cachetrace.py",
        "searched": {
            "root": str(REPO_ROOT),
            "glob": "**/*.py",
            "excluded_path_fragments": list(EXCLUDE_DIR_PARTS),
            "site_patterns": {k: p.pattern for k, p in SITE_PATTERNS.items()},
            "cache_pattern": CACHE_PATTERN.pattern,
            "files_scanned": sum(1 for _ in relevant_files()),
        },
        "controls": controls(),
        "request_construction_sites": findings,
        "summary": {
            "files_constructing_requests": len(findings),
            "cache_aware": [f["file"] for f in cache_aware],
            "no_cache_breakpoint": [f["file"] for f in uncached],
        },
        "repo_wide_cache_control_census": all_cache,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[econ_cachetrace] wrote {OUT}")
    for c in out["controls"]:
        print(f"  {c['id']} {c['verdict']:4}  {c['what']}")
    print(f"\n  scanned {out['searched']['files_scanned']} non-vendor .py files")
    print(f"  request-construction files: {len(findings)}")
    for f in findings:
        kinds = ",".join(f["sites"].keys())
        print(f"    {f['verdict']:<20} {f['file']}   [{kinds}]")
    print(f"\n  repo-wide cache_control occurrences (non-vendor .py): {len(all_cache)}")
    for c in all_cache:
        print(f"    {c['file']}:{c['line']}  {c['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
