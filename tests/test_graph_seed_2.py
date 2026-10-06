"""F09: panel tooltips name what their handlers actually do (text-only, no Houdini)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / "python/synapse/panel/synapse_panel.py").read_text(encoding="utf-8")
RENDER = (ROOT / "python/synapse/server/handlers_render.py").read_text(encoding="utf-8")


def test_help_tooltip_names_the_doc_on_help_opens():
    tip = re.search(r"_help_btn\.setToolTip\(\"([^\"]*)\"\)", PANEL).group(1)
    opened = re.search(
        r"def _on_help\(self\):.*?self\._open_doc\(\"([^\"]+)\"\)", PANEL, re.S
    ).group(1)
    assert opened in tip
    assert "UPGRADE.md" not in tip


def test_halt_tooltip_names_every_swept_root():
    sweep = re.search(r"for root in \(([^)]*)\):", RENDER).group(1)
    roots = re.findall(r"\"(/[a-z]+)\"", sweep)
    assert roots
    tip = PANEL[PANEL.index("Cancel PDG cooks under"):][:200]
    for root in roots:
        assert root in tip
