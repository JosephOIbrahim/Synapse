# SYNAPSE demo scaffold

The staged starting point for the H22 demo (see `../DEMO_SCRIPT.md`). The demo builds its
scene **live from prompts**; this hip is just the clean, Solaris-ready entry point.

## Files
- `synapse_demo.hip` — minimal starting scene: a `/stage` LOP network ready for set-dressing.

## Prerequisite: color management (OCIO)
The demo — and harness task **0.5** (`shot_login`) — requires **`OCIO`** pointed at your color
config (ACES or your studio config):
```
# Windows
set OCIO=C:\path\to\aces\config.ocio
# bash
export OCIO=/path/to/aces/config.ocio
```
This is an artist/pipeline choice. The harness only verifies that `OCIO` is **configured**;
it deliberately does not impose a config (a barebones one would degrade your color pipeline).

## Verify (harness task 0.5)
```
OCIO=<your config>  node harness/run.ts --task 0.5     # hip_opens + shot_login → green
```
Confirmed: with the demo hip present and `OCIO` set, task 0.5 passes (`hip_opens` ✓ `shot_login` ✓).
