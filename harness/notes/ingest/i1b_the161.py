"""I1 — derive the "161 new Copernicus nodes" from the SHIPPED source, and
reconcile it against the governing number.

Law 2: this file is the producer for every count about the named set. Nothing
here is inherited from `docs/H22_FRONTIER.md`, from I0, or from this leg's own
brief — all three are re-derived and the disagreements are reported.

Two sources, and they are NOT the same page:

  S1 SHIPPED  $HFS/houdini/help/news.zip!22/copernicus.txt
              version-pinned to 22.0.368 by construction, present on any
              machine with the build installed.
  S2 CACHE    <userprefs>/config/Help/cache/news/22/copernicus.json
              the BROWSING cache — a reading history, rendered to HTML.

Two extractions, because the governing number depends on which regex you use:

  WIDE    [A-Za-z0-9_:.-]+   matches a node name whole
  NARROW  [a-z0-9_]+         the regex in harness/notes/_h22_frontier_xref.py:30

NARROW does not merely under-match: it TRUNCATES. `xform.html` yields `xform`
and `bakegeometrytextures-2.0` yields `bakegeometrytextures`. On the cache that
truncation is load-bearing by accident — it is what folds the `.html` hrefs and
the bare hrefs into one set.

Producer: this file -> harness/notes/ingest/_i1b_the161.json
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELP = Path(r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help")
NEWS_ZIP = HELP / "news.zip"
NODES_ZIP = HELP / "nodes.zip"
CACHE = Path(os.path.expanduser(
    r"~\OneDrive\Documents\houdini22.0\config\Help\cache\news\22\copernicus.json"))

WIDE = r"[A-Za-z0-9_:.\-]+"
NARROW = r"[a-z0-9_]+"


def _flat(o, out):
    if isinstance(o, dict):
        for v in o.values():
            _flat(v, out)
    elif isinstance(o, list):
        for v in o:
            _flat(v, out)
    elif isinstance(o, str):
        out.append(o)
    return out


def _strip_html(names: set[str]) -> set[str]:
    return {n[:-5] if n.endswith(".html") else n for n in names}


def main() -> int:
    shipped_txt = zipfile.ZipFile(NEWS_ZIP).read("22/copernicus.txt").decode("utf-8-sig")
    shipped_txt = shipped_txt.replace("\r\n", "\n")

    ship_wide = sorted({m for m in re.findall(
        r"Node:/?(?:nodes/)?cop/(%s)" % WIDE, shipped_txt)})
    ship_narrow = sorted({m for m in re.findall(
        r"Node:/?(?:nodes/)?cop/(%s)" % NARROW, shipped_txt)})

    cache_wide: list[str] = []
    cache_narrow: list[str] = []
    if CACHE.exists():
        blob = " ".join(_flat(json.loads(CACHE.read_text(encoding="utf-8")), []))
        cache_wide = sorted(_strip_html(
            {m for m in re.findall(r"/nodes//cop/(%s)" % WIDE, blob)}))
        # The frontier producer's exact expression, character for character.
        cache_narrow = sorted({m for m in re.findall(
            r"/nodes//cop/(%s)" % NARROW, blob)})

    # ---- section structure: the page separates NEW nodes from IMPROVEMENTS
    section = None
    by_section: dict = defaultdict(set)
    for line in shipped_txt.split("\n"):
        m = re.match(r"^(={2,})\s+(.+?)\s+\1\s*$", line)
        if m and len(m.group(1)) == 2:
            section = m.group(2)
            continue
        for mm in re.finditer(r"Node:/?(?:nodes/)?cop/(%s)" % WIDE, line):
            by_section[section].add(mm.group(1))

    IMPROVEMENTS = "Copernicus improvements"
    improved = set(by_section.get(IMPROVEMENTS, set()))
    new_sections = {k: v for k, v in by_section.items() if k != IMPROVEMENTS}
    newly_added = set().union(*new_sections.values()) if new_sections else set()

    pages = {n[4:-4] for n in zipfile.ZipFile(NODES_ZIP).namelist()
             if n.startswith("cop/") and n.endswith(".txt")}

    ship_set, cache_set = set(ship_wide), set(cache_narrow)
    out = {
        "producer": "harness/notes/ingest/i1b_the161.py",
        "build": "22.0.368",
        "tier": "VERIFIED-STATIC",
        "sources": {
            "shipped": "news.zip!22/copernicus.txt",
            "cache": str(CACHE) if CACHE.exists() else None,
        },
        "counts": {
            "shipped_wide": len(ship_wide),
            "shipped_narrow": len(ship_narrow),
            "cache_wide_html_stripped": len(cache_wide),
            "cache_narrow_frontier_regex": len(cache_narrow),
        },
        "governing_number_reproduced": len(cache_narrow),
        "shipped_only": sorted(ship_set - cache_set),
        "cache_only": sorted(cache_set - ship_set),
        "section_breakdown": {str(k): len(v) for k, v in sorted(
            by_section.items(), key=lambda kv: str(kv[0]))},
        "named_total_shipped": len(ship_set),
        "named_in_new_sections": len(newly_added),
        "named_in_improvements_section": len(improved),
        "named_improvements_only": len(improved - newly_added),
        "all_named_have_a_page": sorted(ship_set - pages) == [],
        "named_without_a_page": sorted(ship_set - pages),
        "named": sorted(ship_set),
        "named_new_sections": sorted(newly_added),
        "named_improvements_only_list": sorted(improved - newly_added),
    }
    (HERE / "_i1b_the161.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("THE NAMED COPERNICUS SET")
    print("  shipped  news.zip!22/copernicus.txt   WIDE   : %d" % len(ship_wide))
    print("  cache    copernicus.json  frontier regex     : %d  <- the governing 161"
          % len(cache_narrow))
    print("  shipped-only (invisible to the cache)        : %d" % len(ship_set - cache_set))
    for n in sorted(ship_set - cache_set):
        print("      %s" % n)
    print("  named in NEW-flavoured sections              : %d" % len(newly_added))
    print("  named ONLY in 'Copernicus improvements'      : %d" % len(improved - newly_added))
    print("  every named node has a cop/ page             : %s" % out["all_named_have_a_page"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
