"""
Synapse Node Handler Mixin

Extracted from handlers.py -- contains node creation, deletion, and connection
handlers for the SynapseHandler class.
"""

import os
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError
from .handler_helpers import _HOUDINI_UNAVAILABLE


def _suggest_children(parent_path: str) -> str:
    """List children of a parent path for error enrichment."""
    try:
        parent = hou.node(parent_path)
        if parent and parent.children():
            names = [c.name() for c in parent.children()[:10]]
            return " Children at that path: " + ", ".join(names)
    except Exception:
        pass
    return ""


class NodeHandlerMixin:
    """Mixin providing node creation, deletion, and connection handlers."""

    def _handle_create_node(self, payload: Dict) -> Dict:
        """Handle create_node command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        parent = resolve_param(payload, "parent")
        node_type = resolve_param(payload, "type")
        name = resolve_param(payload, "name", required=False)

        from .main_thread import run_on_main

        def _on_main():
            parent_node = hou.node(parent)
            if parent_node is None:
                hint = _suggest_children(os.path.dirname(parent))
                raise NodeNotFoundError(parent, suggestion=hint.strip() if hint else "")

            if name:
                new_node = parent_node.createNode(node_type, name)
            else:
                new_node = parent_node.createNode(node_type)

            new_node.moveToGoodPosition()

            # Track node in session (logging handled by generic executor in handle())
            bridge = self._get_bridge()  # type: ignore[attr-defined]
            if bridge and self._session_id:  # type: ignore[attr-defined]
                session = bridge.get_session(self._session_id)  # type: ignore[attr-defined]
                if session:
                    session.nodes_created.append(new_node.path())

            return {
                "path": new_node.path(),
                "type": node_type,
                "name": new_node.name(),
            }

        return run_on_main(_on_main)

    def _handle_delete_node(self, payload: Dict) -> Dict:
        """Handle delete_node command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise NodeNotFoundError(node_path)

            node_name = node.name()
            node.destroy()

            return {"deleted": node_path, "name": node_name}

        return run_on_main(_on_main)

    def _handle_connect_nodes(self, payload: Dict) -> Dict:
        """Handle connect_nodes command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        source_path = resolve_param(payload, "source")
        target_path = resolve_param(payload, "target")
        source_output = resolve_param_with_default(payload, "source_output", 0)
        target_input = resolve_param_with_default(payload, "target_input", 0)

        from .main_thread import run_on_main

        def _on_main():
            source_node = hou.node(source_path)
            target_node = hou.node(target_path)

            if source_node is None:
                raise NodeNotFoundError(source_path)
            if target_node is None:
                raise NodeNotFoundError(target_path)

            target_node.setInput(int(target_input), source_node, int(source_output))

            return {
                "source": source_path,
                "target": target_path,
                "source_output": source_output,
                "target_input": target_input,
            }

        return run_on_main(_on_main)
