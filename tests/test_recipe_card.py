"""Headless T11/T12 controls, also runnable by unittest without pytest installed."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import threading
import unittest

from synapse.recipes.card import ApprovalScope, RequestDedup, SpecCache, make_card, spec_digest
from synapse.recipes.contracts import (
    ActionId, ActionSpec, Availability, CheckId, CheckResult, CheckStatus,
    EvidenceFreshness, OperationState, PermissionCategory, RecipeInstance,
    RecipeSpec, RecoveryVerdict, RunRecipeRequest, TerminalVerdict,
)
from synapse.recipes.freshness import EvidenceTracker
from synapse.panel.recipe_card import render_html, render_text
from test_recipe_receipt import sample_receipt


def sample_spec():
    # Structural test data only: not a captured or publishable golden graph.
    return RecipeSpec(
        "solaris.spine", "test", "2", "unmeasured-test-host", "catalog", "test-canon",
        "semantic", "layout", {"hip": "NOT_RUN"}, ({"id": "test-node"},), (),
        tuple(ActionSpec(action, (), (), "render" if action == ActionId.RENDER else "graph",
                         PermissionCategory.APPROVE if action == ActionId.RENDER else PermissionCategory.INFORM)
              for action in ActionId), {"title": "Test offer"})


def sample_instance():
    return RecipeInstance("instance-1", "solaris.spine", "test", {}, {}, 1, "after")


def render_receipt():
    return sample_receipt(action_id=ActionId.RENDER, engine="test-engine",
                          checks=tuple(CheckResult(cid, CheckStatus.PASS) for cid in CheckId))


def sample_scope():
    return ApprovalScope("instance-1", 1, "test-engine", (16, 24), 2, "test.exr")


def tracker(**options):
    return EvidenceTracker(lambda instance: "after", tracking_complete=True,
                           tracking_since="2026-09-04T11:00:00+00:00", **options)


class FreshnessTests(unittest.TestCase):
    def test_future_completion_is_unknown(self):
        receipt = replace(sample_receipt(), completed_at="2999-01-01T00:00:00Z")
        self.assertEqual(tracker().freshness(receipt, sample_instance()), EvidenceFreshness.UNKNOWN)

    def test_current_requires_current_observation_and_complete_tracking(self):
        self.assertEqual(tracker().freshness(sample_receipt(), sample_instance()), EvidenceFreshness.CURRENT)
        for subject in (EvidenceTracker(), EvidenceTracker(lambda instance: "after"),
                        EvidenceTracker(tracking_complete=True, tracking_since="2026-09-04T11:00:00Z")):
            with self.subTest(subject=subject):
                self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.UNKNOWN)

    def test_last_committed_baseline_is_not_live_fingerprint(self):
        subject = EvidenceTracker(lambda instance: "artist-edit", tracking_complete=True,
                                  tracking_since="2026-09-04T11:00:00Z")
        self.assertEqual(sample_instance().authored_baseline, sample_receipt().fingerprint_after)
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.STALE)

    def test_t12_all_events_invalidate_even_unchanged_fingerprint(self):
        for event in ("undo", "redo", "scene_load", "owned_edit", "dependency_change"):
            with self.subTest(event=event):
                subject = tracker()
                subject.invalidate(event, at="2026-09-04T12:00:02Z", instance_id="instance-1")
                freshness = subject.freshness(sample_receipt(), sample_instance())
                self.assertEqual(freshness, EvidenceFreshness.STALE)
                card = make_card(sample_spec(), ActionId.BUILD, availability=Availability.READY,
                                 scope="owned", instance=sample_instance(), receipt=sample_receipt(), freshness=freshness)
                self.assertIn("Freshness: STALE", render_text(card))
                self.assertEqual(card.verdict, TerminalVerdict.VERIFIED)  # historical, not recertified

    def test_scope_and_event_time_are_respected(self):
        subject = tracker()
        subject.invalidate("owned_edit", at="2026-09-04T12:00:02Z", instance_id="different")
        subject.invalidate("undo", at="2026-09-04T11:59:00Z")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.CURRENT)
        subject.invalidate("scene_load", at="2026-09-04T12:00:02Z", instance_id="different")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.STALE)

    def test_timestamp_equality_invalidates_conservatively(self):
        subject = tracker()
        subject.invalidate("undo", at=sample_receipt().completed_at)
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.STALE)

    def test_reload_without_coverage_is_unknown_and_reconnect_not_retroactive(self):
        subject = tracker()
        subject.set_tracking(False, since="2026-09-04T12:00:02Z")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.UNKNOWN)
        subject.set_tracking(True, since="2026-09-04T12:00:03Z")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.UNKNOWN)
        later = replace(sample_receipt(), completed_at="2026-09-04T12:00:04Z")
        self.assertEqual(subject.freshness(later, sample_instance()), EvidenceFreshness.CURRENT)

    def test_missing_poststate_or_observer_failure_is_unknown(self):
        self.assertEqual(tracker().freshness(replace(sample_receipt(), fingerprint_after=None), sample_instance()),
                         EvidenceFreshness.UNKNOWN)
        def fail(instance):
            raise RuntimeError("host unavailable")
        subject = EvidenceTracker(fail, tracking_complete=True, tracking_since="2026-09-04T11:00:00Z")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.UNKNOWN)

    def test_reentrant_invalidation_during_observation_cannot_return_current(self):
        def observe(instance):
            subject.invalidate("undo", at="2026-09-04T12:00:02Z")
            return "after"
        subject = EvidenceTracker(observe, tracking_complete=True, tracking_since="2026-09-04T11:00:00Z")
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.STALE)

    def test_identity_and_revision_changes_are_stale(self):
        for changed in (replace(sample_instance(), instance_id="another"),
                        replace(sample_instance(), recipe_version="new"),
                        replace(sample_instance(), graph_revision=2)):
            self.assertEqual(tracker().freshness(sample_receipt(), changed), EvidenceFreshness.STALE)

    def test_periodic_minimum_and_failure_throttle(self):
        for interval in (0, -1, 0.5, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                tracker(min_interval=interval)
        clock = [10.0]
        calls = []
        subject = tracker(min_interval=2.0, clock=lambda: clock[0])
        self.assertTrue(subject.periodic_recheck(lambda: calls.append(1)))
        for _ in range(100):
            self.assertFalse(subject.periodic_recheck(lambda: calls.append(1)))
        self.assertEqual(calls, [1])
        clock[0] += 2.0
        def fail():
            raise RuntimeError("observation failed")
        with self.assertRaises(RuntimeError):
            subject.periodic_recheck(fail)
        self.assertFalse(subject.periodic_recheck(lambda: calls.append(1)))
        self.assertEqual(subject.freshness(sample_receipt(), sample_instance()), EvidenceFreshness.UNKNOWN)


class CardTests(unittest.TestCase):
    def render_card(self, **changes):
        arguments = dict(availability=Availability.READY, scope="owned render", instance=sample_instance(),
                         receipt=render_receipt(), freshness=EvidenceFreshness.CURRENT, approval_scope=sample_scope())
        return make_card(sample_spec(), ActionId.RENDER, **{**arguments, **changes})

    def test_t12_each_approval_scope_change_requires_reapproval(self):
        self.assertFalse(self.render_card().approval_required)
        changes = dict(instance_id="instance-2", graph_revision=2, engine="different",
                       resolution=(32, 48), samples=3, output_path="different.exr")
        for name, value in changes.items():
            with self.subTest(scope_field=name):
                card = self.render_card(approval_scope=replace(sample_scope(), **{name: value}))
                self.assertTrue(card.approval_required)
                self.assertEqual(card.operation_state, OperationState.AWAITING_APPROVAL)
                self.assertIn("Approval is required", card.reason)

    def test_new_trusted_approval_closes_changed_scope(self):
        scope = replace(sample_scope(), samples=3)
        approval = replace(render_receipt().approval, samples=3)
        self.assertFalse(self.render_card(approval_scope=scope, approval=approval).approval_required)

    def test_live_revision_check_cannot_trust_old_scope_and_old_approval(self):
        card = self.render_card(instance=replace(sample_instance(), graph_revision=2))
        self.assertTrue(card.approval_required)
        self.assertEqual(card.freshness, EvidenceFreshness.STALE)

    def test_inflight_job_stays_running_even_if_next_scope_needs_consent(self):
        card = self.render_card(operation_state=OperationState.RUNNING, approval_scope=replace(sample_scope(), samples=4))
        self.assertTrue(card.approval_required)
        self.assertEqual(card.operation_state, OperationState.RUNNING)

    def test_blocked_offer_is_visible_without_receipt(self):
        card = make_card(sample_spec(), ActionId.BUILD, availability=Availability.BLOCKED,
                         scope="owned", availability_reason="Golden scene unavailable")
        text = render_text(card)
        self.assertIn("BLOCKED", text)
        self.assertIn("Golden scene unavailable", text)
        self.assertIn("Graph (P1): NOT_RUN", text)
        self.assertIn("USD (P2): NOT_RUN", text)
        self.assertIn("Render image (P5): NOT_RUN", text)
        self.assertIsNone(card.verdict)
        self.assertEqual(text.count("\nReason:"), 1)
        self.assertEqual(text.count("\nNext action:"), 1)
        with self.assertRaises(ValueError):
            make_card(sample_spec(), ActionId.BUILD, availability=Availability.BLOCKED, scope="owned")

    def test_no_receipt_cannot_claim_current_and_wrong_receipt_is_rejected(self):
        card = make_card(sample_spec(), ActionId.BUILD, availability=Availability.READY,
                         scope="owned", freshness=EvidenceFreshness.CURRENT)
        self.assertEqual(card.freshness, EvidenceFreshness.UNKNOWN)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.render_card(receipt=replace(render_receipt(), instance_id="another"))

    def test_html_is_escaped_and_stale_history_is_never_green(self):
        # Headless token loading uses existing code, no fake hou module.
        from synapse.panel.designsystem import tokens
        card = self.render_card(scope='<script>alert("x")</script>', freshness=EvidenceFreshness.STALE)
        html = render_html(card, tokens=tokens)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Recorded verdict", html)
        self.assertIn(tokens.STATUS["disconnected"][0], html)
        self.assertNotIn(tokens.STATUS["connected"][0], html)
        self.assertIn(tokens.SURFACE, html)


class SpecCacheTests(unittest.TestCase):
    def test_cache_roundtrip_and_detached_spec(self):
        spec = sample_spec()
        digest = spec_digest(spec)
        cache = SpecCache()
        cache.put(digest, spec)
        spec.nodes[0]["id"] = "artist-edit"
        self.assertEqual(cache.get(digest).nodes[0]["id"], "test-node")
        with self.assertRaises(TypeError):
            cache.get(digest).presentation["verdict"] = "VERIFIED"
        self.assertIsNone(cache.get("missing"))

    def test_no_verdict_in_cache_negative_control(self):
        cache = SpecCache()
        for poisoned in (sample_receipt(), TerminalVerdict.VERIFIED,
                         replace(sample_spec(), presentation={"verdict": "VERIFIED"}),
                         replace(sample_spec(), golden_reference={"nested": [sample_receipt()]}),
                         replace(sample_spec(), presentation={"label": TerminalVerdict.VERIFIED}),
                         replace(sample_spec(), presentation={"label": "VERIFIED"})):
            with self.subTest(payload=type(poisoned).__name__):
                # Independently derive the VALID content key. A wrong-key test
                # would pass even if every outcome guard were removed.
                digest = (hashlib.sha256(json.dumps(asdict(poisoned), sort_keys=True,
                          separators=(",", ":")).encode()).hexdigest()
                          if isinstance(poisoned, RecipeSpec) else "wrong-type")
                with self.assertRaises((ValueError, TypeError)):
                    cache.put(digest, poisoned)
                self.assertIsNone(cache.get(digest))

    def test_digest_checks_entire_spec_and_rejects_wrong_key(self):
        spec = sample_spec()
        for changed in (replace(spec, version="new"), replace(spec, supported_build="new"),
                        replace(spec, layout_digest="new"), replace(spec, semantic_digest="new")):
            self.assertNotEqual(spec_digest(spec), spec_digest(changed))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            SpecCache().put("wrong", spec)


class DedupTests(unittest.TestCase):
    def test_terminal_receipt_must_describe_claimed_action(self):
        dedup = RequestDedup()
        dedup.claim(self.request())
        dedup.transition("req-1", OperationState.RUNNING)
        with self.assertRaisesRegex(ValueError, "claimed request"):
            dedup.transition("req-1", OperationState.TERMINAL, receipt=render_receipt())

    def request(self, **changes):
        return replace(RunRecipeRequest("solaris.spine", ActionId.BUILD.value, "instance-1", {}, 1, "req-1"), **changes)

    def test_lost_response_retry_one_effect_new_request_after_reset_new_effect(self):
        dedup = RequestDedup()
        effects = []
        def effect(request_id):
            effects.append(request_id)
            return sample_receipt(request_id=request_id, run_id="run-" + request_id)
        dedup.execute_once(self.request(), lambda: effect("req-1"))  # response is lost
        retry = dedup.execute_once(self.request(), lambda: effect("req-1"))
        self.assertEqual(retry.operation_state, OperationState.TERMINAL)
        self.assertEqual(effects, ["req-1"])
        dedup.execute_once(self.request(request_id="req-2"), lambda: effect("req-2"))
        self.assertEqual(effects, ["req-1", "req-2"])

    def test_retry_observes_pending_approval_running_and_terminal_job(self):
        dedup = RequestDedup()
        self.assertTrue(dedup.claim(self.request()).should_execute)
        self.assertFalse(dedup.claim(self.request()).should_execute)
        for state in (OperationState.AWAITING_APPROVAL, OperationState.RUNNING, OperationState.TERMINAL):
            job = dedup.transition("req-1", state, job_id="job-1",
                                   receipt=sample_receipt() if state == OperationState.TERMINAL else None)
            retry = dedup.claim(self.request())
            self.assertFalse(retry.should_execute)
            self.assertEqual(retry.job, job)
        with self.assertRaises(ValueError):
            dedup.transition("req-1", OperationState.RUNNING)

    def test_timeout_does_not_allow_retry_and_conflicting_payload_is_refused(self):
        dedup = RequestDedup()
        def timeout():
            raise TimeoutError("task may still be running")
        with self.assertRaises(TimeoutError):
            dedup.execute_once(self.request(), timeout)
        retry = dedup.execute_once(self.request(), lambda: self.fail("duplicate effect"))
        self.assertEqual(retry.operation_state, OperationState.RUNNING)
        with self.assertRaisesRegex(ValueError, "different request"):
            dedup.claim(self.request(slots={"exposure": 1.0}))

    def test_concurrent_retries_reserve_one_effect(self):
        dedup = RequestDedup()
        ready = threading.Barrier(8)
        def claim():
            ready.wait(timeout=5)
            return dedup.claim(self.request()).should_execute
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: claim(), range(8)))
        self.assertEqual(sum(results), 1)

    def test_terminal_requires_receipt_and_job_identity_cannot_change(self):
        dedup = RequestDedup()
        dedup.claim(self.request())
        dedup.transition("req-1", OperationState.RUNNING, job_id="job-1")
        with self.assertRaisesRegex(ValueError, "terminal receipt"):
            dedup.transition("req-1", OperationState.TERMINAL)
        with self.assertRaisesRegex(ValueError, "another job"):
            dedup.transition("req-1", OperationState.TERMINAL, job_id="job-2", receipt=sample_receipt())


if __name__ == "__main__":
    unittest.main()
