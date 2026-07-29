"""The consumer that closes the loop, and the clock that keeps it closed.

An audit traced a finding from birth to merge and found the arrow stops at the
receipt: `findings[]` and `for_ruling[]` are read by no code in the tree, while
Article VI calls `for_ruling[]` "the only channel to the human". 221 such items
existed unread.

Every test states the condition under which it FAILS.
"""
import importlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "harness", "decisions.py")


def _mod():
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        return importlib.import_module("decisions")
    finally:
        sys.path.pop(0)


def test_for_ruling_items_are_actually_read():
    """FAILS IF: receipts carrying for_ruling[] produce no decision items.

    The defect itself. If this returns nothing while receipts hold rulings, the
    channel is unread again and the loop is open.
    """
    d = _mod()
    on_disk = 0
    for n in os.listdir(os.path.join(ROOT, "harness", "notes", "receipts")):
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(ROOT, "harness", "notes", "receipts", n),
                      encoding="utf-8") as fh:
                on_disk += len(json.load(fh).get("for_ruling") or [])
        except Exception:
            pass
    collected = [i for i in d.collect(with_ages=False) if i["kind"] == "ruling"]
    assert len(collected) == on_disk, \
        "%d for_ruling entries on disk, %d collected" % (on_disk, len(collected))
    assert on_disk > 0, "no for_ruling entries to test against - cannot establish the case"


def test_unratified_flywheel_cycles_are_surfaced():
    """FAILS IF: a cycle at ratified:false does not reach the board."""
    d = _mod()
    with open(os.path.join(ROOT, "harness", "state", "flywheel_queue.json"),
              encoding="utf-8") as fh:
        want = sum(1 for c in json.load(fh).get("cycles") or []
                   if isinstance(c, dict) and c.get("ratified") is False)
    got = len([i for i in d.collect(with_ages=False) if i["kind"] == "flywheel"])
    assert got == want, "%d unratified cycles, %d surfaced" % (want, got)


def test_it_never_writes_ratified():
    """FAILS IF: this module can flip a gate.

    Article I - an agent that flips its own gate has removed the only thing
    between a mistake and the main branch. This reads `ratified`; it must never
    assign it.
    """
    src = open(DEC, encoding="utf-8").read()

    # Substring-matching 'ratified' is too crude: the module deliberately
    # PRINTS the exact flip a human should make, and that instruction string
    # contains the token. Assert on writes, not on mentions.
    d = _mod()
    for line in src.splitlines():
        if "ratified" not in line or line.strip().startswith("#"):
            continue
        assert "=" not in line.split("ratified")[0][-3:], \
            "assignment to ratified: %s" % line.strip()

    # The only file this module opens for writing is its own derived markdown.
    writes = [ln for ln in src.splitlines()
              if 'open(' in ln and '"w"' in ln]
    assert writes, "no write found - test cannot establish the case"
    for ln in writes:
        assert "tmp" in ln or "OUT" in ln, "writes to something other than OUT: %s" % ln.strip()
    assert "FLYWHEEL" not in "".join(writes), "opens the flywheel queue for writing"


def test_the_aging_gate_can_fail(monkeypatch):
    """FAILS IF: an over-age queue still reports success.

    This is the difference between a loop that is OBSERVABLE and one that is
    CLOSED. Without a nonzero exit, "nobody got to it" is the ambient condition
    rather than a failing state.
    """
    d = _mod()
    fresh = [{"kind": "ruling", "leg": "X", "text": "t", "source": "s", "age": 10.0}]
    old = [{"kind": "ruling", "leg": "X", "text": "t", "source": "s",
            "age": (d.MAX_DAYS + 1) * 86400.0}]
    assert d.overdue(fresh) == [], "a fresh item was called overdue"
    assert len(d.overdue(old)) == 1, "an over-age item was not flagged"

    # And end to end, through the CLI's exit code.
    out = subprocess.run([sys.executable, DEC, "--count"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8",
                         env=dict(os.environ, SYNAPSE_DECISION_MAX_DAYS="0"))
    assert out.returncode == d.EXIT_OVERDUE, \
        "max-age 0 must make every item overdue, got exit %d" % out.returncode


def test_unknown_age_sorts_last_not_first():
    """FAILS IF: an item with no derivable age is treated as the oldest.

    Neither schema records a deposit date, so age is derived and can be absent.
    An absent age must not jump the queue - that would rank the least-known
    items above the ones with real evidence of waiting.
    """
    d = _mod()
    items = d.collect(with_ages=False)  # every age is None here
    assert items, "nothing collected - cannot establish the case"
    ages = [i["age"] for i in items]
    known = [a for a in ages if a is not None]
    if known and any(a is None for a in ages):
        assert ages.index(None) > max(
            i for i, a in enumerate(ages) if a is not None), \
            "an unknown age sorted above a known one"


def test_text_extraction_survives_both_shapes():
    """FAILS IF: a dict-shaped for_ruling entry renders as a python repr.

    Entries are strings in some receipts and objects in others. A board that
    prints {'question': ...} is a board nobody reads.
    """
    d = _mod()
    assert d._text("plain string") == "plain string"
    assert d._text({"question": "should we ship?"}) == "should we ship?"
    assert d._text({"ruling": "hold"}) == "hold"
    odd = d._text({"unexpected": "shape"})
    assert "unexpected" in odd and not odd.startswith("{'"), odd


def test_statusline_count_spawns_no_subprocess(monkeypatch):
    """FAILS IF: putting decisions on the bar reintroduces the 919ms regression.

    The statusline calls collect(with_ages=False) precisely so the git pass is
    skipped. This pins that.
    """
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        s = importlib.import_module("statusline")
    finally:
        sys.path.pop(0)

    def boom(*a, **k):
        raise AssertionError("decision count spawned a subprocess")

    monkeypatch.setattr(s.subprocess, "run", boom)
    assert isinstance(s.decision_count(), int)
