"""L5-4 — the profile tab switcher's state core, headless.

Covers selection -> settings write -> restore on ``SwitcherState``
(``python/synapse/panel/settings.py``). Qt never loads here: the state logic
is Qt-free by design; the tab strip's Qt behavior (live recompose, history
intact across reopen) is seat-verified per the task card's manual accept.
"""

from synapse.panel.settings import (
    PROFILES,
    SwitcherState,
    default_settings,
    load_settings,
    save_settings,
)


def _settings_file(tmp_path):
    return tmp_path / "panel_settings.json"


def test_restore_defaults_to_expert_when_no_file(tmp_path):
    st = SwitcherState(_settings_file(tmp_path))
    assert st.profile == "expert"


def test_select_writes_through_and_restores(tmp_path):
    path = _settings_file(tmp_path)
    st = SwitcherState(path)
    assert st.select("curious") is True
    assert st.profile == "curious"
    assert st.persist_ok is True
    assert load_settings(path)["profile"] == "curious"
    # restore: a fresh instance (panel reopen) lands on the saved tab
    assert SwitcherState(path).profile == "curious"


def test_select_preserves_sibling_keys(tmp_path):
    path = _settings_file(tmp_path)
    seed = default_settings()
    seed["provider_id"] = "ollama"
    seed["model_by_provider"] = {"ollama": "qwen3:32b"}
    seed["custom"] = {"base_url": "http://localhost:8000",
                      "model": "qwen3-vl:30b", "key_env": "MY_KEY"}
    assert save_settings(seed, path)
    SwitcherState(path).select("ml")
    out = load_settings(path)
    assert out["profile"] == "ml"
    assert out["provider_id"] == "ollama"
    assert out["model_by_provider"] == {"ollama": "qwen3:32b"}
    assert out["custom"]["base_url"] == "http://localhost:8000"


def test_select_rejects_unknown_and_noop(tmp_path):
    path = _settings_file(tmp_path)
    st = SwitcherState(path)
    assert st.select("wizard") is False
    assert st.select("expert") is False        # already the selection
    assert not path.exists()                   # no-ops never touch disk
    assert st.profile == "expert"


def test_restore_survives_corrupt_file(tmp_path):
    path = _settings_file(tmp_path)
    path.write_text("{not json", encoding="utf-8")
    st = SwitcherState(path)
    assert st.profile == "expert"              # defaults-on-corrupt posture
    assert st.select("curious") is True        # select rewrites well-shaped
    assert load_settings(path)["profile"] == "curious"


def test_failed_save_still_switches_and_frays_visibly(tmp_path):
    target = tmp_path / "blocked"
    target.mkdir()                             # save's os.replace cannot land
    st = SwitcherState(target)
    assert st.select("ml") is True             # the session still switches
    assert st.profile == "ml"
    assert st.persist_ok is False              # ...and the failure is visible


def test_profiles_is_the_closed_set():
    assert PROFILES == ("curious", "expert", "ml")
