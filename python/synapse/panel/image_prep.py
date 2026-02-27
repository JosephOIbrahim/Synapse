"""
Synapse Image Preparation — resize and encode images for the Anthropic Vision API.

Loads images via Qt (QPixmap), scales to fit API limits, encodes as JPEG,
and returns a ready-to-send content block. Works inside Houdini (PySide6)
or standalone (PySide2/PySide6).

Usage:
    from synapse.panel.image_prep import prepare_image_block
    block = prepare_image_block("/path/to/screenshot.png")
    # block = {"type": "image", "source": {"type": "base64", ...}}
"""

import base64
import os

try:
    from PySide6 import QtCore, QtGui
except ImportError:
    from PySide2 import QtCore, QtGui


# Anthropic API constraints (as of 2025-06)
MAX_DIMENSION = 1568   # recommended max px on longest side
MAX_BYTES = 5 * 1024 * 1024  # 5MB base64 payload limit
QUALITY_LADDER = (85, 70, 50, 30)  # JPEG quality steps


def prepare_image_block(image_path):
    """Resize and encode an image file for the Anthropic Vision API.

    Returns:
        dict with keys:
            "block"      — Anthropic content block (type: image, source: base64)
            "media_type" — MIME type (always image/jpeg after encoding)
            "orig_bytes" — original file size in bytes
            "sent_bytes" — encoded payload size in bytes
            "dimensions" — (width, height) tuple after resize
            "resized"    — True if dimensions or size changed

    Raises:
        ValueError: if the image can't be decoded or compressed under 5MB.
    """
    if not os.path.isfile(image_path):
        raise ValueError("File not found: {}".format(image_path))

    orig_bytes = os.path.getsize(image_path)
    pixmap = QtGui.QPixmap(image_path)
    if pixmap.isNull():
        raise ValueError("Qt couldn't decode image: {}".format(image_path))

    # Scale down if longest side exceeds API max
    resized = False
    longest = max(pixmap.width(), pixmap.height())
    if longest > MAX_DIMENSION:
        if pixmap.width() >= pixmap.height():
            pixmap = pixmap.scaledToWidth(
                MAX_DIMENSION, QtCore.Qt.SmoothTransformation
            )
        else:
            pixmap = pixmap.scaledToHeight(
                MAX_DIMENSION, QtCore.Qt.SmoothTransformation
            )
        resized = True

    # Encode as JPEG, stepping down quality until under limit
    buf = QtCore.QBuffer()
    for quality in QUALITY_LADDER:
        buf.open(QtCore.QIODevice.WriteOnly)
        pixmap.save(buf, "JPEG", quality)
        buf.close()
        if buf.size() <= MAX_BYTES:
            break
        buf.setData(b"")

    sent_bytes = buf.size()
    if sent_bytes > MAX_BYTES:
        raise ValueError(
            "Image still {:.1f}MB after max compression (limit 5MB)".format(
                sent_bytes / 1024 / 1024
            )
        )

    img_data = base64.standard_b64encode(buf.data().data()).decode("ascii")

    return {
        "block": {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img_data,
            },
        },
        "media_type": "image/jpeg",
        "orig_bytes": orig_bytes,
        "sent_bytes": sent_bytes,
        "dimensions": (pixmap.width(), pixmap.height()),
        "resized": resized or sent_bytes < orig_bytes * 0.95,
    }
