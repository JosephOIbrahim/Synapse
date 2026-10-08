"""retina.firefly_scan: the local noise model (re-review of 8490b80b, FIX_FIRST).

At 8490b80b noise was one MAD per brightness stop. A smooth noise-free
gradient backdrop at the object's stop is not *flat* (no 3x3 neighbourhood is
one exact value) but its residual is 0, so it filled that stop's MAD with
zeros: sigma fell to the 1e-6 floor, object noise flooded the mask and every
planted firefly was lost (the reviewer's attack3 grid: missed 25 of 25 at
every cover up to 0.45). A firefly on the gradient itself was refused as
"attached", because its neighbours sit one gradient step above its median.

Guards like tests/test_retina_fireflies.py: numpy and cv2 must be the real
packages, and ``retina.firefly_scan`` is imported unguarded.
"""

import json

import pytest

np = pytest.importorskip("numpy")
if not isinstance(getattr(np, "__version__", None), str):
    pytest.skip("numpy in sys.modules is not the real package", allow_module_level=True)

from retina.firefly_scan import fireflies  # noqa: E402  (unguarded on purpose)


@pytest.fixture
def cv2():
    mod = pytest.importorskip("cv2")
    if not isinstance(getattr(mod, "__version__", None), str):
        pytest.skip("cv2 in sys.modules is not the real package")
    return mod


H, W = 96, 128


def rgb(lum):
    return np.repeat(np.asarray(lum, dtype=np.float32)[:, :, None], 3, axis=2)


def backdrop(kind):
    yy, xx = np.mgrid[0:H, 0:W]
    if kind == "horizontal .13-.24":  # all of it in stop -3, the object's stop
        return np.broadcast_to(np.linspace(0.13, 0.24, W, dtype=np.float32), (H, W)).copy()
    if kind == "vertical .14-.22":
        return np.broadcast_to(np.linspace(0.14, 0.22, H, dtype=np.float32)[:, None], (H, W)).copy()
    if kind == "radial .10-.25":
        r = np.hypot((xx - W / 2) / W, (yy - H / 2) / H)
        return (0.25 - 0.15 * r / r.max()).astype(np.float32)
    raise ValueError(kind)


def object_on_gradient(kind, cover, seed):
    """Noisy 0.18 +- 0.01 ellipse, ``cover`` of the frame, on a noise-free gradient."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    s = np.sqrt(cover * H * W / np.pi / (W / H))
    obj = ((xx - W // 2) ** 2 / (s * W / H) ** 2 + (yy - H // 2) ** 2 / s**2) <= 1
    lum = backdrop(kind)
    lum[obj] = 0.18 + rng.normal(0.0, 0.01, int(obj.sum()))
    return rgb(lum), obj


ON = [(64, 48), (57, 51), (70, 44)]  # on the object
OFF = [(3, 3), (124, 92)]  # on the gradient


@pytest.mark.parametrize("kind", ["horizontal .13-.24", "vertical .14-.22", "radial .10-.25"])
@pytest.mark.parametrize("cover", [0.1, 0.3, 0.6])
def test_fireflies_on_object_over_smooth_gradient(cv2, kind, cover):
    # 8490b80b: every planted firefly lost (sigma 1e-6, object noise flagged)
    # for covers up to 0.45; at 0.6 the plants were found among ~45 false
    # fireflies per frame.
    img, obj = object_on_gradient(kind, cover, seed=7)
    assert all(obj[y, x] for x, y in ON) and not any(obj[y, x] for x, y in OFF)
    for x, y in ON + OFF:
        img[y, x] = 20.0
    r = fireflies(img)
    assert r["inconclusive"] is False
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(ON + OFF)
    assert r["count"] == 5
    assert r["large_blobs_ignored"] == 0
    # A linear gradient is smooth (residual 0) and leaves the object's stop
    # its own noise. A radial one is curved: its small nonzero residuals
    # still pull the stop's reported MAD down (to 0.0024 at cover 0.1), but
    # detection uses the local sigma, which the object's window dominates.
    if not kind.startswith("radial"):
        by_stop = {lv["stop"]: lv for lv in r["noise"]["levels"]}
        assert by_stop[-3]["sigma"] == pytest.approx(0.01, rel=0.35)
    json.dumps(r)


def test_fireflies_on_smooth_gradient_over_seeds(cv2):
    # Same-stop gradient, 30% cover, 20 seeds: no seed may lose a plant or
    # add a false firefly.
    wrong = []
    for seed in range(20):
        img, _ = object_on_gradient("horizontal .13-.24", 0.3, seed)
        for x, y in ON + OFF:
            img[y, x] = 20.0
        r = fireflies(img)
        got = {(f["x"], f["y"]) for f in r["fireflies"]}
        if r["inconclusive"] or got != set(ON + OFF):
            wrong.append((seed, r["count"], sorted(got - set(ON + OFF))))
    assert wrong == []


def test_fireflies_on_a_bare_smooth_gradient(cv2):
    # No object at all: the gradient is the whole frame, its noise is 0, and
    # each plant's ring sits one gradient step above the plant's median. At
    # 8490b80b all three were "attached" and the count was 0.
    img = rgb(backdrop("horizontal .13-.24"))
    plants = [(20, 10), (64, 48), (110, 80)]
    for x, y in plants:
        img[y, x] = 2.0
    r = fireflies(img)
    assert r["inconclusive"] is False
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(plants)
    assert r["attached_blobs_ignored"] == 0 and r["large_blobs_ignored"] == 0


def test_fireflies_bright_square_on_gradient_is_still_attached(cv2):
    # The gradient allowance in the isolation ring is a rise of the local
    # median on BOTH sides of the peak. A highlight's corner rises on one
    # side only, so its four corners stay attached, as on a flat backdrop
    # (test_fireflies_ignore_a_bright_square).
    img = rgb(backdrop("horizontal .13-.24"))
    img[30:42, 50:62] = 50.0
    r = fireflies(img)
    assert r["count"] == 0
    assert r["attached_blobs_ignored"] == 4


def test_fireflies_noise_is_judged_locally_within_a_stop(cv2):
    # Two surfaces at the same level (stop -3) with different noise: 0.003 on
    # the left, 0.018 on the right (a diffuse and a glossy surface). One MAD
    # for the stop sits between the two: at 8490b80b it missed the plants on
    # the quiet side and flagged the noisy side's noise (153 fireflies for 5
    # plants). Judged locally, only the plants are found, each about 9 of
    # ITS OWN side's sigmas (one clipping pass instead of two reads the
    # noisy side's sigma low: about 10.8 there). Plants sit more than a
    # window's half-width (15 px) from the seam.
    rng = np.random.default_rng(23)
    xx = np.mgrid[0:H, 0:W][1]
    noise = np.where(xx < W // 2, 0.003, 0.018)
    lum = (0.18 + noise * rng.normal(0.0, 1.0, (H, W))).astype(np.float32)
    img = rgb(lum)
    plants = [(12, 20), (20, 70), (30, 45), (110, 30), (100, 75)]
    for x, y in plants:
        img[y, x] = np.float32(np.median(lum[y - 2 : y + 3, x - 2 : x + 3]) + 9 * noise[y, x])
    r = fireflies(img)
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(plants)
    for f in r["fireflies"]:
        assert f["sigmas"] == pytest.approx(9.0, rel=0.1), f


def test_fireflies_object_on_a_gradient_across_stops(cv2):
    # A 0.05 -> 1.0 gradient over 480 px spans stops -5 to 0; only stop -3
    # holds the object's noise. At 8490b80b the plants on the gradient were
    # "attached" (all 10 lost over the reviewer's 5 seeds). Backdrop pixels
    # on the silhouette, whose 5x5 median the darker object pulls down by
    # one gradient step (0.002), sit in a stop with no noise of its own; the
    # half-float floor on the detection sigma (_SMOOTH_REL x the level) is
    # what keeps them out of the count.
    rng = np.random.default_rng(7)
    h, w = 270, 480
    yy, xx = np.mgrid[0:h, 0:w]
    s = np.sqrt(0.3 * h * w / np.pi / (w / h))
    obj = ((xx - w // 2) ** 2 / (s * w / h) ** 2 + (yy - h // 2) ** 2 / s**2) <= 1
    lum = np.broadcast_to(np.linspace(0.05, 1.0, w, dtype=np.float32), (h, w)).copy()
    lum[obj] = 0.18 + rng.normal(0.0, 0.01, int(obj.sum()))
    img = rgb(lum)
    on = [(240, 135), (233, 138), (246, 131)]
    off = [(3, 3), (476, 266)]
    assert all(obj[y, x] for x, y in on) and not any(obj[y, x] for x, y in off)
    for x, y in on + off:
        img[y, x] = 20.0
    r = fireflies(img)
    assert {(f["x"], f["y"]) for f in r["fireflies"]} == set(on + off)
    assert r["count"] == 5


def test_fireflies_stop_with_100_to_300_nonflat_pixels_uses_them(cv2):
    # Pins the non-flat fallback threshold of a stop at _MIN_NOISE_PIXELS
    # (100): a 14x14 noisy 0.18 square on a constant 0.18 backdrop has 256
    # non-flat pixels (the square and its one-pixel ring), so the stop's MAD
    # is taken from them. A 300 mutant (survived every test at 8490b80b)
    # falls back to the whole stop, whose MAD is 0, and reports 1e-6.
    rng = np.random.default_rng(29)
    lum = np.full((48, 64), 0.18, dtype=np.float32)
    lum[17:31, 25:39] = 0.18 + rng.normal(0.0, 0.01, (14, 14))
    img = rgb(lum)
    img[24, 32] = 20.0
    r = fireflies(img)
    (level,) = r["noise"]["levels"]
    assert level["stop"] == -3 and level["borrowed_from"] is None
    assert level["sigma"] == pytest.approx(0.01, rel=0.35)
    assert r["sigma"] == level["sigma"]
    assert [(f["x"], f["y"]) for f in r["fireflies"]] == [(32, 24)]
