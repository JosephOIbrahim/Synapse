"""Scene-model Mile 0 — READ-class observation ledger.

Pins:
  1. Ledger units: append shape (session_id + session_scope), args-hash
     canonicalization determinism, FIFO rotation with trim hysteresis +
     cap reconcile across a simulated process restart, kill switch read at
     call time, never-fail with a ONE-TIME warning, return-truth-follows-
     the-append when rotation breaks.
  2. Fix-pass exclusions: INFRA_READ_COMMANDS (liveness/control-plane)
     never recorded; render polls (the crucible-F3 override) never reach
     the ledger; INFRA ⊆ _READ_ONLY_COMMANDS stays aligned.
  3. handle() hook: a genuine read-only command lands EXACTLY ONE ledger
     row via the _log_executor carrying the handler's per-connection
     session id; a mutating command lands ZERO; SYNAPSE_READ_LEDGER=0
     leaves handler behavior observably unchanged.
  4. Report units (scripts/scene_model_report.py): synthetic fixtures ->
     exact expected numbers; infra bucketed out of the re-read rate; the
     pure-vs-post-mutation split honestly reported unavailable.
  5. Conformance: the report's zero-import mirrors (INFRA_READ_COMMANDS,
     default_log_dir) match their package SSOTs under both env states.

Residency discipline: NO sys.modules hou fakes are planted here — the
conftest canonical fake is the resident (the fake-residency trap). The only
patch surfaces are env vars, module functions, and handler INSTANCES.
"""

import importlib.util
import json
import logging
import os
import time
from datetime import datetime

import pytest

from synapse.core.audit import audit_log
from synapse.core.protocol import SynapseCommand
from synapse.server import handlers as handlers_mod
from synapse.server import read_ledger
from synapse.server.handlers import SynapseHandler


@pytest.fixture(autouse=True)
def _ledger_env(tmp_path, monkeypatch):
    """Isolate every test: tmp logs dir, default env, fresh module state."""
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("SYNAPSE_READ_LEDGER", raising=False)
    monkeypatch.delenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", raising=False)
    read_ledger.reset_ledger_state()
    yield
    read_ledger.reset_ledger_state()


def _rows():
    path = read_ledger.ledger_path()
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _drain_log_executor():
    """Flush both _log_executor workers (the envelope-test idiom)."""
    futs = [handlers_mod._log_executor.submit(lambda: None) for _ in range(2)]
    for f in futs:
        f.result(timeout=5)
    time.sleep(0.05)


def _wait_rows(expected, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = _rows()
        if len(rows) >= expected:
            return rows
        time.sleep(0.02)
    return _rows()


# ── 1. args-hash canonicalization ────────────────────────────────

class TestArgsHash:
    def test_dict_ordering_determinism(self):
        a = {"node": "/obj/x", "parm": "tx", "value": 1}
        b = {"value": 1, "parm": "tx", "node": "/obj/x"}
        assert read_ledger.args_hash(a) == read_ledger.args_hash(b)

    def test_nested_ordering_determinism(self):
        a = {"outer": {"a": 1, "b": [1, 2]}, "z": None}
        b = {"z": None, "outer": {"b": [1, 2], "a": 1}}
        assert read_ledger.args_hash(a) == read_ledger.args_hash(b)

    def test_different_payloads_differ(self):
        assert (read_ledger.args_hash({"node": "/obj/x"})
                != read_ledger.args_hash({"node": "/obj/y"}))

    def test_shape_is_16_hex(self):
        h = read_ledger.args_hash({"any": "thing"})
        assert len(h) == 16
        int(h, 16)  # raises if not hex

    def test_non_json_values_fall_back_to_str(self):
        # default=str: an exotic payload value never breaks the hash
        h = read_ledger.args_hash({"obj": object()})
        assert len(h) == 16


# ── 2. record_read units ─────────────────────────────────────────

class TestRecordRead:
    def test_append_writes_exact_shape_process_fallback(self):
        payload = {"node": "/obj/geo1"}
        result = {"value": 42}
        assert read_ledger.record_read("get_parm", payload, result) is True
        rows = _rows()
        assert len(rows) == 1
        row = rows[0]
        assert set(row) == {"ts", "session_id", "session_scope", "cmd_type",
                            "args_hash", "result_bytes"}
        assert row["cmd_type"] == "get_parm"
        assert row["args_hash"] == read_ledger.args_hash(payload)
        # No session passed -> audit PROCESS-lifetime fallback, honestly
        # scoped (the public accessor, not the private attr).
        assert row["session_id"] == audit_log().current_session_id()
        assert row["session_scope"] == "process"
        expected_bytes = len(json.dumps(
            result, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8"))
        assert row["result_bytes"] == expected_bytes
        datetime.fromisoformat(row["ts"])  # iso8601 or raises

    def test_connection_session_id_is_primary(self):
        # The handler's per-connection id (the Mile-1 baseline identity)
        # wins over the audit process id when provided.
        assert read_ledger.record_read(
            "get_parm", {"node": "/obj/x"}, {}, session_id="ws-client-7",
        ) is True
        row = _rows()[0]
        assert row["session_id"] == "ws-client-7"
        assert row["session_scope"] == "connection"

    def test_infra_commands_never_recorded(self):
        # Liveness/control-plane traffic: identical-payload polling would
        # masquerade as re-reads and flood the FIFO cap (fix pass F1).
        for cmd in sorted(read_ledger.INFRA_READ_COMMANDS):
            assert read_ledger.record_read(cmd, {}, {}) is False, cmd
        assert _rows() == []

    def test_infra_subset_of_read_only_commands(self):
        # Every infra member must be a read-only command — the denylist
        # filters INSIDE the read population, it never reclassifies.
        missing = read_ledger.INFRA_READ_COMMANDS - handlers_mod._READ_ONLY_COMMANDS
        assert missing == set(), (
            f"INFRA_READ_COMMANDS not in _READ_ONLY_COMMANDS: {missing}")

    def test_kill_switch_off_writes_nothing(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "0")
        assert read_ledger.record_read("get_parm", {}, {}) is False
        assert _rows() == []

    def test_kill_switch_read_at_call_time(self, monkeypatch):
        # flip without re-import — the integrity_envelope idiom
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "0")
        assert read_ledger.record_read("get_parm", {}, {}) is False
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "1")
        assert read_ledger.record_read("get_parm", {}, {}) is True
        assert len(_rows()) == 1

    def test_fifo_rotation_keeps_newest(self, monkeypatch):
        # cap=3, slack=max(1, 3//10)=1: trim fires past cap+slack=4, i.e.
        # on the 5th append, down to the newest 3.
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "3")
        for i in range(5):
            assert read_ledger.record_read(f"cmd_{i}", {"i": i}, {}) is True
        rows = _rows()
        assert [r["cmd_type"] for r in rows] == ["cmd_2", "cmd_3", "cmd_4"]

    def test_trim_hysteresis_amortizes_rewrites(self, monkeypatch):
        # The fix-pass efficiency guarantee: at steady state the ledger
        # does NOT full-file rewrite per append. cap=10, slack=1: the 11th
        # append stays on disk untrimmed (within slack); the 12th trims
        # down to exactly cap.
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "10")
        for i in range(11):
            read_ledger.record_read(f"cmd_{i}", {"i": i}, {})
        assert len(_rows()) == 11, "within slack: no rewrite yet"
        read_ledger.record_read("cmd_11", {}, {})
        rows = _rows()
        assert len(rows) == 10, "past cap+slack: trimmed down to cap"
        assert rows[-1]["cmd_type"] == "cmd_11"
        assert rows[0]["cmd_type"] == "cmd_2"

    def test_cap_reconciles_across_restart(self, monkeypatch):
        # FloorGate idiom: the count is re-seeded from disk on first touch
        # of the path, so the cap+slack window survives a process restart.
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "3")
        for i in range(4):
            read_ledger.record_read(f"cmd_{i}", {"i": i}, {})
        assert len(_rows()) == 4  # at cap+slack, untrimmed
        read_ledger.reset_ledger_state()  # simulated restart
        read_ledger.record_read("cmd_new", {}, {})
        rows = _rows()
        # reconciled count=5 > cap+slack=4 -> trim to newest cap=3
        assert [r["cmd_type"] for r in rows] == ["cmd_2", "cmd_3", "cmd_new"]

    def test_cap_zero_disables_rotation(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "0")
        for i in range(7):
            read_ledger.record_read(f"cmd_{i}", {"i": i}, {})
        assert len(_rows()) == 7

    def test_unparseable_cap_disables_rotation(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "garbage")
        assert read_ledger.resolve_max_records() == 0

    def test_default_cap(self):
        assert read_ledger.resolve_max_records() == 5000

    def test_never_fails_on_unwritable_dir(self, tmp_path, monkeypatch, caplog):
        # Point the logs dir UNDER a real file: makedirs must fail there.
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        monkeypatch.setenv("SYNAPSE_LOG_DIR", str(blocker / "sub"))
        with caplog.at_level(logging.WARNING,
                             logger="synapse.server.read_ledger"):
            assert read_ledger.record_read("get_parm", {}, {}) is False
            assert read_ledger.record_read("get_parm", {}, {}) is False
        warnings = [r for r in caplog.records
                    if r.name == "synapse.server.read_ledger"
                    and r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "warning must fire exactly ONCE"

    def test_rotation_failure_keeps_append_truth(self, monkeypatch, caplog):
        # Return truth follows the APPEND: a broken rotation warns once
        # but the row IS on disk, so record_read must say True.
        def _boom(path):
            raise OSError("rotation infrastructure broken")
        monkeypatch.setattr(
            read_ledger._LEDGER, "_bump_and_rotate_locked", _boom)
        with caplog.at_level(logging.WARNING,
                             logger="synapse.server.read_ledger"):
            assert read_ledger.record_read("get_parm", {}, {}) is True
            assert read_ledger.record_read("get_parm", {}, {}) is True
        assert len(_rows()) == 2
        warnings = [r for r in caplog.records
                    if r.name == "synapse.server.read_ledger"
                    and r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "rotation warning must fire exactly ONCE"


# ── 3. handle() hook ─────────────────────────────────────────────

class TestHandleHook:
    @pytest.fixture
    def handler(self, monkeypatch):
        h = SynapseHandler()
        h._registry.register("fake_mutate", lambda payload: {"ok": True})
        # A genuine (non-infra) READ command for hook tests: registered on
        # the instance and added to the read-only set for the test only.
        h._registry.register("fake_read", lambda payload: {"data": 1})
        monkeypatch.setattr(
            handlers_mod, "_READ_ONLY_COMMANDS",
            frozenset(handlers_mod._READ_ONLY_COMMANDS | {"fake_read"}))
        return h

    def test_read_only_command_lands_exactly_one_row(self, handler):
        handler.set_session_id("conn-42")
        resp = handler.handle(SynapseCommand(
            type="fake_read", id="r1", payload={"node": "/obj/x"}))
        assert resp.success
        rows = _wait_rows(1)
        assert len(rows) == 1
        row = rows[0]
        assert row["cmd_type"] == "fake_read"
        assert row["args_hash"] == read_ledger.args_hash({"node": "/obj/x"})
        # The handler's per-connection identity rides the record.
        assert row["session_id"] == "conn-42"
        assert row["session_scope"] == "connection"
        # exactly one — nothing else trickles in behind the drain
        _drain_log_executor()
        assert len(_rows()) == 1

    def test_no_session_id_falls_back_to_process_scope(self, handler):
        resp = handler.handle(SynapseCommand(
            type="fake_read", id="r2", payload={}))
        assert resp.success
        rows = _wait_rows(1)
        assert rows[0]["session_id"] == audit_log().current_session_id()
        assert rows[0]["session_scope"] == "process"

    def test_infra_command_lands_zero_rows(self, handler):
        # ping succeeds but is liveness traffic — never a ledger row.
        resp = handler.handle(SynapseCommand(type="ping", id="i1", payload={}))
        assert resp.success
        _drain_log_executor()
        assert _rows() == []

    def test_render_poll_lands_zero_rows(self, handler):
        # The crucible-F3 override flips _mutating for {"poll": token} —
        # byte-identical payloads that must NOT masquerade as re-reads.
        handler._registry.register(
            "render", lambda payload: {"status": "rendering"})
        resp = handler.handle(SynapseCommand(
            type="render", id="p1", payload={"poll": "tok-1"}))
        assert resp.success
        _drain_log_executor()
        assert _rows() == []

    def test_mutating_command_lands_zero_rows(self, handler, monkeypatch):
        # Isolate the read-arm: no-op the mutating log path on this INSTANCE
        # (audit/bridge/envelope effects are pinned by their own suites).
        monkeypatch.setattr(handler, "_submit_logs",
                            lambda *a, **k: None)
        resp = handler.handle(SynapseCommand(
            type="fake_mutate", id="m1", payload={"node": "/obj/x"},
        ))
        assert resp.success
        _drain_log_executor()
        assert _rows() == []

    def test_kill_switch_handler_behavior_unchanged(self, handler, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "0")
        resp_off = handler.handle(SynapseCommand(
            type="fake_read", id="k1", payload={}))
        assert resp_off.success
        _drain_log_executor()
        assert _rows() == [], "kill switch must yield ZERO rows"

        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "1")
        resp_on = handler.handle(SynapseCommand(
            type="fake_read", id="k2", payload={}))
        _wait_rows(1)
        # identical observable response shape either way
        assert resp_off.success == resp_on.success is True
        assert resp_off.error == resp_on.error
        assert resp_off.data == resp_on.data

    def test_broken_ledger_never_breaks_command(self, handler, monkeypatch):
        # The lazy-import arm swallows ANY ledger failure (ImportError class).
        def _boom():
            raise RuntimeError("ledger infrastructure broken")
        monkeypatch.setattr(read_ledger, "read_ledger_enabled", _boom)
        resp = handler.handle(SynapseCommand(
            type="fake_read", id="b1", payload={}))
        assert resp.success
        _drain_log_executor()
        assert _rows() == []

    def test_failed_command_lands_zero_rows(self, handler):
        # The read-arm is on the SUCCESS path only: a failing READ-classified
        # command must not be recorded as an observation.
        resp = handler.handle(SynapseCommand(
            type="get_parm", id="f1",
            payload={},  # missing node/parm -> handler error, success=False
        ))
        assert not resp.success
        _drain_log_executor()
        assert _rows() == []


# ── 4. report units (scripts/scene_model_report.py) ──────────────

def _load_report_module():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "scene_model_report.py")
    spec = importlib.util.spec_from_file_location("scene_model_report", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_rec(sid, cmd, ahash, scope="connection"):
    return {"ts": "2026-07-18T00:00:00+00:00", "session_id": sid,
            "session_scope": scope, "cmd_type": cmd, "args_hash": ahash,
            "result_bytes": 10}


class TestReadReport:
    def test_re_read_rate_exact(self):
        mod = _load_report_module()
        records = [
            _read_rec("A", "get_parm", "h1"),
            _read_rec("A", "get_parm", "h1"),        # re-read
            _read_rec("A", "get_scene_info", "h2"),
            _read_rec("A", "get_parm", "h1"),        # re-read
            _read_rec("B", "get_parm", "h1"),        # first in B — NOT a re-read
        ]
        stats = mod.compute_read_stats(records)
        assert stats["total_observations"] == 5
        assert stats["session_count"] == 2
        assert stats["per_session_observations"] == {"A": 4, "B": 1}
        assert stats["per_cmd_type"] == {"get_parm": 4, "get_scene_info": 1}
        assert stats["session_scopes"] == {"connection": 5}
        assert stats["re_reads"]["total"] == 2
        assert stats["re_reads"]["rate"] == pytest.approx(0.4)

    def test_infra_bucketed_out_of_rate(self):
        # Legacy ledger rows from before the fix pass may carry infra
        # traffic — the report keeps it out of the headline number.
        mod = _load_report_module()
        stats = mod.compute_read_stats([
            _read_rec("A", "get_parm", "h1"),
            _read_rec("A", "ping", "h0"),
            _read_rec("A", "ping", "h0"),
            _read_rec("A", "render_farm_status", "h0"),
            _read_rec("A", "get_parm", "h1"),        # the only true re-read
        ])
        assert stats["total_observations"] == 2
        assert stats["re_reads"]["total"] == 1
        assert stats["re_reads"]["rate"] == pytest.approx(0.5)
        assert stats["infra_excluded"]["total"] == 3
        assert stats["infra_excluded"]["per_cmd_type"] == {
            "ping": 2, "render_farm_status": 1}

    def test_session_scope_segmentation(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([
            _read_rec("A", "get_parm", "h1"),
            _read_rec("P", "get_parm", "h1", scope="process"),
            {"ts": "x", "session_id": "L", "cmd_type": "get_parm",
             "args_hash": "h1", "result_bytes": 1},  # legacy: no scope
        ])
        assert stats["session_scopes"] == {
            "connection": 1, "process": 1, "unrecorded": 1}

    def test_split_reported_unavailable(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([_read_rec("A", "get_parm", "h1")])
        rr = stats["re_reads"]
        assert rr["pure_re_reads"] is None
        assert rr["post_mutation_re_reads"] is None
        assert "unavailable" in rr["split_note"]

    def test_batch_undercount_stated(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([])
        assert "batch_commands" in stats["batch_note"]
        assert "UNDERCOUNTED" in stats["batch_note"]

    def test_same_hash_different_cmd_not_a_re_read(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([
            _read_rec("A", "get_parm", "h1"),
            _read_rec("A", "get_scene_info", "h1"),
        ])
        assert stats["re_reads"]["total"] == 0

    def test_incomplete_records_skipped(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([
            _read_rec("A", "get_parm", "h1"),
            {"ts": "x", "session_id": "A"},  # missing cmd/hash
        ])
        assert stats["total_observations"] == 1
        assert stats["skipped_records"] == 1

    def test_empty_ledger(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([])
        assert stats["total_observations"] == 0
        assert stats["re_reads"]["rate"] is None

    def test_build_report_deterministic_and_tolerant(self, tmp_path):
        mod = _load_report_module()
        ledger = tmp_path / "read_ledger.jsonl"
        lines = [json.dumps(_read_rec("A", "get_parm", "h1")),
                 "NOT JSON {{{",
                 json.dumps(_read_rec("A", "get_parm", "h1"))]
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        turns = tmp_path / "turns.jsonl"  # absent — empty ledger
        r1 = mod.build_report(str(ledger), str(turns))
        r2 = mod.build_report(str(ledger), str(turns))
        assert r1 == r2, "same inputs must produce same numbers"
        assert r1["read_ledger"]["malformed_lines"] == 1
        assert r1["read_ledger"]["re_reads"]["total"] == 1
        assert r1["turns_ledger"]["sends"] == 0


# ── 5. zero-import mirror conformance ────────────────────────────

class TestMirrorConformance:
    def test_infra_denylist_matches_ledger(self):
        # The report script's zero-import copy must equal the SSOT.
        mod = _load_report_module()
        assert mod.INFRA_READ_COMMANDS == read_ledger.INFRA_READ_COMMANDS

    def test_default_log_dir_matches_core_logfile(self, monkeypatch):
        # The documented-tradeoff mirror of core.logfile.log_dir(), pinned
        # under BOTH env states so drift fails loud.
        mod = _load_report_module()
        from synapse.core.logfile import log_dir
        monkeypatch.setenv("SYNAPSE_LOG_DIR", r"X:\somewhere\else")
        assert mod.default_log_dir() == log_dir()
        monkeypatch.delenv("SYNAPSE_LOG_DIR", raising=False)
        assert mod.default_log_dir() == log_dir()
