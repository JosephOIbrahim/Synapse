"""Headless APEX surface verification entrypoint (thin).

Runs the SYNAPSE science loop (``synapse.science.run_search``) over
``APEX_SEED`` against a live, injected namespace. Designed to run under
headless **hython** on Houdini 21.0.671, but imports and runs fine WITHOUT
Houdini — ``apex`` is an optional dependency, not a hard one.

WHY THIS LIVES IN scripts/ (not python/synapse/)
-------------------------------------------------
It is an operator entrypoint, not library code. The repo's no-print policy
(tests/test_v5_features.py::test_no_print_in_source) only scans
``python/synapse/**``; scripts/ is outside that tree, so ``print`` for the
human-facing summary is fine here.

USAGE
-----
    hython scripts/run_apex_verify.py [jsonl_path]
    python  scripts/run_apex_verify.py [jsonl_path]   # standalone, no apex

If ``jsonl_path`` is omitted it defaults to
``<repo>/.synapse/science/apex_registry.jsonl``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Bootstrap: put the package root (<repo>/python) on sys.path ------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.science import APEX_SEED, Registry, probe, run_search  # noqa: E402


def _build_namespace() -> dict:
    """Build the injected probe namespace.

    ``apex`` is OPTIONAL. If Houdini's ``apex`` module is importable we expose
    it (and a node-type catalog under ``nodetypes``); otherwise the namespace
    is empty and every surface simply probes as absent — the loop still runs.
    """
    namespace: dict = {}
    try:
        import apex  # type: ignore
    except Exception:  # noqa: BLE001 — apex is a soft dependency
        apex = None
    if apex is not None:
        namespace["apex"] = apex

    # Best-effort node-type catalog so "nodetypes.<typename>" surfaces resolve.
    # A plain {name: node_type} dict — probe() does a MEMBERSHIP test on the
    # full "namespace::name" string (not getattr), so no wrapper is needed.
    try:
        import hou  # type: ignore

        catalog: dict = {}
        for category in hou.nodeTypeCategories().values():
            for type_name, node_type in category.nodeTypes().items():
                catalog[type_name] = node_type
        if catalog:
            namespace["nodetypes"] = catalog
    except Exception:  # noqa: BLE001 — hou is a soft dependency
        pass

    return namespace


def main(argv: list[str]) -> int:
    jsonl_path = argv[1] if len(argv) > 1 else str(
        _PROJECT_ROOT / ".synapse" / "science" / "apex_registry.jsonl"
    )
    os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)

    namespace = _build_namespace()
    have_apex = "apex" in namespace
    have_catalog = "nodetypes" in namespace

    registry = Registry(jsonl_path=jsonl_path)
    result = run_search(APEX_SEED, registry, lambda s: probe(namespace, s))

    recorded = result["recorded"]
    champions = [r for r in recorded if r.status == "champion"]
    dead_ends = [r for r in recorded if r.status == "dead_end"]

    print("=" * 60)
    print("SYNAPSE APEX surface verification")
    print("=" * 60)
    print(f"  apex module:     {'present' if have_apex else 'ABSENT (standalone)'}")
    print(f"  nodetype catalog:{'present' if have_catalog else 'ABSENT (standalone)'}")
    print(f"  registry jsonl:  {jsonl_path}")
    print(f"  seeds:           {len(APEX_SEED)}")
    print("-" * 60)
    print(f"  recorded:        {len(recorded)}")
    print(f"    champions:     {len(champions)}")
    print(f"    dead_ends:     {len(dead_ends)}")
    print(f"  skipped (known): {len(result['skipped'])}")
    print(f"  held:            {len(result['held'])}")
    print(f"  halted:          {len(result['halted'])}")
    print("-" * 60)
    for rec in recorded:
        mark = "OK " if rec.status == "champion" else "XX "
        print(f"  {mark}{rec.surface} [{rec.kind}] -> {rec.status}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
