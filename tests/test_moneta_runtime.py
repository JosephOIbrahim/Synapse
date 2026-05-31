"""Mile 3 — pxr/CI path: guarded Moneta import + ephemeral round-trip.

These tests run for real wherever Moneta is importable (locally with
``$MONETA_SRC`` set, or with the package installed) and SKIP cleanly where it
isn't (e.g. stock GitHub CI). The point they pin: the ephemeral /
``MockUsdTarget`` path round-trips a deposit/query with **no OpenUSD** loaded
(harness AP9), and the handle's single-owner URI lock releases on close.
"""

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PYDIR = _ROOT / "python"
sys.path.insert(0, str(_PYDIR))

from synapse.memory import moneta_runtime as mr  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)


def test_guard_reports_available_without_error():
    assert mr.moneta_available() is True
    assert mr.import_error() is None


def test_ephemeral_round_trip():
    with mr.make_ephemeral(embedding_dim=8) as m:
        eid = m.deposit("synapse remembers this", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        hits = m.query([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], limit=5)
        assert len(hits) == 1
        assert hits[0].payload == "synapse remembers this"  # byte-for-byte round-trip
        assert hits[0].entity_id == eid


def test_ephemeral_path_is_pxr_free():
    # Pin AP9 in a CLEAN subprocess: an in-process `"pxr" not in sys.modules`
    # check is unreliable because sibling tests (evolution/Charizard) import pxr
    # and pollute the shared interpreter. A fresh interpreter proves the
    # ephemeral / MockUsdTarget path imports no OpenUSD by itself.
    driver = (
        "import sys;"
        f"sys.path.insert(0, {str(_PYDIR)!r});"
        "from synapse.memory import moneta_runtime as mr;"
        "assert mr.moneta_available();"
        "m = mr.make_ephemeral(embedding_dim=8);"
        "m.deposit('x', [0.1]*8);"
        "assert m.query([0.1]*8, limit=3)[0].payload == 'x';"
        "m.close();"
        "assert 'pxr' not in sys.modules, 'pxr loaded by ephemeral path';"
        "print('PXR_FREE_OK')"
    )
    out = subprocess.check_output([sys.executable, "-c", driver], text=True)
    assert "PXR_FREE_OK" in out


def test_empty_query_returns_empty_not_error():
    with mr.make_ephemeral(embedding_dim=8) as m:
        assert m.query([0.0] * 8, limit=5) == []  # well-defined on an empty store


def test_uri_lock_releases_on_close():
    # Two sequential ephemeral handles must each acquire + release cleanly;
    # a leaked URI lock would surface as MonetaResourceLockedError.
    with mr.make_ephemeral(embedding_dim=4) as m1:
        m1.deposit("first", [1.0, 0.0, 0.0, 0.0])
    with mr.make_ephemeral(embedding_dim=4) as m2:
        m2.deposit("second", [0.0, 1.0, 0.0, 0.0])
        assert m2.ecs.n == 1  # fresh handle, not the previous one's state
