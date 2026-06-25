"""Goalpost -- .synapse/hytest.py must support a MATRIX of Houdini builds.

Contract: hython-matrix (H-MATRIX). Encodes the goal:

    SYNAPSE_HYTHONS (comma/semicolon list of version tokens like
    "21.0.671,21.0.729" or full hython paths) -> run the given pytest selector
    under EACH resolved+usable build; pass IFF ALL pass. A TARGETED build that
    is unresolvable or unusable (no pytest+PySide) is a HARD ERROR, never a
    silent skip. SYNAPSE_HYTHONS unset -> today's single-best behavior unchanged.

PURE PYTHON by design: these exercise the shim's OWN parsing + aggregation
logic. We monkeypatch the shim's hython-resolution + per-build run functions so
NO real hython is ever spawned -- the test is a true pass/fail under stock
`pytest -q` (no PySide, no QApplication, no false-green-via-skip).

hytest.py is a script, not on the import path, so it is loaded via
importlib.util.spec_from_file_location.

The matrix entry points do NOT exist yet. To stay an ASSERTION (never an
AttributeError), every not-yet-built symbol is reached via getattr(..., None)
and asserted on. Both tests FAIL NOW for the right reason (matrix logic absent)
and PASS only once the shim grows the matrix support.
"""

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_HYTEST = os.path.join(_ROOT, ".synapse", "hytest.py")


def _load_hytest():
    """Load .synapse/hytest.py as a fresh module object (it is a script, not on
    the import path). A fresh load per call keeps monkeypatches from leaking
    between tests."""
    spec = importlib.util.spec_from_file_location("synapse_hytest_under_test", _HYTEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _first_attr(mod, names):
    """Return the first attribute on `mod` whose name is in `names` and is
    callable, else None. Lets the worker pick any reasonable name without the
    goalpost dictating one exact identifier."""
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            return fn
    return None


# Candidate names for the SYNAPSE_HYTHONS -> targets parser. The worker may name
# it any of these; the goalpost only requires that ONE exists and behaves.
_PARSER_NAMES = (
    "_matrix_targets", "_targets", "_parse_matrix", "_parse_hythons",
    "_split_targets", "matrix_targets",
)

# Candidate names for "run the selector under one resolved build, return an int
# return code" -- the per-build leaf the matrix aggregates over.
_RUN_ONE_NAMES = (
    "_run_one", "_run_build", "_run_under", "_run_selector", "run_one",
)

# Candidate names for "resolve a single target token/path to a usable hython
# path, else None". The matrix maps targets through this before running.
_RESOLVE_NAMES = (
    "_resolve_target", "_resolve", "_resolve_hython", "resolve_target",
)

# Candidate names for the top-level matrix driver returning an aggregate int
# return code (0 == all passed).
_MATRIX_RUN_NAMES = (
    "_run_matrix", "run_matrix", "_matrix_run", "_run_all", "matrix_main",
)


def test_matrix_targets_parsed():
    """The shim exposes a parser that splits SYNAPSE_HYTHONS into MULTIPLE
    targets across both comma and semicolon separators. FAILS now -- no such
    parser exists; the assertion (not an AttributeError) reports the gap."""
    mod = _load_hytest()
    parser = _first_attr(mod, _PARSER_NAMES)
    assert parser is not None, (
        "hytest.py exposes no SYNAPSE_HYTHONS parser -- expected one of %r. "
        "The matrix needs a function that splits the env list into targets."
        % (_PARSER_NAMES,)
    )

    # Comma-separated version tokens -> two distinct targets.
    comma = list(parser("21.0.671,21.0.729"))
    assert len(comma) == 2, (
        "comma list '21.0.671,21.0.729' must parse to 2 targets, got %r" % (comma,))
    joined = "|".join(str(t) for t in comma)
    assert "21.0.671" in joined and "21.0.729" in joined, (
        "both build tokens must survive parsing, got %r" % (comma,))

    # Semicolon separator is also accepted (the goal names comma/semicolon).
    semi = list(parser("21.0.671;21.0.729"))
    assert len(semi) == 2, (
        "semicolon list '21.0.671;21.0.729' must parse to 2 targets, got %r" % (semi,))

    # Whitespace + a trailing empty segment must not create phantom targets.
    messy = list(parser(" 21.0.671 , 21.0.729 , "))
    assert len(messy) == 2, (
        "stray whitespace / trailing separator must not add empty targets, got %r"
        % (messy,))


def test_matrix_aggregates_all_pass():
    """Running the selector across two targeted builds passes IFF BOTH succeed;
    any per-build failure -- and any unusable/unresolvable TARGETED build --
    fails the whole run (hard error, never a silent skip).

    Pure-python: we monkeypatch the shim's per-build resolution + run so no real
    hython is spawned. getattr-guarded; FAILS now (no matrix driver / no
    resolve seam to monkeypatch)."""
    mod = _load_hytest()

    matrix_run = _first_attr(mod, _MATRIX_RUN_NAMES)
    run_one = _first_attr(mod, _RUN_ONE_NAMES)
    resolve = _first_attr(mod, _RESOLVE_NAMES)

    assert matrix_run is not None, (
        "hytest.py exposes no matrix driver -- expected one of %r returning an "
        "aggregate int return code (0 == all builds passed)." % (_MATRIX_RUN_NAMES,))
    assert run_one is not None, (
        "hytest.py exposes no per-build run seam -- expected one of %r so the "
        "matrix can be exercised without spawning real hython." % (_RUN_ONE_NAMES,))
    assert resolve is not None, (
        "hytest.py exposes no per-target resolver -- expected one of %r so an "
        "unresolvable TARGETED build can be made a hard error, not a skip."
        % (_RESOLVE_NAMES,))

    # --- fakes: resolution maps a target token -> a fake hython path (or None
    # for an unresolvable/unusable target); run maps a fake path -> a return code.
    resolved = {"buildA": "/fake/A/hython", "buildB": "/fake/B/hython"}
    rc_by_path = {"/fake/A/hython": 0, "/fake/B/hython": 0}

    run_calls = []

    def fake_resolve(target, *a, **k):
        return resolved.get(target)

    def fake_run_one(hython, argv, *a, **k):
        run_calls.append(hython)
        return rc_by_path.get(hython, 0)

    # Patch by whatever real names the shim chose (matches the getattr above).
    setattr(mod, resolve.__name__, fake_resolve)
    setattr(mod, run_one.__name__, fake_run_one)

    selector = ["tests/panel/test_hython_matrix.py::test_matrix_targets_parsed"]

    # 1) Both builds pass -> aggregate success (rc 0), and BOTH builds ran.
    run_calls.clear()
    rc_all = matrix_run(["buildA", "buildB"], selector)
    assert rc_all == 0, (
        "matrix must return 0 when every targeted build passes, got %r" % (rc_all,))
    assert len(run_calls) == 2, (
        "every targeted build must actually be run (no short-circuit on first "
        "pass), got %d run(s): %r" % (len(run_calls), run_calls))

    # 2) One build fails -> aggregate failure (nonzero).
    rc_by_path["/fake/B/hython"] = 1
    run_calls.clear()
    rc_one_fail = matrix_run(["buildA", "buildB"], selector)
    assert rc_one_fail != 0, (
        "matrix must FAIL (nonzero) when any targeted build fails, got %r"
        % (rc_one_fail,))
    rc_by_path["/fake/B/hython"] = 0  # restore

    # 3) A TARGETED build that won't resolve is a HARD ERROR -- nonzero, never a
    #    silent skip that aggregates to 0.
    run_calls.clear()
    rc_unresolvable = matrix_run(["buildA", "ghost-build"], selector)
    assert rc_unresolvable != 0, (
        "an unresolvable/unusable TARGETED build must be a hard error (nonzero), "
        "never a silent skip aggregating to 0, got %r" % (rc_unresolvable,))
