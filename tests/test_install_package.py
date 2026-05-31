"""Tests for scripts/install_synapse_package.py — the Houdini package installer.

Standalone, no Houdini. Exercises the pure path-resolution + json-build logic and
the deploy/dry-run behavior against tmp dirs only (never the real prefs).
"""

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load_installer():
    path = _ROOT / "scripts" / "install_synapse_package.py"
    spec = importlib.util.spec_from_file_location("install_synapse_package", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inst = _load_installer()


def test_build_package_uses_absolute_repo_paths(tmp_path):
    repo = tmp_path / "Synapse"
    (repo / "python").mkdir(parents=True)
    (repo / "houdini").mkdir()
    pkg = inst.build_package(repo)
    assert pkg["name"] == "synapse"
    assert pkg["enable"] is True
    env = {e["var"]: e for e in pkg["env"]}
    assert env["SYNAPSE_ROOT"]["value"] == repo.as_posix()
    assert env["PYTHONPATH"]["value"] == (repo / "python").as_posix()
    assert env["PYTHONPATH"]["method"] == "prepend"
    assert pkg["path"] == (repo / "houdini").as_posix()


def test_moneta_src_included_only_when_sibling_exists(tmp_path):
    repo = tmp_path / "Synapse"
    repo.mkdir()
    # No sibling Moneta -> no MONETA_SRC entry.
    pkg = inst.build_package(repo)
    assert "MONETA_SRC" not in {e["var"] for e in pkg["env"]}
    # Create sibling ../Moneta/src -> MONETA_SRC appears, pointing at it.
    (tmp_path / "Moneta" / "src").mkdir(parents=True)
    pkg2 = inst.build_package(repo)
    env = {e["var"]: e["value"] for e in pkg2["env"]}
    assert env["MONETA_SRC"] == (tmp_path / "Moneta" / "src").as_posix()


def test_deploy_dry_run_writes_nothing(tmp_path):
    pref = tmp_path / "houdini21.0"
    target = inst.deploy(pref, {"name": "synapse"}, dry_run=True)
    assert target == pref / "packages" / "synapse.json"
    assert not target.exists()  # dry run wrote nothing


def test_deploy_writes_valid_json(tmp_path):
    pref = tmp_path / "houdini21.0"
    repo = tmp_path / "Synapse"
    (repo / "python").mkdir(parents=True)
    pkg = inst.build_package(repo)
    target = inst.deploy(pref, pkg, dry_run=False)
    assert target.exists()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["name"] == "synapse"
    assert any(e["var"] == "PYTHONPATH" for e in loaded["env"])


def test_pref_dir_detection_honors_env(tmp_path, monkeypatch):
    pref = tmp_path / "houdini21.0"
    pref.mkdir()
    monkeypatch.setenv("HOUDINI_USER_PREF_DIR", str(pref))
    cands = inst.candidate_pref_dirs()
    assert pref.resolve() in [c.resolve() for c in cands]


def test_main_dry_run_against_explicit_pref(tmp_path, capsys):
    pref = tmp_path / "houdini21.0"
    pref.mkdir()
    rc = inst.main(["--pref-dir", str(pref), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert not (pref / "packages" / "synapse.json").exists()


def test_repo_synced_package_json_is_valid_and_portable():
    # The version-controlled packages/synapse.json must be valid JSON and use
    # the portable $HOUDINI_PACKAGE_PATH derivation (no hard-coded user paths).
    repo_pkg = _ROOT / "packages" / "synapse.json"
    data = json.loads(repo_pkg.read_text(encoding="utf-8"))
    assert data["name"] == "synapse"
    blob = json.dumps(data)
    assert "$HOUDINI_PACKAGE_PATH" in blob
    assert "C:/Users" not in blob and "/home/" not in blob  # no user-specific paths
