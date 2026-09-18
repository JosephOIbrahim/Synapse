"""hy_verbs_sweep.py - execute every READ-ONLY verb under headless hython.

Converts the static UI scan from hy_verbs.py into a PROBED table: each verb is
actually called and its outcome recorded on a stated build.

Safety, stated once:
  * The read-only set comes from synapse.server.handlers._READ_ONLY_COMMANDS,
    the same taxonomy FloorGate uses. It is NOT redefined here. Anything not in
    that set is SKIPPED and never called -- delete_node, emergency_halt and
    autonomous_render are all in the registry.
  * A scene fingerprint is taken before and after. A "read-only" verb that
    moves it is reported as a finding, not swallowed.

Crash-safety: run_on_main fast path 2 cannot be interrupted from inside Python,
so a hanging verb can only be ended by the hy.ps1 watchdog killing the process.
The report is therefore rewritten after EVERY verb, and an in_flight marker is
set before each call. If the watchdog fires, the report on disk names the verb
that hung. That attribution is the whole point.

Run:  powershell.exe -File tools\\hy.ps1 tools\\hy_verbs_sweep.py
"""

import json
import os
import sys
import time
import traceback

OUT = os.environ.get("HY_OUT") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_hy_verbs_sweep.json")
REPORT = {"build": None, "in_flight": None, "results": [], "complete": False}


def flush():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2, default=str)


import hou

REPORT["build"] = hou.applicationVersionString()
REPORT["python"] = sys.version.split()[0]
REPORT["ui_available"] = bool(hou.isUIAvailable())
flush()

from synapse.server.handlers import SynapseHandler, _READ_ONLY_COMMANDS

try:
    from synapse.core.errors import (
        SynapseUserError, ParameterError, NodeNotFoundError,
        HoudiniUnavailableError,
    )
    PARAM_ERRS = (SynapseUserError, ParameterError, NodeNotFoundError)
    UI_ERRS = (HoudiniUnavailableError,)
except Exception:
    PARAM_ERRS, UI_ERRS = (), ()

UI_MARKERS = ("hou.ui", "isUIAvailable", "SceneViewer", "curDesktop",
              "paneTabOfType", "flipbook", "no ui", "not available in",
              "desktop", "graphical")


def fingerprint():
    """Cheap scene identity. A read-only verb must not move this."""
    try:
        return {
            "hip": hou.hipFile.name(),
            "obj_children": len(hou.node("/obj").children()),
            "stage_children": len(hou.node("/stage").children()),
            "frame": hou.frame(),
        }
    except Exception as e:
        return {"error": str(e)}


def classify(exc, tb):
    low = (str(exc) + tb).lower()
    if UI_ERRS and isinstance(exc, UI_ERRS):
        return "headless_fail"
    if any(m.lower() in low for m in UI_MARKERS):
        return "headless_fail"
    if PARAM_ERRS and isinstance(exc, PARAM_ERRS):
        return "needs_params"
    if isinstance(exc, (KeyError, TypeError, ValueError)):
        return "needs_params"
    return "error"


handler = SynapseHandler()
reg = handler._registry
all_verbs = sorted(reg.registered_types)
read_only = [v for v in all_verbs if v in _READ_ONLY_COMMANDS]
skipped = [v for v in all_verbs if v not in _READ_ONLY_COMMANDS]

REPORT["counts"] = {
    "registered": len(all_verbs),
    "read_only": len(read_only),
    "skipped_mutating": len(skipped),
}
REPORT["skipped_mutating"] = skipped
REPORT["fingerprint_before"] = fingerprint()
flush()

print("[sweep] %d registered / %d read-only / %d skipped as mutating"
      % (len(all_verbs), len(read_only), len(skipped)), flush=True)

for i, verb in enumerate(read_only, 1):
    REPORT["in_flight"] = verb
    flush()
    t = time.perf_counter()
    try:
        out = reg.get(verb)({})
        rec = {
            "verb": verb,
            "status": "ok",
            "preview": json.dumps(out, default=str)[:220],
        }
    except Exception as e:
        tb = traceback.format_exc()
        rec = {
            "verb": verb,
            "status": classify(e, tb),
            "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
        }
    rec["ms"] = round((time.perf_counter() - t) * 1000, 1)
    REPORT["results"].append(rec)
    REPORT["in_flight"] = None
    flush()
    print("  [%3d/%3d] %-42s %-14s %8.1fms"
          % (i, len(read_only), verb, rec["status"], rec["ms"]), flush=True)


REPORT["fingerprint_after"] = fingerprint()
REPORT["scene_moved"] = (REPORT["fingerprint_before"] != REPORT["fingerprint_after"])

summary = {}
for r in REPORT["results"]:
    summary[r["status"]] = summary.get(r["status"], 0) + 1
REPORT["summary"] = summary
REPORT["headless_fail_verbs"] = [r["verb"] for r in REPORT["results"]
                                 if r["status"] == "headless_fail"]
REPORT["error_verbs"] = [{"verb": r["verb"], "error": r.get("error")}
                         for r in REPORT["results"] if r["status"] == "error"]
REPORT["complete"] = True
flush()

print()
print("=== SWEEP SUMMARY (build %s, ui=%s) ===" % (REPORT["build"],
                                                   REPORT["ui_available"]))
for k in sorted(summary):
    print("  %-14s %d" % (k, summary[k]))
print("  scene_moved   %s" % REPORT["scene_moved"])
if REPORT["headless_fail_verbs"]:
    print("  HEADLESS FAIL: %s" % ", ".join(REPORT["headless_fail_verbs"]))
for e in REPORT["error_verbs"][:15]:
    print("  ERROR %-38s %s" % (e["verb"], e["error"]))
print("=== report: %s ===" % OUT)
