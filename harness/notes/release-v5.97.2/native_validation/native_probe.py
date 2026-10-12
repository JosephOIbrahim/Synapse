"""Seven-fix full-handler native probe. UNRUN; coordinator slot required.

Adapted from preserved native_common/full_worker fixture/readback conventions.
Candidate only, two fresh processes: build and reopen. No production startup.
"""
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parent
HEAD = "b7301f3f985d1c0a9876b8ee629472392422bc26"
INDIE_OPTIONS = "--skip-license-modes=commercial,education,apprentice"
PARENT = "/stage/seven_fix_fixture"
CALLS = 0
HOU = None
G = None
SUBJECT = None
ERROR = None
OUT = None
PROGRESS = {}


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    require(not path.exists(), "Preserve existing artifact: " + str(path))
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def pins():
    manifest = read(ROOT / "prepared-pins.json")
    require(manifest["commit"] == HEAD, "Wrong source head")
    for row in manifest["files"]:
        require(sha(ROOT / row["path"]) == row["sha256"], "Changed preparation pin: " + row["path"])
    for row in manifest["runtime_files"]:
        require(sha(row["path"]) == row["sha256"], "Changed H22 runtime file")
    for row in read(ROOT / "source-manifest.json")["files"]:
        require(sha(ROOT / "source" / row["path"]) == row["sha256"], "Changed candidate source: " + row["path"])
    return manifest


def slot(path, expected_hash, phase):
    require(sha(path) == expected_hash, "Slot receipt changed")
    receipt = read(path)
    require(receipt["commit"] == HEAD and receipt["native_clearance"] is True,
            "Fresh coordinated native clearance absent")
    require(receipt["prepared_pins_sha256"] == sha(ROOT / "prepared-pins.json"), "Unapproved test pins")
    require(receipt["indie_clearance"] is True and receipt["resource_owner_clearance"] is True
            and receipt["live_gui_preserved_clearance"] is True,
            "Indie/resource-owner/live-GUI preservation clearance absent")
    require(phase in receipt["phases"], "Wrong slot phase")
    require(time.time() < receipt["expires_unix"], "Slot expired")
    return receipt


def primitive(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    try:
        return [primitive(v) for v in value]
    except TypeError:
        return str(value)


def sockets(node):
    # Independent native HOM oracle, never candidate observed_inputs.
    result = {}
    for c in node.inputConnections():
        source = c.inputNode() or c.subnetIndirectInput()
        require(source is not None, "Unreadable native source")
        require(str(c.inputIndex()) not in result, "Duplicate native socket")
        result[str(c.inputIndex())] = [source.path(), c.outputIndex()]
    return result


def graph(parent):
    nodes = (parent,) + tuple(parent.allSubChildren())
    require(len(nodes) <= 32, "32-node fixture ceiling")
    return {n.path(): {"type": n.type().name(), "inputs": sockets(n),
                      "parms": {p.name(): p.rawValue() for p in n.parms()},
                      "templates": n.parmTemplateGroup().asDialogScript(),
                      "position": list(n.position()), "comment": n.comment(),
                      "user_data": n.userDataDict(), "display": n.isDisplayFlagSet(),
                      "selected": n.isSelected(), "color": list(n.color().rgb())}
            for n in nodes}


def usd(node):
    stage = node.stage(output_index=0, apply_viewport_overrides=False)
    require(stage is not None and not node.errors(), "Native USD cook failed: " + repr(node.errors()))
    require(not stage.GetCompositionErrors(), "USD composition errors")
    return {str(p.GetPath()): {"type": p.GetTypeName(),
                             "attributes": {a.GetName(): primitive(a.Get()) for a in p.GetAttributes()},
                             "relationships": {r.GetName(): [str(t) for t in r.GetTargets()]
                                               for r in p.GetRelationships()}}
            for p in stage.TraverseAll()}


def state(parent):
    return {"graph": graph(parent), "usd": {n.name(): usd(n) for n in parent.children()}}


def field_diffs(expected, actual, path=""):
    """Exact JSON-pointer differences. No field removal or normalization."""
    def child(key):
        return path + "/" + str(key).replace("~", "~0").replace("/", "~1")
    if type(expected) is not type(actual):
        return [{"path": path, "kind": "type_or_value", "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        rows = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                rows.append({"path": child(key), "kind": "unexpected_field", "actual": actual[key]})
            elif key not in actual:
                rows.append({"path": child(key), "kind": "missing_field", "expected": expected[key]})
            else:
                rows.extend(field_diffs(expected[key], actual[key], child(key)))
        return rows
    if isinstance(expected, list):
        rows = []
        for index in range(max(len(expected), len(actual))):
            if index >= len(expected):
                rows.append({"path": child(index), "kind": "unexpected_element", "actual": actual[index]})
            elif index >= len(actual):
                rows.append({"path": child(index), "kind": "missing_element", "expected": expected[index]})
            else:
                rows.extend(field_diffs(expected[index], actual[index], child(index)))
        return rows
    return [] if expected == actual else [{"path": path, "kind": "value", "expected": expected, "actual": actual}]


def measured_snapshot(name, parent):
    value = state(parent)
    path = OUT / (name + ".json")
    write(path, value)
    return value, {"path": str(path), "sha256": sha(path)}


def measured_comparison(name, expected, actual):
    rows = field_diffs(expected, actual)
    result = {"strict_equal": expected == actual, "difference_count": len(rows), "differences": rows}
    require(result["strict_equal"] is (not rows), "Diff implementation disagrees with exact equality")
    path = OUT / (name + "-diff.json")
    write(path, result)
    return {**result, "artifact": str(path), "sha256": sha(path)}


def labeled(node, label):
    values = [p for p in node.parms() if p.parmTemplate().label() == label]
    require(len(values) == 1, "Unsupported native schema: " + label)
    return values[0]


def setup(merge=False):
    HOU.hipFile.clear(suppress_save_prompt=True)
    parent = HOU.node("/stage").createNode("subnet", "seven_fix_fixture", run_init_scripts=False)
    source = parent.createNode("subnet", "source", run_init_scripts=False)
    require(source.type().maxNumOutputs() >= 2, "Two native subnet outputs unavailable")
    for index in (0, 1):
        script = source.createNode("pythonscript", "marker_" + str(index), run_init_scripts=False)
        labeled(script, "Python Code").set(
            "from pxr import Sdf\n"
            "stage = hou.pwd().editableStage()\n"
            "prim = stage.DefinePrim('/NativeMarker', 'Scope')\n"
            "prim.CreateAttribute('test:output', Sdf.ValueTypeNames.Int).Set(%d)\n" % index)
        output = source.createNode("output", "out_" + str(index), run_init_scripts=False)
        labeled(output, "Output Index").set(index)
        output.setInput(0, script, 0)
    sink = parent.createNode("merge" if merge else "null", "sink", run_init_scripts=False)
    sink.setInput(0, source, 1)
    sink.setDisplayFlag(True)
    # Fixture spare scalar gives the managed-parm contract a measured native value.
    sink.addSpareParmTuple(HOU.FloatParmTemplate("native_gain", "Native Gain", 1, default_value=(0.0,)))
    sentry = parent.createNode("null", "sentry", run_init_scripts=False)
    sentry.setInput(0, source, 0)
    sentry.setComment("artist sentry")
    sentry.setPosition(HOU.Vector2(14, 9))
    sentry.setUserData("native_sentry", "unchanged")
    require(usd(sink)["/NativeMarker"]["attributes"]["test:output"] == 1, "Native output-1 qualification")
    require(usd(sentry)["/NativeMarker"]["attributes"]["test:output"] == 0, "Native output-0 qualification")
    return parent


def base_request():
    return {"parent": PARENT, "frame": False, "sections": False, "splice_layout": "side",
            "nodes": [{"id": "source", "existing": True, "name": "source", "parms": []},
                      {"id": "sink", "type": "null", "parms": {"native_gain": 2.5}}],
            "connections": [{"from": "source", "to": "sink", "input": 0, "output": 1}],
            "display_node": "sink"}


def invoke(request):
    global CALLS
    CALLS += 1
    require(CALLS <= 80, "Handler-call ceiling")
    original = copy.deepcopy(request)
    try:
        return SUBJECT._handle_solaris_build_graph(request)
    finally:
        require(request == original, "Handler mutated request")


def rejected(parent, request, text):
    before, labels = state(parent), tuple(HOU.undos.undoLabels())
    try:
        invoke(request)
    except ERROR as error:
        require(text.lower() in str(error).lower(), "Wrong structured rejection: " + str(error))
        message = str(error)
    else:
        raise AssertionError("Invalid request was admitted")
    require(state(parent) == before, "Preflight rejection changed native graph/USD")
    require(tuple(HOU.undos.undoLabels()) == labels, "Preflight consumed/added undo history")
    return {"error": message, "graph_usd_unchanged": True, "undo_labels_unchanged": True}


def verified(parent, request):
    before = state(parent)
    preview = invoke({**request, "dry_run": True})
    require(preview["dry_run"] is True and preview["status"] == "preview", "False preview")
    require("verification" not in preview and state(parent) == before, "Preview mutated/claimed applied state")
    result = invoke(request)
    require(result["dry_run"] is False and result["verification"]["connections"] == "verified", "No verified apply")
    for wire in result["connections_made"]:
        require(sockets(HOU.node(wire["to"])).get(str(wire["input"])) == [wire["from"], wire["output"]],
                "Success receipt disagrees with native socket")
    require(state(parent)["graph"][PARENT + "/sentry"] == before["graph"][PARENT + "/sentry"], "Artist sentry changed")
    require(usd(parent.node("sentry")) == before["usd"]["sentry"], "Artist USD changed")
    applied = state(parent)
    repeat = invoke(request)
    require(repeat["status"] == "unchanged" and state(parent) == applied, "Second action is not idempotent")
    return {"preview": preview, "apply": result, "repeat": repeat, "state": applied}


def save_case(name, parent, request, observation):
    path = OUT / (name + ".hip")
    require(not path.exists(), "Existing HIP")
    HOU.hipFile.save(str(path), save_to_recent_files=False)
    write(OUT / (name + ".json"), {"hip_sha256": sha(path), "request": request, "observation": observation})
    return {"name": name, "hip": str(path), "sha256": sha(path), "state": state(parent), "request": request}


def build():
    cases, controls = [], []
    PROGRESS.update(cases=cases, controls=controls)
    parent = setup()
    request = base_request()
    for value in (None, 0, "", [], {}, "false"):
        controls.append({"fix": 5, "value": value, **rejected(parent, {**request, "dry_run": value}, "dry_run")})
    for value in (None, [], "", 0):
        bad = copy.deepcopy(request); bad["nodes"][1]["parms"] = value
        controls.append({"fix": 6, "value": value, **rejected(parent, bad, "parms")})
    for empty in (True, False):
        for value in ([], {}, False, 0):
            bad = {**request, "display_node": value}
            if empty:
                bad.update(nodes=[], connections=[])
            controls.append({"fix": 3, "empty": empty, "value": value, **rejected(parent, bad, "display_node")})
    controls.append({"fix": 3, **rejected(parent, {**request, "display_node": "missing"}, "display")})
    huge = 2 ** 100
    bad = {**request, "nodes": [{"id": "source", "existing": True, "name": "source"},
                                {"id": "merge", "type": "merge"}],
           "connections": [{"from": "source", "to": "merge", "input": 0},
                           {"from": "source", "to": "merge", "input": huge}], "display_node": "merge"}
    valid, errors, warnings = G.validate_graph(bad["nodes"], bad["connections"], "merge")
    require(valid and not errors and len(warnings) == 1 and len(warnings[0].encode()) < 512, "Unbounded gap diagnostic")
    controls.append({"fix": 4, "warning": warnings, **rejected(parent, bad, "port count")})
    outcome = verified(parent, request)
    require(parent.node("sink").parm("native_gain").eval() == 2.5, "Managed dictionary did not apply native scalar")
    require(usd(parent.node("sink"))["/NativeMarker"]["attributes"]["test:output"] == 1, "Valid native stage lost")
    cases.append(save_case("managed_preview_repeat", parent, request, outcome))
    parent = setup()
    request = {**base_request(), "nodes": [{"id": "source", "existing": True, "name": "source"},
                                          {"id": "sink", "existing": True, "name": "sink"},
                                          {"id": "inserted", "type": "null"}],
               "connections": [{"from": "source", "to": "inserted", "output": 0},
                               {"from": "inserted", "to": "sink", "input": 0, "insert": True}]}
    controls.append({"fix": 1, **rejected(parent, request, "output 1")})
    request["connections"][0]["output"] = 1
    outcome = verified(parent, request)
    require(sockets(parent.node("inserted"))["0"] == [PARENT + "/source", 1], "Displaced output lost")
    require(usd(parent.node("sink"))["/NativeMarker"]["attributes"]["test:output"] == 1, "Splice USD opinion lost")
    # Inline negative control: socket+USD oracles must reject a real wrong output.
    parent.node("inserted").setInput(0, parent.node("source"), 0)
    require(sockets(parent.node("inserted"))["0"] != [PARENT + "/source", 1], "Socket control did not bite")
    require(usd(parent.node("sink"))["/NativeMarker"]["attributes"]["test:output"] == 0, "USD control did not bite")
    parent.node("inserted").setInput(0, parent.node("source"), 1)
    cases.append(save_case("splice", parent, request, outcome))
    for reverse in (False, True):
        parent = setup(merge=True)
        implicit = {"from": "source", "to": "sink", "output": 1}
        explicit = {"from": "inserted", "to": "sink", "input": 0, "insert": True}
        request = {**request, "connections": [{"from": "source", "to": "inserted", "output": 1}]
                   + ([explicit, implicit] if reverse else [implicit, explicit])}
        outcome = verified(parent, request)
        require(sockets(parent.node("sink")) == {"0": [PARENT + "/inserted", 0], "1": [PARENT + "/source", 1]},
                "Explicit/implicit merge reservation depends on JSON order")
        require(usd(parent.node("sink"))["/NativeMarker"]["attributes"]["test:output"] == 1, "Merge composed stage lost")
        cases.append(save_case("merge_" + str(int(reverse)), parent, request, outcome))
    recovery = []
    PROGRESS["recovery"] = recovery
    for kind in ("wrong_output", "wrong_source", "disconnected"):
        parent = setup()
        request = base_request()
        before_save = state(parent)
        write(OUT / ("fault_" + kind + "-before-save.json"), before_save)
        checkpoint = OUT / ("before_fault_" + kind + ".hip")
        HOU.hipFile.save(str(checkpoint), save_to_recent_files=False)
        checkpoint_hash = sha(checkpoint)
        # Saving authors native metadata. The reference is the actual checkpoint
        # state, captured before any candidate call, never a filtered snapshot.
        before = state(parent)
        write(OUT / ("fault_" + kind + "-saved-checkpoint-state.json"), before)
        save_effect = measured_comparison("fault_" + kind + "-save-effect", before_save, before)
        labels = tuple(HOU.undos.undoLabels())
        enabled = HOU.undos.areEnabled()
        original = G._cook_and_collect_badges
        fired = []

        def late(nodes):
            result = original(nodes)  # Preserve actual native cook/badge path.
            sink, source = parent.node("sink"), parent.node("source")
            require(sockets(sink).get("0") == [source.path(), 1], "Fault fired before requested socket landed")
            sink.setInput(0, source if kind == "wrong_output" else parent.node("sentry") if kind == "wrong_source" else None, 0)
            injected = {"graph": graph(parent), "usd": {}}
            for node in parent.children():
                try:
                    injected["usd"][node.name()] = usd(node)
                except Exception as error:
                    injected["usd"][node.name()] = {"native_observation_unavailable": type(error).__name__, "error": str(error)}
            injected_path = OUT / ("fault_" + kind + "-injected-state.json")
            write(injected_path, injected)
            fired.append({"kind": kind, "after_actual_cook": True, "actual_corrupted_socket": sockets(sink),
                          "injected_state_path": str(injected_path), "injected_state_sha256": sha(injected_path)})
            return result

        G._cook_and_collect_badges = late
        try:
            try:
                invoke(request)
            except ERROR as error:
                require("final connection" in str(error).lower(), "Wrong late failure: " + str(error))
                message = str(error)
            else:
                raise AssertionError("Stale verified receipt escaped after actual native corruption")
        finally:
            G._cook_and_collect_badges = original
        require(len(fired) == 1, "Fault not observed exactly once")
        after = state(parent)
        write(OUT / ("fault_" + kind + "-after-handler.json"), after)
        labels_after = tuple(HOU.undos.undoLabels())
        rollback = "RESTORED" if enabled and after == before and labels_after == labels else "NOT_RESTORED" if after != before else "UNKNOWN"
        item = {"kind": kind, "error": message, "fault": fired, "undo_enabled": enabled,
                "labels_before": labels, "labels_after": labels_after, "product_rollback": rollback,
                "pre_failure_state": before, "post_failure_state": after,
                "pre_save_state": before_save, "save_effect": save_effect,
                "product_rollback_diff": measured_comparison("fault_" + kind + "-product-rollback", before, after),
                "external_checkpoint_recovery": "PENDING"}
        recovery.append(item)
        # External checkpoint recovery is separately attributed, never product undo.
        HOU.hipFile.load(str(checkpoint), suppress_save_prompt=True, ignore_load_warnings=False)
        require(sha(checkpoint) == checkpoint_hash, "Checkpoint changed")
        parent = HOU.node(PARENT)
        restored = state(parent)
        write(OUT / ("fault_" + kind + "-after-reload.json"), restored)
        item.update(external_restored_state=restored,
                    external_reload_diff=measured_comparison("fault_" + kind + "-external-reload", before, restored),
                    external_checkpoint_recovery="PASS" if restored == before else "FAILED_EXACT_EQUALITY")
        require(restored == before, "External checkpoint recovery failed")
        replay = verified(parent, request)
        item["replay"] = replay
        cases.append(save_case("recovery_" + kind, parent, request, replay))
    return {"cases": cases, "controls": controls, "recovery": recovery,
            "product_rollback_gate": "PASS" if all(r["product_rollback"] == "RESTORED" for r in recovery) else "UNAVAILABLE_OR_FAIL"}


def reopen():
    previous = read(OUT / "build.json")
    require(previous["status"] == "ASSERTIONS_PASSED" and previous["pid"] != os.getpid(), "Fresh successful build absent")
    outcomes = []
    PROGRESS["reopened"] = outcomes
    for case in previous["cases"]:
        path = Path(case["hip"])
        require(path.resolve().is_relative_to(OUT) and sha(path) == case["sha256"], "HIP pin changed/outside run")
        HOU.hipFile.load(str(path), suppress_save_prompt=True, ignore_load_warnings=False)
        parent = HOU.node(PARENT)
        reopened_state = state(parent)
        write(OUT / (case["name"] + "-reopened-state.json"), reopened_state)
        reopened_diff = measured_comparison(case["name"] + "-fresh-reopen", case["state"], reopened_state)
        item = {"case": case["name"], "reopen": "PASS" if reopened_state == case["state"] else "FAILED_EXACT_EQUALITY",
                "replay": "PENDING", "different_process": True, "reopen_diff": reopened_diff}
        outcomes.append(item)
        require(reopened_state == case["state"], "Fresh-process reopen graph/USD mismatch")
        repeat = invoke(case["request"])
        require(repeat["status"] == "unchanged" and state(parent) == case["state"], "Reopened second action changed scene")
        parent = setup(merge=case["name"].startswith("merge_"))
        verified(parent, case["request"])
        replay_before_save = state(parent)
        write(OUT / (case["name"] + "-replay-before-save.json"), replay_before_save)
        # Match the original case's persistence boundary: save first, then
        # compare every field. Keep the pre-save state and its exact differences.
        replay_hip = OUT / (case["name"] + "-replay.hip")
        require(not replay_hip.exists(), "Preserve existing replay HIP")
        HOU.hipFile.save(str(replay_hip), save_to_recent_files=False)
        replay_saved = state(parent)
        write(OUT / (case["name"] + "-replay-saved-state.json"), replay_saved)
        item.update(replay_save_effect=measured_comparison(case["name"] + "-replay-save", replay_before_save, replay_saved),
                    replay_diff=measured_comparison(case["name"] + "-fresh-replay", case["state"], replay_saved),
                    replay_hip_sha256=sha(replay_hip),
                    replay="PASS" if replay_saved == case["state"] else "FAILED_EXACT_EQUALITY")
        require(replay_saved == case["state"], "Replay from independently recreated fixture differs")
    return {"reopened": outcomes, "build_report_sha256": sha(OUT / "build.json")}


def early_native_gate(phase):
    """Persist native identity before any candidate import or fixture mutation."""
    gate = {"commit": HEAD, "phase": phase, "pid": os.getpid(), "status": "PENDING",
            "candidate_imported": False, "expected_build": "22.0.400", "expected_category": "Indie",
            "actual_build": None, "actual_version": None, "actual_license_category": None,
            "is_ui_available": None, "python_version": sys.version,
            "license_request": {"HOUDINI_SCRIPT_LICENSE": os.environ.get("HOUDINI_SCRIPT_LICENSE"),
                                "HOUDINI_HYTHON_LIC_OPT": os.environ.get("HOUDINI_HYTHON_LIC_OPT")},
            "native_environment": {"HFS": os.environ.get("HFS"), "HB": os.environ.get("HB"),
                                   "HHP": os.environ.get("HHP"),
                                   "PATH_first": os.environ.get("PATH", "").split(os.pathsep)[0]},
            "seat_scope": "HOM category is not a seat identifier; owner reserves headless availability and protects GUI; no release/reclaim API used"}
    write(OUT / (phase + "-native-gate-start.json"), gate)
    failure = None
    try:
        require(not any(n == "synapse" or n.startswith("synapse.") or n == "release_subject"
                        or n.startswith("release_subject.") for n in sys.modules), "Candidate/production code imported before gate")
        require(sys.version.startswith("3.13."), "Wrong Python ABI")
        require(gate["license_request"] == {"HOUDINI_SCRIPT_LICENSE": "hbatch", "HOUDINI_HYTHON_LIC_OPT": INDIE_OPTIONS},
                "Indie-only child request absent")
        hfs = Path(r"C:\Program Files\Side Effects Software\Houdini 22.0.400").resolve()
        for key, expected in {"HFS": hfs, "HB": hfs / "bin", "HHP": hfs / "houdini/python3.13libs", "PATH_first": hfs / "bin"}.items():
            require(gate["native_environment"][key] and Path(gate["native_environment"][key]).resolve() == expected,
                    "Incorrect child native environment: " + key)
        import hou
        gate.update(actual_build=hou.applicationVersionString(), actual_version=list(hou.applicationVersion()),
                    is_ui_available=hou.isUIAvailable(),
                    actual_main_thread=threading.current_thread() is threading.main_thread())
        category = hou.licenseCategory()
        gate["actual_license_category"] = str(category)
        require(gate["actual_build"] == "22.0.400" and gate["actual_version"] == [22, 0, 400], "Unexpected native build")
        require(category == hou.licenseCategoryType.Indie, "Unexpected/unavailable native licence category")
        require(gate["is_ui_available"] is False and gate["actual_main_thread"], "Not headless/main thread")
        gate["status"] = "PASSED"
    except Exception as error:
        failure = error
        gate.update(status="FAILED", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    # A failed/import-unavailable gate is durable and never reaches candidate code.
    write(OUT / (phase + "-native-gate.json"), gate)
    if failure is not None:
        raise failure
    return hou


def focused_diagnostics(phase):
    """Observation-only diagnostics; strict failures remain failures, never PASS."""
    plan = read(ROOT / "focused-plan.json")
    require(plan["commit"] == HEAD, "Wrong focused source pin")
    observations = {"mode": "FOCUSED_STATE_DIAGNOSTICS", "qualification_verdict": "INCOMPLETE",
                    "assertions_unchanged": True, "snapshots": {}, "comparisons": {}}
    PROGRESS["diagnostics"] = observations
    if phase == "reopen":
        descriptor = plan["passing_case"]
        hip = ROOT / descriptor["hip_relative"]
        old_report = read(ROOT / descriptor["build_relative"])
        require(sha(hip) == descriptor["hip_sha256"], "Passing HIP changed")
        require(sha(ROOT / descriptor["build_relative"]) == descriptor["build_sha256"], "Passing build evidence changed")
        case = next(row for row in old_report["cases"] if row["name"] == descriptor["name"])
        require(case["sha256"] == descriptor["hip_sha256"] and old_report["pid"] != os.getpid(), "Not independently reopened passing case")
        HOU.hipFile.load(str(hip), suppress_save_prompt=True, ignore_load_warnings=False)
        parent = HOU.node(PARENT)
        actual, record = measured_snapshot("independent-passing-splice-reopen", parent)
        expected_path = OUT / "independent-passing-splice-expected.json"
        write(expected_path, case["state"])
        comparison = measured_comparison("independent-passing-splice-reopen", case["state"], actual)
        observations.update(passing_case=descriptor["name"], prior_build_status=old_report["status"],
                            different_process=True, prior_pid=old_report["pid"],
                            full_state_reopen="PASS" if comparison["strict_equal"] else "FAILED_EXACT_EQUALITY",
                            usd_exact_equal=case["state"]["usd"] == actual["usd"],
                            sockets_exact_equal={k: v["inputs"] for k, v in case["state"]["graph"].items()} ==
                                                {k: v["inputs"] for k, v in actual["graph"].items()},
                            candidate_handler_calls=0, snapshot=record, comparison=comparison)
        return {"diagnostics": observations}
    parent = setup()
    before_save, record = measured_snapshot("baseline-before-save", parent)
    observations["snapshots"]["before_save"] = record
    checkpoint = OUT / "baseline-before-any-candidate.hip"
    HOU.hipFile.save(str(checkpoint), save_to_recent_files=False)
    checkpoint_sha = sha(checkpoint)
    after_save, record = measured_snapshot("baseline-after-save", parent)
    observations["snapshots"]["after_save"] = record
    observations["comparisons"]["save_effect"] = measured_comparison("baseline-save", before_save, after_save)
    HOU.hipFile.load(str(checkpoint), suppress_save_prompt=True, ignore_load_warnings=False)
    parent = HOU.node(PARENT)
    baseline_loaded, record = measured_snapshot("baseline-after-reload-without-candidate", parent)
    observations["snapshots"]["baseline_loaded"] = record
    observations["comparisons"]["reload_without_candidate"] = measured_comparison("baseline-reload-no-candidate", before_save, baseline_loaded)
    require(sha(checkpoint) == checkpoint_sha, "Original checkpoint changed")
    canonical_checkpoint = OUT / "loaded-baseline-before-fault.hip"
    HOU.hipFile.save(str(canonical_checkpoint), save_to_recent_files=False)
    canonical_hash = sha(canonical_checkpoint)
    before_fault, record = measured_snapshot("fault-before-candidate", parent)
    observations["snapshots"]["before_fault"] = record
    observations["comparisons"]["canonical_save_effect"] = measured_comparison("loaded-baseline-save", baseline_loaded, before_fault)
    request = base_request()
    enabled, labels_before = HOU.undos.areEnabled(), tuple(HOU.undos.undoLabels())
    original = G._cook_and_collect_badges
    fired = []
    failure_message = None

    def late(nodes):
        result = original(nodes)
        sink, source = parent.node("sink"), parent.node("source")
        require(sockets(sink).get("0") == [source.path(), 1], "Fault before requested real socket landed")
        sink.setInput(0, source, 0)
        injected, record = measured_snapshot("fault-actual-injected-wrong-output", parent)
        observations["snapshots"]["injected"] = record
        fired.append({"actual_socket": sockets(sink), "actual_usd": injected["usd"]["sink"]})
        return result

    G._cook_and_collect_badges = late
    try:
        try:
            invoke(request)
        except ERROR as error:
            require("final connection" in str(error).lower(), "Unexpected failure class/message")
            failure_message = str(error)
    finally:
        G._cook_and_collect_badges = original
    after_handler, record = measured_snapshot("fault-after-candidate-rollback", parent)
    observations["snapshots"]["after_handler"] = record
    observations.update(fault=fired, handler_error=failure_message, undo_enabled=enabled,
                        undo_labels_before=labels_before, undo_labels_after=tuple(HOU.undos.undoLabels()))
    observations["comparisons"]["product_rollback"] = measured_comparison("candidate-product-rollback", before_fault, after_handler)
    require(len(fired) == 1 and failure_message is not None, "Native corrupted socket escaped fail-closed verification")
    HOU.hipFile.load(str(canonical_checkpoint), suppress_save_prompt=True, ignore_load_warnings=False)
    require(sha(canonical_checkpoint) == canonical_hash, "Canonical checkpoint changed")
    parent = HOU.node(PARENT)
    after_reload, record = measured_snapshot("fault-after-tester-checkpoint-reload", parent)
    observations["snapshots"]["after_reload"] = record
    comparison = measured_comparison("tester-checkpoint-recovery", before_fault, after_reload)
    observations["comparisons"]["external_checkpoint"] = comparison
    observations["external_checkpoint_verdict"] = "PASS" if comparison["strict_equal"] else "FAILED_EXACT_EQUALITY"
    observations["product_rollback_verdict"] = "RESTORED" if enabled and before_fault == after_handler and tuple(observations["undo_labels_after"]) == labels_before else "UNAVAILABLE_UNDO_DISABLED" if not enabled else "NOT_RESTORED"
    if comparison["strict_equal"]:
        observations["valid_retry"] = verified(parent, request)
    else:
        observations["valid_retry"] = "SKIPPED; exact checkpoint equality failed"
    return {"diagnostics": observations}


def main():
    global HOU, G, SUBJECT, ERROR, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("build", "reopen"))
    parser.add_argument("--slot", type=Path, required=True)
    parser.add_argument("--slot-sha256", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    manifest = pins(); slot(args.slot, args.slot_sha256, args.phase)
    require(args.diagnostic is (manifest.get("execution_mode") == "focused-state-diagnostics"), "Worker/manifest diagnostic-mode mismatch")
    OUT = args.run_root.resolve()
    require(OUT.is_relative_to(ROOT / "runs") and OUT.is_dir(), "Run directory not private/existing")
    require(not (OUT / "CANCEL").exists(), "Cancelled")
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode, "Need -I -S -B")
    hfs = Path(r"C:\Program Files\Side Effects Software\Houdini 22.0.400")
    require(Path(sys.executable).resolve() == (hfs / "python313/python.exe").resolve(), "Wrong native interpreter")
    require(os.environ.get("HOUDINI_MAXTHREADS") == "2", "Two-thread child configuration absent")
    require(os.environ.get("HOUDINI_PACKAGE_SKIP") == "1" and os.environ.get("HOUDINI_NO_ENV_FILE") == "1", "Child startup settings absent")
    for key in ("HOUDINI_USER_PREF_DIR", "HOUDINI_TEMP_DIR", "TEMP", "TMP"):
        require(Path(os.environ[key].replace("__HVER__", "22.0")).resolve().is_relative_to(OUT), "Non-private child path: " + key)
    sys.path.insert(0, str(hfs / "houdini/python3.13libs"))
    dll_handle = os.add_dll_directory(str(hfs / "bin"))
    hou = early_native_gate(args.phase)
    HOU = hou
    gate_path = OUT / (args.phase + "-native-gate.json")
    require(read(gate_path)["status"] == "PASSED", "Persisted native identity gate did not pass")
    sys.path.insert(0, str(ROOT))
    loader = importlib.import_module("subject_loader")
    SUBJECT, _, ERROR = loader.load_subject(ROOT / "source", ROOT / "source-manifest.json")
    G = importlib.import_module("release_subject.server.handlers_solaris_graph")
    from pxr import Usd
    started = time.perf_counter()
    report = {"commit": HEAD, "pid": os.getpid(), "phase": args.phase, "native": True,
              "houdini_build": hou.applicationVersionString(), "usd_version": list(Usd.GetVersion()),
              "license_category": str(hou.licenseCategory()), "actor": "external tester; copied complete handler",
              "early_native_gate_sha256": sha(gate_path),
              "status": "FAILED", "unverified": ["production install/panel/bridge/dispatcher", "Kestrel benefit",
              "whole-catalog freshness/strict companion battery", "GUI-specific undo/automatic display callbacks"]}
    try:
        report.update(focused_diagnostics(args.phase) if args.diagnostic else build() if args.phase == "build" else reopen())
        pins(); slot(args.slot, args.slot_sha256, args.phase)
        report["status"] = "DIAGNOSTIC_OBSERVATIONS_COMPLETE" if args.diagnostic else "ASSERTIONS_PASSED"
    except Exception:
        report["exception"] = traceback.format_exc()
    finally:
        report.update(PROGRESS)  # Retain completed assertions when a later case fails.
        report.update(handler_calls=CALLS, wall_seconds=time.perf_counter() - started,
                      imported_source_paths=loader.imported_source_paths())
        write(OUT / (args.phase + ".json"), report)
    return 0 if report["status"] in ("ASSERTIONS_PASSED", "DIAGNOSTIC_OBSERVATIONS_COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
