# ▍SYNAPSE Render-Freeze — Operator's Card

**The system:** an agent-team harness that diagnoses (done) and fixes the Karma render freeze.
**The freeze:** `handlers_render.py:497` `node.render()` runs foreground on Houdini's main thread → whole UI freezes.
**The fix (staged, not shipped):** move renders out-of-process via husk — but that's gated on **one live check** below.

---

## ▍The kit

| File | What it is |
|---|---|
| `scripts/render_watch.ps1` | **Out-of-band watcher** — reads Houdini from outside while it's frozen |
| `scripts/build_freeze_repro.py` | Builds the minimal repro scene (`freeze_repro.hip`) |
| `scripts/husk_spike.py` | **First move** — proves husk removes the freeze + captures unsaved edits |
| `scripts/freeze_trace.py` | Existing fsync'd tracer (panel-path confirm) |

---

## ▍FIRST MOVE — the husk export-fidelity spike (do this before anything else)

> The diagnosis is confirmed. The open risk is the **fix's** export fidelity + no-freeze delivery. One shot settles it.

```
1.  Launch Houdini 22.0.368 fresh.
2.  Python Shell:   exec(open(r'C:\Users\User\SYNAPSE\scripts\build_freeze_repro.py').read())
3.  PowerShell:     pwsh -File C:\Users\User\SYNAPSE\scripts\render_watch.ps1
4.  Python Shell:   exec(open(r'C:\Users\User\SYNAPSE\scripts\husk_spike.py').read())
5.  Read the VERDICT the spike prints + cross-check the watcher.
```

**Reads as PASS if:** watcher `Responding` stays **True** the whole time, `husk=1 OUT-OF-PROCESS` appears, and the EXR shows the **unsaved edit** the spike made (brighter light, moved sphere).
**Reads as the Indie fork if:** husk writes **no file** → read `hou.licenseCategory()` in that session. Indie ⇒ husk no-ops ⇒ fix needs the Commercial branch + a separate Indie preview path.

---

## ▍The three questions the spike answers

- **Q1 — Non-freeze?** `Responding` stays True → husk removes the freeze. *(This is the whole point.)*
- **Q2 — Export fidelity?** EXR reflects the unsaved LOP edit → `Flatten().Export()` is faithful.
- **Q3 — Assets resolve?** Add a *textured* material, re-run → grey = the relative-path caveat bites (pivot to ROP `lopoutput` export).

---

## ▍If you want the full isolation matrix (only if the spike is ambiguous)

Fresh Houdini session **per cold cell** (open `freeze_repro.hip`), watcher armed, render **one** frame:

```
# Karma cell:
k=hou.node('/stage/karmarendersettings1'); k.parm('engine').set('xpu')   # or 'cpu'
k.parm('resolutionx').set(64); k.parm('resolutiony').set(64)
hou.node('/stage/usdrender_rop1').render(frame_range=(1,1), verbose=True)
```

**Fingerprints:** XPU = few cores + GPU climbing · CPU = many cores + GPU idle · Mantra = houdini idle + `mantra.exe` busy.
**Cold vs warm:** recovers = latency, never recovers = hang. ⚠ **To force a real COLD cell, delete `%LOCALAPPDATA%\NVIDIA\OptixCache\Houdini22.0` first** — the cache persists on disk, so "relaunch = cold" is otherwise false.

---

## ▍Kill & recover

```
# out-of-process (husk/mantra visible) — try this FIRST, may save the session:
Get-Process husk,mantra -ErrorAction SilentlyContinue | Stop-Process -Force

# in-process Karma (no subprocess) — only a relaunch clears it:
Stop-Process -Id <houdini-pid> -Force
```

Evidence survives the kill: `render_watch.ps1` CSV + `freeze_trace.log` are flushed to `<repo>\.synapse\` every line. Read them **after** killing — don't scrape the frozen UI.

---

## ▍The Indie fix layer (BUILT 2026-07-18 — in the working tree)

The spike settled the fork: live license = **Indie**, and husk **cannot load the Karma delegate** (`Unable to load render plugin: karma`, zero pixels, `--indie` flag included) — but Houdini stayed responsive throughout, so the out-of-process architecture is proven and merely license-blocked. The shipped fix makes the in-process path **survivable**:

| Piece | What it does |
|---|---|
| `server/foreground_guard.py` | Refuses accidental heavy foreground renders. XPU gate = **OptiX cache-warmth** (cold ⇒ refuse at ANY resolution — the fixed compile cost IS the freeze) |
| `server/render_session.py` | Thread-safe token registry for in-flight renders |
| `_handle_render_bounded` (handlers_render.py) | Tool-level `render` wrapper: poll / single-flight / guard / **60s bounded wait → `render_in_progress` token**; `_handle_render` itself unchanged |
| `scripts/prewarm_xpu.py` | Pays the XPU cold-compile at a moment YOU choose (~2 min UI pause once, then cached until a driver/Houdini update) — with an honest cache-delta check |

**Path reality:** the bounded token flow is live on the `/synapse` WS path. The panel (Qt main thread) and `/mcp` (transport marshals the handler onto main) are **guard-only by design** — a bounded wait on the main thread would deadlock.

**New `houdini_render` payload keys:** `poll` (token) · `wait_budget_s` (default 60; 0 = immediate token) · `force_foreground` · `force_new`.

---

## ▍Ship gate (status)

1. ~~Live license read in the bridge session~~ — **DONE: Indie.**
2. ~~husk emits pixels under it~~ — **DONE: REFUTED** (delegate license-gated; husk path shelved until Commercial/Education — the engineering is proven and ready).
3. Warm-cache re-time of the 64² render — **OPEN**: run `prewarm_xpu.py`, then re-render; seconds ⇒ the 92s was cold compile, not a hang.
4. ~~Detached-poll merge spec for husk~~ — **superseded on Indie** by the bounded in-process layer; revisit on a license change.
5. Full `pytest tests/` green + crucible review of the diff — **IN FLIGHT** (suite runs detached to `.synapse/full_suite_20260718.txt`).
