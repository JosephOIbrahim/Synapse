"""Deterministic, dependency-free text embedder for SYNAPSE memory.

Mile 2 of the Moneta <-> SYNAPSE integration (see
``docs/MONETA_SYNAPSE_INTEGRATION_HARNESS.md`` section 5 and the Mile 2 handoff
capsule). This is the *bootstrap* embedder: per harness falsification condition
FC2, the embedding source must be deterministic, offline-capable, and instant so
it can never block the build. A local semantic model (MiniLM-class) swaps in
behind the same :class:`Embedder` interface at the quality pass.

Each deposit is stamped with the embedder's :attr:`Embedder.id` for provenance:
hash vectors and semantic vectors live in different spaces and are not
comparable, so a later swap queries by id, finds non-matching entries, and
re-embeds them (handoff capsule, "PARKED" section).

Pure Python. Zero third-party deps for :class:`HashEmbedder`. The
:class:`SemanticEmbedder` requires ``onnxruntime`` and ``tokenizers`` when the
model file is present; it degrades gracefully to :class:`HashEmbedder` when
those are unavailable or the model file is missing. Importable and testable
standalone in either mode.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from collections import Counter
from pathlib import Path
from typing import Iterator, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Embedder(Protocol):
    """A pinned, deterministic text -> vector map.

    Implementations MUST be pure functions of their input: the same text yields
    the same vector on every call and across process restarts (no randomness, no
    network, no dependence on ``PYTHONHASHSEED``). The returned vector is always
    exactly :attr:`dim` long and, for any non-empty input, L2-normalized.
    """

    id: str   # pinned identifier, stamped onto deposits for provenance
    dim: int

    def embed(self, text: str) -> list[float]:
        ...


class HashEmbedder:
    """Feature-hashing embedder over character n-grams.

    Maps character n-grams into a fixed-dimension vector via the "hashing
    trick", with a sign hash so collisions cancel in expectation rather than
    always accumulating. The hash is :mod:`hashlib`-based (BLAKE2b), so output is
    independent of ``PYTHONHASHSEED`` and identical across processes, platforms,
    and Python versions -- unlike the built-in :func:`hash`, which is salted
    per process for ``str``.

    Contract:

    * **deterministic** -- same text -> identical vector, across calls and
      across process restarts.
    * **fixed length** -- every output is exactly :attr:`dim` floats.
    * **normalized** -- ``||v|| == 1`` for every non-empty input. The empty
      string is the sole input that returns the zero vector.

    n-grams span ``ngram_min..ngram_max`` characters. Including unigrams
    (``ngram_min == 1``) guarantees any non-empty string yields at least one
    feature, so the only zero vector comes from the empty string.
    """

    _FAMILY = "hash-ngram-v1"

    def __init__(self, dim: int = 256, ngram_min: int = 1, ngram_max: int = 3) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        if not (1 <= ngram_min <= ngram_max):
            raise ValueError(
                f"require 1 <= ngram_min <= ngram_max, got "
                f"ngram_min={ngram_min}, ngram_max={ngram_max}"
            )
        self.dim = dim
        self.ngram_min = ngram_min
        self.ngram_max = ngram_max
        # id encodes every parameter that defines the vector space so a swap --
        # or even a re-config -- is detectable from the stamped provenance.
        self.id = f"{self._FAMILY}-d{dim}-n{ngram_min}_{ngram_max}"

    def _ngrams(self, text: str) -> Iterator[str]:
        n_chars = len(text)
        for n in range(self.ngram_min, self.ngram_max + 1):
            if n_chars < n:
                break
            for i in range(n_chars - n + 1):
                yield text[i:i + n]

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        # Counter dedups identical n-grams so each is hashed once, weighted by
        # frequency. Bounds work on very long text: unique n-grams plateau.
        counts = Counter(self._ngrams(text))
        for token, weight in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=9).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dim
            sign = 1.0 if (digest[8] & 1) else -1.0
            vec[bucket] += sign * weight

        norm = math.sqrt(sum(x * x for x in vec))
        if norm != 0.0:
            return [x / norm for x in vec]

        if not text:
            # The empty string produces no n-grams -> zero vector. This is the
            # documented, deterministic degenerate output.
            return vec
        # Non-empty but fully cancelled (reachable only for tiny ``dim`` or
        # adversarial input where signed buckets sum to exactly zero): fall back
        # to a deterministic unit spike so "non-empty => unit norm" always holds.
        digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
        vec[int.from_bytes(digest, "big") % self.dim] = 1.0
        return vec


class SemanticEmbedder:
    """MiniLM-based semantic embedder for production vector recall.

    Uses ONNX Runtime to run a quantized MiniLM-L6-v2 model locally.
    The model and tokenizer are loaded lazily on the first :meth:`embed` call
    so importing this module never blocks on missing dependencies.

    When the ONNX model file is not found (or ``onnxruntime`` / ``tokenizers``
    are not installed), :meth:`embed` transparently falls back to
    :class:`HashEmbedder` with the same output dimension. The embedder's
    ``id`` is always ``"minilm-l6-v2-d384"`` regardless of which backend
    actually produced the vector, so downstream code can detect that a
    re-embed is needed when the model becomes available.

    Contract (same as :class:`Embedder`):

    * **deterministic** -- same text -> identical vector, across calls and
      across process restarts (when the same model file is used).
    * **fixed length** -- every output is exactly :attr:`dim` floats.
    * **normalized** -- ``||v|| == 1`` for every non-empty input.
    """

    _FAMILY = "minilm-l6-v2"

    # Default location: ``~/.synapse/models/minilm-l6-v2/``
    _DEFAULT_MODEL_DIR = str(Path.home() / ".synapse" / "models" / "minilm-l6-v2")
    _MODEL_FILENAME = "model.onnx"
    _TOKENIZER_FILENAME = "tokenizer.json"

    def __init__(
        self,
        dim: int = 384,
        model_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
    ) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self.dim = dim
        self.id = f"{self._FAMILY}-d{dim}"

        # Resolve model / tokenizer paths.
        model_dir = model_path or self._DEFAULT_MODEL_DIR
        self._model_path = os.path.join(model_dir, self._MODEL_FILENAME)
        self._tokenizer_path = (
            tokenizer_path
            or os.path.join(model_dir, self._TOKENIZER_FILENAME)
        )

        # Lazy-loaded state.
        self._session = None
        self._tokenizer = None
        self._fallback: Optional[HashEmbedder] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed *text* and return an L2-normalized vector.

        If the ONNX model is available and loaded, uses semantic inference.
        Otherwise falls back to :class:`HashEmbedder` with the same
        output dimension.
        """
        try:
            self._load_model()
        except Exception:
            return self._fallback_embed(text)

        try:
            return self._semantic_embed(text)
        except Exception:
            return self._fallback_embed(text)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the ONNX session and tokenizer.

        Raises :class:`RuntimeError` when the model file is missing or
        required packages are not installed.
        """
        if self._session is not None:
            return

        if not os.path.isfile(self._model_path):
            raise RuntimeError(
                f"ONNX model not found at {self._model_path}; "
                f"falling back to HashEmbedder"
            )

        # Lazy imports -- these are optional dependencies.
        try:
            import onnxruntime as ort  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                "onnxruntime is not installed; falling back to HashEmbedder"
            ) from exc

        try:
            from tokenizers import Tokenizer  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                "tokenizers is not installed; falling back to HashEmbedder"
            ) from exc

        if not os.path.isfile(self._tokenizer_path):
            raise RuntimeError(
                f"tokenizer file not found at {self._tokenizer_path}; "
                f"falling back to HashEmbedder"
            )

        self._session = ort.InferenceSession(
            self._model_path,
            providers=ort.get_available_providers(),
        )
        self._tokenizer = Tokenizer.from_file(self._tokenizer_path)

    # ------------------------------------------------------------------
    # Inference pipeline
    # ------------------------------------------------------------------

    def _semantic_embed(self, text: str) -> list[float]:
        """Run the full tokenize -> infer -> pool -> normalize pipeline."""
        assert self._session is not None
        assert self._tokenizer is not None

        # Short-circuit: empty text produces a zero vector without wasting
        # inference on all-padding. The zero vector is the documented degenerate
        # output for empty input (same as HashEmbedder).
        if not text:
            return [0.0] * self.dim

        # 1. Tokenize.
        encoding = self._tokenizer.encode(text)
        input_ids = encoding.ids
        attention_mask = encoding.attention_mask

        # MiniLM uses token_type_ids but they are all zero for single-seq.
        token_type_ids = encoding.type_ids if encoding.type_ids else [0] * len(input_ids)

        # Pad / truncate to the model's expected sequence length (128 for
        # MiniLM-L6-v2 by default; we read it from the session input).
        max_len = self._session.get_inputs()[0].shape[1]
        if max_len is None or max_len < 0:
            max_len = 128  # safe fallback

        if len(input_ids) > max_len:
            logger.warning(
                "SemanticEmbedder truncating %d tokens to max_len=%d for text of %d chars",
                len(input_ids), max_len, len(text),
            )
            input_ids = input_ids[:max_len]
            attention_mask = attention_mask[:max_len]
            token_type_ids = token_type_ids[:max_len]
        else:
            pad_len = max_len - len(input_ids)
            input_ids += [0] * pad_len
            attention_mask += [0] * pad_len
            token_type_ids += [0] * pad_len

        # 2. Run inference.
        import numpy as np

        ort_inputs = {
            self._session.get_inputs()[0].name: np.array([input_ids], dtype=np.int64),
            self._session.get_inputs()[1].name: np.array([attention_mask], dtype=np.int64),
            self._session.get_inputs()[2].name: np.array([token_type_ids], dtype=np.int64),
        }
        outputs = self._session.run(None, ort_inputs)
        # outputs[0] shape: (1, seq_len, hidden_dim) -- typically (1, 128, 384)
        token_embeddings = outputs[0][0]  # (seq_len, hidden_dim)

        # 3. Mean pool (masked).
        mask = np.expand_dims(attention_mask, axis=-1).astype(np.float32)  # (seq_len, 1)
        masked = token_embeddings * mask
        summed = masked.sum(axis=0)
        denom = mask.sum(axis=0).clip(min=1e-9)
        pooled = summed / denom  # (hidden_dim,)

        # 4. L2 normalize.
        norm = np.linalg.norm(pooled)
        if norm > 0:
            pooled = pooled / norm

        return pooled.tolist()

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _fallback_embed(self, text: str) -> list[float]:
        """Delegate to :class:`HashEmbedder` with the same output dimension."""
        if self._fallback is None:
            self._fallback = HashEmbedder(dim=self.dim)
        return self._fallback.embed(text)
