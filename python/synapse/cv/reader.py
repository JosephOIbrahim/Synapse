"""The one place frames are read from disk and handed to OpenCV.

``read_linear_rgb`` returns float32 HxWx3 in R, G, B order, linear light.
``read_frame`` returns the same array with the file's data and display
windows, so positions found in the array can be put back in the frame.
``to_cv_bgr`` is the only conversion to OpenCV's B, G, R layout.

Linear means the file's own values. EXR and other float formats store linear
light and are returned untouched. Integer formats (8/16-bit PNG, TIFF, JPEG)
are refused with :class:`CVInputError` rather than guessed at, because their
encoding (sRGB or otherwise) is not reliably stated in the file. Render QC
reads Karma's float EXRs.
"""

from __future__ import annotations

import os

from synapse.cv.deps import CVInputError, require_numpy, require_oiio

_FLOAT_BASETYPES = ("half", "float", "double")


def _pick_rgb(channelnames):
    """Indices of the R, G, B channels by name.

    Bare ``R``/``G``/``B`` win. Otherwise a single layer whose ``.R``, ``.G``
    and ``.B`` are all present (``beauty.R`` ...). Anything else is not RGB.
    """
    names = list(channelnames)
    upper = [n.upper() for n in names]
    if all(c in upper for c in ("R", "G", "B")):
        return [upper.index(c) for c in ("R", "G", "B")]
    layers = {}
    for i, n in enumerate(upper):
        if "." in n:
            layer, _, chan = n.rpartition(".")
            if chan in ("R", "G", "B"):
                layers.setdefault(layer, {})[chan] = i
    full = [name for name, chans in layers.items() if len(chans) == 3]
    if len(full) == 1:
        chans = layers[full[0]]
        return [chans["R"], chans["G"], chans["B"]]
    if len(full) > 1:
        raise CVInputError(
            f"several RGB layers and no bare R/G/B: {sorted(full)}; pick one before analysing"
        )
    raise CVInputError(f"no R, G and B channels in {names}")


def read_linear_rgb(path):
    """Read ``path`` into a float32 HxWx3 array, R, G, B order, alpha dropped.

    The array covers the file's data window; :func:`read_frame` also returns
    where that window sits in the frame.

    Raises :class:`CVDependencyError` when OpenImageIO or numpy is missing,
    :class:`FileNotFoundError` for a missing file and :class:`CVInputError`
    for a file OpenImageIO cannot open, an integer format or no RGB channels.
    """
    return read_frame(path)[0]


def read_frame(path):
    """Read ``path`` as :func:`read_linear_rgb` does; return ``(pixels, window)``.

    ``pixels`` is the array covering the data window. ``window`` is a dict:
    ``x``, ``y``, ``width``, ``height`` (the data window, in the file's pixel
    coordinates), ``full_x``, ``full_y``, ``full_width``, ``full_height`` (the
    display window, the frame) and ``origin``: ``[x - full_x, y - full_y]``,
    the frame position of the array's pixel ``[0, 0]``. Array position
    ``(col, row)`` is frame position ``(col + origin[0], row + origin[1])``;
    pass ``origin`` to :func:`retina.firefly_scan.fireflies` to get frame
    positions. A frame cropped to its data window (Karma does this for an
    object on a transparent background) has a non-zero origin.

    Raises as :func:`read_linear_rgb` does.
    """
    np = require_numpy()
    oiio = require_oiio()
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise CVInputError(f"OpenImageIO cannot open {path}: {oiio.geterror()}")
    try:
        spec = inp.spec()
        basetype = str(spec.format).lower()
        if basetype not in _FLOAT_BASETYPES:
            raise CVInputError(
                f"{path} stores {basetype} pixels; only float formats (EXR, float TIFF) "
                f"are read as linear here"
            )
        idx = _pick_rgb(spec.channelnames)
        # The explicit (subimage, miplevel, chbegin, chend, format) form exists
        # in OpenImageIO 2.5 (Houdini 22's) and 3.x alike.
        pixels = inp.read_image(0, 0, 0, spec.nchannels, "float")
        if pixels is None:
            raise CVInputError(f"OpenImageIO failed reading {path}: {inp.geterror()}")
        height, width, nchannels = spec.height, spec.width, spec.nchannels
        window = {
            "x": int(spec.x),
            "y": int(spec.y),
            "width": int(width),
            "height": int(height),
            "full_x": int(spec.full_x),
            "full_y": int(spec.full_y),
            "full_width": int(spec.full_width),
            "full_height": int(spec.full_height),
            "origin": [int(spec.x - spec.full_x), int(spec.y - spec.full_y)],
        }
    finally:
        inp.close()
    pixels = np.asarray(pixels, dtype=np.float32).reshape(height, width, nchannels)
    return np.ascontiguousarray(pixels[:, :, idx], dtype=np.float32), window


def check_rgb(img):
    """Validate an HxWx3 array and return it as float32. Shared by the analyses."""
    np = require_numpy()
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise CVInputError(f"expected an HxWx3 RGB array, got shape {arr.shape}")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise CVInputError(f"empty image, shape {arr.shape}")
    return arr.astype(np.float32, copy=False)


def to_cv_bgr(img, dtype="float32"):
    """Convert R, G, B order to a contiguous OpenCV B, G, R array.

    ``dtype`` is ``"float32"`` (values kept as they are), ``"uint8"`` or
    ``"uint16"`` (NaN to 0, clipped to 0..1, scaled and rounded). No transfer
    function is applied: the integer forms are for masks and previews, not for
    analysis.
    """
    np = require_numpy()
    arr = check_rgb(img)
    bgr = arr[:, :, ::-1]
    if dtype == "float32":
        return np.ascontiguousarray(bgr, dtype=np.float32)
    if dtype in ("uint8", "uint16"):
        top = 255.0 if dtype == "uint8" else 65535.0
        scaled = np.rint(np.clip(np.nan_to_num(bgr, nan=0.0), 0.0, 1.0) * top)
        return np.ascontiguousarray(scaled.astype(dtype))
    raise CVInputError(f"dtype must be float32, uint8 or uint16, got {dtype!r}")
