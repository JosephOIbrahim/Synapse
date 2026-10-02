"""A test session keeps its logs and its bridge sidecar out of the user's folder.

TESTSPILL / F8 (2026-10-02). The dev seat is the production seat: the same
user runs Houdini and the tests. A full run wrote one ``emergency_halt`` and
``freeze_dump`` pair into ``~/.synapse/logs`` each time, where the newest-five
pruning evicts real freeze evidence, and where "SUSTAINED FREEZE" lines from a
test landed in the log of a Houdini session that was open and healthy.

Three test files already redirected ``$SYNAPSE_LOG_DIR`` for their own tests.
The writes that got through came from outside any one test: a freeze chain's
timer firing after the test that armed it. So the redirect is the session's,
set in ``tests/conftest.py`` before the first test module is imported, and it
holds between tests as well as inside them.

What this does not cover, and says so:

* the audit log (``~/.synapse/audit``) and the gate store (``~/.synapse/gates``)
  have no override and are still written, about 47 KB of audit lines for one
  full run; so is an encryption key on a machine that has none;
* the conversation store: under hython, ``session_store`` saves beside the
  scene (``$HIP/claude/``), which for an untitled scene is the working folder;
* Houdini's own ``pdgservices.json``, which hython touches when it starts.
"""
from __future__ import annotations

import os

from synapse.core import logfile
from synapse.server import bridge_endpoint


def _real(path):
    return os.path.normcase(os.path.realpath(path))


def _under(path, folder):
    path, folder = _real(path), _real(folder)
    return path == folder or path.startswith(folder + os.sep)


_USER_STORE = os.path.join(os.path.expanduser("~"), ".synapse")


def test_the_sessions_logs_are_not_the_users():
    assert os.environ.get("SYNAPSE_LOG_DIR", "").strip(), (
        "tests/conftest.py gave this session no log folder, so every freeze dump "
        "and emergency halt a test writes lands in ~/.synapse/logs")
    assert not _under(logfile.log_dir(), _USER_STORE), logfile.log_dir()


def test_the_sessions_bridge_sidecar_is_not_the_users():
    """A server started by a test would otherwise rewrite the sidecar a live
    Houdini session's own clients read to find it."""
    assert os.environ.get("SYNAPSE_BRIDGE_FILE", "").strip()
    assert not _under(bridge_endpoint.bridge_file(), _USER_STORE), bridge_endpoint.bridge_file()


def test_every_writer_of_freeze_evidence_resolves_the_same_folder(tmp_path, monkeypatch):
    """The halt report, the telemetry flush and the stack dump each ask
    ``logfile.log_dir``. One of them resolving the folder its own way is how a
    redirect that covers the other two would miss it."""
    from synapse.server import emergency_live, marshal_guard, telemetry_dump

    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    assert logfile.log_dir() == str(tmp_path)
    for module in (emergency_live, marshal_guard, telemetry_dump):
        source = open(module.__file__, encoding="utf-8").read()
        assert "from ..core.logfile import log_dir" in source, module.__name__


def test_a_tests_own_choice_still_wins(monkeypatch):
    """The session's folder is a default. A test that clears the variable, to
    exercise the product's own default, gets the product's own default."""
    monkeypatch.delenv("SYNAPSE_LOG_DIR", raising=False)
    monkeypatch.delenv("SYNAPSE_BRIDGE_FILE", raising=False)
    assert logfile.log_dir() == os.path.join(os.path.expanduser("~"), ".synapse", "logs")
    assert bridge_endpoint.bridge_file() == os.path.join(os.path.expanduser("~"), ".synapse", "bridge.json")
