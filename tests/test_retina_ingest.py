"""RETINA ingest — OIIO EXR read tests (need OpenImageIO + numpy).

The ingest OIIO leg reads real EXR pixels, so it can only run where OIIO is
installed — the worker venv, or a hython-seeded venv (Houdini ships OIIO). It
SKIPS in stock CI and on a dev interpreter without OIIO, so ``pytest tests/``
stays green everywhere. The cv2-free parts of ingest (the protected-$OCIO report,
the availability honesty) are pinned below without OIIO where possible.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

_HAS_OIIO = importlib.util.find_spec("OpenImageIO") is not None
_HAS_NUMPY = importlib.util.find_spec("numpy") is not None


# --- these run everywhere (no OIIO needed) --------------------------------

def test_ocio_is_read_never_set(monkeypatch):
    """The worker READS $OCIO; it must never set/clobber it (blueprint §3
    protected-env pattern)."""
    from retina import ingest

    monkeypatch.setenv("OCIO", "/studio/config.ocio")
    assert ingest.ocio_config() == "/studio/config.ocio"
    env = ingest.color_env()
    assert env["ocio_set"] is True
    assert env["ocio_config"] == "/studio/config.ocio"
    assert env["color_managed"] is True
    # calling the report did not mutate the env
    assert os.environ["OCIO"] == "/studio/config.ocio"


def test_color_env_honest_when_ocio_absent(monkeypatch):
    from retina import ingest

    monkeypatch.delenv("OCIO", raising=False)
    env = ingest.color_env()
    assert env["ocio_set"] is False
    assert env["ocio_config"] is None
    assert env["color_managed"] is False


def test_read_without_oiio_raises_honestly():
    """When OIIO is absent, a read raises IngestUnavailable — the honest 'cannot
    run' signal, never a silent empty array."""
    from retina import ingest

    if ingest.oiio_available():
        pytest.skip("OIIO present — the honest-unavailable path is not reachable")
    with pytest.raises(ingest.IngestUnavailable):
        ingest.read_subimage("nonexistent.exr", 0)


# --- these need OIIO -------------------------------------------------------

oiio_only = pytest.mark.skipif(
    not (_HAS_OIIO and _HAS_NUMPY),
    reason="OpenImageIO + numpy not installed (RETINA worker venv only)",
)


@oiio_only
def test_read_beauty_returns_linear_float32_topdown(tmp_path):
    import numpy as np

    from retina import ingest
    from retina.tests.fixtures import img_synth

    beauty = img_synth.gradient_plane(h=32, w=48, c=3)
    ids = img_synth.id_plane(h=32, w=48, regions=[(7, (8, 16, 8, 16))])
    path = str(tmp_path / "frame.0001.exr")
    img_synth.write_multipart_exr(path, beauty, ids)

    got = ingest.read_beauty(path)
    assert got.dtype == np.float32
    assert got.shape[0] == 32 and got.shape[1] == 48  # (H, W, C) top-down
    # gradient increases left->right in the top row (orientation preserved)
    assert got[0, -1, 0] > got[0, 0, 0]


@oiio_only
def test_read_id_plane_untransformed_and_located_from_header(tmp_path):
    import numpy as np

    from retina import ingest
    from retina.tests.fixtures import img_synth

    beauty = img_synth.gradient_plane(h=24, w=24, c=3)
    ids = img_synth.id_plane(h=24, w=24, regions=[(7, (4, 12, 4, 12))])
    path = str(tmp_path / "frame.0002.exr")
    img_synth.write_multipart_exr(path, beauty, ids)

    # header locates the ID subimage (no hardcoded index)
    assert ingest.find_id_subimage(path) is not None
    plane = ingest.read_id_plane(path)
    assert plane.ndim == 2
    # ID values survive as exact integers (Raw colorspace — never colour-transformed)
    assert int(round(float(plane[8, 8]))) == 7
    assert int(round(float(plane[0, 0]))) == 0


@oiio_only
def test_read_id_plane_raises_when_no_id_aov(tmp_path):
    from retina import ingest
    from retina.tests.fixtures import img_synth

    beauty = img_synth.gradient_plane(h=16, w=16, c=3)
    path = str(tmp_path / "beauty_only.0001.exr")
    img_synth.write_multipart_exr(path, beauty, None)  # no ID part

    with pytest.raises(ingest.IngestError):
        ingest.read_id_plane(path)
