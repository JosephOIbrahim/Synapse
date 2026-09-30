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


# ---------------------------------------------------------------------------
# Grounding (D1, 2026-09-30). A Marble export lands upright, on its floor, at a named scale. The whole
# correction lives on one parent Transform LOP (uniform scale, 180 degrees about X for Y-down exports, a Y lift);
# the points and the raw file are never modified. Pure helpers here; `hou` only in _import_native.
# ---------------------------------------------------------------------------
_RES_SUFFIX = re.compile(r'_(?:\d+k|full_res|full|hq)$', re.IGNORECASE)
SIDECAR_SUFFIX = '.world.json'
_FLOOR_NORMAL_COS = 0.866  # faces within 30 degrees of horizontal count as floor


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def world_stem(path) -> str:
    """'<world>_500k.ply' -> '<world>': one stem shared by every resolution of the same export."""
    return _RES_SUFFIX.sub('', Path(path).stem)


def collider_sibling(path):
    """The Marble collider GLB exported beside a splat ('<world>_collider.glb'), or None."""
    source = Path(path)
    for stem in dict.fromkeys((world_stem(source), source.stem)):
        candidate = source.with_name(stem + '_collider.glb')
        if candidate.is_file():
            return candidate
    return None


def sidecar_path(path) -> Path:
    return Path(path).with_name(world_stem(path) + SIDECAR_SUFFIX)


def load_sidecar(path) -> dict:
    """Read the optional '<world>.world.json' beside a local export.

    ``metric_scale_factor`` (> 0) must come with a ``scale_source`` naming where it came from: export
    metadata, a measurement, or a known dimension. Absent file -> {}; malformed -> ImportValidationError.
    """
    target = sidecar_path(path)
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        raise ImportValidationError('The world sidecar %s is not valid JSON.' % target.name) from None
    if not isinstance(data, dict):
        raise ImportValidationError('The world sidecar %s must be a JSON object.' % target.name)
    out = {}
    factor = data.get('metric_scale_factor')
    if factor is not None:
        if not _finite(factor) or not 0 < factor <= 1000:
            raise ImportValidationError('The world sidecar scale must be a positive number no larger than 1000.')
        source = str(data.get('scale_source') or '').strip()
        if not source:
            raise ImportValidationError('The world sidecar must name the source of its scale.')
        out['metric_scale_factor'] = float(factor)
        out['scale_source'] = source[:256]
    return out


def resolve_scale(metadata):
    """(factor, source) from import metadata, or (None, None) when the scale is unknown.

    A World API ``metric_scale_factor`` of 1.0 means the scale could not be inferred (DOCS), so it is unknown.
    """
    semantics = metadata.get('semantics_metadata')
    factor = semantics.get('metric_scale_factor') if isinstance(semantics, dict) else None
    if not _finite(factor) or factor <= 0:
        return None, None
    source = str(metadata.get('scale_source') or '').strip()
    if not source:
        if factor == 1.0:
            return None, None
        source = 'export metadata (semantics_metadata.metric_scale_factor)'
    return float(factor), source[:256]


def _percentile(sorted_values, q):
    k = (len(sorted_values) - 1) * q / 100.0
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def splat_floor_layer(ys, y_down=True, bins=256) -> float:
    """Raw height of the densest horizontal layer at the floor end of a splat: the visible ground."""
    values = sorted(v for v in ys if _finite(v))
    if not values:
        raise ImportValidationError('The splat has no finite positions to ground.')
    if len(values) < 32:
        return _percentile(values, 50)
    lo, hi = (_percentile(values, 80), values[-1]) if y_down else (values[0], _percentile(values, 20))
    if hi <= lo:
        return _percentile(values, 50)
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        if lo <= v <= hi:
            counts[min(int((v - lo) / width), bins - 1)] += 1
    peak = max(range(bins), key=counts.__getitem__)
    return lo + (peak + 0.5) * width


def collider_floor(faces, y_down=True, band=0.25, bins=128):
    """Raw floor height from collider faces [(center_y, normal_y, area), ...].

    The area-weighted peak height of near-horizontal faces in the bottom quarter of the collider's height, refined
    by the area-weighted mean of the faces around that peak. Ledges, sills and steps higher up cannot pull it.
    None when there is no such face.
    """
    kept = [(y, ny, a) for y, ny, a in faces if _finite(y) and _finite(ny) and _finite(a) and a > 0]
    if not kept:
        return None
    heights = [y for y, _, _ in kept]
    top, bottom = min(heights), max(heights)
    span = bottom - top
    lo, hi = (bottom - band * span, bottom) if y_down else (top, top + band * span)
    floor = [(y, a) for y, ny, a in kept if abs(ny) >= _FLOOR_NORMAL_COS and lo <= y <= hi]
    if not floor:
        return None
    if hi <= lo:
        return sum(y * a for y, a in floor) / sum(a for _, a in floor)
    width = (hi - lo) / bins
    area = [0.0] * bins
    for y, a in floor:
        area[min(int((y - lo) / width), bins - 1)] += a
    peak = lo + (max(range(bins), key=area.__getitem__) + 0.5) * width
    near = [(y, a) for y, a in floor if abs(y - peak) <= 1.5 * width]
    return sum(y * a for y, a in near) / sum(a for _, a in near)


def ground_transform(scale, floor_raw, y_down=True):
    """(translate, rotate_degrees, uniform_scale) for a scale-rotate-translate Transform LOP that puts the raw floor
    at y = 0: scale first, flip a Y-down export 180 degrees about X, then lift by the scaled floor."""
    if y_down:
        return (0.0, scale * floor_raw, 0.0), (180.0, 0.0, 0.0), scale
    return (0.0, -scale * floor_raw, 0.0), (0.0, 0.0, 0.0), scale


def grounded_height(raw_y, scale, floor_raw, y_down=True) -> float:
    """Where a raw height lands after ground_transform."""
    return scale * (floor_raw - raw_y) if y_down else scale * (raw_y - floor_raw)


def _apply_sidecar(path, metadata):
    """Fill the scale from '<world>.world.json' when the import metadata has none; export metadata wins."""
    if resolve_scale(metadata)[0] is not None:
        return
    sidecar = load_sidecar(path)
    if 'metric_scale_factor' in sidecar:
        semantics = dict(metadata.get('semantics_metadata') or {})
        semantics['metric_scale_factor'] = sidecar['metric_scale_factor']
        metadata['semantics_metadata'] = semantics
        metadata['scale_source'] = sidecar['scale_source']


def _collider_faces(obj, path):
    """[(center_y, normal_y, area)] for a collider GLB, read through a temporary SOP network that is always removed."""
    temp = obj.createNode('geo', 'synapse_collider_probe')
    try:
        gltf = temp.createNode('gltf', 'COLLIDER')
        parm = gltf.parm('gltffile') or gltf.parm('filename') or gltf.parm('file')
        if parm is None:
            return []
        parm.set(str(path))
        unpack = temp.createNode('unpack', 'UNPACK')
        unpack.setInput(0, gltf)
        unpack.cook(force=True)
        if gltf.errors() or unpack.errors():
            return []
        import hou
        faces = []
        for prim in unpack.geometry().prims():
            vertices = prim.vertices()
            if prim.type() != hou.primType.Polygon or len(vertices) < 3:
                continue
            normal = prim.normal()
            center_y = sum(v.point().position()[1] for v in vertices) / len(vertices)
            faces.append((center_y, normal[1], prim.intrinsicValue('measuredarea')))
        return faces
    finally:
        temp.destroy()


def import_local_asset(path, metadata=None) -> dict:
    """Import on Houdini's main thread; never replace an existing node or scene."""
    info = inspect_ply(path)
    metadata = dict(metadata or {})
    _apply_sidecar(info['path'], metadata)
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
            # D1 grounding: one parent Transform LOP carries the scale, the Y-down flip and the floor lift.
            y_down = str(metadata.get('axis') or 'y_down') != 'y_up'
            ys = geometry.pointFloatAttribValues('P')[1::3]
            collider = collider_sibling(info['path'])
            floor_raw, offset_source = None, None
            if collider is not None:
                floor_raw = collider_floor(_collider_faces(obj, collider), y_down)
                offset_source = 'collider GLB floor faces (densest band in the bottom quarter)'
            if floor_raw is None:
                floor_raw = splat_floor_layer(ys, y_down)
                offset_source = 'splat floor layer (densest band at the floor end)'
            factor, scale_source = resolve_scale(metadata)
            translate, rotate, uniform = ground_transform(factor if factor is not None else 1.0, floor_raw, y_down)
            ground = stage_root.createNode('xform', lop.name() + '_ground')
            made.append(ground)
            ground.setInput(0, lop)
            ground.parm('primpattern').set(lop.parm('pathprefix').eval())
            ground.parmTuple('t').set(translate)
            ground.parmTuple('r').set(rotate)
            ground.parm('scale').set(uniform)
            ground.cook(force=True)
            if ground.errors():
                raise ImportValidationError('Solaris could not ground the imported world.')
            grounding = {'axis': 'y_down_to_y_up' if y_down else 'y_up', 'scale_applied': uniform,
                         'scale_source': scale_source, 'scale_status': 'metric' if scale_source else 'unknown',
                         'floor_raw': round(floor_raw, 6), 'ground_offset_applied': round(translate[1], 6),
                         'ground_offset_source': offset_source,
                         'ground_height': round(grounded_height(splat_floor_layer(ys, y_down), uniform, floor_raw, y_down), 6),
                         'ground_height_source': 'splat floor layer after grounding',
                         'units': 'm' if scale_source else 'scene units',
                         'collider': collider.name if collider is not None else None}
            # Only explicitly allowed non-secret fields enter the HIP; no remote URLs.
            provenance = {k: str(metadata[k])[:256] for k in ('world_id', 'display_name', 'model', 'resolution', 'api_version', 'source', 'sha256', 'scale_source') if k in metadata}
            semantics = metadata.get('semantics_metadata')
            if isinstance(semantics, dict):
                provenance['semantics_metadata'] = {k: v for k in ('metric_scale_factor', 'ground_plane_offset')
                    if isinstance((v := semantics.get(k)), (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
            provenance['coordinate_normalization'] = 'marble_y_down_to_y_up' if y_down else 'preserved_export_coordinates'
            provenance['scale_status'] = grounding['scale_status']
            provenance['grounding'] = grounding
            record = json.dumps(provenance, allow_nan=False, sort_keys=True)
            for node in (geo, lop, ground):
                node.setUserData('synapse.worldlabs', record)
            geo.layoutChildren()
            file_node.moveToGoodPosition()
            bake.setDisplayFlag(True)
            bake.setRenderFlag(True)
            # Make the requested import visible only after all validation succeeds.
            lop.moveToGoodPosition()
            ground.moveToGoodPosition()
            ground.setDisplayFlag(True)
            if scale_source:
                landed = ('Landed at metric scale x%.4g (%s); ground offset from the %s; measured ground height %+.3f m.'
                          % (uniform, scale_source, offset_source, grounding['ground_height']))
            else:
                landed = ('Grounded upright on its floor (offset from the %s), but the metric scale is unknown: add export '
                          'metadata or a %s beside the file to land it at metric scale.' % (offset_source, SIDECAR_SUFFIX))
            return {'node_path': ground.path(), 'import_path': lop.path(), 'sop_path': bake.path(), 'point_count': count,
                    'prim_paths': prim_paths, 'format': 'ply', 'native_type': 'ParticleField3DGaussianSplat',
                    'ground': grounding,
                    'warnings': [landed, 'Native splat import is verified. Karma XPU appearance has not been rendered by this importer.']}
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
