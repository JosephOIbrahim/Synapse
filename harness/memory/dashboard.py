#!/usr/bin/env python3
"""dashboard.py -- MEMORY board status bar + progress dashboard.

Reads harness/memory/STATE.json (and harness/loop/STATE.json for the parent
ladder) and renders the board. Pure stdlib, ASCII-only output so it survives
cp1252 consoles.

    python harness/memory/dashboard.py           # full dashboard
    python harness/memory/dashboard.py --bar     # one-line status bar
    python harness/memory/dashboard.py --json    # machine readable

Honesty rule (AGENTS.md Law 4): this renders STATE.json. It does not verify it.
A rung reads CLOSED here because a conductor wrote CLOSED there; the evidence is
in the artifacts the rung names, not in this file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOARD = REPO / "harness" / "memory" / "STATE.json"
PARENT = REPO / "harness" / "loop" / "STATE.json"

WIDTH = 78

# status token -> (glyph, sort rank)
_MARK = {
    "CLOSED": "[x]",
    "READY": "[>]",
    "RUNNING": "[~]",
    "BLOCKED": "[!]",
    "UNKNOWN": "[?]",
}


def _ascii(text: str) -> str:
    """Transliterate to ASCII so a cp1252 console renders the board, not '?'."""
    return (str(text)
            .replace("—", "--").replace("–", "-")
            .replace("‘", "'").replace("’", "'")
            .replace("“", '"').replace("”", '"')
            .replace("→", "->").replace("≥", ">=")
            .encode("ascii", "replace").decode("ascii"))


def _classify(status: str) -> str:
    s = (status or "").upper()
    for token in ("CLOSED", "RUNNING", "READY", "BLOCKED"):
        if s.startswith(token) or token in s.split(" ")[0].upper():
            return token
    if "CLOSED" in s:
        return "CLOSED"
    if "BLOCKED" in s:
        return "BLOCKED"
    if "READY" in s:
        return "READY"
    return "UNKNOWN"


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        print(f"[dashboard] {path.name} is not valid JSON: {exc}", file=sys.stderr)
        return None


def _rungs(state):
    out = []
    for key, r in (state.get("rungs") or {}).items():
        out.append(
            {
                "id": key,
                "title": r.get("title", ""),
                "status": r.get("status", ""),
                "class": _classify(r.get("status", "")),
                "budget": r.get("agent_budget", 0),
                "receipts": len(r.get("receipts") or []),
            }
        )
    return out


def _bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[" + "?" * width + "]"
    filled = int(round(width * done / total))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def collect():
    board = _load(BOARD)
    if board is None:
        return None
    rungs = _rungs(board)
    closed = sum(1 for r in rungs if r["class"] == "CLOSED")
    blocked = sum(1 for r in rungs if r["class"] == "BLOCKED")
    ready = sum(1 for r in rungs if r["class"] == "READY")
    gates = board.get("human_gates") or {}
    open_gates = [k for k, v in gates.items() if str(v).upper().startswith("OPEN")]
    cap = board.get("spawn_cap", 0)
    reserve = board.get("spawn_reserve", 0)
    spent = board.get("spawned", 0)
    parent = _load(PARENT)
    parent_rungs = _rungs(parent) if parent else []
    parent_closed = sum(1 for r in parent_rungs if r["class"] == "CLOSED")
    return {
        "board": board,
        "rungs": rungs,
        "closed": closed,
        "ready": ready,
        "blocked": blocked,
        "total": len(rungs),
        "open_gates": open_gates,
        "spawn": {"spent": spent, "cap": cap, "reserve": reserve,
                  "usable": max(cap - reserve, 0)},
        "parent": {
            "closed": parent_closed,
            "total": len(parent_rungs),
            "rungs": parent_rungs,
        },
    }


def render_bar(d) -> str:
    s = d["spawn"]
    return (
        f"MEM {_bar(d['closed'], d['total'], 12)} {d['closed']}/{d['total']} rungs"
        f" | ready {d['ready']} blocked {d['blocked']}"
        f" | agents {s['spent']}/{s['usable']}"
        f" | gates open {len(d['open_gates'])}"
        f" | LOOP {d['parent']['closed']}/{d['parent']['total']}"
    )


def render_full(d) -> str:
    b = d["board"]
    L = []
    line = "+" + "=" * (WIDTH - 2) + "+"
    L.append(line)
    L.append("|  MEMORY BOARD".ljust(WIDTH - 1) + "|")
    L.append(("|  " + b.get("_schema", "") + "   base " + str(b.get("base_commit", "?"))
              + " v" + str(b.get("base_version", "?"))
              + "   H" + str(b.get("houdini_build", "?"))).ljust(WIDTH - 1) + "|")
    L.append(line)

    L.append("")
    L.append("  LADDER   " + _bar(d["closed"], d["total"]) + f"  {d['closed']}/{d['total']} closed")
    L.append("")
    for r in d["rungs"]:
        mark = _MARK.get(r["class"], "[?]")
        head = f"  {mark} {r['id'].upper():<4} {r['title']}"
        L.append(_ascii(head)[: WIDTH - 2])
        note = r["status"].split(" -- ")[0].split(" — ")[0]
        L.append(_ascii(f"          {note}")[: WIDTH - 2])
        L.append("")

    s = d["spawn"]
    L.append("  AGENT LEDGER")
    L.append(f"    spawned {s['spent']} / {s['usable']} usable "
             f"(cap {s['cap']}, reserve {s['reserve']})")
    L.append("    " + _bar(s["spent"], max(s["usable"], 1)))
    L.append("")

    L.append("  SUBSTRATE")
    for k, v in (b.get("substrate_presence") or {}).items():
        shape = str(v).split(" -- ")[0].split(" — ")[0]
        L.append(_ascii(f"    {k:<20} {shape}")[: WIDTH - 2])
    L.append("")

    L.append(f"  HUMAN GATES ({len(d['open_gates'])} open)")
    for k, v in (b.get("human_gates") or {}).items():
        state = "OPEN " if str(v).upper().startswith("OPEN") else "closed"
        L.append(_ascii(f"    [{state}] {k}")[: WIDTH - 2])
    L.append("")

    p = d["parent"]
    L.append(f"  PARENT LADDER (THE LOOP v5.1)   {p['closed']}/{p['total']} closed")
    for r in p["rungs"]:
        L.append(f"    {_MARK.get(r['class'], '[?]')} {r['id']}"[: WIDTH - 2])
    L.append("")
    L.append("  " + _ascii(render_bar(d))[: WIDTH - 4])
    L.append(line)
    return "\n".join(L)



# ---------------------------------------------------------------- progress
def _newest_sweep():
    root = REPO / "harness" / "memory" / "runs"
    best = None
    for f in root.glob("*/sweep_*.json"):
        if best is None or f.stat().st_mtime > best.stat().st_mtime:
            best = f
    if best is None:
        return None
    try:
        d = json.loads(best.read_text(encoding="utf-8"))
        d["_path"] = str(best.relative_to(REPO)).replace("\\", "/")
        return d
    except Exception:
        return None


def _legs():
    """In-flight vs landed legs, read from what is actually on disk."""
    busdir = REPO / "harness" / "memory" / "bus"
    landed = sorted(f.stem for f in busdir.glob("*.json"))
    run = None
    board = _load(BOARD) or {}
    for entry in reversed(board.get("log") or []):
        if entry.get("event") == "sprint-dispatched":
            run = entry.get("workflow")
            break
    inflight = []
    for r in _rungs(board):
        if r["class"] == "RUNNING":
            inflight.append(r["id"])
    return {"landed": landed, "inflight": inflight, "run": run}


def render_progress(d) -> str:
    L = []
    lg = _legs()
    sw = _newest_sweep()
    total_legs = 7
    done = max(len(lg["landed"]) - 1, 0)   # memory_m0_audit predates the sprint

    L.append("  MEMORY BOARD -- live")
    L.append("")
    L.append(f"  rungs   {_bar(d['closed'], d['total'])}  {d['closed']}/{d['total']} closed")
    L.append(f"  legs    {_bar(done, total_legs)}  {done}/{total_legs} receipts landed")
    L.append(f"  agents  {_bar(d['spawn']['spent'], max(d['spawn']['usable'],1))}  "
             f"{d['spawn']['spent']}/{d['spawn']['usable']} of budget")
    L.append("")
    L.append(f"  run       {lg['run'] or '(none dispatched)'}")
    L.append(f"  in-flight {' '.join(lg['inflight']) or '(none)'}")
    if sw:
        v = sw.get("verdict", "?")
        nb = sum(1 for f in sw.get("findings", []) if f.get("severity") == "BREACH")
        L.append(f"  sweep     {v}  ({nb} breach, {len(sw.get('findings', []))} finding(s))  {sw.get('_path','')}")
        for w in sw.get("worktrees", []):
            L.append(f"              {w.get('branch'):<18} {len(w.get('changed') or [])} changed")
    else:
        L.append("  sweep     UNKNOWN -- no sweep artifact yet "
                 "(python harness/memory/marshal/sweep.py --out ...)")
    L.append(f"  gates     {len(d['open_gates'])} open")
    L.append("")
    L.append("  " + _ascii(render_bar(d)))
    return chr(10).join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="MEMORY board dashboard")
    ap.add_argument("--bar", action="store_true", help="one-line status bar")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--progress", action="store_true", help="live progress bars")
    args = ap.parse_args()

    d = collect()
    if d is None:
        print("MEM [board missing] harness/memory/STATE.json not found")
        return 1

    if args.json:
        print(json.dumps(
            {k: v for k, v in d.items() if k != "board"}, indent=2, sort_keys=True))
    elif args.progress:
        print(render_progress(d))
    elif args.bar:
        print(render_bar(d))
    else:
        print(render_full(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
