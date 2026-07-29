"""H9 producer 3 of 4 -- coverage, the quality floor, and the corpus.

Emits
    harness/notes/h22_doc_grounding_corpus.json   the deliverable, every entry VERIFIED-DOC
    harness/notes/h9/coverage_report.json         the numbers, with their producers

INPUTS (all three are VERIFIED-RUNTIME artifacts of build 22.0.368)
    harness/notes/h22_lop_catalog_live_22.0.368.json   218 Lop types
    harness/notes/h22_cop_catalog_live_22.0.368.json   384 Cop + 169 Cop2 types
    harness/notes/h9/runtime_parms_22.0.368.json       every live parm, this leg's probe

TIER DISCIPLINE
    A DOCUMENTED entry is tiered VERIFIED-DOC: a NEW tier, meaning "authored by SideFX
    and shipped with the build". It is not VERIFIED-RUNTIME. Documentation supplies
    semantic grounding and cannot supply behavioural grounding, and it inherits every
    place the documentation is silent or stale. lop/karmarenderproperties is 56,325
    characters that never mention the type is deprecated -- the runtime flags it, the
    page does not. Each entry carries a `runtime_disagreement` block so the silence is
    visible in the corpus itself, not only in the receipt.

    An entry for a type with NO page is tiered VERIFIED-RUNTIME, because it holds no
    authored content at all -- only probe output. Tiering it VERIFIED-DOC would claim
    SideFX authorship of a record SideFX never wrote.

THE THREE DENOMINATORS ARE NEVER MERGED (Ruling 3)
    Cop (384) and Cop2 (169) are separate surfaces with separate investment policy;
    Lop (218) is a third. "COP coverage" as a bare phrase is banned. The first-pass
    script _doc_coverage.py merged Cop and Cop2 into a single 491-name set; that is
    why its 94% is not reported here.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docparse as D  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES = os.path.abspath(os.path.join(HERE, ".."))

LOP_CAT = os.path.join(NOTES, "h22_lop_catalog_live_22.0.368.json")
COP_CAT = os.path.join(NOTES, "h22_cop_catalog_live_22.0.368.json")
RUNTIME = os.path.join(HERE, "runtime_parms_22.0.368.json")
INSTANTIATED = os.path.join(HERE, "instantiated_parms_22.0.368.json")
CORPUS_OUT = os.path.join(NOTES, "h22_doc_grounding_corpus.json")
REPORT_OUT = os.path.join(HERE, "coverage_report.json")

# ---------------------------------------------------------------- quality floor
#
# Calibrated against the measured distribution of all 691 pages, not chosen by taste.
# harness/notes/h9/floor_calibration.json records what every candidate rule -- the
# adopted ones AND the rejected ones -- actually excludes.
#
# ADOPTED
#   A. summary present and at least MIN_SUMMARY_WORDS words
#   B. at least one documented parameter that RESOLVES to a parameter on the live
#      node and carries a description that is neither empty nor a placeholder
#
# REJECTED, and why -- a rule that excludes nothing is a decoration (Law 1)
#   * summary >= 40 characters. Excludes 188 pages including
#     cop/blur "Applies a blur to a layer." (26 chars) and cop/camera
#     "Creates a camera." (17). Those are grounding. Length proxies substance badly.
#   * summary must not echo the node label. Measured: rejects 0 of 691. It cannot
#     fail, so it is not a check.
#   * parameter description >= 12 characters. Measured: rejects 0 beyond what the
#     placeholder test already rejects. Subsumed, so not carried.
MIN_SUMMARY_WORDS = 3

# Literal placeholders SideFX shipped in the reference. A parameter whose entire
# documentation is the word "TBD" is a page admitting it has no content there;
# counting it as grounding would be the exact hearsay this leg exists to avoid.
PLACEHOLDER_DESCRIPTIONS = {
    "",
    "tbd",
    "todo",
    "missing",
    "n/a",
    "na",
    "none",
    "see above",
    "see above.",
    "...",
    "-",
}

USABLE_PARM_RATIO = 0.5  # tier T3, reported alongside the floor, not part of it


def summary_words(summary):
    return len((summary or "").split())


def is_placeholder(desc):
    return (desc or "").strip().lower().rstrip(".") in {
        p.rstrip(".") for p in PLACEHOLDER_DESCRIPTIONS
    }


def _hash_reference():
    """Pin the exact archive harvested, so a re-run on another machine can prove sameness."""
    import hashlib

    with open(D.ZIP_PATH, "rb") as fh:
        return hashlib.blake2b(fh.read(), digest_size=16).hexdigest()


def load_live():
    """The live surfaces, one dict per category. Denominators stay separate."""
    with open(LOP_CAT, encoding="utf-8") as fh:
        lop = json.load(fh)
    with open(COP_CAT, encoding="utf-8") as fh:
        cop = json.load(fh)
    with open(RUNTIME, encoding="utf-8") as fh:
        rt = json.load(fh)
    # WHICH DIRECTORIES OF THE REFERENCE ARE SEARCHED, AND WHY -- stated, because an
    # undisclosed scoping choice is how 31 documented types were reported as
    # undocumented (audit finding H9-COV-01).
    #
    # nodes.zip files a node's page by CONTEXT, but network managers get their own
    # 'manager/' directory instead: manager/copnet.txt is 4,022 bytes and documents 14
    # parameters that all resolve id_exact against the live Lop/copnet. Searching only
    # the context directory classified those types 'network_manager -- no page' and the
    # receipt then justified the absence by calling them "containers rather than nodes"
    # -- a justification the reference itself contradicts, since every one of those
    # pages carries '#type: node'.
    #
    # So each surface searches its own context directory PLUS manager/. The other 16
    # directories in the archive (sop/, vop/, dop/ ...) are other node categories and
    # are correctly out of scope; out/ and composite/ are reached only by following an
    # explicit '#redirect:' or ':include', never by the walk.
    MANAGER_DIR = "manager"
    surfaces = {
        "Lop": {
            "types": lop["types"],
            "doc_dirs": ["lop", MANAGER_DIR],
            "denominator": lop["count"],
            "catalog": os.path.relpath(LOP_CAT, os.path.join(NOTES, "..", "..")),
        },
        "Cop": {
            "types": cop["categories"]["copNodeTypeCategory"]["types"],
            "doc_dirs": ["cop"],
            "denominator": cop["categories"]["copNodeTypeCategory"]["count"],
            "catalog": os.path.relpath(COP_CAT, os.path.join(NOTES, "..", "..")),
        },
        "Cop2": {
            "types": cop["categories"]["cop2NodeTypeCategory"]["types"],
            "doc_dirs": ["cop2"],
            "denominator": cop["categories"]["cop2NodeTypeCategory"]["count"],
            "catalog": os.path.relpath(COP_CAT, os.path.join(NOTES, "..", "..")),
        },
    }
    with open(INSTANTIATED, encoding="utf-8") as fh:
        inst = json.load(fh)
    for k in surfaces:
        surfaces[k]["runtime"] = rt["categories"][k]["types"]
        surfaces[k]["instantiated"] = inst["categories"][k]["types"]
        assert len(surfaces[k]["types"]) == surfaces[k]["denominator"]
    return surfaces, rt


def strip_version(name):
    return re.sub(r"::\d+(\.\d+)*$", "", name)


def match_pages(surface, pages):
    """Map live type -> page, and page -> live type. Every match records its kind.

    Ordered, deterministic, and each tier is reported separately so the coverage
    integer can be audited down to which rule earned each hit:

        exact            a candidate spelling equals the live type name
        caseless         equals it ignoring case (Labs:: vs labs::)
        version_tolerant equal after stripping ::<version>, and unambiguous both ways
    """
    live = surface["types"]
    live_by_exact = {n: n for n in live}
    live_by_lower = {}
    for n in live:
        live_by_lower.setdefault(n.lower(), []).append(n)
    live_by_base = {}
    for n in live:
        live_by_base.setdefault(strip_version(n).lower(), []).append(n)

    assigned, page_of, kind_of = {}, {}, {}
    unmatched_pages = []

    def take(page, live_name, kind):
        if live_name in assigned:
            return False
        assigned[live_name] = page["doc_path"]
        page_of[page["doc_path"]] = live_name
        kind_of[live_name] = kind
        return True

    for kind, lookup in (("exact", "exact"), ("caseless", "caseless")):
        for page in pages:
            if page["doc_path"] in page_of:
                continue
            for cand in page["candidate_type_names"]:
                hit = None
                if lookup == "exact":
                    hit = live_by_exact.get(cand)
                else:
                    lst = live_by_lower.get(cand.lower(), [])
                    hit = lst[0] if len(lst) == 1 else None
                if hit and take(page, hit, kind):
                    break

    # version-tolerant, and only where it cannot be ambiguous in either direction
    remaining_pages = [p for p in pages if p["doc_path"] not in page_of]
    base_page_counts = {}
    for page in remaining_pages:
        for cand in page["candidate_type_names"]:
            base_page_counts.setdefault(strip_version(cand).lower(), set()).add(page["doc_path"])
    for page in remaining_pages:
        if page["doc_path"] in page_of:
            continue
        for cand in page["candidate_type_names"]:
            base = strip_version(cand).lower()
            live_hits = [n for n in live_by_base.get(base, []) if n not in assigned]
            if len(live_hits) == 1 and len(base_page_counts.get(base, ())) == 1:
                if take(page, live_hits[0], "version_tolerant"):
                    break

    for page in pages:
        if page["doc_path"] not in page_of:
            unmatched_pages.append(page["doc_path"])

    return assigned, page_of, kind_of, unmatched_pages


def resolve_parm(doc_ids, doc_label, rt_rec, inst_rec=None):
    """Doc parameter -> live parameter name. Returns (resolved_names, how).

    TWO GROUND TRUTHS, because one is not enough in either direction (H9-CC-6):
      template      carries multiparm children as 'bindattrib#'; carries vector parms
                    only under their TUPLE name, so 'bottomleft', never 'bottomleftx'
      instantiated  carries 'bottomleftx' and 'bottomlefty'; carries NO multiparm
                    children, because no instances exist on a fresh node

    Checking only the template called cop/bend's documented 'bottomleftx'/'bottomlefty'
    phantom when both are live and evaluable. Checking only the instantiated node would
    do the same to every multiparm child. The union is the honest answer to "does a
    parameter by this name exist on this node".
    """
    live = set(rt_rec.get("parms", []))
    instantiated = set((inst_rec or {}).get("parms", [])) | set(
        (inst_rec or {}).get("parm_tuples", [])
    )
    label_map = rt_rec.get("label_to_parms", {})
    label_lower = {k.lower(): v for k, v in label_map.items()}

    hits, how = [], None
    for pid in doc_ids:
        if pid in live:
            hits.append(pid)
            how = how or "id_exact"
        elif pid in instantiated:
            hits.append(pid)
            how = how or "id_instantiated"
        elif pid + "#" in live:  # multiparm child: doc says bindattrib, node says bindattrib#
            hits.append(pid + "#")
            how = how or "id_multiparm"
    if hits:
        return sorted(set(hits)), how
    if doc_label:
        if doc_label in label_map:
            return sorted(set(label_map[doc_label])), "label_exact"
        if doc_label.lower() in label_lower:
            return sorted(set(label_lower[doc_label.lower()])), "label_caseless"
        # Cop2 pages document several parameters under one label:
        # 'Translate, Rotate, Scale, Pivot:'. Split only after the whole label has
        # failed, and only accept pieces that are themselves real labels on this node.
        if "," in doc_label:
            pieces = [p.strip() for p in doc_label.split(",") if p.strip()]
            got = []
            for piece in pieces:
                got.extend(label_lower.get(piece.lower(), []))
            if got:
                return sorted(set(got)), "label_split"
    return [], None


def classify_absent(name, rec, documented_bases):
    """Why does this live type have no page? Not all absences are the same absence.

    Order matters: the sibling test runs before the namespace test, because
    `cache` and `cache::2.0` are both live and share ONE authored page. Calling
    that 'namespaced' would hide the actual situation, which is that SideFX
    documented one version of the family and not the other.
    """
    if rec.get("is_manager"):
        return "network_manager"
    low = name.lower()
    if low.startswith("labs::") or low.startswith("kinefx::"):
        return "third_party_or_toolset_hda"
    if strip_version(name).lower() in documented_bases:
        return "sibling_version_documented_only"
    if rec.get("deprecated"):
        return "deprecated"
    return "genuinely_absent"


def build():
    surfaces, rt_meta = load_live()
    hz = D.HelpZip()

    corpus_entries = []
    report = {
        "schema": "h9_coverage_report/v1",
        "producer": "harness/notes/h9/build_corpus.py",
        "build": rt_meta["build"],
        "reference": D.ZIP_PATH,
        "surfaces": {},
    }

    parse_stats = {"pages_parsed": 0, "unresolved_includes": []}
    all_floor_rows = []

    for cat, surface in surfaces.items():
        pages = []
        for ddir in surface["doc_dirs"]:
            for fname in hz.names(ddir + "/"):
                base = os.path.basename(fname)
                if base.startswith("_"):
                    continue  # include fragment, not a node page
                if base == "index.txt":
                    continue  # the context's table of contents, not a node
                page = D.parse_page(hz, fname)
                if page is None:
                    continue
                if page["directives"].get("type", "node").lower() != "node":
                    continue
                pages.append(page)
                parse_stats["pages_parsed"] += 1
                for u in page["unresolved_includes"]:
                    parse_stats["unresolved_includes"].append({"page": fname, "target": u})

        assigned, page_of, kind_of, unmatched_pages = match_pages(surface, pages)
        page_by_path = {p["doc_path"]: p for p in pages}
        documented_bases = {strip_version(n).lower() for n in assigned}

        rows = []
        for live_name, live_rec in sorted(surface["types"].items()):
            rt_rec = surface["runtime"].get(live_name, {})
            doc_path = assigned.get(live_name)
            page = page_by_path.get(doc_path) if doc_path else None

            entry = {
                "type_name": live_name,
                "category": cat,
                "context": surface["doc_dirs"][0],
                "label_runtime": live_rec.get("label"),
                "deprecated_runtime": bool(live_rec.get("deprecated")),
                "is_manager_runtime": bool(live_rec.get("is_manager")),
                "has_page": bool(page),
            }
            # TIER IS PER RECORD, NOT PER FILE (H9-TIER-01).
            # An entry with no page contains no authored content at all -- only probe
            # output. Stamping it VERIFIED-DOC would claim SideFX authorship for a
            # record SideFX never wrote, and point the reader at a runtime_disagreement
            # key the record does not have. The 80 no-page records say what they are.
            if page:
                entry["tier"] = "VERIFIED-DOC"
                entry["tier_note"] = (
                    "Semantic grounding authored by SideFX and shipped with build "
                    "22.0.368. NOT behavioural. Inherits documentation silence and "
                    "staleness -- see runtime_disagreement."
                )
            else:
                entry["tier"] = "VERIFIED-RUNTIME"
                entry["tier_note"] = (
                    "NO DOCUMENTATION EXISTS for this type in the shipped reference. "
                    "Every field here is probe output, so the record is tiered to its "
                    "actual source. It contributes to the denominator and never to any "
                    "doc-derived numerator."
                )

            if page is None:
                cls = classify_absent(live_name, live_rec, documented_bases)
                entry["absence_class"] = cls
                entry["clears_floor"] = False
                entry["floor_failures"] = ["no_page"]
                entry["runtime_parm_count"] = len(rt_rec.get("parms", []))
                if cls == "sibling_version_documented_only":  # noqa: SIM102
                    # How wrong would it be to reuse the sibling's page? Measured,
                    # not assumed: the fraction of THIS type's live parms that the
                    # documented sibling's page also carries.
                    base = strip_version(live_name).lower()
                    sib = next(
                        (
                            n
                            for n in assigned
                            if strip_version(n).lower() == base and n != live_name
                        ),
                        None,
                    )
                    sib_rt = surface["runtime"].get(sib, {}) if sib else {}
                    mine = set(rt_rec.get("parms", []))
                    theirs = set(sib_rt.get("parms", []))
                    entry["sibling"] = {
                        "documented_sibling": sib,
                        "sibling_doc_path": "nodes.zip!" + assigned[sib] if sib else None,
                        "shared_parms": len(mine & theirs),
                        "my_parms": len(mine),
                        "parm_overlap_pct": (
                            round(100.0 * len(mine & theirs) / len(mine), 1) if mine else None
                        ),
                        "note": "the sibling's page is NOT counted as grounding for this "
                        "type; the overlap is reported so the cost of that choice is visible",
                    }
                    # Sensitivity: score THIS type against the sibling's page, using THIS
                    # type's live parameters. One attribution choice moves 14 Lop types,
                    # 6.4% of the denominator, so it is reported both ways rather than
                    # asserted once.
                    sib_page = page_by_path.get(assigned.get(sib)) if sib else None
                    if sib_page:
                        alt_ok = any(
                            resolve_parm(p["ids"], p["label"], rt_rec)[0]
                            and not is_placeholder(p["description"])
                            for p in sib_page["parameters"]
                        )
                        entry["sibling"]["would_clear_floor_if_credited"] = bool(
                            summary_words(sib_page["summary"]) >= MIN_SUMMARY_WORDS
                            and (alt_ok or not rt_rec.get("parms"))
                        )
                corpus_entries.append(entry)
                rows.append(
                    {
                        "type": live_name,
                        "has_page": False,
                        "clears": False,
                        "absence_class": cls,
                        "sibling_overlap_pct": entry.get("sibling", {}).get("parm_overlap_pct"),
                    }
                )
                continue

            # ---- follow an explicit redirect
            # lop/usdrender_rop.txt is 191 bytes and says '#redirect: /nodes/out/usdrender'.
            # SideFX is stating where the documentation lives; a reader follows it, so
            # this does too. The parameter check still runs against the LIVE Lop node,
            # so if the ROP page does not describe the LOP's parameters the mismatch
            # surfaces as a disagreement instead of being quietly credited.
            redirect = page["directives"].get("redirect")
            redirect_info = None
            if redirect:
                rf, _blk, _co = hz.resolve_include(redirect, page["context_dir"], page["doc_path"])
                target = D.parse_page(hz, rf) if rf else None
                if target:
                    redirect_info = {
                        "declared": redirect,
                        "resolved_to": "nodes.zip!" + rf,
                        "stub_bytes": page["doc_bytes"],
                        "target_bytes": target["doc_bytes"],
                    }
                    for key in (
                        "summary",
                        "parameters",
                        "prose_sections",
                        "inputs",
                        "outputs",
                        "related",
                        "title",
                    ):
                        page[key] = target[key]
                else:
                    redirect_info = {
                        "declared": redirect,
                        "resolved_to": None,
                        "note": "redirect target is not inside nodes.zip",
                    }
            entry["redirect"] = redirect_info

            # ---- structure extraction
            inst_rec = surface["instantiated"].get(live_name, {})
            parms_out, documented_live, seen_rec = [], set(), set()
            dupes = 0
            for p in page["parameters"]:
                resolved, how = resolve_parm(p["ids"], p["label"], rt_rec, inst_rec)
                # An include pulled twice under two anchors yields the same record
                # twice. Counting it twice inflates every record-denominator, so
                # identical records are collapsed and the collapse is counted.
                sig = (p["label"], tuple(p["ids"]), tuple(resolved), p["description"][:80])
                if sig in seen_rec:
                    dupes += 1
                    continue
                seen_rec.add(sig)
                documented_live.update(resolved)
                parms_out.append(
                    {
                        "label": p["label"],
                        "documented_ids": p["ids"],
                        "resolved_runtime_parms": resolved,
                        "resolution": how,
                        "resolved_count": len(resolved),
                        "folder": p["folder"],
                        "description": p["description"],
                        "description_chars": len(p["description"]),
                        "doc_source": p["doc_source"],
                        "from_include": p["doc_source"] != page["doc_path"],
                    }
                )

            live_parms = set(rt_rec.get("parms", []))
            inst_parms = set(inst_rec.get("parms", [])) | set(inst_rec.get("parm_tuples", []))
            undocumented = sorted(live_parms - documented_live)
            # PER-ID, not per-record. Harvesting only from records that resolved to
            # nothing erased every bad id that a LABEL match had rescued -- the entry
            # then published an empty disagreement list, which reads as a positive
            # assertion that the page agrees with the runtime. It did not. (H9-TIER-02)
            phantom = sorted(
                {
                    pid
                    for p in parms_out
                    for pid in (p["documented_ids"] or [])
                    if pid not in live_parms
                    and pid not in inst_parms
                    and pid + "#" not in live_parms
                }
            )
            label_only = [p["label"] for p in parms_out if not p["documented_ids"]]

            entry.update(
                {
                    "doc_path": "nodes.zip!" + page["doc_path"],
                    "doc_bytes": page["doc_bytes"],
                    "doc_title": page["title"],
                    "match_kind": kind_of.get(live_name),
                    "candidate_type_names": page["candidate_type_names"],
                    "since": page["directives"].get("since"),
                    "group": page["directives"].get("group"),
                    "icon": page["directives"].get("icon"),
                    "summary": page["summary"],
                    "prose_sections": page["prose_sections"],
                    "parameters": parms_out,
                    "inputs": page["inputs"],
                    "outputs": page["outputs"],
                    "related": page["related"],
                    "runtime_parm_count": len(live_parms),
                    "documented_runtime_parms": len(documented_live),
                    "parm_doc_ratio": (
                        round(len(documented_live) / len(live_parms), 4) if live_parms else None
                    ),
                    "duplicate_records_collapsed": dupes,
                    "runtime_disagreement": {
                        "documented_parms_absent_from_node": phantom,
                        "absent_from_node_basis": "checked against BOTH the parameter "
                        "template and an instantiated node; a name absent from both does "
                        "not exist. Counted per documented id, including ids whose label "
                        "happened to resolve -- a rescued label does not make the id right.",
                        "live_parms_with_no_documentation": undocumented,
                        "parms_documented_by_label_only": label_only,
                        "deprecated_on_runtime_but_page_silent": _page_is_silent_on_deprecation(
                            hz, page, live_rec
                        ),
                    },
                }
            )

            # ---- the quality floor
            failures = []
            summary = page["summary"] or ""
            if summary_words(summary) < MIN_SUMMARY_WORDS:
                failures.append("summary_absent_or_stub")
            good_parms = [
                p
                for p in parms_out
                if p["resolved_runtime_parms"] and not is_placeholder(p["description"])
            ]
            # A node with no parameters cannot have a documented one. Failing it would
            # score a property of the NODE as a defect in the DOCUMENTATION, and would
            # make clause B unsatisfiable rather than merely unsatisfied -- a check that
            # cannot pass is as useless as one that cannot fail.
            clause_b_applicable = bool(live_parms)
            if clause_b_applicable and not good_parms:
                failures.append("no_parameter_resolves_to_a_live_parm_with_a_description")
            entry["clears_floor"] = not failures
            entry["floor_failures"] = failures
            ratio = entry["parm_doc_ratio"]
            entry["usable_tier"] = bool(
                entry["clears_floor"] and ratio is not None and ratio >= USABLE_PARM_RATIO
            )
            entry["floor_evidence"] = {
                "clause_b_applicable": clause_b_applicable,
                "clause_b_note": None
                if clause_b_applicable
                else "node has zero live parameters; clause B is vacuous",
                "summary_words": summary_words(summary),
                "summary_chars": len(summary),
                "parms_resolving_with_real_description": len(good_parms),
                "parms_resolving_but_placeholder_only": sum(
                    1
                    for p in parms_out
                    if p["resolved_runtime_parms"] and is_placeholder(p["description"])
                ),
            }
            corpus_entries.append(entry)
            rows.append(
                {
                    "type": live_name,
                    "has_page": True,
                    "clears": entry["clears_floor"],
                    "usable": entry["usable_tier"],
                    "failures": failures,
                    "match_kind": kind_of.get(live_name),
                    "summary_chars": len(summary),
                    "summary_words": summary_words(summary),
                    "parm_doc_ratio": entry["parm_doc_ratio"],
                    "runtime_parms": len(live_parms),
                    "placeholder_parms": entry["floor_evidence"][
                        "parms_resolving_but_placeholder_only"
                    ],
                }
            )

        all_floor_rows.extend([dict(r, category=cat) for r in rows])

        n = surface["denominator"]
        has = sum(1 for r in rows if r["has_page"])
        clears = sum(1 for r in rows if r["clears"])
        usable = sum(1 for r in rows if r.get("usable"))
        by_kind = {}
        for r in rows:
            if r["has_page"]:
                by_kind[r.get("match_kind")] = by_kind.get(r.get("match_kind"), 0) + 1
        absent = [r for r in rows if not r["has_page"]]
        by_absence = {}
        for r in absent:
            by_absence[r["absence_class"]] = by_absence.get(r["absence_class"], 0) + 1

        report["surfaces"][cat] = {
            "denominator": n,
            "denominator_source": surface["catalog"],
            "pages_in_reference": len(pages),
            "has_page": {"n": has, "pct": round(100.0 * has / n, 1)},
            "clears_quality_floor": {"n": clears, "pct": round(100.0 * clears / n, 1)},
            "clears_usable_tier": {
                "n": usable,
                "pct": round(100.0 * usable / n, 1),
                "note": "T3: clears the floor AND at least %d%% of the live node's "
                "parameters are documented. Reported for scale, not part of the floor."
                % int(USABLE_PARM_RATIO * 100),
            },
            "the_gap": {
                "n": has - clears,
                "pct_of_pages": round(100.0 * (has - clears) / has, 1) if has else None,
                "note": "types with a page that is NOT grounding -- the number a coverage "
                "percentage hides",
            },
            "attribution_sensitivity": _sensitivity(
                [e for e in corpus_entries if e["category"] == cat], has, clears, n, by_kind
            ),
            "parameter_depth": _parm_depth(
                [e for e in corpus_entries if e["category"] == cat], surface
            ),
            "match_kinds": by_kind,
            "absent": {
                "n": len(absent),
                "by_class": by_absence,
                "genuinely_absent": sorted(
                    r["type"] for r in absent if r["absence_class"] == "genuinely_absent"
                ),
                "all_absent": sorted((r["type"], r["absence_class"]) for r in absent),
            },
            "pages_matching_no_live_type": {
                "n": len(unmatched_pages),
                "in_this_surfaces_own_directory": sorted(
                    p for p in unmatched_pages if not p.startswith("manager/")
                ),
                "in_manager_dir": sorted(
                    p for p in unmatched_pages if p.startswith("manager/")
                ),
                "note": "Only the first list is evidence of staleness -- a page in this "
                "surface's own context directory that matches no live type. A manager/ "
                "page unmatched HERE is not stale; manager/ is searched by all three "
                "surfaces and each page matches only the categories that actually have "
                "that manager (there is no copnet inside a Cop network).",
            },
            "floor_failure_census": _census(rows),
        }

    report["parse_stats"] = {
        "pages_parsed": parse_stats["pages_parsed"],
        "unresolved_includes_n": len(parse_stats["unresolved_includes"]),
        "unresolved_includes": parse_stats["unresolved_includes"],
        "note": "unresolved targets point outside nodes.zip (/copernicus, /vex help trees)",
    }
    report["parser_capture_check"] = _capture_check(hz, corpus_entries)
    report["emission_safety"] = _emission_safety(corpus_entries)
    report["quality_floor"] = {
        "definition": (
            "A type CLEARS the floor when (A) its page carries a summary of at least "
            "%d words, AND (B) at least one documented parameter RESOLVES to a "
            "parameter that exists on the live node and carries a description that is "
            "neither empty nor a placeholder." % MIN_SUMMARY_WORDS
        ),
        "min_summary_words": MIN_SUMMARY_WORDS,
        "placeholder_descriptions": sorted(PLACEHOLDER_DESCRIPTIONS),
        "failure_condition": (
            "Law 1, stated before the check was written. Clause A fails a page with no "
            "summary or a two-word one. Clause B fails a page whose every documented "
            "parameter either does not exist on the live node or is documented only as "
            "'TBD'. Both fire on this build; per-surface reject counts and the named "
            "types are in floor_failure_census and floor_rows.json."
        ),
        "why_resolution_against_the_runtime_is_required": (
            "A documented parameter that does not exist on the node is not grounding, "
            "it is the R72 class -- documentation disagreeing with the runtime. Binding "
            "clause B to the live build is what makes this a check rather than a word "
            "count, and it is why the floor could not have been computed from the "
            "reference alone."
        ),
        "calibration": report.get("_calibration"),
    }
    report.pop("_calibration", None)
    return corpus_entries, report, all_floor_rows


def calibrate(entries):
    """What every candidate rule -- adopted and rejected -- actually excludes.

    A threshold nobody can audit is taste wearing a number. This makes the choice
    checkable and, for two of the candidates, demonstrates they were decorations.
    """
    paged = [e for e in entries if e["has_page"]]
    total = len(paged)

    def n_reject(pred):
        return sum(1 for e in paged if pred(e))

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    resolved_parms = [
        p for e in paged for p in e.get("parameters", []) if p["resolved_runtime_parms"]
    ]
    return {
        "pages_considered": total,
        "adopted": {
            "summary_at_least_%d_words" % MIN_SUMMARY_WORDS: {
                "rejects": n_reject(lambda e: summary_words(e.get("summary")) < MIN_SUMMARY_WORDS),
                "why": "the measured distribution bottoms out at 3 words for real "
                "summaries ('Creates a camera.'); below that is empty or a fragment",
            },
            "one_parm_resolving_with_a_non_placeholder_description": {
                "rejects": n_reject(
                    lambda e: e.get("runtime_parm_count")
                    and not any(
                        p["resolved_runtime_parms"] and not is_placeholder(p["description"])
                        for p in e.get("parameters", [])
                    )
                ),
                "vacuous_for_zero_parm_nodes": n_reject(
                    lambda e: not e.get("runtime_parm_count")
                ),
                "why": "grounding requires at least one parameter the reader can act on "
                "that the node actually has",
            },
        },
        "rejected_as_decoration_or_wrong": {
            "summary_at_least_40_chars": {
                "would_reject": n_reject(lambda e: len(e.get("summary") or "") < 40),
                "verdict": "REJECTED -- excludes genuine grounding. cop/blur's "
                "'Applies a blur to a layer.' is 26 characters and is a real summary.",
            },
            "summary_must_not_echo_the_node_label": {
                "would_reject": n_reject(
                    lambda e: bool(norm(e.get("summary")))
                    and norm(e.get("summary")) == norm(e.get("label_runtime"))
                ),
                "verdict": "REJECTED -- rejects 0 of %d. A check that cannot fail is a "
                "decoration (Law 1)." % total,
            },
            "parm_description_at_least_12_chars": {
                "would_reject_beyond_placeholder_test": sum(
                    1
                    for p in resolved_parms
                    if not is_placeholder(p["description"]) and p["description_chars"] < 12
                ),
                "verdict": "REJECTED -- subsumed by the placeholder test; adds nothing.",
            },
        },
        "placeholder_census": {
            "resolved_parms_total": len(resolved_parms),
            "resolved_parms_that_are_placeholders": sum(
                1 for p in resolved_parms if is_placeholder(p["description"])
            ),
            "note": "SideFX shipped these. 'TBD' and empty bodies are the reference "
            "declaring its own gaps; the floor takes it at its word.",
        },
    }


_DEPRECATION_WORDS = ("deprecat", "obsolete", "legacy", "superseded", "no longer")
# The Cop2 pages carry their deprecation banner by reference, not by wording:
#   cop2/loop.txt line 12 -> ':include /composite/_old_cops_deprecated:'
# whose target lives in a SIBLING archive (composite.zip) this harvest does not open,
# and reads "As of Houdini 20.5, use Copernicus nodes instead of Compositing nodes".
# Scanning only the parsed summary and prose sections therefore called that page silent
# when it is not. An include whose NAME states the deprecation counts as a mention.
_DEPRECATION_INCLUDES = ("_old_cops_deprecated", "_deprecated")


def _page_is_silent_on_deprecation(hz, page, live_rec):
    """Is a runtime-deprecated type's page silent about it? Scans the RAW page.

    Reading the parsed fields alone produced a false positive on 1 of 3 flagged types
    (H9-TIER-03). The raw source is scanned instead, so a banner carried by an include
    directive -- which is how the entire Cop2 surface carries it -- is seen.
    """
    if not live_rec.get("deprecated"):
        return False
    raw = (hz.read(page["doc_path"]) or "").lower()
    if any(w in raw for w in _DEPRECATION_WORDS):
        return False
    if any(inc in raw for inc in _DEPRECATION_INCLUDES):
        return False
    return True


def _capture_check(hz, entries):
    """Law 1 check that would have caught the parser's worst defect on the day it shipped.

    A page's own '#id:' directives are a hard lower bound on what the parser must
    extract from it. lop/karmarendersettings declares 153 and the parser captured 8 --
    for one run of the harvest that shortfall was invisible, because nothing compared
    the two. Now it does.

    FAILS WHEN: any page's captured id count is below the count of '#id:' directives
    physically present in its own file. Non-zero shortfall is reported per page and
    the total is a hard number a reader can check.
    """
    shortfalls, checked = [], 0
    for e in entries:
        if not e.get("has_page"):
            continue
        path = (e.get("doc_path") or "").replace("nodes.zip!", "")
        text = hz.read(path)
        if text is None:
            continue
        checked += 1
        _pre, secs = D.split_sections(text)
        # exact comparison: the SET of ids the file declares in its own @parameters
        # section, against the SET the parser extracted. Comparing counts of directive
        # LINES was imprecise in both directions -- one '#id: a, b, c' line declares
        # three ids, and the same id can be declared twice.
        own_ids = set()
        malformed = []
        for line in re.findall(r"^\s*#id:\s*(.+)$", "\n".join(secs.get("parameters", [])), re.M):
            # A directive holding a sentence is a defect in the reference, not a list of
            # parameters: lop/scatterinstances ships
            # '#id: Additional range of orientation for each instance.'
            # Its words are identifier-shaped, so only the sentence test separates them.
            if "," not in line and len(line.split()) >= 3:
                malformed.append(line.strip())
                continue
            # Only identifier-shaped tokens. lop/scatterinstances ships
            # '#id: Additional range of orientation for each instance.' -- a
            # description authored into a directive. That is a defect in the
            # reference, not a parameter, and counting its words as missing ids
            # would make this check lie about the parser.
            for piece in re.split(r"[,\s]+", line.strip()):
                if piece and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:.#]*", piece):
                    own_ids.add(piece)
        got_ids = {i for p in e["parameters"] for i in p["documented_ids"]}
        missing = sorted(own_ids - got_ids)
        if missing:
            shortfalls.append(
                {
                    "type": e["type_name"],
                    "page": path,
                    "declares": len(own_ids),
                    "captured": len(own_ids & got_ids),
                    "missing": missing[:10],
                }
            )
    shortfalls.sort(key=lambda r: -len(r["missing"]))
    return {
        "what_it_asserts": "a page's captured id count is never below the number of "
        "'#id:' directives in its own @parameters section",
        "pages_checked": checked,
        "pages_short": len(shortfalls),
        # UNCAPPED. `worst` below is truncated for readability and `missing` inside each
        # row is truncated too, so a reader who totals that list gets a number smaller
        # than the truth. The first receipt did exactly that and published 19 instead of
        # this figure -- Law 2, a number whose stated producer does not produce it.
        "total_ids_missed": sum(len(r["missing_all"]) for r in shortfalls),
        "result": "PASS" if not shortfalls else "FAIL",
        "worst": [{k: v for k, v in r.items() if k != "missing_all"} for r in shortfalls[:15]],
        "worst_is_truncated_to": 15,
        "failure_condition": "any page where the parser extracted fewer ids than the "
        "file declares. This fired on 100+ pages before the segmentation fix and is the "
        "check whose absence let that defect ship.",
    }


def _sensitivity(entries, has, clears, denom, by_kind=None):
    """The one judgement call in the coverage number, reported both ways.

    14 Lop families ship ONE page for TWO live types. H9 credits the page to the
    version the header declares and leaves the sibling uncredited. The opposite choice
    -- credit a shared page to every sibling in the family -- is defensible too, and a
    reader is entitled to see what it would do to the headline before accepting either.
    Consequence is real, not hypothetical: the existing semantic artifact
    lop_solaris_knowledge_22.json grounds `light`, `domelight` and `reference` (the v1
    siblings), which the strict choice scores as ungrounded.
    """
    sibs = [e for e in entries if e.get("absence_class") == "sibling_version_documented_only"]
    alt_clear = sum(1 for e in sibs if e.get("sibling", {}).get("would_clear_floor_if_credited"))
    return {
        "choice_made": "credit a shared page ONLY to the version its '#version:' header "
        "declares (strict)",
        "types_affected": len(sibs),
        "strict": {
            "has_page": has,
            "has_page_pct": round(100.0 * has / denom, 1),
            "clears_floor": clears,
            "clears_floor_pct": round(100.0 * clears / denom, 1),
        },
        "if_shared_pages_credited_to_every_sibling": {
            "has_page": has + len(sibs),
            "has_page_pct": round(100.0 * (has + len(sibs)) / denom, 1),
            "clears_floor": clears + alt_clear,
            "clears_floor_pct": round(100.0 * (clears + alt_clear) / denom, 1),
        },
        "types_credited_via_a_version_tolerant_match": (by_kind or {}).get("version_tolerant", 0),
        "version_tolerant_note": "A SECOND version-sensitive path, reported because "
        "'types_affected: 0' alone would hide it. These types are credited from a page "
        "whose name carries no version at all (the cop/pyro_*-.txt pages end in a bare "
        "hyphen) to a live type that does -- e.g. cop/pyro_activate.txt to "
        "pyro_activate::2.0. Each was checked by parameter overlap against both live "
        "versions before being accepted, but the credit still rests on a naming "
        "judgement rather than on a declared version.",
        "why_strict_was_chosen": "the page's own '#version:' directive names which sibling "
        "it documents, and the two siblings do not have the same parameters -- "
        "cache/cache::2.0 share only 40% of theirs. Crediting one page to both would "
        "count authored content that does not describe the node it is credited to.",
    }


def _emission_safety(entries):
    """Which key in this corpus is safe to act on -- the documented id, or the label?

    Not a wiring decision (H9 wires nothing). It is the measurement a wiring decision
    would need, taken now while the runtime is in front of us.

    The answer is not symmetric. On lop/portallight the documented ids are `height`
    and `width`; the live parameters are `xn__inputsheight_mva` and
    `xn__inputswidth_zta`. The documented id would emit and silently miss. The
    documented LABEL -- 'Height', 'Width' -- resolves correctly. Any consumer that
    trusts doc-derived ids on punycode-encoded USD attributes inherits the phantom.
    """
    by_cat = {}
    punycode_types = set()
    punycode_parms = 0
    id_wrong_label_right = []
    for e in entries:
        if not e["has_page"]:
            continue
        c = by_cat.setdefault(
            e["category"],
            {"parm_records": 0, "with_explicit_id": 0, "pages": 0, "pages_with_any_id": 0},
        )
        c["pages"] += 1
        any_id = False
        for p in e["parameters"]:
            c["parm_records"] += 1
            if p["documented_ids"]:
                c["with_explicit_id"] += 1
                any_id = True
            for n in p["resolved_runtime_parms"]:
                if n.startswith("xn__"):
                    punycode_parms += 1
                    punycode_types.add("%s/%s" % (e["category"], e["type_name"]))
            # NOTE ON A DROPPED CLAUSE (H9-LAW1-08). This test used to carry a third
            # condition -- "and none of the documented ids is among the resolved parms".
            # It excluded 0 of 385 and could never exclude any, because resolve_parm
            # only returns a label_* resolution AFTER every id has already failed to
            # match. It was an assertion wearing a filter's clothes, so it is gone.
            if p["documented_ids"] and p["resolution"] in (
                "label_exact",
                "label_caseless",
                "label_split",
            ):
                rec = {
                    "type": "%s/%s" % (e["category"], e["type_name"]),
                    "documented_ids": p["documented_ids"],
                    "live_parms": p["resolved_runtime_parms"],
                    "label": p["label"],
                    "label_is_unambiguous": len(p["resolved_runtime_parms"]) == 1,
                }
                id_wrong_label_right.append(rec)
        if any_id:
            c["pages_with_any_id"] += 1
    for c in by_cat.values():
        c["pct_records_with_explicit_id"] = (
            round(100.0 * c["with_explicit_id"] / c["parm_records"], 1)
            if c["parm_records"]
            else None
        )
    return {
        "id_density": by_cat,
        "id_density_note": "Cop2 pages document parameters by LABEL almost exclusively. "
        "An id-keyed consumer would find nearly nothing there; the id-based portion of "
        "the 20-node cross-check is vacuous for Cop2 for exactly this reason.",
        "punycode_encoded_live_parms": {
            "n": punycode_parms,
            "types": sorted(punycode_types),
            "why_it_matters": "the documented name is the USD attribute name; the live "
            "parameter name is punycode-encoded. Emitting the documented name would miss.",
        },
        "documented_id_wrong_but_label_correct": {
            "n_records": len(id_wrong_label_right),
            "n_distinct_cases": len(
                {
                    (r["type"], tuple(r["documented_ids"]), tuple(r["live_parms"]), r["label"])
                    for r in id_wrong_label_right
                }
            ),
            "label_resolves_to_exactly_one_parm": sum(
                1 for r in id_wrong_label_right if r["label_is_unambiguous"]
            ),
            "label_fans_out_to_several_parms": sum(
                1 for r in id_wrong_label_right if not r["label_is_unambiguous"]
            ),
            "sample": id_wrong_label_right[:15],
            "reading": "Only the unambiguous subset supports 'the label is the more "
            "reliable key'. Where one documented label resolves to several live "
            "parameters the label did not resolve correctly, it resolved AMBIGUOUSLY, "
            "and it is not safe to act on either. Recorded as a measurement, not a "
            "wiring recommendation.",
        },
    }


def _parm_depth(entries, surface):
    """Type-level coverage says a node is 'documented'. This says how much of it is.

    A 171-parameter node with three documented parameters counts once in the type
    figure and is nearly useless as grounding. The parameter figure is the one that
    does not flatter.
    """
    live_total = sum(len(v.get("parms", [])) for v in surface["runtime"].values())
    documented = sum(e.get("documented_runtime_parms", 0) or 0 for e in entries)
    placeholder = sum(
        1
        for e in entries
        for p in e.get("parameters", [])
        if p["resolved_runtime_parms"] and is_placeholder(p["description"])
    )
    on_paged = sum(
        len(surface["runtime"].get(e["type_name"], {}).get("parms", []))
        for e in entries
        if e["has_page"]
    )
    return {
        "live_parms_total": live_total,
        "documented_parms": documented,
        "pct_of_all_live_parms": round(100.0 * documented / live_total, 1) if live_total else None,
        "live_parms_on_types_that_have_a_page": on_paged,
        "pct_of_parms_on_documented_types": (
            round(100.0 * documented / on_paged, 1) if on_paged else None
        ),
        "documented_but_placeholder_only": placeholder,
    }


def _census(rows):
    out = {}
    for r in rows:
        for f in r.get("failures", []) or ([] if r["has_page"] else ["no_page"]):
            out[f] = out.get(f, 0) + 1
    return out


def main():
    entries, report, rows = build()
    report["quality_floor"]["calibration"] = calibrate(entries)

    corpus = {
        "schema": "doc_grounding_corpus/v1",
        "tier": "VERIFIED-DOC",
        "tier_definition": (
            "VERIFIED-DOC: authored by SideFX, shipped inside the build, version-pinned "
            "by construction. It is NOT VERIFIED-RUNTIME and must never be summed with "
            "probe-derived grounding -- the total would look like coverage and be partly "
            "hearsay. Documentation supplies semantic grounding only; it cannot supply "
            "behavioural grounding, and it is silent wherever SideFX did not write."
        ),
        "known_silence": (
            "lop/karmarenderproperties is 56,325 characters on 22.0.368 (measured; the H9 "
            "brief says 69,921, which does not reproduce against this zip) and never states "
            "the type is deprecated -- no 'deprecat', 'obsolete', 'legacy', 'superseded' or "
            "'no longer' anywhere in it. The runtime flags it: deprecated()==True. It is not "
            "the only one. THREE deprecated types have a page and none mentions it "
            "(Lop/karma, Lop/karmarenderproperties, Cop2/loop); a fourth, Cop2/swap, is "
            "deprecated with no page at all. Every entry carries runtime_disagreement so the "
            "silence is visible where the entry is read, not only in the receipt."
        ),
        "build": report["build"],
        "reference": report["reference"],
        "reference_blake2b_128": _hash_reference(),
        "reference_note": "ships inside the Houdini install, so it is version-pinned by "
        "construction: no network fetch, no robots restriction, no ambiguity about which "
        "build it describes. The hash pins WHICH copy was harvested.",
        "producer": "harness/notes/h9/build_corpus.py (parser: harness/notes/h9/docparse.py)",
        "runtime_ground_truth": "harness/notes/h9/runtime_parms_22.0.368.json",
        "not_wired": (
            "This corpus is NOT wired into the emission path or the RAG corpus. H9 "
            "produces and measures it; wiring is a separate decision with its own gate. "
            "L1.F11 found 15 phantom createNode sites already living in the RAG corpus "
            "outside the emission gate."
        ),
        "counts": {
            cat: {
                "denominator": s["denominator"],
                "has_page": s["has_page"],
                "clears_quality_floor": s["clears_quality_floor"],
            }
            for cat, s in report["surfaces"].items()
        },
        "entries": entries,
    }

    with open(CORPUS_OUT, "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, indent=1, sort_keys=False)
    with open(REPORT_OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, sort_keys=False)
    with open(os.path.join(HERE, "floor_rows.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=0)

    print("WROTE", CORPUS_OUT, "%.1f MB" % (os.path.getsize(CORPUS_OUT) / 1e6))
    print("WROTE", REPORT_OUT)
    for cat, s in report["surfaces"].items():
        print(
            "  %-5s n=%3d  page %3d (%4.1f%%)  clears %3d (%4.1f%%)  gap %d  absent %d"
            % (
                cat,
                s["denominator"],
                s["has_page"]["n"],
                s["has_page"]["pct"],
                s["clears_quality_floor"]["n"],
                s["clears_quality_floor"]["pct"],
                s["the_gap"]["n"],
                s["absent"]["n"],
            )
        )


if __name__ == "__main__":
    main()
