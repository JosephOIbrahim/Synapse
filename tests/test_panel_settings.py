"""Panel settings persistence — load/save roundtrip, corrupt-file defaults,
atomic write, unknown-pid drop. Qt-free, hou-free, network-free (tmp_path only
— the canonical <repo>/.synapse/ location is never touched by these tests).
"""
import json

from synapse.panel import settings as pset


def test_roundtrip(tmp_path):
    p = tmp_path / "panel_settings.json"
    st = pset.default_settings()
    st["provider_id"] = "ollama"
    st["model_by_provider"] = {"ollama": "glm-5:cloud", "claude": "claude-sonnet-5"}
    st["custom"] = {"base_url": "http://localhost:11434", "model": "m", "key_env": "K"}
    assert pset.save_settings(st, path=p) is True
    assert pset.load_settings(path=p) == st


def test_missing_file_yields_defaults(tmp_path):
    st = pset.load_settings(path=tmp_path / "nope.json")
    assert st == pset.default_settings()
    assert st["provider_id"] == "claude"
    assert st["custom"] == {"base_url": "", "model": "", "key_env": ""}


def test_corrupt_or_unshaped_file_yields_defaults(tmp_path):
    p = tmp_path / "panel_settings.json"
    for garbage in ("{not json", '"a string"', '[]',
                    '{"provider_id": 7, "model_by_provider": "x", "custom": []}'):
        p.write_text(garbage, encoding="utf-8")
        st = pset.load_settings(path=p)
        assert st["provider_id"] == "claude"
        assert st["model_by_provider"] == {}
        assert st["custom"] == {"base_url": "", "model": "", "key_env": ""}


def test_load_drops_non_string_model_picks(tmp_path):
    p = tmp_path / "panel_settings.json"
    p.write_text(json.dumps({"model_by_provider": {"claude": 3, "ollama": "", "nemotron": "ok"}}),
                 encoding="utf-8")
    assert pset.load_settings(path=p)["model_by_provider"] == {"nemotron": "ok"}


def test_save_is_atomic_no_tmp_left_behind(tmp_path):
    p = tmp_path / "panel_settings.json"
    assert pset.save_settings(pset.default_settings(), path=p)
    files = sorted(f.name for f in tmp_path.iterdir())
    assert files == ["panel_settings.json"]          # tmp replaced, not left
    assert json.loads(p.read_text(encoding="utf-8"))["version"] == 1


def test_save_failure_returns_false_not_raise(tmp_path):
    # a directory at the target path makes os.replace fail on every platform
    p = tmp_path / "panel_settings.json"
    p.mkdir()
    assert pset.save_settings(pset.default_settings(), path=p) is False


def test_merged_model_picks_drops_unknown_pids():
    defaults = {"claude": "claude-sonnet-4-6", "ollama": "glm-5:cloud"}
    st = {"model_by_provider": {
        "claude": "claude-opus-4-8",      # known → overrides
        "retired-engine": "whatever",     # unknown pid → dropped
        "ollama": "",                     # empty → ignored
    }}
    merged = pset.merged_model_picks(st, defaults)
    assert merged == {"claude": "claude-opus-4-8", "ollama": "glm-5:cloud"}


def test_settings_path_is_repo_dot_synapse():
    p = pset.settings_path()
    assert p.name == "panel_settings.json"
    assert p.parent.name == ".synapse"
    # repo root sanity: the resolved root holds this test's own directory
    assert (p.parent.parent / "tests").is_dir()
