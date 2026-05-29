"""Tests for FORGE cluster HANDS_USD additions to handlers_usd.py.

Covers:
  - Pure-function _karma_visibility_pythonscript codegen (NO hou).
  - _coerce_bool string/bool coercion (NO hou).
  - Handler-level checks for reference_usd (karma_visible), modify_usd_prim
    (instanceable), set_payload_loadstate, create_point_instancer, and the
    shot_render_ready composite orchestrator.

Bootstrap mirrors tests/test_render.py: a hou/hdefereval stub is injected
into sys.modules and handlers are loaded via importlib bypassing the package
__init__. Pure-function tests do not touch hou at all.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini (mirrors test_render.py)
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    _hou.undos = MagicMock()
    # OperationFailed must be a real exception class for except clauses.
    _hou.OperationFailed = type("OperationFailed", (Exception,), {})
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]
    if not hasattr(_hou, "undos"):
        _hou.undos = MagicMock()
    if not hasattr(_hou, "OperationFailed"):
        _hou.OperationFailed = type("OperationFailed", (Exception,), {})

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]

if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

_root = Path(__file__).resolve().parent.parent / "python" / "synapse"
_handlers_path = _root / "server" / "handlers.py"
_proto_path = _root / "core" / "protocol.py"
_aliases_path = _root / "core" / "aliases.py"
_usd_path = _root / "server" / "handlers_usd.py"

for mod_name, mod_path in [
    ("synapse", _root),
    ("synapse.core", _root / "core"),
    ("synapse.server", _root / "server"),
    ("synapse.session", _root / "session"),
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
usd_mod = sys.modules["synapse.server.handlers_usd"]

_handlers_hou = handlers_mod.hou
if not hasattr(_handlers_hou, "undos"):
    _handlers_hou.undos = MagicMock()
if not hasattr(_handlers_hou, "OperationFailed"):
    _handlers_hou.OperationFailed = type("OperationFailed", (Exception,), {})

# The hou object that handlers_usd.py imported (may differ if a prior test
# replaced sys.modules["hou"]). Ensure it has the bits the handlers touch.
_usd_hou = usd_mod.hou
if _usd_hou is not None:
    if not hasattr(_usd_hou, "undos"):
        _usd_hou.undos = MagicMock()
    if not hasattr(_usd_hou, "OperationFailed"):
        _usd_hou.OperationFailed = type("OperationFailed", (Exception,), {})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


def _setup_lop_mock(handler):
    """Mock _resolve_lop_node -> LOP whose parent().createNode() -> py_lop."""
    lop_node = MagicMock()
    lop_node.path.return_value = "/stage/lop"
    parent = MagicMock()
    lop_node.parent.return_value = parent

    py_lop = MagicMock()
    py_lop.path.return_value = "/stage/py_lop"
    parent.createNode.return_value = py_lop

    handler._resolve_lop_node = MagicMock(return_value=lop_node)
    return lop_node, parent, py_lop


def _last_python_code(py_lop):
    """Extract the code string passed to py_lop.parm('python').set(code)."""
    return py_lop.parm.return_value.set.call_args[0][0]


# ===========================================================================
# (A) PURE-FUNCTION tests — _karma_visibility_pythonscript (NO hou)
# ===========================================================================

class TestKarmaVisibilityPythonscript:
    def test_returns_string_without_hou(self):
        # Must not raise / not import hou at call time.
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        assert isinstance(code, str)
        assert code  # non-empty

    def test_non_clobbering_guards_present(self):
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        # Purpose guarded by HasAuthoredValue, kind guarded by GetKind() truthiness.
        assert "HasAuthoredValue" in code
        assert "GetKind()" in code
        assert "if not" in code

    def test_purpose_default_value_and_api(self):
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        assert "GetPurposeAttr" in code
        assert "'default'" in code
        assert ".Set(" in code

    def test_kind_default_value_and_api(self):
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        assert "SetKind" in code
        assert "'component'" in code
        assert "ModelAPI" in code

    def test_default_prim_fallback_guarded(self):
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        assert "GetDefaultPrim" in code
        # Fallback is guarded on prim_path == '/'.
        assert "== '/'" in code

    def test_custom_values_reflected(self):
        code = usd_mod._karma_visibility_pythonscript(
            "/World/asset", purpose="render", kind="assembly"
        )
        assert "'render'" in code
        assert "'assembly'" in code
        assert "/World/asset" in code

    def test_editable_stage_used(self):
        code = usd_mod._karma_visibility_pythonscript("/World/asset")
        assert "editableStage" in code
        # pxr import lives INSIDE the emitted script, not at call time.
        assert "from pxr import" in code


# ===========================================================================
# (A) PURE-FUNCTION tests — _coerce_bool (NO hou)
# ===========================================================================

class TestCoerceBool:
    @pytest.mark.parametrize("token", ["false", "FALSE", "False", "0", "no",
                                       "NO", "off", "Off", " false ", ""])
    def test_falsey_strings(self, token):
        assert usd_mod._coerce_bool(token) is False

    @pytest.mark.parametrize("token", ["true", "True", "1", "yes", "on",
                                       "anything"])
    def test_truthy_strings(self, token):
        assert usd_mod._coerce_bool(token) is True

    def test_real_bools_passthrough(self):
        assert usd_mod._coerce_bool(True) is True
        assert usd_mod._coerce_bool(False) is False

    def test_none_uses_default(self):
        assert usd_mod._coerce_bool(None) is True
        assert usd_mod._coerce_bool(None, default=False) is False


# ===========================================================================
# (B) HANDLER-LEVEL tests
# ===========================================================================

class TestReferenceUsdKarmaVisible:
    def _setup_parent(self):
        """Mock hou.node(parent) -> parent_node; createNode returns ref + kv."""
        parent_node = MagicMock()

        ref_lop = MagicMock()
        ref_lop.path.return_value = "/stage/ref_import"

        kv_lop = MagicMock()
        kv_lop.path.return_value = "/stage/karma_visibility"

        # First createNode -> reference LOP, second -> karma_visibility LOP.
        parent_node.createNode.side_effect = [ref_lop, kv_lop]
        return parent_node, ref_lop, kv_lop

    def test_karma_visible_true_creates_second_lop(self, handler, monkeypatch):
        parent_node, ref_lop, kv_lop = self._setup_parent()
        monkeypatch.setattr(_usd_hou, "node", lambda p: parent_node)
        # Use a $HIP path so the on-disk isfile() check is short-circuited.

        result = handler._handle_reference_usd({
            "file": "$HIP/asset.usd",
            "mode": "reference",
            "prim_path": "/World/asset",
            "karma_visible": True,
        })

        # Two LOPs created: reference + karma_visibility.
        assert parent_node.createNode.call_count == 2
        assert "karma_visibility" in result
        assert result["karma_visibility"]["purpose"] == "default"
        assert result["karma_visibility"]["kind"] == "component"
        assert result["karma_visibility"]["policy"] == "non-clobbering"
        assert "advisory" not in result
        # The kv LOP got karma codegen wired off the ref LOP.
        kv_lop.setInput.assert_called_once_with(0, ref_lop)
        code = _last_python_code(kv_lop)
        assert "GetPurposeAttr" in code

    def test_karma_visible_string_false_keeps_advisory(self, handler, monkeypatch):
        parent_node, ref_lop, kv_lop = self._setup_parent()
        monkeypatch.setattr(_usd_hou, "node", lambda p: parent_node)

        result = handler._handle_reference_usd({
            "file": "$HIP/asset.usd",
            "mode": "reference",
            "prim_path": "/World/asset",
            "karma_visible": "false",
        })

        # Only the reference LOP created; no karma_visibility LOP.
        assert parent_node.createNode.call_count == 1
        assert "karma_visibility" not in result
        assert "advisory" in result

    def test_payload_mode_default_karma_visible(self, handler, monkeypatch):
        parent_node, ref_lop, kv_lop = self._setup_parent()
        monkeypatch.setattr(_usd_hou, "node", lambda p: parent_node)

        # No karma_visible key -> defaults True.
        result = handler._handle_reference_usd({
            "file": "$HIP/asset.usd",
            "mode": "payload",
            "prim_path": "/World/asset",
        })

        assert result["mode"] == "payload"
        assert "karma_visibility" in result

    def test_sublayer_mode_no_karma(self, handler, monkeypatch):
        parent_node = MagicMock()
        sub_lop = MagicMock()
        sub_lop.path.return_value = "/stage/sublayer_import"
        parent_node.createNode.return_value = sub_lop
        monkeypatch.setattr(_usd_hou, "node", lambda p: parent_node)

        result = handler._handle_reference_usd({
            "file": "$HIP/asset.usd",
            "mode": "sublayer",
        })

        assert "karma_visibility" not in result
        assert "advisory" not in result


class TestModifyUsdPrimInstanceable:
    def test_instanceable_codegen_and_mods(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)

        result = handler._handle_modify_usd_prim({
            "prim_path": "/World/asset",
            "instanceable": True,
        })

        assert result["modifications"]["instanceable"] is True
        code = _last_python_code(py_lop)
        assert "SetInstanceable(True)" in code

    def test_instanceable_false(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)

        handler._handle_modify_usd_prim({
            "prim_path": "/World/asset",
            "instanceable": False,
        })
        code = _last_python_code(py_lop)
        assert "SetInstanceable(False)" in code


class TestSetPayloadLoadstate:
    def test_unload_action(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)

        result = handler._handle_set_payload_loadstate({
            "prim_path": "/World/heavy",
            "action": "unload",
        })

        assert result["action"] == "unload"
        code = _last_python_code(py_lop)
        assert "stage.Unload" in code
        assert "Sdf.Path" in code

    def test_load_with_active(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)

        handler._handle_set_payload_loadstate({
            "prim_path": "/World/heavy",
            "action": "load",
            "active": True,
        })
        code = _last_python_code(py_lop)
        assert "stage.Load" in code
        assert "SetActive(True)" in code

    def test_requires_some_change(self, handler):
        _setup_lop_mock(handler)
        with pytest.raises(ValueError):
            handler._handle_set_payload_loadstate({"prim_path": "/World/heavy"})

    def test_rejects_bad_action(self, handler):
        _setup_lop_mock(handler)
        with pytest.raises(ValueError):
            handler._handle_set_payload_loadstate({
                "prim_path": "/World/heavy",
                "action": "purge",
            })


class TestCreatePointInstancer:
    def test_minimal_codegen(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)

        result = handler._handle_create_point_instancer({
            "prim_path": "/World/scatter",
            "prototypes": ["/World/proto/tree"],
            "positions": [[0, 0, 0], [1, 0, 1], [2, 0, 2]],
        })

        assert result["instance_count"] == 3
        assert result["prototypes"] == ["/World/proto/tree"]
        code = _last_python_code(py_lop)
        assert "PointInstancer" in code
        assert "ProtoIndices" in code or "protoIndices" in code
        assert "Positions" in code or "positions" in code
        # protoIndices defaults to zeros, one per position.
        assert "[0, 0, 0]" in code  # the IntArray of zeros

    def test_empty_prototypes_still_valid(self, handler):
        _, _, py_lop = _setup_lop_mock(handler)
        result = handler._handle_create_point_instancer({
            "prim_path": "/World/scatter",
        })
        assert result["instance_count"] == 0
        code = _last_python_code(py_lop)
        assert "PointInstancer" in code


class TestShotRenderReady:
    def test_orchestrates_in_order(self, handler):
        calls = []

        def _mat(payload):
            calls.append("material")
            return {"material_usd_path": "/stage/mat", "name": "m"}

        def _assemble(payload):
            calls.append("assemble")
            return {"chain": ["/stage/a", "/stage/b"]}

        def _render(payload):
            calls.append("render")
            return {"passed": True, "checks": []}

        handler._handle_create_textured_material = _mat
        handler._handle_solaris_assemble_chain = _assemble
        handler._handle_safe_render = _render

        result = handler._handle_shot_render_ready({
            "diffuse_map": "/tex/albedo.exr",
        })

        assert calls == ["material", "assemble", "render"]
        assert result["passed"] is True
        assert result["material_usd_path"] == "/stage/mat"
        step_names = [s["step"] for s in result["steps"]]
        assert step_names == [
            "create_textured_material", "solaris_assemble_chain", "safe_render"
        ]

    def test_step_error_captured_not_raised(self, handler):
        def _mat(payload):
            raise RuntimeError("material boom")

        handler._handle_create_textured_material = _mat
        handler._handle_solaris_assemble_chain = lambda p: {"chain": []}
        handler._handle_safe_render = lambda p: {"passed": True}

        result = handler._handle_shot_render_ready({})

        assert result["passed"] is False
        mat_step = result["steps"][0]
        assert mat_step["step"] == "create_textured_material"
        assert "material boom" in mat_step["error"]
        # Pipeline still produced a structured summary with all steps attempted.
        assert len(result["steps"]) == 3

    def test_safe_render_failed_marks_not_passed(self, handler):
        handler._handle_create_textured_material = lambda p: {"material_usd_path": "x"}
        handler._handle_solaris_assemble_chain = lambda p: {"chain": []}
        handler._handle_safe_render = lambda p: {"passed": False, "suggestion": "fix cam"}

        result = handler._handle_shot_render_ready({})
        assert result["passed"] is False

    def test_skip_render(self, handler):
        called = {"render": False}

        def _render(payload):
            called["render"] = True
            return {"passed": True}

        handler._handle_create_textured_material = lambda p: {"material_usd_path": "x"}
        handler._handle_solaris_assemble_chain = lambda p: {"chain": []}
        handler._handle_safe_render = _render

        result = handler._handle_shot_render_ready({"skip_render": True})
        assert called["render"] is False
        render_step = result["steps"][-1]
        assert render_step["result"]["skipped"] is True
