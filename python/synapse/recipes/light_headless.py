"""One captured exposure operation on a closed, disposable H22 headless fixture.

No graph builder, render, tool registration or artist-scene entry point lives
here. Callers supply the existing recipe lifecycle/instance. The observer and
mutator are separate; only the observer produces detached authored/ USD data.
"""
from __future__ import annotations

import logging as _boundary_logging
_boundary_log = _boundary_logging.getLogger(__name__)

import ast
from copy import deepcopy
import hashlib
import json
import math
import os
import struct
import threading

from .contracts import ActionId, CheckId, CheckResult, CheckStatus, Refusal, RefusalKind
from .instance import ScopeObservation
from .light_capture import CaptureUnavailable, partition_exposure
from .transaction import HoudiniUndoDriver

BUILD = "22.0.400"
LIGHT_TYPE = "domelight::3.0"
USD_LIGHT_TYPE = "DomeLight_1"  # actual H22.0.400 probe; not guessed USD spelling
EXPOSURE = "xn__inputsexposure_vya"
ROOTS = ("/ch", "/img", "/mat", "/obj", "/out", "/shop", "/stage", "/tasks", "/vex")
EVENTS = ("BeingDeleted", "ChildCreated", "ChildDeleted", "ChildReordered", "ChildSelectionChanged",
          "CustomDataChanged", "FlagChanged", "InputRewired", "NameChanged", "PositionChanged",
          "AppearanceChanged", "NetworkBoxChanged", "NetworkBoxCreated", "NetworkBoxDeleted",
          "ParmTupleChanged", "ParmTupleAnimated", "ParmTupleChannelChanged", "ParmTupleEnabledChanged",
          "ParmTupleLockChanged", "ParmTupleVisibleChanged", "SelectionChanged", "SpareParmTemplatesChanged",
          "StickyNoteChanged", "StickyNoteCreated", "StickyNoteDeleted")


def authored_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _host():
    if threading.current_thread() is not threading.main_thread():
        raise CaptureUnavailable("All bounded LIGHT HOM calls require the main thread")
    try:
        import hou
    except ImportError as exc:
        raise CaptureUnavailable("Houdini is unavailable") from exc
    if hou.isUIAvailable() or hou.applicationVersionString() != BUILD:
        raise CaptureUnavailable("Only fresh disposable headless Houdini 22.0.400 is qualified")
    return hou


class AuthoredCodeCanonicalizer:
    """Exact scoped code data; this does not rebaseline the public c3 fixture."""
    def semantic_digest(self, state, *, version):
        if version != "headless-light-authored-code-v1":
            raise CaptureUnavailable("Unqualified headless canonicalizer version")
        return authored_digest({"version": version, "state": state})


class ClosedLightObserver:
    """Read the full generated OP authored code of the closed fixture.

    Supported scene: the nine empty standard manager contexts, one configured
    dome light and its one network box. No external scene, topology, sticky
    notes, animation, input graph, arbitrary assets or full HIP fidelity claim.
    USD is separately read from the actual cooked dome light, without rendering.
    """
    def __init__(self, node_path, box_name):
        _host()
        if (not isinstance(node_path, str) or not node_path.startswith("/stage/")
                or "/" in node_path[len("/stage/"):] or not node_path[len("/stage/"):].isidentifier()
                or not isinstance(box_name, str) or not box_name.isidentifier()):
            raise CaptureUnavailable("One configured closed-fixture node/box identity required")
        self.node_path, self.box_name = node_path, box_name

    def capture(self):
        hou = _host()
        root, stage = hou.node("/"), hou.node("/stage")
        managers = {node.path(): node for node in root.children()}
        if tuple(sorted(managers)) != ROOTS:
            raise CaptureUnavailable("Unqualified manager context set")
        for path, manager in managers.items():
            if manager.stickyNotes() or (path != "/stage" and (manager.children() or manager.networkBoxes())):
                raise CaptureUnavailable("Closed headless fixture contains outside authored items")
        children = tuple(stage.children())
        boxes = tuple(stage.networkBoxes())
        empty = not children and not boxes
        if not empty:
            if len(children) != 1 or children[0].path() != self.node_path or children[0].type().name() != LIGHT_TYPE:
                raise CaptureUnavailable("Closed fixture must contain only its captured dome light")
            if len(boxes) != 1 or boxes[0].name() != self.box_name or tuple(boxes[0].items()) != children:
                raise CaptureUnavailable("Actual network-box membership does not match the captured light")
        nodes = tuple(root.allSubChildren(recurse_in_locked_nodes=False, sync_delayed_definition=False))
        if len(nodes) > 64:
            raise CaptureUnavailable("Closed fixture node budget exceeded")
        edge_count = sum(len(node.inputConnections()) for node in nodes)
        if edge_count:
            raise CaptureUnavailable("The one-light fixture supports no input graph")
        scripts = {path: manager.asCode(recurse=True) for path, manager in managers.items()}
        token, values = None, {}
        if empty:
            # Measured absence during disposable fixture setup; never a fake
            # exposure or an available LIGHT action.
            normalized = {path: ast.dump(ast.parse(code), include_attributes=False) for path, code in scripts.items()}
        else:
            light = children[0]
            parm = light.parm(EXPOSURE)
            if parm is None or parm.isLocked() or parm.keyframes() or not light.isEditable():
                raise CaptureUnavailable("Captured exposure is unavailable, locked or animated")
            normalized, exposure = partition_exposure(scripts, EXPOSURE)
            actual = parm.eval()
            if type(actual) not in (int, float) or not math.isfinite(actual) or float(actual) != exposure:
                raise CaptureUnavailable("Authored exposure and independent HOM evaluation disagree")
            token = f"{os.getpid()}:{stage.sessionId()}:{boxes[0].sessionId()}"
            values = {self.node_path: {"parms": {EXPOSURE: exposure}}}
        return {"nodes": values, "authored": normalized,
                "userdata": {node.path(): dict(node.userDataDict()) for node in (root, *nodes)},
                "topology": {"node_paths": sorted(node.path() for node in nodes), "node_count": len(nodes), "edge_count": edge_count},
                "scope": {"box_present": not empty, "token": token},
                "globals": {"frame": float(hou.frame()), "fps": float(hou.fps()), "hip_path": hou.hipFile.path()}}

    def __call__(self, stage_path, spec, box_name):
        if stage_path != "/stage" or box_name != self.box_name:
            raise CaptureUnavailable("Observer scope changed")
        snapshot = self.capture()
        present = snapshot["scope"]["box_present"]
        ids = {"key": self.node_path} if present else {}
        return ScopeObservation(present, snapshot["scope"]["token"], ids,
                                deepcopy(snapshot), True, "Closed headless OP authored-code capture only")

    def usd_observation(self):
        hou = _host()
        snapshot = self.capture()
        if not snapshot["scope"]["box_present"]:
            raise CaptureUnavailable("No captured light exists")
        light = hou.node(self.node_path)
        stage = light.stage()  # one built-in source LOP, no render or external graph
        if stage is None:
            raise CaptureUnavailable("The actual light USD stage is unavailable")
        errors = tuple(str(error) for error in stage.GetCompositionErrors())
        members = tuple(stage.Traverse())
        if len(members) > 16:
            raise CaptureUnavailable("Closed light USD prim budget exceeded")
        lights = [prim for prim in members if prim.GetTypeName() == USD_LIGHT_TYPE]
        if len(lights) != 1:
            raise CaptureUnavailable("Exactly one runtime-verified USD dome light required")
        attribute = lights[0].GetAttribute("inputs:exposure")
        value = attribute.Get() if attribute else None
        expected = snapshot["nodes"][self.node_path]["parms"][EXPOSURE]
        attribute_type = str(attribute.GetTypeName()) if attribute else None
        if attribute_type != "float":
            raise CaptureUnavailable("Unqualified USD exposure storage type: " + str(attribute_type))
        # H22 authors this attribute as IEEE binary32; HOM's Python value is a
        # double. Derive exact schema quantization instead of adding a tolerance
        # or falsely rejecting a normal decimal input such as 1.1.
        expected_usd = struct.unpack("<f", struct.pack("<f", expected))[0]
        return {"prim_path": str(lights[0].GetPath()), "prim_type": lights[0].GetTypeName(),
                "exposure": value, "expected_exposure": expected,
                "attribute_type": attribute_type, "expected_usd_exposure": expected_usd,
                "source": "local_stage", "sanitization": "none",
                "composition_errors": errors, "node_errors": tuple(light.errors()),
                "prim_paths": tuple(str(prim.GetPath()) for prim in members),
                "authored_sha256": authored_digest(snapshot)}


class HeadlessLightBackend(HoudiniUndoDriver):
    """Existing transaction backend; one literal set, no mutator telemetry."""
    def __init__(self, observer):
        hou = _host()
        if type(observer) is not ClosedLightObserver:
            raise CaptureUnavailable("Trusted built-in closed-fixture observer required")
        super().__init__(undos=hou.undos)
        self.observer = observer
        self._foreign = 0
        self._unknown = False
        self._writing = False
        self._callback = self._event
        self._registered = []
        self._userdata = {node.path(): dict(node.userDataDict()) for node in (hou.node("/"), *hou.node("/").allSubChildren(recurse_in_locked_nodes=False, sync_delayed_definition=False))}
        self._events = tuple(getattr(hou.nodeEventType, name) for name in EVENTS)
        try:
            self.refresh_tracking()
        except BaseException as _boundary_error:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_headless.__init__', type(_boundary_error).__name__[:120])
            self.close()
            raise

    def refresh_tracking(self):
        hou = _host()
        nodes = (hou.node("/"), *hou.node("/").allSubChildren(recurse_in_locked_nodes=False, sync_delayed_definition=False))
        if len(nodes) > 65:
            raise CaptureUnavailable("Tracking node budget exceeded")
        for node in nodes:
            if node not in self._registered:
                node.addEventCallback(self._events, self._callback)
                self._registered.append(node)

    def _event(self, node=None, event_type=None, **kwargs):
        try:
            hou = _host()
            if node is None or event_type is None:
                self._unknown = True
                return
            parm_tuple = kwargs.get("parm_tuple")
            if (self._writing and node.path() == self.observer.node_path
                    and event_type in (hou.nodeEventType.ParmTupleChanged, hou.nodeEventType.ParmTupleChannelChanged)
                    and parm_tuple is not None and parm_tuple.name() == EXPOSURE):
                return
            self._foreign += 1
        except BaseException as _boundary_error:
            self._unknown = True
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_headless._event', type(_boundary_error).__name__[:120])

    def close(self):
        _host()
        for node in self._registered:
            node.removeEventCallback(self._events, self._callback)
        self._registered.clear()

    def foreign_epoch(self):
        # H22 setUserData did NOT emit the expected CustomDataChanged callback
        # in the real qualification probe. Userdata is immutable in this closed
        # operation; detect boundary drift explicitly and fail tracking closed.
        hou = _host()
        try:
            current = {node.path(): dict(node.userDataDict()) for node in (hou.node("/"), *hou.node("/").allSubChildren(recurse_in_locked_nodes=False, sync_delayed_definition=False))}
            if current != self._userdata:
                self._unknown = True
        except Exception as _boundary_error:
            self._unknown = True
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_headless.foreign_epoch', type(_boundary_error).__name__[:120])
        return None if self._unknown else self._foreign

    def snapshot(self):
        return self.observer.capture()

    def dependencies(self):
        hou = _host()
        # Lazy import keeps one source-identity authority and avoids the adapter/gate import cycle.
        from synapse.loop.light_gate import source_identity
        return {"houdini": hou.applicationVersionString(), "capture": "headless-light-authored-code-v1",
                "node_type": LIGHT_TYPE, "usd_type": USD_LIGHT_TYPE, "source_sha256": source_identity()}

    def preflight(self, operations):
        snapshot = self.snapshot()
        if not snapshot["scope"]["box_present"]:
            raise CaptureUnavailable("Closed fixture has no registered key light")
        for op in operations:
            if (op.kind != "set_parm" or op.target != self.observer.node_path or op.field != EXPOSURE
                    or type(op.value) not in (int, float) or not math.isfinite(op.value)
                    or not -2 <= op.value <= 2
                    or op.writes != (("nodes", op.target, "parms", EXPOSURE),)):
                return Refusal(RefusalKind.SLOT_INVALID, "Prepared LIGHT edit escapes the captured exposure binding")
        if len(operations) != 1:
            return Refusal(RefusalKind.SLOT_INVALID, "Exactly one prepared exposure edit required")
        return None

    def apply(self, operation):
        hou = _host()
        if self.preflight((operation,)) is not None:
            raise CaptureUnavailable("Prepared exposure edit refused")
        self._writing = True
        try:
            hou.node(self.observer.node_path).parm(EXPOSURE).set(float(operation.value))
        finally:
            self._writing = False

    def verify(self, action, instance):
        data = self.observer.usd_observation()
        usd_ok = type(data["exposure"]) in (int, float) and math.isfinite(data["exposure"]) and data["exposure"] == data["expected_usd_exposure"]
        composition_ok = not data["composition_errors"] and not data["node_errors"]
        owned = instance.owned_node_ids == {"key": self.observer.node_path}
        return [CheckResult(check, CheckStatus.PASS if ok else CheckStatus.FAIL, reason, data)
                for check, ok, reason in (
                    (CheckId.P1_GRAPH, owned, "Captured one-light graph and instance binding measured"),
                    (CheckId.P2_USD, usd_ok, "Actual cooked USD exposure compared with independent authored capture"),
                    (CheckId.P4_COMPOSITION, composition_ok, "Actual bounded light USD/node composition errors inspected"),
                    (CheckId.P6_LOCALITY, owned, "Closed fixture and exact prepared leaf; transaction separately checks full authored delta"))]
