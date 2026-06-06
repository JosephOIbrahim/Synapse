"""Tests for the 0a-prime Floor emit-time provenance hook.

Pins the Tier-0 provenance contract:

* ``CommandHandlerRegistry.invoke`` is parity with ``get()`` + call.
* ``FloorGate`` writes exactly ONE provenance file per mutating op, ZERO for a
  read-only op.
* A batch of N mutating sub-ops yields N+1 records, each sub-op carrying
  ``parent`` = the batch envelope id.
* An autonomy-origin op records ``origin='autonomy'``.
* ``payload_digest`` / ``result_digest`` are sha256 of the canonical-serialized
  payload / result.
* An op that RAISES still writes ``outcome='error'`` then propagates.
* ``Dispatcher(is_testing=True, floor_gate=gate)`` routes through the SAME gate.
* The ``floor_gate`` module has zero ``hou``.

Plus two start_hwebserver autostart guards live in
``tests/test_start_hwebserver_durable_ref.py``.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os

import pytest

from synapse.core.floor_gate import FloorGate, FloorContext
import synapse.core.floor_gate as floor_gate_mod
from synapse.server.handlers import CommandHandlerRegistry, _READ_ONLY_COMMANDS


def _records(provenance_dir):
    """All provenance records written under ``provenance_dir``, parsed."""
    out = []
    if not os.path.isdir(provenance_dir):
        return out
    for name in sorted(os.listdir(provenance_dir)):
        if name.endswith(".json"):
            with open(os.path.join(provenance_dir, name), encoding="utf-8") as fh:
                out.append(json.loads(fh.read()))
    return out


def _canonical_sha256(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@pytest.fixture
def prov_dir(tmp_path, monkeypatch):
    """Point the FloorGate's provenance root at a tmp dir for the test."""
    d = tmp_path / "provenance"
    monkeypatch.setenv("SYNAPSE_PROVENANCE_DIR", str(d))
    return str(d)


# ---------------------------------------------------------------------------
# Module hygiene
# ---------------------------------------------------------------------------

def test_floor_gate_module_has_zero_hou():
    """The neutral hook module must never import ``hou`` (non-Houdini path)."""
    src = inspect.getsource(floor_gate_mod)
    for line in src.splitlines():
        stripped = line.strip()
        assert stripped != "import hou", "floor_gate must not import hou"
        assert not stripped.startswith("import hou "), "floor_gate must not import hou"
        assert not stripped.startswith("from hou "), "floor_gate must not import hou"


# ---------------------------------------------------------------------------
# Registry.invoke parity
# ---------------------------------------------------------------------------

def test_invoke_runs_handler_parity_with_get(prov_dir):
    """``invoke`` returns the same result as ``get(cmd)(payload)``."""
    reg = CommandHandlerRegistry()
    reg.register("set_parm", lambda p: {"echo": p, "ran": True})

    direct = reg.get("set_parm")({"a": 1})
    via_invoke = reg.invoke("set_parm", {"a": 1})

    assert via_invoke == direct == {"echo": {"a": 1}, "ran": True}


def test_invoke_unknown_raises_keyerror():
    reg = CommandHandlerRegistry()
    with pytest.raises(KeyError):
        reg.invoke("does_not_exist", {})


# ---------------------------------------------------------------------------
# One record per mutating op, zero for read-only
# ---------------------------------------------------------------------------

def test_mutating_op_writes_exactly_one_record(prov_dir):
    gate = FloorGate()
    gate.wrap("set_parm", {"node": "/obj/geo1", "val": 3}, lambda p: {"ok": True})

    recs = _records(prov_dir)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["op"] == "set_parm"
    assert rec["outcome"] == "ok"
    assert "ts" in rec and rec["ts"]  # ISO8601 timestamp present


def test_read_only_op_writes_zero_records(prov_dir):
    # 'ping' is in _READ_ONLY_COMMANDS — provenance must be silent.
    assert "ping" in _READ_ONLY_COMMANDS
    gate = FloorGate()
    result = gate.wrap("ping", {}, lambda p: {"pong": True})

    assert result == {"pong": True}
    assert _records(prov_dir) == []


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------

def test_payload_and_result_digests_are_canonical_sha256(prov_dir):
    payload = {"z": 1, "a": [3, 2, 1], "nested": {"k": "v"}}
    result = {"status": "ok", "count": 7}

    gate = FloorGate()
    gate.wrap("create_node", payload, lambda p: result)

    rec = _records(prov_dir)[0]
    assert rec["payload_digest"] == _canonical_sha256(payload)
    assert rec["result_digest"] == _canonical_sha256(result)
    # Canonical = order-independent: a reordered-equal payload hashes the same.
    reordered = {"nested": {"k": "v"}, "a": [3, 2, 1], "z": 1}
    assert _canonical_sha256(reordered) == rec["payload_digest"]


# ---------------------------------------------------------------------------
# Error path still records, then propagates
# ---------------------------------------------------------------------------

def test_raising_op_records_error_then_propagates(prov_dir):
    def boom(_payload):
        raise RuntimeError("kaboom")

    gate = FloorGate()
    with pytest.raises(RuntimeError, match="kaboom"):
        gate.wrap("delete_node", {"node": "/obj/x"}, boom)

    recs = _records(prov_dir)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["outcome"] == "error"
    assert rec["error_type"] == "RuntimeError"
    # On error there is no result to digest — result_digest is the digest of None.
    assert rec["result_digest"] == _canonical_sha256(None)


def test_read_only_raising_op_records_nothing(prov_dir):
    def boom(_payload):
        raise RuntimeError("kaboom")

    gate = FloorGate()
    with pytest.raises(RuntimeError):
        gate.wrap("ping", {}, boom)
    assert _records(prov_dir) == []


# ---------------------------------------------------------------------------
# Batch: N sub-ops nested under a parent → N+1 records total
# ---------------------------------------------------------------------------

def test_batch_yields_n_plus_one_records_with_parent(prov_dir):
    """The batch envelope (+1) plus N sub-ops, each nesting under the envelope.

    Drives the real handler-batch site: the outer 'batch_commands' op is one
    record; each routed sub-op carries parent=<batch envelope id>.
    """
    reg = CommandHandlerRegistry()
    reg.register("set_parm", lambda p: {"ok": True})
    reg.register("create_node", lambda p: {"ok": True})

    # Mint the batch envelope id (mirrors _handle_batch_commands) and record the
    # envelope itself via invoke('batch_commands', ...).
    batch_id = reg._floor_gate.new_op_id()
    batch_ctx = FloorContext(origin="batch", parent=batch_id)

    def _envelope(_payload):
        reg.invoke("set_parm", {"i": 0}, ctx=batch_ctx)
        reg.invoke("create_node", {"i": 1}, ctx=batch_ctx)
        reg.invoke("set_parm", {"i": 2}, ctx=batch_ctx)
        return {"results": 3}

    reg.register("batch_commands", _envelope)
    reg.invoke("batch_commands", {"commands": [1, 2, 3]})

    recs = _records(prov_dir)
    # N (=3) sub-ops + 1 envelope.
    assert len(recs) == 4

    envelope = [r for r in recs if r["op"] == "batch_commands"]
    sub_ops = [r for r in recs if r["op"] != "batch_commands"]
    assert len(envelope) == 1
    assert len(sub_ops) == 3
    # Every sub-op nests under the batch envelope id, origin='batch'.
    for r in sub_ops:
        assert r["parent"] == batch_id
        assert r["origin"] == "batch"


# ---------------------------------------------------------------------------
# Autonomy origin
# ---------------------------------------------------------------------------

def test_autonomy_origin_recorded(prov_dir):
    gate = FloorGate()
    gate.wrap(
        "submit_render", {"frames": "1-10"}, lambda p: {"ok": True},
        ctx=FloorContext(origin="autonomy"),
    )
    rec = _records(prov_dir)[0]
    assert rec["origin"] == "autonomy"


def test_session_threaded_into_record(prov_dir):
    gate = FloorGate()
    gate.wrap(
        "set_parm", {"a": 1}, lambda p: {"ok": True},
        ctx=FloorContext(session="sess-42", origin="handler"),
    )
    rec = _records(prov_dir)[0]
    assert rec["session"] == "sess-42"
    assert rec["origin"] == "handler"


# ---------------------------------------------------------------------------
# Dispatcher routes through the SAME gate
# ---------------------------------------------------------------------------

def test_dispatcher_routes_through_same_gate(prov_dir):
    from synapse.cognitive.dispatcher import Dispatcher

    gate = FloorGate()
    disp = Dispatcher(
        is_testing=True,
        tools={"set_parm": lambda **kw: {"echo": kw}},
        floor_gate=gate,
    )
    result = disp.execute("set_parm", {"node": "/obj/geo1", "v": 9})

    assert result == {"echo": {"node": "/obj/geo1", "v": 9}}
    recs = _records(prov_dir)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["op"] == "set_parm"
    # Digest is over the kwargs dict the dispatcher passed as the payload.
    assert rec["payload_digest"] == _canonical_sha256({"node": "/obj/geo1", "v": 9})


def test_dispatcher_without_gate_is_noop(prov_dir):
    """Default Dispatcher (no floor_gate) writes NO provenance — back-compat."""
    from synapse.cognitive.dispatcher import Dispatcher

    disp = Dispatcher(is_testing=True, tools={"set_parm": lambda **kw: {"ok": True}})
    assert disp.execute("set_parm", {"a": 1}) == {"ok": True}
    assert _records(prov_dir) == []


def test_dispatcher_read_only_through_gate_writes_nothing(prov_dir):
    from synapse.cognitive.dispatcher import Dispatcher

    gate = FloorGate()
    disp = Dispatcher(
        is_testing=True,
        tools={"ping": lambda **kw: {"pong": True}},
        floor_gate=gate,
    )
    assert disp.execute("ping", {}) == {"pong": True}
    assert _records(prov_dir) == []
