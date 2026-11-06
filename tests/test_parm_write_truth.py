"""H1-1 / L3-M2: a parameter write reports what the parm holds, not what was asked.

set_parm used to echo the request. Over an expression the render did not
change, over keys it inserted one, and over a channel reference it wrote a
different node and never named it. A clamped parm reported the request beside a
value the scene never held.

The parms here are fakes, built to the behaviour the review probed: keyframes
on an animated parm, getReferencedParm returning the driving parm, and a set
that can clamp. Nothing here needs Houdini.
"""
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.server.parm_authored import (  # noqa: E402
    ParmWriteRefused,
    author_parm_write,
    keyframe_count,
    reference_source,
)


class _Parm:
    """A parm that behaves the way the H22 probe showed."""

    def __init__(self, value, keys=0, source=None, clamp=None, name="tx"):
        self._value = value
        self._keys = keys
        self._source = source
        self._clamp = clamp
        self._name = name
        self.writes = []

    def name(self):
        return self._name

    def keyframes(self):
        return tuple(range(self._keys))

    def getReferencedParm(self):
        return self._source if self._source is not None else self

    def eval(self):
        return self._value

    def set(self, value, follow_parm_reference=True):
        if follow_parm_reference and self._source is not None:
            return self._source.set(value, follow_parm_reference=False)
        self.writes.append(value)
        if self._keys:
            self._keys += 1          # a plain set on a keyed parm adds a key
        self._value = self._clamp(value) if self._clamp else value

    def deleteAllKeyframes(self):
        self._keys = 0

    def node(self):
        return SimpleNamespace(path=lambda: "/obj/light1")


# ---------------------------------------------------------------------------
# The five probe cases
# ---------------------------------------------------------------------------

def test_expression_parm_is_refused_by_default():
    """An animated parm is not silently given another key."""
    parm = _Parm(2.0, keys=2)

    with pytest.raises(ParmWriteRefused) as exc:
        author_parm_write([parm], [5.0])

    assert "2 keyframe" in str(exc.value)
    assert parm.eval() == 2.0
    assert parm.writes == []
    assert keyframe_count(parm) == 2


def test_replace_clears_the_keys_and_reads_back():
    parm = _Parm(2.0, keys=2)

    out = author_parm_write([parm], [5.0], mode="replace")

    assert parm.eval() == 5.0
    assert keyframe_count(parm) == 0
    assert out["value"] == 5.0
    assert out["observed"] == 5.0
    assert out["mismatch"] is False


def test_key_at_frame_adds_a_key_and_reports_it():
    parm = _Parm(2.0, keys=2)

    out = author_parm_write([parm], [5.0], mode="key_at_frame")

    assert parm.eval() == 5.0
    assert keyframe_count(parm) == 3
    assert out["authored"]["keyframe_count"] == [3]


def test_referenced_parm_is_refused_and_write_source_writes_the_source():
    """A channel reference is named, not followed into another node."""
    source = _Parm(1.0, name="intensity")
    driven = _Parm(1.0, source=source, name="ch('intensity')")

    with pytest.raises(ParmWriteRefused) as exc:
        author_parm_write([driven], [4.0])
    assert "driven by" in str(exc.value)
    assert source.eval() == 1.0

    out = author_parm_write([driven], [4.0], mode="write_source")

    assert source.eval() == 4.0
    assert out["observed"] == 4.0
    assert "intensity" in out["authored"]["wrote"][0]


def test_clamped_write_reports_observed_beside_the_request():
    parm = _Parm(1.0, clamp=lambda v: min(1.0, v))

    out = author_parm_write([parm], [5.0])

    assert out["value"] == 5.0
    assert out["observed"] == 1.0
    assert out["mismatch"] is True


def test_plain_write_matches():
    parm = _Parm(0.0)

    out = author_parm_write([parm], [2.0], mode="refuse")

    assert out["observed"] == 2.0
    assert out["mismatch"] is False
    assert reference_source(parm) is None


def test_tuple_write_is_all_or_none():
    """One animated component refuses the whole tuple before anything is written."""
    first, second = _Parm(1.0, name="colorr"), _Parm(1.0, keys=1, name="colorg")

    with pytest.raises(ParmWriteRefused):
        author_parm_write([first, second], [0.5, 0.5])

    assert first.writes == []
    assert second.writes == []


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        author_parm_write([_Parm(1.0)], [2.0], mode="yolo")


# ---------------------------------------------------------------------------
# The handler reply carries the observation
# ---------------------------------------------------------------------------

@contextmanager
def _group(_name):
    yield


def test_set_parm_reply_carries_observed(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(1.0, clamp=lambda v: min(1.0, v))
    node = SimpleNamespace(parm=lambda name: parm if name == "intensity" else None,
                           parmTuple=lambda name: None)
    fake_hou = SimpleNamespace(
        node=lambda path: node,
        undos=SimpleNamespace(group=_group),
    )

    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True)
    monkeypatch.setattr(handlers, "hou", fake_hou)

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/light1", "parm": "intensity", "value": 5.0})

    assert out["value"] == 5.0
    assert out["observed"] == 1.0
    assert out["mismatch"] is True
    assert out["authored"]["mode"] == "refuse"


def test_set_parm_refuses_a_keyed_parm_without_writing(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(2.0, keys=2)
    node = SimpleNamespace(parm=lambda name: parm, parmTuple=lambda name: None)
    fake_hou = SimpleNamespace(node=lambda path: node,
                               undos=SimpleNamespace(group=_group))

    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True)
    monkeypatch.setattr(handlers, "hou", fake_hou)

    with pytest.raises(ParmWriteRefused):
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/light1", "parm": "tx", "value": 5.0})

    assert parm.writes == []
    assert keyframe_count(parm) == 2
