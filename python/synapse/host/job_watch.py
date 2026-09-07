"""Explicit, passive native job observations; no cook, render, model or store.

Houdini 22.0.400 evidence: checks/notifications/native-observation/receipt.md.
ROP PostRender does not prove success. PDG CookComplete can include failed items.
These entries belong to the watcher; no path/time heuristic joins producer jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import islice
import threading
import uuid
import weakref


def _native_main(fn):
    from synapse.server.main_thread import run_on_main
    return run_on_main(fn, timeout=.25, record_stall=False, label="job watch")


def _enum_name(value):
    return str(value).rsplit(".", 1)[-1]


class _Unavailable(Exception):
    """Only locally authored, display-safe source limitations."""


@dataclass
class _Watch:
    source: str
    kind: str
    path: str
    scene: str
    generation: str
    session_id: int
    target_id: int
    context: object = None
    token: str = field(default_factory=lambda: uuid.uuid4().hex)
    cleanup: list = field(default_factory=list)
    active: bool = False
    started: bool = False
    ended: bool = False
    job_id: str | None = None
    state: str = "watching"
    lost: bool = False
    overflow: bool = False
    failure: bool = False
    cancelled: bool = False
    cancel_seen: bool = False
    post_write: bool = False
    items: dict = field(default_factory=dict)

    def identity(self):
        return {"session_id": self.session_id, "generation": self.generation}


class WatchSession:
    """Own only explicit subscriptions, invalidating them before native cleanup.

    ``run_on_main_fn`` and host modules are injection seams for independent tests.
    Snapshot/PDG-event processing is pure Python. Every HOM operation is marshalled.
    """

    def __init__(self, journal, *, hou_module=None, pdg_module=None,
                 run_on_main_fn=None, max_watches=32, max_items=4096, max_nodes=256):
        if hou_module is None:
            try:
                import hou as hou_module
            except ImportError:
                pass
        if pdg_module is None:
            try:
                import pdg as pdg_module
            except ImportError:
                pass
        self._hou, self._pdg, self._journal = hou_module, pdg_module, journal
        self._main = run_on_main_fn or _native_main
        self._lock = threading.RLock()
        self._generation = uuid.uuid4().hex
        self._watches = []
        self._scene_callback = None
        self._closed = False
        self._max_watches = max(1, min(32, max_watches))
        self._max_items = max(1, min(4096, max_items))
        self._max_nodes = max(1, min(256, max_nodes))

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _publish(self, method, *args, **kwargs):
        try:
            return getattr(self._journal, method)(*args, **kwargs)
        except Exception:
            return None

    def _live(self, watch):
        return not self._closed and watch.active and watch.generation == self._generation

    def _metadata(self, watch):
        return {"source": watch.source, "node": watch.path, "scene": watch.scene,
                "identity": watch.identity(), "context_id": watch.generation}

    def _title(self, watch):
        return {"Render": "Watched render activity", "Foreground cache": "Watched foreground cache activity",
                "Background cache": "Watched background cache graph", "TOP graph": "Watched TOP graph"}[watch.kind]

    def _start(self, watch):
        if watch.started:
            self._publish("finish", watch.job_id, "unknown", "Another start arrived before a verified ending.")
        watch.started, watch.ended, watch.state = True, False, "running"
        watch.lost = watch.overflow = watch.failure = watch.cancelled = watch.cancel_seen = watch.post_write = False
        watch.items.clear()
        watch.job_id = self._publish("start", "cache" if "cache" in watch.kind.lower() else "job",
                                     self._title(watch), **self._metadata(watch))
        if watch.job_id is None:
            watch.lost = True

    def _finish(self, watch, state, detail):
        if not watch.started:
            if watch.ended:
                return
            watch.ended, watch.state = True, "unknown"
            self._publish("note", "job", self._title(watch), "Ending observed without its start; outcome is unverified.",
                          state="unknown", dedupe_key=watch.token + ":missing-start", **self._metadata(watch))
            return
        if watch.lost and state != "failed":
            state = "unknown"
        if watch.job_id is None:
            self._publish("note", "job", self._title(watch), "The event journal could not retain the start; outcome is unverified.",
                          state="unknown", dedupe_key=watch.token + ":lost-start", **self._metadata(watch))
        else:
            self._publish("finish", watch.job_id, state, detail)
        watch.started, watch.ended, watch.state = False, True, state
        watch.job_id = None
        watch.items.clear()

    def _abandon(self, watch, detail):
        watch.active = False
        if watch.started:
            self._publish("finish", watch.job_id, "unknown", detail)
        watch.started, watch.job_id, watch.state = False, None, "stopped"
        watch.items.clear()

    def _detach(self, watch):
        # Never hold the session lock while a native emitter removes handlers.
        for remove in reversed(watch.cleanup):
            try:
                remove()
            except Exception:
                pass
        watch.cleanup.clear()

    def _install_scene_callback(self):
        if self._scene_callback is not None:
            return
        owner = weakref.ref(self)
        def callback(event):
            session = owner()
            if session is not None and _enum_name(event) in {"BeforeClear", "BeforeLoad", "BeforeQuit"}:
                session._scene_changed()
        self._hou.hipFile.addEventCallback(callback)
        try:
            if callback not in self._hou.hipFile.eventCallbacks():
                raise RuntimeError("Scene callback was not registered")
        except Exception:
            try:
                self._hou.hipFile.removeEventCallback(callback)
            except Exception:
                pass
            raise
        self._scene_callback = callback

    def _scene_changed(self):
        with self._lock:
            if self._closed:
                return
            self._generation = uuid.uuid4().hex
            watches, self._watches = self._watches, []
            for watch in watches:
                self._abandon(watch, "The scene changed; observation ended before a verified outcome.")
        try:
            self._main(lambda: [self._detach(watch) for watch in watches])
        except Exception:
            pass

    def _node_callback(self, watch):
        owner = weakref.ref(self)
        def callback(**kwargs):
            session = owner()
            if session is None:
                return
            def on_main():
                with session._lock:
                    if not session._live(watch):
                        return
                    event = _enum_name(kwargs.get("event_type"))
                    if event == "BeingDeleted":
                        session._abandon(watch, "A watched node was removed; its outcome is unverified.")
                    elif event == "NameChanged":
                        node = session._hou.nodeBySessionId(watch.session_id)
                        if node is not None:
                            watch.path = node.path()
                if event == "BeingDeleted":
                    session._detach(watch)
                    session._prune()
            try:
                session._main(on_main)
            except Exception:
                with session._lock:
                    watch.lost = True
        return callback

    def _rop_callback(self, watch):
        owner = weakref.ref(self)
        def callback(node, event_type, event_time):
            session = owner()
            if session is None:
                return
            def on_main():
                with session._lock:
                    if not session._live(watch):
                        return
                    if node.sessionId() != watch.target_id:
                        watch.lost = True
                        return
                    event = _enum_name(event_type)
                    if event == "PreRender":
                        session._start(watch)
                    elif event == "PostWrite":
                        watch.post_write = True
                    elif event == "PostRender":
                        try:
                            errors = bool(node.errors())
                            warnings = bool(node.warnings())
                        except Exception:
                            errors = warnings = False
                            watch.lost = True
                        if errors:
                            session._finish(watch, "failed", "Houdini reported render errors. Inspect the watched node.")
                        else:
                            detail = "Render callbacks ended. Requested range, cancellation and output validity are unverified."
                            if watch.post_write:
                                detail += " A write callback was observed."
                            if warnings:
                                detail += " Houdini reported warnings."
                            session._finish(watch, "unknown", detail)
            try:
                session._main(on_main)
            except Exception:
                with session._lock:
                    if session._live(watch):
                        watch.lost = True
                        if _enum_name(event_type) == "PostRender":
                            session._finish(watch, "unknown", "Render activity ended, but its native state could not be read.")
        return callback

    def _item_state(self, watch, item_id, value):
        if type(item_id) is not int or item_id < 0:
            watch.lost = True
            return
        if item_id not in watch.items and len(watch.items) >= self._max_items:
            watch.lost = watch.overflow = True
            return
        name = _enum_name(value)
        watch.items[item_id] = name
        watch.failure |= name == "CookedFail"
        watch.cancelled |= name == "CookedCancel"

    def _collect_node(self, watch, node, collected):
        # Native counts are checked before materializing the workItems list.
        count = node.stats().workItemCount()
        if type(count) is not int or count < 0:
            watch.lost = True
            return
        if count > self._max_items - len(collected):
            watch.lost = watch.overflow = True
            return
        actual = 0
        for item in islice(node.workItems, self._max_items + 1):
            actual += 1
            if actual > count or type(item.id) is not int or item.id < 0 or item.id in collected:
                watch.lost = True
                return
            collected[item.id] = _enum_name(item.state)
        if actual != count:
            watch.lost = True

    def _final_inventory(self, watch):
        """Read every extant graph node, never infer coverage from NodeCooked."""
        graph = watch.context.graph
        count = graph.nodeCount
        if type(count) is not int or count < 0 or watch.context.cooking:
            watch.lost = True
            return
        if count > self._max_nodes:
            watch.lost = watch.overflow = True
            return
        collected, actual = {}, 0
        for node in islice(graph.nodes(), self._max_nodes + 1):
            actual += 1
            if actual > count:
                watch.lost = True
                break
            # A zero-item, ungenerated sibling is not a finished graph.
            if node.isCooked is not True:
                watch.lost = True
            self._collect_node(watch, node, collected)
            if watch.overflow:
                break
        if actual != count or not set(watch.items) <= set(collected):
            watch.lost = True
        watch.items.clear()
        for item_id, state in collected.items():
            self._item_state(watch, item_id, state)

    def _pdg_callback(self, watch):
        owner = weakref.ref(self)
        def callback(event):
            session = owner()
            if session is None:
                return
            # Native PDG event thread: no HOM, run_on_main, Qt or store accesses.
            with session._lock:
                if not session._live(watch):
                    return
                event_name = ""
                try:
                    event_name = _enum_name(event.type)
                    if event_name == "CookStart":
                        session._start(watch)
                    watch.cancel_seen |= bool(watch.context.canceling)
                    if event_name == "CookError":
                        watch.failure = True
                    elif event_name == "WorkItemStateChange" and watch.started:
                        session._item_state(watch, event.workItemId, event.currentState)
                    elif event_name == "NodeCooked" and watch.started:
                        if event.node is None:
                            watch.lost = True
                        else:
                            collected = {}
                            session._collect_node(watch, event.node, collected)
                            for item_id, state in collected.items():
                                session._item_state(watch, item_id, state)
                    elif event_name == "CookComplete":
                        if watch.started:
                            session._final_inventory(watch)
                        states = set(watch.items.values())
                        if watch.failure:
                            state, detail = "failed", "Houdini reported failed TOP work. Inspect the watched graph."
                        elif watch.lost or watch.overflow:
                            state, detail = "unknown", "TOP activity ended with incomplete observation."
                            if watch.overflow:
                                detail += " The node or item observation limit was reached."
                        elif watch.cancelled:
                            state, detail = "cancelled", "Houdini reported cancelled TOP work; some items may have finished."
                        elif watch.cancel_seen:
                            state, detail = "unknown", "A cancellation request was observed; its full outcome is unverified."
                        elif states and states <= {"CookedSuccess", "CookedCache"}:
                            state, detail = "completed", "All items in the bounded final TOP graph inventory finished or were cached. Output contents were not validated."
                        else:
                            state, detail = "unknown", "TOP activity ended without a complete set of terminal item states."
                        session._finish(watch, state, detail)
                except Exception:
                    watch.lost = True
                    if event_name == "CookComplete":
                        session._finish(watch, "unknown", "TOP activity ended, but its terminal state could not be read.")
        return callback

    def _prune(self):
        with self._lock:
            self._watches[:] = [watch for watch in self._watches if self._live(watch)]

    def _attach(self, selected, target, kind, source):
        self._prune()
        target_id = target.sessionId()
        context = target.getPDGGraphContext() if source == "native.pdg" else None
        if source == "native.pdg" and (context is None or self._pdg is None):
            raise _Unavailable("No existing TOP graph context is available; watching does not initialize one.")
        for watch in self._watches:
            if self._live(watch) and watch.source == source and (
                (source == "native.rop" and watch.target_id == target_id) or
                (source == "native.pdg" and watch.context == context)):
                return watch
        if sum(self._live(watch) for watch in self._watches) >= self._max_watches:
            raise _Unavailable("The active watch limit was reached.")
        watch = _Watch(source, kind, selected.path(), self._hou.hipFile.path(), self._generation,
                       selected.sessionId(), target_id, context)
        try:
            if source == "native.rop":
                callback = self._rop_callback(watch)
                target.addRenderEventCallback(callback, run_before_script=False)
                watch.cleanup.append(lambda: target.removeRenderEventCallback(callback))
            else:
                callback = self._pdg_callback(watch)
                for event_name in ("CookStart", "CookComplete", "CookError", "NodeCooked", "WorkItemStateChange"):
                    handle = context.addEventHandler(callback, getattr(self._pdg.EventType, event_name))
                    watch.cleanup.append(lambda handle=handle: context.removeEventHandler(handle))
                    if handle not in context.eventHandlers:
                        raise RuntimeError("TOP callback registration could not be verified")
            node_callback = self._node_callback(watch)
            events = (self._hou.nodeEventType.BeingDeleted, self._hou.nodeEventType.NameChanged)
            nodes = [selected] if selected.sessionId() == target_id else [selected, target]
            for node in nodes:
                node.addEventCallback(events, node_callback)
                watch.cleanup.append(lambda node=node: node.removeEventCallback(events, node_callback))
                if not any(cb == node_callback for _types, cb in node.eventCallbacks()):
                    raise RuntimeError("Node callback registration could not be verified")
        except Exception:
            watch.active = False
            self._detach(watch)
            raise
        watch.active = True
        self._watches.append(watch)
        return watch

    def watch_selected(self):
        result = {"watched": [], "unavailable": []}
        if self._hou is None or self._closed:
            result["unavailable"].append({"path": "Selection", "reason": "Houdini observation is unavailable in this session."})
            return result
        def on_main():
            nodes = self._hou.selectedNodes()
            if not nodes:
                return
            self._install_scene_callback()
            for node in islice(nodes, self._max_watches + 1):
                path = node.path()
                sources = []
                if isinstance(node, self._hou.RopNode):
                    if node.type().name() in {"null", "ropnet"}:
                        result["unavailable"].append({"path": path, "reason": "This render container does not provide render activity callbacks. Select a render output."})
                        continue
                    sources.append((node, "Render", "native.rop"))
                elif isinstance(node, self._hou.TopNode):
                    sources.append((node, "TOP graph", "native.pdg"))
                elif node.type().name() == "filecache::2.0":
                    render = node.node("render")
                    if isinstance(render, self._hou.RopNode):
                        sources.append((render, "Foreground cache", "native.rop"))
                    else:
                        result["unavailable"].append({"path": path, "reason": "Foreground cache render output is unavailable."})
                    try:
                        parm = node.parm("targettopnetwork")
                        top = parm.evalAsNode() if parm is not None else None
                    except Exception:
                        top = None
                    if isinstance(top, self._hou.TopNode):
                        sources.append((top, "Background cache", "native.pdg"))
                    else:
                        result["unavailable"].append({"path": path, "reason": "Background cache TOP graph is unavailable; foreground coverage is separate."})
                else:
                    result["unavailable"].append({"path": path, "reason": "No verified SOP or simulation range completion event. Select its cache output or TOP network."})
                for target, kind, source in sources:
                    try:
                        watch = self._attach(node, target, kind, source)
                        row = {"path": watch.path, "kind": watch.kind}
                        if row not in result["watched"]:
                            result["watched"].append(row)
                    except _Unavailable as exc:
                        result["unavailable"].append({"path": path, "reason": kind + ": " + str(exc)})
                    except Exception:
                        result["unavailable"].append({"path": path, "reason": kind + " callbacks could not be attached to an existing source. No job was started."})
            if len(nodes) > self._max_watches + 1:
                result["unavailable"].append({"path": "Selection", "reason": "The selection exceeds the bounded watch limit."})
        try:
            self._main(on_main)
        except Exception:
            result["unavailable"].append({"path": "Selection", "reason": "Scene-safe observation could not be established. No job was started."})
        return result

    def snapshot(self):
        with self._lock:
            return [{"path": watch.path, "kind": watch.kind, "state": watch.state,
                     "active": self._live(watch), "identity": watch.identity()} for watch in self._watches]

    def focus(self, identity):
        if (type(identity) is not dict or set(identity) != {"session_id", "generation"}
                or type(identity["session_id"]) is not int or identity["session_id"] < 0
                or type(identity["generation"]) is not str):
            return False
        def on_main():
            with self._lock:
                if self._closed or identity["generation"] != self._generation or not any(
                    self._live(watch) and watch.identity() == identity for watch in self._watches):
                    return False
                node = self._hou.nodeBySessionId(identity["session_id"])
                if node is None or node.sessionId() != identity["session_id"]:
                    return False
                node.setCurrent(True, clear_all_selected=True)
                return True
        try:
            return bool(self._main(on_main))
        except Exception:
            return False

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            watches, self._watches = self._watches, []
            callback, self._scene_callback = self._scene_callback, None
            for watch in watches:
                self._abandon(watch, "Watching stopped before a verified outcome. The job itself was not cancelled.")
        def on_main():
            for watch in watches:
                self._detach(watch)
            if callback is not None:
                try:
                    self._hou.hipFile.removeEventCallback(callback)
                except Exception:
                    pass
        try:
            self._main(on_main)
        except Exception:
            pass
