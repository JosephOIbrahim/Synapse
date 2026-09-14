"""Is the stale-cache clobber migrate-wiring's, or agent_state's already?

Every writer in agent_state.py follows Usd.Stage.Open(path) -> edit -> Save().
If that shape clobbers a concurrent writer's record, the hazard is module-wide
and pre-existing, and the branch merely arms it on a hotter path. Tested here
against MASTER's agent_state -- no branch code involved.
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, "C:/Users/User/SYNAPSE/python")
from pxr import Usd, Sdf                                   # noqa: E402
import synapse.memory.agent_state as agent                 # noqa: E402

print("### agent_state under test:", agent.__file__)
print("### SCHEMA_VERSION        :", agent.SCHEMA_VERSION)

OTHER = (
    "from pxr import Usd, Sdf\n"
    "s = Usd.Stage.Open(r'%s')\n"
    "p = s.DefinePrim('/SYNAPSE/memory/decisions/from_other_process','Xform')\n"
    "p.CreateAttribute('synapse:decision', Sdf.ValueTypeNames.String)"
    ".Set('WRITTEN_BY_OTHER_PROCESS')\n"
    "s.GetRootLayer().Save()\n")


def fresh_v2_store():
    root = tempfile.mkdtemp(prefix="wstale_")
    p = os.path.join(root, "agent.usd").replace("\\", "/")
    agent.initialize_agent_usd(p)
    return p


def marker(p):
    lyr = Sdf.Layer.OpenAsAnonymous(p)
    return lyr.GetPrimAtPath(
        "/SYNAPSE/memory/decisions/from_other_process") is not None


def trial(label, action):
    p = fresh_v2_store()
    held = Usd.Stage.Open(p)                 # long-lived session holds the layer
    _ = held.GetPrimAtPath("/SYNAPSE/agent")
    rc = subprocess.run([sys.executable, "-c", OTHER % p],
                        capture_output=True, text=True).returncode
    before = marker(p)
    action(p)
    after = marker(p)
    print("\n--- %s" % label)
    print("    other process rc          : %d" % rc)
    print("    its record on disk before : %s" % before)
    print("    its record on disk after  : %s" % after)
    print("    VERDICT                   : %s" % (
        "CLOBBERED by this writer" if (before and not after) else "survived"))


trial("log_decision (master, a PRODUCTION writer)",
      lambda p: agent.log_decision(p, {
          "decision": "local build", "reasoning": "seat probe",
          "created_paths": ["/obj/geo1/box1"], "model_id": "m",
          "revert": "undo", "parent_path": "/obj/geo1"}))

trial("create_task (master, another production writer)",
      lambda p: agent.create_task(p, "t-1", "seat probe task"))
