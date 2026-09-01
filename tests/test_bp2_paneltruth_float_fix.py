"""BP2-PANELTRUTH T3 — the shelf opens the panel DOCKED, not floating.

``houdini/scripts/python/synapse_shelf.py::open_panel`` used to
``createFloatingPaneTab`` whenever no PythonPanel pane existed — a loose window
that a Houdini restart loses unless the desktop is saved. The fix prefers a
docked home, in three branches, and this test drives ``open_panel`` against a
mocked ``hou`` to prove each one:

  1. an existing Synapse tab is SURFACED (setIsCurrentTab), never re-created;
  2. otherwise a PythonPanel tab is docked into the Network Editor's pane
     (pane.createTab + setActiveInterface);
  3. a floating window appears ONLY when there is no pane to dock into.

Pure stdlib — it never imports a real ``hou`` (a stub loads the module; a
purpose-built fake drives the call) and never imports Qt. Mirrors the
``tests/test_shelf_current.py`` load idiom (hou is restored by object, never
evicted — the suite-wide hou-reimport rule).
"""

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHELF_PY = REPO / "houdini" / "scripts" / "python" / "synapse_shelf.py"


def _load_shelf():
    """Import synapse_shelf under a minimal stub ``hou`` (enough for the module
    body's ``import hou`` + the ``_notify`` default arg), restoring the prior
    resident by object — eviction is banned suite-wide (test_hou_reimport_guard)."""
    prior = sys.modules.get("hou")
    stub = types.ModuleType("hou")
    stub.severityType = types.SimpleNamespace(Message=0, Warning=1, Error=2)
    sys.modules["hou"] = stub
    try:
        spec = importlib.util.spec_from_file_location(
            "synapse_shelf_floatfix_undertest", SHELF_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.modules["hou"] = prior
    return mod


# --------------------------------------------------------------------------- #
# Fake hou — only the surface open_panel reaches for.
# --------------------------------------------------------------------------- #

class _Iface:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _PaneTab:
    def __init__(self, ttype, iface=None, pane=None):
        self._type = ttype
        self._iface = iface
        self._pane = pane
        self.surfaced = 0
        self.set_ifaces = []

    def type(self):
        return self._type

    def activeInterface(self):
        return self._iface

    def setActiveInterface(self, iface):
        self.set_ifaces.append(iface)

    def setIsCurrentTab(self):
        self.surfaced += 1

    def pane(self):
        return self._pane


class _Pane:
    def __init__(self, ptt):
        self._ptt = ptt
        self.created = []

    def createTab(self, ttype):
        tab = _PaneTab(ttype, pane=self)
        self.created.append(tab)
        return tab


class _Desktop:
    def __init__(self, ptt, tabs=(), panes=()):
        self._tabs = list(tabs)
        self._panes = list(panes)
        self.floated = []

    def paneTabs(self):
        return list(self._tabs)

    def paneTabOfType(self, ttype):
        for t in self._tabs:
            if t.type() == ttype:
                return t
        return None

    def panes(self):
        return list(self._panes)

    def createFloatingPaneTab(self, ttype, size=None):
        tab = _PaneTab(ttype)
        self.floated.append((tab, size))
        return tab


def _fake_hou(desktop_factory):
    ptt = types.SimpleNamespace(PythonPanel="PythonPanel",
                                NetworkEditor="NetworkEditor")
    iface = _Iface("synapse_panel")
    hou = types.ModuleType("hou")
    hou.paneTabType = ptt
    hou.severityType = types.SimpleNamespace(Message=0, Warning=1, Error=2)
    hou.findFile = lambda *a, **k: "python_panels/synapse_panel.pypanel"
    hou.pypanel = types.SimpleNamespace(
        interfacesInFile=lambda *a, **k: [iface],
        interfaces=lambda: [iface],
        installFile=lambda *a, **k: None,
    )
    desktop = desktop_factory(ptt, iface)
    hou.ui = types.SimpleNamespace(curDesktop=lambda: desktop)
    hou._desktop = desktop            # test handle
    hou._iface = iface
    hou._ptt = ptt
    return hou


def _run(desktop_factory):
    shelf = _load_shelf()
    hou = _fake_hou(desktop_factory)
    shelf.hou = hou                   # rebind the module global for the call
    shelf.open_panel()
    return hou


# --------------------------------------------------------------------------- #
# Branch 1 — an existing Synapse tab is surfaced, not re-created.
# --------------------------------------------------------------------------- #

def test_existing_synapse_tab_is_surfaced():
    existing = {}

    def factory(ptt, iface):
        tab = _PaneTab(ptt.PythonPanel, iface=iface)
        existing["tab"] = tab
        # a Network Editor also exists — it must NOT be used when a Synapse tab is
        net_pane = _Pane(ptt)
        net = _PaneTab(ptt.NetworkEditor, pane=net_pane)
        existing["net_pane"] = net_pane
        return _Desktop(ptt, tabs=[tab, net], panes=[net_pane])

    hou = _run(factory)
    assert existing["tab"].surfaced == 1                # surfaced
    assert existing["tab"].set_ifaces == []             # not re-set
    assert existing["net_pane"].created == []           # no docked tab created
    assert hou._desktop.floated == []                   # never floated


# --------------------------------------------------------------------------- #
# Branch 2 — dock into the Network Editor's pane.
# --------------------------------------------------------------------------- #

def test_docks_into_network_editor_pane():
    handles = {}

    def factory(ptt, iface):
        net_pane = _Pane(ptt)
        net = _PaneTab(ptt.NetworkEditor, pane=net_pane)
        handles["net_pane"] = net_pane
        return _Desktop(ptt, tabs=[net], panes=[net_pane])

    hou = _run(factory)
    net_pane = handles["net_pane"]
    assert len(net_pane.created) == 1                   # a PythonPanel tab docked
    docked = net_pane.created[0]
    assert docked.type() == hou._ptt.PythonPanel
    assert docked.set_ifaces == [hou._iface]            # set to the synapse panel
    assert docked.surfaced == 1                         # brought forward
    assert hou._desktop.floated == []                   # never floated


# --------------------------------------------------------------------------- #
# Branch 3 — float ONLY when there is no pane to dock into.
# --------------------------------------------------------------------------- #

def test_floats_only_when_no_panes_exist():
    def factory(ptt, iface):
        return _Desktop(ptt, tabs=[], panes=[])         # nothing to dock into

    hou = _run(factory)
    assert len(hou._desktop.floated) == 1               # floated as last resort
    tab, size = hou._desktop.floated[0]
    assert tab.type() == hou._ptt.PythonPanel
    assert size == (320, 600)
    assert tab.set_ifaces == [hou._iface]


# --------------------------------------------------------------------------- #
# Guard — panes exist but no Network Editor and no Synapse tab: dock, don't float
# ("float ONLY if no panes exist").
# --------------------------------------------------------------------------- #

def test_docks_into_any_pane_when_no_network_editor():
    handles = {}

    def factory(ptt, iface):
        some_pane = _Pane(ptt)
        handles["pane"] = some_pane
        return _Desktop(ptt, tabs=[], panes=[some_pane])

    hou = _run(factory)
    assert len(handles["pane"].created) == 1            # docked into the pane
    assert hou._desktop.floated == []                   # never floated
