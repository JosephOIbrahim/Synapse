"""hy_verbs.py - headless verb probe for SYNAPSE under hython.

Answers four questions with evidence rather than code-reading:
  1. Does hou load headless, and on which build?
  2. Does run_on_main resolve to fast path 2 (direct call) with no UI,
     i.e. is hdefereval never imported?
  3. Which verbs does SynapseHandler register, and which of them touch
     UI-only APIs (static scan -- a risk flag, NOT a proof of failure)?
  4. Does a real read-only verb execute end to end?

Run:  powershell.exe -File tools\\hy.ps1 tools\\hy_verbs.py
Emits JSON to stdout and to tools/_hy_verbs_report.json.
"""

import json
import os
import sys
import time
import traceback

R = {"stages": {}, "ok": False}
T0 = time.perf_counter()


def stage(name, fn):
    t = time.perf_counter()
    try:
        R["stages"][name] = {"status": "ok", "data": fn()}
    except Exception as e:
        R["stages"][name] = {
            "status": "FAIL",
            "error": "%s: %s" % (type(e).__name__, e),
            "trace": traceback.format_exc()[-1500:],
        }
    R["stages"][name]["ms"] = round((time.perf_counter() - t) * 1000, 1)
    return R["stages"][name].get("data")


# --- 1. runtime -------------------------------------------------------------
def _runtime():
    import hou
    return {
        "hou_build": hou.applicationVersionString(),
        "python": sys.version.split()[0],
        "ui_available": bool(hou.isUIAvailable()),
        "pid": os.getpid(),
        "pref_dir": os.environ.get("HOUDINI_USER_PREF_DIR", ""),
    }


stage("runtime", _runtime)


# --- 2. dispatch proof ------------------------------------------------------
def _dispatch():
    before = "hdefereval" in sys.modules
    from synapse.server.main_thread import run_on_main

    sentinel = {"ran_on": None}

    def payload():
        import threading
        sentinel["ran_on"] = threading.current_thread().name
        return 42

    result = run_on_main(payload, timeout=5.0, label="hy_verbs_probe")
    after = "hdefereval" in sys.modules
    return {
        "result": result,
        "ran_on_thread": sentinel["ran_on"],
        "hdefereval_before": before,
        "hdefereval_after": after,
        "fast_path_2_confirmed": (result == 42 and not after),
    }


stage("dispatch", _dispatch)


# --- 3. verb surface --------------------------------------------------------
UI_TOKENS = (
    "hou.ui", "hou.qt", "sceneViewer", "curDesktop", "paneTabOfType",
    "flipbook", "displayMessage", "SceneViewer", "hou.session.",
)

_HANDLER = {"obj": None, "registry": None}


def _verbs():
    import inspect
    from synapse.server.handlers import SynapseHandler

    h = SynapseHandler()
    reg = h._registry
    _HANDLER["obj"] = h
    _HANDLER["registry"] = reg

    names = sorted(reg.registered_types)
    ui_risk, clean, unreadable = [], [], []
    for n in names:
        fn = reg.get(n)
        try:
            src = inspect.getsource(fn)
        except Exception:
            unreadable.append(n)
            continue
        hits = sorted({t for t in UI_TOKENS if t in src})
        if hits:
            ui_risk.append({"verb": n, "tokens": hits})
        else:
            clean.append(n)
    return {
        "total": len(names),
        "clean_count": len(clean),
        "ui_risk_count": len(ui_risk),
        "unreadable_count": len(unreadable),
        "ui_risk": ui_risk[:40],
        "sample_clean": clean[:40],
        "note": "ui_risk is a STATIC scan of handler source, not a proven failure",
    }


stage("verbs", _verbs)


# --- 4. live read-only call -------------------------------------------------
SAFE_HINTS = ("server_info", "get_info", "info", "ping", "status", "version",
              "capabilities", "list_nodes", "scene_info")


def _live_call():
    reg = _HANDLER["registry"]
    if reg is None:
        raise RuntimeError("registry unavailable (stage 3 failed)")
    names = list(reg.registered_types)
    ordered = []
    for hint in SAFE_HINTS:
        ordered += [n for n in names if hint in n.lower() and n not in ordered]
    attempts = []
    for n in ordered[:8]:
        try:
            out = reg.get(n)({})
            preview = json.dumps(out, default=str)[:400]
            attempts.append({"verb": n, "status": "ok", "preview": preview})
            return {"executed": n, "attempts": attempts}
        except Exception as e:
            attempts.append({"verb": n,
                             "status": "err",
                             "error": "%s: %s" % (type(e).__name__, e)})
    return {"executed": None, "attempts": attempts}


stage("live_call", _live_call)

R["ok"] = all(s["status"] == "ok" for s in R["stages"].values())
R["total_ms"] = round((time.perf_counter() - T0) * 1000, 1)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "_hy_verbs_report.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(R, f, indent=2, default=str)

print("=== HY_VERBS REPORT ===")
print(json.dumps(R, indent=2, default=str)[:6000])
print("=== report file: %s ===" % out_path)
