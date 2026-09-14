"""I1/B1 probe: does _upgrade_agent_usd's verify read DISK, or its own buffer?

Run:  python probe_migrate.py <tree-root>
The attack's stated falsifier: a read-only agent.usd under real pxr must come
back UNKNOWN. If it comes back "2.0.0" the verify is reading the cached layer
that migrate_to_v2 just edited, and a migration that never reached disk is
reported to all eight ensure_scene_structure callers as a success.
"""
import os, shutil, stat, sys, tempfile

TREE = sys.argv[1]
sys.path.insert(0, os.path.join(TREE, "python"))
from pxr import Usd, Sdf                                    # noqa: E402
import synapse.memory.scene_memory as sm                    # noqa: E402
import synapse.memory.agent_state as agent                  # noqa: E402

print("### tree      :", TREE)
print("### module    :", sm.__file__)
print("### has fix   :", hasattr(sm, "_upgrade_agent_usd"))
if not hasattr(sm, "_upgrade_agent_usd"):
    sys.exit(0)


def write_v0_1_0(path):
    stage = Usd.Stage.CreateNew(path)
    stage.DefinePrim("/SYNAPSE", "Xform")
    a = stage.DefinePrim("/SYNAPSE/agent", "Xform")
    a.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("idle")
    a.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set("0.1.0")
    for p in ("current_plan", "tasks", "verification_log", "session_history"):
        stage.DefinePrim("/SYNAPSE/agent/%s" % p, "Xform")
    t = stage.DefinePrim("/SYNAPSE/agent/tasks/task_0000", "Xform")
    t.CreateAttribute("synapse:description",
                      Sdf.ValueTypeNames.String).Set("legacy shot prep")
    stage.GetRootLayer().customLayerData = {
        "synapse:version": "0.1.0", "synapse:type": "agent_state"}
    stage.GetRootLayer().Save()
    del stage


def on_disk(path):
    """Ground truth, bypassing the layer registry entirely."""
    try:
        lyr = Sdf.Layer.OpenAsAnonymous(path)
        return dict(lyr.customLayerData or {}).get("synapse:version")
    except Exception as exc:                                # noqa: BLE001
        return "<unreadable: %s>" % type(exc).__name__


def case(label, make_readonly):
    root = tempfile.mkdtemp(prefix="mwprobe_")
    p = os.path.join(root, "agent.usd")
    write_v0_1_0(p)
    before = on_disk(p)
    if make_readonly:
        os.chmod(p, stat.S_IREAD)
    got = sm._upgrade_agent_usd(p)
    after = on_disk(p)
    print("\n--- %s" % label)
    print("    disk BEFORE     : %s" % before)
    print("    returned        : %r" % got)
    print("    disk AFTER      : %s" % after)
    print("    agrees with disk: %s" % (got == after))
    if make_readonly:
        verdict = ("BUG CONFIRMED - reported %r while disk is %s" % (got, after)
                   if got not in ("UNKNOWN", "UNAVAILABLE") else "honest")
        print("    VERDICT         : %s" % verdict)
    try:
        os.chmod(p, stat.S_IWRITE); shutil.rmtree(root, ignore_errors=True)
    except Exception:                                       # noqa: BLE001
        pass


case("CONTROL - writable store (migration should land)", False)
case("ATTACK  - read-only store (Save cannot land)", True)
