"""Regression pins for the SECOND form of fake-`hou` residency (R41/R42/R43).

THE DEFECT, VERIFIED-RUNTIME on Houdini 22.0.368, 2026-07-26:

``hou.py`` must never execute twice in one process. When a test evicts ``hou``
from ``sys.modules`` and anything then does ``import hou``:

  1. ``hou.py`` re-executes and re-runs ``_hou.Parm_swigregister(Parm)``, so the
     C extension's type registry now points at a NEW ``Parm`` class object;
  2. ``hou.py:123810 __finishImport()`` RAISES — ``type object 'PerfMonProfile'
     has no attribute 'save'``, the deprecation wrappers are not re-appliable —
     leaving that new class HALF-BUILT: 166 attributes against the original's
     186, and no ``Parm.set``;
  3. importlib discards the failed module, so ``sys.modules['hou']`` and
     ``hou.Parm`` still look perfect. ``hou.Parm.set`` is ``True``;
  4. but ``node.parm("x")`` now returns an instance of the ZOMBIE class and
     ``node.parm("x").set(v)`` raises
     ``AttributeError: 'Parm' object has no attribute 'set'``.

That gap between (3) and (4) is the whole finding. It is why R41's positive
control (``hou.Parm.set`` -> True) and the 17 failures in
``tests/solaris/test_live_wiring.py`` were both true at the same time, and why
the defect read as "a stub Parm is shadowing the real class" when no stub was
involved at all.

Restore-by-object does not repair it — Q1's lesson one layer down. The damage
lands in the C extension, past anything ``sys.modules`` can express. The
re-import is what must not happen, so ``tests/conftest.py`` installs
``HOU_REIMPORT_GUARD`` on ``sys.meta_path`` to make it impossible.

WHAT MAKES EACH PIN BELOW ABLE TO FAIL (Law 1 — stated before it was written):

  test_swig_parm_registry_is_intact
      fails the moment any earlier test in the session re-imports `hou`,
      because `node.parm(...)` then yields the zombie class. Negative control:
      ``test_zombie_parm_reproduces_in_a_clean_subprocess`` builds the failure
      in a throwaway hython and asserts it reproduces — if that subprocess ever
      comes back healthy, this pin is measuring nothing and says so.

  test_guard_returns_the_original_module_object
      fails if the meta_path guard is uninstalled or stops matching `hou`:
      the re-import then re-executes hou.py and returns a different object.

  test_guard_records_the_offence / test_gate_rejects_an_unsanctioned_offender
      fail if the recording or the run-level gate in conftest is removed —
      i.e. if the rescue goes silent (Law 3).

  test_no_module_leaves_a_foreign_hou_resident
      fails if any collected module swaps `sys.modules['hou']` and does not
      restore the ORIGINAL OBJECT.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

import conftest as _conftest

try:
    import hou
except ImportError:  # pragma: no cover — exercised off-host
    hou = None

_REAL_HOU = hou is not None and not getattr(hou, "__synapse_canonical__", False)

live_only = pytest.mark.skipif(
    not _REAL_HOU,
    reason=(
        "live Houdini required — this is a host-behaviour pin and a mock `hou` "
        "cannot disagree with it (Law 1). Run: hython -m pytest "
        "tests/test_hou_reimport_guard.py"
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_parm(name: str):
    """A parameter fetched off a REAL node, via the live C extension."""
    obj = hou.node("/obj")
    node = obj.node(name) or obj.createNode("geo", name)
    return node.parm("tx")


def _hython() -> str | None:
    exe = sys.executable
    base = os.path.basename(exe).lower()
    return exe if base.startswith("hython") or "houdini" in exe.lower() else None


# ---------------------------------------------------------------------------
# 1. The release condition itself
# ---------------------------------------------------------------------------

@live_only
def test_swig_parm_registry_is_intact():
    """`node.parm(...)` must yield the real, fully-built `hou.Parm`.

    FAILS IF: anything in this session re-imported `hou`, re-registering the
    SWIG type map to a half-built class. This is the exact assertion whose
    absence let 17 live-wiring tests report a stub-`Parm` shadow.
    """
    parm = _fresh_parm("synapse_reimport_pin")

    assert type(parm) is hou.Parm, (
        "node.parm() returned an instance of a DIFFERENT class than "
        f"hou.Parm ({type(parm)!r} vs {hou.Parm!r}). The SWIG type registry was "
        "re-pointed by a second execution of hou.py."
    )
    assert hasattr(parm, "set"), (
        "the live `Parm` class has no `.set` — this is the half-built class "
        "left behind when hou.py's __finishImport() raised on re-execution."
    )
    # The module-level view is NOT sufficient evidence: it stays healthy through
    # the whole defect. Asserted here so the pin records why it probes an
    # instance rather than the class off the module.
    assert hasattr(hou.Parm, "set")


@live_only
def test_parm_set_actually_writes():
    """Reachability is not enough — the bound method must work.

    FAILS IF: `.set` resolves to something inert.
    """
    parm = _fresh_parm("synapse_reimport_pin_write")
    parm.set(0.0)
    parm.set(2.5)
    assert parm.eval() == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# 2. Negative control — prove the pin above can fail
# ---------------------------------------------------------------------------

@live_only
def test_zombie_parm_reproduces_in_a_clean_subprocess():
    """The paired negative control for `test_swig_parm_registry_is_intact`.

    Reproduces the defect in a THROWAWAY hython (never in this process, which
    the guard is holding sound) and asserts the failure is real. Without this,
    the pin above is a check with no demonstrated failure mode — a decoration.

    FAILS IF: the corruption stops reproducing. That would mean either SideFX
    fixed re-import (make this xfail with a build number and keep the pin), or
    this control stopped exercising the path — in which case the pin above is
    no longer evidence of anything.
    """
    hy = _hython()
    if hy is None:  # pragma: no cover — belt and braces
        pytest.skip("cannot locate the running hython to spawn a control")

    script = textwrap.dedent(
        """
        import sys, hou
        node = hou.node("/obj").createNode("geo", "zombie_probe")
        before = hasattr(node.parm("tx"), "set")

        saved = sys.modules.pop("hou")          # the forbidden idiom
        try:
            import hou as _again                # re-executes hou.py
        except Exception:
            pass                               # __finishImport() raises; damage done
        sys.modules["hou"] = saved             # textbook restore-by-object

        parm = node.parm("ty")
        print("BEFORE_SET=%s" % before)
        print("MODULE_LOOKS_FINE=%s" % hasattr(sys.modules["hou"].Parm, "set"))
        print("INSTANCE_HAS_SET=%s" % hasattr(parm, "set"))
        print("SAME_CLASS=%s" % (type(parm) is saved.Parm))
        """
    )
    proc = subprocess.run(
        [hy, "-c", script], capture_output=True, text=True, timeout=600
    )
    out = proc.stdout

    assert "BEFORE_SET=True" in out, f"control never had a healthy baseline:\n{out}"
    assert "MODULE_LOOKS_FINE=True" in out, (
        "the module-level view was expected to stay healthy — that is the whole "
        f"trap. Output:\n{out}"
    )
    assert "INSTANCE_HAS_SET=False" in out, (
        "the corruption did NOT reproduce, so `test_swig_parm_registry_is_intact` "
        f"has no demonstrated failure mode on this build. Output:\n{out}"
    )
    assert "SAME_CLASS=False" in out, f"expected a re-pointed type registry:\n{out}"


# ---------------------------------------------------------------------------
# 3. The guard
# ---------------------------------------------------------------------------

@live_only
def test_guard_is_installed():
    """FAILS IF: the meta_path guard is not installed under real Houdini."""
    assert _conftest.HOU_REIMPORT_GUARD is not None
    assert _conftest.HOU_REIMPORT_GUARD in sys.meta_path
    assert sys.meta_path.index(_conftest.HOU_REIMPORT_GUARD) == 0, (
        "the guard must be first — a finder ahead of it could resolve `hou` "
        "and re-execute hou.py before the guard is consulted."
    )


@live_only
def test_guard_returns_the_original_module_object():
    """The sanctioned exercise: evict `hou`, re-import, survive.

    FAILS IF: the guard is uninstalled or stops matching `hou` — the re-import
    then re-executes hou.py and yields a different, half-built module, and the
    registry assertion at the end catches the damage.
    """
    guard = _conftest.HOU_REIMPORT_GUARD
    before = len(guard.interceptions)
    saved = sys.modules.pop("hou")
    try:
        import hou as reimported  # noqa: PLC0415 — the point of the test
    finally:
        sys.modules["hou"] = saved

    assert reimported is saved, (
        "the guard did not intercept: `import hou` produced a new module object, "
        "which means hou.py executed a second time."
    )
    assert len(guard.interceptions) == before + 1

    # And the process is still sound afterwards — the whole purpose.
    parm = _fresh_parm("synapse_reimport_pin_guarded")
    assert type(parm) is hou.Parm
    assert hasattr(parm, "set")


@live_only
def test_guard_records_the_offence():
    """FAILS IF: the rescue goes silent (Law 3 — no success status over a
    thing that went wrong)."""
    guard = _conftest.HOU_REIMPORT_GUARD
    saved = sys.modules.pop("hou")
    try:
        import hou  # noqa: F401, PLC0415
    finally:
        sys.modules["hou"] = saved

    assert guard.interceptions, "an interception was not recorded"
    latest = guard.interceptions[-1]
    assert set(latest) == {"offender", "function", "during"}
    # `during` is the actionable half: the importer is usually innocent product
    # code doing a lazy `import hou`; the guilty party is the test that left
    # `hou` absent. A record without it sends the reader to the wrong file.
    assert latest["during"].endswith("test_guard_records_the_offence"), (
        f"offence not attributed to the test in flight: {latest['during']!r}"
    )
    where = latest["offender"].replace("\\", "/")
    assert "tests/test_hou_reimport_guard.py" in where, (
        f"offence not attributed to the file that caused it: {where}"
    )
    assert int(where.rsplit(":", 1)[1]) > 0, "offence carries no line number"


@live_only
def test_reimport_guard_covers_importlib_reload():
    """The SECOND route in, and the one the guard's docs originally denied.

    ``importlib.reload(hou)`` consults meta_path even with `hou` PRESENT, so it
    reaches the guard without any eviction. It is the nastier route: reload
    re-executes into the SAME namespace, so an unguarded reload makes `hou.Parm`
    ITSELF the zombie (VERIFIED-RUNTIME: `hou.Parm is <original>` -> False,
    dir() 166 vs 186, no `.set`) rather than leaving the module pristine.

    FAILS IF: the guard is uninstalled, or its install condition is narrowed to
    "only when `hou` is absent" on the strength of the comment this pin exists
    to keep honest. Nothing in the tree reloads `hou` today — which is exactly
    why the coverage needs a pin rather than an assumption.
    """
    import importlib

    guard = _conftest.HOU_REIMPORT_GUARD
    before = len(guard.interceptions)
    original_parm = hou.Parm

    reloaded = importlib.reload(sys.modules["hou"])

    assert len(guard.interceptions) == before + 1, "reload did not reach the guard"
    assert reloaded is sys.modules["hou"]
    assert hou.Parm is original_parm, (
        "hou.Parm was replaced in place — the reload re-executed hou.py"
    )
    assert hasattr(hou.Parm, "set")

    parm = _fresh_parm("synapse_reimport_pin_reload")
    assert type(parm) is hou.Parm
    assert hasattr(parm, "set")


# ---------------------------------------------------------------------------
# 4. The run-level gate's own negative control
# ---------------------------------------------------------------------------

def test_gate_ignores_the_sanctioned_exerciser():
    """FAILS IF: the allowlist stops matching this file — every run would then
    go red on its own pin."""
    sanctioned = [
        {"offender": "C:/x/tests/test_hou_reimport_guard.py:123", "function": "t",
         "during": "tests/test_hou_reimport_guard.py::test_guard_is_installed"},
        {"offender": "C:\\x\\tests\\test_hou_reimport_guard.py:9", "function": "t",
         "during": "tests\\test_hou_reimport_guard.py::test_guard_records_the_offence"},
    ]
    assert _conftest.unsanctioned_hou_reimports(sanctioned) == []


def test_gate_rejects_an_unsanctioned_offender():
    """The mutation this gate exists to catch.

    FAILS IF: the allowlist is widened to everything, or the filter is removed
    — a real offender would then pass unreported.
    """
    offences = [
        {"offender": "C:/x/tests/panel/test_theme_source.py:107", "function": "_install_hou",
         "during": "tests/panel/test_theme_source.py::test_tokens_output_byte_identical_headless"},
        {"offender": "C:/x/tests/test_hou_reimport_guard.py:1", "function": "t",
         "during": "tests/test_hou_reimport_guard.py::test_guard_is_installed"},
    ]
    out = _conftest.unsanctioned_hou_reimports(offences)
    assert len(out) == 1
    assert "test_theme_source.py" in out[0]["during"]


def test_gate_is_clean_for_an_empty_trace():
    assert _conftest.unsanctioned_hou_reimports([]) == []


def test_gate_exempts_on_the_guilty_field_not_the_innocent_one():
    """The exemption must key on ``during``, not ``offender``.

    The offender is whichever module executed the lazy ``import hou`` inside the
    window — rotating, innocent production code (theme_source.py:45 in one run,
    store.py:29 in another). Keying the allowlist on it would exempt a shifting
    cast of product files and could never sanction the test actually
    responsible.

    FAILS IF: the filter reverts to matching ``offender``.
    """
    # Sanctioned test, innocent production importer -> exempt.
    sanctioned = [{
        "offender": "C:/x/python/synapse/panel/designsystem/theme_source.py:45",
        "function": "_hcs_surface_rgb",
        "during": "tests/test_hou_reimport_guard.py::test_guard_records_the_offence",
    }]
    assert _conftest.unsanctioned_hou_reimports(sanctioned) == []

    # Guilty test that merely *imports from* the sanctioned path -> NOT exempt.
    disguised = [{
        "offender": "C:/x/tests/test_hou_reimport_guard.py:1",
        "function": "helper",
        "during": "tests/panel/test_theme_source.py::test_tokens_output_byte_identical_headless",
    }]
    assert len(_conftest.unsanctioned_hou_reimports(disguised)) == 1


def test_sessionfinish_gate_raises_on_an_unsanctioned_offence():
    """The enforcement hook itself, not just the pure function under it.

    The three ``test_gate_*`` pins above feed synthetic lists to
    ``unsanctioned_hou_reimports``. That leaves the hook that consumes it
    unexercised: delete the ``raise`` from ``pytest_sessionfinish`` and every
    other pin in this file still passes. This one calls the hook directly.

    FAILS IF: the raise is removed, downgraded to a warning, or the hook stops
    consulting the guard's record.
    """
    guard = _conftest.HOU_REIMPORT_GUARD
    if guard is None:
        pytest.skip("gate only arms under real Houdini — nothing to enforce")

    saved = list(guard.interceptions)
    guard.interceptions.append({
        "offender": "C:/x/python/synapse/whatever.py:1",
        "function": "lazy_import",
        "during": "tests/some_other_file.py::test_that_evicted_hou",
    })
    try:
        with pytest.raises(pytest.UsageError, match="HOU_REIMPORT_GUARD"):
            _conftest.pytest_sessionfinish(_StubSession(), 0)
    finally:
        guard.interceptions[:] = saved

    # And it stays quiet once the offence is gone — a gate that always fires is
    # as useless as one that never does.
    _conftest.pytest_sessionfinish(_StubSession(), 0)


class _StubSession:
    """Minimal stand-in — the hook only ever reads the guard's record."""

    exitstatus = 0


# ---------------------------------------------------------------------------
# 4b. The only version of this law the MERGE GATE can enforce
# ---------------------------------------------------------------------------

_EVICTION_ALLOWLIST = ("tests/test_hou_reimport_guard.py",)


def _hou_evictions_in_tests():
    """Every `pop`/`del`/`monkeypatch.delitem` of ``sys.modules['hou']``."""
    import ast

    tests_root = pathlib.Path(__file__).resolve().parent
    found = []

    def is_sys_modules_hou(n):
        return (
            isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Attribute)
            and n.value.attr == "modules"
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "sys"
            and isinstance(n.slice, ast.Constant)
            and n.slice.value == "hou"
        )

    for path in sorted(tests_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # pragma: no cover
            continue
        rel = path.relative_to(tests_root.parent).as_posix()
        for node in ast.walk(tree):
            kind = None
            if isinstance(node, ast.Delete) and any(is_sys_modules_hou(t) for t in node.targets):
                kind = "del"
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "modules"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "sys"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "hou"
            ):
                kind = "pop"
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "delitem"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "hou"
            ):
                kind = "monkeypatch.delitem"
            if kind:
                found.append((rel, node.lineno, kind))
    return found


def test_no_test_evicts_hou_from_sys_modules():
    """The eviction idiom is banned outright, and this is the ban CI can run.

    Everything else in this file that matters is ``@live_only``: under stock
    python the canonical fake carries ``__synapse_canonical__``, so
    HOU_REIMPORT_GUARD is never built and the session-finish gate returns
    immediately. But the merge ratchet runs the suite on stock python. Without
    a check that fails on EVERY interpreter, a PR reintroducing
    ``sys.modules.pop("hou")`` goes green — the same shape of hole as the
    residency guard that used to disarm itself under hython.

    Two rules, one ban:
      * express absence as ``sys.modules["hou"] = None`` — CPython raises
        ImportError on a None entry without reaching the import machinery;
      * restore the prior resident BY OBJECT.

    A test asserting an ``except ImportError`` fallback MUST use the None
    marker: the meta_path guard hands a popped `hou` straight back, which makes
    "evicted" indistinguishable from "present" and quietly converts such a
    negative control into a decoration.

    FAILS IF: any eviction appears under tests/ outside the sanctioned
    exerciser, which is this file — it has to trip the guard to pin it.
    """
    offenders = [
        (f, line, kind)
        for f, line, kind in _hou_evictions_in_tests()
        if not any(f.endswith(ok) for ok in _EVICTION_ALLOWLIST)
    ]
    assert offenders == [], (
        "sys.modules['hou'] eviction(s) found outside the sanctioned exerciser:\n"
        + "\n".join(f"    {f}:{line}  ({kind})" for f, line, kind in offenders)
        + '\n  Use `sys.modules["hou"] = None` for absence and restore by object.'
    )


def test_the_eviction_scanner_can_actually_see_an_eviction():
    """Paired negative control for the ban above (Law 1).

    A scanner that matched nothing would make the ban vacuously green forever.
    The sanctioned exerciser genuinely contains evictions, so the unfiltered
    scan must find them — and must attribute them to this file.

    FAILS IF: the AST matcher stops recognising the idiom.
    """
    all_found = _hou_evictions_in_tests()
    mine = [(f, line, kind) for f, line, kind in all_found if f.endswith(_EVICTION_ALLOWLIST[0])]
    assert mine, (
        "the scanner found no evictions at all, including the ones this file "
        "provably contains — it is matching nothing and the ban above is vacuous"
    )
    assert {kind for _, _, kind in mine} == {"pop"}


# ---------------------------------------------------------------------------
# 5. Residency proper — the first form of the defect
# ---------------------------------------------------------------------------

def test_no_module_leaves_a_foreign_hou_resident():
    """`sys.modules['hou']` must still be the object this session started with.

    FAILS IF: any module swaps the resident and restores by sentinel (real
    Houdini carries no sentinel, so that restore never runs), by re-import, or
    not at all. Under hython the expected resident is real Houdini; standalone
    it is conftest's canonical fake. Identity is the test in both modes.
    """
    assert _conftest._HOU_AT_IMPORT is not None
    assert sys.modules.get("hou") is _conftest._HOU_AT_IMPORT, (
        "a foreign `hou` is resident. expected "
        f"{_conftest._HOU_AT_IMPORT!r}, found {sys.modules.get('hou')!r}"
    )


def test_residency_guard_compares_by_object_not_by_sentinel():
    """The guard must not be satisfiable by a sentinel attribute.

    FAILS IF: someone reintroduces `getattr(resident, '__synapse_canonical__')`
    as the acceptance test — a fake carrying the sentinel would then pass while
    real Houdini, which carries no sentinel, could never satisfy it. That
    asymmetry is what disarmed this guard under hython in the first place.
    """
    import inspect

    src = inspect.getsource(_conftest.pytest_collection_finish)
    assert "_HOU_AT_IMPORT" in src
    assert "is _HOU_AT_IMPORT" in src, "the guard must compare by object identity"
    assert "__synapse_canonical__" not in src, (
        "sentinel-based acceptance reintroduced into the residency guard"
    )
