"""AUTORESEARCH probe library — the only module that touches hou.

Evidence discipline:
    - Probes ask the live runtime. They never answer from memory.
    - A missing type is an answer (exists: false), not an exception.
    - Probe-internal exceptions surface to the runner, which records
      them as evidence entries rather than crashing the mission.
    - Probes probe for their own tools (hou.text.decode is guarded,
      NodeType.deprecated is guarded) and record which path was used.

hou is imported guarded so mission validation and unit tests run under
plain Python. Execution requires hython — require_hou() enforces it.
"""
from __future__ import annotations

import hashlib
import json as _json
import sys as _sys
from pathlib import Path as _Path

try:
    import hou  # type: ignore
    HOU_AVAILABLE = True
except ImportError:  # plain Python — validation / unit tests only
    hou = None
    HOU_AVAILABLE = False

_REPO_ROOT = _Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- canonicalizer
# The c3 canonicalizer now lives in the PRODUCT tree, at
# synapse/blocks/canonical.py, and this harness imports it. Two copies of the
# filter list would be two silently different oracles: a fixture's committed
# baseline sha256 is only meaningful against a named canonicalizer, and the
# first divergence between harness and reconciler would read as a reconciler
# bug. tests/test_blocks_reconciler.py pins the single-source relationship.
#
# The path is derived from THIS file, so a git worktree's probes.py imports
# that worktree's canonicalizer — which is what makes a worktree run evidence
# about the worktree.
if str(_REPO_ROOT / "python") not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT / "python"))

from synapse.blocks.canonical import (  # noqa: E402
    C1_RULES as _C1_RULES,
    CANONICALIZER_VERSION,
    canonicalize_usda,
    houdini_env_map,
)


def _env_map() -> dict:
    """The c3 environment map for this process, or {} under plain Python.

    R-M5-1: a baseline cut without this is machine-local (finding M5-F1) —
    $HIP reaches the composed stage already expanded, so rule 5 has nothing to
    match unless the environment is handed to it. Every hash produced in this
    module goes through here; there is no second path.
    """
    if not HOU_AVAILABLE:
        return {}
    return houdini_env_map(hou.text.expandString)


_PROBE_NODE = "ar_probe"        # parm-probe scratch node name
_CHAIN_PREFIX = "arc"           # chain nodes: arc<i>_<type> — exact, never auto-incremented


def require_hou() -> None:
    if not HOU_AVAILABLE:
        raise RuntimeError(
            "probes require hython (import hou failed). "
            "Launch via drive_autoresearch.ps1, or run runner.py --validate-only "
            "for schema checks under plain Python."
        )


def get_build() -> str:
    return hou.applicationVersionString()


# ---------------------------------------------------------------- type cache

_types_cache = None


def _lop_types() -> dict:
    """name -> hou.NodeType for the LOP category. Cached per process."""
    global _types_cache
    if _types_cache is None:
        _types_cache = dict(hou.lopNodeTypeCategory().nodeTypes())
    return _types_cache


# ---------------------------------------------------------------- P0 probes

def probe_type_discovery(pattern: str) -> dict:
    """All LOP type names containing `pattern` (case-insensitive), from the
    live category list. This is the probe that finds successors to dead
    literals — the answer comes from the runtime, not from recall."""
    p = pattern.lower()
    matches = sorted(n for n in _lop_types() if p in n.lower())
    return {"pattern": pattern, "count": len(matches), "matches": matches}


def probe_type_existence(name: str) -> dict:
    t = _lop_types().get(name)
    if t is None:
        return {"exists": False}
    # deprecated() is guarded — phantom-API discipline applies to probes too.
    dep_fn = getattr(t, "deprecated", None)
    deprecated = dep_fn() if callable(dep_fn) else None
    return {"exists": True, "description": t.description(), "deprecated": deprecated}


# ---------------------------------------------------------------- P1 probes

def _decoder():
    """hou.text.decode if the runtime has it; else None. Recorded either way."""
    t = getattr(hou, "text", None)
    d = getattr(t, "decode", None) if t is not None else None
    return d if callable(d) else None


def probe_parms(type_name: str, highlight: list) -> dict:
    """Instantiate under /stage, capture every parm name verbatim (encoded
    xn__ names included), destroy. Highlight filters match the raw name or
    its decoded form, case-insensitive."""
    stage = hou.node("/stage")
    if stage is None:
        return {"error": "/stage not present in this session"}

    decode = _decoder()
    node = None
    try:
        node = stage.createNode(type_name, _PROBE_NODE)
        all_names = sorted(p.name() for p in node.parms())

        decoded = {}
        if decode is not None:
            for n in all_names:
                if n.startswith("xn__"):
                    try:
                        d = decode(n)
                        if d and d != n:
                            decoded[n] = d
                    except Exception:
                        pass  # undecodable name — raw form is still evidence

        hits = {}
        for f in highlight:
            fl = f.lower()
            hits[f] = sorted(
                n for n in all_names
                if fl in n.lower() or fl in decoded.get(n, "").lower()
            )

        return {
            "all_count": len(all_names),
            "all": all_names,
            "highlight": hits,
            "decoded": decoded,
            "decoder": "hou.text.decode" if decode else "unavailable",
        }
    finally:
        if node is not None:
            try:
                node.destroy()
            except Exception:
                pass


# ---------------------------------------------------------------- P2 probes

def _build_chain_once(chain: list, stage) -> dict:
    """One construction pass: create with EXACT names, wire linearly,
    compose, flatten, canonicalize, hash, destroy. Returns pass evidence."""
    nodes = []
    per_node = []
    try:
        prev = None
        for i, tname in enumerate(chain):
            requested = f"{_CHAIN_PREFIX}{i}_{tname}"
            n = stage.createNode(tname, requested)
            nodes.append(n)
            per_node.append({"requested_type": tname,
                             "requested_name": requested,
                             "created_name": n.name()})
            if prev is not None:
                n.setInput(0, prev)
            prev = n

        composed = prev.stage()  # composed pxr Usd.Stage at the chain tail
        if composed is None:
            return {"error": "stage() returned None at chain tail",
                    "tail_errors": list(prev.errors()),
                    "per_node": per_node}

        canon = canonicalize_usda(composed.Flatten().ExportToString(),
                                  env=_env_map())
        return {
            "sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
            "line_count": canon.count("\n"),
            "per_node": per_node,
            "canon_text": canon,  # held for diffing; dropped before recording
        }
    finally:
        for n in reversed(nodes):
            try:
                n.destroy()
            except Exception:
                pass


def probe_chain_hash(chain: list, name: str, repeat: int) -> dict:
    """Build the chain `repeat` times from clean, hash each pass, compare.

    stable == True is in-run determinism evidence (F-0): identical
    construction yields identical composed USD within one session. When
    unstable, a bounded line-diff sample of the first divergent pass pair
    ships in the evidence so the volatile source is identifiable."""
    stage = hou.node("/stage")
    if stage is None:
        return {"error": "/stage not present in this session"}

    # Pre-flight: every literal must exist. Missing literal = answer, not crash.
    missing = [t for t in chain if t not in _lop_types()]
    if missing:
        return {"error": "chain contains non-existent type literals",
                "missing": missing, "chain": chain}

    passes = []
    for _ in range(repeat):
        passes.append(_build_chain_once(chain, stage))

    failed = [p for p in passes if "error" in p]
    if failed:
        return {"error": "chain construction failed",
                "detail": {k: v for k, v in failed[0].items() if k != "canon_text"},
                "chain": chain}

    hashes = [p["sha256"] for p in passes]
    stable = len(set(hashes)) == 1

    result = {
        "chain": chain,
        "repeat": repeat,
        "hashes": hashes,
        "stable": stable,
        "sha256": hashes[0] if stable else None,
        "line_count": passes[0]["line_count"],
        "per_node": passes[0]["per_node"],
        "name_drift": any(pn["created_name"] != pn["requested_name"]
                          for p in passes for pn in p["per_node"]),
        "canonicalizer": CANONICALIZER_VERSION,
        "canonicalizer_rules": list(_C1_RULES),
        # Law 2: the environment a c3 hash was cut against travels WITH the
        # hash. A baseline whose env is unrecorded is machine-local and cannot
        # be told apart from one that is not.
        "canonicalizer_env": _env_map(),
    }

    if not stable:
        a = passes[0]["canon_text"].splitlines()
        b = passes[1]["canon_text"].splitlines()
        diff = [{"line": i, "pass0": la, "pass1": lb}
                for i, (la, lb) in enumerate(zip(a, b)) if la != lb]
        if len(a) != len(b):
            diff.append({"line": "length", "pass0": len(a), "pass1": len(b)})
        result["diff_sample"] = diff[:5]

    return result


# ---------------------------------------------------------------- P3 probes
# fixture_hash: build a BLOCKS fixture from its JSON definition and hash the
# composed stage. This builder is the seed of the reconciler's build path.
# ASCII only below (PS-adjacent tooling reads these files).
# _json / _Path / _REPO_ROOT are established at the top of this module,
# alongside the canonicalizer import.


def _build_fixture_once(fx: dict, stage) -> dict:
    """One construction pass from a fixture dict: create nodes with EXACT
    names, set parms (a missing parm name is a hard error - the fixture must
    be exact), wire, position, flag, compose, hash, destroy."""
    nodes = {}
    order = []
    per_node = []
    missing_parms = []
    try:
        for spec in fx["nodes"]:
            n = stage.createNode(spec["type"], spec["name"])
            nodes[spec["name"]] = n
            order.append(n)
            per_node.append({"requested_type": spec["type"],
                             "requested_name": spec["name"],
                             "created_name": n.name()})

        for spec in fx["nodes"]:
            n = nodes[spec["name"]]
            for pname, pval in spec.get("parms", {}).items():
                p = n.parm(pname)
                if p is None:
                    missing_parms.append(spec["name"] + "." + pname)
                else:
                    p.set(pval)
        if missing_parms:
            return {"error": "fixture parm name(s) not found on node(s)",
                    "missing_parms": missing_parms, "per_node": per_node}

        for dst, idx, src in fx.get("wires", []):
            nodes[dst].setInput(int(idx), nodes[src])

        for spec in fx["nodes"]:
            pos = spec.get("position")
            if pos:
                nodes[spec["name"]].setPosition(hou.Vector2(float(pos[0]), float(pos[1])))

        tail_name = fx.get("display") or fx["nodes"][-1]["name"]
        tail = nodes[tail_name]
        tail.setDisplayFlag(True)

        composed = tail.stage()
        if composed is None:
            return {"error": "stage() returned None at fixture tail",
                    "tail_errors": list(tail.errors()), "per_node": per_node}

        canon = canonicalize_usda(composed.Flatten().ExportToString(),
                                  env=_env_map())
        return {"sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
                "line_count": canon.count("\n"),
                "per_node": per_node,
                "canon_text": canon}
    finally:
        for n in reversed(order):
            try:
                n.destroy()
            except Exception:
                pass


def probe_fixture_hash(path: str, name: str, repeat: int) -> dict:
    """Load a fixture (repo-root-relative path), build it `repeat` times from
    clean, hash each pass, compare. Same stability contract as chain_hash."""
    stage = hou.node("/stage")
    if stage is None:
        return {"error": "/stage not present in this session"}

    fp = _REPO_ROOT / path
    if not fp.exists():
        return {"error": "fixture file not found", "path": str(fp)}
    try:
        fx = _json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": "fixture file is not valid JSON", "path": str(fp),
                "detail": str(e)}

    types = [spec.get("type") for spec in fx.get("nodes", [])]
    missing = [t for t in types if t not in _lop_types()]
    if missing:
        return {"error": "fixture contains non-existent type literals",
                "missing": missing, "path": str(fp)}

    passes = []
    for _ in range(repeat):
        passes.append(_build_fixture_once(fx, stage))

    failed = [p for p in passes if "error" in p]
    if failed:
        return {"error": "fixture construction failed",
                "detail": {k: v for k, v in failed[0].items() if k != "canon_text"},
                "path": str(fp)}

    hashes = [p["sha256"] for p in passes]
    stable = len(set(hashes)) == 1

    result = {
        "fixture": fx.get("fixture", name),
        "fixture_version": fx.get("version"),
        "path": path,
        "repeat": repeat,
        "hashes": hashes,
        "stable": stable,
        "sha256": hashes[0] if stable else None,
        "line_count": passes[0]["line_count"],
        "per_node": passes[0]["per_node"],
        "name_drift": any(pn["created_name"] != pn["requested_name"]
                          for p in passes for pn in p["per_node"]),
        "canonicalizer": CANONICALIZER_VERSION,
        "canonicalizer_rules": list(_C1_RULES),
        # Law 2: the environment a c3 hash was cut against travels WITH the
        # hash. A baseline whose env is unrecorded is machine-local and cannot
        # be told apart from one that is not.
        "canonicalizer_env": _env_map(),
    }

    if not stable:
        a = passes[0]["canon_text"].splitlines()
        b = passes[1]["canon_text"].splitlines()
        diff = [{"line": i, "pass0": la, "pass1": lb}
                for i, (la, lb) in enumerate(zip(a, b)) if la != lb]
        if len(a) != len(b):
            diff.append({"line": "length", "pass0": len(a), "pass1": len(b)})
        result["diff_sample"] = diff[:5]

    return result
