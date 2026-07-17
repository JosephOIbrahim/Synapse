"""Build minimal, valid-*enough* EXR **header** bytes for T0 reader tests.

Why hand-build headers instead of a hython fixture generator?

The dispatch offered both roads. Hand-building wins here for three reasons:

1. **Hermetic.** This worktree has no live Houdini/husk to run a one-shot hython
   fixture script against — and T0 is explicitly the tier that needs *neither*
   Houdini nor OpenCV. A committed binary ``.exr`` blob would also be an opaque
   review artifact; this synth is reviewable source that *documents the byte
   layout* it produces.
2. **Deterministic + tiny.** The bytes are generated from parameters at test
   time, so a fixture is exactly the header under test — no drift, no
   multi-megabyte pixel payload.
3. **Faithful to what T0 reads.** T0 reads the *header* only. These bytes carry a
   real EXR magic, a real version field (single- or multi-part), and real
   ``chlist`` / ``box2i`` / ``string`` / ``compression`` attributes in the exact
   on-disk encoding the reader parses. They are header-truthful; they are NOT
   renderable images (no offset tables or pixel data) and are never fed to a real
   EXR decoder — matching how T0 uses them.

Ground truth this mirrors (``perception_truth_22.0.368.json`` item 6): husk
writes multi-part EXR — part ``C``(R,G,B,A) 16-bit half + part ``primid``
(``primid.id``) float32 — so ``multipart_exr_bytes`` reproduces exactly that
shape, and the reader is exercised against the real husk layout.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Sequence, Tuple

_EXR_MAGIC = 20000630
_MULTIPART_FLAG = 0x1000
_PTYPE = {"uint": 0, "half": 1, "float": 2}


def _cstr(s: str) -> bytes:
    return s.encode("utf-8") + b"\x00"


def _attr(name: str, atype: str, value: bytes) -> bytes:
    return _cstr(name) + _cstr(atype) + struct.pack("<i", len(value)) + value


def _chlist(channels: Sequence[Tuple[str, str]]) -> bytes:
    """channels = [(name, pixel_type), ...] -> chlist attribute value bytes."""
    out = b""
    for name, ptype in channels:
        out += _cstr(name)
        out += struct.pack("<i", _PTYPE[ptype])  # pixel type
        out += struct.pack("<Bxxx", 1)           # pLinear + 3 reserved bytes
        out += struct.pack("<i", 1)              # xSampling
        out += struct.pack("<i", 1)              # ySampling
    out += b"\x00"  # empty channel name terminates the list
    return out


def _box2i(x0: int, y0: int, x1: int, y1: int) -> bytes:
    return struct.pack("<iiii", x0, y0, x1, y1)


def _header_body(
    *,
    channels: Sequence[Tuple[str, str]],
    width: int,
    height: int,
    part_name: Optional[str] = None,
    part_type: Optional[str] = None,
    compression: int = 3,  # zips, per the probe
    string_attrs: Optional[Dict[str, str]] = None,
) -> bytes:
    body = b""
    body += _attr("channels", "chlist", _chlist(channels))
    body += _attr("compression", "compression", bytes([compression]))
    body += _attr("dataWindow", "box2i", _box2i(0, 0, width - 1, height - 1))
    body += _attr("displayWindow", "box2i", _box2i(0, 0, width - 1, height - 1))
    body += _attr("lineOrder", "lineOrder", bytes([0]))
    if part_name is not None:
        body += _attr("name", "string", part_name.encode("utf-8"))
    if part_type is not None:
        body += _attr("type", "string", part_type.encode("utf-8"))
    for k, v in (string_attrs or {}).items():
        body += _attr(k, "string", v.encode("utf-8"))
    body += b"\x00"  # end of this header
    return body


def single_part_exr_bytes(
    *,
    width: int = 960,
    height: int = 540,
    channels: Sequence[Tuple[str, str]] = (("R", "half"), ("G", "half"), ("B", "half")),
    string_attrs: Optional[Dict[str, str]] = None,
) -> bytes:
    """A single-part EXR header (no multipart bit)."""
    out = struct.pack("<i", _EXR_MAGIC)
    out += struct.pack("<i", 2)  # version 2, no flags
    out += _header_body(
        channels=channels, width=width, height=height, string_attrs=string_attrs
    )
    return out


def multipart_exr_bytes(
    *,
    width: int = 960,
    height: int = 540,
    fingerprint: Optional[str] = None,
    beauty_channels: Sequence[Tuple[str, str]] = (
        ("R", "half"), ("G", "half"), ("B", "half"), ("A", "half"),
    ),
    id_channel: Tuple[str, str] = ("id", "float"),
) -> bytes:
    """Two-part EXR header mirroring the live husk probe: part ``C`` (beauty,
    half) + part ``primid`` (``id``, float32). The fingerprint receipt, when
    given, rides as a string attribute on the beauty part."""
    string_attrs = {"synapse_retina_fingerprint": fingerprint} if fingerprint else None
    out = struct.pack("<i", _EXR_MAGIC)
    out += struct.pack("<i", 2 | _MULTIPART_FLAG)
    out += _header_body(
        channels=beauty_channels,
        width=width,
        height=height,
        part_name="C",
        part_type="scanlineimage",
        string_attrs=string_attrs,
    )
    out += _header_body(
        channels=[id_channel],
        width=width,
        height=height,
        part_name="primid",
        part_type="scanlineimage",
    )
    out += b"\x00"  # extra NUL terminating the multi-part header list
    return out


def not_an_exr_bytes() -> bytes:
    """Bytes with the wrong magic — for the reader's non-EXR path."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def write_bytes(path, data: bytes) -> str:
    """Write ``data`` to ``path`` (for on-disk product fixtures). Returns the path."""
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)


def write_done(product_path) -> str:
    """Drop a ``<product>.done`` sentinel next to a product fixture."""
    from pathlib import Path

    done = Path(str(product_path) + ".done")
    done.write_text('{"status": "rendered"}', encoding="utf-8")
    return str(done)
