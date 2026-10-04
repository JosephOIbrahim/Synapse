"""H-2 (2026-10-04): execute_vex's Run Over tables match the attribwrangle menu.

The oracle is the parm catalog dumped from the recording build
(rag/catalog/h22.0.400/Sop.json): attribwrangle's ``class`` parm lists
Detail, Primitives, Points, Vertices, Numbers, default Points. The installed
22.0.429 help (sop/_run_over.txt) names the same parm "Run Over".
"""
import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "rag" / "catalog" / "h22.0.400" / "Sop.json"


def _find(node, predicate):
    if isinstance(node, dict):
        if predicate(node):
            return node
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find(child, predicate)
        if found is not None:
            return found
    return None


@pytest.fixture(scope="module")
def menu():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    wrangle = _find(data, lambda d: "attribwrangle" in d)["attribwrangle"]
    parm = _find(wrangle, lambda d: d.get("name") == "class" and "menu_tokens" in d)
    assert parm is not None, "attribwrangle 'class' parm not found in the catalog"
    return parm


def test_catalog_menu_is_the_expected_order(menu):
    assert menu["label"] == "Run Over"
    assert menu["menu_tokens"] == ["detail", "primitive", "point", "vertex", "number"]
    assert menu["default"] == 2


def test_handler_table_matches_the_menu(menu):
    from synapse.server.handlers import VEX_RUN_OVER_CLASS
    for index, token in enumerate(menu["menu_tokens"]):
        assert VEX_RUN_OVER_CLASS[token] == index
    for plural, token in (("primitives", "primitive"), ("points", "point"),
                          ("vertices", "vertex"), ("numbers", "number")):
        assert VEX_RUN_OVER_CLASS[plural] == menu["menu_tokens"].index(token)
    # The handler's fallback for an unknown value is the node's own default.
    assert VEX_RUN_OVER_CLASS["points"] == menu["default"]


def _labels(menu):
    return {i: label.split(" (")[0] for i, label in enumerate(menu["menu_labels"])}


def test_vex_tutor_table_matches_the_menu(menu):
    source = (ROOT / "python" / "synapse" / "panel" / "vex_tutor.py").read_text(encoding="utf-8")
    block = re.search(r"^_RUN_OVER_MAP = (\{.*?\})", source, re.S | re.M)
    assert block, "_RUN_OVER_MAP not found"
    assert ast.literal_eval(block.group(1)) == _labels(menu)


def test_scene_recipe_table_matches_the_menu(menu):
    source = (ROOT / "python" / "synapse" / "routing" / "recipes"
              / "scene_recipes.py").read_text(encoding="utf-8")
    joined = re.sub(r'"\s*\n\s*"', "", source)          # undo adjacent-literal wrapping
    block = re.search(r"class_map = \{\{(.*?)\}\}", joined)
    assert block, "class_map not found in the wrangle recipe"
    assert ast.literal_eval("{" + block.group(1) + "}") == _labels(menu)
