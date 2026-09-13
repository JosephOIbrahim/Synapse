"""Focused G2 checks: missing evidence cannot qualify a host truth claim."""
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "harness/verify/version_agreement.py"
_spec = importlib.util.spec_from_file_location("g2_version_agreement", VERIFIER)
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)


@pytest.fixture
def specimen(tmp_path):
    receipt = json.loads((ROOT / verifier.GRAPH_RECEIPT_PATH).read_text(encoding="utf-8-sig"))
    for relative in verifier.GRAPH_SOURCE_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(encoding="utf-8-sig"), encoding="utf-8")
    for relative in verifier.GRAPH_RECEIPT_PATHS.values():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(encoding="utf-8-sig"), encoding="utf-8")
    artifact = tmp_path / verifier.GRAPH_RECEIPT_PATH
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    return tmp_path, artifact, receipt


def check(root, **kwargs):
    return verifier.graph_agreement(repo_root=root, **kwargs)


def test_checked_in_receipt_matches_source_and_observed_runtime():
    result = verifier.graph_agreement(runtime_build="22.0.417")
    assert result["status"] == "PASS", result
    assert result["ok"] is True
    assert result["runtime_comparison"]["status"] == "PASS"
    assert len(result["stamps"]) == 3


def test_offline_check_does_not_invent_current_runtime():
    result = verifier.graph_agreement()
    assert result["status"] == "PASS"
    assert result["runtime_comparison"] == {"status": "UNKNOWN", "build": None}
    assert "recorded headless" in result["scope"]


@pytest.mark.parametrize("build", ["22.0.399", "21.0.671", "", "22.0"])
def test_runtime_mismatch_is_failure(build):
    result = verifier.graph_agreement(runtime_build=build)
    assert result["status"] == "FAIL"
    assert not result["ok"]
    assert result["runtime_comparison"]["status"] == "FAIL"


def test_missing_receipt_is_unknown(tmp_path):
    result = check(tmp_path)
    assert result["status"] == "UNKNOWN"
    assert not result["ok"]


@pytest.mark.parametrize("text", ["{", "null", "[]", "{}", '{"schema": "unsupported"}'])
def test_malformed_receipt_is_unknown(tmp_path, text):
    path = tmp_path / "receipt.json"
    path.write_text(text, encoding="utf-8")
    result = check(tmp_path, receipt_path=path)
    assert result["status"] == "UNKNOWN"
    assert not result["ok"]


@pytest.mark.parametrize("field", ["build", "checks", "symbols", "seeds", "source", "status"])
def test_missing_required_evidence_is_unknown(specimen, field):
    root, artifact, receipt = specimen
    receipt.pop(field)
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    result = check(root)
    assert result["status"] == "UNKNOWN", result
    assert not result["ok"]


@pytest.mark.parametrize("name", verifier.GRAPH_REQUIRED_CHECKS)
@pytest.mark.parametrize("status,expected", [("FAIL", "FAIL"), ("UNKNOWN", "UNKNOWN"), ("SKIP", "UNKNOWN")])
def test_every_required_check_must_pass(specimen, name, status, expected):
    root, artifact, receipt = specimen
    receipt["checks"][name]["status"] = status
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    result = check(root)
    assert result["status"] == expected
    assert not result["ok"]


@pytest.mark.parametrize("mutation", ["absent", "false", "wrong_count", "unidentified"])
def test_dir_observations_must_be_complete(specimen, mutation):
    root, artifact, receipt = specimen
    if mutation == "absent":
        receipt["symbols"] = []
    elif mutation == "false":
        receipt["symbols"][0]["present"] = False
    elif mutation == "wrong_count":
        receipt["checks"]["symbols"]["observations"] += 1
    else:
        receipt["symbols"][0].pop("member")
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    result = check(root)
    assert result["status"] == "UNKNOWN"
    assert not result["ok"]


@pytest.mark.parametrize("surface", ["runtime", "seed"])
def test_internal_build_disagreement_fails(specimen, surface):
    root, artifact, receipt = specimen
    if surface == "runtime":
        receipt["checks"]["runtime"]["build"] = "22.0.400"
    else:
        receipt["seeds"][0]["houdini_version_stamp"] = "22.0.400"
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    assert check(root)["status"] == "FAIL"


@pytest.mark.parametrize("relative", verifier.GRAPH_SOURCE_PATHS)
@pytest.mark.parametrize("replacement", [
    "GRAPH-TRUTH-BUILD: 22.0.400", "no graph stamp",
    "GRAPH-TRUTH-BUILD: 22.0.417\nGRAPH-TRUTH-BUILD: 22.0.417",
])
def test_each_source_requires_one_matching_stamp(specimen, relative, replacement):
    root, _, _ = specimen
    target = root / relative
    target.write_text(target.read_text(encoding="utf-8").replace(
        "GRAPH-TRUTH-BUILD: 22.0.417", replacement), encoding="utf-8")
    result = check(root)
    assert result["status"] == "FAIL", result


@pytest.mark.parametrize("relative", verifier.GRAPH_SOURCE_PATHS)
def test_executable_edit_invalidates_receipt(specimen, relative):
    root, _, _ = specimen
    target = root / relative
    target.write_text(target.read_text(encoding="utf-8") + "\nG2_CHANGED = True\n", encoding="utf-8")
    result = check(root)
    assert result["status"] == "FAIL"
    assert "implementation changed" in result["reason"]


def test_truth_documentation_and_comment_edits_preserve_qualification(specimen):
    root, _, _ = specimen
    target = root / verifier.GRAPH_SOURCE_PATHS[0]
    text = target.read_text(encoding="utf-8").replace(
        "GRAPH-TRUTH-BUILD:", "Documentation clarification.\nGRAPH-TRUTH-BUILD:", 1)
    target.write_text(text + "\n# documentation-only clarification\n", encoding="utf-8-sig")
    assert check(root)["status"] == "PASS"


def test_missing_source_is_unknown(specimen):
    root, _, _ = specimen
    (root / verifier.GRAPH_SOURCE_PATHS[0]).unlink()
    result = check(root)
    assert result["status"] == "UNKNOWN"
    assert not result["ok"]


def test_missing_implementation_hash_is_unknown(specimen):
    root, artifact, receipt = specimen
    receipt["source"][verifier.GRAPH_SOURCE_PATHS[0]] = {}
    artifact.write_text(json.dumps(receipt), encoding="utf-8")
    assert check(root)["status"] == "UNKNOWN"


@pytest.mark.parametrize("extra,code,status", [
    ([], 0, "PASS"),
    (["--runtime-build", "22.0.417"], 0, "PASS"),
    (["--runtime-build", "22.0.400"], 0, "PASS"),
    (["--runtime-build", "22.0.399"], 1, "FAIL"),
    (["--graph-receipt", "missing.json"], 1, "UNKNOWN"),
])
def test_graph_cli_is_cwd_independent_and_cannot_spawn(monkeypatch, tmp_path, capsys, extra, code, status):
    def forbidden(*args, **kwargs):
        raise AssertionError("graph-only attempted a subprocess")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(VERIFIER), "--graph-only", *extra])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(VERIFIER), run_name="__main__")
    assert exc.value.code == code
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status


def test_graph_cli_refuses_fix(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(VERIFIER), "--graph-only", "--fix"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(VERIFIER), run_name="__main__")
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


@pytest.mark.parametrize("build", verifier.GRAPH_QUALIFIED_BUILDS)
def test_each_qualified_build_uses_its_own_receipt(build):
    result = verifier.graph_agreement(runtime_build=build)
    assert result["status"] == "PASS", result
    assert result["build"] == build
    assert Path(result["artifact"]).name == "graph_truth_%s.json" % build
    assert all(value == list(verifier.GRAPH_QUALIFIED_BUILDS)
               for value in result["stamps"].values())


def test_offline_audit_checks_both_receipts():
    result = verifier.graph_agreement()
    assert result["checked_builds"] == ["22.0.400", "22.0.417"]
    assert all(row["status"] == "PASS" for row in result["build_results"].values())
    assert all(row["runtime_comparison"]["status"] == "UNKNOWN"
               for row in result["build_results"].values())


@pytest.mark.parametrize("build", verifier.GRAPH_QUALIFIED_BUILDS)
def test_missing_one_receipt_cannot_qualify_both(specimen, build):
    root, _, _ = specimen
    (root / verifier.GRAPH_RECEIPT_PATHS[build]).unlink()
    assert check(root)["status"] == "UNKNOWN"
    assert check(root, runtime_build=build)["status"] == "UNKNOWN"


def test_a_417_receipt_cannot_substitute_for_400(specimen):
    root, artifact, _ = specimen
    result = check(root, runtime_build="22.0.400", receipt_path=artifact)
    assert result["status"] == "FAIL"
    assert result["runtime_comparison"]["status"] == "FAIL"


def test_a_failed_400_receipt_blocks_the_offline_audit(specimen):
    root, _, _ = specimen
    path = root / verifier.GRAPH_RECEIPT_PATHS["22.0.400"]
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["checks"]["build_readback"]["status"] = "FAIL"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    result = check(root)
    assert result["status"] == "FAIL"
    assert result["build_results"]["22.0.417"]["status"] == "PASS"
