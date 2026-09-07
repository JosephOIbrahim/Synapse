"""Notification preferences must not silently opt into desktop delivery."""
import json

import pytest

from synapse.panel import settings


def test_fresh_install_keeps_desktop_off(tmp_path):
    prefs = settings.load_settings(tmp_path / "missing.json")["notifications"]
    assert prefs["desktop"] is False
    assert prefs["quiet"] is False
    assert prefs["completions"] is True
    assert prefs["connections"] is True


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, [], {}, [True]])
def test_only_explicit_booleans_change_alert_preferences(tmp_path, value):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"notifications": {"desktop": value, "quiet": value,
                                                  "completions": value, "connections": value}}, sort_keys=True), encoding="utf-8")
    assert settings.load_settings(path)["notifications"] == {
        "desktop": False, "quiet": False, "completions": True, "connections": True}


def test_alert_preferences_roundtrip_preserves_selected_project(tmp_path):
    path = tmp_path / "prefs.json"
    original = {"model_policy_path": str(tmp_path / "project/model_access.json"),
                "model_policy_generation": "selected-project-generation"}
    path.write_text(json.dumps(original, sort_keys=True), encoding="utf-8")
    prefs = settings.load_settings(path)
    prefs["notifications"] = {"desktop": True, "quiet": True, "completions": False, "connections": False}
    assert settings.save_settings(prefs, path)
    actual = settings.load_settings(path)
    assert actual["notifications"] == prefs["notifications"]
    assert actual["model_policy_path"] == original["model_policy_path"]
    assert actual["model_policy_generation"] == original["model_policy_generation"]


def test_bad_preferences_do_not_enable_desktop_or_repair_model_rules(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text('{"notifications": {"desktop": true}, "notifications": {}}', encoding="utf-8")
    actual = settings.load_settings(path)
    assert actual["notifications"]["desktop"] is False
    assert actual["model_policy_path"] is None


def test_new_defaults_are_independent_objects():
    first = settings.default_settings()
    first["notifications"]["desktop"] = True
    assert settings.default_settings()["notifications"]["desktop"] is False
