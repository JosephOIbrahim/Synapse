"""Worker-side frame reader: one EXR part as linear R, G, B plus where it sits.

:func:`retina.firefly_scan.fireflies` takes a float HxWx3 R, G, B array and,
to report frame positions, the data window's ``origin``. ``retina.ingest``
returns every channel of a part and no origin; ``synapse.cv.read_frame``
returns both but lives host-side, which the worker venv does not carry. This
module is the worker's own reader (owner ruling QC-Q1): it mirrors
``python/synapse/cv/reader.py`` (origin = ``[x - full_x, y - full_y]``,
R, G, B picked by name) without importing ``synapse`` or ``cv2``.

The logic that needs no OpenImageIO is in plain functions so it is testable on
stock Python: :func:`origin_from_spec` and :func:`window_from_spec` read any
object with ImageSpec's window attributes, :func:`select_rgb` works on a list
of channel names, and :func:`pixels_to_rgb` turns a spec plus the part's raw
pixels into the RGB array (numpy only). :func:`read_frame` is the thin
OpenImageIO leg around them.

OpenImageIO and numpy are imported when a read is asked for, never at module
import, and must be the real packages (``__version__`` a str), the guard
``retina.firefly_scan`` and ``synapse.cv.deps`` use. A missing one raises
:class:`FrameReaderUnavailable`, a :class:`retina.t1.T1Unavailable`. Pixels
are returned as stored (linear for EXR), never colour-transformed. Integer
formats are refused, as ``synapse.cv`` refuses them, because their encoding is
not reliably stated in the file.

Zero ``hou``, zero ``cv2``, zero ``synapse``.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Dict, List, Sequence, Tuple

from .t1 import T1Unavailable

#: Names this reader in a fireflies() result and a check (``reader`` key).
READER_ID = "retina.frame_reader"

_FLOAT_BASETYPES = ("half", "float", "double")


class FrameReaderUnavailable(T1Unavailable):
    """OpenImageIO or numpy is missing, or what imported is not the real package."""


def _require(package: str, pip_name: str) -> Any:
    try:
        mod = importlib.import_module(package)
    except ImportError as exc:
        raise FrameReaderUnavailable(
            f"the frame reader needs '{package}' (pip install {pip_name} in the RETINA "
            f"venv, retina/requirements.txt): {type(exc).__name__}: {exc}"
        ) from exc
    if mod is None or not isinstance(getattr(mod, "__version__", None), str):
        raise FrameReaderUnavailable(
            f"'{package}' imported but has no str __version__, so it is not the real "
            f"package (pip install {pip_name} in the RETINA venv)"
        )
    return mod


def origin_from_spec(spec: Any) -> List[int]:
    """Frame position of the data window's pixel ``[0, 0]``: ``[x - full_x, y - full_y]``.

    ``spec`` is anything with ImageSpec's ``x``, ``y`` (data window) and
    ``full_x``, ``full_y`` (display window) attributes. Array position
    ``(col, row)`` is frame position ``(col + origin[0], row + origin[1])``.
    Negative when the data window starts before the frame (overscan).
    """
    return [int(spec.x) - int(spec.full_x), int(spec.y) - int(spec.full_y)]


def window_from_spec(spec: Any) -> Dict[str, Any]:
    """Data and display windows of ``spec`` plus :func:`origin_from_spec`, the
    dict shape ``synapse.cv.read_frame`` returns."""
    return {
        "x": int(spec.x),
        "y": int(spec.y),
        "width": int(spec.width),
        "height": int(spec.height),
        "full_x": int(spec.full_x),
        "full_y": int(spec.full_y),
        "full_width": int(spec.full_width),
        "full_height": int(spec.full_height),
        "origin": origin_from_spec(spec),
    }


def select_rgb(channelnames: Sequence[str]) -> Tuple[List[int], List[str], List[str]]:
    """Pick R, G, B by name; return ``(indices, used, dropped)``.

    Matching is case-insensitive, as in ``synapse.cv.reader._pick_rgb``. Bare
    ``R``/``G``/``B`` win. Otherwise exactly one layer whose ``.R``, ``.G`` and
    ``.B`` are all present (``C.R`` ...) is used. ``indices`` are in R, G, B
    order; ``used`` are the file's own names for them; ``dropped`` is every
    other channel, in file order (alpha, depth, other layers).

    Raises :class:`ValueError` naming the channels when there is no R, G, B,
    or when several layers carry one and no bare R/G/B decides between them.
    """
    names = [str(n) for n in channelnames]
    upper = [n.upper() for n in names]
    idx: List[int]
    if all(c in upper for c in ("R", "G", "B")):
        idx = [upper.index(c) for c in ("R", "G", "B")]
    else:
        layers: Dict[str, Dict[str, int]] = {}
        for i, n in enumerate(upper):
            if "." in n:
                layer, _, chan = n.rpartition(".")
                if chan in ("R", "G", "B"):
                    layers.setdefault(layer, {}).setdefault(chan, i)
        full = [name for name, chans in layers.items() if len(chans) == 3]
        if len(full) > 1:
            raise ValueError(
                f"several RGB layers and no bare R/G/B: {sorted(full)}; "
                f"pick one part or layer before analysing"
            )
        if not full:
            raise ValueError(f"no R, G and B channels in {names}; this part is not RGB")
        chans = layers[full[0]]
        idx = [chans["R"], chans["G"], chans["B"]]
    used = [names[i] for i in idx]
    dropped = [n for i, n in enumerate(names) if i not in idx]
    return idx, used, dropped


def _check_float_format(fmt: Any, where: str) -> None:
    basetype = str(fmt).lower()
    if basetype not in _FLOAT_BASETYPES:
        raise ValueError(
            f"{where} stores {basetype} pixels; only float formats (half, float, "
            f"double) are read as linear here"
        )


def pixels_to_rgb(spec: Any, pixels: Any, *, subimage: int = 0) -> Tuple[Any, Dict[str, Any]]:
    """Reduce one part's raw pixels to float32 HxWx3 R, G, B; return ``(rgb, info)``.

    ``pixels`` is the part's data window, any shape that reshapes to
    ``(spec.height, spec.width, spec.nchannels)`` (OIIO returns HxWxC, or HxW
    for one channel). ``info``: ``reader`` (:data:`READER_ID`, always: this
    function names itself as the reader even when the caller supplied
    ``pixels`` read by something else, so such a caller should overwrite
    ``info["reader"]`` before passing it on), ``subimage``,
    ``origin`` (:func:`origin_from_spec`), ``window``
    (:func:`window_from_spec`), ``channels`` (the names used, R, G, B order)
    and ``dropped`` (the rest). Raises :class:`ValueError` for an integer
    format or a part without RGB, :class:`FrameReaderUnavailable` without numpy.
    """
    _check_float_format(spec.format, f"subimage {subimage}")
    idx, used, dropped = select_rgb(spec.channelnames)
    np = _require("numpy", "numpy")
    height, width, nch = int(spec.height), int(spec.width), int(spec.nchannels)
    arr = np.asarray(pixels, dtype=np.float32).reshape(height, width, nch)
    rgb = np.ascontiguousarray(arr[:, :, idx], dtype=np.float32)
    info = {
        "reader": READER_ID,
        "subimage": int(subimage),
        "origin": origin_from_spec(spec),
        "window": window_from_spec(spec),
        "channels": used,
        "dropped": dropped,
    }
    return rgb, info


def read_frame(path: Any, *, subimage: int = 0) -> Tuple[Any, Dict[str, Any]]:
    """Read part ``subimage`` of ``path`` with OpenImageIO; see :func:`pixels_to_rgb`.

    Pass ``info["origin"]`` and ``info["reader"]`` to
    :func:`retina.firefly_scan.fireflies` to get frame positions and a named
    reader in its result.

    Raises :class:`FileNotFoundError` for a missing file,
    :class:`FrameReaderUnavailable` without OpenImageIO or numpy,
    :class:`ValueError` when OIIO cannot open or read the file, the part does
    not exist, its pixels are integers or it has no R, G, B.
    """
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    oiio = _require("OpenImageIO", "OpenImageIO")
    _require("numpy", "numpy")
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise ValueError(f"OpenImageIO cannot open {path}: {oiio.geterror()}")
    try:
        if subimage != 0 and not inp.seek_subimage(subimage, 0):
            raise ValueError(f"{path}: no subimage {subimage} ({inp.geterror()})")
        spec = inp.spec()
        # Refuse before reading pixels: a part without RGB or with integer
        # pixels is not worth decoding.
        _check_float_format(spec.format, f"{path} subimage {subimage}")
        select_rgb(spec.channelnames)
        # The explicit (subimage, miplevel, chbegin, chend, format) form exists
        # in OpenImageIO 2.5 (Houdini 22's) and 3.x alike (synapse.cv.reader).
        pixels = inp.read_image(subimage, 0, 0, int(spec.nchannels), "float")
        if pixels is None:
            raise ValueError(f"OpenImageIO failed reading {path}: {inp.geterror()}")
        return pixels_to_rgb(spec, pixels, subimage=subimage)
    finally:
        inp.close()


__all__ = [
    "READER_ID",
    "FrameReaderUnavailable",
    "origin_from_spec",
    "window_from_spec",
    "select_rgb",
    "pixels_to_rgb",
    "read_frame",
]
