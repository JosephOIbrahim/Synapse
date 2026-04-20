"""API-key retrieval for the SYNAPSE agent daemon.

Sources, checked in order:

  1. ``hou.secure.password('synapse_anthropic')`` — **optional, forward-
     compatible path.** Confirmed **not** present in Houdini 21.0.671
     (baseline Spike 2.3 finding: only ``secureSelectionOption`` in
     ``dir(hou)`` matches ``secure``). Retained so that when SideFX
     ships a secure-credentials API in a future Houdini release, SYNAPSE
     picks it up without code changes.
  2. ``ANTHROPIC_API_KEY`` env var — **current production path.** Used
     by ``spikes/spike_0.py`` and the Sprint 2+ daemon.

Returns ``None`` if neither source provides a usable key; caller decides
whether to halt boot or continue in a degraded mode.

One-shot INFO log at import time announces which path is live on this
Houdini build so operators see the fallback decision in the logs
without having to read the source.

Label convention: ``synapse_anthropic`` is the canonical key name
(shared with ``spikes/spike_0.py`` and the runbook). Rename only in
lockstep across all three call sites and the deployment docs.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

CREDENTIAL_LABEL: str = "synapse_anthropic"
"""Canonical ``hou.secure`` label for the Anthropic API key.

Shared with ``spikes/spike_0.py``. Rename only in lockstep with the
Spike 0 bootstrap script and any deployment / onboarding docs."""

ENV_VAR: str = "ANTHROPIC_API_KEY"
"""Fallback env var name. Matches the Anthropic SDK's default."""


# ---------------------------------------------------------------------------
# One-shot availability detection at import time (Spike 2.3).
# ---------------------------------------------------------------------------
# Confirmed empirically in Houdini 21.0.671: ``hou.secure`` is absent.
# This block logs that observation ONCE at import so operators see
# which credential path is live without spelunking through source.
# The runtime ``_try_hou_secure`` still probes dynamically — that
# preserves forward compatibility for future Houdini releases and
# honours test-level mocks of ``hou.secure``.
try:
    import hou as _hou_probe  # type: ignore[import-not-found]
except ImportError:
    logger.debug("hou unavailable — auth module running outside Houdini")
else:
    _secure_attrs = [n for n in dir(_hou_probe) if "secure" in n.lower()]
    if "secure" in _secure_attrs and hasattr(
        getattr(_hou_probe, "secure"), "password"
    ):
        logger.debug(
            "hou.secure.password available — credential store path live"
        )
    else:
        logger.info(
            "hou.secure not available in this Houdini build "
            "(attrs matching 'secure': %s). Falling back to %s env var.",
            _secure_attrs,
            ENV_VAR,
        )
    del _hou_probe, _secure_attrs


def _try_hou_secure() -> Optional[str]:
    """Fetch the API key from ``hou.secure.password`` — if available.

    Forward-compatible probe. Returns ``None`` on any of:
      - ``hou`` is unimportable (not running inside Houdini).
      - ``hou.secure`` is absent (empirically true in 21.0.671).
      - ``hou.secure.password`` is absent (older Houdini builds).
      - ``hou.secure.password(CREDENTIAL_LABEL)`` raises (any exception).
      - Returned value is empty / whitespace.

    Never raises. Caller routes to the env-var path on ``None``.
    """
    try:
        import hou  # type: ignore[import-not-found]
    except ImportError:
        return None

    secure = getattr(hou, "secure", None)
    if secure is None:
        # Logged once at module import — don't spam on every call.
        return None

    password_fn = getattr(secure, "password", None)
    if password_fn is None:
        return None

    try:
        value = password_fn(CREDENTIAL_LABEL)
    except Exception as exc:  # noqa: BLE001 — Houdini can raise anything
        logger.debug("hou.secure.password(%r) raised: %s", CREDENTIAL_LABEL, exc)
        return None

    if value:
        return str(value).strip() or None
    return None


def _try_env_var() -> Optional[str]:
    """Fetch the API key from the ANTHROPIC_API_KEY env var."""
    value = os.environ.get(ENV_VAR, "").strip()
    return value or None


def get_anthropic_api_key() -> Optional[str]:
    """Resolve the Anthropic API key, preferring ``hou.secure`` over env.

    Returns:
        The API key string on success, or ``None`` if no source
        produced one. Callers MUST handle ``None`` explicitly —
        this function never raises and never guesses.
    """
    key = _try_hou_secure()
    if key:
        logger.info("Anthropic API key loaded from hou.secure")
        return key

    key = _try_env_var()
    if key:
        logger.info("Anthropic API key loaded from %s env var", ENV_VAR)
        return key

    logger.warning(
        "No Anthropic API key found in hou.secure (%r) or env var %s",
        CREDENTIAL_LABEL,
        ENV_VAR,
    )
    return None
