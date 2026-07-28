"""V2 · THE VOICE CONTRACT — mechanically checkable rules on the one free field.

``verdict.Verdict`` has exactly one field the model writes freely. This module is
what stops that field from being the hole the whole contract leaks through.

WHY A VALIDATOR AND NOT AN INSTRUCTION
--------------------------------------
Register instruction in a system prompt is a *request*. A strong model honours it,
a weak model approximates it, and nothing anywhere reports the difference — which
is exactly the failure class the project already knows by name: a check that
cannot fail, reporting healthy, continuously (Law 1). A validator that rejects and
re-asks converts a request into a floor. **A weak model must not be able to
produce a weak panel.**

THE RULES, AND WHAT MAKES EACH ONE FAIL
---------------------------------------
Every rule below states the condition under which it fires, because a rule that
cannot be shown failing is a decoration that will later be cited as evidence
(R127 / R131). ``tests/test_v2_voice_contract.py`` demonstrates each one firing
AND staying silent on a conforming verdict, and
``harness/notes/econ/v2_mutation_test.py`` breaks each rule in turn and asserts
the control goes red — so the controls are pinned to something too (R133).

    not_empty         the model returned nothing where a verdict was required
    one_sentence      a second sentence starts inside the field
    char_ceiling      longer than the panel's own 140-char measure
    outcome_first     the sentence opens on the cause, not the outcome
    names_change      no word from the structured object appears in the sentence
    no_preamble       opens on the agent, the acknowledgement, or the request
    no_hedging        carries a hedge, a maybe, or a "let me know"
    no_request_echo   restates the artist's own words back at them
    no_decoration     markdown, code fences or markup in a plain-text row
    not_a_question    a verdict that asks something is not a verdict

THE FALLBACK IS THE LOAD-BEARING HALF
-------------------------------------
Three rejections and the free field is abandoned: the verdict is TEMPLATED from
``decision``, which is structured, panel-composed, and identical for every tier.
That is what makes invariant 8 survivable in the worst case rather than only in
the best one — when two tiers write differently badly, they converge on the same
bytes instead of on two different kinds of wrong.

The fallback never invents. It composes only fields already present on the
object, it is validated by the same rules it is protecting, and when there is
nothing structured to compose from it returns ``""`` — the same posture
``decision_log.why_from_reasoning`` takes when a turn carried no prose. An empty
verdict row is honest. A plausible substitute is a provenance claim nobody can
check.

Pure Python: no Qt, no ``hou``, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from synapse.panel.verdict import changed_tokens

__all__ = [
    "MAX_VERDICT_CHARS", "MAX_ATTEMPTS",
    "Violation", "VoiceResult", "VoiceRule", "VOICE_RULES", "RULE_IDS",
    "validate", "reask_directive", "fallback_verdict",
    "GateOutcome", "VoiceGate",
]

#: The panel already truncates the verdict at 140 characters
#: (``synapse_panel.py:1220-1224``) into a 360px-wide 21px display label
#: (``face_review.py:224-226``). The ceiling is that measure, made a rule instead
#: of a silent trim — a trim hides the violation, a rule reports it.
MAX_VERDICT_CHARS = 140

#: "Three failures -> fall back." The count is the whole budget: each re-ask is a
#: full API call carrying the entire tools array (E0's k, ``claude_worker.py:153``),
#: so an unbounded re-ask loop is an unbounded bill.
MAX_ATTEMPTS = 3


# -- results ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule. ``detail`` names the offending text, never a paraphrase."""

    rule: str
    detail: str


@dataclass(frozen=True, slots=True)
class VoiceResult:
    """The verdict on a verdict.

    ``skipped`` is not a courtesy field. A rule that could not run (no structured
    object to check against, no request to compare with) is recorded as skipped
    so that "zero violations" can never be read as "every rule was enforced".
    Law 3: this reports what happened, not what was attempted.
    """

    text: str
    violations: tuple[Violation, ...] = ()
    skipped: tuple[str, ...] = ()

    @property
    def ok(self):
        return not self.violations

    def rules_broken(self):
        return tuple(v.rule for v in self.violations)


@dataclass(frozen=True, slots=True)
class VoiceRule:
    """One rule, its reason, and the condition under which it fires."""

    id: str
    fails_when: str
    check: object          # (text, verdict, request) -> Violation | None | "skip"

    def __call__(self, text, verdict, request):
        return self.check(text, verdict, request)


#: Sentinel a rule returns when it could not run at all.
SKIP = "skip"


# -- vocabularies -----------------------------------------------------------

# A new sentence starts after a terminator, whitespace, and an opening capital.
# Requiring the capital keeps "0.01 roughness" and "e.g. the dome" from firing.
_SENTENCE_BREAK = re.compile(r"[.!?][\"')\]]?\s+(?=[A-Z\"'(\[])")
# ...but "e.g. Karma" would still fire, so known abbreviations are excused by the
# token that precedes the terminator.
_ABBREVIATIONS = frozenset({
    "e.g.", "i.e.", "vs.", "etc.", "approx.", "no.", "fig.", "cf.",
    "dr.", "mr.", "mrs.", "ms.", "st.", "ca.", "al.",
})

_LEADING_CAUSE = re.compile(
    r"^\W*\b(because|since|as|after|when|whenever|while|whilst|given|due|owing|"
    r"following|once|upon|although|though|if|in\s+order|so\s+that)\b", re.I)

_PREAMBLE = re.compile(
    r"^\W*\b(i|i'?ve|i'?ll|i'?m|we|we'?ve|we'?ll|let\s+me|let'?s|here'?s|here\s+is|"
    r"sure|certainly|absolutely|okay|ok|alright|great|perfect|done|happy\s+to|"
    r"of\s+course|no\s+problem|as\s+requested|as\s+you\s+requested|you\s+asked|"
    r"per\s+your\s+request|to\s+answer|got\s+it|understood|thanks|just|simply)\b",
    re.I)

_HEDGE = re.compile(
    r"\b(should|shouldn'?t|might|maybe|perhaps|probably|possibly|hopefully|"
    r"i\s+think|i\s+believe|seems?|appears?\s+to|appear\s+to|try\s+to|trying\s+to|"
    r"tried\s+to|attempt(?:ed|s)?\s+to|let\s+me\s+know|if\s+you\s+(?:want|like|'?d)|"
    r"roughly|sort\s+of|kind\s+of|more\s+or\s+less|ish|as\s+far\s+as|"
    r"in\s+theory|for\s+now|hopefully)\b", re.I)

_DECORATION = re.compile(r"(`|\*\*|__|~~|^\s*#|^\s*[-*+]\s|\[[^\]]*\]\([^)]*\)|</?[a-zA-Z])")

#: Stopwords for the request-echo overlap. Deliberately small: the rule is about
#: an artist's *content* words coming back verbatim, not about grammar.
_STOP = frozenset("""
a an and are as at be been but by can could did do does for from get give go
has have how i if in into is it its just make me my not of on or our out over
please put set so than that the their them then there these they this to too
under up use used using want was we were what when where which who will with
would you your
""".split())

#: Overlap at or above this fraction of the verdict's content words means the
#: verdict is the request wearing a full stop.
ECHO_RATIO = 0.6


def _words(text):
    return tuple(w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_']*", text or ""))


def _content_words(text):
    return frozenset(w.lower() for w in _words(text)
                     if len(w) >= 3 and w.lower() not in _STOP)


# -- the rules --------------------------------------------------------------


def _not_empty(text, verdict, request):
    if not (text or "").strip():
        return Violation("not_empty", "the free field is empty")
    return None


def _one_sentence(text, verdict, request):
    body = (text or "").strip()
    if not body:
        return None                      # not_empty owns that case
    for m in _SENTENCE_BREAK.finditer(body):
        preceding = body[:m.start() + 1].rsplit(" ", 1)[-1].lower()
        if preceding in _ABBREVIATIONS:
            continue
        return Violation("one_sentence",
                         "a second sentence starts at %r" % body[m.end():m.end() + 32])
    return None


def _char_ceiling(text, verdict, request):
    body = (text or "").strip()
    if len(body) > MAX_VERDICT_CHARS:
        return Violation("char_ceiling",
                         "%d chars, ceiling is %d" % (len(body), MAX_VERDICT_CHARS))
    return None


def _outcome_first(text, verdict, request):
    body = (text or "").strip()
    m = _LEADING_CAUSE.match(body)
    if m:
        return Violation("outcome_first",
                         "opens on the cause: %r" % m.group(1))
    return None


def _names_change(text, verdict, request):
    """The strongest rule, and the only one that needs the structured object.

    Skipped — never silently passed — when the object names nothing that changed,
    because a turn that altered nothing has nothing for the sentence to name.
    """
    if verdict is None:
        return SKIP
    tokens = changed_tokens(verdict)
    if not tokens:
        return SKIP
    for tok in tokens:
        if re.search(r"(?<![\w/])" + re.escape(tok) + r"(?!\w)", text or "", re.I):
            return None
    return Violation("names_change",
                     "names none of %s" % ", ".join(sorted(tokens)[:6]))


def _no_preamble(text, verdict, request):
    m = _PREAMBLE.match((text or "").strip())
    if m:
        return Violation("no_preamble", "opens on %r" % m.group(1))
    return None


def _no_hedging(text, verdict, request):
    m = _HEDGE.search(text or "")
    if m:
        return Violation("no_hedging", "hedges on %r" % m.group(0))
    return None


def _no_request_echo(text, verdict, request):
    if not (request or "").strip():
        return SKIP
    said = _content_words(text)
    asked = _content_words(request)
    if not said or not asked:
        return SKIP
    shared = said & asked
    ratio = len(shared) / len(said)
    if ratio >= ECHO_RATIO:
        return Violation("no_request_echo",
                         "%d%% of its content words are the request's"
                         % round(ratio * 100))
    return None


def _no_decoration(text, verdict, request):
    if "\n" in (text or "") or "\r" in (text or ""):
        return Violation("no_decoration", "carries a line break")
    m = _DECORATION.search(text or "")
    if m:
        return Violation("no_decoration", "carries markup %r" % m.group(0))
    return None


def _not_a_question(text, verdict, request):
    if "?" in (text or ""):
        return Violation("not_a_question", "asks rather than states")
    return None


VOICE_RULES = (
    VoiceRule("not_empty",
              "the model returned nothing where a verdict was required",
              _not_empty),
    VoiceRule("one_sentence",
              "a second sentence begins inside the field",
              _one_sentence),
    VoiceRule("char_ceiling",
              "the text is longer than the panel's 140-char measure",
              _char_ceiling),
    VoiceRule("outcome_first",
              "the sentence opens on a causal connective instead of the outcome",
              _outcome_first),
    VoiceRule("names_change",
              "no name from the structured object appears in the sentence",
              _names_change),
    VoiceRule("no_preamble",
              "the sentence opens on the agent, an acknowledgement, or the ask",
              _no_preamble),
    VoiceRule("no_hedging",
              "the sentence carries a hedge, a maybe, or a 'let me know'",
              _no_hedging),
    VoiceRule("no_request_echo",
              "most of the sentence's content words are the artist's own",
              _no_request_echo),
    VoiceRule("no_decoration",
              "markdown or markup in a row the panel draws as plain text",
              _no_decoration),
    VoiceRule("not_a_question",
              "the field contains a question mark",
              _not_a_question),
)

RULE_IDS = tuple(r.id for r in VOICE_RULES)


# -- the validator ----------------------------------------------------------


def validate(text, verdict=None, request=None, rules=None):
    """Check one free-field string against the contract.

    ``verdict`` is the structured object the sentence is supposed to be about —
    without it, ``names_change`` cannot run and is reported as SKIPPED rather
    than quietly counted as a pass. ``request`` is the artist's message, needed
    only by ``no_request_echo``.

    ``rules`` resolves ``VOICE_RULES`` at CALL time, not at import time. A
    default argument would snapshot the table when this module loads, leaving
    two authorities on what the rules are — the shape that made a panel line
    render one of two different blues depending on which import it reached
    (``panel/tokens.py``). It is also what made every rule un-mutatable: the
    first run of ``v2_mutation_test.py`` neutered all ten and the suite stayed
    green, because nothing it changed was ever read (V2-F1).
    """
    violations, skipped = [], []
    for rule in (VOICE_RULES if rules is None else rules):
        outcome = rule(text, verdict, request)
        if outcome is SKIP:
            skipped.append(rule.id)
        elif outcome is not None:
            violations.append(outcome)
    return VoiceResult(text=text or "",
                       violations=tuple(violations),
                       skipped=tuple(skipped))


def reask_directive(result):
    """The correction sent back to the model. Terse on purpose — every re-ask is
    a whole extra API call carrying the entire tools array, so the instruction
    that fixes the sentence must not itself cost a paragraph."""
    if result.ok:
        return ""
    fixes = {r.id: r.fails_when for r in VOICE_RULES}
    lines = ["Rewrite the verdict. One sentence, outcome first, "
             "under %d characters, naming what changed." % MAX_VERDICT_CHARS]
    for v in result.violations:
        lines.append("- %s: %s" % (v.rule, v.detail or fixes.get(v.rule, "")))
    return "\n".join(lines)


# -- the templated fallback -------------------------------------------------


def fallback_verdict(verdict, request=None):
    """A verdict composed from ``decision`` — the panel's words, not the model's.

    Candidates are tried richest first and the first one that passes the contract
    wins, so a poisoned ``because`` (a hedge quoted out of the model's prose)
    degrades the template instead of smuggling the hedge past the gate it just
    failed.

    A pure function of ``verdict.decision``: the same decision yields the same
    bytes on every tier, which is what invariant 8 rests on when the free field
    has been abandoned.

    Returns ``""`` when there is nothing structured to compose from. That case is
    real and it is honest — see the module docstring.
    """
    d = getattr(verdict, "decision", None)
    if d is None or not d.chose:
        return ""
    candidates = []
    if d.over and d.because:
        candidates.append("%s over %s — %s" % (d.chose, d.over, d.because))
    if d.because:
        candidates.append("%s — %s" % (d.chose, d.because))
    if d.over:
        candidates.append("%s over %s" % (d.chose, d.over))
    candidates.append(d.chose)
    for text in candidates:
        if validate(text, verdict, request).ok:
            return text
    return ""


# -- the gate ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """What the gate decided about one submission.

    ``accepted`` means a verdict is FINAL and renderable. ``source`` says whose
    words they are — ``model`` (the free field survived), ``fallback`` (three
    rejections, templated from ``decision``), or ``empty`` (three rejections and
    nothing structured to template from, so the row is left out).
    """

    accepted: bool
    text: str
    source: str
    result: VoiceResult
    attempts: int
    reask: str = ""

    @property
    def exhausted(self):
        return self.source in ("fallback", "empty")


class VoiceGate:
    """Reject-and-re-ask on the free field, with a hard floor under it.

    Three failures and the model loses the field: ``submit`` returns the
    templated fallback and every later submission returns the same bytes. The
    gate is deliberately a small state machine rather than a loop, so the caller
    keeps the API call and the gate keeps the counting — the thing being budgeted
    is round-trips, and a component that owns both tends to hide one.
    """

    def __init__(self, verdict, request=None, max_attempts=MAX_ATTEMPTS):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._verdict = verdict
        self._request = request
        self._max_attempts = int(max_attempts)
        self._attempts = 0
        self._final = None

    @property
    def attempts(self):
        return self._attempts

    @property
    def max_attempts(self):
        return self._max_attempts

    @property
    def exhausted(self):
        return self._final is not None

    def submit(self, text):
        """Offer one candidate free field. Returns a ``GateOutcome``."""
        if self._final is not None:
            return self._final                    # idempotent after the floor
        self._attempts += 1
        result = validate(text, self._verdict, self._request)
        if result.ok:
            return GateOutcome(True, result.text, "model", result, self._attempts)
        if self._attempts < self._max_attempts:
            return GateOutcome(False, "", "rejected", result, self._attempts,
                               reask=reask_directive(result))
        templated = fallback_verdict(self._verdict, self._request)
        self._final = GateOutcome(
            True, templated, "fallback" if templated else "empty",
            result, self._attempts)
        return self._final

    def resolve(self, verdict=None):
        """The ``Verdict`` carrying whatever the gate settled on.

        ``verdict`` defaults to the object the gate was built around. Callers get
        a new frozen object rather than a mutated one, because the gate must not
        be able to edit something another surface is already holding.
        """
        target = verdict if verdict is not None else self._verdict
        text = self._final.text if self._final is not None else target.verdict
        return target.with_verdict(text)
