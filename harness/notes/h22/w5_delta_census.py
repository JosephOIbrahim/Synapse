"""W5-DELTA -- census the .368->.400 served-corpus re-promote.

Compares the backed-up .368 corpus (harness/notes/h22/h22_nodes.368.backup.json)
against the freshly promoted .400 corpus (rag/corpus/h22_nodes.json) at the
(context, type) MULTISET level -- the granularity the mission's zero-loss rule is
stated in: "every currently-served (context,type) survives; collisions keep both;
deletions forbidden; adds/changes receipted with counts".

Emits:
  * harness/notes/h22/w5_delta_census.json  -- the full receipt (counts, added,
    dropped, id-level survival, content changes, anatomy cross-check)
  * harness/notes/h22/w5_delta_368_baseline.json -- a SLIM, durable baseline
    (per-context counts + the sorted (ctx,type) multiset + the id set) so the
    pytest can pin zero-loss after the .368 backup is gone.

House rule: a value that cannot be computed is UNKNOWN, never zero.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKUP = HERE / "h22_nodes.368.backup.json"
SERVED = REPO / "rag" / "corpus" / "h22_nodes.json"
CENSUS_OUT = HERE / "w5_delta_census.json"
BASELINE_OUT = HERE / "w5_delta_368_baseline.json"

CONTEXTS = ("cop", "lop", "cop2")


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _keymultiset(entries):
    return Counter((e["context"], e["type"]) for e in entries)


def _ids(entries):
    return [e["id"] for e in entries]


def _content_sig(e):
    """A stable signature of an entry's served content: label + summary + the full
    ordered parameter surface INCLUDING descriptions. Changes here are legitimate
    .400 doc refreshes (datasheet content served by knowledge.py) and are RECEIPTED,
    never treated as loss -- they are the substantive value of re-promoting."""
    params = e.get("parameters") or []
    return (e.get("label"), e.get("summary"), len(params),
            tuple((p.get("label"), tuple(p.get("ids") or []), tuple(p.get("channels") or []),
                   p.get("description"))
                  for p in params))


def census():
    old = _load(BACKUP)
    new = _load(SERVED)
    oe, ne = old["entries"], new["entries"]

    ok_keys, nk_keys = _keymultiset(oe), _keymultiset(ne)
    old_ids, new_ids = set(_ids(oe)), set(_ids(ne))

    # --- zero-loss at the (context,type) multiset level ----------------------
    dropped = {}   # (ctx,type) -> how many copies were LOST (old count - new count, if >0)
    for k, n_old in ok_keys.items():
        n_new = nk_keys.get(k, 0)
        if n_new < n_old:
            dropped["%s/%s" % k] = {"was": n_old, "now": n_new, "lost": n_old - n_new}
    added = {}
    for k, n_new in nk_keys.items():
        n_old = ok_keys.get(k, 0)
        if n_new > n_old:
            added["%s/%s" % k] = {"was": n_old, "now": n_new, "gained": n_new - n_old}

    # --- id-level survival (ids are (ctx,type)-qualified w/ #n discriminators) --
    lost_ids = sorted(old_ids - new_ids)
    new_only_ids = sorted(new_ids - old_ids)

    # --- content changes on surviving ids (informational, receipted) ---------
    old_by_id = {e["id"]: e for e in oe}
    new_by_id = {e["id"]: e for e in ne}
    changed = []
    for i in sorted(old_ids & new_ids):
        so, sn = _content_sig(old_by_id[i]), _content_sig(new_by_id[i])
        if so != sn:
            changed.append({
                "id": i,
                "label_368": old_by_id[i].get("label"), "label_400": new_by_id[i].get("label"),
                "nparams_368": so[2], "nparams_400": sn[2],
                "summary_changed": so[1] != sn[1],
                "params_changed": so[3] != sn[3],
            })

    per_ctx = {}
    for ctx in CONTEXTS:
        o = sum(v for (c, _t), v in ok_keys.items() if c == ctx)
        n = sum(v for (c, _t), v in nk_keys.items() if c == ctx)
        per_ctx[ctx] = {"count_368": o, "count_400": n, "delta": n - o,
                        "meets_ge": n >= o}

    # --- anatomy cross-check against the live-verified .400 anatomy doc -------
    anat = anatomy_crosscheck(ne)

    return {
        "leg": "W5-DELTA / ING-DELTA",
        "compared": {"from": str(BACKUP), "to": str(SERVED)},
        "build_368": old.get("build"), "build_400": new.get("build"),
        "source_archive_368": old.get("source_archive"),
        "source_archive_400": new.get("source_archive"),
        "totals": {"entries_368": len(oe), "entries_400": len(ne),
                   "excluded_368": old.get("counts", {}).get("excluded"),
                   "excluded_400": new.get("counts", {}).get("excluded")},
        "per_context": per_ctx,
        "zero_loss": {
            "dropped_context_type_keys": dropped,          # MUST be empty
            "lost_ids": lost_ids,                          # MUST be empty
            "verdict": "PASS" if not dropped and not lost_ids else "FAIL",
        },
        "adds": {"added_context_type_keys": added, "new_only_ids": new_only_ids},
        "changes": {"n_changed": len(changed), "changed": changed[:200],
                    "changed_truncated": max(0, len(changed) - 200)},
        "collisions_kept_both": _collisions(nk_keys),
        "anatomy_crosscheck": anat,
    }


def _collisions(km):
    """(ctx,type) keys served more than once -- the 'keep both' set (pyro_* dups)."""
    return {"%s/%s" % k: v for k, v in km.items() if v > 1}


def anatomy_crosscheck(entries):
    """No .400 corpus entry may contradict the live-verified compound-node anatomy:
      * NO karmamaterial* type is served (the tab entry is a configured subnet).
      * NO 'instancer' type is served (the tab resolves to copytopoints).
      * copytopoints IS served (the real Solaris instancer type).
      * componentgeometry IS served (its H22 'alternative' output is internal topology
        the corpus does not enumerate -> no field can contradict it; recorded for audit)."""
    by = {(e["context"], e["type"]): e for e in entries}
    km = sorted(e for e in entries if "karmamaterial" in (e["type"] or "").lower())
    ins = sorted((e["context"], e["type"]) for e in entries if e["type"] == "instancer")
    cg = by.get(("lop", "componentgeometry"))
    ctp = by.get(("lop", "copytopoints"))
    contradictions = []
    if km:
        contradictions.append("karmamaterial* type served (phantom): %s"
                              % [(e["context"], e["type"]) for e in km])
    if ins:
        contradictions.append("instancer type served (should be copytopoints): %s" % ins)
    if ctp is None:
        contradictions.append("copytopoints NOT served (the real Solaris instancer type is missing)")
    return {
        "karmamaterial_star_served": [(e["context"], e["type"]) for e in km],
        "instancer_type_served": ins,
        "copytopoints_served": ctp is not None,
        "componentgeometry_served": cg is not None,
        "componentgeometry_nparams": (len(cg.get("parameters") or []) if cg else None),
        "componentgeometry_note": ("H22 'alternative' output is internal sopnet/geo topology; "
                                   "the corpus stores summary+parameters, not output-node lists, "
                                   "so no served field can contradict the anatomy doc."),
        "contradictions": contradictions,
        "verdict": "PASS" if not contradictions else "FAIL",
    }


def slim_baseline():
    old = _load(BACKUP)
    oe = old["entries"]
    km = _keymultiset(oe)
    per_ctx = {ctx: sum(v for (c, _t), v in km.items() if c == ctx) for ctx in CONTEXTS}
    return {
        "note": "W5-DELTA durable .368 zero-loss baseline. The served .400 corpus MUST cover "
                "every (context,type) key below at >= its multiplicity, and carry every id. "
                "Pinned by tests/test_w5_delta_promote_400.py so the guarantee survives the "
                "backup's deletion.",
        "build": old.get("build"),
        "per_context_counts": per_ctx,
        "total": len(oe),
        "context_type_multiset": sorted("%s/%s|%d" % (c, t, n) for (c, t), n in km.items()),
        "ids": sorted(e["id"] for e in oe),
    }


def main() -> int:
    c = census()
    CENSUS_OUT.write_text(json.dumps(c, indent=1), encoding="utf-8")
    BASELINE_OUT.write_text(json.dumps(slim_baseline(), indent=1), encoding="utf-8")

    print("BUILD  %s -> %s" % (c["build_368"], c["build_400"]))
    print("SOURCE %s" % c["source_archive_400"])
    print("per-context (368 -> 400, delta, >=):")
    for ctx in CONTEXTS:
        p = c["per_context"][ctx]
        print("  %-5s %4d -> %4d  (%+d)  ge=%s" % (ctx, p["count_368"], p["count_400"],
                                                   p["delta"], p["meets_ge"]))
    zl = c["zero_loss"]
    print("ZERO-LOSS: %s  dropped_keys=%d  lost_ids=%d"
          % (zl["verdict"], len(zl["dropped_context_type_keys"]), len(zl["lost_ids"])))
    if zl["dropped_context_type_keys"]:
        print("  DROPPED:", zl["dropped_context_type_keys"])
    if zl["lost_ids"]:
        print("  LOST IDS:", zl["lost_ids"][:20])
    ad = c["adds"]
    print("ADDS: keys=%d new_ids=%d %s"
          % (len(ad["added_context_type_keys"]), len(ad["new_only_ids"]),
             ad["new_only_ids"][:20]))
    print("CHANGES (content refresh on surviving ids): %d" % c["changes"]["n_changed"])
    print("COLLISIONS kept-both: %d keys" % len(c["collisions_kept_both"]))
    an = c["anatomy_crosscheck"]
    print("ANATOMY: %s  karmamaterial*=%s instancer=%s copytopoints=%s componentgeometry=%s"
          % (an["verdict"], an["karmamaterial_star_served"], an["instancer_type_served"],
             an["copytopoints_served"], an["componentgeometry_served"]))
    if an["contradictions"]:
        print("  CONTRADICTIONS:", an["contradictions"])
    print("wrote %s + %s" % (CENSUS_OUT.name, BASELINE_OUT.name))
    return 0 if (zl["verdict"] == "PASS" and an["verdict"] == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
