"""Typed substrate seam contracts only; not RC+xi gate acceptance."""
from dataclasses import replace
import math
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from synapse.loop.ports import PortResult
from synapse.loop.rcxi_ports import RcxiObservationPort, SixMetrics, SubstrateSeams, TelemetryObservation


def observation():
    return TelemetryObservation("synthetic-attempt", "a" * 64, "synthetic-profile-v1",
                                SixMetrics(0.0, 10.0, 24.0, 0, 1.0, 0), "SYNTHETIC")


class SubstrateSeamTests(unittest.TestCase):
    def test_unconfigured_ports_are_unavailable_without_side_effects(self):
        with patch("builtins.open", side_effect=AssertionError("no storage writes")), \
                patch.object(Path, "mkdir", side_effect=AssertionError("no owner/store construction")):
            seam = SubstrateSeams()
            results = (seam.compose_sanitized_stage("fixture"), seam.author_precommit("claim", 0.5, "digest"), seam.settle("attempt"))
        for result in results:
            self.assertIsInstance(result, PortResult)
            self.assertEqual(result.status, "UNAVAILABLE")
            self.assertTrue(result.error_message)
            self.assertIsNone(result.payload)

    def test_injected_existing_ports_keep_their_real_result_and_signature(self):
        stage, ledger = Mock(), Mock()
        composition = PortResult.ok({"context": {"fixture": True}, "source": "SYNTHETIC"})
        forecast = PortResult.ok({"forecast_digest": "b" * 64})
        unsettled = PortResult.unavailable("pending evidence")
        stage.compose_sanitized_stage.return_value = composition
        ledger.author_precommit.return_value = forecast
        ledger.settle.return_value = unsettled
        seam = SubstrateSeams(stage=stage, ledger=ledger)
        self.assertIs(seam.compose_sanitized_stage("fixture"), composition)
        self.assertIs(seam.author_precommit("Boolean claim", 0.5, "world"), forecast)
        self.assertIs(seam.settle("attempt"), unsettled)
        ledger.author_precommit.assert_called_once_with("Boolean claim", 0.5, "world")
        ledger.settle.assert_called_once_with("attempt")

    def test_invalid_or_empty_success_is_blocked(self):
        stage = Mock()
        for value in (None, {"status": "SUCCESS"}, PortResult("ALLOW", {}), PortResult.ok()):
            stage.compose_sanitized_stage.return_value = value
            with self.subTest(value=value):
                self.assertEqual(SubstrateSeams(stage=stage).compose_sanitized_stage("fixture").status, "BLOCKED")

    def test_exceptions_are_unavailable_and_do_not_leak_private_text(self):
        stage = Mock()
        stage.compose_sanitized_stage.side_effect = RuntimeError("SECRET at a private path")
        result = SubstrateSeams(stage=stage).compose_sanitized_stage("fixture")
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertNotIn("SECRET", str(result))

    def test_missing_six_component_provider_never_authorizes(self):
        seam = RcxiObservationPort()
        self.assertEqual(seam.observe("attempt", "a" * 64).status, "UNAVAILABLE")
        self.assertEqual(seam.evaluate({"loss": 0}).status, "UNAVAILABLE")

    def test_synthetic_measurement_is_data_and_never_gate_approval(self):
        provider = Mock()
        provider.observe.return_value = observation()
        seam = RcxiObservationPort(provider)
        result = seam.observe("synthetic-attempt", "a" * 64)
        self.assertEqual(result.status, "SUCCESS")
        self.assertFalse(result.payload["authorizes_action"])
        self.assertEqual(result.payload["observation"]["evidence_tier"], "SYNTHETIC")
        self.assertEqual(len(result.payload["observation"]["metrics"]), 6)
        self.assertEqual(seam.evaluate(result).status, "UNAVAILABLE")

    def test_mismatched_or_missing_observation_is_blocked(self):
        provider = Mock()
        for value in (None, {"metrics": {}}, replace(observation(), attempt_id="another-attempt"),
                      replace(observation(), input_sha256="b" * 64)):
            provider.observe.return_value = value
            with self.subTest(value=value):
                self.assertEqual(RcxiObservationPort(provider).observe("synthetic-attempt", "a" * 64).status, "BLOCKED")

    def test_lost_measurement_stays_unavailable(self):
        provider = Mock()
        provider.observe.side_effect = TimeoutError("SECRET")
        result = RcxiObservationPort(provider).observe("synthetic-attempt", "a" * 64)
        self.assertEqual(result.status, "UNAVAILABLE")
        self.assertNotIn("SECRET", str(result))

    def test_unknown_nonfinite_or_missing_metrics_cannot_be_six_metrics(self):
        valid = SixMetrics(0, 10, 24, 0, 1, 0)
        for changes in ({"task_loss": None}, {"execution_ms": math.nan}, {"peak_memory_mb": math.inf},
                        {"state_entropy": -1}, {"invariant_violation": True}, {"invariant_violation": 2},
                        {"complexity_delta": 0.5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(valid, **changes)

    def test_second_observation_does_not_reuse_a_previous_success(self):
        provider = Mock()
        provider.observe.side_effect = [observation(), TimeoutError("lost second measurement")]
        seam = RcxiObservationPort(provider)
        self.assertEqual(seam.observe("synthetic-attempt", "a" * 64).status, "SUCCESS")
        self.assertEqual(seam.observe("second-attempt", "b" * 64).status, "UNAVAILABLE")
        self.assertEqual(seam.evaluate(None).status, "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
