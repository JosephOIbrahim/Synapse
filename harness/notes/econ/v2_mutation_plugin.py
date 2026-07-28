"""V2 · the mutation injector — a pytest plugin that BREAKS one check on purpose.

Loaded by ``v2_mutation_test.py`` with ``-p v2_mutation_plugin`` and the mutation
named in ``SYNAPSE_V2_MUTATION``. Each mutation removes exactly one piece of
enforcement from the shipped modules — not from a test stub — so what the control
suite is pinned to is the product, not a mock of it.

R133: I1 mutation-tested its own controls and found a guard nothing pinned. A
control suite that has never been shown failing is R127's defect wearing a mask,
and 129 green tests is a lot of masks.
"""

import os

MUTATION_ENV = "SYNAPSE_V2_MUTATION"


def _neuter_voice_rule(rule_id):
    """The rule stops being able to reject anything. The exact shape of a check
    that reports healthy, continuously, while proving nothing."""
    from synapse.panel import voice_contract as vc
    vc.VOICE_RULES = tuple(
        vc.VoiceRule(r.id, r.fails_when, (lambda *a, **k: None) if r.id == rule_id
                     else r.check)
        for r in vc.VOICE_RULES)


def _allow_model_free_provenance():
    """Invariant 1 stops being enforced: any field may carry the model's prose."""
    from synapse.panel import verdict as vd
    vd._provenance = lambda value, field: value


def _allow_bool_counts():
    """``True`` becomes a token count of 1 — unmeasured silently becomes measured.

    A MODULE-LEVEL swap is enough: ``By.__post_init__`` resolves ``_count`` through
    globals at call time, not at definition time. An earlier revision rebuilt the
    whole method here "because it closed over ``_count``", which was false and made
    this mutation a strict superset of ``anonymous_by`` — it also deleted the
    model-required, tier-required and tier-regex checks, so a caught superset
    attributed to nothing. Each mutation now removes exactly one guard.
    """
    from synapse.panel import verdict as vd
    real = vd._count

    def lax(value, field, whole=False):
        if isinstance(value, bool):
            return int(value)
        return real(value, field, whole)
    vd._count = lax


def _allow_fractional_tokens():
    """``tokens_in=1.9`` constructs and renders through ``%d`` as ``1``."""
    from synapse.panel import verdict as vd
    real = vd._count
    vd._count = lambda value, field, whole=False: real(value, field, False)


def _allow_anonymous_by():
    """``by`` stops requiring a model and a tier — invariant 6 unenforced.

    Narrowed to exactly that: ``_bounded`` still runs, ``_count`` still runs, only
    the two emptiness checks and the tier shape go.
    """
    from synapse.panel import verdict as vd

    def __post_init__(self):
        s = object.__setattr__
        s(self, "model", vd._bounded(self.model, "by.model", vd.MAX_IDENT_CHARS))
        s(self, "tier", vd._bounded(self.tier, "by.tier", vd.MAX_IDENT_CHARS))
        s(self, "reason", vd._bounded(self.reason, "by.reason", vd.MAX_TEXT_CHARS))
        s(self, "tokens_in", vd._count(self.tokens_in, "by.tokens_in", True))
        s(self, "tokens_out", vd._count(self.tokens_out, "by.tokens_out", True))
        s(self, "cost", vd._count(self.cost, "by.cost"))
    vd.By.__post_init__ = __post_init__


def _unlatch_the_accept_path():
    """The gate stops recording its own acceptances, so ``resolve()`` falls back
    to the object's ORIGINAL free field — V2-F10, restored on purpose."""
    from synapse.panel import voice_contract as vc

    def submit(self, text):
        if self._final is not None:
            return self._final
        self._attempts += 1
        result = vc.validate(text, self._verdict, self._request)
        if result.ok:
            return vc.GateOutcome(True, result.text, "model", result, self._attempts)
        if self._attempts < self._max_attempts:
            return vc.GateOutcome(False, "", "rejected", result, self._attempts,
                                  reask=vc.reask_directive(result))
        templated = vc.fallback_verdict(self._verdict, self._request)
        self._final = vc.GateOutcome(
            True, templated, "fallback" if templated else "empty", result,
            self._attempts)
        return self._final

    def resolve(self, verdict=None):
        target = verdict if verdict is not None else self._verdict
        text = self._final.text if self._final is not None else target.verdict
        return target.with_verdict(text)

    vc.VoiceGate.submit = submit
    vc.VoiceGate.resolve = resolve


def _over_mask_the_register_signature():
    """The signature masks EVERY value, collapsing invariant 8 to 'the row keys
    match'. Green under any content defect — the instrument measuring nothing."""
    from synapse.panel import verdict as vd
    vd.register_signature = lambda v: tuple((k, "<by>") for k, _ in vd.render_rows(v))


def _put_the_author_back_on_the_wire():
    """``by`` returns to the emit schema: the model authors its own credit line,
    including 96 characters of free ``reason`` that renders."""
    from synapse.panel import verdict as vd
    real = vd.json_schema

    def wide():
        schema = real()
        schema["required"] = ["verdict", "by"]
        schema["properties"]["by"] = {
            "type": "object",
            "required": ["model", "tier"],
            "additionalProperties": False,
            "properties": {
                "model": {"type": "string", "maxLength": vd.MAX_IDENT_CHARS},
                "tier": {"type": "string", "pattern": vd._TIER_RE.pattern},
                "reason": {"type": "string", "maxLength": vd.MAX_TEXT_CHARS},
                "tokens_in": {"type": ["integer", "null"], "minimum": 0},
                "tokens_out": {"type": ["integer", "null"], "minimum": 0},
                "cost": {"type": ["number", "null"], "minimum": 0},
            },
        }
        return schema
    vd.json_schema = wide


def _unconstrain_the_wire_paths():
    """``paths`` goes back to a bare string array — the schema blesses payloads
    the constructor rejects."""
    from synapse.panel import verdict as vd
    real = vd.json_schema

    def loose():
        schema = real()
        schema["properties"]["paths"] = {"type": "array", "items": {"type": "string"}}
        return schema
    vd.json_schema = loose


def _restore_the_trim_overflow():
    """``_trim`` appends its ellipsis after cutting to the limit, returning
    limit+1 on any space-free string — V2-F12, restored on purpose."""
    from synapse.panel import decision_log as dlog

    def _trim(text, limit):
        text = " ".join(str(text).split())
        if len(text) <= limit:
            return text
        cut = text[:limit].rsplit(" ", 1)[0]
        return (cut or text[:limit]).rstrip(",;:-") + "…"
    dlog._trim = _trim


def _reject_a_name_inside_its_own_path():
    """``names_change`` excludes '/' from its lookbehind again, so a verdict that
    writes the full path is refused for naming the change too precisely."""
    import re as _re
    from synapse.panel import voice_contract as vc
    from synapse.panel.verdict import changed_tokens

    def check(text, verdict, request):
        if verdict is None:
            return vc.SKIP
        tokens = changed_tokens(verdict)
        if not tokens:
            return vc.SKIP
        for tok in tokens:
            if _re.search(r"(?<![\w/])" + _re.escape(tok) + r"(?!\w)", text or "", _re.I):
                return None
        return vc.Violation("names_change", "names none of %s" % sorted(tokens)[:6])
    vc.VOICE_RULES = tuple(
        vc.VoiceRule(r.id, r.fails_when, check if r.id == "names_change" else r.check)
        for r in vc.VOICE_RULES)


def _allow_none_by():
    """``Verdict`` accepts ``by=None`` — a verdict with no author renders."""
    from synapse.panel import verdict as vd
    real = vd.Verdict.__post_init__

    def lax(self):
        if self.by is None:
            object.__setattr__(self, "by", vd.By(model="unknown", tier="unknown"))
        real(self)
    vd.Verdict.__post_init__ = lax


def _branch_the_renderer_on_tier():
    """The exact defect invariant 8 exists for: a row that appears only on one
    tier. If INV8-A stays green under this, it is measuring nothing."""
    from synapse.panel import verdict as vd
    real = vd.render_rows

    def branching(v):
        rows = list(real(v))
        if v.by.tier == "frontier":
            rows.insert(0, ("BADGE", "frontier"))
        return tuple(rows)
    vd.render_rows = branching
    vd.register_signature = lambda v: tuple(
        (k, "<by>" if k == vd.BY_KEY else val) for k, val in branching(v))


def _let_the_fallback_read_the_free_field():
    """The templated floor starts echoing the prose it just rejected — the
    fallback stops being a pure function of ``decision`` and tiers diverge."""
    from synapse.panel import voice_contract as vc
    real = vc.fallback_verdict

    def leaky(verdict, request=None):
        prose = (getattr(verdict, "verdict", "") or "").strip()
        return prose[:vc.MAX_VERDICT_CHARS] or real(verdict, request)
    vc.fallback_verdict = leaky
    vc.VoiceGate.submit = _rebuilt_submit(vc)


def _spend_a_fourth_attempt():
    """The gate's budget quietly becomes four. Each extra attempt is a whole
    extra API call carrying the entire tools array."""
    from synapse.panel import voice_contract as vc
    vc.MAX_ATTEMPTS = 4
    vc.VoiceGate.__init__.__defaults__ = (None, 4)


def _rebuilt_submit(vc):
    """``VoiceGate.submit`` resolves ``fallback_verdict`` at call time already,
    so this only re-binds the method for mutations that need it."""
    def submit(self, text):
        if self._final is not None:
            return self._final
        self._attempts += 1
        result = vc.validate(text, self._verdict, self._request)
        if result.ok:
            return vc.GateOutcome(True, result.text, "model", result, self._attempts)
        if self._attempts < self._max_attempts:
            return vc.GateOutcome(False, "", "rejected", result, self._attempts,
                                  reask=vc.reask_directive(result))
        templated = vc.fallback_verdict(self._verdict, self._request)
        self._final = vc.GateOutcome(
            True, templated, "fallback" if templated else "empty", result,
            self._attempts)
        return self._final
    return submit


def _drop_the_skipped_list():
    """A rule that could not run starts reporting as a pass — the Law 3
    violation the ``skipped`` field exists to prevent."""
    from synapse.panel import voice_contract as vc
    real = vc.validate

    def quiet(text, verdict=None, request=None, rules=None):
        out = real(text, verdict, request, rules or vc.VOICE_RULES)
        return vc.VoiceResult(text=out.text, violations=out.violations, skipped=())
    vc.validate = quiet


def _let_a_terminal_act_forecast_tokens():
    """An ACCEPT may claim a token spend that cannot happen."""
    from synapse.panel import verdict as vd
    vd.ACTIONS_WITHOUT_TOKEN_COST = ()


def _map_inconclusive_to_pass():
    """RETINA's ratified honesty rule inverted: an inconclusive check renders
    as a pass."""
    from synapse.panel import verdict as vd
    vd.check_from_tristate = lambda passed, text, ref="": vd.Check(
        state="fail" if passed is False else "ok", text=text, ref=ref)


def _let_a_name_be_a_sentence():
    """``chose`` starts accepting prose — a second free field by the back door.

    A module-level swap of ``_identifier`` is enough (globals resolve at call
    time). An earlier revision also rebuilt ``Decision.__post_init__``, which
    silently deleted the separate "chose is required" check and made this a
    two-guard mutation wearing one name.
    """
    from synapse.panel import verdict as vd
    vd._identifier = lambda value, field: vd._bounded(value, field, vd.MAX_IDENT_CHARS)


def _convert_unclassified_rows_silently():
    """``decision_log``'s rule 3 dropped: an unregistered tool's row converts as
    though the registry had backed it."""
    from synapse.panel import decision_log as dlog
    real = dlog.Decision.to_verdict_decision
    dlog.Decision.to_verdict_decision = (
        lambda self, allow_unclassified=False: real(self, True))


#: Every mutation, and the control file that is supposed to notice it.
MUTATIONS = {}
for _rid in ("not_empty", "one_sentence", "char_ceiling", "outcome_first",
             "names_change", "no_preamble", "no_hedging", "no_request_echo",
             "no_decoration", "not_a_question"):
    MUTATIONS["rule:" + _rid] = (
        (lambda rid: (lambda: _neuter_voice_rule(rid)))(_rid),
        "tests/test_v2_voice_contract.py")

MUTATIONS.update({
    "invariant1_model_free": (_allow_model_free_provenance,
                              "tests/test_v2_verdict_contract.py"),
    "bool_is_a_count": (_allow_bool_counts, "tests/test_v2_verdict_contract.py"),
    "anonymous_by": (_allow_anonymous_by, "tests/test_v2_verdict_contract.py"),
    "none_by": (_allow_none_by, "tests/test_v2_verdict_contract.py"),
    "terminal_act_forecast": (_let_a_terminal_act_forecast_tokens,
                              "tests/test_v2_verdict_contract.py"),
    "inconclusive_is_a_pass": (_map_inconclusive_to_pass,
                               "tests/test_v2_verdict_contract.py"),
    "name_may_be_a_sentence": (_let_a_name_be_a_sentence,
                               "tests/test_v2_verdict_contract.py"),
    "silent_unclassified": (_convert_unclassified_rows_silently,
                            "tests/test_v2_verdict_contract.py"),
    "drop_skipped": (_drop_the_skipped_list, "tests/test_v2_voice_contract.py"),
    "fourth_attempt": (_spend_a_fourth_attempt, "tests/test_v2_voice_contract.py"),
    "leaky_fallback": (_let_the_fallback_read_the_free_field,
                       "tests/test_v2_invariant8.py"),
    "tier_branching_renderer": (_branch_the_renderer_on_tier,
                                "tests/test_v2_invariant8.py"),
    # -- added after the adversarial pass: one per defect it found ----------
    "unlatched_accept": (_unlatch_the_accept_path,
                         "tests/test_v2_voice_contract.py"),
    "over_masked_signature": (_over_mask_the_register_signature,
                              "tests/test_v2_invariant8.py"),
    "author_on_the_wire": (_put_the_author_back_on_the_wire,
                           "tests/test_v2_verdict_contract.py"),
    "unconstrained_wire_paths": (_unconstrain_the_wire_paths,
                                 "tests/test_v2_verdict_contract.py"),
    "trim_overflow": (_restore_the_trim_overflow,
                      "tests/test_v2_verdict_contract.py"),
    "fractional_tokens": (_allow_fractional_tokens,
                          "tests/test_v2_verdict_contract.py"),
    "path_name_refused": (_reject_a_name_inside_its_own_path,
                          "tests/test_v2_voice_contract.py"),
})


def pytest_configure(config):
    name = os.environ.get(MUTATION_ENV, "").strip()
    if not name:
        return
    if name not in MUTATIONS:
        raise SystemExit("unknown mutation %r" % name)
    MUTATIONS[name][0]()
    config.stash  # touch, so a linter cannot call this a no-op hook
