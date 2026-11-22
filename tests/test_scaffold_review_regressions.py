"""Review-selected port-envelope regressions; no live executor.

The Atlas fixture-binding regressions that lived here exercised the dormant Atlas executor scaffold
(worldlabs/atlas.py), retired 2026-11-22 for the read-only Atlas v2 client. The contract-only overflow test moved
to tests/test_atlas_contracts.py.
"""
import unittest
from unittest.mock import Mock

from synapse.loop.ports import PortResult
from synapse.loop.rcxi_ports import SubstrateSeams


class PortEnvelopeRegressionTests(unittest.TestCase):
    def test_invalid_envelopes_block_without_relabeling_as_substrate_absence(self):
        stage = Mock()
        invalid = (PortResult([], {}), PortResult("UNAVAILABLE"), PortResult("BLOCKED", {}, "  "),
                   PortResult("SUCCESS", {"context": {}}, "failed"), PortResult("SUCCESS", []),
                   PortResult("SUCCESS", {"context": []}), PortResult("UNAVAILABLE", [], "pending"))
        for value in invalid:
            stage.compose_sanitized_stage.return_value = value
            with self.subTest(value=value):
                self.assertEqual(SubstrateSeams(stage=stage).compose_sanitized_stage("fixture").status, "BLOCKED")

    def test_operation_payloads_and_pending_diagnostics_are_preserved(self):
        ledger = Mock()
        seam = SubstrateSeams(ledger=ledger)
        for payload in ({"seq": 1}, {"forecast_digest": "a" * 64, "state": "FORECAST_PERSISTED"}):
            result = PortResult.ok(payload)
            ledger.author_precommit.return_value = result
            self.assertIs(seam.author_precommit("claim", 0.5, "world"), result)
        for payload in ({}, {"seq": True}, {"seq": 0}, {"forecast_digest": "bad"}):
            ledger.author_precommit.return_value = PortResult.ok(payload)
            self.assertEqual(seam.author_precommit("claim", 0.5, "world").status, "BLOCKED")
        for result in (PortResult("UNAVAILABLE", {"state": "PENDING", "ack": "known"}, "pending evidence"),
                       PortResult.ok({"state": "HIT", "outcome": {"claim": True}})):
            ledger.settle.return_value = result
            self.assertIs(seam.settle("turn"), result)
        ledger.settle.return_value = PortResult.ok({"settled": True})
        self.assertEqual(seam.settle("turn").status, "BLOCKED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
