"""Mile 2 (resource-aware-cache Phase 0, R-CACHE-1) -- tests for
``synapse.cache_policy.signatures``.

Covers blueprint §12.2 (upstream signature: canonical serialization + SHA-256) and §17.2's
boundary test "decisions serialize deterministically for evidence hashing". Pure stdlib.

Every test states the condition under which it fails.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from synapse.cache_policy.models import CacheVerdict, Interval  # noqa: E402
from synapse.cache_policy.signatures import (  # noqa: E402
    build_upstream_signature,
    canonical_bytes,
    compute_evidence_digest,
    digest_of,
)


def test_digest_of_same_input_produces_same_digest():
    """Fails if two calls with an identical (but freshly-constructed, not object-identical)
    payload produce different digests -- the core determinism guarantee."""
    payload_a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    payload_b = {"a": 1, "b": 2, "nested": {"y": 8, "z": 9}}  # different key insertion order
    assert digest_of(payload_a) == digest_of(payload_b)


def test_digest_of_different_input_produces_different_digest():
    """Fails if the digest is insensitive to a real content change (e.g. a constant-digest
    bug, or a bug that only hashes the dict's keys)."""
    assert digest_of({"a": 1}) != digest_of({"a": 2})


def test_digest_is_sha256_prefixed():
    """Fails if the digest string format drifts from the documented 'sha256:<hex>' shape,
    which downstream manifest fields (§7.6 upstream_signature etc.) depend on."""
    d = digest_of({"x": 1})
    assert d.startswith("sha256:")
    hex_part = d.split(":", 1)[1]
    assert len(hex_part) == 64
    int(hex_part, 16)  # raises ValueError if not valid hex


def test_canonical_bytes_flattens_enum_to_its_value():
    """Fails if an Enum member serializes as its repr/name instead of its string value --
    would silently break cross-language/tool consumption of the canonical payload."""
    b = canonical_bytes({"verdict": CacheVerdict.CACHE_NOW})
    assert b'"cache_now"' in b
    assert b"CacheVerdict" not in b


def test_canonical_bytes_flattens_dataclass_recursively():
    """Fails if a nested dataclass (e.g. an Interval inside a larger structure) is not
    flattened to a plain dict before hashing -- json.dumps would raise TypeError on a raw
    dataclass instance."""
    b = canonical_bytes({"cache_bytes": Interval(low=1.0, high=2.0)})
    assert b'"low":1.0' in b or b'"low": 1.0' in b or b'"low":1.0' in b.replace(b" ", b"")


def test_canonical_bytes_sorts_keys_deterministically():
    """Fails if key order in the output bytes tracks insertion order instead of being
    sorted -- two logically-identical dicts built in different code paths must hash the
    same."""
    b1 = canonical_bytes({"z": 1, "a": 2})
    b2 = canonical_bytes({"a": 2, "z": 1})
    assert b1 == b2
    assert b1.index(b'"a"') < b1.index(b'"z"')


def test_compute_evidence_digest_excludes_nothing_passed_in_but_is_still_deterministic():
    """Fails if compute_evidence_digest applies any hidden non-deterministic transform
    (e.g. injecting a timestamp) -- callers are responsible for excluding opaque fields
    themselves (see decision.py's ``_evidence_digest_payload``); this function must be a
    pure pass-through to digest_of."""
    payload = {"strategy_id": "sop_filecache_geometry_v1", "policy": {"ram_safety_fraction": 0.8}}
    assert compute_evidence_digest(payload) == compute_evidence_digest(dict(payload))


def test_build_upstream_signature_omits_none_components():
    """Fails if a None (not-supplied) component is coerced into the canonical payload as a
    literal null that changes the hash versus genuinely omitting it -- §12.2: components are
    included "as available", not padded with fake placeholders."""
    sig_partial = build_upstream_signature(node_type_names_and_versions=["sop/filecache::2.0"])
    sig_same = build_upstream_signature(
        node_type_names_and_versions=["sop/filecache::2.0"],
        parameters_and_expressions=None,
        houdini_build=None,
    )
    assert sig_partial == sig_same


def test_build_upstream_signature_changes_when_a_component_changes():
    """Fails if two different upstream topologies collide onto the same signature -- the
    entire point of §12.2 is that a changed upstream must produce a changed signature so
    ``decision.validate_existing_cache`` can detect STALE."""
    sig1 = build_upstream_signature(node_type_names_and_versions=["sop/filecache::2.0"],
                                     houdini_build="22.0.400")
    sig2 = build_upstream_signature(node_type_names_and_versions=["sop/filecache::2.1"],
                                     houdini_build="22.0.400")
    assert sig1 != sig2


def test_build_upstream_signature_is_order_independent_across_keyword_args():
    """Fails if signature computation is sensitive to the keyword-argument call order
    rather than the logical content -- Python guarantees kwarg dict construction order
    matches call order, so this specifically exercises canonical_bytes's sort_keys
    guarantee end to end."""
    sig_a = build_upstream_signature(houdini_build="22.0.400", strategy_version="v1")
    sig_b = build_upstream_signature(strategy_version="v1", houdini_build="22.0.400")
    assert sig_a == sig_b


def test_signature_reflects_frame_range_change():
    """Fails if frame_range is silently dropped from the canonical payload -- §12.1 lists
    'a different frame range or FPS' as a reason a file can exist while representing a
    stale cache."""
    sig1 = build_upstream_signature(frame_range={"start": 1001, "end": 1240, "step": 1})
    sig2 = build_upstream_signature(frame_range={"start": 1001, "end": 1300, "step": 1})
    assert sig1 != sig2


@dataclass
class _UnknownButFlattenable:
    """Confirms to_jsonable (transitively exercised via canonical_bytes) handles an
    arbitrary dataclass this test file defines, not just the cache_policy package's own
    types -- guards against an accidental isinstance() check tied to a specific class."""
    a: int
    b: str


def test_canonical_bytes_handles_a_foreign_dataclass():
    """Fails if to_jsonable's dataclass branch is somehow specific to cache_policy's own
    dataclasses instead of using the generic ``dataclasses.is_dataclass`` check."""
    b = canonical_bytes(_UnknownButFlattenable(a=1, b="x"))
    assert b'"a":1' in b.replace(b" ", b"")
    assert b'"b":"x"' in b.replace(b" ", b"")
