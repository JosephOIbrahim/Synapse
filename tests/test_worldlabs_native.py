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
        assert len(_children() - before) == 6  # geo, sopimport and the grounding xform per import
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


def _quad_glb(y):
    """A minimal binary glTF 2.0: one 10 x 10 quad at height y (two triangles). Written by hand, no exporter."""
    import struct
    pos = struct.pack('<12f', -5, y, -5, 5, y, -5, 5, y, 5, -5, y, 5)
    binbuf = pos + struct.pack('<6H', 0, 1, 2, 0, 2, 3)
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
           'buffers': [{'byteLength': len(binbuf)}],
           'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 48, 'target': 34962},
                           {'buffer': 0, 'byteOffset': 48, 'byteLength': 12, 'target': 34963}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 4, 'type': 'VEC3',
                          'min': [-5, y, -5], 'max': [5, y, 5]},
                         {'bufferView': 1, 'componentType': 5123, 'count': 6, 'type': 'SCALAR'}]}
    js = json.dumps(doc).encode()
    js += b' ' * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binbuf)
    return (struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(js), b'JSON') + js
            + struct.pack('<I4s', len(binbuf), b'BIN\x00') + binbuf)


def _spz_in(folder):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'spz_fixture_for_native_collider', Path(__file__).resolve().parent / 'fixtures' / 'spz_fixture.py')
    fx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx)
    folder.mkdir()
    source = folder / 'room.spz'
    source.write_bytes(fx.legacy_spz(fx.sample_splats(40, sh_degree=0), version=2, sh_degree=0))
    return source


def test_unreadable_collider_falls_back_to_the_splat_floor(tmp_path):
    """A collider the glTF SOP cannot read must not abort the import (it raised from cook() before)."""
    source = _spz_in(tmp_path / 'scans')
    (source.parent / 'room_collider.glb').write_bytes(b'not a glb')
    prepared = importer.prepare_local_asset(source, tmp_path / 'cache')
    before = _children()
    try:
        result = importer.import_local_asset(prepared['path'], prepared['metadata'])
        assert result['point_count'] == 40
        assert result['ground']['ground_offset_source'].startswith('splat floor layer')
    finally:
        _destroy_added(before)


def test_atlas_spz_finds_its_collider_beside_the_source_not_the_cache(tmp_path):
    """The collider sits beside the .spz the artist chose; the PLY the import reads sits in the cache."""
    scans = tmp_path / 'scans'
    source = _spz_in(scans)
    (scans / 'room_collider.glb').write_bytes(_quad_glb(0.25))
    prepared = importer.prepare_local_asset(source, tmp_path / 'cache')
    assert Path(prepared['path']).parent != scans
    before = _children()
    try:
        result = importer.import_local_asset(prepared['path'], prepared['metadata'])
        g = result['ground']
        assert g['collider'] == 'room_collider.glb'
        assert g['ground_offset_source'].startswith('collider GLB')
        assert abs(g['floor_raw'] - 0.25) < 1e-4
        assert tuple(hou.node(result['node_path']).parmTuple('r').eval()) == (0.0, 0.0, 0.0)
    finally:
        _destroy_added(before)


def test_import_grounds_under_one_xform_with_sidecar_scale(tmp_path):
    source = tmp_path / 'lane_500k.ply'
    source.write_bytes(ply_bytes(points=40))
    (tmp_path / 'lane.world.json').write_text(json.dumps({'metric_scale_factor': 2.5, 'scale_source': 'known dimension: test doorway'}))
    before = _children()
    try:
        result = importer.import_local_asset(source)
        ground = hou.node(result['node_path'])
        assert ground.type().name() == 'xform' and ground.isDisplayFlagSet()
        assert hou.node(result['import_path']).type().name() == 'sopimport'
        g = result['ground']
        assert g['scale_applied'] == 2.5 and g['scale_source'] == 'known dimension: test doorway'
        assert g['scale_status'] == 'metric' and g['units'] == 'm' and g['axis'] == 'y_down_to_y_up'
        assert abs(g['ground_height']) < 1e-6
        assert tuple(ground.parmTuple('r').eval()) == (180.0, 0.0, 0.0)
        saved = json.loads(ground.userData('synapse.worldlabs'))
        assert saved['grounding']['scale_source'] == 'known dimension: test doorway'
        assert 'Landed at metric scale x2.5' in result['warnings'][0]
    finally:
        _destroy_added(before)


def test_atlas_spz_imports_natively_upright_with_no_flip(tmp_path):
    """An Atlas SPZ (RUB, Y-up) goes .spz -> cached PLY -> native GSplats with NO 180-degree flip and unknown scale."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'spz_fixture_for_native', Path(__file__).resolve().parent / 'fixtures' / 'spz_fixture.py')
    fx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx)
    rows = fx.sample_splats(40, sh_degree=3)
    source = tmp_path / 'scene.spz'
    source.write_bytes(fx.legacy_spz(rows, version=3, sh_degree=3))
    prepared = importer.prepare_local_asset(source, tmp_path / 'cache')
    before = _children()
    try:
        result = importer.import_local_asset(prepared['path'], prepared['metadata'])
        assert result['point_count'] == 40
        ground = hou.node(result['node_path'])
        assert tuple(ground.parmTuple('r').eval()) == (0.0, 0.0, 0.0)
        assert result['ground']['axis'] == 'y_up' and result['ground']['scale_status'] == 'unknown'
        record = json.loads(ground.userData('synapse.worldlabs'))
        assert record['coordinate_normalization'] == 'preserved_export_coordinates'
        assert record['spz_sha256'] == prepared['metadata']['spz_sha256']
        prim = hou.node(result['import_path']).stage().GetPrimAtPath(result['prim_paths'][0])
        assert prim.GetTypeName() == 'ParticleField3DGaussianSplat'
    finally:
        _destroy_added(before)
