"""
RELAY-SOLARIS L2 — wiring verifier for ``synapse_solaris_create_variants``.

Source of truth: ``synapse/mcp/tools/solaris/create_variants.py`` ``execute()``
(lines 111-225). Two branches:

* ``variant_type="geometry"`` — duplicates componentgeometry per variant, wires
  them all into a ``componentgeometryvariants``.
* ``variant_type="material"`` — duplicates componentmaterial per variant.

HISTORY — F4/F5, REPAIRED in SR1 M4:

F4  The ``material`` branch never called ``setInput`` on the duplicated
    ``componentmaterial`` nodes. ``hou.copyNodesTo`` does not carry input
    connections to nodes outside the copied set, so each variant landed with
    zero wired inputs against a catalogued ``min_inputs=1``. Fixed at
    ``create_variants.py:168-170`` (base inputs replayed onto each copy).
F5  In the ``geometry`` branch ``componentgeometryvariants`` collected the
    variants but was never wired downstream, so the variant set never reached
    the terminal. Fixed at ``create_variants.py:204-219`` (base geo wired in,
    consumers stolen).

F6 (bare ``except Exception: pass`` under ``status="created"``) is likewise
repaired and pinned by ``tests/solaris/test_create_variants.py``.

SR1 SEAM FIX — the literals below were hand-captured "as emitted today" BEFORE
F4/F5 and were never updated, so they asserted a defect that no longer existed:
a check that cannot fail correctly (Law 1). They now declare the post-F4/F5
topology, live-confirmed against the real emission by
``harness/notes/sr1_seam_probe.py`` LEG-2. They are still falsifiable — revert
either fix and ``geo_variants``/``mat_*`` drop back to dead-end / min_inputs
failures.

RESIDUAL, recorded not fixed: the material branch wires each variant's INPUTS
but nothing consumes the variants, so ``mat_red``/``mat_blue`` remain dead ends
(there is no ``componentmaterialvariants`` merge in the emission). That is a
distinct defect from F4 and outside the SR1 M4 grant; ``verify_static_material``
therefore still reports FAIL, now on ``dead_end[...]`` only.
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "synapse_solaris_create_variants"

#: geometry branch, post-F4/F5. The variant set consumes the base geometry AND
#: every copy, and has taken over the base geometry's consumers -- so the
#: component presents exactly one terminal (``output_base``).
EXPECTED_TOPOLOGY_GEOMETRY: List[Dict[str, Any]] = [
    {"name": "geo_base", "type": "componentgeometry", "inputs": []},
    {"name": "geo_red", "type": "componentgeometry", "inputs": []},
    {"name": "geo_blue", "type": "componentgeometry", "inputs": []},
    {"name": "geo_variants", "type": "componentgeometryvariants",
     "inputs": ["geo_base", "geo_red", "geo_blue"]},
    {"name": "mat_base", "type": "componentmaterial", "inputs": ["geo_variants"]},
    {"name": "output_base", "type": "componentoutput", "inputs": ["mat_base"]},
]

#: material branch, post-F4. Each variant material replays the base material's
#: inputs, so ``min_inputs`` is satisfied. Nothing consumes them yet -- see the
#: RESIDUAL note in the module docstring.
EXPECTED_TOPOLOGY_MATERIAL: List[Dict[str, Any]] = [
    {"name": "geo_base", "type": "componentgeometry", "inputs": []},
    {"name": "mat_base", "type": "componentmaterial", "inputs": ["geo_base"]},
    {"name": "mat_red", "type": "componentmaterial", "inputs": ["geo_base"]},
    {"name": "mat_blue", "type": "componentmaterial", "inputs": ["geo_base"]},
    {"name": "output_base", "type": "componentoutput", "inputs": ["mat_base"]},
]

#: The explore node the tool adds in the PARENT network, fed by the component.
EXPECTED_TOPOLOGY_EXPLORE: List[Dict[str, Any]] = [
    {"name": "component", "type": "subnet", "inputs": []},
    {"name": "explore_component", "type": "explorevariants", "inputs": ["component"]},
]


def verify_static_geometry(catalog=None) -> Dict[str, Any]:
    """Post-F5 this PASSES: geo_variants reaches the terminal."""
    return common.verify_static(TOOL + ":geometry",
                                EXPECTED_TOPOLOGY_GEOMETRY, catalog)


def verify_static_material(catalog=None) -> Dict[str, Any]:
    """Post-F4 ``min_inputs`` passes; still FAILS on the residual dead ends."""
    return common.verify_static(TOOL + ":material",
                                EXPECTED_TOPOLOGY_MATERIAL, catalog)


def verify_static_explore(catalog=None) -> Dict[str, Any]:
    """The explore node IS correctly wired -- this branch should PASS."""
    return common.verify_static(TOOL + ":explore",
                                EXPECTED_TOPOLOGY_EXPLORE, catalog)


def unwired_variant_materials() -> List[str]:
    """Names of material variants emitted with zero wired inputs.

    Post-F4 this is empty. Non-empty is a regression, not a status quo.
    """
    return [n["name"] for n in EXPECTED_TOPOLOGY_MATERIAL
            if n["type"] == "componentmaterial" and not (n.get("inputs") or [])]


def live_build(comp, variant_type: str = "geometry"):
    tool = common.load_tool("create_variants")
    parent = comp.parent()
    before = set(comp.children()) | set(parent.children())
    tool.execute({
        "component_path": comp.path(),
        "variant_type": variant_type,
        "variants": [{"name": "red"}, {"name": "blue"}],
    })
    now = set(comp.children()) | set(parent.children())
    return [n for n in now if n not in before]


def verify_live(comp, variant_type: str = "geometry") -> Dict[str, Any]:
    return common.verify_live(TOOL, live_build(comp, variant_type))
