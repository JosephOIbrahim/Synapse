# harness/battleplan/drift.py - BP2-METER T3. Bus-driven on-target drift check.
# ZERO model calls, pure stdlib. Per leg: on-target ratio over its last 5 progress
# messages (fraction citing a T<n> / acceptance index) < 0.6 = DRIFT -> post a
# `refocus` from the orchestrator with the leg's mission targets VERBATIM; two
# refocus still drifting -> `halt`. Never edits a mission/manifest - reads bus +
# missions, posts to the bus. orchestrate.ps1 runs it per poll, only if -Budget.
import json, re, sys
from pathlib import Path
import bus  # reuse the append-only battleplan bus (read + post)
MISSIONS = Path(__file__).resolve().parent / "missions"
WINDOW = 5             # progress messages considered
ON_TARGET_MIN = 0.6    # below this ratio a leg has drifted
_CITES = re.compile(r"T\d+|acceptance|^\d+$", re.IGNORECASE)


def _on_target(body) -> bool:
    tgt = body.get("target", "") if isinstance(body, dict) else ""
    return bool(_CITES.search(str(tgt)))


def _targets(leg, missions_dir) -> list:
    f = Path(missions_dir) / f"{leg}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("targets", []) if f.exists() else []
    except Exception:
        return []


def check(wave, missions_dir=MISSIONS, post=None) -> list:
    post = post or bus.post
    msgs = bus.read(wave)
    legs = {}
    for m in msgs:
        if m.get("type") == "progress" and m.get("frm"):
            legs.setdefault(m["frm"], []).append(m.get("body") or {})
    acted = []
    receipts = MISSIONS.parent.parent / "notes" / "receipts"
    for leg, prog in legs.items():
        if any(m.get("type") == "halt" and m.get("to") == leg for m in msgs):
            continue  # already halted - never re-halt
        # 2026-09-01 referee guard: a CLOSED leg is not a drifting leg. Its receipt is
        # in-tree, or its last progress said DONE, or it posted a release status -
        # a finished session cannot answer a refocus (observed: refocus -> BP2-STORE
        # on the first poll of the closing wave).
        if (receipts / f"{leg}.json").exists():
            continue
        if any(str((b or {}).get("target", "")).upper() == "DONE" for b in prog):
            continue
        if any(m.get("type") == "status" and m.get("frm") == leg and (m.get("body") or {}).get("release")
               for m in msgs):
            continue
        last = prog[-WINDOW:]
        ratio = sum(_on_target(b) for b in last) / len(last)
        if ratio >= ON_TARGET_MIN:
            continue  # on target
        refocus = sum(1 for m in msgs if m.get("type") == "refocus" and m.get("to") == leg)
        if refocus >= 2:  # two refocus, still drifting -> escalate
            post(wave, "orchestrator", "halt",
                 {"leg": leg, "reason": f"two refocus, still drifting (ratio {ratio:.2f})"}, leg)
            acted.append(("halt", leg))
        else:
            post(wave, "orchestrator", "refocus",
                 {"leg": leg, "targets": _targets(leg, missions_dir),
                  "reason": f"on-target ratio {ratio:.2f} < {ON_TARGET_MIN} over last {len(last)}"}, leg)
            acted.append(("refocus", leg))
    return acted

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: drift.py <wave>"); sys.exit(2)
    for kind, leg in check(sys.argv[1]):
        print(f"{kind} -> {leg}")
