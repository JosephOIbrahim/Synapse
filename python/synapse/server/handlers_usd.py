"""
Synapse USD Handler Mixin

Extracted from handlers.py -- contains USD/Solaris stage handlers and the
_usd_to_json utility for the SynapseHandler class.
"""

import time
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default, USD_PARM_ALIASES


_HOUDINI_UNAVAILABLE = (
    "Houdini isn't reachable right now -- make sure it's running "
    "and Synapse is started from the Python Panel"
)


def _usd_to_json(value):
    """Convert USD attribute values to JSON-serializable Python types."""
    if value is None:
        return None
    # Scalars
    if isinstance(value, (bool, int, float, str)):
        return value
    # Matrix types (GfMatrix4d, GfMatrix3d) -- check BEFORE generic sequence
    if hasattr(value, 'GetRow'):
        try:
            size = 4 if hasattr(value, 'IsIdentity') else 3
            return [[float(value[r][c]) for c in range(size)] for r in range(size)]
        except Exception:
            pass
    # Tuples/vectors (GfVec2f, GfVec3f, GfVec4f, GfQuatf, etc.)
    if hasattr(value, '__len__') and hasattr(value, '__getitem__'):
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return [_usd_to_json(v) for v in value]
    # Asset paths
    if hasattr(value, 'path'):
        return str(value.path)
    return str(value)


class UsdHandlerMixin:
    """Mixin providing USD/Solaris stage handlers."""

    def _resolve_lop_node(self, node_path: str = None):
        """Resolve a LOP node from path or selection."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        if node_path:
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )
            if not hasattr(node, 'stage'):
                raise ValueError(
                    f"The node at {node_path} isn't a LOP node -- "
                    "I need a Solaris/LOP node to access the USD stage"
                )
            return node

        # Search selection for a LOP node
        for n in hou.selectedNodes():
            if hasattr(n, 'stage'):
                return n

        raise ValueError(
            "Couldn't find a LOP node in your selection -- "
            "select one in the Solaris network or specify the node path"
        )

    def _handle_get_stage_info(self, payload: Dict) -> Dict:
        """Handle get_stage_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node", required=False)

        if node_path:
            node = hou.node(node_path)
        else:
            # Try to find the current LOP network
            node = None
            for n in hou.selectedNodes():
                if hasattr(n, 'stage'):
                    node = n
                    break

        if node is None or not hasattr(node, 'stage'):
            raise ValueError(
                "No USD stage found -- select a LOP node or pass "
                "a node path so I know which stage to look at"
            )

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet -- "
                "it may need to cook first, or check the LOP network is set up"
            )

        root = stage.GetPseudoRoot()
        prims = []
        for prim in root.GetAllChildren():
            prims.append({
                "path": str(prim.GetPath()),
                "type": str(prim.GetTypeName()),
            })
            if len(prims) >= 100:
                break

        return {
            "node": node.path(),
            "prim_count": len(prims),
            "prims": prims,
        }

    def _handle_get_usd_attribute(self, payload: Dict) -> Dict:
        """Handle get_usd_attribute command -- read a USD attribute from a prim."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet -- "
                "it may need to cook first, or check the LOP network is set up"
            )

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(
                f"Couldn't find a prim at {prim_path} -- "
                "double-check the path on the USD stage"
            )

        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            # List available attributes to help the caller
            attrs = [a.GetName() for a in prim.GetAttributes()][:30]
            raise ValueError(
                f"That attribute name didn't match ('{attr_name}') on {prim_path}. "
                f"Available attributes: {', '.join(attrs)}"
            )

        value = attr.Get()

        return {
            "node": node.path(),
            "prim_path": prim_path,
            "attribute": attr_name,
            "value": _usd_to_json(value),
            "type_name": str(attr.GetTypeName()),
        }

    def _handle_set_usd_attribute(self, payload: Dict) -> Dict:
        """Handle set_usd_attribute command -- set a USD attribute via Python LOP."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")
        value = resolve_param(payload, "value")

        parent = node.parent()
        safe_name = f"set_{attr_name.replace(':', '_').replace('.', '_')}"
        py_lop = parent.createNode("pythonscript", safe_name)
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        code = (
            "from pxr import Sdf\n"
            "stage = hou.pwd().editableStage()\n"
            f"prim = stage.GetPrimAtPath({repr(prim_path)})\n"
            "if prim:\n"
            f"    attr = prim.GetAttribute({repr(attr_name)})\n"
            "    if attr:\n"
            f"        attr.Set({repr(value)})\n"
        )
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "attribute": attr_name,
            "value": value,
        }

    def _handle_create_usd_prim(self, payload: Dict) -> Dict:
        """Handle create_usd_prim command -- define a USD prim via Python LOP."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        prim_type = resolve_param_with_default(payload, "prim_type", "Xform")

        parent = node.parent()
        safe_name = prim_path.rstrip("/").rsplit("/", 1)[-1] or "prim"
        py_lop = parent.createNode("pythonscript", f"create_{safe_name}")
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        code = (
            "stage = hou.pwd().editableStage()\n"
            f"stage.DefinePrim({repr(prim_path)}, {repr(prim_type)})\n"
        )
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "prim_type": prim_type,
        }

    def _handle_modify_usd_prim(self, payload: Dict) -> Dict:
        """Handle modify_usd_prim command -- set metadata/properties on a prim."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")

        # Collect optional modifications
        kind = resolve_param(payload, "kind", required=False)
        purpose = resolve_param(payload, "purpose", required=False)
        active = resolve_param(payload, "active", required=False)

        parent = node.parent()
        safe_name = prim_path.rstrip("/").rsplit("/", 1)[-1] or "prim"
        py_lop = parent.createNode("pythonscript", f"modify_{safe_name}")
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        lines = [
            "from pxr import Usd, UsdGeom, Sdf, Kind",
            "stage = hou.pwd().editableStage()",
            f"prim = stage.GetPrimAtPath({repr(prim_path)})",
            "if prim:",
        ]
        mods = {}
        if kind is not None:
            lines.append(f"    Usd.ModelAPI(prim).SetKind({repr(kind)})")
            mods["kind"] = kind
        if purpose is not None:
            lines.append(f"    UsdGeom.Imageable(prim).GetPurposeAttr().Set({repr(purpose)})")
            mods["purpose"] = purpose
        if active is not None:
            lines.append(f"    prim.SetActive({active})")
            mods["active"] = active

        if not mods:
            raise ValueError(
                "No changes specified -- pass at least one of: kind, purpose, or active"
            )

        code = "\n".join(lines)
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "modifications": mods,
        }

    def _handle_reference_usd(self, payload: Dict) -> Dict:
        """Import a USD file into the stage via reference or sublayer."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        file_path = resolve_param(payload, "file")
        prim_path = resolve_param_with_default(payload, "prim_path", "/")
        mode = resolve_param_with_default(payload, "mode", "reference")
        parent = resolve_param_with_default(payload, "parent", "/stage")

        parent_node = hou.node(parent)
        if parent_node is None:
            raise ValueError(
                f"Couldn't find the parent node at {parent} -- "
                "verify this path exists (default is /stage)"
            )

        if mode == "sublayer":
            node = parent_node.createNode("sublayer", "sublayer_import")
            node.parm("filepath1").set(file_path)
        elif mode == "reference":
            node = parent_node.createNode("reference", "ref_import")
            node.parm("filepath1").set(file_path)
            if prim_path != "/":
                node.parm("primpath").set(prim_path)
        else:
            raise ValueError(
                f"'{mode}' isn't a recognized import mode -- "
                "use 'reference' or 'sublayer'"
            )

        return {
            "node": node.path(),
            "file": file_path,
            "mode": mode,
            "prim_path": prim_path,
        }
