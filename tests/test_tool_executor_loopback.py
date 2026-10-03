"""The panel's tool dispatch connects to the numeric loopback address first.

On Windows "localhost" resolves to ::1 before 127.0.0.1. Against an IPv4-only
listener each connect then waits about 2 s before falling back, and the panel
opens one connection per tool call (measured 2026-10-03: 2.01 s vs 0.009 s).
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "python" / "synapse" / "panel" / "tool_executor.py"


def _tree():
    return ast.parse(SRC.read_text(encoding="utf-8"))


def test_numeric_loopback_is_tried_first():
    hosts = None
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "loopback_hosts" for t in node.targets):
            hosts = ast.literal_eval(node.value)
    assert hosts == ("127.0.0.1", "localhost")


def test_no_connection_is_opened_to_a_literal_hostname():
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "HTTPConnection":
            first = node.args[0]
            assert not isinstance(first, ast.Constant), "HTTPConnection must take its host from loopback_hosts"
