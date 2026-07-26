# H8 — ORCHESTRATOR GROUND TRUTH

Verified by the orchestrator directly, before and during the agent fan-out, so that agent claims
can be judged against something rather than accepted. Every line here carries the command that
produced it. Tree: `repair/h8-ruling-audit` @ `a64033d`.

This file is evidence, not a verdict ledger. The ledger is `harness/notes/RULING_AUDIT.json`.

---

## A. Reader calibration (R60 — a pin's reader needs its own control)

The audit's "reader" is grep/git over the tree. Before trusting any ABSENT claim, the reader was
shown to find things that are present:

| Ruling | Mandated mechanism | Found at | Verdict on reader |
|---|---|---|---|
| R33 | schema/impl enum pin | `tests/test_solaris_tool_registration.py:134` | reader CAN find |
| R34/R71 | mutation standard | `harness/verify/checks.py:1684` `check_mutation_fail_closed` | reader CAN find |
| R31/R40 | tuple baseline | `harness/verify/checks.py:2122` `check_suite_baseline` | reader CAN find |
| R70 | `PARENT_KEYS` convergence | `tests/solaris/test_*.py` (4 files) | reader CAN find |
| R9 | `ui/` location pin | `tests/test_v5_features.py:54,55,80-82` | reader CAN find |

**Reader calibration PASSES.** An "enforcement: none" verdict below is therefore a finding, not a
failed search. This is R50 applied to the audit itself.

---

## B. Anchors opened and confirmed (Law 5 — write from the tree)

| Ruling | Cited anchor | What is actually there |
|---|---|---|
| R5 | `flywheel_queue.json:80` | `"ratified": false` — CONFIRMED |
| R9 | `tests/test_v5_features.py:54` | `("synapse.ui", …)` — CONFIRMED, still present |
| R12 | `pyproject.toml:102` | `testpaths = ["tests"]` (now :108) — CONFIRMED |
| R21 | `panel/tokens.py:15` | `_sys.path.insert(0, _DESIGN_DIR)` on `~/.synapse/design` — CONFIRMED |
| R28 | `tests/panel/test_docking.py:80` | `pytestmark = pytest.mark.skip(reason="PySide unavailable…")` — CONFIRMED |
| R30 | `tests/test_hda_panel.py:172-175` | now the *repaired* Q1 version (file-backed Qt filter) — ruling WORKED |
| R39 | `run_suite_shipping_python.ps1:23` | `--ignore` removed, removal recorded in a comment — ruling WORKED |
| R40 | `.claude/workflows/h22-relay.js:65` | now "4875 gate / 4048 shipping" — ruling WORKED |
| R41 | `component_builder.py:315` | `name_parm.set(asset_name)` — CONFIRMED verbatim |
| R41 | `scene_template.py:218` | `primpath_parm.set(...)` — CONFIRMED verbatim |
| R67 | `shared/bridge.py:1718` | `top_node.dirtyAllTasks(remove_files=remove_files)` — CONFIRMED, still wrong kwarg |
| R76 | `store.py:830` | now the *repaired* honest `logger.error` arm — ruling WORKED |

**No anchor in this sample was fabricated.** Where an anchor no longer shows the defect, git
history shows the ruling's own remedy landing — that is the ruling working, not evidence failing.

---

## C. Numbers re-derived (Law 2 — no number without a producer)

| Ruling | Claimed | Measured now | Producer | Note |
|---|---|---|---|---|
| R37 | providers 1,510 LOC, 5 engines | **1,510 LOC**, 9 files | ruling names its own producer | exact match; best-evidenced figure in the document |
| R9 | `ui/` 8 files, 1,076 LOC | **8 files**, 1,347 LOC | `find python/synapse/ui -name '*.py'` | file count exact; LOC has no producer path |
| R28 | `panel/` 71 files, 23,365 LOC | **71 files**, 27,265 LOC | `find python/synapse/panel -name '*.py'` | file count exact; LOC has no producer path, and has drifted |
| R2 | LOP 40/218 = 18.3% | ratio arithmetic checks | — | R2 itself adopts the producer rule |

R37 is the control that this method can CONFIRM a number, not only refute one.

---

## D. Mandated checks — built vs not built

The document repeatedly rules that a check be added. Direct test of each:

| Ruling | Check ordered | Present? | Test run |
|---|---|---|---|
| R4 | `lop_emission_grounded`, `no_phantom_api` in `checks.py` | **NO** | `grep -n "lop_emission_grounded\|no_phantom_api" harness/verify/checks.py` → 0 hits |
| R24 | assert `git diff --ignore-cr-at-eol` empty on fresh checkout | **NO** | `grep -ril "ignore-cr-at-eol" harness/verify tests .github scripts` → 0 hits |
| R26 | assert every JSON under `harness/` parses with `json.load` | **NO** | no such check in `checks.py` |
| R32 | assert `--collect-only` count differs primary vs worktree | **NO** | only unrelated `--collect-only` use at `tests/test_residency_guard_fires.py:27` |
| R59 | `checks.py` gate failing on a deprecated symbol in the emission corpus | **NO** | `grep -ci deprecat harness/verify/checks.py` = **0** |
| R2 | any surviving D1 reference is a defect | **NO** | no D1 check in `checks.py` |
| R3 | bare phrase "COP coverage" is banned | **NO** | 0 hits |
| R39 | `--ignore` banned in any harness measurement runner | **NO** | 0 hits |
| R66 | unpinned SideFX docs URL banned in any governing document | **NO** | 0 hits — *and see §E* |
| R33 | schema/impl enum pin, all five tools | **YES** | `tests/test_solaris_tool_registration.py:134` |
| R34/R71 | mutation standard | **YES** | `checks.py:1684` |
| R31/R40 | tuple baseline | **YES** | `checks.py:2122` |

`harness/verify/checks.py` holds **81** `check_*` functions. None of them implements R4, R24, R26,
R32, R59, R2, R3, R39 or R66.

**R59 is the sharpest case.** R65 cites `grep -ci deprecat harness/verify/checks.py` = 0 as proof
that 67 symbols sat in cells no instrument could see. That number is **still 0**. The census H5
ran found the symbols; the gate R59 ordered to keep finding them was never built.

### D.1 — The "Law 1 check set" does not exist

R26 (`:503`) and R32 (`:819`) both rule "**add to the Law 1 check set**". Searched the whole tree:

    grep -rln "Law 1 check set" --include=*.py --include=*.json --include=*.md .
    → harness/notes/CTO_RULINGS_01.md          (and nothing else)

The container named twice as the destination for new checks exists only inside the document that
names it.

---

## E. The document violates its own R66

R66 ruled: *"Every SideFX citation uses `/docs/houdini22.0/`. The unpinned path is **banned in any
governing document, ruling or vendor ask** — it is a URL whose meaning changes underneath a
citation."*

    grep -rn "sidefx.com/docs/houdini/" --include=*.md .
    → harness/notes/CTO_RULINGS_01.md:1482   (R58's Method line)
    → harness/prompts/h5.md:15

`CTO_RULINGS_01.md:1482` is R58, in the same file as R66, ~290 lines earlier, unpinned and
unmarked. A ban with no mechanism, violated by the document that issues it.

---

## F. The evidence base for R48–R78 is not in this tree

31 of 78 rulings (40%) rule from leg receipts. Where those receipts actually are:

    git ls-tree -r --name-only HEAD -- harness/notes/receipts/

Present on this branch (12): `H2 H3 L0 L1 L2 L3 L4 L5 Q1 Q2 SR1 T0`

| Receipt | Rulings resting on it | Status |
|---|---|---|
| `RES.json` | R51, R57 | committed on `repair/fake-hou-residency` only — **absent here** |
| `H3a.json` | R48, R49, R50, R58 | committed on `repair/h3a-cancel-probe` only — **absent here** |
| `H1.json` | R60, R61, R62, R63 | committed on `repair/h1-schemas` only — **absent here** |
| `H6.json` | R74–R78 | committed on `repair/h6-substrate-truth` only — **absent here** |
| `LEDGER.json` | R52, R53, R54, R55, R56 | **untracked on disk, in NO commit on ANY branch** |
| `H5.json` | R65, R66, R67, R68 | **untracked on disk, in NO commit on ANY branch** |
| `H2b.json` | R69, R70, R71 | **untracked on disk, in NO commit on ANY branch** |
| `H7.json` | R72 | **does not exist anywhere** |

Verified by `git ls-tree -r --name-only <branch> -- harness/notes/receipts/` across all nine
`repair/*` branches, plus a disk listing of each worktree.

A reader of `CTO_RULINGS_01.md` on the branch that carries it can open **zero** of the receipts
underpinning rulings 48–78.

This is R38 inverted. R38 ruled that governing documents must ship on every branch they govern, and
mandated cherry-picking the constitution and the rulings onto every active branch. The reverse trip
— the **evidence** coming back to the branch that rules on it — was never made. Three of those
receipts are one `git worktree remove` from being gone, and commit `bd17870`
("evidence(receipts): … the qualifier's receipts were untracked") shows this exact defect was
already found once and recurred.

R29's own words are the standard being failed here: *"A receipt is not the tree. It is a model's
summary of the tree."*

---

## G. WITHDRAWN — and the withdrawal is the useful part

**Claimed first, wrongly:** that `harness/legs.json` reads `ready` for six legs that demonstrably
ran and `blocked` for two that ran green, and that this was Law 3 violated in the harness's own
registry.

**Refuted by reading one more function.** `harness/orchestrate.ps1:51-63` `Get-ReceiptPath` checks
**the leg's own worktree first**, then the main tree. `harness/orchestrate.ps1:66-70`
`Get-LegState` returns `done` whenever a receipt resolves. So the `state` field in `legs.json` is a
declared *initial* value, overridden at runtime by a computed one; only `held` is honoured from the
file. The registry is not lying — I read the data and not the reader.

That comment block at `:53-56` records the same class of error being fixed once already: *"the
orchestrator watched only `$repo\harness\notes\receipts` and reported three completed legs as
'running' for two hours. It was watching a directory that could never fill."*

**What survives, and it is stronger than the withdrawn claim.** The orchestrator's state machine
now depends on receipt files that are **untracked, in no commit, inside disposable worktrees**
(§F). `git worktree remove` on `h5-compat`, `ledger-moneta-seam` or `h2-requalify` would
simultaneously destroy the evidence for eleven rulings *and* silently reset those legs from `done`
to `ready`. The state machine and the evidence base share a single point of failure that version
control does not cover.

Recorded here because this audit is entitled to make an error and is not entitled to keep it.
R60's rule — *a pin's reader needs its own calibration* — applies to the auditor: I read the
registry without reading its reader, which is the same shape as R64 citing a design brief without
probing it.

---

## H-pre. R70 refuted by executed two-sided control — a SIXTH known-wrong ruling

The brief named four known-wrong rulings. The audit found two more. R50 is in the control record.
This is the other, and it was reached by three independent routes: a control lens, the sweep's
adversarial pass, and the orchestrator directly.

**R70 claims:** *"The convergence happened. **The raise did not.**"* — i.e. that R15's named harm
(a caller using a wrong key silently builds into `/stage`) is still live.

**Executed on this branch, both arms:**

    python -c "import sys; sys.path.insert(0,'python')
               from synapse.mcp.tool_impls.solaris import component_builder as cb
               cb.validate({'asset_name':'x','parentPath':'/stage'})"
    → ValidationError: Missing or invalid field 'unknown parameter(s): parentPath -- accepted …'

    cb.validate({'asset_name':'x','parent_path':'/stage'})
    → OK

**The raise exists.** Unknown keys raise; known keys resolve. That is exactly what R70 ordered and
exactly what R70 says had not happened. The raise landed in `1cb99a9` (2026-07-25,
*"fix(solaris): SR1 crucible findings — F4 premise refuted, F8 convergence"*) — **one day before
R70 was written.**

The mechanism of the error is worth more than the error: H2b-F5 measured `_resolve_parent_path`
**in isolation** and reported its `/stage` fallback as reachable behaviour. On the public path
`validate()` raises first, so that fallback is unreachable. A private helper was tested as though
it were the surface.

That is the same defect the document convicts others of — a check measuring something other than
the claim — committed inside the finding that corrects a scope error. R70's *doctrine* (name harm
and mechanism in separate clauses with separate oracles) stands and is worth keeping; its
factual premise does not.

---

## H. H8's own fence — reported honestly rather than assumed

`harness/orchestrate.ps1:147-159` does select the read-only profile for `readonly: true` legs and
launches with `--settings harness/readonly-settings.json --permission-mode acceptEdits`. The
marker `.claude/.orch_launched` (`2026-07-26T17:23:46`) confirms this session is that dispatch.

**Observed anyway:** this leg executed `sed`, `find`, `mkdir`, `diff` and `git ls-tree` — none of
which appear in `readonly-settings.json`'s 19-entry allow list — without challenge.

The deny list (which is the half that actually protects `CTO_RULINGS_01.md`) was **not probed**.
Article I forbids an agent testing or editing its own leash, so this is reported for ruling rather
than resolved. It is the same class as R61 and R69: read-only asserted in prose, only partly
structural in fact.

**Fan-out containment, verified by measurement rather than by promise:**

    git status --porcelain   before fan-out  →  `?? .claude/.orch_launched`
    git status --porcelain   after  fan-out  →  identical

No sub-agent wrote to the tree, including the two agent types (`h22-adjudicator`, `sidefx-cto`)
that hold Write tools. Per R61(c) this was re-read from disk, not inferred from the agents stopping.

**Worktree isolation was deliberately NOT used for the fan-out**, and the reason is a verified
hazard: `master` is `f90946d` and carries only **38** of the 78 rulings. Workflow worktree
isolation branches from master (R69's eleven stray `wf_*` trees are still on disk at `f90946d`,
confirming it). A worktree-isolated agent would have audited a document missing 40 rulings.
