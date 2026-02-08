"""Tests for the houdini_render handler (18th MCP tool).

Mock-based — no Houdini required.
"""

import importlib.util
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini
# ---------------------------------------------------------------------------

# Minimal hou stub — use existing if already in sys.modules (from other test files)
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")

# Import handlers via importlib to bypass package __init__
_handlers_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "handlers.py"
_proto_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "protocol.py"
_aliases_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "aliases.py"

for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _proto_path),
    ("synapse.core.aliases", _aliases_path),
    ("synapse.server.handlers", _handlers_path),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


# ---------------------------------------------------------------------------
# Tests: _find_render_rop
# ---------------------------------------------------------------------------

class TestFindRenderRop:
    def test_finds_karma_in_stage(self):
        karma_node = MagicMock()
        karma_node.type.return_value.name.return_value = "karma"

        stage_parent = MagicMock()
        stage_parent.children.return_value = [karma_node]

        with patch.object(sys.modules["hou"], "node", create=True, side_effect=lambda p: stage_parent if p == "/stage" else None):
            result = handlers_mod._find_render_rop()
            assert result is karma_node

    def test_finds_mantra_in_out(self):
        mantra_node = MagicMock()
        mantra_node.type.return_value.name.return_value = "ifd"

        out_parent = MagicMock()
        out_parent.children.return_value = [mantra_node]

        def _node(p):
            if p == "/stage":
                m = MagicMock()
                m.children.return_value = []
                return m
            if p == "/out":
                return out_parent
            return None

        with patch.object(sys.modules["hou"], "node", create=True, side_effect=_node):
            result = handlers_mod._find_render_rop()
            assert result is mantra_node

    def test_raises_when_no_rop(self):
        empty = MagicMock()
        empty.children.return_value = []

        with patch.object(sys.modules["hou"], "node", create=True, side_effect=lambda p: empty if p in ("/stage", "/out") else None):
            with pytest.raises(ValueError, match="No render ROP found"):
                handlers_mod._find_render_rop()


# ---------------------------------------------------------------------------
# Tests: _detect_karma_engine
# ---------------------------------------------------------------------------

class TestDetectKarmaEngine:
    def test_mantra(self):
        assert handlers_mod._detect_karma_engine(MagicMock(), "ifd") == "mantra"

    def test_opengl(self):
        assert handlers_mod._detect_karma_engine(MagicMock(), "opengl") == "opengl"

    def test_karma_xpu(self):
        node = MagicMock()
        parm = MagicMock()
        parm.eval.return_value = "XPU"
        node.parm.side_effect = lambda n: parm if n == "renderer" else None
        assert handlers_mod._detect_karma_engine(node, "karma") == "karma_xpu"

    def test_karma_cpu(self):
        node = MagicMock()
        parm = MagicMock()
        parm.eval.return_value = "CPU"
        node.parm.side_effect = lambda n: parm if n == "renderer" else None
        assert handlers_mod._detect_karma_engine(node, "karma") == "karma_cpu"

    def test_karma_unknown_parm(self):
        node = MagicMock()
        node.parm.return_value = None
        assert handlers_mod._detect_karma_engine(node, "karma") == "karma"

    def test_usdrender_rop_xpu(self):
        node = MagicMock()
        parm = MagicMock()
        parm.eval.return_value = "xpu"
        node.parm.side_effect = lambda n: parm if n == "karmarenderertype" else None
        assert handlers_mod._detect_karma_engine(node, "usdrender_rop") == "karma_xpu"


# ---------------------------------------------------------------------------
# Tests: _handle_render
# ---------------------------------------------------------------------------

class TestHandleRender:
    """Test _handle_render by mocking hdefereval to skip main-thread dispatch."""

    def _mock_hdefereval_and_run(self, handler, payload, fake_node, frame=1.0):
        """Helper: mock hdefereval + hou + pathlib so _handle_render runs."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn: fn()

        hou = sys.modules["hou"]
        # Ensure parm() returns a mock for outputimage/picture so the handler
        # can set the output path on the node (no longer uses output_file kwarg)
        if fake_node.parm.return_value is None:
            out_parm = MagicMock()
            loppath_parm = None
            orig_side_effect = fake_node.parm.side_effect
            def _parm(n):
                if n in ("outputimage", "picture"):
                    return out_parm
                if n == "loppath":
                    return loppath_parm
                if orig_side_effect:
                    return orig_side_effect(n)
                return None
            fake_node.parm.side_effect = _parm

        with patch.object(hou, "node", return_value=fake_node, create=True), \
             patch.object(hou, "frame", return_value=frame, create=True), \
             patch.object(hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)):
            return handler._handle_render(payload)

    def test_returns_image_path_and_engine(self, handler):
        """Handler returns dict with image_path, format, engine keys."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"
        fake_node.parm.return_value = None

        result = self._mock_hdefereval_and_run(handler, {"node": "/stage/karma1"}, fake_node, frame=1.0)

        assert "image_path" in result
        assert result["format"] == "jpeg"
        assert result["engine"] == "karma"
        assert result["rop"] == "/stage/karma1"

    def test_frame_defaults_to_current(self, handler):
        """When frame is not specified, uses hou.frame()."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"
        fake_node.parm.return_value = None

        self._mock_hdefereval_and_run(handler, {"node": "/stage/karma1"}, fake_node, frame=42.0)

        call_kwargs = fake_node.render.call_args
        assert call_kwargs is not None
        assert call_kwargs[1]["frame_range"] == (42, 42)

    def test_resolution_override(self, handler):
        """Width/height override sets resolutionx/resolutiony parms."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"
        resx_parm = MagicMock()
        resy_parm = MagicMock()
        out_parm = MagicMock()
        override_parm = MagicMock()
        override_parm.eval.return_value = ""
        fake_node.parm.side_effect = lambda n: {
            "resolutionx": resx_parm,
            "resolutiony": resy_parm,
            "outputimage": out_parm,
            "override_res": override_parm,
        }.get(n)

        self._mock_hdefereval_and_run(
            handler, {"node": "/stage/karma1", "width": 1920, "height": 1080}, fake_node
        )

        resx_parm.set.assert_called_once_with(1920)
        resy_parm.set.assert_called_once_with(1080)


# ---------------------------------------------------------------------------
# Tests: aliases
# ---------------------------------------------------------------------------

class TestRenderAliases:
    def test_frame_alias(self):
        aliases_mod = sys.modules["synapse.core.aliases"]
        assert "frame" in aliases_mod.PARAM_ALIASES
        assert "frame_number" in aliases_mod.PARAM_ALIASES["frame"]
