"""Scene-model Mile 0 — READ-class observation ledger.

Pins:
  1. Ledger units: append shape, args-hash canonicalization determinism,
     FIFO rotation + cap reconcile across a simulated process restart,
     kill switch read at call time, never-fail with a ONE-TIME warning.
  2. handle() hook: a read-only command lands EXACTLY ONE ledger row via
     the _log_executor; a mutating command lands ZERO; SYNAPSE_READ_LEDGER=0
     leaves handler behavior observably unchanged (zero rows, same response).
  3. Report units (scripts/scene_model_report.py): synthetic fixtures ->
     exact expected numbers; the pure-vs-post-mutation split is honestly
     reported unavailable (Mile 0 ledgers capture reads only).

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
    def test_append_writes_exact_shape(self):
        payload = {"node": "/obj/geo1"}
        result = {"value": 42}
        assert read_ledger.record_read("get_parm", payload, result) is True
        rows = _rows()
        assert len(rows) == 1
        row = rows[0]
        assert set(row) == {"ts", "session_id", "cmd_type", "args_hash",
                            "result_bytes"}
        assert row["cmd_type"] == "get_parm"
        assert row["args_hash"] == read_ledger.args_hash(payload)
        assert row["session_id"] == audit_log()._current_session
        expected_bytes = len(json.dumps(
            result, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8"))
        assert row["result_bytes"] == expected_bytes
        datetime.fromisoformat(row["ts"])  # iso8601 or raises

    def test_kill_switch_off_writes_nothing(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "0")
        assert read_ledger.record_read("ping", {}, {}) is False
        assert _rows() == []

    def test_kill_switch_read_at_call_time(self, monkeypatch):
        # flip without re-import — the integrity_envelope idiom
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "0")
        assert read_ledger.record_read("ping", {}, {}) is False
        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "1")
        assert read_ledger.record_read("ping", {}, {}) is True
        assert len(_rows()) == 1

    def test_fifo_rotation_keeps_newest(self, monkeypatch):
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "3")
        for i in range(5):
            assert read_ledger.record_read(f"cmd_{i}", {"i": i}, {}) is True
        rows = _rows()
        assert [r["cmd_type"] for r in rows] == ["cmd_2", "cmd_3", "cmd_4"]

    def test_cap_reconciles_across_restart(self, monkeypatch):
        # FloorGate idiom: the cap survives a process restart — the count
        # is re-seeded from disk on first touch of the path.
        monkeypatch.setenv("SYNAPSE_READ_LEDGER_MAX_RECORDS", "3")
        for i in range(3):
            read_ledger.record_read(f"cmd_{i}", {"i": i}, {})
        read_ledger.reset_ledger_state()  # simulated restart
        read_ledger.record_read("cmd_new", {}, {})
        rows = _rows()
        assert [r["cmd_type"] for r in rows] == ["cmd_1", "cmd_2", "cmd_new"]

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
            assert read_ledger.record_read("ping", {}, {}) is False
            assert read_ledger.record_read("ping", {}, {}) is False
        warnings = [r for r in caplog.records
                    if r.name == "synapse.server.read_ledger"
                    and r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "warning must fire exactly ONCE"


# ── 3. handle() hook ─────────────────────────────────────────────

class TestHandleHook:
    @pytest.fixture
    def handler(self):
        h = SynapseHandler()
        h._registry.register("fake_mutate", lambda payload: {"ok": True})
        return h

    def test_read_only_command_lands_exactly_one_row(self, handler):
        resp = handler.handle(SynapseCommand(type="ping", id="r1", payload={}))
        assert resp.success
        rows = _wait_rows(1)
        assert len(rows) == 1
        row = rows[0]
        assert row["cmd_type"] == "ping"
        assert row["args_hash"] == read_ledger.args_hash({})
        assert row["session_id"] == audit_log()._current_session
        # exactly one — nothing else trickles in behind the drain
        _drain_log_executor()
        assert len(_rows()) == 1

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
            type="ping", id="k1", payload={}))
        assert resp_off.success
        _drain_log_executor()
        assert _rows() == [], "kill switch must yield ZERO rows"

        monkeypatch.setenv("SYNAPSE_READ_LEDGER", "1")
        resp_on = handler.handle(SynapseCommand(
            type="ping", id="k2", payload={}))
        _wait_rows(1)
        # identical observable response shape either way
        assert resp_off.success == resp_on.success is True
        assert resp_off.error == resp_on.error
        assert set(resp_off.data) == set(resp_on.data)
        assert resp_off.data["pong"] == resp_on.data["pong"] is True

    def test_broken_ledger_never_breaks_command(self, handler, monkeypatch):
        # The lazy-import arm swallows ANY ledger failure (ImportError class).
        def _boom():
            raise RuntimeError("ledger infrastructure broken")
        monkeypatch.setattr(read_ledger, "read_ledger_enabled", _boom)
        resp = handler.handle(SynapseCommand(type="ping", id="b1", payload={}))
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


def _read_rec(sid, cmd, ahash):
    return {"ts": "2026-07-18T00:00:00+00:00", "session_id": sid,
            "cmd_type": cmd, "args_hash": ahash, "result_bytes": 10}


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
        assert stats["re_reads"]["total"] == 2
        assert stats["re_reads"]["rate"] == pytest.approx(0.4)

    def test_split_reported_unavailable(self):
        mod = _load_report_module()
        stats = mod.compute_read_stats([_read_rec("A", "ping", "h1")])
        rr = stats["re_reads"]
        assert rr["pure_re_reads"] is None
        assert rr["post_mutation_re_reads"] is None
        assert "unavailable" in rr["split_note"]

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
