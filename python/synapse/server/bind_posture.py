"""Listen-address posture for the in-Houdini hwebserver transport (SIDEFXCTO-1).

Houdini's ``hwebserver.run()`` binds the any-address (0.0.0.0) unless the
per-port ``ADDRESS`` setting says otherwise, so SYNAPSE's local mode used to be
reachable from the whole LAN while the docs promised localhost. This module
decides and enforces what SYNAPSE asks Houdini to bind:

* local mode (the default) -> ``127.0.0.1``.
* a non-loopback bind -> only as an explicit opt-in
  (``SYNAPSE_ALLOW_LAN=1`` or a ``SYNAPSE_DEPLOY_MODE`` of studio-lan /
  studio-vpn) AND only with an authentication key configured.
* a non-loopback bind with no key -> :class:`BindPostureError` naming the fix.

Pure stdlib, no ``hwebserver`` / ``hou`` import, so every rule is testable in
stock Python. ``hwebserver_settings()`` shapes the dict Houdini's
``hwebserver.run(settings=...)`` reads (``ADDRESS``, ``ALLOWED_HOSTS``, ``PORT``
-- see the H22 ``hwebserver.setSettingsForPort`` help).
"""

from __future__ import annotations

import ipaddress
import os
from typing import Dict, List, Mapping, Optional

__all__ = [
    "BindPostureError",
    "LOOPBACK_ADDRESS",
    "ANY_ADDRESS",
    "is_loopback_address",
    "resolve_listen_address",
    "enforce_bind_posture",
    "hwebserver_settings",
]

LOOPBACK_ADDRESS = "127.0.0.1"
ANY_ADDRESS = "0.0.0.0"

#: Studio modes are the documented LAN opt-in; local needs SYNAPSE_ALLOW_LAN.
STUDIO_MODES = frozenset({"studio-lan", "studio-vpn"})
_LAN_OPT_IN_VALUES = frozenset({"1", "true", "yes", "on"})

# Module-level constants so the DOC-1 env conformance scan
# (tests/test_m3_env_conformance.py, indirect-constant leg) sees the reads.
_DEPLOY_MODE_VAR = "SYNAPSE_DEPLOY_MODE"
_BIND_ADDRESS_VAR = "SYNAPSE_BIND_ADDRESS"
_ALLOW_LAN_VAR = "SYNAPSE_ALLOW_LAN"


class BindPostureError(RuntimeError):
    """A listen posture that would expose the endpoint without a key."""


def is_loopback_address(address: Optional[str]) -> bool:
    """True for 127.0.0.0/8, ::1 and the literal name ``localhost``.

    ``0.0.0.0`` and ``::`` are any-addresses, not loopback: they accept from
    every interface.
    """
    if not address:
        return False
    value = str(address).strip().lower()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _deploy_mode(environ: Mapping[str, str]) -> str:
    return (environ.get(_DEPLOY_MODE_VAR, "") or "local").strip().lower() or "local"


def _lan_opt_in(environ: Mapping[str, str]) -> bool:
    return (environ.get(_ALLOW_LAN_VAR, "") or "").strip().lower() in _LAN_OPT_IN_VALUES


def resolve_listen_address(
    mode: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> str:
    """Resolve the address the transport should bind.

    ``SYNAPSE_BIND_ADDRESS`` overrides the mode default. In local mode a
    non-loopback value is refused unless ``SYNAPSE_ALLOW_LAN`` opts in;
    studio modes are themselves the documented opt-in.
    """
    environ = os.environ if env is None else env
    effective_mode = (mode or _deploy_mode(environ)).strip().lower() or "local"
    requested = (environ.get(_BIND_ADDRESS_VAR, "") or "").strip()

    if not requested:
        return LOOPBACK_ADDRESS if effective_mode not in STUDIO_MODES else ANY_ADDRESS

    if (effective_mode not in STUDIO_MODES
            and not is_loopback_address(requested)
            and not _lan_opt_in(environ)):
        raise BindPostureError(
            "Refusing to listen on %s: this is local mode and a non-loopback "
            "bind is reachable from other machines. Keep %s (default), or opt "
            "in explicitly with SYNAPSE_ALLOW_LAN=1 (or SYNAPSE_DEPLOY_MODE="
            "studio-lan) and configure an API key." % (requested, LOOPBACK_ADDRESS)
        )
    return requested


def enforce_bind_posture(address: str, auth_key: Optional[str]) -> None:
    """Refuse a non-loopback listen when no authentication key exists.

    Loopback stays usable without a key (the documented single-seat posture);
    anything reachable from another host must be authenticated.
    """
    if is_loopback_address(address):
        return
    if auth_key:
        return
    raise BindPostureError(
        "Refusing to listen on %s: that address is reachable from other "
        "machines and no authentication key is configured. Mint "
        "~/.synapse/auth.key (a fresh Setup install does this) or set "
        "SYNAPSE_API_KEY, or keep the loopback bind (%s). To mint one by "
        "hand: python -c \"import secrets,pathlib; d=pathlib.Path.home()/"
        "'.synapse'; d.mkdir(parents=True, exist_ok=True); "
        "(d/'auth.key').write_text(secrets.token_urlsafe(32))\""
        % (address, LOOPBACK_ADDRESS)
    )


def _loopback_allowed_hosts(port: int) -> List[str]:
    """Host-header allowlist for a loopback bind.

    Both bare and ``host:port`` spellings are present so the list works
    whichever comparison the host header gets (Django-style hosts strip the
    port; a literal comparison does not).
    """
    hosts: List[str] = []
    for name in ("127.0.0.1", "localhost", "::1", "[::1]"):
        for candidate in (name, "%s:%d" % (name, port)):
            if candidate not in hosts:
                hosts.append(candidate)
    return hosts


def hwebserver_settings(address: str, port: int) -> Dict[str, object]:
    """The settings dict passed to ``hwebserver.run(settings=...)``.

    ``ADDRESS`` is Houdini's per-port bind setting (default 0.0.0.0).
    ``ALLOWED_HOSTS`` pins the Host header in local mode; a LAN bind keeps the
    permissive default because the allowed names are deployment-specific.
    """
    return {
        "PORT": int(port),
        "ADDRESS": address,
        "ALLOWED_HOSTS": (_loopback_allowed_hosts(int(port))
                          if is_loopback_address(address) else ["*"]),
    }
