"""Geometry inspection samples numeric attributes with readers Houdini 22.0.400 has.

_geometry_summary used to call ``attr.floatListData()``, which hou.Attrib does
not have in 22.0.400, so every numeric attribute (P, N, Cd ...) came back with
``samples == []`` and an error status. The stand-ins below are spec'd with the
real member names only, taken from a live isolated hython 22.0.400 assay
(cto-20261007 assay_lx.log:95-111) and a follow-up probe of the readers'
return shapes: a phantom call raises AttributeError, exactly as in Houdini.

Pure Python: no hou.
"""
from __future__ import annotations

import importlib.util
import os
from unittest.mock import MagicMock

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "python", "synapse", "server", "introspection.py")
_spec = importlib.util.spec_from_file_location("_introspection_attrib_samples", _PATH)
introspection = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(introspection)

# hou.Attrib members the sampler may use (22.0.400). No floatListData.
_ATTRIB_MEMBERS = ["name", "dataType", "size", "strings", "isArrayType", "type"]
# hou.Geometry members the sampler and the summary may use (22.0.400).
_GEOMETRY_MEMBERS = [
    "points", "prims", "vertices", "pointAttribs", "primAttribs", "globalAttribs",
    "boundingBox", "attribValue",
    "pointFloatAttribValues", "pointIntAttribValues",
    "pointFloatListAttribValues", "pointIntListAttribValues",
    "primFloatAttribValues", "primIntAttribValues",
    "primFloatListAttribValues", "primIntListAttribValues",
    "vertexFloatAttribValues", "vertexIntAttribValues",
    "vertexFloatListAttribValues", "vertexIntListAttribValues",
]


def _attrib(name, data_type, size=1, array=False, strings=()):
    attr = MagicMock(spec=_ATTRIB_MEMBERS)
    attr.name.return_value = name
    attr.dataType.return_value = "attribData." + data_type
    attr.size.return_value = size
    attr.isArrayType.return_value = array
    attr.strings.return_value = tuple(strings)
    return attr


def _summary(point_attribs=(), prim_attribs=(), detail_attribs=(), points=3, prims=1, **values):
    geo = MagicMock(spec=_GEOMETRY_MEMBERS)
    geo.points.return_value = [None] * points
    geo.prims.return_value = [None] * prims  # also the prim count for prim attributes
    geo.vertices.return_value = [None] * 3
    geo.boundingBox.return_value = None
    geo.pointAttribs.return_value = list(point_attribs)
    geo.primAttribs.return_value = list(prim_attribs)
    geo.globalAttribs.return_value = list(detail_attribs)
    for reader, mapping in values.items():
        getattr(geo, reader).side_effect = lambda name, _m=mapping: _m[name]
    node = MagicMock(spec=["geometry"])
    node.geometry.return_value = geo
    return introspection._geometry_summary(node, max_samples=2)


def _by_name(entries):
    return {e["name"]: e for e in entries}


def test_attrib_has_no_float_list_data_in_the_stand_in():
    with pytest.raises(AttributeError):
        MagicMock(spec=_ATTRIB_MEMBERS).floatListData


def test_tuple_float_point_attribute_samples_per_point():
    result = _summary(
        point_attribs=[_attrib("P", "Float", size=3)],
        pointFloatAttribValues={"P": (0.0, 0.5, 0.25, 1.0, 1.5, 1.25, 2.0, 2.5, 2.25)},
    )
    entry = _by_name(result["point_attributes"])["P"]
    assert "sample_status" not in entry, entry
    assert entry["samples"] == [[0.0, 0.5, 0.25], [1.0, 1.5, 1.25]]


def test_scalar_int_point_attribute_samples_flat():
    result = _summary(
        point_attribs=[_attrib("id", "Int")],
        pointIntAttribValues={"id": (10, 20, 30)},
    )
    entry = _by_name(result["point_attributes"])["id"]
    assert entry["samples"] == [10, 20]
    assert "sample_status" not in entry


def test_int_prim_attribute_reads_through_the_prim_reader():
    result = _summary(
        prim_attribs=[_attrib("iv", "Int")],
        primIntAttribValues={"iv": (7,)},
    )
    entry = _by_name(result["prim_attributes"])["iv"]
    assert entry["samples"] == [7]


def test_float_array_point_attribute_reads_through_the_list_reader():
    result = _summary(
        point_attribs=[_attrib("farr", "Float", array=True)],
        pointFloatListAttribValues={"farr": ((0.0,), (1.0, 1.0), (2.0, 2.0, 2.0))},
    )
    entry = _by_name(result["point_attributes"])["farr"]
    assert entry["samples"] == [[0.0], [1.0, 1.0]]


def test_detail_attribute_reads_through_attrib_value():
    result = _summary(
        detail_attribs=[_attrib("dv", "Float", size=2)],
        attribValue={"dv": (1.0, 2.0)},
    )
    entry = _by_name(result["detail_attributes"])["dv"]
    assert entry["samples"] == [[1.0, 2.0]]


def test_string_attribute_still_reads_its_strings():
    result = _summary(point_attribs=[_attrib("name", "String", strings=("a", "b", "c"))])
    entry = _by_name(result["point_attributes"])["name"]
    assert entry["samples"] == ["a", "b"]


def test_dict_attribute_is_named_not_sampled_not_an_error():
    result = _summary(point_attribs=[_attrib("meta", "Dict")])
    entry = _by_name(result["point_attributes"])["meta"]
    assert entry["samples"] == []
    assert not entry["sample_status"].startswith("error"), entry


def test_no_numeric_sample_reports_an_error():
    result = _summary(
        point_attribs=[_attrib("P", "Float", size=3), _attrib("id", "Int")],
        prim_attribs=[_attrib("iv", "Int")],
        detail_attribs=[_attrib("df", "Float")],
        pointFloatAttribValues={"P": (0.0,) * 9},
        pointIntAttribValues={"id": (1, 2, 3)},
        primIntAttribValues={"iv": (7,)},
        attribValue={"df": 9.5},
    )
    entries = result["point_attributes"] + result["prim_attributes"] + result["detail_attributes"]
    for entry in entries:
        assert not str(entry.get("sample_status", "")).startswith("error"), entry
        assert entry["samples"], entry
