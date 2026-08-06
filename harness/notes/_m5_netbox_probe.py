"""M5 VERIFIED-RUNTIME probe: the NetworkBox surface on the live build.

The reconciler's ownership model (D1) is "membership in a network box IS
ownership". Everything that model rests on is probed here, on the running
interpreter, before a line of reconciler code is written:

  1. build string + the type of hou.node('/stage')
  2. box creation / lookup methods on the LOP network
  3. hou.NetworkBox instance surface
  4. destroy() -- does it take the contained-items flag, and what is the
     default? (a wrong default here deletes the artist's nodes)
  5. parentNetworkBox on a member node
  6. name-collision behaviour for BOTH createNode and createNetworkBox

Run:  hython harness/notes/_m5_netbox_probe.py
"""
import inspect
import json

import hou

out = {}
out["build"] = hou.applicationVersionString()

stage = hou.node("/stage")
out["stage_type"] = type(stage).__name__
out["stage_is_none"] = stage is None

out["stage_box_attrs"] = sorted(a for a in dir(stage) if "etworkBox" in a)

NB = getattr(hou, "NetworkBox", None)
out["hou_has_NetworkBox"] = NB is not None
if NB is not None:
    out["NetworkBox_attrs"] = sorted(a for a in dir(NB) if not a.startswith("_"))

probe_nodes = []
box = None
try:
    box = stage.createNetworkBox("SYN_PROBE_BOX")
    out["created_box_type"] = type(box).__name__
    out["created_box_name"] = box.name()

    n1 = stage.createNode("null", "syn_probe_n1")
    probe_nodes.append(n1)
    n2 = stage.createNode("null", "syn_probe_n2")
    probe_nodes.append(n2)

    add_fn = getattr(box, "addItem", None)
    out["has_addItem"] = callable(add_fn)
    if callable(add_fn):
        add_fn(n1)
        add_fn(n2)

    out["box_nodes"] = (sorted(n.name() for n in box.nodes())
                        if hasattr(box, "nodes") else "NO nodes()")
    if hasattr(box, "items"):
        out["box_items"] = sorted(str(i) for i in box.items())
        out["box_items_types"] = sorted({type(i).__name__ for i in box.items()})

    pnb = getattr(n1, "parentNetworkBox", None)
    out["n1_parentNetworkBox"] = (
        pnb().name() if callable(pnb) and pnb() is not None else None
    )

    fnb = getattr(stage, "findNetworkBox", None)
    out["findNetworkBox"] = (
        fnb("SYN_PROBE_BOX").name()
        if callable(fnb) and fnb("SYN_PROBE_BOX") is not None else None
    )
    out["networkBoxes_names"] = sorted(b.name() for b in stage.networkBoxes())

    # name collision: a SECOND box asking for the same name
    box2 = stage.createNetworkBox("SYN_PROBE_BOX")
    out["second_box_name_drift"] = box2.name()
    box2.destroy()

    for label, obj in (("NetworkBox.destroy", getattr(NB, "destroy", None)),
                       ("NetworkBox.removeItem", getattr(NB, "removeItem", None)),
                       ("NetworkBox.addItem", getattr(NB, "addItem", None)),
                       ("NetworkBox.setName", getattr(NB, "setName", None)),
                       ("NetworkBox.nodes", getattr(NB, "nodes", None)),
                       ("NetworkBox.fitAroundContents",
                        getattr(NB, "fitAroundContents", None)),
                       ("LopNetwork.createNetworkBox",
                        getattr(type(stage), "createNetworkBox", None))):
        if obj is None:
            out[label + "__sig"] = "ABSENT"
            continue
        try:
            out[label + "__sig"] = str(inspect.signature(obj))
        except Exception as e:
            out[label + "__sig"] = "unavailable: %s" % e
        doc = getattr(obj, "__doc__", None)
        if doc:
            out[label + "__doc"] = doc.strip().splitlines()[0][:220]

    # THE load-bearing question: does destroy() take the members with it?
    box.destroy()
    box = None
    out["after_box_destroy_nodes_alive"] = [
        (n.name() if n is not None else None)
        for n in (stage.node("syn_probe_n1"), stage.node("syn_probe_n2"))
    ]
    out["after_box_destroy_boxes"] = sorted(b.name() for b in stage.networkBoxes())

    b3 = stage.createNetworkBox("SYN_PROBE_A")
    b4 = stage.createNetworkBox("SYN_PROBE_B")
    try:
        b4.setName("SYN_PROBE_A")
        out["setName_collision"] = "allowed -> %s" % b4.name()
    except Exception as e:
        out["setName_collision"] = "%s: %s" % (type(e).__name__, e)
    b3.destroy()
    b4.destroy()

    dup = stage.createNode("null", "syn_probe_n1")
    out["createNode_dup_name_result"] = dup.name()
    dup.destroy()

finally:
    if box is not None:
        try:
            box.destroy()
        except Exception:
            pass
    for n in reversed(probe_nodes):
        try:
            n.destroy()
        except Exception:
            pass
    for b in stage.networkBoxes():
        if b.name().startswith("SYN_PROBE"):
            try:
                b.destroy()
            except Exception:
                pass

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps(out, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
