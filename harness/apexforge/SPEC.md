# SPEC — APEXFORGE (APEX ground-truth harness)

*Status: ASSEMBLED 2026-08-17. Becomes binding at merge — merge is Joe's word.
Companion papers: `docs/APEX_H22_BLUEPRINT.md` (the work order it executes),
`harness/SPEC.md` (governing harness authority), `harness/autorevise/SPEC.md`
(the architecture it clones), `harness/rsi/SPEC.md` (gate law).*

---

## 1 · What it is

AUTORESEARCH runs probe campaigns. AUTOREVISE runs revision campaigns.
**APEXFORGE runs a truth campaign**: the APEX blueprint's GATE + CAPABILITY
phases (0–4) as one agent-team wave, producing versioned evidence artifacts
(callback catalog, wire matrix, help-xref referee report) and executing the
phantom-name migration those artifacts make checkable. It is a **sibling clone**
of autorevise, not an extension of it:

| Function | Provided by | New here? |
|---|---|---|
| Dispatch, worktrees, model passthrough | `harness/orchestrate.ps1` + legs/v1 manifest | no — reused verbatim |
| Mission admission | `mission_schema.py` (ID family `WA<n>-TAG`) | cloned, one-line edit |
| Mission → row + brief | `compile_wave.py` | cloned, one-line edit |
| Teams that talk | `bus.py` → **`apexforge/bus/<wave>/`** | cloned verbatim, own root |
| Probe execution | autoresearch probe kinds (TRUTH/WIRE author new ones) | invoked |
| Contracts | `.synapse/contracts/apex-*.yaml` (4 for WA1, 2 red for WA2) | **yes** |

**Why a sibling, not a wave family inside autorevise:** W5L is live. Own bus
root + own worktree prefix (`wa1-*`) + own branch family (`wavea1/*`) + own
pid/log files = the two harnesses share zero writable surfaces. One writer per
surface holds by construction, not by discipline.

## 2 · Wave WA1 (compiled here, armed on the word)

| Leg | Blueprint | Deps | Shared seam |
|---|---|---|---|
| WA1-TRUTH | G1+G4+C1 · re-seed, catalog+ports artifact, stamp agreement | — | `autoresearch/probes.py` (with WIRE) |
| WA1-XREF | C3 · help-cache referee, three-way diff, phantoms | — | none (recipes scan read-only) |
| WA1-WIRE | C2 · wire matrix + @/$ table | TRUTH | `autoresearch/probes.py` (with TRUTH) |
| WA1-RECIPE | G2 · phantom-name migration + catalog goalpost | TRUTH | none |
| WA1-ACRUX | crucible · audits all four, builds nothing | all four | read-only |

**Dynamic handoff:** WIRE and RECIPE declare `deps: [WA1-TRUTH]` for dispatch
ordering, but consume the catalog **via the bus** the moment TRUTH posts the
artifact path — mid-wave, before any merge. Scaffolding work (probe kinds,
parser tests, fixture-driven goalposts) starts immediately regardless.

## 3 · Law (unchanged, restated)

Push · merge · tag · `drop.json` · any `ratified`/`held` flip — **Joe, per
act**. Green ACRUX is a precondition for merge words, never a substitute.
Unobtainable renders UNKNOWN — schema-enforced, crucible-re-checked, and for
this harness specifically: a skipped hython probe is UNKNOWN (hytest shim,
skip ≠ pass), and **any APEX name not proven by the apex_truth artifact is
hypothesis** — the phantom class (`apex::rig::`, `apex::sop::`) is what this
wave exists to make unshippable.

## 4 · Run order (each numbered act = one word)

1. Joe words the arm → `powershell -File harness/apexforge/arm_wa1.ps1`
   (builds manifest from `waves/wavea1.rows.json`, launches detached
   orchestrator, pid → `harness/notes/h22/orchestrator-wa1.pid`).
2. Detached watcher → `harness/apexforge/watch_wa1.ps1` (desktop alert + flag
   on ACRUX receipt).
3. Poll → `python harness/apexforge/status_wa1.py` (one pass: orchestrator
   liveness, per-leg ahead counts, receipts, bus lines, open claims, flag).
4. ACRUX green/blocked → Joe's merge words, per branch (`--no-ff`).
5. WA2 authoring (bench rungs A1–A6, `apex-lops-beta.yaml` amber→red,
   `apex-mcp-rerecord.yaml` red) — a fresh authoring pass after WA1 closes.
