import hou, json, time, traceback

OUT = r"C:\Users\User\SYNAPSE\.claude\worktrees\cache-p0\harness\notes\cache_h22_gui_assay_22.0.400.json"
rec = {
    "schema": "cache_h22_gui_assay/v1",
    "houdini_version": hou.applicationVersionString(),
    "ui_available": hou.isUIAvailable(),
}
try:
    geo = hou.node("/obj").createNode("geo", "gui_assay")
    g = geo.createNode("grid", "UNIT_CHECK_HEAVY")
    g.parm("rows").set(2000)
    g.parm("cols").set(2000)
    t0 = time.perf_counter(); g.cook(force=True); w1 = time.perf_counter() - t0
    rec["cook1"] = {"wall_s": round(w1, 4), "lastCookTime_raw": g.lastCookTime(), "cookCount": g.cookCount()}
    g.parm("rows").set(2001)
    t0 = time.perf_counter(); g.cook(force=True); w2 = time.perf_counter() - t0
    rec["cook2"] = {"wall_s": round(w2, 4), "lastCookTime_raw": g.lastCookTime(), "cookCount": g.cookCount()}
    rec["status"] = "ok"
except Exception:
    rec["status"] = "error"
    rec["traceback"] = traceback.format_exc()
with open(OUT, "w") as f:
    json.dump(rec, f, indent=2)
