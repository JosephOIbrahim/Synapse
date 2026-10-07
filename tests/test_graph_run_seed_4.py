"""F01 (IR-03): the stdio MCP adapter's install line installs the pinned set.

pyproject.toml pins mcp==1.26.0 because mcp>=1.27 dropped the
Server.list_tools()/call_tool() decorators mcp_server.py uses. The module
docstring must not tell a reader to install the unpinned latest mcp.
Read by ast, never imported: importing would need the mcp package.
"""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "mcp_server.py"


def _install_line() -> str:
    doc = ast.get_docstring(ast.parse(_SRC.read_text(encoding="utf-8"))) or ""
    lines = [ln for ln in doc.splitlines() if ln.strip().startswith("Install:")]
    assert len(lines) == 1, lines
    return lines[0]


def test_install_line_uses_the_pinned_extra():
    line = _install_line()
    assert '-e ".[mcp]"' in line


def test_install_line_does_not_install_unpinned_mcp():
    assert "pip install mcp websockets" not in _install_line()
