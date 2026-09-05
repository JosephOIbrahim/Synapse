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


def _direct_imports(path):
    """Every synapse.panel.* module a source file imports, at any depth of nesting."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = set()
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
            elif node.level == 1 and path.parent == PANEL:
                # `from .x import y` / `from . import x` inside the panel package
                if parts:
                    found.add(parts[0])
                else:
                    found.update(alias.name for alias in node.names)
    return {name for name in found if _module_path(name) is not None}


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
    assert files, "no .pypanel under houdini/python_panels"
    for file in files:
        text = file.read_text(encoding="utf-8")
        modules = set(re.findall(r"synapse\.panel\.([A-Za-z_][A-Za-z0-9_]*)", text))
        # designsystem is named in a comment about the token authority only.
        assert modules - {"designsystem"} == {SHIPPED}, (file.name, modules)
        assert "from synapse.panel.synapse_panel import onCreateInterface" in text


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
