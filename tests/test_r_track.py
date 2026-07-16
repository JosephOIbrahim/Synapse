"""R track (release-readiness) — pins the 12 R-checks, the tasks.json R.1–R.R conformance
surface, and the guardrail freeze. Loaded by path like test_s_track.py — the harness verify
dir is not a package, so checks.py is exec'd under its own alias.

Seam discipline (mirrors tests/test_s_track.py):
  - fingerprint checks are pinned with SYNTHETIC worktrees planted under tmp_path
    (ctx['wt'] = tmp_path) — no sys.modules fakes, no monkeypatch of Path.read_text;
  - monkeypatch is reserved for the machine-level file seams (_posture_path,
    _receipts_path, _drop_path) and the capstone sub-check stubs (attr + DISPATCH row);
  - assertions on `detail` are SUBSTRING matches (the builder words the messages).

Every RED fixture reproduces the ACTUAL live fingerprint verified 2026-07-10
(spec-R-release-readiness.md "Ground truth") so the gate demonstrably fires on the real
defect shape, and every GREEN fixture reproduces the review's required fix shape.
"""
import importlib.util
import json
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_r", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

# guardrails.checks as of the graft's start — the R track adds TASK verifies, NEVER
# guardrails, so this list is frozen byte-for-byte (spec-R "Style & traps").
GUARDRAILS_FROZEN = [
    "scout_no_apex_corpus",
    "no_rigging_drift",
    "provenance_not_bypassed",
    "phantom_clean",
    "suite_baseline",
]

R_CHECKS = [
    "mutation_fail_closed",
    "runtime_owns_heartbeat",
    "hot_reload_gated",
    "deps_isolated",
    "installer_host_targeted",
    "ci_covers_shipping_surface",
    "shelf_current",
    "tool_metadata_single_source",
    "process_bridge_armed",
    "auth_fail_closed",
    "packaging_self_contained",
    "release_readiness_review",
]

_CTX_KEYS = {"hython": "", "mode": "A"}


def _ctx(wt, mode="A"):
    return {"wt": str(wt), "hython": "", "mode": mode}


def _plant(root, rel, text):
    p = pathlib.Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _run(name, ctx):
    """Reach a check through DISPATCH by name — the frozen surface, same as run_one."""
    fn = checks.DISPATCH.get(name)
    if fn is None:
        pytest.fail(f"DISPATCH lacks '{name}' — the R-checks have not landed")
    return fn(ctx)


def _redirect_posture(monkeypatch, tmp_path, mode=None):
    p = tmp_path / "posture.json"
    if mode is not None:
        p.write_text(json.dumps({"mode": mode, "identity_model": "test", "auto_approve": True}),
                     encoding="utf-8")
    monkeypatch.setattr(checks, "_posture_path", lambda: p)
    return p


def _redirect_receipts(monkeypatch, tmp_path, receipts=None):
    p = tmp_path / "release_receipts.json"
    if receipts is not None:
        p.write_text(json.dumps(receipts), encoding="utf-8")
    monkeypatch.setattr(checks, "_receipts_path", lambda: p)
    return p


def _redirect_drop(monkeypatch, tmp_path, houdini=None):
    p = tmp_path / "drop.json"
    if houdini is not None:
        p.write_text(json.dumps({"houdini": houdini}), encoding="utf-8")
    monkeypatch.setattr(checks, "_drop_path", lambda: p)
    return p


_ALL_PASS_RECEIPTS = {
    k: {"result": "pass", "build": "22.0.640", "date": "2026-07-15", "notes": "drill done"}
    for k in ("g1_clean_install", "g5_lifecycle", "g6_core_smoke",
              "g7_reversibility", "g8_restart", "g9_rollback")
}


# ---------------- conformance: guardrails frozen, DISPATCH rows, tasks.json ----------------

def test_guardrails_untouched_by_graft():
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    assert doc["guardrails"]["checks"] == GUARDRAILS_FROZEN


def test_all_r_checks_in_dispatch():
    for name in R_CHECKS:
        assert name in checks.DISPATCH, f"DISPATCH lacks '{name}'"


def test_r_tasks_conformance():
    import re
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    r_tasks = [t for t in doc["tasks"] if t["id"].startswith("R.")]
    if not r_tasks:
        pytest.skip("no R-tasks in tasks.json yet (graft pending)")
    vocab = set(doc.get("checks_vocabulary", []))
    ids = {t["id"] for t in r_tasks}
    assert "R.R" in ids and "R.1" in ids
    for t in r_tasks:
        assert re.match(r"^R\.(\d{1,2}|R)$", t["id"]), f"bad R id {t['id']}"
        assert t.get("blocked_on") == "release_ratified", \
            f"{t['id']}: every R task holds behind the R.0 ratification flip"
        assert t.get("phase") == "release"
        for name in t.get("verify", []):
            assert name in vocab, f"{t['id']}: verify '{name}' not in checks_vocabulary"
            assert name in checks.DISPATCH, f"{t['id']}: verify '{name}' not in DISPATCH"
    r9 = next(t for t in r_tasks if t["id"] == "R.9")
    assert "human_gate" in r9, "R.9 (security authoring) must be a human gate (S.2/S.3 precedent)"


def test_r0_cycle_queued_unratified_with_evidence():
    doc = json.loads((_REPO / "harness" / "state" / "flywheel_queue.json").read_text(encoding="utf-8"))
    r0 = next((c for c in doc["cycles"] if c.get("id") == "R.0"), None)
    assert r0 is not None, "R.0 cycle missing from flywheel_queue.json"
    assert isinstance(r0.get("ratified"), bool), "ratified must be a boolean (loud-hold contract)"
    assert r0.get("evidence"), "evidence-free cycles are invalid candidates"


# ---------------- mutation_fail_closed (R.1 / P0.2) ----------------

_FAIL_OPEN_EXECUTOR = (
    "def _dispatch(self, request, handler, command):\n"
    "            try:\n"
    "                from synapse.panel.bridge_adapter import (\n"
    "                    execute_through_bridge, is_read_only,\n"
    "                )\n"
    "                if not is_read_only(request.tool_name):\n"
    "                    response = execute_through_bridge(\n"
    "                        request.tool_name, handler, command,\n"
    "                    )\n"
    "                else:\n"
    "                    response = handler.handle(command)\n"
    "            except ImportError:\n"
    "                response = handler.handle(command)\n"
)

_FAIL_OPEN_ADAPTER = (
    "def execute_through_bridge(tool_name, handler, command):\n"
    "    bridge = get_bridge()\n"
    "    if bridge is None:\n"
    "        # Bridge unavailable -- direct dispatch\n"
    "        return handler.handle(command)\n"
)


def test_mutation_fail_closed_red_on_importerror_fallback(tmp_path):
    _plant(tmp_path, "python/synapse/panel/tool_executor.py", _FAIL_OPEN_EXECUTOR)
    res = _run("mutation_fail_closed", _ctx(tmp_path))
    assert res["ok"] is False
    assert "ImportError" in res["detail"]


def test_mutation_fail_closed_red_on_bridge_none_dispatch(tmp_path):
    _plant(tmp_path, "python/synapse/panel/bridge_adapter.py", _FAIL_OPEN_ADAPTER)
    res = _run("mutation_fail_closed", _ctx(tmp_path))
    assert res["ok"] is False
    assert "fail-open" in res["detail"] or "fail OPEN" in res["detail"]


def test_mutation_fail_closed_green_when_fallbacks_gone(tmp_path):
    _plant(tmp_path, "python/synapse/panel/tool_executor.py",
           "def _dispatch(self, request, handler, command):\n"
           "    response = execute_through_bridge(request.tool_name, handler, command)\n")
    _plant(tmp_path, "python/synapse/panel/bridge_adapter.py",
           "def execute_through_bridge(tool_name, handler, command):\n"
           "    bridge = get_bridge()\n"
           "    if bridge is None:\n"
           "        return SynapseResponse(success=False, error='Mutation blocked: bridge unavailable')\n")
    res = _run("mutation_fail_closed", _ctx(tmp_path))
    assert res["ok"] is True


def test_mutation_fail_closed_ignores_read_only_none_branch(tmp_path):
    # get_session_report's `if bridge is None: return None` must NOT trip the bounded pattern.
    _plant(tmp_path, "python/synapse/panel/bridge_adapter.py",
           "def get_session_report():\n"
           "    bridge = get_bridge()\n"
           "    if bridge is None:\n"
           "        return None\n")
    res = _run("mutation_fail_closed", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- runtime_owns_heartbeat (R.2 / P0.3) ----------------

def test_runtime_heartbeat_red_while_panel_owns_beat(tmp_path):
    _plant(tmp_path, "python/synapse/panel/synapse_panel.py",
           "        self._freeze_timer = QTimer(self)\n"
           "        self._freeze_timer.setInterval(1000)\n")
    res = _run("runtime_owns_heartbeat", _ctx(tmp_path))
    assert res["ok"] is False
    assert "panel" in res["detail"]


def test_runtime_heartbeat_red_when_deleted_without_replacement(tmp_path):
    # the two-leg case: removing the panel timer WITHOUT a process-lifetime owner is
    # deleting protection, not relocating it — must stay RED.
    _plant(tmp_path, "python/synapse/panel/synapse_panel.py", "class SynapsePanel: pass\n")
    res = _run("runtime_owns_heartbeat", _ctx(tmp_path))
    assert res["ok"] is False
    assert "removed" in res["detail"] or "owner" in res["detail"]


def test_runtime_heartbeat_green_with_runtime_owner(tmp_path):
    _plant(tmp_path, "python/synapse/panel/synapse_panel.py", "class SynapsePanel: pass\n")
    _plant(tmp_path, "python/synapse/server/freeze_chain.py",
           "# RUNTIME_BEAT_SOURCE — process-lifetime beat owner\n"
           "def ensure_beat_started():\n    pass\n")
    res = _run("runtime_owns_heartbeat", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- hot_reload_gated (R.3 / P0.4) ----------------

_PURGE_COL0 = (
    'import sys, os\n'
    'for _m in sorted(k for k in sys.modules if k.startswith("synapse.")):\n'
    '    del sys.modules[_m]\n'
    'sys.modules.pop("synapse", None)\n'
)

_PURGE_GATED = (
    'import sys, os\n'
    'if os.environ.get("SYNAPSE_DEV_HOT_RELOAD") == "1":\n'
    '    for _m in sorted(k for k in sys.modules if k.startswith("synapse.")):\n'
    '        del sys.modules[_m]\n'
    '    sys.modules.pop("synapse", None)\n'
)


def test_hot_reload_red_on_column0_purge(tmp_path):
    _plant(tmp_path, "houdini/python_panels/synapse_panel.pypanel", _PURGE_COL0)
    res = _run("hot_reload_gated", _ctx(tmp_path))
    assert res["ok"] is False
    assert "unconditional" in res["detail"]


def test_hot_reload_red_on_ungated_indented_purge(tmp_path):
    # re-nested under an always-true block with no env gate — still unconditional in effect.
    _plant(tmp_path, "houdini/python_panels/synapse_panel.pypanel",
           "if True:\n    del sys.modules['synapse.panel']\n".replace("'", '"'))
    res = _run("hot_reload_gated", _ctx(tmp_path))
    assert res["ok"] is False
    assert "SYNAPSE_DEV_HOT_RELOAD" in res["detail"]


def test_hot_reload_green_when_gated(tmp_path):
    _plant(tmp_path, "houdini/python_panels/synapse_panel.pypanel", _PURGE_GATED)
    _plant(tmp_path, "python/synapse/panel/synapse_chat.pypanel", _PURGE_GATED)
    res = _run("hot_reload_gated", _ctx(tmp_path))
    assert res["ok"] is True


def test_hot_reload_green_when_loaders_absent(tmp_path):
    res = _run("hot_reload_gated", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- deps_isolated (R.4 / P0.1) ----------------

_STRICT_GATE = (
    "if (\n"
    "    _synapse_sys.version_info[:2] == (3, 11)\n"
    '    and _synapse_sys.platform.startswith("win")\n'
    "):\n"
    "    _synapse_sys.path.insert(0, _vendor_path)\n"
)


def test_deps_isolated_red_on_strict_cp311_gate(tmp_path):
    _plant(tmp_path, "python/synapse/__init__.py", _STRICT_GATE)
    res = _run("deps_isolated", _ctx(tmp_path))
    assert res["ok"] is False
    assert "boot cliff" in res["detail"]


def test_deps_isolated_prose_sidecar_mention_does_not_green(tmp_path):
    # the daemon's RuntimeError MESSAGE says "sidecar" — a string mention must never satisfy
    # the sidecar leg (def/class lines only).
    _plant(tmp_path, "python/synapse/__init__.py", _STRICT_GATE)
    _plant(tmp_path, "python/synapse/host/daemon.py",
           'MSG = "set up an out-of-process cp311 sidecar (see docs)"\n')
    res = _run("deps_isolated", _ctx(tmp_path))
    assert res["ok"] is False


def test_deps_isolated_green_on_sidecar_implementation(tmp_path):
    _plant(tmp_path, "python/synapse/__init__.py", _STRICT_GATE)
    _plant(tmp_path, "python/synapse/host/sidecar.py",
           "def launch_sidecar(interpreter):\n    pass\n")
    res = _run("deps_isolated", _ctx(tmp_path))
    assert res["ok"] is True


def test_deps_isolated_green_when_strict_equality_replaced(tmp_path):
    _plant(tmp_path, "python/synapse/__init__.py",
           '_abi = f"cp{_synapse_sys.version_info[0]}{_synapse_sys.version_info[1]}-win_amd64"\n'
           "_root = _synapse_os.path.join(_vendor_path, _abi)\n")
    res = _run("deps_isolated", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- installer_host_targeted (R.5 / P0.5) ----------------

def test_installer_red_without_exe_and_verify(tmp_path):
    _plant(tmp_path, "scripts/install_synapse_package.py",
           'ap.add_argument("--pref-dir")\nap.add_argument("--dry-run")\n')
    res = _run("installer_host_targeted", _ctx(tmp_path))
    assert res["ok"] is False
    assert "--houdini-exe" in res["detail"]


def test_installer_green_with_exe_and_verify(tmp_path):
    _plant(tmp_path, "scripts/install_synapse_package.py",
           'ap.add_argument("--houdini-exe")\n'
           "def verify_install(pref_dir, hython):\n    pass\n")
    res = _run("installer_host_targeted", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- ci_covers_shipping_surface (R.6 / P0.6) ----------------

def test_ci_red_posix_only(tmp_path):
    _plant(tmp_path, ".github/workflows/ci.yml",
           "matrix:\n  os: [ubuntu-latest, macos-latest]\n  python-version: ['3.11', '3.14']\n")
    res = _run("ci_covers_shipping_surface", _ctx(tmp_path))
    assert res["ok"] is False
    assert "windows" in res["detail"].lower()


def test_ci_green_with_windows_and_load_probe(tmp_path):
    _plant(tmp_path, ".github/workflows/ci.yml",
           "matrix:\n  os: [ubuntu-latest, macos-latest, windows-latest]\n"
           "steps:\n  - run: python -c \"import pydantic_core\"\n    if: runner.os == 'Windows'\n")
    res = _run("ci_covers_shipping_surface", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- shelf_current (R.7 / P1-shelf) ----------------

def test_shelf_red_pyside2_only_and_stale_message(tmp_path):
    _plant(tmp_path, "houdini/scripts/python/synapse_shelf.py",
           "from PySide2 import QtWidgets\n"
           'MSG = "Run the Synapse installer to set it up:\\n  python install.py"\n')
    res = _run("shelf_current", _ctx(tmp_path))
    assert res["ok"] is False
    assert "PySide6" in res["detail"]
    assert "install" in res["detail"]


def test_shelf_green_with_pyside6_fallback_and_current_installer(tmp_path):
    # the repo-standard fix KEEPS PySide2 as fallback — the gate must green anyway.
    _plant(tmp_path, "houdini/scripts/python/synapse_shelf.py",
           "try:\n    from PySide6 import QtWidgets\n"
           "except ImportError:\n    from PySide2 import QtWidgets\n"
           'MSG = "Run: python scripts/install_synapse_package.py, then restart Houdini"\n')
    res = _run("shelf_current", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- tool_metadata_single_source (R.8 / P1-metadata) ----------------

def test_tool_metadata_red_on_set_parameter_default(tmp_path):
    _plant(tmp_path, "python/synapse/panel/bridge_adapter.py",
           'op_type = _TOOL_TO_OPERATION.get(tool_name, "set_parameter")\n')
    res = _run("tool_metadata_single_source", _ctx(tmp_path))
    assert res["ok"] is False
    assert "set_parameter" in res["detail"]


def test_tool_metadata_green_without_silent_default(tmp_path):
    _plant(tmp_path, "python/synapse/panel/bridge_adapter.py",
           "op_type = _TOOL_TO_OPERATION.get(tool_name)\n"
           "if op_type is None:\n    raise UnknownToolError(tool_name)\n")
    res = _run("tool_metadata_single_source", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- process_bridge_armed (R.9a / P1-consent) ----------------

def test_process_bridge_red_on_gate_none_and_lambda(tmp_path):
    _plant(tmp_path, "shared/bridge.py",
           "bridge = LosslessExecutionBridge(consent_callback=lambda op: True)\n"
           "bridge._gate = None\n")
    res = _run("process_bridge_armed", _ctx(tmp_path))
    assert res["ok"] is False
    assert "disarmed" in res["detail"]


def test_process_bridge_self_gate_assignment_does_not_trip(tmp_path):
    # `self._gate = None` inside the class is NOT the singleton disarm — the `bridge.` prefix
    # keeps the S.2-blind-spot gate scoped to get_process_bridge's construction site.
    _plant(tmp_path, "shared/bridge.py",
           "class LosslessExecutionBridge:\n"
           "    def __init__(self):\n        self._gate = None\n")
    res = _run("process_bridge_armed", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- auth_fail_closed (R.9b / P1-auth) ----------------

def test_auth_red_on_all_three_legs(tmp_path):
    _plant(tmp_path, "python/synapse/server/auth.py",
           "def authenticate(token, expected_key):\n"
           "    if expected_key is None:\n"
           "        return True\n"
           "def validate_origin(origin):\n"
           "    if not origin:\n"
           "        return True\n")
    _plant(tmp_path, "python/synapse/server/websocket.py",
           "auth_required = auth_key is not None or (config and config.auth_required)\n")
    res = _run("auth_fail_closed", _ctx(tmp_path))
    assert res["ok"] is False
    for leg in ("every token", "Origin", "handshake"):
        assert leg in res["detail"]


def test_auth_green_when_fail_closed(tmp_path):
    _plant(tmp_path, "python/synapse/server/auth.py",
           "def authenticate(token, expected_key):\n"
           "    if expected_key is None:\n"
           "        return False  # fail closed\n")
    _plant(tmp_path, "python/synapse/server/websocket.py", "auth_required = True\n")
    res = _run("auth_fail_closed", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- packaging_self_contained (R.10 / P1-packaging) ----------------

def test_packaging_red_on_dual_path_and_shared_import(tmp_path):
    _plant(tmp_path, "packages/synapse.json",
           '{"env": [{"var": "PYTHONPATH", "value": ["$SYNAPSE_ROOT/python", "$SYNAPSE_ROOT"]}]}\n')
    _plant(tmp_path, "python/synapse/server/integrity_envelope.py",
           "from shared.bridge import IntegrityBlock, get_process_bridge\n")
    res = _run("packaging_self_contained", _ctx(tmp_path))
    assert res["ok"] is False
    assert "repo root" in res["detail"] or "repo-root" in res["detail"]


def test_packaging_env_var_definition_does_not_trip(tmp_path):
    # the SYNAPSE_ROOT env-var DEFINITION block must not match the dual-path fingerprint.
    _plant(tmp_path, "packages/synapse.json",
           '{"env": [{"var": "SYNAPSE_ROOT", "value": "/repo"},\n'
           '         {"var": "PYTHONPATH", "value": ["$SYNAPSE_ROOT/python"]}]}\n')
    _plant(tmp_path, "python/synapse/server/integrity_envelope.py",
           "from synapse.shared.bridge import IntegrityBlock\n")
    res = _run("packaging_self_contained", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- release_readiness_review (R.R capstone) ----------------

def _stub_subchecks(monkeypatch, ok_map):
    """Stub every R sub-check to a fixed verdict. The capstone resolves sub-checks by module
    global at call time, so setattr suffices; DISPATCH rows are patched too for by-name runs."""
    for name in R_CHECKS:
        if name == "release_readiness_review":
            continue
        ok = ok_map.get(name, True)
        def stub(ctx, _ok=ok):
            return {"ok": _ok, "detail": "stub"}
        monkeypatch.setattr(checks, f"check_{name}", stub, raising=True)
        if name in checks.DISPATCH:
            monkeypatch.setitem(checks.DISPATCH, name, stub)


def _plant_symbol_table(tmp_path, major="22"):
    _plant(tmp_path, f"python/synapse/cognitive/tools/data/h{major}_symbol_table.json", "{}")


def test_capstone_stable_ready_when_everything_holds(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, {})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, _ALL_PASS_RECEIPTS)
    _redirect_drop(monkeypatch, tmp_path, houdini="22.0.640")
    _plant_symbol_table(tmp_path)
    _plant(tmp_path, "README.md", "# SYNAPSE\nH22 verified on 22.0.640.\n")
    res = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res["ok"] is True
    assert "STABLE-READY" in res["detail"]
    verdict = json.loads(
        (pathlib.Path(tmp_path) / "harness" / "state" / "release_readiness_verdict.json")
        .read_text(encoding="utf-8"))
    assert verdict["verdict"] == "STABLE-READY"
    assert verdict["blockers"] == []
    assert verdict["g_map"]["G10_documentation_truth"] is True


def test_capstone_rc_names_machine_red(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, {"mutation_fail_closed": False})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, _ALL_PASS_RECEIPTS)
    _redirect_drop(monkeypatch, tmp_path, houdini="22.0.640")
    _plant_symbol_table(tmp_path)
    res = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res["ok"] is False
    assert "mutation_fail_closed" in res["detail"]
    assert "RC" in res["detail"]


def test_capstone_rc_when_receipts_pending(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, {})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, None)  # no receipts file at all
    _redirect_drop(monkeypatch, tmp_path, houdini="22.0.640")
    _plant_symbol_table(tmp_path)
    res = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res["ok"] is False
    assert "receipt:" in res["detail"]


def test_capstone_mode_a_is_honestly_pending_drop(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, {})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, _ALL_PASS_RECEIPTS)
    _redirect_drop(monkeypatch, tmp_path)
    res = _run("release_readiness_review", _ctx(tmp_path, mode="A"))
    assert res["ok"] is False
    assert "pending-drop" in res["detail"]


def test_capstone_premature_readme_claim_is_a_blocker(tmp_path, monkeypatch):
    # G10: the label may never outrun the receipts — a claim with pending receipts blocks.
    _stub_subchecks(monkeypatch, {})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, None)
    _redirect_drop(monkeypatch, tmp_path)
    _plant(tmp_path, "README.md", "# SYNAPSE — Houdini 22 ready!\n")
    res = _run("release_readiness_review", _ctx(tmp_path, mode="A"))
    assert res["ok"] is False
    assert "g10" in res["detail"] or "G10" in res["detail"] or "claims" in res["detail"]
    verdict = json.loads(
        (pathlib.Path(tmp_path) / "harness" / "state" / "release_readiness_verdict.json")
        .read_text(encoding="utf-8"))
    assert any(b.startswith("g10") for b in verdict["blockers"])


def test_capstone_security_posture_scoping(tmp_path, monkeypatch):
    # solo → red security legs are ACCEPTED (named, non-blocking); studio → hard blockers.
    _stub_subchecks(monkeypatch, {"auth_fail_closed": False, "process_bridge_armed": False})
    _redirect_receipts(monkeypatch, tmp_path, _ALL_PASS_RECEIPTS)
    _redirect_drop(monkeypatch, tmp_path, houdini="22.0.640")
    _plant_symbol_table(tmp_path)

    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    res_solo = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res_solo["ok"] is True, "solo posture accepts (names) the security trade-offs"
    assert "auth_fail_closed" in res_solo["detail"]

    _redirect_posture(monkeypatch, tmp_path, mode="studio")
    res_studio = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res_studio["ok"] is False, "studio posture snaps security legs back to blockers"
    assert "auth_fail_closed" in res_studio["detail"]


def test_capstone_hygiene_never_blocks(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, {"packaging_self_contained": False,
                                  "tool_metadata_single_source": False})
    _redirect_posture(monkeypatch, tmp_path, mode="solo")
    _redirect_receipts(monkeypatch, tmp_path, _ALL_PASS_RECEIPTS)
    _redirect_drop(monkeypatch, tmp_path, houdini="22.0.640")
    _plant_symbol_table(tmp_path)
    res = _run("release_readiness_review", _ctx(tmp_path, mode="B"))
    assert res["ok"] is True
    assert "packaging_self_contained" in res["detail"]  # named as open hygiene, not hidden


# ---------------- live-tree honesty: the gates must read RED today ----------------

def test_live_tree_gates_read_red_now():
    """Fingerprint honesty (spec 'Ground truth'): against the REAL repo every
    UNRESOLVED P0 gate fires RED today — a gate that greens on the live defect
    is mis-located, not lenient.

    Exception (2026-07-15, H22 drop): deps_isolated (R.4 / P0.1) is now GREEN.
    The cp313 re-vendor replaced the strict ``== (3, 11)`` boot-cliff gate in
    python/synapse/__init__.py with an ABI-set membership test (_VENDOR_PYS) —
    exactly the remediation R.4 tracks. It is asserted GREEN below; the rest
    still read RED."""
    ctx = _ctx(_REPO)
    for name in ("mutation_fail_closed", "runtime_owns_heartbeat", "hot_reload_gated",
                 "installer_host_targeted", "ci_covers_shipping_surface",
                 "shelf_current", "tool_metadata_single_source", "process_bridge_armed",
                 "auth_fail_closed", "packaging_self_contained"):
        res = _run(name, ctx)
        assert res["ok"] is False, f"{name} reads GREEN on the live tree — mis-located fingerprint?"
    # deps_isolated resolved by the H22 cp313 re-vendor — the boot-cliff gate is gone.
    assert _run("deps_isolated", ctx)["ok"] is True, (
        "deps_isolated should read GREEN — the cp313 re-vendor replaced the strict "
        "cp311 equality gate (R.4/P0.1). If this reads RED the re-vendor regressed."
    )
