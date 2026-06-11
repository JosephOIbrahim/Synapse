"""Pin APEX recipe node-type names to the science authority.

The 2026-06-02 science run (``synapse/science/apex_probes.py`` +
``docs/SCIENCE_apex_verify_run_2026-06-02.md``) established that the
``apex::rig::`` / ``apex::sop::`` / ``apex::autorig::`` namespacing the
recipes invented does NOT exist in the live H21.0.671 catalog. These tests
pin ``panel/apex_recipes.py`` to the corrected, catalog-verified names and
to the truth-contract caveats that mark what is still behavior-UNVERIFIED.

NO Houdini, NO apex import -- pure data checks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# --- Bootstrap: package root is <repo>/python -------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.panel.apex_recipes import (  # noqa: E402
    APEX_RECIPES,
    KINEFX_MIGRATION_GUIDE,
    build_apex_recipe_messages,
)
from synapse.science.apex_probes import APEX_SEED  # noqa: E402

# The phantom namespacing the original recipes invented.
FICTIONAL = re.compile(r"apex::(rig|sop|autorig)::")

# Legacy un-namespaced strings that were never types.
LEGACY_TYPES = {"rig_doctor", "apex_editgraph", "invoke"}

# Node-type spellings verified present in the live H21.0.671 catalog
# (kind="nodetype" probes in the science seed -- the mapping authority).
SEED_NODETYPES = {
    s.surface.removeprefix("nodetypes.") for s in APEX_SEED if s.kind == "nodetype"
}

# Un-namespaced strings deliberately NOT migrated this pass: bonegenerator and
# bare "skeleton" were never part of the 2026-06-02 APEX_SEED probe set -- a
# follow-up probe must establish their real catalog spellings. "null" is a
# stock SOP type, not a recipe invention.
EXEMPT_UNNAMESPACED = {"bonegenerator", "skeleton", "null"}

# Recipes that carry a truth-contract caveat after the migration.
CAVEAT_RECIPES = (
    "ik_chain",
    "fk_ik_blend",
    "control_shapes",
    "constraint_setup",
    "kinefx_to_apex",
)


def _all_node_types():
    for name, recipe in APEX_RECIPES.items():
        for node in recipe["nodes"]:
            yield name, node["type"]


# ===========================================================================
# 1. No phantom namespacing in node types
# ===========================================================================

def test_no_phantom_namespacing_in_node_types():
    for recipe_name, node_type in _all_node_types():
        assert not FICTIONAL.search(node_type), (
            f"{recipe_name}: phantom-namespaced type {node_type!r}"
        )
        assert node_type not in LEGACY_TYPES, (
            f"{recipe_name}: legacy non-type string {node_type!r}"
        )


# ===========================================================================
# 2. Every namespaced type is pinned to the science authority
# ===========================================================================

def test_node_types_pinned_to_science_seed():
    for recipe_name, node_type in _all_node_types():
        if "::" in node_type:
            assert node_type in SEED_NODETYPES, (
                f"{recipe_name}: type {node_type!r} is not a catalog-verified "
                f"APEX_SEED nodetype member"
            )
        else:
            assert node_type in EXEMPT_UNNAMESPACED, (
                f"{recipe_name}: un-namespaced type {node_type!r} is neither "
                f"seed-verified nor an exempted legacy string"
            )


# ===========================================================================
# 3. The "guess similar names" instruction is dead
# ===========================================================================

def test_guess_instruction_replaced_by_scout():
    text = build_apex_recipe_messages("fk_chain", {})[0]["content"]
    assert "check for similar types" not in text
    assert "synapse_scout" in text


# ===========================================================================
# 4. Text fields (prose + migration guide) are clean
# ===========================================================================

def test_text_fields_clean_of_fictional_names():
    blob = repr(APEX_RECIPES) + KINEFX_MIGRATION_GUIDE
    match = FICTIONAL.search(blob)
    assert match is None, f"phantom namespacing survives in text: {match.group(0)!r}"
    assert "apex_editgraph" not in blob
    assert "apex::rig::fbik" not in blob


# ===========================================================================
# 5. Truth-contract caveat markings
# ===========================================================================

def test_constraint_setup_caveat_is_unverified():
    caveat = APEX_RECIPES["constraint_setup"]["caveat"]
    assert "UNVERIFIED" in caveat
    assert "apex.Constraint" in caveat


def test_ik_caveats_name_the_graph_internal_vop_constraint():
    for name in ("ik_chain", "fk_ik_blend"):
        caveat = APEX_RECIPES[name]["caveat"]
        assert "Vop" in caveat, f"{name}: caveat missing the Vop constraint"
        assert "INSIDE the APEX graph" in caveat, (
            f"{name}: caveat missing the graph-internal constraint"
        )


def test_caveat_rendered_into_build_messages():
    for name in CAVEAT_RECIPES:
        caveat = APEX_RECIPES[name]["caveat"]
        text = build_apex_recipe_messages(name, {})[0]["content"]
        assert caveat in text, f"{name}: caveat not rendered into instruction"
