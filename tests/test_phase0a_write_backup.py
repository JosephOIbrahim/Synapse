"""Phase 0a: the harness write-path (write_report) is atomic + generationally backed up.

write_report was already atomic (tmp+fsync+os.replace) and confined. Phase 0a adds
generational backup (DR: a corrupting overwrite must leave a recovery point) and binary.
These pins exercise the pure-Python primitive in a tmp dir -- no Houdini.
"""
import base64

import pytest

from synapse.cognitive.tools.write_report import write_report, ReportPathError


def test_atomic_write_basic(tmp_path):
    r = write_report("a/report.md", "hello", base_dir=str(tmp_path))
    assert r["ok"] is True
    assert (tmp_path / "a" / "report.md").read_text(encoding="utf-8") == "hello"
    assert r["bytes_written"] == 5
    assert r["backup"] is None  # no backups by default


def test_generational_backup_rotation(tmp_path):
    p = tmp_path / "ledger.md"
    write_report("ledger.md", "v1", base_dir=str(tmp_path), backups=2)
    r2 = write_report("ledger.md", "v2", base_dir=str(tmp_path), backups=2)
    r3 = write_report("ledger.md", "v3", base_dir=str(tmp_path), backups=2)

    assert p.read_text(encoding="utf-8") == "v3"                                 # current
    assert (tmp_path / "ledger.md.bak.1").read_text(encoding="utf-8") == "v2"     # newest backup
    assert (tmp_path / "ledger.md.bak.2").read_text(encoding="utf-8") == "v1"     # older backup
    assert not (tmp_path / "ledger.md.bak.3").exists()                           # keep=2
    assert r2["backup"].endswith("ledger.md.bak.1")
    assert r3["backup"].endswith("ledger.md.bak.1")


def test_backup_drops_oldest_beyond_keep(tmp_path):
    for v in ("v1", "v2", "v3", "v4"):
        write_report("x.txt", v, base_dir=str(tmp_path), backups=2)
    assert (tmp_path / "x.txt").read_text() == "v4"
    assert (tmp_path / "x.txt.bak.1").read_text() == "v3"
    assert (tmp_path / "x.txt.bak.2").read_text() == "v2"
    assert not (tmp_path / "x.txt.bak.3").exists()  # v1's generation dropped


def test_binary_round_trip(tmp_path):
    raw = bytes(range(256))
    encoded = base64.b64encode(raw).decode("ascii")
    r = write_report("blob.bin", encoded, base_dir=str(tmp_path), binary=True)
    assert r["binary"] is True
    assert (tmp_path / "blob.bin").read_bytes() == raw
    assert r["bytes_written"] == 256


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ReportPathError):
        write_report("../escape.md", "x", base_dir=str(tmp_path))
    with pytest.raises(ReportPathError):
        write_report("a/../../escape.md", "x", base_dir=str(tmp_path))


def test_no_tmp_files_left_behind(tmp_path):
    write_report("clean.md", "data", base_dir=str(tmp_path), backups=1)
    write_report("clean.md", "data2", base_dir=str(tmp_path), backups=1)
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == [], f"atomic write left tmp files: {leftovers}"
