"""D1 grounding helpers (pure Python, no hou): scale source, floor estimates, and the grounding transform."""
import json
import random

import pytest

from synapse.worldlabs import importer
from synapse.worldlabs.importer import (ImportValidationError, collider_floor, collider_sibling, grounded_height,
                                        ground_transform, load_sidecar, resolve_scale, sidecar_path,
                                        splat_floor_layer, world_stem)


def test_y_down_transform_puts_the_raw_floor_at_zero():
    floor, scale = 0.6966, 2.136
    t, r, s = ground_transform(scale, floor, y_down=True)
    assert r == (180.0, 0.0, 0.0) and s == scale
    assert t == pytest.approx((0.0, scale * floor, 0.0))
    assert grounded_height(floor, scale, floor) == pytest.approx(0.0)
    # y-down: 0.1 raw units ABOVE the floor physically is a SMALLER raw y
    assert grounded_height(floor - 0.1, scale, floor) == pytest.approx(0.1 * scale)


def test_y_up_transform_lifts_without_flipping():
    t, r, s = ground_transform(1.5, -1.2, y_down=False)
    assert r == (0.0, 0.0, 0.0) and t == pytest.approx((0.0, 1.8, 0.0))
    assert grounded_height(-1.2, 1.5, -1.2, y_down=False) == pytest.approx(0.0)
    assert grounded_height(-1.0, 1.5, -1.2, y_down=False) == pytest.approx(0.3)


def _lane(seed=7):
    rng = random.Random(seed)
    floor = [rng.gauss(0.62, 0.003) for _ in range(6000)]           # the visible ground layer (y-down: large y)
    walls = [rng.uniform(-6.0, 0.55) for _ in range(20000)]          # facades spread over the height
    sky = [rng.uniform(-19.5, -6.0) for _ in range(3000)]            # far splats above
    below = [rng.uniform(0.66, 0.75) for _ in range(150)]            # a few outliers under the floor
    return floor + walls + sky + below


def test_splat_floor_layer_finds_the_dense_ground_band():
    assert splat_floor_layer(_lane()) == pytest.approx(0.62, abs=0.005)


def test_splat_floor_layer_y_up_uses_the_low_end():
    flipped = [-y for y in _lane()]
    assert splat_floor_layer(flipped, y_down=False) == pytest.approx(-0.62, abs=0.005)


def test_splat_floor_layer_tiny_and_empty_inputs():
    assert splat_floor_layer([0.0]) == 0.0
    assert splat_floor_layer([1.0, 2.0, 3.0]) == 2.0
    with pytest.raises(ImportValidationError):
        splat_floor_layer([float('nan')])


def test_collider_floor_is_the_area_weighted_floor_not_the_lowest_dip():
    faces = [(0.61, 1.0, 4.0), (0.612, -0.99, 3.5), (0.608, 1.0, 3.0),   # the floor, most of the horizontal area
             (0.697, 1.0, 0.05),                                          # one deep dip (the raw max y)
             (0.30, 1.0, 0.2),                                            # a window sill, small
             (-2.0, 0.02, 5.0), (-4.0, -0.01, 5.0), (0.2, 0.05, 5.0),     # walls
             (-5.9, 1.0, 2.0)]                                            # roof-ish faces in the other half
    assert collider_floor(faces) == pytest.approx(0.61, abs=0.005)


def test_collider_floor_none_without_horizontal_faces():
    assert collider_floor([(-1.0, 0.0, 1.0), (0.5, 0.1, 2.0)]) is None
    assert collider_floor([]) is None


def test_world_stem_and_sidecar_names_are_shared_across_resolutions(tmp_path):
    assert world_stem('C:/w/lane_500k.ply') == 'lane'
    assert world_stem('lane_full_res.ply') == 'lane'
    assert world_stem('plain.ply') == 'plain'
    assert sidecar_path(tmp_path / 'lane_100k.ply').name == 'lane.world.json'


def test_collider_sibling(tmp_path):
    ply = tmp_path / 'lane_500k.ply'
    ply.write_bytes(b'ply')
    assert collider_sibling(ply) is None
    (tmp_path / 'lane_collider.glb').write_bytes(b'glTF')
    assert collider_sibling(ply).name == 'lane_collider.glb'


def test_load_sidecar_validates(tmp_path):
    ply = tmp_path / 'lane_500k.ply'
    side = tmp_path / 'lane.world.json'
    assert load_sidecar(ply) == {}
    side.write_text(json.dumps({'metric_scale_factor': 2.136, 'scale_source': 'known dimension: doorway 2.10 m'}))
    assert load_sidecar(ply) == {'metric_scale_factor': 2.136, 'scale_source': 'known dimension: doorway 2.10 m'}
    side.write_text(json.dumps({'metric_scale_factor': 2.136, 'scale_source': 'x' * 400}))
    assert len(load_sidecar(ply)['scale_source']) == 256
    for bad in ({'metric_scale_factor': 2.0}, {'metric_scale_factor': -1, 'scale_source': 's'},
                {'metric_scale_factor': True, 'scale_source': 's'}, [1, 2]):
        side.write_text(json.dumps(bad))
        with pytest.raises(ImportValidationError):
            load_sidecar(ply)
    side.write_text('{not json')
    with pytest.raises(ImportValidationError):
        load_sidecar(ply)


def test_resolve_scale_names_its_source_and_treats_api_one_as_unknown():
    assert resolve_scale({}) == (None, None)
    assert resolve_scale({'semantics_metadata': {'metric_scale_factor': 1.0}}) == (None, None)
    factor, source = resolve_scale({'semantics_metadata': {'metric_scale_factor': 2.0}})
    assert factor == 2.0 and source.startswith('export metadata')
    assert resolve_scale({'semantics_metadata': {'metric_scale_factor': 2.0}, 'scale_source': 'measured'}) == (2.0, 'measured')
    assert resolve_scale({'semantics_metadata': {'metric_scale_factor': float('inf')}}) == (None, None)


def test_sidecar_fills_a_missing_scale_but_never_overrides_export_metadata(tmp_path):
    ply = tmp_path / 'lane_500k.ply'
    (tmp_path / 'lane.world.json').write_text(json.dumps({'metric_scale_factor': 2.136, 'scale_source': 'known dimension'}))
    meta = {}
    importer._apply_sidecar(ply, meta)
    assert resolve_scale(meta) == (2.136, 'known dimension')
    api = {'semantics_metadata': {'metric_scale_factor': 3.0}}
    importer._apply_sidecar(ply, api)
    assert resolve_scale(api)[0] == 3.0


def test_collider_floor_ignores_large_ledges_above_the_bottom_quarter():
    # RC-3 live pass 1 (9/30): balconies, sills and steps in the lower half pulled a median floor up by 0.04 raw units.
    floor = [(0.60 + 0.002 * (i % 5), 1.0, 1.0) for i in range(40)]            # the lane, 40 units of area
    ledges = [(-1.5, 1.0, 30.0), (-2.4, -1.0, 25.0), (0.20, 1.0, 12.0)]        # balconies, an awning, a step run
    walls = [(-3.0, 0.0, 50.0), (-0.5, 0.1, 50.0)]
    roof = [(-5.95, 1.0, 5.0)]
    assert collider_floor(floor + ledges + walls + roof) == pytest.approx(0.604, abs=0.005)
