"""Independent observable boundaries for the explicit native watcher."""
import gc
import threading
import types
import weakref

import pytest

from synapse.job_events import JobJournal
from synapse.host.job_watch import WatchSession


class Hip:
    def __init__(self, host):
        self.host, self.callbacks = host, []
    def path(self):
        self.host.check(); return "C:/synthetic/scene-a.hip"
    def addEventCallback(self, cb):
        self.host.check(); self.callbacks.append(cb)
    def removeEventCallback(self, cb):
        self.host.check(); self.callbacks.remove(cb)
    def eventCallbacks(self):
        self.host.check(); return tuple(self.callbacks)
    def emit(self, event):
        for callback in self.callbacks[:]: callback(event)


class Node:
    def __init__(self, host, sid=1, path="/obj/fixture", typename="python"):
        self.host, self.sid, self.p, self.typename = host, sid, path, typename
        self.callbacks, self.children = [], {}
        self.error_rows, self.warning_rows = (), ()
        self.fail_remove = False
        host.nodes[sid] = self
    def path(self): self.host.check(); return self.p
    def sessionId(self): self.host.check(); return self.sid
    def type(self): self.host.check(); return types.SimpleNamespace(name=lambda: self.typename)
    def node(self, name): self.host.check(); return self.children.get(name)
    def parm(self, name):
        self.host.check()
        if name == "targettopnetwork": return types.SimpleNamespace(evalAsNode=lambda: self.children.get("topnet1"))
        return None
    def errors(self): self.host.check(); return self.error_rows
    def warnings(self): self.host.check(); return self.warning_rows
    def addEventCallback(self, events, cb): self.host.check(); self.callbacks.append((events, cb))
    def removeEventCallback(self, events, cb):
        self.host.check()
        if self.fail_remove: raise RuntimeError("synthetic remove failure")
        self.callbacks.remove((events, cb))
    def eventCallbacks(self): self.host.check(); return tuple(self.callbacks)
    def setCurrent(self, on, clear_all_selected=False): self.host.check(); self.host.focused = self.sid
    def cook(self, *args, **kwargs): raise AssertionError("Observation must never cook")
    def render(self, *args, **kwargs): raise AssertionError("Observation must never render")
    def emit_node(self, event):
        for events, callback in self.callbacks[:]:
            if event in events: callback(node=self, event_type=event)


class Rop(Node):
    def __init__(self, host, sid=1, path="/out/fixture"):
        super().__init__(host, sid, path, "geometry")
        self.render_callbacks = []
    def addRenderEventCallback(self, cb, run_before_script=False):
        self.host.check(); assert run_before_script is False; self.render_callbacks.append(cb)
    def removeRenderEventCallback(self, cb):
        self.host.check()
        if self.fail_remove: raise RuntimeError("synthetic remove failure")
        self.render_callbacks.remove(cb)
    def emit(self, event):
        for cb in self.render_callbacks[:]: cb(self, event, 0.0)


class Graph:
    def __init__(self): self.rows = []
    @property
    def nodeCount(self): return len(self.rows)
    def nodes(self): return list(self.rows)


def pdg_node(name, states, offset=0):
    node = types.SimpleNamespace(name=name, workItems=[types.SimpleNamespace(id=i + offset, state=s) for i, s in enumerate(states)])
    node.isCooked = bool(states)
    node.stats = lambda: types.SimpleNamespace(workItemCount=lambda: len(node.workItems))
    return node


class Context:
    def __init__(self):
        self.eventHandlers, self.fail_at, self.fail_remove = [], None, False
        self.canceling, self.cooking, self.name = False, False, "fixture-graph"
        self.graph = Graph()
    def addEventHandler(self, cb, event):
        if self.fail_at == len(self.eventHandlers): raise RuntimeError("synthetic registration failure")
        handle = types.SimpleNamespace(callback=cb, event=event)
        self.eventHandlers.append(handle); return handle
    def removeEventHandler(self, handle):
        if self.fail_remove: raise RuntimeError("synthetic removal failure")
        self.eventHandlers.remove(handle)
    def hasEventHandler(self, callback): return any(h.callback is callback for h in self.eventHandlers)
    def emit(self, event_type, states=(), *, item_id=-1, current="Undefined", node_name="worker"):
        node = pdg_node(node_name, states) if states is not None else None
        if event_type == "NodeCooked" and node is not None:
            self.graph.rows = [row for row in self.graph.rows if row.name != node.name] + [node]
        event = types.SimpleNamespace(type=event_type, node=node, workItemId=item_id, currentState=current, message="", context=self)
        for handle in self.eventHandlers[:]:
            if handle.event == event_type: handle.callback(event)


class Top(Node):
    def __init__(self, host, sid=1, path="/obj/topnet", context=None):
        super().__init__(host, sid, path, "topnet")
        self.context = context
    def getPDGGraphContext(self): self.host.check(); return self.context


class Host:
    RopNode, TopNode = Rop, Top
    nodeEventType = types.SimpleNamespace(BeingDeleted="BeingDeleted", NameChanged="NameChanged")
    hipFileEventType = types.SimpleNamespace(BeforeClear="BeforeClear", BeforeLoad="BeforeLoad", BeforeQuit="BeforeQuit")
    ropRenderEventType = types.SimpleNamespace(PreRender="PreRender", PreFrame="PreFrame", PostFrame="PostFrame", PostWrite="PostWrite", PostRender="PostRender")
    def __init__(self):
        self.nodes, self.selected, self.focused, self.main_calls, self.hom_reads = {}, [], None, 0, 0
        self.allowed = threading.local()
        self.hipFile = Hip(self)
    def check(self):
        assert getattr(self.allowed, "active", False), "HOM outside run_on_main"
        self.hom_reads += 1
    def run_main(self, fn):
        old = getattr(self.allowed, "active", False)
        self.allowed.active = True; self.main_calls += 1
        try: return fn()
        finally: self.allowed.active = old
    def selectedNodes(self): self.check(); return tuple(self.selected)
    def nodeBySessionId(self, sid): self.check(); return self.nodes.get(sid)


PDG = types.SimpleNamespace(EventType=types.SimpleNamespace(**{name: name for name in
    ("CookStart", "CookComplete", "CookError", "CookWarning", "NodeCooked", "WorkItemStateChange")}))


def setup(kind="rop", **kwargs):
    host, journal = Host(), JobJournal()
    node = Rop(host) if kind == "rop" else Top(host, context=Context()) if kind == "top" else Node(host)
    host.selected = [node]
    watcher = WatchSession(journal, hou_module=host, pdg_module=PDG, run_on_main_fn=host.run_main, **kwargs)
    return host, journal, node, watcher


def entries(journal): return journal.snapshot()["entries"]


def test_attach_is_passive_and_snapshot_detached():
    host, journal, node, watcher = setup()
    result = watcher.watch_selected()
    assert result["watched"] == [{"path": node.p, "kind": "Render"}]
    assert entries(journal) == []
    snapshot = watcher.snapshot()
    snapshot[0]["path"] = "changed"
    assert watcher.snapshot()[0]["path"] == node.p
    watcher.close()
    assert not node.render_callbacks and not host.hipFile.callbacks


@pytest.mark.parametrize("errors,expected", [((), "unknown"), (("raw traceback secret",), "failed")])
def test_rop_end_is_not_success(errors, expected):
    host, journal, node, watcher = setup(); watcher.watch_selected()
    node.emit("PreRender"); node.emit("PostWrite"); node.error_rows = errors; node.emit("PostRender")
    assert entries(journal)[0]["state"] == expected
    assert "raw traceback secret" not in entries(journal)[0]["detail"]
    node.emit("PostRender")
    assert len(entries(journal)) == 1
    watcher.close()


def test_missing_start_and_repeated_runs():
    host, journal, node, watcher = setup(); watcher.watch_selected()
    node.emit("PostRender"); node.emit("PostRender")
    assert [e["state"] for e in entries(journal)] == ["unknown"]
    for _ in range(2): node.emit("PreRender"); node.emit("PostRender")
    assert len(entries(journal)) == 3 and len({e["id"] for e in entries(journal)}) == 3
    watcher.close()


def test_scene_replacement_invalidates_identity_and_running_watch():
    host, journal, node, watcher = setup(); watcher.watch_selected(); node.emit("PreRender")
    identity = entries(journal)[0]["identity"]
    assert watcher.focus(identity) and host.focused == node.sid
    host.hipFile.emit("BeforeClear")
    Rop(host, sid=node.sid, path=node.p)
    assert not watcher.focus(identity)
    assert entries(journal)[0]["state"] == "unknown"
    node.emit("PostRender")
    assert len(entries(journal)) == 1
    watcher.close()


def test_rename_keeps_identity_but_delete_invalidates_it():
    host, journal, node, watcher = setup(); watcher.watch_selected(); node.emit("PreRender")
    identity = entries(journal)[0]["identity"]
    node.p = "/out/renamed"; node.emit_node("NameChanged")
    assert watcher.focus(identity)
    node.emit_node("BeingDeleted"); host.nodes.pop(node.sid)
    assert not watcher.focus(identity)
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()


def test_close_and_failed_unsubscribe_make_queued_callbacks_inert():
    host, journal, node, watcher = setup(); watcher.watch_selected(); node.emit("PreRender")
    node.fail_remove = True
    watcher.close(); watcher.close()
    before = journal.snapshot()
    node.emit("PreRender"); node.emit("PostRender")
    assert journal.snapshot() == before and before["entries"][0]["state"] == "unknown"


def test_destructor_only_cleanup_does_not_leave_owner_in_callbacks():
    host, journal, node, watcher = setup(); watcher.watch_selected()
    ref = weakref.ref(watcher)
    del watcher; gc.collect()
    assert ref() is None and node.render_callbacks == [] and host.hipFile.callbacks == []


def test_unsupported_sop_and_null_rop_never_claim_watch():
    host, journal, node, watcher = setup("sop")
    assert not watcher.watch_selected()["watched"]
    assert "cache" in watcher.watch_selected()["unavailable"][0]["reason"].lower()
    watcher.close()
    host, journal, node, watcher = setup(); node.typename = "null"
    assert not watcher.watch_selected()["watched"]
    watcher.close()


def test_filecache_foreground_survives_unavailable_background():
    host, journal, node, watcher = setup("sop")
    node.typename = "filecache::2.0"
    node.children["render"] = Rop(host, sid=2, path=node.p + "/render")
    node.children["topnet1"] = Top(host, sid=3, path=node.p + "/topnet1", context=None)
    result = watcher.watch_selected()
    assert result["watched"] == [{"path": node.p, "kind": "Foreground cache"}]
    assert result["unavailable"] and "background" in result["unavailable"][0]["reason"].lower()
    watcher.close()


def test_filecache_partial_background_registration_keeps_foreground_live():
    host, journal, node, watcher = setup("sop")
    node.typename = "filecache::2.0"
    render = Rop(host, sid=2, path=node.p + "/render")
    context = Context(); context.fail_at = 2
    node.children.update(render=render, topnet1=Top(host, sid=3, path=node.p + "/topnet1", context=context))
    result = watcher.watch_selected()
    assert result["watched"] == [{"path": node.p, "kind": "Foreground cache"}]
    assert context.eventHandlers == [] and len(render.render_callbacks) == 1
    render.emit("PreRender"); render.emit("PostRender")
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()


@pytest.mark.parametrize("states,expected", [(["CookedSuccess"], "completed"), (["CookedFail"], "failed"),
    (["CookedCancel"], "cancelled"), (["Cooking"], "unknown"), ([], "unknown")])
def test_pdg_terminal_uses_native_item_states_without_hom_on_callback_thread(states, expected):
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    reads = host.hom_reads
    def emit():
        node.context.emit("CookStart", states=None)
        node.context.emit("NodeCooked", states=states)
        node.context.emit("CookComplete", states=None)
    worker = threading.Thread(target=emit); worker.start(); worker.join(1)
    assert not worker.is_alive() and host.hom_reads == reads
    assert entries(journal)[0]["state"] == expected
    watcher.close()


def test_pdg_missing_start_and_collected_state_overflow_are_unknown():
    host, journal, node, watcher = setup("top", max_items=2); watcher.watch_selected()
    node.context.emit("CookComplete", states=None)
    node.context.emit("CookStart", states=None)
    node.context.emit("NodeCooked", states=["CookedSuccess"] * 3)
    node.context.emit("CookComplete", states=None)
    assert [e["state"] for e in entries(journal)] == ["unknown", "unknown"]
    assert "limit" in entries(journal)[1]["detail"].lower()
    watcher.close()


def test_pdg_canceling_does_not_invent_cancelled_outcome():
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    node.context.canceling = True; node.context.emit("CookStart", states=None)
    node.context.canceling = False
    node.context.emit("NodeCooked", states=["CookedSuccess"])
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()


def test_partial_pdg_registration_rolls_back_its_source():
    host, journal, node, watcher = setup("top"); node.context.fail_at = 2
    assert not watcher.watch_selected()["watched"]
    assert node.context.eventHandlers == [] and node.callbacks == []
    watcher.close()


def test_pdg_failed_unsubscribe_and_journal_exception_cannot_escape_to_job():
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    def broken(*args, **kwargs): raise RuntimeError("synthetic publication failure")
    journal.start = broken
    node.context.emit("CookStart", states=None)
    node.context.emit("NodeCooked", states=["CookedSuccess"])
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "unknown"
    node.context.fail_remove = True; watcher.close()
    before = journal.snapshot()
    node.context.emit("CookStart", states=None); node.context.emit("CookComplete", states=None)
    assert journal.snapshot() == before


def test_focus_rejects_malformed_identity_and_never_uses_path():
    host, journal, node, watcher = setup(); watcher.watch_selected()
    for value in (None, {}, {"session_id": True, "generation": "x"}, {"path": node.p}, {"session_id": node.sid, "generation": "wrong"}):
        assert watcher.focus(value) is False
    watcher.close()


def test_deleted_watches_do_not_accumulate_beyond_active_limit():
    host, journal, node, watcher = setup(max_watches=2)
    for sid in range(1, 101):
        node = Rop(host, sid=sid)
        host.selected = [node]
        assert watcher.watch_selected()["watched"]
        callbacks = list(node.render_callbacks)
        node.emit_node("BeingDeleted"); host.nodes.pop(sid)
        for callback in callbacks: callback(node, "PreRender", 0.0)
        assert len(watcher._watches) <= 2
        assert entries(journal) == []
    watcher.close()


def test_pdg_success_subset_does_not_hide_an_unobserved_pending_node():
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    node.context.emit("CookStart", states=None)
    node.context.emit("NodeCooked", states=["CookedSuccess"], node_name="observed")
    node.context.graph.rows.append(pdg_node("unobserved", ["Uncooked"], 99))
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()


def test_pdg_final_graph_inventory_can_finish_without_node_cooked_event():
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    node.context.emit("CookStart", states=None)
    node.context.graph.rows = [pdg_node("a", ["CookedSuccess"]), pdg_node("b", ["CookedCache"], 3)]
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "completed"
    watcher.close()


def test_pdg_ungenerated_empty_sibling_is_not_a_complete_graph():
    host, journal, node, watcher = setup("top"); watcher.watch_selected()
    node.context.emit("CookStart", states=None)
    node.context.emit("NodeCooked", states=["CookedSuccess"])
    node.context.graph.rows.append(pdg_node("ungenerated", []))
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()


@pytest.mark.parametrize("fault", ["missing_api", "node_limit", "item_limit", "count_mismatch", "duplicate_id", "new_cook"])
def test_pdg_unprovable_final_inventory_is_unknown(fault):
    host, journal, node, watcher = setup("top", max_items=2, max_nodes=2); watcher.watch_selected()
    node.context.emit("CookStart", states=None)
    node.context.emit("NodeCooked", states=["CookedSuccess"])
    if fault == "missing_api": node.context.graph = None
    elif fault == "node_limit": node.context.graph.rows += [pdg_node("b", [], 1), pdg_node("c", [], 2)]
    elif fault == "item_limit": node.context.graph.rows += [pdg_node("b", ["CookedSuccess"] * 3, 1)]
    elif fault == "count_mismatch": node.context.graph.rows[0].stats = lambda: types.SimpleNamespace(workItemCount=lambda: 0)
    elif fault == "duplicate_id": node.context.graph.rows += [pdg_node("b", ["CookedSuccess"], 0)]
    elif fault == "new_cook": node.context.cooking = True
    node.context.emit("CookComplete", states=None)
    assert entries(journal)[0]["state"] == "unknown"
    watcher.close()
