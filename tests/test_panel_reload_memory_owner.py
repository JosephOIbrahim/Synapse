"""Reopening the shipped panel must preserve the process memory authority."""
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import xml.etree.ElementTree as ET


PANEL_PATH = Path(__file__).parents[1] / 'houdini/python_panels/synapse_panel.pypanel'


def invalidate(modules):
    tree = ast.parse(ET.parse(PANEL_PATH).findtext('./interface/script'))
    # Execute the shipped top-level cache invalidation statements, isolated from
    # the test process. A restored legacy global purge must fail this test.
    invalidation = [n for n in tree.body if isinstance(n, ast.For) or
                    (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call))]
    namespace = {'sys': SimpleNamespace(modules=modules)}
    exec(compile(ast.Module(body=invalidation, type_ignores=[]), str(PANEL_PATH), 'exec'), namespace)


def test_shipped_panel_reload_retains_host_owners_and_refreshes_ui():
    names = ('synapse', 'synapse.panel', 'synapse.panel.synapse_panel', 'synapse.panel.tool_executor',
             'synapse.memory', 'synapse.memory.store', 'synapse.loop', 'synapse.loop.ports',
             'synapse.host', 'synapse.host.memory_loop', 'synapse.server', 'synapse.server.handlers',
             'synapse.session', 'synapse.session.tracker', 'unrelated')
    before = {name: ModuleType(name) for name in names}
    for name, module in before.items():
        parent, _, child = name.rpartition('.')
        if parent in before:
            setattr(before[parent], child, module)
    package_path = ['configured-ui-path']
    before['synapse.panel'].__path__ = package_path
    owner = object()
    before['synapse.memory.store']._global_synapse = owner
    modules = dict(before)
    invalidate(modules)
    for name in names:
        if name.startswith('synapse.panel.'):
            assert name not in modules
            assert not hasattr(modules['synapse.panel'], name.rsplit('.', 1)[1])
        else:
            assert modules.get(name) is before[name], f'Live owner/module replaced: {name}'
    assert modules['synapse.memory.store']._global_synapse is owner
    assert modules['synapse.panel'].__path__ is package_path
    assert modules['synapse'].memory is before['synapse.memory']


def test_reload_removes_only_the_exact_cached_child_attribute():
    parent = ModuleType('synapse.panel')
    cached = ModuleType('synapse.panel.settings')
    unrelated_state = object()
    parent.settings = unrelated_state
    modules = {'synapse.panel': parent, 'synapse.panel.settings': cached}
    invalidate(modules)
    assert 'synapse.panel.settings' not in modules
    assert parent.settings is unrelated_state


def test_full_loader_reimports_ui_twice_without_replacing_memory_owner(tmp_path):
    # Real import machinery in a disposable process; no Houdini or Qt modules.
    # The retained package's from-list attributes are a second import cache.
    probe = r'''
import json
import os
from pathlib import Path
import sys
from types import ModuleType
import xml.etree.ElementTree as ET

source, folder = map(Path, sys.argv[1:])
script = ET.parse(source).findtext('./interface/script')
os.environ.pop('SYNAPSE_ROOT', None)
root = ModuleType('synapse')
root.__path__ = [str(folder.parent)]
panel = ModuleType('synapse.panel')
panel.__path__ = [str(folder)]
root.panel = panel
memory = ModuleType('synapse.memory')
memory.__path__ = []
store = ModuleType('synapse.memory.store')
owner = store._global_synapse = object()
memory.store = store
root.memory = memory
sys.modules.update({'synapse': root, 'synapse.panel': panel,
                    'synapse.memory': memory, 'synapse.memory.store': store})
stale = ModuleType('synapse.panel.settings')
stale.revision = 'stale'
panel.settings = stale
sys.modules[stale.__name__] = stale
results = []
for revision in ('first', 'second'):
    (folder / 'settings.py').write_text('revision = ' + repr(revision) + '\n', encoding='utf-8')
    (folder / 'synapse_panel.py').write_text(
        'def onCreateInterface():\n    return ' + repr(revision) + '\n', encoding='utf-8')
    namespace = {}
    exec(compile(script, str(source), 'exec'), namespace)
    assert sys.modules['synapse'] is root
    assert sys.modules['synapse.panel'] is panel
    assert sys.modules['synapse.memory'] is memory
    assert sys.modules['synapse.memory.store'] is store
    assert store._global_synapse is owner
    assert root.memory.store is store
    from synapse.panel import settings
    results.append({'settings': settings.revision, 'ui': namespace['onCreateInterface']()})
print(json.dumps(results))
'''
    completed = subprocess.run([sys.executable, '-I', '-B', '-c', probe,
                                str(PANEL_PATH), str(tmp_path)],
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == [
        {'settings': 'first', 'ui': 'first'}, {'settings': 'second', 'ui': 'second'},
    ]
