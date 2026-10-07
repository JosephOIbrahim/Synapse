"""RSI-1: the rope gate refuses a fix that drops a logging line its card never named.

K03 removed `_log.debug("Undo rollback best-effort failed: %s", e)` under a card that
said "Keep the existing logging", and the gate kept it. A check now refuses that shape
before a byte is copied. Code decides; no model is asked.

These tests reuse the throwaway `world` repo from tests/test_rope_graph.py.
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "_rope_graph_tests", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_rope_graph.py"))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
_fix, _git, _head, _read, _write = _base._fix, _base._git, _base._head, _base._read, _base._write
world = _base.world  # the fixture, re-exported so pytest finds it here

LOGGED = ('import logging\n_log = logging.getLogger(__name__)\nVALUE = \'broken\'\n'
          '_log.debug("rollback failed: %s", 1)\n')
FIXED = "import logging\n_log = logging.getLogger(__name__)\nVALUE = 'fixed'\n"
NEW_TEST = "def test_new():\n    assert True\n"
MOVED_TEST = ('import logging\n_log = logging.getLogger(__name__)\n'
              '_log.debug("rollback failed: %s", 1)\n\n\n' + NEW_TEST)
ACCEPT = [{"kind": "grep_min", "path": "pkg/a.py", "pattern": "fixed"}]


def _logged_world(world):
    """The repo's pkg/a.py carries a logger line, committed, and the slot sits on that commit."""
    G, st, repo, slot = world
    _write(repo / "pkg" / "a.py", LOGGED)
    _git(repo, "add", "pkg/a.py")
    assert _git(repo, "commit", "-q", "-m", "a logger line").returncode == 0
    assert _git(slot, "checkout", "-q", "--detach", _head(repo)).returncode == 0
    return G, st, repo, slot


def test_the_gate_refuses_a_fix_that_drops_a_log_line_its_card_never_named(world):
    """Fails on the pre-RSI gate, which kept this fix."""
    G, st, repo, slot = _logged_world(world)
    it = _fix(st, slot, accept=ACCEPT)
    _write(slot / "pkg" / "a.py", FIXED)
    _write(slot / "tests" / "test_new.py", NEW_TEST)
    before = _head(repo)
    verdict, note = G.gate(st, it)
    assert verdict == "dropped_log", note
    assert "rollback failed" in note
    assert '_log.debug("rollback failed: %s", 1)' in _read(repo / "pkg" / "a.py")
    assert _head(repo) == before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert not os.path.exists(str(repo / "tests" / "test_new.py"))
    assert _git(slot, "status", "--porcelain").stdout.strip() == ""
    assert st["slots"][0]["retired"] == ""


def test_a_log_line_moved_to_another_declared_file_is_kept(world):
    """Waiver (i): the same line, added anywhere in the declared files, is a move."""
    G, st, repo, slot = _logged_world(world)
    it = _fix(st, slot, accept=ACCEPT)
    _write(slot / "pkg" / "a.py", FIXED)
    _write(slot / "tests" / "test_new.py", MOVED_TEST)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note


def test_a_card_that_quotes_the_log_line_may_remove_it(world):
    """Waiver (ii): the card names the call's message, so the removal was asked for."""
    G, st, repo, slot = _logged_world(world)
    it = _fix(st, slot, accept=ACCEPT, change="- drop the noisy 'rollback failed: %s' debug line")
    _write(slot / "pkg" / "a.py", FIXED)
    _write(slot / "tests" / "test_new.py", NEW_TEST)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note


def test_the_word_logging_in_a_card_is_no_waiver(world):
    """The K03 shape: a card that says to keep the logging, and a fix that drops it."""
    G, st, repo, slot = _logged_world(world)
    it = _fix(st, slot, accept=ACCEPT, change="- make VALUE fixed. Keep the existing logging.")
    _write(slot / "pkg" / "a.py", FIXED)
    _write(slot / "tests" / "test_new.py", NEW_TEST)
    before = _head(repo)
    verdict, note = G.gate(st, it)
    assert verdict == "dropped_log", note
    assert _head(repo) == before
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


def test_a_line_with_no_logger_call_is_not_this_check_s_business(world):
    """A fix that removes a plain line still reaches the ordinary checks."""
    G, st, repo, slot = _logged_world(world)
    it = _fix(st, slot, accept=ACCEPT)
    _write(slot / "pkg" / "a.py", LOGGED.replace("VALUE = 'broken'", "VALUE = 'fixed'"))
    _write(slot / "tests" / "test_new.py", NEW_TEST)
    verdict, note = G.gate(st, it)
    assert verdict == "kept", note
