"""Spike 3.0 — PDG API Audit (paste-into-Houdini introspection).

Empirically capture the actual PDG / TOPs API surface exposed by SideFX
Houdini 21.0.671 so Spike 3.1's ``TopsEventBridge`` can be coded against
verified reality. Anchors: ``CONTINUATION_INSIDE_OUT_TOPS.md`` § Hard
API verification gate (lines ~290–306); Sprint 3 hard invariant #6 —
*dir() introspection in live Houdini first, blueprint code second.*

Context
-------
The codebase already records (``shared/bridge.py:568``) that **PDG
events live in the standalone ``pdg`` module, not under ``hou.pdg``**.
The bridge sketch in CONTINUATION_INSIDE_OUT_TOPS.md references
``hou.pdg.scheduler``, ``hou.pdg.workItem``, and
``hou.pdg.GraphContext``; this audit verifies whether those names
resolve at all, or whether Spike 3.1 must reach the standalone ``pdg``
module instead — and pins the full event/payload contract surface.

How to use
----------
Inside graphical Houdini 21.0.671 (Joe operates — never the agent):

    1. Windows → Python Source Editor (or Python Shell).
    2. File → Open → docs/sprint3/spike_3_0_pdg_audit_script.py
       (or paste contents directly).
    3. Run.
    4. Watch the shell for SUMMARY + final file path.
    5. Open that file and paste each section into
       docs/sprint3/spike_3_0_pdg_api_audit.md.

Output strategy: HYBRID (file + shell summary). Shell shows liveness +
which surfaces resolved/missing + the report path. The full structured
``dir()``/sig dump goes to disk so Houdini's shell truncation can't
cost us audit fidelity. File path: ``$HIP/spike_3_0_pdg_audit_<stamp>``
when ``$HIP`` is set, else ``~/.synapse/spike_3_0_pdg_audit_<stamp>``.

Read-only. Idempotent. Stdlib + ``hou`` only. Python 3.11 (Houdini's).
"""
from __future__ import annotations

import datetime
import inspect
import os
import sys
import traceback
from pathlib import Path

# `hou` is always present inside Houdini's Python interpreter — no guard.
import hou


# ── Constants ────────────────────────────────────────────────────────

BANNER = "=" * 68
TITLE = "=== SPIKE 3.0 PDG API AUDIT ==="
DONE = "=== AUDIT COMPLETE ==="
DOC_TRUNCATE = 500   # Per-item __doc__ char cap.
REPR_TRUNCATE = 200  # Per-item repr char cap.
KEEP_DUNDERS = {"__call__", "__iter__", "__enter__", "__exit__", "__await__"}


# ── Output sink ──────────────────────────────────────────────────────

class AuditSink:
    """Buffered text writer. Tracks resolved/missing surfaces + errors.

    The file is the durable record; stdout is liveness signal only.
    Houdini's Python Shell can truncate long output, hence the split.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self.surfaces_resolved: list[str] = []
        self.surfaces_missing: list[str] = []
        self.errors: list[tuple[str, str]] = []

    def writeln(self, line: str = "") -> None:
        self._lines.append(line)

    def header(self, title: str) -> None:
        self._lines.append("")
        self._lines.append("-" * 68)
        self._lines.append(f"## {title}")
        self._lines.append("-" * 68)

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


# ── Introspection helpers ────────────────────────────────────────────

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


# ── Surface dump ─────────────────────────────────────────────────────

def dump_surface(sink: AuditSink, label: str, dotted: str) -> None:
    """Resolve ``dotted`` and write a structured dump: type, repr,
    ``__doc__`` excerpt, filtered ``dir()``, per-callable signatures.
    Missing names land in ``sink.surfaces_missing`` with a clear
    note — that's an audit finding, not a script failure."""
    sink.header(label)
    sink.writeln(f"**Resolved path:** ``{dotted}``")
    sink.writeln()

    obj = _resolve(dotted)
    if obj is None:
        sink.writeln(f"**STATUS:** NOT RESOLVABLE — ``{dotted}`` does not exist.")
        sink.writeln()
        sink.writeln(
            "Spike 3.1 cannot reference this name. If the bridge sketch "
            "uses it, the sketch needs revision."
        )
        sink.surfaces_missing.append(dotted)
        return

    sink.surfaces_resolved.append(dotted)
    sink.writeln(f"**STATUS:** RESOLVED")
    sink.writeln(f"**Type:** ``{type(obj).__name__}``")
    sink.writeln(f"**Repr:** ``{_safe_repr(obj)}``")
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
    """Specialised dump for enum-shaped surfaces (``EventType``).
    Lists every public member with its value. Falls back to noting
    missing if the name doesn't resolve."""
    sink.header(label)
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


# ── Audit phases ─────────────────────────────────────────────────────
# Each phase adds rows to the sink. Order matches §2 of the receiving
# doc so paste-from-report → paste-to-doc is linear.

def run_audit(sink: AuditSink) -> None:
    """All seven phases. Failures inside any phase are captured but
    don't abort the rest — every other surface still gets dumped."""

    phases = (
        ("1. PDG top-level surfaces", [
            ("hou.pdg surface", "hou.pdg", "surface"),
            ("Standalone `pdg` module surface", "pdg", "surface"),
        ]),
        ("2. Scheduler surface", [
            ("hou.pdg.scheduler", "hou.pdg.scheduler", "surface"),
            ("pdg.Scheduler", "pdg.Scheduler", "surface"),
            ("pdg.SchedulerType", "pdg.SchedulerType", "surface"),
        ]),
        ("3. WorkItem surface", [
            ("hou.pdg.workItem", "hou.pdg.workItem", "surface"),
            ("pdg.WorkItem", "pdg.WorkItem", "surface"),
        ]),
        ("4. Event subscription API", [
            ("pdg.PyEventHandler", "pdg.PyEventHandler", "surface"),
            ("pdg.EventType (enum)", "pdg.EventType", "enum"),
            ("pdg.EventHandler (abstract base)", "pdg.EventHandler", "surface"),
            ("pdg.PyEventCallback (alt name)", "pdg.PyEventCallback", "surface"),
        ]),
        ("5. Callback registration shape", [
            ("pdg.GraphContext", "pdg.GraphContext", "surface"),
            ("hou.pdg.GraphContext", "hou.pdg.GraphContext", "surface"),
            ("hou.topNodeTypeCategory", "hou.topNodeTypeCategory", "surface"),
        ]),
        ("6. Cook lifecycle event types", [
            # pdg.EventType already dumped in §4; re-state the cross-ref
            # via hou.nodeEventType (parallel surface) and the legacy
            # hou.pdgEventType (expected absent per bridge.py:568).
            ("hou.nodeEventType", "hou.nodeEventType", "enum"),
            ("hou.pdgEventType (legacy, may not exist)", "hou.pdgEventType", "enum"),
        ]),
        ("7. Auxiliary surfaces (bridge sketch references)", [
            ("hou.topNodeTypeCategory (aux)", "hou.topNodeTypeCategory", "surface"),
            ("hou.hipFile", "hou.hipFile", "surface"),
            ("hou.hipFileEventType", "hou.hipFileEventType", "enum"),
            ("hou.hipFile.addEventCallback (probe)", "hou.hipFile.addEventCallback", "surface"),
        ]),
    )

    for phase_label, items in phases:
        sink.writeln()
        sink.writeln(f"# {phase_label}")
        for label, dotted, kind in items:
            try:
                if kind == "enum":
                    dump_enum_like(sink, label, dotted)
                else:
                    dump_surface(sink, label, dotted)
            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc()
                sink.errors.append((label, tb))
                sink.header(f"!! ERROR during {label}")
                sink.writeln("```")
                sink.writeln(tb)
                sink.writeln("```")
                print(f"    !! {type(exc).__name__}: {exc}")


# ── Output destination ───────────────────────────────────────────────

def _resolve_output_path() -> Path:
    """Pick a deterministic file path for the audit report.

    Preference: ``$HIP/spike_3_0_pdg_audit_<stamp>.txt`` (sits next to
    the open scene). Fallback: ``~/.synapse/spike_3_0_pdg_audit_<stamp>.txt``
    when ``$HIP`` is unset (fresh Houdini, no saved scene)."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"spike_3_0_pdg_audit_{stamp}.txt"

    hip = os.environ.get("HIP")
    if hip and Path(hip).is_dir():
        return Path(hip) / fname

    home = Path.home() / ".synapse"
    home.mkdir(parents=True, exist_ok=True)
    return home / fname


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    print(BANNER)
    print(TITLE)
    print(f"  Houdini: {hou.applicationVersionString()}")
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  Time:    {datetime.datetime.now().isoformat(timespec='seconds')}")
    print(BANNER)

    sink = AuditSink()
    sink.writeln(BANNER)
    sink.writeln(TITLE)
    sink.writeln(f"Houdini: {hou.applicationVersionString()}")
    sink.writeln(f"Python:  {sys.version.split()[0]}")
    sink.writeln(f"Time:    {datetime.datetime.now().isoformat(timespec='seconds')}")
    sink.writeln(BANNER)

    print("  [running audit phases ...]")
    run_audit(sink)

    # Summary block
    sink.header("AUDIT SUMMARY")
    sink.writeln(f"Surfaces resolved   : {len(sink.surfaces_resolved)}")
    sink.writeln(f"Surfaces missing    : {len(sink.surfaces_missing)}")
    sink.writeln(f"Errors during audit : {len(sink.errors)}")
    if sink.surfaces_resolved:
        sink.writeln()
        sink.writeln("RESOLVED:")
        for s in sink.surfaces_resolved:
            sink.writeln(f"  + {s}")
    if sink.surfaces_missing:
        sink.writeln()
        sink.writeln("MISSING (Spike 3.1 cannot reference these by name):")
        for s in sink.surfaces_missing:
            sink.writeln(f"  - {s}")

    # Write file
    out_path = _resolve_output_path()
    try:
        out_path.write_text(sink.text(), encoding="utf-8")
        write_ok, write_err = True, None
    except Exception as exc:  # noqa: BLE001
        write_ok, write_err = False, f"{type(exc).__name__}: {exc}"

    # Shell summary
    print(BANNER)
    print("SUMMARY")
    print(f"  resolved : {len(sink.surfaces_resolved)}")
    print(f"  missing  : {len(sink.surfaces_missing)}")
    print(f"  errors   : {len(sink.errors)}")
    if sink.surfaces_missing:
        print("  missing surfaces:")
        for s in sink.surfaces_missing:
            print(f"    - {s}")
    if write_ok:
        print(f"  full report: {out_path}")
    else:
        print(f"  !! file write failed: {write_err}")
        print("  (audit text was captured in memory but not persisted)")
    print(DONE)
    print(BANNER)


# Auto-run on paste — no __main__ guard, because the script is pasted
# into an interactive Python Shell where __name__ != "__main__".
main()
