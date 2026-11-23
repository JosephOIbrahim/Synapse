"""
Synapse Command Handlers

Registry-based command handler system for the Synapse WebSocket server.
Routes incoming commands to appropriate handler functions.
"""

import contextlib
import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Callable, Optional

_log = logging.getLogger(__name__)

# Prometheus histogram bucket boundaries (milliseconds) for per-tool call
# duration. Cumulative "le" semantics: an observation counts toward every
# boundary >= its duration. Mile 0 observability spine.
_TOOL_DURATION_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.protocol import (
    COMMAND_ALIASES,
    CommandType,
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
    normalize_command_type,
)
from ..core.aliases import (
    PARAM_ALIASES,
    resolve_param,
    resolve_param_with_default,
    USD_PARM_ALIASES,
)
from ..core.audit import audit_log, AuditLevel, AuditCategory
from ..core.floor_gate import FloorGate, FloorContext
from ..core.errors import (
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    HoudiniUnavailableError,
    HistoryScopeRefused,
    ExecutionAborted,
    ExecutionDeadlineExceeded,
)
from ..core.outcomes import info as _outcome_info, for_exception as _for_exception
from .handlers_node import NodeHandlerMixin
from .handlers_network_layout import NetworkLayoutMixin
from .handlers_usd import UsdHandlerMixin
from .undo_scope import UndoScope, history as undo_history, note_history_may_change
# R-034 (CONDUCTOR-7): per-step receipts + the applied-step guard for
# batch_commands. Pure Python (no hou), importable standalone.
from .batch_receipts import (
    BatchIdConflict,
    BatchReceiptStore,
    STATUS_ERROR,
    STATUS_IN_PROGRESS,
    STATUS_NOT_RUN,
    STATUS_OK,
    STATUS_UNKNOWN,
    new_batch_id,
    step_summary as _batch_step_summary,
)
# R-035 (CONDUCTOR-8): in-flight autonomous-render task registry. Pure Python
# (no hou, no autonomy import), importable standalone.
from .autonomy_tasks import AutonomyTaskStore, fingerprint as _autonomy_fingerprint
from .handlers_render import (
    RenderHandlerMixin, _undo_labels_snapshot, _rollback_if_group_left_entry,
)
from .handlers_tops import TopsHandlerMixin
from .handlers_farm import FarmHandlerMixin, FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
from .handlers_material import MaterialHandlerMixin
from .handlers_memory import MemoryHandlerMixin
from .handlers_hda import HdaHandlerMixin
from .handlers_cops import CopsHandlerMixin
from .handlers_solaris_assemble import SolarisAssembleMixin
from .handlers_solaris_graph import SolarisGraphMixin
from .handlers_solaris_compose import SolarisComposeMixin
from .handlers_solaris_tools import SolarisToolsMixin
from .handlers_spatial import SpatialHandlerMixin
from .handlers_graph_synth import GraphSynthHandlerMixin
# Mile 4 (resource-aware-cache Phase 1, R-CACHE-1) -- read-only, feature-flagged
# synapse_assess_cache. Import-safe standalone (guards hou/cache_host_probe/cache_policy
# independently); see handlers_cache.py's header for the full architecture.
from .handlers_cache import CacheHandlerMixin
# Live-path integrity envelope (observe-only, PATH-QUALIFIED IntegrityBlocks).
# The module is import-safe standalone; its internals are guarded.
from . import integrity_envelope as _envelope



# ---------------------------------------------------------------------------
# Coaching-tone message helpers
# ---------------------------------------------------------------------------

from .handler_helpers import _suggest_parms, _HOUDINI_UNAVAILABLE, undo_receipt  # noqa: F401
# Reuse 2 threads for fire-and-forget memory logging (avoids Thread() per command)
_log_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synapse-log")

# Idempotent guard functions — injected into execute_python namespace
try:
    from .guards import GUARD_FUNCTIONS as _GUARD_FUNCTIONS
except ImportError:
    _GUARD_FUNCTIONS = {}  # Graceful fallback if guards not available

# Coding-bug errors that trigger auto-rollback in execute_python.
# These indicate the script itself is broken — partial mutations are unwanted.
# Operational errors (RuntimeError, hou.OperationFailed, IOError, etc.) do NOT
# trigger rollback because earlier mutations (node creation, wiring) may be valid.
_ROLLBACK_ERRORS = (NameError, SyntaxError, TypeError, AttributeError, IndexError,
                    KeyError, ValueError, UnboundLocalError)

# attribwrangle "class" (Run Over) menu index, in the node's own order:
# Detail, Primitives, Points, Vertices, Numbers. Pinned against the 22.0.400
# parm catalog by tests/test_harden_h2_vex_run_over.py (H-2, 2026-10-04: the
# earlier table had points=1, so "Points" ran over primitives).
VEX_RUN_OVER_CLASS: Dict[str, int] = {
    "detail": 0,
    "primitives": 1, "primitive": 1, "prims": 1,
    "points": 2, "point": 2,
    "vertices": 3, "vertex": 3,
    "numbers": 4, "number": 4,
}

# Map command types to audit categories for structured logging
_CMD_CATEGORY: Dict[str, AuditCategory] = {
    "create_node": AuditCategory.PIPELINE,
    "delete_node": AuditCategory.PIPELINE,
    "connect_nodes": AuditCategory.PIPELINE,
    "layout_network": AuditCategory.PIPELINE,
    "set_parm": AuditCategory.PIPELINE,
    "set_keyframe": AuditCategory.PIPELINE,
    "execute_python": AuditCategory.PIPELINE,
    "execute_vex": AuditCategory.PIPELINE,
    "render": AuditCategory.RENDER,
    "render_settings": AuditCategory.RENDER,
    "wedge": AuditCategory.RENDER,
    "capture_viewport": AuditCategory.RENDER,
    "configure_render_passes": AuditCategory.RENDER,
    "validate_frame": AuditCategory.RENDER,
    "create_usd_prim": AuditCategory.PIPELINE,
    "modify_usd_prim": AuditCategory.PIPELINE,
    "set_usd_attribute": AuditCategory.PIPELINE,
    "reference_usd": AuditCategory.PIPELINE,
    "set_payload_loadstate": AuditCategory.PIPELINE,
    "create_point_instancer": AuditCategory.PIPELINE,
    "shot_render_ready": AuditCategory.RENDER,
    "query_prims": AuditCategory.PIPELINE,
    "manage_variant_set": AuditCategory.PIPELINE,
    "manage_collection": AuditCategory.PIPELINE,
    "configure_light_linking": AuditCategory.PIPELINE,
    "solaris_validate_ordering": AuditCategory.PIPELINE,
    "solaris_assemble_chain": AuditCategory.PIPELINE,
    "solaris_build_graph": AuditCategory.PIPELINE,
    "solaris_component_builder": AuditCategory.PIPELINE,
    "solaris_scene_template": AuditCategory.PIPELINE,
    "solaris_create_variants": AuditCategory.PIPELINE,
    "solaris_set_purpose": AuditCategory.PIPELINE,
    "solaris_import_megascans": AuditCategory.PIPELINE,
    "solaris_shotsetup_karma_xpu": AuditCategory.PIPELINE,
    "matlib_bind": AuditCategory.MATERIAL,
    "assess_render_ready": AuditCategory.RENDER,
    # D6 -- the camera path's trail: one Python Script LOP SYNAPSE writes itself.
    # get_spatial_path is read-only, no category needed.
    "spatial_trail": AuditCategory.PIPELINE,
    "create_material": AuditCategory.MATERIAL,
    "create_textured_material": AuditCategory.MATERIAL,
    "assign_material": AuditCategory.MATERIAL,
    "add_memory": AuditCategory.ENGRAM,
    "decide": AuditCategory.ENGRAM,
    "batch_commands": AuditCategory.SYNAPSE,
    # Graph synthesis
    "propose_graph": AuditCategory.PIPELINE,
    "instantiate_graph": AuditCategory.PIPELINE,
    # TOPS / PDG
    "tops_get_work_items": AuditCategory.PIPELINE,
    "tops_get_dependency_graph": AuditCategory.PIPELINE,
    "tops_get_cook_stats": AuditCategory.PIPELINE,
    "tops_cook_node": AuditCategory.PIPELINE,
    "tops_generate_items": AuditCategory.PIPELINE,
    "tops_configure_scheduler": AuditCategory.PIPELINE,
    "tops_cancel_cook": AuditCategory.PIPELINE,
    "tops_pause_cook": AuditCategory.PIPELINE,
    "tops_resume_cook": AuditCategory.PIPELINE,
    "tops_dirty_node": AuditCategory.PIPELINE,
    "tops_setup_wedge": AuditCategory.PIPELINE,
    "tops_batch_cook": AuditCategory.PIPELINE,
    "tops_query_items": AuditCategory.PIPELINE,
    "tops_cook_and_validate": AuditCategory.PIPELINE,
    "tops_diagnose": AuditCategory.PIPELINE,
    "tops_pipeline_status": AuditCategory.PIPELINE,
    "tops_multi_shot": AuditCategory.PIPELINE,
    # Autonomous render
    "autonomous_render": AuditCategory.RENDER,
    # Safe / progressive render
    "safe_render": AuditCategory.RENDER,
    "render_progressively": AuditCategory.RENDER,
    # H3b -- background-render stop + emergency halt
    "render_processes": AuditCategory.RENDER,
    "render_stop": AuditCategory.RENDER,
    "emergency_halt": AuditCategory.RENDER,
    # Undo / Redo
    "undo": AuditCategory.PIPELINE,
    "redo": AuditCategory.PIPELINE,
    # HDA operations
    "hda_create": AuditCategory.PIPELINE,
    "hda_promote_parm": AuditCategory.PIPELINE,
    "hda_set_help": AuditCategory.PIPELINE,
    "hda_package": AuditCategory.PIPELINE,
    "hda_list": AuditCategory.PIPELINE,
    # Copernicus (COPs) — Foundation
    "cops_create_network": AuditCategory.PIPELINE,
    "cops_create_copnet": AuditCategory.PIPELINE,
    "cops_create_node": AuditCategory.PIPELINE,
    "cops_connect": AuditCategory.PIPELINE,
    "cops_set_opencl": AuditCategory.PIPELINE,
    # cops_read_layer_info is read-only, no category needed
    # Copernicus (COPs) — Pipeline
    "cops_to_materialx": AuditCategory.PIPELINE,
    "cops_composite_aovs": AuditCategory.RENDER,
    "cops_analyze_render": AuditCategory.RENDER,
    "cops_slap_comp": AuditCategory.PIPELINE,
    # Copernicus (COPs) — Procedural
    "cops_create_solver": AuditCategory.PIPELINE,
    "cops_procedural_texture": AuditCategory.PIPELINE,
    "cops_growth_propagation": AuditCategory.PIPELINE,
    "cops_reaction_diffusion": AuditCategory.PIPELINE,
    "cops_pixel_sort": AuditCategory.PIPELINE,
    "cops_stylize": AuditCategory.PIPELINE,
    # Copernicus (COPs) — Advanced
    "cops_wetmap": AuditCategory.PIPELINE,
    "cops_bake_textures": AuditCategory.PIPELINE,
    "cops_temporal_analysis": AuditCategory.RENDER,
    "cops_stamp_scatter": AuditCategory.PIPELINE,
    "cops_batch_cook": AuditCategory.PIPELINE,
}

# Commands that don't modify state — skip memory logging for these
_READ_ONLY_COMMANDS = frozenset({
    "ping", "get_health", "get_help", "heartbeat",
    "get_parm", "get_scene_info", "get_selection",
    "get_stage_info", "get_usd_attribute",
    "context", "search", "recall",
    "capture_viewport",
    "knowledge_lookup",
    "inspect_selection", "inspect_scene", "inspect_node",
    "network_explain",
    # Mile 4 (R-CACHE-1) -- read-only, feature-flagged cache advisor. No forced cook,
    # no disk write, no node creation anywhere in its call graph (handlers_cache.py).
    "assess_cache",
    "read_material",
    "validate_frame",
    "solaris_validate_ordering",
    "assess_render_ready",
    # D6 -- the camera path read. It evaluates Camera LOP parms per frame
    # (evalAtFrame: no playhead move, no cook) and reads the composed stage;
    # nothing is authored (handlers_spatial.py). Its sibling spatial_trail
    # builds a node and is deliberately absent here.
    "get_spatial_path",
    "get_metrics", "router_stats", "list_recipes", "get_live_metrics",
    "tops_get_work_items", "tops_get_dependency_graph", "tops_get_cook_stats",
    "tops_query_items",
    "tops_diagnose", "tops_pipeline_status",
    "cops_read_layer_info",
    "cops_analyze_render",
    # render_farm_cancel is the control-plane kill switch: it mutates NO scene
    # state (sets two Python flags, no undo entry) and MUST bypass the C5
    # mutation lock -- a running render holds that lock for the whole sequence,
    # so a mutating-classified cancel would block behind the render it cancels
    # -- and the WS resilience layer (read-only fast path). Audit is written
    # in-handler (handlers_render._handle_render_farm_cancel).
    "render_farm_cancel",
    # render_farm_status: same rationale as render_farm_cancel. It is a pure
    # Python-side registry read (farm status + render session summary): no
    # scene mutation, no undo entry. Mutating-classified it took the C5
    # mutation lock off-main, so while a farm render held that lock the
    # status polls that exist to watch it queued behind it -- the opposite
    # of what a status endpoint is for. Master argued this classification
    # for cancel/stop/halt/processes and skipped status; this closes it.
    "render_farm_status",
    # H3b -- the same argument, for the same reason. render_processes only
    # reads rps. render_stop and emergency_halt signal an OS process / cancel
    # PDG contexts; they author no scene state and no undo entry. Critically,
    # a running render holds the C5 mutation lock for its whole duration, so a
    # mutating-classified stop or halt would queue behind the very operation it
    # exists to interrupt -- which is the difference between a kill switch and
    # a decoration. Audit is written in-handler (handlers_render).
    "render_processes", "render_stop", "emergency_halt",
    # cops_temporal_analysis is NOT read-only: it moves the global playhead
    # (hou.setFrame loop) and force-cooks — it must take the C5 mutation lock
    # and leave audit + Floor provenance records.
})


# C5 — cross-client mutation serialization. Two clients can drive one Houdini
# concurrently (the panel ToolExecutor + a stdio MCP client), and nothing
# serializes their command SEQUENCES — so create→connect→set_parm recipes from
# two agents interleave on the shared scene + undo stack. One process-wide lock,
# held only around a MUTATING command's invoke(), restores sequence coherence.
# Skipped on the main thread: main-thread dispatch is already event-loop-
# serialized, and blocking there would deadlock against run_on_main (which needs
# the main thread to make progress). Deliberately NOT a queue/scheduler — call
# batching was refuted for latency (PR #28); this is correctness, not throughput.
_MUTATION_LOCK = threading.Lock()

# Farm controls mutate the job journal, never the artist scene. Keep their
# provenance while excluding them from scene serialization and scene hashes.
_READ_ONLY_COMMANDS = _READ_ONLY_COMMANDS | FARM_READ_COMMANDS


# ---------------------------------------------------------------------------
# Inline-overrun observability (marshal-guard coordination)
# ---------------------------------------------------------------------------
#
# run_on_main has two main-thread fast paths: reentrant (main_thread.py:230) and
# caller-is-already-main (main_thread.py:240). Both invoke fn() INLINE and, by
# construction, DISCARD the ``timeout`` argument -- you cannot bound synchronous
# work on the thread you are standing on. That is correct and load-bearing: it is
# exactly why a main-thread caller executes instead of self-deadlocking in
# hdefereval's blocking primitive. But it means the /mcp dispatch path (which is
# already on the main thread) runs arbitrarily long payloads under a nominal
# budget that is silently a no-op. Not a deadlock -- unbounded main-thread
# capture. Today it is completely INVISIBLE.
#
# We do NOT fake a timeout. We make the overrun OBSERVABLE. Behaviour for
# off-main callers is byte-for-byte unchanged (they do not even enter the timed
# branch); the only addition is a telemetry record when an INLINE payload blows
# past the nominal budget its own handler declared.
#
# COORDINATION: the sink is owned by the marshal-guard owner and lives in
# server/marshal_guard.py::note_main_thread_inline_overrun, whose docstring
# pins a STABLE POSITIONAL signature ``(where, elapsed_s, budget_s, **extra)``
# and names ``handlers_*`` as an expected co-caller. We call it by that exact
# contract and implement no sink of our own.
#
# run_on_main's fast path 2 ALSO reports, as
# ``main_thread.run_on_main:fast_path_2`` against the guard's global
# ``inline_budget_s()``. That record answers "the main thread was captured";
# ours answers "by WHICH handler, against the budget that handler asked for" --
# information the central site cannot recover, since by then the caller's
# ``timeout`` argument has been discarded. Distinct ``where`` values, so the two
# records are separable rather than conflated (see risks: they do both increment
# the shared ``inline_overruns`` counter).
def _would_run_inline_on_main() -> bool:
    """True when a run_on_main call from here would take a main-thread fast path.

    Must be evaluated BEFORE the call: run_on_main sets/clears ``_tls.on_main``
    around fn() on the worker path, so sampling afterwards would misread it.
    Defensive by design -- any failure reports False, which only means we skip
    the extra telemetry. It can never affect execution.
    """
    try:
        from . import main_thread as _mt
        if getattr(_mt._tls, "on_main", False):
            return True                                    # fast path 1
        return threading.current_thread().ident == _mt._MAIN_THREAD_ID  # fast path 2
    except Exception:
        return False


def _note_inline_overrun(label: str, elapsed_s: float, budget_s: float) -> None:
    """Report an inline (unbounded) main-thread payload that blew its budget.

    Reports THROUGH the marshal-guard sink using its pinned positional contract
    ``(where, elapsed_s, budget_s)``. No local log line: the guard already logs
    at WARNING, and a second one here would double-report the same event. If the
    guard module is absent (older tree), we stay silent rather than invent a
    parallel channel -- run_on_main's own fast-path-2 report still covers the
    "main thread was captured" fact.
    """
    try:
        from .marshal_guard import note_main_thread_inline_overrun
    except Exception:
        return
    try:
        note_main_thread_inline_overrun(label, elapsed_s, budget_s)
    except Exception as e:  # pragma: no cover - telemetry is never fatal
        _log.debug("inline-overrun hook failed: %s", e)


def run_on_main_observed(fn, timeout, label):
    """run_on_main, plus inline-overrun telemetry when the budget is a no-op.

    Off-main callers get run_on_main verbatim: same timeout enforcement, same C4
    abandoned-flag zombie kill, same C6 dispatch-wait sample. Only the inline
    main-thread path is instrumented, and only on the way out -- so a payload's
    result and any exception it raises propagate completely unchanged.

    ``label`` is the stable ``where`` identifier for the guard sink; use the
    command name, prefixed so it never collides with the central report.
    It also threads through to run_on_main's OCC main-thread hold histogram,
    so deferred payloads dispatched here are attributed by command name.
    """
    from .main_thread import run_on_main

    if not _would_run_inline_on_main():
        return run_on_main(fn, timeout=timeout, label=label)

    _t0 = time.perf_counter()
    try:
        return run_on_main(fn, timeout=timeout, label=label)
    finally:
        _elapsed = time.perf_counter() - _t0
        if _elapsed > timeout:
            _note_inline_overrun(f"handlers.{label}:inline", _elapsed, timeout)


def _marshal_inspect_read(fn, *, command: str, label: str, subject: str):
    """Marshal an inspect read on its canonical budget, naming a timed-out payload.

    ``run_on_main``'s timeout bounds the WAIT, never the WORK: when it fires the
    payload may still be executing on Houdini's main thread. The stock message
    says "the call may still be running" without saying WHICH call — and a
    geometry walk (R-019) is exactly the payload that can outlive its budget on
    a heavy SOP. R-019 requires the timeout to name what is still running and
    where, so the re-raise keeps the ``MainThreadTimeout`` type the WS
    transports classify on (``transport.timeout`` / ``transport.read_retry``)
    and replaces only the message.

    The budget is read from ``core/timeouts.py`` so the marshal and the MCP
    transport fire at the same boundary (the F6 pattern used by inspect_scene
    and reference_usd).
    """
    from .main_thread import run_on_main, MainThreadTimeout
    from ..core.timeouts import timeout_for

    budget = timeout_for(command)
    try:
        return run_on_main(fn, timeout=budget, label=label)
    except MainThreadTimeout:
        raise MainThreadTimeout(
            "%s timed out after %.1fs waiting for Houdini's main thread; the "
            "read of %s is still running there and may still be cooking. "
            "Check the scene before retrying -- the result was not applied."
            % (command, budget, subject)
        ) from None


_AUTONOMY_STORE_INIT_LOCK = threading.Lock()


def _autonomy_task_store(handler) -> AutonomyTaskStore:
    """This handler's autonomous-render task store, created on first use.

    Same double-checked pattern as ``_batch_store``: handler objects built
    with ``__new__`` (tests, degraded startup) never ran ``__init__``, and
    first use must still work.
    """
    store = getattr(handler, "_autonomy_tasks", None)
    if store is not None:
        return store
    with _AUTONOMY_STORE_INIT_LOCK:
        store = getattr(handler, "_autonomy_tasks", None)
        if store is None:
            store = AutonomyTaskStore()
            handler._autonomy_tasks = store
    return store


def _serialize_render_report(obj):
    """JSON-safe dict for an autonomy RenderReport (dataclasses/enums/datetime)."""
    from dataclasses import asdict

    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize_render_report(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize_render_report(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_render_report(v) for v in obj]
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return obj


# ---------------------------------------------------------------------------
# R-035: running the autonomy loop on a worker thread under Houdini's asyncio
# ---------------------------------------------------------------------------

#: Houdini 22 ships a patched asyncio ("haio"): its event loop refuses
#: ``create_task`` on a non-main thread with this message, which is what kills
#: ``asyncio.run`` before its first task on the autonomous-render worker.
_MAIN_THREAD_GUARD_MARKER = "main thread"


def _is_main_thread_guard(exc: BaseException) -> bool:
    """True only for Houdini's off-main-thread asyncio refusal.

    A RuntimeError without the marker is a different failure. Treating it as
    the guard would trade a reported error for a plan nobody asked to run a
    second time.
    """
    return isinstance(exc, RuntimeError) and _MAIN_THREAD_GUARD_MARKER in str(exc).lower()


def _new_autonomy_loop():
    """Construct a plain asyncio loop without consulting the process policy.

    ``asyncio.new_event_loop()`` -- and therefore ``asyncio.run`` -- reads the
    current policy, which Houdini 22 patches to hand back its guarded
    ``haio.HoudiniEventLoop``. The selector loop is constructed by name and has
    no thread check; ``gather``/``sleep`` are known to work on it off the main
    thread.
    """
    import asyncio

    return asyncio.SelectorEventLoop()


def _close_autonomy_loop(loop) -> None:
    """Close a plain loop, cancelling whatever a failed run left pending.

    Closing with tasks still pending makes the garbage collector print "Task
    was destroyed but it is pending" later, from a thread that cannot explain
    it. Cleanup never outranks the run's outcome -- the receipt already
    carries that -- so a cleanup failure is logged, not raised.
    """
    import asyncio

    try:
        try:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True))
        except Exception as exc:  # noqa: BLE001 -- cleanup must not outrank the result
            _log.debug("autonomy loop cleanup failed: %s", exc)
    finally:
        try:
            loop.close()
        except Exception as exc:  # noqa: BLE001 -- cleanup must not outrank the result
            _log.debug("autonomy loop close failed: %s", exc)


def _run_autonomy_off_main(driver, intent):
    """Run ``driver.execute`` on a plain loop here, or its sync step loop.

    The guard is checked where Houdini's haio refuses -- building the loop,
    then creating the task -- and both happen before the coroutine runs, so
    nothing has been dispatched and the fallback cannot repeat a step. A
    guard raised after that point is a real mid-run failure and is reported
    as one -- it is never a reason to try the run again synchronously.
    """
    loop = None
    try:
        loop = _new_autonomy_loop()
    except RuntimeError as exc:
        if not _is_main_thread_guard(exc):
            raise
        return driver.execute_sync(intent, reason=str(exc))
    try:
        coro = driver.execute(intent)
        try:
            task = loop.create_task(coro)
        except RuntimeError as exc:
            coro.close()  # never started: nothing was dispatched
            if not _is_main_thread_guard(exc):
                raise
            return driver.execute_sync(intent, reason=str(exc))
        return loop.run_until_complete(task)
    finally:
        _close_autonomy_loop(loop)


_BATCH_STORE_INIT_LOCK = threading.Lock()


def _batch_store(handler) -> BatchReceiptStore:
    """This handler's batch receipt store, created on first use.

    Handler objects built with ``__new__`` (tests, degraded startup) never ran
    ``__init__``; first use must still work rather than raise AttributeError.
    The double-checked lock only guards the one-time creation.
    """
    store = getattr(handler, "_batch_receipt_store", None)
    if store is not None:
        return store
    with _BATCH_STORE_INIT_LOCK:
        store = getattr(handler, "_batch_receipt_store", None)
        if store is None:
            store = BatchReceiptStore()
            handler._batch_receipt_store = store
    return store


def _batch_timeout_exception(batch_id, budget, receipts, original):
    """The timeout a batch caller gets: named steps, honest state, resume key.

    R-034: a timed-out batch is not a definite failure. The payload stops at
    its next step boundary, so the caller is told which steps ran, which one
    was in flight (``unknown`` -- never ``error``), and to reuse this batch id
    on a retry so the completed steps are not applied twice.
    """
    from .main_thread import MainThreadTimeout

    snapshot = receipts.snapshot()
    started = getattr(original, "started", None)
    if started is False:
        head = ("Batch %s did not start within %.0fs waiting for Houdini's "
                "main thread; it never began, so nothing was applied."
                % (batch_id, budget))
    elif snapshot["status"] == "complete":
        head = ("Batch %s finished all %d step(s) just as the %.0fs wait "
                "expired; the changes were applied."
                % (batch_id, snapshot["step_count"], budget))
    elif snapshot["status"] == "not_started":
        # The payload began but no step recorded an outcome -- say that and no
        # more. Silence must never read as "nothing happened".
        head = ("Batch %s timed out after %.0fs waiting for Houdini's main "
                "thread; the payload had started but no step recorded an "
                "outcome, so it may still be running. No further step will "
                "be issued." % (batch_id, budget))
    else:
        head = ("Batch %s timed out after %.0fs waiting for Houdini's main "
                "thread; no further step will be issued."
                % (batch_id, budget))
    unknown = snapshot.get("unknown_steps") or []
    middle = (" A step reported unknown may still be changing the scene -- "
              "check it before retrying." if unknown else "")
    exc = MainThreadTimeout(
        "%s Steps: %s.%s Retry with batch_id=%s to skip the steps that "
        "already ran."
        % (head, _batch_step_summary(snapshot), middle, batch_id)
    )
    # ``receipt`` is the generic structured-failure slot _failure_receipt_data
    # merges into response.data; the other attributes name the batch for
    # callers that read the exception directly instead of the wire.
    exc.receipt = snapshot
    exc.batch_id = batch_id
    exc.started = started
    return exc


# =============================================================================
# COMMAND HANDLER REGISTRY
# =============================================================================

class CommandHandlerRegistry:
    """
    Registry for command handlers.

    Allows registering handler functions for specific command types.
    Supports both built-in and custom handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        # One shared FloorGate per registry: the Tier-0 provenance hook. Routing
        # a call through invoke() records one provenance file per mutating op.
        self._floor_gate = FloorGate()

    def register(self, command_type: str, handler: Callable):
        """Register a handler for a command type."""
        self._handlers[command_type] = handler

    def get(self, command_type: str) -> Optional[Callable]:
        """Get handler for a command type (expects pre-normalized type)."""
        return self._handlers.get(command_type)

    def has(self, command_type: str) -> bool:
        """Check if a handler exists for a command type."""
        return self.get(command_type) is not None

    def invoke(
        self,
        command_type: str,
        payload: Any,
        ctx: Optional[FloorContext] = None,
    ) -> Any:
        """Look up the handler for ``command_type`` and run it through the
        FloorGate (additive Tier-0 provenance), returning its result.

        Parity with ``get(cmd)(payload)`` for the happy path; additionally emits
        one provenance record for each mutating op (none for read-only). Raises
        ``KeyError`` if no handler is registered — callers that need the
        not-found-as-data behavior should check ``get()`` first.
        """
        handler = self.get(command_type)
        if handler is None:
            raise KeyError(f"No handler registered for {command_type!r}")
        if command_type in ("undo", "redo") or command_type in _READ_ONLY_COMMANDS:
            return self._floor_gate.wrap(command_type, payload, handler, ctx=ctx)
        # R-012: this may add to Houdini's history, so it ends every handler's
        # redo run -- before (its entries may land at any point) and after
        # (a run recorded while it was in flight).
        note_history_may_change()
        try:
            return self._floor_gate.wrap(command_type, payload, handler, ctx=ctx)
        finally:
            note_history_may_change()

    @property
    def registered_types(self):
        """Get list of registered command types."""
        return list(self._handlers.keys())

# =============================================================================
# SYNAPSE HANDLER
# =============================================================================

def _failure_receipt_data(exc: BaseException) -> Optional[Dict]:
    """The structured receipt an exception carries, wrapped for response.data.

    Handlers that can fail with a machine-readable record attach it to the
    exception (``ParmWriteRefused.receipt``) because the failure arm that
    formats the response does not know the handler. Returning None keeps the
    response shape of every exception that carries no receipt.

    An exception that declares ``outcome_code`` (BRAINSTEM-3/4: ExecutionAborted,
    ExecutionDeadlineExceeded) also carries its typed outcome here, so the wire
    says WHAT KIND of failure this was instead of defaulting to ``tool.failed``.
    ``with_failure_outcome`` preserves a data-level outcome unchanged.
    """
    data: Optional[Dict] = None
    receipt = getattr(exc, "receipt", None)
    if isinstance(receipt, dict):
        data = {"receipt": receipt}
    outcome = _for_exception(exc)
    if outcome is not None:
        data = dict(data or {})
        data["outcome"] = outcome.to_dict()
    return data


class SynapseHandler(NodeHandlerMixin, NetworkLayoutMixin, UsdHandlerMixin, RenderHandlerMixin, TopsHandlerMixin, FarmHandlerMixin, MaterialHandlerMixin, MemoryHandlerMixin, HdaHandlerMixin, CopsHandlerMixin, SolarisAssembleMixin, SolarisGraphMixin, SolarisComposeMixin, SolarisToolsMixin, SpatialHandlerMixin, GraphSynthHandlerMixin, CacheHandlerMixin):
    """
    Main command handler for the Synapse server.

    Routes commands to appropriate handler functions and manages
    integration with the session tracker / memory bridge.
    """

    def __init__(self):
        self._registry = CommandHandlerRegistry()
        self._session_id: Optional[str] = None
        self._user_id: str = ""
        self._bridge = None
        # R-014 (BRAINSTEM-6): the tiered router is constructed HERE, because
        # this is the single seam every transport builds its handler through —
        # the /synapse WS server (SynapseServer.__init__) and the /mcp server
        # (MCPServer._get_handler) both call SynapseHandler(). Before this it
        # was never constructed anywhere, so the advertised synapse_router_stats
        # tool could only raise "Router not initialized". It is NOT on the live
        # command dispatch path (handle() goes straight to the registry), so its
        # counters read zero until something routes through it — the tool
        # reports that honestly instead of failing. Local import: the routing
        # package must not become a module-level dependency of the handler stack;
        # a construction failure leaves router_stats raising its typed error
        # (never a fake success), while the rest of the handler still serves.
        try:
            from ..routing.router import TieredRouter
            self._router = TieredRouter()
        except Exception:
            self._router = None
            _log.debug(
                "TieredRouter construction failed; router_stats will report "
                "unavailable", exc_info=True)
        # R-012: the agent's history tools may only step over SYNAPSE's own
        # entries. handle() records the baseline before the first mutating
        # command runs, reading hou.undos on the main thread (inline there,
        # through run_on_main from any other thread); a history call with no
        # baseline captures one inside its own main-thread call.
        self._undo_scope = UndoScope()
        # R-034 (CONDUCTOR-7): per-batch step receipts. The id a caller
        # supplies (or gets back) is the resume key: a retry skips steps this
        # store already recorded ok, so a timed-out batch is never replayed.
        # Bounded (BatchReceiptStore evicts settled batches first).
        self._batch_receipt_store = BatchReceiptStore()
        # Per-tool call-duration accumulator (Mile 0). Thread-safe: handle()
        # may run under the FastMCP executor on worker threads.
        self._tool_durations: Dict[str, Dict[str, Any]] = {}
        self._tool_durations_lock = threading.Lock()
        self._register_handlers()

    def _record_tool_duration(self, tool: str, duration_ms: float):
        """Record one timed tool call into the cumulative histogram."""
        with self._tool_durations_lock:
            rec = self._tool_durations.get(tool)
            if rec is None:
                rec = {
                    "count": 0,
                    "sum_ms": 0.0,
                    "buckets": {b: 0 for b in _TOOL_DURATION_BUCKETS_MS},
                }
                self._tool_durations[tool] = rec
            rec["count"] += 1
            rec["sum_ms"] += duration_ms
            for b in _TOOL_DURATION_BUCKETS_MS:
                if duration_ms <= b:
                    rec["buckets"][b] += 1

    def tool_duration_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return a snapshot copy of per-tool duration stats for export."""
        with self._tool_durations_lock:
            return {
                tool: {
                    "count": rec["count"],
                    "sum_ms": rec["sum_ms"],
                    "buckets": dict(rec["buckets"]),
                }
                for tool, rec in self._tool_durations.items()
            }

    def set_session_id(self, session_id: str):
        """Set the current session ID for action logging."""
        self._session_id = session_id

    def set_user_id(self, user_id: str):
        """Set the current user ID for per-user audit trails."""
        self._user_id = user_id

    def _get_bridge(self):
        """Lazy-load the bridge to avoid circular imports."""
        if self._bridge is None:
            from ..session.tracker import get_bridge
            self._bridge = get_bridge()
        return self._bridge

    def handle(self, command: SynapseCommand) -> SynapseResponse:
        """
        Handle an incoming command.

        Args:
            command: The command to handle

        Returns:
            SynapseResponse with the result
        """
        # R-013 (SUBSTRATE-7): the envelope decision/state must exist BEFORE
        # the try, because every except arm below returns without reaching
        # _submit_logs — and a failed live operation must still be able to
        # land in the integrity trail. False/None here means "not enveloped",
        # so the arms record nothing unless the command was actually observed.
        _enveloped = False
        _hash_before = None
        _hash_after = None
        cmd_type = command.type
        try:
            # Fast path: try raw type first (aliases are pre-populated in registry)
            cmd_type = command.type
            handler = self._registry.get(cmd_type)
            if handler is None:
                # Fallback: normalize for any aliases not in registry
                cmd_type = normalize_command_type(command.type)
                handler = self._registry.get(cmd_type)

            if handler is None:
                return SynapseResponse(
                    id=command.id,
                    success=False,
                    error=f"I don't recognize the command '{command.type}' \u2014 try get_help to see what's available",
                    sequence=command.sequence,
                )

            _t0 = time.perf_counter()
            # R-012: record the history this handler started from BEFORE this
            # command can add to it, so a SYNAPSE group this session creates
            # counts as this session's. hou.undos is read on Houdini's main
            # thread only: inline when already there, otherwise through
            # run_on_main (the WebSocket route runs handle() on its own
            # thread). History commands capture inside their own main-thread
            # call instead (_history_step), before they judge.
            # Read-only commands (the kill switches among them) and farm
            # controls author no scene step, so they never wait on a capture.
            # Render and hands-off-render polls read a registry, never the
            # scene, and must not wait on a busy main thread.
            _poll_payload = command.payload if isinstance(command.payload, dict) else {}
            _is_poll = ((cmd_type == "render" and bool(_poll_payload.get("poll")))
                        or (cmd_type == "autonomous_render"
                            and bool(_poll_payload.get("task_id"))))
            if (cmd_type not in ("undo", "redo")
                    and cmd_type not in _READ_ONLY_COMMANDS
                    and cmd_type not in FARM_CONTROL_COMMANDS
                    and not _is_poll):
                scope = getattr(self, "_undo_scope", None)
                if scope is not None and scope.needs_baseline and HOU_AVAILABLE:
                    if threading.current_thread() is threading.main_thread():
                        scope.note_session_start(hou.undos)
                    else:
                        try:
                            from .main_thread import run_on_main
                            run_on_main(
                                lambda: scope.note_session_start(hou.undos),
                                timeout=2.0, record_stall=False, record_wait=False,
                                label="history:baseline")
                        except Exception as exc:  # noqa: BLE001 -- retried on the next command
                            scope.capture_failures += 1
                            (_log.warning if scope.capture_failures == 1 else _log.debug)(
                                "undo baseline capture deferred: %s", exc)
            # C5: serialize mutating commands across clients (skip on the main
            # thread — already serialized there, and locking would deadlock
            # run_on_main). Read-only commands never contend.
            _mutating = cmd_type not in _READ_ONLY_COMMANDS
            # A render POLL is a registry read riding the "render" command
            # name (crucible F3): treat it as read-only so it skips the C5
            # lock AND the live integrity envelope — during an active render
            # each envelope scene-hash capture would block against the busy
            # main thread and log a phantom "LIVE mutation" block per poll.
            if (cmd_type == "render" and isinstance(command.payload, dict)
                    and command.payload.get("poll")):
                _mutating = False
            _serialize = (_mutating and cmd_type not in FARM_CONTROL_COMMANDS
                          and threading.current_thread() is not threading.main_thread())
            _lock_cm = _MUTATION_LOCK if _serialize else contextlib.nullcontext()
            # Live-path integrity envelope: cheap topo hashes bracketing the
            # mutation, INSIDE the C5 lock so the pair is adjacent to exactly
            # this op. Observe-only: never wraps, never gates (D1 pinned),
            # never Flattens (include_stage=False in the capture). Decided on
            # the calling thread — the bridge-routed TLS suppression flag does
            # not survive the hop to the log executor.
            # batch_commands: its inner sub-ops dispatch through
            # registry.invoke() directly and bypass handle(), so a batch gets
            # ONE envelope block bracketing the whole batch — inherent to
            # this seam, documented on purpose.
            _enveloped = _mutating and _envelope.envelope_active(cmd_type)
            _hash_before = _hash_after = None
            # Route through invoke() so the FloorGate records Tier-0 provenance
            # for mutating ops (additive — does not replace _submit_logs below).
            with _lock_cm:
                if _enveloped:
                    _hash_before = _envelope.capture_scene_hash(command.payload)
                from ..host.memory_loop import observe_operation
                result = observe_operation(cmd_type, command.payload, lambda: self._registry.invoke(
                    cmd_type, command.payload,
                    ctx=FloorContext(session=self._session_id, origin="handler"),
                ))
                # A before-capture miss (busy main thread) already forces the
                # hash_unavailable sentinel — no delta is computable, so skip
                # the after-capture rather than hold the C5 lock up to another
                # full capture-timeout (halves the stuck-main worst case).
                if _enveloped and _hash_before is not None:
                    _hash_after = _envelope.capture_scene_hash(command.payload)
            self._record_tool_duration(cmd_type, (time.perf_counter() - _t0) * 1000.0)

            # Log action asynchronously — don't block the response path
            if _mutating:
                self._submit_logs(cmd_type, command.payload, result,
                                  hash_before=_hash_before,
                                  hash_after=_hash_after,
                                  enveloped=_enveloped)

            return SynapseResponse(
                id=command.id,
                success=True,
                data=result,
                sequence=command.sequence,
            )

        except SynapseUserError as e:
            # User errors: bad input, missing node, bad parm. Don't trip CB.
            if _enveloped:
                self._record_live_failure(cmd_type, command.payload, _hash_before)
            return SynapseResponse(
                id=command.id,
                success=False,
                data=_failure_receipt_data(e),
                error=str(e),
                sequence=command.sequence,
            )
        except ValueError as e:
            # Legacy ValueError path -- still user error, don't trip CB.
            # A ParmWriteRefused carries the structured write receipt the
            # caller needs to tell "not attempted" from "applied but
            # unverified"; keep it beside the human error, never instead of it.
            if _enveloped:
                self._record_live_failure(cmd_type, command.payload, _hash_before)
            return SynapseResponse(
                id=command.id,
                success=False,
                data=_failure_receipt_data(e),
                error=str(e),
                sequence=command.sequence,
            )
        except SynapseServiceError as e:
            # Service errors: Houdini down, execution crash. DO trip CB.
            # A typed subclass (ExecutionAborted, ExecutionDeadlineExceeded)
            # carries its outcome here, so the wire type survives (BRAINSTEM-3/4).
            if _enveloped:
                self._record_live_failure(cmd_type, command.payload, _hash_before)
            return SynapseResponse(
                id=command.id,
                success=False,
                data=_failure_receipt_data(e),
                error=str(e),
                sequence=command.sequence,
            )
        except Exception as e:
            # BRAINSTEM-5: a main-thread timeout is NOT a definite failure. The
            # payload may have started and may still be running, so this is an
            # unknown outcome that tells the caller to check the scene — never
            # the old generic "failed / Hit a snag" that invited a blind retry.
            # A read changes nothing, so a read that timed out stays retryable.
            # The class is resolved from the LIVE main_thread module (as
            # run_on_main itself does) so a reload cannot split the identity.
            # R-013: a failed live mutation is recorded in the integrity trail
            # here — this arm and the ones above return before _submit_logs.
            if _enveloped:
                self._record_live_failure(cmd_type, command.payload, _hash_before)
            from .main_thread import MainThreadTimeout as _LiveMainThreadTimeout
            if isinstance(e, _LiveMainThreadTimeout):
                _timeout_code = (
                    "transport.read_retry" if cmd_type in _READ_ONLY_COMMANDS
                    else "transport.timeout"
                )
                # R-034: a timed-out batch carries a structured receipt naming
                # which steps ran. It rides the same generic failure slot as
                # every other handler exception; the outcome stays the
                # authoritative timeout classification.
                _timeout_data = _failure_receipt_data(e) or {}
                _timeout_data["outcome"] = _outcome_info(
                    _timeout_code, str(e)).to_dict()
                return SynapseResponse(
                    id=command.id,
                    success=False,
                    data=_timeout_data,
                    error=str(e),
                    sequence=command.sequence,
                )
            # A setter can fail with an exception that is not a ValueError
            # (hou.OperationFailed is a RuntimeError). The receipt rides on the
            # exception; dropping it here is what lost the record for exactly
            # the failures that reached Houdini and failed.
            return SynapseResponse(
                id=command.id,
                success=False,
                data=_failure_receipt_data(e),
                error=f"Hit a snag processing that request: {e}",
                sequence=command.sequence,
            )
        except BaseException as exc:  # noqa: BLE001 -- PyO3's PanicException is a BaseException
            # L-PANIC-WS.1: PyO3 raises a Rust panic as pyo3_runtime.PanicException,
            # which no arm above sees. Answer it under this request's id so the
            # caller gets a reply; re-raise everything else (KeyboardInterrupt,
            # SystemExit, GeneratorExit, asyncio.CancelledError) unchanged.
            try:
                from ..memory.native_panic import is_native_panic
            except Exception:
                _log.error("could not load the native-panic classifier; re-raising", exc_info=True)
                raise exc from None
            if not is_native_panic(exc):
                raise
            # R-013: this is a failed live mutation like any other arm's.
            if _enveloped:
                self._record_live_failure(cmd_type, command.payload, _hash_before)
            _log.error(
                "A native (Rust) extension panicked while handling %r (%s: %s); "
                "answering this request with an error",
                command.type, type(exc).__name__, exc,
                exc_info=True,
            )
            return SynapseResponse(
                id=command.id,
                success=False,
                sequence=command.sequence,
                error=(
                    "A native (Rust) extension panicked while handling '%s' (%s: %s). "
                    "SYNAPSE kept running and answered this request. If Moneta's "
                    "native module is loaded, MONETA_NATIVE=0 set before Houdini "
                    "starts keeps it out." % (command.type, type(exc).__name__, exc)
                ),
            )

    def _submit_logs(self, cmd_type: str, payload: Dict, result: Any,
                     hash_before: Optional[str] = None,
                     hash_after: Optional[str] = None,
                     enveloped: bool = False):
        """Submit bridge + audit log in a single executor call."""
        # R-013 (SUBSTRATE-7): measure the Thread Safety anchor on the thread
        # that just executed the command. The log executor is off-main by
        # construction, so sampling there could never describe the operation.
        executed_on_main = threading.current_thread() is threading.main_thread()
        # Detached farm control must not initialize the artist memory store
        # from a transport worker. Its journal and the audit below own history.
        bridge = None if cmd_type in FARM_CONTROL_COMMANDS else self._get_bridge()
        sid = self._session_id
        uid = self._user_id
        category = _CMD_CATEGORY.get(cmd_type, AuditCategory.SYNAPSE)
        output = result if isinstance(result, dict) else {}
        memory_owner = getattr(bridge, "_synapse", None)
        memory_binding = getattr(memory_owner, "_memory_binding", None)

        def _do_log():
            if bridge and sid:
                def log_memory():
                    if (getattr(bridge, "_synapse", None) is not memory_owner
                            or getattr(memory_owner, "_memory_binding", None) != memory_binding):
                        raise RuntimeError("Scene changed before automatic memory logging")
                    bridge.log_action(f"Executed: {cmd_type}", session_id=sid)
                try:
                    from .main_thread import run_on_main
                    run_on_main(log_memory, label="memory:automatic_action")
                except Exception:
                    _log.warning("Automatic memory log unavailable; retaining audit entry", exc_info=True)
            audit_log().log(
                operation=cmd_type,
                message=f"Executed {cmd_type}",
                level=AuditLevel.AGENT_ACTION,
                category=category,
                user_id=uid,
                input_data=payload,
                output_data=output,
            )
            # Live-path integrity envelope: append the PATH-QUALIFIED
            # IntegrityBlock into the process-wide bridge trail. Fire-and-
            # forget isolation preserved: an envelope failure can never fail
            # the command (the response was already returned) or kill the
            # audit write above.
            if enveloped:
                try:
                    _envelope.record_live_block(
                        cmd_type, payload, hash_before, hash_after,
                        main_thread_executed=executed_on_main)
                except Exception:
                    _log.debug("live integrity envelope record failed",
                               exc_info=True)

        _log_executor.submit(_do_log)

    def _record_live_failure(self, cmd_type: str, payload: Dict,
                             hash_before: Optional[str]) -> None:
        """Record a FAILED enveloped live command in the integrity trail.

        R-013 (SUBSTRATE-7): handle()'s except arms return before
        ``_submit_logs`` is reached, so before this the trail could only ever
        contain successes — a live handler that failed every call still
        reported a perfect LIVE success rate and zero anchor violations.
        This appends a ``success=False`` block (no after-hash: the command
        raised before the post-state was observed) on the same fire-and-forget
        executor as the success path. It never raises: on the failure path the
        command's own error must reach the caller unmasked.
        """
        # Measured on the dispatch thread, before the hop to the executor
        # (same anchor evidence as the success path).
        executed_on_main = threading.current_thread() is threading.main_thread()

        def _do_record():
            try:
                _envelope.record_live_block(
                    cmd_type, payload, hash_before, None,
                    success=False,
                    main_thread_executed=executed_on_main)
            except Exception:
                # An observe-only record can never mask the command's error.
                _log.debug("live integrity envelope failure record failed",
                           exc_info=True)

        try:
            _log_executor.submit(_do_record)
        except Exception:
            # Executor shut down (interpreter exit): the response still goes out.
            _log.debug("could not submit live failure record", exc_info=True)

    def _register_handlers(self):
        """Register all built-in command handlers."""
        reg = self._registry

        # Utility
        reg.register("ping", self._handle_ping)
        reg.register("get_health", self._handle_get_health)
        reg.register("doctor", self._handle_doctor)
        reg.register("get_help", self._handle_get_help)

        # Node operations
        reg.register("create_node", self._handle_create_node)
        reg.register("delete_node", self._handle_delete_node)
        reg.register("connect_nodes", self._handle_connect_nodes)
        reg.register("network_explain", self._handle_network_explain)

        # Parameters
        reg.register("get_parm", self._handle_get_parm)
        reg.register("set_parm", self._handle_set_parm)

        # Scene
        reg.register("get_scene_info", self._handle_get_scene_info)
        reg.register("get_selection", self._handle_get_selection)

        # Execution
        reg.register("execute_python", self._handle_execute_python)
        reg.register("execute_vex", self._handle_execute_vex)

        # Reports — pure off-main-thread file write (never blocked by the main thread)
        reg.register("write_report", self._handle_write_report)

        # USD/Solaris
        reg.register("get_stage_info", self._handle_get_stage_info)
        reg.register("get_usd_attribute", self._handle_get_usd_attribute)
        reg.register("set_usd_attribute", self._handle_set_usd_attribute)
        reg.register("set_usd_primvar", self._handle_set_usd_primvar)
        reg.register("create_usd_prim", self._handle_create_usd_prim)
        reg.register("modify_usd_prim", self._handle_modify_usd_prim)

        # Viewport / Render
        reg.register("capture_viewport", self._handle_capture_viewport)
        # Tool-level renders go through the guarded/bounded wrapper (Indie
        # fix): foreground guard + single-flight + wait_budget_s token flow.
        # Internal orchestrators still call _handle_render directly.
        reg.register("render", self._handle_render_bounded)

        # TOPs / PDG wedging
        reg.register("wedge", self._handle_wedge)

        # TOPS / PDG (Phase 1)
        reg.register("tops_get_work_items", self._handle_tops_get_work_items)
        reg.register("tops_get_dependency_graph", self._handle_tops_get_dependency_graph)
        reg.register("tops_get_cook_stats", self._handle_tops_get_cook_stats)
        reg.register("tops_cook_node", self._handle_tops_cook_node)
        reg.register("tops_generate_items", self._handle_tops_generate_items)

        # TOPS / PDG (Phase 2)
        reg.register("tops_configure_scheduler", self._handle_tops_configure_scheduler)
        reg.register("tops_cancel_cook", self._handle_tops_cancel_cook)
        reg.register("tops_pause_cook", self._handle_tops_pause_cook)
        reg.register("tops_resume_cook", self._handle_tops_resume_cook)
        reg.register("tops_dirty_node", self._handle_tops_dirty_node)

        # TOPS / PDG (Phase 3)
        reg.register("tops_setup_wedge", self._handle_tops_setup_wedge)
        reg.register("tops_batch_cook", self._handle_tops_batch_cook)
        reg.register("tops_query_items", self._handle_tops_query_items)

        # TOPS / PDG (Phase 4: Autonomous Operations)
        reg.register("tops_cook_and_validate", self._handle_tops_cook_and_validate)
        reg.register("tops_diagnose", self._handle_tops_diagnose)
        reg.register("tops_pipeline_status", self._handle_tops_pipeline_status)

        # TOPS / PDG (Phase 5: Streaming & Render Integration)
        reg.register("tops_monitor_stream", self._handle_tops_monitor_stream)
        reg.register("tops_render_sequence", self._handle_tops_render_sequence)
        reg.register("tops_multi_shot", self._handle_tops_multi_shot)

        # USD scene assembly (reference / sublayer / payload) + prim queries
        reg.register("reference_usd", self._handle_reference_usd)
        reg.register("set_payload_loadstate", self._handle_set_payload_loadstate)
        reg.register("create_point_instancer", self._handle_create_point_instancer)
        reg.register("shot_render_ready", self._handle_shot_render_ready)
        reg.register("query_prims", self._handle_query_prims)
        reg.register("manage_variant_set", self._handle_manage_variant_set)
        reg.register("manage_collection", self._handle_manage_collection)
        reg.register("configure_light_linking", self._handle_configure_light_linking)

        # Solaris ordering validation
        reg.register("solaris_validate_ordering", self._handle_solaris_validate_ordering)

        # Solaris auto-assembly
        reg.register("solaris_assemble_chain", self._handle_solaris_assemble_chain)
        reg.register("solaris_build_graph", self._handle_solaris_build_graph)
        reg.register("layout_network", self._handle_layout_network)

        # Solaris NodeFlow tool family (SR1 M1; import_megascans added M5
        # once Ruling 13's F9 + F3 conditions were repaired and live-proven
        # on 22.0.368). All five resolve through the registry. Pinned by
        # tests/test_solaris_tool_registration.py.
        reg.register("solaris_component_builder", self._handle_solaris_component_builder)
        reg.register("solaris_scene_template", self._handle_solaris_scene_template)
        reg.register("solaris_create_variants", self._handle_solaris_create_variants)
        reg.register("solaris_set_purpose", self._handle_solaris_set_purpose)
        reg.register("solaris_import_megascans", self._handle_solaris_import_megascans)

        # Solaris compose tier (PRD 7.1/7.2/7.3)
        reg.register("solaris_shotsetup_karma_xpu", self._handle_solaris_shotsetup_karma_xpu)
        reg.register("matlib_bind", self._handle_matlib_bind)
        reg.register("assess_render_ready", self._handle_assess_render_ready)

        # Spatial lane (D6, R-5): the camera path read and its trail. Exactly
        # these two; describe/classify/frustum stay unregistered (rule D-1,
        # pinned by tests/test_spatial_tools.py).
        reg.register("get_spatial_path", self._handle_get_spatial_path)
        reg.register("spatial_trail", self._handle_spatial_trail)

        # Keyframe / Render Settings
        reg.register("set_keyframe", self._handle_set_keyframe)
        reg.register("render_settings", self._handle_render_settings)

        # Materials
        reg.register("create_material", self._handle_create_material)
        reg.register("create_textured_material", self._handle_create_textured_material)
        reg.register("assign_material", self._handle_assign_material)
        reg.register("read_material", self._handle_read_material)

        # Render passes / AOVs
        reg.register("configure_render_passes", self._handle_configure_render_passes)

        # Quality validation
        reg.register("validate_frame", self._handle_validate_frame)

        # Render farm
        reg.register("render_sequence", self._handle_render_sequence)
        reg.register("render_farm_status", self._handle_render_farm_status)
        reg.register("render_farm_cancel", self._handle_render_farm_cancel)

        # Durable detached TOPs jobs, also used directly by the Render view.
        for command in sorted(FARM_READ_COMMANDS | FARM_CONTROL_COMMANDS):
            reg.register(command, getattr(self, "_handle_" + command))

        # H3b -- background-render stop (rps/rkill) + emergency halt
        reg.register("render_processes", self._handle_render_processes)
        reg.register("render_stop", self._handle_render_stop)
        reg.register("emergency_halt", self._handle_emergency_halt)

        # Safe / progressive render
        reg.register("safe_render", self._handle_safe_render)
        reg.register("render_progressively", self._handle_render_progressively)

        # Knowledge lookup (RAG)
        reg.register("knowledge_lookup", self._handle_knowledge_lookup)

        # Introspection (Phase 1)
        reg.register("inspect_selection", self._handle_inspect_selection)
        reg.register("inspect_scene", self._handle_inspect_scene)
        reg.register("inspect_node", self._handle_inspect_node)

        # Resource-aware cache advisor (Mile 4, Phase 1, R-CACHE-1) -- read-only,
        # feature-flagged off by default (SYNAPSE_CACHE_ADVISOR_ENABLED).
        reg.register("assess_cache", self._handle_assess_cache)
        # Resource-aware cache INSERTION (R-CACHE-1 Phase 2, buildable half) -- an undoable
        # graph mutation (create+wire a File Cache SOP; sets the path parm, writes no disk).
        # Feature-flagged off by default (shares SYNAPSE_CACHE_ADVISOR_ENABLED). NOT read-only:
        # deliberately absent from _READ_ONLY_COMMANDS so it takes the C5 mutation lock and a
        # live PATH-QUALIFIED IntegrityBlock envelope like any other mutation.
        reg.register("insert_cache", self._handle_insert_cache)

        # Batch
        reg.register("batch_commands", self._handle_batch_commands)

        # Metrics / Router stats / Recipes
        reg.register("get_metrics", self._handle_get_metrics)
        reg.register("router_stats", self._handle_router_stats)
        reg.register("list_recipes", self._handle_list_recipes)
        reg.register("get_live_metrics", self._handle_get_live_metrics)

        # Memory operations (new names)
        reg.register("context", self._handle_memory_context)
        reg.register("search", self._handle_memory_search)
        reg.register("add_memory", self._handle_memory_add)
        reg.register("decide", self._handle_memory_decide)
        reg.register("recall", self._handle_memory_recall)

        # Scene memory operations (Living Memory)
        reg.register("project_setup", self._handle_project_setup)
        reg.register("memory_write", self._handle_memory_write)
        reg.register("memory_query", self._handle_memory_query)
        reg.register("memory_status", self._handle_memory_status)
        reg.register("sleep_pass", self._handle_sleep_pass)

        # Autonomous render pipeline
        reg.register("autonomous_render", self._handle_autonomous_render)

        # HDA operations
        reg.register("hda_create", self._handle_hda_create)
        reg.register("hda_promote_parm", self._handle_hda_promote_parm)
        reg.register("hda_set_help", self._handle_hda_set_help)
        reg.register("hda_package", self._handle_hda_package)
        reg.register("hda_list", self._handle_hda_list)

        # Copernicus (COPs) — Foundation
        reg.register("cops_create_network", self._handle_cops_create_network)
        reg.register("cops_create_copnet", self._handle_cops_create_copnet)
        reg.register("cops_create_node", self._handle_cops_create_node)
        reg.register("cops_connect", self._handle_cops_connect)
        reg.register("cops_set_opencl", self._handle_cops_set_opencl)
        reg.register("cops_read_layer_info", self._handle_cops_read_layer_info)

        # Copernicus (COPs) — Pipeline Integration
        reg.register("cops_to_materialx", self._handle_cops_to_materialx)
        reg.register("cops_composite_aovs", self._handle_cops_composite_aovs)
        reg.register("cops_analyze_render", self._handle_cops_analyze_render)
        reg.register("cops_slap_comp", self._handle_cops_slap_comp)

        # Copernicus (COPs) — Procedural & Motion Design
        reg.register("cops_create_solver", self._handle_cops_create_solver)
        reg.register("cops_procedural_texture", self._handle_cops_procedural_texture)
        reg.register("cops_growth_propagation", self._handle_cops_growth_propagation)
        reg.register("cops_reaction_diffusion", self._handle_cops_reaction_diffusion)
        reg.register("cops_pixel_sort", self._handle_cops_pixel_sort)
        reg.register("cops_stylize", self._handle_cops_stylize)

        # Copernicus (COPs) — Advanced
        reg.register("cops_wetmap", self._handle_cops_wetmap)
        reg.register("cops_bake_textures", self._handle_cops_bake_textures)
        reg.register("cops_temporal_analysis", self._handle_cops_temporal_analysis)
        reg.register("cops_stamp_scatter", self._handle_cops_stamp_scatter)
        reg.register("cops_batch_cook", self._handle_cops_batch_cook)

        # Undo / Redo
        reg.register("undo", self._handle_undo)
        reg.register("redo", self._handle_redo)

        # Graph synthesis — BOTH halves run in THIS Houdini process and share
        # this process's single ProposalStore: propose validates against the
        # live runtime + parks an id; instantiate builds that parked id.
        reg.register("propose_graph", self._handle_propose_graph)
        reg.register("instantiate_graph", self._handle_instantiate_graph)

        # Pre-populate alias names so dispatch never needs normalization.
        # Build reverse map: canonical_name -> [alias1, alias2, ...]
        _canonical_to_aliases: Dict[str, list] = {}
        for alias, canonical in COMMAND_ALIASES.items():
            _canonical_to_aliases.setdefault(canonical, []).append(alias)
        for canonical, aliases in _canonical_to_aliases.items():
            handler = reg.get(canonical)
            if handler is not None:
                for alias in aliases:
                    if not reg.has(alias):
                        reg.register(alias, handler)

    # =========================================================================
    # UTILITY HANDLERS
    # =========================================================================

    def _handle_ping(self, payload: Dict) -> Dict:
        """Handle ping command."""
        return {
            "pong": True,
            "timestamp": time.time(),
            "protocol_version": PROTOCOL_VERSION,
        }

    def _handle_get_health(self, payload: Dict) -> Dict:
        """Handle health check command.

        ``write_plane`` is ADDITIVE (see ``server/write_plane.py``): the three
        pre-existing keys keep their exact meanings so no consumer breaks.
        ``healthy`` deliberately stays a liveness answer — a degraded write
        plane is reported in its own field rather than by redefining a key
        other code already reads.

        ``readiness`` is ADDITIVE too: the Level 1 preflight (R-5), ready,
        degraded (reads only) or blocked, with each check and its fix
        (``server/preflight_gate.py``). The stdio bridge sends its SYNAPSE
        version as ``client_version`` so the version check can run.

        ``memory_binding`` is ADDITIVE (R-031): the last failed Save As / load
        memory carry, or ``None`` when none is pending. It is a pure attribute
        read on the process memory owner — no ``hou``, no store — so health can
        answer it on every path, including when the store itself is unreachable.
        """
        from ..host.memory_lifecycle import pending_binding_report
        from .preflight_gate import readiness
        from .write_plane import write_plane_state

        client_version = payload.get("client_version") if isinstance(payload, dict) else None
        return {
            "healthy": True,
            "houdini_available": HOU_AVAILABLE,
            "protocol_version": PROTOCOL_VERSION,
            "write_plane": write_plane_state(),
            "memory_binding": pending_binding_report(),
            "readiness": readiness(
                client_version=client_version if isinstance(client_version, str) else None),
        }

    def _handle_get_help(self, payload: Dict) -> Dict:
        """Handle help command."""
        return {
            "protocol_version": PROTOCOL_VERSION,
            "commands": self._registry.registered_types,
            "description": "Synapse AI-Houdini Bridge v" + PROTOCOL_VERSION,
        }

    def _handle_doctor(self, payload: Dict) -> Dict:
        """Install/ops diagnostics + optional bundle (M3-C). Logic in doctor.py."""
        from .doctor import run_doctor
        return run_doctor(payload, handler=self)

    # =========================================================================
    # UNDO / REDO HANDLERS
    # =========================================================================

    def _handle_undo(self, payload: Dict) -> Dict:
        """Undo SYNAPSE's own last recorded step.

        Reads hou.undos.undoLabels() and refuses unless the next step is a
        SYNAPSE group recorded in this session (R-012): the global history may
        hold the artist's own edit, and an agent must never take that back.
        The refusal names the top label. No parameters required.
        """
        self._history_step("undo")
        return {"status": "ok", "message": "Undid last operation"}

    def _handle_redo(self, payload: Dict) -> Dict:
        """Redo SYNAPSE's own last undone step.

        Reads hou.undos.redoLabels() and refuses unless the next step is a
        SYNAPSE group recorded in this session (R-012). The refusal names the
        top label. No parameters required.
        """
        self._history_step("redo")
        return {"status": "ok", "message": "Redid last undone operation"}

    def _history_step(self, direction: str) -> None:
        """Judge and take one history step in ONE main-thread call.

        The refusal and performUndo/performRedo run together on Houdini's
        main thread, so an artist edit cannot land between the check and the
        step, and hou.undos is never read off the main thread. A call that
        arrives before any baseline captures one first, so every step
        already present counts as pre-session and is refused.
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError(_HOUDINI_UNAVAILABLE)
        from .main_thread import run_on_main
        scope = self._undo_scope

        def _judge_and_step():
            if scope.needs_baseline:
                scope.note_session_start(hou.undos)
            refusal = scope.refusal(hou.undos, direction)
            if refusal:
                raise HistoryScopeRefused(refusal)
            before = undo_history(hou.undos)
            if direction == "undo":
                hou.undos.performUndo()
            else:
                hou.undos.performRedo()
            scope.note_agent_step(direction, before, undo_history(hou.undos))

        run_on_main(_judge_and_step, label="history:%s" % direction)

    # =========================================================================
    # BATCH HANDLER
    # =========================================================================

    def _handle_batch_commands(self, payload: Dict) -> Dict:
        """Execute a batch of commands in declared order.

        Payload:
            commands: list of {type: str, payload: dict}
            atomic: accepted for compatibility but cannot disable grouping
            stop_on_error: bool (default False) -- halt on first error
            batch_id: optional stable id. A retry that reuses it skips every
                step this handler already recorded ok; when absent one is
                generated and returned in the result as ``batch_id``.

        R-012 (SIDEFXCTO-2): ``synapse_batch`` is model-reachable and the live
        ``/synapse`` handlers are not bridge-routed, so a batch payload must not
        be able to turn undo grouping off. Two enforcements, both structural:

        * the undo toggle (``atomic`` / ``use_undo``) is stripped from every
          sub-command payload before ``registry.invoke`` -- execute_python then
          takes its default (grouped, one ``synapse_execute`` entry); a nested
          batch re-applies the same strip at its own dispatch.
        * the envelope group opens whenever Houdini is available, whatever the
          payload's ``atomic`` says -- execute_vex has no group of its own, and
          the other mutating handlers depend on their own inline group either
          way. The old flag could only ever skip this group; that skip was the
          bypass.

        R-034 (CONDUCTOR-7): a timed-out batch neither keeps issuing steps nor
        replays on retry. Every step leaves a receipt before and after it runs
        (``server/batch_receipts.py``); the caller, the marshal and the step
        loop share ONE budget from ``core/timeouts.py`` -- the shipped
        ``batch_commands`` value -- so no layer gives up while another still
        considers the batch live. The loop checks that deadline before issuing
        each step, and a caller whose wait expired is told which steps ran. A
        step that was in flight is reported ``unknown``, never ``failed``: it
        may still be changing the scene. A retry with the same ``batch_id``
        skips the steps already recorded ok; a step left in flight is not
        re-executed (a new batch id is the explicit way to start over).
        """
        commands = payload.get("commands")
        if not commands or not isinstance(commands, list):
            raise ValueError("'commands' must be a non-empty list")
        if any(isinstance(item, dict) and normalize_command_type(item.get("type", ""))
               in ((FARM_CONTROL_COMMANDS | FARM_READ_COMMANDS) - {"farm_inspect"}) for item in commands):
            raise ValueError("Use render preparation, submission and status tools as separate requests, outside a scene-edit batch.")
        if any(isinstance(item, dict) and normalize_command_type(item.get("type", ""))
               in ("undo", "redo") for item in commands):
            raise ValueError("Undo and Redo step through Houdini's existing history, which a batch's own undo group would change. Send them as separate requests, outside a batch.")

        stop_on_error = payload.get("stop_on_error", False)

        # R-034: the batch id is the resume key. A caller may choose it (so a
        # retry after a lost reply can present it) or let us generate one and
        # read it back from the result / timeout receipt.
        batch_id = payload.get("batch_id")
        if batch_id in (None, ""):
            batch_id = new_batch_id()
        elif not isinstance(batch_id, str):
            raise ValueError("'batch_id' must be a string")
        elif len(batch_id) > 128:
            raise ValueError("'batch_id' must be 128 characters or fewer")
        try:
            receipts = _batch_store(self).get_or_create(batch_id, commands)
        except BatchIdConflict as conflict:
            # A reused id for a different command list is the caller's mistake,
            # not a service fault: answer it as a user error, unmasked.
            raise SynapseUserError(str(conflict)) from None

        from .main_thread import MainThreadTimeout
        from ..core.timeouts import timeout_for

        # ONE budget for the caller, the marshal and the step loop (C7). The
        # old 30 s marshal under a 60 s client budget let the payload keep
        # mutating for up to 30 s after the caller was told it timed out.
        budget = timeout_for("batch_commands")
        # Inline callers (panel, in-process) are synchronous: nobody stops
        # waiting for them, so there is no deadline to honour.
        deadline = None if _would_run_inline_on_main() else time.monotonic() + budget

        # The batch envelope's provenance record is the +1 emitted by the outer
        # handle()->invoke('batch_commands') wrap. Read THAT wrap's real op-id
        # (set on this thread's FloorGate context while _handle_batch_commands
        # runs as its handler) so each sub-op nests under the ACTUAL envelope
        # record — not a freshly-minted phantom id that references nothing.
        # Read here, on the handler thread, BEFORE run_on_main marshals the
        # sub-ops away (a contextvar would not survive that thread hop).
        batch_op_id = self._registry._floor_gate.current_op_id()
        batch_ctx = FloorContext(
            session=self._session_id, origin="batch", parent=batch_op_id,
        )

        def _on_main():
            results: list = []
            statuses: list = []
            errors: list = []
            resumed: list = []

            def _stop_remaining(start_index):
                # Positional parity: one slot per declared step, so the
                # receipt and any report line up with the declared list. Only
                # the R-034 paths reach this -- stop_on_error keeps its
                # shipped shape exactly.
                for index in range(start_index, len(commands)):
                    results.append(None)
                    statuses.append(STATUS_NOT_RUN)
                    errors.append("Step %d: not run -- the batch stopped "
                                  "before issuing it." % index)

            def _run_batch():
                # R-012: every alias that resolve_param() maps to the execute
                # handlers' undo toggle. Read live from the alias table, so a
                # future spelling (add_alias) cannot reopen this hole either.
                undo_toggle_keys = frozenset(
                    PARAM_ALIASES.get("atomic", ("atomic", "use_undo")))
                for i, cmd_spec in enumerate(commands):
                    state = receipts.status(i)
                    if state == STATUS_OK:
                        # Applied-step guard (R-034): this step completed on an
                        # earlier attempt. Reuse its recorded result -- never
                        # replay a mutation the scene already holds.
                        results.append(receipts.result(i))
                        statuses.append(STATUS_OK)
                        errors.append(None)
                        resumed.append(i)
                        continue
                    if state in (STATUS_IN_PROGRESS, STATUS_UNKNOWN):
                        # It was mid-flight when an earlier attempt's caller
                        # stopped waiting and no outcome was recorded. It may
                        # have mutated, so it is NOT re-run; stopping here also
                        # avoids applying later steps that may depend on it.
                        note = ("Step %d: state unknown — an earlier attempt "
                                "had it in flight when its caller stopped "
                                "waiting. Not re-run: it may already have "
                                "changed the scene." % i)
                        receipts.finish_unknown(i, note)
                        results.append(None)
                        statuses.append(STATUS_UNKNOWN)
                        errors.append(note)
                        _stop_remaining(i + 1)
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        # The caller has stopped waiting. The in-flight step is
                        # the accepted residual; no NEW step is issued.
                        _stop_remaining(i)
                        break
                    if not isinstance(cmd_spec, dict):
                        # Malformed step: fail it as data, never let it reach
                        # a handler or the grouping decision.
                        err = f"Step {i}: command entry must be an object"
                        receipts.finish_error(i, err)
                        errors.append(err)
                        statuses.append(STATUS_ERROR)
                        results.append(None)
                        if stop_on_error:
                            break
                        continue
                    cmd_type = cmd_spec.get("type", "")
                    cmd_payload = cmd_spec.get("payload", {})
                    if isinstance(cmd_payload, dict):
                        # R-012: a sub-command may not opt out of undo grouping.
                        # Copy -- the caller's payload is left as sent.
                        cmd_payload = {
                            key: value for key, value in cmd_payload.items()
                            if key not in undo_toggle_keys
                        }
                    handler = self._registry.get(cmd_type)

                    if handler is None:
                        err = f"Step {i}: unknown command '{cmd_type}'"
                        receipts.finish_error(i, err)
                        errors.append(err)
                        statuses.append(STATUS_ERROR)
                        results.append(None)
                        if stop_on_error:
                            break
                        continue

                    receipts.begin(i)
                    try:
                        # Route through invoke() so each sub-op emits its own
                        # provenance record nested under the batch envelope.
                        result = self._registry.invoke(
                            cmd_type, cmd_payload, ctx=batch_ctx,
                        )
                        receipts.finish_ok(i, result)
                        results.append(result)
                        statuses.append(STATUS_OK)
                        errors.append(None)
                    except Exception as e:
                        receipts.finish_error(i, f"Step {i}: {e}")
                        results.append(None)
                        statuses.append(STATUS_ERROR)
                        errors.append(f"Step {i}: {e}")
                        if stop_on_error:
                            break

            if HOU_AVAILABLE:
                # R-012: not conditional on the payload's `atomic` -- see the
                # handler docstring. A model-reachable batch may not skip the
                # group that makes its work one artist Ctrl+Z.
                with hou.undos.group("synapse_batch"):
                    _run_batch()
            else:
                _run_batch()

            if STATUS_UNKNOWN in statuses:
                batch_status = "in_progress"
            elif STATUS_NOT_RUN in statuses:
                batch_status = "stopped"
            elif STATUS_ERROR in statuses:
                batch_status = "partial"
            else:
                batch_status = "complete"
            return {
                "results": results,
                "statuses": statuses,
                "errors": errors,
                "batch_id": batch_id,
                "batch_status": batch_status,
                "resumed": resumed,
            }

        try:
            return run_on_main_observed(
                _on_main, timeout=budget, label="batch_commands",
            )
        except MainThreadTimeout as exc:
            raise _batch_timeout_exception(
                batch_id, budget, receipts, exc) from None

    # =========================================================================
    # PARAMETER HANDLERS
    # =========================================================================

    def _handle_get_parm(self, payload: Dict) -> Dict:
        """Handle get_parm command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")

        from .main_thread import run_on_main
        from .parm_authored import authored_fields, authored_tuple_fields

        def _on_main():
            nonlocal parm_name
            node = hou.node(node_path)
            if node is None:
                raise NodeNotFoundError(node_path)

            usd_encoded = USD_PARM_ALIASES.get(parm_name.lower())

            parm = node.parm(parm_name)
            # USD alias fallback -- resolve human-readable name to encoded parm
            if parm is None and usd_encoded:
                parm = node.parm(usd_encoded)
                if parm is not None:
                    parm_name = usd_encoded  # use resolved name in response
            if parm is None:
                # Try as parm tuple. USD color3f/vector attrs (e.g. inputs:color)
                # surface as a parmTuple under the ENCODED name, not a scalar parm
                # -- so try the encoded alias here too, not just the raw name.
                parm_tuple = node.parmTuple(parm_name)
                if parm_tuple is None and usd_encoded:
                    parm_tuple = node.parmTuple(usd_encoded)
                    if parm_tuple is not None:
                        parm_name = usd_encoded
                if parm_tuple is not None:
                    # hou.Parm.eval() reads parameter value -- not Python eval()
                    values = [p.eval() for p in parm_tuple]  # noqa: S307
                    return {
                        "node": node_path,
                        "parm": parm_name,
                        "value": values,
                        "is_tuple": True,
                        **authored_tuple_fields(parm_tuple, values),
                    }
                hint = _suggest_parms(node, parm_name)
                raise ParameterError(node_path, parm_name, suggestion=hint.strip() if hint else "")

            value = parm.eval()
            return {
                "node": node_path,
                "parm": parm_name,
                "value": value,
                "is_tuple": False,
                # The string as written, or the expression that drives the
                # parm, when it differs from the evaluated value (BP12 15).
                **authored_fields(parm, value),
            }

        return run_on_main(_on_main, label="handlers:_handle_get_parm")

    def _handle_set_parm(self, payload: Dict) -> Dict:
        """Handle set_parm command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")

        # Guard: reject NaN/Inf before they reach Houdini (they persist and corrupt)
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            bad = "NaN" if math.isnan(value) else "Infinity"
            raise ValueError(
                f"Can't set {parm_name} to {bad} — that would corrupt the "
                "parameter. Use a finite number instead."
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    bad = "NaN" if math.isnan(v) else "Infinity"
                    raise ValueError(
                        f"Can't set {parm_name} — element {i} is {bad}, which "
                        "would corrupt the parameter. Use finite numbers instead."
                    )

        from .main_thread import run_on_main
        from .parm_authored import (
            WRITE_MODES, ParmWriteRefused, author_parm_write, validate_expect,
            write_refusal,
        )

        # How a write meets an animated or referenced parm. Refusing is the
        # default: a plain set over an expression or a reference reports a
        # value the scene does not hold (H1-1).
        mode = payload.get("mode", "refuse")
        if mode not in WRITE_MODES:
            # A refusal is still a write outcome: it carries the same receipt
            # shape as a write that reached Houdini and failed, with a stable
            # code (see author_parm_write's own mode guard).
            raise write_refusal(
                f"Unknown mode {mode!r}. Use one of: {', '.join(WRITE_MODES)}. "
                "Nothing was written.",
                code="parm.mode_invalid",
                request={"request_id": payload.get("request_id"),
                         "node": node_path, "parm": parm_name,
                         "expected_session": getattr(self, "_session_id", None)},
                mode=mode, values=[value], frame=payload.get("frame"),
                queued=bool(payload.get("queued")),
                expect=payload.get("expect"))

        # Preflight the optional precondition before the main-thread hop, so an
        # unknown or malformed one refuses with zero setters and zero Houdini
        # work. A queued/evidence-derived mutation cannot fall through to
        # "whatever the playhead says".
        queued = payload.get("queued", False)
        frame = payload.get("frame")
        expect = payload.get("expect")
        request_context = {"request_id": payload.get("request_id"),
                           "node": node_path, "parm": parm_name,
                           # The session the write is authorized under. The
                           # session observed when it actually runs is added
                           # on the main thread; a mismatch is evidence.
                           "expected_session": getattr(self, "_session_id", None)}
        if not isinstance(queued, bool):
            raise write_refusal(
                "'queued' must be true or false. Nothing was written.",
                code="parm.precondition_invalid", request=request_context,
                mode=mode, values=[value], frame=frame, queued=bool(queued))
        if frame is not None and (isinstance(frame, bool)
                                  or not isinstance(frame, (int, float))):
            raise write_refusal(
                "'frame' must be a number. Nothing was written.",
                code="parm.precondition_invalid", request=request_context,
                mode=mode, values=[value], frame=None, queued=queued)
        # The precondition is validated before the hop, not merely counted. A
        # misspelled key ("value_typo") used to pass a truthiness test while
        # checking nothing, so the write landed unguarded and reported applied.
        try:
            validate_expect(expect)
        except ParmWriteRefused as exc:
            raise write_refusal(
                str(exc), code=exc.code, request=request_context, mode=mode,
                values=[value], frame=frame, queued=queued, expect=expect
            ) from None
        if queued and not expect:
            # A declared frame alone is not proof the scene is the one the
            # write was planned against: the playhead can be set to any frame
            # and the parm may have moved. A queued write carries the authored
            # state it was planned against, revalidated below on main.
            raise write_refusal(
                "A queued write needs an expected authored state (`expect`); "
                "a declared frame alone does not prove the scene is the one "
                "the write was planned against. Nothing was written.",
                code="parm.precondition_missing", request=request_context,
                mode=mode, values=[value], frame=frame, queued=queued)

        def _on_main():
            nonlocal parm_name
            # What the write ran under, read here and now. Never the
            # pre-hop values: a session can expire or switch between them.
            request_context["observed_session"] = getattr(
                self, "_session_id", None)
            try:
                request_context["observed_frame"] = hou.frame()
            except Exception as exc:
                # Best-effort context: the write still runs, and the receipt
                # records the frame as unknown rather than inventing one.
                _log.debug("observed frame unavailable for the receipt: %s", exc)
                request_context["observed_frame"] = None
            node = hou.node(node_path)
            if node is None:
                raise NodeNotFoundError(node_path)

            usd_encoded = USD_PARM_ALIASES.get(parm_name.lower())

            parm = node.parm(parm_name)
            # USD alias fallback -- resolve human-readable name to encoded parm
            if parm is None and usd_encoded:
                parm = node.parm(usd_encoded)
                if parm is not None:
                    parm_name = usd_encoded
            if parm is not None:
                # If value is a list/tuple but we found a scalar parm, try the
                # tuple parm instead — this lets callers set color (R,G,B) in one
                # call using the base name (e.g., "base_color" with [1,0,0]).
                # W5-UNDOB: one undo group around the parm write so a single
                # Ctrl+Z reverses it. Grouping only, NOT rollback — an exception
                # mid-write is not auto-reversed (matches handlers_node.py).
                if isinstance(value, (list, tuple)):
                    parm_tuple = node.parmTuple(parm_name)
                    if parm_tuple is not None and len(parm_tuple) > 1:
                        with hou.undos.group("synapse_set_parm"):
                            applied = author_parm_write(
                                list(parm_tuple), list(value), mode,
                                parm_tuple=parm_tuple,
                                request=request_context, frame=frame,
                                queued=queued, expect=expect)
                        return {"node": node_path, "parm": parm_name,
                                **applied, **undo_receipt("synapse_set_parm")}
                with hou.undos.group("synapse_set_parm"):
                    applied = author_parm_write(
                        [parm], [value], mode, request=request_context,
                        frame=frame, queued=queued, expect=expect)
                result = {"node": node_path, "parm": parm_name,
                          **applied, **undo_receipt("synapse_set_parm")}
                # Lighting Law: soft warning when intensity > 1.0 on light nodes
                if ("intensity" in parm_name.lower()
                        and isinstance(value, (int, float)) and value > 1.0):
                    try:
                        if "light" in node.type().name().lower():
                            result["warning"] = (
                                "Intensity is usually 1.0 — consider using "
                                "exposure for brightness control (Lighting Law)"
                            )
                    except Exception as e:
                        _log.debug("Lighting Law check skipped: %s", e)
                return result

            # Try as parm tuple. USD color3f/vector attrs (e.g. inputs:color)
            # surface as a parmTuple under the ENCODED name -- try the encoded
            # alias too, not just the raw name.
            parm_tuple = node.parmTuple(parm_name)
            if parm_tuple is None and usd_encoded:
                parm_tuple = node.parmTuple(usd_encoded)
                if parm_tuple is not None:
                    parm_name = usd_encoded
            if parm_tuple is not None:
                # W5-UNDOB: group the tuple write (grouping only, not rollback).
                values = (list(value) if isinstance(value, (list, tuple))
                          else [value] * len(parm_tuple))
                with hou.undos.group("synapse_set_parm"):
                    applied = author_parm_write(
                        list(parm_tuple), values, mode, parm_tuple=parm_tuple,
                        request=request_context, frame=frame, queued=queued,
                        expect=expect)
                result = {"node": node_path, "parm": parm_name,
                          **applied, **undo_receipt("synapse_set_parm")}
                # Lighting Law: soft warning when intensity > 1.0 on light nodes
                if ("intensity" in parm_name.lower()
                        and isinstance(value, (int, float)) and value > 1.0):
                    try:
                        if "light" in node.type().name().lower():
                            result["warning"] = (
                                "Intensity is usually 1.0 — consider using "
                                "exposure for brightness control (Lighting Law)"
                            )
                    except Exception as e:
                        _log.debug("Lighting Law check skipped: %s", e)
                return result

            hint = _suggest_parms(node, parm_name)
            raise ParameterError(node_path, parm_name, suggestion=hint.strip() if hint else "")

        return run_on_main(_on_main, label="handlers:_handle_set_parm")

    # =========================================================================
    # SCENE HANDLERS
    # =========================================================================

    def _handle_get_scene_info(self, payload: Dict) -> Dict:
        """Handle get_scene_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from .main_thread import run_on_main

        def _on_main():
            return {
                "hip_file": hou.hipFile.name(),
                "frame": int(hou.frame()),
                "fps": hou.fps(),
                "frame_range": [int(hou.playbar.frameRange()[0]), int(hou.playbar.frameRange()[1])],
            }

        return run_on_main(_on_main, label="handlers:_handle_get_scene_info")

    def _handle_get_selection(self, payload: Dict) -> Dict:
        """Handle get_selection command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from .main_thread import run_on_main

        def _on_main():
            selected = hou.selectedNodes()
            return {
                "count": len(selected),
                "nodes": [
                    {"path": n.path(), "type": n.type().name(), "name": n.name()}
                    for n in selected[:50]
                ],
            }

        return run_on_main(_on_main, label="handlers:_handle_get_selection")

    # =========================================================================
    # EXECUTION HANDLERS
    # =========================================================================

    def _handle_execute_python(self, payload: Dict) -> Dict:
        """
        Handle execute_python command.

        Executes Python code in Houdini's runtime environment.
        This is a standard DCC scripting pattern for automation.

        Scene mutations are grouped into one undo entry when atomic=True.
        Coding errors roll that group back once; operational errors keep
        partial work for the artist to undo. atomic=False runs ungrouped.
        Filesystem and network effects of executed code are never undone.

        Options:
            dry_run (bool): Compile-only syntax check -- no execution.
            atomic (bool): Wrap in one undo group; roll it back on coding
                errors only (default True). False runs ungrouped. Internal
                only: the MCP tool schema does not advertise it, and every
                registered transport builds its payload through
                _tool_registry, which never forwards it (R-012).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        code = resolve_param(payload, "content")
        dry_run = resolve_param_with_default(payload, "dry_run", False)
        atomic = resolve_param_with_default(payload, "atomic", True)

        # Compile first -- catches SyntaxError for both dry_run and real runs
        try:
            compiled = compile(code, "<synapse_exec>", "exec")
        except SyntaxError as e:
            if dry_run:
                return {"valid": False, "error": str(e), "dry_run": True}
            raise

        if dry_run:
            return {"valid": True, "dry_run": True}

        # Build execution namespace with Houdini access + idempotent guards
        exec_globals = {"hou": hou, "__builtins__": __builtins__}
        try:
            from .guards import GUARD_FUNCTIONS
            exec_globals.update(GUARD_FUNCTIONS)
        except ImportError:
            pass
        exec_locals: dict = {}

        from .main_thread import _SLOW_TIMEOUT
        from .deadline import DeadlineExceeded, run_under_deadline

        def _run_payload():
            """Execute the compiled script under the main-thread deadline.

            BRAINSTEM-3: SystemExit/KeyboardInterrupt/GeneratorExit raised by
            the exec frame are that call's failure, not a server-shutdown
            signal. This is the only place that knows the frame's provenance,
            so they are converted here; the transport-wide re-raise in
            ``handle()`` still covers genuine shutdown raised outside it.

            BRAINSTEM-4: ``run_under_deadline`` arms sys.settrace for the
            payload's own compiled unit, so a pure-Python loop is interruptible
            even when this payload is ALREADY on the main thread — where the
            run_on_main budget below is discarded (fast path 2). A C call is
            the documented residual (server/deadline.py).
            """
            try:
                run_under_deadline(
                    lambda: _run_compiled(compiled, exec_globals, exec_locals),
                    _SLOW_TIMEOUT, label="execute_python",
                    watch_filename="<synapse_exec>",
                )
            except (SystemExit, KeyboardInterrupt, GeneratorExit) as exc:
                raise ExecutionAborted(
                    "execute_python stopped: the script raised %s inside its "
                    "exec frame. The call may have run in part; check the scene "
                    "before trying again." % type(exc).__name__,
                ) from None

        def _on_main():
            # Execute inside undo group with smart rollback:
            # - Coding bugs (NameError, SyntaxError, TypeError, AttributeError)
            #   -> auto-rollback, since the script is broken and partial state is bad
            # - Operational errors (render timeout, file not found, hou.OperationFailed)
            #   -> keep mutations, since node creation/wiring may have succeeded
            # F1 freeze-relief: the update-mode sandwich sits INSIDE the
            # undo group (the probed nesting — probe item (c) opens
            # hou.undos.group across the sandwich, never the reverse).
            # Flag-off/headless = identical behavior to today.
            from .update_mode import cook_sandwich
            if atomic:
                _needs_rollback = False
                _rollback_exc = None
                _labels_before = _undo_labels_snapshot(hou)
                with hou.undos.group("synapse_execute"):
                    with cook_sandwich(label="execute_python"):
                        try:
                            _run_payload()
                        except _ROLLBACK_ERRORS as e:
                            # Don't call performUndo() inside the undo group —
                            # that raises "Cannot undo within an undo group".
                            # Instead, flag for rollback after the group closes.
                            _needs_rollback = True
                            _rollback_exc = e
                # Undo group is now closed — safe to roll back
                if _needs_rollback:
                    _rollback_if_group_left_entry(hou, _labels_before)
                    raise _rollback_exc
            else:
                with cook_sandwich(label="execute_python"):
                    _run_payload()

            # Try to extract a result variable. A script that SET `result` gets
            # that value back even when it is falsy: a measured 0 / False / []
            # is an answer, and must not read the same as "no result set".
            result = exec_locals.get("result", "executed")

            return {
                "executed": True,
                "result": str(result) if "result" in exec_locals else "executed",
            }

        # TIMEOUT CHOICE: _SLOW_TIMEOUT (30s), UNCHANGED -- this is the shipped
        # budget for arbitrary user code and off-main behaviour must not change.
        # On the /mcp path dispatch is ALREADY on the main thread, so run_on_main
        # takes fast path 2 and this 30s is discarded: the payload itself is now
        # bounded by the deadline inside _run_payload. A deadline that fires is
        # an explicit outcome that says the scene may be partial (BRAINSTEM-4),
        # never a silent overrun.
        try:
            return run_on_main_observed(
                _on_main, timeout=_SLOW_TIMEOUT, label="execute_python",
            )
        except DeadlineExceeded as exc:
            raise ExecutionDeadlineExceeded(str(exc)) from None

    def _handle_write_report(self, payload: Dict) -> Dict:
        """Write a report/file to a confined local dir — OFF the main thread.

        Writing a file under the reports dir is pure Python I/O (no ``hou``), so
        this handler runs the write directly on the handler thread and does NOT
        marshal through ``run_on_main`` / ``hdefereval``. It therefore completes
        even when Houdini's main thread is blocked by a modal dialog or an active
        cook — the failure mode that hangs ``execute_python``-based report writes.

        Base dir is resolved WITHOUT touching ``hou`` (so a blocked main thread
        can't stall it): ``$SYNAPSE_REPORTS_DIR`` if set, else ``<repo root>/docs``.
        The path is confined under that base (traversal rejected).
        """
        from synapse.cognitive.tools.write_report import write_report

        relative_path = resolve_param(payload, "relative_path")
        content = resolve_param(payload, "content")
        overwrite = resolve_param_with_default(payload, "overwrite", True)
        backups = resolve_param_with_default(payload, "backups", 0)
        binary = resolve_param_with_default(payload, "binary", False)

        # Single definition, shared with the health write-plane probe, so the
        # dir health reports on and the dir reports land in cannot drift.
        from .write_plane import resolve_reports_base_dir

        base_dir = resolve_reports_base_dir()
        return write_report(
            relative_path, content, overwrite=overwrite, base_dir=base_dir,
            backups=backups, binary=binary,
        )

    def _handle_execute_vex(self, payload: Dict) -> Dict:
        """
        Handle execute_vex command.

        Creates a temporary attribwrangle node, sets the VEX snippet,
        optionally wires an input geometry, and returns the node path.
        Includes VEX error diagnosis when compilation or cooking fails.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        snippet = resolve_param(payload, "snippet")
        run_over = resolve_param_with_default(payload, "run_over", "Points")
        input_node = resolve_param_with_default(payload, "input_node", None)

        # Pre-execution lint check (no hou.* needed)
        from ..routing.vex_diagnostics import (
            lint_vex_snippet, diagnose_vex_error, format_diagnosis,
        )
        lint_issues = lint_vex_snippet(snippet)
        warnings = []
        if lint_issues:
            warnings = [
                {"line": d.line_number, "message": d.symptom, "fix": d.fix}
                for d in lint_issues
            ]

        from .main_thread import _SLOW_TIMEOUT
        from .deadline import Deadline, DeadlineExceeded

        def _on_main():
            deadline = Deadline(_SLOW_TIMEOUT, "execute_vex")
            # Bounded-cook policy (BRAINSTEM-4), check 1: nothing has been
            # created yet, so a budget already spent costs the scene nothing.
            deadline.check()
            # F1 freeze-relief: execute_vex has no undo group of its
            # own — sandwich wraps the whole create/set/cook payload.
            # Flag-off/headless = identical behavior to today.
            from .update_mode import cook_sandwich
            with cook_sandwich(label="execute_vex"):
                # Find or create a working SOP context
                parent = None
                if input_node:
                    src = hou.node(input_node)
                    if src is None:
                        raise NodeNotFoundError(input_node)
                    parent = src.parent()

                if parent is None:
                    # Default to /obj -- create a temp geo container
                    obj = hou.node("/obj")
                    parent = obj.createNode("geo", "synapse_vex_temp")

                wrangle = parent.createNode("attribwrangle", "synapse_vex")
                wrangle.parm("snippet").set(snippet)

                # Map run_over string to the attribwrangle "class" menu index.
                # Unknown values fall back to Points, the node's own default.
                class_val = VEX_RUN_OVER_CLASS.get(
                    str(run_over).strip().lower(), VEX_RUN_OVER_CLASS["points"])
                wrangle.parm("class").set(class_val)

                # Wire input if provided
                if input_node:
                    src = hou.node(input_node)
                    if src is not None:
                        wrangle.setInput(0, src)

                wrangle.setDisplayFlag(True)
                wrangle.setRenderFlag(True)

                # Try to cook and capture any VEX errors
                cook_errors = []
                diagnosis_text = ""
                # Bounded-cook policy, check 2: a cook is a C call — no Python
                # line event fires inside it, and Houdini exposes no cook
                # cancel on the main thread (see server/deadline.py's residual
                # note). So the bound is placed where it can hold: refuse to
                # START a cook whose budget is already spent by the setup above.
                deadline.check()
                cook_started = time.perf_counter()
                try:
                    wrangle.cook(force=True)
                except Exception as cook_exc:
                    error_msg = str(cook_exc)
                    cook_errors.append(error_msg)
                    # Run pattern-based diagnosis
                    diagnoses = diagnose_vex_error(error_msg, snippet, wrangle.path())
                    if diagnoses:
                        diagnosis_text = format_diagnosis(diagnoses, snippet)
                finally:
                    cook_elapsed_s = time.perf_counter() - cook_started

                # Also check node error state (Houdini may set errors without raising)
                node_errors = []
                try:
                    if wrangle.errors():
                        node_errors = list(wrangle.errors())
                        if not diagnosis_text and node_errors:
                            all_errors = " | ".join(node_errors)
                            diagnoses = diagnose_vex_error(all_errors, snippet, wrangle.path())
                            if diagnoses:
                                diagnosis_text = format_diagnosis(diagnoses, snippet)
                except Exception as e:
                    _log.debug("VEX error diagnosis failed: %s", e)

                # Clean up temp nodes on failure when no input was provided
                if (cook_errors or node_errors) and not input_node:
                    try:
                        temp_parent = wrangle.parent()
                        if temp_parent and temp_parent.name().startswith("synapse_vex_temp"):
                            temp_parent.destroy()
                            wrangle = None  # Node no longer exists
                    except Exception as e:
                        _log.debug("VEX temp node cleanup failed: %s", e)

                result = {
                    "node": wrangle.path() if wrangle else "(cleaned up)",
                    "snippet": snippet,
                    "run_over": run_over,
                    "class": class_val,
                }

                if warnings:
                    result["warnings"] = warnings
                if cook_errors or node_errors:
                    result["errors"] = cook_errors + node_errors
                if diagnosis_text:
                    result["diagnosis"] = diagnosis_text
                # A cook that started could not be stopped from Python. Report
                # the overrun beside the result it produced — never claim the
                # cook was interrupted, and never discard a real result.
                if deadline.expired():
                    result["deadline_exceeded"] = {
                        "budget_s": deadline.budget_s,
                        "elapsed_s": round(deadline.elapsed(), 3),
                        "cook_s": round(cook_elapsed_s, 3),
                        "detail": (
                            "The cook finished after the main-thread budget. A "
                            "cook cannot be interrupted from Python, so it was "
                            "not stopped; the result above is what it produced."
                        ),
                    }

                return result

        # TIMEOUT CHOICE: _SLOW_TIMEOUT (30s), UNCHANGED. A wrangle cook is
        # arbitrarily long; 30s is the shipped off-main budget and changing it
        # would break working VEX. On the inline (/mcp) path the budget is a
        # no-op, so the bounded-cook policy inside _on_main is what actually
        # refuses a cook whose budget is spent; a cook already started reports
        # its overrun instead (BRAINSTEM-4).
        try:
            result = run_on_main_observed(
                _on_main, timeout=_SLOW_TIMEOUT, label="execute_vex",
            )
        except DeadlineExceeded as exc:
            raise ExecutionDeadlineExceeded(str(exc)) from None

        # Mile 6: capture successful, non-trivial wrangles as recall-able
        # session memory. Best-effort and off the Houdini main thread -- a
        # capture failure never affects the VEX result.
        if not result.get("errors"):
            try:
                from ..memory.vex_capture import capture_vex_pattern
                bridge = self._get_bridge()  # type: ignore[attr-defined]
                store = getattr(getattr(bridge, "_synapse", None), "store", None)
                if store is not None:
                    capture_vex_pattern(store, snippet, {
                        "node": result.get("node"),
                        "run_over": run_over,
                    })
            except Exception as e:
                _log.debug("VEX session capture skipped: %s", e)

        return result
    # =========================================================================
    # INTROSPECTION HANDLERS (Phase 1)
    # =========================================================================

    def _handle_inspect_selection(self, payload: Dict) -> Dict:
        """Bounded topology scan, with optional detail and pinned preconditions."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_selection
        defaults = {"depth": 0, "include_parameters": False, "include_geometry": False,
                    "max_nodes": 200, "max_edges": 2000, "node_paths": None,
                    "expected_identities": None, "expected_scene": None,
                    "expected_topology_hash": None}
        options = {key: resolve_param_with_default(payload, key, default)
                   for key, default in defaults.items()}
        return _marshal_inspect_read(
            lambda: inspect_selection(**options),
            command="inspect_selection",
            label="handlers:_handle_inspect_selection",
            subject="the current selection (include_geometry=%s)"
                    % bool(options["include_geometry"]),
        )

    def _handle_inspect_scene(self, payload: Dict) -> Dict:
        """Hierarchical scene overview with issues and artist notes."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_scene
        from .main_thread import run_on_main
        root = resolve_param_with_default(payload, "root", "/")
        max_depth = resolve_param_with_default(payload, "max_depth", 3)
        context_filter = resolve_param_with_default(payload, "context_filter", None)
        from ..core.timeouts import timeout_for
        # F6 (2026-08-14): raise this marshal from the 10s default to match the
        # /mcp 30s budget. OWNERSHIP: core/timeouts.py SLOW_COMMANDS
        # ["inspect_scene"]=30s is canonical; this site reads it from that
        # table so marshal and transport stay aligned (a big stage walk is
        # exactly the command class that false-fails at 10s, and on timeout
        # the C4 abandoned flag still no-ops the late payload).
        return run_on_main(lambda: inspect_scene(
            root=root,
            max_depth=int(max_depth),
            context_filter=context_filter,
        ), timeout=timeout_for("inspect_scene"), label="handlers:_handle_inspect_scene")

    def _handle_inspect_node(self, payload: Dict) -> Dict:
        """Deep single-node dump: all parms, expressions, code, geometry, HDA info."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_node_detail
        node_path = resolve_param(payload, "node")
        include_code = resolve_param_with_default(payload, "include_code", True)
        # Geometry is the expensive part of an inspect (full _geometry_summary).
        # Default it OFF so the common "what are this node's parms/code" inspect
        # stays cheap; callers opt in with include_geometry=true (Mile 3a).
        include_geometry = resolve_param_with_default(payload, "include_geometry", False)
        include_expressions = resolve_param_with_default(payload, "include_expressions", True)
        return _marshal_inspect_read(
            lambda: inspect_node_detail(
                node_path=node_path,
                include_code=bool(include_code),
                include_geometry=bool(include_geometry),
                include_expressions=bool(include_expressions),
            ),
            command="inspect_node",
            label="handlers:_handle_inspect_node",
            subject="%s (include_geometry=%s)" % (node_path, bool(include_geometry)),
        )

    def _handle_get_metrics(self, payload: Dict) -> Dict:
        """Return Prometheus-format metrics text."""
        from .metrics import render_prometheus

        router_stats = None
        router = getattr(self, "_router", None)
        if router is not None:
            router_stats = router.stats()

        cb_state = "closed"
        memory_count = 0
        try:
            bridge = self._get_bridge()
            synapse_mem = getattr(bridge, "_synapse", None)
            if synapse_mem is not None:
                memory_count = synapse_mem.store.count()
        except Exception as e:
            _log.debug("Bridge memory count fetch failed: %s", e)

        live_snapshot = None
        agg = getattr(self, "_metrics_aggregator", None)
        if agg:
            snap = agg.latest()
            if snap:
                from .live_metrics import snapshot_to_dict
                live_snapshot = snapshot_to_dict(snap)

        # C6: the dispatch-wait histogram (enqueue→start wake latency) rides the
        # same metrics surface so the floor can be attributed from a live session.
        try:
            from .main_thread import dispatch_wait_stats
            dispatch_waits = dispatch_wait_stats()
        except Exception:
            dispatch_waits = None

        # C6 (continued) — the inline panel/bridge main-thread path short-circuits
        # run_on_main and never samples dispatch_wait; this fn()-duration histogram
        # attributes it. Same guarded-import + best-effort pattern as above.
        try:
            from .main_thread import main_thread_direct_stats
            main_thread_directs = main_thread_direct_stats()
        except Exception:
            main_thread_directs = None

        # OCC — deferred-path main-thread HOLD histogram: fn() duration
        # measured ON the main thread inside _on_main. Real occupancy on the
        # path every off-main tool payload takes. Same guarded pattern.
        try:
            from .main_thread import main_thread_hold_stats
            main_thread_holds = main_thread_hold_stats()
        except Exception:
            main_thread_holds = None

        # R1 stage-integrity hash duration (the Flatten floor on large stages).
        try:
            from shared.bridge import scene_hash_stats
            scene_hashes = scene_hash_stats()
        except Exception:
            scene_hashes = None

        # T4 phase instruments (R302 rank 6): composition-validation and
        # blast-radius durations — non-saturating buckets. Same guarded
        # best-effort pattern as scene_hash above.
        try:
            from shared.bridge import composition_stats
            compositions = composition_stats()
        except Exception:
            compositions = None
        try:
            from shared.bridge import stage_touch_stats
            stage_touches = stage_touch_stats()
        except Exception:
            stage_touches = None

        # Panel inline (main-thread Qt slot) tool-dispatch summary. Importing the
        # accessor pulls in Qt; absent in headless servers → gracefully None.
        try:
            from ..panel.tool_executor import panel_inline_stats
            panel_inlines = panel_inline_stats()
        except Exception:
            panel_inlines = None

        # FRZ — main-thread result-path phases (the Qt half of the attribution).
        # Unlike panel_inline_stats above, this accessor is zero-Qt by construction,
        # so it stays collectable in a headless server rather than degrading to None.
        try:
            from ..panel.result_telemetry import result_render_stats
            panel_results = result_render_stats()
        except Exception:
            panel_results = None

        text = render_prometheus(
            router_stats=router_stats,
            circuit_breaker_state=cb_state,
            memory_entry_count=memory_count,
            tool_durations=self.tool_duration_stats(),
            dispatch_waits=dispatch_waits,
            main_thread_directs=main_thread_directs,
            main_thread_holds=main_thread_holds,
            scene_hashes=scene_hashes,
            panel_inlines=panel_inlines,
            panel_results=panel_results,
            live_snapshot=live_snapshot,
            compositions=compositions,
            stage_touches=stage_touches,
        )
        return {"format": "prometheus", "text": text}

    def _handle_router_stats(self, payload: Dict) -> Dict:
        """Return tier cascade statistics for LLM self-reflection.

        R-014: a default-constructed handler carries its router (see
        __init__), so this serves real stats. The explicit None check keeps
        the F01 contract for the degraded case where construction failed:
        raise a typed service error rather than return a fake success dict.
        """
        router = getattr(self, "_router", None)
        if router is None:
            raise SynapseServiceError("Router not initialized")
        return router.stats()

    def _handle_list_recipes(self, payload: Dict) -> Dict:
        """List all available recipes for artist discovery."""
        from ..routing.recipes import RecipeRegistry
        registry = RecipeRegistry()
        recipes = []
        for recipe in registry.recipes:
            recipes.append({
                "name": recipe.name,
                "description": recipe.description,
                "category": recipe.category,
                "triggers": recipe.triggers,
                "parameters": recipe.parameters,
                "step_count": len(recipe.steps),
            })
        return {
            "count": len(recipes),
            "recipes": sorted(recipes, key=lambda r: r["name"]),
        }

    # ------------------------------------------------------------------
    # Live Metrics (Sprint E)
    # ------------------------------------------------------------------

    def set_metrics_aggregator(self, aggregator) -> None:
        """Inject the MetricsAggregator instance (called by SynapseServer)."""
        self._metrics_aggregator = aggregator

    def _handle_get_live_metrics(self, payload: Dict) -> Dict:
        """Return live metrics snapshot or historical snapshots."""
        if not getattr(self, "_metrics_aggregator", None):
            raise SynapseServiceError("Metrics aggregator not running")

        count = payload.get("history_count", 0)
        if count > 0:
            return {"snapshots": self._metrics_aggregator.history(count)}

        snapshot = self._metrics_aggregator.latest()
        if not snapshot:
            return {"error": "No metrics collected yet"}

        from .live_metrics import snapshot_to_dict
        return snapshot_to_dict(snapshot)

    def _get_knowledge_index(self):
        """Lazy-init and return the shared RAG KnowledgeIndex (or None).

        Shared by ``_handle_knowledge_lookup`` and the memory recall/search
        handlers (see ``handlers_memory.py``) so the recall path can reach the
        RAG corpus -- the VEX corpus and reference docs -- and not just Moneta.
        Never raises: returns None if the index cannot be built, so callers can
        degrade gracefully.
        """
        if not hasattr(self, "_knowledge"):
            try:
                from pathlib import Path as _Path
                from ..routing.knowledge import KnowledgeIndex
                import os
                rag_root = os.environ.get(
                    "SYNAPSE_RAG_ROOT",
                    str(_Path(__file__).resolve().parent.parent.parent.parent / "rag"),
                )
                memory = None
                try:
                    from ..memory.store import get_synapse_memory
                    memory = get_synapse_memory()
                except Exception as e:
                    _log.debug("KnowledgeIndex memory init failed: %s", e)
                self._knowledge = KnowledgeIndex(
                    rag_root=rag_root if _Path(rag_root).exists() else None,
                    memory=memory,
                )
            except Exception as e:
                _log.debug("KnowledgeIndex init failed: %s", e)
                self._knowledge = None
        if self._knowledge is not None:
            # A scene rebind changes the owner. Observe it on main instead of
            # retaining the closed previous scene's memory in the index.
            try:
                from .main_thread import run_on_main
                from ..memory import store as _memory_store
                self._knowledge._memory = run_on_main(
                    lambda: _memory_store._global_synapse,
                    timeout=3.0, label="knowledge:existing_memory_owner")
            except Exception:
                self._knowledge._memory = None
        return self._knowledge

    def _handle_knowledge_lookup(self, payload: Dict) -> Dict:
        """Look up Houdini knowledge from the RAG index.

        Queries the Tier 1 knowledge index for parameter names,
        node types, workflow guides, and FX setup instructions.

        W4-KNOW Target 3: ``context`` narrows a node lookup to one context
        ("cop"/"lop"/...); a bare type that spans several returns a
        ``disambiguation`` list instead of a silent pick. ``k`` bounds that list.
        A node answer carries the full ``parameters`` surface (internal names +
        channels, uncapped - Target 5) and the measured ``serve_bytes``.
        """
        query = resolve_param(payload, "query")
        context = payload.get("context")
        k = payload.get("k")

        knowledge = self._get_knowledge_index()
        if knowledge is None:
            return {
                "found": False,
                "answer": "",
                "confidence": 0.0,
                "topic": "",
                "sources": [],
                "agent_hint": "",
                "summary": "",
                "reference_file": "",
                "context": "",
                "disambiguation": [],
                "parameters": [],
                "serve_bytes": 0,
            }

        kwargs: Dict = {}
        if context:
            kwargs["context"] = context
        if isinstance(k, int) and k > 0:
            kwargs["k"] = k
        result = knowledge.lookup(query, **kwargs)
        return {
            "found": result.found,
            "answer": result.answer,
            "confidence": result.confidence,
            "topic": result.topic,
            "sources": result.sources,
            "agent_hint": result.agent_hint,
            "summary": result.summary,
            "reference_file": result.reference_file,
            "context": result.context,
            "disambiguation": result.disambiguation,
            "parameters": result.parameters,
            "serve_bytes": result.serve_bytes,
        }

    # =========================================================================
    # AUTONOMOUS RENDER
    # =========================================================================

    @staticmethod
    def _resolve_agent_usd() -> Optional[str]:
        """Resolve the live agent.usd path for the current scene, or None.

        Mirrors the WebSocket disconnect hook's pattern (server/websocket.py);
        MCP session ends no longer use it (mcp/session.py writes only into an
        agent.usd that already exists). Best-effort: returns None (never raises)
        when Houdini is unavailable, the scene structure can't be built,
        or the file doesn't exist yet.
        """
        if not HOU_AVAILABLE:
            return None
        try:
            from ..memory.scene_memory import ensure_scene_structure
            hip_path = hou.hipFile.path()
            job_path = hou.getenv("JOB", os.path.dirname(hip_path))
            paths = ensure_scene_structure(hip_path, job_path)
            agent_usd = paths.get("agent_usd", "")
            if agent_usd and os.path.exists(agent_usd):
                return agent_usd
        except Exception as e:  # pragma: no cover - defensive
            _log.debug("agent.usd resolution failed: %s", e)
        return None

    @staticmethod
    def _record_autonomy_task(agent_usd: str, task_id: str, report) -> None:
        """Record the completion + render-quality verification of an autonomy task.

        Best-effort provenance writer for the live autonomous-render path. Closes
        the lifecycle a prior ``create_task(...)`` opened: sets the task status to
        ``completed``/``failed`` and writes a verification_log entry derived from the
        unconditionally-populated report fields (``executed.validation_checks`` and
        ``evaluation``). The artist's ``plan`` keeps the planner's declared checks
        and must not be read as evidence of what ran.

        Note: ``before_state``/``after_state`` here carry **render-quality**
        semantics (pre-flight check summary -> sequence-evaluation score), NOT the
        scene-hash semantics used elsewhere on the bridge path. ``report.verification``
        is deliberately NOT consulted -- it is always None on the live handler path
        (no predictor is constructed).

        Every writer call is wrapped so a failure can never propagate into, abort,
        or slow the render. The writers themselves already no-op without pxr.
        """
        try:
            from ..memory.agent_state import update_task_status, write_verification

            success = bool(getattr(report, "success", False))
            status = "completed" if success else "failed"
            result = "pass" if success else "fail"

            try:
                update_task_status(agent_usd, task_id, status)
            except Exception as e:  # pragma: no cover - defensive
                _log.debug("update_task_status failed for %s: %s", task_id, e)

            # Verification entry from render-quality fields (always populated).
            try:
                # The executed state carries the checks that actually ran.
                # ``report.plan`` is the artist's immutable request and holds
                # the planner's declared (never-executed) checks. The getattr
                # fallback keeps this correct whichever of the two report
                # shapes is live: one branch may not carry ``executed`` yet.
                executed = (getattr(report, "executed", None)
                            or getattr(report, "plan", None))
                checks_list = list(getattr(executed, "validation_checks", []) or [])
                # CheckSeverity.HARD_FAIL.value == "hard_fail" (autonomy/models.py:38)
                # is the live blocking-check value — match it exactly, not a guess.
                hard_fail = sum(
                    1 for c in checks_list
                    if not getattr(c, "passed", False)
                    and str(getattr(getattr(c, "severity", None), "value",
                                    getattr(c, "severity", ""))).lower() == "hard_fail"
                )
                before_state = f"checks={len(checks_list)} hard_fail={hard_fail}"

                evaluation = getattr(report, "evaluation", None)
                if evaluation is not None:
                    after_state = (
                        f"score={getattr(evaluation, 'overall_score', 0.0):.2f} "
                        f"passed={getattr(evaluation, 'passed', False)}"
                    )
                else:
                    after_state = "no_evaluation"

                checks = [
                    f"{getattr(c, 'name', '?')}:{'pass' if getattr(c, 'passed', False) else 'fail'}"
                    for c in checks_list
                ]

                write_verification(agent_usd, task_id, before_state, after_state, checks, result)
            except Exception as e:  # pragma: no cover - defensive
                _log.debug("write_verification failed for %s: %s", task_id, e)
        except Exception as e:  # pragma: no cover - defensive
            # Absolute backstop: provenance recording is best-effort and must
            # never disturb the render result.
            _log.debug("autonomy task recording failed for %s: %s", task_id, e)

    def _handle_autonomous_render(self, payload: Dict) -> Dict:
        """Start or poll an autonomous render task (R-035).

        Payload -- start:
            intent (str, required): Natural-language render intent (e.g. 'render frames 1-48').
            max_iterations (int, optional): Max re-render attempts (default: 3, clamped to 10).
            max_wall_clock_seconds (float, optional): Per-run wall-clock bound
                (default: the canonical 600s client budget; past it the run stops
                at the next step boundary with stop_reason='wall_clock_exceeded').
            quality_threshold (float, optional): Minimum quality score 0.0-1.0 (default: 0.85).

        Payload -- poll:
            task_id (str): The id returned by a start call.

        The Plan -> Validate -> Execute -> Evaluate -> Report loop runs on a
        worker thread; this call returns a task receipt immediately, so the
        tool can never outlive its client budget with the render still inside
        it. A second start whose intent resolves to the same plan (and the
        same run parameters) JOINS the in-flight task -- ``reused: true`` and
        an incremented ``joined_calls`` -- instead of starting a duplicate run.

        The worker runs the driver on a plain asyncio loop it builds itself
        (Houdini 22's patched asyncio refuses the default loop's first
        ``create_task`` off the main thread). If even the plain loop cannot be
        constructed, the driver's synchronous step loop runs instead, and the
        report under the poll receipt's ``result`` carries
        ``execution_mode: "sync_steps"``.

        Returns:
            A task receipt. A poll of a finished task carries the serialized
            RenderReport under ``result``, with ``success`` and ``stop_reason``
            (including 'wall_clock_exceeded') mirrored at the top level.
        """
        store = _autonomy_task_store(self)

        task_id = payload.get("task_id")
        if task_id:
            receipt = store.public(str(task_id))
            if receipt is None:
                raise ValueError(
                    "Couldn't find an autonomous render task with id %r -- it may "
                    "have finished and been evicted, or never existed. Start a new "
                    "run with 'intent'." % (task_id,)
                )
            return receipt

        import asyncio

        intent = payload.get("intent")
        if not intent:
            raise ValueError(
                "We need an intent to plan the render \u2014 "
                "e.g. 'render frames 1-48' or 'render turntable at 50mm'"
            )

        max_iterations = int(payload.get("max_iterations", 3))
        quality_threshold = min(1.0, max(0.0, float(payload.get("quality_threshold", 0.85))))
        wall_clock_seconds = payload.get("max_wall_clock_seconds")

        # The driver resolves the budget the same way; deriving the effective
        # value here keeps a default start and an explicit-600 s start on the
        # same join key instead of running the plan twice.
        from ..core.timeouts import timeout_for
        effective_wall_clock = (
            float(wall_clock_seconds) if wall_clock_seconds
            else timeout_for("autonomous_render")
        )

        # Late import to keep autonomy optional (no import at module level)
        from ..autonomy import (
            AutonomousDriver,
            RenderPlanner,
            PreFlightValidator,
            RenderEvaluator,
        )

        # Adapter: bridge the sync handler registry to the async interface
        # expected by the autonomy modules.
        class _HandlerAdapter:
            """Adapts the sync handler registry to the async interface expected by autonomy modules."""

            def __init__(self, registry):
                self._registry = registry

            def _resolve(self, tool_name):
                handler = self._registry.get(tool_name)
                if handler is None:
                    raise ValueError(f"Couldn't find handler: {tool_name}")
                return handler

            async def call(self, tool_name, params):
                self._resolve(tool_name)
                # Route through invoke() so autonomy-driven ops emit provenance
                # records (origin='autonomy'). Coroutine results still awaited.
                result = self._registry.invoke(
                    tool_name, params, ctx=FloorContext(origin="autonomy"),
                )
                if asyncio.iscoroutine(result):
                    return await result
                return result

            def call_sync(self, tool_name, params):
                """The same dispatch with no event loop (R-035 sync fallback).

                Every live registry handler is synchronous, so this is the
                normal case. A handler that returns a coroutine cannot run
                here (the loop was refused); the step fails honestly instead
                of leaking an un-awaited coroutine.
                """
                self._resolve(tool_name)
                result = self._registry.invoke(
                    tool_name, params, ctx=FloorContext(origin="autonomy"),
                )
                if asyncio.iscoroutine(result):
                    result.close()
                    raise RuntimeError(
                        "Handler %r returned a coroutine, and the synchronous "
                        "fallback has no event loop to run it." % (tool_name,)
                    )
                return result

        adapter = _HandlerAdapter(self._registry)

        # Optionally wire up memory for decision persistence
        memory = None
        try:
            from ..memory.store import get_synapse_memory
            memory = get_synapse_memory()
        except Exception as e:
            _log.debug("Decision memory init failed: %s", e)

        planner = RenderPlanner()
        validator = PreFlightValidator(adapter)
        evaluator = RenderEvaluator(pass_threshold=quality_threshold)

        # Join key: the intent, the plan it resolves to, and the run
        # parameters. Planning is pure CPU (regex + step templates), so
        # deriving it here means a second identical start joins the first
        # instead of racing it into a duplicate run.
        steps_key = []
        try:
            planned = planner.plan(intent)
            steps_key = [
                {"handler": step.handler, "params": step.params}
                for step in getattr(planned, "steps", []) or []
            ]
        except Exception as e:
            _log.debug("Autonomy plan fingerprint skipped: %s", e)
        key = _autonomy_fingerprint(str(intent), steps_key, {
            "max_iterations": max_iterations,
            "quality_threshold": quality_threshold,
            "max_wall_clock_seconds": effective_wall_clock,
        })

        task, joined = store.start_or_join(key, str(intent), meta={
            "max_iterations": max_iterations,
            "quality_threshold": quality_threshold,
        })
        if joined:
            receipt = store.public(task["task_id"]) or {"task_id": task["task_id"]}
            receipt["reused"] = True
            receipt["note"] = (
                "An autonomous render for this intent and plan is already in "
                "flight -- returning its task id instead of starting a second "
                "run. Poll with task_id '%s'." % task["task_id"]
            )
            return receipt

        task_id = task["task_id"]

        try:
            driver = AutonomousDriver(
                planner=planner,
                validator=validator,
                evaluator=evaluator,
                handler_interface=adapter,
                memory_system=memory,
                max_iterations=max_iterations,
                max_wall_clock_seconds=wall_clock_seconds,
            )
        except BaseException as exc:
            # Never leave the registry with a 'running' record and no worker.
            store.fail(task_id, str(exc), type(exc).__name__)
            raise

        # Provenance: open a task lifecycle in agent.usd on dispatch.
        # Best-effort -- a writer failure must never abort or slow the render.
        # The pending task is the producer for the already-live
        # suspend_all_tasks consumers (the WebSocket disconnect hook in
        # server/websocket.py; the MCP session-end recorder in mcp/session.py,
        # which suspends only tasks created by the session's end), which until
        # now had nothing to find.
        agent_usd = self._resolve_agent_usd()
        if agent_usd:
            try:
                from ..memory.agent_state import create_task
                create_task(agent_usd, task_id, intent)
            except Exception as e:
                _log.debug("create_task failed for %s: %s", task_id, e)

        owner = self

        def _worker():
            """Run the autonomy loop off the handler thread and record its outcome."""
            try:
                # R-035: no asyncio.run -- Houdini's patched asyncio refuses
                # its first create_task off the main thread. A plain loop is
                # built explicitly; if even that is refused, the driver runs
                # its synchronous step loop instead.
                report = _run_autonomy_off_main(driver, intent)
                store.complete(
                    task_id,
                    _serialize_render_report(report),
                    success=bool(getattr(report, "success", False)),
                    stop_reason=str(getattr(report, "stop_reason", "") or ""),
                )
            except BaseException as exc:  # noqa: BLE001 -- surfaced in the receipt
                # Render raised (driver error, timeout, ...) -- close the task
                # lifecycle to 'failed' (best-effort) so it does not leak as an
                # orphan 'pending' that the disconnect consumer would later
                # mislabel 'suspended'. The error is reported through the task
                # receipt, not raised into a thread nobody is joined on.
                store.fail(task_id, str(exc), type(exc).__name__)
                if agent_usd:
                    try:
                        from ..memory.agent_state import update_task_status
                        update_task_status(agent_usd, task_id, "failed")
                    except Exception as e:  # pragma: no cover - defensive
                        _log.debug("failed-task lifecycle close failed for %s: %s",
                                   task_id, e)
                return

            # Provenance: close the task lifecycle + write render-quality
            # verification. The helper is fully best-effort -- on ANY internal
            # failure the recorded result is left unchanged.
            if agent_usd:
                owner._record_autonomy_task(agent_usd, task_id, report)

        worker = threading.Thread(
            target=_worker,
            name="synapse.autonomy.%s" % task_id,
            daemon=True,
        )
        worker.start()

        receipt = store.public(task_id) or {"task_id": task_id}
        receipt["reused"] = False
        if receipt.get("status") == "running":
            receipt["note"] = (
                "Autonomous render started on a worker thread -- this call "
                "returned immediately. Poll synapse_autonomous_render with "
                '{"task_id": "%s"} for the final report.' % task_id
            )
        return receipt

def _run_compiled(compiled_code, globals_dict, locals_dict):
    """
    Run compiled Python code. Separated for DCC scripting pattern.

    This uses Python's exec() builtin intentionally for Houdini automation -
    it is NOT shell command execution.
    """
    exec(compiled_code, globals_dict, locals_dict)  # noqa: S102


# Backwards compatibility
NexusHandler = SynapseHandler

# Re-export module-level helpers that moved to mixin modules
# (tests and external code may reference them via handlers_mod)
from .handlers_render import _find_render_rop, _detect_karma_engine  # noqa: E402,F401
from .handlers_usd import _usd_to_json  # noqa: E402,F401
from .handlers_node import _suggest_children  # noqa: E402,F401
