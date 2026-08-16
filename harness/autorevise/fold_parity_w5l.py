# _fold_parity.py - author W5-PARITY / W5-SEAT / W5-PCRUX, compile, fold into live manifest
import json, subprocess, sys
from pathlib import Path

AV = Path(r"C:\Users\User\SYNAPSE\harness\autorevise")
HY = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"
PREFS = r"C:\Users\User\OneDrive\Documents\houdini22.0"
BUS = ("BUS MANDATE (Joe word: teams that communicate): post your claim at start, "
       "post a findings message addressed to your peer leg when you resolve shared "
       "facts (hython path, env recipe), and post an explicit RELEASE at close - "
       "the wave5l F2/F3 no-release debt does not repeat here.")

PARITY = {
  "id": "W5-PARITY",
  "band": "BUILD",
  "class": "build",
  "name": "panel parity 1/2: prove every module the panel executes is the repo's, byte-for-byte, under the real hython",
  "source": {"doc": "houdini/python_panels/synapse_panel.pypanel",
             "anchor": "Joe word 2026-08-16: verify design panel is 1:1 with the repo; panel reported stale after relaunch"},
  "targets": [
    "1) harness/probes/parity_modules/probe_parity.py run under " + HY + " with HOUDINI_USER_PREF_DIR=" + PREFS + " so packages/synapse.json loads for real; if that hython is absent, enumerate Houdini* under Program Files, record the exact invocation tried, and proceed with the newest 22.0 - never silently substitute",
    "2) module provenance, EXHAUSTIVE: glob python/synapse/panel/**/*.py in the worktree, import every one under hython, assert module.__file__ resolves inside C:\\Users\\User\\SYNAPSE, and sha256(source on disk) == sha256(inspect.getsource(module)) - emit per-module rows {module, file, in_repo, sha_match} to harness/probes/parity_modules/results.json",
    "3) pypanel shim fidelity: parse the .pypanel CDATA, exec it under an offscreen QApplication (the W5-PANEL hython pattern), call onCreateInterface(); assert the returned widget's class comes from a repo file and that the shim's sys.modules flush actually ran (plant a sentinel module before exec, assert evicted)",
    "4) behavior pins on the LIVE built widget, master da6d2b33: source-inspect synapse_panel.py for next_font_scale at BOTH R1 sites (the Larger text action and _cycle_font_scale, commit 4c1134d8); tokens.next_font_scale first step from host 1.3 is >= 1.3; chat leading on 12 inserted lines grows document height by 12px +/- 0.5 (the W5-PANEL measured-effective method)",
    "5) every claim carries first-hand hython stdout committed alongside results.json; anything unmeasurable renders UNKNOWN with the exact blocked step; GUI pixel render is explicitly out of scope (Joe's seat)",
    "6) " + BUS
  ],
  "acceptance": [
    {"predicate": "every python/synapse/panel module imports under hython with __file__ in the repo and disk==imported sha, exhaustively (glob count == row count)", "evidence": "probe"},
    {"predicate": "pypanel shim exec builds the widget from repo modules offscreen; flush sentinel evicted", "evidence": "probe"},
    {"predicate": "R1 double-site wiring + font-floor step + leading delta measured on the live widget", "evidence": "test"}
  ],
  "deps": [], "readonly": False,
  "touches": ["harness/probes/parity_modules/"],
  "crucible_criteria": [
    "no claim without observation (face_token house rule) - a parity row without its hython stdout is a laundered claim",
    "exhaustiveness is a measured number: glob count asserted equal to results row count",
    "receipt is this leg's own closing commit; RELEASE posted on the bus"
  ],
  "spawn_classes": ["probe"],
  "note": "Answers Joe's stale report mechanically. Collision guard: touches harness/probes/ only - MEASURES owns validation/ and tests/."
}

SEAT = {
  "id": "W5-SEAT",
  "band": "BUILD",
  "class": "build",
  "name": "panel parity 2/2: prove the seat's resolution order - package, hpath, icons, and zero shadow installs",
  "source": {"doc": "harness/notes/h22/panel-observations-2026-08-16.md",
             "anchor": "Joe word 2026-08-16: verify 1:1 with repo; the load path must be proven, not assumed"},
  "targets": [
    "1) harness/probes/parity_seat/probe_seat.py under " + HY + " with HOUDINI_USER_PREF_DIR=" + PREFS + ": FIRST verify the synapse package actually loaded (hou.houdiniPath() contains C:/Users/User/SYNAPSE/houdini AND os.environ SYNAPSE_ROOT == the repo) - if it did not load, that IS the finding: diagnose why (pref-dir token, package scan), never fake a pass",
    "2) resource resolution via hou.findFile, receipts committed: houdini/toolbar/synapse.shelf and ALL config/Icons/SYNAPSE_*.png (assert count == 7 including SYNAPSE_synapse.png @2dd6bab6) resolve to paths inside the repo",
    "3) shadow-install sweep: importlib.metadata distributions + a walk of every sys.path entry and all site-packages for ANY other provider of a 'synapse' package; prove ORDER: index of repo/python in sys.path is lower than any other candidate; zero shadows is a counted claim",
    "4) multi-build audit: enumerate 'C:/Program Files/Side Effects Software/Houdini*'; if more than one 22.x exists, record each and which prefs dir it maps to; whether Joe's GUI launch used 22.0.400 renders UNKNOWN unless a prefs/log artifact proves it - never guessed",
    "5) pypanel hot-flush pin: parse houdini/python_panels/synapse_panel.pypanel, assert the sys.modules flush block is present (panel-reopen == hot reload; restart only for icons/shelf)",
    "6) " + BUS + " Consume W5-PARITY's hython/env findings from the bus if posted first; otherwise resolve independently and post yours."
  ],
  "acceptance": [
    {"predicate": "package + hpath resolve to the repo under hython with the live prefs dir, first-hand", "evidence": "probe"},
    {"predicate": "all 7 icons + shelf file resolve via hou.findFile into the repo; count asserted", "evidence": "probe"},
    {"predicate": "zero shadow synapse installs; sys.path order proven with indices", "evidence": "probe"}
  ],
  "deps": [], "readonly": False,
  "touches": ["harness/probes/parity_seat/"],
  "crucible_criteria": [
    "no claim without observation; every resolution claim carries hou.findFile stdout",
    "the multi-build question stays UNKNOWN if unprovable - the honest gap Joe closes at his seat",
    "receipt is this leg's own closing commit; RELEASE posted on the bus"
  ],
  "spawn_classes": ["probe"],
  "note": "Disjoint claim from W5-PARITY (parity_seat/ vs parity_modules/). Together they define '1:1 with repo' as: repo-sourced modules, byte-equal, resolved first, no shadows, resources from hpath."
}

PCRUX = {
  "id": "W5-PCRUX",
  "band": "TRUTH",
  "name": "parity crucible: adversarial gate over the two parity probes - no verdict inherited",
  "source": {"doc": "houdini/python_panels/synapse_panel.pypanel",
             "anchor": "house rule: CRUX before any verdict reaches Joe; the audit lens is claim-without-observation"},
  "targets": [
    "1) re-execute BOTH probes from scratch in this worktree - fresh hython runs, own stdout; never trust peer receipts",
    "2) attack exhaustiveness: independent glob of python/synapse/panel/**/*.py, compare to W5-PARITY's row count; a missed module is a failed audit",
    "3) attack the build question: did the probes exercise the hython the GUI seat launches? cross-examine W5-SEAT's multi-build audit; if unprovable it stays UNKNOWN and is said out loud in the verdict",
    "4) attack exec fidelity: the pypanel runs via exec in Houdini's panel context - verify the probe's exec reproduced that (no __file__, module flush) rather than a plain import that would mask loader differences",
    "5) mandate table, binary per leg: receipt HEAD exists and precedes receipt write; receipt is the leg's own closing commit; RELEASE posted (the wave5l F2/F3 check)",
    "6) verdict: harness/notes/receipts/W5-PCRUX_verdict.md + W5-PCRUX.json committed on this leg's branch as its own closing commit; drop flag file harness/notes/h22/w5p-landed.flag"
  ],
  "acceptance": [
    {"predicate": "both probes independently re-executed with first-hand evidence; divergences enumerated", "evidence": "probe"},
    {"predicate": "mandate table binary per leg incl. bus RELEASE check", "evidence": "check"},
    {"predicate": "verdict names every UNKNOWN and exactly what Joe's seat must observe to close each", "evidence": "check"}
  ],
  "deps": ["W5-PARITY", "W5-SEAT"],
  "readonly": True, "touches": [],
  "crucible_criteria": [
    "carries CRX0 + the wave5l precedents as standing checks",
    "unobtainable renders UNKNOWN, never zero and never an estimate"
  ],
  "spawn_classes": ["probe"],
  "note": "Scope frozen to the parity pair. W5-WCRUX keeps the substrate trio. Merge of parity probe artifacts remains Joe's word."
}

MISSIONS = {"w5p_parity.json": PARITY, "w5p_seat.json": SEAT, "w5p_crux.json": PCRUX}
for fn, m in MISSIONS.items():
    (AV / "missions" / fn).write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", fn)

for script in ("compile_wave.py", "make_control.py"):
    r = subprocess.run([sys.executable, str(AV / script)], capture_output=True, text=True, cwd=str(AV.parent.parent))
    print(script, "->", r.returncode, (r.stdout or r.stderr).strip()[-300:])
    if r.returncode != 0:
        sys.exit(f"HALT: {script} failed")

rows = json.loads((AV / "waves" / "wave5.rows.json").read_text(encoding="utf-8"))
man_path = AV / "waves" / "wave5l.live.json"
man = json.loads(man_path.read_text(encoding="utf-8"))
existing = {leg["id"] for leg in man["legs"]}
added = [r["id"] for r in rows
         if r["id"] in ("W5-PARITY", "W5-SEAT", "W5-PCRUX") and r["id"] not in existing]
man["legs"] += [r for r in rows if r["id"] in added]
man["_comment"] += (" | FOLDED 2026-08-16 on Joe word 'use agent teams that have communication "
                    "between agents to verify design panel is 1:1 with the repo': W5-PARITY + "
                    "W5-SEAT (bus-communicating probes) + crucible W5-PCRUX.")
man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
print("appended", added, "-> manifest now", len(man["legs"]), "legs")
