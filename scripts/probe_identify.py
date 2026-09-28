"""hython probe for Identify (BP11-IDCORE). Run: hython scripts/probe_identify.py

Live checks on Houdini 22.0.400 that unit tests on system Python cannot make:

* build the M0 seven-node SOP chain, compose real bubbles, show them
* one undo group per show (``hou.undos.undoLabels()``)
* save with the BeforeSave/AfterSave callbacks installed, reopen, assert the
  saved .hip has zero sentinel lines on disk (rule 4)
* time the main-thread apply for 60 nodes against the 100 ms starting target

Every number is printed with its producer path. Exit code is 0 only when every
assertion holds; a miss prints a FINDING and exits non-zero (never hidden).
"""
import os
import sys
import time
import tempfile
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_PYTHON = os.path.join(os.path.dirname(_HERE), "python")
if _PYTHON not in sys.path:
    sys.path.insert(0, _PYTHON)

import hou  # noqa: E402


def _ensure_corpus():
    """Point at the SideFX corpus so live summaries resolve.

    A worktree usually has no ``.synapse/sidefx_library.json`` of its own (it
    lives in the checkout the worktree was cut from), so walk up to the first
    ancestor that has one and export its root. Without this the bubbles are
    still valid ('- not in library'), but the library path goes unexercised.
    """
    from synapse.cognitive.tools import sidefx_library as sl
    import json
    if os.environ.get(sl.ROOT_ENV):
        return "env"
    here = os.path.abspath(__file__)
    parent = os.path.dirname(here)
    while True:
        cfg = os.path.join(parent, ".synapse", "sidefx_library.json")
        if os.path.exists(cfg):
            try:
                root = json.loads(open(cfg, encoding="utf-8").read()).get("root")
                if root:
                    os.environ[sl.ROOT_ENV] = root
                    return cfg
            except Exception:
                pass
        nxt = os.path.dirname(parent)
        if nxt == parent:
            return None
        parent = nxt


print("CORPUS_CONFIG", _ensure_corpus())

from synapse.identify import facts as F  # noqa: E402
from synapse.identify import library as L  # noqa: E402
from synapse.identify import compose as C  # noqa: E402
from synapse.identify import apply as A  # noqa: E402

FAIL = []


def check(label, ok, detail=""):
    tag = "OK" if ok else "FINDING"
    print(f"[{tag}] {label}: {detail}")
    if not ok:
        FAIL.append(label)


def build_chain():
    obj = hou.node("/obj")
    old = obj.node("identify_probe")
    if old:
        old.destroy()
    geo = obj.createNode("geo", "identify_probe")
    nodes = []

    def mk(t, name, inp=None, idx=0):
        n = geo.createNode(t, name)
        if inp is not None:
            n.setInput(idx, inp)
        nodes.append(n)
        return n

    box = mk("box", "box1")
    bev = mk("polybevel", "polybevel1", box)
    noi = mk("attribnoise", "attribnoise1", bev)
    sct = mk("scatter", "scatter1", noi)
    sph = mk("sphere", "sphere1")
    cpy = mk("copytopoints", "copytopoints1", sph)
    cpy.setInput(1, sct)
    out = mk("null", "OUT")
    out.setInput(0, cpy)
    bev.parm("offset").set(0.07)
    sct.parm("npts").set(250)
    geo.layoutChildren()
    for n in nodes:
        try:
            n.cook(force=True)
        except Exception:
            pass
    return geo, nodes


def build_lop_chain():
    """A LOP chain (BP11-SALIENCE T5): sphere 'ball' + cube 'box' -> merge 'both'.

    lastModifiedPrims() on the merge should report both prim paths, so the merge
    bubble's Here line reads 'writes /ball (+1)' (paths sorted; first + count-1).
    """
    stage = hou.node("/stage")
    old = stage.node("identify_lop_probe")
    if old:
        old.destroy()
    top = stage.createNode("subnet", "identify_lop_probe")
    ball = top.createNode("sphere", "ball")
    box = top.createNode("cube", "box")
    merge = top.createNode("merge", "both")
    merge.setInput(0, ball)
    merge.setInput(1, box)
    top.layoutChildren()
    for n in (ball, box, merge):
        try:
            n.cook(force=True)
        except Exception:
            pass
    return merge


def bubble_for(node):
    f = F.node_facts(node)
    text, source = L.summarize(f.get("help_url"), f.get("hda_help"))
    f["summary"], f["summary_source"] = text, source
    return f, C.compose(f)


def main():
    print("VERSION", hou.applicationVersionString())

    geo, nodes = build_chain()

    items = []
    polybevel_here = None
    for n in nodes:
        f, lines = bubble_for(n)
        items.append((n, lines))
        if n.name() == "polybevel1":
            polybevel_here = lines[1] if len(lines) > 1 else None
        print("BUBBLE", n.name(), "src=", f["summary_source"], "|", " // ".join(lines))

    # PolyBevel: exactly one Here entry, its label, no ramp internal (acceptance).
    check("polybevel one Here entry (offset, no ramp internal)",
          polybevel_here is not None and "," not in polybevel_here
          and "ramp" not in polybevel_here.lower(),
          f"here={polybevel_here!r}")

    # LOP writes line (BP11-SALIENCE T5): the merge bubble names the prims it wrote.
    merge = build_lop_chain()
    lf, llines = bubble_for(merge)
    lop_here = llines[1] if len(llines) > 1 else None
    print("BUBBLE", merge.name(), "lop_writes=", lf.get("lop_writes"),
          "|", " // ".join(llines))
    check("LOP merge Here line reads 'writes /ball (+1)'",
          lop_here == "writes /ball (+1)",
          f"here={lop_here!r} (producer: build_lop_chain + facts._lop_writes)")

    A.install_save_callbacks()

    before = list(hou.undos.undoLabels())
    A.show(items)
    after = list(hou.undos.undoLabels())
    shown_ct = sum(1 for n in nodes if A.SENTINEL in (n.comment() or ""))
    check("seven bubbles shown", shown_ct == 7, f"{shown_ct}/7 comments carry the sentinel")
    new_groups = after.count(A.UNDO_LABEL) - before.count(A.UNDO_LABEL)
    check("one undo group per show", new_groups == 1,
          f"undoLabels gained {new_groups} '{A.UNDO_LABEL}' entr(y/ies)")

    # Save with callbacks installed -> disk must be sentinel-free; reopen proves it.
    hip = os.path.join(tempfile.gettempdir(), "synapse_identify_probe.hip")
    hou.hipFile.save(hip)
    reshown = sum(1 for n in nodes if A.SENTINEL in (n.comment() or ""))
    check("AfterSave re-applied on screen", reshown == 7,
          f"{reshown}/7 sentinels back after save")

    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hipFile.load(hip, suppress_save_prompt=True, ignore_load_warnings=True)
    disk_sentinels = 0
    for n in hou.node("/obj/identify_probe").allSubChildren():
        if A.SENTINEL in (n.comment() or ""):
            disk_sentinels += 1
    check("zero sentinels on disk after reopen", disk_sentinels == 0,
          f"{disk_sentinels} sentinel lines survived the save (producer: hipFile.save+reopen)")

    # Timing: main-thread apply for 60 nodes vs the 100 ms starting target.
    timing_geo = hou.node("/obj").createNode("geo", "identify_timing")
    many = [timing_geo.createNode("null", f"n{i}") for i in range(60)]
    A._reset_state()
    timing_items = [(n, ["Null", "Bypassed off"]) for n in many]
    t0 = time.perf_counter()
    A.show(timing_items)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    print(f"APPLY_MS 60 nodes = {elapsed_ms:.1f} ms (target 100; producer: apply.show timed)")
    check("60-node apply under 100 ms target", elapsed_ms <= 100.0,
          f"{elapsed_ms:.1f} ms (a miss is a finding, tune at the GUI gate)")

    try:
        os.remove(hip)
    except OSError:
        pass

    if FAIL:
        print("PROBE_RESULT FAIL:", ", ".join(FAIL))
        return 1
    print("PROBE_RESULT PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("PROBE_RESULT ERROR")
        sys.exit(2)
