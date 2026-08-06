"""M5b probe 2 -- the NetworkBox EJECTION surface.

R-M5-3 overrides what M5 shipped: a node the artist dragged INTO the box that
the fixture does not declare must be REMOVED FROM THE BOX and LEFT ALIVE.

M5 established the box surface it used (create / destroy / addItem / nodes),
and the M5 resume token says not to re-probe those. ``removeItem`` is a call
M5 never made, so it is probed here before any code is written against it --
the brief's rule: if hou surprises you, dir() first.

Questions, each with the failure it would cause if assumed wrong:

  Q1  Does ``NetworkBox.removeItem`` exist on 22.0.368, and what is its
      signature? -> AttributeError mid-apply, inside the undo group, after
      deletions have already run.
  Q2  After removeItem, is the node still ALIVE in /stage? -> the whole point
      of the ruling; if removeItem destroys, eject IS delete.
  Q3  After removeItem, is the node still reported by box.nodes(recurse=False)?
      -> observe() would keep re-planning the same ejection forever and
      apply_fixture would never converge (residual_ops > 0), exactly the
      M5-F2 defect class.
  Q4  Does removeItem on a NON-member raise? -> the delete/eject loops must
      know whether they need a membership guard.
  Q5  Does box.fitAroundContents() after an ejection re-capture the node?
      -> a cosmetic call at the end of apply could silently undo the ejection.
  Q6  Are the node's AUTHORED properties (position, comment, parms, flags)
      untouched by the round trip? -> F-7's central claim.

    hython harness/notes/_m5b_eject_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "python") not in sys.path:
    sys.path.insert(0, str(REPO / "python"))

STAGE = "/stage"
BOX = "SYN_M5B_PROBE_BOX"


def stage_node():
    return hou.node(STAGE)


def reset():
    st = stage_node()
    for c in list(st.children()):
        try:
            c.destroy()
        except Exception:       # noqa: BLE001
            pass
    for b in list(st.networkBoxes()):
        try:
            b.destroy()
        except Exception:       # noqa: BLE001
            pass


def snap(node) -> dict:
    return {
        "name": node.name(),
        "type": node.type().name(),
        "position": [round(float(node.position()[0]), 6),
                     round(float(node.position()[1]), 6)],
        "comment": node.comment(),
        "bypass": bool(node.isBypassed()),
        "display": bool(node.isDisplayFlagSet()),
    }


def main() -> int:
    out = {"build": hou.applicationVersionString()}

    # -- Q1: the surface itself -------------------------------------------
    out["networkbox_dir"] = sorted(
        d for d in dir(hou.NetworkBox) if not d.startswith("_"))
    out["has_removeItem"] = hasattr(hou.NetworkBox, "removeItem")
    out["has_addItem"] = hasattr(hou.NetworkBox, "addItem")
    try:
        import inspect
        out["removeItem_signature"] = str(
            inspect.signature(hou.NetworkBox.removeItem))
    except Exception as e:      # noqa: BLE001
        out["removeItem_signature"] = "<ERR %s: %s>" % (type(e).__name__, e)

    reset()
    st = stage_node()
    box = st.createNetworkBox(BOX)
    inside = st.createNode("null", "syn_m5b_inside")
    inside.setPosition(hou.Vector2(7.5, 3.25))
    inside.setComment("artist owned - do not touch")
    outsider = st.createNode("null", "syn_m5b_outsider")
    box.addItem(inside)

    out["before"] = {
        "members": sorted(n.name() for n in box.nodes(recurse=False)),
        "inside": snap(inside),
    }

    # -- Q2 / Q3 / Q6: the round trip -------------------------------------
    try:
        box.removeItem(inside)
        out["removeItem_raised"] = None
    except Exception as e:      # noqa: BLE001
        out["removeItem_raised"] = "%s: %s" % (type(e).__name__, e)

    still_alive = st.node("syn_m5b_inside")
    out["after_remove"] = {
        "members": sorted(n.name() for n in box.nodes(recurse=False)),
        "node_still_in_stage": still_alive is not None,
        "stage_children": sorted(c.name() for c in st.children()),
        "authored": snap(still_alive) if still_alive is not None else None,
        "authored_unchanged": (snap(still_alive) == out["before"]["inside"]
                               if still_alive is not None else False),
    }

    # -- Q4: removeItem on a non-member -----------------------------------
    try:
        box.removeItem(outsider)
        out["removeItem_on_nonmember_raised"] = None
    except Exception as e:      # noqa: BLE001
        out["removeItem_on_nonmember_raised"] = "%s: %s" % (type(e).__name__, e)

    # -- Q5: does fitAroundContents re-capture it? ------------------------
    #    Deliberately place the ejected node INSIDE the box's rectangle first,
    #    which is the adversarial case: if membership were spatial rather than
    #    explicit, this is where the ejection would silently undo itself.
    survivor = st.createNode("null", "syn_m5b_keeper")
    box.addItem(survivor)
    if still_alive is not None:
        still_alive.setPosition(survivor.position())
    try:
        box.fitAroundContents()
        out["fitAroundContents_raised"] = None
    except Exception as e:      # noqa: BLE001
        out["fitAroundContents_raised"] = "%s: %s" % (type(e).__name__, e)
    out["after_fit"] = {
        "members": sorted(n.name() for n in box.nodes(recurse=False)),
        "ejected_recaptured": "syn_m5b_inside" in
                              [n.name() for n in box.nodes(recurse=False)],
    }

    reset()
    print(json.dumps(out, indent=2, sort_keys=True, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
