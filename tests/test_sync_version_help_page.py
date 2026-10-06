"""The help page's header version is a sync_version.py surface (rope:U01)."""
import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "sync_version_under_test", ROOT / "scripts" / "sync_version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_help_page_surface_matches_version_file():
    sv = _load()
    assert "help_page" in sv.SURFACES
    canonical = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    assert sv.read_surface("help_page") == canonical


def test_write_surface_changes_only_the_version_text(tmp_path, monkeypatch):
    sv = _load()
    rel = sv.SURFACES["help_page"][1]
    copy = tmp_path / rel
    copy.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / rel, copy)
    before = copy.read_text(encoding="utf-8")
    old = sv.read_surface("help_page")
    monkeypatch.setattr(sv, "ROOT", tmp_path)

    sv.write_surface("help_page", "9.8.7")

    after = copy.read_text(encoding="utf-8")
    assert sv.read_surface("help_page") == "9.8.7"
    assert after == before.replace(f"<span>v{old}</span>", "<span>v9.8.7</span>", 1)
