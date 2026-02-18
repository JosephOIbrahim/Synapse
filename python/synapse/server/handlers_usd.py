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
from .handler_helpers import _HOUDINI_UNAVAILABLE


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

        from .main_thread import run_on_main

        def _on_main():
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

        return run_on_main(_on_main)

    def _handle_get_usd_attribute(self, payload: Dict) -> Dict:
        """Handle get_usd_attribute command -- read a USD attribute from a prim."""
        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)

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

        return run_on_main(_on_main)

    def _handle_set_usd_attribute(self, payload: Dict) -> Dict:
        """Handle set_usd_attribute command -- set a USD attribute via Python LOP."""
        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")
        value = resolve_param(payload, "value")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)

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

        return run_on_main(_on_main)

    def _handle_create_usd_prim(self, payload: Dict) -> Dict:
        """Handle create_usd_prim command -- define a USD prim via Python LOP."""
        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")
        prim_type = resolve_param_with_default(payload, "prim_type", "Xform")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)

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

        return run_on_main(_on_main)

    def _handle_modify_usd_prim(self, payload: Dict) -> Dict:
        """Handle modify_usd_prim command -- set metadata/properties on a prim."""
        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")

        # Collect optional modifications
        kind = resolve_param(payload, "kind", required=False)
        purpose = resolve_param(payload, "purpose", required=False)
        active = resolve_param(payload, "active", required=False)

        # Validate before touching hou.*
        mods = {}
        if kind is not None:
            mods["kind"] = kind
        if purpose is not None:
            mods["purpose"] = purpose
        if active is not None:
            mods["active"] = active

        if not mods:
            raise ValueError(
                "No changes specified -- pass at least one of: kind, purpose, or active"
            )

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)

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
            if kind is not None:
                lines.append(f"    Usd.ModelAPI(prim).SetKind({repr(kind)})")
            if purpose is not None:
                lines.append(f"    UsdGeom.Imageable(prim).GetPurposeAttr().Set({repr(purpose)})")
            if active is not None:
                lines.append(f"    prim.SetActive({active})")

            code = "\n".join(lines)
            py_lop.parm("python").set(code)

            return {
                "created_node": py_lop.path(),
                "prim_path": prim_path,
                "modifications": mods,
            }

        return run_on_main(_on_main)

    def _handle_reference_usd(self, payload: Dict) -> Dict:
        """Import a USD file into the stage via reference, payload, or sublayer.

        Modes:
        - 'reference': Standard USD reference composition (default)
        - 'payload': Deferred-load reference — asset loads only when activated.
          Preferred for heavy assets in large scenes.
        - 'sublayer': Layer stacking — all prims merged into the stage.
          Most reliable for Karma rendering visibility.

        Note: For Karma render scenes, 'sublayer' is the most reliable import
        method. 'reference' and 'payload' may require explicit purpose/kind
        metadata on the imported prims for Karma visibility.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        file_path = resolve_param(payload, "file")
        prim_path = resolve_param_with_default(payload, "prim_path", "/")
        mode = resolve_param_with_default(payload, "mode", "reference")
        parent = resolve_param_with_default(payload, "parent", "/stage")

        # Validate mode before touching hou.*
        if mode not in ("sublayer", "reference", "payload"):
            raise ValueError(
                f"'{mode}' isn't a recognized import mode -- "
                "use 'reference', 'payload', or 'sublayer'"
            )

        from .main_thread import run_on_main

        def _on_main():
            parent_node = hou.node(parent)
            if parent_node is None:
                raise ValueError(
                    f"Couldn't find the parent node at {parent} -- "
                    "verify this path exists (default is /stage)"
                )

            if mode == "sublayer":
                node = parent_node.createNode("sublayer", "sublayer_import")
                node.parm("filepath1").set(file_path)
            else:
                # Both 'reference' and 'payload' use the reference LOP node
                node = parent_node.createNode("reference", "ref_import")
                node.parm("filepath1").set(file_path)
                if prim_path != "/":
                    node.parm("primpath").set(prim_path)

                # Set reference type: payload uses deferred loading
                if mode == "payload":
                    reftype_parm = node.parm("reftype")
                    if reftype_parm is not None:
                        reftype_parm.set("payload")

            result = {
                "node": node.path(),
                "file": file_path,
                "mode": mode,
                "prim_path": prim_path,
            }

            # Add Karma visibility advisory for non-sublayer modes
            if mode in ("reference", "payload"):
                result["advisory"] = (
                    "For Karma rendering, 'sublayer' is the most reliable import "
                    "mode. If this asset isn't visible in renders, try switching "
                    "to mode='sublayer' or ensure the imported prims have "
                    "purpose='default' and kind='component' metadata."
                )

            return result

        return run_on_main(_on_main)

    def _handle_query_prims(self, payload: Dict) -> Dict:
        """Query USD stage prims with filtering by type, purpose, name pattern.

        Walks the stage hierarchy from a root path and returns matching prims
        with their types, paths, and metadata. Useful for discovering what's on
        the stage before making changes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        root_path = resolve_param_with_default(payload, "root_path", "/")
        prim_type = resolve_param(payload, "prim_type", required=False)
        purpose = resolve_param(payload, "purpose", required=False)
        name_pattern = resolve_param(payload, "name_pattern", required=False)
        max_depth = int(resolve_param_with_default(payload, "max_depth", 10))
        limit = int(resolve_param_with_default(payload, "limit", 100))

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            stage = node.stage()
            if stage is None:
                raise ValueError(
                    "That node doesn't have an active USD stage yet -- "
                    "it may need to cook first, or check the LOP network is set up"
                )

            root_prim = stage.GetPrimAtPath(root_path)
            if not root_prim.IsValid():
                raise ValueError(
                    f"Couldn't find a prim at {root_path} -- "
                    "double-check the path on the USD stage"
                )

            from pxr import Usd, UsdGeom

            import re
            name_re = None
            if name_pattern:
                try:
                    name_re = re.compile(name_pattern, re.IGNORECASE)
                except re.error:
                    name_re = None  # fall back to substring match

            results = []

            def _walk(prim, depth):
                if depth > max_depth or len(results) >= limit:
                    return

                prim_type_name = prim.GetTypeName()

                # Apply type filter
                if prim_type:
                    if prim_type_name.lower() != prim_type.lower():
                        for child in prim.GetChildren():
                            _walk(child, depth + 1)
                        return

                # Apply purpose filter
                if purpose:
                    imageable = UsdGeom.Imageable(prim)
                    if imageable:
                        prim_purpose = imageable.ComputePurpose()
                        if prim_purpose != purpose:
                            for child in prim.GetChildren():
                                _walk(child, depth + 1)
                            return

                # Apply name filter
                if name_pattern:
                    prim_name = prim.GetName()
                    if name_re:
                        if not name_re.search(prim_name):
                            for child in prim.GetChildren():
                                _walk(child, depth + 1)
                            return
                    elif name_pattern.lower() not in prim_name.lower():
                        for child in prim.GetChildren():
                            _walk(child, depth + 1)
                        return

                # Prim passes all filters
                entry = {
                    "path": str(prim.GetPath()),
                    "type": prim_type_name,
                    "name": prim.GetName(),
                }

                kind = Usd.ModelAPI(prim).GetKind()
                if kind:
                    entry["kind"] = str(kind)

                imageable = UsdGeom.Imageable(prim)
                if imageable:
                    p = imageable.ComputePurpose()
                    if p:
                        entry["purpose"] = str(p)
                    vis = imageable.ComputeVisibility()
                    if vis:
                        entry["visibility"] = str(vis)

                entry["active"] = prim.IsActive()
                results.append(entry)

                for child in prim.GetChildren():
                    _walk(child, depth + 1)

            _walk(root_prim, 0)

            return {
                "root_path": root_path,
                "prim_count": len(results),
                "prims": results,
                "truncated": len(results) >= limit,
            }

        return run_on_main(_on_main)

    def _handle_manage_variant_set(self, payload: Dict) -> Dict:
        """Manage USD variant sets: create, list, or select variants.

        Actions:
        - 'list':   List variant sets and their variants on a prim.
        - 'create': Create a new variant set and/or add variants to it.
        - 'select': Set the active variant selection on an existing set.

        For 'create', pass variant_set and variants (list of names).
        For 'select', pass variant_set and variant (single name).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")
        action = resolve_param_with_default(payload, "action", "list")

        if action not in ("list", "create", "select"):
            raise ValueError(
                f"'{action}' isn't a recognized action -- "
                "use 'list', 'create', or 'select'"
            )

        variant_set_name = resolve_param(payload, "variant_set", required=(action != "list"))
        variants = resolve_param(payload, "variants", required=False)
        variant = resolve_param(payload, "variant", required=False)

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            if action == "list":
                stage = node.stage()
                if stage is None:
                    raise ValueError(
                        "That node doesn't have an active USD stage yet -- "
                        "it may need to cook first"
                    )
                prim = stage.GetPrimAtPath(prim_path)
                if not prim.IsValid():
                    raise ValueError(
                        f"Couldn't find a prim at {prim_path} -- "
                        "double-check the path on the USD stage"
                    )
                vsets = prim.GetVariantSets()
                set_names = vsets.GetNames()
                result_sets = []
                for sn in set_names:
                    vs = vsets.GetVariantSet(sn)
                    result_sets.append({
                        "name": sn,
                        "variants": vs.GetVariantNames(),
                        "selection": vs.GetVariantSelection(),
                    })
                return {
                    "prim_path": prim_path,
                    "variant_sets": result_sets,
                    "count": len(result_sets),
                }

            elif action == "create":
                if not variants or not isinstance(variants, list):
                    raise ValueError(
                        "For 'create' action, pass 'variants' as a list of "
                        "variant names (e.g. ['red', 'blue', 'green'])"
                    )
                parent = node.parent()
                safe_name = variant_set_name.replace(" ", "_").replace("/", "_")
                py_lop = parent.createNode("pythonscript", f"vset_{safe_name}")
                py_lop.setInput(0, node)
                py_lop.moveToGoodPosition()

                lines = [
                    "from pxr import Usd, Sdf",
                    "stage = hou.pwd().editableStage()",
                    f"prim = stage.GetPrimAtPath({repr(prim_path)})",
                    "if prim:",
                    f"    vset = prim.GetVariantSets().AddVariantSet({repr(variant_set_name)})",
                ]
                for v in variants:
                    lines.append(f"    vset.AddVariant({repr(v)})")
                # Select the first variant by default
                if variants:
                    lines.append(f"    vset.SetVariantSelection({repr(variants[0])})")

                code = "\n".join(lines)
                py_lop.parm("python").set(code)

                return {
                    "node": py_lop.path(),
                    "prim_path": prim_path,
                    "variant_set": variant_set_name,
                    "variants": variants,
                    "default_selection": variants[0] if variants else None,
                }

            else:  # select
                if not variant:
                    raise ValueError(
                        "For 'select' action, pass 'variant' with the name "
                        "to select (e.g. 'red')"
                    )
                parent = node.parent()
                safe_name = variant_set_name.replace(" ", "_").replace("/", "_")
                py_lop = parent.createNode("pythonscript", f"vsel_{safe_name}")
                py_lop.setInput(0, node)
                py_lop.moveToGoodPosition()

                code = "\n".join([
                    "from pxr import Usd",
                    "stage = hou.pwd().editableStage()",
                    f"prim = stage.GetPrimAtPath({repr(prim_path)})",
                    "if prim:",
                    f"    vset = prim.GetVariantSets().GetVariantSet({repr(variant_set_name)})",
                    f"    vset.SetVariantSelection({repr(variant)})",
                ])
                py_lop.parm("python").set(code)

                return {
                    "node": py_lop.path(),
                    "prim_path": prim_path,
                    "variant_set": variant_set_name,
                    "variant": variant,
                }

        return run_on_main(_on_main)

    def _handle_manage_collection(self, payload: Dict) -> Dict:
        """Manage USD collections: create, list, or modify.

        Collections group prims for material assignment, light linking,
        and other operations. Each collection has include/exclude rules.

        Actions:
        - 'list':   List collections on a prim.
        - 'create': Create a new collection with include paths.
        - 'add':    Add paths to an existing collection's includes.
        - 'remove': Remove paths from a collection's includes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")
        action = resolve_param_with_default(payload, "action", "list")

        if action not in ("list", "create", "add", "remove"):
            raise ValueError(
                f"'{action}' isn't a recognized action -- "
                "use 'list', 'create', 'add', or 'remove'"
            )

        collection_name = resolve_param(payload, "collection_name", required=(action != "list"))
        paths = resolve_param(payload, "paths", required=False)
        exclude_paths = resolve_param(payload, "exclude_paths", required=False)
        expansion_rule = resolve_param_with_default(payload, "expansion_rule", "expandPrims")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

            if action == "list":
                stage = node.stage()
                if stage is None:
                    raise ValueError(
                        "That node doesn't have an active USD stage yet -- "
                        "it may need to cook first"
                    )
                prim = stage.GetPrimAtPath(prim_path)
                if not prim.IsValid():
                    raise ValueError(
                        f"Couldn't find a prim at {prim_path} -- "
                        "double-check the path on the USD stage"
                    )

                from pxr import Usd

                collections = Usd.CollectionAPI.GetAllCollections(prim)
                result_colls = []
                for coll in collections:
                    includes = coll.GetIncludesRel()
                    excludes = coll.GetExcludesRel()
                    result_colls.append({
                        "name": coll.GetName(),
                        "includes": [str(t) for t in includes.GetTargets()] if includes else [],
                        "excludes": [str(t) for t in excludes.GetTargets()] if excludes else [],
                        "expansion_rule": str(coll.GetExpansionRuleAttr().Get()) if coll.GetExpansionRuleAttr() else "expandPrims",
                    })
                return {
                    "prim_path": prim_path,
                    "collections": result_colls,
                    "count": len(result_colls),
                }

            elif action == "create":
                if not paths or not isinstance(paths, list):
                    raise ValueError(
                        "For 'create' action, pass 'paths' as a list of "
                        "prim paths to include (e.g. ['/World/geo/mesh1'])"
                    )
                parent = node.parent()
                safe_name = collection_name.replace(" ", "_").replace("/", "_")
                py_lop = parent.createNode("pythonscript", f"coll_{safe_name}")
                py_lop.setInput(0, node)
                py_lop.moveToGoodPosition()

                path_reprs = ", ".join(repr(p) for p in paths)
                lines = [
                    "from pxr import Usd, Sdf",
                    "stage = hou.pwd().editableStage()",
                    f"prim = stage.GetPrimAtPath({repr(prim_path)})",
                    "if prim:",
                    f"    coll = Usd.CollectionAPI.Apply(prim, {repr(collection_name)})",
                    f"    coll.GetExpansionRuleAttr().Set({repr(expansion_rule)})",
                    f"    includes = coll.GetIncludesRel()",
                    f"    for p in [{path_reprs}]:",
                    f"        includes.AddTarget(Sdf.Path(p))",
                ]

                if exclude_paths and isinstance(exclude_paths, list):
                    excl_reprs = ", ".join(repr(p) for p in exclude_paths)
                    lines.append(f"    excludes = coll.GetExcludesRel()")
                    lines.append(f"    for p in [{excl_reprs}]:")
                    lines.append(f"        excludes.AddTarget(Sdf.Path(p))")

                code = "\n".join(lines)
                py_lop.parm("python").set(code)

                result = {
                    "node": py_lop.path(),
                    "prim_path": prim_path,
                    "collection_name": collection_name,
                    "includes": paths,
                    "expansion_rule": expansion_rule,
                }
                if exclude_paths:
                    result["excludes"] = exclude_paths
                return result

            else:  # add or remove
                if not paths or not isinstance(paths, list):
                    raise ValueError(
                        f"For '{action}' action, pass 'paths' as a list of "
                        "prim paths to add/remove"
                    )
                parent = node.parent()
                safe_name = collection_name.replace(" ", "_").replace("/", "_")
                verb = "add" if action == "add" else "rm"
                py_lop = parent.createNode("pythonscript", f"coll_{verb}_{safe_name}")
                py_lop.setInput(0, node)
                py_lop.moveToGoodPosition()

                path_reprs = ", ".join(repr(p) for p in paths)
                op = "AddTarget" if action == "add" else "RemoveTarget"
                lines = [
                    "from pxr import Usd, Sdf",
                    "stage = hou.pwd().editableStage()",
                    f"prim = stage.GetPrimAtPath({repr(prim_path)})",
                    "if prim:",
                    f"    coll = Usd.CollectionAPI.Get(prim, {repr(collection_name)})",
                    f"    includes = coll.GetIncludesRel()",
                    f"    for p in [{path_reprs}]:",
                    f"        includes.{op}(Sdf.Path(p))",
                ]

                code = "\n".join(lines)
                py_lop.parm("python").set(code)

                return {
                    "node": py_lop.path(),
                    "prim_path": prim_path,
                    "collection_name": collection_name,
                    "action": action,
                    "paths": paths,
                }

        return run_on_main(_on_main)

    def _handle_configure_light_linking(self, payload: Dict) -> Dict:
        """Configure light linking between lights and geometry via USD collections.

        Light linking in USD works through collections on light prims:
        - 'lightLink' collection: geometry the light illuminates (default: everything)
        - 'shadowLink' collection: geometry that casts shadows from this light

        Actions:
        - 'include': Set the light to only illuminate specified geometry paths.
        - 'exclude': Exclude specific geometry from this light's illumination.
        - 'shadow_include': Set geometry that casts shadows from this light.
        - 'shadow_exclude': Exclude geometry from casting shadows.
        - 'reset': Remove light linking (light illuminates everything again).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        light_path = resolve_param(payload, "light_path")
        action = resolve_param_with_default(payload, "action", "include")
        geo_paths = resolve_param(payload, "geo_paths", required=False)

        valid_actions = ("include", "exclude", "shadow_include", "shadow_exclude", "reset")
        if action not in valid_actions:
            raise ValueError(
                f"'{action}' isn't a recognized light linking action -- "
                f"use one of: {', '.join(valid_actions)}"
            )

        if action != "reset" and (not geo_paths or not isinstance(geo_paths, list)):
            raise ValueError(
                f"For '{action}' action, pass 'geo_paths' as a list of "
                "geometry prim paths"
            )

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]
            parent = node.parent()

            safe_light = light_path.rstrip("/").rsplit("/", 1)[-1] or "light"
            py_lop = parent.createNode("pythonscript", f"lightlink_{safe_light}")
            py_lop.setInput(0, node)
            py_lop.moveToGoodPosition()

            lines = [
                "from pxr import Usd, UsdLux, Sdf",
                "stage = hou.pwd().editableStage()",
                f"light = stage.GetPrimAtPath({repr(light_path)})",
                "if light:",
            ]

            if action == "reset":
                # Remove custom light linking — restore default illumination
                lines.extend([
                    "    ll = UsdLux.LightAPI(light)",
                    "    coll = ll.GetLightLinkCollectionAPI()",
                    "    includes = coll.GetIncludesRel()",
                    "    includes.ClearTargets(True)",
                    "    includes.AddTarget(Sdf.Path('/'))",
                ])
            elif action in ("include", "exclude"):
                coll_method = "GetLightLinkCollectionAPI"
                if action == "include":
                    path_reprs = ", ".join(repr(p) for p in geo_paths)
                    lines.extend([
                        "    ll = UsdLux.LightAPI(light)",
                        f"    coll = ll.{coll_method}()",
                        "    includes = coll.GetIncludesRel()",
                        "    includes.ClearTargets(True)",
                        f"    for p in [{path_reprs}]:",
                        "        includes.AddTarget(Sdf.Path(p))",
                    ])
                else:  # exclude
                    path_reprs = ", ".join(repr(p) for p in geo_paths)
                    lines.extend([
                        "    ll = UsdLux.LightAPI(light)",
                        f"    coll = ll.{coll_method}()",
                        "    excludes = coll.GetExcludesRel()",
                        f"    for p in [{path_reprs}]:",
                        "        excludes.AddTarget(Sdf.Path(p))",
                    ])
            else:  # shadow_include or shadow_exclude
                coll_method = "GetShadowLinkCollectionAPI"
                if action == "shadow_include":
                    path_reprs = ", ".join(repr(p) for p in geo_paths)
                    lines.extend([
                        "    ll = UsdLux.LightAPI(light)",
                        f"    coll = ll.{coll_method}()",
                        "    includes = coll.GetIncludesRel()",
                        "    includes.ClearTargets(True)",
                        f"    for p in [{path_reprs}]:",
                        "        includes.AddTarget(Sdf.Path(p))",
                    ])
                else:  # shadow_exclude
                    path_reprs = ", ".join(repr(p) for p in geo_paths)
                    lines.extend([
                        "    ll = UsdLux.LightAPI(light)",
                        f"    coll = ll.{coll_method}()",
                        "    excludes = coll.GetExcludesRel()",
                        f"    for p in [{path_reprs}]:",
                        "        excludes.AddTarget(Sdf.Path(p))",
                    ])

            code = "\n".join(lines)
            py_lop.parm("python").set(code)

            result = {
                "node": py_lop.path(),
                "light_path": light_path,
                "action": action,
            }
            if geo_paths:
                result["geo_paths"] = geo_paths
            return result

        return run_on_main(_on_main)
