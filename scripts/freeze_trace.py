"""SYNAPSE freeze tracer — non-invasive live diagnostic.

Run inside Houdini's Python Shell (after the SYNAPSE panel is already open):

    exec(open(r'C:\\Users\\User\\SYNAPSE\\scripts\\freeze_trace.py').read())

Then type "make a box" in the panel. It wraps the tool-execution path with
ENTER/EXIT logging (tool name, gate level, thread) and flushes every line to
disk, so the LAST line written before a freeze pinpoints exactly where — and on
which thread — execution blocks. It changes NO behavior: every wrapper calls the
original and returns its result unchanged. Pure observation.

Log: <repo>/.synapse/freeze_trace.log  (gitignored; readable after a force-kill).

This is the "verify live first" step — the trace is hypothesis-agnostic: whatever
the real freeze point is, it shows up as the last ENTER with no matching EXIT.
"""

import os
import time
import threading
import functools

_LOG = os.path.join(os.environ.get("SYNAPSE_ROOT", r"C:\Users\User\SYNAPSE"),
                    ".synapse", "freeze_trace.log")


def _ensure_log():
    os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    with open(_LOG, "w", encoding="utf-8") as f:
        f.write("# SYNAPSE freeze trace — %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))


def _log(msg):
    line = "%9.3f | %-13s | %s\n" % (time.monotonic(), threading.current_thread().name, msg)
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())   # survive a force-kill during the freeze
    except Exception:
        pass
    try:
        print("[FREEZE-TRACE]", msg.split(" | ")[-1] if " | " in msg else msg)
    except Exception:
        pass


def _wrap(owner, name, label, detail=None):
    """Wrap owner.name to log ENTER/EXIT/RAISE. Idempotent; behavior-preserving."""
    orig = getattr(owner, name, None)
    if orig is None:
        _log("SKIP (missing): %s" % label)
        return
    if getattr(orig, "_ft_wrapped", False):
        return

    @functools.wraps(orig)
    def w(*a, **k):
        try:
            d = detail(*a, **k) if detail else ""
        except Exception:
            d = "<detail?>"
        _log("ENTER %-34s %s" % (label, d))
        try:
            r = orig(*a, **k)
            _log("EXIT  %-34s -> %s" % (label, type(r).__name__))
            return r
        except BaseException as e:
            _log("RAISE %-34s -> %r" % (label, e))
            raise

    w._ft_wrapped = True
    setattr(owner, name, w)
    _log("patched: %s" % label)


def install():
    _ensure_log()
    # 1) Which tool does Claude actually call? (emission vs execution bisect)
    try:
        from synapse.panel import claude_worker as cw
        _wrap(cw.ClaudeWorker, "_execute_tool_block", "worker._execute_tool_block",
              lambda self, block, *a, **k: "TOOL=%s" % (block or {}).get("name"))
        _wrap(cw, "try_mcp_tool_call", "try_mcp_tool_call",
              lambda name, args, *a, **k: "tool=%s" % name)
    except Exception as e:
        _log("patch claude_worker FAILED: %r" % e)
    # 2) Signal path -> main-thread executor
    try:
        from synapse.panel import tool_executor as te
        _wrap(te.ToolExecutor, "execute_tool", "ToolExecutor.execute_tool",
              lambda self, req, *a, **k: "tool=%s" % getattr(req, "tool_name", "?"))
    except Exception as e:
        _log("patch tool_executor FAILED: %r" % e)
    # 3) Bridge adapter
    try:
        from synapse.panel import bridge_adapter as ba
        _wrap(ba, "execute_through_bridge", "execute_through_bridge",
              lambda tool, *a, **k: "tool=%s" % tool)
    except Exception as e:
        _log("patch bridge_adapter FAILED: %r" % e)
    # 4) Consent gate + the suspected FREEZE POINT
    try:
        from shared.bridge import LosslessExecutionBridge as LEB
        _wrap(LEB, "_check_consent", "bridge._check_consent",
              lambda self, op, *a, **k: "op=%s gate=%s" % (op.operation_type, op.gate_level))
        _wrap(LEB, "_wait_for_decision", ">>> bridge._WAIT_FOR_DECISION <<<",
              lambda self, proposal, timeout=None, *a, **k: "timeout=%ss (BLOCKS this thread)" % timeout)
    except Exception as e:
        _log("patch shared.bridge FAILED: %r" % e)
    # 5) Main-thread hop (catches a hou-dispatch freeze)
    try:
        from synapse.server import main_thread as mt
        _wrap(mt, "run_on_main", "run_on_main",
              lambda fn, timeout=None, *a, **k: "timeout=%s" % timeout)
    except Exception as e:
        _log("patch main_thread FAILED: %r" % e)

    _log("=== TRACER INSTALLED — now type 'make a box' in the panel ===")
    print("\n[FREEZE-TRACE] Installed. Log file:\n  %s" % _LOG)
    print("[FREEZE-TRACE] Now type 'make a box' in the SYNAPSE panel.")
    print("[FREEZE-TRACE] If it freezes, the LAST line in the log is the culprit "
          "(an ENTER with no matching EXIT).")
    print("[FREEZE-TRACE] Force-kill Houdini if needed — the log is fsync'd, it survives.")


install()
