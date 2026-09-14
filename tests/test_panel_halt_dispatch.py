"""HALT-1 — the emergency halt must dispatch, or say plainly that it did not.

WHY THIS FILE ASSERTS DISPATCH COUNT AND NOT THE RAIL SENTENCE
--------------------------------------------------------------
The defect this pins was found by a probe and missed by a test that asserted on
the header string. That test set a generic mock as the live call and asserted
the rail read the halting phrase -- which is satisfied by exactly the case where
no halt was dispatched at all. A sentence assertion cannot tell a halt that ran
from a halt that was dropped. **A dispatch counter can.** Every pin here counts
``DirectToolCall.start()`` calls.

THE RULE BEING PINNED, and where it comes from
-----------------------------------------------
``server/handlers.py`` excludes ``emergency_halt`` from the C5 mutation lock,
in its own words: *"a running render holds the C5 mutation lock for its whole
duration, so a mutating-classified stop or halt would queue behind the very
operation it exists to interrupt -- which is the difference between a kill
switch and a decoration."*  The panel must not re-introduce at the UI layer the
serialization the handler layer deliberately removed.

``panel/direct_tool.py``'s ``DirectToolCall`` states the other half: *"Both are
terminal and exactly one fires -- a control that can silently do neither is a
control the artist cannot trust."*  The re-entry guard returns BEFORE the call
is constructed, so neither signal fires. That branch therefore has to report
itself, or the artist is told a safety action is in progress that was never
sent.

BAND: HEADLESS-PROVEN. The shipped method bodies are pulled out of the source
with ``ast`` and driven against stand-ins -- the technique
``tests/test_first_session_panel.py`` uses. Nothing imports PySide, so nothing
here can skip, and a green line means the shipped code ran.
"""

import ast
import os
import sys
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "python"))

_SRC = os.path.join(_ROOT, "python", "synapse", "panel", "synapse_panel.py")

_WANT = {"_run_direct_tool", "_on_emergency_halt", "_on_cancel_cook"}


def _shipped():
    """Exec only the methods under test, out of the shipped source."""
    tree = ast.parse(open(_SRC, encoding="utf-8").read())
    body = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name in _WANT]
    assert len(body) == len(_WANT), (
        "source no longer defines exactly %s" % sorted(_WANT))
    ns = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), "panel", "exec"), ns)
    return ns


_NS = _shipped()


class _Call:
    """Stand-in for DirectToolCall. Counts what was actually dispatched."""

    def __init__(self, tool_name, arguments, parent=None):
        self.tool_name = tool_name
        self.arguments = arguments
        self._running = False
        self.finished_ok = types.SimpleNamespace(connect=lambda f: None)
        self.failed = types.SimpleNamespace(connect=lambda f: None)
        parent.dispatched.append(tool_name)
        self._panel = parent

    def isRunning(self):
        return self._running

    def start(self):
        self._running = True
        self._panel.started.append(self.tool_name)


class _Panel:
    """Only what the probed methods touch. No PySide, no Houdini."""

    def __init__(self):
        self.dispatched = []      # DirectToolCall constructed
        self.started = []         # .start() actually called
        self.said = []            # chat messages the artist would read
        self.header = []          # (state, text) pairs
        self._direct_call = None
        self._direct_calls = {}
        self._last_tool_node = "/obj/geo1/topnet1"
        self._chat = types.SimpleNamespace(
            append_system_message=lambda m: self.said.append(m))

    def _set_header(self, state, text):
        self.header.append((state, text))

    def __getattr__(self, name):
        if name in _NS:
            return lambda *a, **k: _NS[name](self, *a, **k)
        raise AttributeError(name)


def _bind(panel):
    """Point the shipped code at the counting stand-in."""
    _NS["DirectToolCall"] = lambda t, a, parent=None: _Call(t, a, parent=panel)
    return panel


def test_a_first_click_dispatches():
    """Baseline: with nothing in flight, the halt goes out."""
    p = _bind(_Panel())
    p._on_emergency_halt()
    assert p.started == ["synapse_emergency_halt"], p.started


def test_b_blocked_request_is_never_silent():
    """The guard fires NEITHER terminal signal, so it must speak for itself.

    Fails against 5424853a, where this branch was a bare ``return``.
    """
    p = _bind(_Panel())
    p._on_cancel_cook()
    p._direct_call._running = True          # the cancel thread is still alive
    before = len(p.started)
    p._on_emergency_halt()
    blocked = len(p.started) == before
    if blocked:
        assert p.said, (
            "a request that was NOT dispatched said nothing to the artist; "
            "the rail alone reads as in progress")
