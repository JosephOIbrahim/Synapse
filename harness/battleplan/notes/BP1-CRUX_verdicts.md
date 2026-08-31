# BP1-CRUX — adversarial crucible verdicts (wave BP1)

**Read-only crucible.** Builds nothing. Re-ran every builder acceptance predicate
independently, with the crucible's own anchors and its own mutations. A green CRUX
receipt is a **precondition** for Joe's merge words, never a substitute for them.

- **Wave base:** `9e444d90` (shared merge-base of bp1/triage, bp1/rails, bp1/honesty, bp1/crux).
- **⚠ master moved during this session** to `7f82a437+`. Every "vs master" check here is
  against the **wave base `9e444d90`**, not the live master — diffing against the moved
  master produces phantom changes the legs never made (I hit and corrected exactly that
  false-positive on a `CAPSULE` file mid-audit).
- **Leg tips audited:** triage `102c034b`, rails `ec32b62c`, honesty `8c930084` (each ahead=2:
  product commit + receipt commit).

## Bottom line

| Leg | Verdict | Rides? | chain_broken_at |
|---|---|---|---|
| BP1-TRIAGE | **SOUND-WITH-NITS** | YES | none |
| BP1-RAILS | **SOUND-WITH-NITS** | YES | none |
| BP1-HONESTY | **SOUND-WITH-NITS** | YES | none |

All three legs ride. No leg is BROKEN. The nits are non-blocking; none violates an
acceptance predicate or a crucible criterion. TRIAGE is capped at SOUND-WITH-NITS by the
rule "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS" (its GUI half is
correctly UNKNOWN — Joe's deciding run). RAILS and HONESTY each carry one confirmed minor nit.

## Methodology (how the crucible trusted nothing)

- **Fresh detached checkouts** of each leg tip (not the builders' live worktrees).
- **Import resolution proven local** before any mutation: `synapse.loop.ports.__file__`
  resolves into the audit worktree, not the editable-installed main tree
  (`C:\Users\User\Synapse\python`). Without this, mutations would be invisible (false-green).
- **Ran the runtime truth myself:** the hython probe under the shim, `test_rails.py`,
  the tiny-cap halt (own ledger + CLI exit-7), the 8-mutation set, the 58-test recall suite.
- **Did NOT run `orchestrate.ps1`.** Its `Backup-Branches` runs `git push` and is *not*
  guarded by `-DryRun` (called at `harness/orchestrate.ps1:757,816` in the main loop a
  `-DryRun` run still enters). Pushing is a hard constitutional NEVER, so RAILS predicate 3
  was verified by **static additivity proof + byte-identical committed norm-logs** — more
  rigorous than a single live run, and the completeness critic independently corroborated
  the push hazard.

---

## BP1-TRIAGE — SOUND-WITH-NITS (rides)

Gate-0 silent-recall four-gate probe under hython. Re-run of the probe by the crucible in
its own hython:

| Acceptance predicate | Verdict | Crucible anchor |
|---|---|---|
| 1 · artifact: 4 gate rows (verdict ∈ pass\|fail\|UNKNOWN), env=hython, build runtime-observed, DONE last | **pass** | My own shim run `python .synapse/hytest.py …/probe_silent_recall.py -o python_files=probe_silent_recall.py -s` → G1 fail, G2 fail, G3 UNKNOWN, G4 UNKNOWN, build=22.0.417, DONE sentinel last. Byte-structural match to committed `silent_recall_hython.json`. Copy: `BP1-CRUX_triage_hython.json`. |
| 2 · bus bucket finding, anchor = artifact path | **pass** | BP1 bus finding `n=18d0f229ca7d5418`, `body.bucket=env`, anchor = the artifact path. |
| 3 · launch-path inspection carries file:line; OneDrive redirect named | **pass** | Anchors resolve: `packages/synapse.json:22-25` sets `PXR_PLUGINPATH_NAME`. My G1 row corroborates at runtime: `homeHoudiniDirectory=C:/Users/User/houdini22.0` (classic), `package_present_onedrive=true`, `package_absent_classic=true`. |
| 4 · probe runs in the Houdini GUI (gui_required) | **UNKNOWN** | Unobtainable headless. Correctly recorded UNKNOWN — Joe's deciding run at the rig. This is what caps the leg at SOUND-WITH-NITS. |

**Build-stamp crucible criterion (the defect this wave exists to kill):** the stamp is
genuinely runtime-read, not typed. My independent observation `hou.applicationVersionString()`
→ `CRUX_OBSERVED_BUILD=22.0.417`, matching every row's `build` field. **CONFIRMED.**

**UNKNOWN not coerced:** G3/G4 UNKNOWN because `import moneta` → `ModuleNotFoundError` headless
(substrate UNAVAILABLE by construction); G1/G2 are definite measured fails. Never coerced.

**Bucket follows from rows:** `bucket=env` = first gate whose verdict==fail (G1). UNKNOWN gates
never name it. Code-derived (`bucket_from_rows`), independent of the M1 two-store hypothesis.

**No product code touched:** `git diff 9e444d90..bp1/triage` = 4 files, all under
`harness/battleplan/` + the receipt.

**Nits (non-blocking):**
- **T-N1** — GUI half is UNKNOWN (the rule's nit; the deciding production run is Joe's hands).
- **T-N2** — G4 exercises only the most-permissive recall (`query_and_filter([], [])`); a
  silent-empty living in the predicate/filter/embedding path could still pass G4 green in the
  GUI. Scope, not a break; mitigated by the probe's `raw_row_count`/`known_in_raw` diagnostic.
- **T-N3** — `BP1-TRIAGE_launch_path.md`'s "why the classic dir is bare" aside is imprecise
  (`candidate_pref_dirs` still globs `home/houdini2*`, so it would also write the classic dir).
  Speculative aside; the observed facts (classic bare, hython resolves it) are verified on disk.

---

## BP1-RAILS — SOUND-WITH-NITS (rides)

Harness budget rails. All four acceptance predicates and all four crucible criteria hold.

| Acceptance predicate | Verdict | Crucible anchor |
|---|---|---|
| 1 · capped run completes with ledger (leg, model, cap, spent-or-UNKNOWN, remaining) | **pass** | My own control ledger `ledger_bp1-crux-rails-control.json` (status=complete, 0 estimate violations) + builder proofA. |
| 2 · tiny-cap run halts, status=blocked reason=budget | **pass** | My own `ledger_bp1-crux-rails-tinycap.json` (refused CRUX-TRIVIAL-2, status=blocked, reason=budget) + **CLI seam exit-7 on over-cap charge, exit-0 admitted** (the exact path orchestrate.ps1 calls) + builder proofB. |
| 3 · orchestrate.ps1 without -Budget = identical -DryRun output | **pass** | **Static additivity proof** of `git diff 9e444d90..bp1/rails -- harness/orchestrate.ps1`: every changed hunk is (a) the new `$Budget=''` param, (b) inert new function defs, (c) a call returning early when `-Budget` absent (`Rails-Open`→return; `Rails-Charge`→`return $true` *before* any external call, `$LASTEXITCODE` untouched), or (d) the halt block guarded by `if($script:BudgetHalted)`. Corroborated by byte-identical committed `orch_dryrun_before/after.norm.log`. |
| 4 · tests/test_rails.py passes stock pytest | **pass** | My run in wt-rails → **26 passed**. |

**Crucible criteria:** no ledger field is an estimate (token fields are literal `UNKNOWN`,
`wall_ms` measured; grep + my `no_estimate` check = 0 violations); hard stop exercised in an
artifact (my tinycap ledger); orchestrate.ps1 additive (static proof); seam is a pure JSON
lookup table (`rails_exec.json`, `resolve_model` = `json.loads` + dict index, no exec/eval).
All **HOLD**.

**Nit (non-blocking):**
- **R-N1** — an **empty run** (zero admitted charges) serializes `totals.tokens_in/out = 0`
  with `token_meter="measured"`, where a run with an UNKNOWN charge would report `UNKNOWN`.
  Confirmed by me (`rails.py:354`; empty `sum()`→0). The `0` is an **exact empty sum, not an
  estimate**, so it violates neither acceptance nor the "no estimate" criterion, and it never
  appears in any shipped artifact (proofA/proofB/orch-halt/my ledgers all carry real charges).
  Cosmetic — a strict reading of the engine's "Never zero" doctrine would prefer `UNKNOWN` for
  symmetry. Surfaced by the adversarial pass, verified by the crucible.

---

## BP1-HONESTY — SOUND-WITH-NITS (rides)

Recall honesty envelope in `python/synapse/loop/ports.py`. Recall can no longer return
empty-success.

| Acceptance predicate | Verdict | Crucible anchor |
|---|---|---|
| 1 · honesty tests (a)(b)(c) pass; named mutation reddens (a) | **pass** | 9 honesty tests pass + **8 self-authored crucible mutations all reddened a named test, 0 escapes, baseline green before+after** (`BP1-CRUX_mutations.py` → `BP1-CRUX_mutations.json`). Includes the two brief-mandated mutations: restore-empty-list → reddens `test_empty_list_under_bare_success_is_impossible`; delete-layer-check → reddens `test_layer_absent_is_unavailable`. |
| 2 · test_loop_contracts.py unchanged and green | **pass** | Not in `9e444d90..8c930084` name diff (byte-identical); 20/20 pass. |
| 3 · branch diff touches no forbidden surface | **pass** | Base-relative grep of `9e444d90..8c930084` for pgdrm.py/VERSION/README.md/loop-v00.yaml/harness/loop/harness/memory clean. |
| 4 · TRIAGE bucket named in receipt with the bus line | **pass** | Receipt cites bucket=env, bus `n=18d0f229ca7d5418`; verified on the bus. |

**Crucible criteria:** empty-payload-under-SUCCESS impossible (my MUT-1 confirms the test net
catches its restoration); **sec.4 surface byte-identical** base vs tip (header 1-30, `STATUS`
frozenset, all four port signatures — verified byte-for-byte); fix targets the env bucket
(envelope + `LAUNCH_PATH_FIX.md`); no third store authority (`python/synapse/memory/`,
incl. `store.py`+`ledger.py`, byte-unchanged vs base); no forbidden surface. All **HOLD**.
No regression: full recall suite (loop_contracts + v51 + honesty) = **58 pass**.

**Nit (non-blocking):**
- **H-N1** — two **new** envelope lines are unexercised by the named tests:
  `ports.py:344` (`_bind_gate_token` returning `None` for a generic non-import store-open
  failure) and `ports.py:382` (`_guard`'s generic `PortResult.unavailable(detail)` fallthrough).
  Confirmed by me via `--cov-report=term-missing` (69%, lines 344/382 in Missing). Both paths
  **correctly return UNAVAILABLE**, so the empty-success invariant is intact — a coverage gap in
  new defensive code, not a shipped defect.

---

## Wave-level nits (for Joe's ruling, not leg breaks)

- **W-N1** — BP1-TRIAGE and BP1-RAILS declare **overlapping directory-level `touches`**
  (both list `harness/battleplan/notes/` + `harness/battleplan/runs/`). No actual file-path
  collision occurred (the legs' name-only diffs are file-disjoint), but collision-freedom
  relied on **named-file commits + a bus block** (TRIAGE `for_ruling` R2, bus
  `n=18d0f1a48d74e4e4`), not the declared partition. A `git add -A` re-run of either leg would
  have collided. Mission-hygiene note for future waves; declare `touches` at file granularity
  where two legs share a directory.
- **W-N2** — the CRUX charter's target 4 ("reproduce … the -DryRun control output") collides
  with the auto-push prohibition, because `orchestrate.ps1 -DryRun` still reaches the unguarded
  `Backup-Branches` push. The safe route (static additivity + committed norm-log identity) is
  what this crucible used; the charter should state that constraint.

## Adversarial pass

A 4-agent read-only skeptic panel (one per leg + a completeness critic) attacked each verdict
on immutable committed state. **Every verdict held; zero ride-status breaks.** The panel
surfaced R-N1, H-N1, T-N2/T-N3, and W-N1/W-N2 above, plus confirmations that the probe cannot
false-green, the RAILS turns-floor can never coerce the cap to unlimited (independent
`adv_probe`), and each leg's receipt SHAs are real ancestors of their tips. Every adopted nit
was re-verified by the crucible itself before landing here.

## What this does NOT decide

- The **GUI round-trip** (demo-round-trip.yaml, red) and TRIAGE predicate 4 remain Joe's hands.
  The env bucket is a launch-path defect; the GUI half is the production discriminator.
- **Merge, the v5.57.0 tag, and ratifying `memory-recall-honesty.yaml`** are Joe's words, per
  act. This receipt is their precondition, not their substitute. The contract's `passing:false`
  flags were deliberately NOT flipped by HONESTY (a CRUX-verify + human-ratify act) — the
  crucible confirms the five features have green evidence; ratification remains Joe's.
