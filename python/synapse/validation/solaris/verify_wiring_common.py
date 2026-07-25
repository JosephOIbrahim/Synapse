"""
RELAY-SOLARIS L2 — shared wiring-verification harness.

The pre-existing ``verify_component_builder.py`` (under the orphan ``synapse/``
tree) only asks *does this node type exist*. That is an existence probe, not a
wiring proof: a tool can create every node it promised and still emit a network
that composes to nothing. This module supplies the missing half.

Two tiers, deliberately separated:

* **STATIC** — pure Python, no ``hou``. Checks a declared topology against the
  live-probed LOP catalogue
  (``harness/notes/h22_lop_catalog_live_22.0.368.json``, 218 types, blake2b
  pinned). Proves every emitted type *exists on the pinned build* and that the
  declared wiring satisfies each type's ``min_inputs``/``max_inputs``. Runs in
  CI, gates in ``tests/``.
* **LIVE** — requires ``hou`` under hython 22.0.368. Runs the tool for real,
  then proves the *emitted* network (not the declared one) is connected, that
  the terminal LOP composes without error, and that its stage carries prims.

A verifier module declares ``TOOL``, ``EXPECTED_TOPOLOGY`` and (optionally)
``live_build``. Everything else is driven from here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

try:  # pragma: no cover - exercised only inside Houdini
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False


CONTRACT_VERSION = "solaris_wiring_verify/v1"
PINNED_BUILD = "22.0.368"

# repo root: python/synapse/validation/solaris/ -> up 4
_REPO = Path(__file__).resolve().parents[4]
CATALOG_PATH = _REPO / "harness" / "notes" / f"h22_lop_catalog_live_{PINNED_BUILD}.json"

#: Node types these tools emit that are NOT LOPs and so are absent from the LOP
#: catalogue by construction (they live inside a componentgeometry SOP subnet).
#: Listing them explicitly keeps "absent" honest: unknown-and-unlisted is a
#: failure, unknown-because-not-a-LOP is a documented exemption.
#: Types that legitimately terminate a Solaris graph. Used only to break ties
#: when a defective topology presents several terminals.
SINK_TYPES = frozenset({"componentoutput", "usdrender_rop", "usdexport"})

NON_LOP_TYPES = frozenset({
    "usdimport", "xform", "matchsize", "polyreduce", "attribwrangle", "null",
})


#: SR1 M1: the five tools moved from the orphan ``synapse/mcp/tools/solaris/``
#: tree (FINDING F1) into the installable package at
#: ``python/synapse/mcp/tool_impls/solaris/``. Named ``tool_impls`` rather than
#: ``tools`` because a regular ``mcp/tools/`` package shadows the existing
#: ``python/synapse/mcp/tools.py`` HTTP-transport module.
#:
#: The path-import below is retained deliberately: these verifiers must be able
#: to read a tool's source-level structure without the import side effects of
#: the package ``__init__``, and the path is the thing under test.
TOOLS_DIR = Path(__file__).resolve().parents[2] / "mcp" / "tool_impls" / "solaris"


def load_tool(module_name: str):
    """Path-import one Solaris tool module."""
    import importlib.util

    path = TOOLS_DIR / f"{module_name}.py"
    if not path.exists():
        raise FileNotFoundError(f"no such Solaris tool module: {path}")
    spec = importlib.util.spec_from_file_location(
        f"_solaris_tools.{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Check:
    """One assertion with its evidence. Serialises into the result contract."""

    __slots__ = ("name", "ok", "detail")

    def __init__(self, name: str, ok: bool, detail: str = "") -> None:
        self.name = name
        self.ok = bool(ok)
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Check {self.name} {'ok' if self.ok else 'FAIL'}: {self.detail}>"


def load_catalog(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Return the live-probed LOP type catalogue for the pinned build."""
    p = Path(path) if path is not None else CATALOG_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("build") != PINNED_BUILD:
        raise RuntimeError(
            f"catalogue build {data.get('build')!r} != pinned {PINNED_BUILD!r}"
        )
    return data["types"]


def result(tool: str, checks: Sequence[Check], tier: str,
           extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the result contract shared by every verifier."""
    failures = [c.to_dict() for c in checks if not c.ok]
    payload: Dict[str, Any] = {
        "contract": CONTRACT_VERSION,
        "tool": tool,
        "tier": tier,
        "build": PINNED_BUILD,
        "status": "FAIL" if failures else "PASS",
        "checks": [c.to_dict() for c in checks],
        "failures": failures,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# STATIC tier
# ---------------------------------------------------------------------------

def check_topology(topology: Sequence[Dict[str, Any]],
                   catalog: Optional[Dict[str, Dict[str, Any]]] = None,
                   ) -> List[Check]:
    """Check a declared topology against the live catalogue.

    ``topology`` is a sequence of ``{"name", "type", "inputs": [...]}``. An
    entry in ``inputs`` is the *name* of another node in the topology, or
    ``None`` for a deliberately-open input slot.
    """
    cat = load_catalog() if catalog is None else catalog
    checks: List[Check] = []
    names = {n["name"] for n in topology}

    for node in topology:
        name, ntype = node["name"], node["type"]
        inputs = list(node.get("inputs") or [])
        wired = [i for i in inputs if i is not None]

        if ntype in NON_LOP_TYPES:
            checks.append(Check(
                f"{name}:type_exempt", True,
                f"{ntype} is a non-LOP type (SOP-level), exempt from the LOP catalogue",
            ))
            continue

        spec = cat.get(ntype)
        if spec is None:
            checks.append(Check(
                f"{name}:type_exists", False,
                f"type {ntype!r} is ABSENT from the live {PINNED_BUILD} LOP catalogue",
            ))
            continue

        checks.append(Check(f"{name}:type_exists", True, f"{ntype} present"))
        checks.append(Check(
            f"{name}:not_deprecated", not spec.get("deprecated", False),
            f"{ntype} deprecated={spec.get('deprecated')}",
        ))

        # every referenced input must name a real node in the topology
        for ref in wired:
            checks.append(Check(
                f"{name}:input_ref[{ref}]", ref in names,
                f"input source {ref!r} {'found' if ref in names else 'NOT DECLARED'}",
            ))

        lo, hi = spec.get("min_inputs", 0), spec.get("max_inputs", 0)
        checks.append(Check(
            f"{name}:min_inputs", len(wired) >= lo,
            f"{ntype} needs >={lo} wired inputs, topology wires {len(wired)}",
        ))
        checks.append(Check(
            f"{name}:max_inputs", len(wired) <= hi,
            f"{ntype} accepts <={hi} inputs, topology wires {len(wired)}",
        ))

    return checks


def terminals_of(topology: Sequence[Dict[str, Any]]) -> List[str]:
    """Return every node no other node consumes, in declaration order."""
    consumed = {i for n in topology for i in (n.get("inputs") or []) if i}
    return [n["name"] for n in topology if n["name"] not in consumed]


def terminal_of(topology: Sequence[Dict[str, Any]]) -> str:
    """Return THE single terminal, or raise if the graph has more than one."""
    tails = terminals_of(topology)
    if len(tails) != 1:
        raise ValueError(f"expected exactly one terminal, got {tails}")
    return tails[0]


def _reachable_from(by_name: Dict[str, Dict[str, Any]], tail: str) -> set:
    seen: set = set()
    stack = [tail]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in by_name:
            continue
        seen.add(cur)
        stack.extend(i for i in (by_name[cur].get("inputs") or []) if i)
    return seen


def check_connected(topology: Sequence[Dict[str, Any]]) -> List[Check]:
    """Prove the topology is one connected graph feeding a single terminal.

    A multi-terminal graph is not merely "not single terminal" -- each extra
    terminal is a concrete dead end whose whole upstream cone never reaches the
    node that actually gets rendered. Each is named so the failure is
    actionable rather than a bare arity complaint.
    """
    by_name = {n["name"]: n for n in topology}
    tails = terminals_of(topology)
    checks: List[Check] = [Check(
        "single_terminal", len(tails) == 1,
        f"terminal is {tails[0]!r}" if len(tails) == 1
        else f"{len(tails)} terminals, expected 1: {tails}",
    )]
    if not tails:
        return checks

    # The primary terminal is the real sink if there is one, else the tail with
    # the largest upstream cone. Without the sink preference a same-size dead
    # end can win the tie and the error reads backwards.
    cones = {t: _reachable_from(by_name, t) for t in tails}
    primary = max(tails, key=lambda t: (by_name[t]["type"] in SINK_TYPES,
                                        len(cones[t]), -tails.index(t)))

    for t in tails:
        if t == primary:
            continue
        checks.append(Check(
            f"dead_end[{t}]", False,
            f"{t!r} ({by_name[t]['type']}) terminates nothing -- its cone "
            f"{sorted(cones[t])} never reaches the primary terminal {primary!r}",
        ))

    orphans = sorted(set(by_name) - cones[primary])
    checks.append(Check(
        "no_orphans", not orphans,
        f"nodes not reachable upstream of {primary!r}: {orphans}" if orphans
        else f"all {len(by_name)} nodes reachable from {primary!r}",
    ))
    return checks


def verify_static(tool: str, topology: Sequence[Dict[str, Any]],
                  catalog: Optional[Dict[str, Dict[str, Any]]] = None,
                  ) -> Dict[str, Any]:
    """Full STATIC verification for one tool."""
    checks = list(check_topology(topology, catalog)) + list(check_connected(topology))
    return result(tool, checks, tier="static",
                  extra={"node_count": len(topology)})


# ---------------------------------------------------------------------------
# LIVE tier — requires hou
# ---------------------------------------------------------------------------

def check_live_network(nodes: Sequence[Any]) -> List[Check]:
    """Prove a real emitted network is connected and composes.

    For every node: real ``min_inputs`` satisfied by real connections.
    For the terminal LOP: no errors, ``stage()`` resolves, prim count > 0.
    """
    if not HOU_AVAILABLE:  # pragma: no cover
        return [Check("hou_available", False, "hou not importable")]

    checks: List[Check] = []
    lops = [n for n in nodes if isinstance(n, hou.LopNode)]

    for n in nodes:
        nt = n.type()
        try:
            lo = nt.minNumInputs()
        except Exception as exc:  # pragma: no cover
            checks.append(Check(f"{n.name()}:arity_probe", False, repr(exc)))
            continue
        wired = sum(1 for i in n.inputs() if i is not None)
        checks.append(Check(
            f"{n.name()}:min_inputs_live", wired >= lo,
            f"{nt.name()} at {n.path()} needs >={lo}, has {wired} wired",
        ))

    if not lops:
        checks.append(Check("has_lop", False, "no hou.LopNode in emitted network"))
        return checks

    consumed = {i.path() for n in lops for i in n.inputs() if i is not None}
    tails = [n for n in lops if n.path() not in consumed]
    checks.append(Check("single_terminal_live", len(tails) == 1,
                        f"terminal LOPs: {[t.path() for t in tails]}"))
    if len(tails) != 1:
        return checks

    tail = tails[0]
    try:
        errs = [e for e in tail.errors()]
    except Exception as exc:  # pragma: no cover
        errs = [repr(exc)]
    checks.append(Check("terminal_no_errors", not errs,
                        f"{tail.path()} errors: {errs}"))

    try:
        stage = tail.stage()
    except Exception as exc:
        checks.append(Check("terminal_stage_resolves", False,
                            f"{tail.path()}.stage() raised {exc!r}"))
        return checks

    checks.append(Check("terminal_stage_resolves", stage is not None,
                        f"{tail.path()}.stage() -> {stage!r}"))
    if stage is None:
        return checks

    prims = list(stage.Traverse())
    checks.append(Check("stage_prim_count", len(prims) > 0,
                        f"{tail.path()} composed {len(prims)} prims"))
    return checks


def verify_live(tool: str, nodes: Sequence[Any]) -> Dict[str, Any]:
    """Full LIVE verification over an emitted network."""
    checks = check_live_network(nodes)
    return result(tool, checks, tier="live", extra={"node_count": len(nodes)})
