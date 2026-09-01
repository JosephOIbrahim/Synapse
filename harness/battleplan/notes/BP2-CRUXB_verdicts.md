# BP2-CRUXB — Adversarial crucible verdicts (closing wave: PANELDESIGN · HEALTHWIRE · NITS · METERLIVE)

Referee: BP2-CRUXB on `bp2/cruxb` (claude-fable-5, referee tier). Read-only; builds nothing;
flips no contract feature; edits no product file. Every acceptance row below was re-run in a
**fresh checkout** of the leg's branch (git-archive extract, tree-binding proven via
`synapse.__file__` inside the scratch), with the crucible's own anchors. Mutations are
self-authored; no builder's `proved_it_bites` was trusted. gui_required rows are UNKNOWN —
headless cannot see the .400 GUI, and skip ≠ pass.

Method: 4-agent verification workflow `wf_6225b609-d71` over scratch extracts
`pd`/`hw`/`nits`/`mlv` @ `a7035343`/`a50bd2e5`/`0dd5451e`/`56e92d81`, plus first-person
re-runs by the referee for the mission's "yourself" items (sec.4 diff, METER proof, integer
tracing, spec region audit). Mutation ledger: `BP2-CRUXB_mutations.json` (sibling file).

---

## BP2-METERLIVE — VERDICT: SOUND-WITH-NITS (chain intact)

The cleanest of the four. 3/3 acceptance rows re-run PASS with crucible anchors; every
integer in every committed ledger traces to a usage record or is the literal honest-UNKNOWN;
the scratch-repo isolation and the no-product-diff claims verify exactly.

Acceptance re-run (crucible anchors):

1. **Live-run ledger with integer tokens + transcript path — PASS.** First-person: the
   committed transcript `BP2-METERLIVE_transcript_441bb920.jsonl` re-sums to
   `tokens_in=75356 tokens_out=278` from 2 usage records (referee's own python mirror of
   rails' rules), == the autohalt ledger integers; `rails.measure_transcript_tokens` in the
   scratch returns the identical `(75356, 278)`. Halt arithmetic internally consistent:
   remaining `-75633 = 1 − 75634`; `wall_ms=18303` matches the log's dispatch→done stamps.
2. **Tiny-ceiling halt — PASS.** Ledger `status=blocked / reason=budget /
   enforced_unit=tokens`; MLV2 has **no** ledger row; log lines 64–66 carry
   `BUDGET: MLV1 settle crossed the token ceiling` → `BUDGET HALT: dispatch stopped by
   -Budget 4turns,1tokens`.
3. **No-Budget negative control — PASS, non-tautological.** `dryrun_diff.txt` = 4 bytes
   (BOM+LF, zero content); baseline `8afeda21:harness/orchestrate.ps1` = 772 lines vs
   `bp2/meterlive` = 933 lines, `git diff` between them = 216 output lines > 0 — the two
   sources genuinely differ, so the byte-identical logs mean something.

Supporting checks: scratch repo `C:/Users/User/AppData/Local/Temp/bp2mlv/repo` exists,
`remote -v` empty (no origin), single seed commit. `git diff e9ebfeda..0bb56698 --stat` =
13 files, 665 insertions, ALL under `harness/battleplan/{notes,runs}/` — zero product paths.
Transcript is a real Claude Code session (sessionId 441bb920, cwd = MLV1's own scratch
worktree, gitBranch mlv/leg1); the receipt's DISCLOSED provenance caveat is consistent with
the artifacts. The trivial-reap ledger records literal `UNKNOWN` tokens with real wall_ms
ints (26830/18514) — never a fabricated zero.

**NIT (new, crucible-found): rails double-counts repeated usage rows of one API response.**
The settled transcript's 2 usage records are the thinking-block and text-block rows of ONE
response (same `requestId` req_011CedM5gZjooyfVCqJ1GYBG, same `message.id`, identical usage
dict `{in:10, cache_create:22541, cache_read:15127, out:139}` twice). rails sums both rows,
so "measured 75356/278" is that single response counted twice (true single-response spend
37678/139). Direction is conservative — budget halts fire EARLY, never late, and integers
still trace 1:1 to transcript records under rails' documented rule — but the meter
overstates spend when Claude Code stamps the same usage on multiple content-block rows of
one message. Remedy: dedupe by `message.id` (or `requestId`) in
`rails.measure_transcript_tokens`. Affects reported magnitudes in BP2-METER/METERLIVE
ledgers, not their traceability. Proposed as held spawn `BP2-METER-DEDUPE`.

Nits, disclosed by the leg itself and confirmed: settled transcript is a graceful
`claude -p` session in MLV1's worktree, not the reaped interactive dispatch (disclosed,
consistent); trivial reaped legs settle honest-UNKNOWN (disclosed; held spawn SOFTCLOSE
already filed by the leg).

---

## BP2-NITS — VERDICT: BROKEN — chain_broken_at: T1 (acceptance row 1: the regenerated proof still cannot fail)

The leg's charter was closing crucible nits about evidence honesty. Two of its three
acceptance rows fail **as evidence** under first-person re-run, in exactly the
green-light-that-cannot-report-failure class this wave exists to make unshippable. The
*substance* behind every row is true (independently proven below) — the artifacts asserting
it are not.

Acceptance re-run (crucible anchors):

1. **"prove_bp2_meter_dryrun.ps1 re-run produces parent-vs-HEAD control logs with an empty
   diff" — FAIL (vacuous pass; not parent-vs-HEAD).** The committed fix (19a6697c) changed
   line 73 `HEAD:` → `HEAD~1:` — but on `bp2/nits` **every** commit's
   `harness/orchestrate.ps1` is blob `38d02aad` (933 lines): no nits commit touches it. So
   `HEAD~1:orchestrate.ps1` == the edited working copy, byte-identical — the Compare-Object
   compares a file against itself and **cannot produce a non-empty diff**. The true product
   parent is `1c2b78fd^` = `7fc09482`, blob `fdadfe53`, 829 lines — never enters the
   comparison. Referee re-ran BOTH ways in a fresh git clone of bp2/nits:
   - **Run A (as committed): EMPTY DIFF, exit 0 — vacuous** (identical source blobs).
   - **Run B (referee variant, baseline forced to the real `1c2b78fd^` 829-line blob):
     EMPTY DIFF, exit 0 — genuine.** 17-line normalized logs both sides.
   So BP2-METER's additive -DryRun claim is TRUE (Run B here + METERLIVE row 3 both prove
   it against genuinely-different baselines), but the NITS-committed proof does not prove
   it, and the leg's receipt/finding language ("the tautological control has been replaced
   with the truth proof (parent vs HEAD)") asserts the artifact does something it does not.
   The HEAD-vs-HEAD tautology CRUX flagged was re-shipped one level up as HEAD~1-vs-worktree
   on a branch where those are the same bytes.
2. **"MONETA_FOLLOWUPS.md shows FU-1/FU-2 DONE at 3c4f07f9 with the pinning tests named;
   FU-3 open" — FAIL in part (DONE markers + hash pass; named pins are phantom/wrong).**
   Grep confirms: FU-1 L51 + table L148 `DONE | 3c4f07f9`, FU-2 L87 + L149, FU-3 L150 OPEN;
   commit `3c4f07f9` exists and is on master. BUT FU-1's named pin
   `test_moneta_crucible.py::test_duplicate_content_gets_distinct_ids` **does not exist** —
   the tree's only mention is a docstring (test_moneta_crucible.py:213) recording it was
   renamed/inverted to `test_id_collision_does_not_silently_lose_memories`; and FU-2's named
   file `tests/test_memory_models.py` carries zero gate/prune content — the real pin is
   `tests/test_sleep_pass_gate.py` (`test_rejecting_gate_blocks_the_prune`). The phantom
   citations were WRITTEN BY the leg's own commit 361cc6e7. Substance green: the real pins
   pass (12 passed memory_models+sleep_pass_gate; 31 passed moneta_crucible in the scratch).
3. **"dashboard_bp2.py + status_bp2.py render status='open' as live" — PASS.** Referee's
   agent authored its own `status='open'` ledger fixture and drove both readers with globals
   rebound to the fixture repo (dashboard's REPO is hardcoded to the main tree — a straight
   run writes `board_bp2.html` into the live repo, so rebinding was required): `pill('open')`
   → `<span class="pill ok">open</span>` in the Words table (7×); the HTML ledger status
   line renders as plain escaped foot text (matches the leg's own disclosure); status_bp2
   prints `status=open` verbatim. Readers only; no rails change.

Additional findings:
- **No teeth on T3:** zero tests reference `dashboard_bp2`, `status_bp2`, or `pill()` —
  reverting dc9e803e reddens nothing. Recorded as mutation `M-NITS-NO-TEETH` (bit=false).
- **T4 spot-check PASS:** dab6c634 touches only docs/BATTLEPLAN.md (rows 6/7/9/12); sampled
  cited evidence paths exist (profile_diff.json, ledger_bp2-meter-settle.json,
  BP2-STORE.json receipt).
- **Bus procedure:** BP2-NITS posted no claim/release on the battleplan bus (REFEREE
  observed the same at 15:48).

**Why BROKEN and not SOUND-WITH-NITS:** rows 1 and 2 are not UNKNOWNs or disclosed
deferrals — they are receipt evidence that misstates what the committed artifacts do
(a proof that cannot fail presented as the fix for a proof that could not fail; pin names
that point at tests that don't exist). BROKEN does not ride. Remedy is small and mechanical:
(a) parameterize the proof baseline to the METER product parent (`7fc09482`) or an explicit
`-BaselineRef`, regenerate on a tree where baseline ≠ worktree, or adopt METERLIVE's
committed `prove_bp2_meterlive.ps1` T3 form which already does this honestly;
(b) correct the two pin names in MONETA_FOLLOWUPS.md to
`test_moneta_crucible.py::test_id_collision_does_not_silently_lose_memories` (or :244's
count-equals form) and `tests/test_sleep_pass_gate.py::test_rejecting_gate_blocks_the_prune`.
Both fit a fresh one-hour session on the same branch.

---

## BP2-PANELDESIGN — VERDICT: SOUND-WITH-NITS (chain intact)

5/6 acceptance rows re-run pass with crucible anchors; row 6 (GUI sign-off) is gui_required
→ UNKNOWN (Joe's .400 eyes; skip ≠ pass). 4 of 6 self-authored mutations BIT with named
tests; the 2 adversarial survivors are documented teeth gaps, not chain breaks.

Acceptance re-run (fresh extract @ a7035343, tree-binding proven):

1. **Spec exists with px per region — PASS** (referee first-person: §4 L123–240, exactly
   five `### Region` sections, before/after px tables in all five, "no more" confirmed).
2. **No colour token / no hex in the diff — PASS** (referee first-person: 0 added hex, 0
   added QFont/font-family/setFamily lines in `e9ebfeda..3371ba62 -- designsystem/`;
   guard test green).
3. **Gap tokens step by density multipliers — PASS** (`test_bp2_paneldesign_density.py`
   16/16 in the scratch).
4. **Expert pin + pytest -q green — PASS (env-reconciled).** `test_rope_expert_pin.py` 2/2,
   `test_rope_density.py` 11/11, `test_design_system.py` 44/44. Full suite in the git-less
   extract: 18 failed / 6899 passed / 190 skipped — ALL 18 are git-infra tests (worktree
   guard, harness lock, statusline, perf ratchet, vendored-gitignore, d_track, decisions);
   arithmetic reconciles exactly to the claimed 6921 (6899+18=6917, +4 skip-flips). In a
   git-FULL clone of the branch, 16/18 pass; the 2 residuals fail identically on BOTH
   closing branches with self-describing clone-topology errors ("master ref unresolvable",
   "fixture must have origin/master") — environment, not leg code. No product-code failure
   observed anywhere.
5. **Importer chore posted as bus finding — PASS** (bus n=18d149fa5ba88e1c seen first-person;
   `.synapse/verify.py no-importers` re-run in the scratch → exit=1, pair kept).
6. **GUI sign-off on the five regions in .400 — UNKNOWN** (gui_required, unobtainable
   headless).

Mutations (self-authored; ≥4 required, 4 BIT):
- **M-PD-1 hex colour → BIT**: `test_region_rhythm_introduces_no_hex` +
  `test_density_blocks_are_spacing_only` (2 failed).
- **M-PD-2a density-scaled padding replacing the margin → BIT**:
  `test_each_reachable_region_gap_steps_by_the_multiplier` +
  `test_airy_is_looser_than_tight_for_every_region` (2 failed).
- **M-PD-3 Expert manifest reorder → BIT**: `test_expert_resolved_equals_v5420_snapshot` +
  `test_snapshot_orders_pinned_explicitly` (2 failed). (The receipt's "fast local guard"
  `test_expert_manifest_pin_intact` stayed green by design — the real pin bit.)
- **M-PD-4a font-family in a density rule → BIT**: `test_density_blocks_are_spacing_only` +
  `test_rope_density::test_density_rules_step_spacing_only` (2 failed).
- **M-PD-2b (adversarial) density-scaled padding ADDED alongside the margins → SURVIVED**
  (71 passed). TEETH GAP: the "paddings stay fixed" half of sec.7 is unpinned — spacing-only
  guards allow any padding/margin inside density blocks.
- **M-PD-4b (adversarial) font-family in a NON-density sec.7 rule → SURVIVED** (76 passed).
  TEETH GAP: the font guard is density-block-scoped; acceptance row 2's hex/font grep is a
  diff-time chore, not a committed test.

Nits: the two teeth gaps above (remedy: pin "padding values equal across airy/tight per
region" + extend the no-font guard to the whole designsystem sheet — a ~10-line test
addition, proposed as held spawn `BP2-RHYTHM-TEETH`); post-receipt hygiene commit a7035343
(benign contract verify-string fix, but branch HEAD is no longer the receipt — W5H drift);
disclosed reachability deferrals (R3 greenfield, R4 no objectNames) are honest and
spawn-filed by the leg itself.

## BP2-HEALTHWIRE — VERDICT: SOUND-WITH-NITS (chain intact)

3/4 acceptance rows re-run pass with crucible anchors; row 4 (GUI strip observation) is
gui_required → UNKNOWN. 4/4 self-authored mutations BIT — the strongest mutation showing of
the wave, including the adversarial alias-fork the receipt's F2 claimed was locked (it is).

Acceptance re-run (fresh extract @ a50bd2e5, tree-binding proven):

1. **write_plane sub-dict carries embedder_id/embedding_dim/backend_health with ratified
   verdict; unimportable → UNAVAILABLE — PASS.** All 7 tests in
   `test_bp2_healthwire_write_plane_backend_health.py` passed with **0 skips** — the
   moneta-gated test RAN plainly (moneta importable on this host, no env injection needed),
   real embedder fields exercised.
2. **sec.4 tool surface diff empty — PASS** (referee first-person: `_tool_registry.py` blob
   `8c538a85` identical at master == product == base; mcp/ + handlers* diff vs master
   EMPTY; product commit = exactly 4 files, none a tool surface).
3. **test_w3_harden byte-identical + green; pytest -q green — PASS (env-reconciled).**
   Blob `404f6469` == master, 10/10 green. Full suite in the git-less extract: 18 failed /
   6890 passed / 190 skipped — the SAME 18 git-infra ids as the PANELDESIGN extract;
   arithmetic reconciles exactly to the claimed 6912 (6890+18=6908, +4 skip-flips); git-full
   clone: 16/18 pass, same 2 clone-topology residuals as bp2/paneldesign (identical across
   branches ⇒ environment). None of the 18 touch write_plane/memory/healthwire surfaces.
   Post-audit restore integrity proven (scratch write_plane.py blob == branch blob).
4. **Health row observed in the .400 GUI strip — UNKNOWN** (gui_required; the leg's own
   receipt records the strip deliberately does not render the five fields — data proven at
   the synapse_health surface, rendering is the held BP2-HEALTHSTRIP spawn).

Mutations (self-authored; ≥3 required, 4 BIT):
- **M-HW-1 unimportable-reports-ok (verdict forced SUCCESS) → BIT**: 2 failed, including
  `test_health_row_attaches_unavailable_verdict_when_moneta_unimportable` and
  `test_unavailable_is_never_rendered_as_ok`.
- **M-HW-2 drop embedder_id → BIT**: 3 failed (merge/ride/real-embedder tests).
- **M-HW-3 status word 'degraded' → 'impaired' → BIT**: 8 failed — 6 of w3_harden's 10
  (the builder's "test_w3_harden must redden" contract CONFIRMED) + 2 healthwire tests.
- **M-HW-4 (adversarial) verdict/status alias fork → BIT**: 5 failed — receipt F2's
  alias-lock (`verdict == status`) is real.

Nits: gui_required row UNKNOWN (caps at SOUND-WITH-NITS per crucible criteria); FR1
(verdict/status double-key) remains open for Joe/CTO as the leg filed it; full-suite green
adjudicated by reconciliation rather than a literal 0-failed reproduction (env).

---

## Referee first-person anchors (independent of the workflow)

- **sec.4 tool surface (HEALTHWIRE T3, "yourself"):** `_tool_registry.py` blob
  `8c538a856d5e7a81470f8977ab41794aad95f1ea` at master == `4f252ba5` == base `e9ebfeda`;
  `git diff master bp2/healthwire -- python/synapse/mcp/ python/synapse/server/handlers*` =
  EMPTY; full product diff `e9ebfeda..4f252ba5` = exactly 4 files (write_plane.py +38, new
  test +197, docs/help/health_row.md +11, notes +173), memory/ untouched.
- **PANEL_RHYTHM_SPEC region audit (PANELDESIGN T2, "yourself"):** §4 (L123–240) carries
  before/after px tables for exactly five `### Region N` sections (R1 tab strip, R2 verb
  rail, R3 recall card GREENFIELD target spec, R4 token-face rows, R5 ribbon+header) — px
  numbers present in all five; header says "stop at five" and there is no sixth. "No more"
  confirmed by heading grep.
- **PANELDESIGN post-receipt commit:** `a7035343` (above receipt c73e5825) edits ONLY the
  `.synapse/contracts/panel-rhythm.yaml` verify string (ascii-multiplier grep; passing stays
  false — no feature flip). Benign, in-territory; nit: the branch HEAD is no longer the
  receipt commit (W5H "receipt is the closing commit" drifted by one hygiene commit).
- **METER proof lineage:** `1c2b78fd` (METER product) parent `7fc09482`
  (orchestrate.ps1 blob `fdadfe53`, 829 L); product blob `38d02aad` (933 L) == e9ebfeda ==
  bp2/nits == bp2/meterlive; current master `529942f0` (937 L, post-close relay allow-list
  commits).
