"""
RELAY-SOLARIS L2 — wiring verifier for ``synapse_solaris_create_variants``.

Source of truth: ``synapse/mcp/tools/solaris/create_variants.py`` ``execute()``
(lines 111-225). Two branches:

* ``variant_type="geometry"`` — duplicates componentgeometry per variant, wires
  them all into a ``componentgeometryvariants``.
* ``variant_type="material"`` — duplicates componentmaterial per variant.

WIRING DEFECTS THIS VERIFIER PINS (FINDINGS F4/F5, not fixed here per gate):

F4  The ``material`` branch never calls ``setInput`` on the duplicated
    ``componentmaterial`` nodes. ``hou.copyNodesTo`` does not carry input
    connections to nodes outside the copied set, so each variant lands with
    zero wired inputs against a catalogued ``min_inputs=1``. Live, that is the
    "Not enough sources specified." node error.
F5  In the ``geometry`` branch ``componentgeometryvariants`` collects the
    variants but is itself never wired downstream into the component's
    material/output chain, so the variant set never reaches the terminal.

Both branches are additionally wrapped in bare ``except Exception: pass`` and
still return ``status="created"`` — a silent false-success (F6).
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "synapse_solaris_create_variants"

#: geometry branch, as emitted today (base chain + variant set).
EXPECTED_TOPOLOGY_GEOMETRY: List[Dict[str, Any]] = [
    {"name": "geo_base", "type": "componentgeometry", "inputs": []},
    {"name": "geo_red", "type": "componentgeometry", "inputs": []},
    {"name": "geo_blue", "type": "componentgeometry", "inputs": []},
    {"name": "geo_variants", "type": "componentgeometryvariants",
     "inputs": ["geo_red", "geo_blue"]},
    {"name": "mat_base", "type": "componentmaterial", "inputs": ["geo_base"]},
    {"name": "output_base", "type": "componentoutput", "inputs": ["mat_base"]},
]

#: material branch, as emitted today. Variant materials have NO inputs (F4).
EXPECTED_TOPOLOGY_MATERIAL: List[Dict[str, Any]] = [
    {"name": "geo_base", "type": "componentgeometry", "inputs": []},
    {"name": "mat_base", "type": "componentmaterial", "inputs": ["geo_base"]},
    {"name": "mat_red", "type": "componentmaterial", "inputs": []},
    {"name": "mat_blue", "type": "componentmaterial", "inputs": []},
    {"name": "output_base", "type": "componentoutput", "inputs": ["mat_base"]},
]

#: The explore node the tool adds in the PARENT network, fed by the component.
EXPECTED_TOPOLOGY_EXPLORE: List[Dict[str, Any]] = [
    {"name": "component", "type": "subnet", "inputs": []},
    {"name": "explore_component", "type": "explorevariants", "inputs": ["component"]},
]


def verify_static_geometry(catalog=None) -> Dict[str, Any]:
    """Expected to FAIL ``no_orphans``: geo_variants is a dead end (F5)."""
    return common.verify_static(TOOL + ":geometry",
                                EXPECTED_TOPOLOGY_GEOMETRY, catalog)


def verify_static_material(catalog=None) -> Dict[str, Any]:
    """Expected to FAIL ``min_inputs``: variant materials are unwired (F4)."""
    return common.verify_static(TOOL + ":material",
                                EXPECTED_TOPOLOGY_MATERIAL, catalog)


def verify_static_explore(catalog=None) -> Dict[str, Any]:
    """The explore node IS correctly wired -- this branch should PASS."""
    return common.verify_static(TOOL + ":explore",
                                EXPECTED_TOPOLOGY_EXPLORE, catalog)


def unwired_variant_materials() -> List[str]:
    """Names of material variants emitted with zero wired inputs (F4)."""
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
