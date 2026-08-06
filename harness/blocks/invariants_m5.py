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
    C1_RULES,
    CANONICALIZER_VERSION,
    canonicalize_usda,
    houdini_env_map,
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


# The $HIP this run was launched under. F-6 re-pins $HIP between builds, so it
# has to be able to put it back -- otherwise every invariant after F-6 would be
# measured in a different environment than the ones before it.
PINNED_HIP: str = ""


def restore_hip() -> None:
    if PINNED_HIP:
        hou.putenv("HIP", PINNED_HIP)


def hip_pair() -> tuple:
    """Two DIFFERENT $HIP values to build the same fixture under (F-6 / C-6).

    This worktree and the repository's main working tree -- two real
    directories that genuinely differ, which is the drift M5-F1 reported.

    Fails when: they are the same directory (this harness launched from the
    main checkout). A control whose two inputs are identical cannot fail, so
    rather than let C-6 pass vacuously the second value is made synthetic and
    distinct. Law 1: state the condition under which the check fails, and make
    sure it can.
    """
    a = str(REPO).replace("\\", "/")
    b = str(main_worktree_root()).replace("\\", "/")
    if a == b:
        b = a + "/_m5b_alt_hip"     # never written to; only ever expanded
    return a, b


# ------------------------------------------------------------- measurements


def stage_node():
    node = hou.node(STAGE)
    if node is None:
        raise RuntimeError("%s is not present in this session" % STAGE)
    return node


def live_env() -> dict:
    """The c3 environment map for this process, read fresh every call.

    Read fresh on purpose: F-6 re-pins $HIP between builds, so a cached map
    would silently canonicalize the second build against the FIRST build's
    environment and the invariant would pass for the wrong reason.
    """
    return houdini_env_map(hou.text.expandString)


def composed_hash(fx, env=None) -> str:
    """sha256 of the canonicalized composed USD at the fixture's display node.

    This is the instrument the fixture baseline is expressed in -- same
    canonicalizer, same tail, same flatten.

    Args:
        env: ``None`` (default) canonicalizes against the LIVE environment,
             which is what a c3 baseline means. An explicit ``{}`` disables
             rule 5 and reproduces c2 output -- that is not a convenience, it
             is control C-6, which has to be able to show the two $HIP builds
             DISAGREEING before F-6's agreement counts as evidence.
    """
    tail = stage_node().node(fx["display"])
    if tail is None:
        raise RuntimeError("display node %r absent -- nothing to compose"
                           % fx["display"])
    composed = tail.stage()
    if composed is None:
        raise RuntimeError("stage() returned None at %r: %s"
                           % (fx["display"], list(tail.errors())))
    canon = canonicalize_usda(composed.Flatten().ExportToString(),
                              env=live_env() if env is None else env)
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


def authored_only(state) -> dict:
    """A node's state MINUS ``display``.

    ``display`` is deliberately excluded from every "artist node untouched"
    claim in this harness. VERIFIED-RUNTIME 22.0.368 (M5-F7): the LOP display
    flag is ONE exclusive network-wide slot, not a property of a node, so
    honouring a fixture's declared display node necessarily moves it. F-4b
    pins that the move is REPORTED; F-4 and F-7 pin that nothing the artist
    actually authored changed.
    """
    if state is None:
        return {}
    return {k: v for k, v in state.items() if k != "display"}


def build_under_hip(fx, hip: str) -> dict:
    """Pin $HIP, build the fixture from a CLEAN stage, hash it two ways.

    ``c3`` is the hash against the live environment -- what a portable baseline
    means. ``c2`` is the same bytes with rule 5 disabled (``env={}``), which is
    what the hash WAS before R-M5-1 and is the only way to show that these two
    builds genuinely differ in environment.

    Fails when: the $HIP pin does not take. Then both builds would be measured
    under the same environment and F-6 would pass for the wrong reason, so the
    pin is verified rather than assumed.
    """
    hou.putenv("HIP", hip)
    effective = hou.text.expandString("$HIP").replace("\\", "/")
    want = hip.replace("\\", "/")
    if effective != want:
        raise RuntimeError(
            "could not pin $HIP to %r (got %r) -- F-6 would be comparing two "
            "builds made in the SAME environment" % (want, effective))
    reset_stage()
    r = apply_fixture(FIXTURE, STAGE)
    return {
        "hip": want,
        "hip_effective": effective,
        "status": r["status"],
        "applied": r["applied"],
        "ops": r["ops"],
        "c3": composed_hash(fx),            # live env -> rule 5 active
        "c2": composed_hash(fx, env={}),    # rule 5 disabled: the M5-F1 shape
        "env": live_env(),
    }


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

    # C-6: the cross-cwd comparison CAN fail. Two builds under two different
    #      $HIP values must DISAGREE once rule 5 is switched off -- that
    #      disagreement is finding M5-F1 itself. Without this, F-6's agreement
    #      would prove only that the hash is insensitive to something nobody
    #      showed it was ever sensitive to.
    hip_a, hip_b = hip_pair()
    ca = build_under_hip(fx, hip_a)
    cb = build_under_hip(fx, hip_b)
    restore_hip()
    res.record(
        "C-6", "two $HIP builds CAN disagree when rule 5 is disabled (c2)",
        (ca["hip_effective"] != cb["hip_effective"] and ca["c2"] != cb["c2"]),
        {"hip_a": ca["hip_effective"], "hip_b": cb["hip_effective"],
         "hips_differ": ca["hip_effective"] != cb["hip_effective"],
         "c2_a": ca["c2"], "c2_b": cb["c2"],
         "c2_differs": ca["c2"] != cb["c2"],
         "note": ("this IS M5-F1 reproduced: without normalize_houdini_env_"
                  "paths the baseline pins the launch directory")},
    )

    # C-7: the ejection instruments CAN disagree. F-7 asserts a node is ALIVE
    #      and NOT a member; both would pass vacuously if aliveness were always
    #      true or membership always empty. Show each one taking the other
    #      value before F-7 is trusted.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    c7box = stage_node().findNetworkBox(box)
    c7_members = sorted(n.name() for n in c7box.nodes(recurse=False))
    make_artist_node("syn_c7_victim")
    c7_alive_before = stage_node().node("syn_c7_victim") is not None
    stage_node().node("syn_c7_victim").destroy()
    c7_alive_after = stage_node().node("syn_c7_victim") is not None
    res.record(
        "C-7", "membership is not vacuously empty and aliveness is not "
               "vacuously true",
        ("camera" in c7_members and c7_alive_before and not c7_alive_after),
        {"box_members": c7_members,
         "membership_can_be_nonempty": "camera" in c7_members,
         "alive_before_destroy": c7_alive_before,
         "alive_after_destroy": c7_alive_after,
         "aliveness_can_be_false": not c7_alive_after},
    )
    reset_stage()


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

    # -- F-6 ---------------------------------------------------------------
    #
    # CROSS-CWD EQUALITY -- the invariant that proves R-M5-1 actually closed.
    # The same fixture, built twice, under two genuinely different $HIP values,
    # must produce ONE hash. C-6 has already shown these same two builds
    # disagreeing with rule 5 switched off, so an agreement here is a property
    # of the canonicalizer rather than of an insensitive instrument.
    hip_a, hip_b = hip_pair()
    a6 = build_under_hip(fx, hip_a)
    b6 = build_under_hip(fx, hip_b)
    restore_hip()
    res.record(
        "F-6", "the same fixture under two different $HIP values hashes "
               "identically under c3, and equals the committed baseline",
        (a6["hip_effective"] != b6["hip_effective"]
         and a6["c3"] == b6["c3"] == baseline
         and a6["applied"] and b6["applied"]),
        {"hip_a": a6["hip_effective"], "hip_b": b6["hip_effective"],
         "hips_differ": a6["hip_effective"] != b6["hip_effective"],
         "c3_a": a6["c3"], "c3_b": b6["c3"], "baseline": baseline,
         "c3_identical": a6["c3"] == b6["c3"],
         "c3_matches_baseline": a6["c3"] == baseline,
         "c2_a": a6["c2"], "c2_b": b6["c2"],
         "c2_differs_see_C6": a6["c2"] != b6["c2"],
         "env_a": a6["env"], "env_b": b6["env"],
         "canonicalizer": CANONICALIZER_VERSION},
    )

    # -- F-7 ---------------------------------------------------------------
    #
    # EJECTION SAFETY (R-M5-3). The artist drags a node they made INTO our box.
    # The fixture does not declare it. After apply it must be: still alive in
    # /stage, authored-identical, no longer a member, and named in
    # result['ejected'] -- not deleted, and not silently dropped either.
    reset_stage()
    apply_fixture(FIXTURE, STAGE)
    stray = make_artist_node("artist_stray_null")
    stray_before = node_state("artist_stray_null")
    box_obj = stage_node().findNetworkBox(box)
    box_obj.addItem(stray)                      # <- the drag, in code
    members_with_stray = sorted(n.name() for n in box_obj.nodes(recurse=False))
    del stray, box_obj                          # never hold handles across apply

    r7 = apply_fixture(FIXTURE, STAGE)

    stray_after = node_state("artist_stray_null")
    alive = stage_node().node("artist_stray_null") is not None
    members_after = sorted(
        n.name() for n in stage_node().findNetworkBox(box).nodes(recurse=False))
    declared_names = sorted(n["name"] for n in fx["nodes"])
    res.record(
        "F-7", "a node dragged into the box but not declared is EJECTED, not "
               "deleted: alive, authored-unchanged, no longer a member, "
               "reported",
        (alive
         and authored_only(stray_after) == authored_only(stray_before)
         and "artist_stray_null" in members_with_stray
         and "artist_stray_null" not in members_after
         and members_after == declared_names
         and r7.get("ejected") == ["artist_stray_null"]
         and r7.get("deleted") == []
         and r7["applied"] and r7.get("residual_ops") == 0),
        {"alive_after_apply": alive,
         "was_a_member_before": "artist_stray_null" in members_with_stray,
         "is_a_member_after": "artist_stray_null" in members_after,
         "members_with_stray": members_with_stray,
         "members_after": members_after, "declared": declared_names,
         "ejected": r7.get("ejected"), "deleted": r7.get("deleted"),
         "authored_before": authored_only(stray_before),
         "authored_after": authored_only(stray_after),
         "authored_unchanged": (authored_only(stray_after)
                                == authored_only(stray_before)),
         "display_before": (stray_before or {}).get("display"),
         "display_after": (stray_after or {}).get("display"),
         "display_note": ("display is excluded from the authored comparison "
                          "for the F-4 reason: one exclusive network-wide "
                          "slot, not a node property (M5-F7)"),
         "status": r7["status"], "residual_ops": r7.get("residual_ops"),
         "applied": r7["applied"], "verdict": r7["verdict"]},
    )
    reset_stage()


def emit_baseline(fx, out_dir: Path) -> int:
    """PRODUCER for a c3 fixture baseline (Law 2: the number names its path).

    Builds the fixture twice, under two different $HIP values, and emits the
    c3 hash ONLY if both builds agree. A producer that will emit a
    non-portable number under a c3 label is the exact defect R-M5-1 exists to
    close, so this refuses instead: exit 1, nothing to paste.

    Asserts nothing about the COMMITTED baseline -- that is F-1's job, and it
    cannot run until this has been pasted into the fixture.

        hython harness/blocks/invariants_m5.py --emit-baseline
    """
    hip_a, hip_b = hip_pair()
    a = build_under_hip(fx, hip_a)
    b = build_under_hip(fx, hip_b)
    restore_hip()

    portable = a["c3"] == b["c3"]
    payload = {
        "produced_by": "harness/blocks/invariants_m5.py --emit-baseline",
        "produced_at": utc_now(),
        "build": hou.applicationVersionString(),
        "fixture": FIXTURE,
        "canonicalizer": CANONICALIZER_VERSION,
        "canonicalizer_rules": list(C1_RULES),
        "sha256": a["c3"] if portable else None,
        "portable_across_hip": portable,
        "builds": {
            "a": {"hip": a["hip_effective"], "c3": a["c3"], "c2": a["c2"],
                  "env": a["env"], "status": a["status"], "ops": a["ops"]},
            "b": {"hip": b["hip_effective"], "c3": b["c3"], "c2": b["c2"],
                  "env": b["env"], "status": b["status"], "ops": b["ops"]},
        },
        "c2_pair_differs": a["c2"] != b["c2"],
        "superseded": {"sha256": fx["baseline"]["sha256"],
                       "canonicalizer": fx["baseline"]["canonicalizer"]},
    }
    atomic_write(out_dir / "baseline_c3.json",
                 json.dumps(payload, indent=2, sort_keys=True, default=str))

    print("\n--- c3 baseline producer ---", flush=True)
    print("  $HIP a      %s" % a["hip_effective"], flush=True)
    print("  $HIP b      %s" % b["hip_effective"], flush=True)
    print("  c3 a        %s" % a["c3"], flush=True)
    print("  c3 b        %s" % b["c3"], flush=True)
    print("  c2 a        %s" % a["c2"], flush=True)
    print("  c2 b        %s" % b["c2"], flush=True)
    print("  c2 differs  %s   (must be True, else C-6 cannot fail)"
          % (a["c2"] != b["c2"]), flush=True)
    print("  superseded  %s (%s)" % (fx["baseline"]["sha256"],
                                     fx["baseline"]["canonicalizer"]),
          flush=True)
    if not portable:
        print("\nREFUSED  the two $HIP builds do NOT agree under c3 -- the "
              "rule is wrong or incomplete. Nothing emitted.", flush=True)
        return 1
    print("\nBASELINE %s   (canonicalizer %s, build %s)"
          % (a["c3"], CANONICALIZER_VERSION, hou.applicationVersionString()),
          flush=True)
    print("evidence %s" % (out_dir / "baseline_c3.json"), flush=True)
    return 0


def main() -> int:
    global PINNED_HIP
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="run directory (default harness/blocks/runs/<stamp>)")
    ap.add_argument("--hip", default=None,
                    help="value to pin $HIP to (default: the repo's MAIN "
                         "working tree, which is where the baseline was cut)")
    ap.add_argument("--emit-baseline", action="store_true",
                    help="PRODUCE a c3 baseline (two $HIP builds, emitted "
                         "only if they agree) and exit. Asserts nothing "
                         "against the committed baseline.")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else (
        REPO / "harness" / "blocks" / "runs" / ("m5_invariants_" + stamp))
    out_dir.mkdir(parents=True, exist_ok=True)

    hip = args.hip or str(main_worktree_root()).replace("\\", "/")
    hip_before = hou.text.expandString("$HIP")
    hou.putenv("HIP", hip)
    hip_after = hou.text.expandString("$HIP")
    PINNED_HIP = hip_after.replace("\\", "/")

    fx = load_fixture(FIXTURE)
    box = box_name_for(fx, FIXTURE)
    baseline = fx["baseline"]["sha256"]

    if args.emit_baseline:
        print("build   %s" % hou.applicationVersionString(), flush=True)
        print("run dir %s" % out_dir, flush=True)
        return emit_baseline(fx, out_dir)

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
