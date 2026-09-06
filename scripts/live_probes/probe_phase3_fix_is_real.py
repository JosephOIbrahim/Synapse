"""Negative control: the real layout probe must catch reversed input ordering."""
import importlib.util
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
import hou
import synapse.server.handlers_solaris_graph as graph

assert not hou.isUIAvailable(), "This destructive negative control is headless-only"
spec = importlib.util.spec_from_file_location("phase3", Path(__file__).with_name("probe_phase3_layout.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
original = graph._compute_dag_positions

def reversed_inputs(*args, **kwargs):
    return {nid: (-x, y) for nid, (x, y) in original(*args, **kwargs).items()}

graph._compute_dag_positions = reversed_inputs
try:
    result = probe.main()
    assert result == 1, "The layout probe failed to catch deliberately reversed input order"
finally:
    graph._compute_dag_positions = original
    for node in hou.node("/stage").children():
        node.destroy()
print("PROBE VALID: reversed input order was detected on real Houdini nodes")
