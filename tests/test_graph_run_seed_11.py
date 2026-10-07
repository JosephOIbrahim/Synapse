"""F06 (SC-8): execute_python's docstring states its real undo behavior.

It used to promise "undo-wrapped and reversible". Rollback runs only for
_ROLLBACK_ERRORS (coding errors); operational errors keep partial work,
and atomic=False runs with no undo group at all. Read by ast so the test
needs no hou stub.
"""

import ast
from pathlib import Path

_SRC = (Path(__file__).resolve().parent.parent
        / "python" / "synapse" / "server" / "handlers.py")


def _doc() -> str:
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == "SynapseHandler":
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "_handle_execute_python":
                    return ast.get_docstring(fn) or ""
    raise AssertionError("SynapseHandler._handle_execute_python not found")


def test_docstring_does_not_promise_reversibility():
    assert "undo-wrapped and reversible" not in _doc()


def test_docstring_names_the_partial_rollback_and_atomic_false():
    doc = _doc()
    assert "operational errors keep" in doc
    assert "atomic=False runs ungrouped" in doc
