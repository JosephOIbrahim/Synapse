"""Attach a captured viewport to a tool result, so the model can SEE it.

THE GAP THIS CLOSES. `_handle_capture_viewport` has always worked: it drives
Houdini's flipbook API to read the GL framebuffer correctly (QWidget.grab()
returns black on a GL surface), marshals to the main thread, and writes a file.

And the file went nowhere. `claude_worker` contained ZERO occurrences of
"image" or "base64" - the capture existed, and no model had ever been shown one.
SYNAPSE could take the picture and never showed it to anybody.

Anthropic's API accepts a LIST of content blocks inside a tool_result, images
included. So the whole missing link is: notice the tool returned a path, read the
bytes, base64 them, and put an image block beside the text.

WHAT THIS DELIBERATELY DOES NOT DO.

It does not attach to a model that cannot see. Ollama's glm-5:cloud is the
registry's default pick (R162) and vision support is per-model, not per-provider
- sending an image to a text-only model wastes the upload and may fail the call
outright. Capability is checked, and when it is absent the text result is
returned unchanged.

It does not attach a file it cannot vouch for. A missing path, an empty file, an
unknown extension or anything over the API's size limit falls back to text with
a stated reason. A silent failure here would look exactly like a model that
looked and saw nothing, which is the worst of both.
"""
import base64
import os

# Anthropic caps an image at 5MB base64-encoded. Encoding inflates by ~4/3, so
# the raw ceiling is lower than the documented number.
_MAX_RAW_BYTES = int(5 * 1024 * 1024 * 3 / 4)

_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Substrings that mark a model as vision-capable. Deliberately a denylist-free
# allowlist: an unknown model does NOT get an image, because a wasted upload is
# cheaper to explain than a failed call.
_VISION_HINTS = ("claude-", "gpt-4", "gpt-5", "gemini", "llava", "-vl", "vision",
                 "qwen2.5vl", "qwen3-vl", "pixtral", "opus", "sonnet", "haiku",
                 "fable", "mythos")


def model_can_see(model: str) -> bool:
    """Is this model worth sending an image to?

    Unknown models return False. The cost of a false negative is a text-only
    answer; the cost of a false positive is a failed API call mid-turn.
    """
    if not model:
        return False
    m = str(model).lower()
    return any(h in m for h in _VISION_HINTS)


def find_image_path(result) -> "str | None":
    """Pull an image path out of a tool result, or None.

    Looks only at keys a capture tool actually sets. Deliberately narrow: a tool
    that merely MENTIONS a path in prose should not cause an upload.
    """
    if not isinstance(result, dict):
        return None
    for key in ("image_path", "path", "file", "output_path", "capture_path"):
        val = result.get(key)
        if isinstance(val, str) and os.path.splitext(val)[1].lower() in _MEDIA:
            return val
    return None


def encode_image_block(path: str):
    """(block, None) on success, (None, reason) on refusal.

    Every refusal carries a reason, because a silent one is indistinguishable
    from a model that looked and saw nothing.
    """
    ext = os.path.splitext(path)[1].lower()
    media = _MEDIA.get(ext)
    if media is None:
        return None, "unsupported image type %s" % (ext or "(none)")
    if not os.path.isfile(path):
        return None, "capture file not found: %s" % path
    size = os.path.getsize(path)
    if size == 0:
        return None, "capture file is empty"
    if size > _MAX_RAW_BYTES:
        return None, ("capture is %.1f MB, over the %.1f MB API limit"
                      % (size / 1e6, _MAX_RAW_BYTES / 1e6))
    try:
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
    except OSError as exc:
        return None, "capture unreadable: %s" % exc
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media, "data": data},
    }, None


def attach_image(tool_result: dict, raw_result, model: str):
    """Return `(tool_result, verdict)`.

    `verdict` is None when there was no image to consider, or
    `("ok"|"fail", reason)` when there was. The CALLER surfaces that to the
    artist - see the note below, which is the whole reason this returns a
    verdict at all rather than just a dict.

    WHY A VERDICT AND NOT JUST A NOTE IN THE TEXT.

    The first version put the refusal in the tool result and trusted the model
    to relay it. Measured on a live turn: glm-5:cloud received "the active model
    is not vision-capable, so it was not attached", ABSORBED IT, and answered
    "here's what I can see from the viewport capture" - a fluent description of
    a sphere, entirely inferred from the node graph, indistinguishable from
    sight.

    A note in a tool result is a REQUEST. It is not enforcement. The artist has
    to be told by the PANEL, on a surface the model does not author.
    """
    if not isinstance(tool_result, dict) or tool_result.get("is_error"):
        return tool_result, None

    path = find_image_path(raw_result)
    if path is None:
        return tool_result, None

    if not model_can_see(model):
        reason = "%s is not vision-capable — the capture was NOT sent" % (model or "model")
        return _with_note(tool_result, reason), ("fail", reason)

    block, why = encode_image_block(path)
    if block is None:
        reason = "capture not attached: %s" % why
        return _with_note(tool_result, reason), ("fail", reason)

    text = tool_result.get("content")
    if not isinstance(text, str):
        text = str(text)
    out = dict(tool_result)
    out["content"] = [{"type": "text", "text": text}, block]
    return out, ("ok", "viewport image sent to %s" % model)


def _with_note(tool_result: dict, note: str) -> dict:
    """Say why an image is absent, in the result the model actually reads."""
    text = tool_result.get("content")
    if not isinstance(text, str):
        text = str(text)
    out = dict(tool_result)
    out["content"] = "%s\n\n[%s]" % (text, note)
    return out
