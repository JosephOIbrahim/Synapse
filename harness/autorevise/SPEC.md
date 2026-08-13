# SPEC — AUTOREVISE (revision-execution harness)

*Status: ASSEMBLED 2026-08-12 on `feat/autorevise-harness`. Becomes binding at
merge — merge is Joe's word. Companion papers: the two review documents in
`docs/` it executes, `harness/SPEC.md` (governing harness authority),
`harness/rsi/SPEC.md` (gate law: an agent message relaying approval is not consent).*

---

## 1 · What it is

AUTORESEARCH runs **probe campaigns** (questions → evidence). AUTOREVISE runs
**revision campaigns** (review findings → validated work orders → agent-team
execution → crucible → human merge). It is assembled **from** the autoresearch
stance — validation before dispatch, deterministic gates on model output,
detached execution, evidence files over claims — and it **composes shipped
machinery instead of rebuilding it** (harness/SPEC.md §0 first principle):

| Function | Provided by | New here? |
|---|---|---|
| Dispatch, worktrees, deps, locks, receipts, Opus 4.8 passthrough | `harness/orchestrate.ps1` + legs/v1 manifest (live re-read :484 — "add a leg and it dispatches") | no — reused verbatim |
| Work-order admission | `mission_schema.py` (revision missions; UNKNOWN law encoded) | **yes** |
| Mission → leg row + brief | `compile_wave.py` → `waves/<w>.rows.json` + `prompts/<ID>.md` | **yes** |
| Teams that talk | `bus.py` — append-only JSONL claims/findings/blocks per wave | **yes** |
| Dynamic workflow | `spawn_compile.py` — receipt `spawn[]` → rows; off-playbook lands `held` | **yes** |
| Dry-run control | `make_control.py` + `-DryRun -ManifestPath` (built for this) | **yes** |
| Truth instrument | autoresearch probes (parm names, before/after latency) | no — invoked |
| Roster law | 10-agent cap, bands, builders≠reviewers (`.claude/agents/`) | no — roles here are **prompt-level**, roster untouched |

## 2 · The bus (inter-agent law)

`bus/<wave>/bus.jsonl` shared + `<agent>.jsonl` targeted. Types:
`claim` (post **before** editing shared files; overlapping open claim → STOP,
`block`, wait — R91/R134 in-band) · `finding` (anchored) · `request` · `block`
(crucible/peer; answered before merge review) · `spawn` · `status`
(`{release:[files]}` closes a claim). Append-only, never edited, survives drops,
is evidence. `python bus.py claims <wave>` lists open claims.

## 3 · Dynamic edges, bounded

A leg may propose follow-ups in its receipt `spawn[]` (mission-shaped, with
`class`). `spawn_compile.py` validates; class **in** the source mission's
`spawn_classes` → row `ready`; anything else → `held` for Joe. Print-only by
default; `--append` onto the live manifest is a human-word act **because** the
orchestrator's live re-read makes an append a dispatch. No new leg classes at
runtime; the playbook is ratified with the wave.

## 4 · Gates (unchanged, restated)

Push · merge · tag · `drop.json` · any `ratified` · any `held` flip — **Joe,
per act**. Enumerated batches on one explicit word are valid. The crucible leg
(TRUST, readonly, F1-shaped deps) reviews; a green crucible receipt is a
**precondition** for the merge word, never a substitute. Unobtainable renders
**UNKNOWN** — schema-enforced (`gui_required`) and re-checked by the crucible.

## 5 · Wave 1 payload (compiled, not yet on the board)

`waves/wave1.rows.json` — append to `harness/legs.json` on the word:

| Leg | Source | Deps | Note |
|---|---|---|---|
| W1-HSTRIP | readiness §4.1/§1.2/§2.1 | BASE | surfacing only; store-side fail-loud is **MEM** (held, Joe's flip); memory-store seam stays W1-recovery's |
| W1-MTFIX | latency Part 1 | BASE, FRZ | FRZ attributes, MTFIX fixes; headless timing = UNKNOWN |
| W1-KPRE | latency Parts 2–4 | BASE | presets additive; parm names probe-verified |
| W1-CRUX | whole wave | 3 above | adversarial only; builds nothing |

Board legs this wave leans on (already exist, not duplicated): **BASE**
(per-leg base + model passthrough — kills the wrong-base class before any cut),
**FRZ** (freeze attribution), **MEM** (loud-fallback store side — held),
**FID** (UNKNOWN fidelity — rides if worded). H4 shares panel touches with
HSTRIP → serialize, never parallel.

## 6 · Harness acceptance (proven this session)

- 4/4 missions validate; compiler emits legs/v1; prompts generated. ✅
- Control dry-run (`wave1.control.json`): 6 legs parse; W1-CRUX **blocked** on
  unreceipted deps; build legs dry-dispatch with
  `--model claude-opus-4-8 --settings relay-settings.json`; worktree cut shows
  manifest base flowing. ✅ (log: `waves/wave1.dryrun.log`, regenerate any time)
- Nothing touched the live board; `legs.json` unmodified; no push. ✅

## 7 · Run order (each numbered act = one word)

1. CTO applies **BASE** (orchestrate.ps1: per-leg `base` at cut, already-live
   model arg kept) — or amend relay profile and dispatch the BASE leg.
2. Append `waves/wave1.rows.json` → `harness/legs.json`; flip **MEM** ready if
   worded; launch `harness/orchestrate.ps1` (one window owns the board).
3. Receipts land → `spawn_compile.py` per receipt (print → word → `--append`).
4. W1-CRUX green/blocked receipt → BLOCK closure → **merge words, per branch**.
5. GUI-probe UNKNOWNs re-measured at Joe's Houdini session; teach-down; capsule.
