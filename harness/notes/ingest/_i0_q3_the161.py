"""I0 / Q3 — how many of the 161 new Copernicus nodes have a cop/<name>.txt?

Two independent sources for the node list, deliberately:

  S1  SHIPPED   news.zip!22/copernicus.txt        version-pinned by construction
  S2  BROWSED   <userprefs>/config/Help/cache/news/22/copernicus.json
                the source docs/H22_FRONTIER.md's 161 came from, via
                harness/notes/_h22_frontier_xref.py

S1 is authoritative and was not used before — the prior producer read only the
browsing cache (R72: "a node absent from the cache means nobody browsed it").
Reporting both, and their difference, is the point: if they agree, 161 is solid
from a shipped artifact; if they differ, the governing number moves.

R60 controls: a known-present name must read present; a fabricated name must
read ABSENT. Without the second, "all present" is unfalsifiable.

Run: python -c "exec(open('harness/notes/ingest/_i0_q3_the161.py',encoding='utf-8').read())"
"""

from __future__ import annotations

import json
import os
import re
import sys
import zipfile

_HERE = os.path.abspath("harness/notes/ingest")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _i0_reader import (BUILD, NEWS_ZIP, open_archive, page_names,  # noqa: E402
                        parse_page, read_page)

CACHE_JSON = (r"C:\Users\User\OneDrive\Documents\houdini22.0"
              r"\config\Help\cache\news\22\copernicus.json")


def flat(o, acc):
    if isinstance(o, str):
        acc.append(o)
    elif isinstance(o, list):
        for x in o:
            flat(x, acc)
    elif isinstance(o, dict):
        for x in o.values():
            flat(x, acc)
    return acc


def from_shipped() -> list:
    z = zipfile.ZipFile(NEWS_ZIP)
    t = z.read("22/copernicus.txt").decode("utf-8-sig")
    return sorted(set(re.findall(r"Node:/cop/([a-z0-9_]+)", t)))


def from_cache() -> list | None:
    if not os.path.exists(CACHE_JSON):
        return None
    with open(CACHE_JSON, encoding="utf-8") as fh:
        txt = " ".join(flat(json.load(fh), []))
    return sorted(set(re.findall(r"/nodes//cop/([a-z0-9_]+)", txt)))


def main() -> dict:
    z = open_archive()
    cop_stems = {n.split("/", 1)[1][:-4] for n in page_names(z, "cop")}

    shipped = from_shipped()
    cached = from_cache()

    # ------------------------------------------------------------- controls
    controls = []

    def ck(name, got, want, note=""):
        controls.append({"control": name, "got": got, "want": want,
                         "pass": got == want, "note": note})

    ck("C1 shipped list non-empty", len(shipped) > 0, True)
    ck("C2 known-present name reads PRESENT", "grunge_rust" in cop_stems, True)
    ck("C3 fabricated name reads ABSENT",
       "grunge_definitely_not_a_real_cop" in cop_stems, False,
       "without this, 'all present' cannot fail and proves nothing")
    ck("C4 page really parses as a cop node",
       parse_page("cop/grunge_rust.txt",
                  read_page(z, "cop/grunge_rust.txt")).directives.get("context"), "cop")
    ck("C5 cop page population", len(cop_stems), 375)

    # ------------------------------------------------------------- the answer
    present = [n for n in shipped if n in cop_stems]
    absent = [n for n in shipped if n not in cop_stems]

    cross = {}
    if cached is not None:
        cross = {
            "cache_count": len(cached),
            "shipped_count": len(shipped),
            "in_both": len(set(cached) & set(shipped)),
            "shipped_only": sorted(set(shipped) - set(cached)),
            "cache_only": sorted(set(cached) - set(shipped)),
        }

    report = {
        "schema": "i0-q3/v1",
        "build": BUILD,
        "truth_tier": "VERIFIED-STATIC",
        "producer": "harness/notes/ingest/_i0_q3_the161.py",
        "sources": {
            "S1_shipped": f"{NEWS_ZIP}!22/copernicus.txt",
            "S2_browsing_cache": CACHE_JSON if cached is not None else "ABSENT",
        },
        "controls": controls,
        "controls_passed": sum(1 for c in controls if c["pass"]),
        "controls_total": len(controls),
        "new_cop_nodes_named": len(shipped),
        "present_in_nodes_zip": len(present),
        "absent_from_nodes_zip": len(absent),
        "absent_names": absent,
        "source_cross_check": cross,
        "cop_pages_in_archive": len(cop_stems),
    }
    out = os.path.join(_HERE, "_i0_q3_the161.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"controls: {report['controls_passed']}/{report['controls_total']}")
    for c in controls:
        if not c["pass"]:
            print(f"   FAIL {c['control']}: {c['got']!r} != {c['want']!r}")
    print(f"\nS1 SHIPPED  news.zip!22/copernicus.txt  -> {len(shipped)} new cop nodes named")
    if cached is not None:
        print(f"S2 CACHE    news/22/copernicus.json     -> {len(cached)} new cop nodes named")
        print(f"   in both: {cross['in_both']}   shipped-only: {cross['shipped_only']}"
              f"   cache-only: {cross['cache_only']}")
    print(f"\nPRESENT in nodes.zip cop/ : {len(present)}")
    print(f"ABSENT  from nodes.zip cop/: {len(absent)}")
    if absent:
        for a in absent:
            print(f"    - {a}")
    print(f"\nwrote {out}")
    return report


REPORT = main()
