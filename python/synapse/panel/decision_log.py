"""P1 · CREDITED DECISIONS — the producer behind the credit grid's DECISION rows.

``FaceReview`` has always been able to *render* a DECISION row. Measured on
2026-07-27 at commit e086c2c (``harness/notes/p1_layout_census.py``), it had
**zero** product callers: ``set_credit`` was reached from exactly one site, with
the label ``ROUTED``. The panel could draw a credit it could never earn.

This module is the missing half. For every mutation the agent performs it
records **what was chosen and why**, in the agent's own words, so the result
surface can caption it the way a project credits a named partner:

    DECISION   Dark_Glass — over Diamond, closer to scene IOR

WHAT MAKES THIS HONEST (Law 3)
------------------------------
A credit surface that invents its own reasons is worse than no credit surface,
because it is a provenance claim nobody can check. Three rules hold:

1. **The "why" is quoted, never composed.** ``why_from_reasoning`` selects a
   sentence the model actually wrote in the turn that made the call. It never
   summarises, never rephrases and never supplies a default. No reasoning in the
   turn -> the note is empty and the row shows the choice alone.
2. **Only mutations are credited.** Read-only tools make no decision to credit.
   Classification comes from the tree's own authority --
   ``worker_policy``'s index over ``TOOL_DEFS`` -- not a hand-written list that
   would drift the first time a tool is added.
3. **An unregistered tool is still recorded, and says so.** A tool the registry
   cannot classify is precisely the one whose effect is unaudited; dropping it
   would make the surface quietest exactly where it should be loudest. It is
   recorded with ``classified=False`` so nothing downstream can claim registry
   backing it does not have.

V2 · WHERE THIS MEETS THE TYPED CONTRACT
----------------------------------------
``verdict.Verdict`` gives the Review face a shape, and its ``decision`` field is
the typed home of the rows this module produces. ``to_verdict_decision`` is the
adapter, and it exists so that BOTH credit producers in the tree land in the same
field with their source recorded rather than one quietly replacing the other:

* here — the "why" is a sentence the model actually wrote, tagged
  ``MODEL_QUOTED``. Stronger, because it reports what the agent CHOSE.
* ``synapse_panel::_turn_evidence`` — derived from tool names and results, tagged
  ``TOOL`` via ``verdict.decision_from_tool_evidence``. Honest and weaker,
  because it reports what a tool DID.

The adapter refuses an unclassified row by default. The typed schema has no slot
for ``classified``, and converting an unregistered tool's row into a field that
cannot carry the warning would make the surface quietest exactly where rule 3
above makes it loudest.

Pure Python: no Qt, no ``hou``. It runs, and is tested, standalone.
"""

import re

__all__ = [
    "Decision", "DecisionLog",
    "classify_tool", "choice_from_input", "why_from_reasoning",
    "MAX_NOTE_CHARS", "MAX_CHOICE_CHARS",
]

MAX_NOTE_CHARS = 96
MAX_CHOICE_CHARS = 48

# Input keys that name WHAT was chosen, most specific first. A tool's most
# meaningful identifier is the thing an artist would recognise in the scene, so
# an explicit name beats a type, and a type beats a bare path.
_CHOICE_KEYS = (
    "material_name", "material", "name", "node_name", "preset", "recipe",
    "node_type", "prim_type", "prim_path", "node_path", "parent_path",
    "path", "parm", "parm_name", "file_path", "output_path", "asset",
)

# Sentence-ish splitter: a terminator followed by whitespace. Kept deliberately
# simple -- this selects a quote, it does not parse prose.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

# Markdown scaffolding to strip before quoting. Only decoration is removed; the
# words themselves are never altered.
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.M)
_HEADING = re.compile(r"^\s*#{1,6}\s*", re.M)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_)")


class Decision:
    """One credited decision: what the agent chose, and why, for one tool call.

    ``classified`` records whether the tool registry could class the tool at
    all. ``False`` means unregistered -- the row is still shown, but no caller
    may read it as "the registry says this mutates".
    """

    __slots__ = ("tool", "choice", "why", "classified")

    def __init__(self, tool, choice, why="", classified=True):
        self.tool = tool
        self.choice = choice
        self.why = why or ""
        self.classified = bool(classified)

    def as_credit_row(self):
        """``(label, value, note)`` in the shape ``FaceReview.set_credit`` wants."""
        return ("DECISION", self.choice, self.why)

    def to_verdict_decision(self, allow_unclassified=False):
        """This row as a ``verdict.Decision``, or ``None``.

        ``provenance`` is ``MODEL_QUOTED`` when a sentence was actually quoted
        and ``TOOL`` when the turn carried no prose — the row is still real, but
        nothing downstream may read an empty ``because`` as the model's reason.

        Returns ``None`` for a row with nothing to credit, and — unless
        ``allow_unclassified`` is set — for a row the tool registry could not
        classify. See the module docstring for why that is a refusal rather than
        a silent conversion.
        """
        if not self.choice:
            return None
        if not self.classified and not allow_unclassified:
            return None
        try:
            from synapse.panel import verdict as _v
        except Exception:
            return None
        # Clamp to the CONTRACT's ceilings, read from the contract rather than
        # assumed equal to this module's. They happen to match today; a future
        # divergence must narrow the value, not raise inside a credit surface.
        return _v.Decision(
            chose=_trim(self.choice, _v.MAX_IDENT_CHARS),
            because=_trim(self.why, _v.MAX_TEXT_CHARS) if self.why else "",
            provenance=_v.MODEL_QUOTED if self.why else _v.TOOL,
        )

    def __eq__(self, other):
        return (isinstance(other, Decision)
                and (self.tool, self.choice, self.why, self.classified)
                == (other.tool, other.choice, other.why, other.classified))

    def __repr__(self):  # pragma: no cover - diagnostics only
        return "Decision(tool=%r, choice=%r, why=%r, classified=%r)" % (
            self.tool, self.choice, self.why, self.classified)


def classify_tool(tool_name):
    """``"mutation"`` | ``"read_only"`` | ``"unknown"`` for one tool name.

    Delegates to ``worker_policy``'s index over ``TOOL_DEFS`` -- the same table
    the dispatch-side allowlist reads -- so a tool added to the registry is
    classified here without a second list needing to be remembered. If that
    module cannot be imported the answer is ``"unknown"``, never a guess.
    """
    if not tool_name:
        return "unknown"
    try:
        from synapse.panel.worker_policy import _TOOL_INDEX
    except Exception:
        return "unknown"
    info = _TOOL_INDEX.get(tool_name)
    if info is None:
        return "unknown"
    return "read_only" if info.get("read_only") else "mutation"


def _scalar(value):
    """A short display string for a scalar input value, or None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def choice_from_input(tool_name, tool_input):
    """WHAT was chosen: the most identifying scalar in the tool's own input.

    Falls back to the tool name, which is a true statement about what ran. It
    never invents a label for a call whose input carries no identifier.
    """
    if isinstance(tool_input, dict):
        for key in _CHOICE_KEYS:
            if key not in tool_input:
                continue
            text = _scalar(tool_input.get(key))
            if text:
                return _trim(text, MAX_CHOICE_CHARS)
    return tool_name or ""


def _strip_markdown(text):
    text = _FENCE.sub(" ", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _BULLET.sub("", text)
    text = _EMPHASIS.sub("", text)
    return text


def _trim(text, limit):
    """Shorten to AT MOST ``limit`` on a word boundary, with an ellipsis when cut.

    V2-F12: the ellipsis used to be appended AFTER cutting to ``limit``, so a
    string with no space in its first ``limit`` characters came back ``limit+1``
    long — and space-free strings are the commonest real input this sees, because
    ``_CHOICE_KEYS`` selects node paths and file paths. A function that takes a
    limit and returns limit+1 is a bug on its own; it became a crash when the
    typed contract started enforcing the same ceiling strictly.
    """
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    head = text[:limit - 1]                 # reserve the ellipsis's own column
    cut = head.rsplit(" ", 1)[0]
    return (cut or head).rstrip(",;:-") + "…"


def why_from_reasoning(reasoning):
    """QUOTE the model's own reason for the call, or return ``""``.

    The sentence nearest the tool call is the one that explains it, so the LAST
    complete sentence of the turn's prose is taken. The text is only ever
    de-decorated and shortened -- it is never rewritten, and when the turn
    carried no prose the result is the empty string rather than a plausible
    substitute.
    """
    if not reasoning or not isinstance(reasoning, str):
        return ""
    text = _strip_markdown(reasoning).strip()
    if not text:
        return ""
    parts = [p.strip() for p in _SENTENCE.split(text) if p.strip()]
    if not parts:
        return ""
    chosen = parts[-1].rstrip(".")
    if not chosen:
        return ""
    return _trim(chosen, MAX_NOTE_CHARS)


class DecisionLog:
    """The decisions of ONE work cycle, in the order they were made.

    ``begin_cycle`` clears it, so the credit grid shows what this run decided
    rather than an ever-growing session history the artist cannot place.
    """

    def __init__(self, limit=6):
        self._rows = []
        self._limit = int(limit)
        self._skipped_read_only = 0

    def begin_cycle(self):
        self._rows = []
        self._skipped_read_only = 0

    def record(self, tool_name, tool_input=None, reasoning=""):
        """Record one tool call. Returns the ``Decision``, or ``None`` if the
        call was read-only and therefore decided nothing to credit."""
        kind = classify_tool(tool_name)
        if kind == "read_only":
            self._skipped_read_only += 1
            return None
        decision = Decision(
            tool=tool_name,
            choice=choice_from_input(tool_name, tool_input),
            why=why_from_reasoning(reasoning),
            classified=(kind == "mutation"),
        )
        self._rows.append(decision)
        # Keep the most RECENT decisions: the tail of a long run is what the
        # artist is looking at when the result lands.
        if len(self._rows) > self._limit:
            self._rows = self._rows[-self._limit:]
        return decision

    def decisions(self):
        return list(self._rows)

    def skipped_read_only(self):
        return self._skipped_read_only

    def credit_rows(self):
        """``[(label, value, note)]`` for ``FaceReview.set_credit``."""
        return [d.as_credit_row() for d in self._rows]

    def to_verdict_decisions(self, allow_unclassified=False):
        """This cycle's rows as ``verdict.Decision`` objects, in order.

        Rows that decline to convert are DROPPED, not defaulted — the count can
        legitimately be smaller than ``len(self)`` and a caller comparing the two
        is reading the refusal, which is the point.

        A row the contract REJECTS is dropped too, and counted separately in
        ``rejected_conversions``. One malformed row must not take a whole credit
        surface down with it (V2-F12 was exactly that: a 49-character node path
        raised, and every other decision in the cycle went with it) — but a
        rejection is a fact about the data, so it is recorded rather than
        swallowed (Law 3).
        """
        out, rejected = [], 0
        for row in self._rows:
            try:
                converted = row.to_verdict_decision(allow_unclassified)
            except Exception:
                rejected += 1
                continue
            if converted is not None:
                out.append(converted)
        self._rejected_conversions = rejected
        return tuple(out)

    def rejected_conversions(self):
        """How many rows the typed contract refused on the last conversion.
        ``0`` until ``to_verdict_decisions`` has run — it describes what
        happened, not what would happen."""
        return getattr(self, "_rejected_conversions", 0)

    def __len__(self):
        return len(self._rows)
