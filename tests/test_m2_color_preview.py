"""M2-G (hardening report 4.3): color-managed render previews.

The one production EXR->displayable conversion site ran bare iconvert --
whatever transform HOUDINI_AUTOCONVERT_IMAGE_FILES implied, recorded
nowhere -- so on OCIO/ACES shows every LLM visual judgment was made
through the wrong transform. Now _convert_preview (handler_helpers) runs
hoiiotool's OCIO display/view leg first ($OCIO / show-config color.ocio,
injected via the subprocess env -- the live-verified mechanism on
H21.0.671), an honest sRGB fallback second, iconvert -g auto last; the
render result records color_transform / color_managed / preview_tool, and
result['format'] reflects what image_path actually IS (the EXR used to
ship labeled 'jpeg' when conversion failed).

Truth contract pins: color_managed=True ONLY on the verified OCIO leg;
every fallback records its actual transform; GL flipbook previews are
marked 'viewport_display (unverified)'.

NOTE (spec deviation, deliberate): _handle_capture_viewport does NOT gain
the static viewport keys -- test_capture.py pins its exact no-config
result shape ({image_path, width, height, format}, an M2-I pin) and is
outside this WP's touch list. The render flipbook-fallback leg carries
them instead.

Headless. Handler-module globals are patched directly (sys.modules
residency is order-fragile -- docs/HARDENING_RUN_2026-06-10.md Mile 3
forensics); subprocess is mocked by replacing the HELPER module's
reference, never sys.modules. Fake binaries are touched files under
tmp_path/bin with hfs=tmp_path.
"""

import contextlib
import subprocess as real_subprocess
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

from synapse.server import handler_helpers as hh  # noqa: E402
from synapse.server import handlers_render as hr  # noqa: E402
from synapse.server.handlers import SynapseHandler  # noqa: E402


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class _FakeRun:
    """Records subprocess.run calls; behavior scripted per binary basename."""

    def __init__(self):
        self.calls = []  # (argv, kwargs) per call
        self.behavior = {}  # 'hoiiotool'/'iconvert' -> callable(argv, kwargs)

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        name = Path(argv[0]).name.lower().replace(".exe", "")
        beh = self.behavior.get(name)
        if beh is None:
            return SimpleNamespace(
                returncode=1, stderr=b"no behavior scripted", stdout=b""
            )
        return beh(argv, kwargs)


def _ok_writes_dst(argv, kwargs):
    """Successful conversion: exit 0 AND the dst file appears (the helper
    requires both -- live probe: failure writes no file)."""
    dst = argv[argv.index("-o") + 1] if "-o" in argv else argv[-1]
    Path(dst).write_bytes(b"JPG")
    return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")


def _fails(stderr=b"hoiiotool ERROR: bad display"):
    def _beh(argv, kwargs):
        return SimpleNamespace(returncode=1, stderr=stderr, stdout=b"")
    return _beh


def _make_hfs(tmp_path, *names):
    """Touch fake binaries under tmp_path/bin; returns hfs (= tmp_path)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for n in names:
        (bin_dir / n).write_bytes(b"")
    return str(tmp_path)


@pytest.fixture()
def fake_run(monkeypatch):
    """Replace the HELPER module's subprocess reference (never sys.modules)."""
    rec = _FakeRun()
    monkeypatch.setattr(hh, "subprocess", SimpleNamespace(run=rec))
    return rec


@pytest.fixture()
def src_dst(tmp_path):
    src = tmp_path / "g.exr"
    src.write_bytes(b"EXR")
    return str(src), str(tmp_path / "preview.jpg")


# ---------------------------------------------------------------------------
# _convert_preview units
# ---------------------------------------------------------------------------

def test_ocio_leg_explicit_param(tmp_path, fake_run, src_dst, monkeypatch):
    """Explicit ocio= drives the managed leg: --ociodisplay default default,
    OCIO injected into the subprocess env, color_managed=True."""
    monkeypatch.delenv("OCIO", raising=False)
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe")
    fake_run.behavior["hoiiotool"] = _ok_writes_dst

    conv = hh._convert_preview(src, dst, hfs, ocio="ocio://studio-config-latest")

    assert conv["converted"] is True
    assert conv["tool"] == "hoiiotool"
    assert conv["color_managed"] is True
    assert "ociodisplay" in conv["color_transform"]
    assert "ocio://studio-config-latest" in conv["color_transform"]
    assert conv["error"] is None
    argv, kwargs = fake_run.calls[0]
    i = argv.index("--ociodisplay")
    assert argv[i:i + 3] == ["--ociodisplay", "default", "default"]
    assert kwargs["env"]["OCIO"] == "ocio://studio-config-latest"


def test_ocio_leg_from_env(tmp_path, fake_run, src_dst, monkeypatch):
    """No ocio= -> $OCIO env var drives the same managed leg."""
    monkeypatch.setenv("OCIO", "ocio://studio-config-latest")
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe")
    fake_run.behavior["hoiiotool"] = _ok_writes_dst

    conv = hh._convert_preview(src, dst, hfs)

    assert conv["color_managed"] is True
    assert conv["tool"] == "hoiiotool"
    _argv, kwargs = fake_run.calls[0]
    assert kwargs["env"]["OCIO"] == "ocio://studio-config-latest"


def test_explicit_display_view_and_source_colorspace(
    tmp_path, fake_run, src_dst, monkeypatch
):
    """source_colorspace rides the from= qualifier (hoiiotool usage text);
    explicit display/view replace the 'default' keywords."""
    monkeypatch.delenv("OCIO", raising=False)
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe")
    fake_run.behavior["hoiiotool"] = _ok_writes_dst

    conv = hh._convert_preview(
        src, dst, hfs, ocio="ocio://studio-config-latest",
        source_colorspace="ACEScg", display="sRGB - Display", view="ACES 1.0 - SDR Video",
    )

    assert conv["color_managed"] is True
    argv, _kwargs = fake_run.calls[0]
    i = argv.index("--ociodisplay:from=ACEScg")
    assert argv[i:i + 3] == [
        "--ociodisplay:from=ACEScg", "sRGB - Display", "ACES 1.0 - SDR Video"
    ]
    assert "sRGB - Display/ACES 1.0 - SDR Video" in conv["color_transform"]


def test_no_ocio_srgb_fallback_never_claims_managed(
    tmp_path, fake_run, src_dst, monkeypatch
):
    """Truth contract: the no-$OCIO leg converts via the OIIO built-in
    config and NEVER claims color_managed."""
    monkeypatch.delenv("OCIO", raising=False)
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe")
    fake_run.behavior["hoiiotool"] = _ok_writes_dst

    conv = hh._convert_preview(src, dst, hfs)

    assert conv["converted"] is True
    assert conv["color_managed"] is False
    assert conv["color_transform"] == "srgb (OIIO built-in config, no $OCIO)"
    argv, kwargs = fake_run.calls[0]
    i = argv.index("--tocolorspace")
    assert argv[i + 1] == "sRGB - Display"
    assert kwargs.get("env") is None


def test_hoiiotool_failure_falls_through_to_iconvert(
    tmp_path, fake_run, src_dst, monkeypatch
):
    """Failed OCIO leg (rc=1, no dst) falls through to iconvert with exactly
    -g auto (NOT a numeric gamma -- '-g 2.2' is a phantom flag value on
    this binary); the failure's stderr snippet survives the success."""
    monkeypatch.delenv("OCIO", raising=False)
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe", "iconvert.exe")
    fake_run.behavior["hoiiotool"] = _fails()
    fake_run.behavior["iconvert"] = _ok_writes_dst

    conv = hh._convert_preview(src, dst, hfs, ocio="ocio://broken")

    assert conv["converted"] is True
    assert conv["tool"] == "iconvert"
    assert conv["color_managed"] is False
    assert conv["color_transform"] == "gamma_auto (iconvert)"
    assert "bad display" in conv["error"]
    icv_argv = fake_run.calls[1][0]
    gi = icv_argv.index("-g")
    assert icv_argv[gi + 1] == "auto"


def test_no_binaries_returns_unconverted(tmp_path, fake_run, src_dst):
    """Nothing in $HFS/bin: honest no-op, no subprocess call, no raise."""
    src, dst = src_dst
    conv = hh._convert_preview(src, dst, str(tmp_path))

    assert conv == {
        "converted": False,
        "tool": None,
        "color_transform": "none (unconverted)",
        "color_managed": False,
        "error": None,
    }
    assert fake_run.calls == []


def test_run_exceptions_swallowed(tmp_path, fake_run, src_dst, monkeypatch):
    """Timeout/exception inside subprocess.run is swallowed per leg --
    best-effort contract: the helper never raises."""
    monkeypatch.delenv("OCIO", raising=False)
    src, dst = src_dst
    hfs = _make_hfs(tmp_path, "hoiiotool.exe", "iconvert.exe")

    def _timeout(argv, kwargs):
        raise real_subprocess.TimeoutExpired(argv, 15)

    def _boom(argv, kwargs):
        raise RuntimeError("boom")

    fake_run.behavior["hoiiotool"] = _timeout
    fake_run.behavior["iconvert"] = _boom

    conv = hh._convert_preview(src, dst, hfs)

    assert conv["converted"] is False
    assert conv["tool"] is None
    assert conv["color_transform"] == "none (unconverted)"
    assert "boom" in conv["error"]
    assert len(fake_run.calls) == 2


# ---------------------------------------------------------------------------
# _handle_render integration (test_render_offmain_c11.py harness shape)
# ---------------------------------------------------------------------------

class _Parm:
    def __init__(self, v=""):
        self._v = v

    def eval(self):
        return self._v

    def set(self, v):
        self._v = v


class _Rop:
    def __init__(self, picture, on_render=None, type_name="karma"):
        self._picture = picture
        self._on_render = on_render
        self._type = type_name

    def type(self):
        return SimpleNamespace(name=lambda: self._type)

    def parm(self, name):
        return self._picture if name == "picture" else None

    def render(self, frame_range=None, verbose=False):
        if self._on_render is not None:
            self._on_render()

    def path(self):
        return "/out/karma1"


def _wire(monkeypatch, tmp_path, rop, ui=None):
    """Patch handlers_render globals + hdefereval; expandString -> tmp_path
    (so $HOUDINI_TEMP_DIR and $HFS both resolve under the test root)."""
    fake_hou = SimpleNamespace(
        node=lambda p: rop,
        frame=lambda: 1,
        text=SimpleNamespace(expandString=lambda s: str(tmp_path)),
        ui=ui if ui is not None else MagicMock(),
        paneTabType=SimpleNamespace(SceneViewer="SceneViewer"),
        setFrame=lambda f: None,
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )
    fake_hde = ModuleType("hdefereval")
    fake_hde.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    g = SynapseHandler._handle_render.__globals__
    monkeypatch.setitem(g, "hou", fake_hou)
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)
    monkeypatch.delenv("SYNAPSE_SHOW_CONFIG", raising=False)
    return fake_hou


def test_render_result_carries_color_keys(tmp_path, fake_run, monkeypatch):
    """Successful render + successful OCIO conversion: the result records
    the transform, the tool, and an honest jpeg format."""
    monkeypatch.setenv("OCIO", "ocio://studio-config-latest")
    out_file = tmp_path / "render_0001.exr"
    rop = _Rop(
        _Parm(str(tmp_path / "render_$F4.exr")),
        on_render=lambda: out_file.write_bytes(b"EXR"),
    )
    _wire(monkeypatch, tmp_path, rop)
    _make_hfs(tmp_path, "hoiiotool.exe")
    fake_run.behavior["hoiiotool"] = _ok_writes_dst

    result = SynapseHandler()._handle_render({"node": "/out/karma1", "frame": 1})

    assert result["color_managed"] is True
    assert result["preview_tool"] == "hoiiotool"
    assert result["color_transform"].startswith("ociodisplay:")
    assert result["format"] == "jpeg"
    assert result["image_path"].endswith(".jpg")
    assert result["output_file"].endswith(".exr")
    assert "preview_error" not in result


def test_render_conversion_failure_ships_exr_honestly(
    tmp_path, fake_run, monkeypatch
):
    """Conversion failed (no binaries): image_path is the EXR and
    result['format'] says 'exr' (the format-honesty pin -- was hardcoded
    'jpeg'), with the unconverted transform recorded."""
    monkeypatch.delenv("OCIO", raising=False)
    out_file = tmp_path / "render_0001.exr"
    rop = _Rop(
        _Parm(str(tmp_path / "render_$F4.exr")),
        on_render=lambda: out_file.write_bytes(b"EXR"),
    )
    _wire(monkeypatch, tmp_path, rop)
    # No bin/ under hfs -- both converter legs are absent.

    result = SynapseHandler()._handle_render({"node": "/out/karma1", "frame": 1})

    assert result["image_path"].endswith(".exr")
    assert result["format"] == "exr"
    assert result["color_managed"] is False
    assert result["color_transform"] == "none (unconverted)"
    assert result["preview_tool"] is None
    assert "output_file" in result
    assert fake_run.calls == []


def test_flipbook_fallback_marks_viewport_transform(
    tmp_path, fake_run, monkeypatch
):
    """The GL flipbook leg bakes whatever transform the viewport applied --
    recorded honestly as viewport_display/unmanaged, never the converter's."""
    monkeypatch.delenv("OCIO", raising=False)
    # usdrender ROP that writes nothing -> off-main poll fails -> flipbook.
    rop = _Rop(
        _Parm(str(tmp_path / "render_$F4.exr")), type_name="usdrender_rop"
    )
    fb_file = tmp_path / "render_0001_glpreview.0001.jpg"
    sv = MagicMock()
    sv.flipbook.side_effect = lambda **kw: fb_file.write_bytes(b"JPG")
    ui = MagicMock()
    ui.curDesktop.return_value.paneTabOfType.return_value = sv
    _wire(monkeypatch, tmp_path, rop, ui=ui)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)  # skip the 15s poll

    result = SynapseHandler()._handle_render({"node": "/out/karma1", "frame": 1})

    assert result["flipbook_fallback"] is True
    assert result["color_transform"] == "viewport_display (GL flipbook, unverified)"
    assert result["color_managed"] is False
    assert result["format"] == "jpeg"
    assert "output_file" not in result
