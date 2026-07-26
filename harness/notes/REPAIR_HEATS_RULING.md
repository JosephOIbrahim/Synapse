# REPAIR HEATS — RULING BLOCK

**Assembled** 2026-07-26 by **F1 · integration** · model `claude-opus-5[1m]`
**Source** every `for_ruling[]` item across all ten leg receipts, plus H8's — **62 items, 11 receipts**
**Producer** `harness/notes/receipts/{Q1,Q2,RES,H3a,LEDGER,H1,H2b,H5,H6,H7,H8}.json`
**Decided-vs-open basis** `harness/notes/CTO_RULINGS_01.md` @ `a64033d`, 78 rulings, read in full
**Ranked by** cost of delay. Not by leg order, not by severity.

> **Read this first.** Several items in the receipts were **ruled during the run** and must not be
> re-presented as open — the legs wrote their escalations before the rulings that answered them
> existed. Section C lists them so they are visibly closed rather than silently dropped.
>
> Three items are stronger than "decided": they were ruled **and** F1 verified the work is done.
> Four are weaker: **ruled, and the work is still outstanding.** That distinction is the most
> useful thing in this document and it is Section B.

---

## 0 · Found by F1 during integration — not in any receipt

These are not escalations any leg wrote. They surfaced because integration did something no leg
did: put the ten branches in one tree.

### F1-A · LEDGER never landed, and it collides head-on with H6 ⛔ **RANK 1**

`repair/ledger-moneta-seam` reported `status: green` and wrote a receipt recording
`commits: [], merged: false, pushed: false`. **That was literally true.** Every artifact — 504
lines across four product files, a new test module, a mutation harness — sat **uncommitted** in
its worktree. F1's own housekeeping step would have destroyed it.

F1 committed it on **its own branch** (`eb25abe`) so it is durable, and did **not** merge it.

**Why not merged — VERIFIED-RUNTIME, `git merge-tree`:**

```
HEAD + LEDGER            ->  exit 0, clean
LEDGER + H6              ->  CONFLICT (content)
                             python/synapse/memory/moneta_runtime.py
                             docs/studio/DEPLOYMENT.md
```

**The mechanism.** LEDGER and H6 both rewrote `moneta_provenance()` from the same base, in
ignorance of each other. R64 §1 designed them to **compose** — *"`moneta_provenance()` gains
`schema_registered` and `schema_in_use` alongside `available` and the git SHA LEDGER is adding"*
— five conditions, five fields. **Neither branch has all five.** LEDGER has `available` + git SHA;
H6 has `available` + `schema_registered` + `schema_in_use`.

Merging LEDGER first would have blocked **a gate leg** behind a conflict F1 is fenced out of
resolving (*"do not fix forward through a merge conflict into product code you have not read"*).
H6's work was committed and green; LEDGER's was never committed at all. H6 went in.

**The decision:** who authors the union of `moneta_provenance()`, and does LEDGER's half land
before or after? It is authoring, not merge resolution — the merged function must carry all five
fields and no automatic strategy produces that.

**Cost of delay is the highest in this document.** `moneta_runtime.py` now carries H6's rewrite;
every further change to it widens the gap LEDGER's patch must cross. LEDGER's six ruled items
(**R52, R53, R54, R55** — all *decided*) are implemented **only** in that stranded code, so four
rulings the CTO already closed are currently un-shipped.

**Preserved at:** branch `repair/ledger-moneta-seam` @ `eb25abe`; conflict evidence in the F1
receipt; worktree **deliberately not pruned**.

### F1-F · Nine leg sessions are STILL RUNNING, hours after writing "green" receipts ⛔ **RANK 1-equal**

Measured at integration, `Get-CimInstance Win32_Process`, 2026-07-26 19:3x:

```
res 1   h3a 1   ledger 1   h5 1   h7 1   h8 1   f1 1 (this leg)
h1  4   h2  4                              + 12 subagents
                                           = 27 live claude.exe
```

Every one of those legs **wrote a receipt saying it was done.** All hold write tools
(`--permission-mode acceptEdits` under `relay-settings.json`). They are writing into this
repository right now.

**This is not inference — it is demonstrated.** `origin/repair/fake-hou-residency` carries commit
`6db6fd7`, *"fix(tests): RES — fake-hou residency was a re-import, not a stub Parm"* — a **new**
commit, same subject as the `c0cc415` F1 merged, 24 files / 3,780 insertions against the merged
3,782. **The RES session re-authored and re-pushed its work after F1 had already merged its tip.**
Its receipt was written hours earlier.

**This explains three other findings at once:**

| Symptom | Explanation |
|---|---|
| **F1-B** — two branches both claiming H1 | **four** concurrent H1 sessions. Not a mystery; a headcount |
| Merged worktree shells that will not delete (*Device or resource busy*) | live sessions hold them as CWD |
| Every F1 merge appearing on `origin` within ~20s | `harness/orchestrate.ps1:182-211` polls and pushes **every worktree branch** to origin as a backup, by design. It never pushes master (`orchestrate.ps1:11`) |

**This is R61(c) and R78 at session scope.** R61(c): *"stopping a leg does not mean it has stopped.
Any post-stop verification must re-read from disk, never trust that writing has ceased."* R78 built
the `.orch_launched` marker for **two** concurrent sessions on one leg. **There are four on two
legs.**

**What F1 did NOT do, and why:**

- **Did not kill them.** Q1-R4 set the precedent — *"Killing another harness is not an agent's
  call. It was not killed."*
- **Did not delete any leg branch, local or remote.** Deleting refs out from under nine live
  writers is destructive interference. `origin/repair/fake-hou-residency` already carries a commit
  that is **not** in the integration branch; deleting it would destroy unevaluated work.
- **Did not delete merged remote feature branches** (brief step 3). Two independent blockers:
  the poller **re-pushes every worktree branch on every poll**, so deletion is futile while
  `orchestrate.ps1` runs; and the live sessions are still committing to them. The safety criterion
  is computed and recorded — six of eight leg tips *are* ancestors of the pushed
  `origin/feat/repair-heats-01` and would be safe **once the poller and the sessions stop**.

**For ruling:** who stops nine leg sessions that believe they are finished, and should a leg's
receipt be refused unless its own process has exited? A receipt written by a process that keeps
writing is a claim about the past tense that has not happened yet.

### F1-B · Two branches both claim leg H1, with conflicting edits to the same files

`repair/h1-schemas` (3 commits) and `repair/h1-schemas-b` (1 commit) are **two independent
executions of the same brief from the same base (`70ed8ef`)**, both `status: green`, both editing
`schema_set_purpose.py` and `schema_create_variants.py`, each with its own test module.

**F1 adjudicated on evidence, not on recency.** Every test identifier the CTO cites in **R60** and
**R63** — `test_schema_reader_recovers_every_arm_of_a_nested_ternary`,
`test_schema_reader_actually_sees_five_statuses_in_set_purpose`,
`test_every_schema_return_contract_is_pinned` — exists on `repair/h1-schemas` and **nowhere on
`h1-schemas-b`**. The H1 addendum was ruled on the `h1-schemas` receipt. It is canonical and was
merged; `h1-schemas-b` was not merged and not deleted.

**For ruling:** `h1-schemas-b`'s `test_solaris_schema_return_contract.py` (364 lines) is the only
place the **R62** undeclared-key surface is already pinned. Harvest it into the canonical file, or
discard the branch? Its receipt is preserved at
`harness/notes/receipts/H1_SECOND_EXECUTION_h1-schemas-b.json`.

### F1-C · Five of ten legs left their entire product uncommitted

LEDGER, H5, H7, H2b and H8 all finished green and wrote receipts **without committing anything**.
Had F1 executed step 3 (prune merged worktrees) before step 2, the ledger, the compat matrix, the
re-adjudication, the mutation matrices and the 78-ruling audit would all have been destroyed.

This is not a leg failure — no brief told them to commit. **It is a harness gap:** a leg can report
`green` while its work exists only as untracked bytes in a directory the next step deletes.

**For ruling:** should a leg's terminal condition include "your product is committed on your own
branch", enforced by the orchestrator refusing to accept a green receipt from a dirty worktree?

### F1-E · R74's amendments were written, authorised, and blocked by a fence ⚠ **RANK 2-equal**

H6's worktree held **three final amendment drafts** that would have been destroyed by pruning:

```
.claude/R64_AMENDMENT_pending.md   7,287 b   the cover note + both destinations
.claude/amend_R64.md               4,986 b   the R64 amendment text, ready to append
.claude/amend_h6.md                2,169 b   the h6.md premise correction, ready to append
```

The cover note states its own status exactly:

> *"**Status** BLOCKED BY FENCE. Text is final and ready to append; this session cannot write it.
> **Authorised** by the human this session ("Amend before more work lands"), Article VII / F3.
> **Blocked by** `harness/**` is denied to this session's settings profile. Article I corollary.
> No bypass was attempted."*

**This is R74 §2 and §3 — already decided, text already written, and still undone.** The fence
behaved correctly and the agent behaved correctly; the amendment simply had nowhere to go. It is
H8-R1's open channel question (§A8) with a concrete casualty attached.

**F1 preserved all three at `harness/notes/h6_amendments/` and did NOT append them.** Appending to
`CTO_RULINGS_01.md` is a human act under Article VII, and *whether an agent-writable amendment
channel should exist at all* is exactly the open question H8-R1 raises — F1 deciding it by
writing into the document would settle an open ruling by side effect.

**To close it:** append `amend_R64.md` after `CTO_RULINGS_01.md`'s last line, and `amend_h6.md`
to `harness/prompts/h6.md`. Both are append-only by design — *"the record of what the document
said is the point (Article VI)."*

### F1-D · R69's F1-integration check — **PASSED**, and the stray trees confirm the finding

R69 ordered: *"Add it to the F1 integration checks: a worktree at an unexpected base is a finding,
not a curiosity."*

**Executed.** All twelve `repair/*` branches base off `feat/repair-heats-01` history. **None off
master.** Meanwhile the eleven `worktree-wf_cce57a2d-980-*` trees are **all at `f90946d` = master /
v5.34.0** — exactly the H2b-F2 condition R69 named. The check works, and it separates the two
populations cleanly on its first real run.

---

## A · OPEN — ranked by cost of delay

| # | Item | Why it ranks here |
|---|---|---|
| **1** | **F1-F** — nine leg sessions still running with write tools, hours after "green" receipts | The repository is being written to **right now** by processes that believe they finished. RES has already re-pushed work F1 merged. Every number in every receipt — including this integration's — describes a tree that is still moving |
| **1=** | **F1-A** — LEDGER unmerged, collides with H6 in `moneta_provenance()` | Four already-decided rulings (R52–R55) are un-shipped; the gap widens with every touch of `moneta_runtime.py` |
| **2** | **RES-R2** — `check_suite_baseline` ignores pytest's return code | **Ruled R57 and NOT done** — see §B1. The ratchet enforcing Commandment 7 is blind to a guard abort *today*, for every future leg |
| **2=** | **F1-E** — R74's amendments are written, authorised, and unapplied | Two paste operations. Until then R64 and `h6.md` both assert a state that is `REFUTED-LIVE`, and R74 §4's own lesson — *"a design document ages into a claim about the present without anyone editing it"* — is running against the ruling that stated it |
| **3** | **H5-R1** — arm `check_no_decay_clock_emission`, or leave it registered-but-unarmed | The gate is **merged as of this integration** and is unarmed. An unarmed gate everyone believes is armed is the exact Law-1 failure this harness exists to catch. R68 sequences what comes next but does not answer this |
| **4** | **H3a-R2** — the SideFX ask: send it, and by whom | Outward-facing, carries Joe's name. R73 already caught it being **wrong once**; R66 requires one more fetch against the pinned `/docs/houdini22.0/` URL before it goes. Reputational risk is asymmetric |
| **5** | **H3a-R1** — release H3b with its widened scope | The safety gap stays open every day this is held: an artist mid-Karma-render has a Stop that will not stop the render. R73 widened the scope to TOPS-cancel **and** `rkill`. Only Joe releases it (R48 §4) |
| **6** | **H7-R2** — the 528-row `leaf_unbound_owner` census defect | H7 calls it *"the highest-yield change available"* — it would collapse **78% of the residual** and stop `pxr` names being adjudicated against the HOM reference |
| **7** | **Q2-R3** — CI has never exercised the vendored wheels artists receive | Gate A class. Every green gate number describes an interpreter the product never runs on. R31 gave the two-baseline shape; it did not answer whether the gate interpreter changes |
| **8** | **H8-R1** — an amendment channel that does not widen the fence | H8-S1: `CTO_RULINGS_01.md` is deny-listed in **both** agent profiles, so no agent can mark a ruling it refutes. Across **105 supersession pairs, 0 originals are marked in place**. Unmarked supersession is structurally guaranteed, not an oversight |
| **9** | **H8-R5** — which of the 31 UNENFORCED rulings deserve a check | Decides how much of the ruling corpus is real vs. spent |
| **10** | **F1-C** — legs reporting green with everything uncommitted | Nearly destroyed five legs' work in this very run |
| **11** | **H6 FR-2 / FR-3** — should SYNAPSE's Moneta store author real USD; should the package set `PXR_PLUGINPATH_NAME` | R77 established SYNAPSE authors **zero** USD through Moneta. These decide whether that stays true. H6 recommends deciding them **together** — registering a schema nothing authors buys nothing |
| **12** | **H6 FR-4** — `moneta_substrate` returns `fail` on a deployed seat | Shipped as `fail`, not softened (Law 7). A deployed-seat doctor run is red until FR-2/FR-3 land |
| **13** | **F1-B** — harvest or discard `h1-schemas-b` | Only existing pin of the R62 surface |
| **14** | **H2b-R1** — three surviving-mutation pins: repair, retarget, or retire | Known-decorative pins that survive mutation are decorations under R34 |
| **15** | **Q1-R1** — the 5 pre-existing `tests/panel/` failures | They make Q1's documented positive control permanently unsatisfiable |
| **16** | **H5-R10** — the scout's phantom gate shares the EXISTS oracle whose module-expansion defect H5 found | The phantom gate is SYNAPSE's front-line defence (CLAUDE.md §11.15) and its oracle is now known-partial |
| **17** | **H7-R4** — `cop2net` (60 sites): two sources, opposite answers | R72 §3 says disagreement is itself a finding; needs a code read to bind the sites |
| **18** | **H7-R3** — 12 `doc_only` DECAY_CLOCK rows are leads, not verdicts | H7 deliberately reported the floor as 41 *with* the caveat rather than quoting either bound |
| **19** | **H7-R6** — 104 node types never probed live | `exists_basis` is recorded per row, never disguised |
| **20** | **H7-R1** — which corpus governs `pxr` (79 rows) | Terminal cell vs residual |
| **21** | **H7-R5** — R72's two help-cache character counts reproduce under no measure | Amending a ruling is a human act |
| **22** | **H7-R7** — `marshal_map.md:527` cites a nonexistent API | One-line doc fix outside H7's fence |
| **23** | **H7-R8** — promote the deprecation-marker vocabulary into a reusable checker | H7 says: after the census fix, not before |
| **24** | **H8-R3** — is the read-only profile enforcing what R61 intended | H8 ran five command families outside its allow list |
| **25** | **H8-R4** — ratify R50/R34/R60/R71 into the constitution, or downgrade "adopted" to "proposed" | The rulings claim adoption the constitution does not record |
| **26** | **Q2-R6** — ~35 mock-hou / Qt-stub tests already banned by Law 1 | Closing the environment gap **exposes more of them, not fewer** |
| **27** | **Q1-R5** — the skip-set md5 is invocation-dependent | Law 2 applies to the producer, not just the number |
| **28** | **Q1-R2** — scoped `.gitignore:50` negation so `tests/*.py` helpers cannot vanish | Repo-wide config, outside any leg's grant |
| **29** | **Q1-R3** — `harness/SYNAPSE_REPAIR_HEATS.md`'s Q1 anchor is wrong and its baseline commit stale | Governing document; Article VII |
| **30** | **H5-R7** — accept the census's 4th symbol kind, `hom_method` | Found four real DECAY_CLOCK methods no other kind could reach |
| **31** | **H5-R8** — orchestrator wrote `checks.py` in the worktree a cartographer was reading | Article V does not currently cover the sole-writer case |
| **32** | **H5-R12** — ingest `/docs/houdini22.0/tops/` so `pdg.*` gets a documented axis | Today `pdg.*` has no documented axis at all |
| **33** | **H6 FR-6** — `store.py`'s `shadow` branch has the same shape as the F4 defect | Not yet claiming a distinction it fails to make — flagged so it is not lost |
| **34** | **H3a-R3 (part)** — who repairs `harness/notes/_ws_retest.py` | The `dirtyAllTasks` half is decided (R67); the `_ws_retest.py` half is not |

---

## B · DECIDED — but the work is **NOT** done

**This is the section that matters most.** Each of these was ruled. None is finished. Presenting
them as closed would be false; presenting them as open would waste a ruling.

### B1 · RES-R2 → **R57**, undischarged ⚠ **highest-leverage item in this section**

> R57 ruled: *"`check_suite_baseline` ignores pytest's return code (RES-F9). **Fix the ratchet.**
> A guard abort that the ratchet cannot see is Law 1 in the ratchet itself — third instance this
> week."*

**F1 verified the tree.** `harness/verify/checks.py::check_suite_baseline` contains **no reference
to `returncode`**. The ruling is a day old and the hole is open. This is the instrument that
enforces Commandment 7 on every future leg.

### B2 · RES-R3 → **R57**, undischarged

> R57 ruled: *"`shot_layers/` written to repo root by the solaris live tests (RES-F11).
> **Redirect to `tmp_path`.** Gitignoring it hides a test writing outside its sandbox; the write
> is the defect, not its visibility."*

**F1 verified.** No `tmp_path` redirect exists, and `shot_layers/` is present in **two** worktrees
(`fake-hou-residency`, `h2-requalify`) — written during this very run. Absent from the main tree
only because the live tests did not run there.

### B3 · H2b-R3 → **R70**, *partly* discharged — and R70's harm was misstated

> R70 ruled: *"**unknown parameter keys raise.** Not warn, not default. And the pin must
> demonstrate the raise against an unknown key."*

**F1 verified all three parent-taking tools.** The raise **exists** — `validate()` rejects unknown
params via `KNOWN_PARAMS` in `component_builder.py`, `import_megascans.py` and
`scene_template.py`, and it was already present at H2b's own commit `c1d194b`.

**But all three still carry `return "/stage"`.** So the surviving defect is **not** the one R70
named. A caller using a **wrong** key now raises. A caller supplying **no** parent key at all
still silently builds into `/stage`. R70 (and H2b-F5 before it) described the harm as *"a caller
using a wrong key still silently builds into /stage"* — that specific harm is closed. **The
absent-key default is what survives**, and no ruling has named it.

### B4 · H5-R2 / H5-R6 → **R67**, half discharged

- **§1 doc fix — DONE.** `CLAUDE.md` §1.7 now states the live signature is
  `dirtyAllTasks(self, remove_outputs)`, that the call raises `TypeError` on every invocation, and
  that *"nothing may cite PDG dirty-propagation as functional."* **F1 verified this in the tree.**
- **§2 code fix — NOT done, and correctly so.** `shared/bridge.py:1718` is the S.2 boundary,
  human-authored by standing rule. F1's brief forbids touching it. **Still owed.**

---

## C · DECIDED and closed — do **not** re-present these as open

The legs escalated these before the rulings that answered them existed. Twenty-two items.

| Receipt item | Ruled by | The ruling |
|---|---|---|
| **LEDGER FR1** | **R52** | Pin Moneta for release; keep the worktree for development via documented `MONETA_SRC` override |
| **LEDGER FR2** | **R53** | Build the reconciler. A crash loses substrate rows silently while the files survive |
| **LEDGER FR3** | **R53** | Wire recall — **federated read across both stores**, not a merged URI |
| **LEDGER FR4** | **R54** | Env var with repo-relative default; caller passes `$HIP` where available. `ledger.py` stays zero-`hou` |
| **LEDGER FR5** | **R54** | Accept duplicates; **dedupe by `Memory.id` at read time**. A write-time check is O(n) on the hot path |
| **LEDGER FR6** | **R55** | Not a new problem — the gate-vs-shipping split already in `suite_baseline.json`. Do **not** cite the gate number as substrate evidence |
| **H1 R-1** | **R62** | Declare every key, then make the pin an **equality**. An undeclared key is a phantom inverted |
| **H1 R-2 (a)(b)(c)** | **R61** | (a) Fence it — `harness/readonly-settings.json`. (b) Article V extends to **any** fan-out. (c) `TaskStop` is a platform limitation; stopping a leg does not mean it has stopped |
| **H1 R-3** | **R63** | No decision needed. A ruling scoped to its evidence is scoped to whatever was looked at first — pin the **class**, not the instance |
| **H2b-R4** | **R61 + R69** | Fence confirmed and extended: any fan-out must branch from the dispatching leg's HEAD |
| **H3a-R1** | **R48**, amended **R73** | H3b proceeds as TOPS-cancel **and** an `rkill`-based render stop. *(Scope decided; the release itself is still open — §A5)* |
| **H3a-R2** | **R49**, amended **R73** | CTO drafts, Joe sends. The first draft was **wrong** and was rewritten, not sent. *(Sending is still open — §A4)* |
| **H3a-R3 (dirtyAllTasks half)** | **R67** | Fix the doc **now**, separately from the code. Code fix is human-authored |
| **H5-R3** | **R68** | Fix the extractor's blindness **first**, prove it reproduces today's headline symbols, **only then** regenerate. No reordering |
| **H5-R13** | **R72 §3** | Deprecation is the **union** of runtime `deprecationInfo()` and authored help; disagreement is itself a finding. The 19 DECAY_CLOCK count is a **floor, not a total** |
| **H6 FR-1** | **R74** | R64's predicted state is **struck**; measured state stands. Correct `h6.md`; flag Moneta's design brief stale **in Moneta**. Design briefs are `UNVERIFIED` by default |
| **H6 FR-5** | **R78** | The `.orch_launched` marker stands, **and extends to interactive sessions**. Any leg that ran concurrently has its receipt flagged |
| **Q2-R1** | **R40** | Tuple baseline **promoted**. F1 verified: `suite_baseline.json` is `suite_baseline/tuple-v1` |
| **Q2-R2** | **R39 + R47** | Environment gap, **not** "does not run as shipped" — measured by intervention: **88% of failures and 98% of errors were environment** |
| **Q2-R5** | **R39 §1** | `--ignore` is **banned in any harness measurement runner**. `--continue-on-collection-errors` is the correct instrument |
| **RES-R1** | **R57** | The 4 H21-constant tests: **fix in H2**, not in RES |
| **Q1-R4** | **R78** | Same hazard class as the double-dispatch race; the marker is the fix |

**Also answered by action, not by ruling:**

- **H8-R2** — *"Commit LEDGER.json, H5.json and H2b.json, or accept that eleven rulings rest on
  evidence outside version control? H7.json was never written at all."* **F1 committed all three**
  in the consolidation commit. And **H7.json now exists** — H8 audited before H7 finished, so that
  clause was true when written and is false now.

---

## D · Explicitly deferred to this block by the rulings document

`CTO_RULINGS_01.md`, *"Deferred, explicitly"* (between R71 and R72):

> *"The remaining ruling items from both receipts — the corpus/RAG gate extension,
> `apex::buildfkgraph` quarantine, matrix schema versioning, promoting H5's producers into
> `scripts/`, the `pytest -k solaris` interpreter ambiguity — are real and none are blocking.
> **They go to F1's ruling block** rather than being decided here on a first read."*

Arrived as instructed, none blocking:

| Item | Receipt | Agent's recommendation |
|---|---|---|
| Corpus/RAG gate extension | **H5-R4** | Yes, but as its **own** check with its own failure demonstration — not by widening this one |
| `apex::buildfkgraph` quarantine (4 sites) | **H5-R11** | APEX is outside SYNAPSE's declared authoring scope. Quarantine, exception, or remove |
| Matrix schema versioning | **H5-R9** | Two new cells (MISATTRIBUTED, OUT_OF_MATRIX) change the ledger schema |
| Promote H5's producers into `scripts/` | **H5-R5** | Promote `h5_join.py` and `h5_census.py` at minimum — *"a ledger whose producer cannot be re-run is a number travelling without its producer"* |
| `pytest -k solaris` interpreter ambiguity | **H2b-R2** | Sequencing judgement. Closing it means installing packages into the Houdini interpreter — changing the instrument mid-measurement. R47 owns that class |

Plus, from the same class:

| Item | Receipt | Note |
|---|---|---|
| Should the shipping leg re-run every sprint (~2x runtime)? | **Q2-R4** | R40 answered the adjacent half: *"the shipping number is NOT a ratchet floor"* — it becomes one once the 827-test gap is classified. The per-sprint cost question is untouched |

---

## Disposition summary

```
62 for_ruling items across 11 receipts
   22  DECIDED and closed          -> Section C  (do not re-present)
    4  DECIDED, work outstanding   -> Section B  (R57 x2, R67, R70-partial)
    6  DEFERRED here by the CTO    -> Section D
   30  genuinely OPEN              -> Section A
 +  6  found by F1 at integration  -> Section 0  (F1-A .. F1-F)
```

**If only one thing is decided from this document, make it F1-F** — nine leg sessions are still
writing to this repository, and until they stop, every measurement in every receipt (this one
included) describes a tree that is still moving.

**If two, add F1-A** — the only leg of ten that did not land, with four already-closed rulings
(R52–R55) riding on it, and a cost that rises with every commit touching `moneta_runtime.py`.

**If three, add B1** — the ratchet that enforces Commandment 7 cannot see a guard abort, the fix
was ruled a day ago, and every future leg merges through it.
