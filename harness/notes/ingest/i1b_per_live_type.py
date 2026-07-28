"""I1 — coverage per LIVE NODE TYPE, not per help page.

The page view and the type view answer different questions and merging them
hides the gap that matters:

  per page  "of the pages that exist, how many are good enough?"
  per type  "of the node types this build can actually create, how many can
             SYNAPSE say something grounded about?"

Only the type view can see the node types that ship with **no help page at
all** — for those, documentation grounding is not thin, it is absent, and no
amount of better parsing closes them. A probe is the only thing that does.

A type counts as grounded when at least one help page resolving to it clears
I0-FLOOR. Types whose only pages are known-thin are counted separately, never
folded into the grounded number.

Producer: this file -> harness/notes/ingest/_i1b_per_live_type.json
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    corpus = json.loads((HERE / "h22_node_corpus.json").read_text(encoding="utf-8"))
    rt = json.loads((HERE / "_i1b_runtime.json").read_text(encoding="utf-8"))
    names = rt["catalogue_names"]

    out = {
        "producer": "harness/notes/ingest/i1b_per_live_type.py",
        "build": corpus["build"],
        "tier": "VERIFIED-DOC verdict counted against a VERIFIED-RUNTIME "
                "denominator — the two are reported together but never summed "
                "into a single grounding number",
        "rule": "a live type is GROUNDED when >=1 help page resolving to it "
                "clears I0-FLOOR",
        "per_context": {},
    }

    for ctx in ("cop", "lop", "cop2"):
        live = set(names[ctx])
        entries = [e for e in corpus["entries"] if e["context"] == ctx]
        by_type: dict = {}
        for e in entries:
            t = e["runtime"].get("live_type")
            if t:
                by_type.setdefault(t, []).append(e)
        grounded = {t for t, v in by_type.items()
                    if any(x["floor"]["clears"] for x in v)}
        thin_only = set(by_type) - grounded
        no_page = live - set(by_type)
        out["per_context"][ctx] = {
            "catalogue_total_live": len(live),
            "types_with_a_page": len(by_type),
            "types_grounded_to_floor": len(grounded),
            "grounded_pct": round(100.0 * len(grounded) / len(live), 1),
            "types_known_thin_only": len(thin_only),
            "types_with_no_page_at_all": len(no_page),
            "no_page_sample": sorted(no_page)[:20],
            "pages_not_resolving_to_a_live_type": len(
                [e for e in entries if not e["runtime"].get("live_type")]),
        }

    (HERE / "_i1b_per_live_type.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    print("PER LIVE TYPE")
    print("  %-5s %-10s %-9s %-9s %-7s %s"
          % ("ctx", "catalogue", "with_page", "grounded", "thin", "NO PAGE"))
    for ctx, c in out["per_context"].items():
        print("  %-5s %-10d %-9d %-9d %-7d %d"
              % (ctx, c["catalogue_total_live"], c["types_with_a_page"],
                 c["types_grounded_to_floor"], c["types_known_thin_only"],
                 c["types_with_no_page_at_all"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
