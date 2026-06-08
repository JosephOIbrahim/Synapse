"""
host/introspect_runtime.py  —  Scout Spike 2.5 introspection (HOST LAYER)
=========================================================================

Build scout's MEMBERSHIP authority by ``dir()``-walking the live Houdini
runtime. Existence is a membership question and its authority is the runtime,
not prose — this script emits the symbol table; scout *reads* it (so
``cognitive.tools.*`` stays zero-``hou``, boundary preserved).

RUN IT INSIDE H21.0.671 (the interpreter scout grounds for):

    "C:/Program Files/Side Effects Software/Houdini 21.0.671/bin/hython.exe" \
        host/introspect_runtime.py

It walks ``hou`` / ``pdg`` / ``pxr`` to a bounded depth — modules + classes +
class-level callables, no deeper — cycle-guarded (visited set), dunder/_private
skipped, hard node cap (USD's binding graph is large and cyclic). Writes a
version-stamped, BLAKE2b-checksummed JSON table to the committed package data
dir (so the authority travels to CI / headless / hython 631 where ``hou`` and
the gitignored ``.synapse`` store are both absent).

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
        # recurse ONLY into modules and classes — the spec's "modules + classes
        # + class-level callables"; never chase instances / arbitrary objects.
        if depth < max_depth and isinstance(child, (type, types.ModuleType)):
            _walk(child, sym, depth + 1, max_depth, visited, out)


def _data_path() -> Path:
    # host/introspect_runtime.py  ->  parents[1] = repo root
    return (Path(__file__).resolve().parents[1]
            / "python" / "synapse" / "cognitive" / "tools" / "data"
            / "h21_symbol_table.json")


def build_table() -> dict:
    out: set[str] = set()
    visited: set[int] = set()

    import hou
    out.add("hou")
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
    out_fp = _data_path()
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
