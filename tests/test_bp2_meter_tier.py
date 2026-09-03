# tests/test_bp2_meter_tier.py - BP2-METER T2 tier plumbing.
#
# The optional per-leg `tier` travels: mission_schema accepts it (OPTIONAL),
# compile_wave carries it onto the row ONLY when present (a tier-less row stays
# byte-identical), and rails_exec.json + resolve turn a tier into a model. This
# pins the seam so a future doc/code drift fails loud. Pure Python, zero deps.
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "harness"))

# Load the battleplan modules BY FILE PATH under unique names: six harnesses under
# harness/ each ship a mission_schema.py / compile_wave.py, and a bare import returns
# whichever one an earlier test cached in sys.modules (integration finding 2026-09-01).
import importlib.util  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / "harness" / "battleplan" / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ms = _load("bp_mission_schema", "mission_schema.py")
# compile_wave does a bare `import mission_schema` of its sibling: hand it the battleplan
# module for the duration of its load, then restore whatever the rest of the suite had.
_prev = sys.modules.get("mission_schema")
sys.modules["mission_schema"] = ms
try:
    cw = _load("bp_compile_wave", "compile_wave.py")
finally:
    if _prev is None:
        sys.modules.pop("mission_schema", None)
    else:
        sys.modules["mission_schema"] = _prev
from rails import resolve_model  # noqa: E402

BASE = {
    "id": "BP2-METER", "name": "n", "band": "BUILD",
    "source": {"doc": "docs/BATTLEPLAN.md", "anchor": "sec.6"},
    "targets": ["T1"], "acceptance": [{"predicate": "p", "evidence": "test"}],
    "deps": [], "readonly": False, "touches": ["harness/"],
    "crucible_criteria": ["c"],
}


def test_tier_is_an_accepted_optional_field():
    assert "tier" in ms.OPTIONAL
    assert ms.validate_mission(dict(BASE)) == []            # tier-less validates
    assert ms.validate_mission({**BASE, "tier": "referee"}) == []  # with tier too


def test_unknown_field_still_rejected():
    # the OPTIONAL widening is surgical - a genuinely unknown field still fails
    errs = ms.validate_mission({**BASE, "bogus": 1})
    assert any("unknown field" in e for e in errs)


def test_leg_row_omits_tier_when_absent_and_carries_it_when_present():
    assert "tier" not in cw.leg_row(dict(BASE))             # byte-identical default
    assert cw.leg_row({**BASE, "tier": "referee"})["tier"] == "referee"


def test_referee_tier_resolves_to_fable5():
    assert resolve_model("referee") == "claude-fable-5-1"  # BP4 2026-09-03: referee bumped to Fable 5.1 (preflight_bp4.json); follows the seam
