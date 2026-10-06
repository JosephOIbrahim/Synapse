"""HOM-6: hou.expandString is deprecated; call hou.text.expandString.

Text-level check, no Houdini. Two sites (solaris_compose_tools line ~145 and
lookdev_suggestion) stay on the old call because existing test stand-ins
(test_compose_offmain_wp3, test_rsi_stage0_panel) only provide it.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "python" / "synapse"


def _read(rel):
    return (PKG / rel).read_text(encoding="utf-8")


def test_cross_scene_uses_text_expandstring():
    src = _read("panel/cross_scene.py")
    assert "hou.expandString(" not in src
    assert 'hou.text.expandString("$JOB")' in src


def test_compose_preflight_uses_text_expandstring():
    src = _read("server/solaris_compose_tools.py")
    assert 'hasattr(hou, "expandString")' not in src
    assert "hou.text.expandString(pn)" in src


def test_symbol_table_has_text_expandstring():
    table = PKG / "cognitive" / "tools" / "data" / "h22_symbol_table.json"
    symbols = json.loads(table.read_text(encoding="utf-8"))["symbols"]
    assert "hou.text.expandString" in symbols
