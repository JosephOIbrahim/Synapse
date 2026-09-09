"""The docking exemption's premise, pinned (landing r3, CTO RULING-2B, 2026-09-05).

quick_actions.QuickActionPills and chat_panel.SynapseChatPanel are the legacy
Chat/HDA alternate entry. They are exempt from the 380px docking bound ONLY
while no artist can dock them: no .pypanel under houdini/python_panels builds
them, and the shipped panel (synapse.panel.synapse_panel) never imports them,
directly or transitively. The day either premise breaks, this file goes red
and test_panel_rhythm_docking.py returns both regions to its list on its own
(it reads DOCKING_EXEMPT_UNSHIPPED through reachable_panel_modules()).

Source-only: no Qt, no host.
"""

import ast
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "python/synapse/panel"
PYPANELS = ROOT / "houdini/python_panels"
SHIPPED = "synapse_panel"


def _module_path(name):
    """Resolve a synapse.panel.<name> import to its source file (module or package)."""
    file = PANEL / (name + ".py")
    if file.is_file():
        return file
    package = PANEL / name / "__init__.py"
    if package.is_file():
        return package
    return None


def _panel_import_names(tree, relative=False, require_static=False):
    """Read import operations, not comments or retained-module name strings."""
    found = set()
    import_functions = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("importlib", "builtins"):
            import_functions.update(alias.asname or alias.name for alias in node.names
                                    if alias.name == ("import_module" if node.module == "importlib"
                                                      else "__import__"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[:2] == ["synapse", "panel"] and len(parts) > 2:
                    found.add(parts[2])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            parts = module.split(".") if module else []
            if node.level == 0 and parts[:2] == ["synapse", "panel"]:
                if len(parts) > 2:
                    found.add(parts[2])
                else:
                    found.update(alias.name for alias in node.names)
            elif node.level == 1 and relative:
                # `from .x import y` / `from . import x` inside the panel package
                if parts:
                    found.add(parts[0])
                else:
                    found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id in import_functions
                or isinstance(node.func, ast.Attribute)
                and node.func.attr in ("import_module", "__import__")):
            # The thin loader must select a known builder. The wider static
            # import graph also includes ordinary non-panel plugin discovery.
            if not (node.args and isinstance(node.args[0], ast.Constant)):
                assert not require_static, "dynamic import target in panel loader"
                continue
            name = node.args[0].value
            if isinstance(name, str) and name.startswith("synapse.panel."):
                found.add(name.split(".")[2])
    return found


def _direct_imports(path):
    """Every synapse.panel.* module a source file imports, at any depth of nesting."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {name for name in _panel_import_names(tree, relative=path.parent == PANEL)
            if _module_path(name) is not None}


def _assert_shipped_loader(text):
    document = ET.fromstring(text)
    interfaces = document.findall("./interface")
    assert len(interfaces) == 1, "a second interface needs its own docking qualification"
    scripts = interfaces[0].findall("./script")
    assert len(scripts) == 1
    tree = ast.parse(scripts[0].text or "")
    assert _panel_import_names(tree, require_static=True) == {SHIPPED}
    entry = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "onCreateInterface"]
    assert len(entry) == 1
    imports = [node for node in ast.walk(entry[0]) if isinstance(node, ast.ImportFrom)
               and node.module == "synapse.panel.synapse_panel"]
    assert len(imports) == 1 and [(a.name, a.asname) for a in imports[0].names] == [
        ("onCreateInterface", "_build")]
    body = entry[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # entry docstring
    assert len(body) == 1 and isinstance(body[0], ast.Try), "entry must call the shipped builder"
    attempt = body[0]
    assert len(attempt.body) == 2 and attempt.body[0] is imports[0], "entry must call the shipped builder"
    returned = attempt.body[1]
    assert (isinstance(returned, ast.Return) and isinstance(returned.value, ast.Call)
            and isinstance(returned.value.func, ast.Name) and returned.value.func.id == "_build"
            and not returned.value.args and not returned.value.keywords
            and not attempt.orelse and not attempt.finalbody), "entry must call the shipped builder"


def reachable_panel_modules(start=SHIPPED):
    """Transitive closure of synapse.panel modules the shipped panel can import."""
    seen, frontier = set(), [start]
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _module_path(name)
        if path is None:
            continue
        frontier.extend(_direct_imports(path) - seen)
    return seen


def test_the_only_pypanel_builds_the_shipped_panel():
    files = sorted(PYPANELS.glob("*.pypanel"))
    assert len(files) == 1, "the shipped interface has one .pypanel loader"
    for file in files:
        _assert_shipped_loader(file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("addition", [
    "from synapse.panel.chat_panel import SynapseChatPanel",
    "from synapse.panel import quick_actions",
    "def hidden():\n    import synapse.panel.chat_panel as alternate",
    "import importlib\nimportlib.import_module('synapse.panel.chat_panel')",
    "from importlib import import_module as load\nload('synapse.panel.chat_panel')",
    "__import__('synapse.panel.quick_actions')",
    "import builtins\nbuiltins.__import__('synapse.panel.chat_panel')",
    "def hidden():\n    import builtins\n    builtins.__import__('synapse.panel.chat_panel')",
    "from builtins import __import__ as load\nload('synapse.panel.chat_panel')",
    "import importlib\nimportlib.import_module(selected_panel)",
])
def test_loader_guard_rejects_alternate_imports_even_inside_functions(addition):
    original = (PYPANELS / "synapse_panel.pypanel").read_text(encoding="utf-8")
    mutated = original.replace("]]></script>", addition + "\n]]></script>", 1)
    with pytest.raises(AssertionError):
        _assert_shipped_loader(mutated)


def test_loader_guard_ignores_retained_owner_names_but_requires_the_builder_call():
    original = (PYPANELS / "synapse_panel.pypanel").read_text(encoding="utf-8")
    _assert_shipped_loader(original)  # connections is a retained owner, not a builder
    with pytest.raises(AssertionError, match="shipped builder"):
        _assert_shipped_loader(original.replace("return _build()", "return None", 1))


@pytest.mark.parametrize("replacement", [
    "return None\n        return _build()",
    "def unused():\n            return _build()\n        return None",
    "_build = lambda: None\n        return _build()",
])
def test_loader_guard_rejects_a_dead_or_replaced_builder_call(replacement):
    original = (PYPANELS / "synapse_panel.pypanel").read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="shipped builder"):
        _assert_shipped_loader(original.replace("return _build()", replacement, 1))


def test_shipped_panel_never_reaches_the_alternate_entry():
    reachable = reachable_panel_modules()
    assert SHIPPED in reachable and "designsystem" in reachable
    assert "chat_panel" not in reachable, sorted(reachable)
    assert "quick_actions" not in reachable, sorted(reachable)


def test_every_docking_exempt_module_is_unreachable_from_the_shipped_panel():
    from test_panel_rhythm_docking import DOCKING_EXEMPT_UNSHIPPED

    reachable = reachable_panel_modules()
    exempt = {region.split(".")[0] for region, _ in DOCKING_EXEMPT_UNSHIPPED}
    assert exempt, "the exemption list is empty; nothing to pin"
    leaked = sorted(exempt & reachable)
    assert not leaked, (
        "exemption premise broken: %r is reachable from the shipped panel, so "
        "the docking test must measure it again" % leaked)


def test_import_walker_sees_nested_and_relative_imports(tmp_path):
    (tmp_path / "probe.py").write_text(
        "def build():\n    from synapse.panel.tool_palette import ToolPalette\n"
        "import synapse.panel.recall_card\n", encoding="utf-8")
    assert _direct_imports(tmp_path / "probe.py") == {"tool_palette", "recall_card"}
    assert "designsystem" in _direct_imports(PANEL / "recall_card.py")
