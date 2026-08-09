"""host/cache_host_probe.py — Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Authorized scope: Ruling R-CACHE-1 (docs/reviews/cache-adjudication-ruling.md, Joe/CTO,
2026-08-09), acting on docs/intake/adjudication-resource-aware-cache.md against
docs/SYNAPSE_RESOURCE_AWARE_CACHE_BLUEPRINT.md. Phase 0 (trustworthy observation) ONLY —
no recommendation, no node insertion, no disk write, no bake. Phase 1 (advisor) and Phase 2
(insertion/bake) are explicitly out of scope for this module; Phase 2 is additionally
REJECTed at HEAD (no cancel API for an in-flight cook on this build — see adjudication e3).

What this module implements (blueprint refs in parens):
  - `safe_call` — typed-warning-on-exception wrapper; NEVER coerces a failure to a fake 0
    (§17.2 boundary test: "exceptions produce typed warnings, not zero-valued fake evidence").
  - `observe_node_passively` — the §8.2 passive-assessment algorithm, verbatim in spirit:
    reads needsToCook()/isTimeDependent(for_last_cook=True)/lastCookTime()/cookCount() via
    safe_call, and — the load-bearing rule — NEVER calls node.geometry() when needsToCook()
    is True (that read can trigger the exact cook being assessed). See
    tests/test_cache_no_forced_cook.py for the mandatory negative control.
  - lastCookTime() ms -> seconds conversion happens EXACTLY ONCE, inside
    `_evidence_last_cook_seconds` — nowhere else in this file references milliseconds.
    Pinned by tests/test_cache_host_probe_boundary.py.
  - `detect_machine_profile` — §7.2 MachineProfile detection. stdlib first, `psutil`
    declared-optional (try/except ImportError -> *_AVAILABLE flag), vendor GPU tool only
    when present, else `"unknown"` — NEVER a guessed fallback number. This is the direct
    fix-shape for the adjudication a5 defect (`render_preflight.py`'s `else: sys_ram_gb =
    64.0`) — that pattern must not be repeated here, and isn't.

Symbol provenance (CLAUDE.md §12/§15): every `hou.*` name this module can reach —
`hou.OpNode.{needsToCook,isTimeDependent,lastCookTime,cookCount,path,type}`,
`hou.Geometry.intrinsicValue`, `hou.NodeType.name`, `hou.applicationVersionString`,
`hou.node` — is confirmed present (dir()-membership, name-only) on the committed
python/synapse/cognitive/tools/data/h22_symbol_table.json (houdini_version 22.0.400).
Per adjudication c2/c4/c5, name-membership does NOT verify units, kwargs, or intrinsic-
string validity (`lastCookTime()`'s millisecond unit, `isTimeDependent`'s `for_last_cook`
kwarg, `"memoryusage"` as a valid intrinsic key) — those stay V0 until
tests/test_cache_h22_contract.py actually runs on a live 22.0.400 hython (it has NOT been
run in this environment; see that file's header).

Import guard convention (CLAUDE.md §12): `hou` and the optional `psutil`/`synapse.cache_policy`
providers are all try/except-guarded with `*_AVAILABLE` flags so this module — and the
negative-control test that imports it — work with ZERO Houdini present.

Boundary (binding constraint #2): this module may import `synapse.cache_policy.*` (pure,
stdlib-only dataclasses owned by forge-models) but nothing under `synapse.cache_policy`
may ever import this module or anything Houdini-specific. Dependency direction is one-way.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------- import guards
try:
    import hou  # type: ignore

    HOU_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in the no-hou test environment
    hou = None  # type: ignore
    HOU_AVAILABLE = False

try:
    import psutil  # type: ignore

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

try:
    import sys as _sys
    from pathlib import Path as _Path

    _REPO_ROOT = _Path(__file__).resolve().parents[1]
    _PYTHON_DIR = _REPO_ROOT / "python"
    if str(_PYTHON_DIR) not in _sys.path:
        _sys.path.insert(0, str(_PYTHON_DIR))
    from synapse.cache_policy import models as _cache_models  # type: ignore  # noqa: E402

    CACHE_MODELS_AVAILABLE = True
except ImportError:
    _cache_models = None  # type: ignore
    CACHE_MODELS_AVAILABLE = False


SCHEMA_VERSION = "1.0"

# Minimum provenance sources per blueprint §7.1.
_UNKNOWN_SOURCE = "unknown"
_HISTORICAL_SOURCE = "measured_historical"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- safe_call

def safe_call(
    fn: Callable[..., Any],
    *args: Any,
    warnings: Optional[list] = None,
    label: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Call fn(*args, **kwargs); on ANY exception, record a typed warning (never a fake 0)
    and return None. None means "unknown" — callers must never silently coerce it to 0,
    False, or an empty collection. See §17.2: "exceptions produce typed warnings, not
    zero-valued fake evidence."
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - deliberately broad: any hou call can raise
        if warnings is not None:
            name = label or getattr(fn, "__name__", repr(fn))
            warnings.append(f"{name} raised {type(e).__name__}: {e}")
        return None


def _evidence(value: Any, unit: Optional[str], source: str, scope: str,
              confidence: str) -> dict:
    """§7.1 evidence wrapper. `source` is either the literal dotted API path that produced
    `value` this call (confidence=high), `measured_historical` (confidence=medium, pulled
    from last_observation_store rather than this call), or `unknown` (value is None).
    """
    return {
        "value": value,
        "unit": unit,
        "source": source,
        "observed_at": _now_iso(),
        "scope": scope,
        "confidence": confidence,
    }


def _evidence_unknown(unit: Optional[str], scope: str) -> dict:
    return _evidence(None, unit, _UNKNOWN_SOURCE, scope, "unknown")


# --------------------------------------------------------------------------- last-observation store

class LastObservationStore:
    """In-memory only. §8.2's fallback for the dirty-node branch: "fall back to
    last-known-observation store or return a 'dirty, not forced' status." Deliberately NOT
    a new persistence authority — adjudication b12/d6 flagged unreviewed new persistence
    sites as scope creep; a durable version of this store is a Memory-plane decision for a
    later mile, not this one. Callers may substitute their own object with the same
    `.lookup(node_path)` / `.record(node_path, observation)` shape.
    """

    def __init__(self) -> None:
        self._by_path: dict = {}

    def lookup(self, node_path: str) -> Optional[dict]:
        return self._by_path.get(node_path)

    def record(self, node_path: str, observation: dict) -> None:
        self._by_path[node_path] = observation


# --------------------------------------------------------------------------- passive assessment (§8.2)

def observe_node_passively(node: Any, last_observation_store: Optional[LastObservationStore] = None,
                            *, node_path: Optional[str] = None,
                            node_type: Optional[str] = None) -> dict:
    """§8.2 passive assessment algorithm.

    CRITICAL SAFETY INVARIANT: when `node.needsToCook()` is True, `node.geometry()` is
    NEVER called — that read can trigger the very cook this function exists to observe
    without forcing. See tests/test_cache_no_forced_cook.py.

    `node` is duck-typed (any object exposing needsToCook/isTimeDependent/lastCookTime/
    cookCount/geometry/path as zero-or-kwarg callables) so this function — and its
    negative control — run with zero `hou` dependency. A live caller passes a real
    `hou.OpNode`.
    """
    warnings: list = []

    path = node_path
    if path is None:
        path = safe_call(getattr(node, "path", None), warnings=warnings, label="path") \
            if hasattr(node, "path") else None
    scope = f"node:{path or 'unknown'}"

    dirty = safe_call(node.needsToCook, warnings=warnings, label="needsToCook") \
        if hasattr(node, "needsToCook") else None
    time_dependent = safe_call(
        lambda: node.isTimeDependent(for_last_cook=True),
        warnings=warnings, label="isTimeDependent(for_last_cook=True)",
    ) if hasattr(node, "isTimeDependent") else None
    last_cook_ms = safe_call(node.lastCookTime, warnings=warnings, label="lastCookTime") \
        if hasattr(node, "lastCookTime") else None
    cook_count = safe_call(node.cookCount, warnings=warnings, label="cookCount") \
        if hasattr(node, "cookCount") else None

    # --- ms -> s conversion happens EXACTLY ONCE, right here, nowhere else in this file ---
    last_cook_seconds_value = None
    if last_cook_ms is not None:
        last_cook_seconds_value = last_cook_ms / 1000.0
    last_cook_seconds = (
        _evidence(last_cook_seconds_value, "seconds", "hou.OpNode.lastCookTime", scope, "high")
        if last_cook_seconds_value is not None
        else _evidence_unknown("seconds", scope)
    )

    if dirty is True:
        # --- CRITICAL BRANCH: geometry() is NEVER called here. ---
        observation_status = "dirty_not_forced"
        geometry_memory_bytes = _evidence_unknown("bytes", scope)
        if last_observation_store is not None and path is not None:
            historical = last_observation_store.lookup(path)
            if historical is not None:
                hist_geo = historical.get("geometry_memory_bytes")
                hist_value = hist_geo.get("value") if isinstance(hist_geo, dict) else None
                if hist_value is not None:
                    geometry_memory_bytes = _evidence(
                        hist_value, "bytes", _HISTORICAL_SOURCE, scope, "medium",
                    )
    elif dirty is False:
        observation_status = "clean_snapshot"
        geometry = safe_call(node.geometry, warnings=warnings, label="geometry") \
            if hasattr(node, "geometry") else None
        mem = None
        if geometry is not None and hasattr(geometry, "intrinsicValue"):
            mem = safe_call(
                lambda: geometry.intrinsicValue("memoryusage"),
                warnings=warnings, label='Geometry.intrinsicValue("memoryusage")',
            )
        geometry_memory_bytes = (
            _evidence(mem, "bytes", "hou.Geometry.intrinsicValue", scope, "high")
            if mem is not None
            else _evidence_unknown("bytes", scope)
        )
    else:
        # needsToCook() itself failed/returned None — do not guess either branch.
        observation_status = "dirty_unknown"
        geometry_memory_bytes = _evidence_unknown("bytes", scope)

    result = {
        "schema": "cache_host_observation/v1",
        "schema_version": SCHEMA_VERSION,
        "node_path": path if path is not None else "unknown",
        "node_type": node_type if node_type is not None else "unknown",
        "observation_status": observation_status,
        "needs_to_cook": (
            _evidence(dirty, None, "hou.OpNode.needsToCook", scope, "high")
            if dirty is not None else _evidence_unknown(None, scope)
        ),
        "time_dependent": (
            _evidence(time_dependent, None, "hou.OpNode.isTimeDependent", scope, "high")
            if time_dependent is not None else _evidence_unknown(None, scope)
        ),
        "last_cook_seconds": last_cook_seconds,
        "cook_count": (
            _evidence(cook_count, None, "hou.OpNode.cookCount", scope, "high")
            if cook_count is not None else _evidence_unknown(None, scope)
        ),
        "geometry_memory_bytes": geometry_memory_bytes,
        "warnings": warnings,
    }

    if last_observation_store is not None and path is not None and observation_status == "clean_snapshot":
        last_observation_store.record(path, result)

    return result


def to_workload_snapshot_kwargs(observation: dict) -> dict:
    """Maps a cache_host_observation/v1 dict onto the subset of blueprint §7.3
    WorkloadSnapshot fields Phase 0 can honestly populate (`node_path`, `node_type`,
    `time_dependent`, `needs_to_cook`, `last_cook_seconds`, `geometry_memory_bytes`).
    Everything else in §7.3 (cache_strategy_id, strategy_support, frame_range,
    existing_cache, ...) is a Phase 1 (strategy registry / advisor) concern and is
    deliberately NOT fabricated here — a Phase 1 caller merges this partial dict with its
    own resolved fields. Coordinate the exact merge point with forge-models before Phase 1.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "node_path": observation["node_path"],
        "node_type": observation["node_type"],
        "time_dependent": observation["time_dependent"],
        "needs_to_cook": observation["needs_to_cook"],
        "last_cook_seconds": observation["last_cook_seconds"],
        "geometry_memory_bytes": observation["geometry_memory_bytes"],
        "warnings": list(observation.get("warnings", [])),
    }


def maybe_construct_workload_snapshot(observation: dict):
    """Best-effort integration with synapse.cache_policy.models.WorkloadSnapshot when it is
    importable. Falls back to the plain dict from `to_workload_snapshot_kwargs` — never
    raises on a field-shape mismatch, since the two modules are developed concurrently and
    the field names are the coordination point, not a hard import contract yet.
    """
    kwargs = to_workload_snapshot_kwargs(observation)
    if CACHE_MODELS_AVAILABLE and hasattr(_cache_models, "WorkloadSnapshot"):
        try:
            return _cache_models.WorkloadSnapshot(**kwargs)  # type: ignore[call-arg]
        except TypeError:
            pass  # field-shape mismatch — return the dict, do not raise
    return kwargs


# --------------------------------------------------------------------------- MachineProfile (§7.2)

def _detect_os_family() -> str:
    import platform

    system = platform.system()
    return {"Windows": "Windows", "Linux": "Linux", "Darwin": "macOS"}.get(system, "unknown")


def _detect_houdini_thread_cap() -> Optional[int]:
    val = os.environ.get("HOUDINI_MAXTHREADS")
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _read_proc_meminfo(warnings: list) -> tuple:
    """Linux-only stdlib fallback (tier 1: standard-library/read-only OS facilities) used
    only when `psutil` is unavailable. Read-only file I/O, no shell, no subprocess.
    """
    total = avail = None
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            data = {}
            for line in f:
                parts = line.split(":", 1)
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                val = parts[1].strip()
                if val.endswith("kB"):
                    try:
                        data[key] = int(val[:-2].strip()) * 1024
                    except ValueError:
                        continue
            total = data.get("MemTotal")
            avail = data.get("MemAvailable")
    except OSError as e:
        warnings.append(f"/proc/meminfo unavailable: {type(e).__name__}: {e}")
    return total, avail


def _detect_ram(os_family: str, warnings: list) -> tuple:
    """Hardware probing order (§7.2): 1. stdlib, 2. declared-optional psutil, else unknown.
    NEVER a guessed fallback (the adjudication a5 defect this exists to not repeat).
    """
    if PSUTIL_AVAILABLE:
        vm = safe_call(psutil.virtual_memory, warnings=warnings, label="psutil.virtual_memory")  # type: ignore[union-attr]
        if vm is not None:
            return getattr(vm, "total", None), getattr(vm, "available", None)
        return None, None
    if os_family == "Linux":
        return _read_proc_meminfo(warnings)
    # Windows/macOS without psutil: no free stdlib equivalent -> unknown, never guessed.
    return None, None


def _detect_process_rss(warnings: list) -> Optional[int]:
    if not PSUTIL_AVAILABLE:
        return None
    proc = safe_call(lambda: psutil.Process(os.getpid()), warnings=warnings, label="psutil.Process")  # type: ignore[union-attr]
    if proc is None:
        return None
    mem_info = safe_call(proc.memory_info, warnings=warnings, label="Process.memory_info")
    if mem_info is None:
        return None
    return getattr(mem_info, "rss", None)


def _detect_gpu_devices(warnings: list) -> list:
    """Hardware probing order tier 3: vendor GPU tool only when present and relevant.
    `name` is informational; VRAM is included ONLY when actually measured from the tool's
    own output — never inferred from the device name. Bounded subprocess (explicit arg
    list, no shell, 5s timeout) so a hung/missing driver cannot stall the probe.
    """
    tool = shutil.which("nvidia-smi")
    if tool is None:
        return []
    try:
        result = subprocess.run(
            [tool, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except Exception as e:  # noqa: BLE001
        warnings.append(f"nvidia-smi probe failed: {type(e).__name__}: {e}")
        return []
    if result.returncode != 0:
        warnings.append(f"nvidia-smi exited {result.returncode}: {result.stderr.strip()[:200]}")
        return []
    devices = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0]:
            continue
        device: dict = {"name": parts[0]}
        if len(parts) > 1:
            try:
                device["vram_bytes"] = int(parts[1]) * 1024 * 1024  # MiB -> bytes, MEASURED
            except ValueError:
                pass
        devices.append(device)
    return devices


def _detect_cache_volume(cache_root: Optional[str], warnings: list) -> dict:
    """`path_class` is never inferred from a drive letter alone (blueprint explicit rule) —
    Phase 0 has no safe local/network classifier, so it stays `unknown` unless a project/
    user override supplies one. No automatic disk benchmark: read/write throughput fields
    stay `unknown` here; only real approved cache reads/writes (Phase 3, out of scope)
    should ever populate them.
    """
    root = cache_root or os.environ.get("HIP")
    free_bytes = total_bytes = None
    if root:
        try:
            usage = shutil.disk_usage(root)
            free_bytes = usage.free
            total_bytes = usage.total
        except OSError as e:
            warnings.append(f"disk_usage({root!r}) failed: {type(e).__name__}: {e}")
    return {
        "path": root if root is not None else "unknown",
        "path_class": "unknown",
        "free_bytes": free_bytes if free_bytes is not None else "unknown",
        "total_bytes": total_bytes if total_bytes is not None else "unknown",
        "read_mib_s": "unknown",
        "write_mib_s": "unknown",
    }


def _detect_houdini_version(warnings: list) -> str:
    if not HOU_AVAILABLE:
        return "unknown"
    version = safe_call(hou.applicationVersionString, warnings=warnings, label="applicationVersionString")  # type: ignore[union-attr]
    return version if version is not None else "unknown"


def detect_machine_profile(*, synapse_version: Optional[str] = None,
                            cache_root: Optional[str] = None) -> dict:
    """§7.2 MachineProfile. Every field is either a real local measurement or the literal
    string `"unknown"` — never a fallback number, never derived from serial/username/MAC.
    """
    warnings: list = []
    os_family = _detect_os_family()
    cpu_logical_threads = safe_call(os.cpu_count, warnings=warnings, label="os.cpu_count")
    houdini_thread_cap = _detect_houdini_thread_cap()
    ram_total_bytes, ram_available_bytes = _detect_ram(os_family, warnings)
    process_rss_bytes = _detect_process_rss(warnings)
    gpu_devices = _detect_gpu_devices(warnings)
    cache_volume = _detect_cache_volume(cache_root, warnings)

    profile = {
        "schema_version": SCHEMA_VERSION,
        # Opaque, ephemeral per-process ID (never serial/username/MAC-derived). A durable
        # profile_id is a Memory-plane persistence decision deferred beyond Phase 0 —
        # see adjudication b12/d6 on not inventing new persistence authorities here.
        "profile_id": uuid.uuid4().hex,
        "captured_at": _now_iso(),
        "os_family": os_family,
        "cpu_logical_threads": cpu_logical_threads if cpu_logical_threads is not None else "unknown",
        "houdini_thread_cap": houdini_thread_cap if houdini_thread_cap is not None else "unknown",
        "ram_total_bytes": ram_total_bytes if ram_total_bytes is not None else "unknown",
        "ram_available_bytes": ram_available_bytes if ram_available_bytes is not None else "unknown",
        "process_rss_bytes": process_rss_bytes if process_rss_bytes is not None else "unknown",
        "gpu_devices": gpu_devices,
        "cache_volume": cache_volume,
        "houdini_version": _detect_houdini_version(warnings),
        "synapse_version": synapse_version if synapse_version is not None else "unknown",
        "warnings": warnings,
    }
    return profile


def maybe_construct_machine_profile(profile: dict):
    """Same best-effort integration pattern as maybe_construct_workload_snapshot."""
    if CACHE_MODELS_AVAILABLE and hasattr(_cache_models, "MachineProfile"):
        try:
            return _cache_models.MachineProfile(**profile)  # type: ignore[call-arg]
        except TypeError:
            pass
    return profile
