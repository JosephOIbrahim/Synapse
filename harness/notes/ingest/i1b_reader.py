"""I1 — the extractor's reader for $HFS/houdini/help/nodes.zip (Houdini 22.0.368).

This module PARSES and RESOLVES; it decides nothing and it writes nothing.
Every I1 number comes off this one instrument.

R60: calibrated before trusted. `i1b_calibrate.py` drives positive controls
(pages read BY HAND in the leg transcript, whose values are hard-coded here as
expectations), negative controls (mutations that must drive a count to zero),
and blind controls (deliberately naive readers shown returning the WRONG answer
where this one returns the right one). The corpus build REFUSES to run if any
control fails.

Law 1 — every check must be able to fail:
  * every positive control fails if the parser stops seeing a page's parameters
  * every negative control fails if a mutation does NOT change the count
  * every blind control fails if the naive reader AGREES with this one

What this reader inherits from I0, and why each line is here rather than
rediscovered by breakage (I0_SCOUT.md, sha256 0963cf8c...b9fb21, read as a
DESIGN INPUT — every load-bearing number is re-measured by I1's own producers,
never inherited; see I1_INGEST.md §0):

  D1  CRLF pages read as ZERO parameters, silently   -> normalise EOL after recording it
  D2  a BOM eats the first '#directive', silently    -> decode utf-8-sig
  D3  ':vimeo:' + '#id: 406959576' re-keys the       -> a colon-directive CLOSES
      PRECEDING real parameter to a video id            the current item scope

and one this leg adds, found while hand-reading `cop/camerablend.txt`:

  D4  an indented 'NOTE:' + '#id: blend_cameras' in the PREAMBLE (before any
      @section) is recorded as a PAGE-LEVEL directive, so the page acquires a
      bogus '#id'. Page directives are therefore accepted at column 0 only.
"""

from __future__ import annotations

import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_H9 = Path(__file__).resolve().parents[1] / "h9"
if str(_H9) not in sys.path:
    sys.path.insert(0, str(_H9))

import helpdoc  # noqa: E402  (committed at harness/notes/h9/helpdoc.py)

BUILD = "22.0.368"
HELP_DIR = Path(
    r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help"
)
NODES_ZIP = HELP_DIR / "nodes.zip"
NEWS_ZIP = HELP_DIR / "news.zip"

# Contexts this leg ingests, in the order the brief names them.
CONTEXTS = ("cop", "lop", "cop2")

# Live catalogue category per help context. VERIFIED-RUNTIME 22.0.368:
# Cop 384, Lop 218, Cop2 169 — probed, not inherited (_i1_live.py re-probes).
CATEGORY = {"cop": "Cop", "lop": "Lop", "cop2": "Cop2"}


# ---------------------------------------------------------------- verbs
# helpdoc's resolver matches ':include' ONLY. The shipped archive uses THREE
# include verbs, and the two it misses are not decorative:
#   :includeprop  307 archive-wide
#   :import         1 — and it pulls an ENTIRE @parameters section across
#                       contexts: lop/usd_rop.txt <- /nodes/out/usd#parameters
# Widening the module regex re-uses helpdoc's anchor/cycle/unresolved logic
# instead of duplicating 55 subtle lines that would then drift.
# Group numbering is preserved: (1) = pad, (2) = target.
# CONTROL `verbs_all_three_resolve` goes RED if this ever stops taking effect.
_WIDE_INCLUDE_RE = re.compile(r"^(\s*):(?:include|includeprop|import)\s+(.+):\s*$")


def _widen_include_verbs() -> None:
    helpdoc._INCLUDE_RE = _WIDE_INCLUDE_RE


_widen_include_verbs()


# ---------------------------------------------------------------- anchors
# An include anchor can name an @SECTION rather than an id-anchored block:
#     cop/rop_image.txt   :include /nodes/out/image#parameters/:
#     lop/usd_rop.txt     :import  /nodes/out/usd#parameters:
# helpdoc's `_anchored_block` only understands id-style anchors, so both of
# those resolved to nothing and both pages read as having ZERO parameters —
# silently. `cop/rop_image` is one of the newly-named Copernicus nodes, and it
# scored below the quality floor purely because of this.
#
# Found by CROSS-VALIDATION against the second extractor that ran in this
# worktree: it resolved the page and this reader did not. Two instruments
# disagreeing is information; averaging it away would have destroyed it.
# Measured blast radius: 16 section-anchored includes over 13 pages archive-
# wide, 2 of them in this leg's contexts.
# CONTROL `rop_image_section_anchor_resolves` goes RED if this stops working.
_ORIG_ANCHORED_BLOCK = helpdoc._anchored_block

_SECTION_ANCHORS = frozenset({
    "parameters", "inputs", "outputs", "locals", "related",
    "top_attributes", "properties",
})


def _anchored_block_or_section(text: str, anchor: str):
    blk = _ORIG_ANCHORED_BLOCK(text, anchor)
    if blk is not None:
        return blk
    key = anchor.strip("/").strip()
    if key in _SECTION_ANCHORS:
        return helpdoc.at_sections(text).get(key)
    return None


helpdoc._anchored_block = _anchored_block_or_section


# ---------------------------------------------------------------- grammar

RE_DIRECTIVE = re.compile(
    r"^(?P<ind>[ \t]*)#(?P<key>[A-Za-z_][\w]*)\s*:[ \t]*(?P<val>.*?)[ \t]*$")
RE_TITLE = re.compile(r"^=\s+(?P<title>.+?)\s+=\s*$")
RE_HEADING_EQ = re.compile(
    r"^(?P<ind>[ \t]*)(?P<lvl>={2,})\s+(?P<text>.+?)\s+(?P=lvl)\s*$")
RE_HEADING_TILDE = re.compile(
    r"^(?P<ind>[ \t]*)(?P<lvl>~{2,})\s+(?P<text>.+?)\s+(?P=lvl)\s*$")
RE_AT_SECTION = re.compile(r"^@(?P<name>[A-Za-z_][\w]*)(?:\s+(?P<arg>.*?))?\s*$")
RE_INCLUDE = re.compile(
    r"^(?P<ind>[ \t]*):(?P<verb>include|includeprop|import)\s+(?P<target>.+?):\s*$")
# ':vimeo: Transform SOP', ':warning:Deprecated:', ':box:', ':task: ...' and 25
# more shapes. Matched AFTER the include regex so include verbs win.
RE_COLON_DIRECTIVE = re.compile(r"^(?P<ind>[ \t]*):(?P<name>[A-Za-z_][\w.-]*):(?P<arg>.*)$")
RE_ITEM = re.compile(
    r"^(?P<ind>[ \t]*)"
    r"(?P<marker>::)?"
    r"(?P<label>(?!#)(?!:include\b)[^\s:][^:]*?)"
    r":[ \t]*$"
)
RE_SUMMARY_OPEN = re.compile(r'^\s*"""')

# Sections whose entries are documented PARAMETERS. @inputs/@outputs are a
# connection axis, not a parameter axis, and counting them would inflate the
# floor with things that are not parameters.
PARAM_SECTIONS = frozenset({"parameters", "top_attributes", "properties"})

# The banner that made a whole vendor-deprecated subsystem read as current
# (H7-F4). Its target lives in composite.zip, NOT nodes.zip — a reader that
# opens only nodes.zip cannot resolve it.
DEPRECATED_BANNER = "_old_cops_deprecated"

_MARKUP = re.compile(r"[`_*\[\]]")
_WS = re.compile(r"\s+")


def norm_label(s: str) -> str:
    """The join key (R97, re-measured by I0 four ways against the live runtime).

    Exactly three operations, each one measured rather than assumed:
      collapse whitespace, casefold, normalise U+2019 -> U+0027.
    Markup stripping is deliberately NOT applied here; `norm_label_aggressive`
    exists so its effect can be REPORTED as a delta instead of silently folded
    into the headline match rate.
    """
    return _WS.sub(" ", s.replace("\u2019", "'").strip()).casefold()


def norm_label_aggressive(s: str) -> str:
    """norm_label + markup strip. Measured beside the primary, never merged."""
    return _WS.sub(" ", _MARKUP.sub("", s.replace("\u2019", "'")).strip()).casefold()


@dataclass
class Item:
    """One documented parameter record."""

    label: str
    ident: str | None = None        # '#id:'   — EVIDENCE, never the key (R97)
    channels: str | None = None     # '#channels:' — the OTHER internal-name key
    contentfrom: str | None = None  # description lives on another page
    ptype: str | None = None        # '#type:' on the item
    indent: int = 0
    depth: int = 0                  # 0 = top-level parameter, >0 = menu entry
    heading: str | None = None
    section: str = "parameters"
    line: int = 0
    desc: str = ""
    marker: bool = False

    @property
    def described(self) -> bool:
        return bool(self.desc.strip())

    @property
    def internal_names(self) -> list[str]:
        """#id plus #channels, '/' stripped and space-split.
        cop2 is dominated by #channels (248 vs 51 #id): a reader following only
        #id reports that entire parameter surface as un-identifiable."""
        out: list[str] = []
        if self.ident:
            out.append(self.ident.strip())
        if self.channels:
            out.extend(c.lstrip("/") for c in self.channels.split() if c.strip())
        return [o for o in out if o]


@dataclass
class Page:
    name: str                       # 'cop/chromakey.txt' — path INSIDE nodes.zip
    context: str
    stem: str
    eol: str = "LF"
    had_bom: bool = False
    title: str | None = None
    title_line: int | None = None
    summary: str | None = None
    directives: dict = field(default_factory=dict)
    first_directive_line: int | None = None
    at_sections: list = field(default_factory=list)
    includes: list = field(default_factory=list)        # (line, target, section, verb)
    colon_directives: list = field(default_factory=list)
    items: list = field(default_factory=list)
    headings: list = field(default_factory=list)
    related: list = field(default_factory=list)
    unresolved_marks: int = 0

    @property
    def params(self) -> list:
        return [i for i in self.items
                if i.depth == 0 and i.section in PARAM_SECTIONS]

    @property
    def described_params(self) -> list:
        return [i for i in self.params if i.described]

    @property
    def actionable_params(self) -> list:
        return [i for i in self.params if i.internal_names]

    @property
    def header_order(self) -> str:
        if self.title_line is None and self.first_directive_line is None:
            return "neither"
        if self.title_line is None:
            return "directives-only"
        if self.first_directive_line is None:
            return "title-only"
        return ("directives-first" if self.first_directive_line < self.title_line
                else "title-first")

    def rung(self) -> str:
        """EXISTS < SUMMARY < FLOOR < ACTIONABLE — the highest rung reached.

        I0-FLOOR, adopted verbatim so the two legs' numbers are comparable
        rather than merely similar: a page clears the floor when it carries a
        \"\"\"summary\"\"\" AND at least one documented parameter with a
        non-empty description. Neither alone is knowledge — a summary cannot
        ground an action, and parameters with no summary cannot be retrieved
        by intent.

        ACTIONABLE is kept SEPARATE and never merged into the floor: a UI label
        with no internal name cannot ground an emission.
        """
        if not self.summary:
            return "EXISTS"
        if not self.described_params:
            return "SUMMARY"
        if not self.actionable_params:
            return "FLOOR"
        return "ACTIONABLE"

    @property
    def clears_floor(self) -> bool:
        return self.rung() in ("FLOOR", "ACTIONABLE")


def line_ending(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    if lf:
        return "LF"
    return "CR" if cr else "none"


def parse_page(name: str, text: str, had_bom: bool = False) -> Page:
    """Parse one help page. Pure function of its input; no archive access."""
    eol = line_ending(text)
    # Normalise AFTER recording. The archive's real shape is a finding, and
    # silently absorbing it is how the defect stays invisible.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    ctx, _, stem = name.partition("/")
    p = Page(
        name=name,
        context=ctx,
        stem=stem[:-4] if stem.endswith(".txt") else stem,
        eol=eol,
        had_bom=had_bom,
    )

    cur_section: str | None = None
    cur_heading: str | None = None
    pending: Item | None = None
    in_summary = False
    summary_buf: list[str] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        if "UNRESOLVED-INCLUDE" in line or "UNRESOLVED-ANCHOR" in line:
            p.unresolved_marks += 1
            pending = None
            continue

        # ---- """summary""" (may span lines) ------------------------------
        if in_summary:
            if '"""' in line:
                summary_buf.append(line[: line.index('"""')])
                p.summary = "\n".join(summary_buf).strip()
                in_summary = False
            else:
                summary_buf.append(line)
            continue
        if p.summary is None and RE_SUMMARY_OPEN.match(line):
            after = line[line.index('"""') + 3:]
            if '"""' in after:
                p.summary = after[: after.index('"""')].strip()
            else:
                in_summary = True
                summary_buf = [after]
            continue

        # ---- @section ----------------------------------------------------
        m = RE_AT_SECTION.match(line)
        if m and not line.startswith("@@"):
            cur_section = m.group("name")
            p.at_sections.append((idx, cur_section))
            cur_heading = None
            pending = None
            continue

        # ---- :include / :includeprop / :import ---------------------------
        m = RE_INCLUDE.match(line)
        if m:
            p.includes.append((idx, m.group("target").strip(),
                               cur_section or "<preamble>", m.group("verb")))
            pending = None
            continue

        # ---- any other block directive -> CLOSES the item scope (D3) -----
        m = RE_COLON_DIRECTIVE.match(line)
        if m:
            p.colon_directives.append((idx, m.group("name"), m.group("arg").strip()))
            pending = None
            continue

        # ---- '#key: value' -----------------------------------------------
        m = RE_DIRECTIVE.match(line)
        if m:
            key, val = m.group("key"), m.group("val")
            ind = len(m.group("ind").expandtabs(4))
            if pending is not None and ind > pending.indent:
                # binds to the enclosing item. FIRST WINS — a later directive
                # of the same key never overwrites an established internal name.
                if key == "id" and pending.ident is None:
                    pending.ident = val.strip() or None
                elif key == "channels" and pending.channels is None:
                    pending.channels = val.strip() or None
                elif key == "contentfrom" and pending.contentfrom is None:
                    pending.contentfrom = val.strip() or None
                elif key == "type" and pending.ptype is None:
                    pending.ptype = val.strip() or None
                continue
            # D4: page directives at column 0 ONLY. An indented 'NOTE:' +
            # '#id: blend_cameras' in the preamble of cop/camerablend.txt
            # otherwise gives the PAGE a bogus '#id'.
            if cur_section is None and ind == 0:
                if key not in p.directives:
                    p.directives[key] = val
                if p.first_directive_line is None:
                    p.first_directive_line = idx
            continue

        # ---- title / headings ---------------------------------------------
        m = RE_TITLE.match(line)
        if m and cur_section is None and p.title is None:
            p.title = m.group("title").strip()
            p.title_line = idx
            continue

        m = RE_HEADING_EQ.match(line) or RE_HEADING_TILDE.match(line)
        if m:
            cur_heading = m.group("text").strip()
            p.headings.append((idx, cur_heading, cur_section or "<preamble>"))
            pending = None
            continue

        if cur_section == "related" and stripped.startswith("-"):
            p.related.append(stripped.lstrip("- ").strip())
            continue

        # ---- documented items ----------------------------------------------
        if cur_section in PARAM_SECTIONS:
            m = RE_ITEM.match(line)
            if m:
                label = m.group("label").strip()
                if label:
                    it = Item(
                        label=label,
                        indent=len(m.group("ind").expandtabs(4)),
                        heading=cur_heading,
                        section=cur_section,
                        line=idx,
                        marker=bool(m.group("marker")),
                    )
                    p.items.append(it)
                    pending = it
                    continue
            if pending is not None and stripped:
                pending.desc = (pending.desc + " " + stripped).strip()
            continue

    # Depth resolves against the FINAL minimum indent of each (section, heading)
    # scope. Resolving it inline is wrong: a shallower sibling appearing LATER
    # lowers the base, and everything before it was already classified.
    # Measured need: cop puts parameters at column 0, cop2/blur at 8,
    # cop2/emboss at 4 — the base is a per-scope fact, not a per-context one.
    base: dict = {}
    for it in p.items:
        k = (it.section, it.heading)
        base[k] = min(base.get(k, it.indent), it.indent)
    for it in p.items:
        it.depth = 0 if it.indent <= base[(it.section, it.heading)] else 1

    return p


# ---------------------------------------------------------------- archive

class Archive:
    """nodes.zip plus the whole shipped help tree behind it.

    Two readers, on purpose:
      * `raw(name)`   — the page exactly as shipped
      * `resolved(name)` — the same page with :include/:includeprop/:import
                           expanded across EVERY help zip and the loose dirs.

    Resolution is not optional. `lop/distantlight` documents 0 parameters raw
    and its entire @parameters section is include lines; an extractor that
    skips resolution reports fully-documented nodes as ungrounded, and the
    pages it loses concentrate in lop/ — the context that matters for Solaris.
    """

    def __init__(self) -> None:
        self.zip = zipfile.ZipFile(NODES_ZIP)
        self.corpus = helpdoc.HelpCorpus()
        self._raw: dict[str, tuple[str, bool]] = {}

    def page_names(self, context: str | None = None) -> list[str]:
        out = [n for n in self.zip.namelist() if n.endswith(".txt") and "/" in n]
        if context is not None:
            out = [n for n in out if n.split("/", 1)[0] == context]
        return sorted(out)

    def raw_text(self, name: str) -> tuple[str, bool]:
        if name not in self._raw:
            b = self.zip.read(name)
            self._raw[name] = (b.decode("utf-8-sig"), b[:3] == b"\xef\xbb\xbf")
        return self._raw[name]

    def raw(self, name: str) -> Page:
        text, bom = self.raw_text(name)
        return parse_page(name, text, had_bom=bom)

    def resolved(self, name: str) -> tuple[Page, dict]:
        text, bom = self.raw_text(name)
        key = "nodes/" + name[:-4]
        stats: dict = {}
        expanded = helpdoc.resolve_includes(
            text.replace("\r\n", "\n").replace("\r", "\n"),
            self.corpus, key.rsplit("/", 1)[0], stats=stats, self_key=key)
        return parse_page(name, expanded, had_bom=bom), stats

    def is_node_page(self, name: str) -> bool:
        text, _ = self.raw_text(name)
        return helpdoc.is_node_page("nodes/" + name[:-4], text)

    def type_candidates(self, page: Page) -> list[str]:
        return helpdoc.canonical_type_names("nodes/" + page.name[:-4], page.directives)

    def include_targets_recursive(self, name: str, depth: int = 0,
                                  seen: frozenset = frozenset()) -> set:
        """Every include target reachable from a page, transitively.

        Needed for the deprecation axis: the '_old_cops_deprecated' banner can
        arrive through a NESTED include, and checking only the page's own
        include lines would miss it.
        """
        if depth >= 6:
            return set()
        key = "nodes/" + name[:-4]
        text, _ = self.raw_text(name)
        out: set = set()
        frontier = [(text, key.rsplit("/", 1)[0], key)]
        while frontier:
            body, base_dir, self_key = frontier.pop()
            # Per LINE, not finditer: RE_INCLUDE anchors on ^...$ and is not
            # compiled MULTILINE, so scanning the whole body matches nothing —
            # and it matches nothing SILENTLY. Caught by the blur.doc_deprecated
            # control, which is the entire reason that control exists.
            for line in body.replace("\r\n", "\n").split("\n"):
                m = RE_INCLUDE.match(line)
                if not m:
                    continue
                target = m.group("target").strip().strip("\"'")
                out.add(target)
                page_ref, _, _anchor = target.partition("#")
                k = self_key if not page_ref.strip() else \
                    self.corpus.resolve_path(page_ref, base_dir)
                if k and k not in seen and len(seen) < 64:
                    seen = seen | {k}
                    frontier.append((self.corpus.pages[k], k.rsplit("/", 1)[0], k))
        return out


# ---------------------------------------------------------------- deprecation

RE_WARN_DEPRECATED = re.compile(r"^\s*:warning:\s*deprecated", re.IGNORECASE)


def doc_deprecation(page: Page, raw_text: str, include_targets: set) -> dict:
    """The DOC side of the deprecation axis, tiered on purpose (H7-F12).

    STRONG is the only signal that counts as 'the page states a deprecation'.
    WEAK is reported BESIDE it and never merged: `lop/reference.txt` says
    '($IIDX is deprecated)' about an expression variable, not the node — and
    SYNAPSE emits that type 78 times. Counting WEAK would flag it.
    """
    strong: list[str] = []
    if page.directives.get("status", "").strip().lower() == "deprecated":
        strong.append("#status: deprecated")
    if any(DEPRECATED_BANNER in t for t in include_targets):
        strong.append(":include /composite/_old_cops_deprecated:")
    for line in raw_text.replace("\r\n", "\n").split("\n"):
        if RE_WARN_DEPRECATED.match(line):
            strong.append(":warning:Deprecated")
            break
    low = raw_text.lower()
    weak = ("deprecat" in low) or ("obsolete" in low)
    return {
        "strong": sorted(set(strong)),
        "is_deprecated_doc": bool(strong),
        "weak_mention": bool(weak),
    }
