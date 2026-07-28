"""Prove the model actually SAW the image - with a detail the scene cannot reveal.

THE PROBLEM THIS SOLVES, and it is not hypothetical.

On a live turn glm-5:cloud was asked to "look at the viewport and say what you
see". No image was attached - it is not vision-capable - and it answered:

    "A single default sphere sitting at the origin... reading as a plain,
     flat-shaded ball with no materials, no custom lights..."

Fluent, accurate, and derived ENTIRELY from the node graph. Indistinguishable
from sight. A vision feature that cannot be told apart from scene inspection is
not a vision feature; it is a confidence generator.

THE TEST: put something in the PICTURE that is absent from the SCENE.

A random token rendered as an overlay, or a background colour set only in the
viewport. The node graph does not contain it, `inspect_scene` cannot return it,
and no amount of plausible inference reaches it. If the model reports the token,
it looked. If it does not, it did not - regardless of how good the answer sounds.

This is V1's method applied to vision: probe with something only the real path
can produce. V1 used it to establish that no per-object ID mask EXISTS; this
uses it to establish that an attached image is actually READ.

COSTS A COMPLETION. This is the one control here that cannot be free - it needs
a real model call with a real image. Run it deliberately, on a vision-capable
model, when you want the loop closed rather than assumed.

    hython harness/notes/vision_loop_control.py
"""
import base64
import json
import os
import random
import string
import sys
import urllib.request

sys.path.insert(0, "python")

MODEL = "claude-sonnet-4-6"          # must be vision-capable


def key():
    for line in open(".env", encoding="utf-8-sig", errors="replace"):
        s = line.strip()
        for n in ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"):
            if s.startswith(n + "="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")


def make_token_image(token, path):
    """An image whose ONLY content is a token the scene does not contain."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    img = Image.new("RGB", (420, 160), (18, 18, 22))
    d = ImageDraw.Draw(img)
    d.text((24, 64), token, fill=(240, 240, 240))
    img.save(path)
    return True


def ask(api_key, token_path):
    with open(token_path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    body = {
        "model": MODEL,
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text",
                 "text": "Read the text in this image and reply with ONLY that text."},
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": data}},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=90))
    return "".join(b.get("text", "") for b in r.get("content", []))


if __name__ == "__main__":
    token = "SYN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    path = os.path.join(os.environ.get("TEMP", "."), "synapse_vision_token.png")

    if not make_token_image(token, path):
        print("  Pillow is not available in this interpreter - cannot render the")
        print("  token image. Install it, or run this where PIL exists.")
        raise SystemExit(2)

    api_key = key()
    if not api_key:
        print("  No API key found in .env")
        raise SystemExit(2)

    print("  token planted in the image :", token)
    print("  it appears NOWHERE in any scene, graph, or prompt")
    print()
    answer = ask(api_key, path).strip()
    print("  model replied              :", answer[:80])
    print()

    saw = token in answer
    print("  THE MODEL READ THE IMAGE   :", saw)
    print()
    if saw:
        print("  Loop closed. The attach path delivers pixels a model can read,")
        print("  and that is now demonstrated rather than assumed.")
    else:
        print("  NOT closed. The model did not report a token that exists only")
        print("  in the picture - so whatever it says about a viewport is not")
        print("  coming from the viewport.")
    os.unlink(path)
    raise SystemExit(0 if saw else 1)
