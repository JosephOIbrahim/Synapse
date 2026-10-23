"""Regression tests for the release qualification gate itself.

The v5.97.7 qualification leg failed for reasons that were in the GATE, not
in the product. Four of them, each of which had to be fixed before the
release could be cut:

  D1  The gate compared the shipped maintenance tree against the builder's
      record with a plain set comparison. But the builder hashes the
      maintenance tree and only THEN writes maintenance-manifest.json into
      it, because a file cannot carry its own hash. The tree therefore holds
      one more file than the record, by construction, and the comparison
      could not pass for any build at all.
  D2  The gate read the engine's verdict from synapse-check.txt in Inno's
      temporary directory. Inno deletes that directory when it deinitialises,
      so the verdict survived only in the Setup's own log.
  D3  The gate tampered the SOURCE maintenance tree. The engine's guard
      reads app/maintenance, the folder Inno populates and the engine itself
      never creates, so the guard returned silently and the tamper test could
      not fail.
  D4  The published verification record hardcoded a sentence claiming the
      engine came from the compiled Setup's own extraction. It did not.

These tests pin the fixes. They are hermetic: no Houdini, no model, no
network, no compiled executable, and they do not touch the repository.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[4]
GATE = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "installer"

for _path in (str(GATE), str(INSTALLER)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from qualify_production import (compare_maintenance, engine_verdict,  # noqa: E402
                                iss_files_section_mentions_testbuild, redact_pids)
from synapse_setup.engine import check_maintenance  # noqa: E402
from synapse_setup.safety import SetupError  # noqa: E402


# --------------------------------------------------------------------- D1
def _staged_tree(root: Path):
    """A maintenance tree shaped exactly like the builder's.

    The builder hashes the tree, then writes the manifest into it. The
    record therefore has one entry fewer than the tree has files, and the
    manifest is the file that cannot appear in the record.
    """
    maintenance = root / "maintenance"
    maintenance.mkdir(parents=True)
    payloads = {
        "setup_cli.py": b"import synapse_setup\n",
        "synapse_setup/engine.py": b"VERSION = 1\n",
        "getting-started.html": b"<html><body>SYNAPSE</body></html>\n",
    }
    for name, data in payloads.items():
        path = maintenance / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    record = {name: hashlib.sha256(data).hexdigest()
              for name, data in payloads.items()}
    (maintenance / "maintenance-manifest.json").write_text(
        json.dumps({"schema": "synapse-maintenance-1", "files": record},
                   sort_keys=True),
        encoding="utf-8")
    return maintenance, record


def test_a_manifest_the_record_cannot_hash_still_compares_clean(tmp_path):
    """The builder's own shape must compare clean.

    This is the D1 defect: the record holds one entry fewer than the tree
    has files, so a plain set comparison reports the manifest as an extra
    file and fails every build, including correct ones.
    """
    maintenance, record = _staged_tree(tmp_path)
    ok, detail = compare_maintenance(record, maintenance)
    assert ok, detail
    assert "byte-identical" in detail


def test_a_changed_embedded_file_fails_the_comparison(tmp_path):
    maintenance, record = _staged_tree(tmp_path)
    (maintenance / "getting-started.html").write_bytes(b"tampered\n")
    ok, detail = compare_maintenance(record, maintenance)
    assert not ok
    assert "differing" in detail


def test_a_missing_embedded_file_fails_the_comparison(tmp_path):
    maintenance, record = _staged_tree(tmp_path)
    (maintenance / "getting-started.html").unlink()
    ok, detail = compare_maintenance(record, maintenance)
    assert not ok
    assert "missing" in detail


def test_a_manifest_whose_own_map_disagrees_fails_the_comparison(tmp_path):
    maintenance, record = _staged_tree(tmp_path)
    manifest = json.loads((maintenance / "maintenance-manifest.json").read_text(
        encoding="utf-8"))
    manifest["files"]["getting-started.html"] = "0" * 64
    (maintenance / "maintenance-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8")
    ok, detail = compare_maintenance(record, maintenance)
    assert not ok
    assert "file map differs" in detail


def test_a_manifest_with_the_wrong_schema_fails_the_comparison(tmp_path):
    maintenance, record = _staged_tree(tmp_path)
    manifest = json.loads((maintenance / "maintenance-manifest.json").read_text(
        encoding="utf-8"))
    manifest["schema"] = "synapse-maintenance-2"
    (maintenance / "maintenance-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8")
    ok, detail = compare_maintenance(record, maintenance)
    assert not ok
    assert "schema" in detail


def test_a_tree_with_no_manifest_fails_the_comparison(tmp_path):
    maintenance, record = _staged_tree(tmp_path)
    (maintenance / "maintenance-manifest.json").unlink()
    ok, detail = compare_maintenance(record, maintenance)
    assert not ok
    assert "no maintenance manifest" in detail


# --------------------------------------------------------------------- D2
def test_the_verdict_is_recovered_from_the_installers_own_log(tmp_path):
    """Inno deletes its temporary directory, so the log is the survivor."""
    out = tmp_path / "out"
    out.mkdir()
    log = out / "setup.log"
    log.write_text(
        "2026-10-23 14:22:39.092   PrepareToInstall failed: Houdini is running "
        "(houdini.exe PID 32832). Save your work and close Houdini, then retry.\n",
        encoding="utf-8")
    text, origin = engine_verdict(out, log)
    assert "Houdini is running" in text
    assert origin == "setup.log"


def test_a_surviving_verdict_file_is_preferred_over_the_log(tmp_path):
    out = tmp_path / "out"
    (out / "temp" / "is-ABC123").mkdir(parents=True)
    (out / "temp" / "is-ABC123" / "synapse-check.txt").write_text(
        "the engine's own verdict\n", encoding="utf-8")
    log = out / "setup.log"
    log.write_text("PrepareToInstall failed: something else entirely\n", encoding="utf-8")
    text, origin = engine_verdict(out, log)
    assert text == "the engine's own verdict"
    assert origin == "synapse-check.txt"


def test_a_json_verdict_file_is_read_when_no_text_file_survived(tmp_path):
    out = tmp_path / "out"
    (out / "temp" / "is-ABC123").mkdir(parents=True)
    (out / "temp" / "is-ABC123" / "synapse-check.json").write_text(
        json.dumps({"message": "Houdini is running (houdini.exe PID 1)."}),
        encoding="utf-8")
    text, origin = engine_verdict(out, out / "setup.log")
    assert "Houdini is running" in text
    assert origin == "synapse-check.json"


def test_no_surviving_verdict_is_reported_as_empty(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    text, origin = engine_verdict(out, out / "setup.log")
    assert text == ""
    assert origin is None


def test_process_ids_are_stripped_out_of_a_refusal_message():
    redacted = redact_pids("Houdini is running (houdini.exe PID 32832, hython.exe PID 7).")
    assert "32832" not in redacted
    assert "PID <n>" in redacted
    assert "Houdini is running" in redacted


# --------------------------------------------------------------------- D3
def test_the_engines_guard_is_silent_without_the_installed_folder(tmp_path):
    """Why the old tamper test could not fail.

    check_maintenance returns immediately when app/maintenance is absent, so
    a test that tampers the source tree is testing a code path that does
    nothing.
    """
    app = tmp_path / "application"
    app.mkdir()
    assert check_maintenance(app) is None


def test_the_engines_guard_refuses_a_changed_installed_file(tmp_path):
    app = tmp_path / "application"
    maintenance, _ = _staged_tree(app)
    assert check_maintenance(app) is None
    victim = maintenance / "getting-started.html"
    victim.write_bytes(b"tampered\n")
    with pytest.raises(SetupError) as failure:
        check_maintenance(app)
    assert "maintenance file was changed or removed" in str(failure.value)


def test_the_engines_guard_accepts_the_restored_installed_file(tmp_path):
    app = tmp_path / "application"
    maintenance, _ = _staged_tree(app)
    victim = maintenance / "getting-started.html"
    original = victim.read_bytes()
    victim.write_bytes(b"tampered\n")
    with pytest.raises(SetupError):
        check_maintenance(app)
    victim.write_bytes(original)
    assert check_maintenance(app) is None


def test_the_gate_tampers_the_installed_copy_not_the_source_tree():
    """The D3 defect, pinned on the gate's own source.

    The guard reads app/maintenance. Tampering engine_dir - the tree the
    engine was launched from - proves nothing, because the guard never looks
    there.
    """
    source = (GATE / "qualify_production.py").read_text(encoding="utf-8")
    assert 'victim = app / "maintenance" / "getting-started.html"' in source
    assert 'victim = engine_dir / "getting-started.html"' not in source


# --------------------------------------------------------------------- D4
def test_the_published_record_must_not_claim_the_setup_extracted_its_engine():
    """The D4 defect, pinned on the compose script's own source.

    The published verification record asserted that the engine was "the
    engine the compiled production Setup itself extracts". It was not: the
    production Setup refuses before it copies any file, so the engine came
    from the builder's staging directory, and the published text has to say
    which one it actually was.
    """
    source = (GATE / "compose_assets.py").read_text(encoding="utf-8")
    assert "the engine the compiled production Setup itself extracts" not in source
    assert "engine_source" in source


# ------------------------------------------------------------------ twin
def test_the_installers_files_section_is_not_conditional_on_the_test_build():
    """The twin-equality argument depends on this.

    The TestBuild define changes the product name, the sandbox argument and
    the home directory in the [Code] section. If it also changed what the
    [Files] section embeds, a TestSetup and a production Setup would carry
    different bytes and nothing measured against one could stand in for the
    other.
    """
    assert iss_files_section_mentions_testbuild(REPO / "installer" / "windows"
                                                 / "Synapse.iss") is False


def test_a_files_section_with_a_test_build_conditional_is_detected(tmp_path):
    iss = tmp_path / "Synapse.iss"
    iss.write_text("[Setup]\nAppName=x\n\n[Files]\n"
                   "Source: \"a\"; DestDir: \"{tmp}\"; Flags: dontcopy\n"
                   "#ifdef TestBuild\n"
                   "Source: \"b\"; DestDir: \"{tmp}\"\n"
                   "#endif\n\n[Code]\n", encoding="utf-8")
    assert iss_files_section_mentions_testbuild(iss) is True


def test_a_missing_files_section_is_reported_as_unknown(tmp_path):
    iss = tmp_path / "Synapse.iss"
    iss.write_text("[Setup]\nAppName=x\n\n[Code]\n", encoding="utf-8")
    assert iss_files_section_mentions_testbuild(iss) is None
