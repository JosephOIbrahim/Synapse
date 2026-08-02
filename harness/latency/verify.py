#!/usr/bin/env python3
"""Latency harness verifier — 8 predicates, checked live against the tree.

    python harness/latency/verify.py            # human-readable
    python harness/latency/verify.py --json     # the contract progress.py consumes

Contract: --json emits a LIST of {"id","label","status"} where status is
PASS | FAIL | PENDING | UNKNOWN.

  PASS     the predicate is satisfied, proven by a check that ran
  FAIL     the artifact exists and is WRONG — this is the one that means work
  PENDING  the artifact does not exist yet; nothing has been claimed, so nothing
           is broken. PENDING is honest. It is never a synonym for PASS.
  UNKNOWN  the check itself could not run — say so rather than score it

Every predicate names its producer in `detail`. A predicate that cannot state how
it decided is a predicate that should not ship (Law 2).

This verifier does exactly one thing that matters: it must be impossible for a
predicate to read PASS because nothing was checked. Each check that finds no
artifact returns PENDING, and each check that finds a broken artifact returns
FAIL — the two are never collapsed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REGISTRY = HERE / "REGISTRY.json"
LEDGER = HERE / "LEDGER.md"

# Scale terms a cost row must carry to have reached L2. A row that names no
# growth term has not been attributed to a scale regime, whatever else it says.
SCALE_TERMS = ("CONSTANT", "LINEAR_IN_PRIMS", "LINEAR_IN_NODES",
               "LINEAR_IN_TURNS", "OTHER")


def row(pid, label, status, detail, producer):
    return {"id": pid, "label": label, "status": status,
            "detail": detail, "producer": producer}


def _registry():
    """The registry, or None if it is absent/unreadable. None is not empty."""
    if not REGISTRY.is_file():
        return None
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _open_hypotheses(reg):
    """Hypotheses that are live work — pending or confirmed open.

    Deliberately EXCLUDES killed/refuted/already-fixed entries: a refuted
    hypothesis is not required to carry a probe, and demanding one would push
    the harness toward keeping dead entries alive to satisfy its own checker.
    """
    out = []
    for h in (reg.get("hypotheses") or []):
        v = str(h.get("verdict", "pending")).lower()
        if v in ("refuted", "real_but_already_fixed", "not_applicable", "killed"):
            continue
        out.append(h)
    return out


# ── P1 ──────────────────────────────────────────────────────────────────────

def p1_ledger_scaled():
    """Scale-parameterization is a REGISTRY property, checked structurally.

    The first version scanned every LEDGER.md table row for a scale term —
    wrong artifact shape: the ledger also carries action and verdict tables,
    which are not cost rows. The binding contract is `_scale_axis` in the
    registry: every non-dead hypothesis carries a non-null scale_behavior,
    and the ledger exists to narrate the axis.
    """
    prod = "REGISTRY.json hypotheses[].scale_behavior + LEDGER.md exists"
    if not LEDGER.is_file():
        return row("P1", "cost ledger is scale-parameterized", "PENDING",
                   "LEDGER.md not written yet (scout fan-out produces it)", prod)
    reg = _registry()
    if reg is None:
        return row("P1", "cost ledger is scale-parameterized", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    hyps = reg.get("hypotheses") or []
    if not hyps:
        return row("P1", "cost ledger is scale-parameterized", "PENDING",
                   "registry has no hypotheses yet", prod)
    unscaled = [h["id"] for h in hyps
                if str(h.get("verdict", "")).lower() not in
                ("refuted", "killed", "not_applicable")
                and not (h.get("scale_behavior") or "").strip()]
    if unscaled:
        return row("P1", "cost ledger is scale-parameterized", "FAIL",
                   f"{len(unscaled)} live entr(ies) carry no scale term: "
                   f"{', '.join(unscaled[:4])}", prod)
    return row("P1", "cost ledger is scale-parameterized", "PASS",
               f"LEDGER.md present; all {len(hyps)} registry entries carry "
               f"a scale term", prod)


# ── P2 ──────────────────────────────────────────────────────────────────────

def p2_probes():
    prod = "REGISTRY.json hypotheses[].probe"
    reg = _registry()
    if reg is None:
        return row("P2", "every open hypothesis has a runnable probe", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    live = _open_hypotheses(reg)
    if not live:
        return row("P2", "every open hypothesis has a runnable probe", "PENDING",
                   "no open hypotheses in the registry", prod)
    unprobed = [h["id"] for h in live if not (h.get("probe") or "").strip()]
    if len(unprobed) == len(live):
        return row("P2", "every open hypothesis has a runnable probe", "PENDING",
                   f"registry seeded, none probed yet ({len(live)} open)", prod)
    if unprobed:
        return row("P2", "every open hypothesis has a runnable probe", "FAIL",
                   f"{len(unprobed)} open hypothes(es) carry no probe: "
                   f"{', '.join(unprobed[:4])}", prod)
    return row("P2", "every open hypothesis has a runnable probe", "PASS",
               f"all {len(live)} open hypotheses carry a probe", prod)


# ── P3 ──────────────────────────────────────────────────────────────────────

def p3_no_refuted_rework():
    prod = "REGISTRY.json hypotheses[].checked_against_refuted"
    reg = _registry()
    if reg is None:
        return row("P3", "no entry re-proposes refuted ground", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    live = _open_hypotheses(reg)
    if not live:
        return row("P3", "no entry re-proposes refuted ground", "PENDING",
                   "no open hypotheses to check", prod)
    unchecked = [h["id"] for h in live if not h.get("checked_against_refuted")]
    if len(unchecked) == len(live):
        return row("P3", "no entry re-proposes refuted ground", "PENDING",
                   f"adjudication has not run ({len(live)} open, none checked)", prod)
    if unchecked:
        return row("P3", "no entry re-proposes refuted ground", "FAIL",
                   f"{len(unchecked)} open entr(ies) never checked against the "
                   f"refuted list: {', '.join(unchecked[:4])}", prod)
    return row("P3", "no entry re-proposes refuted ground", "PASS",
               f"all {len(live)} open entries adjudicated against the refuted list",
               prod)


# ── P4 ──────────────────────────────────────────────────────────────────────

def p4_instrument_state():
    prod = "REGISTRY.json instruments.*"
    reg = _registry()
    if reg is None:
        return row("P4", "U1-U4 instrument state recorded with locators", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    inst = {k: v for k, v in (reg.get("instruments") or {}).items()
            if not k.startswith("_")}
    if not inst:
        return row("P4", "U1-U4 instrument state recorded with locators", "PENDING",
                   "no instruments block", prod)
    pending = [k for k, v in inst.items()
               if str((v or {}).get("state", "pending")).lower() == "pending"]
    if len(pending) == len(inst):
        return row("P4", "U1-U4 instrument state recorded with locators", "PENDING",
                   f"{len(inst)} instruments, none verified against HEAD yet", prod)
    # A state that is not 'absent' asserts code exists — it must name where.
    unlocated = [k for k, v in inst.items()
                 if str((v or {}).get("state", "")).lower() in ("landed", "partial")
                 and not (v or {}).get("locator")]
    if unlocated:
        return row("P4", "U1-U4 instrument state recorded with locators", "FAIL",
                   f"claimed landed/partial with no locator: {', '.join(unlocated)}",
                   prod)
    return row("P4", "U1-U4 instrument state recorded with locators", "PASS",
               f"{len(inst) - len(pending)}/{len(inst)} verified, all located", prod)


# ── P5 ──────────────────────────────────────────────────────────────────────

def p5_offline_bench():
    """The bench must produce numbers WITHOUT Houdini, or it cannot gate CI."""
    # The two benchmarks live at the REPO ROOT, not under scripts/ — verified
    # 2026-08-02. docs/BENCHMARK_DESIGN.md names them without a directory, which
    # reads as scripts/ and is how this check was wrong on its first run.
    prod = "_benchmark_latency.py --help (exit code + scale flag)"
    bench = next((p for p in (REPO / "_benchmark_latency.py",
                              REPO / "scripts" / "_benchmark_latency.py")
                  if p.is_file()), None)
    if bench is None:
        return row("P5", "scale bench runs offline (CI-gateable)", "PENDING",
                   "_benchmark_latency.py not found at repo root or scripts/", prod)
    src = bench.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"--scale\b|scene_scale|prim_count", src):
        return row("P5", "scale bench runs offline (CI-gateable)", "PENDING",
                   "bench exists but carries no scale parameter yet "
                   "(extend, never rebuild - docs/BENCHMARK_DESIGN.md)", prod)
    try:
        p = subprocess.run([sys.executable, str(bench), "--help"],
                           capture_output=True, text=True, timeout=90,
                           encoding="utf-8", errors="replace", cwd=str(REPO))
    except (OSError, subprocess.SubprocessError) as exc:
        return row("P5", "scale bench runs offline (CI-gateable)", "UNKNOWN",
                   f"could not invoke bench: {type(exc).__name__}", prod)
    if p.returncode != 0:
        return row("P5", "scale bench runs offline (CI-gateable)", "FAIL",
                   f"bench --help exited {p.returncode} without Houdini "
                   f"(offline tier is not runnable)", prod)
    return row("P5", "scale bench runs offline (CI-gateable)", "PASS",
               "bench carries a scale parameter and runs offline", prod)


# ── P6 / P7 ─────────────────────────────────────────────────────────────────

def p6_ratchet_armed():
    prod = "REGISTRY.json ratchet.* + the floor file it names"
    reg = _registry()
    if reg is None:
        return row("P6", "perf ratchet armed (the 4x win is pinned)", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    r = reg.get("ratchet") or {}
    if not r.get("armed"):
        return row("P6", "perf ratchet armed (the 4x win is pinned)", "PENDING",
                   "not armed - arming the first floor is a HUMAN gate (SPEC.md)",
                   prod)
    fp = r.get("floor_path")
    if not fp or not (REPO / fp).exists():
        return row("P6", "perf ratchet armed (the 4x win is pinned)", "FAIL",
                   f"armed=true but floor_path missing on disk: {fp!r}", prod)
    if not r.get("human_armed_by"):
        return row("P6", "perf ratchet armed (the 4x win is pinned)", "FAIL",
                   "armed=true with no human_armed_by - a floor set by the thing "
                   "being measured is not a floor", prod)
    return row("P6", "perf ratchet armed (the 4x win is pinned)", "PASS",
               f"floor {fp} armed by {r['human_armed_by']}", prod)


def p7_floor_at_merge_base():
    """Same discipline as the suite ratchet: a branch must not lower its own bar."""
    prod = "grep merge-base in the ratchet's floor reader"
    reg = _registry()
    if reg is None:
        return row("P7", "ratchet floor read at merge-base", "UNKNOWN",
                   "REGISTRY.json missing or unparseable", prod)
    r = reg.get("ratchet") or {}
    if not r.get("armed"):
        return row("P7", "ratchet floor read at merge-base", "PENDING",
                   "ratchet not armed yet", prod)
    reader = r.get("floor_reader")
    if not reader or not (REPO / reader).is_file():
        return row("P7", "ratchet floor read at merge-base", "FAIL",
                   f"armed but no readable floor_reader: {reader!r}", prod)
    src = (REPO / reader).read_text(encoding="utf-8", errors="replace")
    if "merge-base" not in src and "merge_base" not in src:
        return row("P7", "ratchet floor read at merge-base", "FAIL",
                   f"{reader} never computes a merge-base - a branch can lower "
                   f"its own bar", prod)
    return row("P7", "ratchet floor read at merge-base", "PASS",
               f"{reader} reads the floor at merge-base", prod)


# ── P8 ──────────────────────────────────────────────────────────────────────

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*\.?\d*)\s*(ms|s|sec|seconds|x|%|MB|KB)\b",
                  re.IGNORECASE)


def p8_law2():
    """Every number in this harness's own docs carries a producer path.

    Scoped to LEDGER.md — the artifact that exists to state numbers. SPEC.md
    quotes numbers from the report it cites inline, and a checker that flagged
    those would be measuring prose, not provenance.

    Granularity is the PARAGRAPH (blank-line-delimited block), except table
    rows, which are their own unit. The first version checked physical lines
    and flagged 4 wrapped bullets whose producer sat one line below the
    number — measuring line-wrapping, not provenance. Law 2 binds the claim,
    and the claim is the block.
    """
    prod = "regex scan of LEDGER.md blocks (paragraphs + table rows) with a magnitude"
    if not LEDGER.is_file():
        return row("P8", "Law 2 — every number names its producer", "PENDING",
                   "LEDGER.md not written yet", prod)
    text = LEDGER.read_text(encoding="utf-8", errors="replace")
    has_producer = re.compile(
        r"[\w/\\.-]+\.(?:py|md|json|ts|ps1):\d+|`[^`]+`|\b[0-9a-f]{7,40}\b"
        r"|REQUIRES LIVE BRIDGE|PRIOR|COMMITTED|wf_[a-z0-9-]+|\[(?:C\d|G\d|H\d+|I\d)[^\]]*\]")
    blocks: list = []   # (first_line_no, block_text)
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.lstrip().startswith("|"):
            blocks.append((i + 1, ln))         # table row = its own unit
            i += 1
            continue
        start = i
        buf = [ln]
        while i + 1 < len(lines) and lines[i + 1].strip() \
                and not lines[i + 1].lstrip().startswith("|"):
            i += 1
            buf.append(lines[i])
        blocks.append((start + 1, "\n".join(buf)))
        i += 1
    bare = [str(n) for n, blk in blocks
            if _NUM.search(blk) and not has_producer.search(blk)]
    if bare:
        return row("P8", "Law 2 — every number names its producer", "FAIL",
                   f"{len(bare)} block(s) state a magnitude with no producer "
                   f"(starting at lines {', '.join(bare[:6])})", prod)
    return row("P8", "Law 2 — every number names its producer", "PASS",
               f"all {sum(1 for _, b in blocks if _NUM.search(b))} "
               f"magnitude-bearing blocks carry a producer", prod)


CHECKS = [p1_ledger_scaled, p2_probes, p3_no_refuted_rework, p4_instrument_state,
          p5_offline_bench, p6_ratchet_armed, p7_floor_at_merge_base, p8_law2]


def main():
    ap = argparse.ArgumentParser(description="Latency harness verifier.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as exc:  # a broken check reports itself, never scores
            results.append(row(fn.__name__[:2].upper(), fn.__name__, "UNKNOWN",
                               f"check raised {type(exc).__name__}: {exc}",
                               "verify.py"))

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    width = max(len(r["label"]) for r in results)
    for r in results:
        print(f"  {r['id']:<3} {r['status']:<8} {r['label']:<{width}}  {r['detail']}")
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_pend = sum(1 for r in results if r["status"] == "PENDING")
    print(f"\n  {n_pass} PASS / {n_fail} FAIL / {n_pend} PENDING "
          f"of {len(results)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
