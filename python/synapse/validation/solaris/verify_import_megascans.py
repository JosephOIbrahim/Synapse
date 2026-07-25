"""
RELAY-SOLARIS L2 — wiring verifier for ``synapse_solaris_import_megascans``.

Source of truth: ``synapse/mcp/tools/solaris/import_megascans.py`` ``execute()``
(lines 162-258). The tool builds a ``subnet`` and, inside it, a componentgeometry
whose SOP subnet carries the usdimport -> xform -> [matchsize -> xform] ->
polyreduce chain, plus a ``reference`` LOP for materials, a componentmaterial
and a componentoutput.

WIRING DEFECT THIS VERIFIER PINS (see FINDING F3, not fixed here per gate):
``mtl_ref_<asset>`` (the material ``reference`` LOP) is created and its parms
are set, but it is never wired into anything. ``componentmaterial`` gets only
``setInput(0, geo_node)``; input 1 -- the material input -- is left open. The
imported Megascans materials therefore never reach the component. The network
still *composes* (componentmaterial's min_inputs is 1), which is precisely why
an existence-only check misses it and a connectivity check catches it.

``EXPECTED_TOPOLOGY`` below encodes what the tool ACTUALLY emits, so
``verify_static`` reports the orphan honestly rather than describing an
intended-but-absent wiring.
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "synapse_solaris_import_megascans"

#: LOP-level topology emitted inside the component subnet, as built today.
EXPECTED_TOPOLOGY: List[Dict[str, Any]] = [
    {"name": "geo_asset", "type": "componentgeometry", "inputs": []},
    {"name": "mtl_ref_asset", "type": "reference", "inputs": []},
    {"name": "mat_asset", "type": "componentmaterial", "inputs": ["geo_asset"]},
    {"name": "output_asset", "type": "componentoutput", "inputs": ["mat_asset"]},
]

#: The SOP chain built inside ``componentgeometry`` (non-LOP, catalogue-exempt).
EXPECTED_SOP_CHAIN: List[Dict[str, Any]] = [
    {"name": "import_usdc", "type": "usdimport", "inputs": []},
    {"name": "scale_to_houdini", "type": "xform", "inputs": ["import_usdc"]},
    {"name": "ground_asset", "type": "matchsize", "inputs": ["scale_to_houdini"]},
    {"name": "rotation_fix", "type": "xform", "inputs": ["ground_asset"]},
    {"name": "proxy_reduce", "type": "polyreduce", "inputs": ["rotation_fix"]},
]

#: The material input slot the tool leaves open. Pinned so a future fix that
#: wires it flips this constant and the test that asserts it.
UNWIRED_MATERIAL_INPUT = ("mat_asset", 1, "mtl_ref_asset")


def verify_static(catalog=None) -> Dict[str, Any]:
    """STATIC verification. Expected to FAIL on ``no_orphans`` -- see F3."""
    return common.verify_static(TOOL, EXPECTED_TOPOLOGY, catalog)


def verify_sop_chain(catalog=None) -> Dict[str, Any]:
    """The SOP-side chain is catalogue-exempt but must still be connected."""
    checks = list(common.check_topology(EXPECTED_SOP_CHAIN, catalog))
    checks += list(common.check_connected(EXPECTED_SOP_CHAIN))
    return common.result(TOOL + ":sop_chain", checks, tier="static")


def material_orphan_check() -> common.Check:
    """Isolate the F3 defect as one named, greppable assertion."""
    consumer, slot, orphan = UNWIRED_MATERIAL_INPUT
    node = next(n for n in EXPECTED_TOPOLOGY if n["name"] == consumer)
    wired = list(node.get("inputs") or [])
    connected = len(wired) > slot and wired[slot] == orphan
    return common.Check(
        "material_reference_wired", connected,
        f"{orphan!r} -> {consumer}:input{slot} is "
        f"{'wired' if connected else 'NOT wired (F3: materials orphaned)'}",
    )


def live_build(parent, asset_name: str = "l2asset",
               usdc_path: str = "$HIP/l2_verify_asset.usdc"):
    """``usdc_path`` need not resolve: this verifies WIRING, not asset load."""
    tool = common.load_tool("import_megascans")
    before = set(parent.allSubChildren())
    tool.execute({"parent": parent.path(), "parent_path": parent.path(),
                  "asset_name": asset_name, "usdc_path": usdc_path})
    return [n for n in parent.allSubChildren() if n not in before]


def verify_live(parent, asset_name: str = "l2asset") -> Dict[str, Any]:
    """Only the LOP-level nodes are graded; the SOP chain has its own check."""
    nodes = live_build(parent, asset_name)
    lops = [n for n in nodes if n.type().category().name() == "Lop"]
    return common.verify_live(TOOL, lops)
