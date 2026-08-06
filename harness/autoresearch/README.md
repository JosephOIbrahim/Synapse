# AUTORESEARCH — Operator's Card (v1.1)

Unattended probe campaigns against live Houdini, with a local-model scout.
The model authors **questions**. Only probes produce **answers**.
Feeds BLOCKS: evidence in, fixtures out.

Three tiers: **Claude** orchestrates · **scout tier** (ollama, see `tiers.json`)
authors + triages · **hython** executes probes — deterministic, zero model.

---

## Run it

```powershell
# 0 · smoke check — plain Python, no Houdini needed
python harness\autoresearch\runner.py --mission harness\autoresearch\missions\solaris_basic.json --validate-only

# 1 · load the driver
. .\harness\autoresearch\drive_autoresearch.ps1

# 2 · launch probes (detached — returns instantly)
Start-AutoResearch -Mission solaris_basic

# 3 · poll (repeat until DONE; ~60s hython boot, then fast)
Get-AutoResearchState

# 4 · gate + release lock
Complete-AutoResearch

# 5 · scout: DeepSeek triages the evidence, proposes the next mission
Start-AutoResearchScout            # optionally -Objective "close the LOP coverage gap"
Get-AutoResearchState              # same poller, same sentinels

# 6 · run what the scout proposed (after you eyeball it)
Start-AutoResearch -Mission proposed/next_<slug>
```

---

## What you'll see

Probe run DONE → `runs\<mission>_<stamp>\lop_truth_22.0.368.json` — every entry:
claim · value · probe · build · timestamp.
Scout DONE → `runs\scout_<stamp>\triage.md` (read this) + `triage.json` +
`missions\proposed\next_*.json` (runnable only by your explicit Start-).

The scout's output passes two deterministic gates before anything lands in
`proposed\`: the **literal fence** (only type names the evidence proved alive)
and **schema validation**. Rejections are listed in triage.json, never silently dropped.

---

## When it breaks

**`LAUNCHING` forever, `run.err.log` has content** → hython or python crashed on boot.
The status command prints the log tail. Usual suspect: wrong hython path — pass `-Hython <path>`.

**Heartbeat age > 120s, no sentinel** → hung. `Stop-AutoResearch`, relaunch.

**Scout FAILED** → the sentinel file says whether ollama is down
(`ollama serve`) or the tier's model is missing (`ollama list`, `tiers.json`).

**`lock held by pid N`** → previous probe run never released. Auto-clears if N is dead.

---

## Where it lives

```
harness\autoresearch\
├── runner.py                    # detached hython process (probes)
├── probes.py                    # the only file that touches hou
├── scout.py                     # detached python process (ollama author/triage)
├── tiers.json                   # model names live HERE only
├── mission_schema.py            # validation, plain Python
├── missions\solaris_basic.json  # question sets — edit freely, re-validate
├── missions\proposed\           # scout output, ratified by YOUR Start- call
├── drive_autoresearch.ps1       # DC entry points
└── runs\<stamp>\                # state.json · logs · evidence · DONE/FAILED
```

Safe to touch: mission files, tiers.json, this card. `runs\` is disposable
evidence — never hand-edit an evidence file; re-run the mission instead.

**No blocking watcher exists on purpose.** Poll with repeated
`Get-AutoResearchState` calls — a wait loop inside a Desktop Commander call
is the exact failure this design routes around.

---

## Fixtures (BLOCKS)

Fixture definitions live at repo root: `fixtures\<name>.json` - node types,
exact names, wires, positions, parm pins. Parm NAMES are probe-verified;
parm VALUES are design choices. Each fixture carries its own baked baseline
(sha256 + build + canonicalizer) once verified.

Verify a fixture (repeat-N build + stage hash, watch it in the live terminal):

```powershell
Start-AutoResearch -Mission fixture_verify
```

Open the live terminal window anytime:

```powershell
Show-AutoResearchTerminal
```
