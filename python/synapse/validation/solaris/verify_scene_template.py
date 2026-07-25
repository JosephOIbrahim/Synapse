"""
RELAY-SOLARIS L2 — wiring verifier for ``synapse_solaris_scene_template``.

Source of truth for the declared topology: ``synapse/mcp/tools/solaris/
scene_template.py`` ``execute()`` (the createNode/setInput sequence at lines
190-270). The tool builds one linear LOP chain and terminates on a
``usdrender_rop``.

STATIC proves every emitted type exists on 22.0.368, that each satisfies its
catalogued input arity, and that the chain is a single connected graph.
LIVE runs the real tool and proves the emitted terminal composes to a
non-empty stage.
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "synapse_solaris_scene_template"

#: The canonical chain scene_template.execute() emits, in build order.
EXPECTED_TOPOLOGY: List[Dict[str, Any]] = [
    {"name": "primitive_scene", "type": "primitive", "inputs": []},
    {"name": "geo_0", "type": "sopimport", "inputs": ["primitive_scene"]},
    {"name": "camera1", "type": "camera", "inputs": ["geo_0"]},
    {"name": "materials", "type": "materiallibrary", "inputs": ["camera1"]},
    {"name": "physical_sky", "type": "karmaphysicalsky", "inputs": ["materials"]},
    {"name": "render_settings", "type": "karmarendersettings",
     "inputs": ["physical_sky"]},
    {"name": "render", "type": "usdrender_rop", "inputs": ["render_settings"]},
]


def verify_static(catalog=None) -> Dict[str, Any]:
    return common.verify_static(TOOL, EXPECTED_TOPOLOGY, catalog)


def live_build(parent, scene_name: str = "l2_verify"):
    """Emit the network via the real tool and return the created nodes."""
    # NOTE (F8, corrected SR1 crucible S2): the earlier claim here — that
    # import_megascans and component_builder read ``parent_path`` — was FALSE;
    # all three read ``parent`` only. All three now converge on ``parent_path``
    # with ``parent`` as an accepted alias. Both keys are still passed so this
    # verifier exercises the alias path.
    tool = common.load_tool("scene_template")
    before = set(parent.children())
    tool.execute({"parent": parent.path(), "parent_path": parent.path(),
                  "scene_name": scene_name, "sop_paths": []})
    return [n for n in parent.children() if n not in before]


def verify_live(parent, scene_name: str = "l2_verify") -> Dict[str, Any]:
    return common.verify_live(TOOL, live_build(parent, scene_name))
