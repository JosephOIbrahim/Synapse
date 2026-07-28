"""V2 · INVARIANT 8 — register output is BYTE-COMPARABLE across tiers.

    "Rotate the tier manifest without it and every rotation is a
     re-onboarding event, because the panel visibly becomes a different
     tool and trust was model-specific."

Voice drift is silent. Nothing in a panel reports that this month's model writes
longer sentences than last month's, which makes it the same failure class as
model rot: a thing that degrades continuously while every check stays green. The
suite below is the instrument, and it has three arms because the invariant has
three ways to break.

    INV8-A  the RENDERER must not branch on tier.
            Same structured object, tier varied → identical bytes.
    INV8-B  the GATE must make divergent prose converge.
            Same structured content, two tiers' habits → identical bytes.
    INV8-C  the FALLBACK must be a pure function of `decision`.
            Same decision, any tier → identical bytes.

Byte-comparable is asserted on actual bytes, not on ``==`` between two strings,
because the claim in the invariant is about bytes.
"""

import json
from dataclasses import replace

import pytest

from synapse.panel import voice_contract as vc
from synapse.panel.verdict import (
    BY_KEY, Action, By, Check, Decision, Verdict, Via, register_signature, render_rows,
)

#: Three tiers. Model ids appear here as DATA under test — the invariant that
#: bans model names lives in product code, and this file is the thing checking
#: that product code cannot see them.
TIERS = [
    ("claude-opus-5", "frontier"),
    ("claude-sonnet-4-6", "workhorse"),
    ("claude-haiku-4-5-20251001", "fast"),
]

GOOD = "Dark_Glass now drives the shader, matched to the scene IOR."


def a_by(model, tier):
    return By(model=model, tier=tier, reason="routed by cost")


def a_verdict(model="claude-sonnet-4-6", tier="workhorse", verdict=GOOD):
    return Verdict(
        by=a_by(model, tier),
        verdict=verdict,
        decision=Decision(chose="Dark_Glass", over="Diamond",
                          because="closer to scene IOR"),
        via=Via(node_path="/stage/matlib", mechanism="synapse_solaris_build_graph"),
        checks=(Check("ok", "output written", ref="BL-007"),),
        paths=("/stage/matlib",),
        actions=(Action("Re-render at 4K", "followup", 1800),),
    )


def as_bytes(rows):
    """The literal bytes of a draw list. ``ensure_ascii=False`` keeps the em dash
    and the middle dot as themselves — a comparison that escapes them is
    comparing a transport encoding, not the register."""
    return json.dumps(rows, ensure_ascii=False).encode("utf-8")


# -- INV8-A · the renderer must not branch on tier -------------------------


def test_inv8a_the_register_is_byte_identical_across_every_tier():
    """FAILS IF: ``render_rows`` consults ``by.tier`` or ``by.model`` for
    anything except the author line — a tier-conditional row, a per-model
    separator, a 'frontier gets the cost line' branch."""
    signatures = {as_bytes(register_signature(a_verdict(m, t))) for m, t in TIERS}
    assert len(signatures) == 1, "the register differs across tiers"


def test_inv8a_only_the_author_row_changes_when_the_tier_changes():
    """FAILS IF: a tier change moves anything other than BY. This is the same
    claim as above stated positionally, so a renderer that reorders rows per
    tier without changing their content is still caught."""
    base = render_rows(a_verdict(*TIERS[0]))
    for model, tier in TIERS[1:]:
        other = render_rows(a_verdict(model, tier))
        assert [k for k, _ in base] == [k for k, _ in other]
        differing = [k for (k, a), (_, b) in zip(base, other) if a != b]
        assert differing == [BY_KEY], differing


def test_inv8a_the_masked_row_is_masking_something_real():
    """FAILS IF: ``by`` never reaches the output at all. Without this, masking
    the author row would make INV8-A pass vacuously — the control that stops the
    instrument from measuring nothing (Law 1)."""
    rendered = {dict(render_rows(a_verdict(m, t)))[BY_KEY] for m, t in TIERS}
    assert len(rendered) == len(TIERS)


def test_inv8a_the_mask_covers_the_author_row_and_nothing_else():
    """FAILS IF: ``register_signature`` masks more than the author line.

    A signature that masks EVERY value collapses INV8-A to "the row keys match"
    and stays green through any content defect. The earlier controls could not
    see that: one reads ``render_rows`` (unmasked) and one re-implements the
    masking locally instead of calling the product function. This calls the
    product function and pins the mask's exact footprint.
    """
    v = a_verdict()
    rows = render_rows(v)
    signature = register_signature(v)
    assert len(rows) == len(signature)
    for (key, value), (skey, svalue) in zip(rows, signature):
        assert key == skey
        if key == BY_KEY:
            assert svalue == "<by>" and svalue != value
        else:
            assert svalue == value, "%s was masked and should not be" % key


def test_inv8a_the_instrument_detects_a_renderer_that_does_branch():
    """FAILS IF: the byte comparison cannot see a tier-dependent renderer. This
    is the suite proving it can fail — a passing INV8-A means nothing unless a
    real defect turns it red."""

    def tier_branching_render(v):
        rows = list(render_rows(v))
        if v.by.tier == "frontier":            # the exact defect INV8-A exists for
            rows.insert(0, ("BADGE", "frontier"))
        return tuple((k, "<by>" if k == BY_KEY else val) for k, val in rows)

    signatures = {as_bytes(tier_branching_render(a_verdict(m, t))) for m, t in TIERS}
    assert len(signatures) > 1


# -- INV8-B · the gate must make divergent prose converge ------------------

#: What two tiers actually do differently to the same structured content: one
#: over-explains and hedges, one acknowledges and asks. Both fail the contract,
#: and neither may be allowed to reach the panel as itself.
TIER_PROSE = {
    "frontier": "I've gone ahead and assigned Dark_Glass to the shader, which "
                "should read closer to the scene IOR. Let me know if you want "
                "Diamond back.",
    "workhorse": "Sure! Material updated — probably what you wanted?",
    "fast": "Done",
}


@pytest.mark.parametrize("model,tier", TIERS)
def test_inv8b_each_tiers_own_prose_is_refused(model, tier):
    """FAILS IF: any tier's habitual register passes unchallenged. If one does,
    the panel's voice is that tier's voice and rotation is a re-onboarding."""
    assert not vc.validate(TIER_PROSE[tier], a_verdict(model, tier)).ok


def test_inv8b_divergent_prose_converges_on_identical_bytes():
    """FAILS IF: two tiers writing differently badly produce two different
    panels. The floor is what makes the worst case survivable, and the worst
    case is the one that decides whether rotation is safe."""
    finals = set()
    signatures = set()
    for model, tier in TIERS:
        v = a_verdict(model, tier)
        gate = vc.VoiceGate(v)
        for _ in range(vc.MAX_ATTEMPTS):
            outcome = gate.submit(TIER_PROSE[tier])
        assert outcome.source == "fallback"
        finals.add(outcome.text)
        signatures.add(as_bytes(register_signature(gate.resolve())))
    assert finals == {"Dark_Glass over Diamond — closer to scene IOR"}
    assert len(signatures) == 1


def test_inv8b_conforming_prose_differs_only_in_the_verdict_row():
    """FAILS IF: a conforming sentence is claimed to be byte-identical across
    tiers. It is not, and it is not supposed to be — the invariant is about the
    REGISTER, not the words. Stating the scope precisely is what stops the suite
    from being quoted for more than it proves."""
    a = a_verdict(*TIERS[0], verdict=GOOD)
    b = a_verdict(*TIERS[1], verdict="Dark_Glass drives the shader now, at scene IOR.")
    rows_a, rows_b = render_rows(a), render_rows(b)
    differing = [k for (k, x), (_, y) in zip(rows_a, rows_b) if x != y]
    assert differing == ["VERDICT", BY_KEY]


def test_inv8b_a_tier_that_conforms_and_one_that_does_not_still_share_a_register():
    """FAILS IF: the shape of the surface depends on whether the model got it
    right. Rows, keys and separators are identical either way; only the sentence
    differs, and only ever in the VERDICT row."""
    strong = vc.VoiceGate(a_verdict(*TIERS[0]))
    strong.submit(GOOD)
    weak_v = a_verdict(*TIERS[2])
    weak = vc.VoiceGate(weak_v)
    for _ in range(vc.MAX_ATTEMPTS):
        weak.submit(TIER_PROSE["fast"])
    rows_a = [k for k, _ in render_rows(strong.resolve())]
    rows_b = [k for k, _ in render_rows(weak.resolve())]
    assert rows_a == rows_b


# -- INV8-C · the fallback is a pure function of `decision` ----------------


def test_inv8c_the_fallback_is_identical_on_every_tier():
    """FAILS IF: the templated verdict can vary with the author. It is composed
    from structured fields by the panel; nothing about the model may reach it."""
    texts = {vc.fallback_verdict(a_verdict(m, t)) for m, t in TIERS}
    assert texts == {"Dark_Glass over Diamond — closer to scene IOR"}


def test_inv8c_the_fallback_ignores_the_free_field_entirely():
    """FAILS IF: the abandoned prose leaks into its own replacement."""
    v = a_verdict(verdict="Sure! Material updated — probably what you wanted?")
    assert vc.fallback_verdict(v) == vc.fallback_verdict(a_verdict())


def test_inv8c_the_same_decision_under_a_different_author_is_the_same_bytes():
    base = a_verdict(*TIERS[0])
    other = replace(base, by=a_by(*TIERS[2]))
    assert as_bytes([vc.fallback_verdict(base)]) == as_bytes([vc.fallback_verdict(other)])


# -- the suite covers at least two tiers, as the oracle requires -----------


def test_the_suite_runs_against_more_than_one_tier():
    """FAILS IF: the tier list collapses to one row and every arm above becomes
    a tautology."""
    assert len({t for _, t in TIERS}) >= 2
    assert len({m for m, _ in TIERS}) >= 2
