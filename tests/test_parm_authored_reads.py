"""BP12 item 15, found live on 2026-09-29 in Houdini 22.0.400.

Parameter reads returned only the evaluated value. Claude Code wrote Karma's
output picture as $HIP/render/$HIPNAME.$OS.$F4.exr, read back the expanded
path, and reported a successful write as failed. Reads now carry the string as
written (``raw``) when it differs, and get_parm the expression that drives a
keyframed parm. The fake parms raise the way Houdini 22.0.400 does (hython
probe), with the error class parm_authored actually catches.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.server import parm_authored  # noqa: E402
from synapse.server.parm_authored import (  # noqa: E402
    authored_fields, authored_tuple_fields, raw_string)

_FAILED = parm_authored._OPERATION_FAILED
AUTHORED = "$HIP/render/$HIPNAME.$OS.$F4.exr"
EXPANDED = "C:/shots/render/untitled.preview_settings.0001.exr"


class _Parm:
    def __init__(self, value, unexpanded=None, expression=None, string=True):
        self._value = value
        self._unexpanded = value if unexpanded is None else unexpanded
        self._expression = expression
        self._string = string

    def eval(self):
        return self._value

    def keyframes(self):
        return (object(),) if self._expression else ()

    def unexpandedString(self):
        if not self._string:
            raise _FAILED("Only string parms have unexpanded strings")
        if self._expression:
            raise _FAILED("Cannot get unexpanded string for parms with keyframes")
        return self._unexpanded

    def expression(self):
        if not self._expression:
            raise _FAILED("Parameter is not animated")
        return self._expression

    def expressionLanguage(self):
        return "exprLanguage.Hscript"


def _picture():
    return _Parm(EXPANDED, unexpanded=AUTHORED)


def test_string_with_variables_returns_raw():
    assert authored_fields(_picture(), EXPANDED) == {"raw": AUTHORED}
    assert raw_string(_picture(), EXPANDED) == AUTHORED


def test_plain_and_menu_strings_add_nothing():
    assert authored_fields(_Parm("xpu"), "xpu") == {}
    assert authored_fields(_Parm("/cameras/lookdev_xpu"), "/cameras/lookdev_xpu") == {}


def test_non_string_parm_adds_nothing():
    assert authored_fields(_Parm(1280, string=False), 1280) == {}


def test_keyframed_parm_returns_its_expression():
    tx = _Parm(2.0, expression="$F * 2", string=False)
    assert authored_fields(tx, 2.0) == {
        "expression": "$F * 2", "expression_language": "exprLanguage.Hscript"}
    assert raw_string(tx, 2.0) is None


def test_mock_parm_adds_nothing():
    assert authored_fields(MagicMock(), 1) == {}
    assert raw_string(MagicMock(), 1) is None


def test_tuple_reports_per_component():
    parms = [_Parm("a"), _picture()]
    values = [p.eval() for p in parms]
    assert authored_tuple_fields(parms, values) == {"raw": [None, AUTHORED]}
    assert authored_tuple_fields([_Parm("a")], ["a"]) == {}


def test_get_parm_handler_returns_raw(monkeypatch):
    from synapse.server import handlers

    node = SimpleNamespace(parm=lambda name: _picture() if name == "picture" else None,
                           parmTuple=lambda name: None)
    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True)
    monkeypatch.setattr(handlers.hou, "node", lambda path: node, raising=False)
    out = handlers.SynapseHandler._handle_get_parm(
        None, {"node": "/stage/lookdev_xpu/preview_settings", "parm": "picture"})
    assert out["value"] == EXPANDED
    assert out["raw"] == AUTHORED
    assert out["is_tuple"] is False
