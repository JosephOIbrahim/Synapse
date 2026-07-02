"""
SYNAPSE install/ops doctor (M3-C) — the ``doctor`` command / synapse_doctor tool.

NOT the artist-facing Scene Doctor (panel/scene_doctor.py — scene
diagnostics). This one answers "is this SEAT healthy": version stamp, log
file, telemetry freshness, memory encryption-key fingerprint, symbol-table
build stamp, bridge endpoint, hou availability — plus an optional
diagnostic zip bundle.

Truth contract: a check reports ok/fail ONLY if its probe actually
executed; anything not probed is "skipped" with the reason. The bundle
manifest lists what was actually collected, what was absent (and why),
and what was deliberately excluded (secrets — test-pinned denylist).

Adjudicated a NEW command, not a synapse_health extension: get_health's
3-key shape is test-pinned and read-only-classified, and a bundle mode
that writes a zip cannot live behind a read-only-classified command (the
WP6/M1 lesson). "doctor" is deliberately NOT in _READ_ONLY_COMMANDS — a
run takes the C5 lock and leaves audit + Floor provenance (zero hou work,
so the lock hold is milliseconds).

Read-only by construction: the key-fingerprint check resolves key bytes
itself ($SYNAPSE_ENCRYPTION_KEY else ~/.synapse/encryption.key) and NEVER
instantiates CryptoEngine — get_instance() auto-generates and WRITES a
new key when none exists (crypto.py). A diagnostics run must never mint
a key.
"""

import json
import logging
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("synapse.doctor")

# Secrets / show content NEVER collected into a bundle (test-pinned).
# users.json carries password hashes; memory.jsonl is show content —
# the M3-D egress lane, not a diagnostics artifact.
BUNDLE_EXCLUDE = (
    "encryption.key",
    "encryption.key.bak",
    "auth.key",
    "users.json",
    "memory.jsonl",
)
_EXCLUDE_REASONS = {
    "encryption.key": "secret key material, never collected",
    "encryption.key.bak": "secret key material (escrow copy), never collected",
    "auth.key": "secret key material, never collected",
    "users.json": "password hashes, never collected",
    "memory.jsonl": "show content — egress is M3-D's lane, never collected",
}

MAX_BUNDLE_FILE_BYTES = 10 * 1024 * 1024   # global per-file cap
AUDIT_PER_FILE_CAP = 5 * 1024 * 1024       # newest-3 audit files
HEALTH_TAIL_CAP = 1 * 1024 * 1024          # agent_health_history.jsonl tail

INSTALL_STAMP_FILENAME = "install_stamp.json"  # M3-A's installer stamp


def _resolve_log_dir(home: Path) -> str:
    """The same env-first logic as core/logfile.py, with an injectable home:
    ``$SYNAPSE_LOG_DIR`` else ``<home>/.synapse/logs``."""
    override = os.environ.get("SYNAPSE_LOG_DIR", "").strip()
    if override:
        return override
    return str(home / ".synapse" / "logs")


# =============================================================================
# CHECKS — each returns {"name", "status": ok|fail|skipped, "detail", ...}
# =============================================================================

def _check_version(base: Path) -> Dict[str, Any]:
    name = "version"
    try:
        import synapse
        from ..core.protocol import PROTOCOL_VERSION
        running = getattr(synapse, "__version__", "?")
        detail = f"synapse {running} / protocol {PROTOCOL_VERSION}"
        stamp_file = base / INSTALL_STAMP_FILENAME
        if not stamp_file.exists():
            return {"name": name, "status": "ok",
                    "detail": detail + " (no install stamp)"}
        stamped = json.loads(stamp_file.read_text(encoding="utf-8"))
        stamped_version = stamped.get("synapse_version")
        if stamped_version and stamped_version != running:
            return {"name": name, "status": "fail",
                    "detail": (f"{detail}; install stamp says {stamped_version} "
                               f"— installed tree and stamp disagree")}
        return {"name": name, "status": "ok",
                "detail": f"{detail}; install stamp matches"}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


def _check_log_file(home: Path) -> Dict[str, Any]:
    name = "log_file"
    try:
        from ..core.logfile import LOG_FILENAME, file_logging_disabled
        if file_logging_disabled():
            return {"name": name, "status": "skipped",
                    "detail": "file logging disabled (SYNAPSE_FILE_LOG=0)"}
        path = Path(_resolve_log_dir(home)) / LOG_FILENAME
        if path.exists():
            st = path.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()
            return {"name": name, "status": "ok",
                    "detail": f"{path} ({st.st_size} bytes, mtime {mtime})"}
        return {"name": name, "status": "fail",
                "detail": (f"file logging enabled but {path} does not exist — "
                           "no SYNAPSE process has logged on this seat yet, "
                           "or the bootstrap failed")}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


def _check_telemetry(home: Path) -> Dict[str, Any]:
    name = "telemetry"
    try:
        from .telemetry_dump import TELEMETRY_FILENAME, flush_interval_s
        interval = flush_interval_s()
        if interval <= 0:
            return {"name": name, "status": "skipped",
                    "detail": "periodic flush disabled (SYNAPSE_TELEMETRY_FLUSH_S<=0)"}
        path = Path(_resolve_log_dir(home)) / TELEMETRY_FILENAME
        if not path.exists():
            return {"name": name, "status": "skipped",
                    "detail": f"{path} absent — no server/panel has flushed on this seat"}
        age = time.time() - path.stat().st_mtime
        if age <= 2 * interval:
            return {"name": name, "status": "ok",
                    "detail": f"{path} is {age:.0f}s old (flush interval {interval:.0f}s)"}
        return {"name": name, "status": "fail",
                "detail": (f"{path} is stale: {age:.0f}s old vs flush interval "
                           f"{interval:.0f}s — the flusher thread is not running")}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


# -- memory key fingerprint (check design owned by M3-D; implemented here) ----

def _resolve_store_dir() -> Optional[Path]:
    """Resolve the scene-memory storage dir exactly as the live store does
    (<hip_dir>/.synapse via hou.hipFile.path(), no-hou fallback = cwd), but
    READ-ONLY: no migration copies, no mkdir. None when no store dir exists."""
    project: Optional[Path] = None
    try:
        import hou
        hip = hou.hipFile.path()
        if hip and hip != "untitled.hip":
            project = Path(hip)
        else:
            project = Path(hou.text.expandString("$HOUDINI_TEMP_DIR")) / "untitled"
    except Exception:
        project = None
    if project is None:
        project = Path.cwd() / "untitled.hip"
    base_dir = project.parent if project.is_file() else project
    for store_name in (".synapse", ".nexus", ".engram"):
        candidate = base_dir / store_name
        if candidate.is_dir():
            return candidate
    return None


def _resolve_key_bytes_readonly(home: Path) -> Optional[bytes]:
    """Key resolution in the live order ($SYNAPSE_ENCRYPTION_KEY else
    <home>/.synapse/encryption.key) MINUS the auto-generate branch —
    the doctor must never mint and write a key."""
    env_key = os.environ.get("SYNAPSE_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode("utf-8") if isinstance(env_key, str) else env_key
    key_file = home / ".synapse" / "encryption.key"
    try:
        if key_file.exists():
            return key_file.read_bytes().strip()
    except OSError:
        pass
    return None


MISMATCH_REMEDIATION = (
    "Provision the show key via SYNAPSE_ENCRYPTION_KEY (env beats the "
    "per-user file). Do NOT delete or resave the store — the ciphertext "
    "is recoverable with the right key."
)


def check_memory_key_fingerprint(
    home: Optional[Path] = None,
    storage_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """M3-D's check, exactly as specced: compare the active key fingerprint
    to the store's key.fingerprint sidecar as a PURE READ — never construct
    a MemoryStore (flusher threads + a load), never instantiate CryptoEngine
    (auto-generates + writes). Both fingerprints are non-secret by design
    (sha256[:8]) — safe to print and bundle.

    status: "match" | "mismatch" | "not_checked"; not_checked carries
    reason in {"no_store_dir", "no_sidecar", "no_crypto", "no_key"}.
    """
    home = Path(home) if home is not None else Path.home()
    result: Dict[str, Any] = {
        "check": "memory_key_fingerprint",
        "status": "not_checked",
        "active_fingerprint": None,
        "sidecar_fingerprint": None,
        "storage_dir": None,
        "reason": None,
    }
    store_dir = Path(storage_dir) if storage_dir is not None else _resolve_store_dir()
    if store_dir is None or not store_dir.is_dir():
        result["reason"] = "no_store_dir"
        return result
    result["storage_dir"] = str(store_dir)
    try:
        result["degraded_quarantine_count"] = len(
            list(store_dir.glob("memory.jsonl.degraded-*"))
        )
    except OSError:
        pass

    sidecar = store_dir / "key.fingerprint"
    if not sidecar.exists():
        result["reason"] = "no_sidecar"
        return result
    try:
        result["sidecar_fingerprint"] = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        result["reason"] = "no_sidecar"
        return result

    try:
        from ..core.crypto import key_fingerprint  # pure function, no engine
    except Exception:
        result["reason"] = "no_crypto"
        return result
    key = _resolve_key_bytes_readonly(home)
    if key is None:
        result["reason"] = "no_key"
        return result
    result["active_fingerprint"] = key_fingerprint(key)

    if result["active_fingerprint"] == result["sidecar_fingerprint"]:
        result["status"] = "match"
    else:
        result["status"] = "mismatch"
        result["remediation"] = MISMATCH_REMEDIATION
    return result


def _wrap_memory_key_check(home: Path) -> Dict[str, Any]:
    """Adapt M3-D's result shape into the doctor's check shape, carrying
    the full M3-D contract in ``result``."""
    name = "memory_key_fingerprint"
    try:
        res = check_memory_key_fingerprint(home=home)
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}
    status_map = {"match": "ok", "mismatch": "fail", "not_checked": "skipped"}
    if res["status"] == "match":
        detail = f"active key fingerprint {res['active_fingerprint']} matches the store sidecar"
    elif res["status"] == "mismatch":
        detail = (f"key fingerprint mismatch (sidecar {res['sidecar_fingerprint']} "
                  f"!= active {res['active_fingerprint']}). {MISMATCH_REMEDIATION}")
    else:
        detail = f"not checked ({res['reason']})"
    return {"name": name, "status": status_map[res["status"]],
            "detail": detail, "result": res}


# -----------------------------------------------------------------------------

def _check_symbol_table() -> Dict[str, Any]:
    name = "symbol_table"
    try:
        import synapse
        # Committed package authority (scout.py _PKG_SYMBOL_TABLE path).
        data_dir = (Path(synapse.__file__).resolve().parent
                    / "cognitive" / "tools" / "data")
        running = None
        try:
            import hou
            running = hou.applicationVersionString()
        except Exception:
            running = None
        # Per-major table (runway §1.4) — mirror scout's loader rule: prefer
        # h<major>_symbol_table.json for the RUNNING major when committed,
        # else the h21 file (the stamp compare below still trips the gate).
        table = data_dir / "h21_symbol_table.json"
        major = str(running or "").split(".", 1)[0]
        if major.isdigit():
            candidate = data_dir / f"h{major}_symbol_table.json"
            if candidate.exists():
                table = candidate
        if not table.exists():
            return {"name": name, "status": "fail",
                    "detail": f"symbol table missing: {table}"}
        meta = json.loads(table.read_text(encoding="utf-8"))
        stamp = meta.get("houdini_version")
        described = (f"stamp {stamp} ({meta.get('symbol_count')} symbols, "
                     f"blake2b {meta.get('blake2b')})")
        if not isinstance(running, str):
            return {"name": name, "status": "skipped",
                    "detail": f"{described}; runtime comparison skipped (no hou)"}
        if running == stamp:
            return {"name": name, "status": "ok",
                    "detail": f"{described} == running {running}"}
        return {"name": name, "status": "fail",
                "detail": (f"{described} != running {running} — regenerate via "
                           "host/introspect_runtime.py (scout distrusts a "
                           "version-mismatched table)")}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


def _check_bridge_endpoint(base: Path) -> Dict[str, Any]:
    name = "bridge_endpoint"
    try:
        path = base / "bridge.json"
        if not path.exists():
            return {"name": name, "status": "skipped",
                    "detail": f"{path} absent — server not started on this machine"}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"name": name, "status": "ok",
                "detail": (f"{path}: ws://{data.get('host')}:{data.get('port')} "
                           f"(pid {data.get('pid')}, published {data.get('ts')})")}
    except json.JSONDecodeError as e:
        return {"name": name, "status": "fail",
                "detail": f"bridge.json unreadable/corrupt: {e}"}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


# H5 (multi-client hardening): known localhost MCP-server ports to audit for
# coexistence. Add the official H22 APEX MCP port here once task 1.7 reveals
# it. Hazards + posture: docs/MCP_COEXISTENCE.md.
KNOWN_MCP_PORTS = {8100: "fxhoudinimcp"}


def _check_mcp_coexistence(base: Path) -> Dict[str, Any]:
    """H5: port-collision audit. Resolve our actual bound port (the injectable
    sidecar at ``base/bridge.json`` when present, else the live resolver's
    env/home sidecar → 9999/$SYNAPSE_PORT fallback), TCP-probe the known
    foreign MCP ports, and confirm our own port accepts a connection.
    Read-only, stdlib-only, info/warn detail — NEVER fail: a foreign MCP is a
    documented coexistence hazard, not a broken seat."""
    name = "mcp_coexistence"
    try:
        import socket
        from .bridge_endpoint import resolve_endpoint

        host, our_port = resolve_endpoint()
        sidecar = base / "bridge.json"
        if sidecar.exists():
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                host = str(data.get("host") or host)
                our_port = int(data.get("port") or our_port)
            except Exception:
                pass  # unreadable sidecar is _check_bridge_endpoint's finding

        def _open(probe_host: str, port: int) -> bool:
            try:
                with socket.create_connection((probe_host, port), timeout=0.25):
                    return True
            except OSError:
                return False

        ours_up = _open(host, our_port)
        foreign = [
            f"{label} on :{port}"
            for port, label in sorted(KNOWN_MCP_PORTS.items())
            if port != our_port and _open("127.0.0.1", port)
        ]
        parts = [
            f"SYNAPSE endpoint {host}:{our_port} "
            + ("accepting connections" if ours_up
               else "not accepting connections (server may be down)")
        ]
        if foreign:
            parts.append(
                "foreign MCP detected: " + ", ".join(foreign)
                + " — coexistence hazards documented in docs/MCP_COEXISTENCE.md"
            )
        else:
            parts.append("no known foreign MCP ports open")
        return {"name": name, "status": "ok", "detail": "; ".join(parts),
                "result": {"our_host": host, "our_port": our_port,
                           "our_endpoint_up": ours_up,
                           "foreign_detected": foreign}}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


def _check_main_thread() -> Dict[str, Any]:
    """H3 surfacing: stall-detector state + dispatch-wait histogram. Reports
    state only — the bounded recovery probe belongs to the fast-fail gates."""
    name = "main_thread"
    try:
        from .main_thread import dispatch_wait_stats, stall_state
        state = stall_state()
        waits = dispatch_wait_stats()
        result = {"stall": state, "dispatch_waits": waits}
        if state["stalled"]:
            return {"name": name, "status": "fail",
                    "detail": (f"main thread stalled "
                               f"({state['consecutive_timeouts']} consecutive "
                               "run_on_main timeouts) — a heavy cook, render, or "
                               "another MCP client may be saturating it"),
                    "result": result}
        return {"name": name, "status": "ok",
                "detail": (f"not stalled ({state['consecutive_timeouts']} "
                           f"consecutive timeouts, {waits['count']} dispatch-wait "
                           f"samples, max {waits['max_ms']:.0f}ms)"),
                "result": result}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


def _check_houdini(handler) -> Dict[str, Any]:
    name = "houdini"
    if handler is None:
        return {"name": name, "status": "skipped",
                "detail": "no live handler (doctor run outside the bridge)"}
    try:
        from . import handlers as handlers_mod
        if bool(getattr(handlers_mod, "HOU_AVAILABLE", False)):
            return {"name": name, "status": "ok", "detail": "hou available"}
        return {"name": name, "status": "fail",
                "detail": "handler is live but hou is unavailable"}
    except Exception as e:
        return {"name": name, "status": "skipped", "detail": f"probe failed: {e}"}


# =============================================================================
# BUNDLE
# =============================================================================

def _newest_files(directory: Path, count: int) -> List[Path]:
    files = [p for p in directory.iterdir() if p.is_file()]
    files.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return files[:count]


def _bundle_candidates(base: Path, home: Path) -> List[Dict[str, Any]]:
    """Manifest-driven candidate table. Each row: arcname, path (None when
    the source is unresolvable), per-file cap, optional tail cap, group —
    so every candidate resolves to a collected/absent manifest row."""
    rows: List[Dict[str, Any]] = []
    log_dir = Path(_resolve_log_dir(home))

    def add(arcname, path, cap=MAX_BUNDLE_FILE_BYTES, tail=None):
        rows.append({"arcname": arcname, "path": path, "cap": cap, "tail": tail})

    add("logs/synapse.log", log_dir / "synapse.log")
    for i in (1, 2, 3):
        add(f"logs/synapse.log.{i}", log_dir / f"synapse.log.{i}")
    add("logs/telemetry.json", log_dir / "telemetry.json")
    freeze_dumps = sorted(log_dir.glob("freeze_dump_*.json")) if log_dir.is_dir() else []
    if freeze_dumps:
        for p in freeze_dumps:
            add(f"logs/{p.name}", p)
    else:
        add("logs/freeze_dump_*.json", None)

    add("bridge.json", base / "bridge.json")
    add("deploy.json", base / "deploy.json")

    audit_dir = base / "audit"
    if audit_dir.is_dir():
        for p in _newest_files(audit_dir, 3):
            add(f"audit/{p.name}", p, cap=AUDIT_PER_FILE_CAP)
    else:
        add("audit/", None)

    # Agent-health history (panel/agent_health.py path), tail-capped.
    health_root = os.environ.get("SYNAPSE_ROOT") or str(home)
    add("agent_health_history.jsonl",
        Path(health_root) / ".synapse" / "agent_health_history.jsonl",
        tail=HEALTH_TAIL_CAP)

    # Repo-scoped Floor provenance + ledger, newest 3 each, when resolvable.
    try:
        from ..core.floor_gate import resolve_provenance_dir
        prov_dir = Path(resolve_provenance_dir())
        if prov_dir.is_dir():
            for p in _newest_files(prov_dir, 3):
                add(f"provenance/{p.name}", p)
        else:
            add("provenance/", None)
    except Exception:
        add("provenance/", None)
    try:
        from ..memory.ledger import ledger_dir
        led_dir = Path(ledger_dir())
        if led_dir.is_dir():
            for p in _newest_files(led_dir, 3):
                add(f"ledger/{p.name}", p)
        else:
            add("ledger/", None)
    except Exception:
        add("ledger/", None)

    return rows


def _build_bundle(base: Path, home: Path,
                  checks: List[Dict], summary: Dict) -> Dict[str, Any]:
    """Write the diagnostic zip. The manifest records what was actually
    collected, what was absent (with the reason), and what was deliberately
    excluded — the truth contract applied to collection."""
    collected: List[Dict[str, Any]] = []
    absent: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = [
        {"name": name, "reason": _EXCLUDE_REASONS[name]} for name in BUNDLE_EXCLUDE
    ]
    try:
        diag_dir = base / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_path = diag_dir / f"synapse_diag_{stamp}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for row in _bundle_candidates(base, home):
                arcname, path = row["arcname"], row["path"]
                if path is None or not path.exists():
                    absent.append({"name": arcname, "reason": "missing"})
                    continue
                if path.name in BUNDLE_EXCLUDE:
                    continue  # already listed in the static exclusion manifest
                try:
                    size = path.stat().st_size
                    if row["tail"] is None and size > row["cap"]:
                        absent.append({"name": arcname,
                                       "reason": f"too large ({size} bytes > {row['cap']})"})
                        continue
                    if row["tail"] is not None:
                        with open(path, "rb") as f:
                            if size > row["tail"]:
                                f.seek(size - row["tail"])
                            data = f.read(row["tail"])
                        zf.writestr(arcname, data)
                        collected.append({"name": arcname, "size": len(data)})
                    else:
                        zf.write(path, arcname)
                        collected.append({"name": arcname, "size": size})
                except OSError as e:
                    absent.append({"name": arcname, "reason": f"unreadable: {e}"})

            report = {
                "checks": checks,
                "summary": summary,
                "collected": collected,
                "absent": absent,
                "excluded": excluded,
                "generated": datetime.now(timezone.utc).isoformat(),
            }
            report_blob = json.dumps(report, indent=2, default=str)
            zf.writestr("doctor_report.json", report_blob)
            collected.append({"name": "doctor_report.json", "size": len(report_blob)})

        return {"path": str(zip_path), "collected": collected,
                "absent": absent, "excluded": excluded}
    except Exception as e:
        logger.exception("Diagnostic bundle failed")
        return {"path": None, "collected": collected, "absent": absent,
                "excluded": excluded, "error": str(e)}


# =============================================================================
# ENTRY POINT
# =============================================================================

def run_doctor(payload: Dict, handler=None, home: Optional[Path] = None) -> Dict[str, Any]:
    """Run every diagnostic check; optionally write the bundle.

    *home* defaults to Path.home() and is injectable for tests (the
    AuditLog(log_dir=...)/HumanGate(storage_dir=...) precedent).
    """
    home = Path(home) if home is not None else Path.home()
    base = home / ".synapse"

    checks = [
        _check_version(base),
        _check_log_file(home),
        _check_telemetry(home),
        _wrap_memory_key_check(home),
        _check_symbol_table(),
        _check_bridge_endpoint(base),
        _check_mcp_coexistence(base),
        _check_main_thread(),
        _check_houdini(handler),
    ]
    summary = {"ok": 0, "fail": 0, "skipped": 0}
    for check in checks:
        summary[check["status"]] += 1

    bundle = None
    if payload.get("bundle"):
        bundle = _build_bundle(base, home, checks, summary)

    return {"checks": checks, "summary": summary, "bundle": bundle}
