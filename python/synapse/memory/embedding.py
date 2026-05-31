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

Pure Python. Zero third-party deps. No Houdini, no Moneta, no pxr. Importable
and testable standalone.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Iterator, Protocol, runtime_checkable


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
