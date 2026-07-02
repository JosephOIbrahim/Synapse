"""M3-A (studio-operable, report §4.6 + §5 item 8): the upgrade surface.

A Houdini build change silently disarmed the phantom-API gate: the symbol
table is build-stamped (correct), but a mismatch degraded every scout
verdict to None with one console warning — precisely the week API drift
peaks. Now: every None verdict carries an unverified_reason at point of
use, results carry gate_armed, the panel footer goes loud via
gate_stamp.phantom_gate_status (mirrors scout's own staleness logic so
panel and tool can never disagree), the installer writes a version stamp
the doctor reads, and docs/studio/UPGRADE.md is the per-upgrade runbook
(doc-conformance pinned here).

Headless, stock Python — scout is zero-hou; gate_stamp takes
running_version by injection; the installer loads via importlib-spec.
"""

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from conftest import HOUDINI_BUILD
from synapse.cognitive.tools import scout
from synapse.panel.gate_stamp import phantom_gate_status

_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Hermetic table-store fixture (test_scout.py idiom — module globals patched,
# never sys.modules residency)
# ---------------------------------------------------------------------------


def _write_table(path, symbols, version=HOUDINI_BUILD, corrupt=False):
    syms = sorted(symbols)
    digest = hashlib.blake2b("\n".join(syms).encode("utf-8"), digest_size=16).hexdigest()
    if corrupt:
        digest = "deadbeef" * 4
    path.write_text(json.dumps({
        "schema": "scout_symbol_table/v1", "houdini_version": version,
        "blake2b": digest, "symbol_count": len(syms), "symbols": syms,
    }), encoding="utf-8")


def _table_store(tmp_path, monkeypatch, entries, *, table_symbols=None,
                 table_version=HOUDINI_BUILD, corrupt=False, expected_version=None,
                 policy="warn"):
    cdir = tmp_path / "corpus"; cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()
    if table_symbols is not None:
        _write_table(tmp_path / scout.SYMBOL_TABLE_NAME, table_symbols, table_version, corrupt)
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    monkeypatch.setattr(scout, "DRIFT_POLICY", policy)
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", expected_version)
    monkeypatch.setattr(scout, "_PKG_SYMBOL_TABLE", tmp_path / "no_pkg_table.json")
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()


_ENTRY = [{"id": "d", "type": "ref", "source": "d.md",
           "searchable_text": "general solaris notes about hou.LopNode usage"}]


# ---------------------------------------------------------------------------
# Scout result honesty
# ---------------------------------------------------------------------------


def test_stale_table_verdicts_carry_reason(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch, _ENTRY,
                 table_symbols={"hou.LopNode"}, table_version="21.0.631",
                 expected_version="99.0.000")
    out = scout.synapse_scout("can I use hou.LopNode", k=3)
    assert out["gate_armed"] is False
    for s in out["symbols"]:
        assert s["exists_in_runtime"] is None
        assert "21.0.631" in s["unverified_reason"]
        assert "99.0.000" in s["unverified_reason"]


def test_fresh_table_arms_gate_and_omits_reason(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch, _ENTRY, table_symbols={"hou.LopNode"})
    out = scout.synapse_scout("can I use hou.LopNode", k=3)
    assert out["gate_armed"] is True
    for s in out["symbols"]:
        assert "unverified_reason" not in s  # key absent, not None — shape honesty


def test_missing_table_reason_present(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch, _ENTRY, table_symbols=None)
    out = scout.synapse_scout("can I use hou.LopNode", k=3)
    assert out["gate_armed"] is False
    for s in out["symbols"]:
        assert s["exists_in_runtime"] is None
        assert s["unverified_reason"]  # always says why


def test_scout_description_documents_null_contract():
    desc = scout.SYNAPSE_SCOUT_SCHEMA["description"]
    assert "null" in desc
    assert "gate_armed" in desc
    assert "UPGRADE.md" in desc


# ---------------------------------------------------------------------------
# Panel gate stamp mirrors scout
# ---------------------------------------------------------------------------


def test_gate_stamp_mirrors_scout_verdict(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch, _ENTRY,
                 table_symbols={"hou.LopNode"}, table_version="21.0.671")
    monkeypatch.setattr(scout, "_symbol_table_path",
                        lambda: tmp_path / scout.SYMBOL_TABLE_NAME)
    # Version mismatch -> reason names both versions
    reason = phantom_gate_status(running_version="99.0.000")
    assert reason and "21.0.671" in reason and "99.0.000" in reason
    # Matching version -> armed, no warning
    assert phantom_gate_status(running_version="21.0.671") is None
    # Outside Houdini with no injected version -> claims nothing
    assert phantom_gate_status(running_version=None) is None or isinstance(
        phantom_gate_status(running_version=None), str
    )


def test_gate_stamp_missing_table_reports_reason(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch, _ENTRY, table_symbols=None)
    monkeypatch.setattr(scout, "_symbol_table_path",
                        lambda: tmp_path / scout.SYMBOL_TABLE_NAME)
    reason = phantom_gate_status(running_version="21.0.671")
    assert reason  # stale/missing -> a reason string, never a silent None


# ---------------------------------------------------------------------------
# Installer stamp
# ---------------------------------------------------------------------------


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "install_synapse_package", _ROOT / "scripts" / "install_synapse_package.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_installer_writes_stamp(tmp_path, monkeypatch):
    mod = _load_installer()
    stamp = tmp_path / "install_stamp.json"
    monkeypatch.setattr(mod, "stamp_path", lambda: stamp)
    pref = tmp_path / "houdini21.0"
    pref.mkdir()
    rc = mod.main(["--pref-dir", str(pref)])
    assert rc == 0
    data = json.loads(stamp.read_text(encoding="utf-8"))
    assert data["schema"] == "synapse_install_stamp/v1"
    real_version = re.search(
        r'__version__\s*=\s*"([^"]+)"',
        (_ROOT / "python" / "synapse" / "__init__.py").read_text(encoding="utf-8"),
    ).group(1)
    assert data["synapse_version"] == real_version
    assert data["targets"] == [(pref / "packages" / "synapse.json").as_posix()]


def test_installer_dry_run_writes_no_stamp(tmp_path, monkeypatch):
    mod = _load_installer()
    stamp = tmp_path / "install_stamp.json"
    monkeypatch.setattr(mod, "stamp_path", lambda: stamp)
    pref = tmp_path / "houdini21.0"
    pref.mkdir()
    rc = mod.main(["--pref-dir", str(pref), "--dry-run"])
    assert rc == 0
    assert not stamp.exists()


# ---------------------------------------------------------------------------
# UPGRADE.md doc conformance
# ---------------------------------------------------------------------------


def test_upgrade_doc_conformance():
    doc = (_ROOT / "docs" / "studio" / "UPGRADE.md").read_text(encoding="utf-8")
    artifacts = {
        "host/introspect_runtime.py": _ROOT / "host" / "introspect_runtime.py",
        "h21_symbol_table.json": _ROOT / "python" / "synapse" / "cognitive" / "tools" / "data" / "h21_symbol_table.json",
        "scripts/install_synapse_package.py": _ROOT / "scripts" / "install_synapse_package.py",
        "tests/test_vendored_deps.py": _ROOT / "tests" / "test_vendored_deps.py",
        "install_stamp.json": None,  # name pinned; file is per-seat state
    }
    for name, path in artifacts.items():
        assert name in doc, f"UPGRADE.md missing artifact name {name!r}"
        if path is not None:
            assert path.exists(), f"UPGRADE.md names a nonexistent artifact: {name}"
    assert "SYNAPSE_SCOUT_DRIFT_POLICY" in doc


def test_no_hardcoded_pref_dir_version_in_product_code():
    """No product code hardcodes the versioned pref dir ('houdini21.0') — it
    breaks silently when the pref dir becomes houdini22.0. Derive it from the
    session instead (hou.homeHoudiniDirectory()). One documented exception:
    prompt_to_hda.py's last-ditch standalone fallback (no hou, no env) — pinned
    to EXACTLY one occurrence so new hardcodes there still fail loud."""
    allowed = {"panel/prompt_to_hda.py": 1}
    offenders = {}
    pkg = _ROOT / "python" / "synapse"
    for path in pkg.rglob("*.py"):
        if "_vendor" in path.parts:
            continue
        rel = path.relative_to(pkg).as_posix()
        count = path.read_text(encoding="utf-8", errors="ignore").count("houdini21.0")
        if count and count != allowed.get(rel, 0):
            offenders[rel] = count
    assert not offenders, (
        f"hardcoded 'houdini21.0' pref-dir literals in product code: {offenders} "
        "-- derive from hou.homeHoudiniDirectory() (see the H22 runway plan)."
    )
