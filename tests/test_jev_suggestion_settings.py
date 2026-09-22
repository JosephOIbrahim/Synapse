"""Action ranking is a separate preference, never an egress grant."""
import json

import pytest

from synapse.panel import settings


def test_ranking_defaults_off_for_new_and_old_settings(tmp_path):
    path = tmp_path / "settings.json"
    assert settings.default_settings()["jev_suggestions_enabled"] is False
    path.write_text(json.dumps({"provider_id": "ollama", "jev_routing_mode": "shadow"}, sort_keys=True), encoding="utf-8")
    loaded = settings.load_settings(path)
    assert loaded["jev_suggestions_enabled"] is False
    assert loaded["jev_routing_mode"] == "shadow"


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), (1, False),
    ("true", False), ("on", False), (None, False), ({}, False), ([], False)])
def test_ranking_requires_boolean_and_preserves_model_and_policy(tmp_path, value, expected):
    path = tmp_path / "settings.json"
    payload = {"jev_suggestions_enabled": value, "jev_routing_mode": "off",
               "provider_id": "ollama", "model_choice": {"mode": "exact", "value": "artist-picked"},
               "model_by_provider": {"ollama": "artist-picked"},
               "model_policy_path": "broken-authority-is-not-repaired",
               "model_policy_generation": 29}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    loaded = settings.load_settings(path)
    assert loaded["jev_suggestions_enabled"] is expected
    for key in ("jev_routing_mode", "provider_id", "model_choice", "model_by_provider",
                "model_policy_path", "model_policy_generation"):
        assert loaded[key] == payload[key]


def test_round_trip_changes_preference_without_creating_policy(tmp_path, monkeypatch):
    path, policy = tmp_path / "settings.json", tmp_path / "permissions.json"
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(path))
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(policy))
    before = settings.load_settings()
    assert settings.save_settings({**before, "jev_suggestions_enabled": True})
    assert settings.load_settings()["jev_suggestions_enabled"] is True
    assert not policy.exists()
    assert settings.load_settings()["model_choice"] == before["model_choice"]
