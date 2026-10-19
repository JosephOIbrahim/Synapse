"""Pure synthetic gate components; no Houdini, process monitor or live ledger."""
from dataclasses import replace
import hashlib
import math
import unittest

from synapse.loop.rcxi_ports import SixMetrics
from synapse.loop.rcxi_light import (
    LightRequest, SyntheticCalibrationProfile, SyntheticForecastLedger, SyntheticLightGate,
    SyntheticLightSnapshot, SyntheticMeasurement, histogram_entropy_ev, metric_vector,
    observed_metrics, synthetic_sample_covariance, tension,
)


def profile(**changes):
    # Explicit, artificial test choices. None is a calibrated production default.
    values = dict(profile_id="synthetic-v1", covariance=tuple(tuple(float(i == j) for j in range(6)) for i in range(6)),
                  loss_weight=0.5, tension_limit=2, loss_tolerance=0.01, histogram_width_ev=1,
                  minimum_exposure=-8, maximum_exposure=8, max_attempts=4,
                  max_measured_execution_ms=100, no_progress_limit=2, progress_epsilon=1e-12)
    return SyntheticCalibrationProfile(**{**values, **changes})


def initial():
    return SyntheticLightSnapshot("fixture-recipe", 0, (("key", 0), ("fill", 0)), 2, 1,
                                  hashlib.sha256(b"SYNTHETIC outside-state").hexdigest(),
                                  0, True, True, "artist-before")


class Model:
    def __init__(self):
        self.current = initial()


class Mutator:
    evidence_tier = "SYNTHETIC"

    def __init__(self, model, values=()):
        self.model, self.values = model, list(values)
        self.applies, self.rollbacks = 0, 0
        self.fail_after_apply, self.noop_rollback = False, False
        self.after_apply = None

    def apply(self, request, attempt_id):
        self.applies += 1
        values = dict(self.model.current.light_values)
        values[request.key_light_binding] = self.values.pop(0) if self.values else request.target_exposure
        self.model.current = replace(self.model.current, revision=self.model.current.revision + 1,
                                     light_values=tuple(values.items()), latest_owner=attempt_id)
        if self.after_apply:
            self.after_apply()
        if self.fail_after_apply:
            raise RuntimeError("synthetic partial mutation")
        return {"status": "SUCCESS", "loss": 0}  # intentionally untrusted self-report

    def rollback(self, before, attempt_id):
        self.rollbacks += 1
        if not self.noop_rollback:
            self.model.current = before
        return True  # must not be accepted instead of independent readback


class Observer:
    evidence_tier = "SYNTHETIC"

    def __init__(self, model):
        self.model, self.execution_ms = model, 10
        self.measure_calls = 0
        self.failure = None
        self.after_measure = None

    def capture(self):
        return self.model.current

    def measure(self, before, request, attempt_id):
        self.measure_calls += 1
        if self.failure:
            raise self.failure
        measurement = SyntheticMeasurement(self.capture(), self.execution_ms, 24)
        if self.after_measure:
            self.after_measure()
        return measurement


class Forecaster:
    evidence_tier = "SYNTHETIC"

    def predict(self, request, before, index):
        # Fixture target 2 or 3 with fill=0 gives two equally populated bins:
        # p=(1/2,1/2), entropy=1. This is not host timing/memory evidence.
        return SixMetrics(0, 10, 24, 0, 1, 0)


def rig(values=(), selected_profile=None):
    model = Model()
    mutator, observer, forecaster, ledger = Mutator(model, values), Observer(model), Forecaster(), SyntheticForecastLedger()
    gate = SyntheticLightGate(mutator=mutator, observer=observer, forecaster=forecaster, ledger=ledger,
                              profile=selected_profile or profile())
    request = LightRequest("fixture-recipe", 0, "key", 2)
    return model, mutator, observer, forecaster, ledger, gate, request


class LightArithmeticTests(unittest.TestCase):
    def test_correlated_six_dimensional_tension_has_hand_computed_value(self):
        matrix = [list(row) for row in profile().covariance]
        matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1] = 4, 2, 2, 3
        chosen = profile(covariance=matrix)
        zero, observed = SixMetrics(0, 0, 0, 0, 0, 0), SixMetrics(1, 2, 0, 0, 0, 0)
        # inverse([[4,2],[2,3]])=[[3,-2],[-2,4]]/8;
        # [1,2] * inverse * [1,2]^T = (3-4-4+16)/8 = 11/8.
        self.assertAlmostEqual(tension(zero, observed, chosen), math.sqrt(11 / 8) + 0.5)

    def test_sixth_dimension_participates(self):
        zero = SixMetrics(0, 0, 0, 0, 0, 0)
        self.assertEqual(tension(zero, SixMetrics(0, 0, 0, 0, 0, 1), profile()), 1)
        self.assertEqual(len(metric_vector(zero)), 6)

    def test_unbiased_sample_covariance_and_explicit_ridge(self):
        samples = [SixMetrics(0, 0, 0, 0, 0, 0), SixMetrics(2, 4, 0, 0, 0, 0)]
        matrix = synthetic_sample_covariance(samples, [1] * 6)
        # Means (1,2); sample sums are Cxx=2,Cxy=4,Cyy=8;
        # divide by n-1=1, then add the declared diagonal regularizer.
        self.assertEqual((matrix[0][0], matrix[0][1], matrix[1][1]), (3, 4, 9))
        self.assertEqual(matrix[5][5], 1)

    def test_singular_wrong_shape_or_asymmetric_profile_refuses(self):
        wrong = [list(row) for row in profile().covariance]
        wrong[0][1] = 1
        for covariance in ([[0] * 6] * 6, [[1] * 5] * 5, wrong):
            with self.subTest(covariance=covariance), self.assertRaises(ValueError):
                profile(covariance=covariance)

    def test_profile_has_no_implicit_numeric_defaults_and_rejects_invalid_choices(self):
        with self.assertRaises(TypeError):
            SyntheticCalibrationProfile()
        for changes in ({"max_attempts": True}, {"max_attempts": 1000}, {"loss_weight": -1},
                        {"max_measured_execution_ms": math.inf}, {"histogram_width_ev": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                profile(**changes)

    def test_histogram_entropy_is_independently_computable(self):
        # Two bins with two samples each: -2 * .5 * log2(.5) = 1 bit.
        self.assertEqual(histogram_entropy_ev([0.1, 0.2, 1.2, 1.3], 1), 1)
        self.assertEqual(histogram_entropy_ev([0.1, 0.2], 1), 0)
        with self.assertRaises(ValueError):
            histogram_entropy_ev([], 1)


class SyntheticLightGateTests(unittest.TestCase):
    def test_import_has_no_network_files_or_houdini_effects(self):
        import builtins
        import importlib.util
        from pathlib import Path
        import socket
        import sys
        from unittest.mock import patch
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split(".")[0] in {"hou", "pxr", "PySide6", "PySide2"}:
                raise AssertionError("host import forbidden")
            return original_import(name, *args, **kwargs)
        name = "synapse.loop._light_import_probe"
        path = sys.modules["synapse.loop.rcxi_light"].__file__
        spec = importlib.util.spec_from_file_location(name, path)
        fresh = importlib.util.module_from_spec(spec)
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                patch("builtins.open", side_effect=AssertionError("I/O forbidden")), \
                patch.object(Path, "open", side_effect=AssertionError("I/O forbidden")), \
                patch.object(Path, "mkdir", side_effect=AssertionError("I/O forbidden")), \
                patch("builtins.__import__", side_effect=guarded), patch.dict(sys.modules, {name: fresh}):
            spec.loader.exec_module(fresh)

    def test_objective_and_observed_invariant_semantics(self):
        before = initial()
        after = replace(before, revision=1, light_values=(("key", 1), ("fill", 0)), latest_owner="run:1")
        request = LightRequest("fixture-recipe", 0, "key", 2)
        metrics = observed_metrics(request, before, SyntheticMeasurement(after, 10, 24), "run:1", profile())
        self.assertEqual((metrics.task_loss, metrics.complexity_delta, metrics.state_entropy, metrics.invariant_violation),
                         (0.5, 0, 1, 0))

    def test_only_synthetic_convergence_is_reported(self):
        model, mutator, observer, _, ledger, gate, request = rig()
        result = gate.run_fixture(request, "accepted")
        self.assertEqual(result.verdict, "FIXTURE_CONVERGED")
        self.assertEqual(model.current.exposure("key"), 2)
        self.assertFalse(result.authorizes_live_action)
        self.assertFalse(result.live_validated)
        self.assertEqual(result.ledger_durability, "VOLATILE_SYNTHETIC")
        self.assertEqual((mutator.applies, observer.measure_calls, mutator.rollbacks), (1, 1, 0))

    def test_live_entry_point_is_unavailable_without_dispatch(self):
        _, mutator, _, _, _, gate, request = rig()
        self.assertEqual(gate.execute_live(request).status, "UNAVAILABLE")
        self.assertEqual(mutator.applies, 0)

    def test_cancel_before_dispatch_is_a_noop(self):
        _, mutator, _, _, _, gate, request = rig()
        gate.cancellation.cancel()
        self.assertEqual(gate.run_fixture(request, "cancelled-before").verdict, "FIXTURE_CANCELLED")
        self.assertEqual((mutator.applies, mutator.rollbacks), (0, 0))

    def test_cancel_after_seal_does_not_dispatch(self):
        _, mutator, _, _, ledger, gate, request = rig()
        original = ledger.seal
        def seal(record):
            ack = original(record)
            gate.cancellation.cancel()
            return ack
        ledger.seal = seal
        self.assertEqual(gate.run_fixture(request, "cancelled-after-seal").verdict, "FIXTURE_CANCELLED")
        self.assertEqual(mutator.applies, 0)

    def test_cancel_after_mutation_restores_fixture_instead_of_converging(self):
        model, mutator, _, _, _, gate, request = rig()
        mutator.after_apply = gate.cancellation.cancel
        self.assertEqual(gate.run_fixture(request, "cancelled-after-apply").verdict, "FIXTURE_CANCELLED")
        self.assertEqual(mutator.rollbacks, 1)
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_missing_or_self_observed_fixture_dependencies_refuse(self):
        _, mutator, observer, _, _, gate, request = rig()
        gate.observer = mutator
        self.assertEqual(gate.run_fixture(request, "self-observed").verdict, "UNAVAILABLE")
        gate.observer = observer
        gate.ledger = None
        self.assertEqual(gate.run_fixture(request, "no-ledger").verdict, "UNAVAILABLE")
        self.assertEqual(mutator.applies, 0)

    def test_stale_revision_unknown_tracking_and_out_of_bound_target_do_not_mutate(self):
        for change in ({"revision": 1}, {"foreign_epoch": None}, {"undo_tracking_known": False}, {"undo_enabled": False}):
            model, mutator, _, _, _, gate, request = rig()
            model.current = replace(model.current, **change)
            with self.subTest(change=change):
                self.assertEqual(gate.run_fixture(request, "preflight").verdict, "UNAVAILABLE")
                self.assertEqual(mutator.applies, 0)
        _, mutator, _, _, _, gate, request = rig()
        self.assertEqual(gate.run_fixture(replace(request, target_exposure=100), "bounds").verdict, "UNAVAILABLE")
        self.assertEqual(mutator.applies, 0)

    def test_forecast_is_sealed_and_bound_before_mutator_runs(self):
        _, mutator, _, _, ledger, gate, request = rig()
        original = mutator.apply
        def verify_before_apply(request, attempt_id):
            row = ledger._records[attempt_id]
            self.assertEqual(row["request_sha256"], request.sha256)
            self.assertEqual(row["profile_sha256"], gate.profile.sha256)
            return original(request, attempt_id)
        mutator.apply = verify_before_apply
        self.assertEqual(gate.run_fixture(request, "sealed-first").verdict, "FIXTURE_CONVERGED")

    def test_lost_seal_acknowledgement_prevents_dispatch(self):
        _, mutator, _, _, ledger, gate, request = rig()
        original = ledger.seal
        ledger.seal = lambda record: (original(record), None)[1]
        self.assertEqual(gate.run_fixture(request, "lost-ack").verdict, "BLOCKED")
        self.assertEqual(mutator.applies, 0)

    def test_mutator_success_claim_does_not_override_actual_loss(self):
        model, mutator, _, _, _, gate, request = rig([0], profile(max_attempts=1))
        result = gate.run_fixture(request, "lying-mutator")
        self.assertEqual(result.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(result.trials[0].metrics.task_loss, 1)
        self.assertEqual(model.current.sha256, initial().sha256)
        self.assertEqual(mutator.applies, 1)

    def test_more_fuel_restores_prestate_before_second_trial(self):
        model, mutator, _, _, _, gate, request = rig([1, 2])
        result = gate.run_fixture(request, "retry")
        self.assertEqual([trial.decision for trial in result.trials], ["FIXTURE_MORE_FUEL", "FIXTURE_CONVERGED"])
        self.assertEqual((mutator.applies, mutator.rollbacks), (2, 1))
        self.assertEqual((model.current.revision, model.current.exposure("key")), (1, 2))

    def test_no_progress_thrashes_and_does_not_spend_remaining_attempts(self):
        model, mutator, _, _, _, gate, request = rig([1] * 6, profile(max_attempts=6))
        result = gate.run_fixture(request, "thrash")
        self.assertEqual(result.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(mutator.applies, 3)
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_attempt_fuel_is_enforced_and_restored(self):
        model, mutator, _, _, _, gate, request = rig([1] * 4, profile(max_attempts=2, no_progress_limit=5))
        result = gate.run_fixture(request, "attempt-fuel")
        self.assertEqual(result.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(mutator.applies, 2)
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_measured_work_budget_is_enforced_even_at_zero_loss(self):
        model, mutator, observer, _, _, gate, request = rig(selected_profile=profile(max_measured_execution_ms=5))
        observer.execution_ms = 10
        self.assertEqual(gate.run_fixture(request, "work-fuel").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual((mutator.applies, model.current.sha256), (1, initial().sha256))

    def test_partial_mutation_exception_cannot_converge(self):
        model, mutator, _, _, _, gate, request = rig()
        mutator.fail_after_apply = True
        self.assertEqual(gate.run_fixture(request, "partial").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_tampered_forecast_after_dispatch_rolls_back(self):
        model, mutator, _, _, ledger, gate, request = rig()
        mutator.after_apply = lambda: ledger._records["tamper:1"]["forecast"].update(task_loss=42)
        self.assertEqual(gate.run_fixture(request, "tamper").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_post_dispatch_ledger_error_is_not_an_unhandled_success(self):
        model, _, _, _, ledger, gate, request = rig()
        original = ledger.verify
        calls = []
        def verify(ack, record):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("synthetic ledger unreadable")
            return original(ack, record)
        ledger.verify = verify
        self.assertEqual(gate.run_fixture(request, "ledger-error").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_escaped_scope_is_an_invariant_failure_even_with_generous_threshold(self):
        model, mutator, _, _, _, gate, request = rig(selected_profile=profile(tension_limit=1000))
        mutator.after_apply = lambda: setattr(model, "current", replace(model.current, light_values=(("key", 2), ("fill", 5))))
        result = gate.run_fixture(request, "escaped")
        self.assertEqual(result.verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(result.trials[0].metrics.invariant_violation, 1)
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_foreign_edit_after_measurement_is_quarantined_without_undo(self):
        model, mutator, observer, _, _, gate, request = rig()
        observer.after_measure = lambda: setattr(model, "current", replace(model.current, foreign_epoch=1, latest_owner="artist-new"))
        result = gate.run_fixture(request, "foreign")
        self.assertEqual(result.verdict, "FIXTURE_QUARANTINED")
        self.assertEqual(mutator.rollbacks, 0)
        self.assertEqual(model.current.latest_owner, "artist-new")

    def test_foreign_edit_during_forecast_does_not_dispatch_or_undo(self):
        model, mutator, _, _, ledger, gate, request = rig()
        original = ledger.seal
        def seal(record):
            ack = original(record)
            model.current = replace(model.current, foreign_epoch=1, latest_owner="artist-new")
            return ack
        ledger.seal = seal
        self.assertEqual(gate.run_fixture(request, "foreign-before").verdict, "BLOCKED")
        self.assertEqual((mutator.applies, mutator.rollbacks), (0, 0))

    def test_failed_recovery_readback_quarantines_and_never_retries(self):
        _, mutator, _, _, _, gate, request = rig([1, 2])
        mutator.noop_rollback = True
        self.assertEqual(gate.run_fixture(request, "bad-recovery").verdict, "FIXTURE_QUARANTINED")
        self.assertEqual((mutator.applies, mutator.rollbacks), (1, 1))

    def test_missing_measurement_rolls_back_only_with_proven_fixture_ownership(self):
        model, mutator, observer, _, _, gate, request = rig()
        observer.failure = TimeoutError("no measurement")
        self.assertEqual(gate.run_fixture(request, "unknown-measurement").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(mutator.rollbacks, 1)
        self.assertEqual(model.current.sha256, initial().sha256)

    def test_replacement_controller_cannot_replay_a_sealed_trial(self):
        model, mutator, observer, forecaster, ledger, gate, request = rig([1], profile(max_attempts=1))
        self.assertEqual(gate.run_fixture(request, "replay").verdict, "FIXTURE_ROLLED_BACK")
        second = SyntheticLightGate(mutator=mutator, observer=observer, forecaster=forecaster, ledger=ledger, profile=gate.profile)
        self.assertEqual(second.run_fixture(request, "replay").verdict, "BLOCKED")
        self.assertEqual(mutator.applies, 1)

    def test_second_action_failure_preserves_first_converged_fixture(self):
        model, mutator, _, _, _, gate, request = rig()
        self.assertEqual(gate.run_fixture(request, "first-action").verdict, "FIXTURE_CONVERGED")
        first_state = model.current
        gate.profile = profile(max_attempts=1)
        mutator.values = [1]
        second_request = LightRequest("fixture-recipe", 1, "key", 3)
        self.assertEqual(gate.run_fixture(second_request, "second-action").verdict, "FIXTURE_ROLLED_BACK")
        self.assertEqual(model.current.sha256, first_state.sha256)

    def test_recovery_does_not_trust_an_old_unchanged_snapshot(self):
        model, mutator, _, _, _, gate, _ = rig()
        before = model.current
        model.current = replace(before, foreign_epoch=1, latest_owner="artist-new")
        self.assertFalse(gate._recover(before, before, "old-attempt"))
        self.assertEqual(mutator.rollbacks, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
