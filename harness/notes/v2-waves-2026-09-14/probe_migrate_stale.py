"""B1 second half: the cross-process stale-cache clobber.

Claim under test: a long-lived process (Houdini) has agent.usd's layer cached.
Another process writes a decision to disk. The first process then runs the
upgrade, whose verify reads the CACHED layer -- and whose migrate_to_v2 Saves
that stale layer back over the other process's write, destroying it, while
reporting 2.0.0.
"""
import os, subprocess, sys, tempfile

TREE = sys.argv[1]
sys.path.insert(0, os.path.join(TREE, "python"))
from pxr import Usd, Sdf                                    # noqa: E402
import synapse.memory.scene_memory as sm                    # noqa: E402

root = tempfile.mkdtemp(prefix="mwstale_")
P = os.path.join(root, "agent.usd").replace("\\", "/")

# 1. a v0.1.0 store on disk
stage = Usd.Stage.CreateNew(P)
stage.DefinePrim("/SYNAPSE", "Xform")
a = stage.DefinePrim("/SYNAPSE/agent", "Xform")
a.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set("0.1.0")
stage.DefinePrim("/SYNAPSE/agent/tasks", "Xform")
stage.GetRootLayer().customLayerData = {
    "synapse:version": "0.1.0", "synapse:type": "agent_state"}
stage.GetRootLayer().Save()

# 2. THIS process keeps it open -- a live Houdini session that has read it
held = Usd.Stage.Open(P)
print("### held open in-process, version:",
      held.GetPrimAtPath("/SYNAPSE/agent")
          .GetAttribute("synapse:version").Get())

# 3. ANOTHER process writes a record to disk
code = (
    "from pxr import Usd, Sdf\n"
    "s = Usd.Stage.Open(r'%s')\n"
    "p = s.DefinePrim('/SYNAPSE/agent/tasks/from_other_process', 'Xform')\n"
    "p.CreateAttribute('synapse:marker', Sdf.ValueTypeNames.String)"
    ".Set('WRITTEN_BY_OTHER_PROCESS')\n"
    "s.GetRootLayer().Save()\n" % P
)
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print("### other process rc:", r.returncode, r.stderr.strip()[:120])


def on_disk_has_marker():
    lyr = Sdf.Layer.OpenAsAnonymous(P)          # bypasses the registry
    return lyr.GetPrimAtPath("/SYNAPSE/agent/tasks/from_other_process") is not None


def on_disk_version():
    lyr = Sdf.Layer.OpenAsAnonymous(P)
    return dict(lyr.customLayerData or {}).get("synapse:version")


print("### disk before upgrade : version=%s  other-process record present=%s"
      % (on_disk_version(), on_disk_has_marker()))

# 4. the upgrade runs in the process holding the stale layer
got = sm._upgrade_agent_usd(P)

print("### _upgrade returned   : %r" % got)
print("### disk after  upgrade : version=%s  other-process record present=%s"
      % (on_disk_version(), on_disk_has_marker()))
lost = not on_disk_has_marker()
print("### VERDICT             : %s" % (
    "RECORD DESTROYED while reporting %r" % got if lost
    else "other process's record survived"))

# ---------------------------------------------------------------------------
# Does a Reload BEFORE the migrate preserve the other process's record?
# (The review's fix -- reload before the VERIFY -- is too late: the record is
#  already gone by then. This tests the earlier placement.)
# ---------------------------------------------------------------------------
import shutil, tempfile as _tf
root2 = _tf.mkdtemp(prefix="mwfix_")
Q = os.path.join(root2, "agent.usd").replace("\\", "/")
st = Usd.Stage.CreateNew(Q)
st.DefinePrim("/SYNAPSE", "Xform")
aa = st.DefinePrim("/SYNAPSE/agent", "Xform")
aa.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set("0.1.0")
st.DefinePrim("/SYNAPSE/agent/tasks", "Xform")
st.GetRootLayer().customLayerData = {
    "synapse:version": "0.1.0", "synapse:type": "agent_state"}
st.GetRootLayer().Save()
held2 = Usd.Stage.Open(Q)                       # same stale-cache setup
r2 = subprocess.run([sys.executable, "-c", code.replace(P, Q)],
                    capture_output=True, text=True)

def marker(path):
    lyr = Sdf.Layer.OpenAsAnonymous(path)
    return lyr.GetPrimAtPath("/SYNAPSE/agent/tasks/from_other_process") is not None

print("\n### FIX TRIAL — reload the cached layer BEFORE migrating")
print("### other process rc:", r2.returncode, "| record on disk:", marker(Q))

cached = Sdf.Layer.Find(Q)
print("### layer was cached in this process:", cached is not None)
if cached is not None:
    cached.Reload(force=True)                   # <- the candidate fix

import synapse.memory.agent_state as _agent
_agent.migrate_to_v2(Q)
print("### after reload+migrate | record on disk:", marker(Q),
      "| version:", dict(Sdf.Layer.OpenAsAnonymous(Q).customLayerData or {}
                         ).get("synapse:version"))
print("### VERDICT:", "FIX HOLDS — record survived" if marker(Q)
      else "FIX INSUFFICIENT — record still destroyed")
