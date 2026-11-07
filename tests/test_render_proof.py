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
from types import SimpleNamespace

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


# ---------------------------------------------------------------------------
# Review round 2 — the paths that could still certify the wrong thing
# ---------------------------------------------------------------------------

def test_an_unreadable_baseline_proves_nothing(monkeypatch):
    """A permission error before the render is not evidence of absence."""
    from synapse.server import handlers_render as hr

    def _denied(self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "stat", _denied)

    assert hr._product_identity("C:/nowhere/f.exr") is None
    assert hr._product_changed(None, (True, 4096, 99)) is False


def test_the_sentinel_stamps_the_inherited_nonce(monkeypatch, tmp_path):
    """A later attempt's manifest cannot change the nonce an earlier hook stamps."""
    from synapse.host import retina_sentinel_postframe as sentinel

    product = tmp_path / "f.exr"
    product.write_bytes(b"pixels")
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "products": [str(product)], "render_nonce": "attempt-B", "fingerprint": "fp",
    }), encoding="utf-8")

    monkeypatch.setenv(sentinel.MANIFEST_ENV_VAR, str(manifest))
    monkeypatch.setenv(sentinel.NONCE_ENV_VAR, "attempt-A")

    assert sentinel.run() == 1
    body = json.loads((tmp_path / "f.exr.done").read_text(encoding="utf-8"))
    assert body["render_nonce"] == "attempt-A"

    checks = _checks(_run({**_manifest(tmp_path), "render_nonce": "attempt-B"}))
    assert checks["done_sentinels"]["pass"] is False  # B is looking at A's product


def _stub_header():
    return SimpleNamespace(parts=[], all_channel_names=lambda: [],
                           string_attr=lambda key: None)


def test_an_unwired_receipt_is_inconclusive_not_a_failure(tmp_path):
    """A hook that never ran cannot fail the artifact for its missing receipt."""
    product = tmp_path / "f.exr"
    product.write_bytes(b"pixels")
    manifest = {
        "output_file": str(product),
        "render_nonce": "n1",
        "done_wired": False,   # the space-in-path case: hook never wired
        "receipt_wired": False,
        "fingerprint": "fp-declared",
    }
    event = check_manifest_against_disk(
        manifest, now="2026-11-06T00:00:00Z",
        exr_reader=lambda path: _stub_header())
    checks = _checks(event)
    assert checks["fingerprint_receipt"]["pass"] is None
    assert event["verdict"] != "fail"


class _Cfg:
    def lookup(self, key):
        return {
            "resolution.render": ((1920, 1080), "default"),
            "resolution.preview": ((1280, 720), "default"),
        }[key]


def _progressive_handler(monkeypatch, render_result, seen):
    from synapse.server import handlers as handlers_mod
    from synapse.server import handlers_render as hr

    monkeypatch.setattr(hr, "HOU_AVAILABLE", True)
    monkeypatch.setattr(hr, "get_show_config", lambda *a, **k: _Cfg())
    monkeypatch.setattr(hr, "resolve_show_dirs", lambda *a, **k: {})

    handler = handlers_mod.SynapseHandler()
    handler._handle_render_settings = lambda payload: {}
    handler._handle_render = (
        render_result if callable(render_result) else (lambda payload: render_result))
    handler._handle_validate_frame = lambda payload: (
        seen.append(payload) or {"valid": True})
    return handler


def test_a_progressive_pass_rejects_a_flipbook(monkeypatch):
    seen = []
    handler = _progressive_handler(monkeypatch, {
        "image_path": "x_glpreview.0001.jpg", "flipbook_fallback": True}, seen)
    out = handler._handle_render_progressively({"rop_path": "/stage/karma1"})
    assert out["passes"][0]["status"] == "failed"
    assert seen == []


def test_a_progressive_pass_validates_the_product(monkeypatch):
    seen = []
    handler = _progressive_handler(monkeypatch, {
        "image_path": "/tmp/f.preview.jpg", "output_file": "/tmp/f.exr"}, seen)
    out = handler._handle_render_progressively({"rop_path": "/stage/karma1"})
    assert out["passes"][0]["status"] == "passed"
    assert seen and seen[0]["image_path"] == "/tmp/f.exr"
    assert out["final_image"] == "/tmp/f.exr"


def test_a_manifest_is_per_attempt(tmp_path):
    """B writing its manifest must not change what A's receipt reads."""
    from synapse.host import retina_manifest as rm
    from synapse.panel.render_receipt import compute_receipt

    product = tmp_path / "f.exr"
    product.write_bytes(b"pixels")
    path_a = rm.manifest_path_for(str(product), "attempt-A")
    path_b = rm.manifest_path_for(str(product), "attempt-B")
    assert path_a != path_b

    Path(path_a).write_text(json.dumps({
        "output_file": str(product), "render_nonce": "attempt-A",
        "done_wired": True, "receipt_wired": True,
    }), encoding="utf-8")
    result = {"retina": {"manifest_path": path_a, "render_nonce": "attempt-A"}}

    first = compute_receipt("houdini_render", result, now="2026-11-06T00:00:00Z")
    assert first is not None

    Path(path_b).write_text(json.dumps({
        "output_file": str(product), "render_nonce": "attempt-B",
    }), encoding="utf-8")
    again = compute_receipt("houdini_render", result, now="2026-11-06T00:00:00Z")
    assert again is not None and again["verdict"] == first["verdict"]


def test_a_receipt_from_another_nonce_is_refused(tmp_path):
    from synapse.host import retina_manifest as rm
    from synapse.panel.render_receipt import compute_receipt

    product = tmp_path / "f.exr"
    product.write_bytes(b"pixels")
    path_a = rm.manifest_path_for(str(product), "attempt-A")
    Path(path_a).write_text(json.dumps({
        "output_file": str(product), "render_nonce": "attempt-B",
    }), encoding="utf-8")

    result = {"retina": {"manifest_path": path_a, "render_nonce": "attempt-A"}}
    assert compute_receipt("houdini_render", result, now="t") is None


def test_a_refused_final_pass_fails_the_run(monkeypatch):
    seen = []
    calls = {"n": 0}

    def render(payload):
        calls["n"] += 1
        if calls["n"] == 3:
            return {"image_path": "x_glpreview.0001.jpg", "flipbook_fallback": True}
        return {"image_path": f"/tmp/p{calls['n']}.preview.jpg",
                "output_file": f"/tmp/p{calls['n']}.exr"}

    handler = _progressive_handler(monkeypatch, render, seen)
    out = handler._handle_render_progressively({"rop_path": "/stage/karma1"})

    assert out["success"] is False
    assert out["final_image"] is None
    assert out["last_product"] == "/tmp/p2.exr"
    assert [p["status"] for p in out["passes"]] == ["passed", "passed", "failed"]


def test_a_final_pass_validation_failure_fails_the_run(monkeypatch):
    seen = []
    calls = {"n": 0}

    def render(payload):
        calls["n"] += 1
        return {"image_path": f"/tmp/p{calls['n']}.preview.jpg",
                "output_file": f"/tmp/p{calls['n']}.exr"}

    def validate(payload):
        seen.append(payload)
        valid = len(seen) < 3
        return {"valid": valid, "summary": "ok" if valid else "black frame"}

    handler = _progressive_handler(monkeypatch, render, seen)
    handler._handle_validate_frame = validate
    out = handler._handle_render_progressively({"rop_path": "/stage/karma1"})

    assert out["success"] is False
    assert out["final_image"] is None
    assert out["passes"][-1]["status"] == "failed"
