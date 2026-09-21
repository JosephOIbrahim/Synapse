"""BP9-RESTAMP: H22 doc-intel artifacts read the live build + symbol count, never literals.

Every H22 doc-intel artifact had been pinned to ``22.0.368`` / ``35903`` while the drop
(harness/state/drop.json) said 22.0.400 and the committed symbol table held 36,472 symbols.
This pins the three stamp sources:

* scripts/h22_probe_candidates.py stamps ``against_build`` from ``hou`` under hython,
  else from drop.json ``houdini_build`` -- and refuses (raises) rather than defaulting.
* the three workflows (h22-doc-scout / h22-probe-adjudicate / phantom-sweep) carry no
  ``35903`` / ``22.0.368`` literal; they interpolate a run-time ``STAMP`` read from the
  symbol-table header.
* harness/verify/checks.py::lop_knowledge_stamp_current goes RED when the newest packaged
  lop_solaris_knowledge_<major>.json stamp differs from drop.json, names the re-author
  script, and is GREEN when they agree (temp copies -- the real files are never touched).

Discipline (test_d_track sibling): load checks.py by path, monkeypatch its ``_drop_path``
seam, never sys.modules fakes.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = [
    _REPO / ".claude" / "workflows" / "h22-doc-scout.js",
    _REPO / ".claude" / "workflows" / "h22-probe-adjudicate.js",
    _REPO / ".claude" / "workflows" / "phantom-sweep.js",
]
_PROBE = _REPO / "scripts" / "h22_probe_candidates.py"
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_PKG_KNOWLEDGE = _REPO / "python" / "synapse" / "cognitive" / "tools" / "data" / "lop_solaris_knowledge_22.json"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- probe runner

def test_probe_runner_has_no_literal_build_default():
    src = _PROBE.read_text(encoding="utf-8")
    assert "'22.0.368'" not in src and '"22.0.368"' not in src
    # the stamp is resolved, not defaulted: no data.get("against_build", <literal>)
    assert not re.search(r'against_build",\s*"\d+\.\d+\.\d+"', src)
    assert "hou.applicationVersionString()" in src
    assert 'drop.get("houdini_build")' in src


def test_probe_runner_stamp_falls_back_to_drop_json_then_refuses(tmp_path, monkeypatch):
    mod = _load(_PROBE, "h22_probe_candidates_under_test")
    # not under hython here -- make sure a stray `hou` stub cannot satisfy the first tier
    monkeypatch.setitem(sys.modules, "hou", None)
    drop = tmp_path / "drop.json"
    monkeypatch.setattr(mod, "DROP", drop)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    drop.write_text(json.dumps({"houdini_build": "22.0.999"}), encoding="utf-8")
    assert mod.resolve_against_build() == "22.0.999"
    drop.write_text(json.dumps({"houdini": "21.0.671"}), encoding="utf-8")   # older key accepted
    assert mod.resolve_against_build() == "21.0.671"
    drop.unlink()
    with pytest.raises(RuntimeError, match="cannot stamp against_build"):
        mod.resolve_against_build()


def test_probe_runner_persists_resolved_build(tmp_path, monkeypatch):
    mod = _load(_PROBE, "h22_probe_candidates_persist")
    monkeypatch.setitem(sys.modules, "hou", None)
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps({"houdini_build": "22.0.777"}), encoding="utf-8")
    cand = tmp_path / "cand.json"
    cand.write_text(json.dumps({"generated": "2026-09-21", "against_build": "22.0.368",
                                "candidates": []}), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr(mod, "DROP", drop)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "CAND", cand)
    monkeypatch.setattr(mod, "OUT", out)
    monkeypatch.setattr(mod, "build_ns", lambda: {})
    assert mod.main() == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["against_build"] == "22.0.777"
    assert res["candidates_against_build"] == "22.0.368"   # drift kept visible, not overwritten
    assert res["source_report"].endswith("h22-doc-intel-2026-09-21.md")


# ---------------------------------------------------------------- workflows

@pytest.mark.parametrize("wf", _WORKFLOWS, ids=lambda p: p.name)
def test_workflow_has_no_symbol_count_or_build_literal(wf):
    src = wf.read_text(encoding="utf-8")
    assert "35903" not in src and "35,903" not in src
    assert "22.0.368" not in src
    # the run-time read is present and actually interpolated where the literals used to be
    assert "readSymtabStamp(" in src
    assert "${STAMP.build}" in src and "${STAMP.count}" in src


# ---------------------------------------------------------------- checks verb

def _plant_wt(tmp_path, stamp):
    wt = tmp_path / "wt"
    data_dir = wt / "python" / "synapse" / "cognitive" / "tools" / "data"
    data_dir.mkdir(parents=True)
    src = json.loads(_PKG_KNOWLEDGE.read_text(encoding="utf-8"))   # temp COPY, real file untouched
    src["houdini_version"] = stamp
    (data_dir / "lop_solaris_knowledge_22.json").write_text(json.dumps(src), encoding="utf-8")
    # an older major must not win "newest"
    (data_dir / "lop_solaris_knowledge_21.json").write_text(
        json.dumps({"houdini_version": "21.0.671"}), encoding="utf-8")
    return wt


def test_checks_verb_registered_and_listed_in_help():
    checks = _load(_CHECKS, "harness_checks_restamp")
    assert "lop_knowledge_stamp_current" in checks.DISPATCH
    assert checks.DISPATCH["lop_knowledge_stamp_current"] is checks.check_lop_knowledge_stamp_current


def test_checks_verb_red_when_stamps_differ_green_when_equal(tmp_path, monkeypatch):
    checks = _load(_CHECKS, "harness_checks_restamp_verb")
    drop = tmp_path / "drop.json"
    monkeypatch.setattr(checks, "_drop_path", lambda: drop)
    drop.write_text(json.dumps({"houdini_build": "22.0.400"}), encoding="utf-8")

    wt = _plant_wt(tmp_path, "22.0.368")
    red = checks.check_lop_knowledge_stamp_current({"wt": str(wt)})
    assert red["ok"] is False
    assert "22.0.368" in red["detail"] and "22.0.400" in red["detail"]
    assert "scripts/author_lop_knowledge_22.py" in red["detail"]   # one-line remediation

    (wt / "python/synapse/cognitive/tools/data/lop_solaris_knowledge_22.json").write_text(
        json.dumps({"houdini_version": "22.0.400"}), encoding="utf-8")
    green = checks.check_lop_knowledge_stamp_current({"wt": str(wt)})
    assert green["ok"] is True, green


def test_checks_verb_abstains_without_drop_json(tmp_path, monkeypatch):
    # Mode A (no drop declared) is an honest abstention, never a PASS.
    checks = _load(_CHECKS, "harness_checks_restamp_abstain")
    monkeypatch.setattr(checks, "_drop_path", lambda: tmp_path / "missing-drop.json")
    wt = _plant_wt(tmp_path, "22.0.368")
    r = checks.check_lop_knowledge_stamp_current({"wt": str(wt)})
    assert r["ok"] is None and "absent" in r["detail"]
