"""Headless H22 adapter tests; never run against an artist GUI.

These exercise real HostObserver reads when real hou is already resident.
They are adapter probes, not golden-scene/render qualification.
"""
import sys
import uuid

import pytest

from synapse.recipes.contracts import (
    CheckId, CheckStatus, RecipeInstance, RecipeSpec, SUPPORTED_BUILD,
)
from synapse.recipes.verify import (
    GraphVerifier, USDVerifier, RenderReadinessVerifier, CompositionVerifier,
    HostObserver,
)

_hou = sys.modules.get("hou")
pytestmark = pytest.mark.skipif(
    _hou is None or not getattr(_hou, "__file__", None)
    or getattr(_hou, "__synapse_canonical__", False) is True,
    reason="NOT_RUN: real hou is not resident; run with H22.0.400 headless hython",
)


@pytest.fixture
def host_scene(tmp_path):
    from synapse.server.main_thread import run_on_main
    from synapse.core.mtlx_types import MTLX_STANDARD_SURFACE

    def create():
        if _hou.isUIAvailable():
            pytest.skip("NOT_RUN: live Houdini GUI is a per-act human gate; use headless hython")
        if _hou.applicationVersionString() != SUPPORTED_BUILD:
            pytest.skip("NOT_RUN: adapter qualification is pinned to " + SUPPORTED_BUILD)
        parent = _hou.node("/stage")
        assert parent is not None, "headless /stage must exist"
        scope = parent.createNode("subnet", "verify_" + uuid.uuid4().hex)
        try:
            scene = scope.createNode("pythonscript", "scene")
            render = scope.createNode("usdrender_rop", "render")
            render.setInput(0, scene)
            matlib = scope.createNode("materiallibrary", "materials")
            shader = matlib.createNode(MTLX_STANDARD_SURFACE, "hero_shader")
            color = shader.parmTuple("base_color")
            assert color is not None, "captured base_color interface unavailable"
            color.set((0.5, 0.2, 0.1))
            output_path = str(tmp_path / "never_rendered.exr").replace("\\", "/")
            code = (
                "from pxr import UsdShade, UsdRender, Sdf\n"
                "stage = hou.pwd().editableStage()\n"
                "hero = stage.DefinePrim('/hero', 'Sphere')\n"
                "ground = stage.DefinePrim('/ground', 'Mesh')\n"
                "material = UsdShade.Material.Define(stage, '/materials/hero')\n"
                "shader = UsdShade.Shader.Define(stage, '/materials/hero/surface')\n"
                "shader.CreateIdAttr().Set('UsdPreviewSurface')\n"
                "out = shader.CreateOutput('surface', Sdf.ValueTypeNames.Token)\n"
                "material.CreateSurfaceOutput().ConnectToSource(out)\n"
                "UsdShade.MaterialBindingAPI.Apply(hero).Bind(material)\n"
                "UsdShade.MaterialBindingAPI.Apply(ground).Bind(material)\n"
                "stage.DefinePrim('/camera', 'Camera')\n"
                "stage.DefinePrim('/lights/key', 'RectLight')\n"
                "stage.DefinePrim('/lights/dome', 'DomeLight')\n"
                "settings = UsdRender.Settings.Define(stage, '/Render/intended')\n"
                "settings.CreateCameraRel().SetTargets(['/camera'])\n"
                "product = UsdRender.Product.Define(stage, '/Render/product')\n"
                "product.CreateProductNameAttr().Set(" + repr(output_path) + ")\n"
                "var = UsdRender.Var.Define(stage, '/Render/beauty')\n"
                "var.CreateSourceNameAttr().Set('C')\n"
                "var.CreateDataTypeAttr().Set('color3f')\n"
                "product.CreateOrderedVarsRel().SetTargets(['/Render/beauty'])\n"
                "settings.CreateProductsRel().SetTargets(['/Render/product'])\n"
            )
            scene.parm("python").set(code)
            handles = {"scene": scene, "render": render, "material": matlib, "shader": shader}
            records = tuple({
                "id": key, "parent_id": "material" if key == "shader" else None,
                "category": handle.type().category().name(), "type": handle.type().name(),
                "parms": {"base_color": {"type": "color3", "value": [0.5, 0.2, 0.1]}} if key == "shader" else {},
                "flags": {},
            } for key, handle in handles.items())
            edge = {"src_id": "scene", "src_output": 0, "dst_id": "render", "dst_input": 0}
            requirements = {
                "stage_node_id": "scene", "render_settings_path": "/Render/intended",
                "render_input_connections": [edge],
                "expected_prims": [
                    {"path": "/hero", "type": "Sphere", "material": "/materials/hero",
                     "surface_shader": "/materials/hero/surface", "shader_id": "UsdPreviewSurface"},
                    {"path": "/ground", "type": "Mesh", "material": "/materials/hero"},
                ],
            }
            spec = RecipeSpec("adapter.probe", "1", "2", SUPPORTED_BUILD, "probe", "probe",
                              "unqualified", "layout", {"verification": requirements},
                              records, (edge,), ())
            instance = RecipeInstance("adapter", spec.recipe_id, spec.version,
                                      {key: handle.path() for key, handle in handles.items()},
                                      {}, 0, "unqualified")
            return scope, handles, instance, spec
        except BaseException:
            scope.destroy()
            raise
    scope, handles, instance, spec = run_on_main(create)
    try:
        yield handles, instance, spec
    finally:
        run_on_main(lambda: scope.destroy())


def test_hython_real_graph_nested_typed_color_and_exact_ports(host_scene):
    handles, instance, spec = host_scene
    result = GraphVerifier().run(CheckId.P1_GRAPH, instance, spec)
    assert result.status == CheckStatus.PASS, result


def test_hython_real_stage_material_surface_and_composition(host_scene):
    handles, instance, spec = host_scene
    for cls in (USDVerifier, CompositionVerifier):
        verifier = cls()
        result = verifier.run(verifier.check_id, instance, spec)
        assert result.status == CheckStatus.PASS, result


def test_hython_t7_readiness_branch_removed_camera_remains_valid(host_scene):
    from synapse.server.main_thread import run_on_main
    handles, instance, spec = host_scene
    verifier = RenderReadinessVerifier()
    before = verifier.run(CheckId.P3_RENDER_READY, instance, spec)
    assert before.status == CheckStatus.PASS, before
    run_on_main(lambda: handles["render"].setInput(0, None))
    after = verifier.run(CheckId.P3_RENDER_READY, instance, spec)
    assert after.status == CheckStatus.FAIL, after
    assert after.evidence["clauses"]["camera"] == "pass"
    assert after.evidence["clauses"]["render_input_branch"] == "fail"


def test_hython_t9_missing_stage_lop_never_passes(host_scene):
    handles, instance, spec = host_scene
    instance.owned_node_ids["scene"] += "_absent"
    for cls in (USDVerifier, RenderReadinessVerifier):
        verifier = cls()
        result = verifier.run(verifier.check_id, instance, spec)
        assert result.status == CheckStatus.UNKNOWN
        assert "missing" in result.reason
