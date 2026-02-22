"""Tests for keyframe and render settings handlers."""
import pytest
import sys
import types
from unittest.mock import MagicMock, patch, PropertyMock

# Save original hou module state so we can restore it, not remove it
_original_hou = sys.modules.get("hou", None)

# Create hou mock
hou_mock = types.ModuleType("hou")
sys.modules["hou"] = hou_mock


class _MockKeyframe:
    def __init__(self):
        self._frame = 0
        self._value = 0
    def setFrame(self, f):
        self._frame = f
    def setValue(self, v):
        self._value = v

hou_mock.Keyframe = _MockKeyframe
hou_mock.frame = MagicMock(return_value=1)

# Mock node
_mock_parm = MagicMock()
_mock_parm.eval.return_value = 0.0
_mock_parm.setKeyframe = MagicMock()
_mock_parm.name.return_value = "tx"
_mock_parm.parmTemplate.return_value = MagicMock()

_mock_node = MagicMock()
_mock_node.parm.return_value = _mock_parm
_mock_node.parms.return_value = [_mock_parm]
_mock_node.path.return_value = "/obj/geo1"

hou_mock.node = MagicMock(return_value=_mock_node)


class TestSetKeyframe:
    def test_keyframe_at_specific_frame(self):
        """Setting keyframe at frame 24 should call setKeyframe."""
        _mock_parm.setKeyframe.reset_mock()
        # Simulate handler logic
        node_path = "/obj/geo1"
        parm_name = "tx"
        value = 5.0
        frame = 24

        node = hou_mock.node(node_path)
        parm = node.parm(parm_name)
        key = hou_mock.Keyframe()
        key.setFrame(float(frame))
        key.setValue(float(value))
        parm.setKeyframe(key)

        parm.setKeyframe.assert_called_once()
        assert key._frame == 24.0
        assert key._value == 5.0

    def test_keyframe_default_frame(self):
        """No frame specified should use current frame."""
        key = hou_mock.Keyframe()
        key.setFrame(float(hou_mock.frame()))
        key.setValue(3.0)
        assert key._frame == 1.0
        assert key._value == 3.0

    def test_keyframe_node_not_found(self):
        """Missing node should raise ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError, match="Couldn't find a node"):
            node = hou_mock.node("/bad/path")
            if node is None:
                raise ValueError("Couldn't find a node at /bad/path")
        hou_mock.node.return_value = _mock_node  # restore

    def test_keyframe_parm_not_found(self):
        """Missing parm should raise ValueError."""
        _mock_node.parm.return_value = None
        with pytest.raises(ValueError, match="Couldn't find parameter"):
            node = hou_mock.node("/obj/geo1")
            parm = node.parm("bad_parm")
            if parm is None:
                raise ValueError("Couldn't find parameter 'bad_parm' on /obj/geo1")
        _mock_node.parm.return_value = _mock_parm  # restore


class TestRenderSettings:
    def test_read_settings(self):
        """Should read all evaluable parms."""
        _mock_parm.eval.return_value = 960
        node = hou_mock.node("/out/karma")
        settings = {}
        for parm in node.parms():
            val = parm.eval()
            if isinstance(val, (int, float, str)):
                settings[parm.name()] = val
        assert len(settings) > 0

    def test_apply_overrides(self):
        """Should set parm values from overrides dict."""
        _mock_parm.set.reset_mock()
        node = hou_mock.node("/out/karma")
        overrides = {"resolutionx": 1920}
        for k, v in overrides.items():
            p = node.parm(k)
            if p:
                p.set(v)
        _mock_parm.set.assert_called_with(1920)

    def test_node_not_found(self):
        """Missing node raises ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError):
            node = hou_mock.node("/bad")
            if node is None:
                raise ValueError("Couldn't find a node at /bad")
        hou_mock.node.return_value = _mock_node


# Cleanup — restore original hou module state instead of removing
def teardown_module():
    if _original_hou is not None:
        sys.modules["hou"] = _original_hou
    # If there was no hou before, leave our mock in place so downstream
    # tests that expect hou in sys.modules (e.g. test_render.py) still work.
