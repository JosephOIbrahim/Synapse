"""M2-D (path-policy-core): tokens stay raw, frames target the payload frame.

Four legs, pinned headless:
1. handlers_render read output parms via eval() -- expanded at the PLAYHEAD --
   so an explicit frame=N payload WROTE frame N's pixels into the playhead
   frame's filename (silently destroying any existing render of that frame)
   and reported success at that path. Now the read is frame-targeted
   (evalAsStringAtFrame) and an artist-set parm is never rewritten: the ROP
   expands its own token string at the render frame.
2. build_karma_xpu_shot pre-expanded $HIP into the sublayer filepathN parms
   (layer stack broke on any $HIP move) and authored a token-free productName
   (every sequence frame overwrote ONE file). Now parms keep raw tokens, the
   RenderProduct prim gets $HIP/...$F4.exr expanded at COOK TIME, and
   layer_dir resolver URIs fail loud (compose creates real files).
3. reference_usd's isfile gate rejected ArResolver URIs (asset:/shot:) before
   any node creation. Now URIs pass through VERBATIM and the result says
   honestly that existence was not checked (truth contract).
4. _path_warnings: baked absolute paths get a portability advisory;
   token/URI/relative/empty paths warn nothing.

Headless. Plant-or-enrich hou-fake convention (test_m2_cook_verify.py
header); handler-module globals are patched directly via monkeypatch --
never sys.modules residency (docs/HARDENING_RUN_2026-06-10.md Mile 3).
"""

import contextlib
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

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

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402
from synapse.server import handlers_render as hr  # noqa: E402
from synapse.server import solaris_compose_tools as sct  # noqa: E402
from synapse.server import solaris_compose as scmod  # noqa: E402
from synapse.server.handler_helpers import (  # noqa: E402
    _is_resolver_uri,
    _path_warnings,
)


# ---------------------------------------------------------------------------
# 1+2. Helper truth tables (pure, no hou)
# ---------------------------------------------------------------------------


def test_is_resolver_uri_truth_table():
    for uri in (
        "asset:/show/hero/geo.usd",
        "shot:/sq010/sh020/anim.usd",
        "file:///fs/show/geo.usd",
        "op:/stage/cam",
        "opdef:/Object/geo?ds",
    ):
        assert _is_resolver_uri(uri), uri
    # A Windows drive letter is ONE char before the colon -- never a scheme.
    for not_uri in ("C:/x", "C:\\x", "$HIP/x", "rel/x", "", None):
        assert not _is_resolver_uri(not_uri), not_uri


def test_path_warnings_shapes():
    w = _path_warnings("C:/abs/out.exr", context="ROP output parm")
    assert len(w) == 1
    assert "ROP output parm" in w[0]
    assert "$HIP" in w[0]
    # NOTE: absolute = os.path.isabs (platform semantics) -- on Windows
    # Py3.13+ a drive-less rooted path ('/renders/x') is NOT absolute.
    for clean in ("$HIP/render/x.exr", "asset:/show/x.usd", "rel/x.exr", "", None):
        assert _path_warnings(clean) == [], clean


# ---------------------------------------------------------------------------
# Render harness -- real hou string-parm semantics (the repro, promoted)
# ---------------------------------------------------------------------------


class _FrameParm:
    """String parm with real hou semantics: eval() expands at the PLAYHEAD,
    evalAsStringAtFrame(f) at the given frame, unexpandedString() raw."""

    def __init__(self, raw, hipdir, playstate):
        self._raw = raw
        self._hip = hipdir
        self._playstate = playstate  # {"frame": N} shared with fake hou
        self.set_calls = []

    def _expand(self, frame):
        return self._raw.replace("$HIP", self._hip).replace(
            "$F4", str(int(frame)).zfill(4)
        )

    def unexpandedString(self):
        return self._raw

    def eval(self):
        return self._expand(self._playstate["frame"])

    def evalAsStringAtFrame(self, frame):
        return self._expand(frame)

    def set(self, v):
        self.set_calls.append(v)
        self._raw = v


class _FrameRop:
    """render() evaluates its picture parm AT the render frame (real ROP
    semantics) and writes that file."""

    def __init__(self, picture):
        self.picture = picture

    def type(self):
        return SimpleNamespace(name=lambda: "karma")

    def parm(self, name):
        return self.picture if name == "picture" else None

    def path(self):
        return "/stage/karma1"

    def render(self, frame_range=None, verbose=False):
        out = Path(self.picture.evalAsStringAtFrame(frame_range[0]))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"EXR")


def _render_harness(tmp_path, monkeypatch, raw, playhead=1):
    """Wire handlers_render globals to the frame-faithful fakes."""
    hip = str(tmp_path).replace("\\", "/")
    playstate = {"frame": playhead}
    picture = _FrameParm(raw, hip, playstate)
    rop = _FrameRop(picture)
    fake_hou = SimpleNamespace(
        node=lambda p: rop if p == "/stage/karma1" else None,
        frame=lambda: playstate["frame"],
        text=SimpleNamespace(expandString=lambda s: str(tmp_path)),
        ui=MagicMock(),
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )
    g = SynapseHandler._handle_render.__globals__   # handlers_render namespace
    monkeypatch.setitem(g, "hou", fake_hou)
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)  # never wait in tests
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    monkeypatch.setitem(sys.modules, "hdefereval", _hd)
    return SynapseHandler(), rop, picture, hip


# ---------------------------------------------------------------------------
# 3. LEG 4 core pin -- explicit frame renders AND reports at that frame
# ---------------------------------------------------------------------------


def test_render_explicit_frame_targets_that_frame(tmp_path, monkeypatch):
    """Playhead=1, payload frame=42: the write and the result land at
    shot.0042.exr; the playhead frame's file is never touched."""
    handler, rop, picture, hip = _render_harness(
        tmp_path, monkeypatch, "$HIP/render/shot.$F4.exr", playhead=1
    )

    result = handler._handle_render({"node": "/stage/karma1", "frame": 42})

    assert (tmp_path / "render" / "shot.0042.exr").exists()
    assert not (tmp_path / "render" / "shot.0001.exr").exists(), (
        "frame 42's pixels were written into the playhead frame's filename "
        "(the eval-at-playhead bake bug)"
    )
    assert result["image_path"].endswith("shot.0042.exr")
    assert result["output_file"].endswith("shot.0042.exr")
    # WP4 pin preserved: the picture parm raw is byte-identical after.
    assert picture.unexpandedString() == "$HIP/render/shot.$F4.exr"


def test_render_artist_parm_not_rewritten(tmp_path, monkeypatch):
    """A non-empty artist picture parm gets ZERO sets -- the tokens stay in
    the parm and the ROP expands them at the render frame itself."""
    handler, rop, picture, hip = _render_harness(
        tmp_path, monkeypatch, "$HIP/render/shot.$F4.exr", playhead=7
    )

    handler._handle_render({"node": "/stage/karma1", "frame": 3})

    assert picture.set_calls == []
    assert (tmp_path / "render" / "shot.0003.exr").exists()


def test_render_path_warnings_on_baked_absolute(tmp_path, monkeypatch):
    """A baked absolute output parm gets the portability advisory; a
    tokenized parm gets none."""
    baked = str(tmp_path / "abs_out" / "beauty.exr")
    handler, rop, picture, hip = _render_harness(tmp_path, monkeypatch, baked)
    result = handler._handle_render({"node": "/stage/karma1", "frame": 1})
    assert result["path_warnings"], "baked absolute path must carry the advisory"
    assert "ROP output parm" in result["path_warnings"][0]

    handler2, _, _, _ = _render_harness(
        tmp_path, monkeypatch, "$HIP/render/shot.$F4.exr"
    )
    result2 = handler2._handle_render({"node": "/stage/karma1", "frame": 1})
    assert "path_warnings" not in result2


# ---------------------------------------------------------------------------
# 4. LEG 3 -- reference_usd resolver-URI passthrough (truth contract)
# ---------------------------------------------------------------------------


def _ref_harness(monkeypatch):
    """reference_usd wiring (test_m2_display_policy ref_wired idiom):
    hou.node(parent) -> empty /stage net; createNode returns a recording
    fake whose filepath1 parm logs set() calls verbatim."""
    parent_node = MagicMock(name="parent_node")
    parent_node.displayNode.return_value = None
    parent_node.children.return_value = []

    sub = MagicMock(name="sublayer_import")
    sub.path.return_value = "/stage/sublayer_import"
    sub.parent.return_value = parent_node
    filepath_parm = MagicMock(name="filepath1")
    sub.parm.side_effect = (
        lambda n: filepath_parm if n == "filepath1" else MagicMock()
    )
    parent_node.createNode.return_value = sub

    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
        node=lambda p: parent_node,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    # Patch the LIVE main_thread entry (the handlers resolve it at call time).
    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())
    return SynapseHandler(), filepath_parm


def test_reference_usd_uri_passthrough(monkeypatch):
    handler, filepath_parm = _ref_harness(monkeypatch)
    result = handler._handle_reference_usd({
        "file": "asset:/show/hero/geo.usd",
        "mode": "sublayer",
    })
    # Set VERBATIM -- no expansion, no isfile probe, no node-creation abort.
    filepath_parm.set.assert_called_once_with("asset:/show/hero/geo.usd")
    # Passthrough is never a claimed verification.
    assert "unverified" in result["path_policy"]
    assert "path_warnings" not in result  # URIs carry no baked-path advisory


def test_reference_usd_missing_fs_path_still_rejected(monkeypatch):
    handler, _ = _ref_harness(monkeypatch)
    # The gate survives for real filesystem paths -- including a drive-letter
    # absolute (one char before the colon is NOT a resolver scheme).
    for bad in ("/nope/missing.usd", "C:/nope/missing.usd"):
        with pytest.raises(ValueError, match="Couldn't find the file"):
            handler._handle_reference_usd({"file": bad, "mode": "sublayer"})


# ---------------------------------------------------------------------------
# 5. LEGS 1+2 -- compose parms keep tokens; productName resolves at cook time
# ---------------------------------------------------------------------------


class _RecParm:
    """Unlocked parm that logs (node_label, parm_name, value) into a list."""

    def __init__(self, label, pname, log):
        self._key = (label, pname)
        self._log = log

    def isLocked(self):
        return False

    def set(self, v):
        self._log.append(self._key + (v,))


def _fake_pxr(monkeypatch):
    class _FakeSdfLayer:
        @staticmethod
        def CreateNew(fp):
            Path(fp).parent.mkdir(parents=True, exist_ok=True)
            Path(fp).write_text("#usda 1.0\n")
            return SimpleNamespace(Save=lambda: None)

    fake = ModuleType("pxr")
    fake.Sdf = SimpleNamespace(Layer=_FakeSdfLayer)
    monkeypatch.setitem(sys.modules, "pxr", fake)


def test_compose_parms_keep_tokens(tmp_path, monkeypatch):
    _fake_pxr(monkeypatch)
    set_calls = []
    pys_codes = {}

    def _mk_node(label):
        node = MagicMock(name=label)
        node.path.return_value = "/stage/" + label
        node.parm.side_effect = lambda pn: _RecParm(label, pn, set_calls)
        return node

    fake_sc = SimpleNamespace(
        create_lop=lambda stage, type_name, name: _mk_node(name),
        make_pythonscript_lop=lambda stage, name, code: (
            pys_codes.__setitem__(name, code) or _mk_node(name)
        ),
        wire=lambda node, src, input_index=0: None,
        read_stage=lambda n: "STAGE",
        composition_errors=lambda s: [],
    )
    monkeypatch.setattr(sct, "sc", fake_sc)
    monkeypatch.setattr(sct, "HOU_AVAILABLE", True)
    monkeypatch.setattr(
        sct, "hou",
        SimpleNamespace(expandString=lambda s: s.replace("$HIP", str(tmp_path))),
    )

    result = sct.build_karma_xpu_shot(MagicMock(), shot="wp8")

    # filepath1..5 parms got RAW $HIP token paths, weakest-first...
    fp_sets = [
        (c[1], c[2]) for c in set_calls
        if c[0] == "wp8_dept_stack" and c[1].startswith("filepath")
    ]
    weakest_first = ("layout", "animation", "lighting", "fx", "render")
    assert fp_sets == [
        ("filepath%d" % i, "$HIP/wp8_layers/%s.usd" % d)
        for i, d in enumerate(weakest_first, start=1)
    ]
    # ...while the real .usd files exist on disk at the EXPANDED location.
    for d in weakest_first:
        assert (tmp_path / "wp8_layers" / (d + ".usd")).exists()

    # productName: raw $HIP + $F4 in the parm AND in the pythonscript literal,
    # expanded per-frame at cook time via hou.text.expandString.
    assert ("wp8_karma_xpu", "productName", "$HIP/render/wp8.$F4.exr") in set_calls
    code = pys_codes["wp8_productname"]
    assert "hou.text.expandString" in code
    assert "'$HIP/render/wp8.$F4.exr'" in code

    assert result["product_path"] == "$HIP/render/wp8.$F4.exr"
    assert result["product_name_resolution"].startswith("cook-time")
    assert result["department_parm_paths"] == [
        "$HIP/wp8_layers/%s.usd" % d for d in weakest_first
    ]
    # department_files_weakest_first stays the disk truth (expanded).
    assert all("$" not in fp for fp in result["department_files_weakest_first"])
    assert "path_warnings" not in result  # layer_dir=None -> nothing baked


def test_compose_layer_dir_uri_fails_loud(monkeypatch):
    _fake_pxr(monkeypatch)
    monkeypatch.setattr(sct, "HOU_AVAILABLE", True)
    with pytest.raises(scmod.ComposeError, match="resolver URI"):
        sct.build_karma_xpu_shot(
            MagicMock(), shot="x", layer_dir="asset:/show/layers"
        )
