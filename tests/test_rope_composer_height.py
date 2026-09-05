"""L5-22 — the composer starts centred and remembers the artist's drag.

Joe's seat call: every session began by re-dragging the divider until the
composer sat equidistant between prompt and chat, because first-run height
was the constant 132. Now the first-run height derives from the space the
chat and the composer actually share (half of it, clamped floor..max), a
grip drag persists on release, and a persisted height always beats the
centred default — L6: the panel remembers the artist's answer, it never
re-imposes its own.

Qt-free on purpose: the decision function and the schema-v3 key live in
``settings.py`` and test headless; the Qt wiring is pinned by source
conformance (the ``test_rope_design_conformance`` idiom); the live half is
the task's SEAT check.
"""
import ast
import json
from pathlib import Path

from synapse.panel import settings as pset

REPO = Path(__file__).resolve().parent.parent
PANEL_PATH = REPO / "python" / "synapse" / "panel" / "synapse_panel.py"
PANEL_SRC = PANEL_PATH.read_text(encoding="utf-8")

FLOOR, MAX_H = pset.COMPOSER_FLOOR, pset.COMPOSER_MAX


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _panel_class(name):
    tree = ast.parse(PANEL_SRC)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == name)


# --- first run: centred from the available height, not a constant ------------

def test_first_run_is_half_the_shared_space():
    for shared in (300, 500, 640, 1000):
        assert pset.composer_start_height(None, shared) == shared // 2


def test_first_run_tracks_available_height_not_132():
    # 132 was the v9 constant; first run must move with the pane, not sit still
    assert pset.composer_start_height(None, 1000) == 500 != 132
    assert (pset.composer_start_height(None, 700)
            != pset.composer_start_height(None, 1000))


def test_short_pane_clamps_to_floor():
    # a short pane degrades gracefully — never a composer with no room to type
    assert pset.composer_start_height(None, 100) == FLOOR
    assert pset.composer_start_height(None, 0) == FLOOR


def test_tall_pane_clamps_to_max():
    assert pset.composer_start_height(None, 5000) == MAX_H


# --- the artist's persisted height wins --------------------------------------

def test_persisted_height_beats_centred():
    assert pset.composer_start_height(388, 1000) == 388


def test_persisted_height_still_rides_the_rails():
    assert pset.composer_start_height(8, 1000) == FLOOR
    assert pset.composer_start_height(4000, 1000) == MAX_H


def test_junk_persisted_falls_back_to_centred():
    for junk in (True, False, -3, 0, "tall", 3.5):
        assert pset.composer_start_height(junk, 1000) == 500


# --- schema v3: the key, the default, the migration --------------------------

def test_schema_v3_default_is_centred():
    st = pset.default_settings()
    assert st["composer_height"] is None    # None = never dragged → centred
    assert st["version"] == pset.SETTINGS_VERSION == 3


def test_v2_file_without_key_loads_cleanly_and_centres(tmp_path):
    v2 = {"version": 2, "profile": "curious", "fresh_install": True,
          "provider_id": "claude",
          "model_by_provider": {"claude": "claude-sonnet-4-6"},
          "model_choice": {"mode": "exact", "value": "claude-sonnet-4-6"},
          "custom": {"base_url": "", "model": "", "key_env": ""}}
    st = pset.load_settings(_write(tmp_path / "panel_settings.json", v2))
    assert st["composer_height"] is None    # migration: absent key → centred
    assert st["profile"] == "curious"       # sibling keys ride along untouched
    assert st["model_choice"] == {"mode": "exact", "value": "claude-sonnet-4-6"}


def test_persisted_height_round_trips(tmp_path):
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    st["composer_height"] = 388
    assert pset.save_settings(st, path=p)
    assert pset.load_settings(p)["composer_height"] == 388


def test_junk_height_in_file_sanitizes_to_centred(tmp_path):
    for junk in (True, "tall", -3, 0, 3.5):
        st = pset.load_settings(_write(
            tmp_path / "panel_settings.json",
            dict(pset.default_settings(), composer_height=junk)))
        assert st["composer_height"] is None


def test_missing_and_corrupt_files_still_never_raise(tmp_path):
    # the load_settings posture is preserved: defaults, never an exception
    assert pset.load_settings(tmp_path / "nope.json")["composer_height"] is None
    p = tmp_path / "panel_settings.json"
    p.write_text("{not json", encoding="utf-8")
    assert pset.load_settings(p)["composer_height"] is None


# --- Qt wiring, pinned by source (the live half is the SEAT check) -----------

def test_the_132_constant_is_gone():
    assert "self._user_h = 132" not in PANEL_SRC


def test_panel_settles_where_height_is_real_not_in_init():
    # settle runs at show/resize (def + two call sites), through the shared
    # decision function — never from a constant in __init__
    assert PANEL_SRC.count("_settle_composer_height") >= 3
    assert "def showEvent" in PANEL_SRC
    assert "composer_start_height" in PANEL_SRC


def test_grip_persists_on_release_not_on_move():
    grip = _panel_class("_InputResizeGrip")
    bodies = {f.name: ast.get_source_segment(PANEL_SRC, f)
              for f in grip.body if isinstance(f, ast.FunctionDef)}
    assert "height_committed" in bodies["mouseReleaseEvent"]
    assert "height_committed" not in bodies["mouseMoveEvent"]


def test_settle_is_one_shot():
    # after first run the divider never moves on the panel's own (L6)
    cls = _panel_class("_GrowingInput")
    settle = next(f for f in cls.body
                  if isinstance(f, ast.FunctionDef) and f.name == "settle_height")
    src = ast.get_source_segment(PANEL_SRC, settle)
    assert "_height_settled" in src and "return" in src


def test_autogrow_survives():
    # the auto-grow-to-fit-content behaviour is explicitly kept
    cls = _panel_class("_GrowingInput")
    auto = next(f for f in cls.body
                if isinstance(f, ast.FunctionDef) and f.name == "_autosize")
    assert "_user_h" in ast.get_source_segment(PANEL_SRC, auto)


# --- CTO B4 ruling 2026-09-05: a persisted drag never exceeds THIS pane ---

def test_persisted_from_tall_dock_is_capped_to_short_pane():
    """The G3 regression: composer_height 514 persisted on a tall dock,
    re-applied at PANEL_MIN_HEIGHT where prompt+chat share ~356px, pushed
    Send 441px below the pane. The answer is capped to shared - FLOOR so
    the chat keeps at least one floor's worth."""
    assert pset.composer_start_height(514, 356) == 356 - FLOOR
    assert pset.composer_start_height(514, 356) < 356


def test_cap_never_drops_below_floor_on_a_tiny_pane():
    assert pset.composer_start_height(514, 100) == FLOOR
    assert pset.composer_start_height(514, 0) == 514   # unmeasured pane: rails only


def test_cap_leaves_tall_panes_alone():
    assert pset.composer_start_height(514, 1000) == 514
    assert pset.composer_start_height(None, 1000) == 500
