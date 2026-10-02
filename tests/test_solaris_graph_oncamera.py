"""On-camera polish for Solaris network creation (Oct 7 demo).

G1 -- build_graph cooks what it built and reads node.errors()/warnings();
      an error badge on a NEW node rolls the build back, warnings are reported.
G2 -- build_graph frames the Network Editor on the new nodes when a UI exists.
G3 -- scene_template lays out ONLY its own chain and sets a display flag.

Fakes are pinned to the H22.0.400 signatures (hou.py, verified in hython):
  Node.cook(*args, **kwargs) [force=False], Node.errors(), Node.warnings(),
  NetworkMovableItem.setSelected(on, clear_all_selected=False,
  show_asset_if_selected=False), Node.setCurrent(on, clear_all_selected=False),
  PathBasedPaneTab.pwd(), NetworkEditor.homeToSelection(),
  Node.layoutChildren(items=(), horizontal_spacing=-1.0, vertical_spacing=-1.0).
create_autospec enforces them, so a call with an invented kwarg fails here.
"""

import os
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

from synapse.server import handlers_solaris_graph as graph_mod  # noqa: E402
from synapse.mcp.tool_impls.solaris import scene_template  # noqa: E402


class _Node:
    def path(self): ...
    def name(self): ...
    def cook(self, force=False, frame_range=()): ...
    def errors(self): ...
    def warnings(self): ...
    def setSelected(self, on, clear_all_selected=False, show_asset_if_selected=False): ...
    def setCurrent(self, on, clear_all_selected=False): ...
    def position(self): ...
    def setPosition(self, position): ...
    def layoutChildren(self, items=(), horizontal_spacing=-1.0, vertical_spacing=-1.0): ...
    def children(self): ...


class _LopNode(_Node):
    def setDisplayFlag(self, on): ...
    def inputs(self): ...
    def outputs(self): ...
    def size(self): ...


class _RopNode(_Node):
    """usdrender_rop under /stage: a RopNode, no display flag (H22 probe)."""


class _NetworkEditor:
    def pwd(self): ...
    def homeToSelection(self): ...
    def frameSelection(self): ...
    def setCurrentNode(self, node, pick_node=True): ...
    def setVisibleBounds(self, bounds, transition_time=0.0, max_scale=0.0,
                         set_center_when_scale_rejected=False): ...


class _BoundingRect:
    """hou.BoundingRect(xmin, ymin, xmax, ymax) + expand(offset) (H22 probe)."""
    def __init__(self, x0, y0, x1, y1):
        self.box = [x0, y0, x1, y1]

    def expand(self, offset):
        self.box = [self.box[0] - offset[0], self.box[1] - offset[1],
                    self.box[2] + offset[0], self.box[3] + offset[1]]


class _PaneTab:
    def pwd(self): ...


class _OperationFailed(Exception):
    pass


def _lop(path, errors=(), warnings=(), cook_raises=False):
    node = mock.create_autospec(_LopNode, instance=True)
    node.path.return_value = path
    node.errors.return_value = tuple(errors)
    node.warnings.return_value = tuple(warnings)
    if cook_raises:
        node.cook.side_effect = _OperationFailed()
    return node


def _rop(path, errors=()):
    node = mock.create_autospec(_RopNode, instance=True)
    node.path.return_value = path
    node.errors.return_value = tuple(errors)
    node.warnings.return_value = ()
    return node


def _fake_hou(ui_available=True, tabs=(), with_ui=True):
    ns = types.SimpleNamespace(
        LopNode=_LopNode,
        NetworkEditor=_NetworkEditor,
        BoundingRect=_BoundingRect,
        isUIAvailable=lambda: ui_available,
        Vector2=lambda x, y: (x, y),
    )
    if with_ui:
        ns.ui = types.SimpleNamespace(paneTabs=lambda: tuple(tabs))
    return ns


def _editor(pwd_path):
    editor = mock.create_autospec(_NetworkEditor, instance=True)
    pwd = mock.create_autospec(_Node, instance=True)
    pwd.path.return_value = pwd_path
    editor.pwd.return_value = pwd
    return editor


def _chain():
    """look (2.41) -> key (1.52) -> rim (0.62) -> dome (-1.0); tile 1.13 x 0.28."""
    spec = [("/stage/look", 2.41), ("/stage/key", 1.52), ("/stage/rim", 0.62), ("/stage/dome", -1.0)]
    nodes = []
    for path, y in spec:
        node = _lop(path)
        node.position.return_value = (-1.69, y)
        node.size.return_value = (1.13, 0.28)
        nodes.append(node)
    for index, node in enumerate(nodes):
        node.inputs.return_value = (nodes[index - 1],) if index else ()
        node.outputs.return_value = (nodes[index + 1],) if index + 1 < len(nodes) else ()
    return nodes


def _parent(path="/stage"):
    parent = mock.create_autospec(_Node, instance=True)
    parent.path.return_value = path
    return parent


# ── G1: badge collection ────────────────────────────────────────────────


class TestBadgeCollection:
    def test_errors_and_warnings_are_collected_with_paths(self, monkeypatch):
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(), raising=False)
        bad = _lop("/stage/bad", errors=("Invalid SOP path: /obj/nope",), cook_raises=True)
        warn = _lop("/stage/warn", warnings=("no prims matched",))
        errors, warnings = graph_mod._cook_and_collect_badges([bad, warn])
        assert errors == [("/stage/bad", "Invalid SOP path: /obj/nope")]
        assert warnings == [("/stage/warn", "no prims matched")]

    def test_lop_nodes_are_cooked_before_reading(self, monkeypatch):
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(), raising=False)
        node = _lop("/stage/key")
        graph_mod._cook_and_collect_badges([node])
        node.cook.assert_called_once_with(force=False)

    def test_rop_is_read_but_never_cooked(self, monkeypatch):
        # Cooking a usdrender_rop renders; the check must not do that.
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(), raising=False)
        rop = _rop("/stage/render", errors=("no camera",))
        errors, _ = graph_mod._cook_and_collect_badges([rop])
        rop.cook.assert_not_called()
        assert errors == [("/stage/render", "no camera")]

    def test_cook_failure_is_the_signal_not_a_crash(self, monkeypatch):
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(), raising=False)
        node = _lop("/stage/x", errors=("boom",), cook_raises=True)
        errors, warnings = graph_mod._cook_and_collect_badges([node])
        assert errors == [("/stage/x", "boom")] and warnings == []

    def test_clean_nodes_report_nothing(self, monkeypatch):
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(), raising=False)
        assert graph_mod._cook_and_collect_badges([_lop("/stage/a"), _lop("/stage/b")]) == ([], [])


# ── G2: framing ─────────────────────────────────────────────────────────


class TestFraming:
    def test_no_ui_is_a_noop(self, monkeypatch):
        editor = _editor("/stage")
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(ui_available=False, tabs=[editor]), raising=False)
        node = _lop("/stage/key")
        assert graph_mod._frame_new_nodes(_parent(), [node], node) is False
        node.setSelected.assert_not_called()
        editor.homeToSelection.assert_not_called()

    def test_missing_hou_ui_is_a_noop(self, monkeypatch):
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(with_ui=False), raising=False)
        node = _lop("/stage/key")
        assert graph_mod._frame_new_nodes(_parent(), [node], node) is False

    def test_no_editor_on_this_network(self, monkeypatch):
        other = _editor("/obj")
        not_editor = mock.create_autospec(_PaneTab, instance=True)
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(tabs=[other, not_editor]), raising=False)
        node = _lop("/stage/key")
        assert graph_mod._frame_new_nodes(_parent(), [node], node) is False
        other.homeToSelection.assert_not_called()
        node.setSelected.assert_not_called()

    def test_frames_matching_editor_and_selects_new_nodes(self, monkeypatch):
        match, other = _editor("/stage"), _editor("/obj")
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(tabs=[other, match]), raising=False)
        look, key, rim, dome = _chain()
        assert graph_mod._frame_new_nodes(_parent(), [key, rim], rim) is True
        key.setSelected.assert_called_once_with(True, clear_all_selected=True)
        rim.setSelected.assert_called_once_with(True, clear_all_selected=False)
        rim.setCurrent.assert_called_once_with(True, clear_all_selected=False)
        # P4: the new nodes PLUS their neighbours (look above, dome below), padded
        match.setVisibleBounds.assert_called_once()
        (bounds,), kwargs = match.setVisibleBounds.call_args
        pad_x, pad_y = graph_mod._FRAME_PAD
        assert bounds.box == pytest.approx([-1.69 - pad_x, -1.0 - pad_y,
                                            -1.69 + 1.13 + pad_x, 2.41 + 0.28 + pad_y])
        assert kwargs == {"transition_time": graph_mod._FRAME_TRANSITION}
        match.homeToSelection.assert_not_called()
        match.frameSelection.assert_not_called()
        other.setVisibleBounds.assert_not_called()

    def test_unmeasurable_context_falls_back_to_home(self, monkeypatch):
        match = _editor("/stage")
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(tabs=[match]), raising=False)
        look, key, rim, dome = _chain()
        key.size.side_effect = RuntimeError("no tile")
        assert graph_mod._frame_new_nodes(_parent(), [key, rim], rim) is True
        match.homeToSelection.assert_called_once_with()
        match.setVisibleBounds.assert_not_called()

    def test_any_exception_returns_false(self, monkeypatch):
        match = _editor("/stage")
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(tabs=[match]), raising=False)
        node = _lop("/stage/key")
        node.setSelected.side_effect = RuntimeError("selection blew up")
        assert graph_mod._frame_new_nodes(_parent(), [node], node) is False

    def test_empty_node_list_is_a_noop(self, monkeypatch):
        match = _editor("/stage")
        monkeypatch.setattr(graph_mod, "hou", _fake_hou(tabs=[match]), raising=False)
        assert graph_mod._frame_new_nodes(_parent(), [], None) is False
        match.homeToSelection.assert_not_called()


# ── Handler contract: flags, placement ──────────────────────────────────


class TestHandlerFlags:
    @pytest.mark.parametrize("flag", ["badge_check", "frame"])
    def test_non_boolean_flag_is_rejected(self, monkeypatch, flag):
        from synapse.core.errors import SynapseUserError
        monkeypatch.setattr(graph_mod, "HOU_AVAILABLE", True)
        handler = type("H", (graph_mod.SolarisGraphMixin,), {})()
        with pytest.raises(SynapseUserError, match=flag):
            handler._handle_solaris_build_graph(
                {"nodes": [{"id": "a", "type": "null"}], "connections": [], flag: "yes"})

    def test_badge_check_runs_inside_undo_group_after_sandwich(self):
        src = open(graph_mod.__file__, encoding="utf-8").read()
        group = src.index('with hou.undos.group("SYNAPSE: build_graph")')
        sandwich = src.index("with cook_sandwich(", group)
        check = src.index("_cook_and_collect_badges(\n", sandwich)
        rollback = src.index("hou.undos.performUndo()", check)
        frame = src.index("_frame_new_nodes(parent_node", rollback)
        assert group < sandwich < check < rollback < frame
        # `if badge_check:` is a sibling of `with cook_sandwich(` (same indent),
        # i.e. it runs after the sandwich closed and restored the update mode,
        # but still inside the undo group.
        def indent_of(pos):
            line = src[src.rindex("\n", 0, pos) + 1:pos]
            return len(line) - len(line.lstrip(" "))
        gate = src.index("if badge_check:", sandwich)
        assert gate < check
        assert indent_of(gate) == indent_of(sandwich) > indent_of(group)

    def test_registry_documents_both_flags(self):
        reg = open(os.path.join(os.path.dirname(graph_mod.__file__), "..", "mcp",
                                "_tool_registry.py"), encoding="utf-8").read()
        block = reg[reg.index('("synapse_solaris_build_graph"'):reg.index('("synapse_solaris_component_builder"')]
        assert '"badge_check": {"type": "boolean"' in block
        assert '"frame": {"type": "boolean"' in block


class TestBadgeFailureSaysWhatHappened:
    """A build whose new node errors is rolled back only when its undo group
    reaches the undo stack. Under another open group (the panel's execution
    bridge) it does not, the nodes stay, and before 10/1 the error still said
    "rolled back ... Nothing was left in the network". Probed on 22.0.400."""

    DETAIL = "1 new node(s) showed an error badge after cooking: /stage/bad: boom"

    def test_rolled_back_says_so(self):
        text = str(graph_mod._badge_failure_error(self.DETAIL, True, True))
        assert text.startswith("build rolled back -- 1 new node(s) showed an error badge")
        assert "Nothing was left in the network. Fix the parameter/input named above" in text

    def test_not_rolled_back_under_another_undo_step_says_so(self):
        text = str(graph_mod._badge_failure_error(self.DETAIL, False, True))
        assert text.startswith("build failed and was NOT rolled back -- 1 new node(s)")
        assert "Its nodes are still in the network" in text and "one Ctrl+Z (or REVERT) removes them" in text
        assert "Nothing was left" not in text and "rolled back --" not in text.replace("NOT rolled back --", "")

    def test_undo_off_says_to_remove_them_by_hand(self):
        text = str(graph_mod._badge_failure_error(self.DETAIL, False, False))
        assert "undo is off, so remove them by hand" in text and "Ctrl+Z" not in text

    def test_the_error_is_worded_after_the_rollback_attempt(self):
        src = open(graph_mod.__file__, encoding="utf-8").read()
        raised = src.index("raise _BadgeFailure(")
        attempt = src.index("hou.undos.performUndo()\n                        rolled_back = True", raised)
        worded = src.index("raise _badge_failure_error(str(build_exc), rolled_back, undo_enabled)", attempt)
        assert raised < attempt < worded
        assert src.count('"build rolled back -- "') == 1          # one place words it, and it checks first
        assert issubclass(graph_mod._BadgeFailure, graph_mod.SynapseUserError)


# ── G3: scene_template layout + display ─────────────────────────────────


def _placed(cls, path, pos):
    node = mock.create_autospec(cls, instance=True)
    node.path.return_value = path
    state = {"pos": tuple(pos)}
    node.position.side_effect = lambda: state["pos"]
    node.setPosition.side_effect = lambda p: state.__setitem__("pos", tuple(p))
    return node


class TestSceneTemplateLayout:
    def test_lays_out_only_the_chain_and_moves_it_to_free_space(self, monkeypatch):
        monkeypatch.setattr(scene_template, "hou", _fake_hou(), raising=False)
        import synapse.server.handler_helpers as helpers
        monkeypatch.setattr(helpers, "_free_origin", lambda parent, new_ids: (10.0, -20.0))
        parent = mock.create_autospec(_Node, instance=True)
        chain = [_placed(_LopNode, "/stage/prim", (0.0, 2.0)),
                 _placed(_LopNode, "/stage/cam", (0.0, 1.0)),
                 _placed(_RopNode, "/stage/render", (0.0, 0.0))]
        scene_template._layout_chain(parent, chain)
        parent.layoutChildren.assert_called_once_with(items=tuple(chain))
        # root lands at the free origin; the chain keeps its shape
        assert [n.position() for n in chain] == [(10.0, -20.0), (10.0, -21.0), (10.0, -22.0)]

    def test_never_lays_out_the_whole_network(self, monkeypatch):
        code = [line for line in open(scene_template.__file__, encoding="utf-8")
                if not line.lstrip().startswith("#")]
        assert not any("layoutChildren()" in line for line in code)

    def test_layout_failure_never_fails_the_template(self, monkeypatch):
        monkeypatch.setattr(scene_template, "hou", _fake_hou(), raising=False)
        parent = mock.create_autospec(_Node, instance=True)
        parent.layoutChildren.side_effect = RuntimeError("no")
        scene_template._layout_chain(parent, [_placed(_LopNode, "/stage/a", (0, 0))])

    def test_display_lands_on_last_node_that_has_a_flag(self):
        settings = _placed(_LopNode, "/stage/render_settings", (0, 0))
        rop = _placed(_RopNode, "/stage/render", (0, 0))
        first = _placed(_LopNode, "/stage/prim", (0, 0))
        assert scene_template._set_display_on_last([first, settings, rop]) == "/stage/render_settings"
        settings.setDisplayFlag.assert_called_once_with(True)
        first.setDisplayFlag.assert_not_called()
        assert not hasattr(rop, "setDisplayFlag")

    def test_display_none_when_nothing_can_carry_it(self):
        assert scene_template._set_display_on_last([_placed(_RopNode, "/stage/r", (0, 0))]) is None


# ── Splice placement: side column beside the displaced node ─────────────


class TestSpliceOrigin:
    def test_side_column_beside_the_displaced_node(self):
        # rc3 demo column: ground 3.41, look 2.41, dome 1.52, cam 0.62, settings -0.27
        others = [(-1.69, 3.41), (-1.69, 2.41), (-1.69, 1.52), (-1.69, 0.62), (-1.69, -0.27),
                  (9.0, -20.0)]   # far away, outside the band: ignored
        local = {"key": (0.0, 0.0), "rim": (0.0, -1.2)}
        ox, oy = graph_mod._splice_origin((-1.69, 2.41), local, others)
        assert ox == pytest.approx(-1.69 + graph_mod._SPLICE_SIDE_GAP)
        assert oy == pytest.approx(2.41 - graph_mod._SPLICE_ROW)

    def test_clears_wider_neighbours_in_the_band(self):
        others = [(-1.0, 2.0), (4.0, 1.0)]
        ox, _ = graph_mod._splice_origin((-1.0, 2.0), {"a": (0.0, 0.0)}, others)
        assert ox == pytest.approx(4.0 + graph_mod._SPLICE_SIDE_GAP)

    def test_handler_uses_it_only_for_splices_without_reused_anchors(self):
        src = open(graph_mod.__file__, encoding="utf-8").read()
        anchors = src.index("if anchors:\n")
        splice = src.index("elif splice_anchor is not None and local_positions:", anchors)
        free = src.index("ox, oy = _free_origin(parent_node", splice)
        assert anchors < splice < free


# ── DIAG review #2: an error inherited from upstream is not the new node's ──


def _wired(path, errors=(), inputs=()):
    node = _lop(path, errors=errors)
    node.inputs.return_value = tuple(inputs)
    return node


class TestInheritedErrors:
    def test_new_node_under_an_erroring_existing_node_is_inherited(self):
        # look_fade_10 is a numpy pythonscript LOP in the demo: if it errors,
        # the new light reports "Invalid source ..." -- not its own fault.
        look = _wired("/stage/look_fade_10", errors=("Python error",))
        key = _wired("/stage/dusk_key", errors=("Invalid source /stage/look_fade_10.",), inputs=[look])
        rim = _wired("/stage/dusk_rim", errors=("Invalid source /stage/dusk_key.",), inputs=[key])
        created = {"/stage/dusk_key", "/stage/dusk_rim"}
        assert graph_mod._inherited_error_nodes([key, rim], created) == {
            "/stage/dusk_key": "/stage/look_fade_10", "/stage/dusk_rim": "/stage/look_fade_10"}

    def test_own_error_on_a_new_node_stays_fatal(self):
        look = _wired("/stage/look_fade_10")
        bad = _wired("/stage/bad", errors=("Invalid SOP path",), inputs=[look])
        assert graph_mod._inherited_error_nodes([bad], {"/stage/bad"}) == {}

    def test_downstream_of_a_genuinely_bad_new_node_is_not_excused(self):
        # bad's own error is fatal; rim inherits from a CREATED node that is
        # itself fatal, so rim is not excused either (the rollback names bad).
        look = _wired("/stage/look")
        bad = _wired("/stage/bad", errors=("own",), inputs=[look])
        rim = _wired("/stage/rim", errors=("Invalid source /stage/bad.",), inputs=[bad])
        assert graph_mod._inherited_error_nodes([bad, rim], {"/stage/bad", "/stage/rim"}) == {}

    def test_handler_excludes_inherited_errors_from_rollback(self):
        src = open(graph_mod.__file__, encoding="utf-8").read()
        assert "_inherited_error_nodes(" in src[src.index("if badge_check:"):]
        assert "p not in inherited" in src


class TestSceneTemplateKeepsArtistDisplay:
    def test_execute_only_sets_display_when_nothing_was_displayed(self):
        src = open(scene_template.__file__, encoding="utf-8").read()
        body = src[src.index("def execute("):]
        assert "_displayed_child(parent)" in body
        assert body.index("_displayed_child(parent)") < body.index('createNode("primitive"')
        assert "if display_before is None:" in body

    def test_displayed_child_reads_observed_display(self, monkeypatch):
        import synapse.server.solaris_graph_plan as plan_mod
        monkeypatch.setattr(plan_mod, "observed_display", lambda parent: (None, True))
        assert scene_template._displayed_child(object()) is None
        monkeypatch.setattr(plan_mod, "observed_display", lambda parent: ("/stage/demo_settings", True))
        assert scene_template._displayed_child(object()) == "/stage/demo_settings"
        monkeypatch.setattr(plan_mod, "observed_display", lambda parent: (None, False))
        assert scene_template._displayed_child(object()) == "<unknown>"


# ── Round 2 P3: inline splice layout ────────────────────────────────────


class TestInlineSplice:
    # rc3 demo column: look 2.41 -> dome 1.52 -> cam 0.62 -> settings -0.27 (x -1.69)
    LOOK, DOME = (-1.69, 2.41), (-1.69, 1.52)
    DOWN = {"/stage/demo_dome": (-1.69, 1.52), "/stage/demo_cam": (-1.69, 0.62),
            "/stage/demo_settings": (-1.69, -0.27), "/stage/side_rop": (6.0, 0.0)}
    LOCAL = {"key": (0.0, 0.0), "rim": (0.0, -1.2)}

    def test_new_nodes_go_directly_below_the_anchor_at_its_pitch(self):
        positions, _ = graph_mod._inline_splice_layout(self.LOOK, self.DOME, self.LOCAL, self.DOWN)
        pitch = 2.41 - 1.52
        assert positions["key"] == pytest.approx((-1.69, 2.41 - pitch))
        assert positions["rim"] == pytest.approx((-1.69, 2.41 - 2 * pitch))

    def test_only_the_downstream_column_shifts_by_the_inserted_height(self):
        _, shifts = graph_mod._inline_splice_layout(self.LOOK, self.DOME, self.LOCAL, self.DOWN)
        dy = -2 * (2.41 - 1.52)
        assert [(p, dx) for p, dx, _ in shifts] == [
            ("/stage/demo_cam", 0.0), ("/stage/demo_dome", 0.0), ("/stage/demo_settings", 0.0)]
        assert all(d == pytest.approx(dy) for _, _, d in shifts)   # side_rop out of band

    def test_room_already_there_moves_nothing(self):
        far = (-1.69, -5.0)
        _, shifts = graph_mod._inline_splice_layout(self.LOOK, far, self.LOCAL, {"/stage/b": far})
        assert shifts == []

    def test_not_a_vertical_step_falls_back(self):
        assert graph_mod._inline_splice_layout((0.0, 0.0), (4.0, 0.0), self.LOCAL, {}) is None
        assert graph_mod._inline_splice_layout((0.0, 0.0), (0.0, 1.0), self.LOCAL, {}) is None

    def test_downstream_walk_excludes_new_nodes(self):
        a, b, c = _lop("/stage/b"), _lop("/stage/c"), _lop("/stage/new")
        for node, pos in ((a, (0, 1)), (b, (0, 0)), (c, (0, -1))):
            node.position.return_value = pos
        a.outputs.return_value = (b, c)
        b.outputs.return_value = ()
        c.outputs.return_value = ()
        assert graph_mod._downstream_positions(a, {"/stage/new"}) == {
            "/stage/b": (0, 1), "/stage/c": (0, 0)}

    def test_handler_flag_validated_and_receipt_lists_shifts(self, monkeypatch):
        from synapse.core.errors import SynapseUserError
        monkeypatch.setattr(graph_mod, "HOU_AVAILABLE", True)
        handler = type("H", (graph_mod.SolarisGraphMixin,), {})()
        with pytest.raises(SynapseUserError, match="splice_layout"):
            handler._handle_solaris_build_graph(
                {"nodes": [{"id": "a", "type": "null"}], "connections": [], "splice_layout": "below"})
        src = open(graph_mod.__file__, encoding="utf-8").read()
        assert '"shifted": shifted' in src and '"splice_layout": splice_applied' in src
        assert 'payload.get("splice_layout", "inline")' in src


# ── Round 2 P1: a blind model never sees the capture tool ───────────────


def test_build_reply_rule_in_prompt():
    from synapse.panel import system_prompt
    g = system_prompt._TOOL_GUIDANCE
    assert "**Build replies:**" in g
    assert "at most one short closing sentence; never drop it" in g
    assert "not done or not verified" in g
