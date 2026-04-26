"""Spike 3.2 — Scene-load API audit (paste-into-Houdini introspection).

Empirically capture the actual scene-load event surface in SideFX
Houdini 21.0.671 so Spike 3.2's auto-warm scaffold can be coded against
verified reality. Anchors: ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard
API verification gate; Sprint 3 hard invariant #6 — *dir() introspection
in live Houdini first, blueprint code second.*

What this audit pins
--------------------
The TopsEventBridge sketch in ``CONTINUATION_INSIDE_OUT_TOPS.md`` (lines
~229–246) and Spike 3.1's design assume three things about the scene-
load surface that have NOT been runtime-verified together:

  1. ``hou.hipFile.addEventCallback`` returns nothing useful (handle-less
     subscription; removal by callback identity). Spike 3.0 § 3.1 already
     refuted the "removable handle" hypothesis on dir() inspection alone;
     this audit re-confirms by **calling** the function and recording the
     actual return value.

  2. ``hou.hipFileEventType.AfterLoad`` is the right event for re-warm.
     Spike 3.0 § 2.9 confirmed the enum member exists. This audit
     confirms it actually FIRES during a real File → Open and enumerates
     the full member set so Spike 3.2 can hard-code integer values
     (matches ``python/synapse/host/tops_bridge.py:78-90`` pattern).

  3. **Thread context of the callback fire** — never previously verified.
     This is the load-bearing finding: if AfterLoad fires on the main
     thread, the auto-warm scaffold can call ``hou.*`` directly. If it
     fires on a worker thread, every reaction must marshal through
     ``hdefereval``. The bridge design changes either way — but only one
     way is right, and it is empirical.

Plus the contract probe:

  4. Callback identity / removal — does ``addEventCallback(fn) +
     addEventCallback(fn)`` register once or twice? Determines whether
     Spike 3.2 must guard against double-subscription explicitly.

How to use
----------
Inside graphical Houdini 21.0.671 (Joe operates — never the agent):

    1. Windows → Python Source Editor (NOT Python Shell — script has
       class definitions; pasting line-by-line into the Shell fails per
       Spike 3.0 lesson learned).
    2. File → Open → docs/sprint3/spike_3_2_scene_load_audit_script.py
    3. Apply (Ctrl+Enter) to run it.
    4. Read the ARMED banner — script will instruct: "load any .hip".
    5. File → Open → any small .hip file (or, if no .hip handy, File →
       New then File → Open of an empty/recent file). Goal: trigger
       AfterLoad.
    6. Read the second SUMMARY block printed when the probe finalizes.
    7. Open the report .txt and paste each section into the receiving
       doc: ``docs/sprint3/spike_3_2_scene_load_audit.md``.

Output strategy
---------------
HYBRID (file + shell summary). The synchronous phases (§1, §2, §4, §5)
run at script-load. The probe is then ARMED and ``main()`` returns —
Houdini stays interactive. When AfterLoad fires (or 300s timeout
elapses), the asynchronous probe finalizes: appends §3 to the in-memory
report, unsubscribes the callback, writes the file, and prints the
second SUMMARY block.

File path: ``$HIP/spike_3_2_scene_load_audit_<stamp>.txt`` when ``$HIP``
is set, else ``~/.synapse/spike_3_2_scene_load_audit_<stamp>.txt``.

Constraints
-----------
- Read-only. The only file write is the report .txt. No node creation,
  no parameter sets, no scene mutations. The dedup test subscribes and
  unsubscribes a noop callback under best-effort cleanup. The
  thread-context probe captures-and-unsubscribes from the same callback
  invocation.
- Idempotent on re-paste AFTER the prior probe finalized. Re-paste
  WHILE the prior probe is still armed leaks the prior callback; the
  printed banner offers a manual abort path:
  ``hou.session._SPIKE_3_2_PROBE.abort()``.
- Stdlib + ``hou`` only. No new dependencies.
- Python 3.11 (Houdini 21.0.671's interpreter).
"""
from __future__ import annotations

import datetime
import inspect
import os
import sys
import threading
import traceback
from pathlib import Path

# `hou` is always present inside Houdini's Python interpreter — no guard.
import hou


# ── Constants ────────────────────────────────────────────────────────

BANNER = "=" * 68
TITLE = "=== SPIKE 3.2 SCENE-LOAD AUDIT ==="
ARMED = "=== AUDIT ARMED — load a .hip to fire ==="
EVENT_BANNER = "=== EVENT CAPTURED ==="
TIMEOUT_BANNER = "=== AUDIT TIMEOUT — no AfterLoad captured ==="
DONE = "=== AUDIT COMPLETE ==="
DOC_TRUNCATE = 500   # Per-item __doc__ char cap.
REPR_TRUNCATE = 200  # Per-item repr char cap.
TIMEOUT_SECONDS = 300  # 5 minutes — fallback if no scene load occurs.
KEEP_DUNDERS = {"__call__", "__iter__", "__enter__", "__exit__", "__await__"}
PROBE_GLOBAL_NAME = "_SPIKE_3_2_PROBE"


# ── Output sink (named-bucket variant) ───────────────────────────────

class AuditSink:
    """Buffered text writer with named section buckets so §3 (the
    asynchronous thread-context probe result) can be written into its
    correct position even though it lands chronologically last.

    Disk order: ``header → 1 → 2 → 3 → 4 → 5 → summary``.

    The file is the durable record; stdout is liveness signal only.
    Houdini's Python Shell can truncate long output, hence the split.
    """

    SECTION_ORDER = ("header", "1", "2", "3", "4", "5", "summary")

    def __init__(self) -> None:
        self._buckets: dict[str, list[str]] = {k: [] for k in self.SECTION_ORDER}
        self._current = "header"
        self.surfaces_resolved: list[str] = []
        self.surfaces_missing: list[str] = []
        self.errors: list[tuple[str, str]] = []

    def begin_section(self, key: str, title: str) -> None:
        if key not in self._buckets:
            raise KeyError(f"unknown section: {key}")
        self._current = key
        self._buckets[key].append("")
        self._buckets[key].append("-" * 68)
        self._buckets[key].append(f"## {title}")
        self._buckets[key].append("-" * 68)

    def writeln(self, line: str = "") -> None:
        self._buckets[self._current].append(line)

    def text(self) -> str:
        out: list[str] = []
        for key in self.SECTION_ORDER:
            out.extend(self._buckets[key])
        return "\n".join(out) + "\n"


# ── Introspection helpers (mirror Spike 3.0 audit script) ────────────

def _safe_repr(obj: object, limit: int = REPR_TRUNCATE) -> str:
    try:
        s = repr(obj)
    except Exception as exc:  # noqa: BLE001
        return f"<repr failed: {type(exc).__name__}: {exc}>"
    return s[:limit] + "...[truncated]" if len(s) > limit else s


def _safe_doc(obj: object) -> str:
    doc = getattr(obj, "__doc__", None)
    if not doc:
        return "<no doc>"
    doc = inspect.cleandoc(doc)
    return doc[:DOC_TRUNCATE] + "...[truncated]" if len(doc) > DOC_TRUNCATE else doc


def _safe_signature(obj: object) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        # Builtins, Boost.Python wrappers, slot wrappers — common in hou.
        return f"<no signature: {type(obj).__name__}>"
    except Exception as exc:  # noqa: BLE001
        return f"<signature error: {type(exc).__name__}: {exc}>"


def _filtered_dir(obj: object) -> list[str]:
    """``dir(obj)`` minus private ``_`` prefixes, preserving load-bearing
    dunders (``__call__``, ``__iter__``, ``__enter__``, ``__exit__``,
    ``__await__``)."""
    out: list[str] = []
    for name in dir(obj):
        if name.startswith("_"):
            if name in KEEP_DUNDERS:
                out.append(name)
            continue
        out.append(name)
    return out


def _resolve(path: str) -> object | None:
    """Resolve dotted ``path`` against globals/sys.modules/__import__.
    Returns ``None`` on any failure — the script never raises mid-audit
    just because a name doesn't exist (that *is* the audit signal)."""
    parts = path.split(".")
    root = parts[0]
    obj: object | None = globals().get(root) or sys.modules.get(root)
    if obj is None:
        try:
            obj = __import__(root)
        except Exception:
            return None
    for part in parts[1:]:
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None
    return obj


def dump_surface(sink: AuditSink, label: str, dotted: str) -> None:
    """Resolve ``dotted`` and write a structured dump: type, repr,
    signature (when callable), ``__doc__`` excerpt, filtered ``dir()``,
    per-attribute signatures. Missing names land in
    ``sink.surfaces_missing`` with a clear note — that's an audit
    finding, not a script failure."""
    sink.writeln()
    sink.writeln(f"### {label}")
    sink.writeln()
    sink.writeln(f"**Resolved path:** ``{dotted}``")
    sink.writeln()

    obj = _resolve(dotted)
    if obj is None:
        sink.writeln(f"**STATUS:** NOT RESOLVABLE — ``{dotted}`` does not exist.")
        sink.writeln()
        sink.writeln(
            "Spike 3.2 cannot reference this name. Scaffold revision "
            "required before any code lands."
        )
        sink.surfaces_missing.append(dotted)
        return

    sink.surfaces_resolved.append(dotted)
    sink.writeln(f"**STATUS:** RESOLVED")
    sink.writeln(f"**Type:** ``{type(obj).__name__}``")
    sink.writeln(f"**Repr:** ``{_safe_repr(obj)}``")
    sink.writeln()
    if callable(obj):
        sink.writeln(f"**Signature:** ``{_safe_signature(obj)}``")
        sink.writeln()
    sink.writeln("**__doc__:**")
    sink.writeln("```")
    sink.writeln(_safe_doc(obj))
    sink.writeln("```")
    sink.writeln()

    names = _filtered_dir(obj)
    sink.writeln(f"**dir() — {len(names)} attributes:**")
    sink.writeln("```")
    for name in names:
        try:
            attr = getattr(obj, name)
        except Exception as exc:  # noqa: BLE001
            sink.writeln(f"  {name}  <getattr failed: {type(exc).__name__}>")
            continue
        type_name = type(attr).__name__
        if callable(attr):
            sink.writeln(f"  {name}{_safe_signature(attr)}  -> {type_name}")
        else:
            sink.writeln(f"  {name} = {_safe_repr(attr, limit=80)}  -> {type_name}")
    sink.writeln("```")


def dump_enum_like(sink: AuditSink, label: str, dotted: str) -> None:
    """Specialised dump for enum-shaped surfaces (``hipFileEventType``).
    Lists every public member with its value. Falls back to noting
    missing if the name doesn't resolve."""
    sink.writeln()
    sink.writeln(f"### {label}")
    sink.writeln()
    sink.writeln(f"**Resolved path:** ``{dotted}``")
    sink.writeln()
    obj = _resolve(dotted)
    if obj is None:
        sink.writeln(f"**STATUS:** NOT RESOLVABLE — ``{dotted}`` does not exist.")
        sink.surfaces_missing.append(dotted)
        return
    sink.surfaces_resolved.append(dotted)
    sink.writeln(f"**STATUS:** RESOLVED")
    sink.writeln(f"**Type:** ``{type(obj).__name__}``")
    sink.writeln()
    sink.writeln("**Members (public, value-bearing):**")
    sink.writeln("```")
    for name in _filtered_dir(obj):
        try:
            value = getattr(obj, name)
        except Exception as exc:  # noqa: BLE001
            sink.writeln(f"  {name}  <getattr failed: {type(exc).__name__}>")
            continue
        sink.writeln(f"  {name} = {_safe_repr(value, limit=120)}")
    sink.writeln("```")
    sink.writeln()
    sink.writeln("**__doc__:**")
    sink.writeln("```")
    sink.writeln(_safe_doc(obj))
    sink.writeln("```")


# ── Synchronous audit phases (§1, §2, §4, §5) ────────────────────────

def run_phase_1(sink: AuditSink) -> None:
    """§1. hou.hipFile.addEventCallback surface — dir() + live return-value probe."""
    sink.begin_section("1", "1. hou.hipFile.addEventCallback surface")
    sink.writeln()
    sink.writeln(
        "Watchlist: Spike 3.0 § 3.1 already refuted the bridge sketch's "
        "assumption that ``addEventCallback`` returns a removable handle "
        "(returns ``None``; removal is by callback-identity). This phase "
        "re-confirms in the scene-load scenario specifically AND adds a "
        "**return-value probe** by calling the function with a noop "
        "callback and recording exactly what comes back."
    )

    dump_surface(
        sink,
        "1.1 hou.hipFile.addEventCallback (function surface)",
        "hou.hipFile.addEventCallback",
    )

    # Live return-value probe: call addEventCallback, capture rv,
    # immediately unsubscribe. No event ever fires here.
    sink.writeln()
    sink.writeln("### 1.2 Return-value probe (live call)")
    sink.writeln()
    sink.writeln(
        "Subscribe a noop callback, capture the return value, immediately "
        "unsubscribe. No event fires; pure API contract probe."
    )
    sink.writeln()

    def _noop_for_returnvalue_probe(event_type):
        return  # no side effects

    return_value_repr = "<not captured>"
    return_value_type = "<not captured>"
    add_exception: str | None = None
    remove_result = "<not attempted>"

    try:
        rv = hou.hipFile.addEventCallback(_noop_for_returnvalue_probe)
        return_value_repr = _safe_repr(rv)
        return_value_type = type(rv).__name__
    except Exception as exc:  # noqa: BLE001
        add_exception = f"{type(exc).__name__}: {exc}"

    if add_exception is None:
        try:
            hou.hipFile.removeEventCallback(_noop_for_returnvalue_probe)
            remove_result = "ok"
        except Exception as exc:  # noqa: BLE001
            remove_result = f"{type(exc).__name__}: {exc}"

    sink.writeln("```")
    if add_exception is not None:
        sink.writeln(f"  add raised:           {add_exception}")
    else:
        sink.writeln(f"  return value (repr):  {return_value_repr}")
        sink.writeln(f"  return value (type):  {return_value_type}")
    sink.writeln(f"  remove result:        {remove_result}")
    sink.writeln("```")
    sink.writeln()
    sink.writeln(
        "**Implication for Spike 3.2:** if return value is ``None`` "
        "(expected, per Spike 3.0 § 3.1), the auto-warm scaffold MUST "
        "store the bound callback function reference itself (not a "
        "returned handle) and pass that same function reference to "
        "``hou.hipFile.removeEventCallback`` at teardown."
    )


def run_phase_2(sink: AuditSink) -> None:
    """§2. hou.hipFileEventType enum members — full member dump."""
    sink.begin_section("2", "2. hou.hipFileEventType enum members")
    sink.writeln()
    sink.writeln(
        "Watchlist: Spike 3.0 § 2.9 confirmed the enum exists with "
        "``AfterLoad`` member. This phase enumerates **every** member "
        "with its integer value so Spike 3.2's event filter can hard-"
        "code exact constants — matches the audit-verified-int pattern "
        "in ``python/synapse/host/tops_bridge.py:78-90`` (e.g. "
        "``_EVT_COOK_COMPLETE = 14``)."
    )
    dump_enum_like(
        sink,
        "2.1 hou.hipFileEventType (full member dump with values)",
        "hou.hipFileEventType",
    )


def run_phase_4(sink: AuditSink) -> None:
    """§4. Callback identity / removal — double-add + double-remove probe."""
    sink.begin_section("4", "4. Callback identity / removal behavior")
    sink.writeln()
    sink.writeln(
        "Test: subscribe the same callback function reference twice, "
        "then attempt removal twice. The outcome reveals whether "
        "``addEventCallback`` de-duplicates by identity (idempotent), "
        "treats each subscription as a distinct registration (FIFO "
        "removal), or rejects double-add outright."
    )
    sink.writeln()

    def _noop_for_dedup_probe(event_type):
        return  # no side effects

    results: dict[str, str] = {}

    try:
        hou.hipFile.addEventCallback(_noop_for_dedup_probe)
        results["first_add"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["first_add"] = f"{type(exc).__name__}: {exc}"

    try:
        hou.hipFile.addEventCallback(_noop_for_dedup_probe)
        results["second_add_same_fn"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["second_add_same_fn"] = f"{type(exc).__name__}: {exc}"

    try:
        hou.hipFile.removeEventCallback(_noop_for_dedup_probe)
        results["first_remove"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["first_remove"] = f"{type(exc).__name__}: {exc}"

    try:
        hou.hipFile.removeEventCallback(_noop_for_dedup_probe)
        results["second_remove"] = "ok"
    except Exception as exc:  # noqa: BLE001
        results["second_remove"] = f"{type(exc).__name__}: {exc}"

    # Best-effort sweep — make sure nothing leaks if the API is permissive.
    for _ in range(3):
        try:
            hou.hipFile.removeEventCallback(_noop_for_dedup_probe)
        except Exception:
            break

    sink.writeln("**Sequence of operations + outcomes:**")
    sink.writeln("```")
    for k, v in results.items():
        sink.writeln(f"  {k:<25} : {v}")
    sink.writeln("```")
    sink.writeln()
    sink.writeln("**Interpretation key:**")
    sink.writeln(
        "- If ``second_add_same_fn`` raised → API **rejects** double-add. "
        "Spike 3.2 must check before subscribing (e.g. ``if not "
        "self._registered: hou.hipFile.addEventCallback(...)``)."
    )
    sink.writeln(
        "- If ``second_add_same_fn`` ok AND ``second_remove`` raised → "
        "API **de-duplicates** by callback identity. Idempotent "
        "subscription is safe."
    )
    sink.writeln(
        "- If ``second_add_same_fn`` ok AND ``second_remove`` ok → API "
        "treats double-add as **two distinct registrations** (FIFO-style "
        "removal). Spike 3.2 must guard against double-subscription "
        "with an explicit bool flag or single-registration discipline."
    )


def run_phase_5(sink: AuditSink) -> None:
    """§5. Aux surface — hou.hipFile module, hou.hipFile.path,
    hou.hipFile.removeEventCallback, hou.applicationVersionString."""
    sink.begin_section(
        "5",
        "5. Aux surface (hipFile module, path, removeEventCallback, version)",
    )
    sink.writeln()
    sink.writeln(
        "Auxiliary surfaces the bridge sketch and Spike 3.2 design reach "
        "for. Captured for context completeness so the design pass has "
        "every surface verified up-front rather than discovered mid-impl."
    )

    dump_surface(
        sink,
        "5.1 hou.hipFile (module / namespace surface)",
        "hou.hipFile",
    )
    dump_surface(
        sink,
        "5.2 hou.hipFile.path (current scene path probe)",
        "hou.hipFile.path",
    )

    # Live call hou.hipFile.path() — read-only getter, returns string.
    sink.writeln()
    sink.writeln("### 5.2.1 hou.hipFile.path() — live call result")
    sink.writeln()
    try:
        path_result = hou.hipFile.path()
        sink.writeln("```")
        sink.writeln(f"  hou.hipFile.path() = {_safe_repr(path_result, limit=300)}")
        sink.writeln("```")
    except Exception as exc:  # noqa: BLE001
        sink.writeln("```")
        sink.writeln(f"  hou.hipFile.path() raised: {type(exc).__name__}: {exc}")
        sink.writeln("```")

    dump_surface(
        sink,
        "5.3 hou.hipFile.removeEventCallback",
        "hou.hipFile.removeEventCallback",
    )
    dump_surface(
        sink,
        "5.4 hou.applicationVersionString",
        "hou.applicationVersionString",
    )

    # Live call applicationVersionString — read-only.
    sink.writeln()
    sink.writeln("### 5.4.1 hou.applicationVersionString() — live call result")
    sink.writeln()
    try:
        version_result = hou.applicationVersionString()
        sink.writeln("```")
        sink.writeln(f"  hou.applicationVersionString() = {_safe_repr(version_result)}")
        sink.writeln("```")
    except Exception as exc:  # noqa: BLE001
        sink.writeln("```")
        sink.writeln(f"  hou.applicationVersionString() raised: {type(exc).__name__}: {exc}")
        sink.writeln("```")


# ── Asynchronous thread-context probe (§3 — load-bearing) ────────────

class ThreadContextProbe:
    """Captures threading context of every ``hou.hipFile`` event during
    a user-triggered scene load. Auto-finalizes on the first AfterLoad
    event or after ``TIMEOUT_SECONDS`` (whichever comes first).

    LOAD-BEARING for Spike 3.2: the auto-warm scaffold's threading model
    depends entirely on whether AfterLoad fires on the main thread (no
    marshaling needed) or a worker thread (every ``hou.*`` call must
    marshal through ``hdefereval``).

    Coordination model
    ------------------
    - ``_lock`` serializes the finalize gate between callback fire and
      timer fire (only one of them ever advances past the gate).
    - ``_finalized`` is the latch — once True, callback returns without
      further capture; timeout returns without writing.
    - ``_captured`` accumulates every event observed before finalize so
      the BeforeLoad → AfterLoad sequence is recorded too (interesting
      signal for Spike 3.2's design — both events may be relevant).
    - Finalization (``_write_finalization``) runs OUTSIDE the lock to
      avoid holding the gate during disk I/O.
    """

    def __init__(self, sink: AuditSink, output_path: Path) -> None:
        self._sink = sink
        self._output_path = output_path
        self._lock = threading.Lock()
        self._finalized = False
        self._captured: list[dict[str, str]] = []
        self._timer: threading.Timer | None = None
        self._unsubscribe_result = "<not attempted>"
        self._timeout_fired = False

    # ── Capture helpers ──────────────────────────────────────

    def _capture(self, event_type) -> dict[str, str]:
        thread = threading.current_thread()
        return {
            "thread_name": thread.name,
            "thread_id": str(threading.get_ident()),
            "is_main_thread": str(thread is threading.main_thread()),
            "event_type_repr": _safe_repr(event_type),
            "event_type_str": str(event_type),
            "event_type_typename": type(event_type).__name__,
            "fired_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }

    def _is_after_load(self, event_type) -> bool:
        # Primary path: enum equality. Fallback: string match (in case
        # the runtime enum-equality contract surprises us — that itself
        # is signal worth knowing).
        try:
            if event_type == hou.hipFileEventType.AfterLoad:
                return True
        except Exception:  # noqa: BLE001
            pass
        try:
            return "AfterLoad" in str(event_type)
        except Exception:  # noqa: BLE001
            return False

    def _try_unsubscribe(self) -> str:
        try:
            hou.hipFile.removeEventCallback(self._on_hip_event)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    # ── Event entry points ───────────────────────────────────

    def _on_hip_event(self, event_type) -> None:
        """Fires for every hipFile event. Captures threading context,
        accumulates into ``_captured``, and finalizes on AfterLoad."""
        info = self._capture(event_type)
        finalize = False
        with self._lock:
            if self._finalized:
                return
            self._captured.append(info)
            if self._is_after_load(event_type):
                self._finalized = True
                self._unsubscribe_result = self._try_unsubscribe()
                if self._timer is not None:
                    self._timer.cancel()
                finalize = True
        if finalize:
            # Outside the lock: I/O + stdout.
            self._write_finalization(reason="event_captured")

    def _on_timeout(self) -> None:
        """Fallback finalization if no AfterLoad fires inside
        ``TIMEOUT_SECONDS``. Best-effort unsubscribe; the timer thread
        is non-main, so removal may itself surface threading signal."""
        finalize = False
        with self._lock:
            if self._finalized:
                return
            self._finalized = True
            self._timeout_fired = True
            self._unsubscribe_result = self._try_unsubscribe()
            finalize = True
        if finalize:
            self._write_finalization(reason="timeout")

    # ── Lifecycle ────────────────────────────────────────────

    def arm(self) -> None:
        """Subscribe the callback and start the timeout timer.
        Called from the main thread inside ``main()``."""
        hou.hipFile.addEventCallback(self._on_hip_event)
        timer = threading.Timer(TIMEOUT_SECONDS, self._on_timeout)
        timer.daemon = True
        timer.start()
        self._timer = timer

    def abort(self) -> str:
        """Manual abort — call from interactive shell to unwind cleanly
        if you need to re-paste the script before the probe naturally
        finalizes. Idempotent; safe to call after natural finalization."""
        finalize = False
        with self._lock:
            if self._finalized:
                return "already finalized"
            self._finalized = True
            self._unsubscribe_result = self._try_unsubscribe()
            if self._timer is not None:
                self._timer.cancel()
            finalize = True
        if finalize:
            self._write_finalization(reason="manual_abort")
        return f"aborted; unsubscribe: {self._unsubscribe_result}"

    # ── Finalization ─────────────────────────────────────────

    def _write_finalization(self, reason: str) -> None:
        sink = self._sink
        sink.begin_section("3", "3. Thread-context probe results — LOAD-BEARING")
        sink.writeln()
        sink.writeln(f"**Finalization reason:** ``{reason}``")
        sink.writeln(f"**Events captured:** {len(self._captured)}")
        sink.writeln(f"**Unsubscribe result:** ``{self._unsubscribe_result}``")
        sink.writeln(f"**Timeout fired:** ``{self._timeout_fired}``")
        sink.writeln(f"**Timeout window:** ``{TIMEOUT_SECONDS}s``")
        sink.writeln()

        if not self._captured:
            sink.writeln("**STATUS:** NO EVENTS CAPTURED")
            sink.writeln()
            sink.writeln("No hipFile events fired within the timeout window. Possible reasons:")
            sink.writeln("- Operator did not load a .hip during the probe")
            sink.writeln("- Houdini's event dispatch suppressed in current context")
            sink.writeln("- Callback registration failed silently (cross-check § 1.2)")
            sink.writeln()
            sink.writeln(
                "**Spike 3.2 implication:** thread context unknown. "
                "Re-run the audit with a confirmed File → Open trigger "
                "before opening Spike 3.2 design."
            )
        else:
            sink.writeln(f"**Captured event sequence ({len(self._captured)} events):**")
            sink.writeln()
            for i, info in enumerate(self._captured, 1):
                sink.writeln(f"#### Event {i}")
                sink.writeln("```")
                for k, v in info.items():
                    sink.writeln(f"  {k:<22} : {v}")
                sink.writeln("```")
                sink.writeln()

            # Headline finding extraction for Spike 3.2 design.
            after_load_events = [
                e for e in self._captured
                if "AfterLoad" in e["event_type_str"]
                or "AfterLoad" in e["event_type_repr"]
            ]
            sink.writeln("**Headline finding for Spike 3.2 scaffold:**")
            sink.writeln()
            if after_load_events:
                e = after_load_events[0]
                sink.writeln(
                    f"- AfterLoad fired on thread ``{e['thread_name']}`` "
                    f"(``is_main_thread={e['is_main_thread']}``)"
                )
                if e["is_main_thread"] == "True":
                    sink.writeln(
                        "- **Main thread confirmed.** Spike 3.2 auto-warm "
                        "callback can call ``hou.*`` directly. No "
                        "``hdefereval`` marshaling required for the "
                        "scene-load reaction path."
                    )
                else:
                    sink.writeln(
                        "- **Worker thread.** Spike 3.2 auto-warm callback "
                        "MUST marshal every ``hou.*`` call through "
                        "``hdefereval.executeInMainThread`` (or the "
                        "with-result variant). Bridge design changes "
                        "materially — ``warm_on_scene_load`` becomes a "
                        "main-thread dispatch instead of a direct call."
                    )
            else:
                sink.writeln(
                    "- No AfterLoad event in capture sequence. Other "
                    "events fired (see above) but the load-bearing event "
                    "did not. Re-run with a confirmed File → Open trigger."
                )

        # Build summary block, then write the report and emit the second
        # shell summary so the operator sees liveness even if the file
        # write fails.
        self._build_summary(sink)
        write_ok, write_err = _write_text_safe(self._output_path, sink.text())

        print(BANNER)
        if reason == "event_captured":
            print(EVENT_BANNER)
        elif reason == "timeout":
            print(TIMEOUT_BANNER)
        else:
            print(f"=== AUDIT FINALIZED — reason: {reason} ===")
        print(f"  events captured : {len(self._captured)}")
        for i, info in enumerate(self._captured, 1):
            print(
                f"  [{i}] thread={info['thread_name']} "
                f"is_main={info['is_main_thread']} "
                f"event={info['event_type_str']}"
            )
        print(f"  unsubscribe     : {self._unsubscribe_result}")
        print(f"  resolved        : {len(sink.surfaces_resolved)}")
        print(f"  missing         : {len(sink.surfaces_missing)}")
        print(f"  errors          : {len(sink.errors)}")
        if write_ok:
            print(f"  full report     : {self._output_path}")
        else:
            print(f"  !! file write failed: {write_err}")
            print(
                f"  (audit text held in memory — re-export with "
                f"``hou.session.{PROBE_GLOBAL_NAME}._sink.text()``)"
            )
        print(DONE)
        print(BANNER)

    def _build_summary(self, sink: AuditSink) -> None:
        sink.begin_section("summary", "AUDIT SUMMARY")
        sink.writeln(f"Surfaces resolved   : {len(sink.surfaces_resolved)}")
        sink.writeln(f"Surfaces missing    : {len(sink.surfaces_missing)}")
        sink.writeln(f"Errors during audit : {len(sink.errors)}")
        sink.writeln(f"Events captured     : {len(self._captured)}")
        finalization = (
            "event_captured"
            if self._captured and not self._timeout_fired
            else ("timeout" if self._timeout_fired else "manual_abort")
        )
        sink.writeln(f"Probe finalization  : {finalization}")
        if sink.surfaces_resolved:
            sink.writeln()
            sink.writeln("RESOLVED:")
            for s in sink.surfaces_resolved:
                sink.writeln(f"  + {s}")
        if sink.surfaces_missing:
            sink.writeln()
            sink.writeln("MISSING (Spike 3.2 cannot reference these by name):")
            for s in sink.surfaces_missing:
                sink.writeln(f"  - {s}")


# ── Output destination + write helper ────────────────────────────────

def _resolve_output_path() -> Path:
    """Pick a deterministic file path for the audit report.

    Preference: ``$HIP/spike_3_2_scene_load_audit_<stamp>.txt`` (sits
    next to the open scene). Fallback: ``~/.synapse/...`` when ``$HIP``
    is unset (fresh Houdini, no saved scene)."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"spike_3_2_scene_load_audit_{stamp}.txt"

    hip = os.environ.get("HIP")
    if hip and Path(hip).is_dir():
        return Path(hip) / fname

    home = Path.home() / ".synapse"
    home.mkdir(parents=True, exist_ok=True)
    return home / fname


def _write_text_safe(path: Path, text: str) -> tuple[bool, str | None]:
    try:
        path.write_text(text, encoding="utf-8")
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    print(BANNER)
    print(TITLE)
    print(f"  Houdini : {hou.applicationVersionString()}")
    print(f"  Python  : {sys.version.split()[0]}")
    print(f"  Time    : {datetime.datetime.now().isoformat(timespec='seconds')}")
    print(BANNER)

    # Cross-paste cleanup: if a prior probe is still armed in this
    # Houdini session, abort it so its callback doesn't fire alongside
    # this run's. ``hou.session`` persists across script pastes.
    prior = getattr(hou.session, PROBE_GLOBAL_NAME, None)
    if prior is not None:
        try:
            result = prior.abort()
            print(f"  [previous probe in session: {result}]")
        except Exception as exc:  # noqa: BLE001
            print(f"  [previous probe abort failed: {type(exc).__name__}: {exc}]")

    sink = AuditSink()
    sink.writeln(BANNER)
    sink.writeln(TITLE)
    sink.writeln(f"Houdini: {hou.applicationVersionString()}")
    sink.writeln(f"Python:  {sys.version.split()[0]}")
    sink.writeln(f"Time:    {datetime.datetime.now().isoformat(timespec='seconds')}")
    sink.writeln(BANNER)

    print("  [running synchronous phases ...]")

    for label, fn in (
        ("§1 hou.hipFile.addEventCallback", run_phase_1),
        ("§2 hou.hipFileEventType",         run_phase_2),
        ("§4 callback identity / dedup",    run_phase_4),
        ("§5 aux surface",                  run_phase_5),
    ):
        try:
            fn(sink)
            print(f"    + {label} ok")
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            sink.errors.append((label, tb))
            sink.writeln()
            sink.writeln(f"!! ERROR during {label}")
            sink.writeln("```")
            sink.writeln(tb)
            sink.writeln("```")
            print(f"    !! {label} {type(exc).__name__}: {exc}")

    output_path = _resolve_output_path()

    # Arm the asynchronous thread-context probe.
    probe = ThreadContextProbe(sink, output_path)
    arm_ok = True
    arm_err: str | None = None
    try:
        probe.arm()
    except Exception as exc:  # noqa: BLE001
        arm_ok = False
        arm_err = f"{type(exc).__name__}: {exc}"

    # Stash on hou.session so the operator can manually abort across
    # paste boundaries if needed.
    setattr(hou.session, PROBE_GLOBAL_NAME, probe)

    print(BANNER)
    if not arm_ok:
        print("!! PROBE FAILED TO ARM")
        print(f"  reason: {arm_err}")
        print("  Synchronous phases captured but §3 cannot fill.")
        print("  Writing partial report ...")
        # Synthesize a §3 placeholder + write so the operator still gets
        # a paste-ready report for §1, §2, §4, §5.
        sink.begin_section("3", "3. Thread-context probe results — LOAD-BEARING")
        sink.writeln()
        sink.writeln("**STATUS:** PROBE FAILED TO ARM")
        sink.writeln(f"**Error:** ``{arm_err}``")
        sink.writeln()
        sink.writeln(
            "Spike 3.2 implication: ``hou.hipFile.addEventCallback`` "
            "could not register the probe. Investigate before scaffolding."
        )
        probe._build_summary(sink)
        write_ok, write_err = _write_text_safe(output_path, sink.text())
        if write_ok:
            print(f"  partial report : {output_path}")
        else:
            print(f"  !! file write failed: {write_err}")
        print(DONE)
        print(BANNER)
        return

    print(ARMED)
    print()
    print("  Now do ONE of:")
    print("    a) File → Open → any small .hip file (preferred)")
    print("    b) File → New (clears scene; fires AfterClear, NOT AfterLoad)")
    print()
    print("  The probe will:")
    print("    - Capture which thread every hipFile event fires on")
    print("    - Finalize on first AfterLoad")
    print("    - Auto-unsubscribe + write the full report to disk")
    print("    - Print a second SUMMARY block when done")
    print()
    print(f"  Timeout fallback : {TIMEOUT_SECONDS}s ({TIMEOUT_SECONDS // 60} min)")
    print(f"  Output path      : {output_path}")
    print()
    print(f"  Manual abort     : hou.session.{PROBE_GLOBAL_NAME}.abort()")
    print(BANNER)


# Auto-run on paste — Python Source Editor invokes module-level code
# directly; ``__name__`` != ``"__main__"`` in that context. Mirrors
# the pattern in ``docs/sprint3/spike_3_0_pdg_audit_script.py``.
main()
