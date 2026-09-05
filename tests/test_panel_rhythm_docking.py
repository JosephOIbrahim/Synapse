"""Real Qt probes at 380px; no stubs and no screenshot stand-ins.

Subprocesses isolate Qt from the full suite's PySide/hou fakes and bound widget
lifetimes. Absence exits 77 and becomes an explicit skip, never a green probe.
The worker imports real production constructors, not recreated region layouts.
"""

import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / ".synapse/contracts/docking-minimums.yaml"
DENSITIES = ("airy", "standard", "tight")
PROFILES = {"airy": "curious", "standard": "expert", "tight": "ml"}
# These expected values are independently worked from the brief's fractions:
# 12*(3/2,1,3/4)=(18,12,9); 16*...=(24,16,12); 4*...=(6,4,3).
EXPECTED = {"label": (18, 12, 9), "row": (18, 12, 9),
            "tag": (24, 16, 12), "card": (24, 16, 12),
            "parm_row": (6, 4, 3), "group": (24, 16, 12),
            # landing r3 roles (RULING-3 / RULING-4a): 16*..., 4*..., 0
            "shell": (24, 16, 12), "stack": (6, 4, 3), "band": (0, 0, 0)}
ALTERNATE_REGIONS = (
    "face_work.FaceWork", "face_review.FaceReview", "gate_widget.GateWidget",
    "context_bar.ContextChips", "quick_actions.QuickActionPills",
    "hda_views.DescribeView", "hda_views.BuildingView", "hda_views.ResultView",
    "tool_palette.ToolPalette", "command_palette.CommandPaletteWidget",
    "working_indicator.WorkingIndicator", "health_infographic.HealthInfographic",
    "integrity_readout.IntegrityReadout", "health_strip.HealthStrip",
    "context_bar.build_context_bar_widget", "chat_panel.SynapseChatPanel",
)


def _bounds():
    text = CONTRACT.read_text(encoding="utf-8")
    # Read the actual YAML descriptions; do not silently follow the conflicting
    # 420px token. These constrained fields need no optional YAML dependency.
    heights = re.findall(r'without overflow at (\d+)px tall', text)
    children = re.findall(r'No child sets a hard minimum height above (\d+)px', text)
    assert len(heights) == len(children) == 1, "docking contract shape changed"
    return 380, int(heights[0]), int(children[0])


def test_docking_bounds_read_the_contract_not_panel_height_token():
    from synapse.panel.designsystem import tokens
    width, height, child_height = _bounds()
    assert height <= tokens.PANEL_MIN_HEIGHT
    command = re.search(r'max-min-height python/synapse/panel (\d+)',
                        CONTRACT.read_text(encoding="utf-8"))
    assert command and int(command[1]) == child_height
    assert 0 < child_height < height and tokens.PANEL_MIN_WIDTH <= width


def _run(case, density="standard", detail=""):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SYNAPSE_REDUCED_MOTION="1",
               PYTHONDONTWRITEBYTECODE="1")
    # TEMP/TMP are set by the command in REPORT. Refuse a GUI platform even if
    # the outer suite's environment changes after collection.
    result = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), case, density, detail],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode == 77:
        pytest.skip(result.stdout.strip() or "PySide unavailable; real Qt probe NOT_RUN")
    assert result.returncode == 0, result.stdout + result.stderr
    lines = [line for line in result.stdout.splitlines() if line.startswith("PD_QT=")]
    assert len(lines) == 1, result.stdout + result.stderr
    return json.loads(lines[0].removeprefix("PD_QT="))


@pytest.fixture(scope="module")
def real_qt():
    return _run("available")


@pytest.mark.parametrize("role", tuple(EXPECTED))
@pytest.mark.parametrize("density", DENSITIES)
def test_real_layout_spacing_role_density_and_removal(real_qt, role, density):
    measured = _run("spacing", density, role)
    assert measured["spacing"] == EXPECTED[role][DENSITIES.index(density)]
    assert measured["removed_role_preserved"] and measured["idempotent"]


@pytest.mark.parametrize("pattern", ("label", "row", "tag", "card", "parm_row"))
@pytest.mark.parametrize("density", DENSITIES)
def test_component_pattern_at_docking_width(real_qt, pattern, density):
    assert _run("pattern", density, pattern)["within_bounds"]


@pytest.mark.parametrize("density", DENSITIES)
def test_every_composed_region_and_face_at_docking_bound(real_qt, density):
    measured = _run("panel", density)
    assert measured["regions"] == ["rail", "context_ribbon", "mode_bar", "faces"]
    assert measured["camera_regions"] == ["profile_tab_strip", "header_ribbon",
                                           "chat_transcript", "verb_rail", "token_face"]
    assert measured["states"] == ["direct", "work", "done", "token", "hda"]


@pytest.mark.parametrize("region", ALTERNATE_REGIONS)
@pytest.mark.parametrize("density", DENSITIES)
def test_alternate_census_widget_regions(real_qt, region, density):
    assert _run("alternate", density, region)["within_bounds"]


@pytest.mark.parametrize("density", DENSITIES)
def test_recall_region_when_camera_has_built_it(real_qt, density):
    assert _run("recall", density)["within_bounds"]


def _qt():
    for binding in ("PySide6", "PySide2"):
        try:
            widgets = importlib.import_module(binding + ".QtWidgets")
        except ImportError:
            continue
        assert isinstance(widgets.QApplication, type)
        assert "PySide" in widgets.QApplication.__module__, "a Qt stub is not evidence"
        return widgets
    sys.stdout.write("NOT_RUN: PySide6/PySide2 absent in bound interpreter; no real Qt layout measurement\n")
    raise SystemExit(77)


def _margins(layout):
    margins = layout.contentsMargins()
    return margins.left(), margins.top(), margins.right(), margins.bottom()


def _spacing(widgets, density, role):
    from synapse.panel.designsystem import qss, rhythm
    from synapse.panel import compositor
    root = widgets.QWidget()
    root.setObjectName("DsRoot")
    root.setStyleSheet(qss.stylesheet())
    parent = widgets.QVBoxLayout(root)
    unmarked_spacing, unmarked_margins = parent.spacing(), _margins(parent)
    child = widgets.QWidget()
    parent.addWidget(child)
    box = widgets.QVBoxLayout(child)
    box.addWidget(widgets.QLabel("One"))
    box.addWidget(widgets.QLabel("Two"))
    box.setSpacing(7)
    box.setContentsMargins(1, 2, 3, 4)
    child.setProperty("rhythm_role", role)
    root.setProperty("density", density)
    compositor._repolish_tree(root)
    assert rhythm.apply(root, density) == 1
    first = box.spacing(), _margins(box)
    # shell = (GUTTER, SPACE_SM, GUTTER, SPACE_SM): the one consumer of the
    # 30px gutter token; worked from tokens.py, not from _MARGINS.
    expected_margins = {"row": (16, 12, 16, 12), "tag": (10, 6, 10, 6),
                        "shell": (30, 8, 30, 8)}
    assert first[1] == expected_margins.get(role, (0, 0, 0, 0))
    assert (parent.spacing(), _margins(parent)) == (unmarked_spacing, unmarked_margins)
    rhythm.apply(root, density)
    assert first == (box.spacing(), _margins(box))
    if role in ("label", "tag"):
        font = child.font()
        assert font.capitalization() == type(font).AllUppercase
        assert font.letterSpacing() == (108.0 if role == "label" else 106.0)
    # Negative control: the same real layout without its role retains its
    # measured value when another density is applied.
    child.setProperty("rhythm_role", None)
    other = "tight" if density != "tight" else "airy"
    assert rhythm.apply(root, other) == 0
    assert first == (box.spacing(), _margins(box))
    # Sequence control, including a switch back, tests accumulation bugs.
    child.setProperty("rhythm_role", role)
    for level in ("airy", "tight", "standard", "airy"):
        rhythm.apply(root, level)
        assert box.spacing() == EXPECTED[role][DENSITIES.index(level)]
        assert _margins(box) == first[1]
    root.close()
    return {"spacing": first[0], "idempotent": True, "removed_role_preserved": True}


def _measure(root, widgets):
    width, height, child_height = _bounds()
    root.ensurePolished()
    root.resize(width, height)
    root.show()  # offscreen only; never a live Houdini window
    if root.layout() is not None:
        root.layout().activate()
    minimum = root.minimumSizeHint().expandedTo(root.minimumSize())
    assert 0 < minimum.width() <= width, (root.objectName(), "width", minimum.width(), width)
    assert 0 < minimum.height() <= height, (root.objectName(), "height", minimum.height(), height)
    assert root.width() <= width and root.height() <= height, (root.width(), root.height())
    for child in root.findChildren(widgets.QWidget):
        assert child.minimumHeight() <= child_height, (child.objectName(), child.minimumHeight())
    return {"within_bounds": True, "minimum": [minimum.width(), minimum.height()]}


def _pattern(widgets, density, pattern):
    from synapse.panel.designsystem import qss, rhythm
    from synapse.panel import compositor
    root = widgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", density)
    root.setStyleSheet(qss.stylesheet())
    outer = widgets.QVBoxLayout(root)
    if pattern in ("label", "tag"):
        item = widgets.QLabel("what I remember" if pattern == "label" else "UNAVAILABLE")
    else:
        item = widgets.QWidget()
    item.setProperty("rhythm_role", pattern)
    outer.addWidget(item)
    if pattern == "row":
        box = widgets.QHBoxLayout(item)
        glyph = widgets.QLabel("i")
        glyph.setObjectName("DsRowGlyph")
        box.addWidget(glyph)
        box.addWidget(widgets.QLabel("Recall result"), 1)
    elif pattern == "parm_row":
        box = widgets.QHBoxLayout(item)
        for name, text in (("DsParmLabel", "Tokens"), ("DsParmValue", "UNKNOWN")):
            label = widgets.QLabel(text)
            label.setObjectName(name)
            box.addWidget(label)
        control = widgets.QWidget()
        control.setObjectName("DsParmControl")
        box.addWidget(control, 1)
    elif pattern == "card":
        from synapse.panel.designsystem.components import Card
        cards = widgets.QVBoxLayout(item)
        for _ in range(2):
            card = Card()
            cards.addWidget(card)
            bands = widgets.QVBoxLayout(card)
            bands.setContentsMargins(0, 0, 0, 0)
            bands.setSpacing(0)  # fixed internal seam, not collection rhythm
            for name, text in (("DsCardHeader", "What I remember"),
                               ("DsCardBody", "No stored result"),
                               ("DsCardFooter", "UNAVAILABLE")):
                band = widgets.QLabel(text)
                band.setObjectName(name)
                bands.addWidget(band)
    compositor._repolish_tree(root)
    rhythm.apply(root, density)
    measured = _measure(root, widgets)
    if pattern == "parm_row":
        assert item.findChild(widgets.QLabel, "DsParmLabel").width() == 128
        assert item.findChild(widgets.QLabel, "DsParmValue").width() == 64
    if pattern == "card":
        for name in ("DsCardHeader", "DsCardFooter"):
            assert all(band.height() == 40 for band in item.findChildren(widgets.QLabel, name))
    root.close()
    return measured


def _panel(widgets, density, recall=False):
    if recall and not (ROOT / "python/synapse/panel/recall_card.py").is_file():
        sys.stdout.write("NOT_RUN: recall_card.py absent; CAMERA has not built the region\n")
        raise SystemExit(77)
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel import compositor
    panel = SynapsePanel()
    try:
        panel._recompose(PROFILES[density])
        if recall:
            cards = [w for w in panel.findChildren(widgets.QWidget)
                     if type(w).__module__.endswith(".recall_card")]
            assert cards, "recall module exists but its widget is not wired into the panel"
            for card in cards:
                _measure(card, widgets)
            return {"within_bounds": True}
        measurements = []
        for state in ("direct", "work", "done", "token", "hda"):
            panel._set_face("work" if state == "done" else "direct" if state == "hda" else state)
            if state == "done":
                panel._set_work_substate("done")
            elif state == "work":
                panel._set_work_substate("cook")
            elif state == "hda":
                panel._set_direct_view("hda")
            measurements.append(_measure(panel, widgets))
            for builder in compositor.REGION_BUILDERS.values():
                region = panel._region_cache[builder]
                minimum = region.minimumSizeHint().expandedTo(region.minimumSize())
                assert minimum.width() <= _bounds()[0], (builder, minimum.width())
                assert minimum.height() <= _bounds()[1], (builder, minimum.height())
        # Real source widget identities for the five currently present cameras.
        for region in (panel._chat, panel._font_btn.parentWidget(), panel._faces.widget(2)):
            assert region is not None
            assert region.minimumSizeHint().width() <= _bounds()[0]
        return {"regions": list(compositor.REGION_BUILDERS),
                "camera_regions": ["profile_tab_strip", "header_ribbon", "chat_transcript",
                                   "verb_rail", "token_face"],
                "states": ["direct", "work", "done", "token", "hda"],
                "measurements": measurements}
    finally:
        panel.close()


def _alternate(widgets, density, region):
    from synapse.panel import compositor
    from synapse.panel.designsystem import qss, rhythm
    module, name = region.split(".")
    source = importlib.import_module("synapse.panel." + module)
    constructor = getattr(source, name)
    root = widgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", density)
    root.setStyleSheet(qss.stylesheet())
    box = widgets.QVBoxLayout(root)
    controller = None
    if region == "health_strip.HealthStrip":
        child = constructor(source.build_cells(source.StripSnapshot()))
    elif region == "context_bar.build_context_bar_widget":
        child = constructor(source.ContextBarState())
    elif region == "chat_panel.SynapseChatPanel":
        controller = constructor()
        child = controller.createInterface()
    else:
        child = constructor()
    assert isinstance(child, widgets.QWidget), "fallback object cannot prove QWidget geometry"
    box.addWidget(child)
    compositor._repolish_tree(root)
    rhythm.apply(root, density)
    try:
        measured = _measure(root, widgets)
        # Alternate Chat/HDA entry also has a stacked page; inspect every page
        # through its existing container, without activating its live bridge.
        if controller is not None:
            for index in range(controller._mode_stack.count()):
                controller._mode_stack.setCurrentIndex(index)
                _measure(root, widgets)
        return measured
    finally:
        if controller is not None:
            controller.onDestroyInterface()
        root.close()


if __name__ == "__main__":
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    assert os.environ.get("SYNAPSE_REDUCED_MOTION") == "1"
    sys.path.insert(0, str(ROOT / "python"))
    widgets = _qt()
    case, density, detail = sys.argv[1:4]
    app = widgets.QApplication.instance() or widgets.QApplication([])
    if case == "available":
        result = {"binding": widgets.__name__}
    elif case == "spacing":
        result = _spacing(widgets, density, detail)
    elif case == "pattern":
        result = _pattern(widgets, density, detail)
    elif case == "alternate":
        result = _alternate(widgets, density, detail)
    else:
        assert case in ("panel", "recall")
        result = _panel(widgets, density, recall=case == "recall")
    sys.stdout.write("PD_QT=" + json.dumps(result, sort_keys=True) + "\n")
