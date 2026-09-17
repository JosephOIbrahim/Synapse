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
    3), or the store ITSELF reports that it is refusing writes (B6 -- the
    authoritative check, added after a store refused every write for two days
    while the other three read green; a store that cannot answer reads
    ``unknown``, never ``ok``). ``reason`` names what and why; the ``store``
    field carries the evidence.
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
    "read_store_write_health",
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


# ---------------------------------------------------------------------------
# B6 — the store's OWN write-health verdict (the 2026-09-15 blind spot)
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS, MEASURED
# -------------------------
# Between 2026-09-15 15:09 and 2026-09-17 15:53 a MemoryStore sat DEGRADED and
# refused EVERY write for ~2 days, and every health surface in this repo kept
# reporting ok. One bad line did it: ``MemoryStore.add`` appended a second JSONL
# line for an id that already existed with different content; ``_load``
# (store.py:355-362) raises "conflicting duplicate memory identity" on the second
# differing canonical, and store.py:396-401 degrades the WHOLE store on a
# non-empty unreadable list. Thereafter ``_require_writable_load`` refused every
# write. The only trace was a log line nobody reads.
#
# ``store_health()``'s three existing checks were ALL TRUE throughout:
#   1. the serving class matched the requested backend,
#   2. ``store.count()`` did not raise -- and worse, it returned a NORMAL number,
#      because ``_load`` keeps the FIRST occurrence of a duplicated id and only
#      the second raises, so the record count is not evidence of health,
#   3. durability was not None.
# Three green facts about a store that had not accepted a write in two days.
#
# The missing fact was never derivable from outside the store: only the store
# knows it degraded its own load. Lane B3 makes it askable -- ``is_degraded`` /
# ``degraded_reason`` / ``health()`` on ``MemoryStore`` -- and this reader is the
# consumer. It is the AUTHORITATIVE signal of the four: a store that says it is
# refusing writes is degraded no matter how healthy its class, count and
# durability look.
#
# WHERE THE CONTRACT ACTUALLY LIVES (why we do not just ask the serving object)
# ----------------------------------------------------------------------------
# The pinned contract puts ``health()`` on ``MemoryStore`` -- the jsonl class.
# But the store SERVING this process is usually not a bare ``MemoryStore``:
#
#   ``MonetaBackedStore._jsonl_net`` -- the JSONL dual-write safety net, built
#       whenever ``SYNAPSE_MEMORY_BACKEND == "moneta"`` (moneta_store.py:348-357).
#       THIS is the object that died in the incident: Moneta is the primary, and
#       a mirror refusing every write is exactly the failure that leaves no mark
#       on a Moneta-shaped health surface.
#   ``ShadowMemoryStore.primary`` / ``.shadow`` -- shadow mode wraps two stores
#       and serves the primary.
#
# So "is memory accepting writes" is asked of the serving object AND of the
# contract-bearing stores it wraps. Asking only the facade would have reported
# this incident as healthy a second time.
_HEALTH_CONTRACT_MEMBERS = ("_jsonl_net", "primary", "shadow")


def _health_contract_candidates(store: Any) -> list:
    """The objects that can answer "are you accepting writes", nearest first.

    The serving object itself, then the known contract-bearing stores it wraps
    (see ``_HEALTH_CONTRACT_MEMBERS``). One level deep only and over a FIXED
    name list -- no recursion, no ``__dict__`` walk. A health read must stay
    O(1) and must not be able to spin on a cyclic wrapper.

    Duplicates are collapsed by identity, so a facade exposing the same inner
    store under two names is asked once.
    """
    out: list = []
    seen_ids: set = set()

    def _offer(label: str, obj: Any) -> None:
        if obj is None or id(obj) in seen_ids:
            return
        seen_ids.add(id(obj))
        out.append((label, obj))

    _offer(type(store).__name__, store)
    for member in _HEALTH_CONTRACT_MEMBERS:
        try:
            inner = getattr(store, member, None)
        except Exception:  # noqa: BLE001 -- a property that raises is not an answer
            continue
        if inner is not None:
            _offer("%s.%s" % (type(store).__name__, member), inner)
    return out


def _ask_one_store_health(label: str, obj: Any) -> Dict[str, Any]:
    """Ask ONE object for its write-health. Never raises.

    ``answered`` is the load-bearing field, and it is why this returns a dict
    rather than a bool: "this store says it is healthy" and "this object could
    not tell us" are different answers, and collapsing them into one green is
    the exact failure that produced the two-day outage. An object with no
    ``health()`` returns ``answered=False``, which the caller must resolve to
    UNKNOWN -- never to ok.
    """
    health = getattr(obj, "health", None)
    if not callable(health):
        return {"answered": False, "detail":
                "%s exposes no health() -- the store write-health contract "
                "(is_degraded / degraded_reason / health) is absent on this "
                "object, so its write state is unknown, not healthy" % label}
    try:
        reading = health()
    except Exception as exc:  # noqa: BLE001 -- a health read must never raise
        return {"answered": False, "detail":
                "%s.health() raised (%s: %s)" % (label, type(exc).__name__, exc)}
    if not isinstance(reading, dict):
        return {"answered": False, "detail":
                "%s.health() returned %s, not the contracted dict"
                % (label, type(reading).__name__)}

    row: Dict[str, Any] = {"answered": True}
    for key in ("degraded", "reason", "writable", "records", "rejected_writes"):
        row[key] = reading.get(key)

    degraded = row.get("degraded")
    writable = row.get("writable")
    # A malformed answer is not an ok. The contract promises all five keys; when
    # the two verdict-bearing ones are not the booleans it promises we hold a
    # reading we cannot interpret, and an uninterpretable reading is UNKNOWN.
    if not isinstance(degraded, bool) or not isinstance(writable, bool):
        row["answered"] = False
        row["detail"] = (
            "%s.health() did not return bool degraded/writable "
            "(degraded=%r, writable=%r)" % (label, degraded, writable))
        return row

    row["sick"] = bool(degraded) or not writable
    return row


def read_store_write_health(store: Any) -> Dict[str, Any]:
    """Is this store accepting writes? The one honest answer, for all surfaces.

    Consumed by ``store_health()`` below and by
    ``handlers_memory._handle_memory_status``. The panel health strip asks the
    same question through its own cheaper path -- see
    ``health_strip._gather_memory`` for why it deliberately does not import this
    module.

    Returns::

        {"status": "ok" | "degraded" | "unknown",
         "accepting_writes": True | False | None,   # None == could not tell
         "reason": "<operator sentence>",           # "" only when status is ok
         "rejected_writes": <int|None>,             # refused writes, if counted
         "sources": {<label>: <per-object row>}}    # the evidence, always

    RESOLUTION ORDER, and it is deliberate:

    1. ANY candidate reporting sick -> ``degraded``. A dead safety net is a dead
       safety net even when the primary in front of it is fine -- that is the
       incident, exactly.
    2. else NO candidate answered -> ``unknown``. "We could not determine
       health" and "healthy" are different answers; collapsing them is what let
       a store refuse writes for two days behind a green light.
    3. else -> ``ok``, and it is a real ok: at least one contract-bearing store
       affirmatively said it is accepting writes.

    ``rejected_writes`` is REPORTED but does not by itself set the verdict. It
    is a lifetime counter, and when it is non-zero the cause is already carried
    by ``degraded``/``writable`` on the same reading -- promoting it to a
    verdict would add no new information while making the verdict unclearable
    short of a restart. It is surfaced because "N writes were refused" is the
    number an artist needs in order to know what to re-enter.

    Never raises; never constructs a store; never writes.
    """
    sources: Dict[str, Any] = {}
    sick: list = []
    silent: list = []
    healthy: list = []
    rejected_total: Optional[int] = None

    if store is None:
        return {"status": "unknown", "accepting_writes": None,
                "reason": "no memory store is loaded in this process, so "
                          "whether memory would accept a write is unknown",
                "rejected_writes": None, "sources": sources}

    try:
        candidates = _health_contract_candidates(store)
    except Exception as exc:  # noqa: BLE001 -- a health read must never raise
        return {"status": "unknown", "accepting_writes": None,
                "reason": "could not inspect the live store (%s: %s), so memory "
                          "write state is unknown" % (type(exc).__name__, exc),
                "rejected_writes": None, "sources": sources}

    for label, obj in candidates:
        row = _ask_one_store_health(label, obj)
        sources[label] = row
        if not row.get("answered"):
            silent.append(row.get("detail") or ("%s did not answer" % label))
            continue
        count = row.get("rejected_writes")
        # NEGATIVE IS A SENTINEL, NOT A COUNT. ``MemoryStore.health()``
        # fail-closes with ``rejected_writes: -1`` when its own probe could not
        # complete (store.py's "health probe did not complete" defaults). Adding
        # that to a total would render "-1 write(s) have been refused" — a
        # fabricated number in the one sentence the artist is meant to act on.
        # An uncounted rejection stays uncounted; the store is still reported
        # sick by ``degraded``/``writable`` on the same fail-closed reading.
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            rejected_total = (rejected_total or 0) + count
        if row.get("sick"):
            sick.append("%s is not accepting writes: %s"
                        % (label, row.get("reason") or "no reason given"))
        else:
            healthy.append(label)

    if sick:
        reason = "memory is not accepting writes -- " + "; ".join(sick)
        if rejected_total and rejected_total > 0:
            reason += (" (%d write(s) have been refused and were NOT saved)"
                       % rejected_total)
        return {"status": "degraded", "accepting_writes": False,
                "reason": reason, "rejected_writes": rejected_total,
                "sources": sources}

    if not healthy:
        return {"status": "unknown", "accepting_writes": None,
                "reason": "could not determine whether memory is accepting "
                          "writes -- " + "; ".join(silent),
                "rejected_writes": rejected_total, "sources": sources}

    return {"status": "ok", "accepting_writes": True, "reason": "",
            "rejected_writes": rejected_total, "sources": sources}


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
    ``ok`` / ``degraded`` / ``unknown`` derived from four store-scoped facts:

    1. **Serving identity** — the live store's CLASS vs the requested backend.
       A jsonl ``MemoryStore`` serving while ``moneta``/``shadow`` was selected
       is a degradation even if ``backend_fallback()`` is None (the flag is
       reset per construction; the class is not).
    2. **Enumeration reachability** — ``store.count()`` must not raise. A store
       that cannot be read is degraded regardless of directory writability.
    3. **Durable persistence** (Moneta only) — a Moneta handle with
       ``durability=None`` keeps deposits in RAM; a restart loses them. That is
       a degraded WRITE plane even when the directory probes writable.
    4. **The store's own write verdict** (B6) — ``read_store_write_health()``
       asks the live store, and the contract-bearing stores it wraps, whether
       they are still accepting writes. This is the AUTHORITATIVE check and it
       DOMINATES: facts 1-3 were all green for the two days a degraded store
       refused every write (see the B6 block above), so a sick verdict here is a
       degradation regardless of what they say. When no object can answer, the
       row is ``unknown`` — never ``ok``. It lands under ``write_health``.

    Additive (BP2-HEALTHWIRE, T1): on the evaluated path this row also carries
    ``embedder_id`` and ``embedding_dim`` (the two W1 operator fields it lacked)
    plus a ``backend_health`` sub-dict — the full ``store.backend_health()``
    reading whose ``verdict`` (alias of its ``status``) speaks the ratified
    ``SUCCESS | UNAVAILABLE | BLOCKED`` vocabulary. The row's OWN
    ``ok/degraded/unknown`` word is unchanged; the ratified verdict rides
    alongside it, so an UNAVAILABLE/BLOCKED backend is never presented as ok.

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

    # (4) B6 — the store's OWN answer, and the only one that could have caught
    # the 2026-09-15 outage. Checks 1-3 above were all TRUE for two days while
    # every write was refused, so this one DOMINATES them: it goes into the same
    # `broken` list (degraded wins outright), and a store that cannot tell us
    # goes into `unclear` (unknown), never silently into the ok branch. That
    # unknown is load-bearing, not noise -- it is what a store object predating
    # the health contract, a stub, or a backend that never grew one looks like,
    # and reporting those as healthy is the failure this whole lane exists for.
    write_health = read_store_write_health(store)
    info["write_health"] = write_health
    # Lift the two operator-facing numbers to the top of the row so a consumer
    # that only renders a flat dict still shows them.
    info["accepting_writes"] = write_health.get("accepting_writes")
    info["rejected_writes"] = write_health.get("rejected_writes")
    if write_health.get("status") == "degraded":
        broken.append(write_health.get("reason") or "the live store is not accepting writes")
    elif write_health.get("status") == "unknown":
        unclear.append(write_health.get("reason")
                       or "the live store could not report its write health")

    # BP2-HEALTHWIRE (T1): ride the ratified backend verdict + the two W1
    # operator fields this row lacked (embedder id + embedding dim) ALONGSIDE the
    # existing status word. ADDITIVE ONLY: store.backend_health() speaks the
    # ratified SUCCESS|UNAVAILABLE|BLOCKED vocabulary; write_plane keeps its own
    # ok/degraded/unknown word untouched (its doctor, panel-strip, and
    # test_w3_harden_write_plane_store.py consumers read that word). We reuse the
    # SAME live store object already resolved above — no second construction.
    # backend_health() is self-fenced and never raises; the try/except is a
    # latent-safety belt so a health read still never escapes.
    try:
        from ..memory.store import backend_health as _backend_health
        bh = _backend_health(store)
    except Exception as exc:  # noqa: BLE001 -- health must not raise
        bh = None
        info["backend_health"] = {
            "reason": f"backend_health unreadable: {type(exc).__name__}: {exc}",
        }
    if bh is not None:
        # Two W1 operator fields, merged at top level (honest None on jsonl,
        # which has no embedder — never a fabricated value).
        info["embedder_id"] = bh.get("embedder_id")
        info["embedding_dim"] = bh.get("embedding_dim")
        # The full ratified dict rides under its own key. 'verdict' is an
        # operator-facing alias for backend_health()'s 'status' (store.py is
        # territory-frozen, so the word THERE stays 'status') — identical value,
        # always one of SUCCESS|UNAVAILABLE|BLOCKED, never rendered as ok.
        sub = dict(bh)
        sub["verdict"] = bh.get("status")
        info["backend_health"] = sub

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
