"""WA1-TRUTH (G1+G4+C1) pins — additive autoresearch schema + APEX catalog stamp.

Pure Python, NO hou. These lock the additive contract this leg introduced so a
future edit that breaks it fails loud:

  * the two new probe kinds (apex_callback_discovery / apex_port_signature) are
    registered and validate;
  * type_existence 'category' and chain_hash 'context' are OPTIONAL and default
    to legacy behavior (solaris_basic unchanged);
  * a mission's artifact_prefix flows to the runner's evidence filename;
  * the shipped apex_basic mission validates and is sop-context for the invoke;
  * version_agreement's APEX stamp check reads green against the committed
    artifact, detects a drifted stamp, and treats a MISSING artifact as
    'nothing to compare' — never a false red.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_AR = _ROOT / "harness" / "autoresearch"
if str(_AR) not in sys.path:
    sys.path.insert(0, str(_AR))

import mission_schema as ms  # noqa: E402


def _base(**over):
    d = {"mission": "t", "version": "1", "target_build": "22.0.400",
         "phases": [{"id": "p", "kind": "type_discovery",
                     "questions": [{"pattern": "x"}]}]}
    d.update(over)
    return d


def _load_va():
    spec = importlib.util.spec_from_file_location(
        "wa1_version_agreement", _ROOT / "harness" / "verify" / "version_agreement.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- new kinds -------------------------------------------------------------

def test_new_kinds_registered():
    assert "apex_callback_discovery" in ms.VALID_KINDS
    assert "apex_port_signature" in ms.VALID_KINDS


def test_apex_callback_discovery_defaults_namespace_star():
    m = ms.validate_mission(_base(phases=[
        {"id": "p", "kind": "apex_callback_discovery", "questions": [{}]}]))
    assert m.phases[0].questions[0]["namespace"] == "*"


def test_apex_callback_discovery_rejects_empty_namespace():
    with pytest.raises(ms.MissionError):
        ms.validate_mission(_base(phases=[
            {"id": "p", "kind": "apex_callback_discovery",
             "questions": [{"namespace": "  "}]}]))


def test_apex_port_signature_requires_callback():
    with pytest.raises(ms.MissionError):
        ms.validate_mission(_base(phases=[
            {"id": "p", "kind": "apex_port_signature", "questions": [{}]}]))


# --- optional additive fields default to legacy behavior -------------------

def test_type_existence_category_optional_none_by_default():
    m = ms.validate_mission(_base(phases=[
        {"id": "p", "kind": "type_existence", "questions": [{"name": "x"}]}]))
    assert m.phases[0].questions[0]["category"] is None


def test_type_existence_bad_category_rejected():
    with pytest.raises(ms.MissionError):
        ms.validate_mission(_base(phases=[
            {"id": "p", "kind": "type_existence",
             "questions": [{"name": "x", "category": 5}]}]))


def test_chain_hash_context_defaults_lop():
    m = ms.validate_mission(_base(phases=[
        {"id": "p", "kind": "chain_hash",
         "questions": [{"name": "c", "chain": ["a"]}]}]))
    assert m.phases[0].questions[0]["context"] == "lop"


def test_chain_hash_bad_context_rejected():
    with pytest.raises(ms.MissionError):
        ms.validate_mission(_base(phases=[
            {"id": "p", "kind": "chain_hash",
             "questions": [{"name": "c", "chain": ["a"], "context": "usd"}]}]))


def test_artifact_prefix_default_and_override():
    assert ms.validate_mission(_base()).artifact_prefix == "lop_truth"
    assert ms.validate_mission(_base(artifact_prefix="apex_truth")).artifact_prefix == "apex_truth"


def test_artifact_prefix_must_be_nonempty_string():
    with pytest.raises(ms.MissionError):
        ms.validate_mission(_base(artifact_prefix=""))


# --- shipped missions ------------------------------------------------------

def test_apex_basic_mission_validates_and_is_sop_invoke():
    m = ms.load_mission(_AR / "missions" / "apex_basic.json")
    assert m.artifact_prefix == "apex_truth"
    assert m.target_build == "22.0.400"
    kinds = {ph.kind for ph in m.phases}
    assert {"apex_callback_discovery", "apex_port_signature",
            "type_existence", "chain_hash"} <= kinds
    inv = [q for ph in m.phases if ph.kind == "chain_hash" for q in ph.questions]
    assert inv and all(q["context"] == "sop" for q in inv)


def test_solaris_basic_unchanged_defaults():
    m = ms.load_mission(_AR / "missions" / "solaris_basic.json")
    assert m.artifact_prefix == "lop_truth"
    for ph in m.phases:
        if ph.kind == "type_existence":
            assert all(q["category"] is None for q in ph.questions)
        if ph.kind == "chain_hash":
            assert all(q["context"] == "lop" for q in ph.questions)


# --- runner names the artifact from artifact_prefix (no hou) ---------------

def test_runner_artifact_name_uses_prefix(tmp_path):
    import runner  # noqa: E402  (deferred; importing it never imports hou)
    m = ms.validate_mission(_base(artifact_prefix="apex_truth"))
    run = runner.Run(m, tmp_path)
    run.bind_build("22.0.400", "cX")
    assert run.evidence_path.name == "apex_truth_22.0.400.json"


def test_runner_legacy_prefix_default(tmp_path):
    import runner  # noqa: E402
    run = runner.Run(ms.validate_mission(_base()), tmp_path)
    run.bind_build("22.0.368", "cX")
    assert run.evidence_path.name == "lop_truth_22.0.368.json"


# --- version_agreement APEX stamp contract ---------------------------------

def test_apex_stamp_is_current_build():
    assert _load_va().apex_stamp() == "22.0.400"


def test_apex_agreement_green_against_committed_artifact():
    v = _load_va().apex_agreement()
    assert v["ok"] is True, v["reason"]


def test_apex_agreement_detects_stamp_drift(monkeypatch):
    va = _load_va()
    monkeypatch.setattr(va, "apex_stamp", lambda: "99.9.999")
    v = va.apex_agreement()
    assert v["ok"] is False
    assert "drift" in v["reason"]


def test_apex_agreement_missing_artifact_is_not_drift(monkeypatch):
    va = _load_va()
    monkeypatch.setattr(va, "latest_apex_artifact", lambda: None)
    v = va.apex_agreement()
    assert v["ok"] is True
    assert "nothing to compare" in v["reason"]
