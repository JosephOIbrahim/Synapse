"""SYNTHETIC fixtures only; no real images, credentials or API operation IDs."""
from dataclasses import replace
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from synapse.worldlabs.atlas import (
    AtlasAdapter, AtlasNotEnabled, SyntheticFixtureBinding, SyntheticFixtureEnvelope, SyntheticFixtureTransport,
    parse_fixture_operation, plan_pose, provenance,
)
from synapse.worldlabs.atlas_contracts import (
    AssetRef, CameraIntrinsics, CameraPose, ContractError, PosedRGBDFrame, mask_depth, unproject_metric,
)


def asset(identity, media="image/png"):
    # These identify synthetic fixture tokens, not validated image/EXR files.
    return AssetRef("SYNTHETIC-" + identity, hashlib.sha256(("SYNTHETIC:" + identity).encode()).hexdigest(), media)


def frame(row_order="top_down", axes="rdf", scale=1.0):
    return PosedRGBDFrame("frame-a", asset("rgb-a"), asset("depth-a", "image/x-exr"), asset("confidence-a"),
                          CameraIntrinsics(2, 2, 1, 1, 0, 0),
                          CameraPose((0, 0, 0), (0, 0, 0, 1), axes, "SYNTHETIC-world"),
                          "linear_exr_half", row_order, scale)


def fixture():
    plan = plan_pose((("frame-a", asset("input-a")), ("frame-b", asset("input-b"))))
    assets = {}
    rows = []
    outputs = []
    for name in ("a", "b"):
        rgb, depth, confidence = asset("rgb-" + name), asset("depth-" + name, "image/x-exr"), asset("confidence-" + name)
        assets.update({value.asset_id: value for value in (rgb, depth, confidence)})
        outputs.append((rgb, depth, confidence))
        rows.append({"imageAsset": {"assetId": rgb.asset_id, "url": "https://asset.invalid/private?signature=SECRET"},
                     "camera": {"intrinsics": {"width": 2, "height": 2, "fx": 1, "fy": 1, "cx": 0, "cy": 0},
                                "extrinsics": {"position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "coordinateSystem": "rdf"}},
                     "depth": {"depthAsset": {"assetId": depth.asset_id}, "confidenceAsset": {"assetId": confidence.asset_id}}})
    payload = {"id": "SYNTHETIC-op-pose", "metadata": {"task": "images2PosedRGBD"},
               "done": True, "error": None, "response": {"frames": rows},
               "ownerId": "SECRET-OWNER", "authorization": "SECRET-KEY"}
    binding = SyntheticFixtureBinding(plan.request_id, tuple(row[0] for row in plan.frames), tuple(outputs),
                                      payload["id"], "SYNTHETIC-world")
    return plan, SyntheticFixtureEnvelope(binding, payload), assets


class AtlasScaffoldTests(unittest.TestCase):
    def test_camera_contract_rejects_invalid_values(self):
        for change in ({"width": True}, {"width": 0}, {"fx": 0}, {"cy": math.inf}):
            params = {"width": 2, "height": 2, "fx": 1, "fy": 1, "cx": 0, "cy": 0, **change}
            with self.subTest(change=change), self.assertRaises(ContractError):
                CameraIntrinsics(**params)

    def test_pose_requires_unit_xyzw_and_explicit_axes(self):
        for quat, axes in (((0, 0, 0, 0), "rdf"), ((0, 0, 0, 2), "rdf"), ((0, math.nan, 0, 1), "rdf"), ((0, 0, 0, 1), "unknown")):
            with self.subTest(quat=quat, axes=axes), self.assertRaises(ContractError):
                CameraPose((0, 0, 0), quat, axes, "fixture-world")

    def test_synthetic_plane_has_hand_computed_points(self):
        # x=(u-0)*2/1 and y=(v-0)*2/1 at depth 2; every z is 2.
        self.assertEqual(unproject_metric(frame(), [2, 2, 2, 2]),
                         ((0, 0, 2), (2, 0, 2), (0, 2, 2), (2, 2, 2)))

    def test_rub_changes_camera_basis_not_only_a_label(self):
        self.assertEqual(unproject_metric(frame(axes="rub"), [2, 2, 2, 2]),
                         ((0, 0, -2), (2, 0, -2), (0, -2, -2), (2, -2, -2)))

    def test_quaternion_rotation_and_world_scale(self):
        original = frame(scale=0.5)
        # A 180-degree rotation around Y maps forward +Z to -Z; position is (2,0,0).
        rotated = replace(original, pose=CameraPose((2, 0, 0), (0, 1, 0, 0), "rdf", "fixture-world"))
        self.assertEqual(unproject_metric(rotated, [2, 2, 2, 2])[0], (1, 0, -1))

    def test_decoder_row_order_is_explicit_and_not_globally_flipped(self):
        top = unproject_metric(frame(), [1, 2, 3, 4])
        bottom = unproject_metric(frame(row_order="bottom_up"), [3, 4, 1, 2])
        self.assertEqual(top, bottom)
        self.assertNotEqual(top, unproject_metric(frame(), [3, 4, 1, 2]))

    def test_unknown_scale_refuses_metric_output(self):
        unknown = frame(scale=None)
        self.assertIsNone(unknown.metres_per_unit)
        with self.assertRaises(ContractError):
            unproject_metric(unknown, [2] * 4)

    def test_invalid_depths_are_masked(self):
        self.assertEqual(mask_depth([2, math.nan, math.inf, -1, 0]), (2, None, None, None, None))
        self.assertEqual(unproject_metric(frame(), [2, math.nan, math.inf, -1]), ((0, 0, 2), None, None, None))

    def test_unknown_depth_encoding_or_asset_format_refuses(self):
        with self.assertRaises(ContractError):
            replace(frame(), depth_encoding="mystery_png")
        with self.assertRaises(ContractError):
            asset("unknown", "application/unknown")
        with self.assertRaises(ContractError):
            replace(frame(), decoded_row_order="unknown")

    def test_frame_reordering_changes_identity(self):
        first = (("frame-a", asset("a")), ("frame-b", asset("b")))
        self.assertNotEqual(plan_pose(first).request_id, plan_pose(first[::-1]).request_id)
        self.assertEqual(plan_pose(first).request_id, plan_pose(first).request_id)

    def test_frame_order_and_content_are_both_identity_bound(self):
        first = plan_pose((("frame-a", asset("a")),))
        second = plan_pose((("frame-a", asset("different-content")),))
        self.assertNotEqual(first.request_id, second.request_id)

    def test_fixture_pending_success_and_error_remain_distinct(self):
        plan, payload, assets = fixture()
        success = parse_fixture_operation(payload, plan, assets)
        self.assertEqual(success.phase, "SUCCEEDED")
        self.assertEqual(tuple(item.frame_id for item in success.frames), ("frame-a", "frame-b"))
        pending = payload.with_operation(done=False, response=None)
        self.assertEqual(parse_fixture_operation(pending, plan, assets).phase, "PENDING")
        failed = payload.with_operation(response=None, error={"message": "SECRET-KEY"})
        error = parse_fixture_operation(failed, plan, assets)
        self.assertEqual((error.phase, error.error_code), ("FAILED", "provider_error"))
        self.assertNotIn("SECRET", repr(error))

    def test_ambiguous_partial_or_wrong_family_operations_refuse(self):
        plan, payload, assets = fixture()
        for changed in (payload.with_operation(done=False), payload.with_operation(done="true"),
                        payload.with_operation(error={"code": 1}), payload.with_operation(response=None),
                        payload.with_operation(metadata=[]), payload.with_operation(operation_id=payload["id"], id=None)):
            with self.subTest(changed=changed), self.assertRaises(ContractError):
                parse_fixture_operation(changed, plan, assets)
        with self.assertRaises(ContractError):
            parse_fixture_operation(payload, plan, assets, api_family="marble_v1")

    def test_missing_fixture_asset_bytes_never_invent_a_hash(self):
        plan, payload, assets = fixture()
        with self.assertRaises(ContractError):
            parse_fixture_operation(payload, plan, {})

    def test_real_looking_ids_cannot_be_claimed_as_synthetic_operations(self):
        plan, payload, assets = fixture()
        with self.assertRaises(ContractError):
            parse_fixture_operation(payload.with_operation(id="op-real-looking"), plan, assets)

    def test_provenance_is_ordered_and_excludes_secrets_and_urls(self):
        plan, payload, assets = fixture()
        manifest = provenance(plan, parse_fixture_operation(payload, plan, assets))
        self.assertEqual(manifest.input_sha256, tuple(value.content_sha256 for _, value in plan.frames))
        self.assertEqual(manifest.frame_ids, ("frame-a", "frame-b"))
        self.assertEqual(manifest.evidence_tier, "SYNTHETIC")
        for forbidden in ("SECRET", "url", "authorization", "ownerId", "signature"):
            self.assertNotIn(forbidden, manifest.to_json())

    def test_provenance_rejects_changed_inputs_after_parsing(self):
        plan, payload, assets = fixture()
        operation = parse_fixture_operation(payload, plan, assets)
        changed = plan_pose((("frame-a", asset("different-input")), plan.frames[1]))
        with self.assertRaises(ContractError):
            provenance(changed, operation)

    def test_disabled_cannot_submit_upload_resume_or_read_assets_even_with_flag(self):
        client = Mock()
        adapter = AtlasAdapter(client)
        plan, _, _ = fixture()
        with patch.dict(os.environ, {"SYNAPSE_ATLAS_LANE": "1", "WLT_API_KEY": "DO-NOT-READ-SECRET"}):
            self.assertEqual(adapter.status()["state"], "DISABLED")
            for call in (lambda: adapter.submit(plan), lambda: adapter.upload(b"user-media"),
                         lambda: adapter.resume("operation"),
                         lambda: adapter.read_asset("https://asset.invalid/?signature=SECRET", headers={"WLT-Api-Key": "SECRET"})):
                with self.assertRaises(AtlasNotEnabled) as result:
                    call()
                self.assertNotIn("SECRET", str(result.exception))
        self.assertEqual(client.mock_calls, [])

    def test_only_explicit_memory_fixture_transport_runs(self):
        plan, payload, assets = fixture()
        adapter = AtlasAdapter(Mock())
        self.assertEqual(adapter.run_fixture(plan, SyntheticFixtureTransport(payload, assets)).phase, "SUCCEEDED")
        callback = Mock()
        with self.assertRaises(AtlasNotEnabled):
            adapter.run_fixture(plan, callback)
        callback.assert_not_called()

    def test_import_does_not_access_network_houdini_or_files(self):
        import builtins
        import socket
        before = set(sys.modules)
        real_import = builtins.__import__
        def guard(name, *args, **kwargs):
            if name.split(".")[0] in {"hou", "pxr", "PySide6", "PySide2"}:
                raise AssertionError("Houdini/Qt import forbidden")
            return real_import(name, *args, **kwargs)
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                patch("builtins.open", side_effect=AssertionError("I/O forbidden")), \
                patch.object(Path, "open", side_effect=AssertionError("I/O forbidden")), \
                patch.object(Path, "mkdir", side_effect=AssertionError("I/O forbidden")), \
                patch("builtins.__import__", side_effect=guard):
            for original in ("atlas_contracts", "atlas"):
                path = sys.modules["synapse.worldlabs." + original].__file__
                name = "synapse.worldlabs._import_probe_" + original
                spec = importlib.util.spec_from_file_location(name, path)
                fresh = importlib.util.module_from_spec(spec)
                with patch.dict(sys.modules, {name: fresh}):
                    spec.loader.exec_module(fresh)
        self.assertFalse(({"hou", "pxr", "PySide6"} - before) & set(sys.modules))


if __name__ == "__main__":
    unittest.main(verbosity=2)
