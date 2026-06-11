"""M3-C (studio-operable hardening): rotating file log + telemetry flush +
sustained-freeze evidence dump + the install/ops doctor.

Before M3-C, ZERO logging FileHandlers existed in production code — every
record >= WARNING fell to logging.lastResort (the unsaved Houdini console)
and INFO and below were dropped outright; all three telemetry surfaces were
pure process memory. These pins prove: the file handler attaches once,
records land, policy holds; flushes are atomic and mark absent sections
honestly (never fabricated); FreezeChain._escalate dumps evidence and a
dump failure never blocks the breaker/halt actions; the doctor reports only
checks it actually ran (skipped is not ok), never mints an encryption key,
and the bundle's secrets denylist is enforced.

Headless. hou fake is plant-or-enrich (tests/test_m2_cook_verify.py header
convention — needed because the handler/adapter imports pull hou-guarded
modules); everything else is pure stock python like tests/test_freeze_chain.
test_doctor_command_wired pins the orchestrator-reserved "doctor"
registration in handlers.py — deselect it until that edit lands.
"""

import importlib
import json
import logging
import logging.handlers
import os
import sys
import time
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
# The resident fake's shape leaks into every later-imported handler module
# (first planter wins) -- enrich it with what sibling handler tests rely on,
# never plant a skeleton (test_m2_cook_verify.py pattern).
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    # Sibling convention: expandString returns a real str (later files'
    # handlers run Path() over it when this file is the first planter).
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.core import logfile  # noqa: E402
from synapse.server import doctor  # noqa: E402
from synapse.server import freeze_chain as fc  # noqa: E402
from synapse.server import telemetry_dump as td  # noqa: E402
from synapse.server import websocket as ws  # noqa: E402


# Tiny-threshold chain (test_freeze_chain.py idiom): detection ~0.06s,
# escalation deadline 0.2s.
def _chain():
    return fc.FreezeChain(escalate_after=0.2, heartbeat_interval=0.02,
                          freeze_threshold=0.06)


def _fake_server(with_bridge=True):
    bridge = MagicMock()
    bridge.session_report.return_value = {"ops": 0}
    handler = SimpleNamespace(_bridge=bridge if with_bridge else None)
    breaker = MagicMock()
    return SimpleNamespace(_circuit_breaker=breaker, _handler=handler), breaker, bridge


@pytest.fixture(autouse=True)
def _clean_state():
    """Logger state is process-global: detach + close anything this file
    attached to the 'synapse' logger and restore its level, clear the live
    server registry, stop any flusher thread."""
    ws._register_live_server(None)
    synapse_logger = logging.getLogger("synapse")
    before_handlers = list(synapse_logger.handlers)
    before_level = synapse_logger.level
    yield
    ws._register_live_server(None)
    td.stop_periodic_flush()
    logfile.reset_file_logging()
    for handler in list(synapse_logger.handlers):
        if handler not in before_handlers:
            synapse_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    synapse_logger.setLevel(before_level)


# =============================================================================
# Logfile
# =============================================================================

def test_ensure_file_logging_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("SYNAPSE_FILE_LOG", raising=False)
    p1 = logfile.ensure_file_logging()
    p2 = logfile.ensure_file_logging()
    assert p1 == p2 == str(tmp_path / "synapse.log")
    mine = [
        h for h in logging.getLogger("synapse").handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
        and getattr(h, "baseFilename", None) == p1
    ]
    assert len(mine) == 1


def test_record_lands_in_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("SYNAPSE_FILE_LOG", raising=False)
    path = Path(logfile.ensure_file_logging())
    assert not path.exists()  # delay=True: no file until the first record
    logging.getLogger("synapse.freeze_chain").error("m3c-boom")
    assert path.exists()
    assert "m3c-boom" in path.read_text(encoding="utf-8")


def test_env_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("SYNAPSE_FILE_LOG", "0")
    before = list(logging.getLogger("synapse").handlers)
    assert logfile.ensure_file_logging() is None
    assert logging.getLogger("synapse").handlers == before


def test_policy_pinned(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("SYNAPSE_FILE_LOG", raising=False)
    root_before = list(logging.getLogger().handlers)
    logfile.ensure_file_logging()
    handler = logfile._handler
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    assert handler.level == logging.INFO
    assert logging.getLogger().handlers == root_before  # never touches root


# =============================================================================
# Telemetry flush
# =============================================================================

def test_flush_periodic_atomic(tmp_path):
    out = td.flush_telemetry(dir_path=str(tmp_path))
    assert out == str(tmp_path / "telemetry.json")
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    for key in ("ts", "pid", "synapse_version", "dispatch_waits",
                "tool_durations", "freeze", "live_metrics_latest"):
        assert key in data
    assert not list(tmp_path.glob("*.tmp"))  # atomic: no temp residue


def test_collect_marks_absent(monkeypatch):
    """Truth contract: absence is marked with WHY, never fabricated; the
    always-collectable section is real data."""
    from synapse.server import hwebserver_adapter
    monkeypatch.setattr(hwebserver_adapter, "_handler", None)
    monkeypatch.setattr(fc, "_chain", None)
    data = td.collect_telemetry()
    assert data["tool_durations"] is None
    assert "no live handler" in data["tool_durations_absent"]
    assert data["live_metrics_latest"] is None
    assert "aggregator" in data["live_metrics_latest_absent"]
    assert isinstance(data["dispatch_waits"], dict)
    assert "count" in data["dispatch_waits"]


def test_dispatch_waits_real(tmp_path):
    mt = importlib.import_module("synapse.server.main_thread")
    mt.reset_dispatch_wait_stats()
    mt._record_dispatch_wait(3.0)
    out = td.flush_telemetry(dir_path=str(tmp_path))
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data["dispatch_waits"]["count"] == 1


# =============================================================================
# Escalation dump
# =============================================================================

def test_escalate_dumps_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    chain = _chain()
    try:
        chain.heartbeat()                       # arm monitoring
        time.sleep(0.6)                         # freeze past detection + deadline
        assert chain.escalated is True
        dumps = list(tmp_path.glob("freeze_dump_*.json"))
        assert len(dumps) == 1
        data = json.loads(dumps[0].read_text(encoding="utf-8"))
        assert data["reason"] == "sustained_freeze"
    finally:
        chain._watchdog.stop()


def test_dump_failure_never_blocks_escalation(monkeypatch):
    srv, breaker, _bridge = _fake_server(with_bridge=True)
    ws._register_live_server(srv)

    def _boom(*args, **kwargs):
        raise RuntimeError("dump exploded")

    monkeypatch.setattr(td, "flush_telemetry", _boom)
    chain = _chain()
    try:
        chain.heartbeat()
        time.sleep(0.6)
        assert chain.escalated is True
        breaker.force_open.assert_called_once()  # the breaker still ACTED
    finally:
        chain._watchdog.stop()


def test_freeze_dumps_pruned(tmp_path):
    for i in range(6):
        stale = tmp_path / f"freeze_dump_2026010{i}_000000.json"
        stale.write_text("{}")
        os.utime(stale, (1000 + i, 1000 + i))
    out = td.flush_telemetry(reason="sustained_freeze", dir_path=str(tmp_path))
    dumps = list(tmp_path.glob("freeze_dump_*.json"))
    assert len(dumps) == 5                       # newest 5 remain
    assert Path(out) in dumps                    # the new dump survived


# =============================================================================
# Doctor
# =============================================================================

def test_checks_truth_contract(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SYNAPSE_LOG_DIR", raising=False)
    monkeypatch.delenv("SYNAPSE_FILE_LOG", raising=False)
    monkeypatch.chdir(tmp_path)  # store-dir resolution must not find repo/.synapse
    result = doctor.run_doctor({}, home=tmp_path)
    assert set(result["summary"]) == {"ok", "fail", "skipped"}
    assert sum(result["summary"].values()) == len(result["checks"])
    for check in result["checks"]:
        assert check["status"] in ("ok", "fail", "skipped")
        assert check["detail"]
    by_name = {c["name"]: c for c in result["checks"]}
    fingerprint = by_name["memory_key_fingerprint"]
    assert fingerprint["status"] == "skipped"    # NOT ok — nothing was compared
    assert fingerprint["result"]["status"] == "not_checked"
    # Read-only pin: the doctor must never mint a key (CryptoEngine would).
    assert not (tmp_path / ".synapse" / "encryption.key").exists()


def test_symbol_table_check():
    check = doctor._check_symbol_table()
    assert "21.0.671" in check["detail"]         # the committed build stamp
    assert check["status"] != "fail"             # absent hou is not a failure


def test_memory_key_fingerprint_match_and_mismatch(tmp_path, monkeypatch):
    """The M3-D check contract: pure-read comparison, exact output shape."""
    from synapse.core.crypto import key_fingerprint

    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    store = tmp_path / "store"
    store.mkdir()
    home = tmp_path / "home"
    (home / ".synapse").mkdir(parents=True)
    key = b"0123456789abcdef"
    (home / ".synapse" / "encryption.key").write_bytes(key)

    (store / "key.fingerprint").write_text(key_fingerprint(key))
    res = doctor.check_memory_key_fingerprint(home=home, storage_dir=store)
    assert res["check"] == "memory_key_fingerprint"
    assert res["status"] == "match"
    assert res["active_fingerprint"] == res["sidecar_fingerprint"]
    assert res["storage_dir"] == str(store)

    (store / "key.fingerprint").write_text("deadbeef")
    (store / "memory.jsonl.degraded-123").write_text("x")
    res = doctor.check_memory_key_fingerprint(home=home, storage_dir=store)
    assert res["status"] == "mismatch"
    assert "SYNAPSE_ENCRYPTION_KEY" in res["remediation"]
    assert res["degraded_quarantine_count"] == 1


def test_bundle_collects_and_excludes(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_LOG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".synapse"
    (base / "logs").mkdir(parents=True)
    (base / "logs" / "synapse.log").write_text("log line\n")
    (base / "bridge.json").write_text(
        json.dumps({"host": "localhost", "port": 9999, "pid": 1, "ts": "t"})
    )
    (base / "deploy.json").write_text("{}")
    (base / "encryption.key").write_text("SECRET")
    (base / "auth.key").write_text("SECRET")
    (base / "users.json").write_text("{}")

    result = doctor.run_doctor({"bundle": True}, home=tmp_path)
    bundle = result["bundle"]
    assert bundle["path"] and Path(bundle["path"]).exists()
    assert Path(bundle["path"]).parent == base / "diagnostics"
    with zipfile.ZipFile(bundle["path"]) as zf:
        names = zf.namelist()
    assert "logs/synapse.log" in names
    assert "bridge.json" in names
    assert "deploy.json" in names
    assert "doctor_report.json" in names
    # Secrets denylist: never in the zip AND visibly listed as excluded.
    for secret in ("encryption.key", "auth.key", "users.json"):
        assert not any(secret in name for name in names)
        assert any(entry["name"] == secret for entry in bundle["excluded"])
    # A missing candidate appears as absent with a reason.
    assert any(entry["name"] == "audit/" and entry["reason"] == "missing"
               for entry in bundle["absent"])


def test_doctor_command_wired(tmp_path, monkeypatch):
    """Pins the orchestrator-reserved registration (handlers.py): the live
    "doctor" command dispatches to run_doctor and is NOT read-only-classified
    (bundle writes — a run must take the C5 lock + leave audit/Floor records).
    DESELECT until the orchestrator lands the reserved handlers.py edit."""
    from synapse.core.protocol import SynapseCommand
    from synapse.server import handlers as handlers_mod

    assert "doctor" not in handlers_mod._READ_ONLY_COMMANDS
    monkeypatch.chdir(tmp_path)
    handler = handlers_mod.SynapseHandler()
    response = handler.handle(
        SynapseCommand(type="doctor", id="t", payload={}, sequence=1)
    )
    assert response.success is True
    assert "checks" in response.data
    assert "summary" in response.data
