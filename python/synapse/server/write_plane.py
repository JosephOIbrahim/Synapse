"""Write-plane state for ``get_health`` — is the product's WRITE half alive?

WHY THIS EXISTS
---------------
On 2026-08-02 ``memory_write`` was failing with ``PermissionError WinError 5``
(the store had resolved to an address under Houdini's ``bin/``) while
``get_health`` kept returning ``healthy: true``. A green light over a broken
product is the worst failure mode an agent tool can have: the entire (and, as
it turned out, misdiagnosed) filing in
``docs/tickets/P0_integrity_blocks_write_plane.md`` was assembled by
hand-probing 26 tools one at a time *precisely because health would not say*.
Kept verdict: ``docs/tickets/P0_VERIFICATION_claude-fable_2026-08-02.md``
§"What is genuinely real" — *"health says healthy while a write path is broken
— monitoring blind spot, valid. Surface write-plane state in synapse_health."*

CONTRACT
--------
``write_plane_state()`` returns a dict whose ``status`` is exactly one of:

``ok``
    Every resolved write target accepted (and released) a probe file, and the
    selected memory backend is the one serving.
``degraded``
    At least one target refused a write, or the memory backend silently fell
    back to jsonl (``memory.store.backend_fallback()`` is non-None). ``reason``
    names what and why.
``unknown``
    The check could not run. This is a legitimate value and it is NOT ``ok`` —
    a false ``ok`` is the exact bug this module exists to remove.

``degraded`` outranks ``unknown``: a demonstrated break is never downgraded to
"could not tell".

WHAT IT DOES NOT DO
-------------------
No scene mutation, no ``hou`` write, no real memory write, no network. Health
is called constantly, so the probe is two ``mkstemp`` + ``unlink`` pairs
against directories that already exist, and the ancestor walk is bounded by
``_MAX_ANCESTOR_WALK`` so no path can spin.

Measured warm cost 2.29 ms/call (20 calls, this worktree, 2026-08-02, Python
3.14 on Windows; producer: ``for _ in range(20): write_plane_state()`` timed
with ``time.perf_counter``). Read it against the transport it rides on — the
2026-08-01 review's ``ws_readonly_sweep.json`` measured ``synapse_health`` at
2.01 s round trip, so the probe is ~0.1% of the call it is attached to.

Per-process by construction, and that is the point: it answers "can THIS
process, with THIS scene address and THESE credentials, write", which is the
question a health call is actually being asked. The same directory can probe
writable from an elevated shell and refuse from the Houdini seat.

``os.access`` is deliberately NOT the verdict. On Windows it reports only the
read-only attribute and answers True for exactly the ACL-denied directory that
produced the WinError 5 above — it would have reported this bug as ``ok``.

THE READ-ONLY TENSION, STATED PLAINLY
-------------------------------------
``get_health`` is in ``handlers._READ_ONLY_COMMANDS`` (no audit record, no
Floor provenance, no C5 mutation lock), and this probe does perform a real
filesystem write. That is a deliberate, narrow exception and not the WP6/M1
case the doctor's header cites: the probe leaves **no durable artifact** (the
file is unlinked in the same call), touches no scene state, takes no lock, and
carries no show content — unlike a bundle zip, which persists and is therefore
an egress surface. The alternative, a non-writing check, cannot see the class
of failure this field exists to report. If a future rule bans all I/O from
read-only commands, the honest move is to reclassify ``get_health``, not to
downgrade the probe to one that answers ``ok`` while the product is broken.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "write_plane_state",
    "resolve_reports_base_dir",
    "resolve_memory_target_dir",
    "probe_dir_writable",
]

# Bounded so an absurd/unresolvable path can never spin the health call.
_MAX_ANCESTOR_WALK = 16

_PROBE_PREFIX = ".synapse_write_probe_"


# ---------------------------------------------------------------------------
# Target resolution — must mirror the REAL writers, or health lies politely
# ---------------------------------------------------------------------------

def resolve_reports_base_dir() -> str:
    """The base dir ``write_report`` confines its writes to.

    ``$SYNAPSE_REPORTS_DIR`` if set, else ``<repo root>/docs``. Resolved
    WITHOUT touching ``hou`` for the same reason the handler does it that way:
    a blocked main thread must not be able to stall it. This is the single
    definition — ``handlers._handle_write_report`` calls it too, so the dir
    health probes and the dir reports land in cannot drift apart.
    """
    base_dir = os.environ.get("SYNAPSE_REPORTS_DIR")
    if base_dir:
        return base_dir
    here = os.path.dirname(os.path.abspath(__file__))  # .../python/synapse/server
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(repo_root, "docs")


def resolve_memory_target_dir() -> Path:
    """The directory the scene-memory store writes into.

    The existing store dir when there is one, else the ``.synapse`` path that
    would be created next to the scene. Read-only: no migration copy, no
    ``mkdir`` — the resolution reuses ``doctor._resolve_store_dir`` /
    ``_resolve_store_base_dir`` rather than re-deriving the address, because a
    second copy of that logic is how the C-0 unsaved-scene bug survived (the
    doctor's old inline mirror inspected the wrong directory for every unsaved
    scene).
    """
    from .doctor import _resolve_store_base_dir, _resolve_store_dir

    existing = _resolve_store_dir()
    if existing is not None:
        return existing
    return _resolve_store_base_dir() / ".synapse"


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

def _nearest_existing_dir(path: Path) -> Optional[Path]:
    """The closest ancestor of *path* (or *path* itself) that is a directory.

    The store calls ``mkdir(parents=True)``, so the write that actually has to
    succeed happens in this directory. Bounded walk; None when nothing in the
    chain exists.
    """
    current = Path(path)
    for _ in range(_MAX_ANCESTOR_WALK):
        try:
            if current.is_dir():
                return current
        except OSError:
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent
    return None


def probe_dir_writable(path: Any) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Can we actually create a file in (the nearest existing ancestor of) *path*?

    Returns ``(writable, probed_path, detail)`` where ``writable`` is
    ``True`` (probe file created and removed), ``False`` (the OS refused — this
    is the WinError 5 case), or ``None`` (could not determine).
    """
    target = _nearest_existing_dir(Path(path))
    if target is None:
        return None, None, "no existing ancestor directory to probe"
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=_PROBE_PREFIX, dir=str(target))
    except OSError as exc:
        return False, str(target), f"{type(exc).__name__}: {exc}"
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    # Cleanup failure does not change the verdict — the write succeeded.
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    return True, str(target), None


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def _backend_fallback() -> Optional[Dict[str, Any]]:
    """PR #60's telemetry: non-None when the selected memory backend silently
    fell back to jsonl in this process. Read, never re-derived."""
    from ..memory import store as _store_mod

    return _store_mod.backend_fallback()


def write_plane_state() -> Dict[str, Any]:
    """Cheap, non-mutating verdict on whether SYNAPSE can still write.

    See the module docstring for the ``ok`` / ``degraded`` / ``unknown``
    contract. Never raises: an unexpected failure becomes ``unknown``.
    """
    targets: Dict[str, Any] = {}
    fallback: Optional[Dict[str, Any]] = None
    broken: list = []
    unclear: list = []

    try:
        try:
            fallback = _backend_fallback()
        except Exception as exc:  # noqa: BLE001 -- health must not raise
            fallback = None
            unclear.append(
                f"memory backend fallback state unreadable: {type(exc).__name__}: {exc}"
            )

        if fallback is not None:
            broken.append(
                "memory backend {!r} was selected but this process fell back to "
                "jsonl ({})".format(
                    fallback.get("requested"), fallback.get("reason"),
                )
            )

        for name, resolver in (
            ("memory", resolve_memory_target_dir),
            ("reports", resolve_reports_base_dir),
        ):
            target = resolver()
            writable, probed, detail = probe_dir_writable(target)
            targets[name] = {
                "path": str(target),
                "probed": probed,
                "writable": writable,
                "detail": detail,
            }
            if writable is False:
                broken.append(f"{name} dir not writable ({target}): {detail}")
            elif writable is None:
                unclear.append(f"{name} dir could not be probed ({target}): {detail}")
    except Exception as exc:  # noqa: BLE001 -- health must not raise
        return {
            "status": "unknown",
            "reason": f"write-plane check failed: {type(exc).__name__}: {exc}",
            "targets": targets,
            "backend_fallback": fallback,
        }

    if broken:
        status, reason = "degraded", "; ".join(broken)
    elif unclear:
        status, reason = "unknown", "; ".join(unclear)
    else:
        status, reason = "ok", None

    return {
        "status": status,
        "reason": reason,
        "targets": targets,
        "backend_fallback": fallback,
    }
