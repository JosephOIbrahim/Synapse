"""I1 -- calibration for ``i1_extract``. R60: the reader is not trusted until it
is shown returning a KNOWN answer on pages that were read BY HAND.

Three control classes, and the third is the one that does the real work:

  POSITIVE  a page read by hand, whose exact answer the parser must reproduce.
  NEGATIVE  a MUTATION of a real page that must drive a count to zero or flip a
            verdict. Law 1: a check that cannot fail is a decoration.
  BLIND     a deliberately NAIVE reader, shown returning the WRONG answer on a
            page where ours returns the right one. These reproduce, on purpose,
            the exact silent defects I0 found -- the ones that raise nothing and
            return a plausible number.

Every control below carries ``fails_if``: the condition under which it goes red.
If a control has no statable failure condition it is not a control.

    python harness/notes/ingest/i1_calibrate.py

PRODUCER: this file -> harness/notes/ingest/_i1_calibration.json
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import i1_extract as X  # noqa: E402

RESULTS: list = []


def check(cid: str, kind: str, what: str, fails_if: str, got, expect) -> bool:
    ok = got == expect
    RESULTS.append({
        "id": cid, "class": kind, "asserts": what, "fails_if": fails_if,
        "expected": expect, "got": got, "pass": ok,
    })
    return ok


def checkf(cid: str, kind: str, what: str, fails_if: str, got, pred, expect_desc: str) -> bool:
    ok = bool(pred(got))
    RESULTS.append({
        "id": cid, "class": kind, "asserts": what, "fails_if": fails_if,
        "expected": expect_desc, "got": got, "pass": ok,
    })
    return ok


# ==========================================================================
# GROUND TRUTH -- read by hand from the shipped archive before the parser was
# pointed at it. These are transcriptions, not parser output.
# ==========================================================================
CHROMAKEY_LABELS = [
    "Signature", "Method", "Invert", "Hue/Saturation", "Luminance Range",
    "Screen Color", "Threshold", "Width", "Hue", "Saturation", "Luminance",
    "Interpolation", "Preview", "Preview Color", "Premultiply",
]
CHROMAKEY_IDS = [
    "signature", "method", "invert", "huecircle", "lumrange", "screencolor",
    "threshold", "width", "huerolloff", "satrolloff", "lumrolloff",
    "interpolation", "preview", "previewcolor", "premult",
]
CHROMAKEY_SUMMARY = "Keys an input based on hue, saturation, and luminance ranges."
EMBOSS_RAW_LABELS = [
    "Light Position", "Diffuse Color", "Specular Color", "Diffuse Dimmer",
    "Specular Dimmer", "Bump Height", "Specular Model", "Phong Exponent",
    "Blinn Roughness", "Bump Plane",
]
EMBOSS_RAW_CHANNELS = [
    ["lightposx", "lightposy", "lightposz"], ["diffr", "diffg", "diffb", "diffa"],
    ["specr", "specg", "specb", "speca"], ["diffdimmer"], ["specdimmer"],
    ["bumpscale"], ["specmodel"], ["specexp"], ["specrough"], ["bumpplane"],
]


def main() -> int:
    corpus = X.load_corpus()
    boms = X.bom_keys()

    # ---------------------------------------------------------------- POSITIVE
    ck = X.parse_page("nodes/cop/chromakey", corpus)
    check("P1a", "POSITIVE",
          "cop/chromakey -- the 15 hand-read parameter LABELS, in document order",
          "the parser adds, drops or re-orders any parameter on a page read by hand",
          [i.label for i in ck.params], CHROMAKEY_LABELS)
    check("P1b", "POSITIVE",
          "cop/chromakey -- the 15 hand-read #id values (evidence, not the key)",
          "an #id is bound to the wrong label, or lost",
          [i.ids[0] if i.ids else None for i in ck.params], CHROMAKEY_IDS)
    check("P1c", "POSITIVE", "cop/chromakey -- title, summary, rung, header order",
          "the summary regex loses the trailing sentence, or the rung ladder mis-scores a full page",
          [ck.title, ck.summary, X.rung(ck), ck.header_order],
          ["Chroma Key", CHROMAKEY_SUMMARY, "ACTIONABLE", "directives-first"])
    check("P1d", "POSITIVE",
          "cop/chromakey is CRLF -- recorded, and parsed anyway",
          "line endings are absorbed before being measured, hiding the hazard",
          ck.eol, "CRLF")
    check("P1e", "POSITIVE",
          "cop/chromakey -- the nested 'TIP:' block is folded into its parent, not counted",
          "a nested box is promoted to a parameter, inflating the count",
          [i.label for i in ck.params if i.label == "TIP"] +
          [("TIP" in [i.label for i in ck.params])],
          [False])

    em = X.parse_page("nodes/cop2/emboss", corpus)
    em_raw = X.parse_text("nodes/cop2/emboss", corpus.pages["nodes/cop2/emboss"],
                          corpus.pages["nodes/cop2/emboss"])
    check("P2a", "POSITIVE",
          "cop2/emboss RAW -- the 10 hand-read labels at indent 4 (cop2 is not column-0)",
          "the item base indent is assumed rather than resolved per scope",
          [i.label for i in em_raw.params], EMBOSS_RAW_LABELS)
    check("P2b", "POSITIVE",
          "cop2/emboss -- internal names arrive via #channels, and there are ZERO #id",
          "the reader follows only #id and reports the cop2 surface as un-identifiable",
          [[c for c in i.channels] for i in em_raw.params] +
          [sum(len(i.ids) for i in em_raw.params)],
          EMBOSS_RAW_CHANNELS + [0])
    check("P2c", "POSITIVE",
          "cop2/emboss ships a BOM -- and its first directive survives decoding",
          "the corpus decodes plain utf-8, leaving U+FEFF at offset 0 and eating '#type: node'",
          ["nodes/cop2/emboss" in boms, em.directives.get("type")], [True, "node"])
    check("P2d", "POSITIVE",
          "cop2/emboss 'Specular Model' is documented BY ITS MENU VALUES",
          "menu values are dropped instead of folded, scoring a documented parameter as a stub",
          [bool(i.description) for i in em.params if i.label == "Specular Model"], [True])

    dl = X.parse_page("nodes/lop/distantlight", corpus)
    dl_raw = X.parse_text("nodes/lop/distantlight", corpus.pages["nodes/lop/distantlight"],
                          corpus.pages["nodes/lop/distantlight"])
    check("P3a", "POSITIVE",
          "lop/distantlight -- 0 parameters as it ships, 87 once includes resolve",
          "include resolution is skipped, reporting a fully-documented node as ungrounded",
          [len(dl_raw.params), len(dl.params)], [0, 87])
    check("P3b", "POSITIVE",
          "lop/distantlight is TITLE-first -- directives are not assumed to lead the file",
          "the header block is read from the top of the file, losing #context/#internal on 79% of lop pages",
          dl.header_order, "title-first")
    check("P3c", "POSITIVE",
          "lop/distantlight's one broken include is MARKED and counted, never dropped",
          "an unresolvable target is silently deleted, turning an undercount into a clean-looking parse",
          [dl.include_stats.get("unresolved_anchor"),
           dl.include_stats.get("unresolved_targets")],
          [1, ["_simple_prims#create_prims/"]])

    ad = X.parse_page("nodes/cop/adjacency_distort", corpus)
    sig = [i for i in ad.params if i.label == "Signature"][0]
    check("P4", "POSITIVE",
          "cop/adjacency_distort 'Signature' has NO inline prose -- #contentfrom supplies it",
          "the #contentfrom axis is not followed, scoring documented parameters as described-by-nothing",
          [sig.description_source, bool(sig.description)],
          ["contentfrom:/nodes/cop/distort#signature", True])

    xf = X.parse_page("nodes/sop/xform", corpus)
    comb = [i for i in xf.items if i.label == "Combine"]
    check("P5", "POSITIVE",
          "sop/xform 'Combine' keys to 'combine' -- NOT to the Vimeo video id on the page",
          "a ':vimeo:' block does not close the item scope and its '#id: 406959576' re-keys a real parameter",
          [comb[0].ids if comb else None,
           any(d.isdigit() and len(d) > 5 for i in xf.items for d in i.ids)],
          [["combine"], False])

    names = X.the_161()
    check("P6", "POSITIVE",
          "the 161 new Copernicus nodes, from the SHIPPED news.zip (not the browsing cache)",
          "the what's-new extraction over- or under-counts, or the shipped page stops naming node paths",
          [len(names), len(set(names)), "chromakey" in names], [161, 161, True])

    ur = X.parse_page("nodes/lop/usd_rop", corpus)
    checkf("P7", "POSITIVE",
           "lop/usd_rop -- ':import' is followed, and the @parameters header travels with the section",
           "only ':include' is matched, or an imported @section body lands in the preamble where a parameter parser ignores it",
           len(ur.params), lambda n: n >= 30, ">= 30 parameters")

    check("P8", "POSITIVE",
          "the deprecation banner target resolves -- it lives in composite.zip, NOT nodes.zip",
          "the corpus opens only nodes.zip, reproducing H7-F4: a vendor-deprecated subsystem reads as current",
          ["composite/_old_cops_deprecated" in corpus.pages,
           "Copernicus" in corpus.pages.get("composite/_old_cops_deprecated", "")],
          [True, True])

    with zipfile.ZipFile(X.HELP_DIR / "nodes.zip") as z:
        nz_bom = sum(1 for i in z.infolist()
                     if i.filename.endswith(".txt") and z.open(i).read(3) == b"\xef\xbb\xbf")
    check("P9", "CROSS-CHECK",
          "nodes.zip BOM count == 58, the figure I0 measured independently",
          "this leg's corpus loader disagrees with I0's on the archive's own composition",
          nz_bom, 58)

    dep_em = X.doc_deprecation(corpus.pages["nodes/cop2/emboss"], em.directives,
                               em.raw_includes, em.colon_directives)
    check("P10", "POSITIVE",
          "cop2/emboss is doc-deprecated by the banner, and the signal NAMES its source",
          "the deprecation detector reports a bare boolean with no evidence of which side said so",
          [dep_em["deprecated"], dep_em["signals"]],
          [True, [":include /composite/_old_cops_deprecated"]])

    # ---------------------------------------------------------------- NEGATIVE
    raw_ck = corpus.pages["nodes/cop/chromakey"]

    mut = re.sub(r"^\s*#id:.*$", "", raw_ck, flags=re.M)
    n1 = X.parse_text("nodes/cop/chromakey", mut, mut)
    check("N1", "NEGATIVE",
          "strip every #id: the 15 parameters SURVIVE (label is the key) and 0 ids remain",
          "the parser is secretly keyed on #id -- the count would collapse with the ids",
          [len(n1.params), sum(len(i.ids) for i in n1.params)], [15, 0])

    mut = raw_ck.replace("@parameters", "@notparameters")
    n2 = X.parse_text("nodes/cop/chromakey", mut, mut)
    check("N2", "NEGATIVE",
          "rename @parameters: the parameter count goes to ZERO",
          "the count is not actually measuring the @parameters section -- it would survive its removal",
          len(n2.params), 0)

    mut = corpus.pages["nodes/cop2/emboss"].replace(
        ":include /composite/_old_cops_deprecated:", "")
    n3p = X.parse_text("nodes/cop2/emboss", mut, mut)
    n3 = X.doc_deprecation(mut, n3p.directives, X.parse_include_lines(mut),
                           n3p.colon_directives)
    check("N3", "NEGATIVE",
          "remove the banner: doc-deprecation goes FALSE",
          "the deprecation verdict is unfalsifiable -- it would report True on a clean page",
          n3["deprecated"], False)

    mut = re.sub(r'""".*?"""', "", raw_ck, flags=re.S)
    n4 = X.parse_text("nodes/cop/chromakey", mut, mut)
    check("N4", "NEGATIVE",
          "remove the summary: the rung falls ACTIONABLE -> EXISTS and the page stops clearing",
          "the floor cannot fail -- every page would clear it regardless of content",
          [X.rung(n4), X.clears_floor(X.rung(n4))], ["EXISTS", False])

    mut = re.sub(r"^\s*:include\s+.*:\s*$", "", corpus.pages["nodes/lop/distantlight"],
                 flags=re.M)
    n5 = X.parse_text("nodes/lop/distantlight", mut, mut)
    check("N5", "NEGATIVE",
          "remove distantlight's includes: 87 parameters -> 0",
          "the 87 are being invented somewhere other than include resolution",
          len(n5.params), 0)

    checkf("N6", "NEGATIVE",
           "a fabricated Copernicus name is ABSENT from the 161 and from the archive",
           "the presence test says yes to everything, making '161 of 161' unfalsifiable",
           ["grunge_unobtainium" in names,
            "nodes/cop/grunge_unobtainium" in corpus.pages],
           lambda g: g == [False, False], "[False, False]")

    # Strip descriptions but keep labels and ids: the FLOOR rung must fail while
    # the page still has parameters. This separates "has parameters" from "has
    # documented parameters", which is the whole point of the floor.
    #
    # NOTE: nested entries must go too. The first version of this control kept
    # them, the fold pass turned the surviving "TIP:" label into the parent's
    # description, and the control read ACTIONABLE -- i.e. the MUTATION was
    # wrong, not the reader. Recorded rather than quietly repaired.
    lines = []
    in_par = False
    for line in raw_ck.replace("\r\n", "\n").split("\n"):
        if line.startswith("@"):
            in_par = line.strip() == "@parameters"
            lines.append(line)
            continue
        if not in_par:
            lines.append(line)
            continue
        m_item = X.RE_ITEM.match(line)
        m_dir = X.RE_DIRECTIVE.match(line)
        if (m_item and X._indent(line) == 0) or (m_dir and m_dir.group("key") == "id") \
                or X.RE_HEADING.match(line) or not line.strip():
            lines.append(line)
    mut = "\n".join(lines)
    n7 = X.parse_text("nodes/cop/chromakey", mut, mut)
    check("N7", "NEGATIVE",
          "strip descriptions only: 15 parameters remain but the rung falls to SUMMARY",
          "the floor counts parameters rather than DOCUMENTED parameters -- a stub page would clear it",
          [len(n7.params), X.rung(n7)], [15, "SUMMARY"])

    # ------------------------------------------------------------------- BLIND
    # Naive readers, kept on purpose as negative instruments. Each must return
    # the WRONG answer where the real reader returns the right one.

    def blind_lf_only(text: str) -> int:
        """I0 defect D1: split on '\\n', anchor items on '$', never normalise."""
        return len(re.findall(r"^(?!#)(?!:)[^\s:][^:]*:$", text, re.M))

    b1 = blind_lf_only(raw_ck)
    check("B1", "BLIND",
          "a no-CRLF-normalisation reader finds 0 parameters on cop/chromakey; ours finds 15",
          "the blind reader accidentally works -- then it is not demonstrating the hazard",
          [b1, len(ck.params)], [0, 15])

    with zipfile.ZipFile(X.HELP_DIR / "nodes.zip") as z:
        emboss_bytes = z.read("cop2/emboss.txt")
    blind_text = emboss_bytes.decode("utf-8")          # NOT utf-8-sig
    b2 = X.parse_text("nodes/cop2/emboss", blind_text, blind_text)
    check("B2", "BLIND",
          "a plain-utf-8 reader loses emboss's '#type: node'; ours keeps it",
          "the BOM stops being silent -- the decode would raise instead of succeeding wrongly",
          [b2.directives.get("type"), em.directives.get("type")], [None, "node"])

    def blind_id_binder(text: str) -> dict:
        """I0 defect D3: bind any indented '#id:' to the nearest preceding label,
        with NO colon-directive scope close.

        Identical to the real reader's id collection in every other respect --
        same regexes, same append-and-dedupe -- so the one variable under test is
        the scope close and nothing else.
        """
        out: dict = {}
        label = None
        for line in text.replace("\r\n", "\n").split("\n"):
            m = X.RE_ITEM.match(line)
            if m:
                label = X.clean(m.group("label").strip())
                out.setdefault(label, [])
                continue
            m = X.RE_DIRECTIVE.match(line)
            if m and m.group("key") == "id" and label:
                for part in (q.strip() for q in m.group("val").split(",")):
                    if part and part not in out[label]:
                        out[label].append(part)
        return out

    b3 = blind_id_binder(corpus.pages["nodes/sop/xform"]).get("Combine")
    check("B3", "BLIND",
          "a no-scope-close reader binds sop/xform's Vimeo VIDEO id onto 'Combine'; ours does not",
          "the Vimeo trap stops reproducing -- then P5 is passing for no reason",
          # FOUR video ids, not one: sop/xform ships four :vimeo: blocks in a row
          # after "Combine" and every one of them binds. The expectation was
          # corrected, not the reader -- the trap is worse than I0 recorded.
          [b3, comb[0].ids if comb else None],
          [["combine", "406959576", "406959551", "406959500", "406959532"], ["combine"]])

    b4_pages = {k: v for k, v in corpus.pages.items() if k.startswith("nodes/")}
    check("B4", "BLIND",
          "a nodes.zip-only corpus cannot resolve the deprecation banner; ours can",
          "the banner target turns out to live in nodes.zip after all, and I0-F9 is wrong",
          ["composite/_old_cops_deprecated" in b4_pages,
           "composite/_old_cops_deprecated" in corpus.pages],
          [False, True])

    def blind_include_only(text: str, base: str, key: str) -> str:
        """A ':include'-only resolver: ':import' and ':includeprop' pass through."""
        only = re.sub(r"^(\s*):(?:import|includeprop)\s+.+:\s*$", r"\1",
                      text.replace("\r\n", "\n"), flags=re.M)
        return X.resolve_all(only, corpus, base, self_key=key)

    b5_text = blind_include_only(corpus.pages["nodes/lop/usd_rop"], "nodes/lop",
                                 "nodes/lop/usd_rop")
    b5 = X.parse_text("nodes/lop/usd_rop", corpus.pages["nodes/lop/usd_rop"], b5_text)
    check("B5", "BLIND",
          "a ':include'-only reader loses every usd_rop parameter; ours keeps them",
          "':import' turns out to be decorative, and P7 is testing nothing",
          [len(b5.params) == 0, len(ur.params) >= 30], [True, True])

    b6 = [i for i in X.parse_text("nodes/cop/adjacency_distort",
                                  corpus.pages["nodes/cop/adjacency_distort"],
                                  X.resolve_all(corpus.pages["nodes/cop/adjacency_distort"],
                                                corpus, "nodes/cop",
                                                self_key="nodes/cop/adjacency_distort")
                                  ).params if i.label == "Signature"][0]
    check("B6", "BLIND",
          "without following #contentfrom, adjacency_distort 'Signature' is described by nothing",
          "#contentfrom entries carry inline prose after all, and P4 is redundant",
          [bool(b6.description), bool(sig.description)], [False, True])

    # ``own_description`` is the entry's prose BEFORE menu values were folded in
    # -- i.e. exactly what a no-fold reader would see. cop2/emboss's "Specular
    # Model" has none: its whole body is "Phong:" / "Blinn:". So a no-fold reader
    # scores a fully-documented parameter as a stub, on a page whose ENTIRE
    # parameter surface is #channels-keyed.
    sm = [i for i in em.params if i.label == "Specular Model"][0]
    n_unfolded_thin = sum(1 for i in em.params if not i.own_description)
    check("B7", "BLIND",
          "a no-fold reader scores emboss 'Specular Model' as undocumented; ours documents it",
          "the entry carries inline prose after all, so the fold pass is not what rescues it",
          [sm.own_description, bool(sm.description), n_unfolded_thin >= 1],
          ["", True, True])

    # ------------------------------------------------------------------ report
    out = {
        "schema": "i1_calibration/v1",
        "build": X.BUILD,
        "producer": "harness/notes/ingest/i1_calibrate.py",
        "reader_under_test": "harness/notes/ingest/i1_extract.py",
        "corpus_pages": len(corpus.pages),
        "rule": "R60 -- a reader is shown returning KNOWN answers on hand-read "
                "pages before it is trusted on pages nobody has read. Law 1 -- "
                "every control states the condition under which it fails.",
        "counts": {
            "total": len(RESULTS),
            "passed": sum(1 for r in RESULTS if r["pass"]),
            "failed": sum(1 for r in RESULTS if not r["pass"]),
            "by_class": {k: sum(1 for r in RESULTS if r["class"] == k)
                         for k in sorted({r["class"] for r in RESULTS})},
        },
        "controls": RESULTS,
    }
    dest = Path(__file__).resolve().parent / "_i1_calibration.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

    for r in RESULTS:
        if not r["pass"]:
            print("FAIL %-5s %s\n      expected %r\n      got      %r"
                  % (r["id"], r["asserts"], r["expected"], r["got"]))
    print("%d/%d controls pass  (%s)" % (out["counts"]["passed"], out["counts"]["total"],
                                         ", ".join("%s %d" % (k, v) for k, v
                                                   in out["counts"]["by_class"].items())))
    return 0 if out["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
