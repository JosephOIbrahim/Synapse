# ASSAYER independent re-probe -- hdefereval.executeInMainThread
# Written from scratch; deliberately does NOT import or read harness/notes/h3a_probe.py.
import json
import sys
import traceback

out = {}

# ---- build identity, derived from the probe itself ----
try:
    import hou
    out["hou_import"] = "OK"
    out["applicationVersionString"] = hou.applicationVersionString()
    out["applicationVersion"] = list(hou.applicationVersion())
except Exception as e:
    out["hou_import"] = "FAIL: %r" % (e,)
    print(json.dumps(out, indent=2))
    sys.exit(0)

out["sys_executable"] = sys.executable
out["python_version"] = sys.version.split()[0]

# ---- CONTROLS ----
controls = {}
controls["POS_hasattr_hou_node"] = hasattr(hou, "node")                       # expect True
controls["NEG_hasattr_hou_zzz_indep_control_must_not_exist"] = hasattr(
    hou, "zzz_indep_control_must_not_exist")                                  # expect False
controls["NEG_hasattr_hou_lopNetworks"] = hasattr(hou, "lopNetworks")         # expect False
controls_ok = (
    controls["POS_hasattr_hou_node"] is True
    and controls["NEG_hasattr_hou_zzz_indep_control_must_not_exist"] is False
    and controls["NEG_hasattr_hou_lopNetworks"] is False
)
out["controls"] = controls
out["controls_ok"] = controls_ok

# extra cross-check: dir() agrees with hasattr for the controls
hou_dir = dir(hou)
out["controls_dir_crosscheck"] = {
    "node_in_dir_hou": "node" in hou_dir,
    "zzz_indep_control_must_not_exist_in_dir_hou": "zzz_indep_control_must_not_exist" in hou_dir,
    "lopNetworks_in_dir_hou": "lopNetworks" in hou_dir,
}

# ---- TARGET MODULE ----
try:
    import hdefereval
    out["hdefereval_import"] = "OK"
    out["hdefereval_file"] = getattr(hdefereval, "__file__", None)
    hd_dir = dir(hdefereval)
    out["hdefereval_dir_complete"] = hd_dir
    out["hdefereval_dir_len"] = len(hd_dir)
except Exception as e:
    out["hdefereval_import"] = "FAIL: %r" % (e,)
    out["hdefereval_traceback"] = traceback.format_exc()
    out["hdefereval_dir_complete"] = None
    print(json.dumps(out, indent=2))
    sys.exit(0)

# ---- SYMBOL PROBES (hasattr AND dir(), must agree) ----
targets = [
    "executeDeferred",
    "executeInMainThreadWithResult",
    "executeInMainThread",
    "executeDeferredAfterWaiting",
]
probe = {}
for name in targets:
    ha = hasattr(hdefereval, name)
    ind = name in hd_dir
    probe[name] = {
        "hasattr": ha,
        "in_dir": ind,
        "agree": ha == ind,
        "verdict": "EXISTS" if (ha and ind) else ("ABSENT" if (not ha and not ind) else "DISAGREE"),
        "repr": repr(getattr(hdefereval, name, None)) if ha else None,
    }
out["probe"] = probe

# ---- negative control on the target module itself ----
out["hdefereval_negative_control"] = {
    "zzz_indep_control_must_not_exist": hasattr(hdefereval, "zzz_indep_control_must_not_exist"),
}

print(json.dumps(out, indent=2))
