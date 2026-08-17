# test_bastion_v2.py - BASTION harness v2 self-test. Stock pytest, pure Python,
# NO hou. Covers the three W8-SMITH acceptance predicates:
#   1. schema round-trip (incl. the v2 skills[] field)
#   2. compile of a fixture mission carrying skills[] -> brief lists the skills
#   3. bus kind validation (typed CLAIM/FINDING/HANDOFF/BLOCK/RELEASE on write)
# Skip is NOT pass: every test asserts real behaviour and must actually run.
import json
import sys
from pathlib import Path

# Put the bastion dir on sys.path[0] so `mission_schema`/`compile_wave`/`bus`
# resolve to THIS harness (not the same-named autorevise modules).
BASTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASTION))

import mission_schema as ms   # noqa: E402
import compile_wave as cw     # noqa: E402
import bus                    # noqa: E402

FIXTURE = BASTION / "fixtures" / "w99_skills.json"
TEMPLATE = BASTION / "prompts" / "_template.md"


def _valid_mission_with_skills():
    return {
        "id": "W99-RT",
        "band": "BUILD",
        "name": "round-trip mission with skills[]",
        "source": {"doc": "harness/bastion/PROGRAM.md", "anchor": "HARNESS-V2-SMITH"},
        "targets": ["x"],
        "skills": ["harness/bastion/skills/a.md", "/mnt/skills/public/artifact-design"],
        "deps": [],
        "readonly": False,
        "touches": ["harness/bastion/"],
        "crucible_criteria": ["c"],
        "acceptance": [{"predicate": "p", "evidence": "test"}],
    }


# ---- 1. schema round-trip -------------------------------------------------

def test_schema_accepts_skills_and_round_trips():
    m = _valid_mission_with_skills()
    assert ms.validate_mission(m) == []
    # JSON round-trip must not change the verdict.
    m2 = json.loads(json.dumps(m))
    assert ms.validate_mission(m2) == []
    assert m2["skills"] == m["skills"]


def test_schema_skills_is_optional():
    m = _valid_mission_with_skills()
    del m["skills"]
    assert ms.validate_mission(m) == []


def test_schema_rejects_bad_skills_shape():
    m = _valid_mission_with_skills()
    m["skills"] = "not-a-list"
    errs = ms.validate_mission(m)
    assert any("skills must be a list" in e for e in errs)

    m["skills"] = ["ok", 42, ""]
    errs = ms.validate_mission(m)
    assert any("skills[1]" in e for e in errs)
    assert any("skills[2]" in e for e in errs)


def test_fixture_file_validates():
    m = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert ms.validate_mission(m) == []
    assert m["skills"]  # fixture carries skills[]


# ---- 2. compile of a fixture mission carrying skills[] --------------------

def test_compile_injects_skills_into_brief(tmp_path):
    missions = tmp_path / "missions"
    prompts = tmp_path / "prompts"
    waves = tmp_path / "waves"
    missions.mkdir()
    (missions / "w99_skills.json").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    rc = cw.main(mission_dir=missions, prompts_dir=prompts,
                 waves_dir=waves, template_path=TEMPLATE)
    assert rc == 0

    brief = (prompts / "W99-SKILLS.md").read_text(encoding="utf-8")
    m = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for s in m["skills"]:
        assert s in brief, f"skill path {s!r} missing from compiled brief"
    assert "{SKILLS}" not in brief  # placeholder fully substituted

    rows = json.loads((waves / "wave99.rows.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["id"] == "W99-SKILLS"
    assert rows[0]["prompt"] == "harness/bastion/prompts/W99-SKILLS.md"


def test_compile_renders_none_when_no_skills(tmp_path):
    missions = tmp_path / "missions"
    missions.mkdir()
    m = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del m["skills"]
    m["id"] = "W99-NOSK"
    (missions / "m.json").write_text(json.dumps(m), encoding="utf-8")
    rc = cw.main(mission_dir=missions, prompts_dir=tmp_path / "p",
                 waves_dir=tmp_path / "w", template_path=TEMPLATE)
    assert rc == 0
    brief = (tmp_path / "p" / "W99-NOSK.md").read_text(encoding="utf-8")
    assert "None declared" in brief  # explicit, never a silent empty section


# ---- 3. bus kind validation ----------------------------------------------

def test_bus_accepts_typed_and_operational_kinds():
    for k in ["CLAIM", "Finding", "handoff", "BLOCK", "release",
              "request", "spawn", "status"]:
        assert bus.canonical_kind(k) == k.lower()


def test_bus_rejects_unknown_kind():
    import pytest
    with pytest.raises(bus.BusKindError):
        bus.canonical_kind("gossip")
    with pytest.raises(bus.BusKindError):
        bus.canonical_kind("")


def test_bus_post_refuses_bad_kind_and_writes_good(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    import pytest
    with pytest.raises(bus.BusKindError):
        bus.post("wave99", "W99-RT", "gossip", {"x": 1})

    msg = bus.post("wave99", "W99-RT", "CLAIM", {"files": ["a"]})
    assert msg["type"] == "claim"  # canonicalised to lowercase on storage
    got = bus.read("wave99")
    assert len(got) == 1 and got[0]["type"] == "claim"


def test_bus_release_closes_claim_both_idioms(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "BUS_ROOT", tmp_path / "bus")
    # v2 first-class RELEASE kind closes a matching claim.
    bus.post("wave99", "A", "claim", {"files": ["f1"]})
    assert len(bus.open_claims("wave99")) == 1
    assert bus.has_release("wave99", "A") is False
    bus.post("wave99", "A", "release", {"release": ["f1"]})
    assert bus.open_claims("wave99") == []
    assert bus.has_release("wave99", "A") is True

    # autorevise idiom (status + body.release) still closes - back-compat with
    # the shipped orchestrator close-gate (orchestrate.ps1:206,211).
    bus.post("wave99", "B", "claim", {"files": ["f2"]})
    assert any(c["frm"] == "B" for c in bus.open_claims("wave99"))
    bus.post("wave99", "B", "status", {"release": ["f2"]})
    assert not any(c["frm"] == "B" for c in bus.open_claims("wave99"))
    assert bus.has_release("wave99", "B") is True
