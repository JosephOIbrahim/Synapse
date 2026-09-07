"""Exercise the actual shelf function at the native pane-creation boundary.

H22's default Python Panel can retain its initial minimum width after an
interface switch. The intended interface must therefore reach the *factory*,
before any default QuickStart interface is created. No Qt or live HOM is used.
"""
import importlib.util
from pathlib import Path
import sys
import types

import pytest


SHELF = Path(__file__).resolve().parents[1] / "houdini/scripts/python/synapse_shelf.py"
PYTHON_PANEL = "PythonPanel"
NETWORK_EDITOR = "NetworkEditor"


class Interface:
    def __init__(self, name): self._name = name
    def name(self): return self._name


class Tab:
    def __init__(self, kind, interface=None, pane=None):
        self.kind, self.interface, self.parent_pane = kind, interface, pane
        self.current_calls, self.switches = 0, []
    def type(self): return self.kind
    def activeInterface(self): return self.interface
    def pane(self): return self.parent_pane
    def setIsCurrentTab(self): self.current_calls += 1
    def setActiveInterface(self, interface):
        self.switches.append(interface.name())
        self.interface = interface


class Pane:
    def __init__(self, desktop, name):
        self.desktop, self.name = desktop, name
    def createTab(self, kind, python_panel_interface=None):
        return self.desktop.create(kind, python_panel_interface, pane=self)


class Desktop:
    def __init__(self): self.tabs, self.pane_list, self.created = [], [], []
    def paneTabs(self): return tuple(self.tabs)
    def paneTabOfType(self, kind): return next((tab for tab in self.tabs if tab.kind == kind), None)
    def panes(self): return tuple(self.pane_list)
    def create(self, kind, interface, *, pane=None, size=None):
        tab = Tab(kind, Interface(interface or "__default_quickstart__"), pane)
        self.created.append({"kind": kind, "interface_at_creation": interface,
                             "pane": pane, "size": size, "tab": tab})
        self.tabs.append(tab)
        return tab
    def createFloatingPaneTab(self, kind, size=None, python_panel_interface=None):
        return self.create(kind, python_panel_interface, size=size)


def load_shelf(surface="network", *, missing=False):
    desktop = Desktop()
    fallback = Pane(desktop, "other")
    network = Pane(desktop, "network")
    if surface == "network":
        # Network Editor wins even when another pane is listed first.
        desktop.pane_list = [fallback, network]
        desktop.tabs.append(Tab(NETWORK_EDITOR, pane=network))
    elif surface == "other_pane": desktop.pane_list = [fallback]
    host = types.ModuleType("hou")
    host.paneTabType = types.SimpleNamespace(PythonPanel=PYTHON_PANEL, NetworkEditor=NETWORK_EDITOR)
    host.severityType = types.SimpleNamespace(Message=0, Warning=1, Error=2)
    host.findFile = lambda path: "C:/fixture/" + path
    installs, warnings = [], []
    host.pypanel = types.SimpleNamespace(
        interfacesInFile=lambda path: [Interface("unrelated" if missing else "synapse_panel")],
        installFile=lambda path: installs.append(path),
        interfaces=lambda: {},  # Native interfaces() is a dictionary.
    )
    host.ui = types.SimpleNamespace(curDesktop=lambda: desktop,
        displayMessage=lambda message, **kwargs: warnings.append({"message": message, **kwargs}))
    resident = sys.modules.get("hou")
    sys.modules["hou"] = host
    try:
        spec = importlib.util.spec_from_file_location("synapse_shelf_creation_under_test", SHELF)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        # Restore by object; never evict the shared/real HOM module.
        sys.modules["hou"] = resident
    assert sys.modules.get("hou") is resident
    return module, desktop, installs, warnings


@pytest.mark.parametrize("surface", ["network", "other_pane", "floating"])
def test_first_creation_receives_synapse_interface(surface):
    shelf, desktop, installs, warnings = load_shelf(surface)
    shelf.open_panel()
    assert len(desktop.created) == 1
    created = desktop.created[0]
    assert created["kind"] == PYTHON_PANEL
    assert created["interface_at_creation"] == "synapse_panel"
    assert created["tab"].switches == []
    if surface == "floating":
        assert created["pane"] is None and created["size"] == (320, 600)
    else:
        assert created["pane"].name == ("network" if surface == "network" else "other")
        assert created["tab"].current_calls == 1
    assert installs == [] and warnings == []


@pytest.mark.parametrize("surface", ["network", "floating"])
def test_second_open_reuses_the_created_interface(surface):
    shelf, desktop, installs, warnings = load_shelf(surface)
    shelf.open_panel()
    tab = desktop.created[0]["tab"]
    before = tab.current_calls
    shelf.open_panel()
    assert len(desktop.created) == 1
    assert tab.current_calls == before + 1
    assert warnings == []


def test_existing_synapse_tab_wins_over_other_panes_without_recreation():
    shelf, desktop, installs, warnings = load_shelf()
    existing = Tab(PYTHON_PANEL, Interface("synapse_panel"))
    desktop.tabs.append(existing)
    shelf.open_panel()
    assert existing.current_calls == 1 and existing.switches == []
    assert desktop.created == [] and installs == [] and warnings == []


def test_other_python_interface_is_not_reused_or_replaced():
    shelf, desktop, installs, warnings = load_shelf("other_pane")
    other = Tab(PYTHON_PANEL, Interface("another_tool"))
    desktop.tabs.append(other)
    shelf.open_panel()
    assert len(desktop.created) == 1
    assert desktop.created[0]["interface_at_creation"] == "synapse_panel"
    assert other.current_calls == 0 and other.switches == []


def test_unavailable_interface_preserves_warning_and_creates_nothing():
    shelf, desktop, installs, warnings = load_shelf(missing=True)
    shelf.open_panel()
    assert installs == ["C:/fixture/python_panels/synapse_panel.pypanel"]
    assert desktop.created == []
    assert len(warnings) == 1 and warnings[0]["severity"] == 1
    assert warnings[0]["title"] == "Synapse Panel"
    assert "Couldn't find the Synapse panel" in warnings[0]["message"]
