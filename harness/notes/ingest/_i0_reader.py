"""I0 — the archive reader for $HFS/houdini/help/nodes.zip (Houdini 22.0.368).

READ-ONLY. This module PARSES; it decides nothing. Every producer script in this
leg imports from here so that all I0 numbers come off one instrument.

R60: the reader is calibrated before it is trusted. `_i0_calibrate.py` drives the
positive controls (hand-read pages the parser must reproduce) and the negative
controls (mutated pages the parser must FAIL on). A reader with zero controls
produces green numbers and zero information.

Law 1: every check must be able to fail. The parse functions here return counts
that a mutation can drive to zero; the calibration harness proves that it does.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field

# ---------------------------------------------------------------- archive

NODES_ZIP = (
    r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
    r"\houdini\help\nodes.zip"
)
NEWS_ZIP = (
    r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
    r"\houdini\help\news.zip"
)
BUILD = "22.0.368"


def open_archive(path: str = NODES_ZIP) -> zipfile.ZipFile:
    return zipfile.ZipFile(path)


def page_names(z: zipfile.ZipFile, context: str | None = None) -> list[str]:
    """Every .txt page, optionally filtered to one context directory."""
    out = [n for n in z.namelist() if n.endswith(".txt") and "/" in n]
    if context is not None:
        out = [n for n in out if n.split("/", 1)[0] == context]
    return sorted(out)


def read_page(z: zipfile.ZipFile, name: str) -> str:
    """Measured: 5033/5033 pages decode as strict UTF-8 — but 58 of them carry a
    BOM. Decoding those as plain 'utf-8' SUCCEEDS and leaves U+FEFF at offset 0,
    so the first line reads '\\ufeff#type: node' and the page's opening directive
    is silently lost. 'utf-8-sig' is therefore required, not optional, and no
    encoding error is ever raised to tell you otherwise. (Same defect H9 records
    on cop2/emboss.txt at helpdoc.py:118.)"""
    return z.read(name).decode("utf-8-sig")


# ---------------------------------------------------------------- grammar

# A page directive: "#context: cop". Indented forms occur inside @parameters
# where they bind to the enclosing item instead of to the page.
RE_DIRECTIVE = re.compile(r"^(?P<ind>[ \t]*)#(?P<key>[A-Za-z_][\w]*)\s*:[ \t]*(?P<val>.*?)[ \t]*$")

# "= Chroma Key =" — the page title.
RE_TITLE = re.compile(r"^=\s+(?P<title>.+?)\s+=\s*$")

# "== Key ==", "=== Rolloff ===", "~~~ Render Settings Prim ~~~"
RE_HEADING_EQ = re.compile(r"^(?P<ind>[ \t]*)(?P<lvl>={2,})\s+(?P<text>.+?)\s+(?P=lvl)\s*$")
RE_HEADING_TILDE = re.compile(r"^(?P<ind>[ \t]*)(?P<lvl>~{2,})\s+(?P<text>.+?)\s+(?P=lvl)\s*$")

# "@parameters", "@related", "@top_attributes"
RE_AT_SECTION = re.compile(r"^@(?P<name>[A-Za-z_][\w]*)(?:\s+(?P<arg>.*?))?\s*$")

# THREE include verbs, not one (measured: :include 9986, :includeprop 307, :import 1).
# A reader that follows only ':include' drops 308 transclusions, and ':import' is the
# one that pulls a WHOLE @parameters section (lop/usd_rop.txt <- out/usd#parameters).
RE_INCLUDE = re.compile(
    r"^(?P<ind>[ \t]*):(?P<verb>include|includeprop|import)\s+(?P<target>.+?):\s*$")

# Any other leading-colon block directive: ":vimeo: Transform SOP", ":task: ...",
# ":fig: ...", ":warning:Deprecated:", ":note:", ":col:", ":box:" and 20 more shapes.
# These matter for a reason beyond inventory: ':vimeo:' is followed by an indented
# "#id: 406959576" (a VIDEO id). Binding that to the preceding parameter overwrites a
# real internal name with a Vimeo number — measured live on sop/xform.txt, where
# "Combine" would be re-keyed from 'combine' to '406959576'. So a colon-directive
# CLOSES the current item scope.
RE_COLON_DIRECTIVE = re.compile(r"^(?P<ind>[ \t]*):(?P<name>[A-Za-z_][\w.-]*):(?P<arg>.*)$")

# A documented item label: "Threshold:" / "::`hip`:" / "Units:"
# Excludes directive lines (leading '#') and include lines (leading ':include').
RE_ITEM = re.compile(
    r"^(?P<ind>[ \t]*)"
    r"(?P<marker>::)?"
    r"(?P<label>(?!#)(?!:include\b)[^\s:][^:]*?)"
    r":[ \t]*$"
)

# """summary""" — may span lines.
RE_SUMMARY_OPEN = re.compile(r'^\s*"""')


@dataclass
class Item:
    """One documented parameter/attribute record."""

    label: str
    ident: str | None = None          # from "#id:"
    channels: str | None = None       # from "#channels:" — the OTHER internal-name key
    contentfrom: str | None = None    # description lives on another page
    indent: int = 0
    depth: int = 0                    # 0 = top-level param, >0 = nested menu entry
    heading: str | None = None        # enclosing "== Section =="
    section: str = "parameters"       # the @section it lives in
    line: int = 0
    desc_lines: int = 0
    directives: dict = field(default_factory=dict)
    marker: bool = False              # had the "::" list marker


def line_ending(text: str) -> str:
    """MEASURED, not assumed: 138/5033 pages are CRLF or mixed, and in cop/ it is
    67/375. A parser that splits on '\\n' and anchors items on '$' finds ZERO
    parameters on those pages and raises nothing — the exact 'looks complete,
    joins to nothing' failure this leg exists to prevent. Recorded per page."""
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


@dataclass
class Page:
    name: str
    context: str
    stem: str
    raw_lines: int
    eol: str = "LF"
    title: str | None = None
    title_line: int | None = None
    summary: str | None = None
    directives: dict = field(default_factory=dict)
    directive_order: list = field(default_factory=list)
    first_directive_line: int | None = None
    at_sections: list = field(default_factory=list)
    includes: list = field(default_factory=list)   # (line, target, section, verb)
    colon_directives: list = field(default_factory=list)  # (line, name, arg)
    items: list = field(default_factory=list)      # list[Item]
    headings: list = field(default_factory=list)
    body_chars: int = 0                            # prose outside @sections
    total_chars: int = 0
    related: list = field(default_factory=list)

    # --- convenience views used by the producers -------------------------
    @property
    def params(self) -> list:
        """Top-level documented parameters (depth 0), parameter-ish sections only."""
        return [i for i in self.items if i.depth == 0 and i.section in _PARAM_SECTIONS]

    @property
    def params_with_id(self) -> list:
        return [i for i in self.params if i.ident]

    @property
    def params_with_internal_name(self) -> list:
        """#id OR #channels. H9's ACTIONABLE rung counted both; a reader that
        follows only #id under-reports cop2 by ~5x (248 #channels vs 51 #id)."""
        return [i for i in self.params if i.ident or i.channels]

    @property
    def header_order(self) -> str:
        """'directives-first' | 'title-first' | 'title-only' | 'directives-only' | 'neither'"""
        if self.title_line is None and self.first_directive_line is None:
            return "neither"
        if self.title_line is None:
            return "directives-only"
        if self.first_directive_line is None:
            return "title-only"
        return "directives-first" if self.first_directive_line < self.title_line else "title-first"


_PARAM_SECTIONS = {"parameters", "top_attributes", "properties"}


def _strip_markup(s: str) -> str:
    return s.strip()


def parse_page(name: str, text: str) -> Page:
    """Parse one help page. Pure function of its input — no archive access."""
    eol = line_ending(text)
    # Normalise AFTER recording, never before: the archive's real shape is a
    # finding, and silently absorbing it is how the defect stays invisible.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    ctx, _, stem = name.partition("/")
    p = Page(
        name=name,
        context=ctx,
        stem=stem[:-4] if stem.endswith(".txt") else stem,
        raw_lines=len(lines),
        eol=eol,
        total_chars=len(text),
    )

    cur_section = None           # None = preamble (before any @section)
    cur_heading = None
    # indent of top-level items, resolved per (section, heading) scope
    scope_base_indent: dict = {}
    pending_item: Item | None = None
    in_summary = False
    summary_buf: list = []
    body_buf: list = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # ---- multi-line summary """...""" -------------------------------
        if in_summary:
            if '"""' in line:
                summary_buf.append(line[: line.index('"""')])
                p.summary = "\n".join(summary_buf).strip()
                in_summary = False
            else:
                summary_buf.append(line)
            continue
        if p.summary is None and RE_SUMMARY_OPEN.match(line):
            after = line[line.index('"""') + 3 :]
            if '"""' in after:
                p.summary = after[: after.index('"""')].strip()
            else:
                in_summary = True
                summary_buf = [after]
            continue

        # ---- @section markers -------------------------------------------
        m = RE_AT_SECTION.match(line)
        if m and not line.startswith("@@"):
            cur_section = m.group("name")
            p.at_sections.append((idx, cur_section))
            cur_heading = None
            pending_item = None
            scope_base_indent.clear()
            continue

        # ---- :include / :includeprop / :import ----------------------------
        m = RE_INCLUDE.match(line)
        if m:
            p.includes.append((idx, m.group("target").strip(),
                               cur_section or "<preamble>", m.group("verb")))
            pending_item = None
            continue

        # ---- any other block directive (:vimeo:, :task:, :warning: ...) ----
        m = RE_COLON_DIRECTIVE.match(line)
        if m:
            p.colon_directives.append((idx, m.group("name"), m.group("arg").strip()))
            # CLOSES the item scope — otherwise ':vimeo:' + '#id: 406959576'
            # re-keys the preceding real parameter to a video id.
            pending_item = None
            continue

        # ---- directives ---------------------------------------------------
        m = RE_DIRECTIVE.match(line)
        if m:
            key, val = m.group("key"), m.group("val")
            ind = len(m.group("ind").expandtabs(4))
            if pending_item is not None and ind > pending_item.indent:
                # binds to the enclosing documented item, not to the page.
                # FIRST WINS: a later directive of the same key never overwrites
                # an established internal name.
                if key not in pending_item.directives:
                    pending_item.directives[key] = val
                    if key == "id" and pending_item.ident is None:
                        pending_item.ident = val.strip() or None
                    elif key == "channels" and pending_item.channels is None:
                        pending_item.channels = val.strip() or None
                    elif key == "contentfrom":
                        pending_item.contentfrom = val.strip() or None
                continue
            if cur_section is None:
                if key not in p.directives:
                    p.directives[key] = val
                    p.directive_order.append(key)
                if p.first_directive_line is None:
                    p.first_directive_line = idx
            continue

        # ---- title / headings ----------------------------------------------
        m = RE_TITLE.match(line)
        if m and cur_section is None and p.title is None:
            p.title = m.group("title").strip()
            p.title_line = idx
            continue

        m = RE_HEADING_EQ.match(line) or RE_HEADING_TILDE.match(line)
        if m:
            cur_heading = m.group("text").strip()
            p.headings.append((idx, cur_heading, cur_section or "<preamble>"))
            pending_item = None
            # a new heading opens a new item scope
            scope_base_indent.pop((cur_section, cur_heading), None)
            continue

        # ---- @related list entries -------------------------------------------
        if cur_section == "related" and stripped.startswith("-"):
            p.related.append(stripped.lstrip("- ").strip())
            continue

        # ---- documented items ------------------------------------------------
        if cur_section in _PARAM_SECTIONS:
            m = RE_ITEM.match(line)
            if m:
                ind = len(m.group("ind").expandtabs(4))
                label = _strip_markup(m.group("label"))
                if label:
                    scope = (cur_section, cur_heading)
                    base = scope_base_indent.get(scope)
                    if base is None or ind < base:
                        scope_base_indent[scope] = ind
                        base = ind
                    it = Item(
                        label=label,
                        indent=ind,
                        depth=0 if ind <= base else 1,
                        heading=cur_heading,
                        section=cur_section,
                        line=idx,
                        marker=bool(m.group("marker")),
                    )
                    p.items.append(it)
                    pending_item = it
                    continue
            if pending_item is not None and stripped:
                pending_item.desc_lines += 1
            continue

        # ---- prose ------------------------------------------------------------
        if cur_section is None and stripped:
            body_buf.append(stripped)

    p.body_chars = len("\n".join(body_buf))

    # A depth pass fix-up: an item whose indent exceeds its scope base was marked
    # depth 1 above, but scope base may have been lowered afterwards by a
    # shallower sibling. Re-resolve against the FINAL base for each scope.
    final_base: dict = {}
    for it in p.items:
        k = (it.section, it.heading)
        final_base[k] = min(final_base.get(k, it.indent), it.indent)
    for it in p.items:
        it.depth = 0 if it.indent <= final_base[(it.section, it.heading)] else 1

    return p


def load(z: zipfile.ZipFile, name: str) -> Page:
    return parse_page(name, read_page(z, name))
