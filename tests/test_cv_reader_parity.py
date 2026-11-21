"""R-024 / OBSERVER-8: the host and worker EXR readers are pinned to one contract.

``synapse.cv`` (``python/synapse/cv/reader.py``) and ``retina.frame_reader`` are
two copies of one EXR reading contract: R, G, B picked by channel name, integer
formats refused rather than guessed, and the data/display windows reported with
``origin = [x - full_x, y - full_y]``. The RETINA worker venv carries neither
``synapse`` nor ``cv2``, so the worker cannot import the host copy; the two are
mirrored by necessity. This file is the pin the finding asked for: identical
spec fixtures are read through both implementations and any disagreement —
channel choice, float-format refusal, window or origin — fails here.

Two legs:

* a stand-in OpenImageIO (runs on stock Python + numpy) drives both readers
  through one ``ImageInput`` and compares the arrays, the windows and every
  refusal;
* a real OpenImageIO leg (skipped where OpenImageIO is absent, as in
  ``tests/test_cv_reader.py``) repeats the assertions on generated EXRs built
  with the fixture shapes both suites already use.

numpy is guarded with importorskip AND a realness check (``__version__`` is a
str), so a MagicMock another test planted in sys.modules skips rather than
passes. ``synapse.cv`` and ``retina.frame_reader`` are imported unguarded: on a
tree without either, these tests must fail, not skip.
"""

import sys
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
if not isinstance(getattr(np, "__version__", None), str):
    pytest.skip("numpy in sys.modules is not the real package", allow_module_level=True)

import synapse.cv as host_cv  # noqa: E402  (unguarded on purpose)
from retina.frame_reader import read_frame as worker_read_frame  # noqa: E402


# --------------------------------------------------------------------------
# A stand-in OpenImageIO the two readers share
# --------------------------------------------------------------------------


class _StandInInput:
    """Control-flow and value stand-in for oiio.ImageInput (not an API proof)."""

    def __init__(self, spec, pixels, error="stand-in error"):
        self._spec = spec
        self._pixels = pixels
        self._error = error
        self.closed = False

    def seek_subimage(self, subimage, miplevel):
        return subimage == 0

    def spec(self):
        return self._spec

    def read_image(self, subimage, miplevel, chbegin, chend, fmt):
        return self._pixels

    def geterror(self):
        return self._error

    def close(self):
        self.closed = True


def _stand_in_oiio(entries, error="stand-in open failure"):
    """A module-shaped stand-in. ``__version__`` is a str, so both readers accept
    it as the real package and every realness guard behaves as in production."""

    def open_(path):
        return entries.get(str(path))

    return SimpleNamespace(
        __version__="stand-in",
        ImageInput=SimpleNamespace(open=open_),
        geterror=lambda: error,
    )


def _install(monkeypatch, tmp_path, spec, pixels, *, name="frame.exr", openable=True):
    path = tmp_path / name
    path.write_bytes(b"stand-in")
    entry = _StandInInput(spec, pixels) if openable else None
    monkeypatch.setitem(sys.modules, "OpenImageIO", _stand_in_oiio({str(path): entry}))
    return path


def _spec(**over):
    """A spec-like object: exactly the attributes both readers take from ImageSpec."""
    base = dict(
        x=0, y=0, width=8, height=6, full_x=0, full_y=0, full_width=8, full_height=6,
        nchannels=4, channelnames=("R", "G", "B", "A"), format="half",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _pixels(nchannels=4, height=6, width=8):
    """A distinct value per channel, so selecting the wrong channel cannot pass."""
    raw = np.zeros((height, width, nchannels), dtype=np.float32)
    for i in range(nchannels):
        raw[..., i] = 0.1 * (i + 1)
    return raw


def _read_both(path):
    host_rgb, host_window = host_cv.read_frame(path)
    worker_rgb, worker_info = worker_read_frame(path)
    return host_rgb, host_window, worker_rgb, worker_info


def _refused_both(path):
    """Assert both readers refuse ``path`` as a ValueError; return both errors."""
    with pytest.raises(ValueError) as host_exc:
        host_cv.read_frame(path)
    with pytest.raises(ValueError) as worker_exc:
        worker_read_frame(path)
    return host_exc.value, worker_exc.value


# --------------------------------------------------------------------------
# Stand-in leg: agree on values, windows and origin
# --------------------------------------------------------------------------

# (spec overrides, the contract's known first pixel in R,G,B order, the origin)
_SPEC_CASES = [
    pytest.param(
        dict(channelnames=("R", "G", "B", "A")),
        [0.1, 0.2, 0.3], [0, 0],
        id="bare_rgba",
    ),
    pytest.param(
        dict(channelnames=("A", "B", "G", "R")),  # OpenEXR stores alphabetically
        [0.4, 0.3, 0.2], [0, 0],
        id="alphabetical_storage_read_by_name",
    ),
    pytest.param(
        dict(channelnames=("C.R", "C.G", "C.B", "C.A")),
        [0.1, 0.2, 0.3], [0, 0],
        id="one_layer_prefixed",
    ),
    pytest.param(
        dict(x=10, y=20, full_x=0, full_y=0, full_width=64, full_height=48),
        [0.1, 0.2, 0.3], [10, 20],
        id="data_window_offset_in_frame",
    ),
    pytest.param(
        dict(x=10, y=20, full_x=4, full_y=6, full_width=64, full_height=48),
        [0.1, 0.2, 0.3], [6, 14],
        id="origin_is_relative_to_the_display_window",
    ),
    pytest.param(
        dict(x=-4, y=-2),
        [0.1, 0.2, 0.3], [-4, -2],
        id="overscan_negative_origin",
    ),
    pytest.param(dict(format="half"), [0.1, 0.2, 0.3], [0, 0], id="half_pixels"),
    pytest.param(dict(format="float"), [0.1, 0.2, 0.3], [0, 0], id="float_pixels"),
    pytest.param(dict(format="double"), [0.1, 0.2, 0.3], [0, 0], id="double_pixels"),
]


@pytest.mark.parametrize("over, first_pixel, origin", _SPEC_CASES)
def test_readers_agree_on_spec_fixtures(monkeypatch, tmp_path, over, first_pixel, origin):
    spec = _spec(**over)
    path = _install(monkeypatch, tmp_path, spec, _pixels(spec.nchannels))

    host_rgb, host_window, worker_rgb, worker_info = _read_both(path)

    # The contract's known answer, in both implementations.
    for arr in (host_rgb, worker_rgb):
        assert arr.shape == (6, 8, 3)
        assert arr.dtype == np.float32
        assert arr.flags["C_CONTIGUOUS"]
        assert arr[0, 0].tolist() == pytest.approx(first_pixel, abs=1e-6)

    # The parity pin: any drift between the copies fails here.
    assert np.array_equal(host_rgb, worker_rgb)
    assert host_window == worker_info["window"]
    assert worker_info["origin"] == host_window["origin"] == origin


# --------------------------------------------------------------------------
# Stand-in leg: refuse the same inputs for the same stated reason
# --------------------------------------------------------------------------


def test_integer_pixels_refused_by_both(monkeypatch, tmp_path):
    path = _install(monkeypatch, tmp_path, _spec(format="uint8"), _pixels())
    host_exc, worker_exc = _refused_both(path)
    assert isinstance(host_exc, host_cv.CVInputError)
    for message in (str(host_exc), str(worker_exc)):
        assert "uint8" in message
        assert "float" in message


def test_part_without_rgb_refused_by_both(monkeypatch, tmp_path):
    spec = _spec(nchannels=1, channelnames=("primid.id",), format="float")
    path = _install(monkeypatch, tmp_path, spec, _pixels(1))
    host_exc, worker_exc = _refused_both(path)
    assert "no R, G and B" in str(host_exc)
    assert "no R, G and B" in str(worker_exc)


def test_ambiguous_rgb_layers_refused_by_both(monkeypatch, tmp_path):
    names = ("beauty.R", "beauty.G", "beauty.B", "diffuse.R", "diffuse.G", "diffuse.B")
    path = _install(monkeypatch, tmp_path, _spec(nchannels=6, channelnames=names), _pixels(6))
    host_exc, worker_exc = _refused_both(path)
    for message in (str(host_exc), str(worker_exc)):
        assert "several RGB layers" in message


def test_unopenable_file_refused_by_both(monkeypatch, tmp_path):
    path = _install(monkeypatch, tmp_path, _spec(), _pixels(), openable=False)
    host_exc, worker_exc = _refused_both(path)
    assert "cannot open" in str(host_exc)
    assert "cannot open" in str(worker_exc)


def test_missing_file_raises_file_not_found_in_both(monkeypatch, tmp_path):
    # Dependencies satisfied, so the missing file is the only difference the
    # readers can be reacting to.
    monkeypatch.setitem(sys.modules, "OpenImageIO", _stand_in_oiio({}))
    missing = tmp_path / "absent.exr"
    with pytest.raises(FileNotFoundError):
        host_cv.read_frame(missing)
    with pytest.raises(FileNotFoundError):
        worker_read_frame(missing)


# --------------------------------------------------------------------------
# Real OpenImageIO leg: the same fixtures both suites already write
# --------------------------------------------------------------------------


@pytest.fixture
def oiio():
    mod = pytest.importorskip("OpenImageIO")
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip("OpenImageIO in sys.modules is not the real package")
    return mod


def _write(oiio, path, pixels, channelnames, fmt="float", window=None):
    height, width, channels = pixels.shape
    spec = oiio.ImageSpec(width, height, channels, fmt)
    spec.channelnames = tuple(channelnames)
    if window is not None:
        spec.x, spec.y = window[0], window[1]
        spec.full_x, spec.full_y = window[2], window[3]
        spec.full_width, spec.full_height = window[4], window[5]
    out = oiio.ImageOutput.create(str(path))
    assert out is not None, oiio.geterror()
    assert out.open(str(path), spec), out.geterror()
    assert out.write_image(np.ascontiguousarray(pixels)), out.geterror()
    out.close()
    return path


def test_real_exr_parity_windowed_rgba(oiio, tmp_path):
    px = np.zeros((6, 8, 4), dtype=np.float32)
    px[..., 3] = 1.0
    px[0, 0, :3] = (7.0, 0.25, 0.0)
    px[1, 2, :3] = (5.0, 6.0, 7.0)
    path = _write(
        oiio, tmp_path / "parity_rgba.exr", px, ("R", "G", "B", "A"),
        fmt="half", window=(10, 20, 0, 0, 64, 48),
    )

    host_rgb, host_window, worker_rgb, worker_info = _read_both(path)

    assert np.array_equal(host_rgb, worker_rgb)
    assert host_window == worker_info["window"]
    assert host_window["origin"] == [10, 20]
    assert host_rgb[1, 2].tolist() == [5.0, 6.0, 7.0]


def test_real_exr_parity_layered(oiio, tmp_path):
    px = np.zeros((4, 4, 3), dtype=np.float32)
    px[1, 2] = (0.1, 0.2, 0.3)
    path = _write(oiio, tmp_path / "parity_layer.exr", px, ("beauty.R", "beauty.G", "beauty.B"))

    host_rgb, host_window, worker_rgb, worker_info = _read_both(path)

    assert np.array_equal(host_rgb, worker_rgb)
    assert host_window == worker_info["window"]
    assert host_rgb[1, 2].tolist() == pytest.approx([0.1, 0.2, 0.3], abs=1e-7)


def test_real_integer_file_refused_by_both(oiio, tmp_path):
    px = np.full((4, 4, 3), 128, dtype=np.uint8)
    path = _write(oiio, tmp_path / "grey.png", px, ("R", "G", "B"), fmt="uint8")
    host_exc, worker_exc = _refused_both(path)
    assert "uint8" in str(host_exc)
    assert "uint8" in str(worker_exc)


def test_real_two_layer_file_refused_by_both(oiio, tmp_path):
    names = ("beauty.R", "beauty.G", "beauty.B", "diffuse.R", "diffuse.G", "diffuse.B")
    path = _write(oiio, tmp_path / "layers.exr", np.zeros((4, 4, 6), dtype=np.float32), names)
    host_exc, worker_exc = _refused_both(path)
    assert "several RGB layers" in str(host_exc)
    assert "several RGB layers" in str(worker_exc)
