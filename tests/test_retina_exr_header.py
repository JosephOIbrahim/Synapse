"""RETINA T0 — pure-python EXR header reader tests.

Exercises the multi-part-aware header reader against synthetic headers built by
``retina.tests.fixtures.exr_synth`` (hermetic — no Houdini/OpenEXR needed). The
synthetic layouts mirror the live husk probe (catalog item 6): a 2-part EXR with
a half-float beauty part ``C`` and a float32 ``primid`` part.

These import the repo-root ``retina`` package, which resolves because the CI gate
runs ``python -m pytest tests/`` from the repo root (``-m`` puts cwd on sys.path,
the same mechanism that makes ``import shared`` work in the existing suite).
"""

from __future__ import annotations

import pytest

from retina.exr_header import ExrHeaderError, parse_exr_header, read_exr_header
from retina.tests.fixtures import exr_synth


def test_single_part_header_parses():
    data = exr_synth.single_part_exr_bytes(width=640, height=480)
    header = parse_exr_header(data)
    assert not header.multipart
    assert header.subimage_count == 1
    part = header.parts[0]
    assert part.resolution == [640, 480]
    assert part.channel_names == ["R", "G", "B"]
    assert all(c.pixel_type == "half" for c in part.channels)


def test_multipart_header_is_multipart_aware():
    # The live husk shape: part C (RGBA half) + part primid (id float32).
    data = exr_synth.multipart_exr_bytes(width=960, height=540)
    header = parse_exr_header(data)
    assert header.multipart
    assert header.subimage_count == 2

    names = [p.name for p in header.parts]
    assert names == ["C", "primid"]

    beauty, primid = header.parts
    assert beauty.resolution == [960, 540]
    assert [c.name for c in beauty.channels] == ["R", "G", "B", "A"]
    assert all(c.pixel_type == "half" for c in beauty.channels)


def test_per_aov_pixel_type_is_data_driven_not_assumed():
    # Catalog item 6: NEVER assume half — beauty is half, primid is float32.
    data = exr_synth.multipart_exr_bytes()
    header = parse_exr_header(data)
    beauty, primid = header.parts
    assert beauty.channels[0].pixel_type == "half"
    assert primid.channels[0].pixel_type == "float"


def test_all_channel_names_use_part_dot_channel_convention():
    data = exr_synth.multipart_exr_bytes()
    header = parse_exr_header(data)
    names = header.all_channel_names()
    # Multi-part -> part-qualified names (husk convention part.channel).
    assert "C.R" in names
    assert "primid.id" in names


def test_fingerprint_receipt_surfaces_from_string_attr():
    data = exr_synth.multipart_exr_bytes(fingerprint="rm1cafef00dbaad")
    header = parse_exr_header(data)
    assert header.string_attr("synapse_retina_fingerprint") == "rm1cafef00dbaad"


def test_missing_fingerprint_returns_none():
    data = exr_synth.multipart_exr_bytes(fingerprint=None)
    header = parse_exr_header(data)
    assert header.string_attr("synapse_retina_fingerprint") is None


def test_non_exr_raises_header_error():
    with pytest.raises(ExrHeaderError):
        parse_exr_header(exr_synth.not_an_exr_bytes())


def test_truncated_header_raises_header_error():
    data = exr_synth.single_part_exr_bytes()
    with pytest.raises(ExrHeaderError):
        parse_exr_header(data[:12])  # magic + version, then cut off


def test_read_from_disk(tmp_path):
    p = tmp_path / "frame.0001.exr"
    exr_synth.write_bytes(p, exr_synth.multipart_exr_bytes(width=512, height=512))
    header = read_exr_header(p)
    assert header.multipart
    assert header.parts[0].resolution == [512, 512]


def test_compression_byte_decoded():
    data = exr_synth.single_part_exr_bytes()
    header = parse_exr_header(data)
    # exr_synth writes compression=3 (zips), matching the probe.
    assert header.parts[0].compression == 3
