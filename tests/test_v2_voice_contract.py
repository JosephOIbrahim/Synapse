"""V2 · the voice contract as a VALIDATOR — demonstrated failing, rule by rule.

R127/R131: a control suite that has never been shown failing is a decoration
that will later be cited as evidence. So every rule in ``VOICE_RULES`` gets a
string that fires it and the same conforming sentence that does not, and
``test_every_rule_is_demonstrated_firing`` asserts the demonstration set covers
the rule set — adding a rule without showing it fail turns this file red.

The other half is the floor: three rejections and the free field is abandoned for
a verdict templated from ``decision``. That is what stops a weak model producing
a weak panel, and it is demonstrated firing on the third rejection, not the
second and not the fourth.
"""

import pytest

from synapse.panel import voice_contract as vc
from synapse.panel.verdict import By, Decision, Verdict, Via

GOOD = "Dark_Glass now drives the shader, matched to the scene IOR."


def a_verdict(**kw):
    kw.setdefault("by", By(model="claude-sonnet-4-6", tier="workhorse"))
    kw.setdefault("verdict", GOOD)
    kw.setdefault("decision", Decision(chose="Dark_Glass", over="Diamond",
                                       because="closer to scene IOR"))
    kw.setdefault("via", Via(node_path="/stage/matlib",
                             mechanism="synapse_solaris_build_graph"))
    return Verdict(**kw)


#: (rule id, the offending free field, the request it is checked against).
#: One row per rule. ``test_every_rule_is_demonstrated_firing`` pins the coverage.
FIRING_CASES = [
    ("not_empty", "", None),
    ("one_sentence", "Dark_Glass now drives the shader. The IOR matches the scene.", None),
    ("char_ceiling", "Dark_Glass now drives the shader across every prim in the stage, "
                     "matched to the scene IOR and rewired ahead of the render so the "
                     "lookdev pass reads correctly", None),
    ("outcome_first", "Because the scene IOR is 1.52, Dark_Glass now drives the shader", None),
    ("names_change", "The look is dialled in and reading correctly now", None),
    ("no_preamble", "I've swapped Dark_Glass onto the shader", None),
    ("no_hedging", "Dark_Glass should now drive the shader", None),
    ("no_request_echo", "Dark_Glass material swapped on the glass",
     "swap the material on the glass to Dark_Glass"),
    ("no_decoration", "`Dark_Glass` now drives the shader", None),
    ("not_a_question", "Dark_Glass now drives the shader?", None),
]


@pytest.mark.parametrize("rule_id,text,request_text", FIRING_CASES,
                         ids=[c[0] for c in FIRING_CASES])
def test_each_rule_fires_on_its_own_violation(rule_id, text, request_text):
    """FAILS IF: a rule cannot be made to fire. That is the whole test — a rule
    nobody has seen reject is not a check, it is a decoration (Law 1)."""
    result = vc.validate(text, a_verdict(), request_text)
    assert rule_id in result.rules_broken(), \
        "%s did not fire on %r (fired: %s)" % (rule_id, text, result.rules_broken())
    assert not result.ok


@pytest.mark.parametrize("rule_id,text,request_text", FIRING_CASES,
                         ids=[c[0] for c in FIRING_CASES])
def test_no_rule_fires_on_a_conforming_verdict(rule_id, text, request_text):
    """FAILS IF: a rule has a false positive. A validator that rejects good
    output teaches the model to write worse, not better."""
    result = vc.validate(GOOD, a_verdict(), "make the glass read like dark glass")
    assert rule_id not in result.rules_broken()
    assert result.ok, result.violations


def test_every_rule_is_demonstrated_firing():
    """FAILS IF: a rule is added without a demonstration. The coverage claim is
    an assertion, not a promise kept by whoever edits next."""
    assert {c[0] for c in FIRING_CASES} == set(vc.RULE_IDS)


def test_the_conforming_verdict_really_is_conforming():
    result = vc.validate(GOOD, a_verdict(), "make the glass read like dark glass")
    assert result.ok and result.violations == () and result.skipped == ()


# -- rules that cannot always run say so ------------------------------------


def test_names_change_skips_rather_than_passes_without_a_structured_object():
    """FAILS IF: 'zero violations' can mean 'the rule never ran'. Law 3 — this
    reports what happened, not what was attempted."""
    result = vc.validate("The look is dialled in", verdict=None)
    assert "names_change" in result.skipped
    assert "names_change" not in result.rules_broken()


def test_names_change_skips_when_the_object_names_nothing_that_changed():
    """FAILS IF: the rule invents a vocabulary for a turn that changed nothing.
    A verdict about a read-only turn has nothing structured to name."""
    bare = Verdict(by=By(model="claude-sonnet-4-6", tier="workhorse"))
    assert "names_change" in vc.validate("The stage is clean", bare).skipped


def test_names_change_accepts_a_path_leaf_not_only_the_full_path():
    """FAILS IF: the rule demands a full node path in a 140-char sentence. The
    leaf is what an artist recognises; the vocabulary carries both."""
    assert vc.validate("matlib now carries Dark_Glass", a_verdict()).ok


def test_names_change_sees_a_name_written_inside_its_own_path():
    """FAILS IF: the lookbehind excludes '/'. A verdict that names the change by
    writing its full path was rejected for naming it too precisely — the rule
    refusing the most specific form of exactly what it asks for (V2-F11)."""
    v = Verdict(by=By(model="claude-sonnet-4-6", tier="workhorse"),
                decision=Decision(chose="dome_light"))
    assert vc.validate("/lights/dome_light now carries the studio HDRI", v).ok
    assert vc.validate("Exposure on /lights/dome_light holds at 0.25", v).ok


def test_names_change_still_refuses_a_name_buried_in_a_longer_word():
    """FAILS IF: loosening the lookbehind let a substring match. 'dome_lighting'
    is not 'dome_light'."""
    v = Verdict(by=By(model="claude-sonnet-4-6", tier="workhorse"),
                decision=Decision(chose="dome_light"))
    assert "names_change" in vc.validate("The dome_lighting reads warm", v).rules_broken()


def test_no_request_echo_skips_without_a_request():
    assert "no_request_echo" in vc.validate(GOOD, a_verdict()).skipped


def test_a_skipped_rule_is_not_counted_as_a_pass_anywhere():
    """FAILS IF: ``ok`` is computed from skips. ``ok`` means no violations; the
    skip list is how a caller learns the coverage was partial."""
    result = vc.validate(GOOD, a_verdict())
    assert result.ok and result.skipped == ("no_request_echo",)


# -- the rules that are easy to get subtly wrong ---------------------------


@pytest.mark.parametrize("text", [
    "Roughness now reads 0.01 across the shader",
    "Karma XPU renders the stage at 1.52 IOR",
    "Dark_Glass drives the shader, e.g. the dome and the key",
])
def test_a_decimal_or_abbreviation_is_not_a_second_sentence(text):
    """FAILS IF: the sentence splitter fires on ``0.01`` or ``e.g.``. A splitter
    that rejects real numbers makes every numeric verdict fall back."""
    assert "one_sentence" not in vc.validate(text, a_verdict()).rules_broken()


def test_a_terminal_period_is_not_a_second_sentence():
    assert "one_sentence" not in vc.validate(GOOD, a_verdict()).rules_broken()


def test_the_ceiling_is_the_panels_own_measure():
    """FAILS IF: the ceiling drifts from the 140 the panel already truncates at
    (``synapse_panel.py:1220-1224``). Two ceilings is one silent trim."""
    assert vc.MAX_VERDICT_CHARS == 140
    assert vc.validate("D" * 140 + "ark_Glass", a_verdict()).rules_broken()
    assert "char_ceiling" not in vc.validate(
        "Dark_Glass " + "x" * (140 - len("Dark_Glass ")), a_verdict()).rules_broken()


def test_a_violation_names_the_offending_text_not_a_paraphrase():
    """FAILS IF: the re-ask says 'style issue'. The model has to be told what to
    change, in its own words, or the next attempt is a coin flip."""
    result = vc.validate("Dark_Glass should now drive the shader", a_verdict())
    assert "should" in result.violations[0].detail


# -- the re-ask -------------------------------------------------------------


def test_the_reask_is_empty_on_a_conforming_verdict():
    assert vc.reask_directive(vc.validate(GOOD, a_verdict())) == ""


def test_the_reask_names_every_broken_rule():
    result = vc.validate("I've probably fixed it. Maybe?", a_verdict())
    directive = vc.reask_directive(result)
    for rule in result.rules_broken():
        assert rule in directive


# -- the templated fallback -------------------------------------------------


def test_the_fallback_fires_on_the_third_rejection_and_not_before():
    """FAILS IF: the floor arrives early (a model that would have got it right on
    attempt 3 never does) or late (an unbounded re-ask loop is an unbounded bill,
    since each re-ask is a full request carrying the whole tools array)."""
    gate = vc.VoiceGate(a_verdict())
    first = gate.submit("I've probably done it")
    second = gate.submit("Maybe it works now?")
    assert (first.accepted, second.accepted) == (False, False)
    assert (first.source, second.source) == ("rejected", "rejected")
    third = gate.submit("Should be fine")
    assert third.accepted and third.source == "fallback"
    assert third.attempts == 3
    assert third.text == "Dark_Glass over Diamond — closer to scene IOR"


def test_a_model_that_recovers_on_the_third_attempt_keeps_its_words():
    """FAILS IF: the gate stops listening before its own budget is spent."""
    gate = vc.VoiceGate(a_verdict())
    gate.submit("I've probably done it")
    gate.submit("Maybe it works now?")
    outcome = gate.submit(GOOD)
    assert outcome.accepted and outcome.source == "model" and outcome.text == GOOD


def test_a_conforming_first_attempt_costs_no_re_ask():
    gate = vc.VoiceGate(a_verdict())
    outcome = gate.submit(GOOD)
    assert outcome.accepted and outcome.attempts == 1 and outcome.reask == ""


def test_the_gate_is_idempotent_once_the_floor_is_reached():
    """FAILS IF: a caller can keep submitting past the floor and get a different
    answer each time. The budget is spent; the bytes are settled."""
    gate = vc.VoiceGate(a_verdict(), max_attempts=1)
    first = gate.submit("I've probably done it")
    assert first.source == "fallback" and gate.exhausted
    assert gate.submit(GOOD) is first


def test_the_fallback_refuses_to_smuggle_a_hedge_it_just_rejected():
    """FAILS IF: a poisoned ``because`` rides into the fallback. The template is
    validated by the same rules it is protecting, so a quoted hedge degrades the
    template instead of passing the gate it failed."""
    v = a_verdict(decision=Decision(chose="Dark_Glass", over="Diamond",
                                    because="it should probably match"))
    assert vc.fallback_verdict(v) == "Dark_Glass over Diamond"


def test_the_fallback_degrades_all_the_way_to_the_choice_alone():
    v = a_verdict(decision=Decision(chose="Dark_Glass",
                                    because="it should probably match"))
    assert vc.fallback_verdict(v) == "Dark_Glass"


def test_the_fallback_is_empty_when_there_is_nothing_structured_to_compose():
    """FAILS IF: the panel invents a verdict. An empty row is honest; a plausible
    substitute is a provenance claim nobody can check — the same posture
    ``decision_log.why_from_reasoning`` takes on a turn that carried no prose."""
    v = a_verdict(decision=None)
    assert vc.fallback_verdict(v) == ""
    gate = vc.VoiceGate(v, max_attempts=1)
    outcome = gate.submit("I've probably done it")
    assert outcome.accepted and outcome.source == "empty" and outcome.text == ""


def test_the_fallback_passes_the_contract_it_was_built_to_satisfy():
    """FAILS IF: the floor is below the bar. A fallback that violates the voice
    contract is a second register, not a floor under the first."""
    text = vc.fallback_verdict(a_verdict())
    assert vc.validate(text, a_verdict()).ok


def test_resolve_returns_a_verdict_carrying_the_settled_text():
    gate = vc.VoiceGate(a_verdict(), max_attempts=1)
    gate.submit("I've probably done it")
    resolved = gate.resolve()
    assert resolved.verdict == "Dark_Glass over Diamond — closer to scene IOR"
    assert resolved.by.model == "claude-sonnet-4-6"


# -- the accept path must latch too (V2-F10) --------------------------------
#
# The fixture below deliberately carries a BAD free field. The original tests
# built the gate around a verdict already holding the good sentence and then
# submitted that same sentence, so `resolve()` returning the pre-gate field was
# indistinguishable from it returning the accepted one. Both sides were equal by
# fixture. Four independent reviewers reproduced the defect the fixture hid.

REJECTED_FIRST_DRAFT = "I've probably swapped Dark_Glass in, let me know?"


def a_verdict_with_bad_prose():
    return a_verdict(verdict=REJECTED_FIRST_DRAFT)


def test_resolve_returns_the_accepted_rewrite_not_the_rejected_draft():
    """FAILS IF: acceptance does not latch. This is the canonical loop the gate
    exists for — reject, the model rewrites, the gate accepts — and it used to
    render the string the gate had just REJECTED, violations intact."""
    v = a_verdict_with_bad_prose()
    gate = vc.VoiceGate(v)
    first = gate.submit(v.verdict)
    assert not first.accepted
    second = gate.submit(GOOD)
    assert second.accepted and second.source == "model"
    assert gate.resolve().verdict == GOOD
    assert gate.resolve().verdict != REJECTED_FIRST_DRAFT


def test_a_first_attempt_acceptance_also_latches():
    v = a_verdict_with_bad_prose()
    gate = vc.VoiceGate(v)
    gate.submit(GOOD)
    assert gate.settled and not gate.exhausted
    assert gate.resolve().verdict == GOOD


def test_resolve_refuses_to_answer_before_anything_is_settled():
    """FAILS IF: a gate mid-re-ask hands back the un-gated free field. The caller
    cannot tell a settled verdict from an unexamined one, and the unexamined one
    is the one that renders."""
    gate = vc.VoiceGate(a_verdict_with_bad_prose())
    with pytest.raises(RuntimeError, match="nothing is settled"):
        gate.resolve()
    gate.submit("still bad, probably?")
    with pytest.raises(RuntimeError, match="nothing is settled"):
        gate.resolve()


def test_settled_and_exhausted_are_different_questions():
    """FAILS IF: they are conflated. Conflating them is what let the accept path
    escape ``_final``: 'the floor fired' and 'a verdict is final' are not the
    same fact, and only one of them means the model lost the field."""
    accepted = vc.VoiceGate(a_verdict_with_bad_prose())
    accepted.submit(GOOD)
    assert accepted.settled and not accepted.exhausted

    floored = vc.VoiceGate(a_verdict_with_bad_prose(), max_attempts=1)
    floored.submit("I've probably done it")
    assert floored.settled and floored.exhausted


def test_the_gate_is_idempotent_after_acceptance_too():
    gate = vc.VoiceGate(a_verdict_with_bad_prose())
    first = gate.submit(GOOD)
    assert gate.submit("Diamond drives the shader now.") is first
    assert gate.resolve().verdict == GOOD


def test_the_attempt_budget_is_three():
    """FAILS IF: the brief's number drifts. Three failures, then the floor."""
    assert vc.MAX_ATTEMPTS == 3
    assert vc.VoiceGate(a_verdict()).max_attempts == 3


def test_a_zero_attempt_gate_is_refused():
    with pytest.raises(ValueError, match="max_attempts"):
        vc.VoiceGate(a_verdict(), max_attempts=0)
