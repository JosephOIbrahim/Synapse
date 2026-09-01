# CAPSULE 2026-09-01 EOD — the day the numbers replaced the guesses

Boot next session from this file. Grounded at close (19:3x) against origin/master `5bea9b25`.

## Position
Demo week mile 2/8 (Tue). Two releases shipped today: **v5.59.0** (BP2 pairs 1+2) and **v5.60.0** (BP2 closing wave),
both Latest-in-turn, tags at `06f8df50` / `0135176c`, CI green, triple-checked (state · CI · claims). v5.57.0 draft
published non-Latest at `adfe59e0`. No drafts remain. README/CLAUDE/VERSION/pyproject/__init__/docstring = 5.60.0.

## What landed (all CRUX/CRUXB SOUND-WITH-NITS unless noted)
- STORE: backend_health() honest report (M-5); FU-1 already on master since #16 — pinned.
- LATENCY: memory latency measured under budget (deposit p95 72 / recall 3 / reopen 130 ms; Moneta, N=200, .400 in-process).
- METER: post-close settle from transcript, per-leg tiers (referee/reasoning/mechanical), drift check, status honesty.
- PANELTRUTH: profile diff receipt, TOKEN refresh on task completion, docked-open float fix.
- HEALTHWIRE: health row carries embedder/dim/ratified verdict additively.
- METERLIVE: live settle proof on a scratch orchestrator; first orchestrator-measured leg 75356/278; Opus leg 21.5M/275k.
- PANELDESIGN: sec.7 spacing pass, five camera regions, density-keyed QSS, zero new colours; Expert pin green.
- NITS: **BROKEN** (CRUXB) — METER proof still self-compares; MONETA_FOLLOWUPS flip cites phantom test names. Branch bp2/nits intact, unmerged.

## Harness fixes landed by the referee seat (master)
- compile_wave.py takes a wave arg (no cross-wave clobber).
- drift.py skips closed legs (receipt/DONE/release).
- Test-CloseGate S5 reads the wave's own bus (was autorevise/bus.py → no BP leg ever reached done → settle never fired live). Effective next arm.
- relay-settings.json widened to what legs run (git all forms, powershell, gh read verbs); deny grows (tags, force push, master checkout, gh release writes). Gate C hook still refuses master pushes.
- Two integration-only test fixes (six mission_schema.py collide in sys.modules; latency artifacts are .jsonl).

## Ratified today (Joe words)
sec.2 call 7 (Curious on camera) · call 8 (latency budgets 500/1500/3000, N<=200) · waiver x2 (4 standing RC blockers) ·
merge pairs 1+2 · merge closing (NITS excluded) · publish v5.59.0, v5.60.0, v5.57.0 · relay widening.

## Open — tomorrow
1. **NITS2** (reasoning tier, fresh session): regenerate METER proof against the product commit's true parent (blob must differ);
   fix MONETA_FOLLOWUPS.md with REAL test names; re-verify 'open' readers. Then CRUX pass + merge word.
2. Spawns held: **METER-DEDUPE** (rails may double-count usage rows within one API response — CXB-F3);
   **METERLIVE-SOFTCLOSE** (read its receipt for the ask). Author as missions, dispatch on word.
3. Back-settle today's UNKNOWN ledger rows from transcripts (`rails.py charge --transcript`) so the day's spend is on file.
4. Joe's eyes in .400 (after panel reload): Ctrl+K docks · TOKEN face after a task · profile switch survives reopen ·
   health row shows five fields · five camera regions at the new rhythm. Paste memory_latency_probe.py → memory_latency_gui.jsonl.
5. **Takes x2 on camera** — item 4, the predicate. sec.4 branch rule: no HIT Tue → demo-ready Sun Sep 13 (re-ratify by receipt).
6. Legs ended up in auto mode despite --permission-mode acceptEdits (built-in default on Pro/Max v2.1.228+?). Probe why;
   auto mode's classifier blocked a harness proof `git add`. Legs must stay in acceptEdits.
7. Housekeeping: delete remote scratch branch bp2/integration; prune worktrees only if unusable; orchestrator stopped at close.
8. Beta items surfaced: R.R phantom check uses the 21.0.671 symbol table; shipping-leg suite recorded against 22.0.368 hython.

## Operator's card (unchanged commands)
python harness\battleplan\dashboard_bp2.py --open · status_bp2.py · bus.py read bp2 --types finding,block,refocus ·
arm_bp2.ps1 -Budget "10turns,360000000tokens" · watch_bp2.ps1 · Gate C push: $env:SYNAPSE_GATE_C=1; git push origin master; Remove-Item Env:SYNAPSE_GATE_C
Release ritual: VERSION → sync_version.py --write → RELEASE_vX.md → checks.py --task R.R --mode B → gh release create --draft → Joe: waiver + publish → 3x check.
