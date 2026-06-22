"""Proves the scout's deterministic recon: it flags unconfirmed `owns` paths (the inferred-path
trap) and missing goalpost tests BEFORE any money is spent — read-only, no LLM."""
import scout


def test_verify_target_extraction():
    assert "tests/panel/test_x.py" in scout._verify_targets("pytest -q tests/panel/test_x.py::test_y")
    got = scout._verify_targets(
        "python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel")
    assert "python/synapse/panel/tokens.py" in got


def test_glob_resolution_flags_inferred_paths(tmp_path, monkeypatch):
    (tmp_path / "python" / "synapse" / "panel").mkdir(parents=True)
    (tmp_path / "python" / "synapse" / "panel" / "face_work.py").write_text("x = 1")
    monkeypatch.setattr(scout, "ROOT", str(tmp_path))
    assert scout._glob_count("python/synapse/panel/**") >= 1      # real path resolves
    assert scout._glob_count("python/synapse/daemon/**") == 0     # inferred path: unconfirmed


def test_scout_contract_flags_attention(tmp_path, monkeypatch):
    (tmp_path / "python" / "synapse" / "panel").mkdir(parents=True)
    (tmp_path / "python" / "synapse" / "panel" / "face_review.py").write_text("x = 1")
    cdir = tmp_path / ".synapse" / "contracts"
    cdir.mkdir(parents=True)
    (cdir / "demo.yaml").write_text(
        "id: demo\nautonomy: amber\nmodel: opusplan\n"
        "owns:\n  - python/synapse/panel/**\n  - python/synapse/daemon/**\n"
        "features:\n  - description: d\n    verify: pytest -q tests/panel/test_missing.py::t\n    passing: false\n"
    )
    monkeypatch.setattr(scout, "ROOT", str(tmp_path))
    monkeypatch.setattr(scout, "SYN", str(tmp_path / ".synapse"))
    r = scout.scout_contract("demo")
    assert "python/synapse/daemon/**" in r["unconfirmed_paths"]
    assert "tests/panel/test_missing.py" in r["verify_targets_missing"]
    assert r["status"].startswith("needs-attention")
