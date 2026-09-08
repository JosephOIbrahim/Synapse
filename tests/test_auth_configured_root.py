"""Worktree code must retain the explicitly selected local configuration."""
from pathlib import Path

from synapse.host import auth


def test_configured_root_loads_existing_configuration_without_overriding_environment(tmp_path,monkeypatch):
    configured=tmp_path/'original'
    configured.mkdir()
    (configured/'.env').write_text('SYNAPSE_ROOT_PROBE=from_existing_config\nSYNAPSE_ROOT_OVERRIDE=from_file\n',encoding='utf-8')
    monkeypatch.setenv('SYNAPSE_ROOT',str(configured))
    monkeypatch.setenv('SYNAPSE_ROOT_OVERRIDE','explicit_environment')
    monkeypatch.delenv('SYNAPSE_ROOT_PROBE',raising=False)
    auth._load_dotenv()
    assert auth.os.environ['SYNAPSE_ROOT_PROBE']=='from_existing_config'
    assert auth.os.environ['SYNAPSE_ROOT_OVERRIDE']=='explicit_environment'
    monkeypatch.delenv('SYNAPSE_ROOT_PROBE',raising=False)


def test_unconfigured_root_is_relative_to_source_not_cwd(tmp_path,monkeypatch):
    monkeypatch.delenv('SYNAPSE_ROOT',raising=False)
    monkeypatch.chdir(tmp_path)
    assert auth._repo_root()==Path(auth.__file__).resolve().parents[3]


def test_missing_explicit_root_does_not_fall_back_to_another_config(tmp_path,monkeypatch):
    configured=tmp_path/'missing'
    monkeypatch.setenv('SYNAPSE_ROOT',str(configured))
    assert auth._repo_root()==configured
    auth._load_dotenv()
