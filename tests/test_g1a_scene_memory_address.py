"""G1a: scene_memory must resolve to a writable address, and to ONE address.

The P0, verbatim from the live bridge on 2026-08-02::

    synapse_memory_write ->
    PermissionError [WinError 5] Access is denied:
      'C:\\Program Files\\Side Effects Software\\Houdini 22.0.397\\bin\\claude'

``ensure_scene_structure`` did ``os.makedirs(os.path.join(job_path, "claude"))``
with a raw ``$JOB``. For an UNSAVED scene Houdini reports ``$JOB``/``$HIP``
under its own install ``bin``, so the writer tried to create a directory inside
Program Files and died in front of the artist.

This is the C-0 disease in a second resolver. PR #60 (commit 19c299b) fixed the
same class in ``memory/store.py`` by adding ``hip_is_unsaved()`` and routing
unsaved scenes to ``$HOUDINI_TEMP_DIR``; ``scene_memory.py`` was never touched
by it. These tests pin the fix AND the thing that makes the fix safe: the
docstring contract that readers and the writer resolve identically.
"""

import logging
import os
import types

import pytest

from synapse.memory import scene_memory as sm


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Every test gets its own temp base and a clean relocation map."""
    sm._RELOCATED.clear()
    monkeypatch.setattr(sm, "HOU_AVAILABLE", False)
    monkeypatch.setattr(sm, "hou", None, raising=False)
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path / "HTEMP"))
    yield
    sm._RELOCATED.clear()


def _unwritable(monkeypatch, *denied_roots):
    """Make mkstemp AND makedirs refuse anything under *denied_roots*.

    Stands in for a Windows ACL: the paths exist and look ordinary, but this
    process may not create anything in them. os.access(W_OK) would happily say
    "writable" for exactly this shape, which is why the production code probes
    with a real file instead.
    """
    roots = [os.path.normpath(r) for r in denied_roots]

    def _denied(path):
        p = os.path.normpath(str(path))
        return any(p == r or p.startswith(r + os.sep) for r in roots)

    real_mkstemp = sm.tempfile.mkstemp
    real_makedirs = os.makedirs

    def fake_mkstemp(*a, **kw):
        if _denied(kw.get("dir", "")):
            raise PermissionError(13, "Access is denied")
        return real_mkstemp(*a, **kw)

    def fake_makedirs(path, *a, **kw):
        if _denied(path):
            raise PermissionError(13, "Access is denied", str(path))
        return real_makedirs(path, *a, **kw)

    monkeypatch.setattr(sm.tempfile, "mkstemp", fake_mkstemp)
    monkeypatch.setattr(sm.os, "makedirs", fake_makedirs)


# The exact production shape.
INSTALL_BIN = "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin"


# ---------------------------------------------------------------------------
# the P0 itself
# ---------------------------------------------------------------------------

def test_unsaved_scene_with_unwritable_job_does_not_raise(monkeypatch, tmp_path):
    """The live failure, reproduced by shape and then required not to happen."""
    install_bin = str(tmp_path / "ProgramFiles" / "Houdini 22.0.397" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)

    hip = os.path.join(install_bin, "untitled.hip")

    paths = sm.ensure_scene_structure(hip, install_bin)  # must not raise

    base = sm.unsaved_memory_base()
    assert paths["scene_dir"] == os.path.join(base, "claude")
    assert paths["project_dir"] == os.path.join(base, "claude")
    assert os.path.isdir(paths["scene_dir"])
    assert os.path.isdir(paths["project_dir"])
    for key in ("project_dir", "scene_dir", "project_md", "scene_md"):
        assert install_bin not in paths[key]


def test_the_old_code_would_have_raised_on_this_fixture(monkeypatch, tmp_path):
    """Guard the guard: prove the fixture actually denies writes, so the test
    above is passing because of the fix and not because nothing was blocked."""
    install_bin = str(tmp_path / "PF" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)
    with pytest.raises(PermissionError):
        sm.os.makedirs(os.path.join(install_bin, "claude"), exist_ok=True)


def test_relocation_is_loud(monkeypatch, tmp_path, caplog):
    """LOUDNESS over silence: name the attempted path, the fallback, the reason."""
    install_bin = str(tmp_path / "PF" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)

    with caplog.at_level(logging.WARNING, logger="synapse.scene_memory"):
        sm.ensure_scene_structure(os.path.join(install_bin, "untitled.hip"), install_bin)

    said = [r.getMessage() for r in caplog.records if "relocated" in r.getMessage()]
    assert said, [r.getMessage() for r in caplog.records]
    joined = "\n".join(said)
    assert install_bin in joined                      # attempted
    assert sm.unsaved_memory_base() in joined         # fallback
    assert "not writable" in joined                   # reason


def test_relocation_warns_once_per_parent(monkeypatch, tmp_path, caplog):
    """No alarm fatigue: repeated writes must not repeat the warning."""
    install_bin = str(tmp_path / "PF" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)
    hip = os.path.join(install_bin, "untitled.hip")

    with caplog.at_level(logging.WARNING, logger="synapse.scene_memory"):
        sm.ensure_scene_structure(hip, install_bin)
        sm.ensure_scene_structure(hip, install_bin)
        sm.ensure_scene_structure(hip, install_bin)

    hits = [r for r in caplog.records
            if "relocated" in r.getMessage() and install_bin in r.getMessage()]
    assert len(hits) == 1, [r.getMessage() for r in hits]


# ---------------------------------------------------------------------------
# the contract: reader and writer resolve to the SAME dir
# ---------------------------------------------------------------------------

def test_reader_and_writer_agree_unsaved_unwritable(monkeypatch, tmp_path):
    install_bin = str(tmp_path / "PF" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)
    hip = os.path.join(install_bin, "untitled.hip")

    paths = sm.ensure_scene_structure(hip, install_bin)

    # reader side, exactly as handlers_memory._scene_paths derives it
    assert os.path.join(sm.resolve_hip_dir(hip), "claude") == paths["scene_dir"]
    assert os.path.join(sm.resolve_job_dir(install_bin), "claude") == paths["project_dir"]

    # and the high-level readers land on the written content
    sm.write_memory_entry(paths["scene_dir"], {"content": "ARROW-IN-THE-KNEE"}, "note")
    ctx = sm.load_full_context(sm.resolve_hip_dir(hip), install_bin)
    assert "ARROW-IN-THE-KNEE" in ctx["scene"]["content"]

    status = sm.get_memory_status(sm.resolve_hip_dir(hip), install_bin)
    assert status["scene"]["evolution"] == "charmander"


def test_reader_and_writer_agree_saved_scene(monkeypatch, tmp_path):
    job = tmp_path / "show"
    hip_dir = job / "scenes"
    hip_dir.mkdir(parents=True)
    hip = hip_dir / "shot_010.hip"
    hip.write_text("", encoding="utf-8")

    paths = sm.ensure_scene_structure(str(hip), str(job))

    assert paths["scene_dir"] == os.path.join(str(hip_dir), "claude")
    assert paths["project_dir"] == os.path.join(str(job), "claude")
    assert os.path.join(sm.resolve_hip_dir(str(hip)), "claude") == paths["scene_dir"]
    assert os.path.join(sm.resolve_job_dir(str(job)), "claude") == paths["project_dir"]

    sm.write_memory_entry(paths["scene_dir"], {"content": "SWEETROLL"}, "note")
    ctx = sm.load_full_context(str(hip_dir), str(job))
    assert "SWEETROLL" in ctx["scene"]["content"]


def test_reader_follows_an_unpredicted_makedirs_failure(monkeypatch, tmp_path):
    """The last-line guard must not create a divergence.

    A dir that PROBES writable but REFUSES makedirs (a race, a revoked ACL)
    relocates the writer. The reader has to follow, or status reads an empty
    dir forever while writes land elsewhere.
    """
    job = str(tmp_path / "flaky")
    os.makedirs(job)
    hip = os.path.join(job, "shot.hip")
    with open(hip, "w", encoding="utf-8"):
        pass

    real_makedirs = os.makedirs

    def only_makedirs_denied(path, *a, **kw):
        if os.path.normpath(str(path)) == os.path.normpath(os.path.join(job, "claude")):
            raise PermissionError(13, "Access is denied")
        return real_makedirs(path, *a, **kw)

    monkeypatch.setattr(sm.os, "makedirs", only_makedirs_denied)

    paths = sm.ensure_scene_structure(hip, job)
    base = sm.unsaved_memory_base()
    assert paths["scene_dir"] == os.path.join(base, "claude")

    # reader, resolving from scratch, must land on the same place
    assert os.path.join(sm.resolve_hip_dir(hip), "claude") == paths["scene_dir"]
    assert os.path.join(sm.resolve_job_dir(job), "claude") == paths["project_dir"]


# ---------------------------------------------------------------------------
# a writable $JOB is still preferred -- the fix must not hijack real projects
# ---------------------------------------------------------------------------

def test_writable_job_is_preferred(monkeypatch, tmp_path):
    job = str(tmp_path / "real_show")
    hip_dir = os.path.join(job, "scenes")
    os.makedirs(hip_dir)
    hip = os.path.join(hip_dir, "hero_v003.hip")
    with open(hip, "w", encoding="utf-8"):
        pass

    paths = sm.ensure_scene_structure(hip, job)

    assert paths["project_dir"] == os.path.join(job, "claude")
    assert paths["scene_dir"] == os.path.join(hip_dir, "claude")
    assert sm.unsaved_memory_base() not in paths["project_dir"]
    assert not sm._RELOCATED, "a perfectly writable project must not relocate"


def test_unsaved_scene_with_a_writable_job_keeps_project_memory_in_the_job(
    monkeypatch, tmp_path
):
    """Scene relocates (it has no home yet); the artist's real $JOB does not.

    Only the SCENE is homeless when the hip is unsaved. A $JOB the artist
    deliberately set and that this process can write to is still the right
    address for PROJECT memory.
    """
    job = str(tmp_path / "artist_show")
    os.makedirs(job)
    hip = os.path.join(str(tmp_path / "wherever"), "untitled.hip")

    paths = sm.ensure_scene_structure(hip, job)

    assert paths["project_dir"] == os.path.join(job, "claude")
    assert paths["scene_dir"] == os.path.join(sm.unsaved_memory_base(), "claude")


def test_populated_readonly_dir_is_never_relocated(monkeypatch, tmp_path):
    """An existing claude/ IS the address, even where nothing can be created.

    Guards against the fix eating a read-only-but-populated project share:
    resolution short-circuits on an existing claude/ before any probe.
    """
    job = str(tmp_path / "share")
    os.makedirs(os.path.join(job, "claude"))
    with open(os.path.join(job, "claude", "project.md"), "w", encoding="utf-8") as f:
        f.write("# Project Memory: share\nHISTORY THAT MUST STAY READABLE\n")
    _unwritable(monkeypatch, job)

    assert sm.resolve_job_dir(job) == os.path.normpath(job)
    ctx = sm.load_full_context(job, job)
    assert "HISTORY THAT MUST STAY READABLE" in ctx["project"]["content"]


# ---------------------------------------------------------------------------
# resolver units
# ---------------------------------------------------------------------------

def test_resolvers_are_idempotent(monkeypatch, tmp_path):
    install_bin = str(tmp_path / "PF" / "bin")
    os.makedirs(install_bin)
    _unwritable(monkeypatch, install_bin)

    for start in (os.path.join(install_bin, "untitled.hip"), str(tmp_path / "x.hip")):
        once = sm.resolve_hip_dir(start)
        assert sm.resolve_hip_dir(once) == once

    once = sm.resolve_job_dir(install_bin)
    assert sm.resolve_job_dir(once) == once


def test_unsaved_base_matches_store(monkeypatch, tmp_path):
    """The two subsystems must agree on where an unsaved scene lives.

    store._resolve_project_path returns $HOUDINI_TEMP_DIR/untitled and puts
    .synapse under it; scene_memory puts claude/ under the same root. One
    scene, one address.
    """
    from synapse.memory import store as store_mod

    temp = tmp_path / "HT"
    fake_hou = types.SimpleNamespace(
        hipFile=types.SimpleNamespace(
            path=lambda: INSTALL_BIN + "/untitled.hip",
            isNewFile=lambda: True,
        ),
        text=types.SimpleNamespace(expandString=lambda s: str(temp)),
    )
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store_mod, "hou", fake_hou, raising=False)
    monkeypatch.setattr(sm, "HOU_AVAILABLE", True)
    monkeypatch.setattr(sm, "hou", fake_hou, raising=False)

    store_side = store_mod.SynapseMemory.__new__(
        store_mod.SynapseMemory)._resolve_project_path(None)

    assert os.path.normpath(str(store_side)) == sm.unsaved_memory_base()


def test_unexpanded_houdini_temp_dir_is_rejected(monkeypatch, tmp_path):
    """An undefined $HOUDINI_TEMP_DIR must not become a literal directory.

    hou.text.expandString hands an undefined token straight back. Joining it
    would create a directory literally named '$HOUDINI_TEMP_DIR' wherever the
    process is standing -- an address nobody can predict, which is the class
    of bug this module exists to prevent.
    """
    fake_hou = types.SimpleNamespace(
        text=types.SimpleNamespace(expandString=lambda s: s)  # identity == undefined
    )
    monkeypatch.setattr(sm, "HOU_AVAILABLE", True)
    monkeypatch.setattr(sm, "hou", fake_hou, raising=False)
    monkeypatch.delenv("HOUDINI_TEMP_DIR", raising=False)

    base = sm.unsaved_memory_base()
    assert "$" not in base
    assert base == os.path.normpath(
        os.path.join(sm.tempfile.gettempdir(), "synapse", "untitled"))


def test_hip_is_unsaved_is_not_reimplemented():
    """One detector: scene_memory delegates to store.hip_is_unsaved."""
    from synapse.memory.store import hip_is_unsaved

    assert sm._hip_is_unsaved(INSTALL_BIN + "/untitled.hip") is True
    assert sm._hip_is_unsaved("/show/scenes/shot.hip") is False
    assert sm._hip_is_unsaved(INSTALL_BIN + "/untitled.hip") == hip_is_unsaved(
        os.path.normpath(INSTALL_BIN + "/untitled.hip"), None)


def test_can_create_under_leaves_nothing_behind(tmp_path):
    d = tmp_path / "probe_me"
    d.mkdir()
    assert sm._can_create_under(str(d)) is True
    assert list(d.iterdir()) == []


def test_can_create_under_walks_to_an_existing_ancestor(tmp_path):
    """makedirs only needs the nearest existing ancestor to be writable."""
    deep = tmp_path / "a" / "b" / "c" / "d"
    assert sm._can_create_under(str(deep)) is True


def test_fallback_failing_too_still_raises(monkeypatch, tmp_path):
    """Relocation is a rescue, not a swallow: if the fallback is also refused
    the artist gets the error rather than a silent no-op."""
    job = str(tmp_path / "nope")
    os.makedirs(job)
    _unwritable(monkeypatch, job, str(tmp_path / "HTEMP"))
    with pytest.raises(PermissionError):
        sm.ensure_scene_structure(os.path.join(job, "shot.hip"), job)
