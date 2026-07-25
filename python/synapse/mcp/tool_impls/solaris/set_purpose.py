"""
synapse_solaris_set_purpose — RELAY-SOLARIS Phase 3

Sets USD purpose on geometry within a Component Builder.
Maps purpose names to Component Geometry output connections.

Source pattern: SOLARIS_P3_PURPOSE_SYSTEM
Atomic: undo-wrapped.

Idempotent (SR1 seam fix): the tool keeps ONE `configureprimitive` per
(component, prim_path), identified by its own provenance stamp plus its
`primpattern`. A repeat call updates that node IN PLACE and reports
``unchanged`` when the value does not move. Creation happens only when no
stamped node exists, and the new node is inserted at the DOWNSTREAM end of the
chain (directly upstream of the component's sink) so the last write is the one
that composes.
"""

from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

try:
    from synapse.core.errors import NodeNotFoundError, HoudiniUnavailableError, ValidationError
except ImportError:
    class ValidationError(ValueError): pass
    class NodeNotFoundError(ValueError):
        def __init__(self, path, suggestion=""): super().__init__(f"Node not found: {path}")
    class HoudiniUnavailableError(RuntimeError):
        def __init__(self): super().__init__("Houdini unavailable")


_SOURCE_PATTERN = "SOLARIS_P3_PURPOSE_SYSTEM"
_TOOL_NAME = "synapse_solaris_set_purpose"

# Purpose → Component Geometry output name mapping
PURPOSE_OUTPUT_MAP = {
    "render": "default",
    "proxy": "proxy",
    "simproxy": "sim proxy",
}

# F7. VERIFIED-RUNTIME on 22.0.368: `componentgeometry` exposes NO `purpose`
# parm (57 parms enumerated, absent) — the old code's `geo_node.parm("purpose")`
# branch was permanently dead and the fallback lied. The real authoring
# mechanism is the `configureprimitive` LOP (singular; `configureprimitives` is
# a PHANTOM type), which carries `setpurpose` + `purpose`. Readback via
# UsdGeom.Imageable(prim).GetPurposeAttr() confirmed end-to-end.
#
# USD allows exactly these purpose tokens.
USD_PURPOSE_TOKENS = ("default", "render", "proxy", "guide")

# Our purpose vocabulary → the USD token authored on the prim.
PURPOSE_USD_TOKEN_MAP = {
    "render": "render",
    "proxy": "proxy",
    "simproxy": "guide",
}


def _stamp_provenance(node, info: Dict[str, Any]) -> None:
    try:
        node.setUserData("synapse:tool", info.get("tool", _TOOL_NAME))
        node.setUserData("synapse:source_pattern", info.get("source_pattern", _SOURCE_PATTERN))
        node.setUserData("synapse:reasoning", info.get("reasoning", ""))
    except Exception:
        pass


def _infer_prim_path(comp, geo_node) -> Optional[str]:
    """Best-effort target prim path, read off the geometry node's own stage.

    Asking the geometry what it actually authored beats guessing from names.
    VERIFIED-RUNTIME 22.0.368: a bare `componentgeometry` authors `/ASSET` and
    `/ASSET/geo`, so the top-level prim is the right purpose target.

    Falls back to the componentoutput's `rootprim`. Returns None when neither
    resolves — the caller then reports `noop` rather than claiming a purpose it
    never authored.
    """
    try:
        stage = geo_node.stage()
    except Exception:
        stage = None
    if stage is not None:
        for prim in stage.GetPseudoRoot().GetChildren():
            name = prim.GetName()
            if name == "HoudiniLayerInfo":
                continue
            return str(prim.GetPath())

    for child in comp.children():
        if "componentoutput" not in child.type().name().lower():
            continue
        p = child.parm("rootprim")
        if p is None:
            continue
        try:
            val = p.evalAsString().strip()
        except Exception:
            continue
        if val:
            return val if val.startswith("/") else f"/{val}"
    return None


def _stamped_configures(comp):
    """Every ``configureprimitive`` inside ``comp`` that this tool authored.

    Identity is *provenance*, not node name: names drift (Houdini uniquifies
    ``purpose_render`` into ``purpose_render1``) and a name-based match is what
    let three nodes stack up in the first place.
    """
    for child in comp.children():
        try:
            if (child.type().name() == "configureprimitive"
                    and child.userData("synapse:tool") == _TOOL_NAME):
                yield child
        except Exception:
            continue


def _find_stamped_configure(comp, prim_path: str):
    """This tool's existing configureprimitive targeting ``prim_path``, if any."""
    for child in _stamped_configures(comp):
        try:
            pp = child.parm("primpattern")
            if pp is not None and pp.evalAsString().strip() == prim_path:
                return child
        except Exception:
            continue
    return None


def _insert_after(anchor, cfg) -> None:
    """Splice ``cfg`` directly downstream of ``anchor``, stealing its consumers."""
    cfg.setInput(0, anchor)
    for consumer in anchor.outputs():
        if consumer.path() == cfg.path():
            continue
        for idx, src in enumerate(consumer.inputs()):
            if src is not None and src.path() == anchor.path():
                consumer.setInput(idx, cfg)


def _insert_downstream(comp, cfg, geo_node) -> None:
    """Seat ``cfg`` downstream of every purpose node this tool already placed.

    The pre-fix code always spliced at the geometry end, so each new node
    landed UPSTREAM of the previous one and the FIRST purpose ever set was the
    one that composed — while the call reported the new value. Anchoring on the
    downstream-most stamped node instead makes the last write the winning one.

    VERIFIED-RUNTIME 22.0.368 — why not simply splice directly above the
    ``componentoutput`` sink: ``componentoutput`` restructures the asset
    (``/ASSET`` -> ``/<rootprim>``) and does NOT carry the authored
    ``purpose`` through, so a node seated there authors into a prim the sink
    discards. The purpose must be authored upstream of the sink. That the sink
    drops it at all is a SEPARATE finding, recorded not fixed here — see
    ``harness/notes/sr1_seam_probe.py``.
    """
    others = [n for n in _stamped_configures(comp) if n.path() != cfg.path()]
    if others:
        consumed = {i.path() for n in others for i in n.inputs() if i is not None}
        tail = next((n for n in others if n.path() not in consumed), others[-1])
        _insert_after(tail, cfg)
        return
    _insert_after(geo_node, cfg)


def validate(params: Dict) -> None:
    """Validate parameters."""
    component_path = params.get("component_path")
    if not component_path:
        raise ValidationError("component_path is required")
    purpose = params.get("purpose")
    if purpose not in PURPOSE_OUTPUT_MAP:
        raise ValidationError(
            f"purpose must be one of {list(PURPOSE_OUTPUT_MAP.keys())}, got '{purpose}'"
        )


def plan(params: Dict) -> List[Dict[str, Any]]:
    """Return planned operations."""
    component_path = params.get("component_path", "/stage/component")
    geometry_name = params.get("geometry_name", "")
    purpose = params.get("purpose", "render")

    return [
        {
            "op": "set_purpose",
            "component_path": component_path,
            "geometry_name": geometry_name,
            "purpose": purpose,
            "output_name": PURPOSE_OUTPUT_MAP.get(purpose, "default"),
        },
        {
            "op": "stamp_provenance",
            "tool": _TOOL_NAME,
            "source_pattern": _SOURCE_PATTERN,
        },
    ]


def execute(params: Dict) -> Dict:
    """Execute purpose assignment."""
    if not HOU_AVAILABLE:
        raise HoudiniUnavailableError()

    validate(params)

    component_path = params["component_path"]
    geometry_name = params.get("geometry_name", "")
    purpose = params["purpose"]
    output_name = PURPOSE_OUTPUT_MAP[purpose]

    comp = hou.node(component_path)
    if comp is None:
        raise NodeNotFoundError(component_path, suggestion="Check component path")

    # Find Component Geometry node
    geo_node = None
    for child in comp.children():
        tname = child.type().name().lower()
        if "componentgeometry" in tname:
            if geometry_name:
                if geometry_name in child.name():
                    geo_node = child
                    break
            else:
                geo_node = child
                break

    if geo_node is None:
        return {
            "status": "not_found",
            "message": f"No componentgeometry node found in {component_path}",
        }

    # Which prim are we authoring onto? Explicit beats guessing.
    prim_path = params.get("prim_path") or _infer_prim_path(comp, geo_node)
    if not prim_path:
        # Law 3: nothing was authored, so nothing is claimed.
        return {
            "status": "noop",
            "geometry_path": geo_node.path(),
            "purpose": purpose,
            "reason": (
                "cannot determine the target prim path — pass `prim_path` "
                "explicitly, or give the component a componentoutput node "
                "with a 'name' parameter"
            ),
        }

    usd_token = PURPOSE_USD_TOKEN_MAP[purpose]

    with hou.undos.group(f"SYNAPSE: Set purpose '{purpose}'"):
        existing = _find_stamped_configure(comp, prim_path)
        cfg = existing if existing is not None else comp.createNode(
            "configureprimitive", f"purpose_{purpose}")
        pattern_parm = cfg.parm("primpattern")
        set_parm = cfg.parm("setpurpose")
        value_parm = cfg.parm("purpose")
        if pattern_parm is None or set_parm is None or value_parm is None:
            raise ValidationError(
                "configureprimitive is missing setpurpose/purpose/primpattern "
                f"on this build ({hou.applicationVersionString()}) — "
                "purpose cannot be authored"
            )
        # Read BEFORE writing: "unchanged" has to be decided against the node's
        # prior state, not against the value we are about to set (Law 1).
        try:
            was_enabled = bool(set_parm.eval())
            was_token = value_parm.evalAsString()
        except Exception:
            was_enabled, was_token = False, None
        already = existing is not None and was_enabled and was_token == usd_token

        pattern_parm.set(prim_path)
        set_parm.set(1)
        value_parm.set(usd_token)

        if existing is None:
            # Wire it at the downstream end so the last write is the one that
            # composes to the terminal.
            _insert_downstream(comp, cfg, geo_node)
        elif not already:
            # Keep the node name describing what it now authors.
            try:
                cfg.setName(f"purpose_{purpose}", unique_name=True)
            except Exception:
                pass

        _stamp_provenance(cfg, {
            "tool": _TOOL_NAME,
            "source_pattern": _SOURCE_PATTERN,
            "reasoning": (
                f"Authored USD purpose '{usd_token}' on {prim_path} via "
                f"configureprimitive (output convention: {output_name})"
            ),
        })

        return {
            # Law 3: three distinct things happened, three distinct words.
            "status": ("unchanged" if already
                       else "updated" if existing is not None else "set"),
            "geometry_path": geo_node.path(),
            "configure_node": cfg.path(),
            "prim_path": prim_path,
            "purpose": purpose,
            "usd_purpose": usd_token,
        }
