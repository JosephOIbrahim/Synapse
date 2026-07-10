"""Live-path IntegrityBlock envelope — PATH-QUALIFIED provenance, observe-only.

The live /synapse WS path historically produced NO IntegrityBlocks: handler
mutations were invisible to LosslessExecutionBridge._operation_log and the §16
observability loop. The envelope (python/synapse/server/integrity_envelope.py)
closes that gap WITHOUT wrapping execution, gating (D1 posture, pinned by
tests/test_phase0b_consent_posture.py), or Flattening a stage.

Pinned guarantees:

  1. IntegrityBlock path-qualified fields DEFAULT to exact pre-existing /mcp
     semantics — every existing construction site unchanged; to_dict additive.
  2. anchors_hold: a *_applicable=False anchor is N/A (never faked True);
     a live block with honest False consent/composition/undo reads
     fidelity=1.0 (live is not degraded for being live — CLAUDE.md §1.3).
  3. record_external_block: thread-safe append + lifetime counters into the
     shared trail; §16 operation_stats keys unchanged (additive per_agent key).
  4. get_process_bridge: ONE instance per process, constructed gate-less with
     auto-approve consent regardless of first creator (the panel-freeze
     ordering landmine); panel get_bridge() re-points to _panel_consent.
  5. The envelope NEVER hits stage.Flatten(): include_stage=False skips the S2
     stage block structurally (the Finding 3 floor).
  6. handle() seam: mutating command -> hashes captured + one live block lands
     in the process trail; read-only / skip-set / bridge-routed -> none.
  7. run_on_main record_stall=False + record_wait=False: envelope capture
     timeouts never feed the stall detector (2-strike fast-fail poisoning),
     and envelope wakes never feed the C6 dispatch-wait histogram — the
     still-owed T1 attribution instrument stays a measure of real ops only.
  8. Live hot-path cost is bounded and sheddable: SYNAPSE_LIVE_ENVELOPE=0
     kill switch (call-time, no re-import) -> zero envelope blocks; capture
     timeout is FIXED and short (1.0s default, SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT
     override — never derived from dispatch-wait stats); an active main-thread
     stall skips captures outright (no doomed wake queued); a before-capture
     miss skips the after-capture (at most ONE capture-timeout of C5-lock hold
     per op); pure off-main-thread writes (add_memory/decide/write_report) are
     never enveloped — no new main-thread coupling.

Standalone (no real hou): conftest's canonical fake is resident; the bridge
falls back to timestamp hashing (no hdefereval => _HOU_AVAILABLE False).
"""

import threading
import time
import types

import pytest

import shared.bridge as b
from shared.constants import HASH_LENGTH
from synapse.server import integrity_envelope as env
from synapse.server import main_thread as mt
from synapse.server import handlers as handlers_mod
from synapse.server.handlers import SynapseHandler
from synapse.core.protocol import SynapseCommand
from synapse.panel import bridge_adapter as ba


@pytest.fixture(autouse=True)
def _fresh_process_bridge():
    """Isolate the process-wide singleton (and the panel alias) per test."""
    b.reset_process_bridge()
    ba._bridge = None
    yield
    b.reset_process_bridge()
    ba._bridge = None


def _live_block(**overrides):
    """A canonical honest live block (what record_live_block assembles)."""
    kwargs = dict(
        undo_group_active=False,
        main_thread_executed=True,
        consent_verified=False,
        composition_valid=False,
        agent_id=env.LIVE_AGENT_KEY,
        operation_type="create_node",
        scene_hash_before="aaaa",
        scene_hash_after="bbbb",
        delta_hash="deadbeef",
        execution_path="live",
        consent_applicable=False,
        composition_applicable=False,
        undo_applicable=False,
        hash_target="/obj/geo1",
    )
    kwargs.update(overrides)
    return b.IntegrityBlock(**kwargs)


# ── 1. Path-qualified fields: defaults preserve /mcp semantics ──

class TestIntegrityBlockPathQualified:
    def test_defaults_are_mcp(self):
        block = b.IntegrityBlock()
        assert block.execution_path == "mcp"
        assert block.consent_applicable is True
        assert block.composition_applicable is True
        assert block.undo_applicable is True
        assert block.hash_target == ""

    def test_default_anchors_reduce_to_old_conjunction(self):
        # all four True -> holds (the pre-change behavior)
        block = b.IntegrityBlock(
            undo_group_active=True, main_thread_executed=True,
            consent_verified=True, composition_valid=True,
        )
        assert block.anchors_hold is True
        # flipping ANY of the four with defaults -> does not hold
        for field_name in ("undo_group_active", "main_thread_executed",
                           "consent_verified", "composition_valid"):
            kwargs = dict(
                undo_group_active=True, main_thread_executed=True,
                consent_verified=True, composition_valid=True,
            )
            kwargs[field_name] = False
            assert b.IntegrityBlock(**kwargs).anchors_hold is False, field_name

    def test_mcp_fidelity_unchanged(self):
        # consent False + applicable True (default) is still a hard failure
        block = b.IntegrityBlock(
            undo_group_active=True, main_thread_executed=True,
            consent_verified=False, composition_valid=True,
            delta_hash="x",
        )
        assert block.fidelity == 0.0

    def test_applicable_flags_gate_the_anchor_set(self):
        block = _live_block()
        assert block.anchors_hold is True
        assert block.fidelity == 1.0
        # ...but a not-applicable anchor never excuses main-thread failure
        assert _live_block(main_thread_executed=False).anchors_hold is False

    def test_applicable_false_never_fakes_true(self):
        block = _live_block()
        # honesty: the RAW anchor values stay False in the record
        assert block.consent_verified is False
        assert block.composition_valid is False
        assert block.undo_group_active is False

    def test_to_dict_additive_keys(self):
        d = _live_block().to_dict()
        # legacy keys untouched
        for key in ("anchors_hold", "fidelity", "undo", "thread", "consent",
                    "composition", "agent", "operation", "timestamp",
                    "scene_hash_before", "scene_hash_after", "delta_hash",
                    "external_change_detected"):
            assert key in d, key
        # additive path-qualified keys
        assert d["execution_path"] == "live"
        assert d["consent_applicable"] is False
        assert d["composition_applicable"] is False
        assert d["undo_applicable"] is False
        assert d["hash_target"] == "/obj/geo1"


# ── 3. record_external_block + §16 read surface ────────────────

class TestRecordExternalBlock:
    def test_appends_and_counts_verified(self):
        bridge = b.LosslessExecutionBridge()
        bridge.record_external_block(_live_block())
        stats = bridge.operation_stats()
        assert stats["operations_total"] == 1
        assert stats["operations_verified"] == 1
        assert stats["anchor_violations"] == 0
        assert stats["per_agent"] == {env.LIVE_AGENT_KEY: 1}
        assert stats["per_agent_success_rate"][env.LIVE_AGENT_KEY] == 1.0
        assert stats["per_operation_type"] == {"create_node": 1}
        recent = bridge.recent_operations(10)
        assert len(recent) == 1
        assert recent[0].execution_path == "live"

    def test_degraded_block_counts_violation(self):
        bridge = b.LosslessExecutionBridge()
        bridge.record_external_block(_live_block(main_thread_executed=False))
        stats = bridge.operation_stats()
        assert stats["operations_total"] == 1
        assert stats["operations_verified"] == 0
        assert stats["anchor_violations"] == 1

    def test_operation_stats_keys_unchanged(self):
        # §16.2 pinned read surface — additive only.
        bridge = b.LosslessExecutionBridge()
        bridge.record_external_block(_live_block())
        assert set(bridge.operation_stats()) == {
            "operations_total", "operations_verified", "anchor_violations",
            "success_rate", "log_size", "log_capacity", "per_agent",
            "per_agent_verified", "per_agent_success_rate",
            "per_operation_type", "session_id",
        }

    def test_thread_safe_under_concurrent_appends_and_reads(self):
        bridge = b.LosslessExecutionBridge()
        n_threads, n_each = 8, 50
        errors = []

        def _append():
            try:
                for _ in range(n_each):
                    bridge.record_external_block(_live_block())
            except Exception as e:  # pragma: no cover - failure path
                errors.append(e)

        def _read():
            try:
                for _ in range(200):
                    bridge.operation_stats()
                    bridge.recent_operations(50)
                    bridge.reconstruct_operation_history()
            except Exception as e:  # pragma: no cover - failure path
                errors.append(e)

        threads = ([threading.Thread(target=_append) for _ in range(n_threads)]
                   + [threading.Thread(target=_read) for _ in range(2)])
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors
        stats = bridge.operation_stats()
        assert stats["operations_total"] == n_threads * n_each
        assert stats["operations_verified"] == n_threads * n_each


# ── 4. Process-wide singleton + panel posture ───────────────────

class TestProcessBridge:
    def test_singleton_and_panel_posture_by_construction(self):
        b1 = b.get_process_bridge()
        b2 = b.get_process_bridge()
        assert b1 is b2
        # panel posture regardless of creator: gate OFF, auto-approve callback
        assert b1._gate is None
        assert b1._consent_callback is not None
        assert b1._consent_callback(object()) is True

    def test_reset_drops_instance(self):
        b1 = b.get_process_bridge()
        b.reset_process_bridge()
        assert b.get_process_bridge() is not b1

    def test_panel_get_bridge_returns_process_instance(self):
        pb = b.get_process_bridge()
        bridge = ba.get_bridge()
        assert bridge is pb
        assert bridge._consent_callback is ba._panel_consent
        assert bridge._gate is None

    def test_order_independence_panel_first(self):
        bridge = ba.get_bridge()
        assert b.get_process_bridge() is bridge
        assert bridge._gate is None


# ── 5. include_stage=False never touches the stage (Finding 3) ──

class TestIncludeStage:
    def _stage_node(self):
        calls = {"stage": 0}

        class _Node:
            def children(self):
                return []

            def cookCount(self):
                return 1

            def geometry(self):
                return None

            def stage(self):
                calls["stage"] += 1
                return None

        return _Node(), calls

    def test_live_path_skips_stage_block(self, monkeypatch):
        node, calls = self._stage_node()
        monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
        monkeypatch.setattr(b, "hou", types.SimpleNamespace(node=lambda p: node))
        bridge = b.LosslessExecutionBridge()
        bridge._compute_scene_hash("/stage/x", include_stage=False)
        assert calls["stage"] == 0, "live envelope hash must NEVER touch node.stage()"
        bridge._compute_scene_hash("/stage/x")  # default: stage block runs
        assert calls["stage"] == 1

    def test_single_arg_impl_stub_still_works(self, monkeypatch):
        # tests/test_scene_hash_gate.py monkeypatches the impl with a single-
        # positional-arg lambda; the default path must not forward the kwarg.
        bridge = b.LosslessExecutionBridge()
        monkeypatch.setattr(bridge, "_compute_scene_hash_impl",
                            lambda tp: f"SENTINEL::{tp}")
        assert bridge._compute_scene_hash("/p") == "SENTINEL::/p"

    def test_standalone_fallback_hash_with_include_stage_false(self, monkeypatch):
        # Pin the fallback path explicitly instead of assuming residency (the
        # repo's #1 test trap): an alphabetically-earlier module planting an
        # hdefereval stub flips shared.bridge._HOU_AVAILABLE True at first
        # import, and the canonical conftest fake's hou.node returns None ->
        # 'invalid_context' (15 chars), not the 16-hex timestamp hash this
        # test pins. Same idiom as test_live_path_skips_stage_block above.
        monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
        bridge = b.LosslessExecutionBridge()
        h = bridge._compute_scene_hash("/obj", include_stage=False)
        assert isinstance(h, str) and len(h) == HASH_LENGTH


# ── 6. Envelope module: targets, skip-set, suppression, assembly ─

class TestEnvelopeModule:
    def test_hash_target_extraction(self):
        assert env._hash_target({"node": "/obj/geo1"}) == "/obj/geo1"
        assert env._hash_target({"parent": "/stage"}) == "/stage"
        assert env._hash_target({"node": "relative/path"}) == "/obj"
        assert env._hash_target({}) == "/obj"
        assert env._hash_target(None) == "/obj"

    def test_skip_set_covers_misclassified_read_only(self):
        # Genuinely read-only / non-scene commands NOT in _READ_ONLY_COMMANDS:
        # they must never produce a false "LIVE mutation" block.
        for cmd in ("doctor", "hda_list", "memory_query", "memory_status",
                    "query_prims", "render_farm_status", "tops_monitor_stream",
                    "write_report"):
            assert cmd in env.ENVELOPE_SKIP_COMMANDS, cmd
            assert env.envelope_active(cmd) is False, cmd

    def test_skip_set_covers_off_main_thread_writes(self):
        # PURE off-main-thread writes (zero run_on_main in their handlers —
        # tracker.handle_memory_add / handle_memory_decide / write_report):
        # enveloping them would ADD a main-thread coupling they deliberately
        # avoid, then land a false "LIVE mutation" block for '/obj'.
        for cmd in ("add_memory", "decide", "write_report"):
            assert cmd in env.ENVELOPE_SKIP_COMMANDS, cmd
            assert env.envelope_active(cmd) is False, cmd

    def test_envelope_active_for_mutating_command(self):
        assert env.envelope_active("create_node") is True

    def test_env_kill_switch(self, monkeypatch):
        # SYNAPSE_LIVE_ENVELOPE=0 sheds the two capture hops per mutating op
        # without a code change (the C6/T1 latency-tax escape hatch). Read at
        # call time — the toggle takes effect without re-import.
        assert env.envelope_active("create_node") is True
        for off in ("0", "false", "OFF"):
            monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", off)
            assert env.envelope_active("create_node") is False, off
        monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "1")
        assert env.envelope_active("create_node") is True

    def test_bridge_routed_suppression_restores(self):
        assert env.envelope_active("create_node") is True
        with env.bridge_routed():
            assert env.envelope_active("create_node") is False
            with env.bridge_routed():  # nested
                assert env.envelope_active("create_node") is False
            assert env.envelope_active("create_node") is False
        assert env.envelope_active("create_node") is True

    def test_record_live_block_honest_assembly(self):
        env.record_live_block("create_node", {"node": "/obj/x"}, "aaaa", "bbbb")
        block = b.get_process_bridge().recent_operations(1)[0]
        assert block.execution_path == "live"
        assert block.agent_id == env.LIVE_AGENT_KEY
        assert block.operation_type == "create_node"
        assert block.hash_target == "/obj/x"
        assert block.scene_hash_before == "aaaa"
        assert block.scene_hash_after == "bbbb"
        assert len(block.delta_hash) == HASH_LENGTH
        # honest anchors: nothing faked True, fidelity NOT degraded for
        # being live (constraint 4)
        assert block.undo_group_active is False
        assert block.consent_verified is False
        assert block.composition_valid is False
        assert block.main_thread_executed is True
        assert block.fidelity == 1.0

    def test_record_live_block_no_change(self):
        env.record_live_block("set_parm", {"node": "/obj/x"}, "same", "same")
        block = b.get_process_bridge().recent_operations(1)[0]
        assert block.delta_hash == "no_change"
        assert block.fidelity == 1.0

    def test_record_live_block_hash_unavailable(self):
        # A capture miss (busy main thread) is honest, not a pipeline bug.
        env.record_live_block("set_parm", {"node": "/obj/x"}, None, "bbbb")
        block = b.get_process_bridge().recent_operations(1)[0]
        assert block.delta_hash == "hash_unavailable"
        assert block.scene_hash_before == ""
        assert block.fidelity == 1.0

    def test_capture_timeout_fixed_default_and_env_override(self, monkeypatch):
        # The timeout is FIXED and short — never derived from dispatch-wait
        # stats (an earlier draft derived max*1.5 clamped [2,8]s: on a busy
        # main thread the two capture hops could hold the C5 lock 8-16s/op).
        monkeypatch.delenv("SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT", raising=False)
        assert env._CAPTURE_TIMEOUT_DEFAULT_S == 1.0
        assert env._capture_timeout() == 1.0
        monkeypatch.setenv("SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT", "2.5")
        assert env._capture_timeout() == 2.5
        # a bad value never silently changes the default (repo env idiom)
        for bad in ("garbage", "0", "-3"):
            monkeypatch.setenv("SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT", bad)
            assert env._capture_timeout() == env._CAPTURE_TIMEOUT_DEFAULT_S, bad

    def test_capture_passes_observe_only_flags(self, monkeypatch):
        # The capture must opt out of BOTH instruments: record_stall=False
        # (stall detector, guarantee 7) and record_wait=False (C6 dispatch-
        # wait histogram — the still-owed T1 attribution instrument must
        # measure real command waits only). Resolve the CURRENT resident
        # module the same way the envelope does (call-time import):
        # tests/test_main_thread.py re-plants
        # sys.modules["synapse.server.main_thread"] with a fresh twin at
        # collection time, so the module-level `mt` alias would hit a STALE
        # twin in full-suite runs (the fake-residency trap).
        import importlib
        mt_live = importlib.import_module("synapse.server.main_thread")
        seen = {}

        def _fake_run(fn, timeout=None, record_stall=True, record_wait=True):
            seen.update(timeout=timeout, record_stall=record_stall,
                        record_wait=record_wait)
            return "hash"

        monkeypatch.setattr(mt_live, "run_on_main", _fake_run)
        monkeypatch.setattr(mt_live, "is_main_thread_stalled", lambda: False)
        monkeypatch.delenv("SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT", raising=False)
        assert env.capture_scene_hash({"node": "/obj/x"}) == "hash"
        assert seen["record_stall"] is False
        assert seen["record_wait"] is False
        # fixed short timeout — the C5-lock hold bound per hop
        assert seen["timeout"] == env._CAPTURE_TIMEOUT_DEFAULT_S

    def test_capture_skipped_while_main_thread_stalled(self, monkeypatch):
        # Stall guard (guarantee 8): the detector already knows the main
        # thread is wedged — the capture must return honest None WITHOUT
        # queuing another doomed wake (no run_on_main call at all).
        import importlib
        mt_live = importlib.import_module("synapse.server.main_thread")
        calls = []
        monkeypatch.setattr(mt_live, "is_main_thread_stalled", lambda: True)
        monkeypatch.setattr(
            mt_live, "run_on_main",
            lambda *a, **k: calls.append(1) or "hash")
        assert env.capture_scene_hash({"node": "/obj/x"}) is None
        assert calls == [], "no wake may be queued while stalled"


# ── 7. handle() seam ─────────────────────────────────────────────

class TestHandleSeam:
    @pytest.fixture
    def handler(self):
        h = SynapseHandler()
        h._registry.register("fake_mutate", lambda payload: {"ok": True})
        return h

    def _wait_for_total(self, expected, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            stats = b.get_process_bridge().operation_stats()
            if stats["operations_total"] >= expected:
                return stats
            time.sleep(0.02)
        return b.get_process_bridge().operation_stats()

    def test_mutating_command_lands_live_block(self, handler):
        resp = handler.handle(SynapseCommand(
            type="fake_mutate", id="t1", payload={"node": "/obj/x"},
        ))
        assert resp.success
        stats = self._wait_for_total(1)
        assert stats["operations_total"] == 1
        assert stats["per_agent"] == {env.LIVE_AGENT_KEY: 1}
        block = b.get_process_bridge().recent_operations(1)[0]
        assert block.operation_type == "fake_mutate"
        assert block.execution_path == "live"
        assert block.hash_target == "/obj/x"
        # both captures succeeded on the direct main-thread path
        assert block.scene_hash_before and block.scene_hash_after
        assert block.delta_hash != "hash_unavailable"
        assert block.fidelity == 1.0

    def test_read_only_command_not_enveloped(self, handler):
        resp = handler.handle(SynapseCommand(type="ping", id="t2", payload={}))
        assert resp.success
        # read-only never submits logs at all — nothing lands, ever
        assert b.get_process_bridge().operation_stats()["operations_total"] == 0

    def test_kill_switch_off_lands_zero_blocks(self, handler, monkeypatch):
        # SYNAPSE_LIVE_ENVELOPE=0 end-to-end: a mutating handle() still
        # audits/logs, but zero envelope blocks land in the process trail.
        monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
        resp = handler.handle(SynapseCommand(
            type="fake_mutate", id="t7", payload={"node": "/obj/x"},
        ))
        assert resp.success
        # drain the log executor (both workers) before asserting the count
        futs = [handlers_mod._log_executor.submit(lambda: None)
                for _ in range(2)]
        for f in futs:
            f.result(timeout=5)
        time.sleep(0.05)
        assert b.get_process_bridge().operation_stats()["operations_total"] == 0

    def test_bridge_routed_handle_submits_unenveloped(self, handler, monkeypatch):
        seen = {}

        def _fake_submit(cmd_type, payload, result, hash_before=None,
                         hash_after=None, enveloped=False):
            seen.update(cmd=cmd_type, hb=hash_before, ha=hash_after,
                        env=enveloped)

        monkeypatch.setattr(handler, "_submit_logs", _fake_submit)
        with env.bridge_routed():
            resp = handler.handle(SynapseCommand(
                type="fake_mutate", id="t3", payload={"node": "/obj/x"},
            ))
        assert resp.success
        assert seen["cmd"] == "fake_mutate"
        assert seen["env"] is False, "nested bridge dispatch must be suppressed"
        assert seen["hb"] is None and seen["ha"] is None

    def test_mutating_handle_passes_hashes_to_submit(self, handler, monkeypatch):
        seen = {}

        def _fake_submit(cmd_type, payload, result, hash_before=None,
                         hash_after=None, enveloped=False):
            seen.update(hb=hash_before, ha=hash_after, env=enveloped)

        monkeypatch.setattr(handler, "_submit_logs", _fake_submit)
        handler.handle(SynapseCommand(
            type="fake_mutate", id="t4", payload={"node": "/obj/x"},
        ))
        assert seen["env"] is True
        assert seen["hb"] and seen["ha"]

    def test_before_capture_miss_skips_after_capture(self, handler, monkeypatch):
        # A before-miss already forces the hash_unavailable sentinel (no
        # delta is computable) — the after-capture must be SKIPPED so a
        # stuck main thread costs at most ONE capture-timeout of C5-lock
        # hold per op, not two.
        calls = []
        monkeypatch.setattr(env, "capture_scene_hash",
                            lambda payload: calls.append(1) and None)
        seen = {}

        def _fake_submit(cmd_type, payload, result, hash_before=None,
                         hash_after=None, enveloped=False):
            seen.update(hb=hash_before, ha=hash_after, env=enveloped)

        monkeypatch.setattr(handler, "_submit_logs", _fake_submit)
        resp = handler.handle(SynapseCommand(
            type="fake_mutate", id="t6", payload={"node": "/obj/x"},
        ))
        assert resp.success
        assert len(calls) == 1, "after-capture must be skipped on a before-miss"
        assert seen["env"] is True
        assert seen["hb"] is None and seen["ha"] is None

    def test_execute_through_bridge_records_exactly_one_mcp_block(self, handler):
        # Panel / in-process-MCP path: the bridge's _finalize records the op;
        # the nested handle() must be TLS-suppressed or the shared trail
        # double-counts (one mcp + one live block).
        command = SynapseCommand(type="fake_mutate", id="t5",
                                 payload={"node": "/obj/x"})
        resp = ba.execute_through_bridge("houdini_create_node", handler, command)
        assert resp.success
        # drain the log executor (both workers) before asserting the count
        futs = [handlers_mod._log_executor.submit(lambda: None)
                for _ in range(2)]
        for f in futs:
            f.result(timeout=5)
        time.sleep(0.05)
        stats = b.get_process_bridge().operation_stats()
        assert stats["operations_total"] == 1, (
            "panel//mcp op double-recorded in the shared process trail"
        )
        block = b.get_process_bridge().recent_operations(1)[0]
        assert block.execution_path == "mcp"


# ── 8. run_on_main stall-detector opt-out ────────────────────────

class TestRecordStallOptOut:
    def _timeout_from_worker(self, monkeypatch, record_stall):
        """Force the worker-path timeout: fake hdefereval drops the callback."""
        fake = types.ModuleType("hdefereval")
        fake.executeDeferred = lambda fn: None  # main thread never runs it
        monkeypatch.setitem(__import__("sys").modules, "hdefereval", fake)

        raised = []

        def _run():
            try:
                mt.run_on_main(lambda: True, timeout=0.05,
                               record_stall=record_stall)
            except RuntimeError as e:
                raised.append(e)

        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=5)
        return raised

    def test_record_stall_false_never_feeds_detector(self, monkeypatch):
        mt._record_success()  # clean slate
        try:
            raised = self._timeout_from_worker(monkeypatch, record_stall=False)
            assert raised, "the timeout must still raise RuntimeError"
            assert mt.stall_state()["consecutive_timeouts"] == 0
            assert mt.is_main_thread_stalled() is False
        finally:
            mt._record_success()

    def test_record_stall_default_still_counts(self, monkeypatch):
        mt._record_success()
        try:
            raised = self._timeout_from_worker(monkeypatch, record_stall=True)
            assert raised
            assert mt.stall_state()["consecutive_timeouts"] == 1
        finally:
            mt._record_success()


# ── 9. run_on_main dispatch-wait histogram opt-out ───────────────

class TestRecordWaitOptOut:
    def _run_from_worker(self, monkeypatch, record_wait):
        """Force the worker path with a fake hdefereval that runs the wake
        inline — the histogram decision inside _on_main actually executes."""
        fake = types.ModuleType("hdefereval")
        fake.executeDeferred = lambda fn: fn()
        monkeypatch.setitem(__import__("sys").modules, "hdefereval", fake)

        out = []

        def _run():
            out.append(mt.run_on_main(lambda: 42, timeout=1.0,
                                      record_wait=record_wait))

        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=5)
        return out

    def test_record_wait_false_never_feeds_histogram(self, monkeypatch):
        # The envelope's capture flag: its wakes must never land in the C6
        # dispatch-wait stats (the still-owed C6/T1 attribution instrument).
        mt.reset_dispatch_wait_stats()
        try:
            out = self._run_from_worker(monkeypatch, record_wait=False)
            assert out == [42]
            assert mt.dispatch_wait_stats()["count"] == 0
        finally:
            mt.reset_dispatch_wait_stats()

    def test_record_wait_default_still_records(self, monkeypatch):
        # Every OTHER caller keeps feeding C6 — the instrument stays live.
        mt.reset_dispatch_wait_stats()
        try:
            out = self._run_from_worker(monkeypatch, record_wait=True)
            assert out == [42]
            assert mt.dispatch_wait_stats()["count"] == 1
        finally:
            mt.reset_dispatch_wait_stats()
