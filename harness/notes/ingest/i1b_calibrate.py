"""I1 — reader calibration. R60: the instrument is calibrated BEFORE it is trusted.

Run this before `i1b_extract.py`. The extractor refuses to build a corpus unless
`_i1_calibration.json` reports every control passing, at this reader's source
hash. A reader trusted on 5,000 pages nobody read, on the strength of numbers
that merely look plausible, is the failure this leg exists to prevent.

Three control classes, and each one can fail (Law 1):

  POSITIVE  pages read BY HAND in this leg's transcript before the parser was
            pointed at them. Every expectation below was derived by reading the
            page, not by running the reader and writing down what it said.
            FAILS IF: the parser stops reproducing a hand-read value.

  NEGATIVE  the same pages, mutated. A count that does not MOVE when the thing
            it counts is deleted is not measuring anything.
            FAILS IF: a mutation leaves the count unchanged.

  BLIND     deliberately naive readers, each embodying one documented defect,
            shown returning the WRONG answer where this reader returns the
            right one. A control that only proves "we agree with ourselves"
            proves nothing.
            FAILS IF: the naive reader AGREES with ours (the defect stopped
            being demonstrable, so the guard is no longer evidenced).

Producer: this file -> harness/notes/ingest/_i1_calibration.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import i1b_reader as R  # noqa: E402
import helpdoc  # noqa: E402

RESULTS: list[dict] = []


def check(cls: str, name: str, got, want, note: str = "", cmp: str = "eq") -> None:
    if cmp == "eq":
        ok = got == want
    elif cmp == "ge":
        ok = got >= want
    elif cmp == "ne":
        ok = got != want
    elif cmp == "gt":
        ok = got > want
    else:
        raise ValueError(cmp)
    RESULTS.append({
        "class": cls, "control": name, "ok": bool(ok), "cmp": cmp,
        "got": got if not isinstance(got, (list, tuple)) else list(got),
        "want": want if not isinstance(want, (list, tuple)) else list(want),
        "note": note,
    })


# =====================================================================
# POSITIVE — hand-read pages
# =====================================================================

def positive(a: R.Archive) -> None:
    # ---- P1  cop/chromakey.txt — one of the 161; CRLF; parameters at column 0
    p = a.raw("cop/chromakey.txt")
    check("POSITIVE", "chromakey.eol", p.eol, "CRLF",
          "101 CRLF line breaks; a '\\n'-splitting reader scores this page 0")
    check("POSITIVE", "chromakey.header_order", p.header_order, "directives-first")
    check("POSITIVE", "chromakey.title", p.title, "Chroma Key")
    check("POSITIVE", "chromakey.summary", p.summary,
          "Keys an input based on hue, saturation, and luminance ranges.")
    check("POSITIVE", "chromakey.internal", p.directives.get("internal"), "chromakey")
    check("POSITIVE", "chromakey.param_count", len(p.params), 15)
    check("POSITIVE", "chromakey.labels", [i.label for i in p.params], [
        "Signature", "Method", "Invert", "Hue/Saturation", "Luminance Range",
        "Screen Color", "Threshold", "Width", "Hue", "Saturation", "Luminance",
        "Interpolation", "Preview", "Preview Color", "Premultiply"])
    check("POSITIVE", "chromakey.ids", [i.ident for i in p.params], [
        "signature", "method", "invert", "huecircle", "lumrange", "screencolor",
        "threshold", "width", "huerolloff", "satrolloff", "lumrolloff",
        "interpolation", "preview", "previewcolor", "premult"])
    check("POSITIVE", "chromakey.all_described", len(p.described_params), 15)
    check("POSITIVE", "chromakey.rung", p.rung(), "ACTIONABLE")
    # 'TIP:' is indented INSIDE the Hue/Saturation entry. It is not a parameter.
    check("POSITIVE", "chromakey.TIP_not_a_param",
          any(i.label.upper() == "TIP" for i in p.params), False,
          "an indented 'TIP:' inside an entry must not be counted as a parameter")

    # ---- P2  cop/camerablend.txt — #since 22.0; the D4 preamble-directive trap
    p = a.raw("cop/camerablend.txt")
    check("POSITIVE", "camerablend.since", p.directives.get("since"), "22.0")
    check("POSITIVE", "camerablend.param_count", len(p.params), 1)
    check("POSITIVE", "camerablend.label", [i.label for i in p.params], ["Blend"])
    check("POSITIVE", "camerablend.id", [i.ident for i in p.params], ["blend"])
    check("POSITIVE", "camerablend.D4_no_page_id", "id" in p.directives, False,
          "an indented 'NOTE:'+'#id: blend_cameras' in the PREAMBLE must not "
          "become a page-level directive")
    check("POSITIVE", "camerablend.rung", p.rung(), "ACTIONABLE")

    # ---- P3  cop2/blur.txt — parameters at indent 8; deprecation banner
    p = a.raw("cop2/blur.txt")
    rp, _ = a.resolved("cop2/blur.txt")
    check("POSITIVE", "blur.raw_params", len(p.params), 6)
    check("POSITIVE", "blur.raw_labels", [i.label for i in p.params],
          ["X/Y Filter", "Size", "Y Size", "Units", "Per-Pixel Blur", "Fast Blur"])
    check("POSITIVE", "blur.UVCoords_not_a_param",
          any(i.label == "UV Coords" for i in p.params), False,
          "menu values nested under 'Units:' are depth 1, not parameters")
    check("POSITIVE", "blur.raw_actionable", len(p.actionable_params), 0,
          "no #id and no #channels inline — cop2 documents them via includes")
    check("POSITIVE", "blur.raw_rung", p.rung(), "FLOOR")
    check("POSITIVE", "blur.includes", len(p.includes), 6)
    check("POSITIVE", "blur.resolved_params", len(rp.params), 17)
    check("POSITIVE", "blur.resolved_actionable", len(rp.actionable_params), 6)
    check("POSITIVE", "blur.resolved_rung", rp.rung(), "ACTIONABLE")
    dep = R.doc_deprecation(p, a.raw_text("cop2/blur.txt")[0],
                            a.include_targets_recursive("cop2/blur.txt"))
    check("POSITIVE", "blur.doc_deprecated", dep["is_deprecated_doc"], True,
          "the _old_cops_deprecated banner lives in composite.zip, NOT nodes.zip")

    # ---- P4  lop/distantlight.txt — title-first; the floor FLIP on resolution
    p = a.raw("lop/distantlight.txt")
    rp, st = a.resolved("lop/distantlight.txt")
    check("POSITIVE", "distantlight.header_order", p.header_order, "title-first",
          "79% of lop pages put the title before the directives")
    check("POSITIVE", "distantlight.raw_params", len(p.params), 0)
    check("POSITIVE", "distantlight.raw_rung", p.rung(), "SUMMARY")
    check("POSITIVE", "distantlight.raw_clears_floor", p.clears_floor, False)
    check("POSITIVE", "distantlight.includes", len(p.includes), 14)
    check("POSITIVE", "distantlight.resolved_params", len(rp.params), 87)
    check("POSITIVE", "distantlight.resolved_actionable", len(rp.actionable_params), 78)
    check("POSITIVE", "distantlight.resolved_rung", rp.rung(), "ACTIONABLE")
    check("POSITIVE", "distantlight.FLOOR_FLIP", (p.clears_floor, rp.clears_floor),
          (False, True),
          "a fully-documented node reads as ungrounded without include resolution")

    # ---- P5  cop2/emboss.txt — BOM page; #channels is the internal-name key
    p = a.raw("cop2/emboss.txt")
    check("POSITIVE", "emboss.had_bom", p.had_bom, True)
    check("POSITIVE", "emboss.type_directive", p.directives.get("type"), "node",
          "decoded as plain utf-8 the first directive is eaten and the page "
          "reads as a non-node")
    check("POSITIVE", "emboss.raw_params", len(p.params), 10)
    check("POSITIVE", "emboss.first_label", p.params[0].label, "Light Position")
    check("POSITIVE", "emboss.no_ids", [i.ident for i in p.params].count(None), 10)
    check("POSITIVE", "emboss.channels_split", p.params[0].internal_names,
          ["lightposx", "lightposy", "lightposz"],
          "'/lightposx /lightposy /lightposz' -> '/' stripped, space split")
    check("POSITIVE", "emboss.rung", p.rung(), "ACTIONABLE")


# =====================================================================
# NEGATIVE — mutations that MUST move a count
# =====================================================================

def negative(a: R.Archive) -> None:
    ck, _ = a.raw_text("cop/chromakey.txt")

    m = ck.replace("@parameters", "@notparameters")
    check("NEGATIVE", "chromakey.no_at_parameters",
          len(R.parse_page("cop/chromakey.txt", m).params), 0)
    check("NEGATIVE", "chromakey.no_at_parameters.rung",
          R.parse_page("cop/chromakey.txt", m).rung(), "SUMMARY")

    m = re.sub(r'"""[^"]*"""', "", ck)
    check("NEGATIVE", "chromakey.no_summary",
          R.parse_page("cop/chromakey.txt", m).rung(), "EXISTS")

    m = re.sub(r"(?m)^\s*#id:.*$", "", ck)
    pm = R.parse_page("cop/chromakey.txt", m)
    check("NEGATIVE", "chromakey.no_ids.actionable", len(pm.actionable_params), 0)
    check("NEGATIVE", "chromakey.no_ids.rung", pm.rung(), "FLOOR")
    check("NEGATIVE", "chromakey.no_ids.params_survive", len(pm.params), 15,
          "deleting ids must remove the ACTIONABLE rung WITHOUT losing the "
          "parameters themselves — otherwise the mutation proves the wrong thing")

    dl, _ = a.raw_text("lop/distantlight.txt")
    m = dl.replace(":include", ":xinclude")
    check("NEGATIVE", "distantlight.includes_neutralised",
          len(R.parse_page("lop/distantlight.txt", m).params), 0)

    bl, _ = a.raw_text("cop2/blur.txt")
    m = "\n".join(l for l in bl.split("\n")
                  if not (l.startswith("            ") and l.strip()))
    pm = R.parse_page("cop2/blur.txt", m)
    check("NEGATIVE", "blur.descriptions_stripped.described", len(pm.described_params), 0)
    check("NEGATIVE", "blur.descriptions_stripped.rung", pm.rung(), "SUMMARY")

    em, _ = a.raw_text("cop2/emboss.txt")
    m = re.sub(r"(?m)^\s*#channels:.*$", "", em)
    check("NEGATIVE", "emboss.no_channels.actionable",
          len(R.parse_page("cop2/emboss.txt", m).actionable_params), 0)


# =====================================================================
# BLIND — naive readers shown returning the WRONG answer
# =====================================================================

def blind(a: R.Archive) -> None:
    # ---- B1  D1: split on '\n' without normalising CRLF
    text, _ = a.raw_text("cop/chromakey.txt")
    naive = 0
    section = None
    for line in text.split("\n"):            # CRLF NOT normalised -> trailing '\r'
        ms = R.RE_AT_SECTION.match(line)
        if ms and not line.startswith("@@"):
            section = ms.group("name")
            continue
        if section in R.PARAM_SECTIONS and R.RE_ITEM.match(line):
            naive += 1
    check("BLIND", "B1.crlf_naive_finds_zero", naive, 0,
          "the naive reader must be WRONG here")
    check("BLIND", "B1.ours_finds_fifteen", len(a.raw("cop/chromakey.txt").params), 15)
    check("BLIND", "B1.disagree", naive != 15, True,
          "if these ever agree, the CRLF guard is no longer evidenced")

    # ---- B2  D2: decode utf-8 instead of utf-8-sig
    raw = a.zip.read("cop2/emboss.txt")
    naive_dirs = helpdoc.page_directives(raw.decode("utf-8"))
    ours_dirs = a.raw("cop2/emboss.txt").directives
    check("BLIND", "B2.bom_naive_loses_type", "type" in naive_dirs, False)
    check("BLIND", "B2.ours_keeps_type", ours_dirs.get("type"), "node")

    # ---- B3  D3: no item-scope close + last-wins -> a Vimeo id becomes a parm name
    tx, _ = a.raw_text("sop/xform.txt")
    section = None
    pend = None
    naive_ids: dict = {}
    for line in tx.replace("\r\n", "\n").split("\n"):
        ms = R.RE_AT_SECTION.match(line)
        if ms and not line.startswith("@@"):
            section, pend = ms.group("name"), None
            continue
        if section not in R.PARAM_SECTIONS:
            continue
        md = R.RE_DIRECTIVE.match(line)
        if md:
            if md.group("key") == "id" and pend:
                naive_ids[pend] = md.group("val").strip()      # LAST wins
            continue
        mi = R.RE_ITEM.match(line)
        if mi and mi.group("label").strip():
            pend = mi.group("label").strip()
    ours = [i.ident for i in a.raw("sop/xform.txt").params if i.label == "Combine"]
    check("BLIND", "B3.vimeo_naive_rekeys_combine",
          bool(re.fullmatch(r"\d{6,}", naive_ids.get("Combine", ""))), True,
          "naive binds ':vimeo:'+'#id: <video id>' to the preceding parameter")
    check("BLIND", "B3.ours_keeps_combine", ours, ["combine"])

    # ---- B4  D4: accept indented preamble directives as page directives
    tc, _ = a.raw_text("cop/camerablend.txt")
    naive_page: dict = {}
    for line in tc.replace("\r\n", "\n").split("\n"):
        if line.startswith("@"):
            break
        md = R.RE_DIRECTIVE.match(line)
        if md and md.group("key") not in naive_page:
            naive_page[md.group("key")] = md.group("val")
    check("BLIND", "B4.naive_page_gets_bogus_id",
          naive_page.get("id"), "blend_cameras")
    check("BLIND", "B4.ours_has_no_page_id",
          "id" in a.raw("cop/camerablend.txt").directives, False)

    # ---- B5  one include verb instead of three
    tcam, _ = a.raw_text("obj/cam.txt")
    tcam = tcam.replace("\r\n", "\n")
    seen: dict = {}
    for label, rx in (("wide", R._WIDE_INCLUDE_RE),
                      ("narrow", re.compile(r"^(\s*):include\s+(.+):\s*$"))):
        helpdoc._INCLUDE_RE = rx
        st: dict = {}
        helpdoc.resolve_includes(tcam, a.corpus, "nodes/obj", stats=st,
                                 self_key="nodes/obj/cam")
        seen[label] = st.get("seen", 0)
    helpdoc._INCLUDE_RE = R._WIDE_INCLUDE_RE          # restore the widening
    check("BLIND", "B5.narrow_verb_sees_fewer", seen["narrow"], 12)
    check("BLIND", "B5.wide_verb_sees_more", seen["wide"], 38)
    check("BLIND", "B5.widening_takes_effect", seen["wide"] > seen["narrow"], True,
          "26 ':includeprop' statements are INVISIBLE to a ':include'-only "
          "reader — an undercount that looks like a clean parse")

    # ---- B7  an @section-name anchor, which helpdoc's id-anchor resolver
    #          cannot see. Found by cross-validation, not by these controls —
    #          which is itself the finding: a second instrument caught what a
    #          calibrated first instrument did not.
    orig = R._ORIG_ANCHORED_BLOCK
    body = a.corpus.pages["nodes/out/image"]
    check("BLIND", "B7.id_anchor_resolver_is_blind_to_sections",
          orig(body, "parameters"), None,
          "the naive (original) resolver must be WRONG here")
    check("BLIND", "B7.ours_finds_the_section",
          len(R._anchored_block_or_section(body, "parameters") or "") > 5000, True)
    rp, _ = a.resolved("cop/rop_image.txt")
    check("BLIND", "B7.rop_image_section_anchor_resolves",
          (len(rp.params) > 0, rp.clears_floor), (True, True),
          "cop/rop_image is a newly-named Copernicus node whose ENTIRE "
          "@parameters section is one section-anchored include")

    # ---- B6  #id only, ignoring #channels
    p = a.raw("cop2/emboss.txt")
    check("BLIND", "B6.id_only_scores_zero", len([i for i in p.params if i.ident]), 0)
    check("BLIND", "B6.ours_scores_ten", len(p.actionable_params), 10,
          "cop2 is dominated by #channels; an #id-only reader reports the "
          "entire cop2 parameter surface as un-identifiable")


def main() -> int:
    a = R.Archive()
    positive(a)
    negative(a)
    blind(a)

    src = (HERE / "i1b_reader.py").read_bytes()
    by_class: dict = {}
    for r in RESULTS:
        b = by_class.setdefault(r["class"], {"pass": 0, "fail": 0})
        b["pass" if r["ok"] else "fail"] += 1
    failed = [r for r in RESULTS if not r["ok"]]

    out = {
        "producer": "harness/notes/ingest/i1b_calibrate.py",
        "build": R.BUILD,
        "reader_sha256": hashlib.sha256(src).hexdigest(),
        "total": len(RESULTS),
        "passed": len(RESULTS) - len(failed),
        "failed": len(failed),
        "by_class": by_class,
        "all_pass": not failed,
        "controls": RESULTS,
    }
    (HERE / "_i1b_calibration.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    print("I1 CALIBRATION  %d/%d  %s" % (out["passed"], out["total"],
                                         "ALL PASS" if out["all_pass"] else "FAILED"))
    for k, v in sorted(by_class.items()):
        print("  %-9s pass=%-3d fail=%d" % (k, v["pass"], v["fail"]))
    for r in failed:
        print("  FAIL %-12s %-40s got=%r want=%r" %
              (r["class"], r["control"], r["got"], r["want"]))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
