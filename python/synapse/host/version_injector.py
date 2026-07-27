"""Inject the running Houdini version into host-agnostic modules.

R99. `synapse.cognitive.tools.scout` selects its symbol table by running major:

    h{major}_symbol_table.json

It reads that major from `scout.EXPECTED_HOUDINI_VERSION`, whose docstring said
"mcp_server sets it when hou is importable". **Nothing in the codebase ever set
it.** So the major was always "", the isdigit() guard always failed, and every
session silently loaded `h21_symbol_table.json` while running 22.0.368 -
`h22_symbol_table.json` is 1.2 MB and had never been read once.

Why scout cannot just probe `hou` itself: `synapse.cognitive.*` is architecturally
host-agnostic and a test enforces ZERO hou imports there. The injection design was
therefore correct - only the injector was missing. This module is that injector,
and it lives in `synapse.host.*` where importing hou is permitted.

`synapse.core.wiring` and `synapse.core.lop_knowledge` never had this problem:
both resolve their per-major catalog through their own guarded
`_running_houdini_major()`, and both correctly load the _22 files today. Scout was
the outlier, not the rule.

Idempotent, never raises, safe to call from any host entry point.
"""
from __future__ import annotations

from typing import Optional

__all__ = ["inject_houdini_version", "current_injected_version"]


def _probe() -> Optional[str]:
    """`hou.applicationVersionString()` or None. Guarded local import on purpose:
    this module must not blow up a stock-python import chain."""
    try:
        import hou  # local + guarded (the doctor.py / wiring.py pattern)
        v = hou.applicationVersionString()
    except Exception:
        return None
    return v if isinstance(v, str) and v else None


def inject_houdini_version(force: bool = False) -> Optional[str]:
    """Set `scout.EXPECTED_HOUDINI_VERSION` from the live host.

    Returns the version injected, or None when no host is present (stock python,
    CI, a farm process) - in which case scout keeps its documented H21 fallback
    and a mismatched stamp still reads STALE rather than silent-valid.

    `force=False` will not overwrite a value someone set deliberately.
    """
    from synapse.cognitive.tools import scout  # local: keeps import order free

    if scout.EXPECTED_HOUDINI_VERSION and not force:
        return scout.EXPECTED_HOUDINI_VERSION

    v = _probe()
    if v:
        scout.EXPECTED_HOUDINI_VERSION = v
    return v


def current_injected_version() -> Optional[str]:
    """What scout currently believes it is running against. For synapse_doctor -
    a health check must read the value the PRODUCT reads (R108), not a stamp
    beside it."""
    try:
        from synapse.cognitive.tools import scout
        return scout.EXPECTED_HOUDINI_VERSION
    except Exception:
        return None
