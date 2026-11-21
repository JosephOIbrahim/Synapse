"""SIDEFXCTO-2 / R-012 — the agent history tools cannot take the artist's work.

Predicates from REPAIR_SCAFFOLD_2026-11-20 (audit commit 4aab502a):

* An agent-initiated undo with an artist edit on top refuses and NAMES the top
  label (and performs no native undo). Same for redo.
* No model-reachable schema field disables undo grouping: the
  ``houdini_execute_python`` schema no longer advertises ``atomic``, and the
  registry payload builder drops it even when a client sends it.
* The history tools stay registered (the 139-tool count is pinned) but are
  gated at ``review``, so the default standard-mode worker may not call them.

The real undo-history check needs Houdini; these unit tests drive a fake
``hou.undos`` through the real handler, which the node explicitly permits.
"""

import json
from types import SimpleNamespace

import pytest

from synapse.core.protocol import SynapseCommand


class _Undos:
    """Top-first undo/redo stacks, mirroring hou.undos label order."""

    def __init__(self, undo=(), redo=(), enabled=True):
        self.undo = list(undo)
        self.redo = list(redo)
        self.enabled = enabled
        self.calls = []

    def areEnabled(self):
        return self.enabled

    def undoLabels(self):
        return tuple(self.undo)

    def redoLabels(self):
        return tuple(self.redo)

    def performUndo(self):
        self.calls.append("undo")
        self.redo.insert(0, self.undo.pop(0))

    def performRedo(self):
        self.calls.append("redo")
        self.undo.insert(0, self.redo.pop(0))


@pytest.fixture
def env(monkeypatch):
    import synapse.server.handlers as handlers_mod

    undos = _Undos()
    monkeypatch.setattr(handlers_mod, "hou", SimpleNamespace(undos=undos), raising=False)
    monkeypatch.setattr(handlers_mod, "HOU_AVAILABLE", True)
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    handler = handlers_mod.SynapseHandler()
    monkeypatch.setattr(handler._registry._floor_gate, "wrap",
                        lambda kind, payload, fn, **kw: fn(payload))
    monkeypatch.setattr(handler, "_submit_logs", lambda *a, **kw: None)
    return handler, undos, handlers_mod


def _capture_baseline(handler, undos):
    """Record the session baseline the way handle() does, before any command."""
    assert handler._undo_scope.note_session_start(undos) is True
    assert handler._undo_scope.needs_baseline is False


# ---------------------------------------------------------------------------
# The artist's work is untouchable
# ---------------------------------------------------------------------------

def test_undo_with_artist_edit_on_top_refuses_and_names_it(env):
    handler, undos, mod = env
    undos.undo = ["Artist edit", "SYNAPSE: create_node"]
    _capture_baseline(handler, _Undos())

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_undo({})

    message = str(caught.value)
    assert 'the next undo step is "Artist edit"' in message
    assert "artist's own work" in message
    assert undos.calls == []


def test_redo_with_artist_edit_on_top_refuses_and_names_it(env):
    handler, undos, mod = env
    undos.redo = ["Artist edit", "SYNAPSE: create_node"]
    _capture_baseline(handler, _Undos())

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_redo({})

    assert 'the next redo step is "Artist edit"' in str(caught.value)
    assert undos.calls == []


def test_refusal_is_a_refused_outcome_on_the_wire(env):
    handler, undos, _mod = env
    undos.undo = ["Artist edit"]
    _capture_baseline(handler, _Undos())

    response = handler.handle(SynapseCommand(id="r-012", type="undo", payload={}))

    assert response.success is False
    assert "Artist edit" in response.error
    wire = json.loads(response.to_json())
    outcome = wire["data"]["outcome"]
    assert outcome["code"] == "policy.safety_guard"
    assert outcome["outcome"] == "refused"
    assert outcome["dispatched"] == "no"
    assert undos.calls == []


# ---------------------------------------------------------------------------
# SYNAPSE's own, this-session step is allowed
# ---------------------------------------------------------------------------

def test_session_synapse_step_is_allowed_and_performed(env):
    handler, undos, _mod = env
    _capture_baseline(handler, undos)          # empty stack at session start
    undos.undo = ["synapse_execute"]           # created after the baseline

    result = handler._handle_undo({})

    assert result["status"] == "ok"
    assert undos.calls == ["undo"]


def test_synapse_step_from_before_this_session_refuses(env):
    handler, undos, mod = env
    undos.undo = ["SYNAPSE: old session build"]
    _capture_baseline(handler, undos)          # it was already there

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_undo({})

    message = str(caught.value)
    assert '"SYNAPSE: old session build"' in message
    assert "before this SYNAPSE session started" in message
    assert undos.calls == []


def test_handle_captures_the_baseline_from_hou_undos(env):
    """handle() itself must baseline from hou.undos, not from the hou module.

    Before the fix handle() passed ``hou``: both label reads came back None, no
    baseline was ever captured, and a SYNAPSE step left by an earlier session
    passed the prefix check (release review, 2026-11-21).
    """
    handler, undos, _mod = env
    undos.undo = ["SYNAPSE: old session build"]
    assert handler._undo_scope.needs_baseline is True

    handler.handle(SynapseCommand(id="b-000", type="ping", payload={}))
    assert handler._undo_scope.needs_baseline is True, "a read-only command must not wait on a capture"
    # A mutating command captures before it runs (it fails here: the fake hou has no nodes).
    handler.handle(SynapseCommand(id="b-001", type="create_node",
                                  payload={"parent": "/obj", "type": "null"}))
    assert handler._undo_scope.needs_baseline is False, "handle() captured no baseline"

    response = handler.handle(SynapseCommand(id="b-002", type="undo", payload={}))
    assert response.success is False
    assert "before this SYNAPSE session started" in response.error
    assert undos.calls == []

def test_disabled_history_refuses(env):
    handler, undos, mod = env
    undos.enabled = False

    with pytest.raises(mod.HistoryScopeRefused):
        handler._handle_undo({})

    assert undos.calls == []


# ---------------------------------------------------------------------------
# No model-reachable field disables undo grouping
# ---------------------------------------------------------------------------

def test_execute_python_schema_has_no_atomic_field():
    from synapse.mcp._tool_registry import TOOL_JSON

    props = TOOL_JSON["houdini_execute_python"]["inputSchema"]["properties"]
    assert "atomic" not in props
    assert set(props) == {"code", "dry_run"}


def test_execute_python_builder_drops_atomic():
    from synapse.mcp._tool_registry import _execute_python_payload

    payload = _execute_python_payload(
        {"code": "x = 1", "dry_run": False, "atomic": False})
    assert "atomic" not in payload
    assert payload == {"content": "x = 1", "dry_run": False}


# ---------------------------------------------------------------------------
# Still registered (139), now review-gated
# ---------------------------------------------------------------------------

def test_history_tools_stay_registered_but_are_review_gated(monkeypatch):
    from synapse.mcp._tool_registry import TOOL_DEFS, TOOL_DISPATCH
    from shared.constants import OPERATION_GATES

    assert len(TOOL_DEFS) == 139, "R-012 must not change the registered tool count"
    assert "houdini_undo" in TOOL_DISPATCH and "houdini_redo" in TOOL_DISPATCH
    assert OPERATION_GATES["history_undo"] == "review"
    assert OPERATION_GATES["history_redo"] == "review"

    from synapse.panel import worker_policy
    monkeypatch.delenv("SYNAPSE_WORKER_TOOL_PROFILE", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "standard")
    for name in ("houdini_undo", "houdini_redo"):
        allowed, reason = worker_policy.is_tool_allowed_for_worker(name)
        assert not allowed and "review" in reason


# ---------------------------------------------------------------------------
# Refinement round 1 (2026-11-21): one main-thread call, combined counts,
# a first call with no baseline, half-readable history, batches
# ---------------------------------------------------------------------------

def test_a_history_call_before_any_baseline_refuses_what_is_already_there(env):
    handler, undos, mod = env
    undos.undo = ["SYNAPSE: old session build"]
    assert handler._undo_scope.needs_baseline is True

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_undo({})

    assert "before this SYNAPSE session started" in str(caught.value)
    assert undos.calls == []


def test_an_entry_moved_between_the_stacks_is_still_pre_session(env):
    handler, undos, mod = env
    undos.undo = ["SYNAPSE: old session build"]
    _capture_baseline(handler, undos)
    undos.undo, undos.redo = [], ["SYNAPSE: old session build"]  # the artist pressed Ctrl+Z

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_redo({})

    assert "SYNAPSE: old session build" in str(caught.value)
    assert "did not undo" in str(caught.value), "refused because this session never undid it"
    assert undos.calls == []


def test_a_session_step_still_redoes_after_its_undo(env):
    handler, undos, _mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["SYNAPSE: create_node"]

    assert handler._handle_undo({})["status"] == "ok"
    assert handler._handle_redo({})["status"] == "ok"
    assert undos.calls == ["undo", "redo"]


def test_an_unreadable_direction_captures_no_baseline():
    from synapse.server.undo_scope import UndoScope

    class _Half:
        def undoLabels(self):
            return ()

        def redoLabels(self):
            raise RuntimeError("unreadable")

    scope = UndoScope()
    assert scope.note_session_start(_Half()) is False
    assert scope.needs_baseline is True


def test_off_main_handle_captures_the_baseline_through_run_on_main(env, monkeypatch):
    import threading
    import synapse.server.main_thread as main_thread

    handler, undos, _mod = env
    undos.undo = ["SYNAPSE: old session build"]
    hops = []

    def _fake_run_on_main(fn, *args, **kwargs):
        hops.append(kwargs.get("label"))
        return fn()

    monkeypatch.setattr(main_thread, "run_on_main", _fake_run_on_main)
    worker = threading.Thread(target=lambda: handler.handle(
        SynapseCommand(id="b-101", type="create_node", payload={"parent": "/obj", "type": "null"})))
    worker.start()
    worker.join(10)

    assert not worker.is_alive(), "handle() did not finish"
    assert "history:baseline" in hops, hops
    assert handler._undo_scope.needs_baseline is False


def test_the_judge_and_the_step_run_in_one_main_thread_call(env, monkeypatch):
    import synapse.server.main_thread as main_thread

    handler, undos, _mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["SYNAPSE: create_node"]
    hops = []

    def _fake_run_on_main(fn, *args, **kwargs):
        # The artist edits right before the main thread runs the payload: a check
        # made before the hop would miss it, a check inside the hop refuses.
        hops.append(kwargs.get("label"))
        undos.undo.insert(0, "Artist edit")
        return fn()

    monkeypatch.setattr(main_thread, "run_on_main", _fake_run_on_main)
    with pytest.raises(_mod.HistoryScopeRefused) as caught:
        handler._handle_undo({})

    assert hops == ["history:undo"]
    assert "Artist edit" in str(caught.value)
    assert undos.calls == [], "the check must run inside the main-thread call"


def test_a_batch_refuses_history_commands(env):
    handler, undos, _mod = env
    with pytest.raises(ValueError, match="outside a batch"):
        handler._handle_batch_commands({"commands": [{"type": "undo", "payload": {}}]})
    assert undos.calls == []


# ---------------------------------------------------------------------------
# Refinement round 2: repeated labels (every create is the same label)
# ---------------------------------------------------------------------------

def test_an_older_entry_with_the_same_label_stays_refused(env):
    handler, undos, mod = env
    undos.undo = ["synapse_node_create"]                # left by an earlier session
    _capture_baseline(handler, undos)
    undos.undo = ["synapse_node_create", "synapse_node_create"]   # this session's create on top

    assert handler._handle_undo({})["status"] == "ok"   # takes back this session's create
    with pytest.raises(mod.HistoryScopeRefused):        # the earlier session's is next
        handler._handle_undo({})
    assert undos.calls == ["undo"]


def test_the_session_create_redoes_after_its_undo_with_a_repeated_label(env):
    handler, undos, _mod = env
    undos.undo = ["synapse_node_create"]
    _capture_baseline(handler, undos)
    undos.undo = ["synapse_node_create", "synapse_node_create"]

    handler._handle_undo({})
    assert handler._handle_redo({})["status"] == "ok"
    assert undos.calls == ["undo", "redo"]


def test_a_dropped_pre_session_redo_entry_refuses_conservatively(env):
    """Documented limit: a pre-session redo entry with the same label, dropped by
    this session's first action, makes the session's own step look old."""
    handler, undos, mod = env
    undos.redo = ["synapse_node_create"]
    _capture_baseline(handler, undos)
    undos.undo, undos.redo = ["synapse_node_create"], []   # new create dropped the redo entry

    with pytest.raises(mod.HistoryScopeRefused):
        handler._handle_undo({})
    assert undos.calls == []


# ---------------------------------------------------------------------------
# Refinement round 3: artist-started panel groups, redo of what the agent undid
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["SYNAPSE insert saved network", "SYNAPSE Identify cleanup"])
def test_a_panel_action_the_artist_started_is_never_undone_by_an_agent(env, label):
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = [label]                    # created after the baseline, by the artist's click

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_undo({})
    assert label in str(caught.value)
    assert undos.calls == []


def test_redo_refuses_a_step_this_session_did_not_undo(env):
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.redo = ["SYNAPSE: build_graph"]   # rolled back by a failed build, or the artist's Ctrl+Z

    with pytest.raises(mod.HistoryScopeRefused) as caught:
        handler._handle_redo({})
    assert "did not undo" in str(caught.value)
    assert undos.calls == []


def test_a_disabled_history_records_no_baseline(env):
    handler, undos, _mod = env
    undos.enabled = False
    assert handler._undo_scope.note_session_start(undos) is False
    assert handler._undo_scope.needs_baseline is True


# ---------------------------------------------------------------------------
# Refinement round 4: redo is the exact history this handler left; Spatial click
# ---------------------------------------------------------------------------

def _artist_ctrl_z(undos):
    undos.redo.insert(0, undos.undo.pop(0))


def _artist_ctrl_y(undos):
    undos.undo.insert(0, undos.redo.pop(0))


def test_redo_refuses_a_same_label_step_the_artist_undid(env):
    """Round 4 BUG-1: two creates share a label; the artist undid the older one."""
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["synapse_node_create", "synapse_node_create"]   # c2 on top of c1

    assert handler._handle_undo({})["status"] == "ok"          # the agent undoes c2
    _artist_ctrl_z(undos)                                       # the artist undoes c1

    with pytest.raises(mod.HistoryScopeRefused) as caught:      # c1 is next: not the agent's
        handler._handle_redo({})
    assert "did not undo" in str(caught.value)
    assert undos.calls == ["undo"]


def test_redo_still_works_when_the_artist_returns_the_history_to_where_it_was(env):
    handler, undos, _mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["synapse_node_create", "synapse_node_create"]

    handler._handle_undo({})
    _artist_ctrl_z(undos)
    _artist_ctrl_y(undos)                                       # back to exactly what the agent left

    assert handler._handle_redo({})["status"] == "ok"
    assert undos.calls == ["undo", "redo"]


def test_redo_stops_at_the_entries_this_handler_undid(env):
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["synapse_node_create", "synapse_node_create"]
    _artist_ctrl_z(undos)                                       # the artist undoes c2 first

    handler._handle_undo({})                                    # the agent undoes c1
    assert handler._handle_redo({})["status"] == "ok"           # c1 comes back
    with pytest.raises(mod.HistoryScopeRefused):                # c2 was the artist's undo
        handler._handle_redo({})
    assert undos.calls == ["undo", "redo"]


def test_redo_refuses_a_failed_builds_rollback_after_an_agent_undo(env):
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["synapse_node_create"]
    handler._handle_undo({})
    # A later build opens a group, which drops the redo stack, fails and is rolled back.
    undos.undo, undos.redo = [], ["SYNAPSE: build_graph"]

    with pytest.raises(mod.HistoryScopeRefused):
        handler._handle_redo({})
    assert undos.calls == ["undo"]


def test_the_panel_spatial_click_is_the_artists(env):
    """Round 4 BUG-2: the footer click writes the agent-prefixed trail label."""
    handler, undos, mod = env
    _capture_baseline(handler, _Undos())
    undos.undo = ["SYNAPSE: Draw camera path"]

    with pytest.raises(mod.HistoryScopeRefused):
        handler._handle_undo({})
    assert undos.calls == []


def test_the_refused_trail_label_is_the_one_the_tool_writes():
    from synapse.server.handlers_spatial import TRAIL_UNDO
    from synapse.server.undo_scope import ARTIST_STARTED_LABELS

    assert TRAIL_UNDO in ARTIST_STARTED_LABELS


def test_redo_of_a_pre_session_entry_is_refused_even_with_a_redo_run():
    """Defense in depth (round 4 TEST-3): the undo-stack count still guards redo."""
    from synapse.server.undo_scope import UndoScope, history

    undos = _Undos(undo=["synapse_node_create"])
    scope = UndoScope()
    assert scope.note_session_start(undos)
    undos.undo, undos.redo = [], ["synapse_node_create"]       # the old entry, now on redo
    scope._left_history, scope._redoable = history(undos), 1   # as if the run were ours

    refusal = scope.refusal(undos, "redo")
    assert refusal and "before this SYNAPSE session started" in refusal
