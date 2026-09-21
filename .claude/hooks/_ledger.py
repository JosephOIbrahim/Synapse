"""Hook-fire ledger: append-only JSONL of every Claude Code hook invocation.

Zero decisions live here. This module never allows, denies, blocks or
exits; it only records what a hook decided and how long it took.

Row shape (one JSON object per line):
    {ts, event, script, decision, ms, session, extra}

Destination: ``~/.synapse/hooks.jsonl`` by default, overridable with the
``SYNAPSE_HOOKS_LEDGER`` environment variable (tests point it at a temp
path). Never ``synapse.log``, never ``harness/jev/ledger``.

Every error is swallowed: a broken ledger must never break a hook.
"""

import json
import os
import time

ENV_LEDGER_PATH = "SYNAPSE_HOOKS_LEDGER"
ENV_SESSION = "CLAUDE_SESSION_ID"


def ledger_path():
    """Resolve the ledger file path (env override wins). Never raises."""
    try:
        override = os.environ.get(ENV_LEDGER_PATH, "").strip()
        if override:
            return override
        return os.path.join(os.path.expanduser("~"), ".synapse", "hooks.jsonl")
    except Exception:
        return ""


def record(event, script, decision, ms, extra=None, session=None):
    """Append one row to the hook ledger. Swallows every error.

    event    -- hook event name (e.g. "PreToolUse", "Stop")
    script   -- hook script name (e.g. "guard-edit-targets")
    decision -- what the hook decided, as a short string ("allow", "deny",
                "exit:2", "ok"); recorded verbatim, never interpreted
    ms       -- wall-clock duration of the hook fire in milliseconds
    extra    -- optional JSON-serialisable dict of context
    session  -- optional session id; falls back to CLAUDE_SESSION_ID env
    """
    try:
        path = ledger_path()
        if not path:
            return
        if session is None:
            session = os.environ.get(ENV_SESSION, "") or ""
        row = {
            "ts": time.time(),
            "event": str(event),
            "script": str(script),
            "decision": str(decision),
            "ms": round(float(ms), 3),
            "session": str(session),
            "extra": extra if extra is not None else {},
        }
        line = json.dumps(row, sort_keys=True, default=str)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
