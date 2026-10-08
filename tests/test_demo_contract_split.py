"""Pins the 2026-10-07 amendment of the demo contracts (Jev rulings, cto-postdemo ledger).

demo-round-trip.yaml adopts the three-part pass test and drops payload.hit; the Gate 0 GUI half and
the Ctrl+Z receipt live in demo-gate0-gui.yaml of their own. Stop dates are Joe's call, so the
ratified stop_when string is pinned unchanged. Pure Python: reads two yaml files, nothing else.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import yaml  # pyyaml is a dev dependency (pyproject); a skip here would be an abstention printed as PASS

_CONTRACTS = Path(__file__).resolve().parent.parent / ".synapse" / "contracts"
_ROUND_TRIP = _CONTRACTS / "demo-round-trip.yaml"
_GATE0 = _CONTRACTS / "demo-gate0-gui.yaml"

_RATIFIED_STOP_WHEN = (
    "both takes HIT (branch: Sep 6 stands) OR Tue 18:00 passes without two HITs "
    "(branch: Sep 13) — the decision is a receipt, not a feeling"
)
_PREDICATE = (
    "found=true",
    "matches[0].id == the deposit id",
    "source=knowledge",
)


def _load(path: Path) -> dict:
    assert path.is_file(), f"missing contract: {path.name}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def round_trip() -> dict:
    return _load(_ROUND_TRIP)


@pytest.fixture(scope="module")
def gate0() -> dict:
    return _load(_GATE0)


def _blob(contract: dict) -> str:
    return yaml.safe_dump(contract, allow_unicode=True)


def test_round_trip_goal_states_three_part_predicate(round_trip):
    goal = round_trip["goal"]
    for clause in _PREDICATE:
        assert clause in goal, clause
    assert "no match with source=knowledge" in goal


def test_round_trip_takes_carry_predicate_and_project_scope(round_trip):
    take1 = round_trip["features"][0]["description"]
    assert take1.startswith("round-trip take 1:")
    for clause in _PREDICATE:
        assert clause in take1, clause
    assert "synapse_decide, scope=project" in take1
    assert "synapse_recall, scope=project" in take1
    goal = round_trip["goal"]
    assert "synapse_decide, scope=project" in goal
    assert "synapse_recall, scope=project" in goal
    take2 = round_trip["features"][1]
    assert take2["description"].startswith("round-trip take 2:")
    for take in round_trip["features"]:
        assert "deposit_id" in take["verify"]
        assert "recall scope" in take["verify"]


def test_payload_hit_is_gone(round_trip):
    assert "payload.hit" not in _blob(round_trip)
    assert "payload.hit" not in _ROUND_TRIP.read_text(encoding="utf-8").split("id: demo-round-trip", 1)[1]


def test_round_trip_is_judged_on_memory_alone(round_trip):
    descs = [f["description"] for f in round_trip["features"]]
    assert len(descs) == 2
    assert all(d.startswith("round-trip take") for d in descs)
    blob = _blob(round_trip)
    for gone in ("probe_silent_recall", "silent_recall_gui", "Gate 0", "Ctrl+Z"):
        assert gone not in blob, gone


def test_gate0_contract_holds_the_split_features(gate0):
    assert gate0["id"] == "demo-gate0-gui"
    descs = [f["description"] for f in gate0["features"]]
    assert len(descs) == 2
    assert descs[0].startswith("Gate 0 GUI half run at the rig: probe_silent_recall.py emits four rows")
    assert descs[1].startswith("Ctrl+Z GUI receipt")
    assert "W5-UNDO-GUI" in descs[1]
    assert gate0["features"][0]["verify"] == (
        "silent_recall_gui.json exists with four rows, environment=gui, build runtime-observed")
    assert any("silent_recall_gui.json" in o for o in gate0["owns"])
    assert ".synapse/contracts/demo-gate0-gui.yaml" in gate0["owns"]


@pytest.mark.parametrize("which", ["round_trip", "gate0"])
def test_both_stay_red_and_unflipped(which, request):
    c = request.getfixturevalue(which)
    assert c["autonomy"] == "red"
    assert c["model"] == "opus"
    assert c["do_not_touch"] == ["python/**", "VERSION"]
    assert c["features"], "no features"
    for f in c["features"]:
        assert set(f) == {"description", "verify", "passing"}
        assert f["passing"] is False
    assert isinstance(c["stop_when"], str) and c["stop_when"]


def test_stop_dates_untouched_and_marked_joes_call(round_trip):
    assert round_trip["stop_when"] == _RATIFIED_STOP_WHEN
    text = _ROUND_TRIP.read_text(encoding="utf-8")
    assert "# New stop dates are Joe's call" in text
    assert "Sep" not in _GATE0.read_text(encoding="utf-8").split("stop_when:", 1)[1]
