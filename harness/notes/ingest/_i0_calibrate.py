"""I0 — calibration for _i0_reader (R60, Law 1).

A reader with no controls produces green numbers and zero information (R60).
H5 shipped exactly that: its reader parsed correctly, bound incorrectly, and
reported clean (R88). So before any I0 number is trusted:

  POSITIVE  hand-read pages the parser must reproduce exactly.
  NEGATIVE  mutated pages the parser must FAIL on. If a mutation cannot drive
            the count down, the count was never measuring anything (Law 1).
  BLIND     a deliberately naive reader (column-0 labels only, the H5 failure
            shape) shown returning the WRONG answer where ours returns right.
            This is the R60 control: proof the instrument is not blind.

Run:  python -c "exec(open('harness/notes/ingest/_i0_calibrate.py',encoding='utf-8').read())"
Emits: harness/notes/ingest/_i0_calibration.json  + a PASS/FAIL table.
"""

from __future__ import annotations

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.path.abspath("harness/notes/ingest")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _i0_reader import NODES_ZIP, open_archive, read_page, parse_page  # noqa: E402

RESULTS: list = []


def check(name: str, got, want, note: str = "") -> bool:
    ok = got == want
    RESULTS.append({"control": name, "got": got, "want": want, "pass": ok, "note": note})
    return ok


# ------------------------------------------------------------------ blind reader
def blind_params(text: str) -> int:
    """The H5 failure shape: assume parameters are labels at column 0 and that
    #id is always present. Kept here ON PURPOSE as the negative instrument."""
    out, in_params = 0, False
    for line in text.split("\n"):
        if line.startswith("@parameters"):
            in_params = True
            continue
        if line.startswith("@") and not line.startswith("@parameters"):
            in_params = False
            continue
        if in_params and re.match(r"^[A-Z][^:\s][^:]*:\s*$", line):
            out += 1
    return out


def crlf_blind_params(text: str) -> int:
    """The SECOND failure shape, found by this calibration on 2026-07-27: split on
    '\\n', anchor the label on a bare '$'. On the 138 CRLF pages the trailing
    '\\r' defeats the anchor and the page reads as zero-parameter — silently."""
    out, in_params = 0, False
    for line in text.split("\n"):
        if line.startswith("@parameters"):
            in_params = True
            continue
        if line.startswith("@"):
            in_params = False
            continue
        if in_params and re.match(r"^\s*[A-Z][^:\s][^:]*:$", line):
            out += 1
    return out


def main() -> int:
    z = open_archive(NODES_ZIP)

    # ================================================== POSITIVE CONTROL 1
    # cop/chromakey.txt — hand-read 2026-07-27 from the raw page, 101 lines.
    # 15 parameters in 4 scopes, every one carrying #id. "TIP:" at deeper
    # indent under Hue/Saturation is a trap and must NOT count as a parameter.
    raw = read_page(z, "cop/chromakey.txt")
    p = parse_page("cop/chromakey.txt", raw)
    check("P1 chromakey.title", p.title, "Chroma Key")
    check("P1 chromakey.context_directive", p.directives.get("context"), "cop")
    check("P1 chromakey.internal", p.directives.get("internal"), "chromakey")
    check("P1 chromakey.summary", p.summary,
          "Keys an input based on hue, saturation, and luminance ranges.")
    check("P1 chromakey.header_order", p.header_order, "directives-first")
    check("P1 chromakey.n_params", len(p.params), 15, "hand-counted")
    check("P1 chromakey.n_params_with_id", len(p.params_with_id), 15, "hand-counted")
    check("P1 chromakey.ids", [i.ident for i in p.params],
          ["signature", "method", "invert", "huecircle", "lumrange", "screencolor",
           "threshold", "width", "huerolloff", "satrolloff", "lumrolloff",
           "interpolation", "preview", "previewcolor", "premult"])
    check("P1 chromakey.headings", [h[1] for h in p.headings], ["Key", "Rolloff", "Visualize"])
    check("P1 chromakey.at_sections", [s[1] for s in p.at_sections],
          ["parameters", "inputs", "outputs"])
    check("P1 chromakey.n_includes", len(p.includes), 0)
    check("P1 chromakey.TIP_not_a_param", "TIP" in [i.label for i in p.params], False,
          "TIP: is indented under a param; counting it would be the naive bug")

    # ================================================== POSITIVE CONTROL 2
    # cop2/blur.txt — hand-read 2026-07-27, 77 lines. Parameters live at
    # indent 8 under an indented "== Blur ==". ZERO carry #id. Six :include
    # directives in three distinct shapes. Menu entries UV Coords/Pixels are
    # nested under Units and must NOT count.
    raw2 = read_page(z, "cop2/blur.txt")
    p2 = parse_page("cop2/blur.txt", raw2)
    check("P2 blur.title", p2.title, "Blur")
    check("P2 blur.header_order", p2.header_order, "directives-first")
    check("P2 blur.n_params", len(p2.params), 6, "hand-counted, indent 8")
    check("P2 blur.labels", [i.label for i in p2.params],
          ["X/Y Filter", "Size", "Y Size", "Units", "Per-Pixel Blur", "Fast Blur"])
    check("P2 blur.n_params_with_id", len(p2.params_with_id), 0, "H9-F3: cop2 rarely ids")
    check("P2 blur.menu_entries_excluded",
          sorted({i.label for i in p2.items if i.depth == 1}), ["Pixels", "UV Coords"])
    check("P2 blur.n_includes", len(p2.includes), 6, "hand-counted")
    check("P2 blur.include_targets", [t for _, t, _, _ in p2.includes],
          ["/composite/_old_cops_deprecated", "pixelparms#coppixeldescription/",
           "maskparms#copmaskdescription/", "pixelparms#pixelparms/",
           "maskparms#maskparms/", "localvars"])
    check("P2 blur.deprecation_banner_seen",
          any(t == "/composite/_old_cops_deprecated" for _, t, _, _ in p2.includes), True,
          "H7-F4: H5 missed this and read the whole subsystem as current")

    # ================================================== POSITIVE CONTROL 3
    # out/karma.txt — hand-read, 17 lines. TITLE FIRST, then directives.
    # No @parameters at all: a page that EXISTS and documents zero parameters.
    p3 = parse_page("out/karma.txt", read_page(z, "out/karma.txt"))
    check("P3 outkarma.header_order", p3.header_order, "title-first",
          "lop/ and out/ invert the header order used by cop/ and top/")
    check("P3 outkarma.n_params", len(p3.params), 0, "exists but grounds nothing")
    check("P3 outkarma.has_summary", bool(p3.summary), True)
    check("P3 outkarma.at_sections", [s[1] for s in p3.at_sections], ["related"])

    # ================================================== POSITIVE CONTROL 4
    # top/ropfetch.txt — @top_attributes uses "::`name`:" markers with an
    # indented "#type:" directive. A parameters-only reader scores this page
    # as ungrounded when it is in fact richly documented.
    p4 = parse_page("top/ropfetch.txt", read_page(z, "top/ropfetch.txt"))
    check("P4 ropfetch.has_top_attributes",
          "top_attributes" in [s[1] for s in p4.at_sections], True)
    check("P4 ropfetch.attr_markers_parsed",
          [i.label for i in p4.items if i.section == "top_attributes"][:4],
          ["`hip`", "`outputparm`", "`executeparm`", "`rop`"])

    # ============================ POSITIVE CONTROL 5 — the Vimeo id trap
    # sop/xform.txt closes its @parameters with four ":vimeo: Transform SOP"
    # blocks, each carrying an indented "#id: <9-digit video id>". Binding those
    # to the preceding label re-keys the real parameter "Combine" from 'combine'
    # to '406959576'. That is a silent, plausible, WRONG join key.
    p5 = parse_page("sop/xform.txt", read_page(z, "sop/xform.txt"))
    combine = [i for i in p5.params if i.label == "Combine"]
    check("P5 xform.Combine_found", len(combine), 1)
    check("P5 xform.Combine_id_not_vimeo", combine[0].ident if combine else None, "combine",
          "would be '406959576' if a colon-directive did not close the item scope")
    check("P5 xform.no_numeric_ids",
          [i.ident for i in p5.params if i.ident and i.ident.isdigit()], [])
    check("P5 xform.vimeo_recorded_as_directive",
          sum(1 for _, nm, _ in p5.colon_directives if nm == "vimeo"), 4)

    # ============================ POSITIVE CONTROL 6 — #channels is a join key
    # cop2 names internal parms with "#channels: /blursize", not "#id:".
    # 248 #channels vs 51 #id in that context. An #id-only reader scores the
    # whole context un-identifiable. (H9's helpdoc.py:180 records the same.)
    p6 = parse_page("cop2/edgeblur.txt", read_page(z, "cop2/edgeblur.txt"))
    bs = [i for i in p6.params if i.label == "Blur Size"]
    check("P6 edgeblur.BlurSize_found", len(bs), 1)
    check("P6 edgeblur.BlurSize_has_no_#id", bs[0].ident if bs else "x", None)
    check("P6 edgeblur.BlurSize_channels", bs[0].channels if bs else None, "/blursize")
    check("P6 edgeblur.internal_names_recovered",
          len(p6.params_with_internal_name) > 0, True,
          "0 under an #id-only reader")

    # ============================ POSITIVE CONTROL 7 — the other include verbs
    p7 = parse_page("lop/usd_rop.txt", read_page(z, "lop/usd_rop.txt"))
    check("P7 usd_rop.:import_captured",
          [(t, v) for _, t, _, v in p7.includes if v == "import"],
          [("/nodes/out/usd#parameters", "import")],
          ":import pulls an ENTIRE @parameters section from another context")
    p8 = parse_page("obj/cam.txt", read_page(z, "obj/cam.txt"))
    check("P7 cam.:includeprop_captured",
          any(v == "includeprop" for _, _, _, v in p8.includes), True)

    # ============================ POSITIVE CONTROL 8 — #contentfrom
    # A parameter whose DESCRIPTION lives on another page. Label + id present,
    # inline prose absent. A quality floor keyed on "has a description" must
    # decide about these deliberately, not by accident.
    p9 = parse_page("cop/adjacency_distort.txt", read_page(z, "cop/adjacency_distort.txt"))
    sig = [i for i in p9.params if i.label == "Signature"]
    check("P8 adjacency.Signature_found", len(sig), 1)
    check("P8 adjacency.Signature_contentfrom",
          sig[0].contentfrom if sig else None, "/nodes/cop/distort#signature")
    check("P8 adjacency.Signature_no_inline_desc", sig[0].desc_lines if sig else -1, 0,
          "described BY REFERENCE only")

    # ============================ POSITIVE CONTROL 9 — the H7-F4 banner target
    # is NOT in nodes.zip. A reader opening only nodes.zip cannot resolve it and
    # reproduces H5's defect exactly.
    import zipfile as _zf
    _help = os.path.dirname(NODES_ZIP)
    check("P9 banner_target_absent_from_nodes.zip",
          any("old_cops_deprecated" in n for n in z.namelist()), False)
    _comp = _zf.ZipFile(os.path.join(_help, "composite.zip"))
    check("P9 banner_target_present_in_composite.zip",
          [n for n in _comp.namelist() if "old_cops_deprecated" in n],
          ["_old_cops_deprecated.txt"],
          "H7-F4: resolving it requires globbing every help zip, not just nodes.zip")
    check("P9 banner_body_says_deprecated",
          "deprecated" in _comp.read("_old_cops_deprecated.txt").decode("utf-8").lower(), True)

    # ============================ POSITIVE CONTROL 10 — the BOM
    # 58 pages carry a UTF-8 BOM. Plain 'utf-8' DECODES THEM WITHOUT ERROR and
    # leaves U+FEFF at offset 0, hiding the page's first directive. Measured
    # impact of getting this wrong: 32 pages lose >=1 directive, 26 lose their
    # title. No exception is ever raised.
    bom_pages = [n for n in z.namelist()
                 if n.endswith(".txt") and z.read(n)[:3] == b"\xef\xbb\xbf"]
    check("P10 bom_page_count", len(bom_pages), 58)
    check("P10 emboss_is_a_bom_page", "cop2/emboss.txt" in bom_pages, True)
    p10 = parse_page("cop2/emboss.txt", read_page(z, "cop2/emboss.txt"))
    check("P10 emboss_type_directive_recovered", p10.directives.get("type"), "node",
          "reads as a non-node page under plain utf-8 (H9 helpdoc.py:118)")
    p10bad = parse_page("cop2/emboss.txt", z.read("cop2/emboss.txt").decode("utf-8"))
    check("P10 plain_utf8_LOSES_it", p10bad.directives.get("type"), None,
          "the negative half: proves the control is measuring the BOM")

    # ================================================== NEGATIVE CONTROLS
    # Law 1: state the condition under which each count fails, then cause it.
    n1 = parse_page("x.txt", re.sub(r"^\s*#id:.*$", "", raw, flags=re.M))
    check("N1 strip_all_#id -> ids collapse", len(n1.params_with_id), 0)
    check("N1 strip_all_#id -> params HOLD", len(n1.params), 15,
          "labels survive id removal: proves the two are measured independently")

    n2 = parse_page("x.txt", raw.replace("@parameters", "@notparameters"))
    check("N2 kill_@parameters -> params collapse", len(n2.params), 0)

    n3 = parse_page("x.txt", re.sub(r"^\s*:include .*$", "", raw2, flags=re.M))
    check("N3 strip_includes -> includes collapse", len(n3.includes), 0)

    n4 = parse_page("x.txt", raw.replace('"""Keys an input based on hue, '
                                         'saturation, and luminance ranges."""', ""))
    check("N4 strip_summary -> summary collapses", n4.summary, None)

    n5_txt = "\n".join(l[4:] if l.startswith("    ") else l for l in raw2.split("\n"))
    n5 = parse_page("x.txt", n5_txt)
    check("N5 dedent_cop2 -> params HOLD", len(n5.params), 6,
          "reader is indentation-relative, not column-locked")

    # ================================================== BLIND-READER CONTROL
    # R60: prove the instrument is not blind in the way H5's was. A column-0
    # reader sees chromakey fine and cop2/blur not at all — which is precisely
    # how a whole context reads as ungrounded while being documented.
    check("B1 blind_reader sees chromakey", blind_params(raw), 15)
    check("B1 blind_reader BLIND to cop2/blur", blind_params(raw2), 0,
          "THE failure this calibration exists to exclude")
    check("B1 our_reader sees cop2/blur", len(p2.params), 6)

    # B2 — the CRLF blindness this calibration FOUND in our own reader on the
    # first run. chromakey is one of 67 CRLF pages in cop/ (of 375).
    check("B2 chromakey.eol", p.eol, "CRLF", "17.9% of cop/ is CRLF")
    check("B2 blur.eol", p2.eol, "LF")
    check("B2 crlf_blind_reader BLIND to chromakey", crlf_blind_params(raw), 0,
          "a '$'-anchored reader scores this documented page as ungrounded")
    # The claim here is NOT that the broken reader is accurate — it is that it is
    # ALIVE, so that its 0 on chromakey is caused by CRLF and not by a dead
    # function. (It returns 7 on cop2/blur: 5 real + 2 menu entries, missing
    # "Y Size:" because its own label regex rejects an internal space. Pinning
    # that number would pin a bug's arithmetic, not the control's meaning.)
    check("B2 crlf_blind_reader is ALIVE on an LF page", crlf_blind_params(raw2) > 0, True,
          "isolates CRLF as the cause of its zero, vs. the function being inert")
    check("B2 our_reader sees chromakey after fix", len(p.params), 15)

    # ------------------------------------------------------------------ report
    npass = sum(1 for r in RESULTS if r["pass"])
    print(f"{'CONTROL':46s} {'GOT':>6s}  {'WANT':>6s}  RESULT")
    print("-" * 78)
    for r in RESULTS:
        g = r["got"] if not isinstance(r["got"], list) else f"<{len(r['got'])} items>"
        w = r["want"] if not isinstance(r["want"], list) else f"<{len(r['want'])} items>"
        print(f"{r['control']:46s} {str(g)[:6]:>6s}  {str(w)[:6]:>6s}  "
              f"{'PASS' if r['pass'] else 'FAIL'}")
        if not r["pass"]:
            print(f"    got : {r['got']!r}")
            print(f"    want: {r['want']!r}")
    print("-" * 78)
    print(f"{npass}/{len(RESULTS)} controls pass")

    out = os.path.join(_HERE, "_i0_calibration.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"schema": "i0-calibration/v1", "build": "22.0.368",
                   "archive": NODES_ZIP, "passed": npass, "total": len(RESULTS),
                   "controls": RESULTS}, fh, indent=2)
    print(f"wrote {out}")
    return 0 if npass == len(RESULTS) else 1


main()
