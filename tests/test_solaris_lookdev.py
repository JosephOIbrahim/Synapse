"""Fixed lookdev input contract: reject ambiguity before entering Houdini."""
import pytest
from unittest.mock import MagicMock

from synapse.server.solaris_lookdev import validate_request, _set, _material_wire, _verify_stage, build_lookdev, _restore_flags


def request(**kwargs):
    return {"template": "copernicus_lookdev", **kwargs}


def test_fixed_defaults_and_color_are_explicit():
    result = validate_request(request())
    assert result["parent"] == "/stage"
    assert result["resolution"] == [256, 256]
    assert result["base_color"] == [0.18, 0.04, 0.01]
    assert result["dry_run"] is False


@pytest.mark.parametrize("payload", [
    {"template": "other"}, {"template": "copernicus_lookdev", "execute_python": "anything"},
    request(nodes=[{"id": "override"}]), request(connections=[{"from": "x", "to": "y"}]),
    request(nodes=None), request(nodes={}), request(display_node="output"), request(relayout=True),
    request(relayout=0), request(dry_run="false"), request(dry_run=1), request(layout="diagonal"),
    request(parent="relative"), request(parent="/stage/../obj"), request(parent=None),
    request(template_params=None), request(template_params=[]), request(template_params={"resolution": [8192, 8192]}),
    *[request(template_params={"name": name}) for name in ("", "../artist", "with spaces", "x"*65, "1name")],
    *[request(template_params={"base_color": color}) for color in ([0, 0], [True, 0, 0], [float("nan"), 0, 0], [float("inf"), 0, 0], [-.1, 0, 0], [1.1, 0, 0], ["red", 0, 0])],
    *[request(template_params={"frequency": value}) for value in (0, -1, float("nan"), True)],
    request(template_params={"noise_type": "legacy"}), request(template_params={"octaves": 2.5}),
])
def test_ambiguous_or_unbounded_requests_are_rejected(payload):
    with pytest.raises(ValueError):
        validate_request(payload)


def test_request_values_are_copied_and_finite():
    color=[.1, .2, .3]
    result=validate_request(request(parent="/stage/shot", layout="horizontal", dry_run=True,
                                    template_params={"name":"look_2", "base_color":color, "noise_type":"simplex", "octaves":4, "frequency":2}))
    color[0]=.9
    assert result["base_color"] == [.1, .2, .3]
    assert result["frequency"] == 2
    assert result["layout"] == "horizontal"


def test_huge_color_does_not_overflow_validation():
    with pytest.raises(ValueError):
        validate_request(request(template_params={"base_color": [10**1000, 0, 0]}))


def test_parameter_readback_rejects_silent_ignored_set():
    node = MagicMock()
    node.path.return_value = "/owned/node"
    node.parm.return_value.eval.return_value = 0.1
    with pytest.raises(RuntimeError, match="observed"):
        _set(node, "roughness", 0.6)


@pytest.mark.parametrize("labels,types,outputs", [
    (("different",), ("RGB",), ("RGB",)),
    (("base_color", "base_color"), ("RGB", "RGB"), ("RGB",)),
    (("base_color",), ("Mono",), ("RGB",)),
    (("base_color",), ("RGB",), ("Mono",)),
])
def test_material_port_contract_rejects_label_and_type_drift(labels, types, outputs):
    material, source = MagicMock(), MagicMock()
    material.inputLabels.return_value = labels
    material.inputDataTypes.return_value = types
    source.outputDataTypes.return_value = outputs
    with pytest.raises(RuntimeError):
        _material_wire(material, "base_color", "RGB", source)
    material.setInput.assert_not_called()


def test_semantic_label_is_resolved_to_actual_index_and_read_back():
    material, source = MagicMock(), MagicMock()
    material.inputLabels.return_value = ("base_color", "metalness", "specular_color", "specular_roughness")
    material.inputNames.return_value = ("input1", "input2", "input3", "input4")
    material.inputDataTypes.return_value = ("RGB", "Mono", "RGB", "Mono")
    source.outputDataTypes.return_value = ("Mono",)
    connection = MagicMock()
    connection.inputIndex.return_value = 3
    connection.outputIndex.return_value = 0
    connection.inputNode.return_value = source
    material.inputConnections.return_value = (connection,)
    result = _material_wire(material, "specular_roughness", "Mono", source)
    material.setInput.assert_called_once_with(3, source, 0)
    assert result["name"] == "input4"
    connection.outputIndex.return_value = 1
    with pytest.raises(RuntimeError, match="readback"):
        _material_wire(material, "specular_roughness", "Mono", source)


def test_dry_run_leaves_scene_and_display_untouched():
    hou, parent, sibling = MagicMock(), MagicMock(), MagicMock()
    hou.applicationVersionString.return_value = "22.0.400"
    hou.node.return_value = parent
    parent.path.return_value = "/stage"
    parent.isEditable.return_value = True
    parent.node.return_value = None
    parent.childTypeCategory.return_value.name.return_value = "Lop"
    parent.childTypeCategory.return_value.nodeTypes.return_value = dict.fromkeys(
        ("subnet", "sopnet", "sopimport", "texturemateriallibrary", "camera", "light", "karmarendersettings"))
    parent.children.return_value = (sibling,)
    sibling.path.return_value = "/stage/artist"
    sibling.isDisplayFlagSet.return_value = True
    result = build_lookdev(hou, validate_request(request(dry_run=True)))
    assert result["display_node"] == "/stage/artist"
    assert result["nodes_created"] == []
    parent.createNode.assert_not_called()
    sibling.setDisplayFlag.assert_not_called()
    hou.undos.group.assert_not_called()


@pytest.mark.parametrize("replacement", ["artist", "owner", "new_unowned", "renamed_artist"])
def test_display_restoration_checks_identities_before_any_write(replacement):
    parent, artist, owner = MagicMock(), MagicMock(), MagicMock()
    artist.path.return_value = "/stage/artist"; artist.sessionId.return_value = 11
    owner.path.return_value = "/stage/look"; owner.sessionId.return_value = 12
    artist.isDisplayFlagSet.return_value = False
    owner.isDisplayFlagSet.return_value = True
    children = [artist, owner]
    before = {"/stage/artist": {"id": 11, "flag": True}}
    if replacement == "artist": artist.sessionId.return_value = 99
    if replacement == "renamed_artist": artist.path.return_value = "/stage/renamed"
    if replacement == "owner":
        new_owner = MagicMock()
        new_owner.path.return_value = "/stage/look"; new_owner.sessionId.return_value = 99
        children[1] = new_owner
    if replacement == "new_unowned":
        unowned = MagicMock()
        unowned.path.return_value = "/stage/new_artist"; unowned.sessionId.return_value = 99
        children.append(unowned)
    parent.children.return_value = children
    with pytest.raises(RuntimeError):
        _restore_flags(parent, before, owner)
    for node in children:
        node.setDisplayFlag.assert_not_called()


def test_first_network_can_become_display_without_inventing_prior_state():
    parent, owner = MagicMock(), MagicMock()
    owner.path.return_value = "/stage/look"; owner.sessionId.return_value = 12
    owner.isDisplayFlagSet.return_value = True
    parent.children.return_value = [owner]
    assert _restore_flags(parent, {}, owner, first_display=True) == "/stage/look"
    owner.setDisplayFlag.assert_not_called()


class Attribute:
    def __init__(self, value=None, metadata=None, targets=()):
        self.value, self.metadata, self.targets = value, metadata, targets
    def Get(self): return self.value
    def GetMetadata(self, key): return self.metadata
    def GetTargets(self): return self.targets
    def GetConnections(self): return self.targets


class Prim:
    def __init__(self, type_name, values=None, relationships=None):
        self.type_name, self.values, self.relationships = type_name, values or {}, relationships or {}
    def GetTypeName(self): return self.type_name
    def GetAttribute(self, key): return self.values.get(key, Attribute())
    def GetRelationship(self, key): return Attribute(targets=self.relationships.get(key, ()))


@pytest.fixture
def composed_fixture():
    from types import SimpleNamespace
    mesh = Prim("Mesh", {
        "points": Attribute([(0,0,0)]*4), "faceVertexCounts": Attribute([4]),
        "faceVertexIndices": Attribute([0,1,2,3]),
        "primvars:st": Attribute([(0,0),(1,0),(1,1),(0,1)], "faceVarying"),
    }, {"material:binding": ["/materials/look"]})
    material = Prim("Material", {
        "inputs:base_color": Attribute((1,1,1)), "inputs:base_color_primvar": Attribute(""),
        "inputs:specular_roughness": Attribute(1), "inputs:roughness_primvar": Attribute(""),
        "inputs:uv_primvar": Attribute("st"),
        "inputs:base_color_file": Attribute(SimpleNamespace(path="op:/color{layer}", resolvedPath="op:/color{layer}")),
        "inputs:specular_roughness_file": Attribute(SimpleNamespace(path="op:/roughness{noise}", resolvedPath="op:/roughness{noise}")),
        "outputs:mtlx:surface": Attribute(targets=["/materials/look/mtlx.outputs:out"]),
    })
    settings = Prim("RenderSettings", {"resolution": Attribute([256,256])}, {"camera": ["/camera"]})
    stage = MagicMock()
    prims = {"/mesh":mesh, "/materials/look":material, "/camera":Prim("Camera"), "/settings":settings}
    stage.GetPrimAtPath.side_effect = prims.get
    output, color, roughness = MagicMock(), MagicMock(), MagicMock()
    output.stage.return_value = stage
    output.errors.return_value = ()
    color.path.return_value = "/color"; color.outputNames.return_value = ("layer",)
    roughness.path.return_value = "/roughness"; roughness.outputNames.return_value = ("noise",)
    return (output, "/mesh", "/materials/look", color, roughness, "/camera", "/settings"), prims


def test_usd_verification_does_not_claim_pixels_or_appearance(composed_fixture):
    args, _ = composed_fixture
    result = _verify_stage(*args)
    assert result["usd"] == "verified"
    assert result["texture_pixels"] == "not measured"
    assert result["rendered_appearance"] == "not checked"


@pytest.mark.parametrize("defect", ["collapsed_uv", "nan_uv", "bad_uv_indices", "bad_faces", "wrong_binding", "wrong_source", "wrong_camera", "wrong_resolution", "wrong_multiplier", "broken_surface"])
def test_cook_success_cannot_hide_composed_defects(composed_fixture, defect):
    args, prims = composed_fixture
    mesh, material, settings = prims["/mesh"], prims["/materials/look"], prims["/settings"]
    if defect == "collapsed_uv": mesh.values["primvars:st"].value = [(0,0)]*4
    elif defect == "nan_uv": mesh.values["primvars:st"].value[0] = (float("nan"),0)
    elif defect == "bad_uv_indices": mesh.values["primvars:st:indices"] = Attribute([0,1,1,3])
    elif defect == "bad_faces": mesh.values["faceVertexCounts"].value = [2,2]
    elif defect == "wrong_binding": mesh.relationships["material:binding"] = ["/artist_material"]
    elif defect == "wrong_source": material.values["inputs:specular_roughness_file"].value.path = "op:/unrelated{noise}"
    elif defect == "wrong_camera": settings.relationships["camera"] = ["/artist_camera"]
    elif defect == "wrong_resolution": settings.values["resolution"].value = [1280,720]
    elif defect == "wrong_multiplier": material.values["inputs:specular_roughness"].value = .2
    elif defect == "broken_surface": args[0].stage.return_value.GetAttributeAtPath.return_value = None
    with pytest.raises(RuntimeError):
        _verify_stage(*args)
