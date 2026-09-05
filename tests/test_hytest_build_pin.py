"""B10: the hytest shim must pin to the build the committed symbol table
describes, not to whichever Houdini happens to be newest on the host.

Pure-Python: loads .synapse/hytest.py by path, fakes the installed builds
under tmp_path, and stubs the usability probe so no hython is ever launched.
"""
import glob
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_hytest():
    spec = importlib.util.spec_from_file_location(
        "hytest_under_test", REPO_ROOT / ".synapse" / "hytest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BUILDS = ("22.0.429", "22.0.400", "21.0.773")


@pytest.fixture
def host(monkeypatch, tmp_path):
    """A fake host: three installed hythons, no PATH hython, no pin, a
    committed h22 symbol table stamped 22.0.400, usability always true."""
    hytest = _load_hytest()
    installs = {}
    for ver in BUILDS:
        exe = tmp_path / f"Houdini {ver}" / "bin" / "hython.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("", encoding="utf-8")
        installs[ver] = str(exe).replace("\\", "/")
    data = tmp_path / "data"
    data.mkdir()
    (data / "h22_symbol_table.json").write_text(
        json.dumps({"schema": "scout_symbol_table/v1",
                    "houdini_version": "22.0.400", "symbols": []}),
        encoding="utf-8")

    monkeypatch.delenv("SYNAPSE_HYTHON", raising=False)
    monkeypatch.setattr(hytest, "which", lambda name: None)
    real_glob = glob.glob  # the symbol-table glob must keep working

    def _fake_glob(pat):
        if "Side Effects" in pat:
            return list(installs.values())
        if "hfs" in pat or "Applications" in pat:
            return []
        return real_glob(pat)
    monkeypatch.setattr(hytest.glob, "glob", _fake_glob)
    monkeypatch.setattr(hytest, "_usable", lambda path: True)
    monkeypatch.setattr(hytest, "SYMBOL_TABLE_DIR", str(data), raising=False)

    def _no_launch(*a, **k):  # pragma: no cover - guard
        raise AssertionError("hytest launched a process: %r" % (a,))
    monkeypatch.setattr(hytest.subprocess, "run", _no_launch)
    return hytest, installs, data


def test_prefers_build_matching_committed_symbol_table(host):
    hytest, installs, _ = host
    assert hytest.find_hython() == installs["22.0.400"], (
        "newest-first selected a build with no committed symbol table")


def test_falls_back_to_newest_when_no_stamp_matches(host):
    hytest, installs, data = host
    (data / "h22_symbol_table.json").write_text(
        json.dumps({"houdini_version": "22.0.999", "symbols": []}),
        encoding="utf-8")
    assert hytest.find_hython() == installs["22.0.429"]


def test_explicit_pin_beats_stamp(host, monkeypatch):
    hytest, installs, _ = host
    monkeypatch.setenv("SYNAPSE_HYTHON", installs["21.0.773"])
    assert hytest.find_hython() == installs["21.0.773"]


def test_which_prints_selected_hython_and_launches_nothing(host, capsys):
    hytest, installs, _ = host
    rc = hytest.main(["--which"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip() == installs["22.0.400"]
    assert "22.0.400" in out.err and "symbol-table" in out.err
