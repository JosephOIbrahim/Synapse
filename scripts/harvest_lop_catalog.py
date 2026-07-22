"""Harvest the full live LOP node-type catalog for the RUNNING Houdini major.

Recognition authority for Solaris work: every LOP type the build actually has,
with the arity that decides how it may legally be wired. Complements
``host/introspect_connectivity.py`` (which instantiates a node per type to read
input LABELS -- slow, richer) by being instantiation-free and therefore cheap
enough to re-run on any build drop.

WHY THIS EXISTS: the catalog was first captured ad hoc through a live bridge
session and left untracked in harness/notes/. One ``git clean`` would have
destroyed the only full-surface H22 recognition artifact in the repo, and CI
could not see it at all. A committed artifact needs a committed producer.

RUN IT INSIDE THE TARGET BUILD:

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/harvest_lop_catalog.py

Writes ``harness/notes/h22_lop_catalog_live_<build>.json``.

DETERMINISM: a second run on the same build is byte-identical -- keys sorted,
no wall-clock stamp. The blake2b covers the sorted ``types`` map, matching the
verified_connectivity/v1 stamping convention.

PHANTOM NOTE: ``hou.NodeType.inputLabels`` does NOT exist (verified absent on
22.0.368; the type-level accessor is phantom and the instance-level
``hou.Node.inputLabels`` is the real surface -- see
host/introspect_connectivity.py:15-21). Nothing here reaches for it; label
truth is that probe's job, not this one's.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "lop_catalog_live/v1"
_REPO = Path(__file__).resolve().parents[1]
NOTES_DIR = _REPO / "harness" / "notes"

# Type-level accessors only -- each independently guarded so one missing API on a
# future build degrades that field to None instead of killing the whole harvest.
_FIELDS = (
    ("label", lambda t: t.description()),
    ("min_inputs", lambda t: t.minNumInputs()),
    ("max_inputs", lambda t: t.maxNumInputs()),
    ("max_outputs", lambda t: t.maxNumOutputs()),
    ("deprecated", lambda t: t.deprecated()),
    ("is_manager", lambda t: t.isManager()),
    ("is_generator", lambda t: t.isGenerator()),
)

# maxNumInputs() reports this for variadic types (merge, sublayer, switch, ...).
# Those are the nodes where input INDEX carries USD opinion strength, so they are
# counted out explicitly rather than left for a caller to rediscover.
UNBOUNDED = 9999


def build_catalog() -> dict:
    import hou

    cat = hou.lopNodeTypeCategory()
    types: dict = {}
    errors: list = []
    for name, node_type in cat.nodeTypes().items():
        rec: dict = {}
        for key, read in _FIELDS:
            try:
                rec[key] = read(node_type)
            except Exception as e:  # noqa: BLE001 -- per-field, never fatal
                rec[key] = None
                errors.append(f"{name}.{key}: {type(e).__name__}: {e}")
        types[name] = rec

    stamp = hashlib.blake2b(
        json.dumps(types, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "build": hou.applicationVersionString(),
        "blake2b": stamp,
        "count": len(types),
        "generated": {
            "by": "scripts/harvest_lop_catalog.py",
            "note": ("deterministic: no wall-clock stamp -- a second run on the "
                     "same build must be byte-identical"),
        },
        "types": types,
        "probe_errors": sorted(errors),
    }


def main() -> int:
    catalog = build_catalog()
    build = catalog["build"]
    major = build.split(".", 1)[0]
    out_fp = NOTES_DIR / f"h{major}_lop_catalog_live_{build}.json"
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(
        json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )

    t = catalog["types"]
    gen = sum(1 for r in t.values() if r.get("is_generator"))
    unb = sorted(n for n, r in t.items() if (r.get("max_inputs") or 0) >= UNBOUNDED)
    multi = sum(1 for r in t.values() if 1 < (r.get("max_inputs") or 0) < UNBOUNDED)
    dep = sorted(n for n, r in t.items() if r.get("deprecated"))
    sys.stdout.write(
        f"LOP CATALOG: build={build} types={catalog['count']} generators={gen} "
        f"multi_input={multi} unbounded={len(unb)} deprecated={len(dep)} "
        f"errors={len(catalog['probe_errors'])} "
        f"blake2b={catalog['blake2b'][:12]} -> {out_fp}\n"
    )
    sys.stdout.write(f"  unbounded (input index == USD strength): {', '.join(unb)}\n")
    sys.stdout.write(f"  deprecated: {', '.join(dep) or '(none)'}\n")
    for err in catalog["probe_errors"]:
        sys.stdout.write(f"  ERROR: {err}\n")
    return 1 if catalog["probe_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
