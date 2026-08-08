"""FRZ — attributed freeze probe. Run the SAME line twice: arm, then report.

    exec(open(r'C:\\Users\\User\\SYNAPSE\\scripts\\frz_probe.py').read())

First run ARMS (zeroes every main-thread histogram and stamps a marker).
Send one prompt in the SYNAPSE panel and let the freeze happen.
Second run REPORTS — it prints an attribution ladder naming which layer held
Houdini's main thread, and writes the same content to a file that survives a
force-kill.

WHY "RUN IT TWICE" RATHER THAN A TIMER
--------------------------------------
A QTimer-based auto-report would post work to the very event loop under
investigation, perturbing the thing being measured. Arm/report is inert between
the two runs: it adds nothing to the main thread while the freeze occurs.

WHY EVERY HELPER TAKES EXPLICIT ARGUMENTS
-----------------------------------------
Houdini's Python Shell may execute this under ``exec(code, G, L)`` with
``G is not L``. Under that split scope, module-level names are NOT visible from
inside functions defined in the same file. Every function below therefore
receives what it needs as a parameter, and all orchestration happens at top
level. (Learned the hard way — see the bridge split-scope note.)

READ-ONLY. This script changes no behaviour and fixes nothing: it resets
counters and prints them. It cannot unfreeze Houdini.
"""

import json
import os
import sys
import time

_STATE = os.path.join(
    os.environ.get("SYNAPSE_ROOT", r"C:\Users\User\SYNAPSE"),
    ".synapse", "frz_probe_state.json",
)
_REPORT = os.path.join(
    os.environ.get("SYNAPSE_ROOT", r"C:\Users\User\SYNAPSE"),
    ".synapse", "frz_report.txt",
)


def _try(fn, *a, **k):
    """Call fn, returning (ok, value_or_error). Never raises."""
    try:
        return True, fn(*a, **k)
    except Exception as exc:
        return False, repr(exc)


def _collect(mods):
    """Snapshot every main-thread instrument. `mods` is the imported-module map."""
    out = {}
    mt = mods.get("main_thread")
    mg = mods.get("marshal_guard")
    rt = mods.get("result_telemetry")
    te = mods.get("tool_executor")
    if mt is not None:
        out["dispatch_waits"] = _try(mt.dispatch_wait_stats)[1]
        out["main_thread_direct"] = _try(mt.main_thread_direct_stats)[1]
        out["main_thread_hold"] = _try(mt.main_thread_hold_stats)[1]
        out["stall_state"] = _try(mt.stall_state)[1]
    if mg is not None:
        out["marshal_guard"] = _try(mg.guard_stats)[1]
        out["guard_events"] = _try(mg.guard_events, 20)[1]
    if rt is not None:
        out["panel_result_render"] = _try(rt.result_render_stats)[1]
    if te is not None:
        out["panel_inline"] = _try(te.panel_inline_stats)[1]
    return out


def _reset(mods):
    """Zero every instrument that exposes a reset. Returns the list zeroed."""
    done = []
    mt = mods.get("main_thread")
    mg = mods.get("marshal_guard")
    rt = mods.get("result_telemetry")
    te = mods.get("tool_executor")
    for owner, name in (
        (mt, "reset_dispatch_wait_stats"),
        (mt, "reset_main_thread_direct_stats"),
        (mt, "reset_main_thread_hold_stats"),
        (mg, "reset_guard_state"),
        (rt, "reset_result_render_stats"),
        (te, "reset_panel_inline_stats"),
    ):
        if owner is None:
            continue
        fn = getattr(owner, name, None)
        if fn is None:
            continue
        ok, _ = _try(fn)
        if ok:
            done.append(name)
    return done


def _ms(stats, key="max_ms"):
    try:
        return float((stats or {}).get(key, 0.0) or 0.0)
    except Exception:
        return 0.0


def _ladder(snap):
    """Build the attribution ladder — ordered rungs, worst hold per layer.

    Returns a list of (rung, layer, max_ms, count, note). Ordered so the FIRST
    rung with a number in the freeze band is the attribution.
    """
    rows = []
    dw = snap.get("dispatch_waits") or {}
    rows.append(("1", "worker->main WAKE latency (dispatch_wait)",
                 _ms(dw), dw.get("count", 0),
                 "high here = main was ALREADY busy with something else"))
    md = snap.get("main_thread_direct") or {}
    rows.append(("2", "run_on_main fast path 2: inline fn() on main",
                 _ms(md), md.get("count", 0),
                 "high here = a payload ran inline on the GUI thread"))
    mh = snap.get("main_thread_hold") or {}
    rows.append(("3", "deferred payload HOLD on main (OCC)",
                 _ms(mh), mh.get("count", 0),
                 "high here = a marshalled tool payload occupied main; "
                 "slowest_label names it"))
    pi = snap.get("panel_inline") or {}
    rows.append(("4", "panel inline TOOL dispatch (Qt slot)",
                 _ms(pi), pi.get("count", 0),
                 "high here = full inline tool dispatch"))
    prr = snap.get("panel_result_render") or {}
    for phase in ("send", "stream", "finalize", "append", "review"):
        slot = prr.get(phase) or {}
        rows.append(("5." + phase, "result path: %s" % phase,
                     _ms(slot), slot.get("count", 0),
                     "payload=%s chars, document=%s chars at the worst sample" % (
                         slot.get("payload_chars_at_max_ms", 0),
                         slot.get("doc_chars_at_max_ms", 0))))
    return rows


def _render(snap, armed_at, now):
    lines = []
    lines.append("=" * 78)
    lines.append("FRZ ATTRIBUTED FREEZE REPORT")
    lines.append("=" * 78)
    lines.append("armed  : %s" % time.strftime("%Y-%m-%d %H:%M:%S",
                                               time.localtime(armed_at)))
    lines.append("report : %s" % time.strftime("%Y-%m-%d %H:%M:%S",
                                               time.localtime(now)))
    lines.append("window : %.1f s" % (now - armed_at))
    lines.append("")
    lines.append("ATTRIBUTION LADDER - the first rung showing a hold in the")
    lines.append("freeze band is where the main thread actually went.")
    lines.append("")
    lines.append("  %-11s %-44s %10s %7s" % ("rung", "layer", "max_ms", "count"))
    lines.append("  " + "-" * 76)
    hits = []
    for rung, layer, max_ms, count, note in _ladder(snap):
        mark = "  <<<" if max_ms >= 1000.0 else ""
        lines.append("  %-11s %-44s %10.1f %7s%s" % (
            rung, layer[:44], max_ms, count, mark))
        if max_ms >= 1000.0:
            hits.append((rung, layer, max_ms, note))
    lines.append("")
    if hits:
        lines.append("HOLDS OVER 1000 ms:")
        for rung, layer, max_ms, note in hits:
            lines.append("  rung %s - %s" % (rung, layer))
            lines.append("      %.0f ms. %s" % (max_ms, note))
    else:
        lines.append("NO INSTRUMENTED LAYER SHOWS A HOLD OVER 1000 ms.")
        lines.append("")
        lines.append("  That is a RESULT, not a failed run. If the freeze was")
        lines.append("  observed during this window and every rung is quiet, the")
        lines.append("  cost is outside all Python instrumentation - i.e. native")
        lines.append("  Qt layout, a Houdini cook, or a C-level call. Say so")
        lines.append("  plainly rather than re-running until a number appears.")

    mg = snap.get("marshal_guard") or {}
    lines.append("")
    lines.append("GUARD: mode=%s inline_budget=%ss violations=%s inline_overruns=%s"
                 % (mg.get("mode"), mg.get("inline_budget_s"),
                    mg.get("violations"), mg.get("inline_overruns")))
    ss = snap.get("stall_state") or {}
    lines.append("STALL: stalled=%s consecutive_timeouts=%s"
                 % (ss.get("stalled"), ss.get("consecutive_timeouts")))
    ev = snap.get("guard_events") or []
    if ev:
        lines.append("")
        lines.append("GUARD LEDGER (newest last):")
        for e in ev[-10:]:
            lines.append("  %s where=%s elapsed_s=%s" % (
                e.get("kind"), e.get("where"), e.get("elapsed_s")))
    mh = snap.get("main_thread_hold") or {}
    if mh.get("slowest_label"):
        lines.append("")
        lines.append("SLOWEST DEFERRED PAYLOAD LABEL: %s" % mh.get("slowest_label"))
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level orchestration — everything below runs in the caller's scope.
# ---------------------------------------------------------------------------

_mods = {}
for _key, _path in (
    ("main_thread", "synapse.server.main_thread"),
    ("marshal_guard", "synapse.server.marshal_guard"),
    ("result_telemetry", "synapse.panel.result_telemetry"),
    ("tool_executor", "synapse.panel.tool_executor"),
):
    try:
        __import__(_path)
        _mods[_key] = sys.modules[_path]
    except Exception as _exc:
        _mods[_key] = None
        print("[frz] WARNING: %s unavailable (%r)" % (_path, _exc))

try:
    os.makedirs(os.path.dirname(_STATE), exist_ok=True)
except Exception:
    pass

_armed_at = None
if os.path.exists(_STATE):
    try:
        with open(_STATE, "r", encoding="utf-8") as _f:
            _armed_at = json.load(_f).get("armed_at")
    except Exception:
        _armed_at = None

if _armed_at is None:
    # ---- FIRST RUN: ARM ---------------------------------------------------
    _zeroed = _reset(_mods)
    _now = time.time()
    try:
        with open(_STATE, "w", encoding="utf-8") as _f:
            json.dump({"armed_at": _now}, _f)
    except Exception as _exc:
        print("[frz] could not write state file: %r" % (_exc,))
    print("")
    print("[frz] ARMED at %s" % time.strftime("%H:%M:%S", time.localtime(_now)))
    print("[frz] zeroed: %s" % (", ".join(_zeroed) or "NOTHING — instruments missing"))
    if not _zeroed:
        print("[frz] STOP. No instrument could be reset, so any report would be")
        print("[frz] meaningless. Check that the SYNAPSE panel is open and that")
        print("[frz] synapse is importable in this session.")
    else:
        print("")
        print("[frz] NOW: send ONE prompt in the SYNAPSE panel and let it freeze.")
        print("[frz] THEN: run the exact same line again to get the report:")
        print("")
        print("      exec(open(r'%s').read())"
              % os.path.join(os.environ.get("SYNAPSE_ROOT", r"C:\Users\User\SYNAPSE"),
                             "scripts", "frz_probe.py"))
        print("")
else:
    # ---- SECOND RUN: REPORT ----------------------------------------------
    _snap = _collect(_mods)
    _text = _render(_snap, _armed_at, time.time())
    print("")
    print(_text)
    try:
        with open(_REPORT, "w", encoding="utf-8") as _f:
            _f.write(_text)
            _f.write("\n\nRAW SNAPSHOT\n")
            _f.write(json.dumps(_snap, indent=2, default=str))
            _f.flush()
            os.fsync(_f.fileno())   # survive a force-kill
        print("")
        print("[frz] written: %s" % _REPORT)
    except Exception as _exc:
        print("[frz] could not write report: %r" % (_exc,))
    try:
        os.remove(_STATE)           # disarm, so the next run arms again
        print("[frz] disarmed — run the line again to start a fresh window.")
    except Exception:
        pass
