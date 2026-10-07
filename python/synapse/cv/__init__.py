"""Render QC image analysis: pure functions, no ``hou``.

Phase 1 of ``docs/plans/OPENCV_RENDER_QC.md``. Entry points:

- :func:`read_linear_rgb` reads a frame on disk into float32 HxWx3 linear RGB
  through OpenImageIO. Channel order is fixed there and nowhere else.
- :func:`to_cv_bgr` is the one conversion to OpenCV's B, G, R layout (numpy
  only; the array is handed to cv2 on the far side of the boundary).
- :func:`exposure` reports luminance statistics and a suggested exposure offset.

**No cv2 in this package, ever.** ``python/synapse`` is a host surface and
blueprint P5 (``tests/test_retina_boundary.py``) keeps OpenCV out of it, lazy
imports included. The firefly detector needs cv2, so it lives in the RETINA
worker tree: :func:`retina.firefly_scan.fireflies`.

numpy and OpenImageIO are imported when a function needs them, never at
package import, so ``import synapse.cv`` works on a machine with neither.
A missing or fake dependency raises :class:`CVDependencyError`. Nothing here
returns a made-up result in its place.

Nothing in this package may run on Houdini's main thread. The tools that call
it (Phase 2) decide where it runs.
"""

from synapse.cv.deps import CVDependencyError, CVInputError
from synapse.cv.exposure_stats import REC709_WEIGHTS, exposure, luminance
from synapse.cv.reader import read_linear_rgb, to_cv_bgr

__all__ = [
    "CVDependencyError",
    "CVInputError",
    "REC709_WEIGHTS",
    "exposure",
    "luminance",
    "read_linear_rgb",
    "to_cv_bgr",
]
