"""Qt-free honesty source-pin for the gate widget's fidelity row (FID).

``gate_widget.py`` hard-imports PySide, so every behavioural test of this row
SKIPS under the stock dev interpreter — and a skip exits 0, which CI reads as
passing. That is the Law-1 failure mode: a check that cannot run is a
decoration that will be cited as evidence. This file parses the source with
``ast`` — no Qt import, no widget — so the invariant is pinned on EVERY
interpreter.

The invariant: **a fidelity that was never observed can never render as a
number, and can never paint green.**

The defect it pins, verbatim from the pre-fix source:

    self._fidelity_label = QtWidgets.QLabel("Fidelity 1.0")   # constructed
    fidelity = report.get("session_fidelity", 1.0)            # defaulted in
    self._fidelity_label.setText("Fidelity {f:.1f}".format(f=fidelity))

Mirrors ``tests/test_panel_fidelity_honesty_sourcepin.py``, which pins the same
rule for ``integrity_readout.py``.
"""

import ast
import pathlib

import pytest

_GATE_WIDGET = (
    pathlib.Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "panel" / "gate_widget.py"
)


def _module():
    return ast.parse(_GATE_WIDGET.read_text(encoding="utf-8"))


def _attr_name(node):
    """``t.GROW`` -> ``"GROW"``; anything else -> None."""
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


def _is_unmeasured_guard(test):
    """True if ``test`` is an ``is None`` check on ``fidelity`` — the guard that
    must precede every coloured verdict."""
    for cmp in ast.walk(test):
        if (isinstance(cmp, ast.Compare)
                and isinstance(cmp.left, ast.Name) and cmp.left.id == "fidelity"
                and len(cmp.ops) == 1 and isinstance(cmp.ops[0], ast.Is)
                and isinstance(cmp.comparators[0], ast.Constant)
                and cmp.comparators[0].value is None):
            return True
    return False


def _defaulted_get_calls(tree, key):
    """Every ``<x>.get("<key>", <default>)`` — a two-arg get is a fabricated
    default on the way in."""
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == key):
            hits.append(node)
    return hits


# ── the feeder: no fabricated default on the way in ──────────────

def test_no_defaulted_get_on_session_fidelity():
    """``report.get("session_fidelity", 1.0)`` is the fabrication itself: an
    absent measurement silently becomes a perfect one.

    FAILS IF: any two-argument ``.get("session_fidelity", ...)`` reappears
    anywhere in the module, with ANY default — 1.0, 0.0 or otherwise. There is
    no honest default for an unmade measurement.
    """
    hits = _defaulted_get_calls(_module(), "session_fidelity")
    assert hits == [], (
        "session_fidelity is read with a default (line %s) — an absent "
        "measurement must render UNKNOWN, never a number"
        % ", ".join(str(h.lineno) for h in hits)
    )


def test_observed_fidelity_helper_exists_and_can_return_none():
    """The reader must be able to say "nobody measured this".

    FAILS IF: ``_observed_fidelity`` is gone, or it has no ``return None`` path —
    a reader that always returns a float has no way to express unmeasured.
    """
    fn = _find_func(_module(), "_observed_fidelity")
    assert fn is not None, "_observed_fidelity must exist — it is the no-default reader"
    none_returns = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Return)
        and isinstance(n.value, ast.Constant) and n.value.value is None
    ]
    assert none_returns, (
        "_observed_fidelity never returns None — it cannot express 'unmeasured'"
    )


# ── the verdict: green only from an observation ──────────────────

def test_fidelity_color_unmeasured_returns_slate_not_green():
    """The FIRST statement of ``_fidelity_color`` is the unmeasured guard, and
    it returns the neutral SLATE token.

    FAILS IF: the guard is removed, reordered below a coloured branch, or
    returns GROW/ERROR — an unmeasured row would then read as a pass (or as a
    failure, which is the same lie pointing the other way).
    """
    fn = _find_func(_module(), "_fidelity_color")
    assert fn is not None, "_fidelity_color must exist"
    first = _first_real_stmt(fn)
    assert isinstance(first, ast.If), "first statement must be the unmeasured guard"
    assert _is_unmeasured_guard(first.test), (
        "the guard must test `fidelity is None` — the unmeasured state"
    )
    guard_returns = [s for s in first.body if isinstance(s, ast.Return)]
    assert guard_returns, "the unmeasured guard must return early"
    assert _attr_name(guard_returns[0].value) == "SLATE", (
        "unmeasured guard must return the honest neutral SLATE token"
    )
    for r in guard_returns:
        assert _attr_name(r.value) not in ("GROW", "ERROR"), (
            "unmeasured guard returns a verdict colour — UNKNOWN is neither a "
            "pass nor a failure"
        )


def _ordered_returns(fn):
    """Every ``return`` in ``fn``, in source order (``ast.walk`` is unordered)."""
    return sorted(
        (n for n in ast.walk(fn) if isinstance(n, ast.Return)),
        key=lambda n: n.lineno,
    )


def test_first_exit_from_fidelity_color_is_the_unmeasured_one():
    """The FIRST way out of ``_fidelity_color`` is SLATE, and every green sits
    below it — so no value reaches a verdict colour before the unmeasured
    question has been asked.

    FAILS IF: a GROW return is hoisted above the guard, which is precisely the
    shape the pre-fix row had — ``dot_color = t.GROW`` decided first, with no
    unmeasured branch existing anywhere.
    """
    fn = _find_func(_module(), "_fidelity_color")
    returns = _ordered_returns(fn)
    assert returns, "_fidelity_color must return something"
    assert _attr_name(returns[0].value) == "SLATE", (
        "the first exit is %r, not the unmeasured SLATE — a verdict colour is "
        "decided before 'was this measured?' is asked"
        % _attr_name(returns[0].value)
    )
    greens = [n for n in returns if _attr_name(n.value) == "GROW"]
    assert greens, "expected a GROW (green) branch — the all-clear state"
    for g in greens:
        assert g.lineno > returns[0].lineno, "a green return precedes the guard"


@pytest.mark.parametrize("func_name", ["_render_fidelity", "update_integrity", "_build_ui"])
def test_writers_delegate_the_colour_and_never_name_green(func_name):
    """No widget-side writer may name GROW itself — the colour decision is
    delegated to ``_fidelity_color`` so the guard cannot be bypassed. This is
    the containment that ``test_set_integrity_delegates_green_to_the_guard``
    enforces on ``integrity_readout``.

    FAILS IF: a writer paints green directly — as ``_build_ui`` did, hardcoding
    ``c=t.GROW`` on the dot before a single operation had run.
    """
    fn = _find_func(_module(), func_name)
    assert fn is not None, "%s must exist" % func_name
    for node in ast.walk(fn):
        assert _attr_name(node) != "GROW", (
            "%s references GROW directly — green must route through "
            "_fidelity_color's unmeasured guard" % func_name
        )


def _literal_scores(tree):
    """String constants that spell a fidelity score outright.

    A digit alone is not the tell — ``"Fidelity {f:.1f}"`` is the legitimate
    format template and carries one. The tell is a digit with NO placeholder:
    nothing can substitute into it, so whatever it claims was typed, not
    measured.
    """
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value.strip().lower().startswith("fidelity ")
        and any(ch.isdigit() for ch in n.value)
        and "{" not in n.value
    ]


def test_no_literal_perfect_score_anywhere_in_the_module():
    """The construct-time literal is gone and stays gone.

    FAILS IF: any string constant spells a fidelity score with no placeholder —
    the original defect was exactly ``QLabel("Fidelity 1.0")``, a perfect score
    typed into the UI before anything could have produced it.
    """
    offenders = _literal_scores(_module())
    assert offenders == [], (
        "a literal fidelity score is present in the source: %r" % (offenders,)
    )


# ── prove the detectors are not vacuous (Law 1) ──────────────────

def test_detectors_actually_bite():
    """Fed the PRE-FIX shapes, every detector above must flag them. A source-pin
    that cannot fail is the decoration Law 1 was written for."""
    bad = ast.parse(
        "def _fidelity_color(fidelity):\n"
        "    if fidelity >= 1.0:\n"
        "        return t.GROW\n"                      # green before any guard
        "    return t.SLATE\n"
        "\n"
        "def update_integrity(self, report):\n"
        "    fidelity = report.get('session_fidelity', 1.0)\n"   # fabricated default
        "    self._fidelity_label.setText('Fidelity 1.0')\n"     # literal score
    )

    # 1. the defaulted get is caught
    assert _defaulted_get_calls(bad, "session_fidelity"), (
        "detector missed a two-arg .get('session_fidelity', 1.0)"
    )

    # 2. the missing unmeasured guard is caught — a `>= 1.0` test is not one
    fn = _find_func(bad, "_fidelity_color")
    first = _first_real_stmt(fn)
    assert not _is_unmeasured_guard(first.test), (
        "detector treated a `>= 1.0` branch as an unmeasured guard"
    )

    # 3. green as the FIRST exit is caught
    returns = _ordered_returns(fn)
    assert _attr_name(returns[0].value) == "GROW", (
        "counterexample must exit green first"
    )
    assert _attr_name(returns[0].value) != "SLATE", (
        "detector would accept a first-exit green as the unmeasured guard"
    )

    # 4. the literal perfect score is caught, and the format template is not
    assert _literal_scores(bad) == ["Fidelity 1.0"], (
        "detector missed the literal construct-time score, saw %r"
        % (_literal_scores(bad),)
    )
    template_only = ast.parse("x = 'Fidelity {f:.1f}'")
    assert _literal_scores(template_only) == [], (
        "detector flags the legitimate format template as a literal score"
    )
