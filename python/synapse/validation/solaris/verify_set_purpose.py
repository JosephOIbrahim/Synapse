"""
RELAY-SOLARIS L2 — wiring verifier for ``synapse_solaris_set_purpose``.

Source of truth: ``synapse/mcp/tools/solaris/set_purpose.py`` ``execute()``.

This tool creates no nodes; it mutates a component. So "is the emitted network
connected" is verified against the network it must OPERATE ON: a component
whose componentgeometry -> componentmaterial -> componentoutput chain composes.
If that host chain is not connected, set_purpose has nothing valid to act on.

CORRECTNESS DEFECT THIS VERIFIER PINS (FINDING F7, not fixed here per gate):
``execute()`` looks for a ``purpose`` parm on the componentgeometry node. If
that parm is absent it falls through to a second ``return`` that still reports
``status="set"`` -- with only a ``note`` string to distinguish it. The caller
cannot tell "purpose applied" from "purpose silently not applied". The tool's
own comment concedes the mechanism is unverified ("may need live Houdini
verification"). ``PURPOSE_PARM_IS_LIVE`` records the live answer for 22.0.368.
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "synapse_solaris_set_purpose"

#: The USD purposes the tool claims to support, and the componentgeometry
#: output each maps to. Mirrors ``set_purpose.PURPOSE_OUTPUT_MAP``.
EXPECTED_PURPOSE_MAP = {
    "render": "default",
    "proxy": "proxy",
    "simproxy": "sim proxy",
}

#: The host component chain set_purpose must operate on.
EXPECTED_TOPOLOGY: List[Dict[str, Any]] = [
    {"name": "geo_asset", "type": "componentgeometry", "inputs": []},
    {"name": "mat_asset", "type": "componentmaterial", "inputs": ["geo_asset"]},
    {"name": "output_asset", "type": "componentoutput", "inputs": ["mat_asset"]},
]

#: The status string the tool returns on BOTH the applied and the
#: not-applied path. Pinned so a fix that disambiguates them fails this.
AMBIGUOUS_SUCCESS_STATUS = "set"


def verify_static(catalog=None) -> Dict[str, Any]:
    """The host chain must be a connected, arity-valid component. PASSes."""
    return common.verify_static(TOOL, EXPECTED_TOPOLOGY, catalog)


def verify_purpose_map() -> Dict[str, Any]:
    """The tool's purpose map must match this verifier's declared contract."""
    checks: List[common.Check] = []
    try:
        tool = common.load_tool("set_purpose")
        actual = dict(tool.PURPOSE_OUTPUT_MAP)
    except Exception as exc:
        return common.result(TOOL + ":purpose_map",
                             [common.Check("load_tool", False, repr(exc))],
                             tier="static")

    checks.append(common.Check(
        "purpose_map_matches", actual == EXPECTED_PURPOSE_MAP,
        f"tool map {actual} vs expected {EXPECTED_PURPOSE_MAP}",
    ))
    for purpose in EXPECTED_PURPOSE_MAP:
        checks.append(common.Check(
            f"purpose[{purpose}]:known", purpose in actual,
            f"{purpose!r} {'present' if purpose in actual else 'MISSING'}",
        ))
    return common.result(TOOL + ":purpose_map", checks, tier="static")


def silent_fallback_check() -> common.Check:
    """Pin F7: both return paths report the same status string."""
    import inspect

    tool = common.load_tool("set_purpose")
    src = inspect.getsource(tool.execute)
    occurrences = src.count(f'"status": "{AMBIGUOUS_SUCCESS_STATUS}"')
    return common.Check(
        "status_unambiguous", occurrences <= 1,
        f'execute() returns status="{AMBIGUOUS_SUCCESS_STATUS}" on '
        f"{occurrences} distinct paths "
        f"({'ok' if occurrences <= 1 else 'F7: applied and not-applied are indistinguishable'})",
    )


def live_purpose_parm_present(lopnet) -> Dict[str, Any]:
    """Live: does componentgeometry actually expose a ``purpose`` parm?"""
    node = lopnet.createNode("componentgeometry", "l2_purpose_probe")
    try:
        parm = node.parm("purpose")
        names = sorted(p.name() for p in node.parms())
        check = common.Check(
            "componentgeometry_has_purpose_parm", parm is not None,
            f"parm('purpose') -> {parm!r}; candidates="
            f"{[n for n in names if 'purpose' in n.lower()]}",
        )
        return common.result(TOOL + ":purpose_parm", [check], tier="live")
    finally:
        node.destroy()


def verify_live(lopnet) -> Dict[str, Any]:
    """Live: host chain composes, and record whether the parm mechanism exists."""
    geo = lopnet.createNode("componentgeometry", "l2_geo")
    mat = lopnet.createNode("componentmaterial", "l2_mat")
    out = lopnet.createNode("componentoutput", "l2_out")
    mat.setInput(0, geo)
    out.setInput(0, mat)
    res = common.verify_live(TOOL, [geo, mat, out])
    res["purpose_parm"] = live_purpose_parm_present(lopnet)
    return res
