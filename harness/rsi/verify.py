#!/usr/bin/env python3
"""RSI closure harness — verify.py

The bar. Nine acceptance predicates from SPEC.md, each checked headlessly (no
`hou`, no live bridge, no network). Every PASS comes from an actual check; this
file never returns PASS without evidence. Statuses: PASS / FAIL / PENDING.

  P1  registry completeness    every RSI mechanism in the tree is registered
  P2  rung honesty             every claimed rung carries evidence
  P3  no rung skipping         rungs_proven is a contiguous prefix from L0
  P4  signal-before-loop       no loop at L3+ whose L1 is unproven  (+ LIVE grep)
  P5  fingerprinted evidence   log-based L2 claims name their test-exclusion
  P6  benefit is not activity  L5 claims carry before/after, not activity counts
  P7  reversal exists          every loop at L3+ documents a rollback path
  P8  human gate intact        no loop at L4+ without human_ratified
  P9  reconciliation           both prior efforts are represented, once each

P4 is deliberately self-updating. It does not read a human-maintained status
field to decide whether the router's reward signal is honest — it greps
router.py. The day someone actually passes `success` at those eight call sites,
this predicate changes its own answer. A bar that can only be advanced by
editing the bar is not a bar.

Usage:
  python harness/rsi/verify.py            # table + exit non-zero on FAIL
  python harness/rsi/verify.py --count    # print FAIL count only
  python harness/rsi/verify.py --json     # machine-readable (progress.py contract)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RSI = Path(__file__).resolve().parent
REGISTRY = RSI / "REGISTRY.json"

ROUTER = REPO / "python" / "synapse" / "routing" / "router.py"

LADDER = ["L0", "L1", "L2", "L3", "L4", "L5"]
IDX = {r: i for i, r in enumerate(LADDER)}

# The two prior efforts this harness reconciles (SPEC "Relationship to prior work").
JUNE_LINES = {"R", "O", "S", "F", "E", "C"}
JULY_MECHANISMS = {"A1", "A2", "A3"}

# An L5 BENEFICIAL claim may not rest on any of these. They measure that the
# machinery ran, not that a task got better — the harness-updating-is-not-
# harness-benefit distinction, encoded.
ACTIVITY_WORDS = [
    "recommendation", "recommendations generated", "epoch", "epochs closed",
    "cycle", "cycles run", "memories written", "items recorded", "records",
    "promotions", "count of", "number of runs", "invocations", "calls made",
]

# Files that look like self-improvement machinery. A hit here that no registry
# entry claims is a P1 failure — the registry has drifted behind the code.
RSI_FILE_PATTERNS = [
    r"adaptation\.py$", r"learning\.py$", r"evolution\.py$",
    r"self_?tune", r"feedback", r"reinforce", r"autotune",
]
RSI_CONTENT_PATTERNS = [
    r"\bdef\s+\w*adapt\w*\s*\(", r"\bdef\s+\w*promote\w*\s*\(",
    r"_session_fast_paths", r"FAST_PATH_PROMOTION_THRESHOLD",
    r"\bdef\s+record_outcome\s*\(", r"\bdef\s+evolve_to_\w+\s*\(",
]
SWEEP_ROOTS = ["python", "shared"]
SWEEP_SKIP = {"_vendor", "__pycache__", "tests", "test", ".git", "node_modules"}

PASS, FAIL, PENDING = "PASS", "FAIL", "PENDING"


# ── helpers ─────────────────────────────────────────────────────────────────

def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_registry():
    raw = _read(REGISTRY)
    if raw is None:
        return None, "REGISTRY.json unreadable"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"REGISTRY.json is not valid JSON: {e}"
    loops = data.get("loops")
    if not isinstance(loops, list):
        return None, "REGISTRY.json has no 'loops' list"
    return data, None


def _proven(loop):
    return [r for r in (loop.get("rungs_proven") or []) if r in IDX]


def _top_rung(loop):
    """Highest proven rung index, or -1 if none."""
    pr = _proven(loop)
    return max((IDX[r] for r in pr), default=-1)


# ── the live signal check (what makes P4 self-updating) ─────────────────────

def router_signal_is_constant():
    """Does router.py still hand EpochAdapter a hardcoded success value?

    Returns (is_constant, detail). is_constant=None means 'cannot tell' —
    router.py absent or unparseable — which is PENDING, never a silent PASS.

    Method: find every `self._record_metric(...)` CALL (excluding the `def`),
    and check whether any passes a third argument or an explicit success=.
    """
    src = _read(ROUTER)
    if src is None:
        return None, f"{ROUTER.relative_to(REPO)} unreadable"

    calls, honest = [], []
    for m in re.finditer(r"_record_metric\s*\(", src):
        line_no = src.count("\n", 0, m.start()) + 1
        # Skip the definition itself. The prefix on a def line is "    def "
        # — note .strip() removes the trailing space, so a startswith("def ")
        # test silently fails here and counts the signature as a call site.
        line_start = src.rfind("\n", 0, m.start()) + 1
        if re.match(r"^\s*(async\s+)?def\s+$", src[line_start:m.start()]):
            continue
        # Extract the argument list with simple paren balancing.
        i, depth, args = m.end(), 1, ""
        while i < len(src) and depth:
            ch = src[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            args += ch
            i += 1
        calls.append(line_no)
        # Split on top-level commas only.
        parts, d, cur = [], 0, ""
        for ch in args:
            if ch in "([{":
                d += 1
            elif ch in ")]}":
                d -= 1
            if ch == "," and d == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        if len(parts) >= 3 or any("success" in p for p in parts):
            honest.append(line_no)

    if not calls:
        return None, "no _record_metric call sites found (module may have moved)"
    if honest:
        return False, (f"{len(honest)}/{len(calls)} call sites pass an outcome "
                       f"(lines {', '.join(map(str, honest[:8]))})")
    return True, (f"all {len(calls)} call sites pass only (tier, latency) — "
                  f"success defaults True (lines {', '.join(map(str, calls[:8]))})")


# ── predicates ──────────────────────────────────────────────────────────────

def p1(data):
    """Every RSI-looking surface in the tree is claimed by some registry entry."""
    registered = set()
    for loop in data["loops"]:
        for s in loop.get("surfaces") or []:
            registered.add(s.replace("\\", "/").rstrip("/"))

    def claimed(rel):
        return any(rel == r or rel.startswith(r.rstrip("/") + "/") or r.startswith(rel)
                   for r in registered)

    unclaimed = []
    for root in SWEEP_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(REPO).as_posix()
            if any(part in SWEEP_SKIP for part in p.parts):
                continue
            name_hit = any(re.search(pat, rel) for pat in RSI_FILE_PATTERNS)
            content_hit = False
            if not name_hit:
                txt = _read(p)
                if txt and any(re.search(pat, txt) for pat in RSI_CONTENT_PATTERNS):
                    content_hit = True
            if (name_hit or content_hit) and not claimed(rel):
                unclaimed.append(rel)

    if not unclaimed:
        return PASS, f"sweep of {'/'.join(SWEEP_ROOTS)} found no unregistered RSI surface"
    return FAIL, f"{len(unclaimed)} unregistered RSI surface(s): {', '.join(sorted(unclaimed)[:4])}"


def p2(data):
    bad = []
    for loop in data["loops"]:
        ev = loop.get("evidence") or {}
        for rung in _proven(loop):
            if not ev.get(rung):
                bad.append(f"{loop['id']}:{rung}")
    if not bad:
        n = sum(len(_proven(l)) for l in data["loops"])
        return PASS, f"all {n} proven rung(s) carry evidence"
    return FAIL, f"rung claimed without evidence: {', '.join(bad[:6])}"


def p3(data):
    bad = []
    for loop in data["loops"]:
        pr = set(_proven(loop))
        top = _top_rung(loop)
        if top < 0:
            continue
        expected = set(LADDER[:top + 1])
        if pr != expected:
            bad.append(f"{loop['id']} has {sorted(pr)} not {sorted(expected)}")
    if not bad:
        return PASS, "every rungs_proven is a contiguous prefix from L0"
    return FAIL, "; ".join(bad[:3])


def p4(data):
    """Structural rule + the live grep that lets this predicate update itself."""
    violations = [
        loop["id"] for loop in data["loops"]
        if _top_rung(loop) >= IDX["L3"] and "L1" not in _proven(loop)
    ]
    if violations:
        return FAIL, f"loop(s) at L3+ with L1 unproven: {', '.join(violations)}"

    constant, detail = router_signal_is_constant()
    a1 = next((l for l in data["loops"] if l["id"] == "A1"), None)
    if a1 is None:
        return FAIL, "loop A1 missing from registry; cannot cross-check the live signal"
    a1_claims_honest = "L1" in _proven(a1)

    if constant is None:
        return PENDING, f"structural rule holds; live check unavailable — {detail}"
    if constant and a1_claims_honest:
        return FAIL, f"registry claims A1 is HONEST but the code disagrees — {detail}"
    if not constant and not a1_claims_honest:
        return FAIL, (f"the router signal now carries an outcome but A1 still records L1 "
                      f"as unproven — registry is stale. {detail}")
    state = "still constant" if constant else "now carries an outcome"
    return PASS, f"structural rule holds; live signal {state} and registry agrees — {detail}"


def p5(data):
    """An L2 claim resting on the shared log must name its test-exclusion.

    The production log holds pytest-authored records; a raw log grep is not
    evidence of production execution.
    """
    suspect = []
    for loop in data["loops"]:
        for e in (loop.get("evidence") or {}).get("L2", []) or []:
            s = str(e).lower()
            if "synapse.log" in s or "logs/" in s:
                if not re.search(r"fingerprint|exclu|pytest|test-only|negative control|control", s):
                    suspect.append(f"{loop['id']}")
    if not suspect:
        return PASS, "no log-based L2 claim lacks a test-exclusion"
    return FAIL, f"unfingerprinted log evidence: {', '.join(sorted(set(suspect)))}"


def p6(data):
    bad = []
    for loop in data["loops"]:
        if IDX["L5"] > _top_rung(loop):
            continue
        b = loop.get("benefit")
        if not isinstance(b, dict) or b.get("before") is None or b.get("after") is None:
            bad.append(f"{loop['id']}: L5 without before/after")
            continue
        metric = str(b.get("metric", "")).lower()
        if any(w in metric for w in ACTIVITY_WORDS):
            bad.append(f"{loop['id']}: '{b.get('metric')}' is an activity count")
    if not bad:
        n = sum(1 for l in data["loops"] if _top_rung(l) >= IDX["L5"])
        return PASS, (f"{n} loop(s) at L5, each with a before/after task metric"
                      if n else "no L5 claims to check (0 loops beneficial)")
    return FAIL, "; ".join(bad[:3])


def p7(data):
    bad = []
    for loop in data["loops"]:
        if _top_rung(loop) < IDX["L3"]:
            continue
        rev = loop.get("reversal")
        if not isinstance(rev, dict) or not rev.get("rollback"):
            bad.append(loop["id"])
    if not bad:
        n = sum(1 for l in data["loops"] if _top_rung(l) >= IDX["L3"])
        return PASS, (f"all {n} loop(s) at L3+ document a rollback path"
                      if n else "no loop is at L3+ yet (nothing consumed)")
    return FAIL, f"loop(s) at L3+ with no rollback path: {', '.join(bad)}"


def p8(data):
    bad = [l["id"] for l in data["loops"]
           if _top_rung(l) >= IDX["L4"] and not l.get("human_ratified")]
    if not bad:
        return PASS, "no loop sits at L4+ without a human ratification flip"
    return FAIL, f"unratified loop(s) past the runaway boundary: {', '.join(bad)}"


def p9(data):
    ids = [l.get("id") for l in data["loops"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    missing = (JUNE_LINES | JULY_MECHANISMS) - set(ids)
    if not dupes and not missing:
        return PASS, f"all {len(JUNE_LINES)} June lines + {len(JULY_MECHANISMS)} July mechanisms present, once each"
    parts = []
    if missing:
        parts.append(f"missing: {', '.join(sorted(missing))}")
    if dupes:
        parts.append(f"duplicated: {', '.join(sorted(dupes))}")
    return FAIL, "; ".join(parts)


PREDICATES = [
    ("P1", "registry completeness", p1),
    ("P2", "rung honesty (evidence present)", p2),
    ("P3", "no rung skipping", p3),
    ("P4", "signal-before-loop (live)", p4),
    ("P5", "log evidence fingerprinted", p5),
    ("P6", "benefit is not activity", p6),
    ("P7", "reversal exists at L3+", p7),
    ("P8", "human gate intact at L4+", p8),
    ("P9", "two-effort reconciliation", p9),
]


def run_all():
    data, err = load_registry()
    if data is None:
        return [{"id": pid, "label": label, "status": FAIL, "reason": err}
                for pid, label, _ in PREDICATES]
    out = []
    for pid, label, fn in PREDICATES:
        try:
            status, reason = fn(data)
        except Exception as e:  # a predicate that raises is a FAIL, never a skip
            status, reason = FAIL, f"verifier raised: {type(e).__name__}: {e}"
        out.append({"id": pid, "label": label, "status": status, "reason": reason})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print FAIL count only")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args()

    results = run_all()
    fail = sum(1 for r in results if r["status"] == FAIL)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.count:
        print(fail)
    else:
        for r in results:
            print(f"{r['id']:<4} {r['status']:<8} {r['label']:<34} — {r['reason']}")
        n_pass = sum(1 for r in results if r["status"] == PASS)
        n_pend = sum(1 for r in results if r["status"] == PENDING)
        print(f"\n{n_pass} PASS / {fail} FAIL / {n_pend} PENDING")

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
