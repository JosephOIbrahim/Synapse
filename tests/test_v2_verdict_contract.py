"""V2 · the verdict object as a TYPED CONTRACT — enforced, not documented.

Every test here names the condition under which it fails (Law 1). The three that
carry the leg are:

* ``by`` cannot be omitted, cannot be ``None``, cannot be the wrong type.
* ``MODEL_FREE`` provenance is refused everywhere except the ``verdict`` field —
  invariant 1, checked from inside (constructors raise) and from outside
  (``model_free_fields``).
* an unmeasured count is ``None`` and a measured one may be ``0``, and the two do
  not render the same. E0-F12 says no usage reader is closed yet, so today every
  real verdict carries ``None`` — a schema that could not tell them apart would
  publish a zero-token turn as a measurement.
"""

import json

import pytest

from synapse.panel import decision_log as dlog
from synapse.panel.verdict import (
    ACTION_KINDS, CHECK_STATES, MODEL_FREE, MODEL_QUOTED, PROVENANCE, SYSTEM, TOOL,
    Action, By, Check, Decision, Verdict, Via,
    changed_tokens, check_from_tristate, decision_from_tool_evidence, json_schema,
    model_free_fields, register_signature, render_rows, tool_definition,
)


def a_by(**kw):
    kw.setdefault("model", "claude-sonnet-4-6")
    kw.setdefault("tier", "workhorse")
    return By(**kw)


def a_verdict(**kw):
    kw.setdefault("by", a_by())
    kw.setdefault("verdict", "Dark_Glass now drives the shader.")
    kw.setdefault("decision", Decision(chose="Dark_Glass", over="Diamond",
                                       because="closer to scene IOR",
                                       provenance=MODEL_QUOTED))
    kw.setdefault("via", Via(node_path="/stage/matlib",
                             mechanism="synapse_solaris_build_graph"))
    return Verdict(**kw)


# -- `by` is never null -----------------------------------------------------


def test_verdict_without_by_is_a_type_error():
    """FAILS IF: ``by`` ever acquires a default. The language enforces it before
    any of this module's code runs, which is the strongest available fence."""
    with pytest.raises(TypeError):
        Verdict()


def test_verdict_with_explicit_none_by_is_refused():
    """FAILS IF: a caller can hand in ``None`` and get an anonymous verdict."""
    with pytest.raises(ValueError, match="by is required"):
        Verdict(by=None)


def test_verdict_with_a_dict_by_is_refused():
    """FAILS IF: a loose dict passes for an author block — the shape has to be
    the shape, or ``by.tier`` is whatever a JSON blob happened to carry."""
    with pytest.raises(TypeError, match="must be a By"):
        Verdict(by={"model": "x", "tier": "y"})


@pytest.mark.parametrize("kw", [
    {"model": ""}, {"model": "   "}, {"tier": ""}, {"tier": "   "},
])
def test_by_refuses_an_empty_half(kw):
    """FAILS IF: half an author line counts as an author line."""
    with pytest.raises(ValueError, match="required"):
        a_by(**kw)


@pytest.mark.parametrize("tier", ["Workhorse", "work house", "1st", "TIER-A", ""])
def test_tier_must_be_a_lowercase_constant(tier):
    """FAILS IF: a tier can be free text. The tier is the rotation-stable name;
    if it can drift in case or spacing it cannot key a manifest."""
    with pytest.raises(ValueError):
        a_by(tier=tier)


def test_tier_vocabulary_is_opt_in_and_can_reject():
    """FAILS IF: ``validate_tier`` cannot refuse. The manifest is V3's and does
    not exist yet, so the contract shape-checks today and vocabulary-checks the
    day a ratified set arrives."""
    by = a_by(tier="workhorse")
    assert by.validate_tier(("workhorse", "frontier")) is by
    assert by.validate_tier(()) is by            # no vocabulary => no opinion
    with pytest.raises(ValueError, match="not in the ratified manifest"):
        by.validate_tier(("frontier",))


# -- invariant 1: one free field, and it is `verdict` -----------------------


@pytest.mark.parametrize("build", [
    lambda: Decision(chose="Dark_Glass", provenance=MODEL_FREE),
    lambda: Check(state="ok", text="output written", provenance=MODEL_FREE),
])
def test_model_free_provenance_is_refused_outside_the_verdict_field(build):
    """FAILS IF: a second field can carry the model's unconstrained prose. That
    is invariant 1, and it is the reason the register is checkable at all."""
    with pytest.raises(ValueError, match="may not be MODEL_FREE"):
        build()


def test_model_free_fields_reads_the_invariant_back_off_the_object():
    """FAILS IF: the invariant is only enforced at construction. Reading it back
    is what lets a caller — or a future renderer — assert it independently."""
    assert model_free_fields(a_verdict()) == ("verdict",)


def test_an_empty_free_field_carries_no_model_prose_at_all():
    """FAILS IF: an empty verdict still counts as a model-written string. It is
    the fallback's terminal state and it must read as zero prose, not one."""
    assert model_free_fields(a_verdict(verdict="")) == ()


@pytest.mark.parametrize("prov", [p for p in PROVENANCE if p != MODEL_FREE])
def test_the_other_three_provenance_tiers_are_accepted(prov):
    """FAILS IF: the ladder collapses to a boolean. QUOTED, TOOL and SYSTEM are
    different claims and downstream has to be able to tell them apart."""
    assert Decision(chose="Dark_Glass", provenance=prov).provenance == prov


def test_an_unknown_provenance_is_refused():
    with pytest.raises(ValueError, match="must be one of"):
        Decision(chose="Dark_Glass", provenance="probably_fine")


# -- unmeasured is not zero -------------------------------------------------


def test_none_and_zero_are_different_measurements():
    """FAILS IF: a turn with no usage reader publishes a zero-token turn.
    ``None`` means nobody looked; ``0`` means somebody looked and saw none."""
    unmeasured = a_by()
    measured = a_by(tokens_in=0, tokens_out=0)
    assert unmeasured.measured() is False
    assert measured.measured() is True
    assert dict(render_rows(a_verdict(by=unmeasured)))["BY"] \
        != dict(render_rows(a_verdict(by=measured)))["BY"]
    assert "0/0 tok" in dict(render_rows(a_verdict(by=measured)))["BY"]
    assert "tok" not in dict(render_rows(a_verdict(by=unmeasured)))["BY"]


def test_half_measured_usage_does_not_render_as_measured():
    """FAILS IF: one populated half is enough to claim a reading."""
    assert a_by(tokens_in=812).measured() is False
    assert "tok" not in dict(render_rows(a_verdict(by=a_by(tokens_in=812))))["BY"]


@pytest.mark.parametrize("field", ["tokens_in", "tokens_out", "cost"])
def test_a_bool_is_not_a_count(field):
    """FAILS IF: ``True`` silently becomes a count of 1. ``bool`` is an ``int``
    in Python — this is a number travelling without a producer, in miniature."""
    with pytest.raises(TypeError, match="not a bool"):
        a_by(**{field: True})


@pytest.mark.parametrize("field", ["tokens_in", "tokens_out", "cost"])
def test_a_negative_count_is_refused(field):
    with pytest.raises(ValueError, match=">= 0"):
        a_by(**{field: -1})


def test_cost_is_carried_but_not_rendered():
    """FAILS IF: a currency figure reaches a row. The panel's rule is TOKENS
    ONLY, never $ (``synapse_panel.py:468``), and no usage reader is closed
    (E0-F12) — so a cost row today would be a number with no producer. The field
    stays on the object; V2-F4 escalates whether it should ever draw."""
    v = a_verdict(by=a_by(cost=0.0043))
    assert v.by.cost == 0.0043
    assert "0.0043" not in json.dumps(render_rows(v))
    assert "$" not in json.dumps(render_rows(v))


# -- the parts hold their own shape ----------------------------------------


def test_a_decision_needs_a_subject():
    with pytest.raises(ValueError, match="chose is required"):
        Decision(chose="")


@pytest.mark.parametrize("bad", ["Dark glass. It is nicer", "Done.", "Really?"])
def test_a_name_may_not_be_a_sentence(bad):
    """FAILS IF: ``chose`` can hold prose — that is a second free field by the
    back door, and invariant 1 allows exactly one."""
    with pytest.raises(ValueError, match="name, not a sentence"):
        Decision(chose=bad)


@pytest.mark.parametrize("good", ["shot_010.exr", "gemini-3.5-flash", "0.01_roughness"])
def test_a_dot_inside_a_name_is_still_a_name(good):
    """FAILS IF: the sentence check is 'any period'. ``choice_from_input``
    returns ``file_path`` values, and rejecting those would reject the tree's own
    producer (``decision_log.py:50-54``)."""
    assert Decision(chose=good).chose == good


def test_a_name_longer_than_the_ceiling_is_refused():
    with pytest.raises(ValueError, match="exceeds 48"):
        Decision(chose="x" * 49)


@pytest.mark.parametrize("field,value", [
    ("chose", "one\ntwo"), ("because", "one\ntwo"),
])
def test_a_row_may_not_carry_a_line_break(field, value):
    """FAILS IF: a multi-line value reaches a single-row grid cell."""
    with pytest.raises(ValueError, match="single line"):
        Decision(**{"chose": "Dark_Glass", field: value})


def test_via_path_must_be_absolute():
    with pytest.raises(ValueError, match="must be absolute"):
        Via(node_path="stage/matlib")


def test_paths_must_be_absolute_and_are_de_duplicated_in_order():
    """FAILS IF: the touched-path list can repeat or hold a relative path. The
    order is the order the turn touched them; the de-dup keeps the row count
    honest without reordering."""
    v = a_verdict(paths=["/stage/b", "/stage/a", "/stage/b"])
    assert v.paths == ("/stage/b", "/stage/a")
    with pytest.raises(ValueError, match="must be absolute"):
        a_verdict(paths=["stage/b"])


@pytest.mark.parametrize("state", ["warn", "pass", "inconclusive", "OK", ""])
def test_check_state_is_the_schema_two_state_set(state):
    """FAILS IF: the state set widens by accident. It is ``ok``/``fail`` per the
    schema — and that it cannot say 'inconclusive' is V2-F3, escalated, not
    quietly patched here."""
    with pytest.raises(ValueError, match="state must be one of"):
        Check(state=state, text="output written")
    assert CHECK_STATES == ("ok", "fail")


def test_an_inconclusive_check_never_becomes_a_pass():
    """FAILS IF: RETINA's tri-state maps ``None`` to ``ok``. The ratified rule is
    that an inconclusive check MUST NOT render as a pass
    (``face_review.py:56-64``); mapping it to ``fail`` is lossy in the safe
    direction, which is the only direction available in a two-state field."""
    assert check_from_tristate(True, "output written").state == "ok"
    assert check_from_tristate(False, "output written").state == "fail"
    assert check_from_tristate(None, "output written").state == "fail"


def test_a_nameless_check_is_refused():
    with pytest.raises(ValueError, match="text is required"):
        Check(state="ok", text="")


@pytest.mark.parametrize("kind", ["accept", "revert", "commit"])
def test_a_terminal_act_may_not_forecast_token_spend(kind):
    """FAILS IF: an ACCEPT can claim a token cost. Accept/revert/commit are the
    three verbs the Review face already offers (``face_review.py:325-334``) and
    none of them calls a model — a forecast there is a spend that cannot happen."""
    assert Action(label="ACCEPT", kind=kind).forecast_tokens is None
    with pytest.raises(ValueError, match="spends no model tokens"):
        Action(label="ACCEPT", kind=kind, forecast_tokens=1800)


def test_a_followup_may_forecast():
    assert Action(label="Re-render at 4K", kind="followup",
                  forecast_tokens=1800).forecast_tokens == 1800
    assert "followup" in ACTION_KINDS


def test_an_unknown_action_kind_is_refused():
    with pytest.raises(ValueError, match="kind must be one of"):
        Action(label="Ship it", kind="ship")


def test_the_object_is_frozen():
    """FAILS IF: a rendered verdict can be edited after it was validated. The
    gate hands out copies for exactly this reason."""
    v = a_verdict()
    with pytest.raises(Exception):
        v.verdict = "something else"
    with pytest.raises(Exception):
        v.by.tier = "frontier"


def test_with_verdict_copies_rather_than_mutates():
    v = a_verdict()
    other = v.with_verdict("Diamond now drives the shader.")
    assert v.verdict != other.verdict
    assert other.by is v.by and other.decision is v.decision


# -- the projection ---------------------------------------------------------


def test_render_rows_is_ordered_and_complete():
    """FAILS IF: a schema field stops reaching a row, or the order drifts. Row
    order is part of the register — invariant 8 asserts on these bytes."""
    v = a_verdict(checks=(Check("ok", "output written", ref="BL-007"),),
                  paths=("/stage/matlib",),
                  actions=(Action("ACCEPT", "accept"),))
    assert [k for k, _ in render_rows(v)] == [
        "VERDICT", "DECISION", "VIA", "CHECK", "PATH", "BY", "ACTION"]


def test_an_absent_part_draws_no_row():
    """FAILS IF: an empty section renders an empty row. A blank credit line is a
    claim that something was credited."""
    keys = [k for k, _ in render_rows(Verdict(by=a_by()))]
    assert keys == ["BY"]


def test_the_by_row_is_always_present():
    """FAILS IF: work can render anonymously (invariant 6)."""
    assert "BY" in [k for k, _ in render_rows(Verdict(by=a_by()))]
    assert "BY" in [k for k, _ in register_signature(Verdict(by=a_by()))]


def test_changed_tokens_never_reads_the_free_field():
    """FAILS IF: the 'names the thing that changed' rule can be satisfied by the
    sentence quoting itself. The vocabulary comes only from structured fields."""
    v = a_verdict(verdict="Zzzyzx_Unique_Token now drives the shader.")
    assert "zzzyzx_unique_token" not in changed_tokens(v)
    assert "dark_glass" in changed_tokens(v)


def test_changed_tokens_is_empty_when_nothing_structured_changed():
    """FAILS IF: the vocabulary is invented when the object names nothing. The
    voice rule SKIPS on an empty vocabulary, and it can only do that honestly if
    the vocabulary is genuinely empty here."""
    assert changed_tokens(Verdict(by=a_by(), verdict="Something happened.")) == frozenset()


# -- the reconciliation: both credit producers, neither replaced ------------


def test_decision_log_row_converts_as_a_quote():
    """FAILS IF: P1's quoted 'why' loses its provenance on the way into the typed
    field. QUOTED is a different and stronger claim than TOOL, and the whole
    point of ``decision_log`` is that the difference is auditable."""
    row = dlog.Decision(tool="houdini_create_material", choice="Dark_Glass",
                        why="closer to scene IOR", classified=True)
    d = row.to_verdict_decision()
    assert (d.chose, d.because, d.provenance) == ("Dark_Glass", "closer to scene IOR",
                                                  MODEL_QUOTED)


def test_a_row_with_no_quote_is_tool_provenance_not_a_fake_quote():
    """FAILS IF: an empty ``why`` still claims the model said something."""
    row = dlog.Decision(tool="houdini_create_material", choice="Dark_Glass",
                        why="", classified=True)
    assert row.to_verdict_decision().provenance == TOOL


def test_an_unclassified_row_refuses_to_convert_by_default():
    """FAILS IF: an unregistered tool's row converts silently. The typed schema
    has no slot for ``classified``, and dropping it would make the surface
    quietest exactly where ``decision_log`` rule 3 makes it loudest."""
    row = dlog.Decision(tool="mystery_tool", choice="Dark_Glass", why="", classified=False)
    assert row.to_verdict_decision() is None
    assert row.to_verdict_decision(allow_unclassified=True) is not None


def test_tool_evidence_converts_as_tool_provenance():
    """FAILS IF: P2's tool-derived credit is indistinguishable from a quote. It
    reports what a tool DID, not what the agent CHOSE — honest and weaker."""
    d = decision_from_tool_evidence("houdini_create_material", "/stage/matlib created")
    assert d.provenance == TOOL
    assert d.chose == "houdini_create_material"


def test_both_producers_land_in_the_same_typed_field():
    """FAILS IF: the two credit surfaces need two schemas. Reconciled means one
    field, two recorded sources — not one implementation surviving."""
    quoted = dlog.Decision("houdini_create_material", "Dark_Glass",
                           "closer to scene IOR", True).to_verdict_decision()
    derived = decision_from_tool_evidence("houdini_create_material", "created")
    for d in (quoted, derived):
        assert isinstance(Verdict(by=a_by(), decision=d).decision, Decision)
    assert quoted.provenance != derived.provenance


def test_decision_log_cycle_drops_refusals_rather_than_defaulting(monkeypatch):
    """FAILS IF: a refused row is replaced by a placeholder. The count can be
    smaller than the cycle's row count, and a caller comparing the two is reading
    the refusal — which is the point."""
    monkeypatch.setattr(dlog, "classify_tool",
                        lambda name: "unknown" if name == "mystery_tool" else "mutation")
    log = dlog.DecisionLog()
    log.record("houdini_create_material", {"material_name": "Dark_Glass"}, "Closer to scene IOR.")
    log.record("mystery_tool", {"name": "Whatever"}, "Because.")
    assert len(log) == 2
    assert len(log.to_verdict_decisions()) == 1
    assert len(log.to_verdict_decisions(allow_unclassified=True)) == 2


def test_tool_evidence_with_no_tool_name_credits_nothing():
    with pytest.raises(ValueError, match="credits nothing"):
        decision_from_tool_evidence("", "")


def test_system_is_the_default_provenance():
    """FAILS IF: an unlabelled field claims a model source it never had."""
    assert Decision(chose="Dark_Glass").provenance == SYSTEM
    assert Check(state="ok", text="output written").provenance == SYSTEM


# -- the wire form must not drift from the enforced form -------------------


def _fields(cls):
    return set(cls.__dataclass_fields__)


@pytest.mark.parametrize("path,cls", [
    ((), Verdict), (("by",), By), (("decision",), Decision),
    (("via",), Via),
])
def test_the_schema_properties_match_the_dataclass_fields(path, cls):
    """FAILS IF: a field is added to the contract and not to the wire form (the
    agent cannot emit it) or to the wire form and not the contract (the agent
    emits something nothing validates). One drifts, this goes red."""
    node = json_schema()
    for key in path:
        node = node["properties"][key]
    assert set(node["properties"]) == _fields(cls)


@pytest.mark.parametrize("key,cls", [("checks", Check), ("actions", Action)])
def test_the_schema_array_items_match_their_dataclass_fields(key, cls):
    assert set(json_schema()["properties"][key]["items"]["properties"]) == _fields(cls)


def test_the_wire_form_never_offers_model_free_provenance():
    """FAILS IF: an agent can declare MODEL_FREE on the wire. Invariant 1 has to
    hold at the boundary too, or the constructor spends its life rejecting
    something the schema invited."""
    blob = json.dumps(json_schema())
    assert MODEL_FREE not in blob
    for key in ("decision", "checks"):
        node = json_schema()["properties"][key]
        node = node.get("items", node)
        assert MODEL_FREE not in node["properties"]["provenance"]["enum"]


def test_the_wire_form_requires_an_author():
    """FAILS IF: ``by`` becomes optional on the wire while staying required in
    code — the gap where an anonymous verdict is emitted and then rejected."""
    assert "by" in json_schema()["required"]
    assert set(json_schema()["properties"]["by"]["required"]) == {"model", "tier"}


def test_the_schema_carries_one_ceiling_not_two():
    """FAILS IF: the schema hardcodes a character ceiling of its own. Two
    authorities on one number is how a value drifts in silence."""
    from synapse.panel.voice_contract import MAX_VERDICT_CHARS
    verdict_schema = json_schema()["properties"]["verdict"]
    assert verdict_schema["maxLength"] == MAX_VERDICT_CHARS
    assert str(MAX_VERDICT_CHARS) in verdict_schema["description"]


def test_the_tool_definition_is_shaped_for_the_api():
    defn = tool_definition()
    assert set(defn) == {"name", "description", "input_schema"}
    assert defn["input_schema"] == json_schema()
