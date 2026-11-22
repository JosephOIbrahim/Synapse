"""SPZ Gaussian splats -> a standard 3DGS PLY that the native H22 importer already reads.

World Labs Atlas returns splats only as SPZ (posedImages2Splats ``refinedSplats``). Houdini 22.0.400 has no SPZ reader,
so this module decodes SPZ with the standard library plus numpy (Houdini ships numpy). It uses no native code.

Format source: nianticlabs/spz ``load-spz.cc``, ``splat-utils.h`` and ``splat-types.h`` (read 2026-11-22). The code
wins wherever its comments disagree:
  * v1-v3: one gzip stream holding a 16-byte header, then planar arrays: positions, alphas, colors, scales, rotations, SH.
  * v4: a plaintext 32-byte "NGSP" header, a table of contents, then one zstd frame per array. Python 3.14+ decodes
    zstd natively. Older Pythons need ``zstandard`` or ``pyzstd``, otherwise the file is refused with a clear message.
  * positions: 24-bit signed fixed point / 2**fractionalBits. v1 stores float16.
  * alpha: sigmoid(opacity) * 255.   colors: f_dc * (0.15 * 255) + 127.5.   scales: (log_scale + 10) * 16.
  * rotations: v3+ "smallest three" in 4 bytes. v1-v2 store xyz offset-binary in 3 bytes, with w >= 0 rebuilt.
  * SH: (byte - 128) / 128, ordered per point coefficient-major (R,G,B per coefficient). PLY is channel-planar.

Coordinates are written exactly as stored. SPZ's default frame is RUB: right, up, back, Y-up. That is Houdini's own
frame and Atlas's world frame, so callers import the result with ``axis = 'y_up'`` and no flip.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib

from .client import WorldLabsError

MAGIC = 0x5053474E  # "NGSP" little-endian
COLOR_SCALE = 0.15
SH_DIM = {0: 0, 1: 3, 2: 8, 3: 15, 4: 24}
MAX_POINTS = 10_000_000          # the importer's own ceiling (importer.inspect_ply)
MAX_FILE_BYTES = 2 * 1024 ** 3
PLY_SH_DIM = 15                  # bakegsplat takes DC-only or degree-3 (45 f_rest) layouts
_SQRT1_2 = 0.7071067811865476


class SPZFormatError(WorldLabsError):
    """Public-safe: names the problem, never echoes file bytes."""


def _np():
    try:
        import numpy
    except ImportError:  # pragma: no cover - Houdini and the test env both ship numpy
        raise SPZFormatError('Reading SPZ needs numpy, which this Python does not have.') from None
    return numpy


def _zstd_decompress(data: bytes, expected: int) -> bytes:
    """One zstd frame -> exactly ``expected`` bytes, using whichever decoder this Python has."""
    try:
        from compression import zstd as _std  # Python 3.14+
        out = _std.ZstdDecompressor().decompress(data, max_length=expected)
    except ImportError:
        try:
            import zstandard
            out = zstandard.ZstdDecompressor().decompress(data, max_output_size=expected)
        except ImportError:
            try:
                import pyzstd
                out = pyzstd.decompress(data)
            except ImportError:
                raise SPZFormatError(
                    'This SPZ is version 4 (zstd-compressed), and this Python has no zstd decoder. '
                    'Houdini 22.0.400 runs Python 3.13, which lacks one. Convert it to PLY with another tool, '
                    'or install the zstandard package for Houdini.') from None
    except Exception:
        raise SPZFormatError('A compressed SPZ stream is damaged.') from None
    if len(out) != expected:
        raise SPZFormatError('An SPZ stream decoded to the wrong size.')
    return out


def _gunzip_bounded(raw: bytes, limit: int) -> bytes:
    stream = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = stream.decompress(raw, limit + 1)
    except zlib.error:
        raise SPZFormatError('This SPZ is not a valid gzip stream.') from None
    if len(out) > limit:
        raise SPZFormatError('This SPZ expands beyond the import limit.')
    return out


def _legacy_streams(raw: bytes):
    """v1-v3: header and arrays inside one gzip stream."""
    per_point_max = 9 + 1 + 3 + 3 + 4 + 72
    body = _gunzip_bounded(raw, 16 + MAX_POINTS * per_point_max + (1 << 20))
    if len(body) < 16:
        raise SPZFormatError('This SPZ header is incomplete.')
    magic, version, count, degree, bits, flags, _reserved = struct.unpack_from('<IIIBBBB', body, 0)
    if magic != MAGIC:
        raise SPZFormatError('This file is not an SPZ splat.')
    if version not in (1, 2, 3):
        raise SPZFormatError('This SPZ version is not supported.')
    header = _check_header(version, count, degree, bits, flags)
    sizes = _stream_sizes(header)
    need = 16 + sum(sizes)
    if len(body) < need:
        raise SPZFormatError('This SPZ ends before its splat data does.')
    streams, offset = [], 16
    for size in sizes:
        streams.append(body[offset:offset + size])
        offset += size
    return header, streams


def _v4_streams(raw: bytes):
    if len(raw) < 32:
        raise SPZFormatError('This SPZ header is incomplete.')
    magic, version, count, degree, bits, flags, n_streams, toc = struct.unpack_from('<IIIBBBBI', raw, 0)
    if magic != MAGIC or version != 4:
        raise SPZFormatError('This SPZ version is not supported.')
    header = _check_header(version, count, degree, bits, flags)
    sizes = _stream_sizes(header)
    if n_streams != len(sizes) or toc < 32 or toc + 16 * n_streams > len(raw):
        raise SPZFormatError('This SPZ table of contents is invalid.')
    entries = [struct.unpack_from('<QQ', raw, toc + 16 * i) for i in range(n_streams)]
    offset = toc + 16 * n_streams
    if offset + sum(c for c, _ in entries) != len(raw):
        raise SPZFormatError('This SPZ is truncated or has trailing data.')
    streams = []
    for (compressed, uncompressed), size in zip(entries, sizes):
        if uncompressed != size:
            raise SPZFormatError('An SPZ stream has the wrong size.')
        streams.append(_zstd_decompress(raw[offset:offset + compressed], size))
        offset += compressed
    return header, streams


def _check_header(version, count, degree, bits, flags):
    if not 1 <= count <= MAX_POINTS:
        raise SPZFormatError('The SPZ must contain between 1 and 10 million splats.')
    if degree not in SH_DIM:
        raise SPZFormatError('This SPZ has an unsupported spherical-harmonic degree.')
    if not 0 <= bits <= 24:
        raise SPZFormatError('This SPZ has an invalid position precision.')
    return {'version': version, 'point_count': count, 'sh_degree': degree, 'fractional_bits': bits,
            'antialiased': bool(flags & 1), 'has_extensions': bool(flags & 2)}


def _stream_sizes(header):
    n = header['point_count']
    sizes = [n * (6 if header['version'] == 1 else 9), n, 3 * n, 3 * n, n * (4 if header['version'] >= 3 else 3)]
    sh = 3 * SH_DIM[header['sh_degree']] * n
    if sh:
        sizes.append(sh)
    return sizes


def decode(raw: bytes) -> dict:
    """SPZ bytes -> {'header': ..., arrays in PLY conventions}. Arrays are float32 numpy arrays."""
    np = _np()
    if raw[:4] == b'NGSP':
        header, streams = _v4_streams(raw)
    elif raw[:2] == b'\x1f\x8b':
        header, streams = _legacy_streams(raw)
    else:
        raise SPZFormatError('This file is not an SPZ splat.')
    n = header['point_count']
    version = header['version']

    if version == 1:
        positions = np.frombuffer(streams[0], dtype='<f2').reshape(n, 3).astype(np.float32)
    else:
        b = np.frombuffer(streams[0], dtype=np.uint8).reshape(n, 3, 3).astype(np.int32)
        fixed = b[..., 0] | (b[..., 1] << 8) | (b[..., 2] << 16)
        fixed = np.where(fixed & 0x800000, fixed - (1 << 24), fixed)
        positions = (fixed.astype(np.float64) / float(1 << header['fractional_bits'])).astype(np.float32)

    alpha = np.frombuffer(streams[1], dtype=np.uint8).astype(np.float64) / 255.0
    alpha = np.clip(alpha, 1e-6, 1.0 - 1e-6)   # bytes 0 and 255 would be -inf/+inf logits
    opacity = np.log(alpha / (1.0 - alpha)).astype(np.float32)

    colors = np.frombuffer(streams[2], dtype=np.uint8).reshape(n, 3).astype(np.float32)
    f_dc = ((colors / 255.0) - 0.5) / COLOR_SCALE

    scales = np.frombuffer(streams[3], dtype=np.uint8).reshape(n, 3).astype(np.float32) / 16.0 - 10.0

    xyzw = np.zeros((n, 4), dtype=np.float64)
    if version >= 3:
        comp = np.frombuffer(streams[4], dtype='<u4').astype(np.uint64)
        largest = (comp >> 30).astype(np.int64)
        fields = [(comp >> (10 * k)) & 0x3FF for k in range(3)]   # lowest bits first
        for big in range(4):
            mask = largest == big
            if not mask.any():
                continue
            order = [i for i in (3, 2, 1, 0) if i != big]       # field k fills component order[k]
            for k, comp_index in enumerate(order):
                f = fields[k][mask]
                value = _SQRT1_2 * (f & 0x1FF).astype(np.float64) / 511.0
                xyzw[mask, comp_index] = np.where((f >> 9) & 1, -value, value)
            rest = [i for i in range(4) if i != big]
            xyzw[mask, big] = np.sqrt(np.clip(1.0 - (xyzw[mask][:, rest] ** 2).sum(axis=1), 0.0, None))
    else:
        xyz = np.frombuffer(streams[4], dtype=np.uint8).reshape(n, 3).astype(np.float64) / 127.5 - 1.0
        xyzw[:, :3] = xyz
        xyzw[:, 3] = np.sqrt(np.clip(1.0 - (xyz ** 2).sum(axis=1), 0.0, None))
    rotation = xyzw[:, [3, 0, 1, 2]].astype(np.float32)        # PLY rot_0..3 = w, x, y, z

    dim = SH_DIM[header['sh_degree']]
    if dim:
        sh = (np.frombuffer(streams[5], dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        f_rest = sh.reshape(n, dim, 3).transpose(0, 2, 1)       # -> (n, channel, coefficient)
    else:
        f_rest = np.zeros((n, 3, 0), dtype=np.float32)
    return {'header': header, 'positions': positions, 'opacity': opacity, 'f_dc': f_dc.astype(np.float32),
            'scales': scales.astype(np.float32), 'rotation': rotation, 'f_rest': f_rest.astype(np.float32)}


def write_ply(splats: dict, target) -> dict:
    """Write the standard binary 3DGS PLY that importer.inspect_ply and bakegsplat accept.

    SH is written DC-only (degree 0) or as exactly 45 ``f_rest`` values (degree 3). Degrees 1-2 are zero-padded,
    which changes nothing visually. Degree 4 drops its fourth band, and the returned notes say so.
    """
    np = _np()
    n = splats['header']['point_count']
    have = splats['f_rest'].shape[2]
    notes = []
    if have == 0:
        rest = None
    else:
        rest = np.zeros((n, 3, PLY_SH_DIM), dtype=np.float32)
        keep = min(have, PLY_SH_DIM)
        rest[:, :, :keep] = splats['f_rest'][:, :, :keep]
        if have > PLY_SH_DIM:
            notes.append('Degree-4 view-dependent color was reduced to degree 3 for Houdini.')
        rest = rest.reshape(n, 3 * PLY_SH_DIM)               # channel-planar: f_rest_{c*15 + j}
    names = ['x', 'y', 'z', 'nx', 'ny', 'nz', 'f_dc_0', 'f_dc_1', 'f_dc_2']
    if rest is not None:
        names += ['f_rest_%d' % i for i in range(3 * PLY_SH_DIM)]
    names += ['opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    columns = [splats['positions'], np.zeros((n, 3), dtype=np.float32), splats['f_dc']]
    if rest is not None:
        columns.append(rest)
    columns += [splats['opacity'].reshape(n, 1), splats['scales'], splats['rotation']]
    table = np.ascontiguousarray(np.concatenate(columns, axis=1), dtype='<f4')
    if table.shape[1] != len(names) or not np.isfinite(table).all():
        raise SPZFormatError('The decoded splat contains invalid values.')
    header = ('ply\nformat binary_little_endian 1.0\ncomment SYNAPSE spz->ply (RUB, as stored)\n'
              'element vertex %d\n' % n + ''.join('property float %s\n' % name for name in names) + 'end_header\n')
    target = Path(target)
    with open(target, 'wb') as stream:
        stream.write(header.encode('ascii'))
        table.tofile(stream)
    return {'point_count': n, 'has_spherical_harmonics': rest is not None, 'notes': notes}


def convert_to_ply(source, cache_dir) -> dict:
    """Decode one SPZ file into a content-addressed PLY under ``cache_dir``. Reuses an earlier conversion.

    Returns {'path', 'metadata'}. The metadata carries axis 'y_up' (SPZ's RUB frame) and no scale claim.
    """
    source = Path(source).expanduser().resolve()
    if source.suffix.lower() != '.spz':
        raise SPZFormatError('Choose an .spz splat file.')
    try:
        size = source.stat().st_size
        if size > MAX_FILE_BYTES:
            raise SPZFormatError('This SPZ exceeds the 2 GB import limit.')
        raw = source.read_bytes()
    except OSError:
        raise SPZFormatError('The SPZ file could not be read.') from None
    digest = hashlib.sha256(raw).hexdigest()
    directory = Path(cache_dir).expanduser().resolve() / 'spz'
    target = directory / (digest + '.ply')
    sidecar = target.with_suffix('.json')
    if target.is_file() and sidecar.is_file():
        try:
            return {'path': str(target), 'metadata': json.loads(sidecar.read_text(encoding='utf-8'))}
        except (OSError, ValueError):
            pass  # rebuild a damaged cache entry below
    splats = decode(raw)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.convert-', suffix='.ply', delete=False) as handle:
            temporary = Path(handle.name)
        written = write_ply(splats, temporary)
        os.replace(temporary, target)
        temporary = None
        head = splats['header']
        metadata = {'source': 'spz', 'spz_sha256': digest, 'spz_bytes': size, 'spz_version': head['version'],
                    'sh_degree': head['sh_degree'], 'point_count': head['point_count'],
                    'antialiased': head['antialiased'], 'axis': 'y_up',
                    'coordinate_normalization': 'spz_rub_as_stored', 'scale_status': 'unverified',
                    'notes': written['notes']}
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.metadata-', suffix='.json', mode='w',
                                         encoding='utf-8', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(metadata, stream, indent=2, sort_keys=True, allow_nan=False)
        os.replace(temporary, sidecar)
        temporary = None
        return {'path': str(target), 'metadata': metadata}
    except OSError:
        raise SPZFormatError('The converted splat could not be written to the cache folder.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
