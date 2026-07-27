"""Qt-free honesty source-pin for the RETINA receipt verdict->color mapping.

The receipt widget (``FaceReview.set_receipt``) and its color maps live in
``face_review.py``, which hard-imports PySide -> the Qt panel tests SKIP under
stock CPython. So a future edit mapping a FAIL or INCONCLUSIVE verdict to the
green (``CONIFEROUS``) token would pass CI undetected -- and the render receipt
would lie, the exact failure Mile 2 exists to prevent (crucible finding,
2026-07-17). This test parses the source (no Qt import) and pins the invariant:
**green is reachable only from a genuine pass.** Mirrors the BL-007 source-pin
trick used against synapse_panel.py.
"""

import ast
import pathlib

_FACE_REVIEW = (
    pathlib.Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "panel" / "face_review.py"
)


def _module():
    return ast.parse(_FACE_REVIEW.read_text(encoding="utf-8"))


def _attr_name(node):
    """``t.CONIFEROUS`` -> ``"CONIFEROUS"``; anything else -> None."""
    return node.attr if isinstance(node, ast.Attribute) else None


def _find_assign(mod, name):
    for node in ast.walk(mod):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
    return None


def _find_func(mod, name):
    for node in ast.walk(mod):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_receipt_verdict_color_greens_only_a_pass():
    """``_RECEIPT_VERDICT_COLOR``: only 'pass' may be CONIFEROUS; fail/inconclusive
    must not resolve to the green token."""
    d = _find_assign(_module(), "_RECEIPT_VERDICT_COLOR")
    assert isinstance(d, ast.Dict), "_RECEIPT_VERDICT_COLOR must be a dict literal"
    mapping = {}
    for k, v in zip(d.keys, d.values):
        assert isinstance(k, ast.Constant), "verdict keys must be string literals"
        mapping[k.value] = _attr_name(v)
    # the honest mapping, pinned
    assert mapping.get("pass") == "CONIFEROUS"
    assert mapping.get("inconclusive") == "HOT_SOFT"
    assert mapping.get("fail") == "NO_SOFT"
    # the invariant: nothing but 'pass' may be green
    for verdict, color in mapping.items():
        if verdict != "pass":
            assert color != "CONIFEROUS", (
                f"verdict {verdict!r} maps to green CONIFEROUS -- a lying receipt"
            )


def test_receipt_dot_color_greens_only_a_true_pass():
    """``_receipt_dot_color``: CONIFEROUS is returned ONLY under ``passed is True``;
    the default (None/inconclusive) must never be the green token."""
    fn = _find_func(_module(), "_receipt_dot_color")
    assert fn is not None, "_receipt_dot_color must exist"

    green_returns_guarded = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            test = node.test
            is_true_guard = (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name) and test.left.id == "passed"
                and len(test.ops) == 1 and isinstance(test.ops[0], ast.Is)
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value is True
            )
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and _attr_name(stmt.value) == "CONIFEROUS":
                    green_returns_guarded.append(is_true_guard)

    assert green_returns_guarded, "expected a `passed is True -> CONIFEROUS` branch"
    assert all(green_returns_guarded), "CONIFEROUS (green) reachable without `passed is True`"

    # the function's default/last return must not be green (inconclusive != pass)
    returns = [n for n in fn.body if isinstance(n, ast.Return)]
    assert returns, "_receipt_dot_color must have a default return"
    assert _attr_name(returns[-1].value) != "CONIFEROUS", (
        "default dot color is green -- an inconclusive check would look like a pass"
    )
