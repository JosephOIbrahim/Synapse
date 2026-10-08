"""synapse.cv exposure on generated arrays (Phase 1, render QC).

numpy is needed for every test here and OpenImageIO for the histogram. Each is
guarded with importorskip AND a realness check (``__version__`` is a str), so a
MagicMock another test planted in sys.modules skips instead of passing.
``synapse.cv`` itself is imported unguarded: on a tree without it these tests
must fail, not skip.
"""

import ast
import json
import pathlib
import sys
from unittest.mock import MagicMock

import pytest

np = pytest.importorskip("numpy")
if not isinstance(getattr(np, "__version__", None), str):
    pytest.skip("numpy in sys.modules is not the real package", allow_module_level=True)

import synapse.cv as scv  # noqa: E402  (unguarded on purpose)
from synapse.cv import CVDependencyError, CVInputError, exposure  # noqa: E402


@pytest.fixture
def oiio():
    mod = pytest.importorskip("OpenImageIO")
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip("OpenImageIO in sys.modules is not the real package")
    return mod


def flat(h=48, w=64, value=0.18):
    return np.full((h, w, 3), value, dtype=np.float32)


# --------------------------------------------------------------------------
# Dependencies: missing or fake means a named error, never a result
# --------------------------------------------------------------------------


def test_missing_numpy_raises_named_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)
    with pytest.raises(CVDependencyError) as exc:
        exposure([[[0.18, 0.18, 0.18]]])
    assert exc.value.package == "numpy"
    assert isinstance(exc.value, ImportError)


def test_fake_numpy_is_refused(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", MagicMock())
    with pytest.raises(CVDependencyError, match="not the real package"):
        exposure(flat())


def test_missing_oiio_histogram_raises_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "OpenImageIO", None)
    out = tmp_path / "hist.png"
    with pytest.raises(CVDependencyError) as exc:
        exposure(flat(), histogram_path=out)
    assert "pip install OpenImageIO" in str(exc.value)
    assert not out.exists()


def test_fake_oiio_is_refused(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "OpenImageIO", MagicMock())
    with pytest.raises(CVDependencyError, match="not the real package"):
        exposure(flat(), histogram_path=tmp_path / "hist.png")


def test_exposure_stats_need_neither_oiio_nor_cv2(monkeypatch):
    monkeypatch.setitem(sys.modules, "OpenImageIO", None)
    monkeypatch.setitem(sys.modules, "cv2", None)
    r = exposure(flat())
    assert r["median_luminance"] == pytest.approx(0.18, abs=1e-6)
    assert r["histogram_path"] is None


# --------------------------------------------------------------------------
# Exposure
# --------------------------------------------------------------------------


def test_exposure_flat_grey():
    r = exposure(flat(value=0.18))
    assert r["width"] == 64 and r["height"] == 48
    assert r["pixels_measured"] == 64 * 48
    assert r["mean_luminance"] == pytest.approx(0.18, abs=1e-6)
    assert r["median_luminance"] == pytest.approx(0.18, abs=1e-6)
    assert r["black_pct"] == 0.0
    assert r["clipped_pct"] == 0.0
    assert r["suggested_offset_stops"] == pytest.approx(0.0, abs=1e-5)
    assert r["luminance_weights"] == "rec709"
    assert r["offset_basis"] == "median"
    assert r["target_luminance"] == 0.18
    json.dumps(r)


@pytest.mark.parametrize("value,stops", [(0.09, 1.0), (0.72, -2.0), (0.045, 2.0)])
def test_exposure_offset_in_stops_toward_target(value, stops):
    r = exposure(flat(value=value))
    assert r["suggested_offset_stops"] == pytest.approx(stops, abs=1e-5)


def test_exposure_offset_target_is_a_parameter():
    r = exposure(flat(value=0.18), target_luminance=0.36)
    assert r["suggested_offset_stops"] == pytest.approx(1.0, abs=1e-5)


def test_exposure_clipped_half_frame():
    img = flat(h=10, w=10, value=0.18)
    img[:5] = 2.0
    r = exposure(img)
    assert r["clipped_pct"] == 50.0
    # Median of 50 x 0.18 and 50 x 2.0 is their midpoint.
    assert r["median_luminance"] == pytest.approx((0.18 + 2.0) / 2, abs=1e-5)


def test_exposure_one_channel_at_threshold_counts_as_clipped():
    img = flat(h=10, w=10, value=0.18)
    img[0, 0] = (1.0, 0.0, 0.0)
    img[0, 1] = (0.0, 0.0, 1.5)
    r = exposure(img)
    assert r["clipped_pct"] == 2.0
    assert exposure(img, clip_threshold=2.0)["clipped_pct"] == 0.0


def test_exposure_black_quarter():
    img = flat(h=8, w=8, value=0.18)
    img[:4, :4] = 0.0
    r = exposure(img)
    assert r["black_pct"] == 25.0
    assert exposure(img, black_threshold=0.2)["black_pct"] == 100.0


def test_exposure_uses_rec709_weights():
    assert scv.REC709_WEIGHTS == (0.2126, 0.7152, 0.0722)
    for i, w in enumerate(scv.REC709_WEIGHTS):
        img = np.zeros((4, 4, 3), dtype=np.float32)
        img[..., i] = 1.0
        assert exposure(img, clip_threshold=2.0)["mean_luminance"] == pytest.approx(w, abs=1e-6)


def test_exposure_black_frame_has_no_offset():
    r = exposure(flat(value=0.0))
    assert r["black_pct"] == 100.0
    assert r["suggested_offset_stops"] is None
    assert "median luminance" in r["offset_note"]
    json.dumps(r)


def test_exposure_skips_and_counts_nonfinite_pixels():
    img = flat(h=4, w=4, value=0.18)
    img[0, 0, 1] = np.nan
    img[1, 1, 0] = np.inf
    r = exposure(img)
    assert r["nonfinite_pixels"] == 2
    assert r["pixels_measured"] == 14
    assert r["mean_luminance"] == pytest.approx(0.18, abs=1e-6)
    assert r["clipped_pct"] == 0.0


@pytest.mark.parametrize("shape", [(8, 8), (8, 8, 4), (0, 8, 3)])
def test_exposure_rejects_non_rgb_arrays(shape):
    with pytest.raises(CVInputError):
        exposure(np.zeros(shape, dtype=np.float32))


def test_exposure_writes_histogram_png(oiio, tmp_path):
    out = tmp_path / "sub" / "hist.png"
    img = flat(value=0.18)
    img[:10] = 4.0
    r = exposure(img, histogram_path=out)
    assert r["histogram_path"] == str(out.resolve())
    inp = oiio.ImageInput.open(str(out))
    assert inp is not None, oiio.geterror()
    spec = inp.spec()
    png = inp.read_image(0, 0, 0, spec.nchannels, "uint8")
    inp.close()
    assert (spec.width, spec.height, spec.nchannels) == (640, 200, 3)
    png = np.asarray(png).reshape(200, 640, 3)
    # Bars were drawn (light grey), and the target line (green) runs full height.
    assert int((png == 200).all(axis=2).sum()) > 0
    assert int((png == (80, 200, 80)).all(axis=2).sum()) == 200
    json.dumps(r)


# --------------------------------------------------------------------------
# Package shape: no hou, and no heavy import at module level
# --------------------------------------------------------------------------


def test_package_imports_no_hou_and_defers_heavy_deps():
    pkg = pathlib.Path(scv.__file__).parent
    files = sorted(pkg.glob("*.py"))
    assert {f.name for f in files} == {"__init__.py", "deps.py", "reader.py", "exposure_stats.py"}
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        everywhere = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                everywhere |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                everywhere.add(node.module.split(".")[0])
        assert "hou" not in everywhere, f.name
        top = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                top.add(node.module.split(".")[0])
        assert not top & {"numpy", "cv2", "OpenImageIO"}, (f.name, top)
        # Blueprint P5 is structural: no cv2 by any route, importlib included.
        assert "cv2" not in everywhere, f.name
        literals = {
            n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        assert "cv2" not in literals, f"{f.name} names cv2 as a string: an indirect import?"


def test_submodules_are_not_shadowed_by_the_functions():
    import importlib

    assert callable(scv.exposure)
    assert importlib.import_module("synapse.cv.exposure_stats").exposure is scv.exposure
    assert not hasattr(scv, "fireflies")


# --------------------------------------------------------------------------
# Pins from the review of 65b02294 (nits)
# --------------------------------------------------------------------------


def test_exposure_offset_ignores_a_few_hot_pixels():
    img = flat(value=0.18)
    for x, y in [(1, 1), (10, 20), (40, 30), (63, 47)]:
        img[y, x] = 1000.0
    r = exposure(img)
    assert r["mean_luminance"] > 1.0  # the hot pixels do move the mean
    assert r["suggested_offset_stops"] == pytest.approx(0.0, abs=1e-5)


def test_exposure_black_threshold_is_inclusive():
    img = flat(h=8, w=8, value=0.18)
    img[2, 3] = (0.0004, 0.0007, 0.0002)
    thr = float(scv.luminance(img)[2, 3])  # exactly that pixel's luminance
    assert exposure(img, black_threshold=thr)["black_pct"] == pytest.approx(100.0 / 64)
    below = float(np.nextafter(np.float32(thr), np.float32(0.0)))
    assert exposure(img, black_threshold=below)["black_pct"] == 0.0
