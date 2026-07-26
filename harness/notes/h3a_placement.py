"""H3a pass 2 — class-placement resolution. Read-only.

WHY THIS EXISTS (a probe defect caught in-run, recorded rather than hidden):

Pass 1 (``h3a_probe.py``) resolves a dotted name by walking getattr from the root.
``hou.Node.cook`` came back ABSENT -- yet ``node.cook()`` demonstrably works in the
tree. Both facts are true: HOM splits its node API across a class hierarchy, and the
attribute lives on a SUBCLASS of ``hou.Node``. A class-level probe that asks the wrong
class manufactures a phantom.

That is SYNAPSE's #1 documented failure class arriving from the direction of the
instrument instead of the model. So pass 2 asks a different question:

    given an attribute name, WHICH hou classes actually carry it,
    and is the class the tree calls it on one of them?

Failure condition (Law 1): the positive control asserts ``children`` is found on
``hou.Node``; the negative control asserts a synthetic attribute name is found on ZERO
classes. If the scan reports the synthetic name anywhere, or reports ``children``
nowhere, the scan is broken and its output is UNINTERPRETABLE.

Producer path (Law 2): this file.
"""

from __future__ import annotations

import json
import sys

TARGET_ATTRS = [
    # ABSENT on hou.Node in pass 1 -- resolve where they really live.
    "getPDGGraphContext",
    "getPDGNode",
    "cook",
    "needsToCook",
    "cookCount",
    "isTimeDependent",
    # present on hou.Node in pass 1 -- included as in-band controls
    "children",
    "allSubChildren",
    "type",
    # the render surface
    "render",
    "dirtyAllTasks",
    "cookWorkItems",
]

# Substring patterns for the "does ANY interrupt affordance exist" question.
PATTERNS = ["cancel", "abort", "interrupt", "kill", "stop", "render", "cook", "background", "pdg", "task"]

FOCUS_CLASSES = [
    "Node", "OpNode", "RopNode", "TopNode", "SopNode", "LopNode", "ObjNode",
    "CopNode", "DopNode", "ChopNode", "NetworkMovableItem",
]

POSITIVE_CONTROL_ATTR = "children"
NEGATIVE_CONTROL_ATTR = "zzz_h3a_placement_control_must_not_exist"


def _hou_classes(hou):
    out = {}
    for name in dir(hou):
        try:
            obj = getattr(hou, name)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, type):
            out[name] = obj
    return out


def _classes_with(classes, attr):
    hits = []
    for name, cls in sorted(classes.items()):
        try:
            if hasattr(cls, attr):
                hits.append(name)
        except Exception:  # noqa: BLE001
            continue
    return hits


def _own_vs_inherited(cls, attr):
    """Is the attribute defined on the class itself or inherited?"""
    try:
        if attr in vars(cls):
            return "own"
        for base in cls.__mro__[1:]:
            if attr in vars(base):
                return "inherited:" + base.__name__
        return "present-but-unlocated"
    except Exception:  # noqa: BLE001
        return "unknown"


def main():
    import hou

    classes = _hou_classes(hou)

    pos_hits = _classes_with(classes, POSITIVE_CONTROL_ATTR)
    neg_hits = _classes_with(classes, NEGATIVE_CONTROL_ATTR)
    controls_ok = ("Node" in pos_hits) and (len(neg_hits) == 0)

    placement = {}
    for attr in TARGET_ATTRS:
        hits = _classes_with(classes, attr)
        placement[attr] = {
            "class_count": len(hits),
            "on_hou_Node": "Node" in hits,
            "focus": {
                c: (
                    _own_vs_inherited(classes[c], attr)
                    if (c in classes and hasattr(classes[c], attr))
                    else "ABSENT"
                )
                for c in FOCUS_CLASSES
                if c in classes
            },
            "all_classes": hits if len(hits) <= 40 else hits[:40] + ["...(%d more)" % (len(hits) - 40)],
        }

    mro = {}
    for c in FOCUS_CLASSES:
        if c in classes:
            try:
                mro[c] = [b.__name__ for b in classes[c].__mro__]
            except Exception:  # noqa: BLE001
                mro[c] = None

    # Pattern sweep: every name on the focus classes and on the hou module matching
    # any interrupt-ish pattern. This is what turns "I could not think of the right
    # spelling" into "here is the complete namespace and the spelling is not in it".
    sweep = {}
    for c in FOCUS_CLASSES:
        if c not in classes:
            continue
        try:
            names = dir(classes[c])
        except Exception:  # noqa: BLE001
            continue
        sweep["hou." + c] = {
            p: sorted(n for n in names if p in n.lower()) for p in PATTERNS
        }
    try:
        mod_names = dir(hou)
        sweep["hou"] = {p: sorted(n for n in mod_names if p in n.lower()) for p in PATTERNS}
    except Exception:  # noqa: BLE001
        pass

    try:
        import pdg

        sweep["pdg.GraphContext"] = {
            p: sorted(n for n in dir(pdg.GraphContext) if p in n.lower()) for p in PATTERNS
        }
        sweep["pdg.Scheduler"] = {
            p: sorted(n for n in dir(pdg.Scheduler) if p in n.lower()) for p in PATTERNS
        }
        sweep["pdg.WorkItem"] = {
            p: sorted(n for n in dir(pdg.WorkItem) if p in n.lower()) for p in PATTERNS
        }
        sweep["pdg"] = {p: sorted(n for n in dir(pdg) if p in n.lower()) for p in PATTERNS}
    except Exception as exc:  # noqa: BLE001
        sweep["pdg_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        import hdefereval

        sweep["hdefereval_full_dir"] = sorted(n for n in dir(hdefereval) if not n.startswith("__"))
    except Exception as exc:  # noqa: BLE001
        sweep["hdefereval_error"] = "%s: %s" % (type(exc).__name__, exc)

    rec = {
        "schema": "h3a_placement/v1",
        "producer": "harness/notes/h3a_placement.py",
        "houdini_build": hou.applicationVersionString(),
        "ui_available": bool(hou.isUIAvailable()),
        "hou_class_count": len(classes),
        "controls_ok": controls_ok,
        "controls": {
            "positive": {
                "attr": POSITIVE_CONTROL_ATTR,
                "expect": "found on hou.Node",
                "found_on_Node": "Node" in pos_hits,
                "class_count": len(pos_hits),
            },
            "negative": {
                "attr": NEGATIVE_CONTROL_ATTR,
                "expect": "found on zero classes",
                "hits": neg_hits,
            },
            "failure_condition": (
                "controls_ok is False if 'children' is not found on hou.Node, or if the "
                "synthetic attribute is found on any class. False => UNINTERPRETABLE."
            ),
        },
        "placement": placement,
        "mro": mro,
        "pattern_sweep": sweep,
    }
    return rec


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else None
    record = main()
    text = json.dumps(record, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    sys.exit(0 if record["controls_ok"] else 1)
