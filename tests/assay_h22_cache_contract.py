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
    """§17.4 item 3, re-specified (Mile 3b, R-CACHE-1) as a DECLARED DELTA rather than a
    hard failure on headless: the M3 live run (ede8d1b8,
    harness/notes/cache_h22_contract_assay_22.0.400.json item 3) established that
    lastCookTime() returns 0.0 UNCONDITIONALLY for real cooks on headless hython on this
    build. That is now the EXPECTED headless reading, not a failure -- but only when BOTH
    halves hold: (a) the 0.0 contract still holds on THIS live run, corroborated by
    wall-clock + cookCount evidence of a real cook, AND (b)
    host/cache_host_probe.py's observe_node_passively actually classifies that exact
    reading as UNKNOWN with the 'lastCookTime_unreported' warning (host/cache_host_probe.py
    _evidence_last_cook_seconds, Mile 3b). If lastCookTime() is EVER something other than
    0.0 on a headless run, this item FAILS LOUDLY -- the headless contract itself would have
    changed and must be re-litigated, never silently accepted either way.
    """
    result = _AssayItem(3, "verify lastCookTime() units with a known cook")
    # Computed FIRST and folded into every detail string below (pass or fail) so the
    # written receipt itself proves which branch executed -- never inferred after the fact
    # from prose wording alone.
    ui_available = hou.isUIAvailable()
    session = "GUI" if ui_available else "headless"

    static_out.cook(force=True)
    raw = static_out.lastCookTime()
    if raw is None:
        _record_fail(
            result,
            f"ui_available={ui_available!r} ({session}): lastCookTime() returned None after "
            f"an explicit forced cook",
        )
        return result
    # A trivial box+null cook should complete in well under 10 real-world seconds. If the
    # raw value were milliseconds, `raw` for a sub-second cook would plausibly land in the
    # tens-to-low-thousands range; if it were already seconds, `raw` would be a small
    # fraction. This does not by itself PROVE the unit (a slow enough machine could cook a
    # trivial box in > 1 "second-unit" too) -- the decisive check is the manual timing
    # comparison below.
    import time
    parent = static_out.parent()
    heavy = parent.createNode("grid", "UNIT_CHECK_HEAVY")  # trivial cooks land below timer resolution (0.0); a 4M-pt grid is measurable
    try:
        heavy.parm("rows").set(2000)
        heavy.parm("cols").set(2000)
        count_before = heavy.cookCount()
        t0 = time.perf_counter()
        heavy.cook(force=True)
        wall_seconds = time.perf_counter() - t0
        raw2 = heavy.lastCookTime()
        count_after = heavy.cookCount()

        if not ui_available:
            return _assay_item_3_headless(result, heavy, raw2, wall_seconds,
                                           count_before, count_after, ui_available)
            # heavy.destroy() still runs via the outer finally below.

        # --- GUI session: self-verifying wall-clock-vs-raw unit inference (unchanged) ---
        if raw2 is None or raw2 <= 0:
            _record_fail(
                result,
                f"ui_available={ui_available!r} ({session}): second forced cook produced "
                f"non-positive lastCookTime(): {raw2!r}",
            )
            return result
        # host/cache_host_probe.py's ms->s conversion: raw / 1000.0
        as_seconds_if_ms = raw2 / 1000.0
        as_seconds_if_already_s = raw2
        ms_error = abs(as_seconds_if_ms - wall_seconds)
        s_error = abs(as_seconds_if_already_s - wall_seconds)
        unit = "milliseconds" if ms_error < s_error else "seconds"
        _record_pass(
            result,
            f"ui_available={ui_available!r} ({session}): raw lastCookTime()={raw2!r}, "
            f"wall-clock cook time~={wall_seconds:.6f}s, "
            f"ms-interpretation error={ms_error:.6f}, s-interpretation error={s_error:.6f} "
            f"-> inferred unit: {unit}. Corroborated by "
            f"harness/notes/cache_h22_gui_assay_22.0.400.json's own two GUI data points "
            f"(wall 0.1714s -> raw 171.14; wall 0.1473s -> raw 147.17, both consistent with "
            f"milliseconds). "
            f"host/cache_host_probe.py assumes milliseconds (§8.1) -- if inferred unit above "
            f"is NOT 'milliseconds', file a correction against that module's "
            f"_evidence_last_cook_seconds ms->s conversion before trusting any downstream "
            f"seconds value.",
        )
        return result
    finally:
        heavy.destroy()


def _assay_item_3_headless(result: "_AssayItem", heavy, raw2, wall_seconds,
                            count_before, count_after, ui_available: bool) -> "_AssayItem":
    """Headless half of item 3. Caller (_assay_item_3) still owns `heavy` and destroys it in
    its own `finally` -- this function only decides pass/fail, never touches node lifecycle.
    `ui_available` is threaded through purely so every detail string below records the
    branch that produced it (T6: the receipt must prove which branch ran, not just imply it
    in prose).
    """
    if raw2 != 0.0:
        _record_fail(
            result,
            f"ui_available={ui_available!r} (headless): HEADLESS CONTRACT CHANGED -- "
            "expected lastCookTime()==0.0 unconditionally on headless hython per "
            "harness/notes/cache_h22_contract_assay_22.0.400.json item 3 (M3, ede8d1b8), "
            f"got {raw2!r} instead. Do NOT silently treat this as fine either way -- "
            "re-litigate the headless 0.0 contract, and host/cache_host_probe.py's "
            "_evidence_last_cook_seconds guard built against it (Mile 3b), before trusting "
            "either the old or the new reading.",
        )
        return result

    cook_happened = (
        count_before is not None and count_after is not None
        and count_after > count_before and wall_seconds > 0.0
    )
    if not cook_happened:
        _record_fail(
            result,
            f"ui_available={ui_available!r} (headless): raw2==0.0 as expected, but cook "
            f"evidence is missing/contradictory: cookCount before={count_before!r} "
            f"after={count_after!r}, wall_seconds={wall_seconds:.6f} -- cannot confirm a "
            f"real cook actually happened, so the 0.0-is-expected declared-delta cannot be "
            f"trusted on this run.",
        )
        return result

    # Integration half: confirm host/cache_host_probe.py's guard (Mile 3b) actually
    # classifies THIS live 0.0 reading as UNKNOWN + lastCookTime_unreported, not as a
    # fabricated 0.0-second measurement.
    #
    # REVIEWER FINDING B5 (do not weaken): a naive check here (value is None, confidence
    # unknown, lastCookTime_unreported present) can be FALSELY satisfied if
    # observe_node_passively's OWN internal lastCookTime() re-read happens to raise (a
    # theoretical heisenbug, not the case under test) -- safe_call would degrade that
    # exception to None too, and the guard fires for an unrelated reason while this item
    # still claims "confirmed ... classifies this exact reading". So this check independently
    # re-reads heavy.lastCookTime() immediately before AND after the probe call (both must
    # still be exactly 0.0 -- the same reading raw2 already established) AND requires the
    # probe's own warnings contain NO lastCookTime exception ("this exact reading" is only
    # true if the probe never saw a raise on its own read).
    import cache_host_probe as chp  # host/ adapter under real test, same as items 6/7
    pre_probe_reread = heavy.lastCookTime()
    observation = chp.observe_node_passively(heavy)
    post_probe_reread = heavy.lastCookTime()
    seconds_evidence = observation["last_cook_seconds"]
    # PREFIX match, not substring: safe_call's own exception warning always begins with
    # "lastCookTime raised " (see host/cache_host_probe.py::safe_call). A substring check
    # would also match that phrase if it ever appeared quoted/mentioned INSIDE a different
    # warning's own explanatory text (a real false-positive this assay hit once already,
    # see the guard's own docstring note) -- prefix-matching pins this to an actual
    # separate safe_call exception entry, not incidental wording.
    no_exception_warning = not any(w.startswith("lastCookTime raised") for w in observation["warnings"])
    guard_fired = (
        seconds_evidence["value"] is None
        and seconds_evidence["confidence"] == "unknown"
        and any("lastCookTime_unreported" in w for w in observation["warnings"])
        and no_exception_warning
        and pre_probe_reread == 0.0
        and post_probe_reread == 0.0
    )
    if not guard_fired:
        _record_fail(
            result,
            f"ui_available={ui_available!r} (headless): raw2==0.0 confirmed as a real cook "
            f"(wall_seconds={wall_seconds:.6f}, cookCount {count_before!r}->{count_after!r}), "
            f"pre_probe_reread={pre_probe_reread!r}, post_probe_reread={post_probe_reread!r}, "
            f"no_exception_warning={no_exception_warning!r}, but "
            f"cache_host_probe.observe_node_passively did NOT classify it as UNKNOWN + "
            f"'lastCookTime_unreported' on THIS exact reading -- got "
            f"last_cook_seconds={seconds_evidence!r}, warnings={observation['warnings']!r}. "
            f"The Mile 3b guard is not firing against this live reading.",
        )
        return result

    _record_pass(
        result,
        f"ui_available={ui_available!r} (headless): DECLARED DELTA (H22.0.400): "
        f"lastCookTime()==0.0 for a real cook (wall_seconds={wall_seconds:.6f}, cookCount "
        f"{count_before!r}->{count_after!r}) matches the original M3 finding recorded at "
        f"commit ede8d1b8 (git history -- NOT this same artifact file, which this run "
        f"overwrites; see the FAIL branch above for what a genuine contract change reports) "
        f"-- EXPECTED, not a failure. Units evidence for the positive-value (GUI) path "
        f"(milliseconds) lives in harness/notes/cache_h22_gui_assay_22.0.400.json (a "
        f"headless run cannot self-prove units when the reading is unconditionally 0.0). "
        f"Confirmed host/cache_host_probe.py's _evidence_last_cook_seconds classifies this "
        f"exact reading as UNKNOWN with the 'lastCookTime_unreported' warning: "
        f"last_cook_seconds={seconds_evidence!r}, warnings={observation['warnings']!r}. "
        f"\"This exact reading\" is earned, not assumed: independent re-reads immediately "
        f"before/after the probe call were both "
        f"pre_probe_reread={pre_probe_reread!r}/post_probe_reread={post_probe_reread!r} "
        f"(both 0.0) and the probe's own warnings carried no lastCookTime exception "
        f"(no_exception_warning={no_exception_warning!r}).",
    )
    return result


# --------------------------------------------------------------------------- item 4: needsToCook transitions

def _assay_item_4(static_out) -> _AssayItem:
    result = _AssayItem(4, "verify needsToCook() state transitions after parameter changes")
    static_out.cook(force=True)
    after_cook = static_out.needsToCook()
    _upstream = static_out.inputs()[0]  # null has no tx; dirty via its box
    _upstream.parm("tx").set(_upstream.parm("tx").eval() + 1.0)
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
        time_out.cook(force=True)   # for_last_cook reports on the LAST cook; it must exist
        static_out.cook(force=True)
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
