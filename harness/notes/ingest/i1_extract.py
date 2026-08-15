"""I1 -- the extractor for ``$HFS/houdini/help/nodes.zip`` (the pinned Houdini build).

WHAT THIS IS
------------
The reader I1 builds its grounding corpus with. It is written against
**measured** structure, not assumed structure: every design decision below cites
the I0 scout finding that forced it (``harness/notes/ingest/I0_SCOUT.md`` in the
I0 leg, summarised in that leg's receipt ``harness/notes/receipts/I0.json``).

The nine things I0 said to build against, and where each lives here:

  1. key on LABEL, normalised; ``#id``/``#channels`` are EVIDENCE  -> `Param`, `norm_label`
  2. try ``#id`` against parmTuples() before parms()                -> i1_runtime.py (join order)
  3. resolve ``:include`` + ``:includeprop`` + ``:import`` over ALL
     help zips plus the loose dirs; MARK unresolved, never drop     -> `resolve_all`
  4. decode utf-8-SIG; normalise line endings before parsing        -> `load_page`, `parse_page`
  5. a ``:xxx:`` block directive CLOSES the item scope              -> `parse_page`, RE_COLON
  6. per-context structure is derived PER PAGE, not switched on the
     context name (header order and item indent are both measured)  -> `parse_page`
  7. deprecation is a TWO-SOURCE UNION, recorded per side           -> `doc_deprecation`
  8. record the floor rung per entry; a stub is `known-thin`        -> `rung`
  9. nothing wires into RAG                                         -> nothing here imports
     synapse.*, and the corpus is written under harness/notes/.

TRUTH TIER
----------
Everything this module produces is **VERIFIED-DOC** at the pinned build: read from
the shipped reference of that build. It is NOT VERIFIED-RUNTIME.
Documentation says what a node is FOR; only a probe says what it DOES. Per-entry
provenance, never per-corpus (R119) -- and never summed with probe-derived
grounding into one number.

CALIBRATION
-----------
R60: this reader is not trusted until ``i1_calibrate.py`` shows it returning
KNOWN answers on pages that were read by hand. Every count it produces is one a
mutation can drive to zero, and the calibration proves that it does (Law 1).

PRODUCER: this file. Consumers: i1_calibrate.py, i1_build.py, i1_crosscheck.py.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# The include resolver, the cross-zip corpus loader and the anchored-block
# machinery are REUSED rather than re-derived: they are committed
# (harness/notes/h9/helpdoc.py), they already carry the utf-8-sig fix and the
# loose-directory load, and I0 used them as its second instrument. Re-writing
# them would have produced a third parser and no new evidence.
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "harness" / "notes" / "h9"))
import helpdoc  # noqa: E402  (committed at harness/notes/h9/helpdoc.py)

# These mirror helpdoc's DEFAULT surface (the current pin), for the zero-arg
# callers that want it. helpdoc.resolve_build is the single place the default
# pin lives -- nothing here restates it. Callers that want another build pass
# build=/help_dir= to load_corpus() and never mutate these module attributes.
BUILD = helpdoc.BUILD                     # default pin, resolved by helpdoc; overridable
HELP_DIR = helpdoc.HELP_DIR
NEWS_ZIP = HELP_DIR / "news.zip"

# The contexts this leg ingests. cop == Copernicus (live category `Cop`, 384
# types), cop2 == the legacy compositing network (live category `Cop2`, 169),
# lop == Solaris (218). cop2 is present because the leg must report against all
# three live catalogue totals, and because 138 of the 144 doc-says/runtime-does-
# not deprecations live there (I0-F10) -- omitting it would drop the entire
# announced-for-removal subsystem out of the deprecation axis.
CONTEXTS = ("cop", "lop", "cop2")

_MAX_INCLUDE_DEPTH = 8

# ---------------------------------------------------------------- grammar
#
# Shapes below were measured over the full 5,032-page census by I0 and
# re-confirmed here by hand on cop/chromakey, cop2/emboss, lop/distantlight and
# cop/adjacency_distort before any of them was trusted.

# "#context: cop" at page level; the same shape INDENTED binds to the enclosing
# documented item instead ("    #id: signature").
RE_DIRECTIVE = re.compile(
    r"^(?P<ind>[ \t]*)#(?P<key>[A-Za-z_]\w*)[ \t]*:[ \t]*(?P<val>.*?)[ \t]*$")

# "= Chroma Key ="
RE_TITLE = re.compile(r"^=\s+(?P<title>.+?)\s+=\s*$")

# "== Key ==" / "=== Rolloff ===" / "~~~ Pivot Transform ~~~"
RE_HEADING = re.compile(
    r"^(?P<ind>[ \t]*)(?P<lvl>={2,}|~{2,})\s+(?P<text>.+?)\s+(?P=lvl)\s*$")

# "@parameters", "@related", "@top_attributes"
RE_AT_SECTION = re.compile(r"^@(?P<name>[A-Za-z_]\w*)(?:\s+(?P<arg>.*?))?\s*$")

# THREE include verbs ship, not one (I0-F8: :include 9,986 / :includeprop 307 /
# :import 1). A reader matching only ':include' drops 308 transclusions, and
# ':import' is the one that pulls a whole @parameters section across contexts.
RE_INCLUDE = re.compile(
    r"^(?P<ind>[ \t]*):(?P<verb>include|includeprop|import)\s+(?P<target>.+?):\s*$")

# Any OTHER leading-colon block directive: ":vimeo: Transform SOP", ":task:",
# ":fig:", ":warning:Deprecated:", ":col:", ":box:" and 24 more shapes.
# This matters beyond inventory: ':vimeo:' is followed by an indented
# "#id: 406959576" -- a VIDEO id. Binding that to the preceding parameter
# re-keys a real internal name to a Vimeo number (I0's defect D3, measured live
# on sop/xform "Combine"). So a colon directive CLOSES the current item scope.
RE_COLON = re.compile(r"^(?P<ind>[ \t]*):(?P<name>[A-Za-z_][\w.-]*):(?P<arg>.*)$")

# A documented item label: "Threshold:" / "::`hip`:" / "Light Position:"
RE_ITEM = re.compile(
    r"^(?P<ind>[ \t]*)"
    r"(?P<marker>::)?"
    r"(?P<label>(?!#)(?!:)[^\s:][^:]*?)"
    r":[ \t]*$")

RE_SUMMARY_OPEN = re.compile(r'^\s*"""')
RE_MARKER = re.compile(r"^\s*<!--\s*(UNRESOLVED-INCLUDE|UNRESOLVED-ANCHOR|CYCLIC-INCLUDE)\s")

# Sections whose items are PARAMETERS. `top_attributes` and `properties` are the
# other two shapes a documented driveable field ships under (I0 Q1: 1,761 pages
# have no @parameters at all and document through other sections).
PARAM_SECTIONS = ("parameters", "top_attributes", "properties")

# --- deprecation, doc side. STRONG only. -------------------------------------
# I0-F10 / H7-F12: the WEAK signal (the word "deprecat" anywhere) flags
# lop/reference, whose page says "($IIDX is deprecated)" about an EXPRESSION
# VARIABLE, not the node -- a type SYNAPSE emits 78 times. WEAK is recorded
# beside STRONG and NEVER merged into it.
DEPRECATED_BANNER = "/composite/_old_cops_deprecated"
RE_WEAK_DEPRECATION = re.compile(r"deprecat|obsolete", re.I)


# ---------------------------------------------------------------- helpers
def norm_label(s: str) -> str:
    """The join key (I0-F3 / R97), normalised.

    Label is present on 100% of documented parameter records and resolves
    88.7-89.1% of them against the live runtime; ``#id`` is present on 62-85%
    and resolves 43.4-52.9%. So label is the key and ``#id`` is evidence.

    Normalisation is deliberately conservative -- collapse whitespace, casefold,
    fold the typographic apostrophe (U+2019) onto ASCII, and strip the trailing
    ellipsis Houdini puts on button labels ("Reload Files..."). Anything more
    aggressive starts inventing matches.
    """
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("…", "...")
    s = re.sub(r"\.\.\.$", "", s.strip())
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def _indent(line: str) -> int:
    return len(line) - len(line.expandtabs(4).lstrip(" ")) if "\t" in line \
        else len(line) - len(line.lstrip(" "))


def line_ending(text: str) -> str:
    """Recorded BEFORE normalisation, never absorbed silently.

    138 of 5,033 pages are CRLF or mixed and 67 of 375 ``cop/`` pages are CRLF
    (I0's defect D1). A parser that splits on '\\n' and anchors items on '$'
    finds ZERO parameters on those pages and raises nothing. cop/chromakey --
    one of the 161 new Copernicus nodes -- is one of them.
    """
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


def clean(s: str) -> str:
    """Strip help markup, keep the words. Grounding is prose, not wiki source."""
    return helpdoc.clean_markup(s)


# ---------------------------------------------------------------- includes
def _at_section_block(text: str, name: str) -> str | None:
    """The body of an ``@<name>`` section.

    Needed for ``:import``, the third include verb: lop/usd_rop.txt carries
    ``:import /nodes/out/usd#parameters:`` and the anchor names an @section, not
    an ``#id`` or a ``== .. == (anchor)``. helpdoc's ``_anchored_block`` knows
    the four id/section/tag forms and not this one, so it is added here rather
    than patched into a committed module another leg depends on.
    """
    out: list[str] = []
    hit = False
    for line in text.splitlines():
        m = RE_AT_SECTION.match(line)
        if m:
            if hit:
                break
            hit = m.group("name").lower() == name.lower()
            continue
        if hit:
            out.append(line)
    return "\n".join(out) if hit else None


def _anchored(body: str, anchor: str) -> tuple:
    """(block, came_from_an_@section). The second half is not cosmetic.

    ``lop/usd_rop.txt`` is the archive's single ``:import``, and it reads
    ``:import /nodes/out/usd#parameters:`` into a page that has NO
    ``@parameters`` marker of its own. Splicing the bare body in leaves every
    imported parameter sitting in the preamble, where a parameter parser
    correctly ignores it -- the page reports ZERO parameters while carrying 60.
    So when the anchor names an @section, the section header travels with the
    section. That is what the directive means.
    """
    blk = helpdoc._anchored_block(body, anchor)
    if blk is not None:
        return blk, False
    blk = _at_section_block(body, anchor)
    return (blk, True) if blk is not None else (None, False)


def resolve_all(text: str, corpus: helpdoc.HelpCorpus, base_dir: str,
                depth: int = 0, seen: frozenset = frozenset(),
                stats: dict | None = None, self_key: str | None = None) -> str:
    """Expand every include, in all three shipped verbs, recursively.

    Unresolvable targets become a MARKER, never a deletion. A silently-dropped
    include is an undercount that looks like a clean parse -- and 385 of the
    shipped archive's include anchors are genuinely broken (I0-F9), so this path
    is exercised on real pages, not hypothetically.
    """
    if depth >= _MAX_INCLUDE_DEPTH:
        return text
    out: list[str] = []
    for line in text.splitlines():
        m = RE_INCLUDE.match(line)
        if not m:
            out.append(line)
            continue
        pad, verb, target = m.group("ind"), m.group("verb"), m.group("target").strip()
        # Targets whose anchor contains colons ship quoted.
        if len(target) > 1 and target[0] == target[-1] and target[0] in "\"'":
            target = target[1:-1].strip()
        if stats is not None:
            stats["seen"] = stats.get("seen", 0) + 1
            stats.setdefault("verbs", {})
            stats["verbs"][verb] = stats["verbs"].get(verb, 0) + 1
        page_ref, _, anchor = target.partition("#")
        # Colons inside an anchor are backslash-escaped in the shipped source;
        # a trailing '/' is shipped on lop's sampling blocks.
        anchor = anchor.strip("/").strip().replace("\\:", ":")
        key = self_key if not page_ref.strip() else corpus.resolve_path(page_ref, base_dir)
        if key is None:
            if stats is not None:
                stats["unresolved_page"] = stats.get("unresolved_page", 0) + 1
                stats.setdefault("unresolved_targets", []).append(target)
            out.append("%s<!-- UNRESOLVED-INCLUDE %s -->" % (pad, target))
            continue
        if key in seen:
            out.append("%s<!-- CYCLIC-INCLUDE %s -->" % (pad, target))
            continue
        body = corpus.pages[key].replace("\r\n", "\n").replace("\r", "\n")
        if anchor:
            blk, from_at_section = _anchored(body, anchor)
            if blk is None:
                if stats is not None:
                    stats["unresolved_anchor"] = stats.get("unresolved_anchor", 0) + 1
                    stats.setdefault("unresolved_targets", []).append(target)
                out.append("%s<!-- UNRESOLVED-ANCHOR %s -->" % (pad, target))
                continue
            if from_at_section and anchor.lower() in PARAM_SECTIONS:
                blk = "@%s\n%s" % (anchor.lower(), blk)
            body = blk
        else:
            body = helpdoc._strip_page_furniture(body)
        if stats is not None:
            stats["resolved"] = stats.get("resolved", 0) + 1
        body = resolve_all(body, corpus, key.rsplit("/", 1)[0],
                           depth + 1, seen | {key}, stats, self_key=key)
        out.extend(pad + l if l.strip() else l for l in body.splitlines())
    return "\n".join(out)


def contentfrom_text(target: str, corpus: helpdoc.HelpCorpus, base_dir: str) -> str | None:
    """Follow a ``#contentfrom:`` to the prose it points at.

    1,199 records carry it (I0-F4). cop/adjacency_distort documents its
    ``Signature`` parameter with a label, an ``#id`` and NO inline prose at all
    -- the description lives on cop/distort. helpdoc does not follow this axis
    (I0 section 8 names it as an open gap), so a floor that requires "has a
    description" would score those entries thin when the documentation is
    actually complete. Following it is the deliberate decision I0-F4 asks for.
    """
    page_ref, _, anchor = target.strip().partition("#")
    anchor = anchor.strip("/").strip().replace("\\:", ":")
    key = corpus.resolve_path(page_ref, base_dir) if page_ref.strip() else None
    if key is None:
        return None
    body = corpus.pages[key].replace("\r\n", "\n").replace("\r", "\n")
    blk = _anchored(body, anchor)[0] if anchor else helpdoc._strip_page_furniture(body)
    if blk is None:
        return None
    blk = resolve_all(blk, corpus, key.rsplit("/", 1)[0], depth=1, seen={key})
    keep: list[str] = []
    for i, line in enumerate(blk.splitlines()):
        if RE_DIRECTIVE.match(line) or RE_MARKER.match(line):
            continue
        if i == 0 and RE_ITEM.match(line):      # the anchored block's own label
            continue
        keep.append(line)
    return clean(" ".join("\n".join(keep).split())) or None


# ---------------------------------------------------------------- records
@dataclass
class Param:
    """One documented parameter record. LABEL is the key; ids are evidence."""

    label: str
    label_norm: str = ""
    ids: list = field(default_factory=list)        # from "#id:"  (evidence)
    channels: list = field(default_factory=list)   # from "#channels:" (evidence)
    contentfrom: str | None = None
    description: str = ""
    own_description: str = ""                      # before menu values were folded in
    description_source: str = "none"               # inline | contentfrom:<t> | none
    heading: str | None = None
    section: str = "parameters"
    indent: int = 0
    depth: int = 0
    line: int = 0
    parent: int = -1        # index into Page.items, -1 = top level

    @property
    def internal_names(self) -> list:
        return list(self.ids) + list(self.channels)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "label_norm": self.label_norm,
            "ids": self.ids,
            "channels": self.channels,
            "description": self.description,
            "description_source": self.description_source,
            "heading": self.heading,
            "section": self.section,
        }


@dataclass
class Page:
    help_key: str
    context: str
    stem: str
    source: str
    eol: str = "LF"
    bom: bool = False
    title: str | None = None
    title_line: int | None = None
    first_directive_line: int | None = None
    summary: str | None = None
    overview: str = ""
    directives: dict = field(default_factory=dict)
    at_sections: list = field(default_factory=list)
    colon_directives: list = field(default_factory=list)
    raw_includes: list = field(default_factory=list)   # (line, verb, target)
    items: list = field(default_factory=list)          # list[Param]
    headings: list = field(default_factory=list)
    related: list = field(default_factory=list)
    include_stats: dict = field(default_factory=dict)
    raw_chars: int = 0
    resolved_chars: int = 0

    @property
    def params(self) -> list:
        """Top-level documented parameters. Nested entries are MENU VALUES --
        they document the parameter, they are not separate parameters."""
        return [i for i in self.items if i.depth == 0 and i.section in PARAM_SECTIONS]

    @property
    def header_order(self) -> str:
        if self.title_line is None and self.first_directive_line is None:
            return "neither"
        if self.title_line is None:
            return "directives-only"
        if self.first_directive_line is None:
            return "title-only"
        return "directives-first" if self.first_directive_line < self.title_line \
            else "title-first"


# ---------------------------------------------------------------- parsing
def parse_text(help_key: str, raw: str, resolved: str, source: str = "") -> Page:
    """Parse one help page. Pure function of its input -- no archive access.

    Structure is derived PER PAGE rather than switched on the context name:
    header order is measured (cop/ is 98% directives-first, lop/ is 79%
    title-first) and the item base indent is resolved per (section, heading)
    scope (cop/ puts parameters at column 0, cop2/ at indent 4 or deeper).
    Switching on the context name would be right today and wrong on the next
    build; measuring per page is right on both.
    """
    ctx, _, stem = help_key[len("nodes/"):].partition("/") if help_key.startswith("nodes/") \
        else ("", "", help_key)
    p = Page(help_key=help_key, context=ctx, stem=stem, source=source,
             eol=line_ending(raw), bom=raw.startswith("﻿"),
             raw_chars=len(raw), resolved_chars=len(resolved))

    # Record the shape, THEN normalise. Absorbing CRLF before measuring it is
    # how the defect stays invisible.
    text = resolved.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    cur_section: str | None = None
    cur_heading: str | None = None
    scope_base: dict = {}
    stack: list = []            # (indent, index) -- open item ancestry
    pending: Param | None = None
    in_summary = False
    summary_buf: list = []
    body_buf: list = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # ---- """summary""" (may span lines) ------------------------------
        if in_summary:
            if '"""' in line:
                summary_buf.append(line[: line.index('"""')])
                p.summary = clean(" ".join("\n".join(summary_buf).split())) or None
                in_summary = False
            else:
                summary_buf.append(line)
            continue
        if p.summary is None and RE_SUMMARY_OPEN.match(line):
            after = line[line.index('"""') + 3:]
            if '"""' in after:
                p.summary = clean(after[: after.index('"""')].strip()) or None
            else:
                in_summary = True
                summary_buf = [after]
            continue

        # ---- @section ------------------------------------------------------
        m = RE_AT_SECTION.match(line)
        if m and not line.startswith("@@"):
            cur_section = m.group("name").lower()
            p.at_sections.append(cur_section)
            cur_heading = None
            pending = None
            scope_base.clear()
            stack.clear()
            continue

        # ---- an include that survived resolution (a marker) -----------------
        if RE_MARKER.match(line):
            pending = None
            continue

        # ---- any colon block directive: CLOSES the item scope ---------------
        m = RE_COLON.match(line)
        if m and not RE_INCLUDE.match(line):
            p.colon_directives.append((idx, m.group("name"), m.group("arg").strip()))
            pending = None
            continue
        if RE_INCLUDE.match(line):          # only reachable on unresolved input
            pending = None
            continue

        # ---- directives -----------------------------------------------------
        m = RE_DIRECTIVE.match(line)
        if m:
            key, val = m.group("key").lower(), m.group("val")
            ind = _indent(line)
            if pending is not None and ind > pending.indent:
                # Binds to the enclosing documented item. FIRST WINS: a later
                # directive of the same key never overwrites an established
                # internal name.
                if key == "id":
                    for part in (q.strip() for q in val.split(",")):
                        if part and part not in pending.ids:
                            pending.ids.append(part)
                elif key == "channels":
                    for part in (q.strip().lstrip("/") for q in val.split()):
                        if part and part not in pending.channels:
                            pending.channels.append(part)
                elif key == "contentfrom" and pending.contentfrom is None:
                    pending.contentfrom = val.strip() or None
                continue
            if cur_section is None:
                if key not in p.directives:
                    p.directives[key] = val
                if p.first_directive_line is None:
                    p.first_directive_line = idx
            continue

        # ---- title / headings ------------------------------------------------
        m = RE_TITLE.match(line)
        if m and cur_section is None and p.title is None:
            p.title = clean(m.group("title").strip()) or None
            p.title_line = idx
            continue

        m = RE_HEADING.match(line)
        if m:
            cur_heading = clean(m.group("text").strip())
            p.headings.append(cur_heading)
            pending = None
            stack.clear()
            scope_base.pop((cur_section, cur_heading), None)
            continue

        # ---- @related --------------------------------------------------------
        if cur_section == "related" and stripped.startswith("-"):
            p.related.append(stripped.lstrip("- ").strip())
            continue

        # ---- documented items -------------------------------------------------
        if cur_section in PARAM_SECTIONS:
            m = RE_ITEM.match(line)
            if m:
                ind = _indent(line)
                label = clean(m.group("label").strip())
                if label:
                    scope = (cur_section, cur_heading)
                    base = scope_base.get(scope)
                    if base is None or ind < base:
                        scope_base[scope] = ind
                        base = ind
                    while stack and stack[-1][0] >= ind:
                        stack.pop()
                    it = Param(label=label, label_norm=norm_label(label), indent=ind,
                               depth=0 if ind <= base else 1, heading=cur_heading,
                               section=cur_section, line=idx,
                               parent=stack[-1][1] if stack else -1)
                    p.items.append(it)
                    stack.append((ind, len(p.items) - 1))
                    pending = it
                    continue
            if pending is not None:
                if stripped and _indent(line) <= pending.indent:
                    pending = None
                else:
                    body_line = stripped
                    if body_line:
                        pending.description = (pending.description + " " + body_line).strip() \
                            if pending.description else body_line
            continue

        # ---- prose ------------------------------------------------------------
        if cur_section is None and stripped:
            body_buf.append(stripped)

    # A late shallower sibling can lower a scope's base indent after earlier
    # items were classified against a deeper one. Re-resolve against the FINAL
    # base -- without this, a page whose first parameter is indented deeper than
    # its siblings loses every sibling to depth 1.
    final_base: dict = {}
    for it in p.items:
        k = (it.section, it.heading)
        final_base[k] = min(final_base.get(k, it.indent), it.indent)
    for it in p.items:
        it.depth = 0 if it.indent <= final_base[(it.section, it.heading)] else 1

    # Nested entries are MENU VALUES, and a menu value is the parameter's
    # documentation, not a parameter of its own. cop2/emboss's "Specular Model"
    # carries no prose at all -- its whole body is "Phong:" / "Blinn:" and their
    # descriptions. Left unfolded it scores as an undocumented parameter, which
    # is the "stub" verdict applied to a page that is in fact fully documented.
    # Folded in document order, into the top-level ancestor.
    for it in p.items:
        it.own_description = clean(" ".join(it.description.split()))
    for i, it in enumerate(p.items):
        if it.depth == 0:
            continue
        root = it.parent
        while root >= 0 and p.items[root].depth != 0:
            root = p.items[root].parent
        if root < 0:
            continue
        chunk = ("%s: %s" % (it.label, it.description)).strip().rstrip(":")
        p.items[root].description = (p.items[root].description + " " + chunk).strip()

    for it in p.items:
        it.description = clean(" ".join(it.description.split()))
        if it.description:
            it.description_source = "inline"

    p.overview = clean(" ".join(" ".join(body_buf).split()))
    return p


def parse_include_lines(raw: str) -> list:
    """(line, verb, target) for every include ON THE PAGE, before resolution.

    Kept separate from the resolved parse because the raw form is what carries
    the deprecation banner: ``:include /composite/_old_cops_deprecated:``.
    """
    out = []
    for i, line in enumerate(raw.replace("\r\n", "\n").split("\n"), start=1):
        m = RE_INCLUDE.match(line)
        if m:
            out.append((i, m.group("verb"), m.group("target").strip()))
    return out


def parse_page(help_key: str, corpus: helpdoc.HelpCorpus) -> Page:
    """Full structured record for one help page, includes resolved."""
    raw = corpus.pages[help_key]
    base_dir = help_key.rsplit("/", 1)[0]
    stats: dict = {}
    resolved = resolve_all(raw.replace("\r\n", "\n").replace("\r", "\n"),
                           corpus, base_dir, stats=stats, self_key=help_key)
    p = parse_text(help_key, raw, resolved, source=corpus.origin.get(help_key, help_key))
    p.include_stats = stats
    p.raw_includes = parse_include_lines(raw)

    # Follow #contentfrom for any parameter with no inline prose (I0-F4).
    for it in p.params:
        if it.description or not it.contentfrom:
            continue
        got = contentfrom_text(it.contentfrom, corpus, base_dir)
        if got:
            it.description = got
            it.description_source = "contentfrom:%s" % it.contentfrom
    return p


# ---------------------------------------------------------------- verdicts
def doc_deprecation(raw: str, directives: dict, includes: list,
                    colon_directives: list, build: str | None = None) -> dict:
    """The DOC side of the deprecation union. STRONG signals only.

    R72 / I0-F10: deprecation is the union of runtime ``deprecationInfo()`` and
    authored help, and the two disagree on 195 node types. This function is one
    half. It never returns the runtime's opinion and never merges with it.

    ``build`` labels the record with the build actually parsed (pass
    ``corpus.build``); omitted, it defaults to the module pin. A page parsed
    from a non-default corpus must not be stamped with the default build.
    """
    signals: list[str] = []
    status = (directives.get("status") or "").strip().lower()
    if "deprecat" in status:
        signals.append("#status: %s" % directives.get("status").strip())
    for _line, _verb, target in includes:
        if DEPRECATED_BANNER in target:
            signals.append(":include %s" % target)
            break
    for _line, name, arg in colon_directives:
        # ':warning:Deprecated:' -- and an uppercase ':WARNING:' variant ships,
        # which a case-sensitive matcher misses (I0-F8).
        if name.lower() == "warning" and "deprecat" in (arg or "").lower():
            signals.append(":warning:%s" % arg.strip())
            break
    return {
        "deprecated": bool(signals),
        "signals": signals,
        "weak_mention": bool(RE_WEAK_DEPRECATION.search(raw)),
        "tier": "VERIFIED-DOC",
        "build": build or BUILD,
    }


# The floor, taken VERBATIM from I0 so the two legs' numbers are comparable
# rather than merely similar.
#
#   I1-FLOOR = the page carries a \"\"\"summary\"\"\"
#              AND >= 1 documented parameter with a non-empty description
#
# Rungs are cumulative: a page with described parameters and no summary scores
# EXISTS, not FLOOR. That is I0's ladder and it is kept exactly, because the
# leg's headline number is a comparison against I0's.
RUNGS = ("EXISTS", "SUMMARY", "FLOOR", "ACTIONABLE")


def rung(page: Page) -> str:
    if not page.summary:
        return "EXISTS"
    params = page.params
    if not any(pm.description for pm in params):
        return "SUMMARY"
    if not any(pm.internal_names for pm in params):
        return "FLOOR"
    return "ACTIONABLE"


def clears_floor(r: str) -> bool:
    return r in ("FLOOR", "ACTIONABLE")


# ---------------------------------------------------------------- corpus IO
def load_corpus(build: str | None = None, help_dir=None) -> helpdoc.HelpCorpus:
    """All shipped help, every ``*.zip`` plus the loose directories.

    NOT nodes.zip alone. ``:include /composite/_old_cops_deprecated:`` appears on
    145 pages and its target lives in ``composite.zip`` -- a nodes.zip-only
    reader cannot resolve it and reproduces H5's defect exactly, reading an
    entire vendor-deprecated subsystem as current (I0-F9 / H7-F4).

    ``build`` (or ``help_dir``) selects the archive through helpdoc's
    parameterized surface; omitted, it defaults to the current pin. The caller
    chooses the build -- nothing here mutates helpdoc -- and an absent archive
    fails loudly (``HelpCorpus._load``), never falls back to another build.
    """
    return helpdoc.HelpCorpus(build=build, help_dir=help_dir)


def bom_keys(help_dir=None) -> set:
    """Help keys whose shipped bytes begin with a UTF-8 BOM.

    Recorded because the corpus loader decodes ``utf-8-sig``, which STRIPS the
    BOM -- so by the time any parser sees the text, the hazard is invisible.
    That is exactly why it is a silent-failure class: decoding plain ``utf-8``
    also SUCCEEDS, leaves U+FEFF at offset 0, and eats the page's first
    directive (I0's defect D2: 32 pages lose a directive, 26 lose their title;
    cop2/emboss loses ``#type: node`` and stops being a node page).

    ``help_dir`` (e.g. ``corpus.help_dir``) selects the build; omitted, it uses
    the default pin.
    """
    import zipfile
    hd = Path(help_dir) if help_dir is not None else HELP_DIR
    out = set()
    for zp in sorted(hd.glob("*.zip")):
        root = zp.stem
        try:
            zf = zipfile.ZipFile(zp)
        except zipfile.BadZipFile:
            continue
        with zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.endswith(".txt"):
                    continue
                with zf.open(info) as fh:
                    if fh.read(3) == b"\xef\xbb\xbf":
                        out.add("%s/%s" % (root, info.filename[:-4]))
    return out


def node_pages(corpus: helpdoc.HelpCorpus, context: str) -> list:
    """Help keys that are node pages in one context, sorted."""
    pref = "nodes/%s/" % context
    out = []
    for k in corpus.pages:
        if not k.startswith(pref) or "/" in k[len(pref):]:
            continue
        if helpdoc.is_node_page(k, corpus.pages[k]):
            out.append(k)
    return sorted(out)


def all_pages(corpus: helpdoc.HelpCorpus, context: str) -> list:
    """Every ``.txt`` under one context, node page or not -- the EXISTS census."""
    pref = "nodes/%s/" % context
    return sorted(k for k in corpus.pages
                  if k.startswith(pref) and "/" not in k[len(pref):])


def type_candidates(help_key: str, directives: dict) -> list:
    return helpdoc.canonical_type_names(help_key, directives)


# The shipped what's-new page links node paths in TWO forms, and the difference
# is one character:
#
#     [Grunge Aurora COP|Node:/cop/grunge_aurora]      161 occurrences
#     [Node:cop/geotoadjacency]                         11 occurrences
#
# A pattern requiring the leading slash returns 161 and drops 10 real node
# types -- the entire adjacency_* family, both layerattrib_* nodes, and three
# block_begin/block_end pairs. All 10 have a page and all 10 clear the floor.
#
# **The governing "161" is therefore a floor, not a total. The number is 171.**
# It is wrong in docs/H22_FRONTIER.md, in I0's Q3 ("161 named, 161 present"),
# in harness/SYNAPSE_INGEST.md and in this leg's own brief -- and it was wrong
# in this extractor's first version, whose calibration control asserted 161 and
# so PINNED the defect. A positive control inherited from the brief rather than
# measured from the archive locks in the brief's error (Law 5).
#
# Found by the concurrent I1 run (see .claude/remediation_ticket.md), verified
# here independently before being accepted.
RE_NODE_LINK = re.compile(r"Node:/?cop/([A-Za-z0-9_:.\-]+)")


def _news_zip(help_dir=None) -> Path:
    return (Path(help_dir) if help_dir is not None else HELP_DIR) / "news.zip"


def new_copernicus_nodes(help_dir=None) -> list:
    """Every new Copernicus node named in the SHIPPED what's-new page.

    ``news.zip!22/copernicus.txt``, not the browsing help cache: the shipped
    page is version-pinned by construction while the cache is a reading history
    that records only what somebody happened to open (I0-F5).

    Returns **171** on the default pin, both link forms counted; the count is a
    property of the build, so ``help_dir`` (e.g. ``corpus.help_dir``) selects it.
    """
    import zipfile
    with zipfile.ZipFile(_news_zip(help_dir)) as z:
        text = z.read("22/copernicus.txt").decode("utf-8-sig")
    names = []
    for m in RE_NODE_LINK.finditer(text):
        n = m.group(1).rstrip("].,")
        if n not in names:
            names.append(n)
    return sorted(names)


def new_copernicus_nodes_slash_only(help_dir=None) -> list:
    """The 161 a leading-slash-only pattern returns. Kept as a NEGATIVE
    instrument: the calibration proves this undercounts, so the defect cannot
    silently return."""
    import zipfile
    with zipfile.ZipFile(_news_zip(help_dir)) as z:
        text = z.read("22/copernicus.txt").decode("utf-8-sig")
    return sorted({m.group(1).rstrip("].,")
                   for m in re.finditer(r"Node:/cop/([A-Za-z0-9_:.\-]+)", text)})
