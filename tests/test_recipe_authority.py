"""Pure C3 controls; also runnable with unittest when pytest is unavailable.

The miniature specification tests authority, not golden-scene qualification.
No scene API is imported or planted. The executor is an explicit recording
backend, and every no-mutation claim asserts its call count.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import math
import unittest
from unittest.mock import patch

from synapse.recipes import authority, phrases
from synapse.recipes.contracts import (
    ActionId, ActionSpec, ApprovalBinding, DEMO_PHRASES, PermissionCategory as P,
    RecipeSpec, Refusal, RefusalKind as R, RunRecipeRequest, SlotSchema,
)
from synapse.server.handlers_recipe import RecipeHandlerMixin, parse_request


def make_spec():
    actions = (
        ActionSpec(ActionId.BUILD, (), (), "graph", P.REVIEW),
        ActionSpec(ActionId.LIGHT, (SlotSchema("exposure", "float", "key.exposure", -2, 2),), (), "field", P.INFORM),
        ActionSpec(ActionId.MATERIAL, (SlotSchema("base_color", "color3", "shader.base_color", 0, 1),), (), "field", P.INFORM),
        ActionSpec(ActionId.RENDER, (
            SlotSchema("width", "int", "settings.width", 1, 128),
            SlotSchema("height", "int", "settings.height", 1, 128),
            SlotSchema("samples", "int", "settings.samples", 1, 4),
            SlotSchema("engine", "enum", "settings.engine", enum=("karma_cpu",)),
        ), (), "render", P.APPROVE),
    )
    return RecipeSpec("solaris.spine", "test", "2", "22.0.400", "test-catalog",
                      "test-canon", "test-semantic", "test-layout", {"status": "TEST_ONLY"},
                      tuple({"id": key} for key in ("key", "shader", "settings")), (), actions,
                      {"named_colors": {"blue": (0.0, 0.0, 1.0), "red": (1.0, 0.0, 0.0)},
                       "demo_slots": {ActionId.RENDER.value: {"width": 64, "height": 64, "samples": 1, "engine": "karma_cpu"}}})


def request(action=ActionId.LIGHT, slots=None, request_id="request-1"):
    if slots is None:
        slots = {ActionId.BUILD: {}, ActionId.LIGHT: {"exposure": 1},
                 ActionId.MATERIAL: {"base_color": [0, 0, 1]},
                 ActionId.RENDER: {"width": 64, "height": 64, "samples": 1, "engine": "karma_cpu"}}[action]
    return RunRecipeRequest("solaris.spine", action.value,
                            None if action == ActionId.BUILD else "instance-1", slots,
                            None if action == ActionId.BUILD else 3, request_id)


def scope():
    return authority.ApprovalScope("instance-1", 3, "karma_cpu", (64, 64), 1, "runs/request-1/image.exr")


class RecordingExecutor:
    def __init__(self, gate=P.INFORM):
        self.calls = []
        self.gate = gate

    def wrapped_permission(self, action):
        return self.gate

    def execute(self, operation):
        self.calls.append(operation)
        return {"status": "recorded_by_test_backend", "request_id": operation.request.request_id}


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.spec = make_spec()

    def assert_refused(self, result, kind=R.SLOT_INVALID):
        self.assertIsInstance(result, Refusal)
        self.assertEqual(result.kind, kind)
        self.assertTrue(result.reason)

    def test_typed_values_and_targets(self):
        checked = authority.validate_request(request(), self.spec)
        self.assertIs(type(checked.slots["exposure"]), float)
        bindings = authority.typed_bindings(checked, self.spec)
        self.assertEqual(bindings, (authority.TypedBinding("key", "exposure", 1.0),))
        with self.assertRaises(TypeError):
            checked.slots["exposure"] = 42

    def test_numeric_bounds_finiteness_and_types(self):
        for value in (-3, 3, float("nan"), float("inf"), -float("inf"), True, "1.0", None, 10 ** 1000):
            with self.subTest(value=repr(value)[:60]):
                self.assert_refused(authority.validate_request(request(slots={"exposure": value}), self.spec))
        for value in (-2, 0, 2, 0.25):
            self.assertIsInstance(authority.validate_request(request(slots={"exposure": value}), self.spec), RunRecipeRequest)

    def test_unknown_missing_and_nonstring_slot_keys(self):
        for slots in ({}, {"exposure": 0, "fog": True}, {1: 0}, [], None):
            req = replace(request(), slots=slots)
            self.assert_refused(authority.validate_request(req, self.spec))

    def test_enum_and_integer_negative_controls(self):
        base = request(ActionId.RENDER)
        for key, value in (("engine", "karma_xpu"), ("engine", 0), ("samples", True),
                           ("samples", 1.0), ("samples", 0), ("samples", 5), ("width", math.inf)):
            with self.subTest(key=key, value=value):
                self.assert_refused(authority.validate_request(replace(base, slots={**base.slots, key: value}), self.spec))

    def test_color_components_not_strings_booleans_or_unbounded(self):
        for value in ([0, 1], [0, 0, 0, 0], [0, True, 1], [0, math.nan, 1],
                      [0, math.inf, 1], [-0.1, 0, 1], [0, 0, 1.1], "red"):
            with self.subTest(value=value):
                self.assert_refused(authority.validate_request(request(ActionId.MATERIAL, {"base_color": value}), self.spec))

    def test_unknown_action_and_recipe(self):
        for req in (replace(request(), action_id="fog"), replace(request(), recipe_id="other")):
            self.assert_refused(authority.validate_request(req, self.spec), R.UNKNOWN_ACTION)

    def test_instance_and_revision_shape(self):
        for req in (replace(request(), expected_revision=True), replace(request(), expected_revision=-1),
                    replace(request(), instance_id=None), replace(request(), request_id=" "),
                    replace(request(), instance_id="/stage/key ")):
            self.assert_refused(authority.validate_request(req, self.spec))
        self.assert_refused(authority.validate_request(replace(request(), expected_revision=None), self.spec), R.STALE)

    def test_schema_errors_fail_closed(self):
        original = self.spec.actions[1]
        for slot in (replace(original.slots[0], min=math.nan), replace(original.slots[0], min=4, max=2),
                     replace(original.slots[0], type="python"), replace(original.slots[0], binding="key.exposure;evil()"),
                     replace(original.slots[0], binding="missing.exposure"), replace(original.slots[0], enum=("1",))):
            spec = replace(self.spec, actions=(replace(original, slots=(slot,)),))
            self.assert_refused(authority.validate_request(request(), spec))

    def test_string_slots_are_literal_data(self):
        slot = SlotSchema("label", "str", "key.label")
        spec = replace(self.spec, actions=(replace(self.spec.actions[1], slots=(slot,)),))
        text = "'); __import__('os').system('do-not-execute') #"
        bindings = authority.typed_bindings(request(slots={"label": text}), spec)
        self.assertEqual(bindings[0].value, text)
        self.assertEqual(bindings[0].parm_name, "label")

    def test_duplicate_actions_are_ambiguous(self):
        spec = replace(self.spec, actions=self.spec.actions + (self.spec.actions[1],))
        self.assert_refused(authority.validate_request(request(), spec), R.AMBIGUOUS)

    def test_permission_cannot_be_lowered(self):
        order = [P.INFORM, P.REVIEW, P.APPROVE, P.CRITICAL]
        for declared in order:
            for wrapped in order:
                action = replace(self.spec.actions[1], permission=declared)
                result = authority.effective_permission(action, wrapped)
                self.assertGreaterEqual(order.index(result), order.index(declared))
                self.assertGreaterEqual(order.index(result), order.index(wrapped))
                self.assertIn(result, (declared, wrapped))

    def test_t6_missing_approval(self):
        self.assert_refused(authority.require_approval(None, scope()), R.APPROVAL_REQUIRED)

    def test_approval_exact_match_and_provenance(self):
        binding = authority.bind_approval(scope(), approved_by="human:test", approved_at="2026-09-04T18:00:00+00:00")
        self.assertTrue(authority.recheck_approval(binding, scope()))
        self.assertIsNone(authority.require_approval(binding, scope()))
        self.assertFalse(authority.recheck_approval(asdict(binding), scope()))
        self.assertFalse(authority.recheck_approval(replace(binding, approved_by=""), scope()))
        self.assertFalse(authority.recheck_approval(replace(binding, approved_at="yesterday"), scope()))

    def test_each_bound_field_mismatch_denied(self):
        binding = authority.bind_approval(scope(), approved_by="human:test")
        for key, value in (("instance_id", "instance-2"), ("graph_revision", 4), ("engine", "karma_xpu"),
                           ("resolution", (65, 64)), ("resolution", (64, 65)), ("samples", 2),
                           ("output_path", "runs/request-2/image.exr"), ("output_path", "RUNS/request-1/image.exr")):
            with self.subTest(key=key, value=value):
                live = replace(scope(), **{key: value})
                self.assertFalse(authority.recheck_approval(binding, live))
                self.assert_refused(authority.require_approval(binding, live), R.APPROVAL_MISMATCH)

    def test_scope_types_are_not_coerced(self):
        binding = authority.bind_approval(scope(), approved_by="human:test")
        for key, value in (("graph_revision", 3.0), ("samples", True), ("resolution", (64.0, 64)), ("output_path", None)):
            self.assertFalse(authority.recheck_approval(binding, {**asdict(scope()), key: value}))
        self.assertFalse(authority.recheck_approval(binding, {}))
        with self.assertRaises(ValueError):
            authority.bind_approval(scope(), approved_by="")

    def test_terminal_stops_second_mutation_but_allows_reads(self):
        for action in self.spec.actions:
            budget = authority.MutationBudget()
            self.assertTrue(authority.is_terminal(action))
            self.assertIsNone(budget.consume(action))
            self.assertIsNone(budget.consume(mutating=False))
            self.assert_refused(budget.consume(), R.CONFLICT)  # generic follow-on setter
            self.assert_refused(budget.consume(action), R.CONFLICT)
        self.assertIsNone(authority.MutationBudget().consume(ActionId.LIGHT))

    def test_terminal_reservation_is_thread_safe(self):
        budget = authority.MutationBudget()
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(lambda _: budget.consume(ActionId.BUILD), range(8)))
        self.assertEqual(sum(value is None for value in outcomes), 1)

    def test_t4_entire_request_refused_before_dispatch(self):
        executor = RecordingExecutor()
        matched = phrases.match_phrase("build the solaris spine and add fog", self.spec, request_id="t4")
        if isinstance(matched, RunRecipeRequest):
            executor.calls.append(matched)  # dispatch spy accepts any escaped plan
        self.assert_refused(matched, R.TRAILING_CLAUSE)
        self.assertIn("and add fog", matched.reason)
        self.assertEqual(matched.supported_alternative, "build the solaris spine")
        self.assertEqual(executor.calls, [])

    def test_phrase_leading_and_trailing_clauses_preserved(self):
        for text in ("first add fog then build the solaris spine", "build the solaris spine and add fog",
                     "make the hero red and add fog", "set the key light exposure to 1 and add fog"):
            result = phrases.match_phrase(text, self.spec, request_id="t4", instance_id="instance-1", expected_revision=3)
            self.assert_refused(result, R.TRAILING_CLAUSE)
            self.assertIn("fog", result.reason)

    def test_phrases_only_case_and_whitespace_normalized(self):
        result = phrases.match_phrase(" \tBUILD  the Solaris\nspine ", self.spec, request_id="build")
        self.assertEqual(result.action_id, ActionId.BUILD)
        for text in ("build the solaris spine.", "please build a scene", "", "build-the-solaris-spine"):
            result = phrases.match_phrase(text, self.spec, request_id="offlist")
            self.assertIsInstance(result, Refusal)
            self.assertTrue(result.supported_alternative)

    def test_phrase_extracts_finite_float(self):
        for token, expected in (("-1.25", -1.25), ("1e-1", 0.1)):
            result = phrases.match_phrase("set the key light exposure to " + token, self.spec,
                                           request_id="light", instance_id="instance-1", expected_revision=3)
            self.assertEqual(result.slots["exposure"], expected)
        for token in ("nan", "inf", "1e999", "nope", "3"):
            self.assert_refused(phrases.match_phrase("set the key light exposure to " + token, self.spec,
                                                    request_id="light", instance_id="instance-1", expected_revision=3))

    def test_named_color_uses_curated_constants(self):
        for name, channels in self.spec.presentation["named_colors"].items():
            result = phrases.match_phrase("make the hero " + name.upper(), self.spec,
                                           request_id="color", instance_id="instance-1", expected_revision=3)
            self.assertEqual(result.slots["base_color"], channels)
        self.assert_refused(phrases.match_phrase("make the hero mauve", self.spec,
                                                request_id="color", instance_id="instance-1", expected_revision=3))

    def test_phrase_ambiguity_is_not_order_dependent(self):
        table = {**DEMO_PHRASES, ActionId.LIGHT: ("build the solaris spine",)}
        with patch.object(phrases, "DEMO_PHRASES", table):
            self.assert_refused(phrases.match_phrase("build the solaris spine", self.spec, request_id="amb"), R.AMBIGUOUS)
        self.assert_refused(phrases.match_phrase("build the solaris spine and render the spine", self.spec, request_id="amb"), R.AMBIGUOUS)

    def test_render_phrase_uses_only_curated_defaults(self):
        result = phrases.match_phrase("render the spine", self.spec, request_id="render",
                                       instance_id="instance-1", expected_revision=3)
        self.assertEqual(result.slots, request(ActionId.RENDER).slots)
        spec = replace(self.spec, presentation={})
        self.assert_refused(phrases.match_phrase("render the spine", spec, request_id="render",
                                                instance_id="instance-1", expected_revision=3))


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.spec = make_spec()
        self.executor = RecordingExecutor()
        self.handler = RecipeHandlerMixin()
        self.handler.configure_recipe_authority(spec_loader=lambda _: self.spec, executor=self.executor,
                                               scope_provider=lambda *_: scope(), mutation_budget=authority.MutationBudget())

    def call(self, req=None):
        return self.handler._handle_run_recipe(asdict(request() if req is None else req))

    def test_handler_executes_only_prepared_typed_operation(self):
        result = self.call()
        self.assertEqual(result["status"], "recorded_by_test_backend")
        self.assertEqual(len(self.executor.calls), 1)
        op = self.executor.calls[0]
        self.assertEqual(op.bindings, (authority.TypedBinding("key", "exposure", 1.0),))
        self.assertEqual(op.permission, P.INFORM)

    def test_invalid_input_never_dispatches(self):
        result = self.call(request(slots={"exposure": math.nan}))
        self.assertEqual(result["kind"], R.SLOT_INVALID.value)
        self.assertEqual(self.executor.calls, [])

    def test_t6_render_awaits_trusted_approval(self):
        result = self.call(request(ActionId.RENDER))
        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(result["kind"], R.APPROVAL_REQUIRED.value)
        self.assertEqual(result["binding"], asdict(scope()))
        self.assertNotIn("approved_by", result["binding"])
        self.assertEqual(self.executor.calls, [])

    def test_t6_wrapper_cannot_self_approve(self):
        for key in ("approved", "approval", "auto_approve", "consent", "binding"):
            payload = {**asdict(request(ActionId.RENDER)), key: asdict(authority.bind_approval(scope(), approved_by="model"))}
            result = self.handler._handle_run_recipe(payload)
            self.assertEqual(result["kind"], R.APPROVAL_REQUIRED.value)
        self.assertEqual(self.executor.calls, [])

    def test_untrusted_capabilities_cannot_hide_in_slots(self):
        for key in ("output_path", "output_root", "node_path", "code", "approved"):
            result = self.call(request(slots={"exposure": 0, key: "untrusted"}))
            self.assertEqual(result["kind"], R.SLOT_INVALID.value)
        self.assertEqual(self.executor.calls, [])

    def test_render_gate_floor_cannot_be_relabelled(self):
        self.spec = replace(self.spec, actions=tuple(replace(a, permission=P.INFORM) for a in self.spec.actions))
        result = self.call(request(ActionId.RENDER))
        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(self.executor.calls, [])

    def test_wrapped_critical_effect_remains_gated(self):
        self.executor.gate = P.CRITICAL
        result = self.call()
        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(result["permission"], P.CRITICAL.value)
        self.assertEqual(self.executor.calls, [])

    def test_request_id_dedup_returns_defensive_prior_outcome(self):
        first = self.call()
        first["status"] = "tampered"
        second = self.call()
        self.assertEqual(second["status"], "recorded_by_test_backend")
        self.assertEqual(len(self.executor.calls), 1)

    def test_pending_approval_deduplicated_and_never_dispatched(self):
        req = request(ActionId.RENDER)
        first = self.call(req)
        self.assertEqual(self.call(req), first)
        self.assertEqual(self.executor.calls, [])

    def test_changed_payload_cannot_reuse_request_id(self):
        self.call()
        result = self.call(request(slots={"exposure": 0}))
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["kind"], R.DUPLICATE_REQUEST.value)
        self.assertEqual(len(self.executor.calls), 1)

    def test_concurrent_retries_execute_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.call(), range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(self.executor.calls), 1)

    def test_failure_cached_after_possible_mutation(self):
        def fail(op):
            self.executor.calls.append(op)
            raise TimeoutError("terminal state not observed")
        with patch.object(self.executor, "execute", fail):
            result = self.call()
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertEqual(self.call(), result)
        self.assertEqual(len(self.executor.calls), 1)

    def test_second_action_requires_new_host_turn(self):
        self.call()
        result = self.call(request(request_id="request-2"))
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["kind"], R.CONFLICT.value)
        self.assertEqual(len(self.executor.calls), 1)
        self.handler.begin_recipe_turn(authority.MutationBudget())
        result = self.call(request(request_id="request-3"))
        self.assertEqual(result["status"], "recorded_by_test_backend")
        self.assertEqual(len(self.executor.calls), 2)

    def test_approval_proposal_also_ends_turn(self):
        self.call(request(ActionId.RENDER))
        result = self.call(request(request_id="follow-on"))
        self.assertEqual(result["kind"], R.CONFLICT.value)
        self.assertEqual(self.executor.calls, [])

    def test_stale_proposal_scope_refused(self):
        self.handler._recipe_scope_provider = lambda *_: replace(scope(), graph_revision=4)
        self.assertEqual(self.call(request(ActionId.RENDER))["kind"], R.STALE.value)
        self.assertEqual(self.executor.calls, [])

    def test_absent_executor_loader_or_turn_is_unavailable(self):
        self.handler._recipe_executor = None
        self.assertEqual(self.call()["status"], "UNAVAILABLE")
        unconfigured = RecipeHandlerMixin()
        self.assertEqual(unconfigured._handle_run_recipe(asdict(request()))["status"], "UNAVAILABLE")
        unconfigured.configure_recipe_authority()
        self.assertEqual(unconfigured._handle_run_recipe(asdict(request()))["status"], "UNAVAILABLE")

    def test_golden_pending_never_dispatches(self):
        self.spec = replace(self.spec, golden_reference={"status": "PENDING_HUMAN"})
        self.assertEqual(self.call()["status"], "UNAVAILABLE")
        self.assertEqual(self.executor.calls, [])

    def test_payload_parser_rejects_unknown_and_missing_fields(self):
        for payload in (None, [], {}, {**asdict(request()), "extra": 1}):
            self.assertIsInstance(parse_request(payload), Refusal)


if __name__ == "__main__":
    unittest.main()
