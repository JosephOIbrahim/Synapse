"""M2-I (report sect 5 item 7b + sect 4.2 [F] rider): show-config mechanism.

synapse.core.show_config is the layered per-show/per-scene convention store
(env > $HIP > $JOB > built-in DEFAULTS, per-key) that the render/compose
handlers consult for their previously-hardcoded defaults. The keystone bar:
with NO config files present, every constructed path/resolution is
byte-identical to the pre-M2-I behavior (test 8 pins this), and a
``naming.versioning = "increment"`` show.json switches the default render
output to comparable vNNN version dirs (test 9 pins the rider's claim).

Headless. Plant-or-enrich hou-fake convention (test_m2_cook_verify.py
header); handler-module globals are patched directly via monkeypatch --
never sys.modules residency (docs/HARDENING_RUN_2026-06-10.md Mile 3).
"""

import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
# The resident fake's shape leaks into every later-imported handler module
# (first planter wins) -- enrich it with what sibling handler tests rely on,
# never plant a skeleton (test_autonomy_live_contract.py pattern).
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    # Sibling convention: expandString returns a real str (later files'
    # handlers run Path() over it when this file is the first planter).
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd
elif not hasattr(sys.modules["hdefereval"], "executeInMainThreadWithResult"):
    sys.modules["hdefereval"].executeInMainThreadWithResult = (
        lambda fn, *a, **k: fn(*a, **k)
    )

from synapse.core import show_config as sc  # noqa: E402
from synapse.server import handlers_memory as hm  # noqa: E402
from synapse.server import handlers_render as hr  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_show_config(monkeypatch):
    """No env layer, no stale cache -- every test starts from a cold loader."""
    monkeypatch.delenv("SYNAPSE_SHOW_CONFIG", raising=False)
    sc.reload_show_config()
    yield
    sc.reload_show_config()


def _write_cfg(dirpath, data):
    """Plant <dirpath>/.synapse/show.json; returns the file path."""
    d = Path(dirpath) / ".synapse"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "show.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Core loader (no hou needed -- dirs passed explicitly)
# ---------------------------------------------------------------------------

# Doc-conformance pin for the schema: today's exact hardcoded values.
EXPECTED_DEFAULTS = {
    "resolution.render": [1920, 1080],
    "resolution.preview": [1280, 720],
    "resolution.capture": [800, 600],
    "output.render_root": "$HIP/.synapse/renders",
    "output.report_root": "$HIP/.synapse/render_reports",
    "output.sequence_root": "$HIP/render",
    "output.cache_root": "$HIP/cache",
    "frames.padding": 4,
    "frames.fps": 24.0,
    "naming.render_basename": "render",
    "naming.versioning": "timestamp",
    "color.ocio": "",
    "color.display": "",
    "color.view": "",
}


def test_defaults_when_no_config(tmp_path):
    hip = tmp_path / "hip"
    job = tmp_path / "job"
    hip.mkdir()
    job.mkdir()
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    for key, expected in EXPECTED_DEFAULTS.items():
        val, src = cfg.lookup(key)
        assert val == expected, f"{key}: {val!r} != {expected!r}"
        assert src == "default", f"{key} came from {src!r}, not 'default'"
    assert cfg.source_files == {}


def test_precedence_env_over_hip_over_job(tmp_path, monkeypatch):
    hip = tmp_path / "hip"
    job = tmp_path / "job"
    _write_cfg(hip, {"resolution": {"render": [2048, 858]}})
    _write_cfg(job, {"resolution": {"render": [3840, 2160]}})
    env_file = tmp_path / "env_show.json"
    env_file.write_text(
        json.dumps({"resolution": {"render": [1024, 512]}}), encoding="utf-8"
    )

    # hip beats job (scene overrides show)
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg.lookup("resolution.render") == ([2048, 858], "hip")

    # env beats hip
    monkeypatch.setenv("SYNAPSE_SHOW_CONFIG", str(env_file))
    sc.reload_show_config()
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg.lookup("resolution.render") == ([1024, 512], "env")

    # job alone still wins over defaults
    empty_hip = tmp_path / "empty_hip"
    empty_hip.mkdir()
    monkeypatch.delenv("SYNAPSE_SHOW_CONFIG")
    sc.reload_show_config()
    cfg = sc.get_show_config(hip_dir=str(empty_hip), job_dir=str(job))
    assert cfg.lookup("resolution.render") == ([3840, 2160], "job")


def test_per_key_fallthrough(tmp_path):
    hip = tmp_path / "hip"
    job = tmp_path / "job"
    job.mkdir()
    _write_cfg(hip, {"naming": {"versioning": "increment"}})
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg.lookup("naming.versioning") == ("increment", "hip")
    # Keys the hip file does NOT define fall through to defaults
    val, src = cfg.lookup("output.render_root")
    assert src == "default"
    assert val == "$HIP/.synapse/renders"
    # ...including the sibling key inside the same partially-defined group
    assert cfg.lookup("naming.render_basename") == ("render", "default")


def test_malformed_json_degrades_to_defaults(tmp_path):
    hip = tmp_path / "hip"
    job = tmp_path / "job"
    job.mkdir()
    d = hip / ".synapse"
    d.mkdir(parents=True)
    (d / "show.json").write_text("{not valid json", encoding="utf-8")
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))  # must not raise
    assert cfg.lookup("resolution.render") == ([1920, 1080], "default")
    assert "hip" not in cfg.source_files
    # Non-dict top level degrades the same way
    (d / "show.json").write_text("[1, 2, 3]", encoding="utf-8")
    sc.reload_show_config()
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg.lookup("resolution.render") == ([1920, 1080], "default")


def test_cache_and_explicit_reload(tmp_path):
    hip = tmp_path / "hip"
    job = tmp_path / "job"
    job.mkdir()
    _write_cfg(hip, {"resolution": {"render": [100, 100]}})
    cfg = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg.get("resolution.render") == [100, 100]

    # Rewriting the file does NOT change the cached read (no mtime polling)
    _write_cfg(hip, {"resolution": {"render": [200, 200]}})
    cfg2 = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg2 is cfg
    assert cfg2.get("resolution.render") == [100, 100]

    # Explicit reload is the refresh point
    sc.reload_show_config()
    cfg3 = sc.get_show_config(hip_dir=str(hip), job_dir=str(job))
    assert cfg3.get("resolution.render") == [200, 200]


def test_next_version_dir(tmp_path):
    # Missing root -> v001 (zero-padded name pinned)
    missing = tmp_path / "nope"
    assert Path(sc.next_version_dir(str(missing))).name == "v001"
    # Empty root -> v001
    root = tmp_path / "renders"
    root.mkdir()
    assert Path(sc.next_version_dir(str(root))).name == "v001"
    # Existing v001 + v002 + junk -> v003
    (root / "v001").mkdir()
    (root / "v002").mkdir()
    (root / "vfoo").mkdir()        # non-numeric dir ignored
    (root / "v009").write_text("")  # FILE named like a version ignored
    nxt = sc.next_version_dir(str(root))
    assert Path(nxt).name == "v003"
    assert Path(nxt).parent == root


def test_headless_dirs_none(tmp_path, monkeypatch):
    # Patch the show_config MODULE globals directly (never sys.modules)
    monkeypatch.setattr(sc, "hou", None)
    monkeypatch.setattr(sc, "_HOU_AVAILABLE", False)
    assert sc.resolve_show_dirs() == (None, None)
    # No dirs at all -> defaults only
    cfg = sc.get_show_config()
    assert cfg.lookup("resolution.render") == ([1920, 1080], "default")
    assert cfg.source_files == {}
    # env layer still serves headless
    env_file = tmp_path / "env_show.json"
    env_file.write_text(
        json.dumps({"frames": {"padding": 5}}), encoding="utf-8"
    )
    monkeypatch.setenv("SYNAPSE_SHOW_CONFIG", str(env_file))
    sc.reload_show_config()
    cfg = sc.get_show_config()
    assert cfg.lookup("frames.padding") == (5, "env")
    assert cfg.lookup("frames.fps") == (24.0, "default")


# ---------------------------------------------------------------------------
# Handler wiring -- _handle_render default-output branch
# ---------------------------------------------------------------------------


def _render_harness(monkeypatch, tmp_path, cfg):
    """Wire handlers_render module globals for a default-branch render.

    Returns (handler, out_parm, dirs) -- the test_render.py path-aware
    harness idiom: only the requested ROP resolves via hou.node.
    """
    temp_dir = tmp_path / "houdini_temp"
    render_root = tmp_path / "renders_root"
    hfs_dir = tmp_path / "hfs"
    temp_dir.mkdir(exist_ok=True)

    fake_node = MagicMock()
    fake_node.path.return_value = "/stage/karma1"
    fake_node.type.return_value.name.return_value = "karma"
    out_parm = MagicMock()
    out_parm.eval.return_value = ""  # no artist output -> default branch
    fake_node.parm.side_effect = (
        lambda n: out_parm if n in ("outputimage", "picture") else None
    )

    def _expand(s):
        return {
            "$HOUDINI_TEMP_DIR": str(temp_dir),
            "$HIP/.synapse/renders": str(render_root),
            "$HFS": str(hfs_dir),
        }.get(s, s)

    fake_hou = SimpleNamespace(
        node=lambda p: fake_node if p == "/stage/karma1" else None,
        frame=MagicMock(return_value=1.0),
        text=SimpleNamespace(expandString=_expand),
        undos=MagicMock(),
    )
    monkeypatch.setattr(hr, "hou", fake_hou)
    monkeypatch.setattr(hr, "HOU_AVAILABLE", True)
    # The no-files config under test -- patched ON the handler module
    monkeypatch.setattr(hr, "get_show_config", lambda *a, **k: cfg)

    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    monkeypatch.setitem(sys.modules, "hdefereval", _hd)

    handler = hr.RenderHandlerMixin()
    dirs = SimpleNamespace(
        temp_dir=temp_dir, render_root=render_root, hfs_dir=hfs_dir
    )
    return handler, out_parm, dirs


def test_render_default_path_byte_identical_without_config(monkeypatch, tmp_path):
    """ZERO-CHANGE PIN: no config files -> the default render path is
    byte-identical to today's render_<timestamp>.$F4.exr under the
    expanded output root."""
    cfg = sc.ShowConfig([("default", sc.DEFAULTS)], {})
    handler, out_parm, dirs = _render_harness(monkeypatch, tmp_path, cfg)

    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
         patch("pathlib.Path.mkdir", return_value=None):
        result = handler._handle_render({"node": "/stage/karma1"})

    set_path = out_parm.set.call_args_list[0][0][0]
    assert re.fullmatch(r"render_\d+\.\$F4\.exr", Path(set_path).name)
    assert Path(set_path).parent == dirs.render_root
    # The advisory is honest: the default branch ran on built-in defaults
    assert "show_config" in result
    assert "output.render_root" in result["show_config"]["default_used"]
    assert result["show_config"]["source_files"] == {}
    # Resolved output reported with the frame token expanded
    assert re.fullmatch(r"render_\d+\.0001\.exr", Path(result["output_file"]).name)


def test_render_versioned_when_increment(monkeypatch, tmp_path):
    """The rider, pinned: naming.versioning='increment' gives reruns
    identical basenames in sibling vNNN dirs -- directly comparable,
    never overwritten."""
    cfg = sc.ShowConfig(
        [("hip", {"naming": {"versioning": "increment"}}),
         ("default", sc.DEFAULTS)],
        {"hip": str(tmp_path / "hip" / ".synapse" / "show.json")},
    )
    handler, out_parm, dirs = _render_harness(monkeypatch, tmp_path, cfg)
    dirs.render_root.mkdir(exist_ok=True)

    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)), \
         patch("pathlib.Path.mkdir", return_value=None):
        handler._handle_render({"node": "/stage/karma1"})
        first = out_parm.set.call_args_list[0][0][0]

        # Simulate the first run's version dir landing on disk
        # (os.makedirs -- pathlib.Path.mkdir is patched out in this block)
        os.makedirs(dirs.render_root / "v001")
        out_parm.set.reset_mock()
        result = handler._handle_render({"node": "/stage/karma1"})
        second = out_parm.set.call_args_list[0][0][0]

    assert Path(first).parent == dirs.render_root / "v001"
    assert Path(second).parent == dirs.render_root / "v002"
    # The comparability claim: identical basenames across runs
    assert Path(first).name == Path(second).name == "render.$F4.exr"
    # versioning came from the hip config file, not a built-in default
    assert "naming.versioning" not in result["show_config"]["default_used"]
    assert "hip" in result["show_config"]["source_files"]


# ---------------------------------------------------------------------------
# Handler wiring -- project_setup surfaces the effective config
# ---------------------------------------------------------------------------


def test_project_setup_surfaces_config(monkeypatch, tmp_path):
    hip_dir = tmp_path / "scenes"
    job_dir = tmp_path
    hip_dir.mkdir()
    _write_cfg(hip_dir, {"resolution": {"render": [4096, 2160]}})

    sp = {
        "hip_path": str(hip_dir / "shot.hip"),
        "hip_dir": str(hip_dir),
        "job_path": str(job_dir),
    }
    monkeypatch.setattr(
        hm.MemoryHandlerMixin, "_scene_paths", staticmethod(lambda: sp)
    )

    handler = hm.MemoryHandlerMixin()
    result = handler._handle_project_setup({})

    # Existing result keys unchanged (additive contract)
    for key in ("paths", "project_memory", "scene_memory", "agent_state",
                "evolution_stage", "suspended_tasks"):
        assert key in result
    # Effective (deep-merged) config: planted key visible, defaults intact
    assert result["show_config"]["resolution"]["render"] == [4096, 2160]
    assert result["show_config"]["resolution"]["preview"] == [1280, 720]
    assert result["show_config"]["frames"]["padding"] == 4
    assert result["show_config_sources"]["hip"].endswith("show.json")
    assert "job" not in result["show_config_sources"]
