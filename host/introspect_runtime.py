"""
host/introspect_runtime.py  —  Scout Spike 2.5 introspection (HOST LAYER)
=========================================================================

Build scout's MEMBERSHIP authority by ``dir()``-walking the live Houdini
runtime. Existence is a membership question and its authority is the runtime,
not prose — this script emits the symbol table; scout *reads* it (so
``cognitive.tools.*`` stays zero-``hou``, boundary preserved).

RUN IT INSIDE THE BUILD SCOUT GROUNDS FOR (per-major output, runway §1.4):

    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
        host/introspect_runtime.py

It walks ``hou`` / ``pdg`` / ``pxr`` to a bounded depth — modules + classes +
class-level callables + SWIG namespace instances owned by the root
(``hou.undos``, ``hou.hipFile``, ``hou.hda`` ...; CTO B2 2026-09-05), no
deeper — cycle-guarded (visited set), dunder/_private skipped, hard node cap
(USD's binding graph is large and cyclic). Writes a version-stamped,
BLAKE2b-checksummed JSON table to the committed package data dir (so the
authority travels to CI / headless / stock python where ``hou`` and the
gitignored ``.synapse`` store are both absent).

HEADLESS CAVEAT: a hython run omits the GUI submodules (``hou.ui``, ``hou.qt``,
``hou.audio``, ``hou.desktop``, ``hou.viewportVisualizers``). The phantom lint
unions them back in via ``harness/verify/checks.py::_GUI_HOU_ABSENT_HEADLESS``
(pinned by ``tests/test_phantom_guardrail.py``) — regenerating here must not be
read as certifying their absence.

Why a file run, not the WS transport: multi-line code over the live ``/synapse``
transport fails; a file run inside Houdini sidesteps it.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

SCHEMA = "scout_symbol_table/v1"
# Depth is bounded by the eval: hou/pdg need module->class->callable (2);
# pxr needs the submodule + its classes (1) — USD's deeper graph is huge/cyclic.
DEPTH_HOU_PDG = 2
DEPTH_PXR = 1
NODE_CAP = 300_000          # hard backstop; truncation is surfaced, never silent


def _walk(obj, prefix, depth, max_depth, visited, out):
    if len(out) >= NODE_CAP:
        return
    oid = id(obj)
    if oid in visited:
        return
    visited.add(oid)
    try:
        names = dir(obj)
    except Exception:
        return
    for name in names:
        if name.startswith("_"):            # skip dunders + _private
            continue
        try:
            child = getattr(obj, name)
        except Exception:
            continue
        sym = prefix + "." + name
        out.add(sym)
        if len(out) >= NODE_CAP:
            return
        # recurse into modules, classes, and NAMESPACE INSTANCES owned by the
        # walked root — the spec's "modules + classes + class-level callables"
        # plus the SWIG namespaces (hou.undos, hou.hipFile, hou.hda, ... — 22 on
        # 22.0.400) that are instances of a type defined in `hou`; never chase
        # arbitrary foreign objects. See _is_namespace_instance.
        if depth < max_depth and (isinstance(child, (type, types.ModuleType))
                                  or _is_namespace_instance(child, prefix, depth)):
            _walk(child, sym, depth + 1, max_depth, visited, out)


def _is_namespace_instance(obj, prefix: str, depth: int) -> bool:
    """CTO B2 (2026-09-05): ``hou.undos`` is neither a class nor a module —
    ``type(hou.undos).__name__ == 'undos'`` and ``__module__ == 'hou'``, a
    SWIG namespace instance. Walking only ``(type, ModuleType)`` recorded the
    bare ``hou.undos`` and none of its members, so scout certified
    ``hou.undos.group`` as a phantom while 13 server files call it.

    Rule: recurse when the object is a DIRECT child of the walked root module
    (``depth == 0``) and its TYPE is defined in that root (``prefix`` is the
    root name: ``hou`` / ``pdg``) — the 22 SWIG namespaces on 22.0.400
    (undos, hipFile, hda, playbar, lop, ...). Instances whose type lives
    elsewhere (``hou.cvar`` — builtins swigvarlink; ``hou.lopTraversalDemands``
    — houpythonportion.lop) stay leaves. Deeper instances stay leaves too: an
    enum value such as ``hou.nodeTypeFilter.Chop`` is a ``hou.EnumValue``
    instance, and recursing it only adds per-value ``.name/.this/.thisown``
    noise (+3,420 entries measured) with no membership value. pxr is
    unaffected: its type modules are ``pxr.<Sub>``, never the bare root."""
    if depth != 0 or "." in prefix:
        return False
    if isinstance(obj, (type, types.ModuleType)) or callable(obj):
        return False
    try:
        return getattr(type(obj), "__module__", None) == prefix
    except Exception:
        return False


def _data_path(major: int = 21) -> Path:
    # host/introspect_runtime.py  ->  parents[1] = repo root
    # Per-major output (runway §1.4): h<major>_symbol_table.json — an H22 run
    # writes alongside the committed H21 table, never over it.
    return (Path(__file__).resolve().parents[1]
            / "python" / "synapse" / "cognitive" / "tools" / "data"
            / f"h{major}_symbol_table.json")


def build_table() -> dict:
    out: set[str] = set()
    visited: set[int] = set()

    import hou
    out.add("hou")
    # Lazy hou submodules (hou.qt, hou.secure) are dir()-empty until explicitly imported.
    import importlib
    for _lazy in ("hou.qt", "hou.secure"):
        try:
            importlib.import_module(_lazy)
        except Exception:
            pass
    _walk(hou, "hou", 0, DEPTH_HOU_PDG, visited, out)

    try:
        import pdg
        out.add("pdg")
        _walk(pdg, "pdg", 0, DEPTH_HOU_PDG, visited, out)
    except Exception as e:
        sys.stderr.write(f"[introspect] pdg unavailable: {e}\n")

    try:
        import pxr
        import pkgutil
        out.add("pxr")
        for m in pkgutil.iter_modules(pxr.__path__):
            full = "pxr." + m.name
            try:
                import importlib
                sub = importlib.import_module(full)
            except Exception:
                continue
            out.add(full)
            _walk(sub, full, 0, DEPTH_PXR, visited, out)
    except Exception as e:
        sys.stderr.write(f"[introspect] pxr unavailable: {e}\n")

    symbols = sorted(out)
    digest = hashlib.blake2b("\n".join(symbols).encode("utf-8"), digest_size=16).hexdigest()
    return {
        "schema": SCHEMA,
        "houdini_version": hou.applicationVersionString(),
        "depth": {"hou_pdg": DEPTH_HOU_PDG, "pxr": DEPTH_PXR},
        "node_cap": NODE_CAP,
        "truncated": len(out) >= NODE_CAP,
        "symbol_count": len(symbols),
        "blake2b": digest,
        "symbols": symbols,
    }


def main() -> int:
    table = build_table()
    out_fp = _data_path(int(table["houdini_version"].split(".")[0]))
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    sys.stdout.write(
        f"TABLE: version={table['houdini_version']} symbols={table['symbol_count']} "
        f"truncated={table['truncated']} blake2b={table['blake2b'][:12]} -> {out_fp}\n"
    )
    # quick self-check on the eval's load-bearing reals
    for s in ("hou.LopNode", "hou.SopNode", "pdg.EventType", "pxr.Usd", "pxr.Sdf"):
        sys.stdout.write(f"  check {s:22} {s in set(table['symbols'])}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
