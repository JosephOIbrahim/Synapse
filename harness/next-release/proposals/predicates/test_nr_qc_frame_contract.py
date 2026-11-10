"""Closure predicate for NR-QC-FRAME-CONTRACT (render-qc amendment, owner ruling QC-Q1).

Done when the worker tree carries its own frame reader and the firefly scan names
what it measured:

* ``retina/frame_reader.py`` computes the data-window origin relative to the display
  window from a spec-like object, and selects R, G, B by name from a channel list,
  dropping alpha and refusing a part without RGB with a ValueError that says why;
* a 4-channel part whose data window does not start at the frame corner comes out as
  RGB, and fireflies found in it carry frame positions;
* ``fireflies()`` results name ``luminance_basis`` and ``reader``;
* ``retina.firefly_scan.firefly_check`` turns a result into a ``make_check`` record
  whose ``pass`` is None for an inconclusive result, True for a clean frame and False
  for a finding.

Red when written (b856fafb): ``retina/frame_reader.py`` and ``firefly_check`` do not
exist, so every test below fails with ModuleNotFoundError / ImportError.

Behavioural, stock Python. The pure tests need nothing beyond the standard library;
the end-to-end test needs numpy and cv2 (skipped, with a realness check, where they
are absent). It never needs OpenImageIO, never launches Houdini, touches a GPU or
uses the network.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _repo_root() -> Path:
    """Find the repository root from the working directory, never from this file's
    location, so the predicate keeps working wherever it is moved (review G1)."""
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / ".git").exists() and (p / "harness" / "next-release" / "graph.json").is_file():
            return p
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    raise AssertionError("repository root not found: run this predicate from inside the SYNAPSE checkout")


ROOT = _repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _spec(**kw):
    base = dict(x=0, y=0, width=32, height=24, full_x=0, full_y=0, full_width=32,
                full_height=24, nchannels=4, channelnames=("R", "G", "B", "A"), format="half")
    base.update(kw)
    return SimpleNamespace(**base)


def _frame_reader():
    return importlib.import_module("retina.frame_reader")


def _firefly_check():
    return importlib.import_module("retina.firefly_scan").firefly_check


def test_origin_is_data_window_minus_display_window():
    fr = _frame_reader()
    assert fr.origin_from_spec(_spec(x=130, y=95, full_x=30, full_y=45)) == [100, 50]


def test_rgba_is_reduced_to_rgb_by_name():
    fr = _frame_reader()
    idx, used, dropped = fr.select_rgb(["A", "B", "G", "R"])
    assert idx == [3, 2, 1] and used == ["R", "G", "B"] and dropped == ["A"]
    idx, used, dropped = fr.select_rgb(["C.A", "C.B", "C.G", "C.R"])
    assert used == ["C.R", "C.G", "C.B"] and dropped == ["C.A"]


def test_part_without_rgb_is_refused_with_a_reason():
    fr = _frame_reader()
    with pytest.raises(ValueError, match="no R, G and B"):
        fr.select_rgb(["primid.id"])


def test_check_is_tri_state():
    check = _firefly_check()
    common = {"threshold_sigma": 6.0, "origin": None, "luminance_basis": "rec709_weights",
              "reader": None, "mask_path": None, "fireflies": [], "pixel_count": None}
    inconclusive = check(dict(common, inconclusive=True, note="too few lit pixels",
                              count=None, sigma=None, worst=None))
    assert inconclusive["pass"] is None
    clean = check(dict(common, inconclusive=False, note=None, count=0, sigma=0.01, worst=None))
    assert clean["pass"] is True
    worst = {"x": 7, "y": 5, "frame_x": 107, "frame_y": 55}
    found = check(dict(common, inconclusive=False, note=None, count=1, sigma=0.01,
                       worst=worst, origin=[100, 50]))
    assert found["pass"] is False
    assert found["frame_position"] == [107, 55]
    assert found["luminance_basis"] == "rec709_weights"
    assert "reader" in found


def test_windowed_rgba_part_reports_frame_positions():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    for mod in (np, cv2):
        if not isinstance(getattr(mod, "__version__", None), str):
            pytest.skip(f"{mod.__name__} in sys.modules is not the real package")
    fr = _frame_reader()
    from retina.firefly_scan import fireflies

    raw = np.full((24, 32, 4), 0.18, dtype=np.float32)
    raw[..., 3] = 1.0
    raw[5, 7, :3] = 40.0
    rgb, info = fr.pixels_to_rgb(_spec(x=130, y=95, full_x=30, full_y=45), raw)
    assert rgb.shape == (24, 32, 3)
    assert info["dropped"] == ["A"]
    r = fireflies(rgb, origin=info["origin"], reader=info["reader"])
    assert r["luminance_basis"] == "rec709_weights"
    assert r["reader"] == info["reader"] is not None
    assert r["count"] == 1
    assert (r["fireflies"][0]["frame_x"], r["fireflies"][0]["frame_y"]) == (107, 55)
