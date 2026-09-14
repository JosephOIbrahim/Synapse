"""The panel's system-prompt fallback must declare itself (INTENT.md S4/S6/S7).

`SynapsePanel._build_system_prompt` has two fallback branches. When
`synapse.panel.system_prompt` cannot be imported, or when `build_system_prompt`
raises, the method substitutes the profile overlay - which is `""` by default -
for the real steering prompt and returns it. The method's own docstring names
the consequence: with an empty system prompt the model EXPLAINS build requests
instead of executing them. Substituting silently is a state the system has not
earned (S6: unmeasured behaviour reads UNAVAILABLE); the artist and the log
must be able to tell a degraded turn from a healthy one (S4, S7).

These tests pin the ANNOUNCEMENT only. Which branch runs, and what each branch
returns, are asserted unchanged.

The method body is compiled straight out of the shipped source, so no Qt, no
Houdini and no panel construction is involved.
"""
import ast
from contextlib import contextmanager
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

PANEL = Path(__file__).parents[1] / "python/synapse/panel/synapse_panel.py"
PANEL_LOGGER = "synapse.panel.synapse_panel"
PROMPT_MODULE = "synapse.panel.system_prompt"
# `_prompt_fallback` is the announcement helper; it does not exist before the
# fix, so the slice must not require it or these tests would error instead of
# failing on the claim under test.
SLICE = ("_build_system_prompt", "_prompt_fallback")


def _slice_panel():
    """Compile the shipped prompt-building methods, nothing else."""
    source = PANEL.read_text(encoding="utf-8")
    tree = ast.parse(source, str(PANEL))
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "SynapsePanel")
    methods = [node for node in cls.body
               if isinstance(node, ast.FunctionDef) and node.name in SLICE]
    assert any(node.name == "_build_system_prompt" for node in methods)
    module = ModuleType("panel_prompt_slice")
    module.__dict__["logger"] = logging.getLogger(PANEL_LOGGER)
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(PANEL), "exec"),
         module.__dict__)
    return {node.name: module.__dict__[node.name] for node in methods}


def make_panel(overlay=""):
    panel = SimpleNamespace(_system_prompt_overlay=overlay, _chat=Mock())
    for name, function in _slice_panel().items():
        setattr(panel, name, function.__get__(panel))
    return panel


@contextmanager
def prompt_builder(build):
    """Install a stand-in `synapse.panel.system_prompt`, or break the import.

    `build=None` plants `None` in sys.modules, which is how CPython itself
    reports a halted import - a real ImportError raised by the real import
    statement, not a monkeypatched stand-in for one.
    """
    missing = object()
    previous = sys.modules.get(PROMPT_MODULE, missing)
    try:
        if build is None:
            sys.modules[PROMPT_MODULE] = None
        else:
            module = ModuleType(PROMPT_MODULE)
            module.build_system_prompt = build
            sys.modules[PROMPT_MODULE] = module
        yield
    finally:
        if previous is missing:
            sys.modules.pop(PROMPT_MODULE, None)
        else:
            sys.modules[PROMPT_MODULE] = previous


@pytest.fixture
def records():
    """Every record the panel logger emits, captured at DEBUG.

    Capturing below WARNING on purpose: a `logger.debug` in the fallback would
    land in this list and still leave the WARNING assertions red, which is the
    point - DEBUG is filtered out of production logging, so it announces
    nothing to anyone watching the panel.
    """
    target = logging.getLogger(PANEL_LOGGER)
    collected = []

    class Collect(logging.Handler):
        def emit(self, record):
            collected.append(record)

    handler = Collect(level=logging.DEBUG)
    level, disabled = target.level, target.disabled
    target.addHandler(handler)
    target.setLevel(logging.DEBUG)
    target.disabled = False
    try:
        yield collected
    finally:
        target.removeHandler(handler)
        target.setLevel(level)
        target.disabled = disabled


def warnings_in(records):
    return [record for record in records if record.levelno >= logging.WARNING]


def boom(ctx):
    raise RuntimeError("synthetic builder failure")


def test_import_fallback_is_announced_at_warning_with_its_branch_and_reason(records):
    panel = make_panel()
    with prompt_builder(None):
        prompt = panel._build_system_prompt()
    assert prompt == "", "the substituted prompt itself must not change"
    assert warnings_in(records), (
        "the import fallback swapped in an empty system prompt and said nothing")
    message = warnings_in(records)[0].getMessage()
    assert "branch=import" in message, message
    # The real class, not the base class: CPython raises ModuleNotFoundError
    # for a halted import, and the notice reports what actually happened.
    assert "ModuleNotFoundError" in message, message
    assert PROMPT_MODULE in message, message
    assert "UNAVAILABLE" in message, message


def test_build_fallback_is_announced_at_warning_with_its_branch_and_reason(records):
    panel = make_panel(overlay="OVERLAY STEER")
    with prompt_builder(boom):
        prompt = panel._build_system_prompt()
    assert prompt == "OVERLAY STEER", "the substituted prompt itself must not change"
    assert warnings_in(records), (
        "build_system_prompt raised, the overlay was sent instead, and nothing said so")
    message = warnings_in(records)[0].getMessage()
    assert "branch=build" in message, message
    assert "RuntimeError" in message, message
    assert "synthetic builder failure" in message, message


def test_the_two_branches_are_distinguishable_in_the_log(records):
    with prompt_builder(None):
        make_panel()._build_system_prompt()
    with prompt_builder(boom):
        make_panel()._build_system_prompt()
    said = [record.getMessage() for record in warnings_in(records)]
    assert len(said) == 2, said
    assert "branch=import" in said[0] and "branch=build" in said[1], said


def test_artist_is_told_once_per_degradation_and_again_after_a_healthy_turn(records):
    panel = make_panel()
    with prompt_builder(None):
        panel._build_system_prompt()
        panel._build_system_prompt()
    assert panel._chat.append_system_message.call_count == 1, (
        "the artist must be told the steering prompt was substituted - once, "
        "not once per turn")
    said = panel._chat.append_system_message.call_args[0][0]
    assert "UNAVAILABLE" in said, said
    with prompt_builder(lambda ctx: "BASE PROMPT"):
        assert panel._build_system_prompt() == "BASE PROMPT"
    with prompt_builder(None):
        panel._build_system_prompt()
    assert panel._chat.append_system_message.call_count == 2, (
        "a turn that degrades again after a healthy one is a new degradation")


def test_healthy_build_announces_nothing_and_keeps_the_overlay_suffix(records):
    panel = make_panel(overlay="OVERLAY STEER")
    with prompt_builder(lambda ctx: "BASE PROMPT"):
        prompt = panel._build_system_prompt()
    assert prompt == "BASE PROMPT\n\nOVERLAY STEER"
    assert warnings_in(records) == [], (
        "a healthy turn must not carry a degradation warning")
    panel._chat.append_system_message.assert_not_called()
