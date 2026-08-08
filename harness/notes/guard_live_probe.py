"""GUARD leg -- LIVE verification of the shot_layers write-site guard on H22.

Producer path for the `foreign_cwd_clean` figure in
harness/notes/receipts/GUARD.json (Law 2). Real `hou`, real `/stage`, real
filesystem -- no mocks.

    cd <a scratch dir>   # this becomes the foreign CWD
    "<HFS>/bin/hython.exe" <repo>/harness/notes/guard_live_probe.py <proj_dir>

A) unsaved scene + default layer_dir, invoked from a foreign CWD -> must refuse
   and leave the CWD clean (the RES-F11 litter condition).
B) saved scene -> must still build, into $HIP, with nothing at the CWD.
"""
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))            # <repo>/harness/notes
_REPO_PY = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "python")
sys.path.insert(0, _REPO_PY)
import hou                                                       # noqa: E402
from synapse.server import solaris_compose_tools as sct          # noqa: E402
from synapse.server import solaris_compose as sc                 # noqa: E402

proj = sys.argv[1]
out = {"build": hou.applicationVersionString(), "cwd": os.getcwd()}

stage = hou.node("/stage")
out["stage"] = stage.path()
out["hou_available"] = sct.HOU_AVAILABLE

# --- A) UNSAVED scene, default layer_dir, foreign CWD -> refuse, no litter ---
out["A_isNewFile"] = hou.hipFile.isNewFile()
out["A_HIP"] = hou.expandString("$HIP")
try:
    sct.build_karma_xpu_shot(stage, shot="shot", verify=False)
    out["A_result"] = "RETURNED (no refusal)"
except sc.ComposeError as e:
    out["A_result"] = "ComposeError: %s" % e
except Exception as e:                                            # noqa: BLE001
    out["A_result"] = "%s: %s" % (type(e).__name__, e)
out["A_cwd_listing"] = sorted(os.listdir(os.getcwd()))
out["A_shot_layers_at_cwd"] = os.path.isdir(os.path.join(os.getcwd(), "shot_layers"))

# --- B) SAVED scene -> builds into $HIP, still nothing at the CWD -----------
hou.hipFile.save(os.path.join(proj, "live.hip").replace("\\", "/"))
out["B_isNewFile"] = hou.hipFile.isNewFile()
out["B_HIP"] = hou.expandString("$HIP")
try:
    r = sct.build_karma_xpu_shot(hou.node("/stage"), shot="shot", verify=False)
    out["B_result"] = "built"
    out["B_disk_writes"] = r["disk_writes"]
except Exception as e:                                            # noqa: BLE001
    out["B_result"] = "%s: %s" % (type(e).__name__, e)
sl = os.path.join(proj, "shot_layers")
out["B_layers_in_proj"] = sorted(os.listdir(sl)) if os.path.isdir(sl) else "ABSENT"
out["B_shot_layers_at_cwd"] = os.path.isdir(os.path.join(os.getcwd(), "shot_layers"))
out["B_cwd_listing"] = sorted(os.listdir(os.getcwd()))
print("RESULT_JSON " + json.dumps(out, indent=1))
