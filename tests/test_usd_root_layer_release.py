"""Closing a Moneta-backed store lets go of the engine target's root layer.

Moneta's real USD target keeps ``_root_layer`` after ``close()``, and ``atexit``
keeps every store built by ``from_storage_dir`` alive until the process ends.
So ``.moneta/usd/cortex_root.usda`` stayed registered with USD, a second open of
the same directory could not create it, and that store came back without USD
sublayers. ``rebind_owner`` makes exactly that second open to verify a rebind.

These tests pin the release with inert handles, so they run without Moneta and
without USD. ``tests/test_usd_reopen_keeps_real_usd_pxr.py`` checks the same
thing against real USD, under hython.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402


def _store(target, close=None):
    calls = []

    def default_close():
        calls.append(("handle.close", getattr(target, "_root_layer", "absent")))

    handle = SimpleNamespace(authoring_target=target, durability=None,
                             close=close or default_close)
    return MonetaBackedStore(handle, HashEmbedder(dim=8)), calls


def test_close_releases_the_targets_root_layer():
    layer = object()
    target = SimpleNamespace(_root_layer=layer)
    store, calls = _store(target)
    store.close()
    assert target._root_layer is None
    # The handle closed first, while the target still held its layer.
    assert calls == [("handle.close", layer)]


def test_root_layer_is_released_when_the_handle_close_raises():
    target = SimpleNamespace(_root_layer=object())

    def broken():
        raise OSError("the snapshot thread did not stop")

    store, _ = _store(target, close=broken)
    with pytest.raises(OSError):
        store.close()
    assert target._root_layer is None


def test_a_target_without_a_root_layer_is_left_alone():
    target = SimpleNamespace(log_path=None)  # the mock target has no root layer
    store, _ = _store(target)
    store.close()
    assert not hasattr(target, "_root_layer")


def test_a_handle_without_a_target_closes_cleanly():
    closed = []
    handle = SimpleNamespace(durability=None, close=lambda: closed.append(True))
    MonetaBackedStore(handle, HashEmbedder(dim=8)).close()
    assert closed == [True]


def test_a_second_close_does_nothing():
    target = SimpleNamespace(_root_layer=object())
    store, calls = _store(target)
    store.close()
    target._root_layer = "held by a later owner"
    store.close()
    assert target._root_layer == "held by a later owner"
    assert len(calls) == 1
