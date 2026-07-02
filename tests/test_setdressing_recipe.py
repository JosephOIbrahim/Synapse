"""Pin the Solaris set-dressing recipe to live-verified node types + RAW USD names.

The 2026-06-26 live probe on Houdini 21.0.671 established the set-dressing
ground truth this recipe is built on:

  * The set-dressing LOP types that EXIST: instancer, layout, duplicate,
    componentgeometry, componentoutput, extractinstances, mergepointinstancers,
    modifypointinstances, splitpointinstancers. There is NO native Solaris
    scatter LOP -- scatter is SOP-side, brought in via sopimport.
  * set_usd_attribute authors the RAW USD attribute name (prim.GetAttribute
    (name).Set under an `if attr:` guard). A punycode (xn__) name resolves to
    an INVALID attribute and SILENTLY NO-OPS. Raw schema names (protoIndices,
    positions, inputs:*) are stable across Houdini/USD builds -> H22-safe.

These tests assert the ``solaris_scatter_instances`` recipe registers, that
every ``create_node`` type it emits is in the verified-existing set, and that
no USD attribute name is a punycode (xn__) spelling.

NO Houdini import -- pure data checks on the recipe templates.
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Bootstrap: package root is <repo>/python -------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.routing.recipes import Recipe, RecipeRegistry  # noqa: E402
from synapse.routing.recipes.scene_recipes import (  # noqa: E402
    register_scene_recipes,
)

RECIPE_NAME = "solaris_scatter_instances"

# Node-type spellings verified present in the live H21.0.671 catalog for
# Solaris set-dressing, plus the generic stage-composition LOP `merge`. Every
# create_node type the recipe emits must be a member of this set.
VERIFIED_NODE_TYPES = {
    "instancer",
    "layout",
    "duplicate",
    "componentgeometry",
    "componentoutput",
    "extractinstances",
    "mergepointinstancers",
    "modifypointinstances",
    "splitpointinstancers",
    "sopimport",
    "merge",
}

# RAW USD names the recipe is allowed to author. Punycode (xn__) is forbidden.
ALLOWED_USD_ATTRIBUTES = {"protoIndices", "positions"}


def _scene_registry() -> RecipeRegistry:
    """A registry containing ONLY the scene recipes (no other built-ins)."""
    reg = RecipeRegistry(include_builtins=False)
    register_scene_recipes(reg)
    return reg


def _get_recipe(reg: RecipeRegistry) -> Recipe:
    for recipe in reg.recipes:
        if recipe.name == RECIPE_NAME:
            return recipe
    raise AssertionError(f"{RECIPE_NAME!r} not registered by register_scene_recipes")


def _create_node_types(recipe: Recipe):
    for step in recipe.steps:
        if step.action == "create_node":
            yield step.payload_template["type"]


def _usd_attribute_names(recipe: Recipe):
    for step in recipe.steps:
        if step.action == "set_usd_attribute":
            yield step.payload_template["usd_attribute"]


# ===========================================================================
# 1. Registration
# ===========================================================================

def test_recipe_registers():
    recipe = _get_recipe(_scene_registry())
    assert recipe.name == RECIPE_NAME
    assert recipe.steps, "recipe has no steps"
    assert recipe.category == "set_dressing"


def test_recipe_present_in_full_builtin_registry():
    # The default registry (all built-ins) must also carry it.
    names = {r.name for r in RecipeRegistry().recipes}
    assert RECIPE_NAME in names


# ===========================================================================
# 2. Every create_node type is live-verified
# ===========================================================================

def test_all_create_node_types_are_verified():
    recipe = _get_recipe(_scene_registry())
    used = list(_create_node_types(recipe))
    assert used, "recipe creates no nodes"
    for node_type in used:
        assert node_type in VERIFIED_NODE_TYPES, (
            f"{RECIPE_NAME}: create_node type {node_type!r} is not a "
            f"live-verified set-dressing/LOP type"
        )


def test_no_native_solaris_scatter_lop():
    # There is no native Solaris scatter LOP; scatter is SOP-side + sopimport.
    recipe = _get_recipe(_scene_registry())
    assert "scatter" not in set(_create_node_types(recipe)), (
        "recipe emits a `scatter` LOP -- no native Solaris scatter LOP exists; "
        "use a SOP scatter brought in via sopimport"
    )
    assert "sopimport" in set(_create_node_types(recipe)), (
        "recipe must import scatter points via sopimport"
    )


# ===========================================================================
# 3. USD attributes use RAW names, never punycode
# ===========================================================================

def test_usd_attributes_are_raw_names_not_punycode():
    recipe = _get_recipe(_scene_registry())
    attrs = list(_usd_attribute_names(recipe))
    assert attrs, "recipe sets no USD attributes"
    for name in attrs:
        assert not name.startswith("xn__"), (
            f"{RECIPE_NAME}: USD attribute {name!r} is a punycode spelling -- "
            f"set_usd_attribute silently no-ops on those; use the RAW name"
        )
        assert name in ALLOWED_USD_ATTRIBUTES, (
            f"{RECIPE_NAME}: unexpected USD attribute {name!r}"
        )


def test_no_punycode_anywhere_in_recipe():
    recipe = _get_recipe(_scene_registry())
    blob = repr([step.payload_template for step in recipe.steps])
    assert "xn__" not in blob, "punycode (xn__) leaked into a recipe payload"


def test_point_instancer_prim_authored():
    recipe = _get_recipe(_scene_registry())
    prim_types = [
        step.payload_template.get("prim_type")
        for step in recipe.steps
        if step.action == "create_usd_prim"
    ]
    assert "PointInstancer" in prim_types, (
        "recipe must author a PointInstancer prim"
    )


# ===========================================================================
# 4. Triggers fire on natural phrasing
# ===========================================================================

def test_triggers_match_natural_phrasing():
    # Note: "scatter X on/onto/over Y" is owned by the earlier-registered
    # scatter_copy recipe (copy-to-points). This recipe wins the unambiguous
    # set-dressing / instancer phrasings and the non-colliding connectors.
    reg = _scene_registry()
    for phrase in (
        "solaris set dressing in /stage",
        "scatter instances across /stage",
        "set up a point instancer",
    ):
        match = reg.match(phrase)
        assert match is not None, f"no recipe matched {phrase!r}"
        recipe, _params = match
        assert recipe.name == RECIPE_NAME, (
            f"{phrase!r} matched {recipe.name!r}, expected {RECIPE_NAME!r}"
        )


def test_parent_param_captured():
    recipe = _get_recipe(_scene_registry())
    params = recipe.match("solaris set dressing in /stage/shot01")
    assert params is not None
    assert params["parent"] == "/stage/shot01"
