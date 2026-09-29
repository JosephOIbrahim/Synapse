"""Item 19: the memory status report names the embedder backend that is live.

The SemanticEmbedder id is constant (minilm-l6-v2-d384) whether the ONNX
model or the hash fallback is serving, so the id alone cannot tell a caller
which one it is getting. ``backend`` can.
"""
from synapse.memory.embedding import HashEmbedder, SemanticEmbedder
from synapse.memory import store as store_mod


def test_missing_model_reports_hash_and_keeps_id(tmp_path):
    emb = SemanticEmbedder(model_path=str(tmp_path / "nope"))
    assert emb.backend == "unloaded"          # a read never loads the model
    assert emb._session is None
    assert len(emb.embed("hello")) == emb.dim
    assert emb.backend == "hash"
    assert emb.id == "minilm-l6-v2-d384"


def test_loaded_session_reports_onnx(tmp_path):
    emb = SemanticEmbedder(model_path=str(tmp_path / "nope"))
    emb._session = object()  # a loaded session means the model is serving
    assert emb.backend == "onnx"


def test_hash_embedder_reports_hash():
    assert HashEmbedder().backend == "hash"


def test_docstring_no_longer_claims_id_detects_reembed():
    doc = SemanticEmbedder.__doc__
    assert "cannot be used to detect" in doc


def test_status_report_carries_backend_key(tmp_path, monkeypatch):
    emb = SemanticEmbedder(model_path=str(tmp_path / "nope"))

    class _Store:
        embedder_id = emb.id
        _embedder = emb

        def count(self):
            return 0

    emb.embed("warm")  # force the fallback so the report has something to say
    rep = store_mod.backend_health(_Store())
    assert rep["embedder_backend"] == "hash"
    assert rep["embedder_id"] == "minilm-l6-v2-d384"
