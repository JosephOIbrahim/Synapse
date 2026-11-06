"""Optional dependencies (numpy, OpenImageIO), imported fresh on every call.

No ``cv2`` here, by rule: ``python/synapse`` is a host surface and blueprint P5
(``tests/test_retina_boundary.py``) keeps OpenCV out of it entirely, lazy
imports included. Work that needs cv2 lives in the RETINA worker tree.

Each ``require_*`` runs a real ``import`` every time. Python's module cache
makes that cheap, and it means a test that sets ``sys.modules[name] = None``
sees the module as missing. A module that imports but is not the real package
(a ``MagicMock`` another test installed, a stub) is refused: its
``__version__`` must be a str.
"""

from __future__ import annotations

import importlib


class CVDependencyError(ImportError):
    """A package the analysis needs is missing, or what imported is not real."""

    def __init__(self, package: str, pip_name: str, detail: str = ""):
        self.package = package
        self.pip_name = pip_name
        msg = (
            f"synapse.cv needs '{package}' (pip install {pip_name}) and it is not "
            f"available in this Python"
        )
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class CVInputError(ValueError):
    """The image or file handed in cannot be analysed as RGB."""


def _require(package: str, pip_name: str):
    try:
        mod = importlib.import_module(package)
    except ImportError as exc:
        raise CVDependencyError(package, pip_name, f"{type(exc).__name__}: {exc}") from exc
    if mod is None or not isinstance(getattr(mod, "__version__", None), str):
        raise CVDependencyError(
            package,
            pip_name,
            f"the imported '{package}' has no str __version__, so it is not the real package",
        )
    return mod


def require_numpy():
    return _require("numpy", "numpy")


def require_oiio():
    return _require("OpenImageIO", "OpenImageIO")
