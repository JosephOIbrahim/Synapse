# W5-CRUX — wave-5 crucible verdict board

**Adversarial gate over W5-DENSE / W5-DELTA / W5-BASE / W5-UNDO.**
First live enforcement of the commit-before-receipt mandate (CRX0, wave 4).
Read-only crucible: verifies, never repairs. Every number below was re-measured
independently — no leg's figure was inherited. Merge remains Joe's word.

Arm point (this crux's session start): master `b2412b6b`.
Verdict point: master **`3db5b244`** — master moved once mid-verdict (see §3).

---

## 1. Mandate — commit-before-receipt (CRX0 first live enforcement) — PASS, all four

| Leg | branch tip = receipt HEAD | ahead | product-commit time | receipt mtime | order |
|---|---|---|---|---|---|
| W5-BASE  | `20e0a888` ✓ | 1 | 15:42:25 | 15:44 | commit → receipt ✓ |
| W5-DELTA | `b4bbb562` (product `728d905d` ✓ reachable) | 2 | 15:33:47 / receipt-commit 15:36:52 | 15:36 | product → receipt ✓ |
| W5-DENSE | `594d1a68` ✓ | 1 | 15:45:42 | 15:47 | commit → receipt ✓ |
| W5-UNDO  | `c938ef0a` ✓ | 1 | 15:26:02 | 15:32 | commit → receipt ✓ |

Every stated HEAD exists, is reachable on its branch, ahead ≥ 1, and each receipt
was written **after** its product commit existed. **No builder at ahead:0; no
phantom sha.** The mandate's standing-block condition is not tripped on any leg —
CRX0 needs no post-hoc rescue this wave.

## 2. Independent re-verification — none inherited

**W5-DENSE — bars reproduce exactly (twice: dense worktree + merged .400 tree).**
Hybrid type-name P@1 **1.0 (603/603)**, cop/lop floor **1.0 (527/527)**,
disambiguation **1.0 (42/42)**, served_phantom **0.0 (0/659)**. Lexical
**0.9453 (570/603) / 0.9962 (525/527)** == W4-CRUX. `content_digest`
`6a683ee6…` matches; delete+rebuild byte-identical (11/11 incl.
`test_delete_rebuild_identical`). Node-dense index 1010×384.

**W5-DELTA — zero-loss + freshness confirmed.** 659 entries, per-context
cop 358 / lop 169 / cop2 132 == .368; **0 lost / 0 added / 0 dropped keys**,
id-order position-identical, retrieval surface (id/type/context/label/summary/
searchable_text) **byte-identical (0 field diffs)** — only `parameters[]` moved.
K.7 `corpus_stamp_fresh` **ok:true** (build 22.0.400 == ratified 22.0.400).
scout_eval on .400: floor 0.9526, disamb 1.0, served_phantom 0.0, p@1 0.7529.
Calibration 35/35. 16 tests green.

**W5-BASE — honest-blocked at receipt-time; human-resolved mid-verdict.**
Proposal is a valid R31 two-leg tuple (`parse_tuple_baseline` accepts it, rejects
the live FLAT file). Zero `checks.py` edits. At receipt-time the target file was
deny-listed → BASE correctly recorded **blocked / UNKNOWN**, escalated via
for_ruling + bus, did not circumvent. **Mid-verdict Joe applied the proposal to
master (`3db5b244`)** — the exact for_ruling action; applied file == banked
proposal (gate + shipping legs identical). suite_baseline is now **green** in the
`.git`-dir main checkout (6389/0 ratchet holds), R.R `guardrail_violations = []`
on master. The previously-UNKNOWN acceptance is now measurably **pass** — not
laundered (attributable to the human commit, not the wave5/base branch).

**W5-UNDO — 3 pass + 1 honest UNKNOWN.** `test_node_undo_grouping` 11/11 asserts
**exactly one** group per handler (rules out zero/two) + exception-path tests
prove the group closes AND the exception propagates. `test_network_explain`
19/19. Scope-honesty confirmed: only create/connect/delete are in
`handlers_node.py` (all 3 wrapped); `set_parm` lives in `handlers.py`
(unwrapped, F1), `set_keyframe` in `handlers_render.py` (unwrapped, F3);
`integrity_envelope.py:19-28` docstring now stale (F2). CLAUDE.md states the
honest split, not "all four wrapped." The live one-Ctrl+Z acceptance stays
**UNKNOWN** (gui_required) — no headless simulation substituted.

## 3. Parallel-writer audit — clean (two Joe commits, both disjoint)

Window `52f22821..3db5b244` (branch-point → current master):

| commit | author | files | collision |
|---|---|---|---|
| `b2412b6b` | Joe | `harness/notes/h22/CAPSULE-2026-08-15-w4.md` | none |
| `3db5b244` | Joe | `harness/verify/suite_baseline.json` | **none** — this is BASE's for_ruling, human-applied (16:18:35, mid-verdict) |

`3db5b244` touches suite_baseline.json (BASE's file) but as the **authorized
completion of BASE's for_ruling**, not a competing writer. `handlers_node.py`
seam (UNDO): last writer `0d3a33eb` is an ancestor of UNDO's base — no race.

## 4. Combined-state board (target 4) — exact failing surface named

- **scout_eval bars met on the merged .400 corpus:** P@1 1.0, floor 1.0,
  disamb 1.0, served_phantom 0.0. ✓
- **corpus stamped .400:** ✓ (K.7 `corpus_stamp_fresh` ok:true in the merged tree).
- **R.R `guardrail_violations` empty:** ✓ **on master** (BASE's tuple applied);
  ✗ in the combined *worktree* tree, where a full-suite re-run reddens on **5**
  tests — 3× `test_statusline.py` (linked-worktree `.git`-is-a-FILE artifact) +
  2× W4-GUARD: `test_live_worktree_is_honestly_red` (DELTA's .400 corpus flips
  freshness green, breaking the pinned STALE expectation) and
  `test_real_seeded_ledger_never_wires_apex` (ledger not co-flipped → verify
  mismatch). The two W4-GUARD reds are the **designed .368→.400 handoff**
  surfacing as pinned-test breakage — same root cause as K.7's
  `ingest_ledger_single_writer` red.

**The all-three-green board is not simultaneously realized in any single context
today:** master has R.R-green but corpus .368; the combined tree has corpus .400
+ bars but suite_baseline reddens on the coupled handoff + the statusline
worktree defect. It becomes reachable when DELTA's corpus **and** ledger flip
(for_ruling R1) **and** the two pinned W4-GUARD test updates land together, plus
the statusline worktree-gitdir fix (BASE spawn W5-STATUSLINE-WT) or a `.git`-dir
eval context. BASE's half (suite_baseline promotion) is already done (`3db5b244`).

## 5. Bus contract audit (target 6) — honored, coherent timestamps

- CTO brief 14:49:08 set the contract.
- DELTA → DENSE census **15:21:04**; DELTA → CRUX anatomy PASS + compliance
  **15:21:05**; DELTA → * scout bug **15:21:05**.
- DENSE → CRUX index stamp **15:45:12**; DENSE → CRUX "CONSUMED DELTA census
  (bus 15:21:04)" **15:45:12** — demonstrably read DELTA (15:21) before its final
  eval (15:45). Ordering coherent.

## 6. Anatomy cross-reference (target 6) — zero contradictions; one coverage gap

| Target | Result | Contradiction? |
|---|---|---|
| karma material builder | 0 `karmamaterial*` types served; honest not-found / subnet-family prose | none |
| componentgeometry `alternative` | real node served; the doc's 'alternative' does **not** surface (see gap) | none served |
| instancer → copytopoints | `copytopoints` served real; no exact `instancer` type | none |
| three island paths | component* nodes served; the doc's island paths do **not** surface | none served |

**Zero unresolved contradictions** (nothing served contradicts the live-verified
doc). **Coverage gap filed (F-CRUX-1):** `solaris_compound_node_anatomy.md` — the
CTO-bound reference — has a `rag/semantic_index/meta.jsonl` embedding row but **no
`rag/corpus/` backing entry**, so scout's own defensive skip-id-without-corpus
logic (DENSE's F2 crash-fix) drops it. Direct probe: `scout('componentgeometry')`
→ `['h22:lop/componentgeometry']` only, anatomy absent across three phrasings.
This **refutes** DENSE receipt predicate-5's evidence ("anatomy rank-2 … retrieval
brings them together"). The doc's H22 specifics ('alternative' 4th output; the
sopnet/geo · edit · extras island paths) are therefore **not discoverable** via
the merged retrieval.

## 7. Quit-rule check (target 5) — escalations, not silent grinds

DELTA / DENSE / UNDO quit-rules correctly **not triggered** (zero-loss, floor
unchanged, seam clean). BASE hit a hard permission block and **escalated**
(blocked status + for_ruling + bus post, no circumvention) — an escalation.

## Per-leg verdicts

| Leg | Verdict | Basis |
|---|---|---|
| W5-DENSE | **pass_with_findings** | Bars reproduce exactly; predicate-5 anatomy-rank-2 evidence REFUTED (F-CRUX-1) |
| W5-DELTA | **pass_with_findings** | Zero-loss + freshness confirmed; 11/16/18 drift (18 correct); corpus↔ledger coupling (for_ruling R1 required) |
| W5-BASE  | **pass_with_findings** | Honest-blocked → human-applied mid-verdict (`3db5b244`); now green on master; not laundered |
| W5-UNDO  | **pass_with_findings** | 3 pass + honest gui UNKNOWN; scope-honesty correct |

## Overall: green_with_findings

Mandate honored by all four (crux's central mission passes clean). No laundering,
no false-green, no seam collision, no mandate violation. The all-green board
exists on master for BASE's half and is otherwise gated on human merge actions
that must land coupled.
