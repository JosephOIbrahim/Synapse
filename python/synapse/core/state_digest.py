"""
state_digest.py - blast-radius-scoped state capture for the audit log.

Piece 2 of AUDIT_STATE_CAPTURE_SCOPE.md.

state_digest() returns (digest, snapshot):

    digest   - sha256 hex over the canonicalised snapshot, or "" when the
               operation is out of scope
    snapshot - the dict the digest was taken over, or None

The caller decides what to keep. Digest alone gives change detection,
which is what a failure predictor needs. Keeping snapshots and diffing
before/after gives state transitions, at the cost of disk and encryption
load. That choice lives at the call site, not here.

Whole-scene hashing is deliberately not offered. It is correct and it
would dominate the latency of every bridge call.
"""
import re
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple

# Read-only: before == after by definition, never worth hashing.
SKIP_PREFIXES = (
    "cops_read_", "read_", "get_", "list_", "query_", "inspect_",
    "usd_read_", "scene_read_", "ping",
)

# Unbounded blast radius. Marked null rather than faked - a fabricated
# hash would teach a downstream model that unscoped ops are always clean.
NULL_OPS = {"execute_python", "execute_hscript", "run_script", "eval_python"}

# Parameter-level ops hash the touched node's parm dict.
PARM_OPS = {"set_parm", "set_parms", "set_parm_expression", "set_parm_tuple"}

# Keys in input_data that carry node paths, in the shapes the live corpus
# actually uses: {"node": "/obj/x"}, {"node_path": "/obj/top"}, lists.
PATH_KEYS = (
    "node", "node_path", "path", "parent", "parent_path",
    "target", "target_path", "nodes", "node_paths", "paths",
)

# Parms whose evaluated value moves with the playbar. Including them would
# produce a spurious diff on every call at a different frame.
TIME_VARYING = re.compile(
    r"\$F\b|\$FF\b|\$T\b|\$SF\b|\$RFSTART|\$RFEND|\$NFRAMES|frame\s*\(\s*\)",
    re.IGNORECASE,
)

FLOAT_FMT = ".6g"


def _canon(v: Any) -> Any:
    """Canonical form. Floats get fixed precision so 0.1+0.2 and 0.3 agree."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return format(v, FLOAT_FMT)
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _canon(v[k]) for k in sorted(v, key=str)}
    return v


def _sha(obj: Any) -> str:
    blob = json.dumps(_canon(obj), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def extract_paths(args: Any, _depth: int = 0) -> List[str]:
    """Pull node paths out of an input_data dict. Recurses for batch ops."""
    found: List[str] = []
    if _depth > 4:
        return found
    if isinstance(args, str):
        return [args] if args.startswith("/") else []
    if isinstance(args, (list, tuple)):
        for item in args:
            found.extend(extract_paths(item, _depth + 1))
        return found
    if isinstance(args, dict):
        for k, v in args.items():
            if k in PATH_KEYS:
                if isinstance(v, str) and v.startswith("/"):
                    found.append(v)
                elif isinstance(v, (list, tuple)):
                    found.extend(x for x in v if isinstance(x, str) and x.startswith("/"))
            elif isinstance(v, (dict, list, tuple)):
                found.extend(extract_paths(v, _depth + 1))
    # dedupe, preserve order
    seen, out = set(), []
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def parm_snapshot(node) -> Dict[str, Any]:
    """Evaluated parm dict, time-varying parms excluded."""
    out: Dict[str, Any] = {}
    for p in node.parms():
        try:
            raw = str(p.rawValue())
        except Exception:
            continue
        if TIME_VARYING.search(raw):
            continue
        try:
            out[p.name()] = _canon(p.eval())
        except Exception:
            out[p.name()] = raw
    return out


def children_snapshot(node) -> Dict[str, Any]:
    """Topology of a node's children: names + types, order-independent."""
    try:
        kids = sorted(
            [c.name(), c.type().name()] for c in node.children()
        )
    except Exception:
        kids = []
    return {"children": kids}


def _hou():
    try:
        import hou  # noqa: F401
        return hou
    except Exception:
        return None


def in_scope(operation: str) -> bool:
    """True if this operation gets a state hash at all."""
    op = (operation or "").lower()
    if not op:
        return False
    if op in NULL_OPS:
        return False
    if op.startswith(SKIP_PREFIXES):
        return False
    return True


def state_digest(
    operation: str,
    args: Any,
    hou_module=None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Returns (sha256_hex, snapshot). ("", None) when out of scope."""
    if not in_scope(operation):
        return "", None

    hou = hou_module if hou_module is not None else _hou()
    if hou is None:
        return "", None

    paths = extract_paths(args)
    if not paths:
        return "", None

    op = operation.lower()
    parm_level = op in PARM_OPS
    snapshot: Dict[str, Any] = {}

    for path in paths:
        try:
            node = hou.node(path)
        except Exception:
            node = None
        if node is None:
            snapshot[path] = {"__missing__": True}
            continue
        try:
            snapshot[path] = (
                parm_snapshot(node) if parm_level else children_snapshot(node)
            )
        except Exception as exc:
            snapshot[path] = {"__error__": type(exc).__name__}

    return _sha(snapshot), snapshot


def changed(before_hash: str, after_hash: str) -> Optional[bool]:
    """True/False if both hashes are real, None if either is out of scope.

    None means 'unknown', not 'unchanged'. Downstream consumers must not
    collapse the two.
    """
    if not before_hash or not after_hash:
        return None
    return before_hash != after_hash
