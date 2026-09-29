"""BP12 item 22: the older synapse.ui panel is retired (2026-09-29).

It was exported as synapse.SynapsePanel / NexusPanel / create_panel, shared a class name with the panel
Houdini registers, and nothing shipped built it. Its Clear All button was the only caller of
MemoryStore.clear(). These tests keep it from coming back by accident.
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "python" / "synapse"
RETIRED = ("SynapsePanel", "NexusPanel", "create_panel", "UI_AVAILABLE")


def test_the_older_panel_tree_has_no_python_files():
    assert not [p for p in (PKG / "ui").rglob("*.py")], "python/synapse/ui is retired; do not add to it"


@pytest.mark.parametrize("name", RETIRED)
def test_retired_exports_raise_with_a_pointer_to_the_live_panel(name):
    import synapse

    with pytest.raises(AttributeError) as info:
        getattr(synapse, name)
    assert "synapse.panel.synapse_panel" in str(info.value)
    assert name not in synapse.__all__


def test_the_registered_pane_loads_the_v9_panel_and_never_the_older_one():
    loader = (ROOT / "houdini" / "python_panels" / "synapse_panel.pypanel").read_text(encoding="utf-8")
    assert "synapse.panel.synapse_panel" in loader
    assert "synapse.ui" not in loader
