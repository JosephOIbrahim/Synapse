"""The older help pages name the buttons the panel and shelf actually carry."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELP = ROOT / "docs" / "help"
PANEL = (ROOT / "python" / "synapse" / "panel" / "synapse_panel.py").read_text(encoding="utf-8")
SHELF = (ROOT / "houdini" / "toolbar" / "synapse.shelf").read_text(encoding="utf-8")


def _page(name):
    return (HELP / name).read_text(encoding="utf-8")


def test_events_page_names_the_updates_button():
    text = _page("events.md")
    assert 'c.Button("Updates"' in PANEL
    assert "Open **Updates** below the prompt" in text
    assert "Open **Events**" not in text
    assert "Opening Events" not in text
    # the slash command is still real
    assert '"/events"' in PANEL and "`/events`" in text


def test_commands_page_names_the_footer_buttons():
    text = _page("commands.md")
    for label in ("Commands", "Saved networks", "Updates"):
        assert 'Button("%s"' % label in PANEL
    assert "Commands, Saved networks and Updates stay below the composer" in text
    assert "Commands, Recipes and Events" not in text


def test_docking_page_names_the_shelf_label():
    text = _page("panel_docking.md")
    assert '<tool name="synapse_panel" label="Synapse"' in SHELF
    assert "**Synapse** button" in text
    assert "Open Synapse Panel" not in text
