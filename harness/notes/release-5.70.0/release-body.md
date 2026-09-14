The panel names its own tools the way an artist would say them.

**"Create usd prim" is now "Create USD primitive."** The old label fallback ran
`.capitalize()`, which lowercases everything after the first character, so every
domain word an artist actually reads — USD, VEX, AOVs, OpenCL, MaterialX, Karma —
arrived destroyed. Only the `houdini_` namespace was stripped, so every
`synapse_`/`cops_`/`tops_` tool led with a namespace nobody needs to read.

| before | after |
|---|---|
| Create usd prim | **Create USD primitive** |
| Synapse solaris shotsetup karma xpu | **Solaris shot setup Karma XPU** |
| Cops reaction diffusion | **Reaction diffusion** |
| Composite aovs | **Composite AOVs** |

**A curated-label map had been running at 4 of 8, silently.** Four keys were written
against the tool registry's *second* column — the wire command name — while the label
function receives the *first*. A key that matches nothing fails quietly: the artist
just sees the derived label, which reads as a style choice rather than a miss. The
actual fix is the guard now standing behind it: a test that reads the live registry
and fails if any curated key stops being a real tool. No PySide, no Houdini — it runs
on stock CI and cannot skip.

## Install

`SYNAPSE-5.70.0-Setup.exe` upgrades in place and preserves projects, memory,
credentials and custom files — that path is one of the 19 qualification checks.

- The installer is **unsigned**. Verify against `SHA256SUMS.txt`.
- Running from source? Pull `v5.70.0`. **A live Houdini session holds the old
  `activity.py` in memory until the panel is reloaded or Houdini restarts** — the
  labels change on the next load, not the next turn.

## What was measured

- Stock suite **8920 passed / 430 skipped / 0 failed**.
- Panel seat suite on Houdini 22.0.400 offscreen: **201 passed / 5 failed** — the same
  five known reds as 5.69.0, **none new**.
- Installer qualification **19 of 19 PASS, exit 0**, against an isolated TestSetup that
  carries the same payload sha256 as the file published here.
- Read-only check against a running Houdini 22.0.400: the new labels are produced by
  that process's own tree, scene unchanged (9 nodes before and after, zero diffs).

`installer-verification.json` carries the full evidence, **including what was not run**
and one measurement that was discarded and why.

## Still open

- Five panel seat tests remain red. Two are recorded design conflicts awaiting a
  ruling; three are named and undiagnosed.
- The suite's skip population is not stable — 21 tests are disabled by a symbol missing
  from an out-of-tree dependency, and no gate in this repository can see it.
- `QMenu` modals can still hang a seat test; the guard documents the hole rather than
  implying it is closed.
- The panel's emergency halt fires, but does not survive a frozen main thread.
- Code signing, a clean Windows machine and native wizard visual qualification remain
  separate checks.

Full notes: [`docs/releases/v5.70.0.md`](https://github.com/JosephOIbrahim/Synapse/blob/v5.70.0/docs/releases/v5.70.0.md)
