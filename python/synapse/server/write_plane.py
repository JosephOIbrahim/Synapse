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
    back to jsonl (``memory.store.backend_fallback()`` is non-None), or the
    LIVE store itself is degraded — the serving store class is jsonl while
    moneta/shadow was selected, ``store.count()`` cannot enumerate it, or a
    Moneta store has no durability layer (``store_health()``, W3-HARDEN target
    3). ``reason`` names what and why; the ``store`` field carries the evidence.
``unknown``
    The check could not run. This is a legitimate value and it is NOT ``ok`` —
    a false ``ok`` is the exact bug this module exists to remove.

``degraded`` outranks ``unknown``: a demonstrated break is never downgraded to
"could not tell".

WHAT IT DOES NOT DO
-------------------
No scene mutation, no ``hou`` write, no real memory write, no network. Health
is called constantly, so the probe is two ``O_CREAT|O_EXCL`` create + unlink
pairs against directories that already exist, and the ancestor walk is bounded
by ``_MAX_ANCESTOR_WALK`` so no path can spin.

``tempfile.mkstemp`` is deliberately NOT the probe primitive. Its internal
retry loop trusts ``os.access(dir, W_OK)`` — the exact Windows lie documented
below — and retries ``PermissionError`` up to ``TMP_MAX`` (2**31-1) times on an
ACL-denied directory: measured ~13.7k refusals/s ≈ 43 HOURS per call, on the
transport's event loop, pre-RBAC and un-rate-limited (G1b crucible,
2026-08-02). One non-retrying ``os.open`` surfaces the real ``WinError``
immediately. ``tests/test_write_plane_health.py`` pins both the primitive and
the wall-clock bound against a real ACL-denied directory.

``hou`` READS are marshalled: ``resolve_memory_target_dir`` reaches
``hou.hipFile.path()`` through the doctor's resolvers, so off the main thread
it routes through ``run_on_main`` with a short timeout (the marshal-deadlock
class: never call ``hou`` off-main, never blocking-marshal FROM main). A
failed or timed-out marshal surfaces as ``unknown`` with the reason — never a
silently wrong address.

The probe file lands in the probed directory itself (for reports that is the
git-tracked ``docs/``). If the process dies inside the create→unlink window a
``.synapse_write_probe_*`` file can persist; accepted narrow risk, fenced by a
``.gitignore`` entry for the prefix so it can never become a tracked artifact.

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
import threading
import uuid
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


# Off-main marshal budget for the hou-touching resolution. Health must stay
# bounded: a busy main thread turns into 'unknown(reason)' after this many
# seconds, never into an open-ended wait.
_RESOLVE_TIMEOUT_S = 2.0


def _resolve_via_doctor() -> Path:
    from .doctor import _resolve_store_base_dir, _resolve_store_dir

    existing = _resolve_store_dir()
    if existing is not None:
        return existing
    return _resolve_store_base_dir() / ".synapse"


def resolve_memory_target_dir() -> Path:
    """The directory the scene-memory store writes into.

    The existing store dir when there is one, else the ``.synapse`` path that
    would be created next to the scene. Read-only: no migration copy, no
    ``mkdir`` — the resolution reuses ``doctor._resolve_store_dir`` /
    ``_resolve_store_base_dir`` rather than re-deriving the address, because a
    second copy of that logic is how the C-0 unsaved-scene bug survived (the
    doctor's old inline mirror inspected the wrong directory for every unsaved
    scene).

    THREAD CONTRACT (G1b crucible): the doctor resolvers read
    ``hou.hipFile.path()``. On the main thread (hwebserver transport) that is
    a direct call. Off the main thread with a LIVE ``hou`` (websockets
    transport handler thread) it is marshalled via ``run_on_main`` with a
    short timeout — the same discipline every other hou-reading handler
    follows. Headless (no ``hou`` in the process) there is nothing to marshal;
    the resolvers' own no-hou fallback runs wherever we are. Failures
    propagate to the caller, which records ``unknown`` with the reason.
    """
    on_main = threading.current_thread() is threading.main_thread()
    # sys.modules check, not an import attempt: inside Houdini the host has
    # already imported hou; headless it is absent and the resolvers fall back
    # without touching it, so a marshal would be pure overhead (and hdefereval
    # is unimportable headless anyway).
    import sys as _sys
    hou_live = "hou" in _sys.modules and _sys.modules["hou"] is not None

    if on_main or not hou_live:
        return _resolve_via_doctor()

    from .main_thread import run_on_main

    return run_on_main(_resolve_via_doctor, timeout=_RESOLVE_TIMEOUT_S,
                       label="write_plane.resolve_memory_target_dir")


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


def _probe_open(tmp_path: str) -> int:
    """The probe primitive: ONE non-retrying exclusive create.

    Split out as the injection seam for the classification tests (they patch
    this, not the OS) and as the single place the no-mkstemp rule is visible.
    """
    return os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)


def probe_dir_writable(path: Any) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Can we actually create a file in (the nearest existing ancestor of) *path*?

    Returns ``(writable, probed_path, detail)`` where ``writable`` is
    ``True`` (probe file created and removed), ``False`` (the OS refused — this
    is the WinError 5 case), or ``None`` (could not determine).

    The primitive is one NON-RETRYING ``os.open(O_CREAT|O_EXCL|O_WRONLY)``.
    Never ``tempfile.mkstemp``: its retry loop trusts ``os.access(W_OK)``,
    which answers True on a Windows ACL-denied directory, so it spins
    ``PermissionError`` for up to ``TMP_MAX`` (2**31-1) iterations — measured
    ~43 hours — on exactly the condition this probe exists to report in
    milliseconds (G1b crucible, 2026-08-02). A uuid filename makes collision
    effectively impossible; two bounded attempts are kept purely so a
    same-nanosecond crash leftover cannot flip the verdict.
    """
    target = _nearest_existing_dir(Path(path))
    if target is None:
        return None, None, "no existing ancestor directory to probe"
    last_exists: Optional[str] = None
    for _ in range(2):
        tmp_path = os.path.join(
            str(target), f"{_PROBE_PREFIX}{os.getpid()}_{uuid.uuid4().hex}")
        try:
            fd = _probe_open(tmp_path)
        except FileExistsError as exc:
            last_exists = f"{type(exc).__name__}: {exc}"
            continue  # bounded: one more unique name, then give up honestly
        except OSError as exc:
            # The real refusal, immediately, with the real winerror.
            return False, str(target), f"{type(exc).__name__}: {exc}"
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
    return None, str(target), (
        f"probe name collided twice (uuid) — not a permission verdict: "
        f"{last_exists}")


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def _backend_fallback() -> Optional[Dict[str, Any]]:
    """PR #60's telemetry: non-None when the selected memory backend silently
    fell back to jsonl in this process. Read, never re-derived."""
    from ..memory import store as _store_mod

    return _store_mod.backend_fallback()


# ---------------------------------------------------------------------------
# Store-level evidence (W3-HARDEN target 3) — write_plane for the STORE
# ---------------------------------------------------------------------------
#
# The dir + fallback-flag checks above answer "is the write TARGET reachable".
# They do NOT answer "is the store that is ACTUALLY serving the one the operator
# asked for, and can it still enumerate + persist". A degraded store behind a
# healthy bridge is the exact blind spot the spec's Phase-6 telemetry item
# closes (docs/SYNAPSE-memory-engineering-spec.md §8): *"doctor reports
# write_plane for the STORE, not just the bridge"*. The signals below are read
# from the LIVE store OBJECT, so they survive a fallback flag that lied or was
# reset — ``store._make_store`` resets ``_BACKEND_FALLBACK`` on every
# construction, so a later successful reconstruction can blank a real earlier
# fallback, but the serving CLASS cannot be reset out from under the truth.

# The jsonl store class name (``store.MemoryStore``) and the Moneta adapter's
# (``moneta_store.MonetaBackedStore``). Matched by name, not import, so this
# module never drags the memory package's optional deps into a health call.
_JSONL_STORE_CLASSES = {"MemoryStore"}
_MONETA_STORE_CLASSES = {"MonetaBackedStore"}


def _live_store() -> Any:
    """The backend store object ALREADY instantiated in this process, or None.

    Read-only by construction: it reads ``store._global_synapse`` directly and
    NEVER calls ``get_synapse_memory()`` — instantiating a store from inside a
    health probe would be a mutation (it materializes ``.synapse`` on disk). A
    process with no store loaded returns None, which the caller records as
    ``evaluated=False`` — "no store loaded" is not a degradation.
    """
    try:
        from ..memory import store as _store_mod
        sm = getattr(_store_mod, "_global_synapse", None)
        if sm is None:
            return None
        return getattr(sm, "store", None)
    except Exception:  # noqa: BLE001 -- health must not raise
        return None


def store_health() -> Dict[str, Any]:
    """Non-mutating, store-level write evidence read from the live store object.

    Returns ``evaluated=False`` (contributes NOTHING to the verdict) when no
    store has been instantiated in this process. Otherwise ``status`` is
    ``ok`` / ``degraded`` / ``unknown`` derived from three store-scoped facts:

    1. **Serving identity** — the live store's CLASS vs the requested backend.
       A jsonl ``MemoryStore`` serving while ``moneta``/``shadow`` was selected
       is a degradation even if ``backend_fallback()`` is None (the flag is
       reset per construction; the class is not).
    2. **Enumeration reachability** — ``store.count()`` must not raise. A store
       that cannot be read is degraded regardless of directory writability.
    3. **Durable persistence** (Moneta only) — a Moneta handle with
       ``durability=None`` keeps deposits in RAM; a restart loses them. That is
       a degraded WRITE plane even when the directory probes writable.

    Never raises; never constructs a store.
    """
    store = _live_store()
    if store is None:
        return {"evaluated": False,
                "reason": "no memory store instantiated in this process"}

    info: Dict[str, Any] = {"evaluated": True}
    broken: list = []
    unclear: list = []
    requested = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").strip().lower()
    cls = type(store).__name__
    info["requested_backend"] = requested
    info["serving_class"] = cls

    # (1) Serving-backend identity from the live OBJECT, not the fallback flag.
    serving_jsonl = cls in _JSONL_STORE_CLASSES
    info["serving_jsonl"] = serving_jsonl
    if requested in ("moneta", "shadow") and serving_jsonl:
        broken.append(
            f"backend {requested!r} was selected but a jsonl {cls} is the live "
            f"store — the selected substrate is not the one serving")

    # (2) Enumeration reachability.
    try:
        info["count"] = int(store.count())
    except Exception as exc:  # noqa: BLE001
        info["count"] = None
        broken.append(
            f"store.count() raised ({type(exc).__name__}: {exc}) — the live "
            f"store cannot be enumerated")

    # (3) Moneta-specific durable persistence layer.
    if cls in _MONETA_STORE_CLASSES:
        handle = getattr(store, "_handle", None)
        durability = getattr(handle, "durability", None) if handle is not None else None
        info["durable"] = durability is not None
        if handle is None:
            # A Moneta-classed store with no engine handle cannot persist OR
            # read — it is degraded, not merely non-durable. (The live adapter
            # always sets _handle in __init__, so this is a latent-safety guard,
            # not a live path; the crucible flagged the earlier guard's blind
            # spot when handle was None, W3-HARDEN adversarial P3-b.)
            broken.append(
                "moneta store has no engine handle — it can neither persist "
                "nor read")
        elif durability is None:
            broken.append(
                "moneta store has no durability layer — deposits are RAM-only "
                "and will not survive a restart")

    if broken:
        info["status"], info["reason"] = "degraded", "; ".join(broken)
    elif unclear:
        info["status"], info["reason"] = "unknown", "; ".join(unclear)
    else:
        info["status"], info["reason"] = "ok", None
    return info


def write_plane_state() -> Dict[str, Any]:
    """Cheap, non-mutating verdict on whether SYNAPSE can still write.

    See the module docstring for the ``ok`` / ``degraded`` / ``unknown``
    contract. Never raises: an unexpected failure becomes ``unknown``.
    """
    targets: Dict[str, Any] = {}
    fallback: Optional[Dict[str, Any]] = None
    store_info: Optional[Dict[str, Any]] = None
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
            try:
                target = resolver()
            except Exception as exc:  # noqa: BLE001 -- e.g. busy-main marshal timeout
                targets[name] = {"path": None, "probed": None,
                                 "writable": None,
                                 "detail": f"{type(exc).__name__}: {exc}"}
                unclear.append(
                    f"{name} target unresolvable: {type(exc).__name__}: {exc}")
                continue
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

        # Store-level evidence (target 3): fold a live-store degradation into the
        # SAME verdict lists. store_health() is self-fenced and never raises, but
        # it stays inside the outer try so any unexpected escape still lands as
        # 'unknown', never a false 'ok'. A process with no live store contributes
        # nothing (evaluated=False) — preserving the existing dir-only verdict.
        store_info = store_health()
        if store_info.get("evaluated"):
            s_status = store_info.get("status")
            if s_status == "degraded":
                broken.append(f"store degraded: {store_info.get('reason')}")
            elif s_status == "unknown":
                unclear.append(f"store health unclear: {store_info.get('reason')}")
    except Exception as exc:  # noqa: BLE001 -- health must not raise
        return {
            "status": "unknown",
            "reason": f"write-plane check failed: {type(exc).__name__}: {exc}",
            "targets": targets,
            "backend_fallback": fallback,
            "store": store_info,
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
        "store": store_info,
    }
