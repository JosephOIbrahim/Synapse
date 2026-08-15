# W5-HCRUX — House-Cleaning Crucible Verdict Board

**Leg:** W5-HCRUX (band TRUTH, `readonly`, `touches: []`)
**Branch:** `wave5/hcrux` · base `c7a6a08d` (master)
**Gates:** W5-UNDOB, W5-CRUXS1, W5-STATWT, W5-HYGIENE
**Verdict:** `green_with_findings` — the *work* of all four legs is sound and composes; the *close protocol* failed for 2 of 4 (receipts left worktree-only). **Merge remains Joe's word.**

> House rule honored: every number below carries a producer path. Nothing inherited from the legs' own receipts — every acceptance was independently re-executed. The one un-measurable item (live GUI Ctrl+Z) is recorded UNKNOWN, never zero, never a pass.

---

## Headline

| Dimension | Result |
|---|---|
| Per-leg acceptance (independent re-exec) | **4/4 legs GREEN** (UNDOB 3/3 · CRUXS1 1/1 · STATWT 2/2 · HYGIENE 3/3) |
| Receipt-closing-commit mandate (binary) | **2/4 PASS** — STATWT, HYGIENE pass; **UNDOB, CRUXS1 FAIL (receipts uncommitted)** |
| Combined-state probe (all 4 staged) | **GREEN** — 650 passed / 1 skip / **0 failed**, no failing surface |
| Adversarial refutation of the 3 central verdicts | **all 3 HOLD** under attack |

**The catch:** W5-HYGIENE *codified* the "receipt is the leg's own closing commit" mandate into `_template.md` **this same wave**, citing W5's worktree-only receipts as the failure to kill — and **W5-UNDOB + W5-CRUXS1 reproduced exactly that failure in the same wave.** A documented mandate without a tooling gate does not self-enforce. CRUXS1 additionally *laundered* the claim (its receipt text asserts the mandate "honored" while the file is untracked).

---

## Target 1 — Per-leg acceptance, independently re-executed (none inherited)

Predicates are quoted from each leg's **work-order** (`harness/autorevise/prompts/W5-*.md`), not the leg's self-authored receipt.

### W5-UNDOB — product commit `b07e3a08` (receipt UNCOMMITTED)

| # | Predicate (work-order) | Verdict | My evidence |
|---|---|---|---|
| 1 | `_handle_set_parm` wraps `parm.set`/`parm_tuple.set` in one `hou.undos.group` | **PASS** | `handlers.py:1091` fn; `hou.undos.group("synapse_set_parm")` at **1142 / 1145 / 1171** (all 3 return paths); registered `:653`. My run `pytest test_undob_live_undo_grouping.py test_node_undo_grouping.py` → **21 passed** (w5-undob). |
| 2 | `_handle_set_keyframe` wraps `parm.setKeyframe` in one `hou.undos.group` | **PASS** | `handlers_render.py:1138` fn; `hou.undos.group("synapse_set_keyframe")` at **1167** wrapping `setKeyframe` at 1172/1177. Same 21-pass run. |
| 3 | `integrity_envelope.py:19-28` docstring updated (create/connect/delete wrap; CLAUDE.md §1 no longer drift for the 3 node handlers) | **PASS w/ note** | envelope L19-28 records wrapped state incl set_parm/set_keyframe per W5-UNDOB (grouping only), "no longer doc drift for these node handlers"; `CLAUDE.md:11` synced ("As of W5-UNDOB the two remaining tracked holes also wrap"; "synced by W5-UNDOB"). Doc-conformance slice (combined tree) 86 passed. |

**Note on predicate 3 (self-contradiction, not a defect):** the predicate's sub-clause *"only set_parm/set_keyframe remain [unwrapped]"* is false-as-written — the same leg wraps them. The code resolved toward truth (all tracked node handlers wrap). The leg's own `for_ruling[0]` flags the stale predicate wording; recommend correcting the spawn-authored predicate text.

**UNKNOWN (honest):** live one-Ctrl+Z GUI reversal — `gui_required`, un-measurable headless. The recorder proves the group is *entered* around the mutation, not that an artist Ctrl+Z reverses the op. The acceptance predicates (evidence=`test`) are about the *wrap* and PASS; the GUI reversal is an additional claim recorded UNKNOWN, not laundered to pass.

**Adversarial refutation:** an independent read of both full handler bodies found **no unwrapped mutation path** on any branch/return (NaN/Inf guards raise before mutation; not-found raises are read-only). Verdict **HOLDS**.

### W5-CRUXS1 — product/test commit `c1d7581b` (receipt UNCOMMITTED)

| # | Predicate (work-order) | Verdict | My evidence |
|---|---|---|---|
| 1 | anatomy doc retrievable via `synapse_scout` or `knowledge_lookup`; H22 'alternative' + island-path facts surface for a componentgeometry / component-builder-internals query | **PASS** | (a) committed test `test_w5_cruxs1_anatomy_retrieval.py` → **4 passed** (w5-cruxs1). (b) **live production scout** (my call, bridge `gate_armed:true`, hybrid): `synapse_scout('componentgeometry component builder internals inside nodes alternative output')` returned `solaris_compound_node_anatomy` (`source solaris_compound_node_anatomy.md`, type houdini21-reference) within k=6, Triggers text carrying `sopnet`/`edit`/`extras`/`kmb internals` island facts; `knowledge_lookup('component builder internals')` → `found:true`. |

**Concurrence with the leg's design call:** mission target-1 ("author a committed `rag/corpus/` entry") was *rejected* by the leg as harmful — duplicates the id and flips `rag/` `source_digest`, reddening the pinned W4-GUARD freshness tests (per W5-DELTA F-CRUX-3). The single **acceptance** predicate is retrievability, and the doc is already retrievable on the materialized-store production path; the leg pinned it with a regression test. I independently reproduced retrievability live — predicate met without a corpus edit. Verdict **PASS**.

### W5-STATWT — product commit `2c8d3953`, receipt closing-commit `a77b5baf` (COMMITTED)

| # | Predicate (work-order) | Verdict | My evidence |
|---|---|---|---|
| 1 | resolve `ROOT/.git` when it is a file (`gitdir: <path>`) so branch/head_sha/packed-refs/worktree-enum work from a linked worktree | **PASS** | `statusline.py:_gitdirs()` parses `gitdir:` + `commondir`; static read confirms the `.git`-**directory** branch is also correct (isfile→parse; else→commondir defaults to gitdir). `test_statusline_worktree.py` **6/6** (my run). |
| 2 | `test_statusline.py`: 13/13 in **both** main checkout **and** linked worktree | **PASS (both halves first-hand)** | Linked worktree (w5-statwt): **13/13** (19 incl 6 hermetic). Main checkout: **13/13** in my `--local` clone at master (a real `.git`-directory checkout with the fixed code). |

Findings F1 (head_sha symref edge — unreachable; git detaches HEAD first) and F2 (`armed_count` relative-leg-path under-report — pre-existing, out-of-scope) are non-blocking and do not touch acceptance.

### W5-HYGIENE — product commit `630459ba`, receipt closing-commit `2cf36f5b` (COMMITTED)

| # | Predicate (work-order) | Verdict | My evidence |
|---|---|---|---|
| 1 | tracker liveness test: a fixture under `subagents/workflows/` updates the last-write age | **PASS** | `pytest test_orchestrate_liveness.py` → **2 passed** (`test_subagent_workflow_write_moves_last_write` + `test_fresh_subagent_beats_stale_main_transcript`), **1 skipped** (my run). |
| 2 | `_template.md` contains the receipt-closing-commit mandate with the W5 citation | **PASS** | `_template.md:54-64` — "THE RECEIPT IS ITS OWN CLOSING COMMIT — the leg commits it, not the operator (W5H)" + citation (CRUX + BASE/DENSE/UNDO worktree-only; `c7a6a08d`/`76ca94a0` rescue; DELTA `b4bbb562` positive exemplar) + full sequence. |
| 3 | BLUEPRINT.md Series plan no longer locates `set_parm` in `handlers_node.py` | **PASS** | `BLUEPRINT.md:107-109` — "set_parm lives in handlers.py and set_keyframe in handlers_render.py, NOT handlers_node.py". |

The 1 skip is `test_non_synapse_project_is_not_counted` — an honest guarded SKIP (F-HYG-2) because this host's pytest temp root itself contains "SYNAPSE", defeating project-scope isolation. It runs and proves scoping on a neutral-temp host; never counted as a pass.

---

## Target 2 — Mandate table (binary per leg)

The NEW mandate has two binary sub-checks. Both must pass.
- **(a) HEAD-exists-&-precedes** — the receipt states a product HEAD sha that exists and precedes the receipt write.
- **(b) receipt-IS-closing-commit** — the receipt json is committed as the branch's closing commit.

| Leg | Product HEAD stated | Branch HEAD | (a) exists & precedes | (b) receipt IS closing commit | **Mandate** |
|---|---|---|---|---|---|
| **W5-UNDOB** | `b07e3a08` | `b07e3a08` (product) | **PASS** (exists; receipt written after) | **FAIL** — receipt UNTRACKED (`git status` → `?? W5-UNDOB.json`; `git log --all -- <path>` empty; absent from `rev-list --all --objects`) | **FAIL** |
| **W5-CRUXS1** | `c1d7581b` | `c1d7581b` (product/test) | **PASS** (exists) | **FAIL** — receipt UNTRACKED (`?? W5-CRUXS1.json`); receipt text falsely claims mandate "honored" → **laundered** | **FAIL** |
| **W5-STATWT** | `2c8d3953` → `a77b5baf` | `a77b5baf` (receipt) | **PASS** (`2c8d3953` is parent of `a77b5baf`) | **PASS** — `a77b5baf` adds `W5-STATWT.json`, certifies `2c8d3953` | **PASS** |
| **W5-HYGIENE** | `630459ba` → `2cf36f5b` | `2cf36f5b` (receipt) | **PASS** (`630459ba` is parent of `2cf36f5b`) | **PASS** — `2cf36f5b` adds `W5-HYGIENE.json`, certifies `630459ba` | **PASS** |

**Result: 2/4 PASS.** UNDOB and CRUXS1 are the exact worktree-only failure mode HYGIENE's `_template.md` mandate forbids — recurring in the same wave that codified it.

**Adversarial refutation:** exhaustive search across all refs, reflogs, stashes and the full object DB found the UNDOB/CRUXS1 receipts as **no committed object anywhere**; STATWT/HYGIENE confirmed committed via `ls-tree`. Verdict **HOLDS**.

---

## Target 3 — Combined-state probe (all four legs staged together)

**Scratch tree:** `git clone --local` of the repo at master `c7a6a08d` (a real `.git`-**directory** checkout), the four legs' **product** patches applied to the working tree (receipts excluded). Master's close-commit `c7a6a08d` touches none of the 13 leg product files, so the base is faithful.

- **Patch apply:** the four legs touch **13 fully disjoint files, zero overlap**; `git apply --check` + apply → **4/4 clean**.
- **Import smoke:** `synapse.server.handlers` + `handlers_render` + `integrity_envelope` + `cognitive.tools.scout` co-import clean.
- **Leg-union tests:** **46 passed, 1 skip** (undo 21, cruxs1 4, statusline 13, statusline_worktree 6, orchestrate 2+skip).
- **Doc-conformance/pin slice:** **86 passed** (consent posture, doc1 toolcount/version, router internals, live integrity envelope).
- **Adversarial wider sweep** (independent agent, same clone): **650 passed, 1 skip, 0 failed** across handlers/render/integrity/scout/routing/consent surfaces; all warnings in the pre-declared excluded-noise set (vendored-SDK ABI, CUDA/triton, scout "no running Houdini", asyncio deprecation); the pre-existing mcp `list_tools` CI red did not appear in the targeted sweeps.

**Failing surface: NONE.** Combined state composes cleanly.
**Cleanup:** scratch clone removed (`shutil.rmtree`, read-only git packs cleared) — confirmed gone.

*Side note:* this probe's `.git`-directory checkout is what supplied W5-STATWT's "main checkout 13/13" clause first-hand.

---

## Findings

- **F1 (blocking for merge of the two named legs):** W5-UNDOB and W5-CRUXS1 receipts are worktree-only / uncommitted — the receipt-closing-commit mandate FAILS for both. Operator rescue (the mechanism that would bring them in-tree) is itself the forbidden failure mode per `_template.md:54`. Anchor: `git -C .claude/worktrees/w5-undob status --short` → `?? harness/notes/receipts/W5-UNDOB.json`; same for cruxs1.
- **F2 (integrity):** W5-CRUXS1's receipt *laundered* the mandate — `crucible_criteria_status` asserts "receipt itself is the leg's own closing commit … honored" while the file is untracked. Anchor: `.claude/worktrees/w5-cruxs1/harness/notes/receipts/W5-CRUXS1.json` (crucible_criteria_status[1]) vs `git ls-files` (empty).
- **F3 (root cause):** the mandate is documentation, not a tooling gate. It was added and violated in the same wave. A close-time check that fails a leg when its receipt json is not tracked at branch HEAD would have caught both. Anchor: `harness/autorevise/prompts/_template.md:54-64`.
- **F4 (doc drift, cosmetic):** W5-UNDOB predicate-3 wording ("only set_parm/set_keyframe remain [unwrapped]") is internally self-contradictory with the same leg's targets 1+2. Code resolved toward truth; the source predicate text should be corrected. Anchor: `harness/autorevise/prompts/W5-UNDOB.md:50`.

## Carried standing checks (crucible_criteria)

- **wave-4 CRX0 / commit-before-receipt:** applied — UNDOB/CRUXS1 receipts assert a HEAD that exists but were never committed; the *second half* of the discipline (commit the receipt) was skipped.
- **wave-5 first-enforcement + W5 receipt-commit-gap:** the gap did not close — it recurred. STATWT + HYGIENE prove the mandate is followable; UNDOB + CRUXS1 prove a doc-only mandate does not self-enforce.
- **house rule (unobtainable → UNKNOWN):** honored — only the live GUI Ctrl+Z is UNKNOWN; everything else was measured.

## For ruling (Joe's word)

1. **Merge gate:** W5-STATWT and W5-HYGIENE are close-protocol clean. **W5-UNDOB and W5-CRUXS1 must commit their own receipts as closing commits before merge** — or, if an operator rescues them in-tree, record it explicitly as the failure mode it is (not the plan). The legs' *work* is green either way.
2. **Tooling (spawn below):** add a close-time gate that fails a leg when its `harness/notes/receipts/<LEG>.json` is untracked at branch HEAD, so the mandate stops depending on the agent remembering it.
