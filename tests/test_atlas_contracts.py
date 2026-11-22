"""Atlas camera/depth contracts (python/synapse/worldlabs/atlas_contracts.py). SYNTHETIC fixtures only.

These tests came from tests/test_atlas_scaffold.py and tests/test_scaffold_review_regressions.py when the dormant
Atlas executor scaffold (worldlabs/atlas.py) was retired for the read-only Atlas v2 client (2026-11-22). The contracts
stay: the HD1 physical-frame track builds on them. The tests that exercised only the retired scaffold's fixture
binding, plan identity and adapter went with it.
"""
from dataclasses import replace
import hashlib
import importlib
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

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


class AtlasContractTests(unittest.TestCase):
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
            path = sys.modules["synapse.worldlabs.atlas_contracts"].__file__
            name = "synapse.worldlabs._import_probe_atlas_contracts"
            spec = importlib.util.spec_from_file_location(name, path)
            fresh = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {name: fresh}):
                spec.loader.exec_module(fresh)
        self.assertFalse(({"hou", "pxr", "PySide6"} - before) & set(sys.modules))


if __name__ == "__main__":
    unittest.main(verbosity=2)
