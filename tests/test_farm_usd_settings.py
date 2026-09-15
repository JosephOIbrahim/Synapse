"""Synthetic USD-only controls. Never imports hou or executes a renderer."""
from pathlib import Path
import json
import sys

import pytest

WORKTREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKTREE / "python"))
from synapse.farm.native_driver import _localize_usd
pytest.importorskip("pxr")
from pxr import Gf, Sdf, Usd


@pytest.mark.parametrize("animated", [False, True])
def test_localized_usd_uses_reviewed_sample_budget(tmp_path, animated):
    package_root = tmp_path / "package"
    package_root.mkdir()
    usd_path = package_root / "frame.usda"
    stage = Usd.Stage.CreateNew(str(usd_path))
    stage.DefinePrim("/camera", "Camera")
    settings = stage.DefinePrim("/settings", "RenderSettings")
    settings.CreateRelationship("camera").SetTargets(["/camera"])
    settings.CreateRelationship("products").SetTargets(["/product"])
    product = stage.DefinePrim("/product", "RenderProduct")
    product.CreateAttribute("productName", Sdf.ValueTypeNames.Token).Set("original.exr")
    settings.CreateAttribute("resolution", Sdf.ValueTypeNames.Int2).Set(Gf.Vec2i(64, 64))
    sample_keys = ("karma:global:samplesperpixel", "karma:global:pathtracedsamples")
    for key in sample_keys:
        attr = settings.CreateAttribute(key, Sdf.ValueTypeNames.Int)
        if animated:
            attr.Set(128, Usd.TimeCode(1))
            attr.Set(256, Usd.TimeCode(2))
        else:
            attr.Set(128)
    stage.SetMetadata("renderSettingsPrimPath", "/settings")
    stage.GetRootLayer().Save()
    plan = {"width": 256, "height": 256, "samples": 8}
    _localize_usd(usd_path, package_root, tmp_path / "outputs/beauty.exr", plan)
    reloaded = Usd.Stage.Open(str(usd_path))
    values = {key: {"default": reloaded.GetPrimAtPath("/settings").GetAttribute(key).Get(),
        "frame1": reloaded.GetPrimAtPath("/settings").GetAttribute(key).Get(Usd.TimeCode(1)),
        "frame2": reloaded.GetPrimAtPath("/settings").GetAttribute(key).Get(Usd.TimeCode(2))}
        for key in sample_keys}
    (tmp_path / "sample-budget-evidence.json").write_text(json.dumps(values, indent=2), encoding="utf-8")
    assert all(value == plan["samples"] for entry in values.values() for value in entry.values()), values
