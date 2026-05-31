"""Import-guarded access to the Moneta memory engine (Mile 3).

Moneta ships as a separate package (repo: JosephOIbrahim/Moneta). It is NOT a
hard dependency of SYNAPSE: this module guards the import so SYNAPSE runs
unchanged when Moneta is absent (CI without the package, or environments that
haven't opted into the Moneta backend). When present, :func:`make_ephemeral`
builds a pxr-free, in-memory, ``MockUsdTarget``-backed handle -- the path CI
exercises with no OpenUSD requirement (harness AP9).

Package resolution order:
  1. ``import moneta`` (pip-installed, or already on ``sys.path``).
  2. If that fails and ``$MONETA_SRC`` points at a directory, insert it on
     ``sys.path`` and retry.

Packaging Moneta as a proper wheel is the long-term fix; until then the env
var is the seam (the production bridge / CI sets it). No user-specific path is
ever hard-coded here.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

_MONETA_AVAILABLE = False
_MONETA_IMPORT_ERROR: Optional[str] = None
Moneta = None
MonetaConfig = None


def _try_import() -> bool:
    """Attempt to bind ``Moneta``/``MonetaConfig``. Idempotent and cheap."""
    global _MONETA_AVAILABLE, _MONETA_IMPORT_ERROR, Moneta, MonetaConfig
    if _MONETA_AVAILABLE:
        return True
    try:
        from moneta import Moneta as _M, MonetaConfig as _C
        Moneta, MonetaConfig = _M, _C
        _MONETA_AVAILABLE = True
        _MONETA_IMPORT_ERROR = None
        return True
    except Exception as first_err:  # ImportError, or a transitive failure
        src = os.environ.get("MONETA_SRC")
        if src and os.path.isdir(src):
            if src not in sys.path:
                sys.path.insert(0, src)
            try:
                from moneta import Moneta as _M, MonetaConfig as _C
                Moneta, MonetaConfig = _M, _C
                _MONETA_AVAILABLE = True
                _MONETA_IMPORT_ERROR = None
                return True
            except Exception as second_err:
                _MONETA_IMPORT_ERROR = f"{type(second_err).__name__}: {second_err}"
                return False
        _MONETA_IMPORT_ERROR = f"{type(first_err).__name__}: {first_err}"
        return False


_try_import()


def moneta_available() -> bool:
    """True if the Moneta package can be imported (retries once)."""
    return _MONETA_AVAILABLE or _try_import()


def import_error() -> Optional[str]:
    """The last import failure string, or None if Moneta imported cleanly."""
    return _MONETA_IMPORT_ERROR


def make_ephemeral(embedding_dim: Optional[int] = None, **overrides: Any):
    """Construct an ephemeral, pxr-free Moneta handle (``MockUsdTarget``-backed).

    ``MonetaConfig.ephemeral()`` auto-generates a unique ``storage_uri`` and
    defaults ``use_real_usd=False`` (mock target) with no snapshot/WAL paths,
    so the handle is fully in-memory and needs no OpenUSD.

    The caller owns the handle lifetime -- use it as a context manager or call
    ``close()`` -- because Moneta enforces single-owner URI locking.
    """
    if not moneta_available():
        raise RuntimeError(
            "Moneta is not importable. Install the moneta package or set "
            f"$MONETA_SRC to its source directory. Last error: {import_error()}"
        )
    cfg_kwargs = dict(overrides)
    if embedding_dim is not None:
        cfg_kwargs["embedding_dim"] = embedding_dim
    return Moneta(MonetaConfig.ephemeral(**cfg_kwargs))
