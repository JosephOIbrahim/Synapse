"""HOM-2: every hou.nodeEventType.<Name> the Houdini hooks use must exist in H22."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "synapse" / "hooks" / "synapse_hooks_houdini.py"
TABLE = ROOT / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"


def _collect_names():
    text = HOOKS.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"hou\.nodeEventType\.(\w+)", text)))


def test_collector_finds_names():
    assert len(_collect_names()) >= 4


def test_node_event_names_exist_in_h22():
    symbols = set(json.loads(TABLE.read_text(encoding="utf-8"))["symbols"])
    missing = [n for n in _collect_names() if f"hou.nodeEventType.{n}" not in symbols]
    assert not missing, f"not in H22 symbol table: {missing}"
