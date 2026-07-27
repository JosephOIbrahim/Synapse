"""H9 Work 1 -- TRUE doc coverage of the live LOP/COP catalogues.

Supersedes the first pass in ``harness/notes/_doc_coverage.py``, whose
catalogue parse was approximate in three ways, each verified here:

  * ``name.split("::")[-1]`` on ``Labs::biome_plant_scatter_import::1.0``
    yields ``"1.0"`` -- hence the '1.0'/'2.0' entries in its missing list.
    Houdini's grammar is ``[namespace::]name[::version]``; the LAST field is
    the version, not the name.
  * lower-casing and de-duplicating collapsed 218 live LOP types to 198 and
    553 live COP types to 491, so its denominators were not the catalogues.
  * it counted every ``lop/*.txt`` as a node page, including the 16 ``_``-prefixed
    include fragments -- and would have missed that ``cop2/maskparms.txt``
    is a fragment with no underscore at all.

WHAT COUNTS AS COVERED, stated so it can fail
---------------------------------------------
EXACT  the page's candidate type spellings contain the live type name verbatim.
BASE   the live type is namespaced/versioned and only its base name matched --
       e.g. live ``backgroundplate::2.0`` against a page that declares
       ``#internal: backgroundplate``. Real grounding, but possibly authored
       for a different version, so it is counted and reported SEPARATELY.
ELSEWHERE  no page in this context, but a node page in another context declares
       the same internal name (network managers: chopnet, dopnet, matnet).
       Semantic content exists; it is not context-specific.
ABSENT everything else.

This check can fail: if the mapping were wrong, EXACT would collapse toward
zero and ABSENT would fill with common types like ``blend`` or ``camera``.
The negative control at the bottom asserts that a deliberately-wrong mapping
scores strictly worse, so a pass is not vacuous (Law 1).

PRODUCER of every integer in H9's coverage section: this file.
Writes harness/notes/h9/coverage.json.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpdoc  # noqa: E402

NOTES = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "coverage.json"

LOP_CAT = NOTES / "h22_lop_catalog_live_22.0.368.json"
COP_CAT = NOTES / "h22_cop_catalog_live_22.0.368.json"


def load_catalogues() -> dict[str, dict[str, dict]]:
    """Live type catalogues, read at full fidelity -- no lowering, no dedup."""
    lop = json.loads(LOP_CAT.read_text(encoding="utf-8"))
    cop = json.loads(COP_CAT.read_text(encoding="utf-8"))
    assert lop["schema"] == "lop_catalog_live/v1", lop["schema"]
    assert cop["schema"] == "cop_catalog_live/v1", cop["schema"]
    assert lop["build"] == helpdoc.BUILD and cop["build"] == helpdoc.BUILD
    out = {"lop": dict(lop["types"])}
    # category_name is the HOM spelling ('Cop', 'Cop2'); the help contexts are
    # lower-case ('cop', 'cop2'). Mapped explicitly rather than by .lower() so a
    # future category name that does not match a help context fails loudly.
    _CTX = {"Cop": "cop", "Cop2": "cop2"}
    for cat, blob in cop["categories"].items():
        ctx = _CTX.get(blob["category_name"])
        if ctx is None:
            raise SystemExit("unmapped COP category %r -- refusing to guess a help context"
                             % blob["category_name"])
        out[ctx] = dict(blob["types"])
    return out


def split_type(name: str) -> tuple[str | None, str, str | None]:
    """``[namespace::]name[::version]`` -> (namespace, name, version).

    The discriminator is that a version is numeric. ``kinefx::sopcharacterimport``
    is namespace+name; ``backgroundplate::2.0`` is name+version. Getting this
    backwards is precisely the first pass's defect.
    """
    parts = name.split("::")
    ver = None
    if len(parts) > 1 and re.fullmatch(r"\d+(?:\.\d+)*", parts[-1]):
        ver = parts[-1]
        parts = parts[:-1]
    if len(parts) >= 2:
        return "::".join(parts[:-1]), parts[-1], ver
    return None, parts[0], ver


def build_page_index(corpus: helpdoc.HelpCorpus) -> tuple[dict, dict, list]:
    """Index EVERY node page in the shipped corpus, by context.

    Indexing all contexts (not only lop/cop/cop2) is what makes the ELSEWHERE
    verdict able to fire at all: the network managers live at nodes/manager/*.
    """
    all_ctx = helpdoc.all_node_contexts(corpus)
    pages = helpdoc.node_pages(corpus, contexts=all_ctx)
    exact: dict[str, dict[str, str]] = {}
    base: dict[str, dict[str, list[str]]] = {}
    records = []
    for key in pages:
        d = helpdoc.page_directives(corpus.pages[key])
        ctx = key.split("/")[1]
        cands = helpdoc.canonical_type_names(key, d)
        records.append({"help_key": key, "context": ctx, "candidates": cands})
        for c in cands:
            exact.setdefault(ctx, {}).setdefault(c.lower(), key)
            _, nm, _v = split_type(c)
            base.setdefault(ctx, {}).setdefault(nm.lower(), []).append(key)
    return exact, base, records


def classify(live_name: str, ctx: str, exact: dict, base: dict) -> tuple[str, str | None]:
    lo = live_name.lower()
    if lo in exact.get(ctx, {}):
        return "EXACT", exact[ctx][lo]
    ns, nm, ver = split_type(live_name)
    hit = base.get(ctx, {}).get(nm.lower())
    if hit:
        return "BASE", hit[0]
    for other, table in exact.items():
        if other == ctx:
            continue
        if lo in table:
            return "ELSEWHERE", table[lo]
        h2 = base.get(other, {}).get(nm.lower())
        if h2:
            return "ELSEWHERE", h2[0]
    return "ABSENT", None


def run() -> dict:
    corpus = helpdoc.HelpCorpus()
    cats = load_catalogues()
    exact, base, page_records = build_page_index(corpus)

    result = {
        "schema": "h9_coverage/v1",
        "truth_tier": "VERIFIED-DOC",
        "build": helpdoc.BUILD,
        "producer": "harness/notes/h9/coverage.py",
        "help_archive": str(helpdoc.NODES_ZIP),
        "supersedes": "harness/notes/_doc_coverage.py (approximate catalogue parse)",
        "page_census": {},
        "contexts": {},
    }

    for ctx in ("lop", "cop", "cop2"):
        allf = [k for k in corpus.pages
                if k.startswith("nodes/%s/" % ctx) and "/" not in k[len("nodes/%s/" % ctx):]]
        nodep = [r for r in page_records if r["context"] == ctx]
        kinds = Counter(helpdoc.page_directives(corpus.pages[k]).get("type", "<none>").strip()
                        for k in allf)
        result["page_census"][ctx] = {
            "files_in_zip": len(allf),
            "node_pages": len(nodep),
            "by_page_type": dict(kinds),
            "note": "node_pages filters on '#type: node'; the remainder are "
                    "include fragments and index pages, which are not grounding "
                    "for a node and must not inflate a coverage denominator.",
        }

    for ctx, live in (("lop", cats["lop"]),
                      ("cop", cats["cop"]),
                      ("cop2", cats["cop2"])):
        rows = []
        for name in sorted(live):
            verdict, key = classify(name, ctx, exact, base)
            ns, nm, ver = split_type(name)
            rows.append({
                "type": name, "namespace": ns, "base": nm, "version": ver,
                "verdict": verdict, "help_key": key,
                "deprecated_runtime": bool(live[name].get("deprecated")),
                "label": live[name].get("label"),
                "is_manager": bool(live[name].get("is_manager")),
            })
        c = Counter(r["verdict"] for r in rows)
        total = len(rows)
        covered_strict = c["EXACT"]
        covered_incl_base = c["EXACT"] + c["BASE"]
        absent = [r for r in rows if r["verdict"] == "ABSENT"]
        result["contexts"][ctx] = {
            "live_types": total,
            "EXACT": c["EXACT"],
            "BASE": c["BASE"],
            "ELSEWHERE": c["ELSEWHERE"],
            "ABSENT": c["ABSENT"],
            "coverage_exact_pct": round(100.0 * covered_strict / total, 1),
            "coverage_with_base_pct": round(100.0 * covered_incl_base / total, 1),
            "absent_breakdown": dict(Counter(
                "third_party_namespace" if r["namespace"] and r["namespace"] != "kinefx"
                else "manager" if r["is_manager"]
                else "versioned_variant" if r["version"]
                else "plain" for r in absent)),
            "absent_types": [r["type"] for r in absent],
            "rows": rows,
        }
    return result


def negative_control(result: dict) -> dict:
    """Law 1 -- prove the mapping can fail.

    Re-run LOP classification with the first pass's own broken rule
    (``split("::")[-1]`` as the name). If the check is real, coverage must
    collapse. If it does not, the check is not measuring the mapping.
    """
    corpus = helpdoc.HelpCorpus()
    cats = load_catalogues()
    exact, base, _ = build_page_index(corpus)
    bad_hits = 0
    for name in cats["lop"]:
        broken = name.split("::")[-1].lower()
        if broken in exact.get("lop", {}) or broken in base.get("lop", {}):
            bad_hits += 1
    good = result["contexts"]["lop"]["EXACT"] + result["contexts"]["lop"]["BASE"]
    return {
        "control": "re-classify LOP with the superseded split('::')[-1] rule",
        "correct_rule_covered": good,
        "broken_rule_covered": bad_hits,
        "strictly_worse": bad_hits < good,
        "verdict": "PASS -- the mapping is load-bearing" if bad_hits < good
                   else "FAIL -- coverage is insensitive to the mapping; the check proves nothing",
    }


if __name__ == "__main__":
    res = run()
    res["negative_control"] = negative_control(res)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")

    print("PAGE CENSUS (files in zip vs actual node pages)")
    for ctx, c in res["page_census"].items():
        print("  %-5s files=%3d  node_pages=%3d  types=%s"
              % (ctx, c["files_in_zip"], c["node_pages"], c["by_page_type"]))
    print("\nTRUE COVERAGE against the live catalogues")
    for ctx, c in res["contexts"].items():
        print("  %-5s live=%3d  EXACT=%3d (%.1f%%)  +BASE=%3d (%.1f%%)  ELSEWHERE=%2d  ABSENT=%3d"
              % (ctx, c["live_types"], c["EXACT"], c["coverage_exact_pct"],
                 c["EXACT"] + c["BASE"], c["coverage_with_base_pct"],
                 c["ELSEWHERE"], c["ABSENT"]))
        print("        absent breakdown:", c["absent_breakdown"])
        print("        absent sample   :", c["absent_types"][:12])
    nc = res["negative_control"]
    print("\nNEGATIVE CONTROL: correct=%d broken=%d -> %s"
          % (nc["correct_rule_covered"], nc["broken_rule_covered"], nc["verdict"]))
    print("\nwrote", OUT)
