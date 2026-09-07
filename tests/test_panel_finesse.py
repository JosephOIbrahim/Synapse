"""Composed command discovery must preserve the command's local identity."""
import ast
from pathlib import Path
import sys
from types import MethodType, ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


PANEL = Path(__file__).parents[1] / 'python/synapse/panel'


def functions(filename, names, namespace):
    tree = ast.parse((PANEL / filename).read_text(encoding='utf-8'))
    wanted = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in wanted} == set(names)
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(PANEL / filename), 'exec'), namespace)
    return namespace


def entries(monkeypatch, category, command, description):
    legacy = ModuleType('synapse.panel.command_palette')
    legacy.build_palette_entries = lambda: [SimpleNamespace(category=category, command=command,
        label=command, description=description, verb='build', context=None)]
    monkeypatch.setitem(sys.modules, legacy.__name__, legacy)
    registry = ModuleType('synapse.mcp._tool_registry')
    registry.TOOL_DEFS = []
    monkeypatch.setitem(sys.modules, registry.__name__, registry)
    panel_module = ModuleType('synapse.panel.synapse_panel')
    panel_module._QUICK_ACTIONS = []
    monkeypatch.setitem(sys.modules, panel_module.__name__, panel_module)
    ns = functions('tool_palette.py', ['_load_entries'], {
        '_MATERIAL_PRESETS': [], '_RENDER_TIERS': [], '_ctx_rank': lambda _: 0,
        '_CATEGORY_DOMAIN': {'command': 'Commands', 'recipe': 'Recipes', 'vex': 'VEX'},
        '_CATEGORY_PREFIX': {'recipe': 'Build this network recipe — ', 'vex': 'Explain this VEX — '},
    })
    return ns['_load_entries']()


@pytest.mark.parametrize('command,method', [('/events', '_open_notifications'), ('/saved-recipes', '_open_saved_recipes')])
@pytest.mark.parametrize('busy', [False, True])
def test_palette_choice_opens_local_view_without_a_model_or_draft_change(monkeypatch, command, method, busy):
    row, = entries(monkeypatch, 'command', command, 'A readable description, not a command')
    ns = functions('synapse_panel.py', ['_on_tool_picked', '_send'], {
        '_ACTIVE_PANEL_WORKERS': {object()} if busy else set(), 'ClaudeWorker': None})
    panel = SimpleNamespace(_open_notifications=Mock(), _open_saved_recipes=Mock(),
        _prepare_connection=Mock(side_effect=AssertionError('Local navigation reached the model')),
        _input=Mock(), _messages=[{'role': 'user', 'content': 'earlier'}],
        _pending_context=['/stage/selected'], _worker=None, _chat=Mock())
    panel._input.toPlainText.return_value = 'An unfinished creative thought'
    panel._send = MethodType(ns['_send'], panel)
    ns['_on_tool_picked'](panel, row['send'])
    getattr(panel, method).assert_called_once_with()
    panel._prepare_connection.assert_not_called()
    panel._input.clear.assert_not_called()
    panel._input.setPlainText.assert_not_called()
    assert panel._messages == [{'role': 'user', 'content': 'earlier'}]
    assert panel._pending_context == ['/stage/selected']


def test_other_slash_commands_keep_their_dispatch_payload(monkeypatch):
    row, = entries(monkeypatch, 'command', '/help', 'Show help and available commands')
    assert row['send'] == '/help'


@pytest.mark.parametrize('category,prefix', [('recipe', 'Build this network recipe — '), ('vex', 'Explain this VEX — ')])
def test_recipe_and_vex_choices_keep_existing_prompt_intent(monkeypatch, category, prefix):
    row, = entries(monkeypatch, category, 'example', 'The existing request')
    assert row['send'] == prefix + 'The existing request'
