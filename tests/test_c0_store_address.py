"""C-0: the substrate's address + loud backend fallback.

Address half. For an UNSAVED scene ``hou.hipFile.path()`` returns a FULL
path ending in ``untitled.hip`` (production logs 2026-07-31 14:42:14 and
2026-08-01 10:25:01 show ``C:/Program Files/.../bin/untitled.hip``), so the
old guard ``hip_path != "untitled.hip"`` never matched, the temp-dir branch
was dead code, and the store landed at ``<process-cwd>/untitled.hip/.synapse``
— inside Program Files, where mkdir raised PermissionError WinError 5.
Detection is now by basename via ``store.hip_is_unsaved``, with
``hou.hipFile.isNewFile()`` (getattr-guarded — the h22 symbol table is
depth-limited and cannot verdict hipFile members) disambiguating a scene
genuinely SAVED as untitled.hip.

Loudness half. When $SYNAPSE_MEMORY_BACKEND selects moneta/shadow but the
process ends up serving jsonl, the swap is recorded process-locally
(``store.backend_fallback()``) and the doctor's ``moneta_substrate`` check
fails with the attempted path and reason. The fallback BEHAVIOUR is
unchanged — the process stays alive on jsonl; only the silence was the
defect.
"""

import logging
import types
from pathlib import Path

import pytest

from synapse.memory import store as store_mod
from synapse.memory.store import SynapseMemory, hip_is_unsaved


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fake_hou(hip_path, temp_dir, is_new=None, with_is_new=True):
    """A minimal hou stand-in for _resolve_project_path."""
    hip_file = types.SimpleNamespace(path=lambda: hip_path)
    if with_is_new:
        hip_file.isNewFile = lambda: is_new
    text = types.SimpleNamespace(expandString=lambda s: str(temp_dir))
    return types.SimpleNamespace(hipFile=hip_file, text=text)


def _resolve(monkeypatch, fake_hou):
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store_mod, "hou", fake_hou, raising=False)
    sm = SynapseMemory.__new__(SynapseMemory)  # no __init__: no disk writes
    return sm._resolve_project_path(None)


@pytest.fixture(autouse=True)
def _clean_module_flags():
    store_mod._BACKEND_FALLBACK = None
    announced = store_mod._UNSAVED_RELOCATION_ANNOUNCED
    yield
    store_mod._BACKEND_FALLBACK = None
    store_mod._UNSAVED_RELOCATION_ANNOUNCED = announced


# ---------------------------------------------------------------------------
# address: unsaved scene -> $HOUDINI_TEMP_DIR
# ---------------------------------------------------------------------------

def test_unsaved_full_path_routes_to_temp(monkeypatch, tmp_path):
    """The exact production shape: full path ending in untitled.hip."""
    hip = "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/untitled.hip"
    out = _resolve(monkeypatch, _fake_hou(hip, tmp_path, is_new=True))
    assert out == Path(str(tmp_path)) / "untitled"
    assert "Program Files" not in str(out)


def test_saved_scene_routes_to_project(monkeypatch, tmp_path):
    hip = str(tmp_path / "shots" / "seq010_v002.hip")
    out = _resolve(monkeypatch, _fake_hou(hip, tmp_path / "TEMP", is_new=False))
    assert out == Path(hip)


def test_scene_genuinely_saved_as_untitled_hip_stays_in_project(
    monkeypatch, tmp_path
):
    """Discriminator choice, documented: a scene really named untitled.hip in
    a real project dir is told apart by hou.hipFile.isNewFile() == False and
    keeps its project-local store."""
    hip = str(tmp_path / "myproject" / "untitled.hip")
    out = _resolve(monkeypatch, _fake_hou(hip, tmp_path / "TEMP", is_new=False))
    assert out == Path(hip)


def test_untitled_basename_without_isnewfile_falls_back_to_temp(
    monkeypatch, tmp_path
):
    """When isNewFile is absent (getattr-guarded phantom defense), basename
    wins and the scene is treated as unsaved — the documented conservative
    fallback: a wrong-but-writable temp address over a possibly unwritable
    launch-directory address."""
    hip = str(tmp_path / "myproject" / "untitled.hip")
    out = _resolve(monkeypatch, _fake_hou(hip, tmp_path, with_is_new=False))
    assert out == Path(str(tmp_path)) / "untitled"


def test_hip_is_unsaved_unit():
    assert hip_is_unsaved(None) is True
    assert hip_is_unsaved("") is True
    assert hip_is_unsaved("/projects/shot_v001.hip") is False
    # basename-only (no hou module passed): untitled.hip reads unsaved
    assert hip_is_unsaved("C:/anywhere/untitled.hip") is True


def test_hip_is_unsaved_survives_a_raising_isnewfile(tmp_path):
    """A broken isNewFile must not take the resolver down — basename verdict
    stands."""
    hip_file = types.SimpleNamespace(
        isNewFile=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    fake = types.SimpleNamespace(hipFile=hip_file)
    assert hip_is_unsaved("C:/x/untitled.hip", fake) is True


def test_unsaved_relocation_is_announced_once(monkeypatch, tmp_path, caplog):
    """Migration honesty: first unsaved-scene resolution says plainly where
    the store lives now and that old cwd-based stores are not carried over —
    once per process, not once per resolution."""
    store_mod._UNSAVED_RELOCATION_ANNOUNCED = False
    hip = "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/untitled.hip"
    with caplog.at_level(logging.INFO, logger="synapse.memory"):
        _resolve(monkeypatch, _fake_hou(hip, tmp_path, is_new=True))
        _resolve(monkeypatch, _fake_hou(hip, tmp_path, is_new=True))
    hits = [r for r in caplog.records if "NOT carried over" in r.getMessage()]
    assert len(hits) == 1, [r.getMessage() for r in caplog.records]
    assert "$HOUDINI_TEMP_DIR" in hits[0].getMessage()


# ---------------------------------------------------------------------------
# loudness: selected-but-not-serving is recorded and the doctor fails on it
# ---------------------------------------------------------------------------

def test_moneta_init_failure_is_loud_and_recorded(monkeypatch, tmp_path, caplog):
    """The 2026-07-31/08-01 defect: PermissionError during moneta init fell
    back to jsonl with one quiet line. The fallback must stay (process
    alive), but it must name the attempted path and be queryable."""
    from synapse.memory import moneta_runtime, moneta_store
    from synapse.memory.store import MemoryStore

    monkeypatch.setattr(moneta_runtime, "moneta_available", lambda: True)
    monkeypatch.setattr(moneta_runtime, "import_error", lambda: None)

    def denied(*_a, **_k):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                        staticmethod(denied))
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")

    with caplog.at_level(logging.ERROR, logger="synapse.memory"):
        store = SynapseMemory._make_store(None, tmp_path / "proj" / ".synapse")

    # behaviour unchanged: alive, serving jsonl
    assert isinstance(store, MemoryStore)

    # recorded
    fb = store_mod.backend_fallback()
    assert fb is not None
    assert fb["requested"] == "moneta"
    assert fb["served"] == "jsonl"
    assert "proj" in fb["storage_dir"]
    assert "PermissionError" in fb["reason"]

    # loud, with the attempted path and the consequence in one message
    said = [r.getMessage() for r in caplog.records
            if "FELL BACK" in r.getMessage()]
    assert said, [r.getMessage() for r in caplog.records]
    assert str(tmp_path / "proj" / ".synapse") in said[0]


def test_clean_construction_clears_the_flag(monkeypatch, tmp_path):
    """The flag reflects the most recent construction: a later clean jsonl
    build must not leave a stale fallback for the doctor to report."""
    store_mod._record_backend_fallback("moneta", tmp_path, "stale")
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    SynapseMemory._make_store(None, tmp_path / "clean" / ".synapse")
    assert store_mod.backend_fallback() is None


def test_doctor_surfaces_the_fallback(monkeypatch, tmp_path):
    from synapse.server import doctor

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    store_mod._record_backend_fallback(
        "moneta", tmp_path / "proj" / ".synapse",
        "init failed: PermissionError: [Errno 13] Access is denied",
    )
    check = doctor._check_moneta_substrate()
    assert check["status"] == "fail"
    assert "fell back" in check["detail"].lower()
    assert str(tmp_path / "proj" / ".synapse") in check["detail"]
    assert check["result"]["fallback"]["requested"] == "moneta"


def test_doctor_stays_quiet_on_a_jsonl_seat_even_with_a_stale_flag(
    monkeypatch, tmp_path
):
    """No alarm fatigue: the backend-not-selected skip still wins — the
    fallback verdict only fires on a seat that asked for moneta/shadow."""
    from synapse.server import doctor

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    store_mod._record_backend_fallback("moneta", tmp_path, "whatever")
    check = doctor._check_moneta_substrate()
    assert check["status"] == "skipped"
    assert "not selected" in check["detail"]
