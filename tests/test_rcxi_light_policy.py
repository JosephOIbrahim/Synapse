"""Reproduce the independent sealed-policy finding at every callback boundary."""
from dataclasses import replace
import unittest

from test_rcxi_light import initial, profile, rig
from synapse.loop.rcxi_light import LightRequest
from synapse.loop.rcxi_ports import SixMetrics


class SealedPolicyTests(unittest.TestCase):
    def assert_restored(self, model, mutator, result):
        self.assertEqual(result.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual((mutator.applies, mutator.rollbacks), (1, 1))
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_review_counterexample_tolerance_rebind_after_apply_cannot_converge(self):
        model, mutator, _, _, ledger, gate, request = rig([0])
        original_hash = gate.profile.sha256
        mutator.after_apply = lambda: setattr(gate, "profile", replace(gate.profile, loss_tolerance=1))
        result = gate.run_fixture(request, "policy-after-apply")
        self.assert_restored(model, mutator, result)
        self.assertEqual(ledger._records["policy-after-apply:1"]["profile_sha256"], original_hash)
        self.assertEqual(result.profile_sha256, original_hash)

    def test_policy_rebind_during_forecast_refuses_before_sealing_or_dispatch(self):
        _, mutator, _, forecaster, ledger, gate, request = rig()
        predict = forecaster.predict
        def predict_with_rebind(*args):
            gate.profile = replace(gate.profile, loss_tolerance=1)
            return predict(*args)
        forecaster.predict = predict_with_rebind
        self.assertEqual(gate.run_fixture(request, "policy-forecast").verdict, "BLOCKED")
        self.assertEqual(mutator.applies, 0)
        self.assertEqual(len(ledger._records), 0)

    def test_policy_rebind_after_custody_refuses_before_dispatch(self):
        _, mutator, _, _, ledger, gate, request = rig()
        seal = ledger.seal
        def seal_then_rebind(record):
            ack = seal(record)
            gate.profile = replace(gate.profile, loss_tolerance=1)
            return ack
        ledger.seal = seal_then_rebind
        self.assertEqual(gate.run_fixture(request, "policy-custody").verdict, "BLOCKED")
        self.assertEqual((mutator.applies, mutator.rollbacks), (0, 0))

    def test_measured_work_policy_cannot_be_relaxed_during_measurement(self):
        model, mutator, observer, forecaster, _, gate, request = rig(selected_profile=profile(max_attempts=1))
        observer.execution_ms = 150
        forecaster.predict = lambda *args: SixMetrics(0, 150, 24, 0, 1, 0)
        observer.after_measure = lambda: setattr(gate, "profile", replace(gate.profile, max_measured_execution_ms=1000))
        self.assert_restored(model, mutator, gate.run_fixture(request, "policy-budget"))

    def test_policy_rebind_at_post_dispatch_ledger_verification_cannot_converge(self):
        model, mutator, _, _, ledger, gate, request = rig([0])
        verify = ledger.verify
        calls = 0
        def verify_then_rebind(*args):
            nonlocal calls
            calls += 1
            answer = verify(*args)
            if calls == 2:
                gate.profile = replace(gate.profile, loss_tolerance=1)
            return answer
        ledger.verify = verify_then_rebind
        self.assert_restored(model, mutator, gate.run_fixture(request, "policy-final-verify"))

    def test_policy_rebind_during_initial_capture_refuses_before_dispatch(self):
        _, mutator, observer, _, _, gate, request = rig()
        capture = observer.capture
        def capture_then_rebind():
            gate.profile = replace(gate.profile, loss_tolerance=1)
            return capture()
        observer.capture = capture_then_rebind
        self.assertEqual(gate.run_fixture(request, "policy-initial").verdict, "BLOCKED")
        self.assertEqual(mutator.applies, 0)

    def test_policy_rebind_during_final_capture_cannot_converge(self):
        model, mutator, observer, _, _, gate, request = rig([0])
        capture = observer.capture
        calls = 0
        def capture_then_rebind():
            nonlocal calls
            calls += 1
            if calls == 4:
                gate.profile = replace(gate.profile, loss_tolerance=1)
            return capture()
        observer.capture = capture_then_rebind
        self.assert_restored(model, mutator, gate.run_fixture(request, "policy-final-capture"))

    def test_invalid_profile_after_apply_cannot_converge(self):
        model, mutator, _, _, _, gate, request = rig()
        mutator.after_apply = lambda: setattr(gate, "profile", None)
        self.assert_restored(model, mutator, gate.run_fixture(request, "policy-unavailable"))

    def test_equivalent_policy_replacement_preserves_content_identity(self):
        _, mutator, _, _, _, gate, request = rig()
        expected = gate.profile.sha256
        mutator.after_apply = lambda: setattr(gate, "profile", replace(gate.profile))
        result = gate.run_fixture(request, "equivalent-policy")
        self.assertEqual(result.verdict, "FIXTURE_CONVERGED")
        self.assertEqual(result.profile_sha256, expected)

    def test_each_composed_run_seals_its_own_selected_profile(self):
        model, mutator, _, _, ledger, gate, request = rig()
        first_hash = gate.profile.sha256
        first = gate.run_fixture(request, "policy-first")
        self.assertEqual(first.verdict, "FIXTURE_CONVERGED")
        first_state = model.current
        gate.profile = profile(max_attempts=1)
        second_hash = gate.profile.sha256
        mutator.values = [1]
        second = gate.run_fixture(LightRequest("fixture-recipe", 1, "key", 3), "policy-second")
        self.assertEqual(second.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(model.current.sha256, first_state.sha256)
        self.assertNotEqual(first_hash, second_hash)
        self.assertEqual((first.profile_sha256, second.profile_sha256), (first_hash, second_hash))
        self.assertEqual(ledger._records["policy-first:1"]["profile_sha256"], first_hash)
        self.assertEqual(ledger._records["policy-second:1"]["profile_sha256"], second_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
