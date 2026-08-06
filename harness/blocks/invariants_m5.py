"""M5 CRUCIBLE invariants -- F-1..F-5 for the BLOCKS reconciler.

Headless hython, the autoresearch run pattern: atomic artifact writes, a
DONE / FAILED sentinel written LAST, evidence that stands on its own.

    hython harness/blocks/invariants_m5.py
    hython harness/blocks/invariants_m5.py --out harness/blocks/runs/manual
    hython harness/blocks/invariants_m5.py --hip C:/Users/User/SYNAPSE

The invariants
--------------
  F-1  apply on a clean stage                  -> composed hash == baseline
  F-2  apply -> remove -> apply                -> same hash
  F-3  apply on an already-applied stage       -> ops == 0 AND hash unchanged
  F-4  artist node outside the box, no clash   -> apply succeeds, artist node
                                                  byte-untouched, box correct
  F-5  artist node named `camera` outside box  -> collision report, ZERO
                                                  mutations, stage signature
                                                  unchanged

Negative controls (Constitution Law 1: state the condition under which each
check fails, then prove it can). Four instruments are used above -- the
composed hash, the op count, the stage signature and the collision gate --
and each one is shown disagreeing with a deliberately wrong stage before any
of them is trusted to agree. A check that cannot fail is a decoration that
will later be cited as evidence.

$HIP pinning (VERIFIED-RUNTIME 2026-08-06, build 22.0.368)
----------------------------------------------------------
The committed baseline is NOT environment-free. karmarendersettings authors
``$HIP/render/<hipname>.<node>.####.exr`` into the composed stage, and $HIP
resolves to the process working directory for an unsaved scene. Run from this
worktree the same build yields 6552415d...; run from the main working tree it
yields the committed 8bb05761.... So the harness PINS $HIP via hou.putenv
rather than depending on where it was launched, and records the pinned value
in the evidence. The default is the MAIN working tree of this repository --
the environment the baseline was cut in. See for_ruling in the M5 receipt: the
fixture records no $HIP, so the baseline is machine-local until it does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "python") not in sys.path:
    # The worktree's OWN code, ahead of any editable install pointing at the
    # primary checkout. Same reasoning as pyproject's pythonpath=["python"]:
    # a harness that verifies a different tree than the one it lives in is a
    # check that cannot see what it claims to check.
    sys.path.insert(0, str(REPO / "python"))

from synapse.blocks.canonical import (           # noqa: E402
    CANONICALIZER_VERSION,
    canonicalize_usda,
)
from synapse.blocks.fixtures import (            # noqa: E402
    box_name_for,
    load_fixture,
)
from synapse.blocks.plan import build_plan       # noqa: E402
from synapse.blocks.runtime import (             # noqa: E402
    apply_fixture,
    observe,
    remove_fixture,
)

FIXTURE = "solaris.basic"
STAGE = "/stage"


# ------------------------------------------------------------------ plumbing


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main_worktree_root() -> Path:
    """The repository's MAIN working tree, resolved without shelling out.

    A main checkout has a ``.git`` DIRECTORY. A linked worktree has a ``.git``
    FILE reading ``gitdir: <main>/.git/worktrees/<name>``, so the main root is
    three parents up from that path.
    """
    dot = REPO / ".git"
    if dot.is_dir():
        return REPO
    if dot.is_file():
        try:
            line = dot.read_text(encoding="utf-8").strip()
            if line.startswith("gitdir:"):
                gitdir = Path(line.split(":", 1)[1].strip())
                return gitdir.parents[2]
        except (OSError, IndexError):
            pass
    return REPO


# ------------------------------------------------------------- measurements


def stage_node():
    node = hou.node(STAGE)
    if node is None:
        raise RuntimeError("%s is not present in this session" % STAGE)
    return node


def composed_hash(fx) -> str:
    """sha256 of the canonicalized composed USD at the fixture's display node.

    This is the instrument the fixture baseline is expressed in -- same
    canonicalizer, same tail, same flatten.
    """
    tail = stage_node().node(fx["display"])
    if tail is None:
        raise RuntimeError("display node %r absent -- nothing to compose"
                           % fx["display"])
    composed = tail.stage()
    if composed is None:
        raise RuntimeError("stage() returned None at %r: %s"
                           % (fx["display"], list(tail.errors())))
    canon = canonicalize_usda(composed.Flatten().ExportToString())
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def stage_signature() -> str:
    """sha256 of the FULL topology of /stage -- every child and every box.

    The composed hash only sees what reaches the display node, so it is blind
    to a node sitting off to the side. F-5 claims "zero mutations", which is a
    claim about the whole network, so it needs an instrument that can see the
    whole network.
    """
    return hashlib.sha256(
        json.dumps(stage_state(), sort_keys=True).encode("utf-8")
    ).hexdigest()


def read_parm(parm) -> str:
    """The authored value of a parm, as text, for signature purposes.

    VERIFIED-RUNTIME 22.0.368: ``unexpandedString()`` raises
    ``hou.OperationFailed("Cannot get unexpanded string for parms with
    keyframes")``. Some default LOP parms ARE keyframed, so the string path
    needs a real fallback -- and the fallback must still capture the value,
    not swallow it, or a mutation could hide behind an unreadable parm.
    """
    try:
        if parm.parmTemplate().type() == hou.parmTemplateType.String:
            return "s:" + str(parm.unexpandedString())
    except hou.OperationFailed:
        try:
            return "k:" + repr([(k.frame(), k.expression())
                                for k in parm.keyframes()])
        except Exception as e:
            return "kerr:" + type(e).__name__
    except Exception as e:
        return "terr:" + type(e).__name__
    try:
        return "v:" + str(parm.eval())
    except Exception as e:
        return "verr:" + type(e).__name__


def stage_state() -> dict:
    stage = stage_node()
    nodes = {}
    for child in sorted(stage.children(), key=lambda c: c.name()):
        nodes[child.name()] = {
            "type": child.type().name(),
            "position": [round(float(child.position()[0]), 6),
                         round(float(child.position()[1]), 6)],
            "display": bool(child.isDisplayFlagSet()),
            "bypass": bool(child.isBypassed()),
            "comment": child.comment(),
            "inputs": [(i.name() if i is not None else None)
                       for i in child.inputs()],
            "parms": {p.name(): read_parm(p)
                      for p in sorted(child.parms(), key=lambda x: x.name())},
        }
    boxes = {}
    for box in sorted(stage.networkBoxes(), key=lambda b: b.name()):
        boxes[box.name()] = sorted(n.name() for n in box.nodes(recurse=False))
    return {"nodes": nodes, "boxes": boxes}


def reset_stage() -> None:
    """Destroy every child and every network box in /stage.

    Harness-local scorched earth so each invariant starts from a known state.
    This is NOT the reconciler's delete path -- the reconciler may only touch
    its own box members (D3), and nothing here is imported by product code.
    """
    stage = stage_node()
    for child in list(stage.children()):
        try:
            child.destroy()
        except Exception:
            pass
    for box in list(stage.networkBoxes()):
        try:
            box.destroy()
        except Exception:
            pass
    remaining = [c.name() for c in stage.children()]
    if remaining:
        raise RuntimeError("reset_stage left %r behind" % remaining)


def make_artist_node(name: str, ntype: str = "null"):
    """A node the reconciler must never touch. Given a distinctive position
    and comment so any mutation shows up in the signature."""
    node = stage_node().createNode(ntype, name)
    if node.name() != name:
        raise RuntimeError("could not create artist node %r (got %r)"
                           % (name, node.name()))
    node.setPosition(hou.Vector2(7.5, 3.25))
    node.setComment("artist owned - do not touch")
    return node


def node_state(name: str):
    st = stage_state()["nodes"]
    return st.get(name)


# ------------------------------------------------------------------- runner


class Results:
    def __init__(self):
        self.entries = []

    def record(self, ident, title, passed, detail):
        self.entries.append({
            "id": ident, "title": title,
            "status": "PASS" if passed else "FAIL",
            "detail": detail, "ts": utc_now(),
        })
        print("[%s] %-4s %s" % ("PASS" if passed else "FAIL", ident, title),
              flush=True)
        if not passed:
            print("       detail: %s"
                  % json.dumps(detail, sort_keys=True, default=str)[:1200],
                  flush=True)
        return passed

    @property
    def failures(self):
        return [e for e in self.entries if e["status"] == "FAIL"]


def run_controls(fx, box, baseline, res: Results) -> None:
    """Prove every instrument can disagree BEFORE any of them is trusted."""

    # C-1: the composed hash discriminates. Build, break, compare.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    good = composed_hash(fx)
    stage_node().node("dome_light").destroy()
    broken = composed_hash(fx)
    res.record(
        "C-1", "composed hash CAN disagree (node removed from the chain)",
        good != broken,
        {"with_dome_light": good, "without": broken},
    )

    # C-2: the op count discriminates. Applied stage, then drift one parm.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    quiet = build_plan(fx, observe(fx, box, STAGE), box_name=box).ops
    stage_node().node("geo").parm("primpath").set("/drifted")
    loud = build_plan(fx, observe(fx, box, STAGE), box_name=box).ops
    res.record(
        "C-2", "op count CAN be non-zero (one parm drifted)",
        quiet == 0 and loud == 1,
        {"applied_ops": quiet, "drifted_ops": loud},
    )

    # C-3: the stage signature discriminates. Move one node 0.5 units.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    before = stage_signature()
    n = stage_node().node("geo")
    n.setPosition(hou.Vector2(n.position()[0] + 0.5, n.position()[1]))
    res.record(
        "C-3", "stage signature CAN change (one node nudged)",
        before != stage_signature(), {"before": before, "after": stage_signature()},
    )

    # C-4: the collision gate is not always-on. Same name INSIDE the box is
    #      the normal reconcile case and must NOT be reported as a clash.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    snap = observe(fx, box, STAGE)
    inside = build_plan(fx, snap, box_name=box)
    res.record(
        "C-4", "collision gate is silent when the name is INSIDE the box",
        not inside.blocked and "camera" in snap["box_members"],
        {"blocked": inside.blocked,
         "camera_is_member": "camera" in snap["box_members"]},
    )

    # C-5: the baseline the whole run compares against is the committed one.
    res.record(
        "C-5", "baseline under test is the fixture's committed sha256",
        baseline == fx["baseline"]["sha256"] and len(baseline) == 64,
        {"baseline": baseline, "canonicalizer": CANONICALIZER_VERSION,
         "fixture_canonicalizer": fx["baseline"]["canonicalizer"]},
    )


def run_invariants(fx, box, baseline, res: Results) -> None:

    # -- F-1 -------------------------------------------------------------
    reset_stage()
    r1 = apply_fixture(FIXTURE, STAGE)
    h1 = composed_hash(fx)
    snap1 = observe(fx, box, STAGE)
    res.record(
        "F-1", "apply on a clean stage reproduces the committed baseline",
        (h1 == baseline and r1["applied"] and r1["status"] == "built"
         and sorted(snap1["box_members"]) == sorted(
             n["name"] for n in fx["nodes"])),
        {"hash": h1, "baseline": baseline, "status": r1["status"],
         "ops": r1["ops"], "applied": r1["applied"],
         "box_members": sorted(snap1["box_members"]),
         "verdict": r1["verdict"]},
    )

    # -- F-2 -------------------------------------------------------------
    rm = remove_fixture(FIXTURE, STAGE)
    after_remove = stage_state()
    r2 = apply_fixture(FIXTURE, STAGE)
    h2 = composed_hash(fx)
    res.record(
        "F-2", "apply -> remove -> apply reproduces the same hash",
        (h2 == baseline and rm["status"] == "removed"
         and not after_remove["nodes"] and not after_remove["boxes"]
         and r2["status"] == "built"),
        {"hash_after_reapply": h2, "baseline": baseline,
         "removed": sorted(rm["deleted"]), "remove_ops": rm["ops"],
         "stage_between": after_remove, "reapply_status": r2["status"],
         "remove_verdict": rm["verdict"]},
    )

    # -- F-3 -------------------------------------------------------------
    h_before = composed_hash(fx)
    r3 = apply_fixture(FIXTURE, STAGE)
    h_after = composed_hash(fx)
    res.record(
        "F-3", "apply on an already-applied stage is a true no-op",
        (r3["ops"] == 0 and r3["status"] == "noop" and r3["applied"]
         and h_after == h_before == baseline
         and not r3["created"] and not r3["deleted"] and not r3["changed"]),
        {"ops": r3["ops"], "status": r3["status"],
         "hash_before": h_before, "hash_after": h_after,
         "created": r3["created"], "deleted": r3["deleted"],
         "changed": r3["changed"], "verdict": r3["verdict"]},
    )

    # -- F-4 -------------------------------------------------------------
    #
    # "byte-untouched" is asserted over the artist node's AUTHORED state:
    # type, name, position, parms, comment, wiring, bypass. It deliberately
    # excludes ``display``, and F-4b below is why -- the LOP display flag is
    # one exclusive network-wide slot, not a property of the node. A fixture
    # that declares a display node cannot be honoured without taking it. The
    # claim is therefore split, not softened: F-4 pins that nothing the artist
    # AUTHORED changed, and F-4b pins that the one thing that did change is
    # reported by name instead of happening silently.
    reset_stage()
    artist = make_artist_node("artist_wip_null")
    artist_before = node_state("artist_wip_null")
    held_display_before = bool(artist_before["display"])
    r4 = apply_fixture(FIXTURE, STAGE)
    artist_after = node_state("artist_wip_null")
    snap4 = observe(fx, box, STAGE)
    h4 = composed_hash(fx)

    authored_before = {k: v for k, v in artist_before.items() if k != "display"}
    authored_after = {k: v for k, v in artist_after.items() if k != "display"}

    res.record(
        "F-4", "an artist node outside the box keeps every authored property",
        (r4["applied"] and not r4["collisions"]
         and authored_after == authored_before
         and "artist_wip_null" not in snap4["box_members"]
         and sorted(snap4["box_members"]) == sorted(
             n["name"] for n in fx["nodes"])),
        {"applied": r4["applied"], "status": r4["status"],
         "authored_unchanged": authored_after == authored_before,
         "authored_before": authored_before, "authored_after": authored_after,
         "display_before": artist_before["display"],
         "display_after": artist_after["display"],
         "box_members": sorted(snap4["box_members"]),
         "composed_hash": h4, "baseline": baseline,
         "hash_matches_baseline_note": (
             "recorded, not gated: a node off the display chain does not "
             "reach the composed stage"),
         "verdict": r4["verdict"]},
    )

    res.record(
        "F-4b", "taking the exclusive display flag is reported, not silent",
        (held_display_before
         and artist_after["display"] is False
         and r4.get("display_taken_from") == "artist_wip_null"
         and r4.get("display_taken_from_outside_box") is True),
        {"artist_held_display_before": held_display_before,
         "artist_holds_display_after": artist_after["display"],
         "display_taken_from": r4.get("display_taken_from"),
         "from_outside_box": r4.get("display_taken_from_outside_box"),
         "note": ("the display flag is ONE slot per network; honouring the "
                  "fixture's declared display node necessarily moves it. "
                  "See for_ruling in receipts/M5.json.")},
    )

    # -- F-5 -------------------------------------------------------------
    reset_stage()
    clash = make_artist_node("camera")
    sig_before = stage_signature()
    state_before = stage_state()
    r5 = apply_fixture(FIXTURE, STAGE)
    sig_after = stage_signature()
    state_after = stage_state()
    res.record(
        "F-5", "a name clash outside the box mutates nothing and reports",
        (r5["status"] == "collision" and r5["applied"] is False
         and r5["ops"] == 0
         and [c["name"] for c in r5["collisions"]] == ["camera"]
         and sig_after == sig_before
         and not r5["created"] and not r5["deleted"]),
        {"status": r5["status"], "ops": r5["ops"], "applied": r5["applied"],
         "collisions": r5["collisions"],
         "signature_before": sig_before, "signature_after": sig_after,
         "signature_unchanged": sig_after == sig_before,
         "stage_before": state_before, "stage_after": state_after,
         "verdict": r5["verdict"]},
    )
    del clash
    reset_stage()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="run directory (default harness/blocks/runs/<stamp>)")
    ap.add_argument("--hip", default=None,
                    help="value to pin $HIP to (default: the repo's MAIN "
                         "working tree, which is where the baseline was cut)")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else (
        REPO / "harness" / "blocks" / "runs" / ("m5_invariants_" + stamp))
    out_dir.mkdir(parents=True, exist_ok=True)

    hip = args.hip or str(main_worktree_root()).replace("\\", "/")
    hip_before = hou.text.expandString("$HIP")
    hou.putenv("HIP", hip)
    hip_after = hou.text.expandString("$HIP")

    fx = load_fixture(FIXTURE)
    box = box_name_for(fx, FIXTURE)
    baseline = fx["baseline"]["sha256"]

    res = Results()
    meta = {
        "harness": "m5_invariants",
        "version": "1.0.0",
        "started": utc_now(),
        "build": hou.applicationVersionString(),
        "target_build": fx.get("target_build"),
        "build_matches_target": (
            hou.applicationVersionString() == fx.get("target_build")),
        "fixture": FIXTURE,
        "fixture_version": fx.get("version"),
        "box": box,
        "baseline": baseline,
        "canonicalizer": CANONICALIZER_VERSION,
        "repo": str(REPO),
        "synapse_package": str(Path(sys.modules["synapse"].__file__).parent),
        "cwd": str(Path.cwd()),
        "hip_pinned_to": hip,
        "hip_before_pin": hip_before,
        "hip_after_pin": hip_after,
        "hip_pin_effective": hip_after.replace("\\", "/") == hip,
    }
    print("build   %s (target %s)" % (meta["build"], meta["target_build"]),
          flush=True)
    print("package %s" % meta["synapse_package"], flush=True)
    print("$HIP    %s -> %s" % (hip_before, hip_after), flush=True)
    print("run dir %s" % out_dir, flush=True)

    failed_hard = None
    try:
        if not meta["hip_pin_effective"]:
            raise RuntimeError(
                "could not pin $HIP to %r (got %r) -- the baseline comparison "
                "would be measuring the launch directory, not the reconciler"
                % (hip, hip_after))
        run_controls(fx, box, baseline, res)
        run_invariants(fx, box, baseline, res)
    except Exception:
        failed_hard = traceback.format_exc()

    meta["finished"] = utc_now()
    evidence = {"meta": meta, "entries": res.entries,
                "crash": failed_hard}
    ev_path = out_dir / "invariants_m5.json"
    atomic_write(ev_path, json.dumps(evidence, indent=2, sort_keys=True,
                                     default=str))

    n_pass = len([e for e in res.entries if e["status"] == "PASS"])
    n_fail = len(res.failures)
    summary = {"pass": n_pass, "fail": n_fail, "crash": bool(failed_hard),
               "evidence": ev_path.name, "finished": meta["finished"]}

    if failed_hard or n_fail:
        atomic_write(out_dir / "FAILED",
                     json.dumps(summary, indent=2)
                     + ("\n\n" + failed_hard if failed_hard else ""))
        print("\nFAILED  pass=%d fail=%d crash=%s" % (n_pass, n_fail,
                                                      bool(failed_hard)),
              flush=True)
        if failed_hard:
            print(failed_hard, flush=True)
        return 1

    atomic_write(out_dir / "DONE", json.dumps(summary, indent=2))
    print("\nDONE    pass=%d fail=0" % n_pass, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
