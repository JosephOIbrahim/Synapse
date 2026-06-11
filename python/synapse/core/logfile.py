"""
Rotating file log for the in-Houdini SYNAPSE process (M3-C).

Before this module, ZERO logging FileHandlers existed in production code:
everything >= WARNING fell through to ``logging.lastResort`` (the unsaved
Houdini console) and INFO and below were dropped outright — every crash and
freeze the resilience stack exists to explain left no durable evidence.

One mechanism, three idempotent callers (hwebserver_adapter.start_hwebserver,
start_hwebserver.main, the panel's D3 freeze-heartbeat init block). The
handler attaches to ``logging.getLogger("synapse")`` ONLY — never root — so
Houdini/vendor/httpcore noise is never captured and console behavior is
unchanged (propagation untouched; lastResort still prints WARNING+ only).

Deliberately env-configured, NOT show_config: logging must bootstrap
headless/pre-hou and is machine-scoped, while ``resolve_show_dirs()`` is
hou-coupled main-thread-only (show_config.py). The external stdio
mcp_server.py process keeps its own stderr logging — two processes, two
trails (RotatingFileHandler is not multi-process safe on Windows).

Zero ``hou``. Never raises — a logging failure must never break startup.
"""

import logging
import logging.handlers
import os
import threading
from typing import Optional

_ENV_DIR = "SYNAPSE_LOG_DIR"
# "0"/"false" disables; default on
_ENV_DISABLE = "SYNAPSE_FILE_LOG"

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3  # worst case ~20 MB on disk
LOG_FILENAME = "synapse.log"

# Same record format as the external mcp_server.py stderr trail.
_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Module singleton (freeze_chain._chain idiom): one handler per process.
_lock = threading.Lock()
_handler: Optional[logging.handlers.RotatingFileHandler] = None
_path: Optional[str] = None


def log_dir() -> str:
    """Resolve the log directory: ``$SYNAPSE_LOG_DIR`` else ``~/.synapse/logs``."""
    override = os.environ.get(_ENV_DIR, "").strip()
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".synapse", "logs")


def file_logging_disabled() -> bool:
    """True when the operator opted out via ``SYNAPSE_FILE_LOG=0`` (or "false")."""
    return os.environ.get(_ENV_DISABLE, "").strip().lower() in ("0", "false")


def ensure_file_logging() -> Optional[str]:
    """Attach the rotating file handler to the ``synapse`` logger (idempotent).

    Returns the log file path, or None when disabled or on any failure.
    Safe to call from every bootstrap site — the first caller wins, later
    calls return the existing path. MUST never raise: a broken filesystem
    or locked-down home dir cannot be allowed to break startup.
    """
    global _handler, _path
    try:
        with _lock:
            if _handler is not None:
                return _path
            if file_logging_disabled():
                return None
            directory = log_dir()
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, LOG_FILENAME)
            handler = logging.handlers.RotatingFileHandler(
                path,
                maxBytes=DEFAULT_MAX_BYTES,
                backupCount=DEFAULT_BACKUP_COUNT,
                encoding="utf-8",
                delay=True,  # no file until the first record
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter(_FORMAT))
            synapse_logger = logging.getLogger("synapse")
            synapse_logger.addHandler(handler)
            # INFO records must reach the file. Only lift a NOTSET level —
            # an operator/test-configured level is respected.
            if synapse_logger.level == logging.NOTSET:
                synapse_logger.setLevel(logging.INFO)
            _handler = handler
            _path = path
            return path
    except Exception:
        return None


def reset_file_logging() -> None:
    """Test/diagnostic helper — detach + close the handler and clear the
    singleton so the next ensure_file_logging() re-attaches."""
    global _handler, _path
    with _lock:
        if _handler is not None:
            try:
                logging.getLogger("synapse").removeHandler(_handler)
                _handler.close()
            except Exception:
                pass
        _handler = None
        _path = None
