"""Pure authored-graph identity and explicit stage canonicalization context.

Graph v1 sorts node/connection records, never their ordered parameter values.
It excludes presentation and layout from semantic identity. It does NOT round
numbers, evaluate expressions, strip dates, or rename node IDs. Only parameters
explicitly typed ``path`` may use caller-approved c3 path tokens. No environment
is read implicitly. Stage text uses the existing BLOCKS c3 implementation; its
documented filters are deliberately not applied to authored graph strings.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from synapse.blocks import canonical as c3
from synapse.recipes.contracts import RecipeSpec

CANONICALIZER_VERSION = "recipes-graph-v1+c3"
STAGE_VERSION = "recipes-stage-v1+c3"
SEMANTIC_NODE_KEYS = (
    "id", "parent_id", "category", "type", "parms", "expressions", "flags", "ports",
)


def plain(value: Any) -> Any:
    """Copy JSON-shaped mappings/tuples without losing numeric or string types."""
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        plain(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def canonicalizer_digest() -> str:
    """Pin both implementations, using LF bytes for checkout independence."""
    return digest({
        "version": CANONICALIZER_VERSION,
        "graph_source": Path(__file__).read_text(encoding="utf-8"),
        "stage_source": Path(c3.__file__).read_text(encoding="utf-8"),
    })


def _approved_tokens(tokens: Mapping[str, str] | None) -> dict[str, str]:
    tokens = dict(tokens or {})
    if set(tokens) - set(c3.ENV_VARS):
        raise ValueError("unapproved path token")
    valid = c3.houdini_env_map(lambda key: tokens[key], names=tuple(tokens))
    if valid != tokens:
        raise ValueError("path token expansions must be absolute paths")
    return valid


def _normalize_path(value: str, tokens: Mapping[str, str]) -> str:
    # Reuse the single c3 substitution authority, including longest-prefix order
    # and Windows slash variants. Narrow its application to whole path prefixes.
    for needle, token in c3._env_substitutions(tokens):
        prefix = needle.rstrip("/\\")
        if value == prefix or value.startswith(prefix + "/") or value.startswith(prefix + "\\"):
            return token + value[len(prefix):].replace("\\", "/")
    return value


def _graph(value: RecipeSpec | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, RecipeSpec):
        return {"nodes": value.nodes, "connections": value.connections}
    if not isinstance(value, Mapping):
        raise TypeError("expected RecipeSpec or observed graph mapping")
    return value


def semantic_digest(spec_or_observed: RecipeSpec | Mapping[str, Any], *,
                    path_tokens: Mapping[str, str] | None = None) -> str:
    graph = _graph(spec_or_observed)
    tokens = _approved_tokens(path_tokens)
    nodes = []
    for node in graph["nodes"]:
        record = {key: plain(node[key]) for key in SEMANTIC_NODE_KEYS if key in node}
        for parm in record.get("parms", {}).values():
            if isinstance(parm, dict) and parm.get("type") == "path" and "value" in parm:
                parm["value"] = _normalize_path(parm["value"], tokens)
        nodes.append(record)
    nodes.sort(key=lambda node: node["id"])
    connections = sorted((plain(wire) for wire in graph["connections"]),
                         key=lambda wire: (wire["dst_id"], wire["dst_input"],
                                           wire["src_id"], wire["src_output"]))
    return digest({"version": CANONICALIZER_VERSION,
                   "nodes": nodes, "connections": connections})


def layout_digest(spec_or_observed: RecipeSpec | Mapping[str, Any]) -> str:
    graph = _graph(spec_or_observed)
    return digest({"version": "recipes-layout-v1", "nodes": sorted(
        ({"id": node["id"], "position": plain(node["position"])} for node in graph["nodes"]),
        key=lambda node: node["id"],
    )})


def stage_canonicalization_record(*, frame: float, time: float,
                                  load_rules: list, layers: list,
                                  resolver_identity: Mapping[str, Any],
                                  dependency_identity: Mapping[str, Any]) -> dict:
    """Caller-observed context; no default frame, resolver, or layer inventory.

    Layer order is significant. Anonymous layer handles may be normalized in
    c3 text, but the caller must retain layer content identities in this record.
    Empty dependency identity means an observed empty inventory, not UNKNOWN.
    """
    for name, value in (("frame", frame), ("time", time)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"stage {name} must be finite")
    if not isinstance(load_rules, (list, tuple)) or not isinstance(layers, (list, tuple)) or not layers:
        raise ValueError("stage requires load rules and a nonempty layer inventory")
    if not isinstance(resolver_identity, Mapping) or not resolver_identity or not isinstance(dependency_identity, Mapping):
        raise ValueError("stage requires resolver and dependency identity")
    record = {"version": STAGE_VERSION, "frame": frame, "time": time,
              "load_rules": plain(load_rules), "layers": plain(layers),
              "resolver_identity": plain(resolver_identity),
              "dependency_identity": plain(dependency_identity)}
    digest(record)  # Reject non-JSON/NaN nested identity data too.
    return record


def canonicalize_stage(text: str, record: Mapping[str, Any], *,
                       path_tokens: Mapping[str, str]) -> dict:
    """Reuse c3 stage rules verbatim, bound to explicit observation context."""
    if record.get("version") != STAGE_VERSION:
        raise ValueError("unsupported stage canonicalizer version")
    context = stage_canonicalization_record(**{key: record[key] for key in (
        "frame", "time", "load_rules", "layers", "resolver_identity", "dependency_identity",
    )})
    return {"context": context, "rules": list(c3.C1_RULES),
            "canonical_text": c3.canonicalize_usda(text, env=_approved_tokens(path_tokens))}
