# ▍Gate A L3-5 — Apprentice Session Card

**What this is.** One real Houdini session under the **Apprentice** license tier.
Serves two purposes at once (the same work, two purposes — reach-matrix.yaml notes):
1. **Gate A L3-5** — publish the README support matrix (Commercial/Indie/Apprentice/Education × panel/build/husk/renders).
2. **REACH R3** — fill the Apprentice/ApprenticeHD rows of `harness/reach/reach_matrix_2026-08-18.json`.

**Why it's human.** The seat's live license is **Indie** (measured, F5a probe 2026-08-15).
An Apprentice session needs an Apprentice login (free SideFX account) — a human act.
The harness refuses to run while Houdini is alive, and the rope operator card lists
L3-5 under "Your two tasks (agents can't do these)".

---

## The session — one sitting, ~20 minutes

### 0. Launch Apprentice Houdini

Launch Houdini under the Apprentice tier. On this seat the executables live at
`C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\`. Use the
**Apprentice** launcher (or log in with an Apprentice account so the license
server serves the Apprentice tier). Confirm the tier before anything else:

```
Python Shell:  print(hou.licenseCategory())
```

**Must print `licenseCategoryType.Apprentice`** (or ApprenticeHD). If it prints
Indie, the session is NOT an Apprentice session — stop and relaunch under the
Apprentice login. A wrong-tier session fills no cell.

### 1. Doctor

```
Python Shell:  exec(open(r'C:\Users\User\SYNAPSE\python\synapse\server\doctor.py').read())
```

Or via the panel's Scene Doctor (`python/synapse/panel/scene_doctor.py`).
Record: any RED lines, the bridge endpoint, the write-plane verdict. (The
bridge may be down — that's a finding, not a stop.)

### 2. The L3-1 prompt (the First-prompt recipe)

In the panel chat, type exactly:

> **Make me simple terrain — a grid displaced with mountain noise.**

This maps to `mountain_displace` in `python/synapse/panel/recipe_book.py`:
a 100×100 `grid` SOP wired into a `mountain` SOP (height 1.5). Two nodes, one connection.

**Record:** did the panel build the two nodes? Did the viewport show terrain?
Any error surfaced? (The recipe is the same on every tier — the point is the
panel runs at all under Apprentice.)

### 3. One render attempt

Render one frame (Karma or Mantra — whatever the session offers). **Record the
outcome verbatim.** Under Apprentice the expected answers are:

- **"Watermarked"** — render completed with a watermark. That's a real answer.
- **"Unavailable"** — the renderer refused (license-gated, like Indie's husk
  no-op). That's a real answer.
- **"Unknown"** — NOT an answer. If the render neither completes nor refuses
  cleanly, say what actually happened instead.

### 4. Close the task

```
python harness\rope\runner.py human L3-5 --done "Apprentice row filled"
```

---

## The matrix — what the session must fill

| Tier | panel | build (recipe) | husk | renders |
|---|---|---|---|---|
| Commercial | (session-independent — known) | (known) | (known) | (known) |
| Indie | runs (F5a probe, 2026-08-15) | runs | **unavailable** — husk cannot load the Karma delegate (`Unable to load render plugin: karma`, zero pixels, `--indie` included; render-freeze card) | in-process Karma survivable; XPU cold-compile = freeze risk (foreground_guard) |
| **Apprentice** | **← this session** | **← this session** | **← this session** | **← this session** |
| Education | (session-independent — known) | (known) | (known) | (known) |

**Discipline:** "Watermarked" and "unavailable" are answers; "unknown" is not.
Every cell the session fills must come from what the session actually showed.

---

## After the session

1. Publish the matrix in README.md (the L3-5 accept is `grep_min "Apprentice"` + manual "matrix row completed from a real Apprentice session").
2. Fill the Apprentice/ApprenticeHD rows of `reach_matrix_2026-08-18.json` (same evidence, two purposes) and re-run the three matrix goalposts.
3. `runner.py human L3-5 --done "Apprentice row filled"` closes the rope task.
