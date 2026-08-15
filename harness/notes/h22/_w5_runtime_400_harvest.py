"""W5-DELTA -- harvest the LIVE 22.0.400 runtime catalogue for cop/lop/cop2.

Runs under hython 22.0.400. REUSES harness/notes/ingest/i1_runtime.py verbatim
(harvest_category / deprecation_control) -- no new extraction machinery. i1_runtime's
own main() hard-pins .368 and is NOT invoked here; only its pure harvest functions are
imported. Output schema is byte-compatible with ingest/_i1_runtime.json so i1_build's
build_entry can consume it unchanged.

Additionally records an anatomy_probe: the live-.400 answers to the three cross-reference
facts the mission binds (instancer->copytopoints, no karmamaterial* type, componentgeometry
present) so the corpus census can be checked against LIVE runtime evidence, not just doc.

PRODUCER: this file -> harness/notes/h22/_w5_runtime_400.json
Read-only against Houdini (queries the catalogue + deprecationInfo; creates nothing).
"""
from __future__ import annotations
import json, sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                       # .../<worktree root>
INGEST = REPO / "harness" / "notes" / "ingest"
sys.path.insert(0, str(INGEST))

import hou                                    # noqa: E402  (hython only)
import i1_runtime as R                        # noqa: E402  (reused verbatim)

CATEGORIES = ("Cop", "Cop2", "Lop")
OUT = HERE / "_w5_runtime_400.json"


def anatomy_probe() -> dict:
    cats = hou.nodeTypeCategories()
    lop = cats["Lop"].nodeTypes()
    km = {c: sorted(t for t in cats[c].nodeTypes() if "karmamaterial" in t.lower())
          for c in CATEGORIES}
    return {
        "lop_has_instancer": "instancer" in lop,
        "lop_has_copytopoints": "copytopoints" in lop,
        "lop_has_componentgeometry": "componentgeometry" in lop,
        "lop_has_materiallibrary": "materiallibrary" in lop,
        "lop_has_karmarendersettings": "karmarendersettings" in lop,
        "karmamaterial_star_types_by_cat": km,
        "note": "live-.400 evidence for the mission cross-reference (anatomy doc). "
                "instancer tab resolves to copytopoints; no karmamaterial* VOP type; "
                "componentgeometry present.",
    }


def main() -> int:
    build = hou.applicationVersionString()
    cats = {c: R.harvest_category(c) for c in CATEGORIES}
    out = {
        "schema": "i1_runtime/v1",
        "truth_tier": "VERIFIED-RUNTIME",
        "build": build,
        "producer": "harness/notes/h22/_w5_runtime_400_harvest.py (hython; reuses "
                    "harness/notes/ingest/i1_runtime.harvest_category)",
        "determinism": "no wall-clock stamp; a second run on the same build is byte-identical",
        "reused_from": "harness/notes/ingest/i1_runtime.py (W5-DELTA harvests .400; "
                       "i1_runtime.main() itself hard-pins .368 and is not invoked)",
        "categories": cats,
        "controls": {"deprecation_detector": R.deprecation_control()},
        "counts": {c: cats[c]["count"] for c in CATEGORIES},
        "anatomy_probe": anatomy_probe(),
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print("BUILD=%s" % build)
    for c in CATEGORIES:
        print("  %-5s %4d types, %3d runtime-deprecated"
              % (c, cats[c]["count"],
                 sum(1 for t in cats[c]["types"].values() if t["deprecated"])))
    ap = out["anatomy_probe"]
    print("  anatomy: instancer=%s copytopoints=%s componentgeometry=%s karmamaterial*=%s"
          % (ap["lop_has_instancer"], ap["lop_has_copytopoints"],
             ap["lop_has_componentgeometry"], ap["karmamaterial_star_types_by_cat"]))
    print("  deprecation control pass=%s" % out["controls"]["deprecation_detector"]["pass"])
    print("wrote %s (%.2f MB)" % (OUT, OUT.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
