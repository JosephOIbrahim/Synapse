# H22 Context-Knowledge Campaign — Blueprint

**Status:** DRAFT — pending Gate A ratification (uncommitted until the word)
**Authored:** 2026-08-15 · Driver: Fable 5 (establishment) → Opus 4.8 (leg agents, manifest-pinned)
**Source:** h22-context-knowledge-recon-2026-08-15 (19-agent recon, pre-flight re-verified)

## Mission
`scout` / `knowledge_lookup` / `recall` answer node-and-parameter questions for every
relevant H22 context, phantom-guarded, at the bar COP/LOP already meet.
**Out of scope:** new MCP tool families; planner/recipe coverage; APEX local corpus
(D-H22-2 federation holds by default — policy memo, not a build).

## Repo state at authoring (observed this session)
- master `2ceb68b7` (v5.49.0), CI green (run 31885542151), **ahead 1 of origin** (recon doc, unpushed)
- W1 `fix/memory-store-recovery` MERGED · `fix/moneta-schema-registration` MERGED — no surface conflict
- Session-verified anchors: `knowledge.py:45` _CONTEXT_RANK · `:160` hardcoded ".368" hint ·
  `i1_extract.py:121` PARAM_SECTIONS lacks @inputs/@outputs · `:59` BUILD = helpdoc.BUILD
- Pre-flight-verified only (re-confirm at leg time): `knowledge.py:141` 2-token gate ·
  rigging-drift hard-fail internals (def observed at `checks.py:324`; report cited :361-363)
- Model plumbing live: `orchestrate.ps1:228` manifest-level "model" passthrough

## Invariants (house rules bound to this campaign)
1. **UNKNOWN never zero, never an estimate.** Denominators headless-`hython` only, native/third-party split.
2. **One writer per surface.** `knowledge.py` has exactly one leg owner; ledger design is single-writer.
3. **Per-act words:** arm, merge, push, wiring flips, ratified state. Relayed approval is not consent.
4. **Backup-before-mutation** on the JSON→SQLite move; keep-both-never-delete on any collision.
5. **CRUX before merge.** Capsules only at closed loops.

## Wave K1 — four surface-disjoint legs
**LEG-KNOW** (worktree) — `python/synapse/routing/knowledge.py` + promote path
- emit `id` + `searchable_text` at promote (scout visibility)
- key `(context, type)` + disambiguation list replaces silent pick
- `context` / `k` parameters added to tool schema
- type-name intent test replaces the 2-token bail-out
- return internal names + channels, uncapped (kills the 12-label ceiling)
- similarity floor: dense path can answer not-found
- build-stamp check at corpus load; kill the `:160` ".368" hint
- conformance test written against the NEW contract (runtime checkpoint guard)

**LEG-HELPDOC** (worktree) — parameterize `helpdoc.BUILD`/`HELP_DIR`; update importers (`i1_extract.py:59` et al)
**LEG-GUARD** (worktree) — `checks.py` freshness gate + per-context ledger over `legs.json` (single-writer design)
**LEG-CRUX-RULING** (no worktree; notes-only) — adversarial pass on the bookish-AST ruling
evidence → `harness/notes/h22/crux-ruling.md` → feeds Gate P

**Proof without new data:** extended `scout_eval` against today's COP/LOP corpus —
P@1 ≥ 0.98 · disambiguation 1.00 on the 239-name collision set · floor honored · phantom 0.00.

## Gates
- **A — scope ratification** (this doc). Blocks all arming. Docket below.
- **P — parser source ruling:** `i1_extract` + 4 patches vs bookish-AST adapter. After LEG-CRUX-RULING lands.
- **B — consumer-fix review** on `knowledge.py`. Non-negotiable.
- **C — per-context wiring flips** into `rag/corpus/`. Non-negotiable, per rung.
- **D — merge to master.** Non-negotiable, per-act.
- Delegable: calibration sign-off, build re-ratification.

## After K1
**Wave S — storage.** SQLite + FTS5, lazy serve; JSONL shards stay the git-tracked build
source; collapse to one resident index. Backup gate on migration. **Lands before DOP.**
**Wave I — ingest ladder.** `ING-<CTX>` data legs, no worktree, `harness/autoresearch/` as-is:
1. CHOP — promotes into the *current* JSON store; proves the loop end-to-end (trivial mass; re-promote after S is free)
2. TOP — 19 shipped `tops_*` tools vs zero backing knowledge, worst phantom history. Not negotiable downward.
3. DOP → 4. OBJ/ROP → 5. VOP → 6. SOP (**strictly after Wave S** — 44.9% of projected mass)

**APEX** — policy memo only; `check_no_rigging_drift` untouched; parser capability documented, not shipped.

## Acceptance bars (machine-derived keys · seeded RNG · committed sha256)
| metric | bar |
|---|---|
| live coverage vs native types | ≥ 0.80 |
| floor-clearing among served entries | 1.00 |
| served phantom rate | 0.00 — release-blocking |
| retrieval P@1, type-name queries | ≥ 0.98 |
| context disambiguation (239-name set) | 1.00 |

## Arm protocol — the Opus seam
- Wave manifest carries `"model": "claude-opus-4-8"` (passthrough at `orchestrate.ps1:228`). Fable dispatches nothing.
- Flow: author missions (`harness/autorevise/missions/`) → `mission_schema.py` validate →
  `compile_wave.py` → `make_control.py` dry-run → **ARM on per-act word**.
- Every mission prompt carries the explicit hold-turn instruction (`prompts/_template.md`).
- Detached: `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass' -WindowStyle Hidden -PassThru`, PID captured, stdout/stderr → named logs.
- Board read: `Select-String -Path $log -Pattern 'board ' | Select-Object -Last 1`
- Worktree product check: `git rev-list --count BASE..HEAD` — ahead:0 is a standing CRUX block.

## Gate A docket (human words required)
1. Ratify scope: Wave K1 as specified; ingest ladder order; APEX stays federated.
2. Non-node surfaces (VEX / hscript / HOM) — largest recon hole. IN (adds a scout wave) or OUT (recorded)?
3. Wave-2 crucible debt — recommend: ACCEPT on pre-flight cover, EXCEPT the bookish ruling → LEG-CRUX-RULING.
4. Commit this blueprint + push the ahead-1 recon commit (Gate C word).

## UNKNOWN ledger (rendered UNKNOWN until measured)
- Native SOP count — pending `s0_typedump.py::classify()` bucket at ING-SOP
- Non-node surface sizing — no agent reported; unpriced
- bookish adapter maintenance cost across a Houdini major — unpriced

*Assembled by Fable 5 from the 2026-08-15 recon under Joe's direction; leg execution pinned to Opus 4.8 at arm.*

## Series plan — waves 5–9 (ratified 2026-08-15, post-v5.50.0)

**Shape:** 5 = trust the gauges · 6 = build capacity (SQLite+FTS5, before mass) ·
7–9 = ingest ladder (CHOP → TOP → DOP → OBJ/ROP → VOP → SOP) · one hardening leg
rides every wave (undo drift → provenance guardrail → execute_python builtins).
One wave in flight at a time, 3–5 legs each, crucible in every wave, words stay human.

**Wave 5 roster:** W5-DENSE (S1: node entries into the dense index → P@1 bar) ·
W5-DELTA (.400 re-ingest of shipped contexts → freshness gate green) ·
W5-BASE (suite_baseline R31 tuple promotion) · W5-UNDO (hardening: wrap the
create/connect/delete mutations in handlers_node.py in undo groups; set_parm
lives in handlers.py and set_keyframe in handlers_render.py, NOT
handlers_node.py, so those remaining live-path Ctrl+Z holes ride W5-UNDO-B —
corrected per CRUX-R2) · W5-CRUX (gate).
Gate P ruling is Joe's word, not a leg; Branch-A parser patches enter at wave 7
only after that ruling.

**Quit-rules (escalate, don't grind):**
- DENSE: embedding nodes degrades COP/LOP lexical floor below 1.00 → STOP, ruling.
- DELTA: any served entry lost vs the .368 corpus → STOP, keep-both, ruling.
- BASE: fix requires checks.py logic edits (not just the baseline file) → STOP, bigger leg.
- UNDO: handlers_node.py shows parallel-session activity at leg start → STOP, escalate;
  live Ctrl+Z verification is gui_required → UNKNOWN pending Joe's receipt, never faked.
