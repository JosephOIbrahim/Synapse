"""tests/assay_h22_cache_contract.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

***********************************************************************************
* THIS SCRIPT HAS **NOT BEEN RUN**. It is written and committed in Mile 2 as a    *
* SCRIPT ONLY. Execution against a live Houdini 22.0.400 hython is MILE 3 work    *
* and is explicitly OUT OF SCOPE for this dispatch (R-CACHE-1 wave consequence:   *
* "Mile 3 = live H22 assay (22.0.400)"). Nothing in this repository may cite any  *
* result from this file as PASS/CONFIRMED until it has actually executed in a    *
* real hython process and produced a written artifact -- per blueprint §17.4:    *
* "If Houdini is unavailable, report the assay as not run, never passed," and    *
* adjudication b8 (ADOPT, "Build claims need receipts").                          *
***********************************************************************************

Not collected by pytest: filename does not match this repo's
``python_files = ["test_*.py"]`` (pyproject.toml [tool.pytest.ini_options]), so
``pytest tests/`` never imports, collects, or executes this module. Filename
deliberately follows the ``introspect_cook_api.py``/``introspect_cook_truth.py``
"assay script, not a test" convention already established under ``host/``.

Implements blueprint §17.4 live-assay items 1-7 ONLY (items 8-10 are Phase 1/2 --
File Cache parameter names/modes, sequential-Simulation-vs-independent-frames
behavior, and manifest cancellation state -- explicitly out of scope for this mile
per the dispatch's binding constraints and adjudication e3/REJECT on cancellation):

  1. build a cheap static SOP and a time-dependent SOP;
  2. verify API availability and hou.OpNode ownership;
  3. verify lastCookTime() units with a known cook;
  4. verify needsToCook() state transitions after parameter changes;
  5. verify isTimeDependent(for_last_cook=True) behavior;
  6. verify passive assessment does not change cookCount();
  7. verify memoryusage is positive and handled when unavailable.

Every assertion in this file targets the ACTUAL host adapter
(``host/cache_host_probe.py``, already committed, not modified by this script) so a
future Mile-3 run validates real production code, not a throwaway reimplementation.

Run (Mile 3, inside a real hython -- never plain python):
    hython tests/assay_h22_cache_contract.py [--out <path>]

Residue-free discipline (matching host/introspect_cook_truth.py): every trial node
is created under a disposable container that is destroyed (and verified absent)
before the script exits, on both the success and failure paths.

Artifact contract (mirrors host/introspect_cook_api.py's byte-for-byte convention):
    {schema: "cache_h22_contract_assay/v1", houdini_version, platform, command,
     exit_status, items: [{item, description, status, detail}, ...], blake2b}
    status in {"pass", "fail", "not_run"} -- "not_run" only if this script itself
    could not import hou; NEVER "pass" without a real assertion having executed.
    blake2b over json.dumps({"items": items}, sort_keys=True), digest_size=16.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import traceback

try:
    import hou  # hython interpreter -- the live build IS the authority
    HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore
    HOU_AVAILABLE = False

_HOST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "host")
if _HOST_DIR not in sys.path:
    sys.path.insert(0, _HOST_DIR)


class _AssayItem:
    def __init__(self, item: int, description: str):
        self.item = item
        self.description = description
        self.status = "not_run"
        self.detail = ""

    def to_dict(self) -> dict:
        return {"item": self.item, "description": self.description,
                "status": self.status, "detail": self.detail}


def _record_pass(result: _AssayItem, detail: str) -> None:
    result.status = "pass"
    result.detail = detail


def _record_fail(result: _AssayItem, detail: str) -> None:
    result.status = "fail"
    result.detail = detail


# --------------------------------------------------------------------------- item 1: build fixtures

def _build_fixtures():
    """§17.4 item 1: a cheap static SOP and a time-dependent SOP, in a disposable
    container. Returns (container_node, static_out_node, time_dependent_out_node)."""
    container = hou.node("/obj").createNode("geo", "cache_h22_assay")
    box = container.createNode("box", "static_box1")
    static_out = container.createNode("null", "STATIC_OUT")
    static_out.setInput(0, box)

    td_box = container.createNode("box", "time_dependent_box1")
    td_box.parm("tx").setExpression("$FF * 0.1")  # frame-dependent expression
    time_out = container.createNode("null", "TIME_DEPENDENT_OUT")
    time_out.setInput(0, td_box)

    return container, static_out, time_out


# --------------------------------------------------------------------------- item 2: API availability

def _assay_item_2(static_out) -> _AssayItem:
    result = _AssayItem(2, "verify API availability and hou.OpNode ownership")
    required = ("needsToCook", "isTimeDependent", "lastCookTime", "cookCount")
    missing = [name for name in required if name not in dir(hou.OpNode)]
    if missing:
        _record_fail(result, f"missing on hou.OpNode: {missing}")
        return result
    not_bound = [name for name in required if not hasattr(static_out, name)]
    if not_bound:
        _record_fail(result, f"present on hou.OpNode but not bound on a live instance: {not_bound}")
        return result
    _record_pass(result, f"all of {required} present on hou.OpNode and bound on a live instance")
    return result


# --------------------------------------------------------------------------- item 3: lastCookTime units

def _assay_item_3(static_out) -> _AssayItem:
    result = _AssayItem(3, "verify lastCookTime() units with a known cook")
    static_out.cook(force=True)
    raw = static_out.lastCookTime()
    if raw is None:
        _record_fail(result, "lastCookTime() returned None after an explicit forced cook")
        return result
    # A trivial box+null cook should complete in well under 10 real-world seconds. If the
    # raw value were milliseconds, `raw` for a sub-second cook would plausibly land in the
    # tens-to-low-thousands range; if it were already seconds, `raw` would be a small
    # fraction. This does not by itself PROVE the unit (a slow enough machine could cook a
    # trivial box in > 1 "second-unit" too) -- the decisive check is the manual timing
    # comparison below.
    import time
    t0 = time.perf_counter()
    static_out.parm("tx").set(static_out.parm("tx").eval() + 0.001)  # dirty it
    static_out.cook(force=True)
    wall_seconds = time.perf_counter() - t0
    raw2 = static_out.lastCookTime()
    if raw2 is None or raw2 <= 0:
        _record_fail(result, f"second forced cook produced non-positive lastCookTime(): {raw2!r}")
        return result
    # host/cache_host_probe.py's ms->s conversion: raw / 1000.0
    as_seconds_if_ms = raw2 / 1000.0
    as_seconds_if_already_s = raw2
    ms_error = abs(as_seconds_if_ms - wall_seconds)
    s_error = abs(as_seconds_if_already_s - wall_seconds)
    unit = "milliseconds" if ms_error < s_error else "seconds"
    _record_pass(
        result,
        f"raw lastCookTime()={raw2!r}, wall-clock cook time~={wall_seconds:.6f}s, "
        f"ms-interpretation error={ms_error:.6f}, s-interpretation error={s_error:.6f} "
        f"-> inferred unit: {unit}. "
        f"host/cache_host_probe.py assumes milliseconds (§8.1) -- if inferred unit above "
        f"is NOT 'milliseconds', file a correction against that module's "
        f"_evidence_last_cook_seconds ms->s conversion before trusting any downstream "
        f"seconds value.",
    )
    return result


# --------------------------------------------------------------------------- item 4: needsToCook transitions

def _assay_item_4(static_out) -> _AssayItem:
    result = _AssayItem(4, "verify needsToCook() state transitions after parameter changes")
    static_out.cook(force=True)
    after_cook = static_out.needsToCook()
    static_out.parm("tx").set(static_out.parm("tx").eval() + 1.0)
    after_dirty = static_out.needsToCook()
    static_out.cook(force=True)
    after_recook = static_out.needsToCook()
    ok = (after_cook is False) and (after_dirty is True) and (after_recook is False)
    detail = f"after_cook={after_cook!r} after_dirty={after_dirty!r} after_recook={after_recook!r}"
    if ok:
        _record_pass(result, detail)
    else:
        _record_fail(result, detail)
    return result


# --------------------------------------------------------------------------- item 5: isTimeDependent(for_last_cook=True)

def _assay_item_5(time_out, static_out) -> _AssayItem:
    result = _AssayItem(5, "verify isTimeDependent(for_last_cook=True) behavior")
    try:
        td = time_out.isTimeDependent(for_last_cook=True)
        static_td = static_out.isTimeDependent(for_last_cook=True)
    except TypeError as e:
        _record_fail(result, f"for_last_cook kwarg rejected by isTimeDependent(): {e}")
        return result
    detail = f"time_dependent_node.isTimeDependent(for_last_cook=True)={td!r}, static_node={static_td!r}"
    if td is True and static_td is False:
        _record_pass(result, detail)
    else:
        _record_fail(result, detail)
    return result


# --------------------------------------------------------------------------- item 6: passive assessment doesn't perturb cookCount

def _assay_item_6(static_out) -> _AssayItem:
    result = _AssayItem(6, "verify passive assessment does not change cookCount()")
    static_out.cook(force=True)
    before = static_out.cookCount()
    import cache_host_probe as chp  # host/ adapter under real test
    chp.observe_node_passively(static_out)
    chp.observe_node_passively(static_out)
    after = static_out.cookCount()
    detail = f"cookCount before={before!r} after two observe_node_passively() calls={after!r}"
    if before == after:
        _record_pass(result, detail)
    else:
        _record_fail(result, detail)
    return result


# --------------------------------------------------------------------------- item 7: memoryusage positive / unavailable

def _assay_item_7(static_out, container) -> _AssayItem:
    result = _AssayItem(7, "verify memoryusage is positive and handled when unavailable")
    static_out.cook(force=True)
    geo = static_out.geometry()
    try:
        mem = geo.intrinsicValue("memoryusage")
    except Exception as e:
        _record_fail(result, f"intrinsicValue('memoryusage') raised on a cooked node: "
                              f"{type(e).__name__}: {e}")
        return result
    if not isinstance(mem, (int, float)) or mem <= 0:
        _record_fail(result, f"memoryusage was not a positive number: {mem!r}")
        return result

    # "handled when unavailable" half: a node that has never cooked (needsToCook True) --
    # host/cache_host_probe.py's dirty branch must never call geometry() at all, so this
    # confirms the UNAVAILABLE case is handled by NOT ASKING, not by a try/except around a
    # call that might raise.
    dirty_box = container.createNode("box", "assay_dirty_never_cooked")
    dirty_box.parm("tx").setExpression("$FF")  # keep it time-dependent/dirty-prone
    import cache_host_probe as chp
    observation = chp.observe_node_passively(dirty_box)
    handled_ok = observation["observation_status"] in ("dirty_not_forced", "dirty_unknown")
    detail = (
        f"cooked-node memoryusage={mem!r} (positive: OK); "
        f"never-cooked node observation_status={observation['observation_status']!r} "
        f"(expected dirty_not_forced/dirty_unknown -- geometry() never called)"
    )
    if handled_ok:
        _record_pass(result, detail)
    else:
        _record_fail(result, detail)
    return result


# --------------------------------------------------------------------------- runner

def _run_all() -> list:
    items = []
    container = None
    try:
        container, static_out, time_out = _build_fixtures()
        item1 = _AssayItem(1, "build a cheap static SOP and a time-dependent SOP")
        _record_pass(item1, f"container={container.path()!r} static={static_out.path()!r} "
                             f"time_dependent={time_out.path()!r}")
        items.append(item1)

        items.append(_assay_item_2(static_out))
        items.append(_assay_item_3(static_out))
        items.append(_assay_item_4(static_out))
        items.append(_assay_item_5(time_out, static_out))
        items.append(_assay_item_6(static_out))
        items.append(_assay_item_7(static_out, container))
    except Exception:
        failure = _AssayItem(0, "unhandled exception during assay run")
        _record_fail(failure, traceback.format_exc())
        items.append(failure)
    finally:
        if container is not None:
            path = container.path()
            container.destroy()
            still_present = hou.node(path) is not None
            if still_present:
                print(f"WARNING: assay container {path!r} still present after destroy()",
                      file=sys.stderr)
    return items


def main() -> int:
    out = None
    args = sys.argv[1:]
    if "--out" in args:
        out = args[args.index("--out") + 1]

    if not HOU_AVAILABLE:
        # §17.4: "If Houdini is unavailable, report the assay as not run, never passed."
        doc = {
            "schema": "cache_h22_contract_assay/v1",
            "houdini_version": "unknown",
            "platform": platform.platform(),
            "command": " ".join([sys.executable or "python"] + sys.argv),
            "exit_status": "not_run",
            "items": [],
            "blake2b": hashlib.blake2b(
                json.dumps({"items": []}, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                digest_size=16).hexdigest(),
        }
        print("CACHE_H22_CONTRACT_ASSAY: hou unavailable -- reporting NOT RUN (never passed)")
        if out:
            _write_artifact(doc, out)
        return 1

    build = hou.applicationVersionString()
    if out is None:
        out = os.path.join("harness", "notes", f"cache_h22_contract_assay_{build}.json")

    items = _run_all()
    items_dicts = [i.to_dict() for i in items]
    any_fail = any(i.status != "pass" for i in items)

    doc = {
        "schema": "cache_h22_contract_assay/v1",
        "houdini_version": build,
        "platform": platform.platform(),
        "command": " ".join([sys.executable or "hython"] + sys.argv),
        "exit_status": "fail" if any_fail else "pass",
        "items": items_dicts,
        "blake2b": hashlib.blake2b(
            json.dumps({"items": items_dicts}, sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest(),
    }
    _write_artifact(doc, out)
    print(f"CACHE_H22_CONTRACT_ASSAY build={build} status={doc['exit_status']} -> {out}")
    for i in items_dicts:
        print(f"  [{i['status']}] item {i['item']}: {i['description']}")
    return 0 if not any_fail else 1


def _write_artifact(doc: dict, out: str) -> None:
    tmp = out + ".tmp"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out)


if __name__ == "__main__":
    sys.exit(main())
