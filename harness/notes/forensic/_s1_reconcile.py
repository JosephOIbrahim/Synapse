"""S1 producer path — reconcile the orchestrator's verdicts against the agent fan-out.

After the resumed fan-out, most tools carry TWO independent verdicts:
  * the orchestrator's, from reading the handler (s1_classification.json)
  * a cartographer reader's, plus a crucible adversary's refutation attempt

This does NOT silently prefer one. It reports:
  * agreement rate — how often two independent readers landed on the same class
  * every DISAGREEMENT, with both sides, so a human can see where the inventory
    is soft
  * every DOWNGRADE the adversary forced, which is the pass the first run never got

Emits harness/notes/forensic/s1_reconciliation.json.

Law 1 — how this fails: if the journal holds no classify results, the script
exits non-zero rather than reporting a vacuous 100% agreement. A reconciliation
with nothing to reconcile is the exact "check that cannot fail" the constitution
bans.

Precedence, stated once and applied uniformly:
  1. A live observation by the orchestrator (provenance 'live') OUTRANKS any
     static read by either party. VERIFIED-RUNTIME beats VERIFIED-STATIC — that
     is Article II, not a preference.
  2. Otherwise the adversary's post-refutation class wins over the classifier's,
     because it survived an attack the other never faced.
  3. Where only one party has an opinion, it stands, tagged as unreconciled.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FOR = ROOT / "harness" / "notes" / "forensic"
JOURNAL = (
    ROOT.parent.parent.parent
    / ".claude/projects/C--Users-User-SYNAPSE--claude-worktrees-s1-forensic"
    / "0e34aceb-0245-47ad-94fb-99cff55a76fb/subagents/workflows/wf_cb86d227-4cd/journal.jsonl"
)
if len(sys.argv) > 1:
    JOURNAL = pathlib.Path(sys.argv[1])

if not JOURNAL.exists():
    sys.exit(f"FAIL: journal not found at {JOURNAL}")

classified: dict[str, dict] = {}
refuted: dict[str, dict] = {}

for line in JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("type") != "result":
        continue
    res = d.get("result")
    if not isinstance(res, dict):
        continue
    for row in res.get("tools", []) or []:
        if isinstance(row, dict) and row.get("tool"):
            classified[row["tool"]] = row
    for row in res.get("verdicts", []) or []:
        if isinstance(row, dict) and row.get("tool"):
            refuted[row["tool"]] = row

if not classified:
    sys.exit("FAIL: journal holds zero classify results — nothing to reconcile.")

mine = {
    r["tool"]: r
    for r in json.loads((FOR / "s1_classification.json").read_text(encoding="utf-8"))["verdicts"]
}

rows, disagreements, downgrades = [], [], []

for tool, m in sorted(mine.items()):
    a = classified.get(tool)
    ref = refuted.get(tool)
    agent_class = (ref or {}).get("final_klass") or (a or {}).get("klass")

    live = m["provenance"] == "live"
    if agent_class is None:
        final, why = m["klass"], "orchestrator only — no agent verdict"
    elif live and m["klass"] != agent_class:
        final, why = m["klass"], (
            "orchestrator LIVE observation outranks the agent's static read "
            "(Article II: VERIFIED-RUNTIME > VERIFIED-STATIC)"
        )
    elif m["klass"] == agent_class:
        final, why = m["klass"], "both readers agree"
    else:
        final, why = agent_class, (
            "agent verdict taken — it faced an adversarial refutation pass the "
            "orchestrator's read did not"
        )

    if agent_class and m["klass"] != agent_class:
        disagreements.append({
            "tool": tool,
            "orchestrator": m["klass"], "orchestrator_provenance": m["provenance"],
            "agent": agent_class,
            "classifier_said": (a or {}).get("klass"),
            "adversary_upheld": (ref or {}).get("upheld"),
            "adversary_why": ((ref or {}).get("why") or "")[:400],
            "resolved_to": final, "rule": why,
        })

    if ref and ref.get("upheld") is False:
        downgrades.append({
            "tool": tool,
            "from": ref.get("original_klass"), "to": ref.get("final_klass"),
            "why": (ref.get("why") or "")[:400],
            "anchor": ref.get("anchor", ""),
        })

    rows.append({
        "tool": tool, "final": final, "rule": why,
        "orchestrator": m["klass"], "agent": agent_class,
        "artist_task": m["artist_task"] or (a or {}).get("artist_task", ""),
        "would_artist_reach": (
            m["would_artist_reach"]
            if m["would_artist_reach"] is not None
            else (a or {}).get("would_artist_reach")
        ),
    })

both = [r for r in rows if r["agent"] is not None]
agree = [r for r in both if r["orchestrator"] == r["agent"]]

final_counts: dict[str, int] = {}
for r in rows:
    final_counts[r["final"]] = final_counts.get(r["final"], 0) + 1

by_task: dict[str, dict] = {}
for r in rows:
    if r["final"] not in ("WORKS", "PARTIAL"):
        continue
    t = r["artist_task"] or "unclassified"
    d = by_task.setdefault(t, {"WORKS": 0, "PARTIAL": 0, "reach_yes": 0, "reach_no": 0})
    d[r["final"]] += 1
    d["reach_yes" if r["would_artist_reach"] else "reach_no"] += 1

out = {
    "producer": "harness/notes/forensic/_s1_reconcile.py",
    "journal": str(JOURNAL),
    "tools_total": len(rows),
    "tools_with_two_independent_verdicts": len(both),
    "agreement_count": len(agree),
    "agreement_rate": round(len(agree) / len(both), 3) if both else None,
    "disagreement_count": len(disagreements),
    "adversary_downgrades": len(downgrades),
    "refutation_coverage": len(refuted),
    "final_counts": final_counts,
    "by_artist_task": dict(sorted(by_task.items())),
    "disagreements": disagreements,
    "downgrades": downgrades,
    "rows": rows,
}
(FOR / "s1_reconciliation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(
    {k: v for k, v in out.items() if k not in ("rows", "disagreements", "downgrades")},
    indent=1,
))
print(f"\ndisagreements: {len(disagreements)}   adversary downgrades: {len(downgrades)}")
for d in disagreements[:25]:
    print(f"  {d['tool']:38s} orch={d['orchestrator']:<11s} agent={d['agent']:<11s} -> {d['resolved_to']}")
