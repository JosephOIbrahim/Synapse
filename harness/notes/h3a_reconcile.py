"""H3a reconciliation - merge the two producers per symbol. Read-only. Producer path: this file.

Producer 1 (authoritative): harness/notes/h3a/live_gui.json  - live GUI Houdini 22.0.368 via the
                            SYNAPSE bridge. Sees hou.ui AND can import hdefereval.
Producer 2 (corroborating): harness/notes/h3a/<GROUP>_hython.json - headless hython3.13, same build.
                            Blind to hou.ui; hdefereval refuses to import.

Rule, stated before the merge so it cannot be tuned to the answer:
  * both EXISTS            -> CONFIRMED   (agreement)
  * both ABSENT            -> ABSENT      (agreement)
  * GUI EXISTS / headless ABSENT-or-UNVERIFIABLE, and the symbol is interpreter-scoped
    (hou.ui.* or hdefereval.*) -> CONFIRMED, divergence EXPLAINED-BY-INTERPRETER
  * any other disagreement -> CONFLICT, and the leg reports it rather than picking a winner.
Failure condition: if either producer's controls_ok is false, that producer is dropped and said so.
"""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
H3A = os.path.join(BASE, "h3a")

gui = json.load(open(os.path.join(H3A, "live_gui.json"), encoding="utf-8"))
man = json.load(open(os.path.join(BASE, "h3a_symbols.json"), encoding="utf-8"))

meta = {}
for g, entries in man["groups"].items():
    for e in entries:
        meta[e["symbol"]] = {"group": g, "candidate": e.get("candidate", False),
                             "gui_only": e.get("gui_only", False), "anchor": e.get("anchor"),
                             "why": e.get("why")}

head = {}
head_ctl = {}
for g in man["groups"]:
    p = os.path.join(H3A, "%s_hython.json" % g)
    if not os.path.exists(p):
        head_ctl[g] = "MISSING ARTIFACT"
        continue
    d = json.load(open(p, encoding="utf-8"))
    head_ctl[g] = "controls_ok=%s" % d["controls_ok"]
    if not d["controls_ok"]:
        continue
    for r in d["results"]:
        head[r["symbol"]] = r

assert gui["controls_ok"], "GUI producer controls failed - run is UNINTERPRETABLE"

V = {"EXISTS": "CONFIRMED", "ABSENT": "ABSENT", "UNVERIFIABLE": "UNVERIFIABLE"}
rows, conflicts = [], []
for r in gui["results"]:
    s = r["symbol"]
    m = meta.get(s, {})
    gv = V[r["verdict"]]
    hr = head.get(s)
    hv = V[hr["verdict"]] if hr else None
    interpreter_scoped = s.startswith("hou.ui") or s.split(".")[0] == "hdefereval"
    if hv is None:
        agree = "GUI-ONLY-PRODUCER"
    elif hv == gv:
        agree = "AGREE"
    elif interpreter_scoped:
        agree = "EXPLAINED-BY-INTERPRETER"
    else:
        agree = "CONFLICT"
        conflicts.append((s, gv, hv))
    rows.append({"symbol": s, "verdict": gv, "group": m.get("group"),
                 "candidate": m.get("candidate"), "gui_only": m.get("gui_only"),
                 "anchor": m.get("anchor"), "headless": hv, "reconciliation": agree,
                 "evidence": r["evidence"], "signature": r.get("signature")})

out = {"schema": "h3a_reconcile/v1", "producer": "harness/notes/h3a_reconcile.py",
       "authoritative_producer": "harness/notes/h3a/live_gui.json (GUI 22.0.368)",
       "corroborating_producer_controls": head_ctl,
       "counts": {"total": len(rows),
                  "CONFIRMED": sum(1 for r in rows if r["verdict"] == "CONFIRMED"),
                  "ABSENT": sum(1 for r in rows if r["verdict"] == "ABSENT"),
                  "UNVERIFIABLE": sum(1 for r in rows if r["verdict"] == "UNVERIFIABLE"),
                  "AGREE": sum(1 for r in rows if r["reconciliation"] == "AGREE"),
                  "EXPLAINED_BY_INTERPRETER": sum(1 for r in rows if r["reconciliation"] == "EXPLAINED-BY-INTERPRETER"),
                  "CONFLICT": len(conflicts)},
       "conflicts": conflicts, "rows": rows}
json.dump(out, open(os.path.join(H3A, "reconciled.json"), "w", encoding="utf-8"), indent=2)
print(json.dumps(out["counts"], indent=1))
print("CONFLICTS:", conflicts or "none")
