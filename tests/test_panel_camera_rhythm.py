"""CAMERA display contracts and protected-source controls; no host required."""

import ast
from contextlib import nullcontext
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from synapse.panel.recall_card import latest_recall_result, recall_view


ROOT = Path(__file__).resolve().parents[1]
BASE = "ce04dcb0"
# Landing r3 (CTO 2026-09-05, R2-03 / F-A3): synapse_panel.py's protected
# lifecycle methods are compared against the master merge-base of the landing,
# because master's B4 (composer cap) edited showEvent / _GrowingInput.__init__
# after ce04dcb0 and the merge inherits those bytes. Every other CAMERA-frozen
# file stays pinned to ce04dcb0 except the explicit supersessions below.
#
# A LITERAL, like BASE above - never `git merge-base master HEAD` (CRUX round 3):
# the day this lands, merge-base(master, HEAD) == HEAD and the thirteen
# lifecycle pins plus the constructor pin would compare the tree to itself,
# green regardless of edits to _on_done (the isolated-green class R2-03 named);
# a checkout without a local `master` ref would error instead of measuring.
# Re-anchored 2026-09-05 at the bc-wave landing (CTO, RULING_DIRECTION_BC.md
# Addendum 3): _on_done / _start_worker / _on_stop / _set_busy and the composer
# constructor changed under written rulings (busy guard, state sentence, one
# '/' telling). The pin keeps its job for the NEXT wave: lifecycle methods are
# byte-identical to this landing unless a ruling says otherwise.
_PANEL_BASE = "47ffea0e"


def _panel_base():
    return _PANEL_BASE
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


def _assert_lifecycle_method(current, original, name):
    if name == "_on_stop":
        # M4 revokes permission before cooperative worker cancellation. Freeze
        # every other byte and require the exact additive call, once.
        addition = '        _revoke_model_connections(getattr(self, "_permission_connections", ()))\n'
        assert current.count(addition) == 1
        current = current.replace(addition, "", 1)
    elif name == "_set_busy":
        # Artist-approved Connect / Doctor placement keeps Connect visible and
        # disables it while busy. Only these two statements supersede the pin;
        # the state transitions and every other lifecycle byte stay frozen.
        approved = ('        self._connect_btn.setVisible(True)\n'
                    '        self._connect_btn.setEnabled(not busy)\n')
        previous = '        self._connect_btn.setVisible(not busy)   # Connect | Stop share one slot\n'
        assert current.count(approved) == 1, "Connect stays visible and is disabled while busy"
        current = current.replace(approved, previous, 1)
    assert current == original


# Joe's approved first-session roadmap (2026-09-06) changes connection/start,
# completion attribution, and close/key lifetime. Those paths now have behavior
# controls in test_first_session_panel and check_first_session_qt, including
# decline preservation, actual task identity, and QObject destruction. Keep the
# old CAMERA freeze on the unrelated measurement and lifecycle methods.
@pytest.mark.parametrize("name", ["_refresh_token_surfaces", "_show_token_face",
                                  "_build_token_face", "_on_token",
                                  "_on_stop", "_set_busy",
                                  "showEvent", "_update_context", "_update_health"])
def test_lifecycle_and_token_completion_methods_byte_identical(name):
    _assert_lifecycle_method(_method(_source("synapse_panel.py"), name),
                             _method(_source("synapse_panel.py", _panel_base()), name), name)


@pytest.mark.parametrize("name", ["_set_busy", "_on_token", "_update_context"])
def test_lifecycle_pin_rejects_unrelated_work_even_in_an_amended_method(name):
    current = _method(_source("synapse_panel.py"), name)
    original = _method(_source("synapse_panel.py", _panel_base()), name)
    with pytest.raises(AssertionError):
        _assert_lifecycle_method(current + "\n        self._worker = None", original, name)


def test_connect_stays_visible_and_busy_transitions_keep_their_lifecycle():
    source = ast.parse(_source("synapse_panel.py"))
    method = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef)
                  and node.name == "_set_busy")
    namespace = {"_timed_phase": lambda name: nullcontext()}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "panel-busy", "exec"), namespace)
    panel = SimpleNamespace(
        _send_btn=Mock(), _stop_btn=Mock(), _connect_btn=Mock(), _was_busy=False,
        _stopping=False, _set_work_substate=Mock(), _populate_review=Mock(), _render_state=Mock())
    sequence = (False, True, True, False, False, True, False)
    for busy, expected in zip(sequence, ("idle", "working", "working", "done", "idle", "working", "done")):
        namespace["_set_busy"](panel, busy)
        assert panel._was_busy is busy and panel._turn_state == expected
    assert panel._connect_btn.setVisible.call_args_list == [call(True)] * len(sequence)
    assert panel._connect_btn.setEnabled.call_args_list == [call(not busy) for busy in sequence]
    assert panel._send_btn.setEnabled.call_args_list == [call(not busy) for busy in sequence]
    assert panel._stop_btn.setVisible.call_args_list == [call(busy) for busy in sequence]
    assert panel._stop_btn.setEnabled.call_args_list == [call(busy) for busy in sequence]
    assert panel._set_work_substate.call_args_list == [call("cook"), call("done")] * 2
    assert panel._populate_review.call_count == 2
    assert panel._render_state.call_count == len(sequence)


def test_stop_revokes_connections_before_worker_abort():
    tree = ast.parse(_source("synapse_panel.py"))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_revoke_model_connections")
    stop = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                and node.name == "_on_stop")
    namespace = {"_STOPPING_PHRASE": "Stopping"}
    exec(compile(ast.Module(body=[helper, stop], type_ignores=[]), "panel-stop", "exec"), namespace)
    events = []
    panel = SimpleNamespace(
        _permission_connections=[SimpleNamespace(revoke=lambda: events.append("revoke"))],
        _worker=SimpleNamespace(abort=lambda: events.append("abort")),
        _stop_btn=Mock(), _header_status=Mock(), _last_tool="synthetic tool", _set_header=Mock())
    namespace["_on_stop"](panel)
    assert events == ["revoke", "abort"]
    assert panel._stopping is True
    panel._stop_btn.setEnabled.assert_called_once_with(False)
    panel._set_header.assert_called_once_with("working", "Stopping")


def _assert_panel_constructors(current_source, original_source):
    # Compare class identities: the approved shortcut layout precedes the
    # protected _GrowingInput constructor but cannot displace its source pin.
    def constructors(source):
        result = {}
        for cls in ast.parse(source).body:
            if not isinstance(cls, ast.ClassDef) or cls.name == "SynapsePanel":
                continue
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                    assert cls.name not in result, "duplicate constructor"
                    result[cls.name] = ast.get_source_segment(source, node)
        return result
    current = constructors(current_source)
    original = constructors(original_source)
    assert set(current) == set(original) | {"_ShortcutLayout"}
    # The annotation is allowed on BOTH sides (the base now carries it too).
    strip = lambda src: re.sub(r"  # rhythm-exempt:[^\n]*", "", src)
    assert {name: strip(current[name]) for name in original} == {
        name: strip(source) for name, source in original.items()}
    # The new layout stores caller-owned gaps and gets its zero margins from
    # the shared band role. No constructor/lifecycle carve-out for other code.
    shortcut = '''def __init__(self, horizontal_gap, vertical_gap):
        super().__init__()
        self._items = []
        self._horizontal_gap = horizontal_gap
        self._vertical_gap = vertical_gap
        rhythm.apply_layout_margins(self, "band")'''
    assert ast.dump(ast.parse(current["_ShortcutLayout"])) == ast.dump(ast.parse(shortcut))


def test_constructor_lifecycle_is_unchanged_except_root_sheet_annotation():
    _assert_panel_constructors(_source("synapse_panel.py"),
                               _source("synapse_panel.py", _panel_base()))


@pytest.mark.parametrize("before,after", [
    ("self.setAcceptRichText(False)", "self.setAcceptRichText(True)"),
    ('rhythm.apply_layout_margins(self, "band")', 'rhythm.apply_layout_margins(self, "row")'),
    ("class _GrowingInput", "class ExtraOwner:\n    def __init__(self):\n        pass\n\nclass _GrowingInput"),
])
def test_constructor_pin_rejects_changed_input_new_owners_and_shortcut_drift(before, after):
    current = _source("synapse_panel.py")
    assert current.count(before) == 1
    with pytest.raises(AssertionError):
        _assert_panel_constructors(current.replace(before, after, 1),
                                   _source("synapse_panel.py", _panel_base()))


# J2 (RULING_JOE_FIVE.md, 2026-09-05): "the whole point of TOKEN is it supposed
# to count token use" - _refresh_usage is the one pinned method J2 edits (it now
# feeds the SPEND / SESSION blocks through _refresh_spend), so it re-anchors to
# the J2 landing commit; refresh_from_probe and measure_static stay at ce04dcb0
# and must be byte-identical. A LITERAL, like BASE: the integrator MERGES J2,
# never squashes or rebases it, or the SHA stops resolving and this pin errors
# instead of measuring.
_J2_BASE = "c28ac3dc"


# First-session location evidence replaces probe-all/first-result selection.
# Actual count composition and pricing surfaces retain their original controls.
@pytest.mark.parametrize("name,base", [("measure_static", BASE),
                                       ("_refresh_spend", _J2_BASE)])
def test_token_measurement_paths_are_unchanged(name, base):
    current = _method(_source("face_token.py"), name)
    if name == "_refresh_spend":
        # M4 adds requested-versus-reported identity to the note; measured
        # counts, context arithmetic and pricing keep the J2 byte pin.
        addition = ('        reported = snap.get("reported_models") or []\n'
                    '        notes.append("Requested: %s. API reported: %s" % (\n'
                    '            snap.get("model") or "unknown", ", ".join(reported) if reported else "unknown"))\n')
        assert current.count(addition) == 1
        current = current.replace(addition, "", 1)
    assert current == _method(_source("face_token.py", base), name)


@pytest.mark.parametrize("reported,expected", [([], "unknown"), (["api-alias"], "api-alias")])
def test_spend_note_distinguishes_requested_and_reported_models(reported, expected):
    source = ast.parse(_source("face_token.py"))
    method = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef)
                  and node.name == "_refresh_spend")
    namespace = {"UNKNOWN": "UNKNOWN"}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "token-spend", "exec"), namespace)
    face = SimpleNamespace(set_row=Mock(), _set_note=Mock(), _spend_note="spend", _session_note="session")
    snap = {"provider": "custom", "model": "requested-model", "reported_models": reported,
            "input_tokens": 11, "output_tokens": 4,
            "session": {"input_tokens": 11, "output_tokens": 4, "tasks": 1}}
    namespace["_refresh_spend"](face, snap)
    note = next(call.args[1] for call in face._set_note.call_args_list if call.args[0] == "spend")
    assert "Requested: requested-model. API reported: " + expected in note
    face.set_row.assert_any_call("prompt", 11)
    face.set_row.assert_any_call("completion", 4)
    face.set_row.assert_any_call("total", 15)
    face.set_row.assert_any_call("session total", 15)


def test_token_readout_worker_fontload_and_shelf_unchanged():
    # J2 (RULING_JOE_FIVE.md, 2026-09-05): token_readout.py gained the context /
    # session / usd display rules and claude_worker.py the provider id + context
    # window hand-off to the sink, under the written ruling - both re-anchor to
    # the J2 landing commit (_J2_BASE); the pill / meter rules and the worker's
    # hou-free invariant are unchanged (tests/test_bp2_paneltruth_token_refresh.py).
    # fontload.py stays pinned at ce04dcb0.
    # Worker activity and cancellation pairing are covered behaviorally by
    # test_first_session_panel; the untouched token display rule remains pinned.
    j2_paths = ["python/synapse/panel/token_readout.py"]
    assert subprocess.check_output(["git", "diff", _J2_BASE, "--", *j2_paths], cwd=ROOT) == b""
    # tokens.py left this list 2026-09-05: W7 (Joe's wordmark
    # addendum) adds a token under a written ruling.
    paths = ["python/synapse/panel/designsystem/fontload.py"]
    assert subprocess.check_output(["git", "diff", BASE, "--", *paths], cwd=ROOT) == b""
    # M6's approved shelf-width fix selects the interface at native creation,
    # before QuickStart can retain its minimum width. Supersede only the shelf
    # pin with the reviewed source digest (universal newlines, UTF-8), never HEAD.
    # test_panel_shelf_open and test_bp2_paneltruth_float_fix prove the behavior.
    shelf = (ROOT / "houdini/scripts/python/synapse_shelf.py").read_text(encoding="utf-8")
    assert hashlib.sha256(shelf.encode("utf-8")).hexdigest() == (
        "b46788aafd73f792b0dafa4474c97437d91d03766ad4a6752272888741be34a2"
    ), "Shelf differs from the reviewed M6 interface-at-creation source"


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
        # bc-wave (2026-09-05): recall_card's two tagged spacing sites went
        # with the rail; the ceiling follows the census down, never up.
        expected = {"synapse_panel.py": (0, 1), "recall_card.py": (0, 0)}.get(
            Path(file["path"]).name, (0, 0))
        assert (len(file["spacing"]), len(file["inline_styles"])) == expected
        for site in file["spacing"] + file["inline_styles"]:
            assert "rhythm-exempt:" in (ROOT / file["path"]).read_text(encoding="utf-8").splitlines()[site["line"] - 1]


def test_no_widget_takes_both_label_type_appliers():
    """RULING-4d doctrine: rhythm_role="label" is the section eyebrow (mono,
    upper, tracked); TYPE_ROLES['label'] via c.label(role="label") is UI label
    text (sans, BP4). Different things - never both on one widget."""
    offenders = []
    for path in sorted((ROOT / "python/synapse/panel").glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            applier = '.setProperty("rhythm_role", "label")'
            if applier not in line:
                continue
            target = line.split(applier)[0].strip()
            window = [near.split("  #")[0] for near in lines[max(0, index - 3):index + 4]]
            if any(target + " = c.label(" in near and 'role="label"' in near for near in window):
                offenders.append((path.name, index + 1))
    assert not offenders, offenders


def test_shell_role_consumes_the_gutter_token_and_ratios_are_gone():
    """RULING-3: the 30px gutter is a role margin, so tokens.GUTTER has a
    consumer and the four edge containers carry it. RULING-4e: no ratio."""
    from synapse.panel.designsystem import rhythm, tokens as t

    assert rhythm._MARGINS["shell"] == (t.GUTTER, t.SPACE_SM, t.GUTTER, t.SPACE_SM)
    assert rhythm.ROLE_GAPS["band"] == 0 and rhythm.ROLE_GAPS["stack"] == t.SPACE_GRID[0]
    panel_source = _source("synapse_panel.py")
    # bc-wave BC-1 (2026-09-05): the verb rail's edge container retired with
    # the rail, so three edge containers carry the gutter (rail, ribbon,
    # direct face); the tab row folded into the overflow in BC-5.
    assert panel_source.count('setProperty("rhythm_role", "shell")') == 3
    assert 'setProperty("rhythm_role", "band")' in panel_source
    qss_source = (ROOT / "python/synapse/panel/designsystem/qss.py").read_text(encoding="utf-8")
    assert "role_size" not in qss_source
    for name in ("chat_panel.py", "gate_widget.py", "context_bar.py", "face_review.py",
                 "hda_views.py", "quick_actions.py", "tool_palette.py",
                 "working_indicator.py", "command_palette.py", "recall_card.py"):
        assert '"rhythm_role", "parm_row"' not in _source(name), name


def test_new_card_has_no_capability_or_background_work():
    source = _source("recall_card.py")
    tree = ast.parse(source)
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(any(word in name for word in ("server", "memory", "transport", "hou")) for name in imports)
    assert not any(isinstance(n, ast.Attribute) and n.attr in ("QTimer", "QThread", "start")
                   for n in ast.walk(tree))
