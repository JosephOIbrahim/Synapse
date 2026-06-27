"""
Telemetry flush — periodic snapshot + sustained-freeze evidence dump (M3-C).

The process's three telemetry surfaces (the C6 dispatch-wait histogram in
``main_thread``, the per-tool duration histogram on the live SynapseHandler,
the live-metrics ring) are pure process memory — they die with the process,
which is exactly when the post-mortem needs them. This module flushes them
to disk: a periodic atomic overwrite of ``telemetry.json`` plus timestamped
``freeze_dump_*.json`` evidence files written by ``FreezeChain._escalate``
at the sustained-freeze deadline (newest 5 kept).

Truth contract: every section is present as real data OR an explicit
absence marker stating why — never fabricated. On the live hwebserver
transport the live-metrics aggregator is never constructed (websocket-only
wiring), so ``live_metrics_latest`` is ALWAYS honestly absent there.

Collection uses the freeze_chain peek discipline: attribute reads on
already-constructed objects only — never constructs a handler, chain, or
aggregator. Zero ``hou``. Never raises.
"""

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("synapse.telemetry")

# Seconds; <=0 disables the periodic flush.
_ENV_FLUSH_S = "SYNAPSE_TELEMETRY_FLUSH_S"
DEFAULT_FLUSH_S = 60.0

TELEMETRY_FILENAME = "telemetry.json"
FREEZE_DUMP_PREFIX = "freeze_dump_"
FREEZE_DUMP_KEEP = 5

# Module-singleton flusher thread (freeze_chain._chain idiom).
_flush_lock = threading.Lock()
_flush_thread: Optional[threading.Thread] = None
_flush_stop = threading.Event()


def flush_interval_s() -> float:
    """Configured periodic-flush interval: ``$SYNAPSE_TELEMETRY_FLUSH_S``
    else 60.0. A value <= 0 disables the periodic flush."""
    raw = os.environ.get(_ENV_FLUSH_S, "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return DEFAULT_FLUSH_S


def _peek_live_handler():
    """The live SynapseHandler, if any — hwebserver module global first,
    then the live server's. Attribute peeks only; NEVER constructs one
    (the freeze_chain._peek_* discipline)."""
    try:
        from . import hwebserver_adapter
        handler = getattr(hwebserver_adapter, "_handler", None)
        if handler is not None:
            return handler
    except Exception:
        pass
    try:
        from .freeze_chain import _peek_live_server
        srv = _peek_live_server()
        return getattr(srv, "_handler", None) if srv is not None else None
    except Exception:
        return None


def _peek_live_aggregator():
    """The live MetricsAggregator, if any — hwebserver module global first,
    then the live websocket server's. Attribute peeks only; NEVER constructs
    one (the freeze_chain._peek_* discipline). The hwebserver transport now
    builds + feeds one (start_hwebserver), so the dominant path is no longer
    always-absent."""
    try:
        from . import hwebserver_adapter
        agg = getattr(hwebserver_adapter, "_metrics_aggregator", None)
        if agg is not None:
            return agg
    except Exception:
        pass
    try:
        from .freeze_chain import _peek_live_server
        srv = _peek_live_server()
        return getattr(srv, "_metrics_aggregator", None) if srv is not None else None
    except Exception:
        return None


def collect_telemetry() -> dict:
    """Snapshot every telemetry surface. Each section is real data or None
    plus an ``*_absent`` marker stating why. Individually try/excepted —
    one broken surface never empties the rest."""
    out = {
        "ts": time.time(),
        "pid": os.getpid(),
        "synapse_version": None,
        "dispatch_waits": None,
        "main_thread_direct": None,
        "tool_durations": None,
        "freeze": None,
        "live_metrics_latest": None,
    }
    try:
        import synapse
        out["synapse_version"] = getattr(synapse, "__version__", None)
    except Exception:
        pass

    # C6 enqueue->start histogram — module-level, always collectable.
    try:
        from .main_thread import dispatch_wait_stats
        out["dispatch_waits"] = dispatch_wait_stats()
    except Exception:
        out["dispatch_waits_absent"] = "main_thread stats unavailable"

    # C6 (continued) — main-thread DIRECT-path fn() duration. The dominant
    # panel/bridge inline path short-circuits run_on_main and never samples the
    # dispatch-wait histogram; this surface attributes it. Module-level, always
    # collectable.
    try:
        from .main_thread import main_thread_direct_stats
        out["main_thread_direct"] = main_thread_direct_stats()
    except Exception:
        out["main_thread_direct_absent"] = "main_thread stats unavailable"

    # Per-tool duration histogram — lives on the live handler instance.
    try:
        handler = _peek_live_handler()
        if handler is not None:
            out["tool_durations"] = handler.tool_duration_stats()
    except Exception:
        pass
    if out["tool_durations"] is None:
        out["tool_durations_absent"] = "no live handler"

    # Freeze chain — peek the module global; get_freeze_chain() constructs.
    try:
        from . import freeze_chain
        chain = getattr(freeze_chain, "_chain", None)
        if chain is not None:
            out["freeze"] = chain.stats()
    except Exception:
        pass
    if out["freeze"] is None:
        out["freeze_absent"] = "freeze chain not constructed"

    # Live-metrics ring — the hwebserver transport (dominant path) or the legacy
    # websocket server may construct + feed one. Peek both; never construct.
    try:
        agg = _peek_live_aggregator()
        snap = agg.latest() if agg is not None else None
        if snap is not None:
            from .live_metrics import snapshot_to_dict
            out["live_metrics_latest"] = snapshot_to_dict(snap)
    except Exception:
        pass
    if out["live_metrics_latest"] is None:
        out["live_metrics_latest_absent"] = (
            "no metrics aggregator running (none constructed, or no snapshot collected yet)"
        )
    return out


def _prune_freeze_dumps(directory: str, keep: int = FREEZE_DUMP_KEEP) -> None:
    """Keep the newest *keep* freeze_dump_*.json files; remove the rest."""
    try:
        dumps = [
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.startswith(FREEZE_DUMP_PREFIX) and name.endswith(".json")
        ]
        dumps.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
        for stale in dumps[keep:]:
            try:
                os.remove(stale)
            except OSError:
                pass
    except Exception:
        pass


def flush_telemetry(reason: str = "periodic", dir_path: Optional[str] = None) -> Optional[str]:
    """Write one telemetry snapshot to disk. Returns the path or None.

    reason == "periodic": atomic overwrite of ``telemetry.json`` (tmp in the
    same dir + os.replace — the bridge_endpoint idiom). Any other reason
    (e.g. "sustained_freeze"): a NEW ``freeze_dump_<UTC>.json`` evidence
    file, then prune to the newest 5 — bounded evidence the periodic flush
    can never overwrite. Never raises.
    """
    try:
        if dir_path is None:
            from ..core.logfile import log_dir
            dir_path = log_dir()
        os.makedirs(dir_path, exist_ok=True)

        data = collect_telemetry()
        data["reason"] = reason
        blob = json.dumps(data, sort_keys=True, default=str).encode("utf-8")

        if reason == "periodic":
            target = os.path.join(dir_path, TELEMETRY_FILENAME)
            fd, tmp_path = tempfile.mkstemp(
                prefix=".telemetry-", suffix=".tmp", dir=dir_path
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(blob)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                os.replace(tmp_path, target)
            except Exception:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except OSError:
                    pass
                return None
            return target

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target = os.path.join(dir_path, f"{FREEZE_DUMP_PREFIX}{stamp}.json")
        with open(target, "wb") as f:
            f.write(blob)
        _prune_freeze_dumps(dir_path)
        return target
    except Exception:
        logger.debug("Telemetry flush failed (best-effort)", exc_info=True)
        return None


def start_periodic_flush(interval_s: Optional[float] = None) -> bool:
    """Start the module-singleton periodic flusher (idempotent under lock).

    Daemon thread, Event.wait loop (the live_metrics MetricsAggregator
    idiom). Returns True when a flusher is running, False when disabled
    (interval <= 0) or on failure. Never raises.
    """
    global _flush_thread
    try:
        if interval_s is None:
            interval_s = flush_interval_s()
        if interval_s <= 0:
            return False
        with _flush_lock:
            if _flush_thread is not None and _flush_thread.is_alive():
                return True
            _flush_stop.clear()
            wait_s = float(interval_s)

            def _run():
                while not _flush_stop.wait(wait_s):
                    flush_telemetry(reason="periodic")

            thread = threading.Thread(
                target=_run, daemon=True, name="Synapse-TelemetryFlush"
            )
            _flush_thread = thread
            thread.start()
            return True
    except Exception:
        logger.debug("Telemetry flush thread start failed", exc_info=True)
        return False


def stop_periodic_flush() -> None:
    """Test/shutdown helper — signal the flusher and clear the singleton."""
    global _flush_thread
    with _flush_lock:
        _flush_stop.set()
        thread, _flush_thread = _flush_thread, None
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
