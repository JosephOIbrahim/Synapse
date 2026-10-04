"""B1: a guarded parm write that does not land is reported, never dropped.

The catalog ratchet (test_harden_catalog_conformance) lists parm names the
product writes that do not exist on the recording build. This test holds the
other half: in the files those misses live in, every such name has a
``note_missing`` branch, and the tool returns ``parms_missed``.

Pure Python: no hou.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).resolve().parent / "fixtures" / "catalog_conformance_baseline.json"

# Baseline entries that are not writes a tool can report on.
NOT_A_WRITE = {
    # a read fallback for a COP2 depth query
    "parm|python/synapse/server/handlers_cops.py|data_type",
    # a live probe that reports through its own Check
    "typed|python/synapse/validation/solaris/verify_set_purpose.py|componentgeometry.purpose",
    # the plan-only op list of import_megascans (data, not a call)
    "typed|python/synapse/mcp/tool_impls/solaris/import_megascans.py|reference.destpath",
}

# The shipped TOPs surface is quarantined (tests/test_d_track.py,
# test_tops_path_untouched_green_at_head). Its misses stay on the ratchet's
# list and are owed a parms_missed report when that quarantine lifts.
QUARANTINED = "python/synapse/server/handlers_tops/"


def _load_note_missing():
    path = ROOT / "python" / "synapse" / "core" / "parm_report.py"
    spec = importlib.util.spec_from_file_location("_parm_report_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.note_missing


class _Type:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Node:
    def __init__(self, name):
        self._type = _Type(name)

    def type(self):
        return self._type


def test_note_missing_records_type_and_alternates_once():
    note_missing = _load_note_missing()
    missed = []
    node = _Node("ropfetch")
    note_missing(missed, node, "pdg_framerange")
    note_missing(missed, node, "pdg_framerange")
    note_missing(missed, node, "picture", "outputimage")
    assert missed == ["ropfetch.pdg_framerange", "ropfetch.picture|outputimage"]


def test_note_missing_survives_a_broken_node():
    note_missing = _load_note_missing()
    missed = []
    note_missing(missed, object(), "resx")
    assert missed == ["?.resx"]


def _reported_names(rel):
    """Parm names passed to note_missing(...) anywhere in the file."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "note_missing"):
            for arg in node.args[2:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


def _baseline_writes():
    entries = json.loads(BASELINE.read_text(encoding="utf-8"))["misses"]
    out = []
    for entry in sorted(entries):
        kind, rel, literal = entry.split("|")
        if kind == "type" or entry in NOT_A_WRITE or rel.startswith(QUARANTINED):
            continue
        out.append((rel, literal.split(".", 1)[1] if kind == "typed" else literal, entry))
    return out


def test_the_work_list_is_not_empty():
    assert len(_baseline_writes()) >= 8


@pytest.mark.parametrize("rel,parm,entry", _baseline_writes())
def test_every_known_missing_parm_write_is_reported(rel, parm, entry):
    assert parm in _reported_names(rel), (
        f"{entry}: the name is missing on the recording build and its guarded "
        f"write has no note_missing branch, so the tool would report success.")


@pytest.mark.parametrize("rel", sorted({rel for rel, _, _ in _baseline_writes()}))
def test_the_tool_returns_parms_missed(rel):
    assert '"parms_missed": parms_missed' in (ROOT / rel).read_text(encoding="utf-8")
