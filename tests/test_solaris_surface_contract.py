"""Real in-memory USD shader oracle; no Houdini, memory owner, render or file export."""
from types import SimpleNamespace
import pytest

pytest.importorskip("pxr.Usd", reason="Requires a real OpenUSD runtime")
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade
if not isinstance(getattr(Usd, "Stage", None), type):
    pytest.skip("A real OpenUSD stage is required", allow_module_level=True)
from synapse.server.solaris_lookdev import _verify_stage


class AttributeProxy:
    """Houdini op: resolver only; never substitutes a shader or USD connection."""
    def __init__(self, path):
        self.path = path
    def Get(self):
        return SimpleNamespace(path=self.path, resolvedPath=self.path)


class MaterialProxy:
    def __init__(self, prim):
        self.prim = prim
    def __bool__(self):
        return bool(self.prim)
    def GetTypeName(self):
        return self.prim.GetTypeName()
    def GetAttribute(self, name):
        if name == "inputs:base_color_file":
            return AttributeProxy("op:/color{layer}")
        if name == "inputs:specular_roughness_file":
            return AttributeProxy("op:/roughness{noise}")
        return self.prim.GetAttribute(name)


class StageProxy:
    def __init__(self, stage):
        self.stage = stage
    def GetPrimAtPath(self, path):
        prim = self.stage.GetPrimAtPath(path)
        return MaterialProxy(prim) if path == "/materials/look" else prim
    def GetAttributeAtPath(self, path):
        return self.stage.GetAttributeAtPath(path)


def make_stage(defect):
    stage = Usd.Stage.CreateInMemory()
    mesh = UsdGeom.Mesh.Define(stage, "/mesh")
    mesh.CreatePointsAttr([(-1, -1, 0), (1, -1, 0), (-1, 1, 0), (1, 1, 0)])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 3, 2])
    mesh.CreateOrientationAttr("leftHanded")
    mesh.CreateSubdivisionSchemeAttr("none")
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, "faceVarying")
    st.Set([(0, 0), (1, 0), (1, 1), (0, 1)])
    mesh.GetPrim().CreateRelationship("material:binding").SetTargets(["/materials/look"])
    material = UsdShade.Material.Define(stage, "/materials/look")
    for name, typ, value in (("base_color", Sdf.ValueTypeNames.Color3f, (1, 1, 1)),
                             ("base_color_primvar", Sdf.ValueTypeNames.String, ""),
                             ("specular_roughness", Sdf.ValueTypeNames.Float, 1.0),
                             ("roughness_primvar", Sdf.ValueTypeNames.String, ""),
                             ("uv_primvar", Sdf.ValueTypeNames.String, "st")):
        material.CreateInput(name, typ).Set(value)
    if defect == "non_shader_target":
        target = stage.DefinePrim("/materials/look/not_a_shader", "Scope")
        target.CreateAttribute("outputs:out", Sdf.ValueTypeNames.Token)
        target_path = "/materials/look/not_a_shader.outputs:out"
    else:
        target = UsdShade.Shader.Define(stage, "/materials/look/surface")
        target.CreateIdAttr("UsdPreviewSurface" if defect == "wrong_shader" else "ND_standard_surface_surfaceshader")
        output_name = "not_in_nodedef" if defect == "invented_output" else "out"
        output_type = Sdf.ValueTypeNames.Float if defect == "float_output" else Sdf.ValueTypeNames.Token
        target.CreateOutput(output_name, output_type)
        target_path = "/materials/look/surface.outputs:" + output_name
    if defect == "missing_target":
        target_path = "/materials/look/missing.outputs:out"
    elif defect == "input_target":
        target.CreateInput("wrong", Sdf.ValueTypeNames.Token)
        target_path = "/materials/look/surface.inputs:wrong"
    elif defect == "nodegraph":
        graph = UsdShade.NodeGraph.Define(stage, "/materials/look/graph")
        graph.CreateOutput("surface", Sdf.ValueTypeNames.Token).GetAttr().SetConnections([target_path])
        target_path = "/materials/look/graph.outputs:surface"
    if defect == "float_material_output":
        material.GetPrim().CreateAttribute("outputs:mtlx:surface", Sdf.ValueTypeNames.Float).SetConnections([target_path])
    else:
        material.CreateSurfaceOutput("mtlx").GetAttr().SetConnections([target_path])
    UsdGeom.Camera.Define(stage, "/camera")
    settings = stage.DefinePrim("/settings", "RenderSettings")
    settings.CreateRelationship("camera").SetTargets(["/camera"])
    settings.CreateAttribute("resolution", Sdf.ValueTypeNames.Int2).Set(Gf.Vec2i(256, 256))
    return stage, material, target_path


def inspect_case(defect):
    stage, material, target_path = make_stage(defect)
    oracle_shader, source_name, source_type = material.ComputeSurfaceSource("mtlx")
    output = SimpleNamespace(stage=lambda **kw: StageProxy(stage), errors=lambda: ())
    color = SimpleNamespace(path=lambda: "/color", outputNames=lambda: ("layer",))
    roughness = SimpleNamespace(path=lambda: "/roughness", outputNames=lambda: ("noise",))
    try:
        result = _verify_stage(output, "/mesh", "/materials/look", color, roughness, "/camera", "/settings")
    except Exception as exc:
        result = {"raised": type(exc).__name__, "reason": str(exc)}
    return {"case": defect, "target_attribute_exists": bool(stage.GetAttributeAtPath(target_path)),
            "usd_computes_surface_shader": bool(oracle_shader),
            "source_name": str(source_name), "production_verdict": result}


@pytest.mark.parametrize("case", ["valid_shader", "nodegraph"])
def test_resolved_standard_surface_is_verified(case):
    observed = inspect_case(case)
    assert observed["usd_computes_surface_shader"]
    assert observed["production_verdict"].get("usd") == "verified", observed


@pytest.mark.parametrize("case", ["missing_target", "non_shader_target", "wrong_shader", "input_target",
                                  "invented_output", "float_output", "float_material_output"])
def test_unresolved_or_wrong_surface_is_rejected(case):
    observed = inspect_case(case)
    assert observed["production_verdict"].get("raised") == "RuntimeError", observed
