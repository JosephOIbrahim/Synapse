"""WP4 (M1 production hardening) — houdini_render leaves the ROP byte-identical.

Before WP4, _render_on_main captured the artist's output path via parm.eval()
(already expanded) and never restored ANY parm it set — so one render rewrote
'$JOB/render_$F4.exr' into a hardcoded absolute single-frame path, silently
destroying the artist's token-based pipeline config. Now every parm set is
captured token-preserving (_parm_raw -> unexpandedString with eval fallback)
and restored in a finally, the whole mutation span runs inside
hou.undos.group("SYNAPSE: render"), and the flipbook fallback restores the
playhead.

Also pins WP2 Change-4 handler side: render_settings with node:"" (the
autonomy replan payload) falls back to _find_render_rop discovery.

Headless, per the tests/test_render_offmain_c11.py convention: fakes in
sys.modules before importing SynapseHandler, then monkeypatch the
handlers_render globals.
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Established handler-test convention: fakes before importing handlers.
_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)
_hde = ModuleType("hdefereval")
_hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
sys.modules.setdefault("hou", _mock_hou)
sys.modules.setdefault("hdefereval", _hde)

from synapse.server.handlers import SynapseHandler  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _Parm:
    """String parm: raw keeps $-tokens; eval() expands them (like hou)."""

    def __init__(self, raw, jobdir=""):
        self._raw = raw
        self._job = jobdir

    def unexpandedString(self):
        return self._raw

    def eval(self):
        return self._raw.replace("$JOB", self._job).replace("$F4", "0001")

    def evalAsStringAtFrame(self, frame):
        # M2-D enrichment: expand-at-given-frame semantics mirroring eval().
        return self._raw.replace("$JOB", self._job).replace(
            "$F4", str(int(frame)).zfill(4)
        )

    def set(self, v):
        self._raw = v


class _IntParm:
    """Numeric parm: unexpandedString() raises like hou does on non-string
    parms, so _parm_raw must take the eval() fallback."""

    def __init__(self, v):
        self._v = v

    def unexpandedString(self):
        raise TypeError("Parameter is not a string parameter")

    def eval(self):
        return self._v

    def set(self, v):
        self._v = v


class _Rop:
    """Fake ROP: render() snapshots what the renderer actually SAW into
    .seen and (optionally) writes the output file so the success path
    completes. Optionally raises to exercise the exception path."""

    def __init__(self, tmp_path, rop_type="karma", writes_output=True,
                 render_raises=None):
        self._type = rop_type
        self._writes = writes_output
        self._raises = render_raises
        self.picture = _Parm("$JOB/render_$F4.exr", str(tmp_path))
        self.resolutionx = _IntParm(1920)
        self.resolutiony = _IntParm(1080)
        self.override_res = _Parm("camera")
        self.seen = {}

    def type(self):
        return SimpleNamespace(name=lambda: self._type)

    def parm(self, name):
        if name in ("picture", "resolutionx", "resolutiony", "override_res"):
            return getattr(self, name)
        return None

    def parms(self):
        return []

    def path(self):
        return "/stage/rop1"

    def render(self, frame_range=None, verbose=False):
        self.seen = {
            "picture": self.picture.eval(),
            "resolutionx": self.resolutionx.eval(),
            "resolutiony": self.resolutiony.eval(),
            "override_res": self.override_res.eval(),
        }
        if self._raises is not None:
            raise self._raises
        if self._writes:
            Path(self.picture.eval()).write_bytes(b"EXR")


class _UndoRecorder:
    """Recording stand-in for hou.undos: group(label) yields a context
    manager that logs enter labels and exit count."""

    def __init__(self):
        self.entered = []
        self.exits = 0

    def group(self, label):
        rec = self

        class _Group:
            def __enter__(self):
                rec.entered.append(label)
                return self

            def __exit__(self, *exc):
                rec.exits += 1
                return False

        return _Group()


def _fake_hou(tmp_path, nodes, start_frame=42):
    """Build a fake hou + setFrame call log + undo recorder."""
    setframes = []
    undo = _UndoRecorder()
    cur = {"frame": start_frame}

    def _set_frame(f):
        cur["frame"] = f
        setframes.append(f)

    fake = SimpleNamespace(
        node=lambda p: nodes.get(p),
        frame=lambda: cur["frame"],
        setFrame=_set_frame,
        text=SimpleNamespace(expandString=lambda s: str(tmp_path)),
        ui=MagicMock(),
        paneTabType=SimpleNamespace(SceneViewer="SceneViewer"),
        undos=undo,
    )
    return fake, setframes, undo


def _patch(monkeypatch, fake_hou):
    """Swap the handlers_render globals to the fake (c11 convention)."""
    from synapse.server import handlers_render as hr

    g = SynapseHandler._handle_render.__globals__   # handlers_render namespace
    monkeypatch.setitem(g, "hou", fake_hou)
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)  # never wait in tests


# ---------------------------------------------------------------------------
# 1. The P0 token pin
# ---------------------------------------------------------------------------

def test_render_preserves_output_tokens(tmp_path, monkeypatch):
    """After houdini_render, the picture parm still holds $JOB/$F4 tokens."""
    rop = _Rop(tmp_path)
    fake, _, _ = _fake_hou(tmp_path, {"/stage/rop1": rop})
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    result = h._handle_render({"node": "/stage/rop1", "frame": 1})

    assert result["image_path"]                       # render actually completed
    assert rop.picture.unexpandedString() == "$JOB/render_$F4.exr"


# ---------------------------------------------------------------------------
# 2. Override-then-restore
# ---------------------------------------------------------------------------

def test_render_overrides_seen_by_renderer_then_restored(tmp_path, monkeypatch):
    rop = _Rop(tmp_path)
    fake, _, _ = _fake_hou(tmp_path, {"/stage/rop1": rop})
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    result = h._handle_render(
        {"node": "/stage/rop1", "frame": 1, "width": 320, "height": 240}
    )

    # The renderer saw the overrides + the expanded output path...
    assert rop.seen["resolutionx"] == 320
    assert rop.seen["resolutiony"] == 240
    assert rop.seen["override_res"] == "specific"
    assert rop.seen["picture"] == f"{tmp_path}/render_0001.exr"
    assert result["image_path"]

    # ...but the ROP is byte-identical afterwards.
    assert rop.resolutionx.eval() == 1920
    assert rop.resolutiony.eval() == 1080
    assert rop.override_res.eval() == "camera"
    assert rop.picture.unexpandedString() == "$JOB/render_$F4.exr"


# ---------------------------------------------------------------------------
# 3. Exception path: restore anyway, exception propagates
# ---------------------------------------------------------------------------

def test_render_exception_still_restores_parms(tmp_path, monkeypatch):
    rop = _Rop(tmp_path, render_raises=RuntimeError("renderer exploded"))
    fake, _, _ = _fake_hou(tmp_path, {"/stage/rop1": rop})
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    with pytest.raises(RuntimeError, match="renderer exploded"):
        h._handle_render(
            {"node": "/stage/rop1", "frame": 1, "width": 320, "height": 240}
        )

    assert rop.picture.unexpandedString() == "$JOB/render_$F4.exr"
    assert rop.resolutionx.eval() == 1920
    assert rop.resolutiony.eval() == 1080
    assert rop.override_res.eval() == "camera"


# ---------------------------------------------------------------------------
# 4. Undo idiom
# ---------------------------------------------------------------------------

def test_render_mutation_span_wrapped_in_undo_group(tmp_path, monkeypatch):
    rop = _Rop(tmp_path)
    fake, _, undo = _fake_hou(tmp_path, {"/stage/rop1": rop})
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    h._handle_render({"node": "/stage/rop1", "frame": 1})

    assert undo.entered == ["SYNAPSE: render"]
    assert undo.exits == 1


# ---------------------------------------------------------------------------
# 5. Flipbook fallback restores the playhead
# ---------------------------------------------------------------------------

def test_flipbook_fallback_restores_playhead(tmp_path, monkeypatch):
    # usdrender ROP that writes nothing -> poll fails -> flipbook fallback.
    rop = _Rop(tmp_path, rop_type="usdrender_rop", writes_output=False)
    fake, setframes, _ = _fake_hou(
        tmp_path, {"/stage/rop1": rop}, start_frame=42
    )
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    # Fake SceneViewer (MagicMock ui) writes no flipbook file either, so the
    # handler reports failure honestly -- but the playhead must be restored.
    with pytest.raises(RuntimeError, match="output wasn't created"):
        h._handle_render({"node": "/stage/rop1", "frame": 1})

    assert setframes == [1, 42], (
        "flipbook must setFrame(render frame) then restore the artist's "
        "playhead -- the call log must end at the pre-call frame"
    )


# ---------------------------------------------------------------------------
# 6. render_settings empty-node auto-discovery (WP2 Change-4 handler side)
# ---------------------------------------------------------------------------

def test_render_settings_empty_node_discovers_rop(tmp_path, monkeypatch):
    rop = _Rop(tmp_path)
    stage = SimpleNamespace(children=lambda: [rop])
    fake, _, _ = _fake_hou(tmp_path, {"/stage": stage, "/stage/rop1": rop})
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    result = h._handle_render_settings(
        {"node": "", "settings": {"resolutionx": 320}}
    )

    assert result["node"] == "/stage/rop1"        # discovered, reported truthfully
    assert result["settings"]["resolutionx"] == 320
    assert rop.resolutionx.eval() == 320          # settings tool persists on purpose


def test_render_settings_empty_node_no_rop_anywhere_is_loud(tmp_path, monkeypatch):
    fake, _, _ = _fake_hou(tmp_path, {})          # no /stage, no /out
    _patch(monkeypatch, fake)

    h = SynapseHandler()
    with pytest.raises(ValueError, match="auto-find a render ROP"):
        h._handle_render_settings({"node": "", "settings": {"resolutionx": 320}})
