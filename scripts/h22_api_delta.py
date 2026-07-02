"""H22 drop-day API-delta probe (task 0.2, deliverable C — the one command).

Wires the three probes into one machine-readable delta report:

1. **Symbols** — regenerates the scout symbol table in-memory via
   ``host/introspect_runtime.build_table()`` after force-importing the lazily
   loaded ``hou.qt`` / ``hou.text`` / ``hou.secure`` submodules (the ``dir()``
   blind spot from ``docs/H22_READINESS_REPORT.md``), then diffs against the
   committed baseline, ranking removed symbols by SYNAPSE call-site usage.
2. **Node types** — rebuilds the emitted-node-type catalog in-memory via
   ``host/introspect_nodetypes.build_catalog()`` and diffs against the
   committed baseline: missing types, parm renames, default changes.
3. **Punycode** — re-probes the live ``xn__`` parm map off real light LOPs
   and diffs against ``synapse.core.usd_punycode.PUNYCODE_PARMS``, emitting a
   ready-to-paste proposed block.

Outputs ``.claude/probe_delta.json`` (schema ``h22_probe_delta/v1`` — exactly
what ``harness/verify/checks.py::check_probe_clean`` counts) and
``.claude/probe_delta.md`` (the human triage doc, grouped by consumer).
Mode-A identity proof: on H21.0.671 with the committed baselines,
``unpatched == []``.

The diff engine itself is hou-free (``synapse.cognitive.tools.api_delta``,
exercised by ``tests/test_h22_api_delta.py`` on stock 3.14); this script is
the hython-side wiring. It lives in scripts/ (operator entrypoint — ``print``
allowed, per ``run_apex_verify.py``'s precedent).

USAGE
-----
    hython scripts/h22_api_delta.py [--baseline-table <path>]
        [--baseline-catalog <path>] [--baseline-encodings <path>]
        [--out .claude/probe_delta.json]

Defaults point at the committed H21 artifacts. Exit 0 = facts reported
(``check_probe_clean`` judges the drift count); exit 1 = the probe itself
failed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# --- Bootstrap: put the package root (<repo>/python) on sys.path ------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.cognitive.tools import api_delta  # noqa: E402
from synapse.core.usd_punycode import PUNYCODE_PARMS, USD_ATTR_NAMES  # noqa: E402

_DATA = _PKG / "synapse" / "cognitive" / "tools" / "data"
_NOTES = _PROJECT_ROOT / "harness" / "notes"

# hou namespaces that are lazily materialized — touched BEFORE the walk so
# any dir(hou) entries they add are visible and drop day gets no false
# 'removed' noise. Live-verified on 21.0.671 hython (2026-07-01):
# ``importlib.import_module("hou.qt")`` can NEVER work (hou is a module, not
# a package); ``getattr(hou, "text")`` loads an INSTANCE namespace (23
# members the depth-walker does not descend into — the known dir() blind
# spot, symmetric between baseline and live); ``hou.qt`` is UI-only and
# ``hou.secure`` does not exist headless on this build. Facts are reported,
# never fatal.


def _load_host_module(name: str):
    """host/ is a plain directory (not a package) — load by file path."""
    spec = importlib.util.spec_from_file_location(
        name, _PROJECT_ROOT / "host" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _force_import_lazy_submodules() -> list:
    import hou

    loaded = []
    for name in ("qt", "text", "secure"):
        try:
            getattr(hou, name)
            loaded.append(f"hou.{name}")
        except Exception as e:  # noqa: BLE001 — absence is a fact, not a crash
            print(f"  lazy namespace hou.{name} did not load: {e}")
    return loaded


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline-table",
                    default=str(_DATA / "h21_symbol_table.json"))
    ap.add_argument("--baseline-catalog",
                    default=str(_NOTES / "verified_nodetype_catalog_21.0.671.json"))
    ap.add_argument("--baseline-encodings",
                    default=str(_NOTES / "verified_usdlux_encodings_21.0.671.json"))
    ap.add_argument("--out", default=str(_PROJECT_ROOT / ".claude" / "probe_delta.json"))
    args = ap.parse_args(argv)

    baseline_table = json.loads(Path(args.baseline_table).read_text(encoding="utf-8"))
    baseline_catalog = json.loads(Path(args.baseline_catalog).read_text(encoding="utf-8"))
    baseline_encodings = json.loads(Path(args.baseline_encodings).read_text(encoding="utf-8"))

    # -- Probe 1: symbols ----------------------------------------------------
    print("probe 1/3: symbol table (force-importing lazy hou submodules first)")
    _force_import_lazy_submodules()
    introspect_runtime = _load_host_module("introspect_runtime")
    live_table = introspect_runtime.build_table()
    callsites = api_delta.build_callsite_index(_PKG / "synapse")
    symbols = api_delta.diff_symbols(
        baseline_table["symbols"], live_table["symbols"], callsites
    )

    # -- Probe 2: node types -------------------------------------------------
    print("probe 2/3: emitted node-type catalog")
    introspect_nodetypes = _load_host_module("introspect_nodetypes")
    live_catalog = introspect_nodetypes.build_catalog()
    node_types = api_delta.diff_node_catalogs(baseline_catalog, live_catalog)

    # -- Probe 3: punycode ---------------------------------------------------
    print("probe 3/3: punycode re-probe")
    live_raw_map = live_catalog["punycode"]["raw"]
    punycode = api_delta.diff_punycode(
        PUNYCODE_PARMS, live_raw_map,
        api_delta.flatten_verified_encodings(baseline_encodings),
        USD_ATTR_NAMES,
    )

    # -- Report ---------------------------------------------------------------
    report = api_delta.build_delta(
        baseline_table["houdini_version"], live_table["houdini_version"],
        symbols, node_types, punycode,
    )
    out_json = Path(args.out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    proposed = api_delta.proposed_punycode_block(
        PUNYCODE_PARMS, live_raw_map, USD_ATTR_NAMES
    )
    out_md = out_json.with_suffix(".md")
    out_md.write_text(api_delta.render_markdown(report, proposed), encoding="utf-8")

    # Probe-generated encodings for the live build. NEVER overwrite an
    # existing curated file — on an identity run the committed ground truth
    # (verified_usdlux_encodings_21.0.671.json) stays byte-for-byte intact.
    enc_fp = _NOTES / f"verified_usdlux_encodings_{report['live_build']}.json"
    if enc_fp.exists():
        print(f"  encodings file exists, left untouched: {enc_fp.name}")
    else:
        enc_fp.write_text(json.dumps({
            "_provenance": (
                f"probe-generated by scripts/h22_api_delta.py off live light LOPs, "
                f"Houdini {report['live_build']}"
            ),
            "aliases_verified": live_catalog["punycode"]["aliases"],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  wrote probe-generated encodings: {enc_fp.name}")

    n = len(report["unpatched"])
    print(
        f"DELTA: baseline={report['baseline_build']} live={report['live_build']} "
        f"symbols +{symbols['added_count']}/-{symbols['removed_count']} "
        f"node_types missing={len(node_types['missing_types'])} "
        f"parm_changes={len(node_types['parm_changes'])} "
        f"punycode changed={len(punycode['changed'])} vanished={len(punycode['vanished'])}"
    )
    print(f"UNPATCHED: {n} -> {out_json}")
    print(f"TRIAGE:    {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
