"""Synthetic SPZ writer for tests and probes. Loaded by file path, never imported as a package.

It follows the PACKING side of nianticlabs/spz (load-spz.cc / splat-utils.h, read 2026-11-22). A second, independent
implementation (Jackneill/spz math.rs) agrees on every formula used here. The decoder under test lives in
python/synapse/worldlabs/spz.py, and this writer shares no code with it.

All bytes are synthetic. No World Labs asset is involved.
"""
from __future__ import annotations

import gzip
import math
import struct

MAGIC = 0x5053474E
SQRT1_2 = 0.7071067811865476
SH_DIM = {0: 0, 1: 3, 2: 8, 3: 15, 4: 24}


def _u8(x):
    return max(0, min(255, int(round(x))))


def pack_position(value, bits):
    fixed = int(round(value * (1 << bits)))
    return struct.pack('<i', fixed)[:3]


def pack_alpha(opacity_logit):
    return _u8(255.0 / (1.0 + math.exp(-opacity_logit)))


def pack_color(f_dc):
    return _u8(f_dc * (0.15 * 255.0) + 0.5 * 255.0)


def pack_scale(log_scale):
    return _u8((log_scale + 10.0) * 16.0)


def pack_rotation_smallest_three(xyzw):
    norm = math.sqrt(sum(c * c for c in xyzw))
    q = [c / norm for c in xyzw]
    largest = 0
    for i in range(1, 4):
        if abs(q[i]) > abs(q[largest]):
            largest = i
    negate = q[largest] < 0
    comp = largest
    for i in range(4):
        if i == largest:
            continue
        negbit = 1 if ((q[i] < 0) != negate) else 0
        mag = min(511, int(math.floor(511.0 * (abs(q[i]) / SQRT1_2) + 0.5)))
        comp = (comp << 10) | (negbit << 9) | mag
    return struct.pack('<I', comp)


def pack_rotation_first_three(xyzw):
    norm = math.sqrt(sum(c * c for c in xyzw))
    x, y, z, w = (c / norm for c in xyzw)
    if w < 0:
        x, y, z = -x, -y, -z
    return bytes(_u8(c * 127.5 + 127.5) for c in (x, y, z))


def pack_sh(value):
    return _u8(value * 128.0 + 128.0)


def body(splats, version, sh_degree, bits=12):
    """Planar arrays in file order: positions, alphas, colors, scales, rotations, SH (coefficient-major)."""
    dim = SH_DIM[sh_degree]
    out = []
    if version == 1:
        out.append(b''.join(struct.pack('<3e', *s['position']) for s in splats))
    else:
        out.append(b''.join(b''.join(pack_position(v, bits) for v in s['position']) for s in splats))
    out.append(bytes(pack_alpha(s['opacity']) for s in splats))
    out.append(bytes(pack_color(c) for s in splats for c in s['f_dc']))
    out.append(bytes(pack_scale(c) for s in splats for c in s['scale']))
    pack = pack_rotation_smallest_three if version >= 3 else pack_rotation_first_three
    out.append(b''.join(pack(s['xyzw']) for s in splats))
    if dim:
        # s['sh'][j][c]: coefficient j, channel c -> written j-major, then R, G, B.
        out.append(bytes(pack_sh(s['sh'][j][c]) for s in splats for j in range(dim) for c in range(3)))
    return out


def legacy_spz(splats, version=3, sh_degree=0, bits=12, flags=0):
    header = struct.pack('<IIIBBBB', MAGIC, version, len(splats), sh_degree, bits, flags, 0)
    return gzip.compress(header + b''.join(body(splats, version, sh_degree, bits)), mtime=0)


def v4_spz(splats, sh_degree=0, bits=12, compress=None):
    """NGSP v4: 32-byte header, TOC, one zstd frame per stream. ``compress`` defaults to compression.zstd."""
    if compress is None:
        from compression import zstd
        compress = zstd.compress
    streams = body(splats, 4, sh_degree, bits)
    frames = [compress(s) for s in streams]
    header = struct.pack('<IIIBBBBI12x', MAGIC, 4, len(splats), sh_degree, bits, 0, len(streams), 32)
    toc = b''.join(struct.pack('<QQ', len(f), len(s)) for f, s in zip(frames, streams))
    return header + toc + b''.join(frames)


def sample_splats(count=7, sh_degree=0):
    """Deterministic, varied splats with exact-ish values (no randomness)."""
    dim = SH_DIM[sh_degree]
    rows = []
    for i in range(count):
        t = i / max(1, count - 1)
        angle = 0.3 + 2.4 * t
        axis = [(0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.6, 0.0, 0.8)][i % 4]
        s = math.sin(angle / 2.0)
        xyzw = (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0) * (1 if i % 3 else -1))
        rows.append({
            'position': (-3.0 + 6.0 * t, 0.25 * i - 1.0, 2.0 - 0.5 * i),
            'opacity': -3.0 + 6.0 * t,
            'f_dc': (-2.0 + 4.0 * t, 0.5 - t, 1.5 * t - 0.25),
            'scale': (-6.0 + t, -4.5, -3.0 - 2.0 * t),
            'xyzw': xyzw,
            'sh': [[((j + 1) * (c + 2) * (1 if (i + j) % 2 else -1)) / 100.0 for c in range(3)] for j in range(dim)],
        })
    return rows
