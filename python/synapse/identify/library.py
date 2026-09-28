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


_OPERATOR_RE = re.compile(
    r"^operator:(?P<context>[^/]+)/(?P<name>[^?]+)(?:\?version=(?P<version>[\w.]+))?$")

_SENTENCE_END = re.compile(r"(?<=[.!?])(\s|$)")

_PARAGRAPHS = re.compile(r"\n\s*\n")


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


def summary_paragraph(body: str) -> str:
    """The description paragraph of a node help page.

    Corpus node pages read ``Title\\n\\nSummary sentence.\\n\\n...`` — the first
    paragraph is the node's own title (a bare heading). Drop that heading so the
    What line is the description, not ``PolyBevel PolyBevel ...``.
    """
    paragraphs = [p.strip() for p in _PARAGRAPHS.split(str(body or "").strip()) if p.strip()]
    if not paragraphs:
        return ""
    head = paragraphs[0]
    if len(paragraphs) > 1 and "\n" not in head and len(head) <= 40 and not re.search(r"[.!?]", head):
        return paragraphs[1]
    return head


def summarize(help_url: str, hda_help: str | None = None,
              lookup=None) -> tuple[str | None, str]:
    """Return ``(summary_text, source)`` where source is ``library``/``hda``/``unknown``.

    Order per sec. 2: an exact help-path library row, else an HDA's embedded
    help first sentence, else unknown. *lookup* defaults to the library's exact
    ``help_summary``; it is injectable for tests. A ``lookup`` that raises is
    treated as no row (honest unknown), never a crash on the bubble path.
    """
    if lookup is None:
        from synapse.cognitive.tools.sidefx_library import help_summary as lookup

    keys = derive_help_keys(help_url)
    if keys:
        try:
            hit = lookup(keys)
        except Exception as e:

                logging.debug("exception: %s", e)

                        
        if hit:
            text = first_sentence(summary_paragraph(hit[0]))
            if text:
                return (text, "library")

    if hda_help and str(hda_help).strip():
        text = first_sentence(summary_paragraph(hda_help))
        if text:
            return (text, "hda")

    return (None, "unknown")
