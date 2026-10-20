"""Detached authored-code capture for the one closed headless LIGHT fixture.

Generated HOM code is parsed as data and never executed. Exactly one literal
exposure setter is partitioned from all remaining authored statements. This
does not claim a general HIP/renderer/external-asset serialization.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import ctypes
import math
import os
from typing import Mapping

if os.name == "nt":
    from ctypes import wintypes

    class _ProcessMemoryCounters(ctypes.Structure):
        # A single stable ABI type. Defining this inside each observation leaks
        # ctypes pointer-cache entries on the qualified CPython 3.13 runtime.
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                        "PagefileUsage", "PeakPagefileUsage")]]


class CaptureUnavailable(RuntimeError):
    pass


def partition_exposure(scripts: Mapping[str, str], field: str):
    """Return all normalized authored code and the sole finite exposure value.

    All statements, including locks, expressions on OTHER fields, userdata,
    layout, wires and boxes remain in the outside capture. Only the argument
    to the one selected literal setter becomes a separately writable leaf.
    """
    if not scripts or not isinstance(field, str) or not field:
        raise CaptureUnavailable("Complete authored scripts and one field required")
    if sum(len(code) for code in scripts.values()) > 4_000_000:
        raise CaptureUnavailable("Closed fixture authored-code budget exceeded")
    normalized, values, bindings = {}, [], 0
    for path, code in sorted(scripts.items()):
        if not isinstance(path, str) or not isinstance(code, str):
            raise CaptureUnavailable("Authored script identity/type unavailable")
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            raise CaptureUnavailable("Generated authored code cannot be parsed") from exc
        if sum(1 for _ in ast.walk(tree)) > 60_000:
            raise CaptureUnavailable("Closed fixture syntax budget exceeded")
        active = False
        for statement in tree.body:
            if (isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "hou_parm" for target in statement.targets)):
                call = statement.value
                active = (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                          and isinstance(call.func.value, ast.Name) and call.func.value.id == "hou_node"
                          and call.func.attr == "parm" and len(call.args) == 1 and not call.keywords
                          and isinstance(call.args[0], ast.Constant) and call.args[0].value == field)
                bindings += int(active)
            if not active or not isinstance(statement, ast.Expr):
                continue
            call = statement.value
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name) and call.func.value.id == "hou_parm"):
                continue
            if call.func.attr in {"setExpression", "setKeyframe", "setKeyframes"}:
                raise CaptureUnavailable("Captured LIGHT field must be a literal, unanimated value")
            if call.func.attr == "set":
                if len(call.args) != 1 or call.keywords:
                    raise CaptureUnavailable("Unknown exposure setter shape")
                try:
                    value = ast.literal_eval(call.args[0])
                except (ValueError, TypeError) as exc:
                    raise CaptureUnavailable("Exposure is not a captured literal") from exc
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise CaptureUnavailable("Finite scalar exposure required")
                values.append(float(value))
                call.args[0] = ast.Constant(value="SYNAPSE_CAPTURED_EXPOSURE_VALUE")
        normalized[path] = ast.dump(tree, include_attributes=False)
    if bindings != 1 or len(values) != 1:
        raise CaptureUnavailable("Exactly one complete captured exposure binding required")
    return deepcopy(normalized), values[0]


def process_peak_working_set():
    """Own-process Windows lifetime peak, measured at observation; bytes and MB.

    It is NOT a per-operation allocation or interval-reset peak. This exact
    lifetime window is bound into calibration and every observation receipt.
    Sources: Microsoft GetProcessMemoryInfo / PROCESS_MEMORY_COUNTERS docs.
    https://learn.microsoft.com/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
    https://learn.microsoft.com/windows/win32/api/psapi/ns-psapi-process_memory_counters
    """
    if os.name != "nt":
        raise CaptureUnavailable("Windows process peak memory is unavailable on this host")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessMemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise CaptureUnavailable("Own-process peak memory query failed: " + str(ctypes.get_last_error()))
    peak = int(counters.PeakWorkingSetSize)
    if peak <= 0 or peak < int(counters.WorkingSetSize):
        raise CaptureUnavailable("Invalid own-process memory counters")
    return {"pid": os.getpid(), "peak_bytes": peak, "peak_memory_mb": peak / 1_000_000,
            "window": "PROCESS_LIFETIME_PEAK_WORKING_SET_AT_OBSERVATION", "producer": "Windows.GetProcessMemoryInfo.PeakWorkingSetSize"}
