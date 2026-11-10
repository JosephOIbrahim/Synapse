"""retina.frame_reader and the firefly check (render QC, NR-QC-FRAME-CONTRACT).

The worker-side reader turns one EXR part into the float32 HxWx3 R, G, B array
that :func:`retina.firefly_scan.fireflies` takes, plus the data-window origin
that puts array positions back in the frame. Its pure logic (origin from a
spec, channel selection from a name list, spec + raw pixels to RGB) needs no
OpenImageIO, so most of this file runs on stock Python. The OIIO-backed tests
write a real EXR and skip where OpenImageIO is not installed.

numpy, cv2 and OpenImageIO are guarded with importorskip AND a realness check
(``__version__`` is a str), so a MagicMock another test planted in sys.modules
skips instead of passing. ``retina.frame_reader`` and ``retina.firefly_scan``
are imported unguarded: on a tree without them these tests must fail, not skip.
"""

import json
import sys
from types import SimpleNamespace

import pytest

from retina.firefly_scan import firefly_check  # noqa: E402  (unguarded on purpose)
from retina.frame_reader import (  # noqa: E402  (unguarded on purpose)
    READER_ID,
    FrameReaderUnavailable,
    origin_from_spec,
    select_rgb,
    window_from_spec,
)
from retina.t1 import T1Unavailable  # noqa: E402


def _real(name):
    mod = pytest.importorskip(name)
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip(f"{name} in sys.modules is not the real package")
    return mod


@pytest.fixture
def np():
    return _real("numpy")


@pytest.fixture
def cv2():
    return _real("cv2")


@pytest.fixture
def oiio():
    return _real("OpenImageIO")


def fake_spec(**kw):
    """A spec-like object: the attributes frame_reader reads from an ImageSpec."""
    base = dict(
        x=0, y=0, width=8, height=6, full_x=0, full_y=0, full_width=8, full_height=6,
        nchannels=4, channelnames=("R", "G", "B", "A"), format="half",
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# Origin (pure)
# --------------------------------------------------------------------------


def test_origin_is_data_window_relative_to_display_window():
    spec = fake_spec(x=110, y=70, full_x=10, full_y=20)
    assert origin_from_spec(spec) == [100, 50]


def test_origin_zero_when_windows_coincide():
    assert origin_from_spec(fake_spec()) == [0, 0]


def test_origin_can_be_negative_overscan():
    # A data window larger than the frame (overscan) starts before its corner.
    assert origin_from_spec(fake_spec(x=-4, y=-2, full_x=0, full_y=0)) == [-4, -2]


def test_origin_values_are_plain_ints():
    o = origin_from_spec(fake_spec(x=7.0, y=3.0, full_x=2.0, full_y=1.0))
    assert o == [5, 2] and all(type(v) is int for v in o)


def test_window_from_spec_names_both_windows():
    spec = fake_spec(x=110, y=70, width=8, height=6, full_x=10, full_y=20,
                     full_width=640, full_height=360)
    assert window_from_spec(spec) == {
        "x": 110, "y": 70, "width": 8, "height": 6,
        "full_x": 10, "full_y": 20, "full_width": 640, "full_height": 360,
        "origin": [100, 50],
    }


# --------------------------------------------------------------------------
# Channel selection (pure)
# --------------------------------------------------------------------------


def test_select_rgb_drops_alpha():
    idx, used, dropped = select_rgb(["R", "G", "B", "A"])
    assert idx == [0, 1, 2]
    assert used == ["R", "G", "B"]
    assert dropped == ["A"]


def test_select_rgb_reorders_by_name():
    # OpenEXR stores channels alphabetically: A, B, G, R.
    idx, used, dropped = select_rgb(["A", "B", "G", "R"])
    assert idx == [3, 2, 1]
    assert used == ["R", "G", "B"]
    assert dropped == ["A"]


def test_select_rgb_is_case_insensitive_and_keeps_file_names():
    idx, used, _ = select_rgb(["r", "g", "b"])
    assert idx == [0, 1, 2]
    assert used == ["r", "g", "b"]


def test_select_rgb_accepts_one_layer_prefix():
    idx, used, dropped = select_rgb(["C.A", "C.B", "C.G", "C.R", "depth.Z"])
    assert idx == [3, 2, 1]
    assert used == ["C.R", "C.G", "C.B"]
    assert dropped == ["C.A", "depth.Z"]


def test_select_rgb_bare_rgb_wins_over_a_layer():
    idx, used, dropped = select_rgb(["R", "G", "B", "diffuse.R", "diffuse.G", "diffuse.B"])
    assert idx == [0, 1, 2]
    assert dropped == ["diffuse.R", "diffuse.G", "diffuse.B"]


def test_select_rgb_refuses_two_layers_and_says_why():
    with pytest.raises(ValueError, match="several RGB layers") as exc:
        select_rgb(["C.R", "C.G", "C.B", "diffuse.R", "diffuse.G", "diffuse.B"])
    assert "C" in str(exc.value) and "DIFFUSE" in str(exc.value).upper()


def test_select_rgb_refuses_a_part_without_rgb():
    with pytest.raises(ValueError, match="no R, G and B") as exc:
        select_rgb(["primid.id"])
    assert "primid.id" in str(exc.value)


def test_select_rgb_refuses_a_partial_layer():
    with pytest.raises(ValueError, match="no R, G and B"):
        select_rgb(["C.R", "C.G", "A"])


# --------------------------------------------------------------------------
# Spec + raw pixels -> RGB (numpy only)
# --------------------------------------------------------------------------


def test_pixels_to_rgb_reduces_rgba_to_rgb(np):
    from retina.frame_reader import pixels_to_rgb

    raw = np.zeros((6, 8, 4), dtype=np.float32)
    raw[..., 0], raw[..., 1], raw[..., 2], raw[..., 3] = 0.1, 0.2, 0.3, 1.0
    rgb, info = pixels_to_rgb(fake_spec(x=13, y=24, full_x=3, full_y=4), raw, subimage=2)
    assert rgb.shape == (6, 8, 3) and rgb.dtype == np.float32
    assert rgb.flags["C_CONTIGUOUS"]
    assert rgb[0, 0].tolist() == pytest.approx([0.1, 0.2, 0.3])
    assert info["origin"] == [10, 20]
    assert info["subimage"] == 2
    assert info["channels"] == ["R", "G", "B"]
    assert info["dropped"] == ["A"]
    assert info["reader"] == READER_ID
    json.dumps(info)


def test_pixels_to_rgb_selects_channels_by_name_not_position(np):
    """Distinct per-channel values stored A, B, G, R come out R, G, B (referee F2)."""
    from retina.frame_reader import pixels_to_rgb

    raw = np.zeros((6, 8, 4), dtype=np.float32)
    raw[..., 0], raw[..., 1], raw[..., 2], raw[..., 3] = 0.9, 0.3, 0.2, 0.1  # A B G R
    rgb, info = pixels_to_rgb(fake_spec(channelnames=("A", "B", "G", "R")), raw)
    assert rgb[3, 4].tolist() == pytest.approx([0.1, 0.2, 0.3])
    assert info["channels"] == ["R", "G", "B"]
    assert info["dropped"] == ["A"]


def test_pixels_to_rgb_accepts_flat_buffer(np):
    from retina.frame_reader import pixels_to_rgb

    raw = np.arange(6 * 8 * 4, dtype=np.float32)
    rgb, _ = pixels_to_rgb(fake_spec(), raw)
    assert rgb.shape == (6, 8, 3)
    assert rgb[0, 1].tolist() == [4.0, 5.0, 6.0]


def test_pixels_to_rgb_refuses_a_part_without_rgb(np):
    from retina.frame_reader import pixels_to_rgb

    spec = fake_spec(nchannels=1, channelnames=("primid.id",), format="float")
    with pytest.raises(ValueError, match="no R, G and B"):
        pixels_to_rgb(spec, np.zeros((6, 8, 1), dtype=np.float32))


def test_pixels_to_rgb_refuses_integer_pixels(np):
    from retina.frame_reader import pixels_to_rgb

    spec = fake_spec(format="uint8")
    with pytest.raises(ValueError, match="uint8"):
        pixels_to_rgb(spec, np.zeros((6, 8, 4), dtype=np.float32))


def test_windowed_rgba_frame_positions_through_fireflies(np, cv2):
    """End to end on stock Python: a 4-channel part whose data window does not
    start at the display corner reports firefly positions in the frame."""
    from retina.firefly_scan import fireflies
    from retina.frame_reader import pixels_to_rgb

    raw = np.full((24, 32, 4), 0.18, dtype=np.float32)
    raw[..., 3] = 1.0
    raw[5, 7, :3] = 40.0
    spec = fake_spec(x=130, y=95, width=32, height=24, full_x=30, full_y=45,
                     full_width=640, full_height=360, nchannels=4,
                     channelnames=("A", "B", "G", "R"))
    # Alphabetical storage: put the bright value where R, G, B live.
    raw = raw[..., ::-1].copy()
    rgb, info = pixels_to_rgb(spec, raw)
    r = fireflies(rgb, origin=info["origin"], reader=info["reader"])
    assert r["count"] == 1
    f = r["fireflies"][0]
    assert (f["x"], f["y"]) == (7, 5)
    assert (f["frame_x"], f["frame_y"]) == (107, 55)
    assert (r["worst"]["frame_x"], r["worst"]["frame_y"]) == (107, 55)
    assert r["reader"] == READER_ID
    c = firefly_check(r)
    assert c["frame_position"] == [107, 55]
    assert c["reader"] == READER_ID


# --------------------------------------------------------------------------
# The OIIO leg
# --------------------------------------------------------------------------


def test_missing_oiio_raises_named_error(monkeypatch, tmp_path):
    from retina.frame_reader import read_frame

    path = tmp_path / "x.exr"
    path.write_bytes(b"not read")
    monkeypatch.setitem(sys.modules, "OpenImageIO", None)
    with pytest.raises(FrameReaderUnavailable) as exc:
        read_frame(path)
    assert isinstance(exc.value, T1Unavailable)
    assert "OpenImageIO" in str(exc.value)


def test_fake_oiio_is_refused(monkeypatch, tmp_path):
    from retina.frame_reader import read_frame

    path = tmp_path / "x.exr"
    path.write_bytes(b"not read")
    monkeypatch.setitem(sys.modules, "OpenImageIO", SimpleNamespace())
    with pytest.raises(FrameReaderUnavailable, match="not the real package"):
        read_frame(path)


def test_missing_file_raises(tmp_path):
    from retina.frame_reader import read_frame

    with pytest.raises(FileNotFoundError):
        read_frame(tmp_path / "absent.exr")


class _FakeInput:
    """Control-flow stand-in for oiio.ImageInput (not an API proof)."""

    def __init__(self, parts, log):
        self.parts, self.log, self.current = parts, log, 0

    def seek_subimage(self, subimage, miplevel):
        self.log.append(("seek", subimage, miplevel))
        if subimage >= len(self.parts):
            return False
        self.current = subimage
        return True

    def spec(self):
        return self.parts[self.current][0]

    def read_image(self, subimage, miplevel, chbegin, chend, fmt):
        self.log.append(("read", subimage, miplevel, chbegin, chend, fmt))
        return self.parts[subimage][1]

    def geterror(self):
        return "fake error"

    def close(self):
        self.log.append(("close",))


def _fake_oiio(parts, log):
    def open_(path):
        log.append(("open", path))
        return _FakeInput(parts, log)

    return SimpleNamespace(
        __version__="fake", ImageInput=SimpleNamespace(open=open_), geterror=lambda: "fake"
    )


def test_read_frame_control_flow_with_a_stand_in(np, monkeypatch, tmp_path):
    """Exercises read_frame's seek/read/close path on stock Python against a
    stand-in. It proves the control flow, not that the calls match OIIO."""
    from retina.frame_reader import read_frame

    path = tmp_path / "multi.exr"
    path.write_bytes(b"stand-in")
    beauty = np.full((6, 8, 4), 0.5, dtype=np.float32)
    idpart = np.zeros((6, 8, 1), dtype=np.float32)
    parts = [
        (fake_spec(nchannels=1, channelnames=("primid.id",), format="float"), idpart),
        (fake_spec(x=5, y=6, full_x=1, full_y=2, channelnames=("C.R", "C.G", "C.B", "C.A")), beauty),
    ]
    log = []
    monkeypatch.setitem(sys.modules, "OpenImageIO", _fake_oiio(parts, log))
    rgb, info = read_frame(path, subimage=1)
    assert rgb.shape == (6, 8, 3)
    assert info["origin"] == [4, 4]
    assert info["subimage"] == 1
    assert info["channels"] == ["C.R", "C.G", "C.B"]
    assert info["dropped"] == ["C.A"]
    assert ("seek", 1, 0) in log
    assert log[-1] == ("close",)
    log.clear()
    with pytest.raises(ValueError, match="no R, G and B"):
        read_frame(path, subimage=0)
    assert log[-1] == ("close",)
    log.clear()
    with pytest.raises(ValueError, match="no subimage 5"):
        read_frame(path, subimage=5)
    assert log[-1] == ("close",)


def _write_windowed_rgba(oiio, np, path, pixels, x, y, full_x, full_y, full_w, full_h):
    h, w, c = pixels.shape
    spec = oiio.ImageSpec(w, h, c, "half")
    spec.channelnames = ("R", "G", "B", "A")
    spec.alpha_channel = 3
    spec.x, spec.y = x, y
    spec.full_x, spec.full_y, spec.full_width, spec.full_height = full_x, full_y, full_w, full_h
    out = oiio.ImageOutput.create(str(path))
    assert out is not None, oiio.geterror()
    assert out.open(str(path), spec), out.geterror()
    assert out.write_image(np.ascontiguousarray(pixels)), out.geterror()
    out.close()
    return path


def test_oiio_windowed_rgba_reads_rgb_and_origin(oiio, np, tmp_path):
    from retina.frame_reader import read_frame

    px = np.zeros((6, 8, 4), dtype=np.float32)
    px[..., 3] = 1.0
    px[1, 2, :3] = (5.0, 6.0, 7.0)
    path = _write_windowed_rgba(oiio, np, tmp_path / "dw.exr", px, 10, 20, 0, 0, 64, 48)
    rgb, info = read_frame(path)
    assert rgb.shape == (6, 8, 3) and rgb.dtype == np.float32
    assert rgb[1, 2].tolist() == [5.0, 6.0, 7.0]
    assert info["origin"] == [10, 20]
    assert info["channels"] == ["R", "G", "B"]
    assert info["dropped"] == ["A"]
    assert info["subimage"] == 0
    assert info["window"]["full_width"] == 64


def test_oiio_windowed_rgba_frame_positions_through_fireflies(oiio, np, cv2, tmp_path):
    from retina.firefly_scan import fireflies
    from retina.frame_reader import read_frame

    px = np.full((24, 32, 4), 0.18, dtype=np.float32)
    px[..., 3] = 1.0
    px[5, 7, :3] = 40.0
    path = _write_windowed_rgba(oiio, np, tmp_path / "ffdw.exr", px, 100, 50, 0, 0, 640, 360)
    rgb, info = read_frame(path)
    r = fireflies(rgb, origin=info["origin"], reader=info["reader"])
    assert r["count"] == 1
    f = r["fireflies"][0]
    assert (f["x"], f["y"]) == (7, 5)
    assert (f["frame_x"], f["frame_y"]) == (107, 55)
    assert firefly_check(r)["frame_position"] == [107, 55]


# --------------------------------------------------------------------------
# fireflies() names its basis and reader
# --------------------------------------------------------------------------


def test_fireflies_names_luminance_basis_and_reader(np, cv2):
    from retina.firefly_scan import fireflies

    img = np.full((48, 64, 3), 0.18, dtype=np.float32)
    r = fireflies(img)
    assert r["luminance_basis"] == "rec709_weights"
    assert r["reader"] is None
    r = fireflies(img, reader="custom")
    assert r["reader"] == "custom"
    json.dumps(r)


def test_inconclusive_fireflies_still_names_basis(np, cv2):
    from retina.firefly_scan import fireflies

    # A 6x6 noisy patch on black: too few lit pixels for a noise estimate
    # (the fixture tests/test_retina_fireflies.py uses for the same path).
    rng = np.random.default_rng(3)
    img = np.zeros((64, 64, 3), dtype=np.float32)
    img[20:26, 20:26] = (0.18 + rng.normal(0, 0.01, (6, 6, 1))).astype(np.float32)
    r = fireflies(img, reader=READER_ID)
    assert r["inconclusive"] is True
    assert r["luminance_basis"] == "rec709_weights"
    assert r["reader"] == READER_ID


# --------------------------------------------------------------------------
# firefly_check (pure: dict in, dict out)
# --------------------------------------------------------------------------


def _result(**kw):
    base = {
        "width": 64, "height": 48, "nonfinite_pixels": 0, "threshold_sigma": 6.0,
        "max_blob_area": 9, "origin": None, "luminance_basis": "rec709_weights",
        "reader": None, "sigma": 0.01, "threshold": 0.06, "inconclusive": False,
        "note": None, "count": 0, "pixel_count": 0, "worst": None, "fireflies": [],
        "fireflies_truncated": False, "mask_path": None,
    }
    base.update(kw)
    return base


def test_check_inconclusive_is_none():
    c = firefly_check(_result(inconclusive=True, count=None, sigma=None, threshold=None,
                              note="too few lit pixels"))
    assert c["pass"] is None
    assert "too few lit pixels" in c["detail"]
    assert c["count"] is None


def test_check_clean_frame_passes():
    c = firefly_check(_result())
    assert c["pass"] is True
    assert c["count"] == 0
    assert c["worst"] is None
    assert c["frame_position"] is None


def test_check_a_firefly_is_a_finding():
    worst = {"x": 7, "y": 5, "frame_x": 107, "frame_y": 55, "rgb": [40.0] * 3,
             "luminance": 40.0, "sigmas": 900.0}
    c = firefly_check(_result(count=1, pixel_count=1, worst=worst, origin=[100, 50],
                              reader=READER_ID, mask_path="C:/f/beauty.fireflies.png"))
    assert c["pass"] is False
    assert c["count"] == 1
    assert c["worst"] == worst
    assert c["frame_position"] == [107, 55]
    assert c["array_position"] == [7, 5]
    assert c["origin"] == [100, 50]
    assert c["mask_path"] == "C:/f/beauty.fireflies.png"
    assert c["luminance_basis"] == "rec709_weights"
    assert c["reader"] == READER_ID
    assert c["threshold_sigma"] == 6.0
    assert c["sigma"] == 0.01


def test_check_without_origin_has_no_frame_position():
    worst = {"x": 7, "y": 5, "rgb": [40.0] * 3, "luminance": 40.0, "sigmas": 900.0}
    c = firefly_check(_result(count=1, worst=worst))
    assert c["frame_position"] is None
    assert c["array_position"] == [7, 5]


def test_check_shape_and_name():
    c = firefly_check(_result())
    assert c["name"] == "firefly_scan"
    assert set(c) >= {"name", "pass", "detail", "count", "worst", "frame_position",
                      "threshold_sigma", "sigma", "mask_path", "luminance_basis", "reader"}
    json.dumps(c)


def test_check_extras_cannot_overwrite_the_verdict():
    # A stray key in the result must not reach name/pass/detail.
    # "pass" is among the stray keys: a result saying pass=True with count=2
    # must still be a finding (referee F6).
    c = firefly_check(_result(count=2, worst={"x": 1, "y": 1}, name="x", detail="y",
                              **{"pass": True}))
    assert c["name"] == "firefly_scan"
    assert c["pass"] is False
    assert c["detail"] != "y"


def test_check_stray_pass_key_cannot_turn_a_clean_frame_red():
    c = firefly_check(_result(**{"pass": False}))
    assert c["pass"] is True


# Each half of the inconclusive guard on its own (referee F5).


def test_check_inconclusive_flag_wins_over_a_zero_count():
    c = firefly_check(_result(inconclusive=True, count=0, note="noise not estimated"))
    assert c["pass"] is None
    assert "noise not estimated" in c["detail"]


def test_check_missing_count_is_none_even_when_not_flagged():
    c = firefly_check(_result(inconclusive=False, count=None))
    assert c["pass"] is None
    assert c["detail"].startswith("inconclusive")


# --------------------------------------------------------------------------
# Non-finite pixels (referee F1)
# --------------------------------------------------------------------------


def test_check_all_nonfinite_frame_is_none_and_says_why():
    c = firefly_check(_result(nonfinite_pixels=64 * 48))
    assert c["pass"] is None
    assert "non-finite" in c["detail"]
    assert c["nonfinite_pixels"] == 64 * 48


def test_check_some_nonfinite_pixels_ride_as_an_extra_and_in_the_detail():
    c = firefly_check(_result(nonfinite_pixels=3))
    # The count-based verdict is kept (no new threshold); the record says
    # the pixels were zeroed before the scan.
    assert c["pass"] is True
    assert c["nonfinite_pixels"] == 3
    assert "3 non-finite" in c["detail"]
    assert "zeroed" in c["detail"]


def test_check_some_nonfinite_pixels_named_on_a_finding_too():
    c = firefly_check(_result(count=1, worst={"x": 1, "y": 1}, nonfinite_pixels=1))
    assert c["pass"] is False
    assert c["nonfinite_pixels"] == 1
    assert "1 non-finite pixel " in c["detail"]


def test_check_finite_frame_carries_zero_nonfinite_and_no_note():
    c = firefly_check(_result())
    assert c["nonfinite_pixels"] == 0
    assert "non-finite" not in c["detail"]


def test_check_without_nonfinite_key_still_works():
    r = _result()
    del r["nonfinite_pixels"]
    c = firefly_check(r)
    assert c["pass"] is True
    assert c["nonfinite_pixels"] is None


# Referee round 2 on 17e450b5.


def test_check_one_finite_pixel_left_is_not_all_nonfinite():
    # width*height - 1 non-finite: one real pixel remains, so the
    # count-based verdict stands and the zeroed note is carried. Kills the
    # "width only", "height only" and ">= total - 1" comparisons.
    c = firefly_check(_result(width=64, height=48, count=0, nonfinite_pixels=64 * 48 - 1))
    assert c["pass"] is True
    assert "zeroed" in c["detail"]
    assert c["nonfinite_pixels"] == 64 * 48 - 1


def test_check_all_nonfinite_detail_has_no_zeroed_note():
    c = firefly_check(_result(nonfinite_pixels=64 * 48))
    assert c["pass"] is None
    assert "zeroed" not in c["detail"]


@pytest.mark.parametrize(
    "bad",
    [
        "abc",                # int() raises ValueError
        object(),             # int() raises TypeError
        float("inf"),         # int() raises OverflowError
        float("nan"),
        -3,
        True,
        False,
        2.5,
    ],
    ids=["str", "object", "inf", "nan", "negative", "bool_true", "bool_false",
         "non_integer_float"],
)
def test_check_bad_nonfinite_value_reads_none(bad):
    clean = firefly_check(_result())
    c = firefly_check(_result(nonfinite_pixels=bad))
    assert c["nonfinite_pixels"] is None
    # Nothing raw reaches the detail: it reads exactly as a clean frame's.
    assert c["detail"] == clean["detail"]
    assert c["pass"] is True


@pytest.mark.parametrize(
    "dims",
    [
        {"width": "MISSING"},
        {"height": "MISSING"},
        {"width": None},
        {"height": None},
        {"width": 0},
        {"height": 0},
        {"width": -64, "height": -48},
        {"width": True},
        {"height": 2.5},
        {"width": "64"},
    ],
    ids=["width_missing", "height_missing", "width_none", "height_none", "width_zero",
         "height_zero", "both_negative", "width_bool", "height_float", "width_str"],
)
@pytest.mark.parametrize("count", [0, 1])
def test_check_nonfinite_without_a_usable_size_is_inconclusive(dims, count):
    r = _result(nonfinite_pixels=5, count=count, worst={"x": 1, "y": 1} if count else None)
    for k, v in dims.items():
        if v == "MISSING":
            del r[k]
        else:
            r[k] = v
    c = firefly_check(r)
    assert c["pass"] is None  # fail closed: never True, and no count verdict
    assert c["detail"].startswith("inconclusive")
    assert "frame size" in c["detail"]
    assert c["nonfinite_pixels"] == 5


@pytest.mark.parametrize("nonfinite", [0, None, "MISSING"])
@pytest.mark.parametrize("key", ["width", "height"])
def test_check_missing_size_without_nonfinite_keeps_the_count_verdict(nonfinite, key):
    for count, want in ((0, True), (1, False)):
        r = _result(count=count, worst={"x": 1, "y": 1} if count else None)
        if nonfinite == "MISSING":
            del r["nonfinite_pixels"]
        else:
            r["nonfinite_pixels"] = nonfinite
        del r[key]
        c = firefly_check(r)
        assert c["pass"] is want
        assert "frame size" not in c["detail"]


def test_all_nan_frame_through_fireflies_is_not_a_pass(np, cv2):
    from retina.firefly_scan import fireflies

    r = fireflies(np.full((48, 64, 3), np.nan, dtype=np.float32))
    c = firefly_check(r)
    assert c["pass"] is None
    assert "non-finite" in c["detail"]
    assert c["nonfinite_pixels"] == 48 * 64


def test_one_inf_pixel_through_fireflies_is_named(np, cv2):
    from retina.firefly_scan import fireflies

    rng = np.random.default_rng(1)
    img = (0.18 + rng.normal(0, 0.01, (48, 64, 1))).repeat(3, axis=2).astype(np.float32)
    img[10, 10, 0] = np.inf
    c = firefly_check(fireflies(img))
    assert c["nonfinite_pixels"] == 1
    assert "1 non-finite pixel " in c["detail"]
