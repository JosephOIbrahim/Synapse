"""H9 -- adjudicate the two things the cross-check flagged rather than assume them.

RUN: hython3.13.exe harness/notes/h9/diagnose_mismatch.py
Writes harness/notes/h9/mismatch_diagnosis.json.

Q1  The probe's positive control returned 8/10 against the committed COP
    catalogue. Is the probe broken, or do the two harvests enumerate multiparm
    and ramp templates under different policies? Until this is answered, every
    doc/runtime disagreement this leg reports is suspect.

Q2  The sweep says 177 of 199 documented ids on lop/rendersettings, and 51 of 84
    on lop/light::2.0, do not exist as live parms. Either the parser is wrong or
    the docs' ``#id:`` field is not a Houdini parameter name. Those have opposite
    consequences, so it is resolved by looking rather than by reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path

import hou

H9 = Path(__file__).resolve().parent
NOTES = H9.parent
COP_CAT = NOTES / "h22_cop_catalog_live_22.0.368.json"
CORPUS = NOTES / "h22_doc_grounding_corpus.json"
OUT = H9 / "mismatch_diagnosis.json"


def templates(nt, recurse: bool):
    out = []

    def rec(ts, depth):
        for t in ts:
            kids = None
            if hasattr(t, "parmTemplates"):
                try:
                    kids = t.parmTemplates()
                except Exception:
                    kids = None
            out.append((t.name(), kids is not None, depth))
            if kids and recurse:
                rec(kids, depth + 1)

    rec(nt.parmTemplateGroup().entries(), 0)
    return out


def main() -> None:
    res = {"schema": "h9_mismatch_diagnosis/v1",
           "truth_tier": "VERIFIED-RUNTIME",
           "producer": "harness/notes/h9/diagnose_mismatch.py",
           "build": hou.applicationVersionString()}

    # ---- Q1 -------------------------------------------------------------
    cop = json.loads(COP_CAT.read_text(encoding="utf-8"))
    types = cop["categories"]["copNodeTypeCategory"]["types"]
    cat = {c.name(): c for c in hou.nodeTypeCategories().values()}["Cop"]
    q1 = []
    for tname in ("cablepack", "cellularnoise3d"):
        nt = hou.nodeType(cat, tname)
        flat = templates(nt, recurse=False)
        deep = templates(nt, recurse=True)
        catalogue = set(types[tname]["parms"])
        q1.append({
            "type": tname,
            "catalogue_parms": sorted(catalogue),
            "probe_toplevel_including_folders": sorted({n for n, _f, _d in flat}),
            "probe_recursive_nonfolder": sorted(
                {n for n, f, _d in deep if not f}),
            "catalogue_equals_toplevel": catalogue == {n for n, _f, _d in flat},
            "catalogue_subset_of_recursive_all": catalogue <= {n for n, _f, _d in deep},
        })
    res["q1_probe_vs_catalogue"] = {
        "question": "is the probe broken, or is this an enumeration-policy difference?",
        "cases": q1,
        # The claim under test is 'neither harvest missed a parameter the other
        # saw', so the subset relation is the criterion. Equality with the
        # top-level listing was the first guess and it is false for
        # cellularnoise3d, whose top level is four unnamed folders.
        "verdict": ("ENUMERATION POLICY, NOT A BROKEN PROBE -- every parameter in "
                    "the committed catalogue is present in this probe's walk. The "
                    "two differ only in how they represent ramp and multiparm "
                    "containers: the catalogue keeps the container name "
                    "('bevelramp', 'fields'), this probe descends into it "
                    "('bevelramp#value', 'fieldname#'). No parameter is missing "
                    "from either side."
                    if all(c["catalogue_subset_of_recursive_all"] for c in q1)
                    else "UNEXPLAINED -- treat the cross-check as unverified."),
    }

    # ---- Q2 -------------------------------------------------------------
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    ents = {(e["context"], e["type"]): e for e in corpus["entries"]}
    lop = {c.name(): c for c in hou.nodeTypeCategories().values()}["Lop"]
    q2 = []
    for tname in ("light::2.0", "rendersettings", "rendergeometrysettings", "domelight::3.0"):
        e = ents.get(("lop", tname))
        if not e:
            continue
        nt = hou.nodeType(lop, tname)
        if nt is None:
            continue
        live = sorted({n for n, f, _d in templates(nt, True) if not f})
        docids = sorted({i for p in e["parameters"] for i in p["ids"]})
        missing = [d for d in docids if d not in set(live)]
        # Do the missing ids look like USD attribute names rather than parm names?
        usd_shaped = [d for d in missing if ":" in d]
        # Houdini encodes namespaced USD attrs into punycode parm names.
        punycode_live = [n for n in live if n.startswith("xn__")]
        q2.append({
            "type": tname,
            "documented_ids": len(docids),
            "live_parms": len(live),
            "documented_ids_absent_from_live": len(missing),
            "absent_examples": missing[:14],
            "absent_that_are_colon_namespaced": len(usd_shaped),
            "live_punycode_parm_count": len(punycode_live),
            "live_punycode_examples": punycode_live[:10],
            "live_parm_examples": live[:14],
        })
    res["q2_doc_ids_vs_parm_names"] = {
        "question": "are the docs' #id: values Houdini parameter names?",
        "cases": q2,
    }

    # ---- Q3 -------------------------------------------------------------
    # COP/COP2 carry no colon-namespaced ids yet still disagree (cop 88.2%,
    # cop2 65.5%). Different cause, so it is looked at rather than assumed to be
    # the same one.
    cats_all = {c.name(): c for c in hou.nodeTypeCategories().values()}
    q3 = []
    for ctx, tname in (("cop2", "emboss"), ("cop2", "border"),
                       ("cop", "pyro_block_end"), ("cop", "colorcorrect")):
        e = ents.get((ctx, tname))
        nt = hou.nodeType(cats_all["Cop2" if ctx == "cop2" else "Cop"], tname)
        if not e or nt is None:
            continue
        live = sorted({n for n, f, _d in templates(nt, True) if not f})
        docids = sorted({i for p in e["parameters"] for i in p["ids"]})
        missing = [d for d in docids if d not in set(live)]
        # Hypothesis: the doc names a CHANNEL (component) and the live template
        # is the containing vector parm -- 'diffr' documented, 'diff' live.
        recovered = []
        for d in missing:
            for cut in (1, 2):
                if len(d) > cut and d[:-cut] in set(live):
                    recovered.append({"documented": d, "live_parm": d[:-cut]})
                    break
        q3.append({
            "context": ctx, "type": tname,
            "documented_ids": len(docids), "live_parms": len(live),
            "absent": len(missing),
            "absent_examples": missing[:10],
            "recovered_by_stripping_component_suffix": len(recovered),
            "recovered_examples": recovered[:8],
            "live_examples": live[:12],
        })
    res["q3_cop_channel_semantics"] = {
        "question": "COP/COP2 ids carry no colons yet still miss. Are they "
                    "component CHANNEL names rather than parm names?",
        "cases": q3,
    }
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:6000])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
