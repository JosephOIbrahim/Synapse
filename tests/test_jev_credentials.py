"""Offline credential lifetime and precedence; never use a real key or registry."""
import importlib
from types import SimpleNamespace

import pytest

from synapse.jev import adapter, credentials


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    credentials.clear_session_key()
    monkeypatch.setenv("TYPESAFE_API_KEY", "configured-test-key")
    yield
    credentials.clear_session_key()


def test_artist_session_key_overrides_environment_and_clear_restores_it(monkeypatch):
    assert adapter.resolve_key() == "configured-test-key"
    credentials.set_session_key("  replacement-test-key  ")
    assert adapter.resolve_key() == "replacement-test-key"
    assert credentials.key_source() == "session"
    assert credentials.os.environ["TYPESAFE_API_KEY"] == "configured-test-key"
    credentials.clear_session_key()
    assert adapter.resolve_key() == "configured-test-key"
    assert credentials.key_source() == "environment"


def test_session_key_survives_module_refresh():
    credentials.set_session_key("saved-test-key")
    importlib.reload(credentials)
    assert adapter.resolve_key() == "saved-test-key"
    credentials.clear_session_key()
    importlib.reload(credentials)
    assert adapter.resolve_key() == "configured-test-key"


@pytest.mark.parametrize("invalid", ["", "  ", "key\nsecret", "key secret", "key\x00", "clé", "x" * 4097, None])
def test_invalid_replacement_keeps_previous_key_and_does_not_echo_input(invalid):
    credentials.set_session_key("saved-test-key")
    with pytest.raises(ValueError) as error:
        credentials.set_session_key(invalid)
    assert adapter.resolve_key() == "saved-test-key"
    assert "saved-test-key" not in str(error.value)
    if isinstance(invalid, str) and invalid.strip():
        assert invalid not in str(error.value)


def test_existing_windows_registry_fallback_is_preserved(monkeypatch):
    class Handle:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.delenv("TYPESAFE_API_KEY")
    monkeypatch.setattr(credentials.sys, "platform", "win32")
    fake_registry = SimpleNamespace(HKEY_CURRENT_USER=object(),
        OpenKey=lambda *args: Handle(),
        QueryValueEx=lambda handle, name: ("registry-test-key", 1))
    monkeypatch.setitem(credentials.sys.modules, "winreg", fake_registry)
    assert adapter.resolve_key() == "registry-test-key"
    credentials.set_session_key("session-test-key")
    assert adapter.resolve_key() == "session-test-key"


def test_no_key_has_an_explicit_absent_status(monkeypatch):
    monkeypatch.setattr(credentials, "_configured_key", lambda: None)
    assert credentials.resolve_key() is None
    assert credentials.key_source() == "none"
