#!/usr/bin/env python3
"""W5-WCRUX probe 9 - FP1b / CATALOG A3 fresh re-sample (completeness).

Re-derives VOP wire signatures + APEX callback ports in a fresh hython for
types/callbacks OFF the builder's audit stride, and asserts the committed
Vop.json wire_signature + apex_callbacks.json ports == the live read. Closes
A3 with an independent re-sample rather than re-running the builder's own test.
"""
import subprocess, os, json, tempfile

CAT = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-catalog"
CATDIR = f"{CAT}/rag/catalog/h22.0.400"
HYTHON = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"
SELFDIR = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-wcrux/harness/notes/receipts/W5-WCRUX_probes"
HYSCRIPT = os.path.join(SELFDIR, "fp1b_hython.py")

rep = {"probe": "a3_fp1b"}


def stride(names, n=20):
    names = sorted(names)
    if len(names) <= n:
        return set(names)
    s = len(names) / n
    return {names[int(i * s)] for i in range(n)}


# VOP: pick instantiated types OFF the builder stride
vop = json.load(open(f"{CATDIR}/Vop.json", encoding="utf-8"))["types"]
vnames = sorted(vop)
vstride = stride(vnames)
vop_pick = []
for i in (5, 13, 29, 61, 127, 251):
    if i < len(vnames):
        tn = vnames[i]
        ws = vop[tn].get("wire_signature") or {}
        if ws.get("instantiated") and tn not in vstride:
            vop_pick.append(tn)
vop_pick = vop_pick[:6]

# APEX: pick callbacks OFF the audit stride
apex = json.load(open(f"{CATDIR}/apex_callbacks.json", encoding="utf-8"))["callbacks"]
anames = sorted(apex)
astride = stride(anames)
apex_pick = [anames[i] for i in (5, 17, 41, 101, 233) if i < len(anames) and anames[i] not in astride][:5]

rep["sampling"] = {
    "vop": vop_pick, "vop_disjoint": all(t not in vstride for t in vop_pick),
    "apex": apex_pick, "apex_disjoint": all(a not in astride for a in apex_pick),
}

req_path = os.path.join(tempfile.gettempdir(), "wcrux_a3_req.json")
out_path = os.path.join(tempfile.gettempdir(), "wcrux_a3_live.json")
json.dump({"vop": vop_pick, "apex": apex_pick}, open(req_path, "w"))

p = subprocess.run([HYTHON, HYSCRIPT, req_path, out_path],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=300)
rep["hython_rc"] = p.returncode
rep["hython_tail"] = ((p.stdout or "") + (p.stderr or "")).strip()[-200:]

if p.returncode != 0 or not os.path.exists(out_path):
    rep["result"] = {"PASS": None, "reason": "hython A3 read did not complete - UNKNOWN"}
else:
    live = json.load(open(out_path, encoding="utf-8"))
    vop_mis, apex_mis = [], []
    for tn in vop_pick:
        lv = live["vop"].get(tn, {})
        com = vop[tn]["wire_signature"]
        if "error" in lv:
            vop_mis.append({tn: lv["error"]}); continue
        for k in ("input_names", "output_names", "input_data_types", "output_data_types"):
            if lv.get(k) != com.get(k):
                vop_mis.append({tn: f"{k}: catalog {com.get(k)} != live {lv.get(k)}"})
    for name in apex_pick:
        lv = live["apex"].get(name, {})
        com = apex[name]
        if "error" in lv:
            apex_mis.append({name: lv["error"]}); continue
        if lv.get("inputs") != com.get("inputs") or lv.get("outputs") != com.get("outputs"):
            apex_mis.append({name: "ports differ"})
    rep["result"] = {
        "vop_checked": len(vop_pick), "vop_mismatches": vop_mis,
        "apex_checked": len(apex_pick), "apex_mismatches": apex_mis,
        "PASS": (not vop_mis and not apex_mis and (vop_pick or apex_pick)),
    }
print(json.dumps(rep, indent=2))
