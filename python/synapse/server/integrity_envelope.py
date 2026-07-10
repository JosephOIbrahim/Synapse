"""
Live-Path Integrity Envelope — PATH-QUALIFIED IntegrityBlocks for /synapse ops.

Mutating commands on the live ``/synapse`` WS path get an observe-only
``IntegrityBlock``: two cheap topological scene hashes captured around
``registry.invoke()`` in ``SynapseHandler.handle()`` (inside the C5 mutation
lock, so the pair is adjacent to exactly that op), assembled on the
``_submit_logs`` executor thread, and appended into the process-wide
``LosslessExecutionBridge`` (``shared.bridge.get_process_bridge``) so the
§16 observability loop (operation_stats / recent_operations /
ConductorAdvisor) sees live ops in the same trail as ``/mcp`` ops.

HONESTY CONTRACT (per-path anchor semantics, CLAUDE.md §1.3):
  - The envelope OBSERVES; it never wraps execution, never gates (D1 posture,
    pinned by tests/test_phase0b_consent_posture.py), and never Flattens a
    stage (``include_stage=False`` on every capture — the Finding 3 floor).
  - consent / composition: no gate ran, no validation ran — recorded False
    with ``*_applicable=False`` (anchor N/A), never faked True.
  - undo: recorded False with ``undo_applicable=False``. SOME live handlers
    do wrap inline (hou.undos.group in handlers_usd/_material/_cops/batch/
    execute), but the highest-traffic ones (create_node / set_parm /
    connect_nodes / delete_node in handlers_node.py) do NOT, and per-op
    verification would need ``hou.undos`` member APIs that are not in the
    introspected symbol table (the same reason H2 rejected undo-stack
    inspection) — so the anchor is recorded as not-verified rather than
    asserted from a contract the code falsifies. (This exposes CLAUDE.md §1's
    "inline hou.undos.group(...)" live-path claim as doc drift — surfaced
    there, not re-asserted here.)
  - ``main_thread_executed=True`` IS asserted: every hou-touching live
    handler marshals through ``server.main_thread.run_on_main``
    (code-verified), and the envelope's own captures ride the same mechanism.

Import-guarded, zero-``hou``, standalone-safe: on ImportError every entry
point no-ops (``envelope_active()`` -> False).
"""

import hashlib
import logging
import os
import sys
import threading
from contextlib import contextmanager
from datetime import datetime

_log = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", ".."))  # server->synapse->python->repo root
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Import bridge (graceful fallback) ────────────────────────────
_ENVELOPE_AVAILABLE = False
try:
    from shared.bridge import IntegrityBlock, get_process_bridge
    from shared.constants import HASH_LENGTH
    _ENVELOPE_AVAILABLE = True
except ImportError:
    IntegrityBlock = None  # type: ignore[assignment,misc]
    get_process_bridge = None  # type: ignore[assignment]
    HASH_LENGTH = 16  # type: ignore[assignment]


#: per_agent counter key for live blocks in the shared trail. The envelope
#: records SUCCESSFUL ops only (handle()'s except branches never reach
#: _submit_logs), so the LIVE per-agent success rate stays 1.0 and never
#: trips the ConductorAdvisor agent_health verdict.
LIVE_AGENT_KEY = "LIVE"

# Commands classified mutating by handlers._READ_ONLY_COMMANDS' complement
# but which are genuinely read-only / non-scene — verified by diffing the
# reg.register() calls against the frozenset. Enveloping them would add two
# main-thread hash hops per call AND a false "LIVE mutation" block to the
# audited trail. Additive skip-set: fixing _READ_ONLY_COMMANDS itself would
# also change C5 lock behavior (that set is load-bearing — see the
# render_farm_cancel note there), so the envelope carries its own.
ENVELOPE_SKIP_COMMANDS = frozenset({
    "doctor",
    "hda_list",
    "memory_query",
    "memory_status",
    "query_prims",
    "render_farm_status",
    "tops_monitor_stream",
    # PURE off-main-thread writes by design (zero run_on_main in their
    # handlers — verified: _handle_write_report, tracker.handle_memory_add,
    # tracker.handle_memory_decide) that touch no scene. Envelope captures
    # would ADD a main-thread dependency they deliberately avoid (up to 2x
    # capture-timeout on a cooking main thread) and land a false "LIVE
    # mutation" block for '/obj' — provenance noise for non-scene ops.
    # (project_setup/memory_write/sleep_pass DO touch run_on_main already,
    # so they stay enveloped — no new coupling, and they read scene paths.)
    "add_memory",
    "decide",
    "write_report",
})

# ── Bridge-routed suppression (thread-local) ─────────────────────
# When handler.handle() runs NESTED inside LosslessExecutionBridge.execute()
# (the panel adapter + the in-process /mcp adapter via execute_through_bridge),
# the bridge's _finalize already records the op — a live block on top would
# double-count operations_total in the shared process instance.
# bridge.execute() runs fn on the caller's thread, so a thread-local is
# correct here.

_tls = threading.local()


@contextmanager
def bridge_routed():
    """Mark this thread as executing inside bridge.execute() so handle()
    suppresses the live envelope for the nested dispatch."""
    prev = getattr(_tls, "bridge_routed", False)
    _tls.bridge_routed = True
    try:
        yield
    finally:
        _tls.bridge_routed = prev


def _envelope_enabled() -> bool:
    """Env kill switch: ``SYNAPSE_LIVE_ENVELOPE=0`` disables all live-path
    captures and blocks without a code change. The escape hatch for the
    unresolved C6/T1 hypothesis (~2s executeDeferred wake floor): if T1 is
    real, the two capture hops per mutating op become a measurable latency
    tax, and the operator must be able to shed it in production immediately.
    Read at call time (cheap dict lookup) so a test/live toggle takes effect
    without re-import."""
    return os.environ.get(
        "SYNAPSE_LIVE_ENVELOPE", "1"
    ).strip().lower() not in ("0", "false", "off")


def envelope_active(cmd_type: str) -> bool:
    """Whether *cmd_type* gets a live block. Evaluated in handle() on the
    CALLING thread — the TLS flag does not survive the hop to the log
    executor, so the decision is made before submit."""
    return (
        _ENVELOPE_AVAILABLE
        and _envelope_enabled()
        and cmd_type not in ENVELOPE_SKIP_COMMANDS
        and not getattr(_tls, "bridge_routed", False)
    )


# ── Hash target extraction ───────────────────────────────────────
# Same payload field list bridge_adapter already uses for blast-radius
# extraction. First absolute-path string wins; "/obj" is the legacy default.
_HASH_FIELDS = ("node", "node_path", "parent", "path", "source")


def _hash_target(payload) -> str:
    if isinstance(payload, dict):
        for field_name in _HASH_FIELDS:
            val = payload.get(field_name)
            if isinstance(val, str) and val.startswith("/"):
                return val
    return "/obj"


# ── Capture timeout (fixed, short) ───────────────────────────────
# A capture hop must never hold the C5 mutation lock long: a miss is honest
# (None -> the 'hash_unavailable' sentinel, fidelity stays 1.0), so the
# right bound is a fixed SHORT timeout, not an adaptive one. An earlier
# draft derived it from dispatch_wait_stats() (max*1.5, clamped [2,8]s) —
# deleted: on a busy main thread that let the two capture hops hold the C5
# lock 8-16s per op, a latency tax the envelope must never impose. Missing
# a hash on a wedged main thread is the designed outcome, not a failure.
_CAPTURE_TIMEOUT_DEFAULT_S = 1.0
_CAPTURE_TIMEOUT_ENV = "SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT"


def _capture_timeout() -> float:
    """Fixed short bound (seconds) on each envelope hash hop. Env override
    via SYNAPSE_ENVELOPE_CAPTURE_TIMEOUT (float, > 0), read at call time; a
    bad value never silently changes the default — same idiom as
    _stage_hash_prim_threshold in shared/bridge.py."""
    raw = os.environ.get(_CAPTURE_TIMEOUT_ENV)
    if raw:
        try:
            v = float(raw)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return _CAPTURE_TIMEOUT_DEFAULT_S


# ── Scene-hash capture ───────────────────────────────────────────

_infra_warned = False


def capture_scene_hash(payload):
    """Capture one cheap topological scene hash (never stage.Flatten) on the
    main thread. Returns the hash string, or None on honest failure — a
    capture miss must never block or fail the command it observes."""
    global _infra_warned
    if not _ENVELOPE_AVAILABLE:
        return None
    try:
        from .main_thread import is_main_thread_stalled, run_on_main
        # Stall guard: the detector already knows the main thread is wedged
        # (2+ consecutive run_on_main timeouts) — queuing another doomed wake
        # would just burn a capture timeout inside the C5 lock. Honest None,
        # same 'hash_unavailable' semantics as a capture miss.
        if is_main_thread_stalled():
            return None
        bridge = get_process_bridge()
        target = _hash_target(payload)
        # record_stall=False: two envelope hash hops per mutating op must
        # never feed the stall detector (threshold=2) and flip the WS
        # resilience layer into fast-failing REAL commands.
        # record_wait=False: nor the C6 dispatch-wait histogram — the
        # envelope would otherwise dominate the still-owed T1 attribution
        # instrument at ~2 samples/op.
        return run_on_main(
            lambda: bridge._compute_scene_hash(target, include_stage=False),
            timeout=_capture_timeout(),
            record_stall=False,
            record_wait=False,
        )
    except RuntimeError:
        # run_on_main timeout: main thread busy (cook/render). Honest None —
        # the block records the hash_unavailable sentinel.
        return None
    except Exception:
        # Anything else means the capture INFRASTRUCTURE is broken (import
        # failure, signature drift, phantom API). One-time loud warning: a
        # dead capture path must not silently self-attest hash_unavailable
        # forever.
        if not _infra_warned:
            _infra_warned = True
            _log.warning(
                "live integrity envelope: scene-hash capture infrastructure "
                "failed -- all live blocks will record hash_unavailable "
                "until this is fixed",
                exc_info=True,
            )
        return None


# ── Block assembly + record ──────────────────────────────────────

def record_live_block(cmd_type, payload, hash_before, hash_after) -> None:
    """Build the PATH-QUALIFIED IntegrityBlock for one successful live op and
    append it to the process-wide bridge trail. Runs on the handlers'
    _log_executor thread (fire-and-forget) — record_external_block is
    thread-safe."""
    if not _ENVELOPE_AVAILABLE:
        return
    if hash_before and hash_after:
        if hash_before == hash_after:
            delta = "no_change"
        else:
            delta = hashlib.sha256(
                f"{hash_before}:{hash_after}".encode()
            ).hexdigest()[:HASH_LENGTH]
    else:
        # Truthy sentinel: a snapshot MISS (busy main thread) is NOT a
        # pipeline bug, so fidelity stays 1.0 (CLAUDE.md §1.3) — the honesty
        # lives in the sentinel + the empty hash fields.
        delta = "hash_unavailable"
    block = IntegrityBlock(
        # Anchor honesty (see module docstring): only main-thread marshalling
        # is asserted; undo/consent/composition are recorded not-verified /
        # not-applicable — never faked True.
        undo_group_active=False,
        main_thread_executed=True,
        consent_verified=False,
        composition_valid=False,
        agent_id=LIVE_AGENT_KEY,
        operation_type=cmd_type,
        timestamp=datetime.now().isoformat(),
        scene_hash_before=hash_before or "",
        scene_hash_after=hash_after or "",
        delta_hash=delta,
        execution_path="live",
        consent_applicable=False,
        composition_applicable=False,
        undo_applicable=False,
        hash_target=_hash_target(payload),
    )
    get_process_bridge().record_external_block(block)
