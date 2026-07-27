"""Call inspect_scene DIRECTLY, bypassing run_on_main and the bridge.

S1-F2 observed the MCP tool hang 1800s twice on a 9-node empty scene while
synapse_ping answered instantly in the same session - so the bridge and the
main-thread queue were healthy. That points at inspect_scene itself rather than
at the marshal.

S1's candidate mechanism - node.errors() forcing cooks - was REFUTED by direct
measurement: _node_issues over 12 real LOP nodes cost 0.00s total.

This calls the function directly with a watchdog, so a hang is bounded and
reported rather than inherited.
"""
import threading, time, sys
import hou

result = {}


def call(root, depth, label):
    from synapse.server.introspection import inspect_scene
    done = threading.Event()

    def run():
        t = time.time()
        try:
            r = inspect_scene(root=root, max_depth=depth, context_filter=None)
            result[label] = ("ok", time.time() - t,
                             len(r.get("nodes", [])) if isinstance(r, dict) else "-")
        except Exception as e:
            result[label] = ("raised", time.time() - t, "%s: %s" % (type(e).__name__, str(e)[:70]))
        done.set()

    th = threading.Thread(target=run, daemon=True)
    th.start()
    if done.wait(timeout=45):
        k, dt, extra = result[label]
        print("  %-30s %-7s %6.2fs   %s" % (label, k, dt, extra), flush=True)
    else:
        print("  %-30s HUNG    >45s   <- reproduces" % label, flush=True)


print("=== EMPTY SCENE ===", flush=True)
print("  /stage children:", len(hou.node("/stage").children()), flush=True)
call("/", 1, "root=/ depth=1")
call("/stage", 1, "root=/stage depth=1")
call("/obj", 1, "root=/obj depth=1")

print(flush=True)
print("=== karma_user_guide.hip ===", flush=True)
SCENE = (r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
         r"\houdini\help\files\karma_user_guide\karma_user_guide.hip")
t = time.time()
hou.hipFile.load(SCENE, suppress_save_prompt=True, ignore_load_warnings=True)
print("  loaded %.1fs, /stage children: %d"
      % (time.time() - t, len(hou.node("/stage").children())), flush=True)
call("/stage", 1, "root=/stage depth=1")
call("/", 3, "root=/ depth=3 (the default)")
