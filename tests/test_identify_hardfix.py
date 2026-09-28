"""Behavior pins for the BP11-HARDFIX Identify restoration (fakes only, no hou).

Each pin bites when the matching HARDEN defect is re-applied:

  * ``facts._parm_is_expression`` — a plain parm is NOT an expression and a keyed
    parm IS (defect 2: the ``if parm.keyframes():`` guard was deleted, so every
    literal parameter whose ``expression()`` raises was read as an expression).
  * ``library.summarize`` — a raising ``lookup`` returns the honest-unknown
    fallback (defect 3: ``hit = None`` was deleted from the except, so a library
    outage raised ``UnboundLocalError`` on the bubble path instead of unknown).
  * ``salience.run_shadow`` — releases its slot when job submission raises
    (defect 4: ``_JOBS.slot.release()`` was deleted, leaking a slot per failure).

Plus a compile guard: every ``python/synapse/identify/*.py`` parses (defect 1:
``salience.py`` did not parse — an IndentationError broke the whole module).
"""
import compileall
import threading
from pathlib import Path

from synapse.identify import facts, library, salience


class _FakeParm:
    """A parm whose ``expression()`` / ``keyframes()`` behaviour is controlled."""

    def __init__(self, *, has_expression, keyframes):
        self._has_expression = has_expression
        self._keyframes = list(keyframes)

    def expression(self):
        if not self._has_expression:
            raise ValueError("no expression on this parm")
        return "$F"

    def keyframes(self):
        return self._keyframes


def test_plain_parm_is_not_expression():
    # expression() raises AND there are no keyframes -> not driven -> False.
    plain = [_FakeParm(has_expression=False, keyframes=[])]
    assert facts._parm_is_expression(plain) is False


def test_keyed_parm_is_expression():
    # expression() raises but the parm carries keyframes -> keyed -> True.
    keyed = [_FakeParm(has_expression=False, keyframes=[object()])]
    assert facts._parm_is_expression(keyed) is True


def test_summarize_returns_honest_unknown_when_lookup_raises():
    def raising_lookup(_keys):
        raise RuntimeError("library outage")

    text, source = library.summarize(
        "operator:Sop/polybevel?version=3.0", hda_help=None, lookup=raising_lookup
    )
    assert source == "unknown"
    assert text is None


def test_run_shadow_releases_slot_when_spawn_raises(monkeypatch):
    # Reach the spawn: preference on, Jev enabled, more survivors than HERE_PARMS.
    monkeypatch.setattr(salience.adapter, "enabled", lambda **_: True)
    monkeypatch.setattr(
        salience, "survivors",
        lambda _facts: [{"name": n} for n in "abcde"],
    )
    # A fresh slot so the pin is independent of test order.
    monkeypatch.setattr(salience._JOBS, "slot", threading.BoundedSemaphore(1))

    def raising_spawn(_target):
        raise RuntimeError("thread submission failed")

    result = salience.run_shadow({}, opt_in=True, spawn=raising_spawn)
    assert result is None
    # The slot must have been released back; a leaked slot fails this acquire.
    got = salience._JOBS.slot.acquire(blocking=False)
    assert got, "run_shadow leaked its salience slot when spawn raised"
    salience._JOBS.slot.release()


def test_all_identify_modules_compile():
    identify_dir = Path(salience.__file__).parent
    assert compileall.compile_dir(str(identify_dir), quiet=1, force=True), (
        "a python/synapse/identify/*.py module failed to compile"
    )
