"""
Synapse Solaris NodeFlow Tool Handler Mixin

Server-side entry points for the RELAY-SOLARIS Phase 3 tool family whose
implementations live in `synapse.mcp.tool_impls.solaris`. Each handler is a
thin marshalling shim: validate the payload with the tool's own `validate()`,
then run its `execute()` on the Houdini main thread.

SR1 M1 (CTO Ruling 12). Before this file the five tools sat outside the
installable package with no registry entry and no handler -- unreachable from
both `/mcp` and `/synapse` (L2 finding F1). A registry entry without a handler
is a lie, so registration and handler landed in the same change.

Gated: `solaris_import_megascans` has a handler defined here but is NOT
registered in handlers.py and NOT in `_tool_registry.TOOL_DEFS` -- CTO Ruling
13 on finding F9. Its `execute()` raises `hou.PermissionError` on every
invocation on 22.0.368. Promotion is a later mile, after F9 + F3 are repaired
and live-verified. The gate is pinned by
`tests/test_solaris_tool_registration.py`.
"""

from typing import Any, Dict

from ..mcp.tool_impls.solaris import (
    component_builder as _component_builder,
    create_variants as _create_variants,
    import_megascans as _import_megascans,
    scene_template as _scene_template,
    set_purpose as _set_purpose,
)

# Main-thread marshalling budget. These tools build whole component graphs;
# 30s matches the surrounding Solaris handlers' slow-op ceiling.
_SOLARIS_TOOL_TIMEOUT = 30.0


def _run_tool(module, payload: Dict) -> Dict[str, Any]:
    """Validate then execute a Solaris tool module on the main thread.

    `validate()` runs first and outside the marshal so a bad payload fails
    fast with the tool's own ValidationError rather than burning a main-thread
    slot. `execute()` re-validates internally; that redundancy is deliberate --
    the tool must remain safe when called directly.
    """
    params = dict(payload or {})
    module.validate(params)

    from .main_thread import run_on_main

    return run_on_main(lambda: module.execute(params), timeout=_SOLARIS_TOOL_TIMEOUT)


class SolarisToolsMixin:
    """Handlers for the Solaris NodeFlow tool family."""

    def _handle_solaris_component_builder(self, payload: Dict) -> Dict[str, Any]:
        """Build a USD Component Builder network for a production asset."""
        return _run_tool(_component_builder, payload)

    def _handle_solaris_scene_template(self, payload: Dict) -> Dict[str, Any]:
        """Build the canonical Solaris scene skeleton in a LOP network."""
        return _run_tool(_scene_template, payload)

    def _handle_solaris_create_variants(self, payload: Dict) -> Dict[str, Any]:
        """Create material or geometry variants on a Component Builder."""
        return _run_tool(_create_variants, payload)

    def _handle_solaris_set_purpose(self, payload: Dict) -> Dict[str, Any]:
        """Set the USD purpose on geometry within a Component Builder."""
        return _run_tool(_set_purpose, payload)

    # --- GATED: not registered. See module docstring / Ruling 13 / F9. ---
    def _handle_solaris_import_megascans(self, payload: Dict) -> Dict[str, Any]:
        """Import a Megascans/Fab .usdc asset into a Component Builder.

        NOT reachable: absent from `handlers.py` registration and from
        `_tool_registry.TOOL_DEFS`. Defined so the promotion mile is a
        registration change rather than a new implementation.
        """
        return _run_tool(_import_megascans, payload)
