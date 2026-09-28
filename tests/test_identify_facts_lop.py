"""BP11-SALIENCE T5: the LOP ``writes <first> (+N)`` Here line, from a fake node.

``facts._lop_writes`` reads ``hou.LopNode.lastModifiedPrims()`` (seat-probed live
on 22.0.400) for LOP-category nodes only. These tests need no ``hou``: a fake node
supplies the two duck-typed calls ``_lop_writes`` makes — ``type().category().name()``
and ``lastModifiedPrims()`` — plus the handful ``node_facts`` reads under try/except.
Every test names the mutation that reddens it.

The live end of this row is ``scripts/probe_identify.py`` under hython; here we pin
the pure behaviour so a regression reddens on system Python.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PYTHON = str(Path(__file__).resolve().parents[1] / "python")
if _PYTHON not in sys.path:
    sys.path.insert(0, _PYTHON)

from synapse.identify import compose as C  # noqa: E402
from synapse.identify import facts as F  # noqa: E402


class _Cat:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Type:
    def __init__(self, category, description="Fake", type_name="fake"):
        self._category = _Cat(category)
        self._description = description
        self._type_name = type_name

    def category(self):
        return self._category

    def description(self):
        return self._description

    def name(self):
        return self._type_name

    def definition(self):
        return None


class _FakeNode:
    """Minimal stand-in: only the methods ``facts`` reads, all overridable."""

    def __init__(self, *, category="Lop", modified=None, raises=False, path="/stage/fake"):
        self._category = category
        self._modified = modified if modified is not None else []
        self._raises = raises
        self._path = path

    def path(self):
        return self._path

    def type(self):
        return _Type(self._category)

    def parms(self):
        return []

    def errors(self):
        return []

    def warnings(self):
        return []

    def isBypassed(self):
        return False

    def lastModifiedPrims(self):
        if self._raises:
            raise RuntimeError("lastModifiedPrims exploded")
        return list(self._modified)


# ----------------------------------------------------------------- _lop_writes direct
def test_lop_writes_sorts_and_counts():
    """A LOP reporting ['/box', '/ball'] -> {'first': '/ball', 'count': 2}. Mutation:
    drop the ``sorted(...)`` in ``_lop_writes`` -> first becomes '/box' -> RED."""
    node = _FakeNode(category="Lop", modified=["/box", "/ball"])
    assert F._lop_writes(node) == {"first": "/ball", "count": 2}


def test_lop_writes_here_line_reads_writes_ball_plus_one():
    """The composed Here line for the fake LOP is exactly 'writes /ball (+1)'.
    Mutation: make ``_lop_writes`` return None for a LOP -> the line vanishes -> RED."""
    node = _FakeNode(category="Lop", modified=["/box", "/ball"])
    facts = F.node_facts(node)
    facts["summary"], facts["summary_source"] = None, "unknown"  # force a bare What line
    lines = C.compose(facts)
    assert "writes /ball (+1)" in lines


def test_sop_node_has_no_writes_line():
    """A SOP node yields no writes dict and no writes line. Mutation: delete the
    ``category().name() != 'Lop'`` guard -> a SOP's (phantom) call is attempted and,
    if it ever returned prims, a writes line would appear -> RED here."""
    node = _FakeNode(category="Sop", modified=["/box", "/ball"])
    assert F._lop_writes(node) is None
    facts = F.node_facts(node)
    assert facts["lop_writes"] is None
    facts["summary"], facts["summary_source"] = None, "unknown"
    assert not any(line.startswith("writes ") for line in C.compose(facts))


def test_raising_last_modified_prims_yields_no_line():
    """A LOP whose lastModifiedPrims() raises -> None, not a crash. Mutation: remove
    the try/except around the call in ``_lop_writes`` -> node_facts raises -> RED."""
    node = _FakeNode(category="Lop", raises=True)
    assert F._lop_writes(node) is None
    facts = F.node_facts(node)
    assert facts["lop_writes"] is None
    assert not any(line.startswith("writes ") for line in C.compose(facts))


def test_lop_that_has_not_cooked_yields_no_line():
    """No cook -> no modified prims -> no line (never cook to get the paths).
    Mutation: return {'first': '', 'count': 0} instead of None on empty -> RED."""
    node = _FakeNode(category="Lop", modified=[])
    assert F._lop_writes(node) is None


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
