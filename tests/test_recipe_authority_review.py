"""Independent AUTHORITY crucible; no Houdini, fabricated host, or scene claims.

The executor records calls only. Its label cannot be mistaken for a live result.
Tests intentionally fail when a boundary violates the brief; do not weaken them
to match the current implementation. Parent owns source fixes and final receipt.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import threading
import unittest

from synapse.recipes import authority, phrases
from synapse.recipes.contracts import (
    ActionId, ActionSpec, PermissionCategory, RecipeSpec, Refusal,
    RefusalKind, RunRecipeRequest, SlotSchema,
)
from synapse.server.handlers_recipe import RecipeHandlerMixin


def fixture():
    """Two allowed fields, independently chosen bounds, no golden qualification."""
    return RecipeSpec(
        "solaris.spine", "review", "2", "22.0.400", "not-live", "review",
        "not-measured", "not-measured", {"status": "TEST_ONLY"},
        ({"id": "key"}, {"id": "shader"}, {"id": "settings"}), (),
        (
            ActionSpec(ActionId.BUILD, (), (), "graph", PermissionCategory.REVIEW),
            ActionSpec(ActionId.LIGHT,
                       (SlotSchema("exposure", "float", "key.exposure", -1, 1),),
                       (), "field", PermissionCategory.INFORM),
            ActionSpec(ActionId.MATERIAL,
                       (SlotSchema("color", "color3", "shader.base_color", 0, 1),),
                       (), "field", PermissionCategory.INFORM),
            ActionSpec(ActionId.RENDER, (), (), "render", PermissionCategory.APPROVE),
        ),
        {"named_colors": {"red": (1, 0, 0)}},
    )


def payload(request_id="review-1", **updates):
    request = RunRecipeRequest("solaris.spine", ActionId.LIGHT.value,
                               "review-instance", {"exposure": 1}, 2, request_id)
    return asdict(replace(request, **updates))


def live_scope():
    return authority.ApprovalScope("review-instance", 2, "karma_cpu",
                                   (16, 16), 1, "review/run/image.exr")


class Recorder:
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def wrapped_permission(self, action):
        return PermissionCategory.INFORM

    def execute(self, operation):
        self.calls.append(operation)
        if self.callback:
            return self.callback(operation)
        return {"status": "review_backend_recorded", "nested": {"count": len(self.calls)}}


class AuthorityIndependentReview(unittest.TestCase):
    def handler(self, *, callback=None, scope_provider=None):
        host = RecipeHandlerMixin()
        recorder = Recorder(callback)
        host.configure_recipe_authority(
            spec_loader=lambda _: fixture(), executor=recorder,
            scope_provider=scope_provider or (lambda *_: live_scope()),
            mutation_budget=authority.MutationBudget(),
        )
        return host, recorder

    def test_punctuation_attached_extra_clause_is_identified(self):
        # Punctuation is preserved, never normalized away. The clause must be
        # reported as such, rather than disappearing into an unknown-action label.
        for text in ("build the solaris spine; add fog",
                     "build the solaris spine, then add fog",
                     "add fog;build the solaris spine"):
            with self.subTest(text=text):
                result = phrases.match_phrase(text, fixture(), request_id="phrase-review")
                self.assertIsInstance(result, Refusal)
                self.assertEqual(result.kind, RefusalKind.TRAILING_CLAUSE)
                self.assertIn("fog", result.reason)
                self.assertEqual(result.supported_alternative, "build the solaris spine")

    def test_malformed_approval_scope_is_not_offered_to_human(self):
        for updates in ({"samples": 0}, {"samples": True},
                        {"resolution": (0, 16)}, {"engine": ""},
                        {"output_path": ""}):
            with self.subTest(updates=updates):
                scope = replace(live_scope(), **updates)
                host, recorder = self.handler(scope_provider=lambda *_: scope)
                result = host._handle_run_recipe(payload(action_id=ActionId.RENDER.value, slots={}))
                self.assertIn(result["status"], ("refused", "UNAVAILABLE"))
                self.assertEqual(recorder.calls, [])

    def test_boolean_retry_does_not_inherit_valid_numeric_outcome(self):
        host, recorder = self.handler()
        first = host._handle_run_recipe(payload())
        self.assertEqual(first["status"], "review_backend_recorded")
        # JSON true is invalid for a numeric slot even though Python true == 1.
        repeated_id_with_invalid_type = host._handle_run_recipe(payload(slots={"exposure": True}))
        self.assertEqual(repeated_id_with_invalid_type["status"], "refused")
        self.assertIn(repeated_id_with_invalid_type["kind"],
                      (RefusalKind.SLOT_INVALID.value, RefusalKind.DUPLICATE_REQUEST.value))
        self.assertEqual(len(recorder.calls), 1)

    def test_overlapping_transport_retry_executes_once(self):
        entered, release, retry_entered = threading.Event(), threading.Event(), threading.Event()

        def hold(operation):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test failed to release recorder")
            return {"status": "review_backend_recorded"}

        host, recorder = self.handler(callback=hold)

        def retry():
            retry_entered.set()
            return host._handle_run_recipe(payload())

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(host._handle_run_recipe, payload())
            try:
                self.assertTrue(entered.wait(5))
                second = pool.submit(retry)
                self.assertTrue(retry_entered.wait(5))
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5), second.result(timeout=5))
        self.assertEqual(len(recorder.calls), 1)

    def test_overlapping_distinct_requests_share_terminal_budget(self):
        host, recorder = self.handler()
        barrier = threading.Barrier(4)

        def invoke(index):
            barrier.wait(timeout=5)
            return host._handle_run_recipe(payload(request_id=f"parallel-{index}"))

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(invoke, range(4)))
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(sum(r["status"] == "review_backend_recorded" for r in results), 1)
        self.assertEqual(sum(r.get("kind") == RefusalKind.CONFLICT.value for r in results), 3)

    def test_reentrant_retry_observes_inflight_without_reexecuting(self):
        reentrant = []

        def during_execute(operation):
            reentrant.append(host._handle_run_recipe(payload()))
            return {"status": "review_backend_recorded"}

        host, recorder = self.handler(callback=during_execute)
        final = host._handle_run_recipe(payload())
        self.assertEqual(reentrant[0]["status"], "UNKNOWN")
        self.assertEqual(host._handle_run_recipe(payload()), final)
        self.assertEqual(len(recorder.calls), 1)

    def test_failed_terminal_action_denies_follow_on_repair(self):
        def uncertain(operation):
            raise TimeoutError("test uncertainty after possible side effect")

        host, recorder = self.handler(callback=uncertain)
        self.assertEqual(host._handle_run_recipe(payload())["status"], "UNKNOWN")
        repair = host._handle_run_recipe(payload(request_id="repair"))
        self.assertEqual(repair["kind"], RefusalKind.CONFLICT.value)
        self.assertEqual(len(recorder.calls), 1)

    def test_request_and_nested_outcome_are_detached_from_caller(self):
        host, recorder = self.handler()
        original = payload()
        result = host._handle_run_recipe(original)
        original["slots"]["exposure"] = -1
        result["nested"]["count"] = 1000
        retry = host._handle_run_recipe(payload())
        self.assertEqual(retry["nested"]["count"], 1)
        self.assertEqual(recorder.calls[0].bindings[0].value, 1.0)
        self.assertEqual(len(recorder.calls), 1)

    def test_json_shape_errors_fail_closed_without_dispatch(self):
        for updates in ({"recipe_id": []}, {"action_id": {}}, {"request_id": []},
                        {"instance_id": []}, {"expected_revision": True}, {"slots": []}):
            with self.subTest(updates=updates):
                host, recorder = self.handler()
                result = host._handle_run_recipe({**payload(), **updates})
                self.assertEqual(result["status"], "refused")
                self.assertEqual(recorder.calls, [])

    def test_scope_boolean_integer_collision_does_not_approve(self):
        scope = replace(live_scope(), graph_revision=1)
        binding = authority.bind_approval(scope, approved_by="human:review",
                                          approved_at="2026-09-04T18:00:00+00:00")
        self.assertTrue(authority.recheck_approval(binding, scope))
        for updates in ({"graph_revision": True}, {"samples": True}):
            self.assertFalse(authority.recheck_approval(binding, replace(scope, **updates)))


if __name__ == "__main__":
    unittest.main()
