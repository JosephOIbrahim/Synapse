"""Live H22 hython round-trip for relationship-aware get/set_usd_attribute.

Reproduces N-3's verified chain (docs/reviews/h22-now-probes-2026-07-16.md):
a Karma light + karmablockerlightfilter + karmarendersettings, with the
light's ``light:filters`` relationship assigned to the blocker, then rounds
that one real relationship through the SYNAPSE handlers:

  * ``_handle_get_usd_attribute`` must return the blocker path as a
    ``property_kind == "relationship"`` target list (pre-fix it RAISED); and
  * ``_handle_set_usd_attribute`` must re-author the targets via ``SetTargets``
    (pre-fix it silently no-op'd), verified by reading the cooked stage back.

Skip-guarded, following the repo's live-test convention (test_inspect_live.py):
runs ONLY when ``SYNAPSE_H22_LIVE=1`` is set inside a real Houdini 22 hython
session. CI never sets it, so the whole module is skipped there -- ``hou`` is
imported *inside* the test, never at collection time, so a headless collect is
always clean. All PROVISIONAL-headless per N-3 until reconfirmed on the live
bridge.

Run it (inside an H22 hython with the SYNAPSE package importable):
    set SYNAPSE_H22_LIVE=1
    hython -m pytest tests/test_usd_relationship_live.py -q -s
"""

import os

import pytest

_LIVE = os.environ.get("SYNAPSE_H22_LIVE") == "1"

pytestmark = pytest.mark.skipif(
    not _LIVE,
    reason="live H22 hython round-trip; set SYNAPSE_H22_LIVE=1 under real hython",
)


def _create_light(stage):
    """N-3 used light::2.0; fall back to bare `light` if the version drifts."""
    for tname in ("light::2.0", "light"):
        try:
            return stage.createNode(tname, "keylight")
        except Exception:
            continue
    raise RuntimeError("could not create a Karma light LOP (light::2.0 / light)")


def test_live_karma_light_filter_relationship_roundtrip():
    import hou

    from synapse.server.handlers import SynapseHandler

    stage = hou.node("/stage")
    if stage is None:
        stage = hou.node("/").createNode("lopnet", "stage_relprobe")

    light = _create_light(stage)
    blocker = stage.createNode("karmablockerlightfilter", "blocker")
    blocker.setInput(0, light)
    krs = stage.createNode("karmarendersettings", "krs")
    krs.setInput(0, blocker)

    # Assign the filter to the light via its parm (N-3: xn__lightfilters_lva).
    blocker_prim = "/blocker"
    parm = light.parm("xn__lightfilters_lva") or light.parm("lightfilters")
    assert parm is not None, "light has no light-filters parm to author through"
    parm.set(blocker_prim)
    krs.cook(force=True)

    # Discover the light prim carrying a populated light:filters relationship.
    composed = krs.stage()
    light_path = None
    for prim in composed.Traverse():
        rel = prim.GetRelationship("light:filters")
        if rel.IsValid() and rel.GetTargets():
            light_path = str(prim.GetPath())
            break
    assert light_path is not None, "no prim with a populated light:filters relationship"

    handler = SynapseHandler()

    # READ: pre-fix this RAISED ValueError. Now it returns the target list.
    read = handler._handle_get_usd_attribute({
        "node": krs.path(),
        "prim_path": light_path,
        "usd_attribute": "light:filters",
    })
    assert read["property_kind"] == "relationship"
    assert read["type_name"] == "relationship"
    assert blocker_prim in read["value"]
    assert isinstance(read["value"], list)

    # WRITE: pre-fix this silently no-op'd. Now it authors via SetTargets.
    new_targets = [blocker_prim]
    set_res = handler._handle_set_usd_attribute({
        "node": krs.path(),
        "prim_path": light_path,
        "usd_attribute": "light:filters",
        "value": new_targets,
    })
    assert "cook_error" not in set_res, set_res.get("cook_error")

    # Read the authored relationship back off the downstream node's stage.
    authored = hou.node(set_res["created_node"])
    back = authored.stage()
    prim = back.GetPrimAtPath(light_path)
    rel = prim.GetRelationship("light:filters")
    assert rel.IsValid()
    assert blocker_prim in [str(t) for t in rel.GetTargets()]
