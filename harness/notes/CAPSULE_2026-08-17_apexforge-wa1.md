# CAPSULE 2026-08-17 — APEXFORGE WA1 (authored, proven, parked at arm)

## State
- `harness/apexforge/` = new sibling harness (autorevise clone): own bus, wa1-* worktrees, wavea1/* branches. Zero shared writable surface with W5L.
- Wave WA1 (APEX blueprint phases 0–4): WA1-TRUTH (G1/G4+C1), WA1-XREF (C3), WA1-WIRE (C2, deps TRUTH), WA1-RECIPE (G2, deps TRUTH), WA1-ACRUX (crucible, deps all).
- 5/5 missions validate; prompts compiled; manifest legs/v1; **-DryRun control pass GREEN** (dep gating exact, Opus 4.8 dispatch line correct, zero footprint). Log: `harness/apexforge/waves/wavea1.dryrun.log`.
- Committed `9f3bf690`, **pushed to origin/master** (Gate C word given + honored).
- Contracts: `.synapse/contracts/apex-{truth-reseed,help-xref,wire-matrix,recipes-migration}.yaml` (force-added per tracked-contract precedent). WA2 red contracts (lops-beta, mcp-rerecord) not yet authored.
- Source doc in-tree: `docs/APEX_H22_BLUEPRINT.md` (paths resolved: science/panel → python/synapse/...).

## Tomorrow-you: one command to arm
1. `powershell -File C:\Users\User\SYNAPSE\harness\apexforge\arm_wa1.ps1`
2. Watcher: `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\User\SYNAPSE\harness\apexforge\watch_wa1.ps1' -WindowStyle Hidden`
3. Board: `python C:\Users\User\SYNAPSE\harness\apexforge\status_wa1.py`
4. ACRUX toast → read receipt → merge words per branch (--no-ff).

## Watch-fors
- `harness/autoresearch/probes.py` = TRUTH/WIRE shared seam → bus-serialized by design; a stuck open claim = holder crashed, check its log.
- RECIPE goalpost must FAIL-LOUD without catalog artifact (never skip) — ACRUX re-runs the RED leg itself.
- apex_truth build stamp must be runtime-observed; typed stamp = the defect class.

## Queued
- Release update on GitHub: **blocked behind g5 re-run** (W5L fix, Joe's hands) + g6–g9 close. Surface + take the word then.
- WA2 authoring after WA1 closes: bench rungs A1–A6, apex-lops-beta (amber→red), apex-mcp-rerecord (red, Joe launches).
- Teach-down delivered 2026-08-17 in-session (sea level complete).
