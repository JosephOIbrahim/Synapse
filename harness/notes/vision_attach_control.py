"""Control for the viewport-vision link.

The capture always worked and the file went nowhere - claude_worker contained
ZERO occurrences of "image" or "base64". This closes that, and the risks are all
in the refusal paths rather than the happy one.

Asserts, in order of what would hurt most:

  1. A REFUSAL IS NEVER SILENT. Every path that declines to attach must say so
     in the text the model reads. A silent skip is indistinguishable from a
     model that looked and saw nothing - the worst possible failure, because it
     produces a confident answer about an image nobody sent.
  2. A TEXT-ONLY MODEL GETS NO IMAGE. glm-5:cloud is the registry default
     (R162); sending it an image wastes the upload and may fail the call.
  3. AN UNKNOWN MODEL GETS NO IMAGE. Unknown is treated as text-only - a
     text-only answer costs less than a failed call mid-turn.
  4. The happy path actually produces a valid Anthropic image block.
  5. A tool with no image path is passed through UNCHANGED - this must not
     touch the 120 tools that never capture anything.
"""
import base64
import os
import sys
import tempfile

sys.path.insert(0, "python")

from synapse.panel.vision_attach import (
    attach_image, encode_image_block, find_image_path, model_can_see,
)

ok = {}

# A real 1x1 PNG, so the encode path is exercised rather than mocked.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
tmp = os.path.join(tempfile.gettempdir(), "synapse_vision_control.png")
with open(tmp, "wb") as fh:
    fh.write(PNG)

base = {"type": "tool_result", "tool_use_id": "t1",
        "content": '{"image_path": "%s"}' % tmp.replace("\\", "/"),
        "is_error": False}
raw = {"image_path": tmp}


def content_of(r):
    return r.get("content")


# 2 + 1 - a text-only model gets no image, and is TOLD why
r, _v = attach_image(dict(base), raw, "glm-5:cloud")
ok["text-only model gets no image"] = isinstance(content_of(r), str)
ok["and is told why"] = "not vision-capable" in str(content_of(r))

# 3 - unknown model is treated as text-only
ok["unknown model gets no image"] = not model_can_see("some-new-model-x")

# 4 - the happy path
r, _v = attach_image(dict(base), raw, "claude-sonnet-4-6")
blocks = content_of(r)
ok["vision model gets a list"] = isinstance(blocks, list)
if isinstance(blocks, list):
    img = [b for b in blocks if b.get("type") == "image"]
    ok["exactly one image block"] = len(img) == 1
    if img:
        s = img[0]["source"]
        ok["valid anthropic image source"] = (
            s.get("type") == "base64"
            and s.get("media_type") == "image/png"
            and len(s.get("data", "")) > 0)
    ok["text survives beside it"] = any(b.get("type") == "text" for b in blocks)

# 1 - a missing file refuses LOUDLY
r, _v = attach_image(dict(base), {"image_path": tmp + ".nope.png"}, "claude-sonnet-4-6")
ok["missing file refuses loudly"] = (
    isinstance(content_of(r), str) and "not attached" in content_of(r))

# 5 - a tool with no image is untouched
plain = {"type": "tool_result", "tool_use_id": "t2",
         "content": '{"ok": true}', "is_error": False}
r, _v = attach_image(dict(plain), {"ok": True}, "claude-sonnet-4-6")
ok["no-image tool passes through"] = r == plain

# and an errored tool is never decorated
err = {"type": "tool_result", "tool_use_id": "t3",
       "content": "boom", "is_error": True}
ok["errored tool untouched"] = attach_image(dict(err), raw, "claude-sonnet-4-6")[0] == err

# THE ASSERTION THIS CHANGE EXISTS FOR: a refusal must reach the PANEL.
# A note in the tool result is a request - glm-5:cloud absorbed one and
# answered as if it had looked. The verdict is what the panel flags.
_r, v = attach_image(dict(base), raw, "glm-5:cloud")
ok["refusal returns a fail verdict"] = v is not None and v[0] == "fail"
_r, v = attach_image(dict(base), raw, "claude-sonnet-4-6")
ok["success returns an ok verdict"] = v is not None and v[0] == "ok"
_r, v = attach_image(dict(plain), {"ok": True}, "claude-sonnet-4-6")
ok["no image returns no verdict"] = v is None

print("%-36s %s" % ("ASSERTION", "RESULT"))
print("-" * 48)
for k, v in ok.items():
    print("%-36s %s" % (k, v))

os.unlink(tmp)

allok = all(ok.values())
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
