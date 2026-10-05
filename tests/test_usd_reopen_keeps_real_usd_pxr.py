"""A store reopened in the same process keeps real USD. Runs under hython only.

``rebind_owner`` opens the target store, closes it, and opens it again to
verify what it carried. Before the root layer was released on close, that
second open could not create ``.moneta/usd/cortex_root.usda``, and the store
the session went on to use ran without USD sublayers. The live log shows it on
2026-10-04, on each launch that had the pane docked before a scene was opened:
"Moneta init with use_real_usd=True failed ... A layer already exists".

Reproduce: ``hython`` with ``$MONETA_SRC`` set, then ``pytest`` on this file.
"""
import logging

import pytest

pytest.importorskip("pxr")

from pxr import Sdf  # noqa: E402

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)

FALLBACK = "use_real_usd=True failed"


def _open(directory):
    return MonetaBackedStore.from_storage_dir(directory, embedder=HashEmbedder())


def _root_layer_id(directory):
    return (directory / ".moneta" / "usd" / "cortex_root.usda").as_posix()


def _real_usd(store):
    handle = store._handle
    return handle.config.use_real_usd and type(handle.authoring_target).__name__ == "UsdTarget"


def test_close_unregisters_the_root_layer(tmp_path):
    store = _open(tmp_path)
    try:
        assert _real_usd(store), "the first open in a process must get real USD"
        assert Sdf.Layer.Find(_root_layer_id(tmp_path)) is not None
    finally:
        store.close()
    assert Sdf.Layer.Find(_root_layer_id(tmp_path)) is None


def test_a_reopen_in_the_same_process_keeps_real_usd(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="synapse.memory.moneta_store")
    kept = []
    for _ in range(3):
        store = _open(tmp_path)
        kept.append(_real_usd(store))
        store.close()
    assert kept == [True, True, True]
    assert FALLBACK not in caplog.text


def test_a_rebind_keeps_real_usd(tmp_path, monkeypatch, caplog):
    """The path the live session takes: open the target, close it, reopen it."""
    from synapse.host import memory_lifecycle as lifecycle
    from synapse.memory import store as module
    import synapse.session.tracker as tracker

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    monkeypatch.setattr(module.SynapseMemory, "_make_store",
                        lambda self, directory: _open(directory))
    monkeypatch.setattr(tracker, "_bridge", None)
    old = module.SynapseMemory(project_path=str(tmp_path / "untitled"))
    monkeypatch.setattr(module, "_global_synapse", old)
    caplog.set_level(logging.WARNING, logger="synapse.memory.moneta_store")

    result = lifecycle.rebind_owner(tmp_path / "show")
    rebound = module._global_synapse
    try:
        assert result["status"] == "REBOUND"
        assert rebound is not old
        assert _real_usd(rebound.store), "the verified reopen fell back from real USD"
        assert FALLBACK not in caplog.text
    finally:
        rebound.store.close()
