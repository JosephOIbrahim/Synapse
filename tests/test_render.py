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
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]

# Ensure executeDeferred runs immediately (needed by run_on_main)
if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

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

# Get the hou module that handlers.py actually imported — may differ from
# sys.modules["hou"] if earlier test files replaced it without restoring.
_handlers_hou = handlers_mod.hou


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

        with patch.object(_handlers_hou, "node", create=True, side_effect=lambda p: stage_parent if p == "/stage" else None):
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

        with patch.object(_handlers_hou, "node", create=True, side_effect=_node):
            result = handlers_mod._find_render_rop()
            assert result is mantra_node

    def test_raises_when_no_rop(self):
        empty = MagicMock()
        empty.children.return_value = []

        with patch.object(_handlers_hou, "node", create=True, side_effect=lambda p: empty if p in ("/stage", "/out") else None):
            with pytest.raises(ValueError, match="Couldn't auto-find a render ROP"):
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
        hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)

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

        with patch.object(_handlers_hou, "node", return_value=fake_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=frame, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
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

    def test_flipbook_fallback_on_usdrender_no_output(self, handler):
        """When usdrender ROP produces no output, fall back to flipbook."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/usdrender_rop1"
        fake_node.type.return_value.name.return_value = "usdrender_rop"

        out_parm = MagicMock()
        fake_node.parm.side_effect = lambda n: out_parm if n in ("outputimage", "picture") else None

        # Track how many times Path.exists is called to simulate:
        # - node.render() output poll: always False (60 iterations)
        # - flipbook output check: True
        call_count = {"n": 0}

        def _fake_exists(self_path):
            call_count["n"] += 1
            # First 60 calls are the render poll loop — all fail
            if call_count["n"] <= 60:
                return False
            # After that, flipbook output exists
            return True

        # Mock the Scene Viewer for flipbook
        mock_vp = MagicMock()
        mock_fb_settings = MagicMock()
        mock_sv = MagicMock()
        mock_sv.curViewport.return_value = mock_vp
        mock_sv.flipbookSettings.return_value = mock_fb_settings
        mock_desktop = MagicMock()
        mock_desktop.paneTabOfType.return_value = mock_sv

        with patch.object(_handlers_hou, "node", return_value=fake_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=1.0, create=True), \
             patch.object(_handlers_hou, "setFrame", create=True), \
             patch.object(_handlers_hou, "ui", MagicMock(curDesktop=MagicMock(return_value=mock_desktop)), create=True), \
             patch.object(_handlers_hou, "paneTabType", MagicMock(SceneViewer="SceneViewer"), create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", _fake_exists), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=2048)), \
             patch("time.sleep"):
            result = handler._handle_render({"node": "/stage/usdrender_rop1"})

        assert result["flipbook_fallback"] is True
        assert result["rop_type"] == "usdrender_rop"
        mock_sv.flipbook.assert_called_once()

    def test_no_flipbook_fallback_for_non_usdrender(self, handler):
        """Non-usdrender ROPs raise RuntimeError without attempting flipbook."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        fake_node = MagicMock()
        fake_node.path.return_value = "/out/mantra1"
        fake_node.type.return_value.name.return_value = "ifd"

        out_parm = MagicMock()
        fake_node.parm.side_effect = lambda n: out_parm if n in ("outputimage", "picture") else None

        with patch.object(_handlers_hou, "node", return_value=fake_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=1.0, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=0)), \
             patch("time.sleep"):
            with pytest.raises(RuntimeError, match="output wasn't created"):
                handler._handle_render({"node": "/out/mantra1"})


# ---------------------------------------------------------------------------
# Tests: BL-007 — EXR persistence and pre-render validation
# ---------------------------------------------------------------------------

class TestRenderEXRPersistence:
    """Tests for BL-007: render should write EXR to disk, not just JPEG preview."""

    def _setup_render(self, handler, fake_node, payload, frame=1.0,
                      exists_pattern=None, artist_output=""):
        """Helper to run _handle_render with controlled mocks."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        out_parm = MagicMock()
        out_parm.eval.return_value = artist_output
        loppath_parm = MagicMock()
        loppath_parm.eval.return_value = ""

        def _parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            if n == "loppath":
                return loppath_parm
            return None

        fake_node.parm.side_effect = _parm

        if exists_pattern is None:
            exists_fn = lambda self_path: True
        else:
            exists_fn = exists_pattern

        with patch.object(_handlers_hou, "node", return_value=fake_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=frame, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", exists_fn), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
             patch("pathlib.Path.mkdir", return_value=None):
            return handler._handle_render(payload)

    def test_default_exr_when_no_artist_output(self, handler):
        """When no artist output path is configured, default to EXR (not JPEG)."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"

        result = self._setup_render(
            handler, fake_node, {"node": "/stage/karma1"}, artist_output=""
        )

        # output_file should be reported in the result
        assert "output_file" in result
        assert result["output_file"].endswith(".exr")

    def test_artist_exr_path_preserved(self, handler):
        """When artist has configured an EXR output path, it's used and reported."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"

        result = self._setup_render(
            handler, fake_node, {"node": "/stage/karma1"},
            artist_output="/renders/beauty/shot.0001.exr"
        )

        assert "output_file" in result
        assert result["output_file"] == "/renders/beauty/shot.0001.exr"

    def test_output_parm_set_even_without_initial_parm(self, handler):
        """Handler sets outputimage/picture parm even if it wasn't initially configured."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"

        out_parm = MagicMock()
        out_parm.eval.return_value = ""
        # No loppath parm on Karma LOP nodes in /stage
        def _parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            return None  # No loppath, no other parms

        fake_node.parm.side_effect = _parm

        with patch.object(_handlers_hou, "node", return_value=fake_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=1.0, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
             patch("pathlib.Path.mkdir", return_value=None):
            handler._handle_render({"node": "/stage/karma1"})

        # The output parm should have been set to an EXR path
        out_parm.set.assert_called()
        set_path = out_parm.set.call_args[0][0]
        assert ".exr" in set_path

    def test_upstream_karma_lop_picture_discovered(self, handler):
        """Handler discovers picture parm from upstream Karma LOP when ROP has none."""
        import hdefereval
        hdefereval.executeInMainThreadWithResult = lambda fn, *a, **kw: fn(*a, **kw)

        fake_node = MagicMock()
        fake_node.path.return_value = "/out/usdrender1"
        fake_node.type.return_value.name.return_value = "usdrender"

        # ROP has empty outputimage
        out_parm = MagicMock()
        out_parm.eval.return_value = ""

        # loppath points to a Karma LOP that has a picture parm
        loppath_parm = MagicMock()
        loppath_parm.eval.return_value = "/stage/karma1"

        karma_lop = MagicMock()
        karma_picture = MagicMock()
        karma_picture.eval.return_value = "/renders/shot_beauty.$F4.exr"
        karma_lop.parm.side_effect = lambda n: karma_picture if n == "picture" else None
        karma_lop.inputs.return_value = []

        def _parm(n):
            if n in ("outputimage", "picture"):
                return out_parm
            if n == "loppath":
                return loppath_parm
            if n == "override_res":
                return None
            return None

        fake_node.parm.side_effect = _parm

        def _hou_node(p):
            if p == "/out/usdrender1":
                return fake_node
            if p == "/stage/karma1":
                return karma_lop
            return None

        with patch.object(_handlers_hou, "node", side_effect=_hou_node, create=True), \
             patch.object(_handlers_hou, "frame", return_value=1.0, create=True), \
             patch.object(_handlers_hou, "text", MagicMock(expandString=MagicMock(return_value="/tmp/houdini_temp")), create=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
             patch("pathlib.Path.mkdir", return_value=None):
            result = handler._handle_render({"node": "/out/usdrender1"})

        # Should have used the Karma LOP's picture path
        assert "output_file" in result
        assert "shot_beauty" in result["output_file"]

    def test_frame_token_resolved_in_output(self, handler):
        """$F4 frame tokens are resolved to actual frame number in output_file."""
        fake_node = MagicMock()
        fake_node.path.return_value = "/stage/karma1"
        fake_node.type.return_value.name.return_value = "karma"

        result = self._setup_render(
            handler, fake_node, {"node": "/stage/karma1", "frame": 42},
            artist_output="/renders/shot.$F4.exr", frame=42.0
        )

        assert "output_file" in result
        assert "0042" in result["output_file"]
        assert "$F4" not in result["output_file"]


# ---------------------------------------------------------------------------
# Tests: aliases
# ---------------------------------------------------------------------------

class TestConfigureRenderPasses:
    """Tests for _handle_configure_render_passes."""

    def _setup_lop_mock(self, handler):
        """Set up a mock LOP node and parent for render passes."""
        lop_node = MagicMock()
        lop_node.path.return_value = "/stage/render_settings"
        parent = MagicMock()
        lop_node.parent.return_value = parent

        py_lop = MagicMock()
        py_lop.path.return_value = "/stage/render_passes"
        parent.createNode.return_value = py_lop

        handler._resolve_lop_node = MagicMock(return_value=lop_node)
        return lop_node, parent, py_lop

    def test_preset_passes_created(self, handler):
        """Preset pass names resolve to correct source_name and data_type."""
        _, parent, py_lop = self._setup_lop_mock(handler)

        result = handler._handle_configure_render_passes({
            "passes": ["beauty", "normal", "depth"],
        })

        assert result["pass_count"] == 3
        names = [p["name"] for p in result["passes"]]
        assert "beauty" in names
        assert "normal" in names
        assert "depth" in names

        # Verify correct source names
        by_name = {p["name"]: p for p in result["passes"]}
        assert by_name["beauty"]["source_name"] == "C"
        assert by_name["beauty"]["data_type"] == "color4f"
        assert by_name["normal"]["source_name"] == "N"
        assert by_name["normal"]["data_type"] == "normal3f"
        assert by_name["depth"]["source_name"] == "Z"
        assert by_name["depth"]["data_type"] == "float"

    def test_comma_separated_string(self, handler):
        """Passes can be a comma-separated string."""
        self._setup_lop_mock(handler)

        result = handler._handle_configure_render_passes({
            "passes": "beauty, diffuse, specular",
        })

        assert result["pass_count"] == 3
        names = [p["name"] for p in result["passes"]]
        assert "beauty" in names
        assert "diffuse" in names
        assert "specular" in names

    def test_custom_pass_dict(self, handler):
        """Custom pass with explicit source_name and data_type."""
        self._setup_lop_mock(handler)

        result = handler._handle_configure_render_passes({
            "passes": [
                {"name": "my_aov", "source_name": "custom_lpe", "data_type": "color4f"},
            ],
        })

        assert result["pass_count"] == 1
        p = result["passes"][0]
        assert p["name"] == "my_aov"
        assert p["source_name"] == "custom_lpe"
        assert p["data_type"] == "color4f"
        assert p["prim_path"] == "/Render/rendersettings/my_aov"

    def test_python_lop_created_and_wired(self, handler):
        """A pythonscript LOP is created, wired to input, and has code set."""
        lop_node, parent, py_lop = self._setup_lop_mock(handler)

        handler._handle_configure_render_passes({
            "passes": ["beauty"],
        })

        parent.createNode.assert_called_once_with("pythonscript", "render_passes")
        py_lop.setInput.assert_called_once_with(0, lop_node)
        py_lop.moveToGoodPosition.assert_called_once()

        # Verify python code was set
        py_lop.parm.assert_called_with("python")
        code_set_call = py_lop.parm.return_value.set
        code_set_call.assert_called_once()
        code = code_set_call.call_args[0][0]
        assert "UsdRender.Var.Define" in code
        assert "'/Render/rendersettings/beauty'" in code

    def test_clear_existing_flag(self, handler):
        """clear_existing=True adds stage cleanup code."""
        _, _, py_lop = self._setup_lop_mock(handler)

        handler._handle_configure_render_passes({
            "passes": ["beauty"],
            "clear_existing": True,
        })

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "Clear existing render vars" in code
        assert "RemovePrim" in code

    def test_clear_existing_false_omits_cleanup(self, handler):
        """clear_existing=False (default) does not add cleanup code."""
        _, _, py_lop = self._setup_lop_mock(handler)

        handler._handle_configure_render_passes({
            "passes": ["beauty"],
        })

        code = py_lop.parm.return_value.set.call_args[0][0]
        assert "RemovePrim" not in code
        assert result_check(handler._handle_configure_render_passes({
            "passes": ["beauty"],
        }), "clear_existing", False)

    def test_unknown_pass_treated_as_custom(self, handler):
        """An unknown pass name is treated as custom with color3f default."""
        self._setup_lop_mock(handler)

        result = handler._handle_configure_render_passes({
            "passes": ["my_fancy_pass"],
        })

        assert result["pass_count"] == 1
        p = result["passes"][0]
        assert p["name"] == "my_fancy_pass"
        assert p["source_name"] == "my_fancy_pass"
        assert p["data_type"] == "color3f"

    def test_invalid_passes_type_raises(self, handler):
        """Non-list, non-string passes raises ValueError."""
        self._setup_lop_mock(handler)

        with pytest.raises(ValueError, match="passes should be a list"):
            handler._handle_configure_render_passes({
                "passes": 42,
            })

    def test_cryptomatte_presets(self, handler):
        """Cryptomatte presets resolve correctly."""
        self._setup_lop_mock(handler)

        result = handler._handle_configure_render_passes({
            "passes": ["crypto_material", "crypto_object", "crypto_asset"],
        })

        assert result["pass_count"] == 3
        by_name = {p["name"]: p for p in result["passes"]}
        assert by_name["crypto_material"]["source_name"] == "crypto_material"
        assert by_name["crypto_material"]["data_type"] == "color4f"
        assert by_name["crypto_object"]["source_name"] == "crypto_object"
        assert by_name["crypto_asset"]["source_name"] == "crypto_asset"


def result_check(result, key, expected):
    """Utility to check a result dict key matches expected value."""
    return result.get(key) == expected


class TestRenderAliases:
    def test_frame_alias(self):
        aliases_mod = sys.modules["synapse.core.aliases"]
        assert "frame" in aliases_mod.PARAM_ALIASES
        assert "frame_number" in aliases_mod.PARAM_ALIASES["frame"]
