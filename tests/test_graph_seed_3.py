"""F06: the _ARTIST_COMMANDS frozenset literal must not repeat entries."""

import ast
from pathlib import Path

RBAC = Path(__file__).resolve().parents[1] / "python" / "synapse" / "server" / "rbac.py"


def _artist_literal_elts():
    tree = ast.parse(RBAC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_ARTIST_COMMANDS" for t in targets):
            continue
        call = node.value
        assert isinstance(call, ast.Call) and call.args
        literal = call.args[0]
        assert isinstance(literal, ast.Set)
        return [e.value for e in literal.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    raise AssertionError("_ARTIST_COMMANDS assignment not found in rbac.py")


def test_artist_commands_literal_has_no_duplicates():
    elts = _artist_literal_elts()
    assert elts
    dupes = sorted({e for e in elts if elts.count(e) > 1})
    assert len(elts) == len(set(elts)), f"duplicate entries: {dupes}"
