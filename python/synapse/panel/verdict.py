"""V2 · THE VERDICT CONTRACT — the object the agent emits, the rows the panel draws.

Blueprint Mile 3. The Review face has always been able to *render* a result; what
it never had was a **shape** for one. ``show_result`` takes seven loose keyword
arguments, every one of them optional, and the only thing that has ever fed it is
prose scraped off the end of a stream (``synapse_panel.py:1220-1226`` takes the
first line of ``_stream_buf`` and truncates it at 140 characters).

That is the whole problem this module exists to close. **A panel fed prose has the
register of whichever model wrote the prose.** Rotate the tier manifest and the
panel visibly becomes a different tool, because the trust the artist built was
model-specific. So the agent emits STRUCTURE and the panel composes the rows:

    verdict   free text · ONE sentence · governed by ``voice_contract``
    decision  { chose, over, because }
    via       { node_path, mechanism }
    by        { model, tier, reason, tokens_in, tokens_out, cost }
    checks    [ { state, text, ref } ]
    paths     [ str ]
    actions   [ { label, kind, forecast_tokens } ]

WHAT IS ENFORCED, NOT DOCUMENTED
--------------------------------
1. **``by`` is never null.** It is the first field and carries no default, so a
   ``Verdict`` built without an author is a ``TypeError`` from the language
   itself; passing ``None`` explicitly raises ``ValueError``. A verdict with no
   author does not render because it cannot be constructed.
2. **Exactly one field may carry the model's free prose, and it is ``verdict``.**
   Every other place prose can enter (``Decision.because``, ``Check.text``)
   declares a ``provenance`` and is refused if it declares ``MODEL_FREE``.
   ``model_free_fields()`` reads the answer back off a built object, so the
   invariant is checkable from outside as well as enforced from inside.
3. **Unmeasured is not zero.** ``tokens_in``/``tokens_out``/``cost`` accept
   ``None`` for *not measured* and reject ``bool``. ``0`` is a measurement and
   renders; ``None`` is an absence and does not. The panel's own metering rule
   ("TOKENS ONLY, never $ ... stays EMPTY until real usage arrives — never
   estimated", ``synapse_panel.py:468-471``) depends on the difference, and
   E0-F12 says no usage reader is closed yet, so ``None`` is the honest state
   today.

THE PROVENANCE LADDER
---------------------
``MODEL_FREE`` is not the only way a string can come from a model, and pretending
otherwise would have made this contract quietly contradict work that landed the
same day. ``decision_log.py`` QUOTES a sentence the model wrote — it selects, it
never composes — and ``synapse_panel.py::_turn_evidence`` derives a row from what
a tool DID. Both are honest and they are not the same thing, so the ladder names
all four:

    MODEL_FREE    the model's own prose, unconstrained.  ONE field: ``verdict``.
    MODEL_QUOTED  a sentence the model wrote, selected verbatim (decision_log)
    TOOL          derived from a tool's name/input/result (_turn_evidence)
    SYSTEM        composed by the panel or router from its own state

Anything downstream can read the tier and refuse to claim more than it has. That
is the same rule ``Decision.classified`` already encodes one layer down.

Pure Python: no Qt, no ``hou``, no network. It runs, and is tested, standalone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

__all__ = [
    "MODEL_FREE", "MODEL_QUOTED", "TOOL", "SYSTEM", "PROVENANCE",
    "CHECK_STATES", "ACTION_KINDS", "ACTIONS_WITHOUT_TOKEN_COST",
    "By", "Decision", "Via", "Check", "Action", "Verdict",
    "model_free_fields", "changed_tokens",
    "render_rows", "register_signature", "BY_KEY",
    "decision_from_tool_evidence", "check_from_tristate",
    "MAX_IDENT_CHARS", "MAX_TEXT_CHARS",
    "json_schema", "tool_definition", "TOOL_NAME",
]

# -- the provenance ladder --------------------------------------------------

MODEL_FREE = "model_free"
MODEL_QUOTED = "model_quoted"
TOOL = "tool"
SYSTEM = "system"
PROVENANCE = (MODEL_FREE, MODEL_QUOTED, TOOL, SYSTEM)

# -- closed vocabularies ----------------------------------------------------

#: A check reads ``ok`` or ``fail``. Deliberately two-state, per the schema.
#: NOTE (V2-F3, escalated): ``face_review.py`` renders five statuses and RETINA's
#: receipt is TRI-state, with a ratified honesty rule that an inconclusive check
#: "MUST NOT render as a pass" (``face_review.py:56-64``). Two states cannot say
#: "inconclusive". ``check_from_tristate`` therefore maps unknown to ``fail``,
#: never to ``ok`` — lossy in the safe direction, and named rather than hidden.
CHECK_STATES = ("ok", "fail")

#: The three terminal acts are the ones the Review face already offers
#: (``face_review.py:325-334``); ``followup`` is the only kind that spends model
#: tokens, which is why it is the only kind a forecast may be attached to.
ACTION_KINDS = ("accept", "revert", "commit", "followup")
ACTIONS_WITHOUT_TOKEN_COST = ("accept", "revert", "commit")

#: Identifier-ish fields (``chose``, ``over``, ``mechanism``, ``tier``, labels)
#: are names, not prose. The ceiling is ``decision_log.MAX_CHOICE_CHARS``.
MAX_IDENT_CHARS = 48
#: Prose-ish fields that are NOT the free field (``because``, ``Check.text``).
#: The ceiling is ``decision_log.MAX_NOTE_CHARS``.
MAX_TEXT_CHARS = 96

_TIER_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
#: A sentence boundary INSIDE a name: a terminator followed by a space or the
#: end of the string. Deliberately not "any period" — real names carry dots
#: (``shot_010.exr``, ``gemini-3.5-flash``, ``0.01``) and rejecting those would
#: reject ``decision_log.choice_from_input``'s own output for ``file_path``.
_SENTENCE_IN_NAME = re.compile(r"[.!?](\s|$)")


# -- shared validators ------------------------------------------------------


def _clean(value, field):
    """A single-line string, or raise. ``None`` becomes ``""``."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("%s must be a str, got %s" % (field, type(value).__name__))
    if "\n" in value or "\r" in value:
        raise ValueError("%s must be a single line — the panel draws one row" % field)
    return value.strip()


def _bounded(value, field, limit):
    text = _clean(value, field)
    if len(text) > limit:
        raise ValueError("%s exceeds %d chars (%d)" % (field, limit, len(text)))
    return text


def _identifier(value, field):
    """A name, not a sentence — because a field that accepts a sentence is a
    second free field by the back door, and invariant 1 allows exactly one."""
    text = _bounded(value, field, MAX_IDENT_CHARS)
    if _SENTENCE_IN_NAME.search(text):
        raise ValueError("%s is a name, not a sentence — it may not end or break "
                         "on '.', '!' or '?' (got %r)" % (field, text))
    return text


def _provenance(value, field):
    if value not in PROVENANCE:
        raise ValueError("%s must be one of %r, got %r" % (field, PROVENANCE, value))
    if value == MODEL_FREE:
        # Invariant 1, enforced at the only place it can be broken.
        raise ValueError(
            "%s may not be MODEL_FREE — 'verdict' is the only field that renders "
            "a string the model wrote freely" % field)
    return value


def _count(value, field, whole=False):
    """A non-negative count, or ``None`` for NOT MEASURED.

    ``bool`` is refused explicitly: ``True`` is an ``int`` in Python and would
    silently become a count of 1, which is the exact shape of a number that
    travels without a producer.

    ``whole=True`` additionally refuses a float. Tokens are counted, not
    measured: ``tokens_in=1.9`` used to construct and then render through ``%d``
    as ``1``, so a wrong figure became a plausible one on the way to the screen
    (V2-F15). ``cost`` is genuinely fractional and stays a float.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("%s must be a number or None, not a bool" % field)
    if not isinstance(value, (int, float)):
        raise TypeError("%s must be a number or None, got %s"
                        % (field, type(value).__name__))
    if whole and not isinstance(value, int):
        raise TypeError("%s counts whole tokens — %r would be truncated on the "
                        "way to the row" % (field, value))
    if value < 0:
        raise ValueError("%s must be >= 0, got %r" % (field, value))
    return value


# -- the parts --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class By:
    """WHO did the work. The partner line. Never null, never anonymous.

    ``model`` is runtime data read off the live provider — it is not, and must
    not become, a constant in code (invariant: tier constants only). ``tier`` is
    the rotation-stable name; ``reason`` is the ROUTER's reason for picking this
    tier and carries SYSTEM provenance by construction, never the model's own
    account of itself.

    ``tier`` is shape-checked, not vocabulary-checked. The tier manifest is V3's
    (the probe layer) and does not exist yet; a closed set invented here would
    reject V3's names on the day it lands. Pass ``tier_vocabulary`` to
    ``validate_tier`` once the manifest is ratified. (V2-F2, escalated.)
    """

    model: str
    tier: str
    reason: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost: float | None = None

    def __post_init__(self):
        s = object.__setattr__
        model = _bounded(self.model, "by.model", MAX_IDENT_CHARS)
        if not model:
            raise ValueError("by.model is required — no anonymous work")
        tier = _bounded(self.tier, "by.tier", MAX_IDENT_CHARS)
        if not tier:
            raise ValueError("by.tier is required — no anonymous work")
        if not _TIER_RE.match(tier):
            raise ValueError(
                "by.tier must be a lowercase identifier (a rotation-stable "
                "constant), got %r" % tier)
        s(self, "model", model)
        s(self, "tier", tier)
        s(self, "reason", _bounded(self.reason, "by.reason", MAX_TEXT_CHARS))
        s(self, "tokens_in", _count(self.tokens_in, "by.tokens_in", whole=True))
        s(self, "tokens_out", _count(self.tokens_out, "by.tokens_out", whole=True))
        s(self, "cost", _count(self.cost, "by.cost"))

    def validate_tier(self, tier_vocabulary):
        """Raise unless ``tier`` is in a supplied closed set.

        Separate from construction on purpose: the contract can be enforced
        today, and the vocabulary bolted on the day a manifest exists, without
        either half waiting for the other.
        """
        if tier_vocabulary and self.tier not in tuple(tier_vocabulary):
            raise ValueError("by.tier %r not in the ratified manifest %r"
                             % (self.tier, tuple(tier_vocabulary)))
        return self

    def measured(self):
        """``True`` only when real usage was read. ``0`` counts; ``None`` does not."""
        return self.tokens_in is not None and self.tokens_out is not None


@dataclass(frozen=True, slots=True)
class Decision:
    """WHAT was chosen, WHAT it beat, and WHY — the credit row.

    ``chose`` and ``over`` are names (a material, a node type, a template), not
    sentences; ``because`` is the only prose-ish field, which is why
    ``provenance`` describes ``because``. ``MODEL_QUOTED`` means a sentence the
    model actually wrote was SELECTED verbatim (``decision_log.why_from_reasoning``
    — it never summarises and never supplies a default). ``TOOL`` means it was
    derived from what a tool did. ``SYSTEM`` means the panel composed it.
    """

    chose: str
    over: str = ""
    because: str = ""
    provenance: str = SYSTEM

    def __post_init__(self):
        s = object.__setattr__
        chose = _identifier(self.chose, "decision.chose")
        if not chose:
            raise ValueError("decision.chose is required — a decision with no "
                             "subject is not a decision")
        s(self, "chose", chose)
        s(self, "over", _identifier(self.over, "decision.over"))
        s(self, "because", _bounded(self.because, "decision.because", MAX_TEXT_CHARS))
        s(self, "provenance", _provenance(self.provenance, "decision.provenance"))


@dataclass(frozen=True, slots=True)
class Via:
    """HOW the change reached the scene: where it landed, and by what mechanism."""

    node_path: str = ""
    mechanism: str = ""

    def __post_init__(self):
        s = object.__setattr__
        path = _bounded(self.node_path, "via.node_path", MAX_TEXT_CHARS)
        if path and not path.startswith("/"):
            raise ValueError("via.node_path must be absolute, got %r" % path)
        if " " in path:
            raise ValueError("via.node_path must be one path, got %r" % path)
        s(self, "node_path", path)
        s(self, "mechanism", _identifier(self.mechanism, "via.mechanism"))


@dataclass(frozen=True, slots=True)
class Check:
    """One quality check. ``state`` is the schema's two-state ``ok``/``fail``."""

    state: str
    text: str
    ref: str = ""
    provenance: str = SYSTEM

    def __post_init__(self):
        s = object.__setattr__
        if self.state not in CHECK_STATES:
            raise ValueError("check.state must be one of %r, got %r"
                             % (CHECK_STATES, self.state))
        text = _bounded(self.text, "check.text", MAX_TEXT_CHARS)
        if not text:
            raise ValueError("check.text is required — a nameless check is a dot "
                             "with no claim behind it")
        s(self, "text", text)
        s(self, "ref", _identifier(self.ref, "check.ref"))
        s(self, "provenance", _provenance(self.provenance, "check.provenance"))


@dataclass(frozen=True, slots=True)
class Action:
    """One offered next step. Only ``followup`` spends model tokens, so only
    ``followup`` may carry a forecast — an ACCEPT that claims a token cost is
    reporting a spend that cannot happen."""

    label: str
    kind: str
    forecast_tokens: int | None = None

    def __post_init__(self):
        s = object.__setattr__
        if self.kind not in ACTION_KINDS:
            raise ValueError("action.kind must be one of %r, got %r"
                             % (ACTION_KINDS, self.kind))
        label = _identifier(self.label, "action.label")
        if not label:
            raise ValueError("action.label is required")
        forecast = _count(self.forecast_tokens, "action.forecast_tokens",
                          whole=True)
        if forecast is not None and self.kind in ACTIONS_WITHOUT_TOKEN_COST:
            raise ValueError(
                "action.forecast_tokens on kind %r — %r spends no model "
                "tokens" % (self.kind, self.kind))
        s(self, "label", label)
        s(self, "forecast_tokens", forecast)


# -- the whole object -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Verdict:
    """Everything the Review face renders, emitted by the agent, drawn by the panel.

    ``by`` is first and has no default. That is the enforcement: ``Verdict()``
    raises ``TypeError`` before any of this module's code runs.
    """

    by: By
    verdict: str = ""
    decision: Decision | None = None
    via: Via | None = None
    checks: tuple[Check, ...] = ()
    paths: tuple[str, ...] = ()
    actions: tuple[Action, ...] = ()

    def __post_init__(self):
        s = object.__setattr__
        if self.by is None:
            raise ValueError("Verdict.by is required — a verdict with no author "
                             "does not render")
        if not isinstance(self.by, By):
            raise TypeError("Verdict.by must be a By, got %s"
                            % type(self.by).__name__)
        # `verdict` is the ONE free field. It is length-checked by the voice
        # contract, not here: this module owns the shape, `voice_contract` owns
        # the register, and a ceiling enforced in two places drifts in one.
        s(self, "verdict", _clean(self.verdict, "verdict"))
        if self.decision is not None and not isinstance(self.decision, Decision):
            raise TypeError("Verdict.decision must be a Decision")
        if self.via is not None and not isinstance(self.via, Via):
            raise TypeError("Verdict.via must be a Via")
        s(self, "checks", _tuple_of(self.checks, Check, "checks"))
        s(self, "actions", _tuple_of(self.actions, Action, "actions"))
        paths = []
        for i, p in enumerate(self.paths or ()):
            path = _bounded(p, "paths[%d]" % i, MAX_TEXT_CHARS)
            if not path.startswith("/"):
                raise ValueError("paths[%d] must be absolute, got %r" % (i, path))
            if path not in paths:          # order-preserving de-dup
                paths.append(path)
        s(self, "paths", tuple(paths))

    def with_verdict(self, text):
        """A copy carrying a different free field. Used by the voice gate, which
        must be able to substitute the templated fallback without mutating an
        object other code already holds."""
        return replace(self, verdict=text)


def _tuple_of(items, cls, field):
    out = []
    for i, item in enumerate(items or ()):
        if not isinstance(item, cls):
            raise TypeError("%s[%d] must be a %s, got %s"
                            % (field, i, cls.__name__, type(item).__name__))
        out.append(item)
    return tuple(out)


# -- reading the invariant back off a built object --------------------------


def model_free_fields(verdict):
    """The names of fields on ``verdict`` carrying ``MODEL_FREE`` provenance.

    Invariant 1 says this must be exactly ``("verdict",)`` — and only when the
    free field is actually populated. The constructors refuse ``MODEL_FREE``
    anywhere else, so this reads back what they enforced; it exists so the
    invariant can be *checked from outside*, which is what makes it testable
    rather than merely asserted.
    """
    fields = []
    if verdict.verdict:
        fields.append("verdict")
    if verdict.decision is not None and verdict.decision.provenance == MODEL_FREE:
        fields.append("decision.because")          # pragma: no cover - unreachable
    for i, chk in enumerate(verdict.checks):
        if chk.provenance == MODEL_FREE:
            fields.append("checks[%d].text" % i)   # pragma: no cover - unreachable
    return tuple(fields)


def changed_tokens(verdict):
    """The vocabulary of THINGS THAT CHANGED, for the voice contract's
    "names the thing that changed" rule.

    Drawn only from structured fields — ``decision.chose``, the node path and its
    leaf, each touched path and its leaf. Never from ``verdict`` itself, which
    would let the free field satisfy the rule by quoting itself.
    """
    out = set()

    def add(text):
        text = (text or "").strip()
        if not text:
            return
        out.add(text.lower())
        leaf = text.rstrip("/").rsplit("/", 1)[-1]
        if leaf:
            out.add(leaf.lower())

    if verdict.decision is not None:
        add(verdict.decision.chose)
    if verdict.via is not None:
        add(verdict.via.node_path)
        add(verdict.via.mechanism)
    for path in verdict.paths:
        add(path)
    return frozenset(t for t in out if len(t) >= 3)


# -- the projection the panel draws -----------------------------------------

#: The BY row's key. ``register_signature`` masks this row and only this row.
BY_KEY = "BY"

_ROW_SEP = " · "


def render_rows(verdict):
    """The panel's draw list, as an ordered tuple of ``(key, value)`` pairs.

    A PURE function of ``verdict``: no clock, no locale, no dict iteration, no
    module state, and — the point of invariant 8 — **no branch on tier or model**.
    Two tiers handed the same structured object produce byte-identical rows.

    This is a projection, not a widget. Nothing here touches Qt, and nothing in
    the panel calls it yet: T.4's freeze holds until V3 lands. It exists now
    because an invariant about rendered output needs a rendering to assert on,
    and a suite that waits for the UI is a suite that arrives after the drift.
    """
    rows = []
    if verdict.verdict:
        rows.append(("VERDICT", verdict.verdict))

    d = verdict.decision
    if d is not None:
        value = d.chose
        if d.over:
            value += " over " + d.over
        if d.because:
            value += " — " + d.because
        rows.append(("DECISION", value))

    v = verdict.via
    if v is not None and (v.node_path or v.mechanism):
        rows.append(("VIA", _ROW_SEP.join(p for p in (v.node_path, v.mechanism) if p)))

    for chk in verdict.checks:
        value = chk.state + _ROW_SEP + chk.text
        if chk.ref:
            value += _ROW_SEP + chk.ref
        rows.append(("CHECK", value))

    for path in verdict.paths:
        rows.append(("PATH", path))

    rows.append((BY_KEY, _by_value(verdict.by)))

    for act in verdict.actions:
        value = act.label + _ROW_SEP + act.kind
        if act.forecast_tokens is not None:
            value += _ROW_SEP + "~%d tok" % act.forecast_tokens
        rows.append(("ACTION", value))

    return tuple(rows)


def _by_value(by):
    """``model · tier`` plus reason and, only when actually measured, usage.

    ``cost`` is carried by the contract and NOT rendered here. The panel's
    metering rule is "TOKENS ONLY, never $" (``synapse_panel.py:468``), and no
    usage reader is closed yet (E0-F12), so a cost row today would be a currency
    figure with no producer behind it. Carried, not drawn, and escalated (V2-F4)
    rather than dropped from the schema.
    """
    parts = [by.model, by.tier]
    if by.reason:
        parts.append(by.reason)
    if by.measured():
        parts.append("%d/%d tok" % (by.tokens_in, by.tokens_out))
    return _ROW_SEP.join(parts)


def register_signature(verdict):
    """``render_rows`` with the BY row's VALUE masked — the register itself.

    Invariant 8 is about the *register*, and the author line is the one row that
    is *supposed* to change when the tier changes. Masking it leaves exactly the
    thing that must not: row order, keys, separators, and every composed value.
    The BY row is kept as a key with a masked value so that a renderer which
    *drops* the author line is still caught.
    """
    return tuple((k, "<by>" if k == BY_KEY else v) for k, v in render_rows(verdict))


# -- reconciling the two credit producers that already exist ----------------


def decision_from_tool_evidence(tool_name, detail="", chose=""):
    """A ``Decision`` in the shape ``synapse_panel::_turn_evidence`` produces.

    ``_turn_evidence`` emits ``("DECISION", tool_name, detail)`` from what a tool
    DID — honest, and weaker than a quote, because it reports the effect rather
    than the choice. Tagging it ``TOOL`` is what keeps that distinction readable
    downstream instead of letting it blur into ``decision_log``'s quoted rows.

    Neither producer replaces the other; both land in the same typed field with
    their source recorded. See ``decision_log.Decision.to_verdict_decision`` for
    the quoted half.
    """
    name = (chose or tool_name or "").strip()
    if not name:
        raise ValueError("tool evidence with no tool name credits nothing")
    return Decision(
        chose=name[:MAX_IDENT_CHARS].rstrip(".!?"),
        because=(detail or "").strip()[:MAX_TEXT_CHARS],
        provenance=TOOL,
    )


# -- the wire form ----------------------------------------------------------

TOOL_NAME = "emit_verdict"


def json_schema():
    """The contract as JSON Schema — the shape the agent emits against.

    Generated from the same constants the dataclasses validate with, so the wire
    form and the enforced form cannot drift apart. ``tests`` pins the property
    names against the dataclass fields; a field added to one and not the other
    turns that test red.

    **``by`` is NOT in this schema, and its absence is the point (V2-F13).** The
    first draft required the model to emit its own author block — its own model
    id, its own tier, 96 characters of free-text ``reason``, and its own token
    counts — every one of which renders. That is a model writing its own credit
    line while the tool description says *"you write only `verdict`"*, and a
    second free field arriving through the one door invariant 1 was built to
    watch. ``by`` is SYSTEM data: the panel knows which provider it called and
    what the router decided, and asking the model to report it would be taking a
    witness's word for the witness's identity.

    This is also the thing that replaces register instruction in the system
    prompt, and it is not free — ``harness/notes/econ/v2_prompt_delta.py``
    measures what it costs so the before/after is a NET figure rather than a
    cherry-picked saving.
    """
    # Imported at CALL time, not module level: ``voice_contract`` imports this
    # module. A hardcoded 140 here would be a second authority on the ceiling,
    # and two authorities on one number is how a value drifts in silence.
    from synapse.panel.voice_contract import MAX_VERDICT_CHARS

    return {
        "type": "object",
        "required": ["verdict"],
        "additionalProperties": False,
        "properties": {
            "verdict": {
                "type": "string",
                "maxLength": MAX_VERDICT_CHARS,
                "description": ("ONE sentence. Outcome first, cause second. Name "
                                "the thing that changed. No preamble, no hedging, "
                                "no restating the request. Max %d characters."
                                % MAX_VERDICT_CHARS),
            },
            "decision": {
                "type": ["object", "null"],
                "required": ["chose"],
                "additionalProperties": False,
                "properties": {
                    "chose": {"type": "string", "maxLength": MAX_IDENT_CHARS},
                    "over": {"type": "string", "maxLength": MAX_IDENT_CHARS},
                    "because": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                    "provenance": {"type": "string",
                                   "enum": [p for p in PROVENANCE if p != MODEL_FREE]},
                },
            },
            "via": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "properties": {
                    "node_path": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                    "mechanism": {"type": "string", "maxLength": MAX_IDENT_CHARS},
                },
            },
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["state", "text"],
                    "additionalProperties": False,
                    "properties": {
                        "state": {"type": "string", "enum": list(CHECK_STATES)},
                        "text": {"type": "string", "maxLength": MAX_TEXT_CHARS},
                        "ref": {"type": "string", "maxLength": MAX_IDENT_CHARS},
                        "provenance": {
                            "type": "string",
                            "enum": [p for p in PROVENANCE if p != MODEL_FREE]},
                    },
                },
            },
            # Constrained to what the constructor enforces. An unconstrained
            # array here invited a payload the schema blessed and `Verdict`
            # then rejected — the gap where an agent emits something valid and
            # the panel explodes on it (V2-F14).
            "paths": {
                "type": "array",
                "items": {"type": "string", "pattern": "^/",
                          "minLength": 2, "maxLength": MAX_TEXT_CHARS},
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["label", "kind"],
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string", "maxLength": MAX_IDENT_CHARS},
                        "kind": {"type": "string", "enum": list(ACTION_KINDS)},
                        "forecast_tokens": {"type": ["integer", "null"], "minimum": 0},
                    },
                },
            },
        },
    }


def tool_definition():
    """The contract as an Anthropic tool definition.

    Structured output on this path is a tool call, so the schema is priced as a
    tool definition — the same place the 19,711-token surface E0 measured lives.
    """
    return {
        "name": TOOL_NAME,
        "description": ("Report the finished work as structure. The panel draws "
                        "the rows; you write only `verdict`."),
        "input_schema": json_schema(),
    }


def check_from_tristate(passed, text, ref=""):
    """A ``Check`` from RETINA's tri-state ``pass`` field.

    ``True`` -> ``ok``. ``False`` -> ``fail``. **``None`` (inconclusive) ->
    ``fail``**, never ``ok``: the schema has two states and the ratified honesty
    rule is that an inconclusive check must not render as a pass
    (``face_review.py:56-64``). The mapping is lossy and it is lossy in the safe
    direction. That the schema cannot say "inconclusive" is V2-F3, escalated.
    """
    return Check(state="ok" if passed is True else "fail", text=text, ref=ref)
