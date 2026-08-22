#!/usr/bin/env python3
"""digest.py -- turn the QUARTERMASTER packet into a per-role briefing.

The packet is the durable record and it is large. Injecting it whole into
`args.supply` would put ~27KB in front of all eight leg prompts -- more input
than the duplicated work it exists to prevent. That is not a saving, it is a
reshuffle.

So: extract only what a leg ACTS ON, sliced by role. An M1 forge does not need
the §4 port surface; an M2 forge does not need the ephemeral-store census.
Every field kept is one a leg would otherwise have to re-derive at its own cost.

    python harness/memory/supply/digest.py --role m1
    python harness/memory/supply/digest.py --role all --measure
    python harness/memory/supply/digest.py --args --role sprint   # dispatch blob

Honesty rule: this only ever DROPS. It never paraphrases a measured value, and
every kept number stays verbatim. Truncation is stated inline with a pointer to
the packet, so a leg that needs the rest knows exactly where it is.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SUPPLY = REPO / "harness" / "memory" / "supply"
RUNS = REPO / "harness" / "memory" / "runs"


def newest(glob_dir: Path, pattern: str):
    best = None
    for f in glob_dir.glob(pattern):
        if best is None or f.stat().st_mtime > best.stat().st_mtime:
            best = f
    return best


def load_packet():
    f = newest(SUPPLY, "packet_*.json")
    if f is None:
        return None, None
    return json.loads(f.read_text(encoding="utf-8")), f


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO)).replace("\\", "/")


def _flat(x, kind):
    """Densify one packet entry. Picks the informative fields instead of
    json.dumps-then-truncate, which wastes bytes on punctuation and then cuts
    mid-value. Never rewords a measured string; only selects and shortens."""
    if isinstance(x, str):
        return x
    if not isinstance(x, dict):
        return str(x)
    g = lambda *k: next((str(x[i]) for i in k if x.get(i)), "")
    if kind == "red":
        return f"{g('nodeid')}  @{g('assertion_site')}  {g('failure_verbatim', 'why', 'detail')[:140]}"
    if kind == "sig":
        ps = x.get("params") or []
        return f"{g('port')}.{g('method')}({', '.join(map(str, ps))})  {g('def_line')}"
    if kind == "ref":
        return f"{g('path')}  {g('ratification_line', 'the_pin', 'note')[:120]}"
    if kind == "wt":
        return (f"{g('branch') or g('path')}  @{g('head')[:8]}  "
                f"{'clean' if x.get('clean') else 'dirty: ' + g('dirty_detail')[:70]}")
    if kind == "gap":
        return f"{g('gap')}  ({g('why')[:110]})"
    if kind == "auth":
        return f"{g('name', 'authority', 'symbol')} {g('path', 'site')}  {g('problem', 'note', 'detail')[:110]}"
    return json.dumps(x)[:200]


def _cap(items, n, where):
    items = list(items or [])
    head = items[:n]
    if len(items) > n:
        head.append(f"(+{len(items) - n} more -- full list in {where})")
    return head


def digest(pkt, src, role):
    """Role-sliced briefing. Only drops; never rewords a measured value."""
    where = _rel(src)
    out = [f"SOURCE: {where} (produced {pkt.get('produced_at', '?')} by {pkt.get('produced_by', '?')})"]

    # --- floor: every role needs it ---------------------------------------
    f = pkt.get("1_suite_floor") or {}
    out.append("")
    out.append("SUITE FLOOR -- measured at merge-base, NOT on your branch:")
    out.append(f"  {f.get('summary_line_verbatim', 'UNKNOWN')}")
    out.append(f"  {f.get('collection_line_verbatim', '')}   cmd: {f.get('command', '?')}")
    reds = f.get("the_two_reds_by_name") or []
    for r in _cap(reds, 4, where):
        out.append(f"  RED  {_flat(r, 'red')}")
    if f.get("subtraction_rule_for_later_legs"):
        out.append(f"  RULE {f['subtraction_rule_for_later_legs']}")
    mcp = f.get("known_master_red_mcp_list_tools")
    if isinstance(mcp, dict):
        verdict = mcp.get("verdict") or mcp.get("status") or json.dumps(mcp)[:160]
        out.append(f"  NOTE mcp list_tools red: {verdict}")

    # --- M1 slice ----------------------------------------------------------
    if role in ("m1", "all", "sprint"):
        c = pkt.get("2_constraints_m1_must_not_break") or {}
        out.append("")
        out.append("M1 CONSTRAINTS -- what a lock change must not break:")
        for a in _cap(c.get("the_two_authorities_to_reconcile_not_triple"), 3, where):
            out.append(f"  AUTH {_flat(a, 'auth')}")
        two = c.get("tests_that_hold_two_or_more_live_stores_at_once")
        if isinstance(two, dict):
            names = two.get("tests") or two.get("list") or []
            out.append(f"  MULTI-STORE TESTS ({len(names)}): "
                       f"{', '.join(str(x)[:70] for x in names[:5])}"
                       f"{' ...' if len(names) > 5 else ''}")
        uniq = c.get("tests_relying_on_a_unique_auto_generated_storage_uri")
        if isinstance(uniq, dict):
            out.append(f"  UNIQUE-URI DEPENDENTS: {len(uniq.get('tests') or uniq.get('list') or [])}")
        if c.get("design_note_for_the_forge"):
            out.append(f"  DESIGN {c['design_note_for_the_forge']}")

    # --- M2 slice ----------------------------------------------------------
    if role in ("m2", "all", "sprint"):
        s = pkt.get("3_surface_m2_must_not_move") or {}
        out.append("")
        out.append("M2 PINNED SURFACE -- do not move it:")
        out.append(f"  file {s.get('file', '?')}")
        for p in _cap(s.get("parameter_names_as_they_stand_today"), 5, where):
            out.append(f"  SIG  {_flat(p, 'sig')}")
        rc = s.get("ratifying_contract")
        pt = s.get("pinning_test")
        if rc:
            out.append(f"  CONTRACT {_flat(rc, 'ref')}")
        if pt:
            out.append(f"  PINNED-BY {_flat(pt, 'ref')}")
        if s.get("the_rule_for_M2"):
            out.append(f"  RULE {s['the_rule_for_M2']}")

    # --- readiness + honest gaps: every role -------------------------------
    r = pkt.get("4_readiness") or {}
    wts = r.get("worktrees") or []
    if wts:
        out.append("")
        out.append("READINESS:")
        for w in _cap(wts, 4, where):
            out.append(f"  {_flat(w, 'wt')}")

    gaps = pkt.get("5_could_not_supply") or []
    out.append("")
    out.append("QUARTERMASTER COULD NOT SUPPLY (treat each as UNKNOWN, not as fine):")
    for gap in _cap(gaps, 4, where):
        out.append(f"  - {_flat(gap, 'gap')}")

    return "\n".join(out)


def latest_sweep():
    f = newest(RUNS, "*/sweep_*.json")
    if f is None:
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    lines = [f"SOURCE: {_rel(f)}", f"VERDICT: {d.get('verdict')}"]
    for fi in d.get("findings", []):
        lines.append(f"  [{fi['severity']}] {fi['invariant']} {fi['detail'][:160]}")
    for w in d.get("worktrees", []):
        lines.append(f"  {w.get('branch')}: {len(w.get('changed') or [])} changed "
                     f"-- {', '.join((w.get('changed') or [])[:4])}")
    if d.get("main_tree_code_edits"):
        lines.append(f"  REPO-ROOT CODE EDITS PRESENT: {d['main_tree_code_edits'][:5]}")
    else:
        lines.append("  repo root clean of code edits (I1 holds)")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="packet -> per-role briefing")
    ap.add_argument("--role", default="all",
                    choices=["m0", "m1", "m2", "m3", "all", "sprint"])
    ap.add_argument("--args", action="store_true",
                    help="emit the dispatch args blob (supply + advisory)")
    ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()

    pkt, src = load_packet()
    if pkt is None:
        print("NO PACKET -- run mem-quartermaster first")
        return 1

    d = digest(pkt, src, a.role)
    adv = latest_sweep()

    if a.args:
        print(json.dumps({"supply": d, "advisory": adv or ""}, indent=2))
    else:
        print(d)
        if adv:
            print("\n--- MARSHAL ADVISORY ---\n" + adv)

    if a.measure:
        raw = len(src.read_text(encoding="utf-8"))
        cut = len(d)
        print(f"\n[measure] packet {raw:,}B -> role={a.role} digest {cut:,}B "
              f"({100 - round(100 * cut / raw)}% smaller); "
              f"advisory {len(adv or ''):,}B", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
