"""SPZ -> 3DGS PLY decoder (python/synapse/worldlabs/spz.py).

World Labs Atlas returns splats only as SPZ, and Houdini 22.0.400 cannot read SPZ. The decoder is checked three ways:
  * hand-computed golden bytes for one splat (independent of any writer);
  * round trips through tests/fixtures/spz_fixture.py, which follows the reference PACKING code and shares nothing
    with the decoder;
  * the written PLY is accepted by the importer's own inspect_ply.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import math
from pathlib import Path
import struct

import numpy as np
import pytest

from synapse.worldlabs import spz
from synapse.worldlabs.importer import inspect_ply

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "spz_fixture.py"
_spec = importlib.util.spec_from_file_location("spz_fixture_for_tests", _FIXTURE)
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


def _has_stdlib_zstd():
    try:
        from compression import zstd  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Golden bytes: one splat, every field hand-computed from the reference formulas
# ---------------------------------------------------------------------------

def _golden_v3():
    header = struct.pack('<IIIBBBB', 0x5053474E, 3, 1, 0, 12, 0, 0)
    positions = bytes([0x00, 0x10, 0x00,      # +1.0  = 4096 / 2**12
                       0x00, 0xF8, 0xFF,      # -0.5  = -2048 (24-bit two's complement)
                       0x00, 0x20, 0x00])     # +2.0  = 8192
    alpha = bytes([191])                      # logit = ln(191/64)
    colors = bytes([128, 255, 0])             # f_dc = (b/255 - 0.5) / 0.15
    scales = bytes([160, 144, 0])             # log scale = b/16 - 10 -> 0, -1, -10
    # Smallest three: largest = y (index 1) in bits 30-31; fields low->high fill w, z, x.
    # w = 511 (sqrt(1/2)), z = 0, x = 0 -> comp = 1<<30 | 511 -> bytes FF 01 00 40.
    rotation = bytes([0xFF, 0x01, 0x00, 0x40])
    return gzip.compress(header + positions + alpha + colors + scales + rotation, mtime=0)


def test_golden_single_splat_v3():
    out = spz.decode(_golden_v3())
    assert out['header'] == {'version': 3, 'point_count': 1, 'sh_degree': 0, 'fractional_bits': 12,
                             'antialiased': False, 'has_extensions': False}
    np.testing.assert_allclose(out['positions'][0], [1.0, -0.5, 2.0], atol=0)
    assert out['opacity'][0] == pytest.approx(math.log(191 / 64), abs=1e-6)
    np.testing.assert_allclose(out['f_dc'][0], [(128 / 255 - 0.5) / 0.15, (1.0 - 0.5) / 0.15, -0.5 / 0.15],
                               atol=1e-6)
    np.testing.assert_allclose(out['scales'][0], [0.0, -1.0, -10.0])
    # PLY order: rot_0..3 = w, x, y, z
    np.testing.assert_allclose(out['rotation'][0], [math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0], atol=1e-6)


def test_golden_first_three_v2_rebuilds_positive_w():
    header = struct.pack('<IIIBBBB', 0x5053474E, 2, 1, 0, 12, 0, 0)
    raw = gzip.compress(header + bytes(9) + bytes([128]) + bytes([128] * 3) + bytes([160] * 3)
                        + bytes([255, 128, 128]), mtime=0)   # x = 255/127.5 - 1 = 1
    out = spz.decode(raw)
    w, x, y, z = out['rotation'][0]
    assert x == pytest.approx(1.0) and abs(y) < 0.01 and abs(z) < 0.01 and w == pytest.approx(0.0, abs=0.13)


# ---------------------------------------------------------------------------
# Round trips through the reference-style writer
# ---------------------------------------------------------------------------

def _expect(rows, out, rot_tol, pos_tol=1.0 / 4096):
    n = len(rows)
    assert out['header']['point_count'] == n
    np.testing.assert_allclose(out['positions'], [r['position'] for r in rows], atol=pos_tol)
    np.testing.assert_allclose(out['f_dc'], [r['f_dc'] for r in rows], atol=0.5 / (0.15 * 255) + 1e-6)
    np.testing.assert_allclose(out['scales'], [r['scale'] for r in rows], atol=1 / 32 + 1e-6)
    alphas = 1 / (1 + np.exp(-out['opacity']))
    np.testing.assert_allclose(alphas, [1 / (1 + math.exp(-r['opacity'])) for r in rows], atol=0.5 / 255 + 1e-6)
    for row, got in zip(rows, out['rotation']):
        x, y, z, w = row['xyzw']
        norm = math.sqrt(x * x + y * y + z * z + w * w)
        want = np.array([w, x, y, z]) / norm
        # q and -q are the same rotation
        assert min(np.abs(got - want).max(), np.abs(got + want).max()) < rot_tol


@pytest.mark.parametrize("version", [2, 3])
def test_legacy_round_trip(version):
    rows = fx.sample_splats(9)
    out = spz.decode(fx.legacy_spz(rows, version=version))
    _expect(rows, out, rot_tol=0.012 if version == 2 else 0.003)


def test_v1_float16_positions():
    rows = fx.sample_splats(4)
    out = spz.decode(fx.legacy_spz(rows, version=1))
    _expect(rows, out, rot_tol=0.012, pos_tol=2e-3)


@pytest.mark.skipif(not _has_stdlib_zstd(), reason="needs Python 3.14 compression.zstd to WRITE the v4 fixture")
def test_v4_zstd_round_trip():
    rows = fx.sample_splats(11, sh_degree=1)
    out = spz.decode(fx.v4_spz(rows, sh_degree=1))
    _expect(rows, out, rot_tol=0.003)
    assert out['header']['version'] == 4


def test_v4_without_any_zstd_decoder_is_refused_plainly(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_zstd(name, *args, **kwargs):
        if name in ("compression", "zstandard", "pyzstd") or name.startswith("compression."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    header = struct.pack('<IIIBBBBI12x', 0x5053474E, 4, 1, 0, 12, 0, 5, 32)
    sizes = [9, 1, 3, 3, 4]
    toc = b''.join(struct.pack('<QQ', 1, s) for s in sizes)
    raw = header + toc + bytes(5)
    monkeypatch.setattr(builtins, "__import__", no_zstd)
    with pytest.raises(spz.SPZFormatError, match="zstd"):
        spz.decode(raw)


@pytest.mark.parametrize("degree", [1, 2, 3, 4])
def test_sh_reorders_coefficient_major_to_channel_planar(degree):
    rows = fx.sample_splats(3, sh_degree=degree)
    out = spz.decode(fx.legacy_spz(rows, version=3, sh_degree=degree))
    dim = spz.SH_DIM[degree]
    assert out['f_rest'].shape == (3, 3, dim)
    for i, row in enumerate(rows):
        for j in range(dim):
            for c in range(3):
                assert out['f_rest'][i, c, j] == pytest.approx(row['sh'][j][c], abs=1 / 128 + 1e-6)


# ---------------------------------------------------------------------------
# PLY output: the importer's own validator accepts it; SH lands where bakegsplat reads it
# ---------------------------------------------------------------------------

def _read_ply(path):
    data = Path(path).read_bytes()
    end = data.index(b'end_header\n') + len(b'end_header\n')
    names = [line.split()[2] for line in data[:end].decode('ascii').splitlines() if line.startswith('property')]
    table = np.frombuffer(data[end:], dtype='<f4').reshape(-1, len(names))
    return names, table


@pytest.mark.parametrize("degree", [0, 1, 3, 4])
def test_written_ply_passes_inspect_ply(tmp_path, degree):
    rows = fx.sample_splats(5, sh_degree=degree)
    decoded = spz.decode(fx.legacy_spz(rows, version=3, sh_degree=degree))
    target = tmp_path / "out.ply"
    written = spz.write_ply(decoded, target)
    info = inspect_ply(target)
    assert info['point_count'] == 5
    assert info['has_spherical_harmonics'] is (degree > 0)
    assert bool(written['notes']) is (degree == 4)
    names, table = _read_ply(target)
    col = {n: k for k, n in enumerate(names)}
    np.testing.assert_allclose(table[:, [col['x'], col['y'], col['z']]], decoded['positions'])
    if degree:
        dim = spz.SH_DIM[degree]
        for c in range(3):
            for j in range(15):
                got = table[:, col['f_rest_%d' % (c * 15 + j)]]
                want = decoded['f_rest'][:, c, j] if j < dim else 0.0
                np.testing.assert_allclose(got, want)


def test_convert_to_ply_is_content_addressed_and_reused(tmp_path):
    source = tmp_path / "scene.spz"
    source.write_bytes(fx.legacy_spz(fx.sample_splats(6), version=3))
    first = spz.convert_to_ply(source, tmp_path / "cache")
    assert Path(first['path']).name == first['metadata']['spz_sha256'] + '.ply'
    assert first['metadata']['axis'] == 'y_up'
    assert first['metadata']['scale_status'] == 'unverified'
    stamp = Path(first['path']).stat().st_mtime_ns
    second = spz.convert_to_ply(source, tmp_path / "cache")
    assert second['path'] == first['path'] and Path(second['path']).stat().st_mtime_ns == stamp
    sidecar = json.loads(Path(first['path']).with_suffix('.json').read_text(encoding='utf-8'))
    assert sidecar == first['metadata']
    assert not [p for p in (tmp_path / "cache" / "spz").iterdir() if p.name.startswith('.')]


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,match", [
    (b"not a splat at all", "not an SPZ"),
    (gzip.compress(b"\x00" * 16, mtime=0), "not an SPZ"),
    (gzip.compress(struct.pack('<IIIBBBB', 0x5053474E, 9, 1, 0, 12, 0, 0), mtime=0), "version"),
    (gzip.compress(struct.pack('<IIIBBBB', 0x5053474E, 3, 0, 0, 12, 0, 0), mtime=0), "between 1 and 10 million"),
    (gzip.compress(struct.pack('<IIIBBBB', 0x5053474E, 3, 1, 5, 12, 0, 0), mtime=0), "degree"),
    (gzip.compress(struct.pack('<IIIBBBB', 0x5053474E, 3, 1, 0, 40, 0, 0), mtime=0), "precision"),
    (gzip.compress(struct.pack('<IIIBBBB', 0x5053474E, 3, 4, 0, 12, 0, 0) + bytes(10), mtime=0), "ends before"),
    (b"\x1f\x8b" + b"\x00" * 30, "gzip"),
])
def test_bad_input_is_refused_with_a_public_message(raw, match):
    with pytest.raises(spz.SPZFormatError, match=match):
        spz.decode(raw)


def test_v4_truncated_table_is_refused():
    header = struct.pack('<IIIBBBBI12x', 0x5053474E, 4, 1, 0, 12, 0, 5, 32)
    with pytest.raises(spz.SPZFormatError, match="table of contents|truncated"):
        spz.decode(header + bytes(8))


def test_convert_refuses_a_non_spz_name(tmp_path):
    target = tmp_path / "scene.ply"
    target.write_bytes(b"ply\n")
    with pytest.raises(spz.SPZFormatError, match=r"\.spz"):
        spz.convert_to_ply(target, tmp_path)
