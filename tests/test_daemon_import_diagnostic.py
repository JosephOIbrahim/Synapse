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
import json
import os
import subprocess
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Real-probe test
# ---------------------------------------------------------------------------
#
# Four of the five tests above fake both halves of the failure:
# ``_break_anthropic`` puts ``None`` in ``sys.modules['anthropic']`` and
# ``_pretend_present`` replaces ``importlib.util.find_spec``. The fifth,
# ``test_without_the_risk_flag_the_original_boot_error_is_untouched``, breaks
# the import alone. None of the five asks the presence probe to resolve a real
# installed distribution. A probe answering from the wrong source therefore
# still satisfies the two tests that assert on message substrings --
# ``test_both_installed_says_the_import_failed_on_a_dependency`` (the November
# 2026 case this file exists to prove) and
# ``test_it_no_longer_claims_the_packages_are_missing``, which needs only that
# the phrase "no real" is absent. Stated that narrowly on purpose: every one of
# the five asserts on message text, so a wrong-source probe is invisible to all
# of them in principle; only the subprocess test below requires the real import
# path.
#
# This test asks the real question in a subprocess. An import hook makes
# ``httpx`` -- a hard dependency of anthropic that it imports at module scope
# -- raise ``ModuleNotFoundError``, so ``from anthropic import Anthropic``
# fails for real, the way it did in November 2026 when a present SDK died on a
# broken transitive dependency. CPython removes a module from ``sys.modules``
# when its import raises, so afterwards ``find_spec('anthropic')`` must
# resolve the installed distribution; the child asserts that state and then
# calls the diagnostic. Nothing in the child replaces ``find_spec`` or plants
# a ``sys.modules`` entry for ``anthropic``.

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_PYTHON = _REPO_ROOT / "python"

_DIAGNOSTIC_MARKER = "__DAEMON_DIAGNOSTIC__"

_REAL_FAILURE_SCRIPT = """
import importlib.util
import json
import sys

sys.path.insert(0, __PROJECT_PYTHON__)


class _BlockTransitiveDependency:
    # anthropic imports httpx at module scope; making that dependency
    # genuinely unimportable makes `import anthropic` fail for real.
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "httpx" or fullname.startswith("httpx."):
            raise ModuleNotFoundError("No module named 'httpx'", name="httpx")
        return None


sys.meta_path.insert(0, _BlockTransitiveDependency())

# Does the hook actually fire? find_spec goes through the meta path, so it answers
# the question WITHOUT importing httpx -- importing it here would cache the module
# and defeat the very hook under test. On a machine where httpx is already loaded,
# or where this anthropic version does not import httpx eagerly, the hook cannot
# produce the failure and the test would otherwise assert about the wrong exception.
try:
    importlib.util.find_spec("httpx")
    hook_fires = False
except ModuleNotFoundError:
    hook_fires = True

import synapse
synapse._VENDOR_ABI_RISK = True

from synapse.host.daemon import SynapseDaemon

_spec_anthropic = importlib.util.find_spec("anthropic")
premise = {
    "synapse_file": getattr(synapse, "__file__", None),
    "hook_fires": hook_fires,
    "httpx_in_sys_modules": "httpx" in sys.modules,
    "anthropic_already_imported": "anthropic" in sys.modules,
    "find_spec_anthropic": _spec_anthropic is not None,
    "find_spec_anthropic_origin": getattr(_spec_anthropic, "origin", None),
    "find_spec_pydantic": importlib.util.find_spec("pydantic") is not None,
    "python": ".".join(str(part) for part in sys.version_info[:3]),
}

raised = None
message = ""
try:
    SynapseDaemon(api_key="test", boot_gate=False)._build_anthropic_client()
except BaseException as exc:  # noqa: BLE001 -- the diagnostic must raise
    raised = type(exc).__name__
    message = str(exc)
else:
    raised = "NO-EXCEPTION"

print("__DAEMON_DIAGNOSTIC__" + json.dumps({
    "premise": premise,
    "raised": raised,
    "message": message,
    "anthropic_in_sys_modules_after": "anthropic" in sys.modules,
}))
"""


def _run_real_failed_import() -> dict:
    """Run the diagnostic in a fresh interpreter and return its report."""
    script = _REAL_FAILURE_SCRIPT.replace(
        "__PROJECT_PYTHON__", repr(str(_PROJECT_PYTHON))
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
             # A dummy key so that if the import does NOT fail, the child reaches
             # make_anthropic_client with a key instead of raising ModelAccessDenied,
             # which would name the wrong cause. The test asserts on `raised`, so a
             # fall-through still fails -- but legibly.
             "ANTHROPIC_API_KEY": "test-key-not-used"},
    )
    assert result.returncode == 0, (
        f"child interpreter failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    lines = [
        line for line in result.stdout.splitlines()
        if line.startswith(_DIAGNOSTIC_MARKER)
    ]
    assert lines, (
        "child produced no diagnostic report\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return json.loads(lines[-1][len(_DIAGNOSTIC_MARKER):])


def test_real_failed_import_finds_the_installed_anthropic():
    """A real broken anthropic import must still report both as installed.

    Fails if the diagnostic reports the packages as absent when they are
    installed but their import failed, or if it stops carrying the original
    exception type and text through to the message.
    """
    outcome = _run_real_failed_import()
    premise = outcome["premise"]

    if not (premise["find_spec_anthropic"] and premise["find_spec_pydantic"]):
        pytest.skip(
            "anthropic/pydantic are not resolvable in this interpreter; "
            "pyproject.toml declares pydantic as a base dependency and "
            "anthropic in the dev extra, and this test needs real "
            "distributions for find_spec to resolve"
        )

    if not premise.get("hook_fires"):
        pytest.skip(
            "the httpx import hook cannot fire in this interpreter "
            f"(httpx already in sys.modules: {premise.get('httpx_in_sys_modules')}). "
            "This anthropic version does not import httpx at module scope, so no "
            "real failed import can be produced here and the diagnostic would be "
            "asserted against the wrong exception."
        )

    assert premise["anthropic_already_imported"] is False, (
        "the daemon import chain preloaded anthropic, so this test cannot "
        "exercise a real failed import from a clean interpreter"
    )
    synapse_path = Path(premise["synapse_file"]).resolve()
    assert synapse_path.is_relative_to(_PROJECT_PYTHON.resolve()), (
        f"child imported {synapse_path}, not the tree under {_PROJECT_PYTHON}"
    )

    assert outcome["raised"] == "RuntimeError", (
        f"expected the risk-flag diagnostic, got {outcome['raised']!r}: "
        f"{outcome['message']}"
    )
    message = outcome["message"]
    assert "Both 'anthropic' and 'pydantic' are installed" in message, message
    assert "failed on a dependency of theirs" in message, message
    assert "ModuleNotFoundError" in message, (
        "the message must name the exception type the real import raised"
    )
    assert "No module named 'httpx'" in message, (
        "the message must carry the original exception text, not a summary"
    )
    assert f"on Python {premise['python']}" in message, (
        "the message must name the running Python, as the diagnostic claims"
    )
    assert "no real" not in message
    assert outcome["anthropic_in_sys_modules_after"] is False, (
        "a failed import must leave no sys.modules entry; that is what makes "
        "find_spec resolve the installed distribution instead of a stale one"
    )
