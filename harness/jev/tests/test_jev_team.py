# test_jev_team.py - biting tests for the JEV-TEAM guard (helm mile 2). Same contract as the
# other guard tests: exact decisions, the reddening mutation named in each docstring, hermetic.
from __future__ import annotations

import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
BP_DIR = JEV_DIR.parent / "battleplan"
for p in (str(JEV_DIR), str(BP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import jev_client as jc  # noqa: E402
import jev_team as jt  # noqa: E402
import mission_schema as ms  # noqa: E402
import compile_wave as cw  # noqa: E402

POLICY = jc.load_questions()["guards"]["team"]["policy"]
BUILD = {"id": "BP9-X", "class": "build", "readonly": False}
SCOUT = {"id": "BP9-S", "class": "truth", "readonly": True}


def _a(score, conf=0.9, shared=0.1):
    return {"choices": {}, "scores": {"parallelizable": {"score": score, "confidence": conf, "probabilities": {}}},
            "nouls": {"shared_files": {"noul": shared}}}


def test_none_answer_is_zero_subagents():
    """Mutation: return a non-zero default on answers=None -> tokens spent with no judgment."""
    assert jt.decide(BUILD, None, POLICY)["max_subagents"] == 0


def test_bands_map_serial_some_wide():
    """Mutation: shift a band edge or swap the counts -> a serial leg gets a team."""
    assert jt.decide(BUILD, _a(0.3), POLICY)["max_subagents"] == 0
    assert jt.decide(BUILD, _a(1.2), POLICY)["max_subagents"] == 2
    assert jt.decide(BUILD, _a(1.9), POLICY)["max_subagents"] == 4


def test_low_confidence_rounds_down_one_band():
    """Mutation: round UP on doubt (the tier-routing habit) -> uncertainty buys agents."""
    assert jt.decide(BUILD, _a(1.9, conf=0.4), POLICY)["max_subagents"] == 2
    assert jt.decide(BUILD, _a(1.2, conf=0.4), POLICY)["max_subagents"] == 0
    assert jt.decide(BUILD, _a(1.9, conf=None), POLICY)["max_subagents"] == 2


def test_writers_sharing_files_get_zero_but_readers_do_not():
    """Mutation: drop the shared_files check -> two subagents edit one file; or apply it to
    read-only scouts -> scouts lose a team they can safely have."""
    assert jt.decide(BUILD, _a(1.9, shared=0.8), POLICY)["max_subagents"] == 0
    assert jt.decide(SCOUT, _a(1.9, shared=0.8), POLICY)["max_subagents"] == 4
    a = _a(1.9)
    a["nouls"]["shared_files"] = {"noul": None}
    assert jt.decide(BUILD, a, POLICY)["max_subagents"] == 0  # unknown collision risk = assume collision


def test_referee_and_tidy_work_alone():
    """Mutation: remove the class rule -> the crucible delegates its own verification."""
    assert jt.decide({"class": "crucible", "readonly": True}, _a(2.0), POLICY)["max_subagents"] == 0
    assert jt.decide({"class": "tidy", "readonly": True}, _a(2.0), POLICY)["max_subagents"] == 0


def test_never_past_the_hard_cap_and_tier_is_a_rails_name():
    """Mutation: raise a band count above hard_cap, or name a model in policy.subagent_tier."""
    p = {**POLICY, "bands": [[1.0, 0], [1.7, 2], [9.9, 12]]}
    assert jt.decide(BUILD, _a(2.0), p)["max_subagents"] == POLICY["hard_cap"]
    assert POLICY["subagent_tier"] in jc.rails_tiers()
    bad = jt.decide(BUILD, _a(2.0), {**POLICY, "subagent_tier": "claude-opus-4-8"})
    assert bad["max_subagents"] == 0 and bad["subagent_tier"] is None


def test_team_lines_empty_at_zero():
    """Mutation: render a Team section at zero -> every auto leg's prompt changes."""
    assert jt.team_lines({"max_subagents": 0, "subagent_tier": "mechanical"}) == ""
    s = jt.team_lines({"max_subagents": 2, "subagent_tier": "mechanical"})
    assert "at most 2 subagents" in s and "`mechanical`" in s


def _mission(**kw):
    m = {"id": "BP9-TEAMT", "name": "n", "band": "BUILD", "class": "build", "tier": "reasoning",
         "source": {"doc": "harness/battleplan/notes/JEV_HELM.md", "anchor": "mile 2"}, "targets": ["T1"],
         "acceptance": [{"predicate": "p", "evidence": "test"}], "deps": [], "readonly": False,
         "touches": [], "crucible_criteria": ["c"]}
    m.update(kw)
    return m


def test_schema_accepts_and_rejects_team():
    """Mutation: drop the team validation -> a mission asks for 40 subagents on a model string."""
    assert ms.validate_mission(_mission()) == []
    assert ms.validate_mission(_mission(team="auto")) == []
    assert ms.validate_mission(_mission(team={"max_subagents": 2, "subagent_tier": "mechanical"})) == []
    assert ms.validate_mission(_mission(team={"max_subagents": 40, "subagent_tier": "mechanical"}))
    assert ms.validate_mission(_mission(team={"max_subagents": 2, "subagent_tier": "claude-opus-4-8"}))
    assert ms.validate_mission(_mission(band="TRUST", readonly=True, **{"class": "crucible"},
                                        team={"max_subagents": 2, "subagent_tier": "mechanical"}))


def test_teamless_leg_compiles_byte_identical():
    """Mutation: add a team key or a Team section for a mission with no team field -> every
    existing wave's rows and prompts change (the invariant-2 promise, extended to teams)."""
    m = _mission()
    row = cw.leg_row(m)
    assert "team" not in row
    with_zero = cw.leg_row(_mission(team={"max_subagents": 0, "subagent_tier": "mechanical"}))
    assert cw.fill_prompt(m, row).count("## Team") == 0
    assert cw.fill_prompt(_mission(team=with_zero["team"]), with_zero).count("## Team") == 0
    two = cw.leg_row(_mission(team={"max_subagents": 2, "subagent_tier": "mechanical"}))
    assert cw.fill_prompt(_mission(team=two["team"]), two).count("## Team") == 1
