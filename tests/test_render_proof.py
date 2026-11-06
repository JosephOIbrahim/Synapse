"""G32: prove this render produced this frame.

Three failures, one question: is the frame on disk the one this render wrote?

- H3-1: any non-empty file at the product path counted as a successful render,
  so a husk that failed without raising left yesterday's frame looking fresh.
- H3-2: the farm validated `image_path`, which can be a preview or a GL
  flipbook grab; the product never reached validation.
- H3-9: RETINA T0 read a `.done` left by a previous attempt as this render's
  pixels-landed signal, and failed good frames when the sentinel was never
  wired at all.

No Houdini is needed: the handler's proof is a pure function of two identities,
the farm's is a callback response, and T0 reads bytes.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from retina.exr_header import ExrHeaderError  # noqa: E402
from retina.t0 import check_manifest_against_disk  # noqa: E402
from synapse.server.handlers_render import (  # noqa: E402
    _product_changed,
    _product_identity,
)
from synapse.server.render_farm import (  # noqa: E402
    RenderCallbacks,
    RenderFarmOrchestrator,
)


# ---------------------------------------------------------------------------
# H3-1 — the product's identity must change
# ---------------------------------------------------------------------------

def test_identity_of_a_missing_product(tmp_path):
    assert _product_identity(str(tmp_path / "nothing.exr")) == (False, 0, 0)


def test_identity_of_a_written_product(tmp_path):
    product = tmp_path / "frame.0001.exr"
    product.write_bytes(b"pixels")
    exists, size, mtime_ns = _product_identity(str(product))
    assert exists is True
    assert size == len(b"pixels")
    assert mtime_ns > 0


def test_a_stale_frame_is_not_proof():
    before = (True, 4096, 111)
    assert _product_changed(before, (True, 4096, 111)) is False
    assert _product_changed(before, (True, 4096, 112)) is True
    assert _product_changed(before, (True, 8192, 112)) is True


def test_no_file_before_and_none_after_is_not_proof():
    assert _product_changed((False, 0, 0), (False, 0, 0)) is False
    assert _product_changed((False, 0, 0), (True, 0, 5)) is False  # still empty
    assert _product_changed((False, 0, 0), (True, 12, 5)) is True


# ---------------------------------------------------------------------------
# H3-2 — the farm validates the product, not the preview
# ---------------------------------------------------------------------------

def _farm(render_resp, validate):
    callbacks = RenderCallbacks(
        render_frame=lambda payload: render_resp,
        validate_frame=validate,
        get_render_settings=lambda payload: {"settings": {}},
        set_render_settings=lambda payload: {"settings": {}},
    )
    return RenderFarmOrchestrator(callbacks)


def test_a_flipbook_grab_is_a_failed_frame():
    seen = []
    farm = _farm({"image_path": "x_glpreview.0001.jpg", "flipbook_fallback": True},
                 lambda payload: seen.append(payload) or {"valid": True})
    try:
        result = farm._render_frame_only("/out/u", 1)
    finally:
        farm.shutdown()
    assert result.success is False
    assert "flipbook" in result.error.lower()
    assert seen == []  # nothing was validated


def test_a_preview_without_a_product_is_a_failed_frame():
    farm = _farm({"image_path": "preview.jpg"},
                 lambda payload: {"valid": True})
    try:
        result = farm._render_frame_only("/out/u", 1)
    finally:
        farm.shutdown()
    assert result.success is False
    assert "output_file" in result.error


def test_validation_receives_the_product_not_the_preview():
    seen = []
    farm = _farm(
        {"image_path": "/tmp/f.0001.preview.jpg",
         "output_file": "/tmp/f.0001.exr"},
        lambda payload: seen.append(payload) or {"valid": True},
    )
    try:
        result = farm._render_frame_only("/out/u", 1)
    finally:
        farm.shutdown()
    assert result.success is True
    assert result.output_file == "/tmp/f.0001.exr"

    seen.clear()
    farm = _farm(
        {"image_path": "/tmp/f.0001.preview.jpg",
         "output_file": "/tmp/f.0001.exr"},
        lambda payload: seen.append(payload) or {"valid": True},
    )
    try:
        validated = farm.render_frame_validated("/out/u", 1)
    finally:
        farm.shutdown()
    assert validated.success is True
    assert seen and seen[0]["output_file"] == "/tmp/f.0001.exr"
    assert seen[0]["image_path"] == "/tmp/f.0001.exr"


# ---------------------------------------------------------------------------
# H3-9 — T0 reads the product file and matches this render's nonce
# ---------------------------------------------------------------------------

def _checks(event):
    return {c["name"]: c for c in event["checks"]}


def _reader_that_cannot_read(path):
    raise ExrHeaderError("not an EXR this reader understands")


def _manifest(tmp_path, *, nonce="nonce-1", done_wired=True, done_nonce="nonce-1",
              done_file=True, products=None):
    product = tmp_path / "frame.0001.exr"
    product.write_bytes(b"pixels")
    manifest = {
        "output_file": str(product),
        "products": products if products is not None else [str(product)],
        "render_nonce": nonce,
        "done_wired": done_wired,
    }
    if done_file:
        body = {"status": "rendered"}
        if done_nonce is not None:
            body["render_nonce"] = done_nonce
        (tmp_path / "frame.0001.exr.done").write_text(json.dumps(body))
    return manifest


def _run(manifest):
    return check_manifest_against_disk(
        manifest, now="2026-11-06T00:00:00Z",
        exr_reader=_reader_that_cannot_read)


def test_output_file_is_the_product(tmp_path):
    """The manifest's products list may name something else; output_file wins."""
    manifest = _manifest(tmp_path, products=[str(tmp_path / "gone.exr")])
    checks = _checks(_run(manifest))
    assert checks["products_exist"]["pass"] is True
    assert checks["product_count"]["pass"] is True


def test_done_with_this_render_nonce_passes(tmp_path):
    checks = _checks(_run(_manifest(tmp_path)))
    assert checks["done_sentinels"]["pass"] is True


def test_done_from_another_render_fails(tmp_path):
    checks = _checks(_run(_manifest(tmp_path, done_nonce="nonce-0")))
    assert checks["done_sentinels"]["pass"] is False
    assert "stale" in checks["done_sentinels"]["detail"]


def test_done_without_a_nonce_is_inconclusive(tmp_path):
    checks = _checks(_run(_manifest(tmp_path, done_nonce=None)))
    assert checks["done_sentinels"]["pass"] is None


def test_manifest_without_a_nonce_is_inconclusive(tmp_path):
    checks = _checks(_run(_manifest(tmp_path, nonce=None)))
    assert checks["done_sentinels"]["pass"] is None


def test_an_unwired_sentinel_is_inconclusive_not_a_failure(tmp_path):
    checks = _checks(_run(_manifest(tmp_path, done_wired=False, done_file=False)))
    assert checks["done_sentinels"]["pass"] is None
    assert "never wired" in checks["done_sentinels"]["detail"]
