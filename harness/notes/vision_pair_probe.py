"""Does a before/after pair already reach the model in one turn?

The vision-based diff needs two images the model can compare. The worker
collects every tool_result from a turn into ONE user message, and the attach
fires per-result - so two captures in one turn SHOULD already produce two image
blocks side by side, with no new code at all.

That is worth checking before building a diff pipeline. If it holds, the
capability exists and only needs to be asked for.
"""
import base64
import os
import sys
import tempfile

sys.path.insert(0, "python")

from synapse.panel.vision_attach import attach_image

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

paths = []
for name in ("synapse_before.png", "synapse_after.png"):
    p = os.path.join(tempfile.gettempdir(), name)
    with open(p, "wb") as fh:
        fh.write(PNG)
    paths.append(p)

results = []
for i, p in enumerate(paths):
    tr = {"type": "tool_result", "tool_use_id": "t%d" % i,
          "content": '{"image_path": "%s"}' % p.replace("\\", "/"),
          "is_error": False}
    out, verdict = attach_image(tr, {"image_path": p}, "claude-fable-5")
    attached = isinstance(out.get("content"), list)
    results.append(out)
    print("  capture %d  ->  %-16s  verdict %s"
          % (i + 1, "IMAGE ATTACHED" if attached else "text only",
             verdict[0] if verdict else "-"))

# The worker appends every result from a turn as ONE user message.
imgs = sum(1
           for r in results
           if isinstance(r.get("content"), list)
           for b in r["content"]
           if b.get("type") == "image")

print()
print("  image blocks in ONE user message :", imgs)
print("  a before/after pair reaches the model in a single turn :", imgs == 2)
print()
if imgs == 2:
    print("  So the diff capability EXISTS. It needs asking for, not building:")
    print("  'capture the viewport, add a light, capture it again, and tell me")
    print("   what changed'")

for p in paths:
    os.unlink(p)

sys.exit(0 if imgs == 2 else 1)
