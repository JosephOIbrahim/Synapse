"""H9 Work 4 -- cross-check the harvested documentation against the live runtime.

RUN INSIDE THE TARGET BUILD:

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython3.13.exe" \
        harness/notes/h9/crosscheck_runtime.py

Writes harness/notes/h9/crosscheck.json.

THE QUESTION
------------
Documentation is D2 (semantic) and can be stale. R72 is the proof: the runtime
flags nodes/lop/karmarenderproperties deprecated and the 56KB page never says
so. This leg's corpus inherits that class of defect wholesale, so it must be
measured rather than assumed small.

For a random sample of 10 LOP + 10 COP types, compare the internal parameter
names the DOCUMENTATION declares (``#id:`` / ``#channels:``) against the parameter
names the LIVE NODE TYPE actually has. **Where they disagree, the docs are wrong**
-- the runtime is the authority (Article II: observed beats documented).

SAMPLING FRAME, stated because it changes what the number means
---------------------------------------------------------------
The sample is drawn from types whose page reaches the ACTIONABLE rung, i.e.
declares at least one internal parameter id. Types with no documented id have
nothing name-shaped to compare, so including them would measure the corpus's
coverage a second time instead of its accuracy. The frame is reported alongside
the result as a fraction of the full catalogue, so the reader can see what the
sample does and does not speak for.

Seeded (SEED below) so a re-run selects the same 20 types.

CONTROLS
--------
1. positive control on the PROBE: the committed COP catalogue already carries a
   live ``parms`` list per type. If this script's runtime harvest disagrees with
   that artifact, the probe is broken and no disagreement it reports about the
   docs can be trusted.
2. negative control on the COMPARISON: documented ids are also compared against a
   DIFFERENT node's live parms. If a shuffled pairing scores as well as the true
   pairing, the metric is not measuring agreement (Law 1).
3. a full-population sweep over every type with a page, as corroboration for the
   n=20 oracle. The sample is the brief's oracle; the sweep says whether the
   sample was lucky.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

H9 = Path(__file__).resolve().parent
NOTES = H9.parent
REPO = NOTES.parent.parent
CORPUS = NOTES / "h22_doc_grounding_corpus.json"
COP_CAT = NOTES / "h22_cop_catalog_live_22.0.368.json"
OUT = H9 / "crosscheck.json"

SEED = 20260727
SAMPLE_N = 10

import hou  # noqa: E402  (only meaningful under hython)


# --------------------------------------------------------------------------
# API existence first -- Safety Rule 15: verify an unfamiliar surface before
# leaning on it, and record the verdict rather than assuming.
# --------------------------------------------------------------------------
def api_probe() -> dict:
    return {
        "hou.nodeTypeCategories": hasattr(hou, "nodeTypeCategories"),
        "hou.NodeType.parmTemplateGroup": hasattr(hou.NodeType, "parmTemplateGroup"),
        "hou.ParmTemplateGroup.entries": hasattr(hou.ParmTemplateGroup, "entries"),
        "hou.FolderParmTemplate.parmTemplates": hasattr(
            hou.FolderParmTemplate, "parmTemplates"),
        "houdini_build": hou.applicationVersionString(),
    }


def walk_templates(group) -> list[dict]:
    """Every parameter template, folders recursed.

    Instantiation-free: reading the TYPE's template group avoids creating a node
    per type, which on 600 types would be slow and would mutate the scene.
    """
    out: list[dict] = []

    def rec(templates, depth=0):
        for t in templates:
            try:
                name = t.name()
            except Exception:
                continue
            kids = None
            if hasattr(t, "parmTemplates"):
                try:
                    kids = t.parmTemplates()
                except Exception:
                    kids = None
            # Folders are containers; they also occupy a parm name. Recorded
            # with is_folder so the comparison can choose to exclude them.
            out.append({
                "name": name,
                "label": getattr(t, "label", lambda: None)(),
                "is_folder": kids is not None,
                "depth": depth,
            })
            if kids:
                rec(kids, depth + 1)

    try:
        rec(group.entries())
    except Exception as exc:  # pragma: no cover - live-only path
        out.append({"name": "<ERROR>", "label": str(exc), "is_folder": False, "depth": 0})
    return out


def live_parms(category, type_name: str) -> dict:
    nt = hou.nodeType(category, type_name)
    if nt is None:
        return {"found": False, "parms": [], "error": "hou.nodeType returned None"}
    try:
        g = nt.parmTemplateGroup()
    except Exception as exc:
        return {"found": True, "parms": [], "error": "parmTemplateGroup: %s" % exc}
    tpl = walk_templates(g)
    return {
        "found": True,
        "parms": tpl,
        "names": sorted({t["name"] for t in tpl if not t["is_folder"]}),
        "all_names": sorted({t["name"] for t in tpl}),
        "labels": sorted({(t["label"] or "") for t in tpl if t["label"]}),
        "deprecated": bool(nt.deprecated()),
        "error": None,
    }


def normalise(n: str) -> str:
    """Multiparm templates end in '#' ('copy#'); an instance is 'copy1'.

    Reported as a SEPARATE, looser metric -- never folded into the strict count,
    because normalisation manufactures agreement and the strict number is the
    one that says whether an emitter could use the documented name verbatim.
    """
    return n.rstrip("#").rstrip("0123456789")


def compare(doc_ids: list[str], live: dict) -> dict:
    live_all = set(live.get("all_names") or [])
    doc = [d for d in doc_ids if d]
    matched = [d for d in doc if d in live_all]
    unmatched = [d for d in doc if d not in live_all]
    live_norm = {normalise(n) for n in live_all}
    loose = [d for d in unmatched if normalise(d) in live_norm]
    # Decomposition: a colon-namespaced id is a USD attribute name, and the docs
    # are not claiming it is a parm. Reported SEPARATELY, never substituted for
    # the headline -- excluding the ids that fail is how a real disagreement gets
    # tuned into a clean number.
    plain = [d for d in doc if ":" not in d]
    plain_matched = [d for d in plain if d in live_all]
    return {
        "documented_ids": len(doc),
        "live_parms": len(live_all),
        "matched_strict": len(matched),
        "unmatched": len(unmatched),
        "matched_loose_extra": len(loose),
        "unmatched_examples": unmatched[:12],
        "precision_strict": round(len(matched) / len(doc), 3) if doc else None,
        "undocumented_live": len(live_all) - len(matched),
        "usd_shaped_ids": len(doc) - len(plain),
        "plain_ids": len(plain),
        "plain_matched": len(plain_matched),
    }


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cats = {c.name(): c for c in hou.nodeTypeCategories().values()}
    ctx_cat = {"lop": cats.get("Lop"), "cop": cats.get("Cop"), "cop2": cats.get("Cop2")}

    result = {
        "schema": "h9_crosscheck/v1",
        "truth_tier": "VERIFIED-RUNTIME",
        "producer": "harness/notes/h9/crosscheck_runtime.py",
        "seed": SEED,
        "api_probe": api_probe(),
        "categories_found": {k: (v.name() if v else None) for k, v in ctx_cat.items()},
    }

    by_ctx: dict[str, list[dict]] = {}
    for e in corpus["entries"]:
        by_ctx.setdefault(e["context"], []).append(e)

    # ---------------- sampled oracle (the brief's 10 + 10) ----------------
    rng = random.Random(SEED)
    samples: dict[str, list[dict]] = {}
    for ctx in ("lop", "cop"):
        frame = sorted([e for e in by_ctx.get(ctx, []) if e["quality"]["actionable"]],
                       key=lambda e: e["type"])
        picked = rng.sample(frame, min(SAMPLE_N, len(frame)))
        rows = []
        for e in picked:
            ids = sorted({i for p in e["parameters"] for i in p["ids"]})
            lv = live_parms(ctx_cat[ctx], e["type"])
            cmpres = compare(ids, lv)
            rows.append({
                "type": e["type"], "help_key": e["help_key"],
                "live_found": lv["found"], "live_error": lv.get("error"),
                "runtime_deprecated": lv.get("deprecated"),
                "doc_says_deprecated": e["caveats"]["doc_mentions_deprecated"],
                **cmpres,
            })
        samples[ctx] = rows
        result.setdefault("sampling_frame", {})[ctx] = {
            "frame_size": len(frame),
            "catalogue_size": len(by_ctx.get(ctx, [])),
            "frame_note": "types whose page declares >=1 internal parameter id",
        }
    result["sample"] = samples

    agree = {}
    for ctx, rows in samples.items():
        full = [r for r in rows if r["documented_ids"] and r["unmatched"] == 0]
        agree[ctx] = {
            "nodes_sampled": len(rows),
            "nodes_in_full_agreement": len(full),
            "documented_ids_total": sum(r["documented_ids"] for r in rows),
            "matched_strict_total": sum(r["matched_strict"] for r in rows),
            "unmatched_total": sum(r["unmatched"] for r in rows),
        }
        t = agree[ctx]["documented_ids_total"]
        agree[ctx]["id_level_agreement_pct"] = (
            round(100.0 * agree[ctx]["matched_strict_total"] / t, 1) if t else None)
        p = sum(r["plain_ids"] for r in rows)
        agree[ctx]["usd_shaped_ids_total"] = sum(r["usd_shaped_ids"] for r in rows)
        agree[ctx]["plain_ids_total"] = p
        agree[ctx]["plain_matched_total"] = sum(r["plain_matched"] for r in rows)
        agree[ctx]["plain_id_agreement_pct"] = (
            round(100.0 * agree[ctx]["plain_matched_total"] / p, 1) if p else None)
    result["agreement"] = agree
    result["agreement_note"] = (
        "id_level_agreement_pct is the HEADLINE: of every internal id the docs "
        "declare, how many exist on the live type. plain_id_agreement_pct is the "
        "same figure with colon-namespaced (USD attribute) ids removed -- reported "
        "for diagnosis, never as the result.")

    # ---------------- control 1: probe vs committed COP catalogue ----------
    copcat = json.loads(COP_CAT.read_text(encoding="utf-8"))
    coptypes = copcat["categories"]["copNodeTypeCategory"]["types"]
    checked = agreed = 0
    diffs = []
    for r in samples.get("cop", []):
        rec = coptypes.get(r["type"])
        if not rec or "parms" not in rec:
            continue
        lv = live_parms(ctx_cat["cop"], r["type"])
        checked += 1
        a = set(rec["parms"])
        b = set(lv.get("names") or [])          # non-folder templates
        allb = set(lv.get("all_names") or [])   # + folder/ramp/multiparm containers
        # The claim under test is 'this probe did not MISS a parameter the earlier
        # harvest saw'. Set equality is the wrong criterion and returned a bare
        # INVESTIGATE: the two harvests represent ramp and multiparm containers
        # differently (catalogue keeps 'bevelramp', this walk descends to
        # 'bevelramp#value'). Adjudicated in mismatch_diagnosis.json. The subset
        # relation is the real claim and can still fail.
        if a <= allb:
            agreed += 1
        else:
            diffs.append({"type": r["type"],
                          "missed_by_probe": sorted(a - allb)[:8],
                          "representation_only": sorted(a - b)[:8]})
    result["control_probe_vs_catalogue"] = {
        "purpose": "positive control on THIS PROBE. The committed COP catalogue "
                   "carries live parms harvested previously. If this run MISSES a "
                   "parameter that harvest saw, the probe is broken and its "
                   "verdicts about the docs are worthless.",
        "criterion": "every catalogue parm appears in this probe's walk (subset)",
        "types_checked": checked, "no_parameter_missed": agreed,
        "differences": diffs[:6],
        "adjudication": "harness/notes/h9/mismatch_diagnosis.json",
        "verdict": "PASS" if checked and agreed == checked else
                   ("NO-DATA" if not checked else "FAIL"),
    }

    # ---------------- control 2: shuffled pairing --------------------------
    shuffled = {}
    for ctx, rows in samples.items():
        ents = {e["type"]: e for e in by_ctx[ctx]}
        types = [r["type"] for r in rows]
        rot = types[1:] + types[:1]
        tot = mat = 0
        for src, dst in zip(types, rot):
            ids = sorted({i for p in ents[src]["parameters"] for i in p["ids"]})
            lv = live_parms(ctx_cat[ctx], dst)
            c = compare(ids, lv)
            tot += c["documented_ids"]
            mat += c["matched_strict"]
        shuffled[ctx] = {
            "documented_ids_total": tot, "matched_strict_total": mat,
            "id_level_agreement_pct": round(100.0 * mat / tot, 1) if tot else None,
        }
    result["control_shuffled_pairing"] = {
        "purpose": "negative control on the COMPARISON. Documented ids scored "
                   "against a DIFFERENT node's live parms. A metric that cannot "
                   "tell these apart is not measuring agreement (Law 1).",
        "result": shuffled,
        "verdict": "PASS" if all(
            (shuffled[c]["id_level_agreement_pct"] or 0)
            < (agree[c]["id_level_agreement_pct"] or 0) for c in shuffled) else "FAIL",
    }

    # ---------------- corroboration: full-population sweep -----------------
    sweep = {}
    for ctx in ("lop", "cop", "cop2"):
        if ctx_cat.get(ctx) is None:
            continue
        tot = mat = nodes = full_ok = missing = 0
        ptot = pmat = usdn = 0
        worst = []
        for e in by_ctx.get(ctx, []):
            ids = sorted({i for p in e["parameters"] for i in p["ids"]})
            if not ids:
                continue
            lv = live_parms(ctx_cat[ctx], e["type"])
            if not lv["found"]:
                missing += 1
                continue
            c = compare(ids, lv)
            nodes += 1
            tot += c["documented_ids"]
            mat += c["matched_strict"]
            ptot += c["plain_ids"]
            pmat += c["plain_matched"]
            usdn += c["usd_shaped_ids"]
            if c["unmatched"] == 0:
                full_ok += 1
            elif c["unmatched"] > 3:
                worst.append({"type": e["type"], "unmatched": c["unmatched"],
                              "documented": c["documented_ids"],
                              "usd_shaped": c["usd_shaped_ids"],
                              "examples": c["unmatched_examples"][:6]})
        worst.sort(key=lambda x: -x["unmatched"])
        sweep[ctx] = {
            "nodes_compared": nodes,
            "nodes_in_full_agreement": full_ok,
            "documented_ids_total": tot,
            "matched_strict_total": mat,
            "id_level_agreement_pct": round(100.0 * mat / tot, 1) if tot else None,
            "usd_shaped_ids_total": usdn,
            "plain_ids_total": ptot,
            "plain_matched_total": pmat,
            "plain_id_agreement_pct": round(100.0 * pmat / ptot, 1) if ptot else None,
            "type_not_found_on_build": missing,
            "worst_offenders": worst[:12],
        }
    result["full_population_sweep"] = sweep

    # ---------------- deprecation cross-check (R72 class) ------------------
    dep = []
    for ctx in ("lop", "cop", "cop2"):
        if ctx_cat.get(ctx) is None:
            continue
        for e in by_ctx.get(ctx, []):
            lv_nt = hou.nodeType(ctx_cat[ctx], e["type"])
            if lv_nt is None:
                continue
            if lv_nt.deprecated() and not e["caveats"]["doc_mentions_deprecated"]:
                dep.append({"type": e["type"], "context": ctx,
                            "help_key": e["help_key"]})
    result["silent_deprecation_live"] = {
        "purpose": "R72 re-measured against the LIVE runtime rather than the "
                   "committed catalogue.",
        "count": len(dep), "types": dep[:40],
    }

    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({
        "api_probe": result["api_probe"],
        "agreement": result["agreement"],
        "control_probe_vs_catalogue": {
            k: v for k, v in result["control_probe_vs_catalogue"].items()
            if k != "differences"},
        "control_shuffled": result["control_shuffled_pairing"]["result"],
        "control_shuffled_verdict": result["control_shuffled_pairing"]["verdict"],
        "sweep": {k: {kk: vv for kk, vv in v.items() if kk != "worst_offenders"}
                  for k, v in sweep.items()},
        "silent_deprecation_live": result["silent_deprecation_live"]["count"],
    }, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
