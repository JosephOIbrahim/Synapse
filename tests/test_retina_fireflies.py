"""retina.firefly_scan on generated arrays (render QC Phase 1).

The firefly detector needs cv2, so it lives in the RETINA worker tree, not in
``python/synapse`` (blueprint P5, tests/test_retina_boundary.py). numpy and cv2
are guarded with importorskip AND a realness check (``__version__`` is a str),
so a MagicMock another test planted in sys.modules skips instead of passing.
``retina.firefly_scan`` itself is imported unguarded: on a tree without it these
tests must fail, not skip.
"""

import json
import sys
from unittest.mock import MagicMock

import pytest

np = pytest.importorskip("numpy")
if not isinstance(getattr(np, "__version__", None), str):
    pytest.skip("numpy in sys.modules is not the real package", allow_module_level=True)

from retina.firefly_scan import FirefliesUnavailable, fireflies  # noqa: E402  (unguarded on purpose)
from retina.t1 import T1Unavailable  # noqa: E402


@pytest.fixture
def cv2():
    mod = pytest.importorskip("cv2")
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip("cv2 in sys.modules is not the real package")
    return mod


def flat(h=48, w=64, value=0.18):
    return np.full((h, w, 3), value, dtype=np.float32)


def test_missing_cv2_raises_named_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", None)
    with pytest.raises(FirefliesUnavailable) as exc:
        fireflies(flat())
    assert isinstance(exc.value, T1Unavailable)
    assert "opencv-python-headless" in str(exc.value)


def test_fake_cv2_is_refused(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", MagicMock())
    with pytest.raises(FirefliesUnavailable, match="not the real package"):
        fireflies(flat())


def test_missing_numpy_raises_named_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)
    with pytest.raises(FirefliesUnavailable, match="numpy"):
        fireflies([[[0.18, 0.18, 0.18]]])


# --------------------------------------------------------------------------
# Fireflies
# --------------------------------------------------------------------------

PLANTED = [((10, 5), 50.0), ((40, 30), 20.0), ((63, 47), 100.0)]  # (x, y), value


def planted(img=None):
    img = flat() if img is None else img
    for (x, y), v in PLANTED:
        img[y, x] = v
    return img


def test_fireflies_planted_on_flat_grey(cv2):
    r = fireflies(planted())
    assert r["count"] == 3
    assert r["pixel_count"] == 3
    assert [(f["x"], f["y"]) for f in r["fireflies"]] == [(63, 47), (10, 5), (40, 30)]
    assert all(f["area"] == 1 for f in r["fireflies"])
    w = r["worst"]
    assert (w["x"], w["y"]) == (63, 47)
    assert w["rgb"] == [100.0, 100.0, 100.0]
    assert w["luminance"] == pytest.approx(100.0, rel=1e-6)
    assert r["large_blobs_ignored"] == 0
    assert r["attached_blobs_ignored"] == 0
    assert r["threshold_sigma"] == 6.0
    json.dumps(r)


def test_fireflies_on_seeded_noise(cv2):
    rng = np.random.default_rng(20261007)
    img = (0.18 + rng.normal(0.0, 0.01, size=(96, 128, 1))).astype(np.float32)
    img = np.repeat(img, 3, axis=2)
    spots = {(7, 3): 5.0, (100, 50): 3.0, (64, 90): 8.0, (127, 0): 4.0}
    for (x, y), v in spots.items():
        img[y, x] = v
    r = fireflies(img)
    assert r["count"] == 4
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(spots)
    assert (r["worst"]["x"], r["worst"]["y"]) == (64, 90)
    # The noise estimate is close to the planted noise, not inflated by the spots.
    assert r["sigma"] == pytest.approx(0.01, rel=0.35)


def test_fireflies_small_blobs_count_once(cv2):
    img = flat()
    img[10:12, 10:12] = 30.0  # 2x2
    img[30:33, 40:43] = 30.0  # 3x3
    img[31, 41] = 40.0  # its peak
    r = fireflies(img)
    assert r["count"] == 2
    by_area = sorted((f["area"], f["x"], f["y"]) for f in r["fireflies"])
    assert by_area[0][0] == 4
    assert by_area[1] == (9, 41, 31)
    assert r["pixel_count"] == 13


def test_fireflies_ignore_a_bright_square(cv2):
    img = flat()
    img[10:20, 20:30] = 50.0
    r = fireflies(img)
    assert r["count"] == 0
    assert r["worst"] is None
    # Each of the four sharp corners passes the 5x5 median as a 3-pixel blob;
    # the isolation ring sees the bright square and refuses all four.
    assert r["attached_blobs_ignored"] == 4
    assert r["large_blobs_ignored"] == 0


def test_fireflies_clean_frame_reports_none(cv2):
    r = fireflies(flat())
    assert r["count"] == 0
    assert r["pixel_count"] == 0
    assert r["worst"] is None
    assert r["fireflies"] == []


def test_fireflies_coloured_spike_found_by_luminance(cv2):
    img = flat()
    img[20, 20] = (60.0, 0.0, 0.0)
    r = fireflies(img)
    assert r["count"] == 1
    assert r["worst"]["rgb"] == [60.0, 0.0, 0.0]
    assert r["worst"]["luminance"] == pytest.approx(60.0 * 0.2126, rel=1e-5)


def test_fireflies_threshold_sigma_is_honoured(cv2):
    rng = np.random.default_rng(7)
    img = np.repeat((0.18 + rng.normal(0, 0.01, (64, 64, 1))).astype(np.float32), 3, axis=2)
    img[32, 32] = 0.18 + 0.01 * 15  # about 15 sigma over its neighbours
    assert fireflies(img, threshold_sigma=6.0)["count"] >= 1
    assert fireflies(img, threshold_sigma=40.0)["count"] == 0


def test_fireflies_writes_exact_mask(cv2, tmp_path):
    out = tmp_path / "mask.png"
    r = fireflies(planted(), mask_path=out)
    assert r["mask_path"] == str(out.resolve())
    mask = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    assert mask.shape == (48, 64) and mask.dtype == np.uint8
    ys, xs = np.nonzero(mask)
    assert set(zip(xs.tolist(), ys.tolist())) == {p for p, _ in PLANTED}
    assert set(np.unique(mask).tolist()) == {0, 255}


def test_fireflies_listing_is_capped(cv2):
    img = flat(h=64, w=64)
    for i in range(6):
        img[5 + 10 * i, 5] = 10.0 + i
    r = fireflies(img, max_listed=2)
    assert r["count"] == 6
    assert len(r["fireflies"]) == 2
    assert r["fireflies_truncated"] is True


def test_fireflies_nonfinite_is_counted_not_crashing(cv2):
    img = planted()
    img[0, 0, 0] = np.nan
    r = fireflies(img)
    assert r["nonfinite_pixels"] == 1
    assert r["count"] == 3


def test_fireflies_rejects_bad_parameters(cv2):
    with pytest.raises(ValueError):
        fireflies(flat(), threshold_sigma=0)
    with pytest.raises(ValueError):
        fireflies(flat(), max_blob_area=0)
    with pytest.raises(ValueError):
        fireflies(np.zeros((8, 8), dtype=np.float32))
