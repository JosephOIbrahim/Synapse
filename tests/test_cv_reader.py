"""synapse.cv reader: generated EXRs through OpenImageIO, and the OpenCV hand-off.

Guards: numpy, OpenImageIO and cv2 via importorskip plus a realness check
(``__version__`` is a str), so a MagicMock in sys.modules skips rather than
passes. ``synapse.cv`` is imported unguarded: these tests fail on a tree
without it.
"""

import sys

import pytest

np = pytest.importorskip("numpy")
if not isinstance(getattr(np, "__version__", None), str):
    pytest.skip("numpy in sys.modules is not the real package", allow_module_level=True)

from synapse.cv import (  # noqa: E402  (unguarded on purpose)
    CVDependencyError,
    CVInputError,
    exposure,
    read_linear_rgb,
    to_cv_bgr,
)


def _real(name):
    mod = pytest.importorskip(name)
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip(f"{name} in sys.modules is not the real package")
    return mod


@pytest.fixture
def oiio():
    return _real("OpenImageIO")


@pytest.fixture
def cv2():
    return _real("cv2")


def write_image(oiio, path, pixels, channelnames, fmt="float"):
    h, w, c = pixels.shape
    spec = oiio.ImageSpec(w, h, c, fmt)
    spec.channelnames = tuple(channelnames)
    out = oiio.ImageOutput.create(str(path))
    assert out is not None, oiio.geterror()
    assert out.open(str(path), spec), out.geterror()
    assert out.write_image(np.ascontiguousarray(pixels)), out.geterror()
    out.close()
    return path


# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------


def test_missing_oiio_raises_named_error(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "OpenImageIO", None)
    with pytest.raises(CVDependencyError) as exc:
        read_linear_rgb(tmp_path / "anything.exr")
    assert exc.value.package == "OpenImageIO"
    assert "pip install OpenImageIO" in str(exc.value)


# --------------------------------------------------------------------------
# read_linear_rgb
# --------------------------------------------------------------------------


def test_reads_rgba_exr_in_rgb_order_and_drops_alpha(oiio, tmp_path):
    px = np.zeros((6, 8, 4), dtype=np.float32)
    px[..., 3] = 1.0
    px[2, 5] = (1.25, 2.5, 3.75, 0.5)
    px[0, 0] = (7.0, 0.0, 0.0, 1.0)
    path = write_image(oiio, tmp_path / "rgba.exr", px, ("R", "G", "B", "A"))
    img = read_linear_rgb(path)
    assert img.shape == (6, 8, 3)
    assert img.dtype == np.float32
    assert img.flags["C_CONTIGUOUS"]
    assert img[2, 5].tolist() == [1.25, 2.5, 3.75]
    assert img[0, 0].tolist() == [7.0, 0.0, 0.0]
    assert img[1, 1].tolist() == [0.0, 0.0, 0.0]


def test_reads_layered_exr_by_channel_name(oiio, tmp_path):
    px = np.zeros((4, 4, 3), dtype=np.float32)
    px[1, 2] = (0.1, 0.2, 0.3)
    path = write_image(oiio, tmp_path / "layer.exr", px, ("beauty.R", "beauty.G", "beauty.B"))
    img = read_linear_rgb(path)
    assert img[1, 2].tolist() == pytest.approx([0.1, 0.2, 0.3], abs=1e-7)


def test_half_exr_flat_grey_round_trip_to_exposure(oiio, tmp_path):
    px = np.full((32, 32, 3), 0.18, dtype=np.float32)
    path = write_image(oiio, tmp_path / "grey_half.exr", px, ("R", "G", "B"), fmt="half")
    img = read_linear_rgb(path)
    assert img.dtype == np.float32
    r = exposure(img)
    # 0.18 in half precision is 0.179993...
    assert r["median_luminance"] == pytest.approx(0.18, abs=1e-4)
    assert r["suggested_offset_stops"] == pytest.approx(0.0, abs=1e-3)
    assert r["black_pct"] == 0.0 and r["clipped_pct"] == 0.0


def test_clipped_exr_round_trip(oiio, tmp_path):
    px = np.full((10, 10, 3), 0.18, dtype=np.float32)
    px[:, :3] = 6.0
    img = read_linear_rgb(write_image(oiio, tmp_path / "clip.exr", px, ("R", "G", "B")))
    assert exposure(img)["clipped_pct"] == 30.0


def test_planted_fireflies_exr_round_trip(oiio, cv2, tmp_path):
    # The host-side reader feeds the worker-side detector (retina, where cv2 lives).
    from retina.firefly_scan import fireflies

    px = np.full((48, 64, 4), 0.18, dtype=np.float32)
    px[..., 3] = 1.0
    for (x, y), v in {(3, 4): 40.0, (50, 20): 90.0}.items():
        px[y, x, :3] = v
    img = read_linear_rgb(write_image(oiio, tmp_path / "ff.exr", px, ("R", "G", "B", "A")))
    r = fireflies(img)
    assert r["count"] == 2
    assert [(f["x"], f["y"]) for f in r["fireflies"]] == [(50, 20), (3, 4)]
    assert r["worst"]["rgb"] == [90.0, 90.0, 90.0]


def test_single_channel_exr_has_no_rgb(oiio, tmp_path):
    px = np.full((4, 4, 1), 0.5, dtype=np.float32)
    path = write_image(oiio, tmp_path / "y.exr", px, ("Y",))
    with pytest.raises(CVInputError, match="no R, G and B"):
        read_linear_rgb(path)


def test_integer_format_is_refused_not_guessed(oiio, tmp_path):
    px = np.full((4, 4, 3), 128, dtype=np.uint8)
    path = write_image(oiio, tmp_path / "grey.png", px, ("R", "G", "B"), fmt="uint8")
    with pytest.raises(CVInputError, match="uint8"):
        read_linear_rgb(path)


def test_missing_file(oiio, tmp_path):
    with pytest.raises(FileNotFoundError):
        read_linear_rgb(tmp_path / "nope.exr")


def test_unreadable_file(oiio, tmp_path):
    bad = tmp_path / "bad.exr"
    bad.write_bytes(b"not an image")
    with pytest.raises(CVInputError, match="cannot open"):
        read_linear_rgb(bad)


# --------------------------------------------------------------------------
# to_cv_bgr: the one conversion to OpenCV's layout
# --------------------------------------------------------------------------


def test_to_cv_bgr_float_swaps_channels(cv2):
    rgb = np.zeros((2, 3, 3), dtype=np.float32)
    rgb[1, 2] = (0.9, 0.5, 0.1)
    bgr = to_cv_bgr(rgb)
    assert bgr.dtype == np.float32 and bgr.flags["C_CONTIGUOUS"]
    assert bgr[1, 2].tolist() == pytest.approx([0.1, 0.5, 0.9])
    back = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    assert np.array_equal(back, rgb)


def test_to_cv_bgr_uint8_clips_and_rounds(cv2):
    rgb = np.array([[[0.5, 2.0, -1.0]]], dtype=np.float32)
    bgr = to_cv_bgr(rgb, dtype="uint8")
    assert bgr.dtype == np.uint8
    assert bgr[0, 0].tolist() == [0, 255, 128]
    assert to_cv_bgr(rgb, dtype="uint16")[0, 0].tolist() == [0, 65535, 32768]
    # OpenCV reads it as a 3-channel BGR image: its gray conversion weights blue lowest.
    assert cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).shape == (1, 1)


def test_to_cv_bgr_rejects_unknown_dtype():
    with pytest.raises(CVInputError):
        to_cv_bgr(np.zeros((2, 2, 3), dtype=np.float32), dtype="int8")


# --------------------------------------------------------------------------
# Pins from the review of 65b02294 (nits)
# --------------------------------------------------------------------------


def test_several_rgb_layers_are_refused(oiio, tmp_path):
    px = np.zeros((4, 4, 6), dtype=np.float32)
    names = ("beauty.R", "beauty.G", "beauty.B", "diffuse.R", "diffuse.G", "diffuse.B")
    path = write_image(oiio, tmp_path / "layers.exr", px, names)
    with pytest.raises(CVInputError, match="several RGB layers"):
        read_linear_rgb(path)


def write_windowed(oiio, path, pixels, x, y, full_w, full_h):
    h, w, c = pixels.shape
    spec = oiio.ImageSpec(w, h, c, "float")
    spec.channelnames = ("R", "G", "B")
    spec.x, spec.y = x, y
    spec.full_x, spec.full_y, spec.full_width, spec.full_height = 0, 0, full_w, full_h
    out = oiio.ImageOutput.create(str(path))
    assert out is not None, oiio.geterror()
    assert out.open(str(path), spec), out.geterror()
    assert out.write_image(np.ascontiguousarray(pixels)), out.geterror()
    out.close()
    return path


def test_read_frame_carries_the_data_window(oiio, tmp_path):
    from synapse.cv import read_frame  # inside: a tree without it fails here only

    px = np.zeros((6, 8, 3), dtype=np.float32)
    px[1, 2] = (5.0, 6.0, 7.0)
    path = write_windowed(oiio, tmp_path / "dw.exr", px, 10, 20, 64, 48)
    img, window = read_frame(path)
    assert window == {
        "x": 10, "y": 20, "width": 8, "height": 6,
        "full_x": 0, "full_y": 0, "full_width": 64, "full_height": 48,
        "origin": [10, 20],
    }
    assert img[1, 2].tolist() == [5.0, 6.0, 7.0]
    assert np.array_equal(img, read_linear_rgb(path))


def test_windowed_exr_fireflies_in_frame_positions(oiio, cv2, tmp_path):
    from synapse.cv import read_frame
    from retina.firefly_scan import fireflies

    px = np.full((24, 32, 3), 0.18, dtype=np.float32)
    px[5, 7] = 40.0
    img, window = read_frame(write_windowed(oiio, tmp_path / "ffdw.exr", px, 100, 50, 640, 360))
    r = fireflies(img, origin=window["origin"])
    assert r["count"] == 1
    f = r["fireflies"][0]
    assert (f["x"], f["y"]) == (7, 5)
    assert (f["frame_x"], f["frame_y"]) == (107, 55)


def test_read_frame_origin_is_relative_to_the_display_window(oiio, tmp_path):
    # The origin is the data window's position IN THE FRAME: x - full_x,
    # y - full_y. Every other test has its display window at (0, 0), where a
    # mutant returning the raw data-window corner survived (d4c7ab11 review).
    from synapse.cv import read_frame

    px = np.zeros((6, 8, 3), dtype=np.float32)
    px[1, 2] = (5.0, 6.0, 7.0)
    spec = oiio.ImageSpec(8, 6, 3, "float")
    spec.channelnames = ("R", "G", "B")
    spec.x, spec.y = 10, 20
    spec.full_x, spec.full_y, spec.full_width, spec.full_height = 4, 6, 64, 48
    path = tmp_path / "dwfull.exr"
    out = oiio.ImageOutput.create(str(path))
    assert out is not None, oiio.geterror()
    assert out.open(str(path), spec), out.geterror()
    assert out.write_image(np.ascontiguousarray(px)), out.geterror()
    out.close()
    img, window = read_frame(path)
    assert (window["full_x"], window["full_y"]) == (4, 6)
    assert (window["x"], window["y"]) == (10, 20)
    assert window["origin"] == [6, 14]
    assert img[1, 2].tolist() == [5.0, 6.0, 7.0]
