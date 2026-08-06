"""M5 probe #5: the runtime primitives the reconciler is about to call.

Every question here has a wrong answer that would ship a bug:

  Q1 Is the LOP display flag EXCLUSIVE? If setting it on B clears it on A,
     the planner's clear_display list is dead code that reports ops nobody
     performed (Law 3).
  Q2 Does hou.undos.group() work in headless hython, or does the invariant
     harness need a guard?
  Q3 How do we read a parm's authored value so a re-apply compares equal?
     eval() vs unexpandedString() diverge the moment a value contains '$'.
  Q4 node.position() shape, and does it round-trip through setPosition?
  Q5 node.inputs() padding, and does setInput(i, None) disconnect?
  Q6 Does destroying a node that is a box member leave the box intact?

Run:  hython harness/notes/_m5_runtime_probe.py
"""
import json

import hou

out = {"build": hou.applicationVersionString()}
stage = hou.node("/stage")

made = []
box = None
try:
    a = stage.createNode("camera", "m5_a"); made.append(a)
    b = stage.createNode("camera", "m5_b"); made.append(b)

    # --- Q1 display exclusivity ---
    a.setDisplayFlag(True)
    out["after_setA"] = {"a": a.isDisplayFlagSet(), "b": b.isDisplayFlagSet()}
    b.setDisplayFlag(True)
    out["after_setB"] = {"a": a.isDisplayFlagSet(), "b": b.isDisplayFlagSet()}
    out["display_is_exclusive"] = (not a.isDisplayFlagSet()) and b.isDisplayFlagSet()

    # --- Q2 undo group headless ---
    out["has_hou_undos"] = hasattr(hou, "undos")
    try:
        with hou.undos.group("M5 probe"):
            tmp = stage.createNode("null", "m5_undo_probe")
            tmp.destroy()
        out["undos_group"] = "ok"
    except Exception as e:
        out["undos_group"] = "%s: %s" % (type(e).__name__, e)
    try:
        out["undos_are_enabled"] = hou.undos.areEnabled()
    except Exception as e:
        out["undos_are_enabled"] = "%s: %s" % (type(e).__name__, e)

    # --- Q3 parm read-back ---
    p = a.parm("primpath")
    out["primpath_parm_present"] = p is not None
    if p is not None:
        out["primpath_default_eval"] = p.eval()
        out["primpath_default_unexpanded"] = p.unexpandedString()
        p.set("/cameras/camera")
        out["primpath_after_set_eval"] = p.eval()
        out["primpath_after_set_unexpanded"] = p.unexpandedString()
        tpl = p.parmTemplate()
        out["primpath_template_type"] = str(tpl.type())
        out["is_string_template"] = (tpl.type() == hou.parmTemplateType.String)
        # a value containing a variable: do eval and unexpanded diverge?
        p.set("$HIP/x")
        out["dollar_eval"] = p.eval()
        out["dollar_unexpanded"] = p.unexpandedString()
        p.set("/cameras/camera")

    # numeric parm read-back
    for cand in ("resx", "resolutionx", "iconscale"):
        np_ = a.parm(cand)
        if np_ is not None:
            out["numeric_parm"] = cand
            out["numeric_eval_type"] = type(np_.eval()).__name__
            out["numeric_template_type"] = str(np_.parmTemplate().type())
            break

    # --- Q4 position ---
    a.setPosition(hou.Vector2(0.0, -3.0))
    pos = a.position()
    out["position_type"] = type(pos).__name__
    out["position_tuple"] = [float(pos[0]), float(pos[1])]
    out["position_roundtrip_exact"] = (float(pos[0]) == 0.0 and float(pos[1]) == -3.0)

    # --- Q5 inputs ---
    b.setInput(0, a)
    ins = b.inputs()
    out["inputs_len"] = len(ins)
    out["inputs_repr"] = [(i.name() if i is not None else None) for i in ins]
    out["input_connectors_len"] = len(b.inputConnectors())
    b.setInput(0, None)
    out["inputs_after_disconnect"] = [
        (i.name() if i is not None else None) for i in b.inputs()
    ]

    # --- Q6 destroy a box member ---
    box = stage.createNetworkBox("M5_PROBE_BOX")
    box.addItem(a)
    box.addItem(b)
    out["box_before_destroy"] = sorted(n.name() for n in box.nodes())
    # NOTE (VERIFIED-RUNTIME): list.remove() on a destroyed hou.Node raises
    # hou.ObjectWasDeleted from Node.__eq__ -- drop the reference BEFORE
    # destroying, never after. The reconciler must not hold node handles
    # across a destroy pass.
    made = [n for n in made if n.name() != "m5_b"]
    b.destroy()
    out["box_after_member_destroy"] = sorted(n.name() for n in box.nodes())
    out["box_still_exists"] = stage.findNetworkBox("M5_PROBE_BOX") is not None

finally:
    if box is not None:
        try:
            box.destroy()
        except Exception:
            pass
    for n in reversed(made):
        try:
            n.destroy()
        except Exception:
            pass
    for bx in stage.networkBoxes():
        if bx.name().startswith("M5_PROBE"):
            try:
                bx.destroy()
            except Exception:
                pass

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps(out, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
