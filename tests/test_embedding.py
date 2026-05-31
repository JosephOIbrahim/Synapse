"""CRUCIBLE suite for synapse.memory.embedding (Mile 2 bootstrap embedder).

Hostile by design. The contract under attack (handoff capsule "FIRST TASK"):

  * determinism    -- same input -> identical vector, across calls AND across
                      process restarts (the real trap: str hash() is salted by
                      PYTHONHASHSEED, so a naive impl passes in-process and fails
                      across processes).
  * fixed dim      -- every output is exactly ``dim`` long.
  * normalization  -- ||v|| == 1 for non-empty input.
  * edges          -- empty, whitespace-only, unicode, very long, near-dupes.

Pure standalone: no Houdini, no Moneta, no pxr. Never weaken a test to pass --
fix forward.
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PYDIR = _ROOT / "python"
sys.path.insert(0, str(_PYDIR))

from synapse.memory.embedding import Embedder, HashEmbedder  # noqa: E402

TOL = 1e-9


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def _cosine(a, b):
    return sum(x * y for x, y in zip(a, b))  # both unit vectors


# --------------------------------------------------------------------------- #
# interface / provenance
# --------------------------------------------------------------------------- #

def test_implements_embedder_protocol():
    assert isinstance(HashEmbedder(), Embedder)


def test_id_and_dim_exposed():
    emb = HashEmbedder()
    assert emb.dim == 256
    assert emb.id.startswith("hash-ngram-v1")
    # id must encode every parameter that defines the vector space, so a swap
    # or re-config is detectable from stamped provenance.
    assert emb.id == "hash-ngram-v1-d256-n1_3"
    assert HashEmbedder(dim=384).id == "hash-ngram-v1-d384-n1_3"
    assert HashEmbedder(dim=256).id != HashEmbedder(dim=384).id
    assert HashEmbedder(ngram_max=4).id != HashEmbedder(ngram_max=3).id


def test_invalid_construction_rejected():
    with pytest.raises(ValueError):
        HashEmbedder(dim=0)
    with pytest.raises(ValueError):
        HashEmbedder(dim=-5)
    with pytest.raises(ValueError):
        HashEmbedder(ngram_min=0)
    with pytest.raises(ValueError):
        HashEmbedder(ngram_min=3, ngram_max=2)


# --------------------------------------------------------------------------- #
# fixed dim
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("dim", [2, 16, 256, 384, 1000])
def test_fixed_dim_holds_for_every_input(dim):
    emb = HashEmbedder(dim=dim)
    for text in ["", " ", "a", "hello world", "x" * 5000, "café 🧠 déjà"]:
        v = emb.embed(text)
        assert isinstance(v, list)
        assert len(v) == dim
        assert all(isinstance(x, float) for x in v)


# --------------------------------------------------------------------------- #
# determinism
# --------------------------------------------------------------------------- #

def test_determinism_same_process():
    emb = HashEmbedder()
    text = "Synapse routes tasks to specialist agents."
    assert emb.embed(text) == emb.embed(text)
    # Two independent instances with identical config agree exactly.
    assert HashEmbedder().embed(text) == HashEmbedder().embed(text)


# This is the load-bearing test. A naive implementation built on the built-in
# hash() for str passes every in-process check and silently fails here, because
# CPython salts str/bytes hashing per process (PYTHONHASHSEED). Vectors stamped
# into Moneta deposits would then differ run-to-run -- catastrophic for recall.
def test_determinism_across_processes_and_hashseed():
    driver = (
        "import sys, json;"
        f"sys.path.insert(0, {str(_PYDIR)!r});"
        "from synapse.memory.embedding import HashEmbedder;"
        "print(json.dumps(HashEmbedder().embed('Synapse\\u2194Moneta caf\\u00e9 "
        "\\U0001f9e0 d\\u00e9j\\u00e0 vu')))"
    )

    def run(seed):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        out = subprocess.check_output([sys.executable, "-c", driver], env=env)
        return json.loads(out)

    a = run("0")
    b = run("1")
    c = run("123456789")
    assert a == b == c
    assert abs(_norm(a) - 1.0) < 1e-6


# --------------------------------------------------------------------------- #
# normalization
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text", [
    "a",
    "hello",
    "The quick brown fox jumps over the lazy dog.",
    "   ",                       # whitespace-only is NON-empty -> must normalize
    "\t\n  \r",
    "café déjà vu naïve",        # latin-1 supplement
    "日本語のテキスト",            # CJK
    "🧠🔥✨ emoji run 🚀",          # astral plane
    # Wrapped in pytest.param with an explicit id: a 100k-char value used as a
    # raw param becomes the node id, which pytest writes into PYTEST_CURRENT_TEST
    # -- and Windows caps env vars at 32767 chars, erroring at teardown.
    pytest.param("a" * 100_000, id="very-long"),
])
def test_unit_norm_for_nonempty(text):
    v = HashEmbedder().embed(text)
    assert abs(_norm(v) - 1.0) < 1e-6


def test_empty_string_is_the_only_zero_vector():
    v = HashEmbedder().embed("")
    assert len(v) == 256
    assert _norm(v) == 0.0
    assert all(x == 0.0 for x in v)


def test_tiny_dim_nonempty_still_unit_norm():
    # Adversarial: with dim this small the signed buckets can sum to exactly
    # zero. The fallback unit-spike must still deliver a normalized vector.
    emb = HashEmbedder(dim=2)
    for text in ["a", "ab", "abc", "the cat sat", "  ", "🧠"]:
        v = emb.embed(text)
        assert len(v) == 2
        assert abs(_norm(v) - 1.0) < 1e-6


# --------------------------------------------------------------------------- #
# discrimination / near-duplicates
# --------------------------------------------------------------------------- #

def test_distinct_inputs_give_distinct_vectors():
    emb = HashEmbedder()
    a = emb.embed("render the karma beauty pass")
    b = emb.embed("evolve the scene memory to charizard")
    assert a != b
    assert _cosine(a, b) < 0.99


def test_near_duplicates_are_close_but_not_identical():
    emb = HashEmbedder()
    base = "The shot is rendering on the farm tonight."
    near = "The shot is rendering on the farm tonigth."  # one transposition
    va, vn = emb.embed(base), emb.embed(near)
    assert va != vn
    sim = _cosine(va, vn)
    assert 0.85 < sim < 1.0  # sensitive, yet stable under a tiny edit


def test_unicode_is_deterministic_and_distinct():
    emb = HashEmbedder()
    assert emb.embed("naïve café") == emb.embed("naïve café")
    assert emb.embed("café") != emb.embed("cafe")  # accent is signal, not noise


# --------------------------------------------------------------------------- #
# performance guard for "very long text"
# --------------------------------------------------------------------------- #

def test_very_long_text_terminates_cheaply():
    # Counter-dedup keeps this bounded by the count of UNIQUE n-grams, which
    # plateaus, not by raw length. Half a megabyte must embed without blowing up.
    emb = HashEmbedder()
    v = emb.embed("lorem ipsum dolor sit amet " * 20_000)
    assert len(v) == 256
    assert abs(_norm(v) - 1.0) < 1e-6
