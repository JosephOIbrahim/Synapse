"""G1a followup — discovery reads the RAW project root, memory reads the RESOLVED address.

The G1a crucible proved a SEV 3 regression in the original G1a commit:
``_scene_paths()["job_path"]`` changed meaning from "the project root" to
"the resolved (possibly relocated) memory address", and two consumers that
wanted the ROOT silently degraded on a normal studio layout, where the show
root is readable but NOT writable:

  * cross-scene search globbed the resolved dir  -> 2 memory.md hits became 0
  * get_show_config read the resolved dir        -> a readable show.json was
                                                    ignored; defaults served

The fix keeps both meanings, separately: ``job_path`` (resolved, for memory
writes/reads) and ``job_root`` (raw ``$JOB``, for discovery). These tests pin
each consumer to its correct key. They are handler-layer tests: hou is faked,
``_scene_paths`` is exercised through the mixin with the module's globals
patched -- the pattern of tests/test_m2_show_config.py.
"""
from __future__ import annotations

import importlib.util
import os
import stat
import sys
import types
from pathlib import Path

import pytest

import pkgbootstrap

REPO = Path(__file__).resolve().parent.parent
HANDLERS = REPO / "python" / "synapse" / "server" / "handlers_memory.py"

# Modules `_load_handlers` evicts and re-imports. monkeypatch.delitem's undo
# puts the ORIGINAL object back into sys.modules but never re-binds it on its
# parent package — importlib bound the reloaded copy there, and that binding
# survives. Measured at base (this file alone): synapse.server.handlers_memory
# came out WRONG-MOD, with _pytest.monkeypatch.resolve() returning a DIFFERENT
# object than sys.modules held. There is no hook into monkeypatch's teardown,
# so the reconciliation runs after it.
_REBIND_AFTER = ("synapse.server.handlers_memory",)


@pytest.fixture(autouse=True)
def _rebind_reloaded_modules():
    """Re-assert sys.modules[name] is <parent>.<leaf> after monkeypatch undoes.

    Autouse fixtures are set up BEFORE the test's own fixtures, so they
    finalize AFTER them — this runs once monkeypatch has already restored the
    sys.modules entries. Pinned rather than assumed: see
    tests/test_pkg_bootstrap_invariant.py::
    test_autouse_rebind_runs_after_monkeypatch_undo.
    """
    yield
    pkgbootstrap.rebind_modules(_REBIND_AFTER)


# ── harness ──────────────────────────────────────────────────────────────────

def _load_handlers(monkeypatch, fake_hou):
    """Import handlers_memory as part of the real package with hou faked.

    The module does relative imports (..memory.scene_memory), so it must load
    inside the package -- but we fake ``hou`` in sys.modules BEFORE import so
    the guard block binds our fake.
    """
    monkeypatch.setitem(sys.modules, "hou", fake_hou)
    # hdefereval must exist for main_thread import chains; make run_on_main
    # synchronous so the handler logic runs inline.
    _hd = types.ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    monkeypatch.setitem(sys.modules, "hdefereval", _hd)

    for m in list(sys.modules):
        if m.startswith("synapse.server.handlers_memory"):
            monkeypatch.delitem(sys.modules, m, raising=False)
    pkg_root = str(REPO / "python")
    if pkg_root not in sys.path:
        monkeypatch.syspath_prepend(pkg_root)
    import synapse.server.handlers_memory as hm
    hm = importlib.reload(hm)
    monkeypatch.setattr(hm, "hou", fake_hou, raising=False)
    monkeypatch.setattr(hm, "HOU_AVAILABLE", True, raising=False)
    # run_on_main inline (no real main thread here)
    from synapse.server import main_thread as mt
    monkeypatch.setattr(mt, "run_on_main", lambda fn, **k: fn(), raising=False)
    return hm


def _fake_hou(hip_path, job):
    hou = types.ModuleType("hou")
    hou.hipFile = types.SimpleNamespace(path=lambda: str(hip_path))
    hou.getenv = lambda name, default=None: {"JOB": str(job)}.get(name, default)
    return hou


def _deny_writes(path: Path):
    """Best-effort read-only dir. Windows honors the flag for mkdir denial via
    ACLs inconsistently, so tests that NEED denial force relocation through the
    resolver contract instead (unsaved-scene routing), which is deterministic."""
    os.chmod(path, stat.S_IREAD | stat.S_IEXEC)


class _Handler:
    """Minimal host for the mixin under test (_scene_paths is a staticmethod)."""

    def __init__(self, hm):
        self._hm = hm

    def _scene_paths(self):
        return self._hm.MemoryHandlerMixin._scene_paths()


# ── the two pins ─────────────────────────────────────────────────────────────

def test_scene_paths_returns_both_keys_and_they_diverge_on_unusable_job(
        tmp_path, monkeypatch):
    """An unusable $JOB relocates job_path but must NOT relocate job_root.

    Relocation at RESOLVE time happens when the writability probe fails, so
    the probe is patched to report the root unwritable -- this pins the
    two-key CONTRACT; the probe's own truth (real denied dirs, files-as-dirs
    at makedirs time) is pinned by the lane's 17 tests in
    tests/test_g1a_scene_memory_address.py. A writable $JOB correctly does
    NOT diverge (verified by the first version of this test failing for
    exactly that reason).
    """
    job = tmp_path / "studio_share"
    job.mkdir()
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path / "htemp"))
    hou = _fake_hou("untitled.hip", job)
    hm = _load_handlers(monkeypatch, hou)
    import synapse.memory.scene_memory as sm
    monkeypatch.setattr(sm, "_can_create_under", lambda p: False)

    sp = _Handler(hm)._scene_paths()

    assert "job_root" in sp and "job_path" in sp, (
        "the two-meanings contract: resolved address AND raw root")
    assert os.path.normcase(sp["job_root"]) == os.path.normcase(str(job)), (
        "job_root must be the RAW $JOB, untouched by resolution")
    assert os.path.normcase(sp["job_path"]) != os.path.normcase(str(job)), (
        "unusable $JOB: job_path must have relocated away from it")


def test_cross_scene_search_globs_the_raw_root(tmp_path, monkeypatch):
    """The crucible's proven loss: sibling scenes' memory must stay findable.

    Layout: a show root carrying two shots with claude/memory.md, hip unsaved
    (so the memory address relocates to temp). Search scope=all must still
    return hits from under the RAW root.
    """
    job = tmp_path / "showroot"
    for shot in ("shot_010", "shot_020"):
        d = job / shot / "claude"
        d.mkdir(parents=True)
        (d / "memory.md").write_text(
            "## Decision: use karma xpu\ntagged for search\n", encoding="utf-8")
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path / "htemp"))
    hou = _fake_hou("untitled.hip", job)
    hm = _load_handlers(monkeypatch, hou)

    h = _Handler(hm)
    sp = h._scene_paths()

    # The glob root the handler uses, per the fix: job_root over job_path.
    job_root = sp.get("job_root") or sp["job_path"]
    import glob as glob_mod
    hits = sorted(glob_mod.glob(
        os.path.join(job_root, "**", "claude", "memory.md"), recursive=True))
    assert len(hits) == 2, (
        f"discovery must walk the raw root; got {len(hits)} from {job_root!r}")

    # And the source line pins the handler itself to job_root, so a refactor
    # back to sp["job_path"] fails here, not in a studio.
    src = HANDLERS.read_text(encoding="utf-8")
    assert 'os.path.join(job_root, "**", "claude", "memory.md")' in src, (
        "handlers_memory cross-scene glob must be rooted at job_root")


def test_show_config_reads_the_raw_root(tmp_path, monkeypatch):
    """The second consumer: a readable show.json at the root must be served
    even when the memory address relocated (unsaved scene)."""
    job = tmp_path / "studio_share"
    (job / ".synapse").mkdir(parents=True)
    (job / ".synapse" / "show.json").write_text(
        '{"fps": 48.0}', encoding="utf-8")
    monkeypatch.setenv("HOUDINI_TEMP_DIR", str(tmp_path / "htemp"))
    hou = _fake_hou("untitled.hip", job)
    hm = _load_handlers(monkeypatch, hou)

    sp = _Handler(hm)._scene_paths()
    from synapse.core.show_config import get_show_config, reload_show_config
    reload_show_config()
    cfg = get_show_config(hip_dir=sp["hip_dir"],
                          job_dir=sp.get("job_root", sp["job_path"]))
    fps = cfg.as_dict().get("fps")
    assert fps == 48.0, (
        f"show.json at the raw root must be honored; got fps={fps!r} "
        f"(job_root={sp.get('job_root')!r}, job_path={sp['job_path']!r})")

    src = HANDLERS.read_text(encoding="utf-8")
    assert 'job_dir=sp.get("job_root", job_path)' in src, (
        "project_setup must hand get_show_config the raw root")
