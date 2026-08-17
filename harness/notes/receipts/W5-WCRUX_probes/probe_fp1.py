#!/usr/bin/env python3
"""W5-WCRUX probe 4 - FP1 audit (target 2): sample catalog rows against a FRESH
hython session MYSELF, with DIFFERENT nodes than the builder's deterministic
stride. Any committed row that does not equal a fresh live read is a laundered
claim; any row that cannot trace to the dump receipt is unprovenanced.

Two halves:
  STATIC   - every category file traces to _manifest.json + dump_receipt.txt
             (build key, counts, blake2b present, probe_errors 0).
  LIVE     - pick OFF-STRIDE types in dop/cop/chop/vop (disjoint from the
             builder's 20-type stride) + common SOP types the builder NEVER
             audited, re-read each in a fresh hython via the CANONICAL
             extraction (_type_record), and assert the committed base record
             (minus doc/wire_signature) == the live read, field for field.
"""
import subprocess, os, json, tempfile

CAT = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-catalog"
CATDIR = f"{CAT}/rag/catalog/h22.0.400"
HYTHON = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"
SELFDIR = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-wcrux/harness/notes/receipts/W5-WCRUX_probes"
HYSCRIPT = os.path.join(SELFDIR, "fp1_hython.py")

rep = {"probe": "fp1"}


def load_cat(domain):
    with open(f"{CATDIR}/{domain}.json", encoding="utf-8") as f:
        return json.load(f)


def builder_stride(names, n=20):
    names = sorted(names)
    if len(names) <= n:
        return set(names)
    stride = len(names) / n
    return {names[int(i * stride)] for i in range(n)}


def base_of(row):
    return {k: v for k, v in row.items() if k not in ("doc", "wire_signature")}


# ---- STATIC provenance ----------------------------------------------------
with open(f"{CATDIR}/_manifest.json", encoding="utf-8") as f:
    manifest = json.load(f)
rep["static"] = {
    "build": manifest["build"],
    "category_count": manifest["category_count"],
    "total_probe_errors": manifest["total_probe_errors"],
    "dump_receipt_present": os.path.exists(f"{CATDIR}/dump_receipt.txt"),
    "every_file_has_blake2b": all("blake2b" in v for k, v in manifest["files"].items()
                                  if not k.startswith("apex")),
    "PASS": (manifest["build"] == "22.0.400" and manifest["total_probe_errors"] == 0
             and os.path.exists(f"{CATDIR}/dump_receipt.txt")),
}

# ---- pick DIFFERENT nodes -------------------------------------------------
picks, committed, sampling = [], {}, {}
OFF = [3, 7, 11, 17, 23, 29, 37]   # off-stride ordinals (into sorted list)
for domain in ("Dop", "Cop", "Chop", "Vop"):
    types = load_cat(domain)["types"]
    names = sorted(types)
    stride = builder_stride(names)
    chosen = [names[i] for i in OFF if i < len(names) and names[i] not in stride]
    chosen = list(dict.fromkeys(chosen))[:6]
    sampling[domain] = {"chosen": chosen,
                        "disjoint_from_builder_stride": all(c not in stride for c in chosen),
                        "builder_stride_size": len(stride)}
    for tn in chosen:
        picks.append({"category": domain, "type": tn})
        committed[f"{domain}/{tn}"] = base_of(types[tn])

sop = load_cat("Sop")["types"]
for tn in ("box", "sphere", "grid", "attribwrangle", "copytopoints", "merge", "scatter"):
    if tn in sop:
        picks.append({"category": "Sop", "type": tn})
        committed[f"Sop/{tn}"] = base_of(sop[tn])
sampling["Sop"] = {"chosen": [p["type"] for p in picks if p["category"] == "Sop"],
                   "note": "builder audited 0 SOP types; all 'different'"}
rep["sampling"] = sampling
rep["picks_count"] = len(picks)

# ---- LIVE re-read via fresh hython (canonical _type_record) ---------------
picks_path = os.path.join(tempfile.gettempdir(), "wcrux_fp1_picks.json")
out_path = os.path.join(tempfile.gettempdir(), "wcrux_fp1_live.json")
with open(picks_path, "w", encoding="utf-8") as f:
    json.dump({"picks": picks}, f)

p = subprocess.run([HYTHON, HYSCRIPT, picks_path, out_path],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=300)
rep["hython_rc"] = p.returncode
rep["hython_tail"] = ((p.stdout or "") + (p.stderr or "")).strip()[-300:]

if p.returncode != 0 or not os.path.exists(out_path):
    rep["live"] = {"PASS": None, "reason": "hython live read did not complete - UNKNOWN"}
else:
    with open(out_path, encoding="utf-8") as f:
        live = json.load(f)
    mismatches, checked = [], 0
    for key, com in committed.items():
        lv = live.get(key)
        if lv is None:
            mismatches.append({"anchor": key, "why": "not read live"})
        elif "error" in lv:
            mismatches.append({"anchor": key, "why": f"live: {lv['error']}"})
        else:
            checked += 1
            if lv != com:
                diff_keys = sorted(set(com) | set(lv))
                diffs = {}
                for k in diff_keys:
                    cv, lvv = com.get(k), lv.get(k)
                    if cv != lvv:
                        if k == "parms":
                            cn = {pp["name"] for pp in cv or []}
                            ln = {pp["name"] for pp in lvv or []}
                            diffs["parms"] = {"only_catalog": sorted(cn - ln)[:8],
                                              "only_live": sorted(ln - cn)[:8],
                                              "n_catalog": len(cv or []), "n_live": len(lvv or [])}
                        else:
                            diffs[k] = {"catalog": cv, "live": lvv}
                mismatches.append({"anchor": key, "diffs": diffs})
    rep["live"] = {
        "types_read_live": len([k for k, v in live.items() if "error" not in v]),
        "types_compared": checked,
        "mismatches": mismatches,
        "PASS": (len(mismatches) == 0 and checked > 0),
    }

rep["FP1_PASS"] = (rep["static"]["PASS"] and rep.get("live", {}).get("PASS") is True)
print(json.dumps(rep, indent=2))
