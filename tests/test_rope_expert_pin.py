"""Rope L5-5 — expert regression pin (safety net, Law L5).

Snapshot test: the RESOLVED expert manifest — region order, builders, widget
ids in order, visibility, collapse, stretch, prominence, defaults, overlay —
must equal the v5.42.0 structure recorded verbatim below. Any drift in the
expert manifest, the compositor's defaulting, or the region vocabulary fails
this test loudly. Pure data through ``compositor.resolve``; no Qt.

The literal is deliberately fully expanded (no helpers building it): the pin
must not share construction logic with the code it pins.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from synapse.panel import compositor
from synapse.panel.manifests import get_manifest

# The v5.42.0 expert surface, as resolve() emits it. Recorded 2026-08-03 from
# the shipped panel wiring: four regions in root-layout order, faces dominant
# (stretch 1), every widget visible / uncollapsed / standard prominence, no
# system-prompt overlay.
V5420_EXPERT_RESOLVED = {
    "profile": "expert",
    "system_prompt_overlay": "",
    "defaults": {
        "visible": True, "collapsed": False, "stretch": 0,
        "prominence": "standard",
    },
    "regions": [
        {
            "id": "rail", "builder": "_build_rail",
            "visible": True, "collapsed": False, "stretch": 0,
            "prominence": "standard",
            "widgets": [
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "mark"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "wordmark"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "header_status"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "author_token"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "token_meter"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "palette_hint"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "stop"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "connection_dot"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "connection_label"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "connect"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "corpus"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "activity_meter"},
            ],
        },
        {
            "id": "context_ribbon", "builder": "_build_context_ribbon",
            "visible": True, "collapsed": False, "stretch": 0,
            "prominence": "standard",
            "widgets": [
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "context_label"},
            ],
        },
        {
            "id": "mode_bar", "builder": "_build_mode_bar",
            "visible": True, "collapsed": False, "stretch": 0,
            "prominence": "standard",
            "widgets": [
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "chat_pill"},
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "token_pill"},
            ],
        },
        {
            "id": "faces", "builder": "_build_faces",
            "visible": True, "collapsed": False, "stretch": 1,
            "prominence": "standard",
            "widgets": [
                {"visible": True, "collapsed": False, "stretch": 0,
                 "prominence": "standard", "id": "faces_stack"},
            ],
        },
    ],
}


def test_expert_resolved_equals_v5420_snapshot():
    """The whole resolved plan, verbatim. Dict equality is recursive and the
    region/widget lists are order-sensitive — one comparison pins everything
    this net exists to catch."""
    assert compositor.resolve(get_manifest("expert")) == V5420_EXPERT_RESOLVED


def test_snapshot_orders_pinned_explicitly():
    """Redundant with the equality above by construction, but fails with a
    readable one-line diff when only ordering drifts."""
    plan = compositor.resolve(get_manifest("expert"))
    assert [r["id"] for r in plan["regions"]] == [
        "rail", "context_ribbon", "mode_bar", "faces"]
    assert {r["id"]: [w["id"] for w in r["widgets"]]
            for r in plan["regions"]} == {
        rid: wids for rid, wids in (
            (r["id"], [w["id"] for w in r["widgets"]])
            for r in V5420_EXPERT_RESOLVED["regions"])}
