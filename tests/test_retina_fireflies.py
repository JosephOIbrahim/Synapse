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


# --------------------------------------------------------------------------
# Noise estimate (review of 65b02294, F1): black background, degenerate input
# --------------------------------------------------------------------------


def object_on_black(h=96, w=128, cover=0.45, noise=0.01, seed=11):
    """Noisy 0.18 ellipse on an exactly black frame, ``cover`` of the area."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    a = np.sqrt(cover * h * w / np.pi * (w / h))
    b = a * h / w
    obj = ((xx - w / 2) ** 2 / a**2 + (yy - h / 2) ** 2 / b**2) <= 1
    lum = np.zeros((h, w), dtype=np.float32)
    lum[obj] = 0.18 + rng.normal(0.0, noise, int(obj.sum()))
    return np.repeat(lum[:, :, None], 3, axis=2), obj


def test_fireflies_on_object_over_black_background(cv2):
    # More than half the frame is exactly black, so a whole-frame MAD is 0 and
    # the threshold collapses onto the object noise (found 0/3 at 65b02294).
    img, obj = object_on_black()
    assert obj.mean() < 0.5
    on = [(64, 48), (50, 40), (80, 55)]
    off = [(3, 3), (124, 92)]
    assert all(obj[y, x] for x, y in on) and not any(obj[y, x] for x, y in off)
    for x, y in on + off:
        img[y, x] = 20.0
    r = fireflies(img)
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(on + off)
    assert r["inconclusive"] is False
    assert r["count"] == 5
    assert r["large_blobs_ignored"] == 0
    assert r["sigma"] == pytest.approx(0.01, rel=0.35)
    assert r["noise"]["black_sigma"] == pytest.approx(1e-6)
    json.dumps(r)


def test_fireflies_too_few_lit_pixels_is_inconclusive(cv2, tmp_path):
    # A 6x6 noisy patch on black: 36 lit pixels cannot give a noise estimate,
    # so there is no count at all, not a count against a guessed sigma.
    rng = np.random.default_rng(3)
    img = np.zeros((64, 64, 3), dtype=np.float32)
    img[20:26, 20:26] = (0.18 + rng.normal(0, 0.01, (6, 6, 1))).astype(np.float32)
    img[22, 22] = 20.0
    out = tmp_path / "mask.png"
    r = fireflies(img, mask_path=out)
    assert r["inconclusive"] is True
    assert "cannot be estimated" in r["note"]
    assert r["count"] is None and r["pixel_count"] is None
    assert r["sigma"] is None and r["threshold"] is None
    assert r["worst"] is None and r["fireflies"] == []
    assert 0 < r["noise"]["lit_pixels"] < r["noise"]["min_pixels"]
    assert r["mask_path"] is None and not out.exists()
    json.dumps(r)


def test_fireflies_all_black_frame_is_judged_not_inconclusive(cv2):
    # Nothing lit at all: the black class is exactly noise-free, so a spike on
    # it is a confident firefly.
    img = np.zeros((48, 64, 3), dtype=np.float32)
    img[10, 10] = 5.0
    r = fireflies(img)
    assert r["inconclusive"] is False
    assert r["count"] == 1 and (r["worst"]["x"], r["worst"]["y"]) == (10, 10)
    assert r["noise"]["lit_pixels"] == 0


@pytest.mark.parametrize("level", [0.0, 0.18])
def test_fireflies_sigma_floor_ignores_sub_floor_bumps(cv2, level):
    # Pins the 1e-6 sigma floor (a 'no floor' mutant survived every test at
    # 65b02294): on an exactly flat frame the MAD is 0, and without the floor
    # a +1e-7 bump would be a firefly. Only the real spike may be.
    img = flat(value=level)
    for x, y in [(5, 5), (20, 30), (50, 10), (33, 40)]:
        img[y, x] += np.float32(1e-7)
    img[24, 32] = 20.0
    r = fireflies(img)
    assert r["count"] == 1
    assert (r["worst"]["x"], r["worst"]["y"]) == (32, 24)
    assert r["attached_blobs_ignored"] == 0 and r["large_blobs_ignored"] == 0


# --------------------------------------------------------------------------
# Noise per stop (review of 65b02294, F2): noise that grows with brightness
# --------------------------------------------------------------------------


def test_fireflies_noise_is_judged_per_stop(cv2):
    # 5% relative noise on a 0.05 half and a 5.0 half. One absolute sigma
    # (65b02294) flagged the bright half's noise: 220 false fireflies on a
    # 270x480 frame. Per stop, only the planted ones are found, each about
    # 12 of its own sigmas over its neighbourhood.
    rng = np.random.default_rng(5)
    h, w = 96, 128
    xx = np.mgrid[0:h, 0:w][1]
    base = np.where(xx < w // 2, 0.05, 5.0)
    lum = (base * (1 + rng.normal(0.0, 0.05, (h, w)))).astype(np.float32)
    img = np.repeat(lum[:, :, None], 3, axis=2)
    plants = {(20, 30): 0.05 * 1.6, (100, 60): 5.0 * 1.6}
    for (x, y), v in plants.items():
        img[y, x] = v
    r = fireflies(img)
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(plants)
    assert r["large_blobs_ignored"] == 0 and r["attached_blobs_ignored"] == 0
    by_stop = {lv["stop"]: lv for lv in r["noise"]["levels"]}
    assert by_stop[-5]["sigma"] == pytest.approx(0.05 * 0.05, rel=0.35)
    assert by_stop[2]["sigma"] == pytest.approx(5.0 * 0.05, rel=0.35)


def test_fireflies_sparse_stop_borrows_the_nearest(cv2):
    # The 10x10 square at 50.0 is under 100 pixels at stop 5, so it borrows
    # the sigma of stop -3 (0.18) and says so.
    img = flat()
    img[10:20, 20:30] = 50.0
    r = fireflies(img)
    by_stop = {lv["stop"]: lv for lv in r["noise"]["levels"]}
    assert by_stop[-3]["borrowed_from"] is None
    assert by_stop[5]["pixels"] < 100
    assert by_stop[5]["borrowed_from"] == -3
    assert by_stop[5]["sigma"] == by_stop[-3]["sigma"]


# --------------------------------------------------------------------------
# Pins from the review of 65b02294 (nits)
# --------------------------------------------------------------------------


def test_fireflies_diagonal_pair_is_one_blob(cv2):
    # 8-connected: two pixels touching only at a corner are one firefly.
    img = flat()
    img[10, 10] = 30.0
    img[11, 11] = 30.0
    r = fireflies(img)
    assert r["count"] == 1
    assert r["fireflies"][0]["area"] == 2
    assert r["pixel_count"] == 2


def test_fireflies_pixel_exactly_at_threshold_is_not_a_firefly(cv2):
    # Candidates need residual > threshold, strictly. On an all-black frame the
    # sigma is the 1e-6 floor, so the threshold is float32(6) * float32(1e-6);
    # find a grey value whose Rec.709 luminance is exactly that.
    from retina.firefly_scan import _luminance

    t = np.float32(6.0) * np.float32(1e-6)
    v = t
    for _ in range(200):
        lum = _luminance(np, np.full((1, 1, 3), v, dtype=np.float32))[0, 0]
        if lum == t:
            break
        v = np.nextafter(v, np.float32(1.0) if lum < t else np.float32(0.0), dtype=np.float32)
    else:
        pytest.skip("no float32 grey has a luminance exactly at the threshold")
    img = np.zeros((32, 32, 3), dtype=np.float32)
    img[10, 10] = v
    assert fireflies(img)["count"] == 0
    img[10, 10] = np.nextafter(v, np.float32(1.0), dtype=np.float32)
    assert fireflies(img)["count"] == 1


def test_fireflies_origin_adds_frame_positions(cv2):
    r = fireflies(planted(), origin=(10, 20))
    assert r["origin"] == [10, 20]
    assert [(f["x"], f["y"]) for f in r["fireflies"]] == [(63, 47), (10, 5), (40, 30)]
    assert [(f["frame_x"], f["frame_y"]) for f in r["fireflies"]] == [(73, 67), (20, 25), (50, 50)]
    assert (r["worst"]["frame_x"], r["worst"]["frame_y"]) == (73, 67)
    assert "frame_x" not in fireflies(planted())["fireflies"][0]
    assert fireflies(planted())["origin"] is None
    with pytest.raises(ValueError, match="origin"):
        fireflies(flat(), origin=(1,))
