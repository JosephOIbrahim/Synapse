"""Isolated hython tests: actual native splats and cleanup, never a live scene."""
from pathlib import Path
import json

import pytest
import hou

from synapse.worldlabs import importer
from test_worldlabs_client import ply_bytes

pytestmark = pytest.mark.skipif(getattr(hou, '__synapse_canonical__', False), reason='Requires isolated real H22 hython; fake hou is not native splat evidence')


def _children():
    return {n.path() for p in ('/obj', '/stage') for n in hou.node(p).children()}


def _destroy_added(before):
    for path in sorted(_children() - before, reverse=True):
        node = hou.node(path)
        if node:
            node.destroy()


def test_import_is_native_and_second_import_does_not_replace_first(tmp_path):
    source = tmp_path / 'tiny.ply'
    source.write_bytes(ply_bytes())
    before = _children()
    try:
        one = importer.import_local_asset(source, {'display_name': 'Test world', 'world_id': 'fixture-id'})
        two = importer.import_local_asset(source, {'display_name': 'Test world'})
        assert one['point_count'] == 1
        assert one['node_path'] != two['node_path']
        assert hou.node(one['node_path']) is not None
        for result in (one, two):
            stage = hou.node(result['node_path']).stage()
            assert len(result['prim_paths']) == 1
            prim = stage.GetPrimAtPath(result['prim_paths'][0])
            assert prim.GetTypeName() == 'ParticleField3DGaussianSplat'
            assert len(prim.GetAttribute('positions').Get() or prim.GetAttribute('positionsh').Get()) == 1
        assert len(_children() - before) == 4
    finally:
        _destroy_added(before)


def test_truncated_ply_failure_removes_temporary_nodes(tmp_path):
    source = tmp_path / 'broken.ply'
    # Header promises a splat but the body is absent: actual File SOP must fail.
    source.write_bytes(ply_bytes().split(b'end_header\n')[0] + b'end_header\n')
    before = _children()
    try:
        with pytest.raises(importer.ImportValidationError):
            importer.import_local_asset(source)
        assert _children() == before
    finally:
        _destroy_added(before)


def test_failed_solaris_verification_removes_both_new_networks(tmp_path, monkeypatch):
    source = tmp_path / 'tiny.ply'
    source.write_bytes(ply_bytes())
    before = _children()
    monkeypatch.setattr(importer, '_native_prim_paths', lambda lop: [])
    try:
        with pytest.raises(importer.ImportValidationError, match='native Gaussian-splat primitive'):
            importer.import_local_asset(source)
        assert _children() == before
    finally:
        _destroy_added(before)


def test_sh_coefficients_survive_and_provenance_excludes_unapproved_fields(tmp_path):
    source = tmp_path / 'sh.ply'
    source.write_bytes(ply_bytes(sh=True))
    before = _children()
    try:
        result = importer.import_local_asset(source, {'world_id': 'fixture-id', 'api_key': 'secret',
            'semantics_metadata': {'metric_scale_factor': 2.0, 'download_url': 'https://secret.invalid/'}})
        sop = hou.node(result['sop_path'])
        assert sop.parm('sphcoeff').eval() == 1
        geometry = sop.geometry()
        assert all(geometry.findPointAttrib(a).size() == 16 for a in ('GS_SPH_R', 'GS_SPH_G', 'GS_SPH_B'))
        lop = hou.node(result['node_path'])
        prim = lop.stage().GetPrimAtPath(result['prim_paths'][0])
        assert prim.GetAttribute('radiance:sphericalHarmonicsDegree').Get() == 3
        saved = lop.userData('synapse.worldlabs')
        assert 'secret' not in saved and 'download_url' not in saved
        assert json.loads(saved)['semantics_metadata'] == {'metric_scale_factor': 2.0}
    finally:
        _destroy_added(before)


def test_failed_second_import_preserves_previous_native_world(tmp_path, monkeypatch):
    source = tmp_path / 'tiny.ply'
    source.write_bytes(ply_bytes())
    before = _children()
    try:
        first = importer.import_local_asset(source)
        previous = hou.node(first['node_path'])
        previous_paths = _children()
        monkeypatch.setattr(importer, '_native_prim_paths', lambda lop: [])
        with pytest.raises(importer.ImportValidationError):
            importer.import_local_asset(source)
        assert _children() == previous_paths
        assert previous.isDisplayFlagSet()
        assert previous.stage().GetPrimAtPath(first['prim_paths'][0]).GetTypeName() == 'ParticleField3DGaussianSplat'
    finally:
        _destroy_added(before)
