"""Minimal, dependency-free OpenEXR **header** reader for T0.

Why this exists
---------------
T0 answers "did anything render, at the right resolution, with the right AOVs?"
That is a *header* question — it never needs a pixel. A full OpenEXR/OIIO decode
would drag a native library (and, at M1, a wheel) into a tier that is supposed
to be pure arithmetic on bytes. So T0 reads the header itself.

Ground truth (``harness/notes/perception_truth_22.0.368.json``, item 6, live on
22.0.368):

* **husk writes multi-part EXR.** The probe frame had ``oiio:subimages = 2`` —
  part ``C`` (R,G,B,A) plus part ``primid`` (single channel ``primid.id``). T0
  header parsing MUST be multi-part-aware, so this reader walks every part.
* **per-AOV pixel type is data-driven** — beauty ``C`` was 16-bit *half*, the
  ``primid`` AOV was *float32*. NEVER assume half; this reader reports the pixel
  type *read from the header* for every channel.
* the free receipt (``synapse_retina_fingerprint``) rides as a **string header
  attribute** (``husk --extra-metadata`` → EXR metadata), so this reader also
  surfaces arbitrary string attributes for the in-artifact manifest check.

Format facts encoded below (OpenEXR file layout spec):

* magic = ``20000630`` (``0x01312F76``) as a little-endian ``int32`` — the four
  on-disk bytes are ``76 2f 31 01``.
* version ``int32`` LE: low byte = format version (2); **bit 12 (0x1000) =
  multi-part**; bit 11 (0x800) = deep/non-image; bit 10 (0x400) = long names.
* an attribute = ``name\\0`` ``type\\0`` ``size:int32LE`` ``value[size]``.
* a header ends at an empty attribute name (a lone ``\\0``). In a **multi-part**
  file the sequence of headers is terminated by ONE additional ``\\0`` after the
  final header's terminator; a single-part file has exactly one header.
* ``chlist`` value = repeated ``name\\0`` ``pixelType:int32`` ``pLinear:uint8``
  + 3 reserved bytes ``xSampling:int32`` ``ySampling:int32``, ended by ``\\0``.
* ``box2i`` value = four ``int32`` (xMin,yMin,xMax,yMax); resolution derives from
  the *data* window as ``(xMax-xMin+1, yMax-yMin+1)``.

This is a reader, not a validator: it decodes the attributes T0 needs and is
tolerant of the rest. It is deliberately hermetic — no third-party import — so it
runs identically in the worker venv and in stock-python CI.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# EXR magic as the on-disk little-endian int32 (bytes 76 2f 31 01).
EXR_MAGIC = 20000630
_MULTIPART_FLAG = 0x1000

# int32 pixel-type code -> human name (OpenEXR PixelType enum).
_PIXEL_TYPES = {0: "uint", 1: "half", 2: "float"}

# Headers are tiny; never read an unbounded file into memory chasing a
# terminator on a corrupt/huge file.
_MAX_HEADER_BYTES = 1 << 20  # 1 MiB is orders of magnitude more than any header


class ExrHeaderError(ValueError):
    """Raised when the bytes are not a parseable EXR header."""


@dataclass
class ExrChannel:
    name: str
    pixel_type: str  # "half" | "float" | "uint" | "unknown:<n>"
    x_sampling: int = 1
    y_sampling: int = 1

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "pixel_type": self.pixel_type,
            "x_sampling": self.x_sampling,
            "y_sampling": self.y_sampling,
        }


@dataclass
class ExrPart:
    """One sub-image (part) of an EXR. Single-part files have exactly one."""

    name: Optional[str] = None  # part name ("C", "primid", ...) — None if unnamed
    type: Optional[str] = None  # "scanlineimage" / "tiledimage" / ...
    channels: List[ExrChannel] = field(default_factory=list)
    data_window: Optional[List[int]] = None
    display_window: Optional[List[int]] = None
    compression: Optional[int] = None
    string_attrs: Dict[str, str] = field(default_factory=dict)

    @property
    def resolution(self) -> Optional[List[int]]:
        """(width, height) from the DATA window, or None if absent."""
        w = self.data_window
        if not w or len(w) != 4:
            return None
        return [w[2] - w[0] + 1, w[3] - w[1] + 1]

    @property
    def channel_names(self) -> List[str]:
        return [c.name for c in self.channels]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "channels": [c.to_dict() for c in self.channels],
            "data_window": self.data_window,
            "display_window": self.display_window,
            "resolution": self.resolution,
            "compression": self.compression,
            "string_attrs": dict(self.string_attrs),
        }


@dataclass
class ExrHeader:
    version: int
    multipart: bool
    parts: List[ExrPart]

    @property
    def subimage_count(self) -> int:
        return len(self.parts)

    def all_channel_names(self) -> List[str]:
        """Every channel across every part, in ``part.channel`` convention where
        the part is named (matches husk's beauty ``C`` / AOV ``primid.id``)."""
        names: List[str] = []
        for part in self.parts:
            for ch in part.channels:
                if part.name and self.multipart:
                    names.append(f"{part.name}.{ch.name}")
                else:
                    names.append(ch.name)
        return names

    def string_attr(self, key: str) -> Optional[str]:
        """First occurrence of a string header attribute across parts — used to
        read the in-artifact ``synapse_retina_fingerprint`` receipt."""
        for part in self.parts:
            if key in part.string_attrs:
                return part.string_attrs[key]
        return None

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "multipart": self.multipart,
            "subimage_count": self.subimage_count,
            "parts": [p.to_dict() for p in self.parts],
        }


class _Cursor:
    """A forward-only cursor over a bytes buffer with bounds-checked reads."""

    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0

    def _need(self, n: int) -> None:
        if self.pos + n > len(self.buf):
            raise ExrHeaderError(
                f"truncated EXR header: wanted {n} bytes at offset {self.pos}, "
                f"only {len(self.buf) - self.pos} remain"
            )

    def read(self, n: int) -> bytes:
        self._need(n)
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out

    def read_int32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_uint8(self) -> int:
        return self.read(1)[0]

    def peek_byte(self) -> Optional[int]:
        if self.pos >= len(self.buf):
            return None
        return self.buf[self.pos]

    def read_cstring(self) -> str:
        """Read a NUL-terminated string (the NUL is consumed)."""
        end = self.buf.find(b"\x00", self.pos)
        if end == -1:
            raise ExrHeaderError(
                f"unterminated string at offset {self.pos} (no NUL before EOF)"
            )
        if end - self.pos > _MAX_HEADER_BYTES:
            raise ExrHeaderError("implausibly long header string — refusing to read")
        out = self.buf[self.pos:end].decode("utf-8", errors="replace")
        self.pos = end + 1
        return out


def _parse_chlist(value: bytes) -> List[ExrChannel]:
    cur = _Cursor(value)
    channels: List[ExrChannel] = []
    while True:
        if cur.peek_byte() == 0:  # empty channel name terminates the list
            cur.read(1)
            break
        name = cur.read_cstring()
        ptype = cur.read_int32()
        cur.read(4)  # pLinear (1 byte) + 3 reserved
        x_samp = cur.read_int32()
        y_samp = cur.read_int32()
        channels.append(
            ExrChannel(
                name=name,
                pixel_type=_PIXEL_TYPES.get(ptype, f"unknown:{ptype}"),
                x_sampling=x_samp,
                y_sampling=y_samp,
            )
        )
    return channels


def _parse_box2i(value: bytes) -> Optional[List[int]]:
    if len(value) < 16:
        return None
    return list(struct.unpack("<iiii", value[:16]))


def _parse_string(value: bytes) -> str:
    # An EXR "string" attribute value is the raw bytes (length == attr size);
    # there is no inner length prefix (that is "stringvector").
    return value.decode("utf-8", errors="replace")


def _parse_one_header(cur: _Cursor) -> ExrPart:
    part = ExrPart()
    while True:
        if cur.peek_byte() == 0:  # lone NUL = end of this header
            cur.read(1)
            break
        name = cur.read_cstring()
        attr_type = cur.read_cstring()
        size = cur.read_int32()
        if size < 0 or size > _MAX_HEADER_BYTES:
            raise ExrHeaderError(
                f"attribute {name!r} has implausible size {size}"
            )
        value = cur.read(size)

        if name == "channels" and attr_type == "chlist":
            part.channels = _parse_chlist(value)
        elif name == "dataWindow" and attr_type == "box2i":
            part.data_window = _parse_box2i(value)
        elif name == "displayWindow" and attr_type == "box2i":
            part.display_window = _parse_box2i(value)
        elif name == "compression" and attr_type == "compression" and value:
            part.compression = value[0]
        elif name == "name" and attr_type == "string":
            part.name = _parse_string(value)
        elif name == "type" and attr_type == "string":
            part.type = _parse_string(value)
        elif attr_type == "string":
            # Arbitrary string attribute (e.g. the synapse_retina_fingerprint
            # receipt) — keep it for the manifest-in-EXR check.
            part.string_attrs[name] = _parse_string(value)
        # every other attribute type is skipped by design (value already consumed)
    return part


def parse_exr_header(data: bytes) -> ExrHeader:
    """Parse EXR header bytes into an :class:`ExrHeader` (multi-part aware).

    Raises :class:`ExrHeaderError` if the magic is wrong or the bytes truncate
    mid-header. Callers that want "not an EXR" to be a soft, honest signal (T0
    does) should catch :class:`ExrHeaderError`.
    """
    cur = _Cursor(data)
    magic = cur.read_int32()
    if magic != EXR_MAGIC:
        raise ExrHeaderError(
            f"not an EXR: magic 0x{magic & 0xFFFFFFFF:08x} != 0x{EXR_MAGIC:08x}"
        )
    version_field = cur.read_int32()
    multipart = bool(version_field & _MULTIPART_FLAG)

    parts: List[ExrPart] = []
    if not multipart:
        parts.append(_parse_one_header(cur))
    else:
        # Headers concatenated; the list ends with an extra lone NUL after the
        # final header's own terminator.
        while True:
            nxt = cur.peek_byte()
            if nxt is None:
                raise ExrHeaderError(
                    "multi-part EXR header ended without the list terminator"
                )
            if nxt == 0:  # the extra NUL closing the header list
                cur.read(1)
                break
            parts.append(_parse_one_header(cur))

    return ExrHeader(version=version_field & 0xFFFFFFFF, multipart=multipart, parts=parts)


def read_exr_header(path: str | Path, *, max_bytes: int = _MAX_HEADER_BYTES) -> ExrHeader:
    """Open ``path`` and parse just enough of its head to decode the EXR header.

    Reads a bounded prefix (headers precede pixel data), so this is cheap even on
    a 24 MB float frame. Propagates :class:`ExrHeaderError` for non-EXR / truncated
    inputs and ``OSError`` for unreadable paths — T0 turns both into honest
    ``inconclusive``/``fail`` verdicts rather than a silent pass.
    """
    p = Path(path)
    with p.open("rb") as fh:
        data = fh.read(max_bytes)
    return parse_exr_header(data)
