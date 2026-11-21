"""R-023 -- the stdio image branch sends only what it can vouch for.

A capture or render result whose file is not a display media type is never
turned into ImageContent (an EXR used to be labelled image/png and read
whole), and a file over the shared vision-attachment ceiling is refused in
text with its size named.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("mcp")
pytest.importorskip("websockets")
mcp_server = pytest.importorskip("mcp_server")

from synapse.panel import vision_attach  # noqa: E402

CAPTURE = "houdini_capture_viewport"
RENDER = "houdini_render"


class _Recorder:
    """Fake mcp_server.send_command: returns the canned scene result."""

    def __init__(self, data):
        self.data = data
        self.calls = []

    async def __call__(self, cmd_type, payload=None):
        self.calls.append((cmd_type, payload))
        return self.data


def _call(monkeypatch, data, name=CAPTURE):
    recorder = _Recorder(data)
    monkeypatch.setattr(mcp_server, "send_command", recorder)
    result = asyncio.run(mcp_server.call_tool(name, {}))
    return result, recorder


def _blocks(result):
    """call_tool returns a plain list on success, a CallToolResult on failure."""
    if isinstance(result, dict):
        return result["content"]
    if hasattr(result, "content"):
        return result.content
    return result


def _kind(block):
    return block["type"] if isinstance(block, dict) else block.type


def _field(block, key):
    return block[key] if isinstance(block, dict) else getattr(block, key)


def _text(result):
    return "\n".join(_field(block, "text") for block in _blocks(result)
                     if _kind(block) == "text")


def test_the_ceiling_and_media_map_are_vision_attachs():
    # One owner for the policy (repair: reuse, do not fork a second copy).
    assert mcp_server._IMAGE_MAX_RAW_BYTES == vision_attach._MAX_RAW_BYTES
    assert mcp_server._IMAGE_MEDIA is vision_attach._MEDIA


def test_a_six_mb_exr_result_is_a_text_refusal_naming_the_size(monkeypatch, tmp_path):
    exr = tmp_path / "beauty.1001.exr"
    exr.write_bytes(b"v" * (6 * 1024 * 1024))
    result, recorder = _call(monkeypatch, {
        "image_path": str(exr), "format": "exr", "width": 1920, "height": 1080})

    assert recorder.calls, "the result should come through the WS command, not a shortcut"
    assert "image" not in [_kind(block) for block in _blocks(result)]
    meta = json.loads(_text(result))
    reason = meta["image_omitted"]
    assert f"{exr.stat().st_size / 1e6:.1f} MB" in reason, reason
    assert "limit" in reason, reason
    assert str(exr) in reason, reason


def test_a_small_exr_is_never_labelled_image_png(monkeypatch, tmp_path):
    exr = tmp_path / "beauty.1001.exr"
    exr.write_bytes(b"v" * 1024)
    result, _ = _call(monkeypatch, {"image_path": str(exr), "format": "exr"}, name=RENDER)

    assert "image" not in [_kind(block) for block in _blocks(result)]
    meta = json.loads(_text(result))
    assert meta["format"] == "exr"
    reason = meta["image_omitted"]
    assert str(exr) in reason, "the output path must ride in the text result"
    assert "not attached" in reason


def test_a_png_within_budget_is_attached_as_png(monkeypatch, tmp_path):
    png = tmp_path / "capture.png"
    payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    png.write_bytes(payload)

    result, _ = _call(monkeypatch, {"image_path": str(png), "format": "png"})
    images = [block for block in _blocks(result) if _kind(block) == "image"]

    assert len(images) == 1
    assert _field(images[0], "mimeType") == "image/png"
    assert base64.b64decode(_field(images[0], "data")) == payload


def test_a_jpeg_file_is_attached_as_jpeg(monkeypatch, tmp_path):
    jpg = tmp_path / "frame.jpg"
    jpg.write_bytes(b"\xff\xd8\xff" + b"\x00" * 16)

    result, _ = _call(monkeypatch, {"image_path": str(jpg), "format": "jpeg"})
    images = [block for block in _blocks(result) if _kind(block) == "image"]

    assert len(images) == 1
    assert _field(images[0], "mimeType") == "image/jpeg"


def test_a_missing_image_file_stays_a_tool_failure(monkeypatch, tmp_path):
    result, _ = _call(monkeypatch, {
        "image_path": str(tmp_path / "gone.png"), "format": "png"})

    assert _field(result, "isError") is True
    assert "wasn't found" in _text(result)
