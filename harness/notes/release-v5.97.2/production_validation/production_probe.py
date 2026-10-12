"""Real-package SynapseHandler/production bridge seam. Native UNRUN until fresh slot.
Fixture/state/identity ideas reused from v456; no namespace loader or fake bridge.
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
HEAD = "945df057aa1e6b3f4849d80332f762bf56911ca2"
INDIE_OPTIONS = "--skip-license-modes=commercial,education,apprentice"
PARENT = "/stage/production_bridge_fixture"
HOU = None
OUT = None
PROGRESS = {"calls": [], "phase": "NOT_STARTED"}

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
    parent = HOU.node("/stage").createNode("subnet", "production_bridge_fixture", run_init_scripts=False)
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
            "seat_scope": "HOM category is not a seat identifier; owner reserves separate graphical availability and protects GUI; no release/reclaim API used"}
    write(OUT / (phase + "-native-gate-start.json"), gate)
    failure = None
    try:
        require(not any(n == "synapse" or n.startswith("synapse.") or n == "release_subject"
                        or n.startswith("release_subject.") for n in sys.modules), "Candidate/production code imported before gate")
        require(sys.version.startswith("3.13."), "Wrong Python ABI")
        require(os.environ.get("SYNAPSE_GUI_LAUNCH_MODE") == "owned-indie-waitforui", "Owned graphical Indie launch declaration absent")
        hfs = Path(r"C:\Program Files\Side Effects Software\Houdini 22.0.400").resolve()
        for key, expected in {"HFS": hfs, "HB": hfs / "bin", "HHP": hfs / "houdini/python3.13libs", "PATH_first": hfs / "python313/Lib/site-packages-forced/PySide6"}.items():
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
        require(gate["is_ui_available"] is True and gate["actual_main_thread"], "Not graphical/main thread")
        gate["status"] = "PASSED"
    except Exception as error:
        failure = error
        gate.update(status="FAILED", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    # A failed/import-unavailable gate is durable and never reaches candidate code.
    write(OUT / (phase + "-native-gate.json"), gate)
    if failure is not None:
        raise failure
    return hou

def verify_pins():
    manifest = read(ROOT / 'prepared-pins.json')
    require(manifest['commit'] == HEAD and manifest['execution_mode'] == 'production-seam', 'Wrong sealed mode/head')
    for row in manifest['files']:
        require(sha(ROOT / row['path']) == row['sha256'], 'Changed preparation pin: ' + row['path'])
    for row in manifest['runtime_files']:
        require(sha(row['path']) == row['sha256'], 'Changed H22 runtime')
    source = read(ROOT / 'source-manifest.json')
    require(source['commit'] == HEAD, 'Wrong full candidate checkout')
    repo = Path(source['source_root']).resolve()
    for row in source['files']:
        path = (repo / row['path']).resolve()
        require(path.is_relative_to(repo) and sha(path) == row['sha256'], 'Changed candidate file: ' + row['path'])
    return manifest, source, repo


def verify_slot(path, digest):
    require(sha(path) == digest, 'Owner receipt changed')
    r = read(path)
    require(r['commit'] == HEAD and r['prepared_pins_sha256'] == sha(ROOT / 'prepared-pins.json'), 'Unapproved source/test pins')
    require(all(r[k] is True for k in ('native_clearance', 'indie_clearance', 'resource_owner_clearance', 'live_gui_preserved_clearance', 'graphical_clearance', 'desktop_owner_clearance')), 'Owner clearance absent')
    require(r['phases'] == ['production'], 'Wrong slot phase')
    require(r['limits'] == {'processes': 1, 'threads': 2, 'child_seconds': 120, 'aggregate_seconds': 180, 'memory_bytes': 8589934592, 'artifact_bytes': 67108864}, 'Wrong resource envelope')
    require(r['not_before_unix'] <= time.time() < r['expires_unix'], 'Slot not active/expired')
    return r


def loaded_candidate_origins(source, repo):
    pinned = {row['path']: row['sha256'] for row in source['files']}
    rows = []
    require(not any(n == 'release_subject' or n.startswith('release_subject.') for n in sys.modules), 'Copied handler namespace imported')
    for name, module in sorted(sys.modules.copy().items()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if name == 'synapse' or name.startswith('synapse.') or name == 'shared' or name.startswith('shared.'):
            require(path.is_relative_to(repo), 'Candidate module came from another installation: ' + name)
        if path.is_relative_to(repo):
            relative = path.relative_to(repo).as_posix()
            require(relative in pinned and sha(path) == pinned[relative], 'Unpinned imported candidate file: ' + relative)
            rows.append({'module': name, 'path': relative, 'sha256': pinned[relative]})
    return rows


def phase(name, payload):
    PROGRESS['phase'] = name
    write(OUT / (name + '.json'), {'commit': HEAD, 'pid': os.getpid(), 'phase': name, **payload})


def require_integrity(response):
    require(response.success is True and isinstance(response.data, dict), 'Production call failed: ' + str(response.error))
    integrity = response.data.get('_integrity')
    require(isinstance(integrity, dict), 'Missing actual production IntegrityBlock')
    require(integrity['execution_path'] == 'mcp' and integrity['thread'] is True and integrity['undo'] is True
            and integrity['consent'] is True and integrity['composition_applicable'] is True
            and integrity['composition'] is True and integrity['stage_hash_full_fidelity'] is True,
            'Production bridge anchors missing or degraded')
    return integrity


def run_case(source, repo):
    # Full production package import AFTER persisted native identity gate.
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / 'python'))
    import synapse
    from synapse.core.protocol import SynapseCommand
    from synapse.core.audit import AuditLog
    from synapse.server.handlers import SynapseHandler
    from synapse.panel import bridge_adapter as adapter
    from synapse.server import handlers_solaris_graph as graph_module
    from shared import bridge as production
    require(synapse.__version__ == '5.97.2', 'Unexpected loaded release version')
    phase('production-import-availability', {'adapter_bridge_available': adapter._BRIDGE_AVAILABLE, 'bridge_hou_available': production._HOU_AVAILABLE, 'actual_hou_identity': production.hou is HOU, 'bridge_hdefereval_origin': getattr(production.hdefereval, '__file__', None)})
    require(adapter._BRIDGE_AVAILABLE and production._HOU_AVAILABLE and production.hou is HOU, 'Production bridge/HOM unavailable; no direct fallback')
    require(production.hdefereval is importlib.import_module('hdefereval'), 'Substituted main-thread marshal')
    # Supported real audit singleton configuration; no replacement class/handler.
    require(AuditLog._instance is None, 'Audit singleton was initialized before private configuration')
    audit = AuditLog.get_instance(log_dir=OUT / 'audit')
    require(audit._log_dir.resolve().is_relative_to(OUT), 'Audit path outside owned run')
    bridge = adapter.get_bridge()
    require(bridge is not None and type(bridge) is production.LosslessExecutionBridge, 'Real bridge absent')
    handler = SynapseHandler()
    registered = handler._registry.get('solaris_build_graph')
    require(registered is not None and registered.__self__ is handler and registered.__func__ is graph_module.SolarisGraphMixin._handle_solaris_build_graph, 'Wrong registered graph authority')
    imported = loaded_candidate_origins(source, repo)
    phase('01-real-package', {'version': synapse.__version__, 'loaded_modules': imported, 'bridge_class': type(bridge).__module__ + '.' + type(bridge).__name__,
                             'handler_class': type(handler).__module__ + '.' + type(handler).__name__, 'real_hou': True, 'direct_fallback': False})

    parent = HOU.node(PARENT)
    require(parent is not None and HOU.undos.areEnabled(), 'Private fixture/actual undo unavailable')
    request = {'parent': PARENT, 'frame': False, 'sections': False, 'splice_layout': 'side',
               'nodes': [{'id': 'source', 'existing': True, 'name': 'source'},
                         {'id': 'sink', 'existing': True, 'name': 'sink'},
                         {'id': 'merge', 'existing': True, 'name': 'merge'},
                         {'id': 'inserted', 'type': 'null'}],
               'connections': [{'from': 'source', 'to': 'inserted', 'output': 1},
                               {'from': 'inserted', 'to': 'sink', 'input': 0, 'insert': True},
                               {'from': 'source', 'to': 'merge', 'output': 1},
                               {'from': 'source', 'to': 'merge', 'input': 0, 'output': 1}],
               'display_node': 'sink'}
    require(usd(parent)['/NativeMarker']['attributes']['test:output'] == 1, 'Fixture parent stage unavailable')

    def invoke(name, payload):
        require(len(PROGRESS['calls']) < 8, 'Eight-call ceiling')
        require(threading.current_thread() is threading.main_thread(), 'Native call off main thread')
        command = SynapseCommand(type='solaris_build_graph', id='native-production-' + name, payload=copy.deepcopy(payload), client_version='5.97.2')
        original = copy.deepcopy(command.payload)
        started = time.perf_counter()
        response = adapter.execute_through_bridge('synapse_solaris_build_graph', handler, command)
        require(command.payload == original, 'Production dispatch mutated caller request')
        wire_response = json.loads(response.to_json())
        row = {'name': name, 'wall_seconds': time.perf_counter() - started, 'response': wire_response,
               'bridge_stats': bridge.operation_stats(), 'undo_labels': list(HOU.undos.undoLabels())}
        PROGRESS['calls'].append(row)
        phase('call-' + name, row)
        return response

    baseline, baseline_artifact = measured_snapshot('baseline-before-preview', parent)
    labels_baseline = tuple(HOU.undos.undoLabels())
    preview = invoke('preview', {**request, 'dry_run': True})
    require_integrity(preview)
    require(preview.data['status'] == 'preview' and preview.data['dry_run'] is True and 'verification' not in preview.data, 'Preview claimed apply')
    preview_state, preview_artifact = measured_snapshot('after-preview', parent)
    preview_diff = measured_comparison('preview', baseline, preview_state)
    require(preview_diff['strict_equal'] and tuple(HOU.undos.undoLabels()) == labels_baseline, 'Preview changed native scene/history')
    applied = invoke('apply', request)
    require_integrity(applied)
    require(applied.data['verification']['connections'] == 'verified' and applied.data['dry_run'] is False, 'Missing verified production apply')
    for wire in applied.data['connections_made']:
        require(sockets(HOU.node(wire['to'])).get(str(wire['input'])) == [wire['from'], wire['output']], 'Receipt disagrees with actual HOM')
    require(sockets(parent.node('inserted')) == {'0': [PARENT + '/source', 1]}, 'Insertion displaced output1')
    require(sockets(parent.node('sink')) == {'0': [PARENT + '/inserted', 0]}, 'Insertion destination incorrect')
    require(sockets(parent.node('merge')) == {'0': [PARENT + '/source', 1], '1': [PARENT + '/source', 1]}, 'Reserved merge input lost on production route')
    require(usd(parent.node('sink'))['/NativeMarker']['attributes']['test:output'] == 1, 'Applied USD output opinion incorrect')
    require(graph(parent)[PARENT + '/sentry'] == baseline['graph'][PARENT + '/sentry'], 'Artist sentry changed on apply')
    applied_state, applied_artifact = measured_snapshot('after-apply', parent)
    repeat = invoke('repeat', request)
    require_integrity(repeat)
    repeated_state, repeated_artifact = measured_snapshot('after-repeat', parent)
    repeat_diff = measured_comparison('repeat', applied_state, repeated_state)
    require(repeat.data['status'] == 'unchanged' and repeat_diff['strict_equal'], 'Production repeat is not idempotent')
    phase('02-positive-outcomes', {'baseline': baseline_artifact, 'preview': preview_artifact, 'preview_diff': preview_diff,
                                  'apply': applied_artifact, 'repeat': repeated_artifact, 'repeat_diff': repeat_diff,
                                  'native_socket_checks': 'PASS', 'native_usd_checks': 'PASS'})

    # Save-time metadata is retained and enters the BEFORE reference, never filtered.
    before_save = state(parent)
    checkpoint = OUT / 'private-production-checkpoint.hip'
    HOU.hipFile.save(str(checkpoint), save_to_recent_files=False)
    save_effect = measured_comparison('checkpoint-save-effect', before_save, state(parent))
    with HOU.undos.group('SYNAPSE TEST: private artist history sentry'):
        parent.node('sentry').setComment('artist sentry with preexisting history')
    before_fault, before_artifact = measured_snapshot('before-fault-saved-reference', parent)
    labels_before = tuple(HOU.undos.undoLabels())
    require(any('private artist history sentry' in s for s in labels_before), 'No preexisting artist-history sentry')
    original_cook = graph_module._cook_and_collect_badges
    fired = []
    verified_before = bridge.operation_stats()['operations_verified']

    def corrupt_after_real_cook(nodes):
        badges = original_cook(nodes)
        inserted, source_node = parent.node('inserted'), parent.node('source')
        require(sockets(inserted).get('0') == [source_node.path(), 1], 'Fault before desired wire landed')
        inserted.setInput(0, source_node, 0)
        injected, artifact = measured_snapshot('fault-injected-after-real-cook', parent)
        require(injected['usd']['sink']['/NativeMarker']['attributes']['test:output'] == 0, 'USD negative control did not bite')
        fired.append({'after_real_cook': True, 'actual_socket': sockets(inserted), 'artifact': artifact})
        return badges

    graph_module._cook_and_collect_badges = corrupt_after_real_cook
    try:
        failure = invoke('fault', request)
    finally:
        graph_module._cook_and_collect_badges = original_cook
    require(len(fired) == 1 and failure.success is False and 'final connection' in str(failure.error).lower(), 'Final drift escaped production refusal')
    require(not isinstance(failure.data, dict) or 'verification' not in failure.data, 'Failure emitted verified-wire claim')
    failed_state, failed_artifact = measured_snapshot('after-failure-outer-group-closed', parent)
    require(failed_state != before_fault and sockets(parent.node('inserted')).get('0') == [PARENT + '/source', 0], 'Expected residual outer-group state not observed')
    require('rolled back' not in str(failure.error).lower(), 'Failure falsely claimed restoration')
    integrity = failure.data.get('_integrity', {}) if isinstance(failure.data, dict) else {}
    require(integrity.get('thread') is True and integrity.get('undo') is True and integrity.get('delta_hash') != 'rolled_back', 'Failure integrity contradicts outer-group state')
    verified_delta = bridge.operation_stats()['operations_verified'] - verified_before
    require(verified_delta == 0, 'Failed handler counted as verified production operation')
    phase('03-drift-refusal', {'fault': fired, 'before': before_artifact, 'after': failed_artifact, 'failure': json.loads(failure.to_json()),
                             'save_effect': save_effect, 'checkpoint_sha256': sha(checkpoint), 'labels_before': labels_before,
                             'labels_after': list(HOU.undos.undoLabels()), 'post_fault_verified_delta': verified_delta,
                             'automatic_product_restoration': 'NOT_RESTORED_OUTER_GROUP; honest refusal'})

    # Actual artist-style native undo AFTER production bridge group has closed.
    HOU.undos.performUndo()
    restored_state, restored_artifact = measured_snapshot('after-artist-undo', parent)
    restoration = measured_comparison('artist-undo-restoration', before_fault, restored_state)
    require(restoration['strict_equal'] and tuple(HOU.undos.undoLabels()) == labels_before, 'Native post-group artist undo did not restore exact scene/history')
    recovery = invoke('recovery-repeat', request)
    require_integrity(recovery)
    require(recovery.data['status'] == 'unchanged' and state(parent) == before_fault, 'Restored production graph cannot repeat cleanly')
    from synapse.memory import store as memory_module
    owner = memory_module._global_synapse
    require(owner is not None and Path(owner.storage_dir).resolve().is_relative_to(OUT), 'Production memory owner not inside private run')
    final_imports = loaded_candidate_origins(source, repo)
    phase('04-artist-recovery', {'restoration': restoration, 'restored': restored_artifact, 'labels_restored': True,
                               'private_memory_owner': str(owner.storage_dir), 'audit_root': str(audit._log_dir),
                               'loaded_modules': final_imports, 'bridge_stats': bridge.operation_stats()})
    return {'production_path': 'REAL_PACKAGE_REAL_BRIDGE', 'calls': PROGRESS['calls'], 'preview_graph_usd_history': 'PASS',
            'apply_socket_usd': 'PASS', 'repeat_full_state': 'PASS', 'final_drift_refusal': 'PASS',
            'artist_undo_restoration': 'PASS', 'post_fault_verified_delta': verified_delta,
            'automatic_product_restoration': 'NOT_RESTORED_OUTER_GROUP; honest refusal; artist undo restores',
            'loaded_candidate_modules': final_imports, 'bridge_stats': bridge.operation_stats()}


def main():
    global HOU, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['production'], required=True)
    parser.add_argument('--slot', type=Path, required=True)
    parser.add_argument('--slot-sha256', required=True)
    parser.add_argument('--run-root', type=Path, required=True)
    args = parser.parse_args()
    OUT = args.run_root.resolve()
    require(OUT.is_relative_to(ROOT / 'runs') and OUT.is_dir(), 'Owned run root absent')
    report = {'commit': HEAD, 'pid': os.getpid(), 'phase': 'production', 'status': 'FAILED', 'calls': PROGRESS['calls'],
              'scope': 'Real candidate package, registry, production bridge and post-group native undo; no GUI/transport/installer/benchmark',
              'unverified': ['painted GUI/transport callbacks', 'copied-Kestrel benefit', 'whole-catalog/strict battery', 'installer/seat identity']}
    started = time.perf_counter()
    original_update_mode = None
    try:
        manifest, source, repo = verify_pins()
        verify_slot(args.slot, args.slot_sha256)
        require(sys.flags.dont_write_bytecode and os.environ.get('PYTHONNOUSERSITE') == '1', 'Private graphical Python startup flags absent')
        hfs = Path(r'C:\Program Files\Side Effects Software\Houdini 22.0.400')
        require(Path(sys.executable).resolve().parent == (hfs / 'bin').resolve(), 'Wrong graphical executable directory')
        require(os.environ.get('HOUDINI_MAXTHREADS') == '2' and os.environ.get('HOUDINI_PACKAGE_SKIP') == '1' and os.environ.get('HOUDINI_NO_ENV_FILE') == '1', 'Startup/resource settings absent')
        require(os.environ.get('SYNAPSE_LOOP_ENABLED') == '0' and os.environ.get('SYNAPSE_AUTO_MEMORY') == '0', 'Opt-in autonomous housekeeping active')
        for key in ('HOUDINI_USER_PREF_DIR', 'HOUDINI_TEMP_DIR', 'TEMP', 'TMP', 'SYNAPSE_ROOT', 'SYNAPSE_LOG_DIR', 'SYNAPSE_PROVENANCE_DIR', 'SYNAPSE_LEDGER_DIR'):
            require(Path(os.environ[key].replace('__HVER__', '22.0')).resolve().is_relative_to(OUT), 'Non-private supported child path: ' + key)
        sys.path.insert(0, str(hfs / 'houdini/python3.13libs'))
        dll_handle = os.add_dll_directory(str(hfs / 'bin'))
        HOU = early_native_gate('production')
        gate_path = OUT / 'production-native-gate.json'
        require(read(gate_path)['status'] == 'PASSED', 'Persisted early identity gate absent')
        report['early_native_gate_sha256'] = sha(gate_path)
        expected_paths = read(ROOT / 'vendor-dependencies.json')['packages']
        actual_paths = {str(Path(p).resolve()).casefold() for p in HOU.houdiniPath()}
        require(all(str(Path(row['hpath']).resolve()).casefold() in actual_paths for row in expected_paths), 'Missing explicit vendor dependency hpath')
        require(not os.environ.get('HOUDINI_DISABLE_PDG'), 'Vendor GUI PDG initialization disabled')
        phase('vendor-gui-dependencies', {'houdini_path': list(HOU.houdiniPath()), 'packages': expected_paths,
                                         'ocio': os.environ.get('OCIO'), 'package_mode': 'Explicit installed vendor hpath equivalents; package scanning remains disabled'})
        actual_hdef = importlib.import_module('hdefereval')
        require(actual_hdef.hou is HOU, 'Graphical hdefereval not bound to actual HOM')
        phase('graphical-startup-context', {'hdefereval_origin': actual_hdef.__file__, 'sys_executable': sys.executable,
                                          'sys_path': list(sys.path), 'python_flags': str(sys.flags), 'ui_available': HOU.isUIAvailable()})

        # GUI starts manual for empty startup. Native LOP stage evaluation requires
        # the ordinary automatic update mode, enabled only in this owned session.
        original_update_mode = HOU.updateModeSetting()
        HOU.setUpdateMode(HOU.updateMode.AutoUpdate)
        require(HOU.updateModeSetting() == HOU.updateMode.AutoUpdate, 'Private fixture automatic cooking unavailable')
        phase('private-fixture-update-mode', {'before': str(original_update_mode), 'actual': str(HOU.updateModeSetting()),
                                             'scope': 'Owned synthetic <=32-node CPU LOP fixture only; no render/simulation/live scene'})
        # Vendor startup exposed an inherited user dependency directory at v484.
        # Exclude it before candidate imports; never unload already imported code
        # to manufacture a clean identity verdict.
        rejected = [p for p in sys.path if not p or not (Path(p).resolve().is_relative_to(hfs.resolve()) or Path(p).resolve().is_relative_to(ROOT))]
        sys.path[:] = [p for p in sys.path if p and p not in rejected]
        inherited_user_modules = []
        installed_user_root = (Path.home() / 'SYNAPSE').resolve()
        for name, module in list(sys.modules.items()):
            origin = getattr(module, '__file__', None)
            if origin and Path(origin).resolve().is_relative_to(installed_user_root):
                inherited_user_modules.append({'module': name, 'origin': origin})
        phase('private-python-search-path', {'excluded_paths': rejected, 'actual_paths': list(sys.path), 'inherited_user_modules': inherited_user_modules})
        require(not inherited_user_modules, 'Unrelated installed user module already loaded at GUI startup')

        # New private synthetic scene only; save BEFORE production memory imports.
        parent = setup()
        merge = parent.createNode('merge', 'merge', run_init_scripts=False)
        merge.setInput(0, parent.node('source'), 1)
        output = parent.createNode('output', 'fixture_output', run_init_scripts=False)
        labeled(output, 'Output Index').set(0)
        output.setInput(0, parent.node('sink'), 0)
        parent.node('sink').setDisplayFlag(True)
        HOU.hipFile.save(str(OUT / 'private-production-start.hip'), save_to_recent_files=False)
        phase('00-private-fixture', {'hip': HOU.hipFile.path(), 'initial_state': state(parent), 'actual_undo_enabled': HOU.undos.areEnabled()})
        report.update(run_case(source, repo))
        verify_pins()
        verify_slot(args.slot, args.slot_sha256)
        report['status'] = 'ASSERTIONS_PASSED'
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(), last_phase=PROGRESS['phase'])
    finally:
        if original_update_mode is not None:
            try:
                HOU.setUpdateMode(original_update_mode)
                report['private_update_mode_restored'] = HOU.updateModeSetting() == original_update_mode
                require(report['private_update_mode_restored'], 'Owned GUI update mode did not restore exactly')
            except Exception as error:
                report.update(status='FAILED', mode_restore_error=str(error))
        report['wall_seconds'] = time.perf_counter() - started
        report['calls'] = PROGRESS['calls']
        write(OUT / 'production.json', report)
    print(json.dumps({'status': report['status'], 'pid': os.getpid(), 'phase': report['phase'], 'calls': len(report['calls']), 'wall_seconds': report['wall_seconds']}))
    return 0 if report['status'] == 'ASSERTIONS_PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
