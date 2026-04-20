"""API-key retrieval for the SYNAPSE agent daemon (Sprint 3 Spike 2 P1).

Two sources, checked in order:

  1. ``hou.secure.password('synapse_anthropic')`` — resolved against
     Houdini's native secret store (Windows Credential Manager under the
     hood). Production default. Zero external deps, OS-level encryption.
  2. ``ANTHROPIC_API_KEY`` env var — dev and CI fallback. Also used by
     ``spikes/spike_0.py`` so the same key works across modes.

Returns ``None`` if neither source provides a usable key; caller decides
whether to halt boot or continue in a degraded mode.

Label convention: ``synapse_anthropic`` is the canonical key name.
Setting it from a Houdini Python shell::

    hou.secure.setPassword('synapse_anthropic', 'sk-ant-...')

This label is shared with ``spike_0.py`` — do not rename without updating
both call sites and the deployment docs.
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


def _try_hou_secure() -> Optional[str]:
    """Fetch the API key from ``hou.secure.password``.

    Returns ``None`` if ``hou`` is unavailable (not running inside
    Houdini), if ``hou.secure`` is missing (older Houdini builds), or
    if no password is stored under ``CREDENTIAL_LABEL``. Any exception
    is downgraded to a debug log — boot continues via the env var path.
    """
    try:
        import hou  # type: ignore[import-not-found]
    except ImportError:
        return None

    secure = getattr(hou, "secure", None)
    if secure is None:
        logger.debug("hou.secure not present on this Houdini build")
        return None

    password_fn = getattr(secure, "password", None)
    if password_fn is None:
        logger.debug("hou.secure has no password() method")
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
