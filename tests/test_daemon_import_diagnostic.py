"""The vendored-ABI diagnostic must name what actually went wrong.

This branch exists to turn a cryptic deep ImportError into something a person
can act on. It previously did the opposite: it claimed no real pydantic or
anthropic was installed. On the failure it was written for, in November 2026,
both were installed and anthropic's own import died on a missing transitive
dependency — opentelemetry had no `trace` submodule. Anyone reading the old
message would have reinstalled packages that were already there.

The message is now built from a presence probe rather than an assumption, so
these tests pin the distinction it has to keep: installed-and-broken is not
the same as absent.
"""

import importlib.util
import sys

import pytest

pytest.importorskip("synapse.host.daemon")

import synapse  # noqa: E402
from synapse.host.daemon import SynapseDaemon  # noqa: E402


def _daemon() -> SynapseDaemon:
    return SynapseDaemon(api_key="test", boot_gate=False)


def _break_anthropic(monkeypatch) -> None:
    """Make `from anthropic import Anthropic` raise ImportError.

    None in sys.modules is the documented way to make an import fail without
    uninstalling anything: the import system raises ImportError on it.
    """
    monkeypatch.setitem(sys.modules, "anthropic", None)


def _pretend_present(monkeypatch, present: set) -> None:
    """Answer find_spec for anthropic/pydantic without importing either."""
    real = importlib.util.find_spec

    def fake(name, *args, **kwargs):
        if name in ("anthropic", "pydantic"):
            return object() if name in present else None
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", fake)


def _risk_on(monkeypatch) -> None:
    monkeypatch.setattr(synapse, "_VENDOR_ABI_RISK", True, raising=False)


def test_both_installed_says_the_import_failed_on_a_dependency(monkeypatch):
    """The real November 2026 case: present packages, broken import."""
    _risk_on(monkeypatch)
    _break_anthropic(monkeypatch)
    _pretend_present(monkeypatch, {"anthropic", "pydantic"})

    with pytest.raises(RuntimeError) as caught:
        _daemon()._build_anthropic_client()

    message = str(caught.value)
    assert "Both 'anthropic' and 'pydantic' are installed" in message, message
    assert "failed on a dependency of theirs" in message
    assert ("ImportError" in message or "ModuleNotFoundError" in message), (
        "the message must name the exception type; ModuleNotFoundError is the "
        "subclass CPython raises for a None entry in sys.modules"
    )
    assert "No module named" in message or "sys.modules" in message, (
        "the message must carry the original exception text, not a summary"
    )


def test_it_no_longer_claims_the_packages_are_missing(monkeypatch):
    """The exact sentence that was false. It must never come back."""
    _risk_on(monkeypatch)
    _break_anthropic(monkeypatch)
    _pretend_present(monkeypatch, {"anthropic", "pydantic"})

    with pytest.raises(RuntimeError) as caught:
        _daemon()._build_anthropic_client()

    assert "no real pydantic/anthropic is installed" not in str(caught.value)
    assert "no real" not in str(caught.value)


def test_neither_installed_says_so(monkeypatch):
    _risk_on(monkeypatch)
    _break_anthropic(monkeypatch)
    _pretend_present(monkeypatch, set())

    with pytest.raises(RuntimeError) as caught:
        _daemon()._build_anthropic_client()

    assert "Neither 'anthropic' nor 'pydantic' is installed" in str(caught.value)


def test_one_installed_names_which(monkeypatch):
    _risk_on(monkeypatch)
    _break_anthropic(monkeypatch)
    _pretend_present(monkeypatch, {"anthropic"})

    with pytest.raises(RuntimeError) as caught:
        _daemon()._build_anthropic_client()

    message = str(caught.value)
    assert "'anthropic' is installed" in message
    assert "'pydantic' is not" in message


def test_without_the_risk_flag_the_original_boot_error_is_untouched(monkeypatch):
    """A genuinely missing dependency takes the old path, unescalated."""
    monkeypatch.setattr(synapse, "_VENDOR_ABI_RISK", False, raising=False)
    _break_anthropic(monkeypatch)

    from synapse.host.daemon import DaemonBootError

    with pytest.raises(DaemonBootError):
        _daemon()._build_anthropic_client()
