"""SWEEP_A source receipts and real, isolated offscreen widget probes.

No fake Qt pass: a missing binding exits 77 and is reported as NOT_RUN.
The Qt probes exercise the production constructors and repeated state changes.
"""

import ast
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "python/synapse/panel"
BASE = "ce04dcb0"
FILES = ("chat_panel.py", "face_review.py", "gate_widget.py", "context_bar.py",
         "face_work.py", "quick_actions.py")
FACTORIES = ("chat_panel.SynapseChatPanel", "face_review.FaceReview",
             "gate_widget.GateWidget", "gate_widget._ProposalCard",
             "context_bar.ContextChips", "context_bar.build_context_bar_widget",
             "face_work.FaceWork", "quick_actions.QuickActionPills")


def _base(path):
    return subprocess.check_output(
        ["git", "show", BASE + ":" + path], cwd=ROOT).decode("utf-8")


def _calls(source):
    return [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)]


def _structure(source):
    """Inventory constructors, layout membership, parenting and signal wiring."""
    result = Counter()
    for call in _calls(source):
        name = ast.unparse(call.func)
        if (name.startswith(("QtWidgets.Q", "c.")) or
                name.endswith((".addWidget", ".insertWidget", ".addLayout",
                               ".addStretch", ".addSpacing", ".setParent", ".connect"))):
            result[ast.dump(call, include_attributes=False)] += 1
    return result


@pytest.mark.parametrize("filename", FILES)
def test_no_new_structure_and_every_residual_is_reasoned(filename):
    from test_panel_rhythm_owner import _scan

    path = "python/synapse/panel/" + filename
    source = (PANEL / filename).read_text(encoding="utf-8")
    assert _structure(source) == _structure(_base(path))
    for key, line, exempt in _scan(source, path):
        assert key[1] == "spacing" and exempt, (filename, line, key)
    assert 'setProperty("rhythm_role",' in source


def _scopes(source):
    scopes = {}

    class Visitor(ast.NodeVisitor):
        path = ()

        def visit_scope(self, node):
            previous = self.path
            self.path += (node.name,)
            if isinstance(node, ast.FunctionDef):
                scopes[self.path] = node
            self.generic_visit(node)
            self.path = previous

        visit_ClassDef = visit_FunctionDef = visit_scope

    Visitor().visit(ast.parse(source))
    return scopes


@pytest.mark.parametrize("filename", FILES)
def test_every_former_widget_layout_owner_has_a_role_in_its_own_scope(filename):
    old = _scopes(_base("python/synapse/panel/" + filename))
    new = _scopes((PANEL / filename).read_text(encoding="utf-8"))
    for scope, function in old.items():
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
        changed_layouts = {ast.unparse(n.func.value) for n in calls
                           if isinstance(n.func, ast.Attribute) and n.func.attr in
                           ("setSpacing", "setContentsMargins", "setHorizontalSpacing",
                            "setVerticalSpacing")}
        for assignment in ast.walk(function):
            if not isinstance(assignment, ast.Assign):
                continue
            call = assignment.value
            if not (isinstance(call, ast.Call) and call.args and
                    ast.unparse(call.func).startswith("QtWidgets.Q") and
                    ast.unparse(call.func).endswith("Layout") and
                    ast.unparse(assignment.targets[0]) in changed_layouts):
                continue
            owner = ast.unparse(call.args[0])
            assert scope in new
            role_owners = {ast.unparse(n.func.value) for n in ast.walk(new[scope])
                           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr == "setProperty" and n.args
                           and isinstance(n.args[0], ast.Constant)
                           and n.args[0].value == "rhythm_role"}
            assert owner in role_owners, (filename, scope, owner)




def _outside_rhythm_block(text):
    """The QSS module text with the LEVER role block (_rhythm_stylesheet) blanked.

    Landing r3 (CTO 2026-09-05, RULING-4e): that one function is the upstream
    region the landing edits under a written ruling (the dead 0.72x / 0.68x
    ratios). Everything else before the first sweep marker stays byte-identical
    to ce04dcb0, which is what "append-only" protects.
    """
    tree = ast.parse(text)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_rhythm_stylesheet")
    lines = text.splitlines()
    return "\n".join(lines[:node.lineno - 1] + lines[node.end_lineno:]).rstrip()


def test_qss_is_append_only_and_every_style_key_has_rules():
    from synapse.panel.designsystem import qss

    source = (PANEL / "designsystem/qss.py").read_text(encoding="utf-8")
    original = _base("python/synapse/panel/designsystem/qss.py")
    marker = "# --- SWEEP_A (chat_panel.py)"
    prefix, added = source[:source.index(marker)], source[source.index(marker):]
    assert _outside_rhythm_block(prefix) == _outside_rhythm_block(original)
    # Landing r3 (CTO 2026-09-05, R2-03): SWEEP_A owns exactly its own marked
    # block; later sweeps append their own blocks after it, so the pin is
    # fence-scoped to SWEEP_A's block instead of the whole tail.
    assert added.strip().startswith("# --- SWEEP_A (chat_panel.py)")
    end = "# --- END SWEEP_A"
    assert end in added
    block_a = added[:added.index(end) + len(end)]
    assert not re.search(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z_])", block_a)
    # F-C1: families travel by QFont (fontload / rhythm), never by QSS.
    assert "font-family:" not in block_a
    sheet = qss.stylesheet()
    for filename in FILES:
        for call in _calls((PANEL / filename).read_text(encoding="utf-8")):
            if ast.unparse(call.func) == "qss.sweep_a_style":
                key = ast.literal_eval(call.args[1])
                assert '[sweep_a_style="%s"]' % key in sheet, key
    # A sweep must never mutate upstream QSS text or require its own caller.
    assert sheet.startswith(qss._sweep_a_base_stylesheet())


def test_scoped_rules_keep_pseudo_states_on_the_target():
    from synapse.panel.designsystem import qss

    sheet = qss._sweep_a_rule(
        "probe", "QPushButton:hover {padding: 4px;} QMenu::item:selected {margin: 0;}")
    assert 'QPushButton[sweep_a_style="probe"]:hover' in sheet
    assert 'QMenu[sweep_a_style="probe"]::item:selected' in sheet
    assert 'QPushButton:hover[sweep_a_style=' not in sheet
    assert 'QPushButton:hover {' not in sheet


@pytest.mark.parametrize("suffix", ("20", "30", "CC"))
def test_legacy_argb_conversion_preserves_all_four_channels(suffix):
    from synapse.panel.designsystem import qss, tokens

    for color in (tokens.SIGNAL, tokens.GROW, tokens.ERROR):
        # Independent packed-word oracle: Qt's eight-digit order is ARGB.
        packed = int(color.lstrip("#") + suffix, 16)
        expected = ((packed >> 16) & 255, (packed >> 8) & 255,
                    packed & 255, (packed >> 24) & 255)
        output = qss._sweep_a_legacy_argb(color, suffix)
        channels = tuple(map(int, re.fullmatch(
            r"rgba\((\d+), (\d+), (\d+), (\d+)\)", output).groups()))
        assert channels == expected


def _run(factory, density, case="rhythm"):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SYNAPSE_REDUCED_MOTION="1",
               PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), factory, density, case],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stdout + result.stderr
    payloads = [line[8:] for line in result.stdout.splitlines() if line.startswith("SWEEP_A=")]
    assert len(payloads) == 1, result.stdout + result.stderr
    return json.loads(payloads[0])


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
@pytest.mark.parametrize("factory", FACTORIES)
def test_production_layout_roles_density_sequence_and_removal(factory, density):
    result = _run(factory, density)
    assert result["layouts"] > 0
    assert result["role_removed_unchanged"] and result["sequence_restored"]


@pytest.mark.parametrize("factory", ("gate_widget.GateWidget", "gate_widget._ProposalCard",
                                     "context_bar.ContextChips", "face_work.FaceWork",
                                     "chat_panel.SynapseChatPanel", "quick_actions.QuickActionPills"))
def test_dynamic_states_still_select_paint_and_keep_controls(factory):
    assert _run(factory, "airy", "states")["states_verified"]


def _qt():
    for binding in ("PySide6", "PySide2"):
        try:
            widgets = importlib.import_module(binding + ".QtWidgets")
        except ImportError:
            continue
        assert "PySide" in widgets.QApplication.__module__, "Qt stub cannot certify layout"
        return widgets
    print("NOT_RUN: PySide6/PySide2 absent from bound Python; Qt measurement unavailable")
    raise SystemExit(77)


def _construct(widgets, factory, density):
    from synapse.panel.designsystem import qss

    module, name = factory.split(".")
    source = importlib.import_module("synapse.panel." + module)
    constructor = getattr(source, name)
    controller = None
    host = widgets.QWidget()
    host.setObjectName("DsRoot")
    host.setProperty("density", density)
    host.setStyleSheet(qss.stylesheet())
    box = widgets.QVBoxLayout(host)
    if name == "SynapseChatPanel":
        controller = constructor()
        child = controller.createInterface()  # never activate its bridge/timers
    elif name == "build_context_bar_widget":
        child = constructor(source.ContextBarState())
    elif name == "_ProposalCard":
        child = constructor({"proposal_id": "sweep-probe", "level": "approve",
                             "operation": "probe", "agent_id": "probe-agent",
                             "description": "A local display fixture"})
    else:
        child = constructor()
    box.addWidget(child)
    return host, child, controller


def _layout_sequence(widgets, host, child, density):
    from synapse.panel.designsystem import rhythm, tokens
    from synapse.panel import compositor

    compositor._repolish_tree(host)
    owners = [w for w in [child] + child.findChildren(widgets.QWidget)
              if w.property("rhythm_role") and w.layout() is not None]
    assert owners
    roles = [w.property("rhythm_role") for w in owners]
    # Independently chosen component bases, not copied from ROLE_GAPS.
    bases = {"group": 16, "parm_row": 4, "card": 16, "stack": 4}
    identities = [id(w) for w in owners]
    for level in (density, "tight", "airy", "standard", density):
        rhythm.apply(child, level)
        for w, role in zip(owners, roles):
            assert w.layout().spacing() == tokens.gap(bases[role], level)
            m = w.layout().contentsMargins()
            assert (m.left(), m.top(), m.right(), m.bottom()) == (0, 0, 0, 0)
    assert identities == [id(w) for w in owners]
    before = [w.layout().spacing() for w in owners]
    for w in owners:
        w.setProperty("rhythm_role", None)
    rhythm.apply(child, "tight" if density != "tight" else "airy")
    assert before == [w.layout().spacing() for w in owners]
    for w, role in zip(owners, roles):
        w.setProperty("rhythm_role", role)
    return {"layouts": len(owners), "role_removed_unchanged": True,
            "sequence_restored": True}


def _states(widgets, host, child, controller, factory):
    from synapse.panel.designsystem import tokens, qss, rhythm
    from synapse.panel import compositor

    compositor._repolish_tree(host)
    rhythm.apply(host, "airy")

    def painted(widget, expected):
        widget.ensurePolished()
        assert widget.palette().color(widget.foregroundRole()).name().lower() == expected.lower()

    if factory == "gate_widget.GateWidget":
        for value, expected in ((None, tokens.SLATE), (1.0, tokens.GROW),
                                (0.1, tokens.ERROR), (None, tokens.SLATE)):
            child._render_fidelity(value)
            painted(child._fidelity_dot, expected)
        child.handle_ws_proposal({"proposal_id": "late", "level": "review"})
        card = child._cards["late"]
        assert card.layout().spacing() == tokens.gap(4, "airy")
        child.update_integrity({"operations_total": 1, "anchor_violations": 1})
        painted(child._violations_label, tokens.ERROR)
        child.update_integrity({"operations_total": 1, "anchor_violations": 0})
        painted(child._violations_label, tokens.SLATE)
    elif factory == "gate_widget._ProposalCard":
        buttons = child._approve_btn, child._reject_btn
        child.mark_gate_unreachable()
        assert child.isEnabled() and all(not b.isHidden() for b in buttons)
        assert "NOT RECORDED" in child._countdown_label.text()
        child.mark_decided("approved")
        assert child._countdown_label.text() == "APPROVED"
        painted(child._countdown_label, tokens.GROW)
        child._end_flash()
        assert not child.isEnabled()
        assert child.property("sweep_a_style") == "gate_card"
    elif factory == "context_bar.ContextChips":
        from synapse.panel.context_bar import ContextBarState, update_context_bar_widget

        for stage, expected in (("structured", tokens.SIGNAL), ("composed", tokens.GROW),
                                ("flat", tokens.TEXT_SECONDARY)):
            update_context_bar_widget(child._inner, ContextBarState(memory_stage=stage))
            painted(child._inner.findChild(widgets.QLabel, "ctx_memory"), expected)
    elif factory == "face_work.FaceWork":
        for phase, expected in (("running", tokens.SIGNAL), ("done", tokens.GROW),
                                ("error", tokens.ERROR)):
            child.set_tool_status("probe", phase)
            assert child._plan_box.count() == 1
            painted(child._plan_box.itemAt(0).widget(), expected)
        child.reset()
        painted(child._plan_box.itemAt(0).widget(), tokens.TEXT_TERTIARY)
    elif factory == "chat_panel.SynapseChatPanel":
        for connected, expected in ((True, tokens.GROW), (False, tokens.ERROR), (True, tokens.GROW)):
            controller._on_status_changed(connected)
            painted(controller._conn_dot, expected)
            painted(controller._conn_label, expected)
        for mode in ("hda", "chat", "hda", "chat"):
            controller._set_mode(mode)
            assert controller._mode_stack.currentIndex() == (mode == "hda")
    else:
        original = list(child._pills)
        for expanded in (False, True, False, True):
            child.set_expanded(expanded)
            assert child._pills_container.isHidden() != expanded
            assert original == child._pills
    return {"states_verified": True}


if __name__ == "__main__":
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert os.environ["SYNAPSE_REDUCED_MOTION"] == "1"
    sys.path.insert(0, str(ROOT / "python"))
    qt = _qt()
    app = qt.QApplication.instance() or qt.QApplication([])
    factory, density, case = sys.argv[1:]
    host, child, controller = _construct(qt, factory, density)
    try:
        result = (_layout_sequence(qt, host, child, density) if case == "rhythm"
                  else _states(qt, host, child, controller, factory))
        print("SWEEP_A=" + json.dumps(result, sort_keys=True))
    finally:
        if controller is not None:
            controller.onDestroyInterface()
        host.close()
