"""Recipe Book recipes name node types and parms that Houdini 22.0.400 has.

Each recipe below once told the model to create a node type or set a parm the
22.0.400 runtime does not have. The names asserted here come from a live,
isolated hython 22.0.400 assay (cto-20261007 assay_lx.log), and every node and
parm in these recipes is also checked against the catalogue file of the
recipe's own context (rag/catalog/h22.0.400/Sop.json or Lop.json). The
cross-category alias table in test_harden_catalog_conformance is too lenient
here: it accepts ``bendangle`` for ``bend`` because another category's ``bend``
has it.

Pure Python: no hou.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse.panel.recipe_book import RECIPES, build_recipe_messages

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "rag" / "catalog" / "h22.0.400"
_CONTEXT_FILE = {"SOP": "Sop.json", "LOP": "Lop.json"}
_CACHE: dict = {}


def _types(context):
    name = _CONTEXT_FILE[context]
    if name not in _CACHE:
        _CACHE[name] = json.loads((CATALOG / name).read_text(encoding="utf-8"))["types"]
    return _CACHE[name]


def _parm(context, node_type, parm):
    for record in _types(context)[node_type].get("parms") or []:
        if record.get("name") == parm:
            return record
    return None


def _node(recipe, name):
    return next(n for n in recipe["nodes"] if n["name"] == name)


def _message_text(category, recipe_name):
    messages = build_recipe_messages(category, recipe_name, {"parent_path": "/obj/geo1"})
    assert messages, (category, recipe_name)
    return "\n".join(m["content"] for m in messages if isinstance(m.get("content"), str))


def _assert_recipe_resolves(category, recipe_name):
    recipe = RECIPES[category][recipe_name]
    context = recipe["context"]
    types = _types(context)
    for node in recipe["nodes"]:
        assert node["type"] in types, (recipe_name, node["type"], _CONTEXT_FILE[context])
        for parm in node["parms"]:
            assert _parm(context, node["type"], parm) is not None, (
                recipe_name, node["type"], parm, _CONTEXT_FILE[context])
    names = {n["name"] for n in recipe["nodes"]}
    for src, dst, _ in recipe["connections"]:
        assert src in names and dst in names, (recipe_name, src, dst)


# -- LX-06: asset_structure ends in the USD ROP LOP, not the phantom 'usdrop' --

def test_asset_structure_writes_through_the_usd_rop_lop():
    recipe = RECIPES["usd"]["asset_structure"]
    types = [n["type"] for n in recipe["nodes"]]
    assert "usdrop" not in types
    assert types[-1] == "usd_rop"
    assert ["configure1", "usd_rop1", 0] in recipe["connections"]
    text = _message_text("usd", "asset_structure")
    assert "type='usd_rop'" in text
    assert "usdrop" not in text.replace("usd_rop", "")


def test_asset_structure_resolves_in_the_lop_catalogue():
    _assert_recipe_resolves("usd", "asset_structure")


# -- LX-04: trail_effect sets trail.length and draws lines ('poly'), not a mesh --

def test_trail_effect_sets_the_real_length_parm_and_the_lines_result():
    recipe = RECIPES["motion"]["trail_effect"]
    parms = _node(recipe, "trail1")["parms"]
    assert "traillength" not in parms
    assert parms["length"] == 10
    # The recipe draws trail lines and fades alpha along each one, so the
    # result menu entry is 'poly' (Connect as Polygons), not 'mesh'.
    tokens = _parm("SOP", "trail", "result")["menu_tokens"]
    assert tokens[parms["result"]] == "poly", tokens
    assert "traillength" not in recipe["key_parms"]
    assert "length" in recipe["key_parms"]
    assert not any("Connect as Trails" in tip for tip in recipe["tips"])
    text = _message_text("motion", "trail_effect")
    assert "length = 10" in text and "result = 2" in text
    assert "traillength" not in text


def test_trail_effect_resolves_in_the_sop_catalogue():
    _assert_recipe_resolves("motion", "trail_effect")


# -- LX-05: bend_twist sets bend.bend and twists on the Bend SOP itself --
# (the Twist SOP is deprecated in 22.0.400; see test_recipe_bend_twist_on_bend_sop)

def test_bend_twist_sets_the_real_bend_and_twist_parms():
    recipe = RECIPES["deformation"]["bend_twist"]
    bend = _node(recipe, "bend1")["parms"]
    assert "bendangle" not in bend and bend["bend"] == 45
    assert bend["enabletwist"] == 1 and bend["twist"] == 180
    assert not any(n["type"] == "twist" for n in recipe["nodes"])
    assert _parm("SOP", "bend", "enabletwist")["type"] == "Toggle"
    assert recipe["key_parms"] == ["bend", "enabletwist", "twist"]
    text = _message_text("deformation", "bend_twist")
    assert "bend = 45" in text and "twist = 180" in text
    assert "bendangle" not in text
    assert "strength" not in text


def test_bend_twist_resolves_in_the_sop_catalogue():
    _assert_recipe_resolves("deformation", "bend_twist")
