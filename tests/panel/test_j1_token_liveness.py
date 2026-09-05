"""design/joe-five J1 - the model token is a status light (Joe's word
2026-09-05, harness/cto/runs/2026-09-05/RULING_JOE_FIVE.md J1).

Joe: "the model has no color so if you are running an llm there is no
highlight color its grey which is confusing in context to the user."

The token says WHICH engine is thinking; that is state, and state has colour
in this panel (the mark, the state sentence). The colour is the engine's
liveness, from the existing palette - no new hex, no new font:

  live     Houdini connected (or 'warning') AND the engine keyed
           -> CONIFEROUS   #6E8F72  hue 127.3 deg = 15-degree bucket 8
  working  a turn is streaming
           -> WARM         #FF7759  hue  10.8 deg = bucket 0 (the mark's note)
  off      not connected, or no key for the engine
           -> TEXT_DISABLED (achromatic: no bucket)

Wired to the same signal the mark and Connect read (_apply_context ->
_render_state), so it is never a stale green. 'Keyed' is decided by the
provider's own resolve_key() (env / .env reads only - never a network probe;
ollama's 'not-needed' counts, an unconfigured Custom engine is None).

Supersedes RULING_DIRECTION_BC.md Addendum 3.3 ('the token is data, not a
status light'); the bc-wave pin in test_bc_wave.py moves with this ruling.

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. Every
test points SYNAPSE_PANEL_SETTINGS at its own scratch file and restores the
engine pick it changed, so a provider switch here never leaks into the next
panel this process builds (the artist's real picks are never read or written).
Shown RED first on the tree before the fix: the property is None and the
token's grab holds no chromatic pixel after _apply_context.
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

import test_bc_wave as _bc          # the panel builder + the review's hue predicate

if not _bc._HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")
QtGui = getattr(_bc, "QtGui", None)
QtCore = getattr(_bc, "QtCore", None)

_CONTEXT = {"frame": 1, "selected_nodes": [], "scene_file": ""}
_LIVE_BUCKET = 8      # CONIFEROUS #6E8F72 -> 127.3 deg // 15
_WORKING_BUCKET = 0   # WARM       #FF7759 ->  10.8 deg // 15


@pytest.fixture
def scratch_settings(monkeypatch):
    """A fresh settings file per test: the panel boots on defaults and every
    _persist_picks() lands here, not in the module-wide scratch file."""
    path = os.path.join(tempfile.mkdtemp(prefix="synapse_j1_"), "panel_settings.json")
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", path)
    return path


def _token(panel):
    return panel._author_lbl


def _buckets(panel, widget=None):
    """15-degree hue buckets (the review's predicate, test_bc_wave._hue_buckets
    arithmetic) of the PANEL pixels under ``widget`` - an opaque composite
    over PANEL grey, which preserves the painted hue exactly. The button's own
    ``grab()`` is not used: it renders on a transparent pixmap, and the RGB888
    conversion un-premultiplies its low-alpha edge pixels into phantom hues
    (measured on this tree: CONIFEROUS text read {8, 10}, never {8})."""
    import colorsys
    _bc._app().processEvents()
    if widget is None:
        pix = panel.grab()
    else:
        top = widget.mapTo(panel, QtCore.QPoint(0, 0))
        pix = panel.grab(QtCore.QRect(top, widget.size()))
    img = pix.toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    raw = bytes(img.constBits())
    colours = set()
    for y in range(h):
        row = raw[y * bpl:y * bpl + 3 * w]
        colours.update(zip(row[0::3], row[1::3], row[2::3]))
    return {int(colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360) // 15
            for r, g, b in colours if max(r, g, b) - min(r, g, b) > 24}


def test_boot_disconnected_token_is_off_and_grey(scratch_settings):
    """At boot the panel is not connected (headless), so the token is 'off':
    TEXT_DISABLED, no chromatic pixel, and the tooltip says why. The same
    truth the mark shows (disconnected) - one signal, two readouts."""
    p = _bc._panel("expert")
    try:
        tok = _token(p)
        assert p._mark._state == "disconnected"
        assert tok.property("liveness") == "off", tok.property("liveness")
        assert _buckets(p, tok) == set(), sorted(_buckets(p, tok))
        assert "Not connected" in tok.toolTip(), tok.toolTip()
        assert tok.toolTip().startswith("Engine & model - click to switch")
    finally:
        p.close()


def test_connected_keyed_engine_is_live_then_working_then_live(scratch_settings):
    """A keyless engine (ollama: resolve_key() == 'not-needed') on a connected
    panel is 'live' (CONIFEROUS, bucket 8); a streaming turn turns it 'working'
    (WARM, bucket 0 - the mark's own note); the turn ending returns it to
    'live'. The colour follows _apply_context / _set_busy - the same edges the
    mark and Connect follow - never a stale value."""
    p = _bc._panel("expert")
    pid0 = p._provider_id
    try:
        tok = _token(p)
        p._set_provider("ollama")
        assert p._provider_id == "ollama"
        p._apply_context(dict(_CONTEXT))
        assert p._conn_state == "connected"
        assert tok.property("liveness") == "live", tok.property("liveness")
        assert _buckets(p, tok) == {_LIVE_BUCKET}, sorted(_buckets(p, tok))
        assert tok.toolTip() == "Engine & model - click to switch", tok.toolTip()

        p._set_busy(True)
        assert tok.property("liveness") == "working", tok.property("liveness")
        assert _buckets(p, tok) == {_WORKING_BUCKET}, sorted(_buckets(p, tok))

        p._set_busy(False)
        assert tok.property("liveness") == "live", tok.property("liveness")
        assert _buckets(p, tok) == {_LIVE_BUCKET}, sorted(_buckets(p, tok))
    finally:
        p._set_provider(pid0)
        p.close()


def test_connected_unkeyed_engine_is_off_with_reason(scratch_settings):
    """An unconfigured Custom engine resolves no key (resolve_key() is None),
    so even on a connected panel the token is 'off' and the tooltip names the
    engine. The Configure dialog an unconfigured pick opens is stubbed (it is
    modal; the switch path underneath is the production one)."""
    p = _bc._panel("expert")
    pid0 = p._provider_id
    p._configure_custom = lambda: None      # record nothing, open no dialog
    try:
        tok = _token(p)
        p._apply_context(dict(_CONTEXT))
        assert p._conn_state == "connected"
        assert not p._custom_configured()
        p._set_provider("custom")
        assert p._provider_id == "custom"
        assert tok.property("liveness") == "off", tok.property("liveness")
        assert _buckets(p, tok) == set(), sorted(_buckets(p, tok))
        assert "No key for custom" in tok.toolTip(), tok.toolTip()
    finally:
        p._set_provider(pid0)
        p.__dict__.pop("_configure_custom", None)
        p.close()
