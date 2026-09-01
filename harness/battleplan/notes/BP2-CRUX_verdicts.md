# BP2-CRUX — Adversarial crucible verdicts (wave BP2 pairs 1+2)

**Leg:** BP2-CRUX · **Branch:** `bp2/crux` · **Date:** 2026-09-01
**Model:** reasoning (`claude-opus-4-8`) — the orchestrator resolves one model per manifest (sec.12 R-5), so the referee-tier *intent* (`claude-fable-5`) yields to reasoning; this receipt says so.
**Scope:** read-only. Audits four pair-builder receipts (METER, PANELTRUTH, LATENCY, STORE). Builds nothing, flips no contract feature, edits no product file.

## Method (every anchor is the crucible's own)

- **Fresh checkout per leg** via `git archive bp2/<leg> | tar -x` into a private scratch tree — **zero git-state mutation** (no worktree, no stash, no checkout). The scratch tree binds over the editable-install `.pth` (which points at the *main* tree) via the tests' pytest `pythonpath`/`sys.path.insert`; baseline-green proves the binding before any mutation.
- Every acceptance predicate **re-run independently** with a crux-own anchor (a command I ran, a file:line I read, a test id I executed) — never the builder's evidence string.
- **12 self-authored mutations** (4 each for the three code legs), each applied to the scratch copy, each must redden a **named** test for the **right reason** (failure on the intended assertion, not import/syntax), reverted between mutations so none compound. See `BP2-CRUX_mutations.json`.
- **Settle reproduced** by the crux with its own ledger; **latency probe re-run** by the crux with its own artifact (`BP2-CRUX_latency_reprobe.json`).
- `gui_required` / hython-gated predicates that cannot be measured headless are **UNKNOWN** (skip ≠ pass), never a pass.

## Verdict table

| Leg | Product HEAD | Verdict | chain_broken_at | Acceptance | Mutations |
|---|---|---|---|---|---|
| BP2-METER | `1c2b78fd` | **SOUND-WITH-NITS** | none | 7/7 pass | 4/4 bit |
| BP2-PANELTRUTH | `d9b0c06d` | **SOUND-WITH-NITS** | none | 5/7 pass · 2 UNKNOWN | 4/4 bit |
| BP2-LATENCY | `0ef53146` | **SOUND-WITH-NITS** | none | 4/5 pass · 1 UNKNOWN | probe-reproduced (empty product diff) |
| BP2-STORE | `dd66b089` | **SOUND-WITH-NITS** | none | 6/6 pass · 0 UNKNOWN | 4/4 bit |

**No BROKEN verdict** → all four legs ride, subject to Joe's merge words and the GUI halves he must eye. None is bare SOUND: every leg carries an honest UNKNOWN (the three GUI/`gui_required` halves) or a disclosed nit. A green CRUX receipt is a **precondition** for Joe's merge words, never a substitute.

---

## BP2-METER — SOUND-WITH-NITS

Token-meter post-close **settle**, per-leg **tier** resolution (incl. referee), bus-driven **drift** check, unit+status honesty.

**Acceptance (7/7 pass, crux-own anchors):**
1. **Integer tokens traceable to a named transcript** — PASS. Reproduced the settle over `tests/fixtures/transcript_with_usage.jsonl`; my own ledger: `tokens_in=12700`, `tokens_out=470`, `wall_ms=8482` (all int). Hand-summed the fixture: out `150+320=470`; in `(1000+200+3000)+(500+8000)=12700` — exact. Unresolvable → literal `UNKNOWN`.
2. **Negative control (no transcript → UNKNOWN, enforced_unit stays turns)** — PASS. My CLI run printed all three token fields `UNKNOWN`, `enforced_unit=turns`.
3. **Fixture with/without usage; enforced_unit flips to tokens only on ceiling+measured** — PASS. `measure(with)=(12700,470)`, `measure(no_usage)=(UNKNOWN,UNKNOWN)`; flip test 4/4 sub-cases.
4. **Tiny ceiling halts after settle (blocked/budget/tokens)** — PASS. settle exit=7; ledger `status=blocked reason=budget enforced_unit=tokens` (spend 13170 > 100).
5. **-DryRun byte-identical** — PASS **but see nit**. I re-derived the control myself against the *true* pre-edit parent `1c2b78fd^` → **EMPTY DIFF**; every added orchestrate.ps1 line is gated behind `-Budget` (Rails-Settle/Drift-Check/Rails-Charge) or the `leg.tier` Start-Leg block.
6. **drift.py: refocus carries targets verbatim; two-unimproved → halt; zero model calls** — PASS. 6/6 tests; read all 60 lines — imports json/re/sys/pathlib/bus only; never edits a mission/manifest.
7. **`rails.py resolve referee` → claude-fable-5** — PASS (first-person, exit 0; `rails_exec.json tiers.referee={claude, claude-fable-5}`).

**Mutations (4/4 bit, right reason):** strip usage records → with-usage measure reddens; neuter settle body → settle test reddens; hardcode measure constant → negative control reddens; force enforced_unit flip without ceiling → flip test reddens.

**Nits (about the committed *evidence*, not the code):**
- **The committed dry-run proof script is tautological as-shipped.** `harness/battleplan/runs/2026-09-01/prove_bp2_meter_dryrun.ps1:73` uses `git show HEAD:harness/orchestrate.ps1` as its pre-edit baseline. That was a real baseline only *before* the BP2-METER commit; now that the edits are at HEAD, re-running it diffs the edited file against itself and prints EMPTY DIFF **regardless of correctness**. The acceptance still holds — I re-derived it against the true parent and got EMPTY DIFF — but the committed artifact is **not independently reproducible as-shipped**. A future auditor should diff parent-vs-HEAD, not HEAD-vs-HEAD.
- Wording: `dryrun_bp2meter_diff.txt` is called "EMPTY" but is 4 bytes (UTF-8 BOM + newline) — empty of diff *content*, not zero-byte. Harmless overstatement.

---

## BP2-PANELTRUTH — SOUND-WITH-NITS

Panel token-readout refresh (event-driven), docked-open float fix, profile-diff artifact.

**Acceptance (5/7 pass, 2 UNKNOWN):**
1. **profile_diff.json states curious/expert/ml differences; producer re-run agrees** — PASS. I ran the scratch producer; `json.load(regen) == json.load(committed)` **FULL equality**. Density airy/standard/tight; identical 20-widget id-set all `visible=True` (non-vacuous); identical base prompt sha `d06fd7e21aa6f4f3`; distinct overlay shas; composed differs only by overlay.
2. **density repolish test** — PASS (7 passed).
3. **profile persist (select→save→load→same)** — PASS.
4. **TOKEN refresh (fed→face+pill; unfed→UNKNOWN)** — PASS for the pure-rule + fake-self path (14 passed). The **real-widget FaceToken/Pill Qt end-to-end is UNKNOWN** (2 skipped, "PySide unavailable — run via hython"; skip ≠ pass).
5. **float fix (3 branches + no-Network-Editor guard)** — PASS (4 passed).
6. **test_expert_resolved_equals_v5420_snapshot** — PASS (`tests/test_rope_expert_pin.py`).
7. **GUI verify in live .400 (Ctrl+K docked, live face update, reopen-survival)** — **UNKNOWN** (gui_required; unmeasurable headless).

**Leg-specific:** Expert pin green ✓. `synapse_panel.py` lifecycle/timer ranges **untouched** — git diff shows exactly one hunk `@@ -2361 @@` (`_on_done` + new `_refresh_token_surfaces`); `__init__` timers (L433-444), showEvent (L1418), closeEvent (shifted 2625→2652 by +27 lines, still outside the hunk) all unchanged. No `hou.` in `claude_worker.py`. **Territory breach remediated** (crux-verified): master tree carries zero PANELTRUTH files; all artifacts on-branch (`panel-truth.yaml` blob `b8cb7b6`).

**Mutations (4/4 bit, right reason):** remove compose repolish → density test reddens; neuter `_on_done` refresh (open-only) → 3 refresh tests redden; add QTimer poll of the sink → not-timer-driven pin reddens; float-first → float-fix test reddens.

**Nits:** row 7 (GUI) UNKNOWN and the row-4 real-widget Qt UNKNOWN both cap this below SOUND (correctly recorded by the builder, not laundered into green). Accuracy note: the scratch **binding lever is the pytest `pythonpath=['python']` config, not the `sys.path.insert`** the receipt attributed it to (the density/float tests have no such insert) — binding was still verified real (probe printed `compositor.__file__` = scratch path).

---

## BP2-LATENCY — SOUND-WITH-NITS *(crux self-audit, first-person hython)*

Memory-latency probe; public `synapse.loop.ports.MemoryPort` surface only; **empty diff** under `python/synapse/memory/`.

**Acceptance (4/5 pass, 1 UNKNOWN):**
1. **hython artifact: 5 repeats, per-op p50/p95, N, backend, embedder, dim, build in-process; unmeasured=UNKNOWN** — PASS. Both `memory_latency_hython.json` (honest UNAVAILABLE, all ops UNKNOWN) and `..._provisioned.json` (real numbers) present. **I independently reproduced** the provisioned run under hython pinned to 22.0.400 (`BP2-CRUX_latency_reprobe.json`).
2. **memory_latency_gui.json from the .400 GUI shell (Joe)** — **UNKNOWN** (gui_required).
3. **contract authored, all features passing:false** — PASS. 8 features all `passing:false`, zero `passing:true`, ratification PENDING Joe — **not flipped by the crucible**.
4. **diff under python/synapse/memory/ empty** — PASS (`git diff --stat 7fc09482..bp2/latency -- python/synapse/memory/` empty).
5. **bus finding: under budget with numbers OR bucket+spawn** — PASS (bus `18d13ee9a7c6dfa4`: UNDER BUDGET with numbers; no bucket, no spawn).

**Crux first-person reproduction (build stamp = observed):** `hou.applicationVersionString()` I observed directly = **22.0.400**; my pinned reprobe stamped **22.0.400** (match). All ops under budget — deposit p95 77.3/500, recall 2.3/1500, recall_after_reopen 6.2/1500, reopen_with_memory_layer 147.3/3000; `known_recalled` **5/5** pre- and post-reopen (no silent-empty); p95 present; n=5 per op. No bucket named → no isolating row required.

**Mutation-equivalent:** BP2-LATENCY changed **no product code** (empty `memory/` diff), so mission target 4 substitutes a probe reproduction for the mutation battery — satisfied by the independent reprobe above (acceptance predicate 3).

**Nits:**
- **hytest shim newest-wins:** an un-pinned headless reprobe stamped **22.0.429** (newest installed), diverging from the live demo build **22.0.400**. Repro must pin `SYNAPSE_HYTHON` to the demo build. The builder artifact correctly stamped 22.0.400 (controlled).
- The **default agent lane** (no Moneta env) is UNAVAILABLE by construction (`env_unset`); the under-budget numbers come **only** from the provisioned-headless proxy. The **demo-relevant GUI .400 number remains `gui_required` UNKNOWN** (row 2).

---

## BP2-STORE — SOUND-WITH-NITS *(acceptance is the cleanest of the four — no UNKNOWN)*

Memory-store honesty: `backend_health()` speaking ratified SUCCESS|UNAVAILABLE|BLOCKED; FU-1 id-ordering pins.

**Acceptance (6/6 pass, 0 UNKNOWN, crux-own anchors):**
1. **Distinct ids at different created_at; dedup at same content+type+created_at** — PASS (3 passed; `models.py:140-162`). Non-vacuous: mutations M1/M2 both redden the participation assertions.
2. **MonetaBackedStore count()==len(all()) after two identical deposits** — PASS, **MEASURED not skipped** (Moneta importable this seat, `moneta_available()=True`); `s.count()==len(s.all())==2`, distinct ids.
3. **Moneta-unimportable → backend_health UNAVAILABLE/BLOCKED, never SUCCESS** — PASS (`store.py:818/867-869`; M3 forcing SUCCESS reddens exactly this).
4. **Health line carries requested/active backend, embedder id, dim, row count** — PASS (`store.py:871-879`, all five fields).
5. **test_loop_contracts.py unchanged and green** — PASS (diff empty; 20 passed).
6. **Store authorities remain exactly TWO; backend_health constructs nothing** — PASS (`store.py:1692` + `ledger.py:398`; backend_health is a non-constructing observer, adds no census key).

**Leg-specific (crux first-person, corroborated by the auditor):** sec.4 tool surface **byte-identical** (all 6 memory-tool files, 0 diff lines) ✓; **forbidden-file grep CLEAN** (no pgdrm.py/VERSION/README.md/loop-v00.yaml/harness-loop/harness-memory) ✓; only 6 in-territory files changed; vocabulary == ratified `ports.STATUS`; revert integrity 64 passed.

**Mutations (4/4 bit, right reason):** reorder id-mint before created_at → id-collision; drop created_at from hash → 2 participation tests; force SUCCESS on moneta-unavailable → UNAVAILABLE test; truncate id `[:12]→[:8]` → legacy-format test.

**Why SOUND-WITH-NITS and not SOUND:** STORE's own acceptance is **unconditionally clean** — the downgrade is driven by two *disclosed, deferred* nits, not any acceptance gap:
- **F4 (warn):** the **server operator health row** (`server/write_plane.store_health`) still carries only 3/5 fields and uses its own `degraded`/`ok` word rather than the ratified UNAVAILABLE/BLOCKED. It is **operator-visible for the sec.1 demo**. Correctly deferred to held spawn `BP2-STORE-HEALTHWIRE` (server/ is out of STORE territory), but a merger should see it.
- **F1 (info):** FU-1 (Memory.id after created_at defaults) already landed on base via `3c4f07f9`/#16 — `models.py` is byte-identical to base on this branch; the leg's own contribution is `store.py backend_health()` + the test pins. Honestly recorded; the pinned behavior is real (M1/M2 redden it). `docs/MONETA_FOLLOWUPS.md` FU-1 is stale (out of territory) — a doc pass should mark it DONE.

---

## For Joe's ruling (verdicts are READ before merge words fire)

1. **All four legs are eligible to ride** (no BROKEN). Merge is Joe's word, per act — never an agent's.
2. **Three GUI/`gui_required` halves remain UNKNOWN** and need Joe's eyes on live Houdini 22.0.400: PANELTRUTH row 7 (Ctrl+K docked / live face update / reopen-survival), PANELTRUTH row-4 real-widget Qt, LATENCY row 2 (GUI paste of `memory_latency_gui.json`). These are honest UNKNOWNs, not blockers to the code — but the sec.1 demo beat's "green" call for the panel/latency halves depends on them.
3. **METER dry-run proof artifact** is tautological as-shipped (HEAD-vs-HEAD). The claim is true (crux re-derived it against the true parent), but if the committed artifact is to serve as standalone evidence it should be regenerated parent-vs-HEAD.
4. **STORE F4** (server operator health row not yet ratified-vocabulary) is deferred to held spawn `BP2-STORE-HEALTHWIRE`; **STORE F2** (`docs/MONETA_FOLLOWUPS.md` FU-1 stale) needs a docs-owning writer.
5. **Contract features stay `passing:false`** on both LATENCY and PANELTRUTH contracts — the crucible flipped none. Flipping is Joe's word.

## Evidence artifacts (all on branch bp2/crux)

- `harness/battleplan/notes/BP2-CRUX_mutations.json` — 12 code mutations, all reddened for the right reason + LATENCY reproduction-equivalent.
- `harness/battleplan/notes/BP2-CRUX_latency_reprobe.json` — first-person hython reprobe (pinned 22.0.400 + shim-newest 22.0.429), under-budget confirmed.
