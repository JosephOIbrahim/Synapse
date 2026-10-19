"""Review-selected failures and composed fixture controls; no live executor."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from test_atlas_scaffold import asset, fixture, frame
from synapse.worldlabs.atlas import SyntheticFixtureEnvelope, SyntheticFixtureTransport, parse_fixture_operation, plan_pose, provenance
from synapse.worldlabs.atlas_contracts import CameraIntrinsics, CameraPose, ContractError, unproject_metric
from synapse.loop.ports import PortResult
from synapse.loop.rcxi_ports import SubstrateSeams


class FixtureBindingTests(unittest.TestCase):
    def test_changed_inputs_order_and_terminal_states_cannot_rebind(self):
        plan, payload, assets = fixture()
        changed = (plan_pose(plan.frames[::-1]), plan_pose((("frame-a", asset("unrelated")), plan.frames[1])))
        states = (payload, payload.with_operation(done=False, response=None),
                  payload.with_operation(response=None, error={"message": "private"}))
        transport = SyntheticFixtureTransport(payload, assets)
        self.assertEqual(transport.run(plan).phase, "SUCCEEDED")
        for other in changed:
            for state in states:
                with self.subTest(request=other.request_id, done=state["done"]), self.assertRaises(ContractError):
                    parse_fixture_operation(state, other, assets)
            with self.assertRaises(ContractError):
                transport.run(other)
        self.assertEqual(transport.run(plan).phase, "SUCCEEDED")

    def test_unbound_provider_dict_is_refused_and_binding_is_fixed(self):
        plan, payload, assets = fixture()
        with self.assertRaises(ContractError):
            parse_fixture_operation(dict(payload), plan, assets)
        with self.assertRaises(ContractError):
            SyntheticFixtureTransport(dict(payload), assets)
        with self.assertRaises(AttributeError):
            payload._binding = replace(payload.binding, request_sha256="b" * 64)
        copied = deepcopy(payload)
        self.assertIsInstance(copied, SyntheticFixtureEnvelope)
        self.assertEqual(copied.binding, payload.binding)

    def test_output_order_and_supplied_bytes_remain_bound(self):
        plan, payload, assets = fixture()
        changed = deepcopy(payload)
        changed["response"]["frames"].reverse()
        with self.assertRaises(ContractError):
            parse_fixture_operation(changed, plan, assets)
        changed_assets = dict(assets)
        original = payload.binding.output_assets[0][0]
        changed_assets[original.asset_id] = replace(original, content_sha256="c" * 64)
        with self.assertRaises(ContractError):
            parse_fixture_operation(payload, plan, changed_assets)

    def test_success_requires_common_world_and_unique_ids_but_axes_can_differ(self):
        plan, payload, assets = fixture()
        operation = parse_fixture_operation(payload, plan, assets)
        first, second = operation.frames
        with self.assertRaises(ContractError):
            replace(operation, frames=(first, replace(second, frame_id=first.frame_id)))
        with self.assertRaises(ContractError):
            replace(operation, frames=(first, replace(second, pose=replace(second.pose, world_frame="other"))))
        different_axes = replace(second, pose=replace(second.pose, coordinate_system="rub"))
        self.assertEqual(replace(operation, frames=(first, different_axes)).phase, "SUCCEEDED")

    def test_spatial_digest_covers_camera_world_decoder_and_scale(self):
        plan, payload, assets = fixture()
        operation = parse_fixture_operation(payload, plan, assets)
        original = provenance(plan, operation)
        first, second = operation.frames
        changes = (
            replace(first, intrinsics=replace(first.intrinsics, fx=2)),
            replace(first, pose=replace(first.pose, position=(100, 200, 300))),
            replace(first, decoded_row_order="bottom_up"),
            replace(first, metres_per_unit=0.1),
        )
        for altered in changes:
            changed = provenance(plan, replace(operation, frames=(altered, second)))
            self.assertEqual(changed.output_sha256, original.output_sha256)
            self.assertNotEqual(changed.spatial_result_sha256, original.spatial_result_sha256)
        world_changed = replace(operation, frames=tuple(replace(row, pose=replace(row.pose, world_frame="other")) for row in operation.frames))
        self.assertNotEqual(provenance(plan, world_changed).spatial_result_sha256, original.spatial_result_sha256)

    def test_overflow_at_camera_rotation_translation_and_scaling_is_refused(self):
        base = frame()
        extreme = (
            (replace(base, intrinsics=CameraIntrinsics(2, 2, 1e-308, 1, 0, 0)), [1e308] * 4),
            (replace(base, pose=CameraPose((0, 0, 0), (0, 1, 0, 0), "rdf", "world")), [1e308] * 4),
            (replace(base, pose=replace(base.pose, position=(0, 0, 1e308))), [1e308] * 4),
            (replace(base, metres_per_unit=1e308), [2] * 4),
        )
        for posed, depths in extreme:
            with self.subTest(posed=posed), self.assertRaises(ContractError):
                unproject_metric(posed, depths)


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
