"""python/synapse/cache_policy/signatures.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Canonical serialization + SHA-256 digests per blueprint §12.2 (upstream signature) and the
§7.5 ``evidence_digest`` field. Pure stdlib (``hashlib`` + ``json``) -- no ``hou``, no Qt.

Determinism (§17.2 boundary test: "decisions serialize deterministically for evidence
hashing"): ``canonical_bytes()`` sorts dict keys, uses a fixed separator, and routes every
non-primitive value through ``models.to_jsonable`` first, so two calls with equal input
always produce byte-identical output and therefore an identical digest. This is exercised in
tests/test_cache_signatures.py.

§12.2 explicitly warns: "Do not rely only on Houdini session data IDs for persistent
validity." Nothing in this module reads a live session id; every signature component here is
caller-supplied data.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from .models import to_jsonable

SIGNATURE_ALGORITHM_VERSION = "sha256-canonical-json/v1"
"""§12.2: "The signature algorithm version belongs in the manifest." Callers that persist a
signature (e.g. into a CacheManifest) should record this string alongside it."""


def canonical_bytes(obj: Any) -> bytes:
    """Deterministic canonical JSON encoding: sorted keys, compact separators, explicit
    dataclass/Enum flattening via ``to_jsonable`` (never json's implicit str-Enum handling).
    """
    jsonable = to_jsonable(obj)
    return json.dumps(
        jsonable, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def sha256_hexdigest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_of(obj: Any) -> str:
    """``"sha256:<hex>"`` digest of the canonical serialization of ``obj``. Same input ->
    same output, always -- no timestamps, no randomness, no session state involved."""
    return "sha256:" + sha256_hexdigest(canonical_bytes(obj))


# --------------------------------------------------------------------------- §12.2 upstream signature

_UPSTREAM_SIGNATURE_COMPONENT_KEYS = (
    "upstream_topology",
    "node_type_names_and_versions",
    "parameters_and_expressions",
    "input_ordering_and_connection_identities",
    "hda_definition_identity",
    "frame_range",
    "context_options",
    "external_dependency_identities",
    "strategy_version",
    "houdini_build",
    "compatibility_policy",
)


def build_upstream_signature(*, upstream_topology: Any = None,
                              node_type_names_and_versions: Any = None,
                              parameters_and_expressions: Any = None,
                              input_ordering_and_connection_identities: Any = None,
                              hda_definition_identity: Any = None,
                              frame_range: Any = None,
                              context_options: Any = None,
                              external_dependency_identities: Any = None,
                              strategy_version: Optional[str] = None,
                              houdini_build: Optional[str] = None,
                              compatibility_policy: Optional[str] = None) -> str:
    """§12.2: "Create a canonical, versioned serialization containing, as available: ...
    Hash the canonical bytes with SHA-256." Every component is optional (``None`` when a
    caller cannot supply it) -- omitted components are simply absent from the canonical
    payload, never coerced to a fake placeholder. Two calls with the same non-None
    components in any keyword order produce the identical digest (order-independence comes
    from ``canonical_bytes``'s ``sort_keys=True``).
    """
    values = {
        "upstream_topology": upstream_topology,
        "node_type_names_and_versions": node_type_names_and_versions,
        "parameters_and_expressions": parameters_and_expressions,
        "input_ordering_and_connection_identities": input_ordering_and_connection_identities,
        "hda_definition_identity": hda_definition_identity,
        "frame_range": frame_range,
        "context_options": context_options,
        "external_dependency_identities": external_dependency_identities,
        "strategy_version": strategy_version,
        "houdini_build": houdini_build,
        "compatibility_policy": compatibility_policy,
    }
    payload = {k: v for k, v in values.items() if v is not None}
    payload["_signature_algorithm_version"] = SIGNATURE_ALGORITHM_VERSION
    return digest_of(payload)


def compute_evidence_digest(evidence_payload: dict) -> str:
    """§7.5 ``evidence_digest``: a stable hash of the substantive evidence/estimates a
    CacheDecision was computed from. Callers MUST exclude opaque/non-deterministic fields
    (``decision_id``, wall-clock timestamps) from ``evidence_payload`` before calling this --
    decision.py does so explicitly; see its ``_evidence_digest_payload`` helper.
    """
    return digest_of(evidence_payload)
