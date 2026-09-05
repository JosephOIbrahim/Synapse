"""SWEEP_B source guards and isolated real-Qt sequence probes.

Real geometry is never inferred from a stub. The subprocess exits 77 when
neither PySide binding is installed; the orchestrator runs that tier in hython.
"""

import ast
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
MODULES = ("hda_views", "tool_palette", "command_palette", "working_indicator")
REGIONS = (
    "hda_views.DescribeView", "hda_views.BuildingView", "hda_views.ResultView",
    "tool_palette.ToolPalette", "command_palette.CommandPaletteWidget",
    "working_indicator.WorkingIndicator",
)
OWNER_ROLES = dict(zip(REGIONS, ("parm_row", "group", "parm_row", "parm_row", "group", "parm_row")))


def _base(path):
    return subprocess.check_output(
        ["git", "show", "ce04dcb0:" + path], cwd=ROOT, text=True, encoding="utf-8")


@pytest.mark.parametrize("name", MODULES)
def test_migrated_widget_has_zero_imperative_rhythm_owners(name):
    source = (PANEL / (name + ".py")).read_text(encoding="utf-8")
    forbidden = {"setStyleSheet", "setSpacing", "setContentsMargins",
                 "setHorizontalSpacing", "setVerticalSpacing"}
    assert not [node.lineno for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden]


@pytest.mark.parametrize("region,role", OWNER_ROLES.items())
def test_each_real_constructor_declares_its_layout_role(region, role):
    module, name = region.split(".")
    tree = ast.parse((PANEL / (module + ".py")).read_text(encoding="utf-8"))
    constructors = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                    and node.name == name and node.bases]
    # CommandPalette's unavailable fallback has no QWidget base and is excluded.
    assert len(constructors) == 1
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and ast.unparse(node.func) == "self.setProperty"
               and [ast.literal_eval(arg) for arg in node.args] == ["rhythm_role", role]
               for node in ast.walk(constructors[0])
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and ast.unparse(node.func) == "self.setProperty"
               and all(isinstance(arg, ast.Constant) for arg in node.args))


def test_qss_preserves_inherited_bytes_and_uses_only_existing_tokens():
    from synapse.panel.designsystem import qss, tokens
    path = "python/synapse/panel/designsystem/qss.py"
    source = (ROOT / path).read_text(encoding="utf-8")
    assert source.startswith(_base(path)), "QSS edit outside append-only block"
    tail = source[len(_base(path)):]
    # Landing r3 (CTO 2026-09-05, R2-03): the tail carries SWEEP_A's block
    # first; SWEEP_B's guarantees are fence-scoped to its own marked block.
    start, end = "# --- SWEEP_B (", "# --- END SWEEP_B"
    assert start in tail and end in tail
    assert tail.rstrip().endswith(end)
    block_b = tail[tail.index(start):tail.index(end) + len(end)]
    assert not re.search(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z_])", block_b)
    assert "font-family:" not in block_b
    for node in ast.walk(ast.parse(block_b)):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "t":
            assert hasattr(tokens, node.attr), node.attr
    sheet = qss.stylesheet()
    assert "SWEEP_B: HDA views" in sheet and "SWEEP_B: working_indicator" in sheet


def test_no_widget_constructors_added():
    from collections import Counter
    def constructors(source):
        result = Counter()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else node.func.id if isinstance(node.func, ast.Name) else "")
            if name.startswith("Q") and not name.endswith("Layout"):
                result[name] += 1
        return result
    for name in MODULES:
        path = "python/synapse/panel/" + name + ".py"
        assert not (constructors((ROOT / path).read_text(encoding="utf-8")) - constructors(_base(path)))


def _run(region):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SYNAPSE_REDUCED_MOTION="1",
               PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), region],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if process.returncode == 77:
        pytest.skip(process.stdout.strip())
    assert process.returncode == 0, process.stdout + process.stderr
    lines = [line for line in process.stdout.splitlines() if line.startswith("SWEEP_B_QT=")]
    assert len(lines) == 1, process.stdout
    return json.loads(lines[0].split("=", 1)[1])


@pytest.mark.parametrize("region", REGIONS)
def test_real_spacing_docking_and_second_action_sequence(region):
    measured = _run(region)
    assert measured["densities"] == ["airy", "tight", "standard", "airy"]
    assert measured["states_checked"] and measured["role_removal_preserves_spacing"]


def _qt():
    for name in ("PySide6", "PySide2"):
        try:
            widgets = importlib.import_module(name + ".QtWidgets")
            gui = importlib.import_module(name + ".QtGui")
        except ImportError:
            continue
        assert isinstance(widgets.QApplication, type) and "PySide" in widgets.QApplication.__module__
        return widgets, gui
    sys.stdout.write("NOT_RUN: bound Python has no PySide6/PySide2; real SWEEP_B layout/state measurement unavailable\n")
    raise SystemExit(77)


def _worker(region, widgets, gui):
    from synapse.panel import compositor
    from synapse.panel.designsystem import qss, rhythm, tokens
    module, name = region.split(".")
    source = importlib.import_module("synapse.panel." + module)
    parent = widgets.QWidget()
    parent.setObjectName("DsRoot")
    parent.setStyleSheet(qss.stylesheet())
    parent.resize(380, 400)
    box = widgets.QVBoxLayout(parent)
    child = getattr(source, name)(parent)
    box.addWidget(child)
    # Fractions worked independently: group 16*(3/2,3/4,1,3/2),
    # parameter row 4*(3/2,3/4,1,3/2); no values copied from ROLE_GAPS.
    expected = (24, 12, 16, 24) if OWNER_ROLES[region] == "group" else (6, 3, 4, 6)
    levels = ("airy", "tight", "standard", "airy")
    measurements = []

    def color(label):
        label.ensurePolished()
        return label.palette().color(gui.QPalette.WindowText).name().lower()

    def geometry():
        parent.ensurePolished()
        parent.resize(380, 400)
        parent.show()
        box.activate()
        widgets.QApplication.processEvents()
        for widget in (parent, child):
            minimum = widget.minimumSizeHint().expandedTo(widget.minimumSize())
            assert 0 < minimum.width() <= 380, (region, "minimum width", minimum.width())
            assert 0 < minimum.height() <= 400, (region, "minimum height", minimum.height())
        assert parent.width() <= 380 and parent.height() <= 400
        assert all(widget.minimumHeight() <= 200 for widget in parent.findChildren(widgets.QWidget))

    try:
        for density, gap in zip(levels, expected):
            parent.setProperty("density", density)
            compositor._repolish_tree(parent)
            rhythm.apply(parent, density)
            if module in ("tool_palette", "command_palette"):
                child.hide()
                child.show()  # real showEvent re-reads the changed parent profile
                assert child.property("density") == density
            assert child.layout().spacing() == gap
            for layout in child.findChildren(widgets.QLayout):
                if module == "command_palette" and layout is not child.layout():
                    assert layout.spacing() == dict(airy=6, standard=4, tight=3)[density]
                elif layout is not child.layout():
                    # Nested layouts inherit the owning QWidget's marked layout.
                    assert layout.spacing() == gap, (region, type(layout).__name__, layout.spacing())
            geometry()
            before = child.layout().contentsMargins()
            assert (before.left(), before.top(), before.right(), before.bottom()) == (0, 0, 0, 0)
            rhythm.apply(parent, density)
            assert child.layout().spacing() == gap
            assert child.layout().contentsMargins() == before
            measurements.append(gap)

        if name == "DescribeView":
            calls = []
            child.generate_requested.connect(lambda *args: calls.append(args))
            child.prompt_input.setPlainText("Build a scatter")
            child.context_combo.setCurrentText("LOP")
            child.chk_toolbar.setChecked(True)
            child.generate_btn.click()
            assert calls[-1] == ("Build a scatter", "LOP", {"include_help": True, "add_to_toolbar": True})
            child.reset()
            child.generate_btn.click()
            assert len(calls) == 1
        elif name == "BuildingView":
            child.update_stage("building_nodes", 50, "Building internal nodes")
            assert color(child.dot_labels[0]) == tokens.GROW.lower()
            assert color(child.dot_labels[3]) == tokens.FIRE.lower()
            child.reset()
            assert all(color(dot) == tokens.TEXT_DISABLED.lower() for dot in child.dot_labels)
            child.update_stage("validating", 95)
            assert color(child.dot_labels[-1]) == tokens.FIRE.lower()
        elif name == "ResultView":
            for success in (True, False, True):
                child.populate({"success": success, "node_path": "/obj/" + "asset_" * 40,
                                "error": "Failure " * 12, "parameters": [{"name": "scale", "type": "float", "default": 1}]})
                assert color(child.status_label) == (tokens.GROW if success else tokens.ERROR).lower()
                assert color(child.path_label) == (tokens.GROW if success else tokens.ERROR).lower()
                geometry()
            actions = []
            child.action_requested.connect(actions.append)
            for button in child.findChildren(widgets.QPushButton, "DsHdaAction"):
                button.click()
            assert actions == ["inspect", "edit", "save"]
        elif name == "WorkingIndicator":
            source.read_stall_state = lambda: {"stalled": False}
            source.read_inline_budget = lambda: 30
            child.set_busy(True)
            assert color(child._text) == tokens.STATUS["working"][0].lower()
            child.refresh(stall={"stalled": True}, budget_s=30)
            assert color(child._text) == tokens.STATUS["warning"][0].lower()
            geometry()
            child.set_busy(False)
            assert child.isHidden() and child._text.text() == ""
            child.set_busy(True)
            assert color(child._text) == tokens.STATUS["working"][0].lower()
        elif name == "ToolPalette":
            child._set_axis("verb", "render")
            assert all(row["verb"] == "render" for row in child._visible())
            child._set_axis("verb", "render")
            assert child._verb is None and child._visible() == child._rows
            child._refilter("no such command 987654321")
            assert child._list.count() == 0
            child._refilter("")
            assert child._list.count() > 0
        else:
            child.show_palette()
            child._on_search("no such command 987654321")
            assert child._list.count() == 0
            child._on_search("")
            calls = []
            child.command_selected.connect(calls.append)
            item = child._list.item(0)
            assert item is not None
            child._on_select(item)
            assert calls and child.isHidden()

        if module == "hda_views":
            # The retained alternate entry has no DsRoot and only old HDA ids.
            # Reparent a fresh real view there, then verify central paint lands.
            legacy_parent = widgets.QWidget()
            legacy_box = widgets.QVBoxLayout(legacy_parent)
            legacy_view = getattr(source, name)()
            legacy_box.addWidget(legacy_view)
            try:
                legacy_parent.show()
                widgets.QApplication.processEvents()
                assert legacy_view.objectName() == "DsRoot"
                assert "SWEEP_B: HDA views" in legacy_view.styleSheet()
                if name == "BuildingView":
                    legacy_view.update_stage("building_nodes", 50)
                    assert color(legacy_view.dot_labels[3]) == tokens.FIRE.lower()
                elif name == "ResultView":
                    legacy_view.populate({"success": False, "error": "Failure"})
                    assert color(legacy_view.status_label) == tokens.ERROR.lower()
            finally:
                legacy_view.close()
                legacy_parent.close()

        saved = child.layout().spacing()
        child.setProperty("rhythm_role", None)
        rhythm.apply(parent, "tight")
        assert child.layout().spacing() == saved
        return {"densities": levels, "spacing": measurements,
                "states_checked": True, "role_removal_preserves_spacing": True}
    finally:
        child.close()
        parent.close()


if __name__ == "__main__":
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert os.environ["SYNAPSE_REDUCED_MOTION"] == "1"
    sys.path.insert(0, str(ROOT / "python"))
    widgets, gui = _qt()
    app = widgets.QApplication.instance() or widgets.QApplication([])
    result = _worker(sys.argv[1], widgets, gui)
    sys.stdout.write("SWEEP_B_QT=" + json.dumps(result, sort_keys=True) + "\n")
