"""Qt-free honesty source-pin for the Mile-4 fidelity readout color mapping.

The readout widget (``IntegrityReadout.set_integrity`` + ``_fidelity_color``)
lives in ``integrity_readout.py``, which hard-imports PySide → the Qt panel
tests SKIP under stock CPython. So a future edit mapping a **no-data** or a
**violation** state to the green (``OK_SOFT``) token would pass CI undetected --
and the panel would paint a green "fidelity 100%" over a session that never ran
or that broke, the exact lie CLAUDE.md's *"fidelity = 1.0 or stop"* guarantee
exists to prevent. This test parses the source (no Qt import) and pins the
invariant: **green is reachable only from a genuine all-clear.** Mirrors
``tests/test_panel_receipt_honesty_sourcepin.py``.
"""

import ast
import pathlib

_INTEGRITY_READOUT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "panel" / "integrity_readout.py"
)


def _module():
    return ast.parse(_INTEGRITY_READOUT.read_text(encoding="utf-8"))


def _attr_name(node):
    """``t.OK_SOFT`` -> ``"OK_SOFT"``; anything else -> None."""
    return node.attr if isinstance(node, ast.Attribute) else None


def _find_func(mod, name):
    for node in ast.walk(mod):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _returns_attr(stmt, name):
    return isinstance(stmt, ast.Return) and _attr_name(stmt.value) == name


def _first_real_stmt(fn):
    """The first statement of ``fn`` that is not a docstring."""
    body = fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1]
    return body[0]


def _is_all_clear_guard(test):
    """True if ``test`` contains a ``violations == 0`` comparison — the guard
    that must gate every green return."""
    for cmp in ast.walk(test):
        if (isinstance(cmp, ast.Compare)
                and isinstance(cmp.left, ast.Name) and cmp.left.id == "violations"
                and len(cmp.ops) == 1 and isinstance(cmp.ops[0], ast.Eq)
                and isinstance(cmp.comparators[0], ast.Constant)
                and cmp.comparators[0].value == 0):
            return True
    return False


def _count_ok_soft(fn):
    """(total OK_SOFT returns, OK_SOFT returns inside a `violations == 0` If)."""
    total = sum(1 for n in ast.walk(fn) if _returns_attr(n, "OK_SOFT"))
    guarded = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and _is_all_clear_guard(node.test):
            for stmt in node.body:
                if _returns_attr(stmt, "OK_SOFT"):
                    guarded += 1
    return total, guarded


def test_fidelity_color_greens_only_all_clear():
    """``_fidelity_color``: every green (OK_SOFT) return is gated by a
    ``violations == 0`` comparison — so a violation state can never be green."""
    fn = _find_func(_module(), "_fidelity_color")
    assert fn is not None, "_fidelity_color must exist"
    total, guarded = _count_ok_soft(fn)
    assert total >= 1, "expected an OK_SOFT (green) branch — the all-clear state"
    assert total == guarded, (
        "OK_SOFT (green) reachable without a `violations == 0` guard -- "
        "a violation could paint green"
    )


def test_fidelity_color_no_data_returns_slate_not_green():
    """The FIRST statement of ``_fidelity_color`` is the ``has_data`` guard and
    it returns SLATE (never green) — a session with no operations must never
    look like a pass. ``session_fidelity`` reads 1.0 at total==0, so without
    this guard the widget would paint a fabricated 100%."""
    fn = _find_func(_module(), "_fidelity_color")
    first = _first_real_stmt(fn)
    assert isinstance(first, ast.If), "first statement must be the has_data guard"
    assert "has_data" in ast.dump(first.test), "the guard must test has_data"
    guard_returns = [s for s in first.body if isinstance(s, ast.Return)]
    assert guard_returns, "the has_data guard must return early"
    for r in guard_returns:
        assert _attr_name(r.value) != "OK_SOFT", (
            "no-data guard returns green OK_SOFT -- a lying 100%"
        )
    assert _attr_name(guard_returns[0].value) == "SLATE", (
        "no-data guard must return the honest SLATE token"
    )


def test_set_integrity_delegates_green_to_the_guard():
    """``set_integrity`` must NOT name OK_SOFT directly — the color decision is
    delegated to ``_fidelity_color`` so the honesty invariant lives in exactly
    one pinned place. A direct green in set_integrity would bypass the guard."""
    fn = _find_func(_module(), "set_integrity")
    assert fn is not None, "set_integrity must exist"
    for node in ast.walk(fn):
        assert _attr_name(node) != "OK_SOFT", (
            "set_integrity references OK_SOFT directly -- green must route "
            "through _fidelity_color's violations==0 guard"
        )


def test_guard_detector_actually_bites():
    """Prove the checker is not vacuous: fed an ``_fidelity_color`` that returns
    green UNGUARDED, ``_count_ok_soft`` must report total != guarded (i.e. the
    real test above would fail on it)."""
    bad = ast.parse(
        "def _fidelity_color(summary):\n"
        "    if not summary.get('has_data'):\n"
        "        return t.SLATE\n"
        "    return t.OK_SOFT\n"          # unguarded green — a lie
    )
    fn = _find_func(bad, "_fidelity_color")
    total, guarded = _count_ok_soft(fn)
    assert total == 1 and guarded == 0, "counterexample must be an unguarded green"
    assert total != guarded, "detector failed to flag an unguarded green -- vacuous"
