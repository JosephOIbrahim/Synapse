"""H1-1 / L3-M2: a parameter write reports what the parm holds, not what was asked.

set_parm used to echo the request. Over an expression the render did not change,
over keys it inserted one, and over a channel reference it wrote a different
node and never named it. A clamped parm reported the request beside a value the
scene never held.

The parms here follow what Houdini 22.0.400 actually does, probed in hython:

- getReferencedParm() returns an equal but distinct wrapper, even for a plain
  parm, so an identity check would call every parm a reference to itself;
- set(value) on a keyed parm adds a key at the current frame, while
  set(value, follow_parm_reference=False) clears the keys and writes a
  constant;
- expression() raises for a parm with more than one key;
- a tuple setter refuses a wrong-arity list with InvalidSize;
- captured Keyframe objects can be put back with setKeyframe after a failed
  write.
"""
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.server import parm_authored  # noqa: E402
from synapse.server.parm_authored import (  # noqa: E402
    ParmWriteRefused,
    author_parm_write,
    authored_fields,
    keyframe_count,
    reference_source,
)


class _Key:
    """hou.Keyframe stand-in: setFrame/setValue, then frame()/value()."""

    def __init__(self, frame=1.0, value=0.0):
        self._frame = frame
        self._value = value

    def setFrame(self, frame):
        self._frame = frame

    def setValue(self, value):
        self._value = value

    def frame(self):
        return self._frame

    def value(self):
        return self._value


class _ParmView:
    """A distinct wrapper for the same parm; equal, not identical."""

    def __init__(self, parm):
        self._parm = parm

    def __eq__(self, other):
        return isinstance(other, (_Parm, _ParmView)) and self._id == other._id

    def __hash__(self):
        return hash(self._id)

    @property
    def _id(self):
        return self._parm._id


class _Parm:
    """A parm that behaves the way the H22 probe showed."""

    def __init__(self, value, keys=(), source=None, clamp=None, name="tx",
                 frame=1.0, rejects=None):
        self._value = value
        self._keys = [_Key(f, v) for f, v in keys]
        self._source = source
        self._clamp = clamp
        self._name = name
        self._frame = frame
        self._rejects = rejects
        self._id = object()
        self.writes = []

    def __eq__(self, other):
        return isinstance(other, (_Parm, _ParmView)) and self._id == other._id

    def __hash__(self):
        return hash(self._id)

    # -- reads ---------------------------------------------------------
    def name(self):
        return self._name

    def node(self):
        return SimpleNamespace(path=lambda: "/obj/light1")

    def keyframes(self):
        return tuple(self._keys)

    def getReferencedParm(self):
        return self._source if self._source is not None else _ParmView(self)

    def eval(self):
        if not self._keys:
            return self._value
        for key in self._keys:
            if key.frame() == self._frame:
                return key.value()
        return self._keys[0].value()

    def expression(self):
        if len(self._keys) != 1:
            raise parm_authored._OPERATION_FAILED("Parameter must have exactly one keyframe")
        return "keyed"

    def expressionLanguage(self):
        return "exprLanguage.Hscript"

    def unexpandedString(self):
        raise parm_authored._OPERATION_FAILED("Only string parms have unexpanded strings")

    # -- writes --------------------------------------------------------
    def _store_key(self, key):
        self._keys = [k for k in self._keys if k.frame() != key.frame()]
        self._keys.append(key)
        self._keys.sort(key=lambda k: k.frame())

    def set(self, value, follow_parm_reference=True):
        if follow_parm_reference and self._source is not None:
            return self._source.set(value, follow_parm_reference=False)
        if self._rejects is not None and self._rejects(value):
            raise TypeError("not a number")
        self.writes.append(value)
        if self._keys:
            if follow_parm_reference:
                self._store_key(_Key(self._frame, value))   # add a key, keep the rest
            else:
                self._keys = []                            # clears the animation
                self._value = value
        else:
            self._value = self._clamp(value) if self._clamp else value

    def setKeyframe(self, key):
        self._store_key(key)

    def deleteAllKeyframes(self):
        self._keys = []


# ---------------------------------------------------------------------------
# The probe cases
# ---------------------------------------------------------------------------

def test_plain_parm_is_not_mistaken_for_a_reference():
    """getReferencedParm returns an equal, distinct wrapper for a plain parm."""
    parm = _Parm(0.0)
    view = parm.getReferencedParm()
    assert view == parm
    assert view is not parm
    assert reference_source(parm) is None

    out = author_parm_write([parm], [3.0])

    assert parm.eval() == 3.0
    assert out["observed"] == 3.0
    assert out["mismatch"] is False


def test_expression_parm_is_refused_by_default():
    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)])

    with pytest.raises(ParmWriteRefused) as exc:
        author_parm_write([parm], [5.0])

    assert "2 keyframe" in str(exc.value)
    assert parm.writes == []
    assert keyframe_count(parm) == 2


def test_replace_clears_the_keys_and_reads_back():
    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)])

    out = author_parm_write([parm], [5.0], mode="replace")

    assert parm.eval() == 5.0
    assert keyframe_count(parm) == 0
    assert out["observed"] == 5.0
    assert out["mismatch"] is False


def test_replace_puts_the_keys_back_when_the_value_is_refused():
    """A refused value must not cost the artist the animation."""
    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)],
                 rejects=lambda v: not isinstance(v, (int, float)))

    with pytest.raises(TypeError):
        author_parm_write([parm], ["not-a-number"], mode="replace")

    assert [(k.frame(), k.value()) for k in parm.keyframes()] == [(1.0, 1.0), (10.0, 100.0)]


def test_key_at_frame_keeps_the_other_keys(monkeypatch):
    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)], frame=5.0)
    monkeypatch.setattr(
        parm_authored, "hou",
        SimpleNamespace(Keyframe=_Key, frame=lambda: 5.0))

    out = author_parm_write([parm], [7.0], mode="key_at_frame")

    assert [(k.frame(), k.value()) for k in parm.keyframes()] == [
        (1.0, 1.0), (5.0, 7.0), (10.0, 100.0)]
    assert out["observed"] == 7.0
    assert out["authored"]["keyframe_count"] == [3]


def test_referenced_parm_is_refused_and_write_source_writes_the_source():
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


def test_tuple_write_is_all_or_none():
    first, second = _Parm(1.0, name="colorr"), _Parm(1.0, keys=[(1.0, 1.0)], name="colorg")

    with pytest.raises(ParmWriteRefused):
        author_parm_write([first, second], [0.5, 0.5])

    assert first.writes == []
    assert second.writes == []


def test_tuple_arity_mismatch_writes_nothing():
    parms = [_Parm(0.0), _Parm(0.0), _Parm(0.0)]

    with pytest.raises(ValueError) as exc:
        author_parm_write(parms, [1.0, 2.0])

    assert "Nothing was written" in str(exc.value)
    assert all(p.writes == [] for p in parms)


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        author_parm_write([_Parm(1.0)], [2.0], mode="yolo")


def test_multi_key_read_keeps_the_count_when_expression_raises():
    """expression() refuses a two-key parm; the count must survive that."""
    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)])

    assert authored_fields(parm, 2.0) == {"keyframe_count": 2}


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
    fake_hou = SimpleNamespace(node=lambda path: node,
                               undos=SimpleNamespace(group=_group))

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

    parm = _Parm(2.0, keys=[(1.0, 1.0), (10.0, 100.0)])
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
