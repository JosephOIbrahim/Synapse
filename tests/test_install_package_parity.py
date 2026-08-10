"""Env-surface parity: installer resolver vs the tracked Houdini package.

The tracked ``packages/synapse.json`` and the installer's ``build_package()``
are two authors of the same contract -- the env surface a Houdini session
needs. On 2026-08-09 they drifted: the tracked package registered the
MonetaMemory USD schema (PXR_PLUGINPATH_NAME) and selected the moneta
backend; the resolver did not. Only resolver output ever reaches a prefs
dir, so the schema went unregistered and Moneta's USD substrate silently
degraded to MockUsdTarget on H22.

These tests pin the env-var NAME sets together. Values legitimately differ
(tracked = $-vars, resolved = absolute paths); names may not.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _installer():
    spec = importlib.util.spec_from_file_location(
        "install_synapse_package",
        REPO_ROOT / "scripts" / "install_synapse_package.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tracked_env_names() -> set:
    data = json.loads(
        (REPO_ROOT / "packages" / "synapse.json").read_text(encoding="utf-8")
    )
    return {e["var"] for e in data["env"]}


def _fake_seat(tmp_path: Path, with_schema: bool = True) -> Path:
    """A repo checkout with a sibling Moneta, the shape build_package probes."""
    repo = tmp_path / "Synapse"
    (repo / "python").mkdir(parents=True)
    (repo / "houdini").mkdir()
    src = tmp_path / "Moneta" / "src"
    src.mkdir(parents=True)
    if with_schema:
        schema = tmp_path / "Moneta" / "schema"
        schema.mkdir()
        (schema / "plugInfo.json").write_text("{}", encoding="utf-8")
    return repo


def test_resolver_env_names_match_tracked_package(tmp_path):
    """With a full Moneta seat, resolver and tracked package must author the
    exact same env-var names. A new var added to either surface alone fails
    here -- that failure IS the drift alarm."""
    mod = _installer()
    repo = _fake_seat(tmp_path, with_schema=True)
    resolved = {e["var"] for e in mod.build_package(repo)["env"]}
    assert resolved == _tracked_env_names()


def test_schema_var_requires_real_pluginfo(tmp_path):
    """No plugInfo.json on disk -> no PXR_PLUGINPATH_NAME entry. An env var
    pointing at nothing is an asserted claim, not an observed one."""
    mod = _installer()
    repo = _fake_seat(tmp_path, with_schema=False)
    resolved = {e["var"] for e in mod.build_package(repo)["env"]}
    assert "PXR_PLUGINPATH_NAME" not in resolved
    # The backend flag still rides with a Moneta src checkout: store selection
    # has a loud fallback (store.py), schema registration does not.
    assert "SYNAPSE_MEMORY_BACKEND" in resolved


def test_no_moneta_means_no_moneta_vars(tmp_path):
    """A seat with no Moneta sibling authors none of the Moneta trio."""
    mod = _installer()
    repo = tmp_path / "Synapse"
    (repo / "python").mkdir(parents=True)
    (repo / "houdini").mkdir()
    resolved = {e["var"] for e in mod.build_package(repo)["env"]}
    assert resolved.isdisjoint(
        {"MONETA_SRC", "PXR_PLUGINPATH_NAME", "SYNAPSE_MEMORY_BACKEND"}
    )


def test_schema_value_is_the_pluginfo_dir(tmp_path):
    """The registered path must be the directory that HOLDS plugInfo.json --
    USD scans PXR_PLUGINPATH_NAME entries for plugInfo, not grandchildren."""
    mod = _installer()
    repo = _fake_seat(tmp_path, with_schema=True)
    vals = [e["value"] for e in mod.build_package(repo)["env"]
            if e["var"] == "PXR_PLUGINPATH_NAME"]
    assert len(vals) == 1
    assert (Path(vals[0]) / "plugInfo.json").is_file()
