"""Node type -> one-line summary, by exact help path only.

The What line of a bubble is the node type's summary. It comes from an *exact*
help-path row in the local SideFX library (IDENTIFY_BLUEPRINT sec. 2/3): a
search-ranked hit is never used, because a near match on the wrong page is a
phantom. For an HDA that carries embedded help, the first sentence of that help
is used. When neither exists the type is honestly unknown.

No ``hou`` import lives here: the caller passes the already-read
``defaultHelpUrl()`` string and, for an HDA, the embedded help text. That keeps
this module runnable off the main thread and on system Python.
"""
from __future__ import annotations

import re
import logging

_log = logging.getLogger(__name__)


_OPERATOR_RE = re.compile(
    r"^operator:(?P<context>[^/]+)/(?P<name>[^?]+)(?:\?version=(?P<version>[\w.]+))?$")

_SENTENCE_END = re.compile(r"(?<=[.!?])(\s|$)")

_PARAGRAPHS = re.compile(r"\n\s*\n")

#: A Houdini help-page header directive line, e.g. ``#type: node`` (sec. 2).
_HELP_DIRECTIVE = re.compile(r"^#[A-Za-z][\w-]*:")

#: A Houdini help-page include line, e.g. ``:include /shelf/polyextrude#includeme:``
#: — a ``:name ...:`` markup directive that carries no prose (sec. 2).
_HELP_INCLUDE = re.compile(r"^:[A-Za-z][\w-]*(?:\s.*)?:$")


def derive_help_keys(help_url: str) -> list[str]:
    """Canonical ``nodes/<context>/<name>`` keys, most specific first.

    ``operator:Sop/polybevel?version=3.0`` yields the versioned page key first
    (``nodes/sop/polybevel-3.0``) and its base (``nodes/sop/polybevel``), so a
    versioned page wins when the library has one and the base is the fallback.
    A non-operator URL yields no keys.
    """
    if not isinstance(help_url, str):
        return []
    match = _OPERATOR_RE.match(help_url.strip())
    if not match:
        return []
    context = match.group("context").strip().lower()
    name = match.group("name").strip().lower()
    # A namespaced/versioned type name (``polybevel::3.0``) reduces to its stem;
    # the version is carried by the ``?version=`` query, not the name.
    name = name.split("::", 1)[0]
    if not context or not name:
        return []
    base = f"nodes/{context}/{name}"
    keys: list[str] = []
    version = match.group("version")
    if version:
        keys.append(f"{base}-{version.strip().lower()}")
    keys.append(base)
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
    lines = text.lstrip("﻿").split("\n")
    start = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("﻿")
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
        line = line.strip().lstrip("﻿").strip()
        if not line:
            continue
        saw_line = True
        if not (_HELP_DIRECTIVE.match(line) or _HELP_INCLUDE.match(line)):
            return False
    return saw_line


def summary_paragraph(body: str) -> str:
    """The description paragraph of a node help page.

    Corpus node pages read ``Title\\n\\nSummary sentence.\\n\\n...`` — the first
    paragraph is the node's own title (a bare heading). Drop that heading so the
    What line is the description, not ``PolyBevel PolyBevel ...``. Help-markup
    paragraphs — a leading BOM, ``#key: value`` header directives, and
    ``:name ...:`` includes — are dropped *wherever they sit*, not only at the
    top of the body, so a directive block that follows the title never becomes
    the summary (BP11-IDFIX2, sec. 2). When only markup remains the result is
    empty, which the caller reports as the honest unknown.
    """
    paragraphs = []
    for p in _PARAGRAPHS.split(_strip_help_header(str(body or "")).strip()):
        p = p.strip()
        if not p or not p.lstrip("﻿").strip():
            continue          # empty, or only a BOM / whitespace
        if _is_markup_only(p):
            continue          # a directive/include-only paragraph, wherever it sits
        paragraphs.append(p)
    if not paragraphs:
        return ""
    head = paragraphs[0]
    if len(paragraphs) > 1 and "\n" not in head and len(head) <= 40 and not re.search(r"[.!?]", head):
        return paragraphs[1]
    return head


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
            text = first_sentence(summary_paragraph(hit[0]))
            if text:
                result = (text, "library")

    if result[0] is None and hda_help and str(hda_help).strip():
        text = first_sentence(summary_paragraph(hda_help))
        if text:
            result = (text, "hda")

    if use_cache and not failed and (result[0] is not None or identity is not None):
        _SUMMARY_CACHE[cache_key] = result
    return result
