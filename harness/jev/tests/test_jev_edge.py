# test_jev_edge.py - biting tests for the JEV-EDGE guard (helm mile 3). plan_edge() is pure, so
# every rule is asserted without a network call, a manifest on disk, or an orchestrator.
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
BP_DIR = JEV_DIR.parent / "battleplan"
for p in (str(JEV_DIR), str(BP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import jev_edge as je  # noqa: E402
import mission_schema as ms  # noqa: E402

CAP = je.caps()["max_inserted_legs"]
FLAG = {"verdict": "FLAG", "rows": [1], "reason": "row(s) [1] evidence does not support predicate"}


def _m(mid="BP9-BUILDA", cls="build", tier="reasoning"):
    return {"id": mid, "name": "n", "band": "BUILD" if cls == "build" else "TRUST", "class": cls, "tier": tier,
            "source": {"doc": "harness/battleplan/notes/JEV_HELM.md", "anchor": "mile 3"}, "targets": ["T1"],
            "acceptance": [{"predicate": "p0", "evidence": "test"}, {"predicate": "p1 count equals 22", "evidence": "check"}],
            "deps": [], "readonly": cls != "build", "touches": ["harness/x.py"], "crucible_criteria": ["c"]}


def _manifest():
    return {"wave": "bp9", "legs": [
        {"id": "BP9-BUILDA", "branch": "bp9/builda", "base": "master", "deps": [], "state": "ready"},
        {"id": "BP9-BUILDB", "branch": "bp9/buildb", "base": "master", "deps": [], "state": "ready"},
        {"id": "BP9-CRUX", "branch": "bp9/crux", "base": "master", "deps": ["BP9-BUILDA", "BP9-BUILDB"], "state": "ready"}]}


def test_clear_and_referee_change_nothing():
    """Mutation: insert on any non-CLEAR verdict -> every thin receipt buys a leg."""
    for v in ("CLEAR", "REFEREE"):
        assert je.plan_edge(_manifest(), _m(), {"verdict": v, "rows": [1]}, CAP)["action"] == "continue"
    assert je.plan_edge(_manifest(), _m(), None, CAP)["action"] == "continue"


def test_flag_inserts_one_repair_on_the_flagged_branch_and_gates_dependents():
    """Mutation: base the repair on master -> it cannot see the work it repairs; or skip the
    dependents rewrite -> CRUX runs before the repair lands."""
    man = _manifest()
    before = copy.deepcopy(man)
    p = je.plan_edge(man, _m(), FLAG, CAP)
    assert man == before                                  # pure: input never mutated
    assert p["action"] == "insert_repair" and p["row"]["id"] == "BP9-RPR1"
    assert p["row"]["base"] == "bp9/builda" and p["row"]["deps"] == ["BP9-BUILDA"]
    legs = {x["id"]: x for x in p["manifest"]["legs"]}
    assert legs["BP9-CRUX"]["deps"] == ["BP9-BUILDA", "BP9-BUILDB", "BP9-RPR1"] and p["dependents"] == ["BP9-CRUX"]
    assert [x["id"] for x in p["manifest"]["legs"]].index("BP9-RPR1") == 1   # right after the flagged leg


def test_repair_mission_is_scoped_to_flagged_rows_and_valid():
    """Mutation: copy ALL acceptance rows into the repair -> a second full build, not a repair."""
    p = je.plan_edge(_manifest(), _m(), FLAG, CAP)
    rm = p["mission"]
    assert rm["acceptance"] == [{"predicate": "p1 count equals 22", "evidence": "check"}]
    assert len(rm["targets"]) == 1 and "p1 count equals 22" in rm["targets"][0]
    assert rm["tier"] == "reasoning" and ms.validate_mission(rm) == []
    assert je.plan_edge(_manifest(), _m(tier="auto"), FLAG, CAP)["mission"]["tier"] == "reasoning"


def test_cap_is_hard():
    """Mutation: compare with > instead of >= (or drop the check) -> an unbounded wave."""
    man = _manifest()
    for i in range(CAP):
        man["legs"].append({"id": f"BP9-RPR{i + 1}", "branch": "b", "deps": [], "inserted_by": je.TAG, "repairs": f"BP9-OLD{i}"})
    p = je.plan_edge(man, _m(), FLAG, CAP)
    assert p["action"] == "cap_reached" and "manifest" not in p


def test_no_chains_no_double_repair_no_referee():
    """Mutation: drop any of the three rules -> repairs of repairs, two repairs of one leg, or
    the crucible's own receipt rewriting the graph."""
    man = _manifest()
    man["legs"].append({"id": "BP9-RPR1", "branch": "bp9/rpr1", "deps": ["BP9-BUILDA"], "inserted_by": je.TAG, "repairs": "BP9-BUILDA"})
    assert je.plan_edge(man, _m("BP9-RPR1"), FLAG, CAP)["action"] == "continue"      # no chains
    assert je.plan_edge(man, _m("BP9-BUILDA"), FLAG, CAP)["action"] == "continue"    # already repaired
    assert je.plan_edge(_manifest(), _m("BP9-CRUX", cls="crucible"), FLAG, CAP)["action"] == "continue"
    assert je.plan_edge(_manifest(), _m("BP9-NOPE"), FLAG, CAP)["action"] == "continue"


def test_run_is_dry_by_default_and_never_raises(tmp_path, monkeypatch):
    """Mutation: write the manifest without --apply, or let an exception escape -> a shadow run
    edits a live wave, or a guard bug stops the orchestrator."""
    monkeypatch.setattr(je.jc, "LEDGER_DIR", tmp_path / "ledger")
    mp = tmp_path / "bp9.live.json"
    mp.write_text(json.dumps(_manifest()), encoding="utf-8")
    raw = mp.read_bytes()
    out = je.run(mp, "BP9-BUILDA", tmp_path / "missing-receipt.json", do_apply=False)
    assert out["action"] == "continue" and out["applied"] is False and out["reason"].startswith("fallback")
    assert mp.read_bytes() == raw
    rows = [json.loads(l) for l in (tmp_path / "ledger" / "bp9.edge.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["mode"] == "shadow" and rows[-1]["decision"]["applied"] is False
