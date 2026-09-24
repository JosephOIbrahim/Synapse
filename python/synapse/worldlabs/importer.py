"""Validated PLY -> native H22 GSplats -> Solaris, with rollback on failure.

File/bakegsplat/sopimport and the native USD type were verified in an isolated
Houdini 22.0.400 process. Direct SPZ decoding and GLB-as-splats are unsupported.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from .client import WorldLabsError


class ImportValidationError(WorldLabsError):
    pass


def inspect_ply(path) -> dict:
    source = Path(path).expanduser().resolve()
    if source.suffix.lower() != '.ply':
        raise ImportValidationError('Choose a Gaussian-splat PLY export. Direct SPZ import is not supported; GLB is a mesh, not a splat.')
    required = {'x', 'y', 'z', 'opacity'}
    required.update('f_dc_%d' % i for i in range(3))
    required.update('scale_%d' % i for i in range(3))
    required.update('rot_%d' % i for i in range(4))
    properties, count, in_vertex, total, has_format = set(), 0, False, 0, False
    try:
        with source.open('rb') as stream:
            if stream.readline(16).strip() != b'ply':
                raise ImportValidationError('This file is not a PLY export.')
            for _ in range(512):
                raw = stream.readline(4097)
                total += len(raw)
                if not raw or len(raw) > 4096 or total > 65536:
                    raise ImportValidationError('This PLY header is incomplete or too large.')
                parts = raw.decode('ascii').strip().split()
                if not parts:
                    continue
                if parts[0] == 'format':
                    if len(parts) != 3 or parts[1] not in ('ascii', 'binary_little_endian', 'binary_big_endian') or parts[2] != '1.0':
                        raise ImportValidationError('This PLY encoding is not supported.')
                    has_format = True
                if parts[0] == 'element':
                    in_vertex = len(parts) == 3 and parts[1] == 'vertex'
                    if in_vertex:
                        count = int(parts[2])
                elif parts[0] == 'property' and in_vertex:
                    if len(parts) == 3:
                        properties.add(parts[2])
                elif parts[0] == 'end_header':
                    break
            else:
                raise ImportValidationError('This PLY header is incomplete or too large.')
    except (OSError, UnicodeError, ValueError):
        raise ImportValidationError('The PLY file could not be read. Choose a valid local export.') from None
    if not has_format:
        raise ImportValidationError('This PLY is missing its encoding declaration.')
    if count < 1 or count > 10_000_000:
        raise ImportValidationError('The PLY must contain between 1 and 10 million splats.')
    if not required.issubset(properties):
        raise ImportValidationError('This PLY contains ordinary points or is missing Gaussian color, opacity, scale, or rotation attributes.')
    sh = {name for name in properties if name.startswith('f_rest_')}
    if sh and sh != {'f_rest_%d' % i for i in range(45)}:
        raise ImportValidationError('This PLY has an unsupported spherical-harmonic layout; 45 coefficients or DC-only color are supported.')
    return {'path': str(source), 'point_count': count, 'has_spherical_harmonics': bool(sh)}


def import_local_asset(path, metadata=None) -> dict:
    """Import on Houdini's main thread; never replace an existing node or scene."""
    info = inspect_ply(path)
    metadata = dict(metadata or {})
    from synapse.server.main_thread import run_on_main
    return run_on_main(lambda: _import_native(info, metadata), timeout=120.0, label='worldlabs.import_local_asset')


def _native_prim_paths(lop):
    stage = lop.stage()
    return [] if stage is None else [str(p.GetPath()) for p in stage.Traverse() if p.GetTypeName() == 'ParticleField3DGaussianSplat']


def _import_native(info, metadata):
    import hou

    if hou.applicationVersion() < (22, 0, 400):
        raise ImportValidationError('Native World Labs import requires Houdini 22.0.400 or later.')
    obj, stage_root = hou.node('/obj'), hou.node('/stage')
    if obj is None or stage_root is None:
        raise ImportValidationError('The current Houdini scene does not have object and Solaris contexts.')
    for category, node_type in ((hou.sopNodeTypeCategory(), 'file'), (hou.sopNodeTypeCategory(), 'bakegsplat'),
                                (hou.lopNodeTypeCategory(), 'sopimport')):
        if hou.nodeType(category, node_type) is None:
            raise ImportValidationError('This Houdini build is missing native Gaussian-splat import nodes.')
    label = str(metadata.get('display_name') or Path(info['path']).stem)
    name = 'worldlabs_' + (re.sub(r'[^A-Za-z0-9_]+', '_', label).strip('_')[:42] or 'world')
    made = []
    with hou.undos.group('Import World Labs Gaussian splat'):
        try:
            geo = obj.createNode('geo', name)
            made.append(geo)
            file_node = geo.createNode('file', 'SOURCE_PLY')
            file_node.parm('file').set(info['path'])
            file_node.cook(force=True)
            if file_node.errors():
                raise ImportValidationError('Houdini could not load this PLY export.')
            bake = geo.createNode('bakegsplat', 'NATIVE_GSPLATS')
            bake.setInput(0, file_node)
            bake.parm('gsplat').set(1)
            bake.parm('sphcoeff').set(int(info['has_spherical_harmonics']))
            bake.cook(force=True)
            geometry = bake.geometry()
            count = geometry.intrinsicValue('pointcount')
            if bake.errors() or count != info['point_count'] or not all(geometry.findPointAttrib(a) for a in ('Cd', 'scale', 'orient', 'GS_Alpha')):
                raise ImportValidationError('Houdini did not produce a complete native Gaussian splat.')
            lop = stage_root.createNode('sopimport', name)
            made.append(lop)
            lop.parm('soppath').set(bake.path())
            lop.parm('pathprefix').set('/WorldLabs/' + lop.name())
            lop.cook(force=True)
            prim_paths = _native_prim_paths(lop)
            if lop.errors() or not prim_paths:
                raise ImportValidationError('Solaris did not create a native Gaussian-splat primitive.')
            # Only explicitly allowed non-secret fields enter the HIP; no remote URLs.
            provenance = {k: str(metadata[k])[:256] for k in ('world_id', 'display_name', 'model', 'resolution', 'api_version', 'source', 'sha256', 'coordinate_normalization', 'scale_status') if k in metadata}
            semantics = metadata.get('semantics_metadata')
            if isinstance(semantics, dict):
                provenance['semantics_metadata'] = {k: v for k in ('metric_scale_factor', 'ground_plane_offset')
                    if isinstance((v := semantics.get(k)), (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
            geo.setUserData('synapse.worldlabs', json.dumps(provenance, allow_nan=False, sort_keys=True))
            lop.setUserData('synapse.worldlabs', json.dumps(provenance, allow_nan=False, sort_keys=True))
            geo.layoutChildren()
            file_node.moveToGoodPosition()
            bake.setDisplayFlag(True)
            bake.setRenderFlag(True)
            # Make the requested import visible only after all validation succeeds.
            lop.moveToGoodPosition()
            lop.setDisplayFlag(True)
            return {'node_path': lop.path(), 'sop_path': bake.path(), 'point_count': count,
                    'prim_paths': prim_paths, 'format': 'ply', 'native_type': 'ParticleField3DGaussianSplat',
                    'warnings': ['Export coordinates and units were preserved; metric scale and grounding are unverified.',
                                 'Native splat import is verified. Karma XPU appearance has not been rendered by this importer.']}
        except Exception as exc:
            failed_cleanup = []
            for node in reversed(made):
                try:
                    node.destroy()
                except Exception:
                    failed_cleanup.append(node.path())
            if failed_cleanup:
                raise ImportValidationError('Import failed and temporary nodes remain: ' + ', '.join(failed_cleanup)) from None
            if isinstance(exc, WorldLabsError):
                raise
            raise ImportValidationError('Houdini could not complete the import; the new nodes were removed.') from None
