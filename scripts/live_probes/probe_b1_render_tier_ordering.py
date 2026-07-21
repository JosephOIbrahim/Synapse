"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"         scripts/live_probes/probe_b1_render_tier_ordering.py

B1: proves a ground plane and shadow catcher wire UPSTREAM of the render
ROP against real Houdini nodes. Exit 0 = correct chain.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "python"))

import hou  # noqa: E402
from synapse.server.handlers_solaris_assemble import (  # noqa: E402
    SolarisAssembleMixin, _SOLARIS_NODE_ORDER, _UNRANKED_RANK,
)


class _Harness(SolarisAssembleMixin):
    """Bare host for the mixin -- no transport, no server."""


def build_scene():
    stage = hou.node("/stage")
    for child in list(stage.children()):
        child.destroy()
    # An existing, correctly-wired spine: sopcreate -> karmarendersettings -> rop
    geo = stage.createNode("sopcreate", "asset")
    krs = stage.createNode("karmarendersettings", "rendersettings")
    rop = stage.createNode("usdrender_rop", "render")
    krs.setInput(0, geo)
    rop.setInput(0, krs)
    # ...and the two unwired nodes the recon predicted would land after the ROP.
    stage.createNode("plane", "ground")
    stage.createNode("shadowcatcher", "catcher")
    return stage, rop


def main():
    stage, rop = build_scene()
    result = _Harness()._handle_solaris_assemble_chain({
        "mode": "all", "parent": "/stage",
    })
    chain = result["chain"]
    print("BUILD           :", hou.applicationVersionString())
    print("CHAIN           :", " -> ".join(p.rsplit("/", 1)[-1] for p in chain))
    print("UNRANKED        :", result.get("unranked", []))
    print("OVERWRITTEN     :", result.get("overwritten", []))

    names = [p.rsplit("/", 1)[-1] for p in chain]
    failures = []
    if "render" not in names:
        failures.append("render ROP missing from chain")
    else:
        rop_i = names.index("render")
        for ground in ("ground", "catcher"):
            if ground not in names:
                failures.append("%s never wired into the chain" % ground)
            elif names.index(ground) > rop_i:
                failures.append(
                    "%s at index %d is DOWNSTREAM of the ROP at %d -- B1 live"
                    % (ground, names.index(ground), rop_i))

    # The wiring must actually be real, not just an ordering claim.
    for node in stage.children():
        if node.type().name().split("::")[0] == "plane":
            if not node.outputs():
                failures.append("plane has no output connection")

    print()
    print("rank(plane)     :", _SOLARIS_NODE_ORDER.get("plane"))
    print("rank(unranked)  :", _UNRANKED_RANK)
    print("rank(rop)       :", _SOLARIS_NODE_ORDER["usdrender_rop"])
    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("PASS: ground plane + shadow catcher both wired upstream of the ROP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
