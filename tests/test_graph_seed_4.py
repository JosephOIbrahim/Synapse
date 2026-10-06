"""F08: mcp_server.py must import concurrent.futures at module level."""
import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "mcp_server.py"


def test_concurrent_futures_imported_at_module_level():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "concurrent.futures" in imported


def test_dispatch_executor_has_no_local_import():
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_dispatch_executor"
    )
    local = [n for n in ast.walk(fn) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not local
