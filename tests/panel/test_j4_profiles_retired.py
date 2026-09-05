"""design/joe-five J4 - the profile switch leaves the UI (Joe's word 2026-09-05).

RULING_JOE_FIVE J4: "Curious / Expert / ML are retired from the panel for now:
no Profile submenu, no pills, no density switch exposed. The composed profile
is `expert` (the default). Manifests, compositor and settings keep the
machinery (tests still exercise it) so it can return with a real difference;
nothing an artist can reach shows it. Persisted `profile` in settings is read
as `expert` regardless."

Two pins, one file:

  1. the composed panel is expert no matter what the settings file says, and
     the overflow carries no Profile submenu and no profile action anywhere -
     RED on the BC-5 fold (the panel composed `curious` from the file and the
     overflow held 'Profile >' with three checkable actions);
  2. the machinery survives underneath: `_recompose(profile)` still moves the
     root density, so manifests / compositor / settings stay exercised and
     the profiles can come back the day they carry a real difference.

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. Builds
against a scratch settings file so the artist's real picks are never read or
written (settings.py honours SYNAPSE_PANEL_SETTINGS).
"""
import json
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_j4_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

PROFILES = ("curious", "expert", "ml")
W, H = 340, 760

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _panel_from_persisted(tmp_path, monkeypatch, profile):
    """A composed panel booted from a settings file that persists ``profile``
    - the artist's pick on disk, the one J4 says the panel reads as expert."""
    path = tmp_path / "panel_settings.json"
    path.write_text(json.dumps({"profile": profile}), encoding="utf-8")
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(path))
    _app()
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p.resize(W, H)
    p.show()
    _app().processEvents()
    return p


def _all_actions(menu):
    """Every QAction reachable from ``menu``, submenus included (depth-first)."""
    out = []
    for act in menu.actions():
        out.append(act)
        sub = act.menu()
        if sub is not None:
            out.extend(_all_actions(sub))
    return out


def test_persisted_profile_composes_expert_and_overflow_has_no_profile(tmp_path, monkeypatch):
    """J4 pin 1. The settings file says `curious`; the composed panel is expert
    (root density `standard`, `_layout_profile` expert) and nothing an artist
    can reach shows a profile: no QMenu titled 'Profile' under the overflow,
    no checkable action anywhere in it whose data() names a profile, and no
    profile-action builder on the class."""
    from synapse.panel.synapse_panel import SynapsePanel
    p = _panel_from_persisted(tmp_path, monkeypatch, "curious")
    try:
        assert p.property("density") == "standard", p.property("density")
        assert p._layout_profile == "expert", p._layout_profile
        menu = p._build_overflow_menu()
        titles = [m.title() for m in menu.findChildren(QtWidgets.QMenu)]
        assert "Profile" not in titles, titles
        leaks = [(a.text(), a.data()) for a in _all_actions(menu)
                 if a.isCheckable() and a.data() in PROFILES]
        assert not leaks, leaks
    finally:
        p.close()
    assert not hasattr(SynapsePanel, "_build_profile_actions"), (
        "the profile-action builder must be gone (J4)")


def test_recompose_machinery_survives(tmp_path, monkeypatch):
    """J4 pin 2. The switch left the UI, not the tree: `_recompose(profile)`
    still drives the compositor over the live panel, so the manifests keep
    their density lever for the day the profiles return."""
    p = _panel_from_persisted(tmp_path, monkeypatch, "curious")
    try:
        assert p.property("density") == "standard"
        p._recompose("curious")
        _app().processEvents()
        assert p.property("density") == "airy", p.property("density")
        p._recompose("expert")
        _app().processEvents()
        assert p.property("density") == "standard", p.property("density")
    finally:
        p.close()
