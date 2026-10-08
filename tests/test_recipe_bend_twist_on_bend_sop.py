"""bend_twist twists with the Bend SOP's own twist, not the deprecated Twist SOP.

Houdini 22.0.400 marks the Twist SOP deprecated (rag/catalog/h22.0.400/Sop.json,
``types.twist.deprecated``). The Bend SOP carries its own twist: ``enabletwist``
(Toggle, default off) and ``twist`` (Float). Both names were probed live on
hython 22.0.400 (cto-20261007 assay_lx.log:60-71, re-probed for this change):
setting ``twist`` without ``enabletwist`` leaves the geometry unchanged, so the
recipe must turn the toggle on.

Pure Python: no hou.
"""
from __future__ import annotations

import json
from pathlib import Path

from synapse.panel.recipe_book import RECIPES, build_recipe_messages

ROOT = Path(__file__).resolve().parent.parent
SOP_CATALOG = ROOT / "rag" / "catalog" / "h22.0.400" / "Sop.json"


def _sop_types():
    return json.loads(SOP_CATALOG.read_text(encoding="utf-8"))["types"]


def _recipe():
    return RECIPES["deformation"]["bend_twist"]


def _text():
    messages = build_recipe_messages("deformation", "bend_twist", {"parent_path": "/obj/geo1"})
    assert messages
    return "\n".join(m["content"] for m in messages if isinstance(m.get("content"), str))


def test_the_twist_sop_is_deprecated_in_the_catalogue():
    # The premise of the change: if this ever flips, the move is worth revisiting.
    types = _sop_types()
    assert types["twist"].get("deprecated") is True
    assert types["bend"].get("deprecated") is False


def test_bend_twist_creates_no_twist_sop():
    recipe = _recipe()
    assert [n["type"] for n in recipe["nodes"]] == ["tube", "bend"]
    assert recipe["connections"] == [["tube1", "bend1", 0]]
    text = _text()
    assert "type='twist'" not in text
    assert "strength" not in text


def test_bend_twist_turns_on_the_bend_sops_own_twist():
    bend = next(n for n in _recipe()["nodes"] if n["name"] == "bend1")
    assert bend["type"] == "bend"
    assert bend["parms"] == {"bend": 45, "enabletwist": 1, "twist": 180}
    text = _text()
    assert "type='bend' name='bend1'" in text
    assert "enabletwist = 1" in text and "twist = 180" in text and "bend = 45" in text


def test_bend_twist_key_parms_name_the_toggle_and_the_angle():
    recipe = _recipe()
    assert recipe["key_parms"] == ["bend", "enabletwist", "twist"]
    assert "Key parameters to set: bend, enabletwist, twist" in _text()


def test_bend_twist_parms_exist_on_the_bend_sop_in_the_catalogue():
    records = {r["name"]: r for r in _sop_types()["bend"]["parms"]}
    assert records["enabletwist"]["type"] == "Toggle"
    assert records["twist"]["type"] == "Float"
    assert records["twist"]["min"] <= 180 <= records["twist"]["max"]
    for parm in _recipe()["nodes"][1]["parms"]:
        assert parm in records, parm


def test_bend_twist_prose_no_longer_points_at_a_separate_twist_node():
    recipe = _recipe()
    prose = " ".join([recipe["description"], recipe["explanation"], *recipe["tips"]])
    assert "after twist" not in prose
    assert "Chains a bend and twist deformer" not in prose
    assert "enabletwist" in prose or "Enable Twist" in prose
