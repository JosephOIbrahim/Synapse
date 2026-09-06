"""Host-owned local native clips with USD metadata; all HOM runs on main.

This asset library never opens a Moneta handle, composes a scene USD stage,
evaluates parameters for inventory, requests a model, or starts a render.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import posixpath
import threading
import tempfile
import time

from synapse.recipes.library import SavedNetworkLibrary, LibraryError, default_library_path


def _main(fn):
    from synapse.server.main_thread import run_on_main
    return run_on_main(fn, label="saved-network")


def _hou():
    try:
        import hou
    except ImportError as exc:
        raise LibraryError("Saved networks need an open Houdini session.") from exc
    if threading.current_thread() is not threading.main_thread():
        raise LibraryError("Network capture must run on Houdini's main thread.")
    return hou


class USDMetadata:
    def _layer(self):
        try:
            from pxr import Sdf
        except ImportError as exc:
            raise LibraryError("USD metadata support is unavailable in this host.") from exc
        return Sdf.Layer.CreateAnonymous("recipe.usda")

    def write(self, path, data):
        layer = self._layer()
        layer.customLayerData = {"synapse_saved_network": json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False)}
        if not layer.Export(str(path)):
            raise LibraryError("The local USD recipe record could not be written.")

    def read(self, path):
        # A fresh anonymous layer avoids cached older metadata or store handles.
        layer = self._layer()
        if not layer.Import(str(path)) or layer.subLayerPaths:
            raise LibraryError("The USD recipe record is unreadable or has unexpected composition.")
        return json.loads(layer.customLayerData["synapse_saved_network"])


def _relative(node, parent):
    return node.path()[len(parent.path()) + 1:]


def _selected():
    hou = _hou()
    nodes = tuple(hou.selectedNodes())
    if not nodes:
        raise LibraryError("Select the Solaris nodes to save first.")
    parent = nodes[0].parent()
    if parent.childTypeCategory().name() != "Lop" or any(node.parent() != parent for node in nodes):
        raise LibraryError("Select sibling nodes in one Solaris network.")
    return _bounded(nodes), parent


def _bounded(nodes):
    if not 1 <= len(nodes) <= 200:
        raise LibraryError("Save between 1 and 200 selected Solaris nodes at a time.")
    if len(_descendants(nodes)) > 1000:
        raise LibraryError("This selection contains more than 1,000 nested nodes. Save a smaller section.")
    return nodes


def _descendants(nodes):
    return tuple(nodes) + tuple(child for node in nodes
                               for child in node.allSubChildren(recurse_in_locked_nodes=False))


def _dots(nodes, parent):
    """Keep intervening root dots and the contents of selected subnetworks."""
    hou = _hou()
    found = {}
    pending = [wire.inputItem() for node in nodes for wire in node.inputConnections()]
    while pending:
        item = pending.pop()
        if not isinstance(item, hou.NetworkDot):
            continue
        if item.parent() != parent:
            raise LibraryError("A connection dot belongs to another network.")
        if item.path() in found:
            continue
        if len(found) >= 200:
            raise LibraryError("Save a smaller section with at most 200 connection dots.")
        found[item.path()] = item
        pending.extend(wire.inputItem() for wire in item.inputConnections())
    for node in _descendants(nodes):
        if not node.isNetwork():
            continue
        for item in node.networkDots():
            found[item.path()] = item
            if len(found) > 1000:
                raise LibraryError("This selection contains more than 1,000 nested connection dots.")
    return tuple(found[path] for path in sorted(found))


def _boxes(nodes, dots, parent):
    owned = {item.path() for item in tuple(nodes) + tuple(dots) if item.parent() == parent}
    return tuple(box for box in parent.networkBoxes()
                 if box.items(recurse=False) and {item.path() for item in box.items(recurse=False)} <= owned)


def _file_dependency(raw, keys, scene, job):
    if keys or "`" in raw or any(token in raw for token in ("$F", "<UDIM>", "<udim>", "*", "?")):
        return {"status": "unresolved", "source_path": None}
    value = raw.replace("$HIP/", str(Path(scene).parent).replace("\\", "/") + "/")
    value = value.replace("$JOB/", job.rstrip("/\\") + "/") if job else value
    if "$" in value or "%" in value or "://" in value or value.startswith(("//", "\\\\")):
        return {"status": "unresolved", "source_path": None}
    path = Path(value)
    if not path.is_absolute():
        path = Path(scene).parent / path
    return {"status": "present" if path.is_file() else "missing", "source_path": str(path.resolve())}


def validate_placement(snapshot):
    """Reject invalid placement inventory before creating or moving any item."""
    def relative(value):
        return (isinstance(value, str) and 0 < len(value) <= 4096
                and not any(char in value for char in ("\\", ":", "\x00"))
                and all(part not in ("", ".", "..") for part in value.split("/")))

    def position(value):
        return (isinstance(value, (list, tuple)) and len(value) == 2
                and all(type(number) in (int, float) and math.isfinite(number) for number in value))

    try:
        roots, nodes, boxes = snapshot["roots"], snapshot["nodes"], snapshot["boxes"]
        if (not isinstance(roots, list) or not 1 <= len(roots) <= 200
                or any(not relative(name) or "/" in name for name in roots)
                or len(set(roots)) != len(roots)
                or not isinstance(nodes, list) or not 1 <= len(nodes) <= 1000
                or not isinstance(boxes, list)):
            raise ValueError("invalid roots or item inventory")
        names = set()
        for item in nodes:
            name = item["name"]
            if (not relative(name) or name in names or name.split("/")[0] not in roots
                    or not position(item["position"])):
                raise ValueError("invalid or unowned node placement")
            names.add(name)
        if not set(roots) <= names or any("/" in name and name.rsplit("/", 1)[0] not in names for name in names):
            raise ValueError("missing parent in node inventory")
        dot_names = set()
        dots = snapshot.get("dots", [])
        if not isinstance(dots, list) or len(dots) > 1000:
            raise ValueError("invalid connection dot inventory")
        for item in dots:
            name = item["name"]
            if (not relative(name) or name in names or name in dot_names
                    or ("/" in name and name.rsplit("/", 1)[0] not in names)
                    or not position(item["position"]) or type(item["pinned"]) is not bool):
                raise ValueError("invalid connection dot placement")
            dot_names.add(name)
        box_names = set()
        for item in boxes:
            name = item["name"]
            if (not relative(name) or "/" in name or name in box_names or name in names or name in dot_names
                    or not position(item["position"]) or not isinstance(item["nodes"], list)
                    or not set(item["nodes"]) <= set(roots)
                    or not set(item.get("dots", [])) <= {dot for dot in dot_names if "/" not in dot}):
                raise ValueError("invalid section box placement")
            box_names.add(name)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise LibraryError(f"The saved network has invalid placement metadata: {exc}") from exc


def observe(nodes, parent):
    """Detached authored values; rawValue/keyframes do not evaluate expressions."""
    hou = _hou()
    all_nodes = _descendants(nodes)
    dots = _dots(nodes, parent)
    owned = {node.path() for node in all_nodes}
    owned_items = owned | {dot.path() for dot in dots}
    scene, job = hou.hipFile.path(), hou.getenv("JOB") or ""
    records, wires, dependencies = [], [], []
    for node in all_nodes:
        name = _relative(node, parent)
        parms = {}
        for parm in node.parms():
            keys = [key.asCode() for key in parm.keyframes()]
            raw = parm.rawValue()
            parms[parm.name()] = {"raw": raw, "keyframes": keys}
            template = parm.parmTemplate()
            if template.type() == hou.parmTemplateType.String:
                kind = template.stringType()
                if raw and kind == hou.stringParmType.FileReference:
                    dependencies.append(dict(kind="file", node=name, parm=parm.name(), value=raw,
                                             **_file_dependency(raw, keys, scene, job)))
                elif raw and kind == hou.stringParmType.NodeReference:
                    resolved = posixpath.normpath(posixpath.join(node.path(), raw))
                    if resolved not in owned:
                        dependencies.append({"kind": "node", "node": name, "parm": parm.name(),
                                             "value": raw, "status": "unresolved", "source_path": resolved})
                elif raw and kind == hou.stringParmType.NodeReferenceList:
                    dependencies.append({"kind": "node_list", "node": name, "parm": parm.name(),
                                         "value": raw, "status": "unresolved"})
            if keys:
                dependencies.append({"kind": "expression", "node": name, "parm": parm.name(),
                                     "value": raw, "status": "unresolved"})
        flags = {}
        for method in ("isDisplayFlagSet", "isBypassed", "isRenderFlagSet"):
            accessor = getattr(node, method, None)
            if callable(accessor):
                flags[method] = bool(accessor())
        records.append({"name": name, "type": node.type().name(), "category": node.type().category().name(),
                        "position": list(node.position()), "comment": node.comment(), "parms": parms, "flags": flags})
        definition = node.type().definition()
        if definition is not None:
            dependencies.append({"kind": "definition", "node": name, "value": definition.libraryFilePath(),
                                 "type": node.type().name(), "category": node.type().category().name(), "status": "required"})
    for item in tuple(all_nodes) + dots:
        for wire in item.inputConnections():
            indirect = wire.subnetIndirectInput()
            source = wire.inputItem()
            entry = {"destination": _relative(item, parent), "input": wire.inputIndex(), "output": wire.inputItemOutputIndex()}
            if source is not None and source.path() in owned_items:
                entry["source"] = _relative(source, parent)
            elif indirect is not None:
                indirect_path = indirect.path()
                entry["indirect"] = (indirect_path[len(parent.path()) + 1:]
                                     if indirect_path.startswith(parent.path() + "/") else indirect_path)
                # An input belonging to the captured parent becomes a detached
                # input of the new container; nested subnet boundaries stay local.
                if indirect.parent() == parent:
                    entry["boundary"] = True
                    dependencies.append(dict(kind="input", status="detached", value=indirect_path,
                                             resolved_output=wire.outputIndex(), **entry))
            else:
                dependencies.append(dict(kind="input", status="detached",
                                         value=source.path() if source is not None else "unknown",
                                         resolved_output=wire.outputIndex(), **entry))
                continue  # native clips omit ordinary external input wires
            wires.append(entry)
    boxes = _boxes(nodes, dots, parent)
    box_records = [{"name": box.name(), "comment": box.comment(), "position": list(box.position()),
                    "nodes": sorted(node.name() for node in box.nodes(recurse=False)),
                    "dots": sorted(item.name() for item in box.items(recurse=False) if isinstance(item, hou.NetworkDot))} for box in boxes]
    dot_records = [{"name": _relative(dot, parent), "position": list(dot.position()), "pinned": dot.isPinned()} for dot in dots]
    return {"houdini": hou.applicationVersionString(), "category": "Lop", "source_scene": scene,
            "source_parent": parent.path(), "source_job": job,
            "roots": sorted(node.name() for node in nodes), "nodes": sorted(records, key=lambda item: item["name"]),
            "wires": sorted(wires, key=lambda item: (item["destination"], item["input"])),
            "boxes": sorted(box_records, key=lambda item: item["name"]), "dots": dot_records, "dependencies": dependencies}


def capture(nodes, parent, path):
    snapshot = observe(nodes, parent)
    dots = _dots(nodes, parent)
    root_dots = tuple(dot for dot in dots if dot.parent() == parent)
    boxes = _boxes(nodes, dots, parent)
    parent.saveItemsToFile(tuple(nodes) + root_dots + boxes, str(path), save_hda_fallbacks=False)
    after = observe(nodes, parent)
    if snapshot != after:
        raise LibraryError("The selection changed during capture. Save it again once it is stable.")
    return snapshot


class SavedNetworkService:
    def __init__(self, root=None):
        self.library = SavedNetworkLibrary(root or default_library_path(), USDMetadata())
        self._callbacks = {}

    def scene_path(self):
        return _main(lambda: _hou().hipFile.path())

    def selection_identity(self):
        def get():
            nodes, _ = _selected()
            return tuple((node.sessionId(), node.path()) for node in nodes)
        return _main(get)

    def save_selection(self, name, tags, notes="", *, recipe_id=None):
        identities = self.selection_identity()
        return self.save_identity(name=name, tags=tags, notes=notes, recipe_id=recipe_id,
                                  identities=identities, source_scene=self.scene_path(), reason="SaveSelection")

    def save_identity(self, *, name, tags, notes, recipe_id, identities, source_scene, reason, arm_id=None):
        def save():
            hou = _hou()
            nodes = tuple(hou.nodeBySessionId(identifier) for identifier, _ in identities)
            if not nodes or any(node is None or node.path() != path for node, (_, path) in zip(nodes, identities)):
                raise LibraryError("A watched node was deleted, renamed or replaced. Select the network again.")
            parent = nodes[0].parent()
            if parent.childTypeCategory().name() != "Lop" or any(node.parent() != parent for node in nodes):
                raise LibraryError("The watched selection no longer belongs to one Solaris network.")
            _bounded(nodes)
            def writer(path):
                result = capture(nodes, parent, path)
                result.update(armed_source_scene=source_scene, capture_reason=reason, arm_id=arm_id)
                return result
            return self.library.save(name, tags, notes, writer, recipe_id=recipe_id)
        return _main(save)

    def search(self, query="", *, all_versions=False):
        return _main(lambda: self.library.search(query, all_versions=all_versions))

    def inspect(self, recipe_id, version):
        return _main(lambda: self.library.load(recipe_id, version))

    def _preflight(self, record):
        hou = _hou()
        snapshot = record["snapshot"]
        validate_placement(snapshot)
        if snapshot["houdini"] != hou.applicationVersionString():
            raise LibraryError("This version was captured in a different Houdini build. It needs qualification before insertion.")
        for node in snapshot["nodes"]:
            category = hou.nodeTypeCategories().get(node["category"])
            if category is None or node["type"] not in category.nodeTypes():
                raise LibraryError(f"Required node type is unavailable: {node['category']}/{node['type']}")
        for dependency in snapshot["dependencies"]:
            if dependency["kind"] != "file" or dependency["status"] == "unresolved":
                continue
            current = _file_dependency(dependency["value"], [], hou.hipFile.path(), hou.getenv("JOB") or "")
            if current["status"] != "present":
                raise LibraryError(f"A required file is missing: {dependency['value']}")
            if current["source_path"] != dependency["source_path"]:
                raise LibraryError(f"This scene resolves a file reference differently: {dependency['value']}. Resolve it before inserting.")

    def restore(self, recipe_id, version, *, dependencies_reviewed=False):
        def insert():
            hou = _hou()
            record = self.library.load(recipe_id, version)
            self._preflight(record)
            expected = record["snapshot"]
            if expected["dependencies"] and not dependencies_reviewed:
                raise LibraryError("Review the listed dependencies before inserting this saved network.")
            stage = hou.node("/stage")
            if stage is None:
                raise LibraryError("Open a Solaris scene before inserting a recipe.")
            before = tuple((node, list(node.position()), bool(node.isDisplayFlagSet())) for node in stage.children())
            container = None
            try:
                with hou.undos.group("SYNAPSE insert saved network"):
                    container = stage.createNode("subnet", "recipe_" + recipe_id[:8], run_init_scripts=False)
                    if container.children():
                        raise LibraryError("The new recipe container was not empty.")
                    container.loadItemsFromFile(str(self.library.version_path(recipe_id, version) / "network.cpio"))
                    owned_nodes = {_relative(node, container): node for node in container.allSubChildren(recurse_in_locked_nodes=False)}
                    roots = tuple(owned_nodes.get(name) for name in expected["roots"])
                    if any(node is None for node in roots) or set(node.name() for node in container.children()) != set(expected["roots"]):
                        raise LibraryError("The inserted node set differs from the saved selection.")
                    expected_dots = expected.get("dots", [])
                    if {dot.name() for dot in container.networkDots()} != {dot["name"] for dot in expected_dots if "/" not in dot["name"]}:
                        raise LibraryError("The inserted connection dots differ from the saved selection.")
                    owned_dots = {_relative(dot, container): dot for dot in _dots(roots, container)}
                    for item in expected["boxes"]:
                        box = next((box for box in container.networkBoxes() if box.name() == item["name"]), None)
                        if box is None:
                            raise LibraryError("A saved section box is missing.")
                        box.setPosition(hou.Vector2(item["position"]))
                    # Moving a box also moves its members. Restore exact node
                    # coordinates after box positions, including nested contents.
                    for item in expected["nodes"]:
                        node = owned_nodes.get(item["name"])
                        if node is None:
                            raise LibraryError(f"A nested node is missing: {item['name']}")
                        node.setPosition(hou.Vector2(item["position"]))
                    for item in expected_dots:
                        dot = owned_dots.get(item["name"])
                        if dot is None:
                            raise LibraryError("A saved connection dot is missing.")
                        dot.setPosition(hou.Vector2(item["position"]))
                    actual = observe(roots, container)
                    for key in ("roots", "nodes", "wires", "boxes", "dots"):
                        if actual[key] != expected[key]:
                            raise LibraryError(f"Inserted {key} did not match the saved network.")
                    container.setDisplayFlag(False)
                    for node, position, display in before:
                        if list(node.position()) != position:
                            raise LibraryError("An existing node moved during insertion.")
                        if bool(node.isDisplayFlagSet()) != display:
                            node.setDisplayFlag(display)
                    return {"status": "inserted", "path": container.path(), "nodes": len(expected["nodes"]),
                            "dependencies": expected["dependencies"], "dependency_closure": "unverified",
                            "message": f"Inserted {record['name']} in a new subnet. External references remain as listed."}
            except Exception as exc:
                residue = None
                if container is not None:
                    path = container.path()
                    try:
                        container.destroy()
                        if hou.node(path) is not None:
                            residue = path
                    except Exception:
                        residue = path
                for node, position, display in before:
                    try:
                        if list(node.position()) != position:
                            node.setPosition(hou.Vector2(position))
                        if bool(node.isDisplayFlagSet()) != display:
                            node.setDisplayFlag(display)
                        if list(node.position()) != position or bool(node.isDisplayFlagSet()) != display:
                            residue = residue or "existing layout or display state differs"
                    except Exception:
                        residue = residue or "existing layout or display state could not be restored"
                suffix = f" Cleanup is incomplete: {residue}" if residue else " The new subnet was removed."
                raise LibraryError(f"Could not insert the saved network: {exc}.{suffix}") from exc
        return _main(insert)

    def subscribe(self, callback):
        def attach():
            hou = _hou()
            if callback in self._callbacks:
                return
            def event(kind):
                callback(str(kind).split(".")[-1])
            hou.hipFile.addEventCallback(event)
            self._callbacks[callback] = event
        return _main(attach)

    def unsubscribe(self, callback):
        def detach():
            event = self._callbacks.get(callback)
            if event is not None:
                _hou().hipFile.removeEventCallback(event)
                del self._callbacks[callback]
        return _main(detach)

    def record_notice(self, result):
        root = self.library.root
        root.mkdir(parents=True, exist_ok=True)
        path = root / "last-capture.json"
        data = dict(result, recorded_utc=datetime.now(timezone.utc).isoformat())
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".last-capture-", suffix=".json", dir=root, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(4):
                try:
                    temporary.replace(path)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    # Windows may briefly hold the destination during another
                    # atomic publication; permanent access errors still surface.
                    time.sleep(.01 * (2 ** attempt))
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def last_notice(self):
        path = self.library.root / "last-capture.json"
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or not isinstance(record.get("message"), str) or not record["message"].strip() or not isinstance(record.get("status"), str):
                raise ValueError("the saved capture result has an invalid shape")
            return record
        except (OSError, ValueError) as exc:
            return {"status": "failed", "message": f"The last capture record could not be read: {exc}"}

    def report_notice_failure(self, message):
        logging.getLogger(__name__).error("%s", message)
        def show():
            hou = _hou()
            if hou.isUIAvailable():
                hou.ui.setStatusMessage(message, severity=hou.severityType.Warning)
        return _main(show)
