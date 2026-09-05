"""CAMERA display contracts and protected-source controls; no host required."""

import ast
import importlib.util
from pathlib import Path
import re
import subprocess

import pytest

from synapse.panel.recall_card import latest_recall_result, recall_view


ROOT = Path(__file__).resolve().parents[1]
BASE = "ce04dcb0"
CAMERA = ("synapse_panel.py", "face_token.py", "token_readout.py",
          "chat_display.py", "recall_card.py")


@pytest.mark.parametrize("status,hit,expected", [
    ("SUCCESS", True, "HIT"), ("SUCCESS", False, "NO HIT"),
    ("SUCCESS", None, "UNKNOWN"), ("SUCCESS", "false", "UNKNOWN"),
    ("SUCCESS", 0, "UNKNOWN"), ("SUCCESS", 1, "UNKNOWN"),
    ("UNAVAILABLE", True, "UNAVAILABLE"), ("BLOCKED", True, "BLOCKED"),
    ("created", True, "UNKNOWN"), (None, True, "UNKNOWN"),
])
def test_recall_status_requires_measured_boolean(status, hit, expected):
    result = {"STATUS": status, "payload": {"hit": hit, "deposit": "a deposit"}}
    assert recall_view(result)["status"] == expected


def test_recall_preserves_deposit_and_failure_reason_without_rendering_html():
    deposit = '<script>not markup</script>\nSecond line.'
    assert recall_view({"STATUS": "SUCCESS", "payload": {"hit": True, "deposit": deposit}}) == {
        "status": "HIT", "deposit": deposit}
    assert recall_view({"STATUS": "BLOCKED", "reason": "gate offline",
                        "payload": {"hit": True, "deposit": deposit}}) == {
        "status": "BLOCKED", "deposit": "gate offline"}
    assert recall_view({"found": False, "error": "Memory not available"}) == {
        "status": "UNAVAILABLE", "deposit": "Memory not available"}


@pytest.mark.parametrize("value", [None, [], "success", 0, {"payload": None},
                                  {"found": "yes"}, {"found": 0}])
def test_malformed_recall_stays_unknown(value):
    assert recall_view(value) == {"status": "UNKNOWN", "deposit": "UNKNOWN"}


def test_legacy_tracker_matches_preserve_prose_and_do_not_invent_missing_body():
    result = {"found": True, "matches": [{"content": "First"}, {"content": "Second"}]}
    assert recall_view(result) == {"status": "HIT", "deposit": "First\n\nSecond"}
    assert recall_view({"found": True, "matches": []}) == {
        "status": "HIT", "deposit": "UNKNOWN"}
    assert recall_view({"found": False, "matches": []})["status"] == "NO HIT"


def test_correlate_result_ids_and_never_use_request_status_as_recall():
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "synapse_recall", "id": "recall"},
            {"type": "tool_use", "name": "synapse_search", "id": "search"}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "recall",
             "content": '{"found": true, "matches": [{"content": "stored"}]}'},
            {"type": "tool_result", "tool_use_id": "search", "content": '{"found": false}'}]},
    ]
    assert recall_view(latest_recall_result(messages))["deposit"] == "stored"
    messages.append({"content": [{"type": "tool_result", "tool_use_id": "recall",
                                  "content": "truncated json"}]})
    assert recall_view(latest_recall_result(messages))["status"] == "UNKNOWN"
    messages[-1]["content"][0]["is_error"] = True
    assert recall_view(latest_recall_result(messages))["status"] == "UNAVAILABLE"
    assert latest_recall_result([{"name": "synapse_recall", "phase": "done"}]) is None


def test_recall_malformed_ids_and_text_cannot_make_a_hit_or_raise():
    uncorrelated = [{"content": [{"type": "tool_use", "name": "synapse_recall"},
                                 {"type": "tool_result", "content": '{"found":true}'}]}]
    assert latest_recall_result(uncorrelated) is None
    messages = [{"content": [{"type": "tool_use", "name": "synapse_recall", "id": "r"},
                              {"type": "tool_result", "tool_use_id": "r",
                               "content": [{"type": "text", "text": None}]}]}]
    assert recall_view(latest_recall_result(messages))["status"] == "UNKNOWN"
    messages[0]["content"][1].update(content="Memory backend offline", is_error=True)
    assert recall_view(latest_recall_result(messages)) == {
        "status": "UNAVAILABLE", "deposit": "Memory backend offline"}


def _source(name, revision=None):
    path = "python/synapse/panel/" + name
    if revision:
        return subprocess.check_output(["git", "show", revision + ":" + path],
                                       cwd=ROOT).decode("utf-8")
    return (ROOT / path).read_text(encoding="utf-8")


def _method(source, name):
    node = next(n for n in ast.walk(ast.parse(source))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return "\n".join(source.splitlines()[node.lineno - 1:node.end_lineno])


@pytest.mark.parametrize("name", ["_on_done", "_refresh_token_surfaces", "_show_token_face",
                                  "_build_token_face", "_start_worker", "_on_token",
                                  "_on_error", "_on_stop", "_set_busy", "closeEvent",
                                  "showEvent", "_update_context", "_update_health"])
def test_lifecycle_and_token_completion_methods_byte_identical(name):
    assert _method(_source("synapse_panel.py"), name) == _method(_source("synapse_panel.py", BASE), name)


def test_constructor_lifecycle_is_unchanged_except_root_sheet_annotation():
    current = _method(_source("synapse_panel.py"), "__init__")
    # The first __init__ is _GrowingInput, also protected; compare all init nodes.
    def constructors(source):
        return [ast.get_source_segment(source, n) for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"]
    current = constructors(_source("synapse_panel.py"))
    original = constructors(_source("synapse_panel.py", BASE))
    assert [re.sub(r"  # rhythm-exempt:[^\n]*", "", s) for s in current] == original


@pytest.mark.parametrize("name", ["refresh_from_probe", "_refresh_usage", "measure_static"])
def test_token_measurement_paths_are_unchanged(name):
    assert _method(_source("face_token.py"), name) == _method(_source("face_token.py", BASE), name)


def test_token_readout_worker_fontload_and_shelf_unchanged():
    paths = ["python/synapse/panel/token_readout.py", "python/synapse/panel/claude_worker.py",
             "python/synapse/panel/designsystem/fontload.py",
             "python/synapse/panel/designsystem/tokens.py",
             "houdini/scripts/python/synapse_shelf.py"]
    assert subprocess.check_output(["git", "diff", BASE, "--", *paths], cwd=ROOT) == b""


def camera_census():
    spec = importlib.util.spec_from_file_location("camera_census", ROOT / "harness/notes/panel_rhythm_census.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.census(ROOT / "python/synapse/panel")
    assert result["measurement_complete"] and not result["errors"]
    return [f for f in result["files"] if Path(f["path"]).name in CAMERA]


def test_camera_residual_cannot_regrow():
    # Strict ownership prevents editing the shared residual file. This local
    # ceiling protects the reduction independently; it doesn't waive raw zero.
    files = camera_census()
    assert len(files) == len(CAMERA)
    for file in files:
        assert not file["hex_sites"]
        assert not file["grid_spacing"]
        expected = {"synapse_panel.py": (0, 1), "recall_card.py": (2, 0)}.get(
            Path(file["path"]).name, (0, 0))
        assert (len(file["spacing"]), len(file["inline_styles"])) == expected
        for site in file["spacing"] + file["inline_styles"]:
            assert "rhythm-exempt:" in (ROOT / file["path"]).read_text(encoding="utf-8").splitlines()[site["line"] - 1]


def test_new_card_has_no_capability_or_background_work():
    source = _source("recall_card.py")
    tree = ast.parse(source)
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(any(word in name for word in ("server", "memory", "transport", "hou")) for name in imports)
    assert not any(isinstance(n, ast.Attribute) and n.attr in ("QTimer", "QThread", "start")
                   for n in ast.walk(tree))
