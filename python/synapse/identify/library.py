"""Node type -> one-line summary, by exact help path only.

The What line of a bubble is the node type's summary. It comes from an *exact*
help-path row in the local SideFX library (IDENTIFY_BLUEPRINT sec. 2/3): a
search-ranked hit is never used, because a near match on the wrong page is a
phantom. The help path is built the way Houdini's own help browser builds it
(:func:`derive_help_keys`). For an HDA that carries embedded help, that help's
summary is used. When neither exists the type is honestly unknown.

A help page's summary is its triple-quoted tooltip when it has one, else its
first prose paragraph before any section, rendered as plain words
(:func:`summary_text`). Help markup never reaches a What line; :data:`RESIDUE`
is the one pattern that says what counts as markup.

No ``hou`` import lives here: the caller passes the already-read
``defaultHelpUrl()`` string and, for an HDA, the embedded help text. That keeps
this module runnable off the main thread and on system Python.
"""
from __future__ import annotations

import re
import logging
from urllib.parse import parse_qs

_log = logging.getLogger(__name__)


#: Houdini's own map from a node type category to its help folder
#: (``houdinihelp.api.table_to_dir``, Houdini 22.0.400), keyed in lower case.
#: ``Object`` pages live under ``nodes/obj``, ``Driver`` (ROP) pages under
#: ``nodes/out`` and ``VopNet`` pages under ``nodes/vex``.
_TABLE_TO_DIR = {
    "object": "obj", "sop": "sop", "particle": "part", "dop": "dop",
    "chopnet": "chopnet", "chop": "chop", "driver": "out", "shop": "shop",
    "cop": "cop", "cop2": "cop2", "copnet": "copnet", "vop": "vop",
    "vopnet": "vex", "top": "top", "topnet": "topnet", "lop": "lop",
    "manager": "manager", "data": "data", "apex": "apex",
}

_OPERATOR_RE = re.compile(
    r"^operator:(?P<table>[^/?]+)/(?P<name>[^?]+)(?:\?(?P<query>.*))?$")

_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")

_SENTENCE_END = re.compile(r"(?<=[.!?])(\s|$)")

_PARAGRAPHS = re.compile(r"\n\s*\n")

#: A Houdini help-page header directive line, e.g. ``#type: node`` (sec. 2), or
#: one written without its colon (``#icon COMMON/materialx``, BP12 item 3).
_HELP_DIRECTIVE = re.compile(r"^#[A-Za-z][\w-]*(?::|\s)")

#: A Houdini help-page include line, e.g. ``:include /shelf/polyextrude#includeme:``
#: — a ``:name ...:`` markup directive that carries no prose (sec. 2).
_HELP_INCLUDE = re.compile(r"^:[A-Za-z][\w-]*(?:\s.*)?:$")

#: Houdini's tooltip rule (``houdinihelp.api.tooltip_regex``): a help page's
#: summary is the text between its first pair of triple double quotes.
_TOOLTIP = re.compile(r'"""(.*?)"""', re.DOTALL)

#: A wiki heading (``= Name =``, ``== Main ==``, ``=== Volume === (volume)``).
_WIKI_HEADING = re.compile(r"^(=+)[^=].*?\1(?:\s*\([\w.\-]*\))?$")

#: A markdown heading (``# Labs Auto UV``, ``## Parameters``).
_MD_HEADING = re.compile(r"^(#{1,6})\s+\S")

#: A section marker (``@parameters``, ``@subtopics Examples``): the page's
#: summary never follows one.
_SECTION_MARK = re.compile(r"^@[A-Za-z]")

#: The first line of a note or warning box (``:warning:Deprecated:``,
#: ``:note:``, ``**NOTE:**``, a ``> **Note**`` quote). A box is a callout, not
#: the node's summary.
_ADMONITION = re.compile(r"^(?::[a-z]+:|\*\*[A-Za-z][A-Za-z ]*:\*\*|>)")

#: A list item, table row, code fence or block tag: never the summary.
_NOT_PROSE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|\||```|~~~|\{\{\{|<<)|>>$|\|\||\s\|$")

#: A definition-list term, e.g. ``Proxy Display:``: a parameter, not the node.
_DEF_TERM = re.compile(r"^[^\s.!?][^.!?]{0,78}:$")

#: A help source path the library uses as an untitled page's title.
_SOURCE_PATH = re.compile(r"^[\w./-]+\.txt$")

#: A bracketed placeholder left by a help template, e.g. ``[Basic Description]``.
_PLACEHOLDER = re.compile(r"^\[[^\]:|/]*\]$")

#: An HTML comment such as ``<!---#icon: SOP/rbdxform--->``.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

#: An include file's header (``#type: include``): shared text, not a node's page.
_INCLUDE_PAGE = re.compile(r"^#type:\s*include\b", re.MULTILINE)

#: A picture reference, ``[Image:/images/nodes/vop/mtlxbump.jpg]``.
_IMAGE = re.compile(r"\[Image:[^\]]*\]")

#: A markdown link ``[Labs UV Visualize](../sop/labs--visualize_uvs)``.
_MD_LINK = re.compile(r"\[([^\]\[]+)\]\([^)\s]*\)")

#: A wiki link ``[Node:dop/clothobject]``, ``[Muscles|/character/muscles]``.
#: Only a bracket with a scheme, a path or a label counts, so a range such as
#: ``[0, 1]`` in prose is left alone.
_WIKI_LINK = re.compile(r"\[(?:(?P<label>[^\]|\[]+)\|)?(?P<target>[^\]\[\s|]*[:/][^\]\[\s|]*)\]")

#: Help markup that must never reach a What line. The corpus sweep
#: (``scripts/sweep_identify_summaries.py``) and the corpus-gated test use this
#: one pattern, so "no residue" means the same thing in both.
RESIDUE = re.compile(
    r"\ufeff|\*\*|''|`|\"\"\"|\[Image:|\]\(|\[[^\]]*[:|/][^\]]*\]"
    r"|^=+\s|\s=+$|(?:^|\s)#{1,6}\s|#[A-Za-z][\w-]*:|^#[A-Za-z][\w-]*\s"
    r"|(?:^|\s):[a-z][\w-]*(?::|\s|$)|^@[A-Za-z]|\{\{\{|\}\}\}|</?[a-z]+[^>]*>"
    r"|(?<!\w)_[^_\s][^_]*_(?!\w)|(?<![\w*])\*(?=\S)[^*\n]+?(?<=\S)\*(?![\w*])"
    r"|^\[[^\]]*\]$|<<|>>|\|\||^>\s|~~~|\bid=\"|^[\w./-]+\.txt$")


def _split_type_name(name: str) -> tuple[str, str, str]:
    """``[namespace::]name[::version]`` -> (namespace, name, version)."""
    parts = [p for p in name.split("::") if p]
    version = parts.pop() if len(parts) > 1 and _VERSION_RE.match(parts[-1]) else ""
    namespace = "::".join(parts[:-1]) if len(parts) > 1 else ""
    return namespace, (parts[-1] if parts else ""), version


def derive_help_keys(help_url: str) -> list[str]:
    """Candidate ``nodes/<folder>/<page>`` keys for a help URL, most specific first.

    This mirrors Houdini's own resolution (``houdinihelp.api.components_to_path``
    in Houdini 22). The category picks the help folder (``Object`` -> ``obj``,
    ``Driver`` -> ``out``, ``VopNet`` -> ``vex``), a ``?namespace=`` becomes a
    ``<namespace>--`` prefix with any colon written as ``$``, and a
    ``?version=`` becomes a ``-<version>`` suffix. So
    ``operator:Cop/uv_grid_texture?namespace=labs&version=1.0`` yields
    ``nodes/cop/labs--uv_grid_texture-1.0``, then the unversioned
    ``nodes/cop/labs--uv_grid_texture``: the versioned page wins when the
    library has one. A type without a namespace then falls back to
    ``nodes/manager/<name>``, as Houdini does for a network manager such as a
    ``sopnet`` inside another context. A scoped type (``?scopeop=``) needs
    ``hou`` to decode its scope, so it yields no keys and stays honestly
    unknown, as does any URL that is not an ``operator:`` link.
    """
    if not isinstance(help_url, str):
        return []
    match = _OPERATOR_RE.match(help_url.strip())
    if not match:
        return []
    query = parse_qs(match.group("query") or "")
    if query.get("scopeop"):
        return []
    table = match.group("table").strip()
    name = match.group("name").strip()
    namespace = (query.get("namespace") or [""])[0].strip()
    version = (query.get("version") or [""])[0].strip()
    if "::" in name:
        # Houdini 22 writes the namespace and version as query fields; read a
        # full type name (``polyextrude::2.0``) too, as older callers passed.
        name_ns, name, name_version = _split_type_name(name)
        namespace = namespace or name_ns
        version = version or name_version
    if "/" in name:  # houdinihelp: a name like ``Sop/foo`` carries its own category
        table, name = name.split("/", 1)
    folder = _TABLE_TO_DIR.get(table.strip().lower(), table.strip().lower())
    name = name.strip()
    if not folder or not name:
        return []
    page = (namespace.replace(":", "$") + "--" if namespace else "") + name.replace("/", "_")
    base = f"nodes/{folder}/{page}".lower()
    keys = [f"{base}-{version.lower()}"] if version else []
    keys.append(base)
    if not namespace and folder != "manager":
        keys.append(f"nodes/manager/{name.lower()}")
    return keys


def first_sentence(text: str) -> str:
    """The first sentence of *text*, whitespace-collapsed."""
    collapsed = " ".join(str(text or "").split())
    if not collapsed:
        return ""
    end = _SENTENCE_END.search(collapsed)
    if end:
        return collapsed[: end.start() + 1].strip()
    return collapsed


def _strip_help_header(text: str) -> str:
    """Drop a leading UTF-8 BOM and any ``#key: value`` help-header lines.

    Houdini help pages often begin with directives like ``#type: node`` and
    ``#context: sop``, sometimes behind a UTF-8 BOM. Skip the BOM and those
    header lines so the first *prose* line wins, not a directive (sec. 2). When
    only a BOM and directives are present the result is empty, which the caller
    reports as the honest unknown.
    """
    lines = text.lstrip("\ufeff").split("\n")
    start = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("\ufeff")
        if not stripped or _HELP_DIRECTIVE.match(stripped):
            continue
        start = i
        break
    return "\n".join(lines[start:])


def _is_markup_only(paragraph: str) -> bool:
    """True when *paragraph* carries only help markup, no prose (sec. 2).

    Real corpus pages interleave help-markup paragraphs with the prose: a
    ``#type: node`` directive block or a ``:include ...:`` line can sit *after*
    the title, so stripping the header only from the top of the body is not
    enough (BP11-IDFIX2). A paragraph is markup-only when, after dropping a
    U+FEFF from each line, it has at least one non-empty line and every
    non-empty line is a ``#key: value`` directive or a ``:name ...:`` include.
    Such a paragraph is never a node's description, so the caller skips it
    wherever it sits.
    """
    saw_line = False
    for line in paragraph.split("\n"):
        line = line.strip().lstrip("\ufeff").strip()
        if not line:
            continue
        saw_line = True
        if not (_HELP_DIRECTIVE.match(line) or _HELP_INCLUDE.match(line)):
            return False
    return saw_line


def _content_lines(paragraph: str) -> list[str]:
    """A paragraph's lines without help markup: no directive, include or picture line.

    Indentation is kept (an indented line belongs to a list or a box). Such a
    markup line never carries prose, wherever it sits (BP11-IDFIX2).
    """
    kept = []
    for line in paragraph.split("\n"):
        bare = line.strip()
        if not bare or _HELP_DIRECTIVE.match(bare) or _HELP_INCLUDE.match(bare) \
                or _IMAGE.fullmatch(bare):
            continue
        kept.append(line.rstrip())
    return kept


def _indented(line: str) -> bool:
    return line[:1] in (" ", "\t")


def _first_line(paragraphs: list, index: int) -> str:
    """The first line of ``paragraphs[index]``, indentation kept; ``""`` past the end."""
    return paragraphs[index].split("\n", 1)[0] if index < len(paragraphs) else ""


def _heading_level(line: str) -> int:
    """1 for a title heading, 2+ for a section heading, 0 for anything else."""
    line = line.strip()
    wiki = _WIKI_HEADING.match(line)
    if wiki:
        return len(wiki.group(1))
    md = _MD_HEADING.match(line)
    if md and not _HELP_DIRECTIVE.match(line):
        return len(md.group(1))
    return 0


def summary_paragraph(body: str) -> str:
    """The summary paragraph of a node help page, or ``""`` when it has none.

    Houdini's own rule comes first: text between triple double quotes is the
    summary, as HDA help writes it (``\"\"\"Delays transformations.\"\"\"``).
    Otherwise the summary is the first prose paragraph before any section.
    The walk skips:

    * a title: a ``= Name =`` or ``# Name`` heading, the breadcrumb lines
      above one, or a first short line with no sentence punctuation;
    * help markup: ``#key: value`` directives and ``:include ...:`` lines
      wherever they sit (BP11-IDFIX2), and a picture-only paragraph;
    * a note or warning box (``:warning:``, ``**NOTE:**``), a list item, a
      table row, a code fence, an indented block, and a template placeholder
      such as ``[Basic Description]``.

    It stops at a section heading (``== Main ==``, ``## Parameters``), an
    ``@parameters`` marker or a parameter term (``Proxy Display:``): past
    those the prose describes a part of the node, not the node.

    A U+FEFF after the start of the body marks where the page's own file
    begins; the library's page-top chunk sometimes carries a stray title from
    an included page before it, so that text is dropped.
    """
    text = str(body or "")
    lead = text.lstrip("\ufeff")
    cut = lead.find("\ufeff")
    title_seen = cut > 0
    if title_seen:
        lead = lead[cut:]
    text = _HTML_COMMENT.sub("", lead.replace("\ufeff", ""))
    if _INCLUDE_PAGE.search(text):
        return ""

    tooltip = _TOOLTIP.search(text)
    if tooltip:
        found = " ".join(tooltip.group(1).split())
        if found and not _PLACEHOLDER.match(found):
            return found
        text = text[: tooltip.start()] + text[tooltip.end():]

    paragraphs = [p for p in _PARAGRAPHS.split(_strip_help_header(text).strip())
                  if p.strip()]
    for index, paragraph in enumerate(paragraphs):
        lines = _content_lines(paragraph)
        marks = [i for i, line in enumerate(lines) if _heading_level(line)]
        if marks:
            last = marks[-1]
            if any(re.search(r"[.!?]", line) and not _heading_level(line)
                   for line in lines[:last]):
                # A sentence sits above the heading: that sentence is prose.
                lines = lines[: marks[0]]
            else:
                if _heading_level(lines[last]) >= 2:
                    return ""
                title_seen = True
                lines = lines[last + 1:]
        if not lines:
            continue
        first = lines[0].strip()
        if _ADMONITION.match(first):
            continue
        if _SECTION_MARK.match(first) or (_DEF_TERM.match(first) and _indented(
                lines[1] if len(lines) > 1 else _first_line(paragraphs, index + 1))):
            return ""
        if len(lines) == 1 and _SOURCE_PATH.match(first):
            title_seen = True   # the library titles an untitled page with its file path
            continue
        if _indented(lines[0]) or _NOT_PROSE.search(first) or _PLACEHOLDER.match(first):
            continue
        more_follows = any(_content_lines(later) for later in paragraphs[index + 1:])
        if (not title_seen and more_follows and len(lines) == 1 and len(first) <= 60
                and not re.search(r"[.!?]", first)):
            title_seen = True
            continue
        return "\n".join(line.strip() for line in lines)
    return ""


def _link_label(match: re.Match) -> str:
    """A wiki link's label, else the last part of its target."""
    label = match.group("label")
    if label and label.strip():
        return label.strip()
    target = match.group("target").rstrip("/")
    return re.split(r"[/:]", target)[-1].split("#", 1)[0]


def plain_text(text: str) -> str:
    """Help markup inside a summary rendered as the words a reader sees.

    Code spans keep their text without the backticks (and are protected
    first, so ``_id_`` inside one is not read as italics). A picture is
    dropped; a link keeps its label, or the last part of its target;
    ``**bold**``, ``*italic*``, ``''italic''`` and ``_italic_`` keep their
    words.
    """
    spans: list[str] = []

    def _keep(match: re.Match) -> str:
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]*)`", _keep, str(text or ""))
    text = _IMAGE.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _WIKI_LINK.sub(_link_label, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", text)
    text = re.sub(r"''(.+?)''", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\s][^_]*?)_(?!\w)", r"\1", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    return " ".join(text.split())


def summary_text(body: str) -> str:
    """The What line a help page gives: its summary's first sentence, plain."""
    return first_sentence(plain_text(summary_paragraph(body)))


#: Per-process memo keyed by ``(help_url, hda_help, corpus identity)`` (sec. 5
#: responsiveness). Only the production path (``lookup is None``) is memoized,
#: so an injected test ``lookup`` is always called and never served a stale
#: cached row. A lookup that raised, or a miss while the library could not be
#: read, is never stored, so an outage on the first click is not pinned until
#: Houdini restarts (CRUX2 N1). The corpus identity is the library root and its
#: published generation, so a rebuilt or re-pointed library is looked up afresh.
_SUMMARY_CACHE: dict[tuple, tuple] = {}


def summarize(help_url: str, hda_help: str | None = None,
              lookup=None) -> tuple[str | None, str]:
    """Return ``(summary_text, source)`` where source is ``library``/``hda``/``unknown``.

    Order per sec. 2: an exact help-path library row, else an HDA's embedded
    help first sentence, else unknown. *lookup* defaults to the library's exact
    ``help_summary``; it is injectable for tests. A ``lookup`` that raises is
    treated as no row (honest unknown), never a crash on the bubble path.

    The default path memoizes per ``(help_url, hda_help, corpus identity)`` for
    the life of the process, so a 200-node selection of a few types costs one
    library lookup per distinct type, not one per node (sec. 5). It remembers a
    found summary, and a miss only when the library was readable; an outage is
    looked up again on the next click (CRUX2 N1).
    """
    use_cache = lookup is None
    identity = None
    if use_cache:
        from synapse.cognitive.tools import sidefx_library as _sidefx
        identity = _sidefx.corpus_identity()
        cache_key = (help_url, hda_help, identity)
        if cache_key in _SUMMARY_CACHE:
            return _SUMMARY_CACHE[cache_key]
        lookup = _sidefx.help_summary

    result: tuple[str | None, str] = (None, "unknown")
    failed = False
    keys = derive_help_keys(help_url)
    if keys:
        try:
            hit = lookup(keys)
        except Exception:
            _log.debug("library lookup failed; the miss is not remembered", exc_info=True)
            hit, failed = None, True
        if hit:
            text = summary_text(hit[0])
            if text:
                result = (text, "library")

    if result[0] is None and hda_help and str(hda_help).strip():
        text = summary_text(hda_help)
        if text:
            result = (text, "hda")

    if use_cache and not failed and (result[0] is not None or identity is not None):
        _SUMMARY_CACHE[cache_key] = result
    return result
