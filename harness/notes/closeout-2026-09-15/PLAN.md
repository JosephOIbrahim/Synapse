## The call

Five branches are already on master and can be deleted this morning without review; eleven more are superseded, dead, or worth only a hand-salvaged hunk; five merge, in a fixed order, with `fix/cto-render-20260908` last because it is the only high-risk one and the only one with no PR and therefore no CI. PR #80 closes rather than merges — master already shipped that installer and the branch's four differing files are the older 5.67.4-preview text (`git show master:README.md:13` advertises 5.70.0). The one artist-facing scaffold worth building next is **the Undo Receipt**: every mutating handler already computes the exact answer to "what does one Ctrl+Z reverse?" as a `hou.undos.group("...")` label and throws it away, and a repo-wide grep for `Ctrl+Z|undoable|can be undone` across every `.py` returns **zero** artist-facing strings.

---

## Merge train

**The suite gate, stated once.**

Full `pytest tests/` at the merge-base of each branch, then again after the rebase. Zero NEW reds. The local floor was **8869 passed / 412 skipped / 0 failed at bd65e4b6** (producer: `harness/notes/v2-waves-2026-09-14/suite-floor-bd65e4b6.txt`).

Three standing hazards on that gate:

- **Never** run `pytest tests/` while the hython seat suite is running. They fight over `~/.synapse/logs/synapse.log` and whichever loses the rotation race fakes a red.
- `python` on this shell resolves to **3.14.2**, not the repo's 3.13, and emits a vendored-SDK ABI mismatch warning on `import synapse`. The 8869 floor was not measured on 3.14. Pin the interpreter or every delta you see is manufactured.
- This host has **both** Houdini 22.0.400 and 22.0.429 installed and the hytest shim picks newest. Any live probe needs `SYNAPSE_HYTHON` pinned or the receipt lies about which build it ran on.

**Pre-flight, before stop 1.**

```powershell
cd C:\Users\User\SYNAPSE
git log --oneline -1 master                 # expect 67625294
git worktree list                           # record every checked-out branch BEFORE any delete
git -C C:\Users\User\synapse-m2-pgdrm-wt status --porcelain
```

That last line is not optional. **The mem/m2-pgdrm repair is uncommitted in its worktree** — `M python/synapse/loop/pgdrm.py`, `M tests/test_pgdrm_kernel.py`, +326/-1. Any `git worktree remove` or `prune` pass that runs before stop 4 destroys it.

Also check for a live orchestrator before touching any remote branch. `orchestrate.ps1`'s `Backup-Branches` auto-pushes every feature branch while an orchestrator runs, so a public delete can come straight back.

---

### Stop 1 — `design/rulings-2026-09-14` (batch 0) · MERGE_NOW · conf 0.95

**Fix the branch, then merge once.** The original verdict merged first and corrected second; both corrections are edits to the one file being merged, and **origin is a public repo**, so the known-wrong sentence would enter public master history and get fixed by a second commit. merge-base *is* master HEAD and the PR is CLEAN, so an extra commit on the branch cannot create a rebase surface.

```powershell
gh pr view 82 --json mergeable,mergeStateStatus,statusCheckRollup
```

Then, on the branch, two edits to `harness/design_review/2026-09-14/RULINGS-OPEN.md`:

1. **Split C2 into C2a and C2b.** C2a = ship / don't ship the receipt line. C2b = scroll the content or the widget. As written, the reply "C2 ship" does not say which, and the ambiguous reading is the one the doc itself prices at **-73 to -87px**.
2. **Correct the "If you only do one thing" sentence** (verified verbatim at lines 27-28) to match A1's own body: A1 gates B2, B2 gates A2, A3 is a conditional guard on A1. It does not collapse three items into bookkeeping.

Let CI re-run — a five-minute docs job, already proven green. Then:

```powershell
gh pr merge 82 --squash --subject "docs(design): put the 16 open design calls on one decision surface"
```

**Verify after.** `git ls-tree --name-only master -- harness/design_review/2026-09-14/` — AIRY-ANSWER.md, DECISION-BRIEF.md, README.md, REFINEMENT-COHERE.md, SCAFFOLD.html and SEAT-CONFLICTS-FOR-JOE.md are all tracked **on master**, so every link in the merged doc resolves with no follow-up.

**Unblocks.** Nothing mechanical. It puts 16 rulings on one surface — it does not give them a landing zone (see DEC-3).

**Suite.** Zero code under `python/`; this is a docs-only diff under `harness/`. The floor is not at risk by construction, but no suite was executed to prove it.

**Refuter dissent:** none. CI is fully green on headRefOid 5c1e7acb — 4/4 test jobs (ubuntu + macos × 3.11 + 3.14) plus CodeRabbit, all SUCCESS. The phantom-lint concern the original verdict raised as its one unknown is empirically disproven.

**Not checked:** whether branch protection or CODEOWNERS imposes a required reviewer on `harness/` paths, which would make `gh pr merge --squash` fail despite CLEAN.

---

### Stop 2 — `fix/demo-repairs-20260909` (batch 2) · REBASE_THEN_MERGE · conf 0.88

**Second because it is the smallest of the three tool-count resolutions.** Exactly two conflicts, both one line.

```powershell
git fetch --all; git log --oneline -1 master      # confirm still 67625294
git checkout -b rebase/demo-repairs fix/cto-demo-repairs-20260909
git rebase master
```

Conflicts, both one-line:

| File | Line | Resolution |
|---|---|---|
| `CLAUDE.md` | 3 | Keep master's line (SYNAPSE v5.70.0); bump the tool count |
| `README.md` | 121 | Keep master's line; bump the same count |

**Do not type "129".** Recount from the producer: `grep -c` on `_tool_registry.py` tuple heads returns 128 today. Recount after the rebase applies. Then grep for a count-pinning conformance test that also needs the bump.

Before you trust it, three things the original verdict missed:

- The commit **modifies four existing test files** — `tests/test_store_degraded_load.py`, `test_memory_handle_law.py`, `test_loop_integration.py`, `test_rsi_stage0_panel.py`. `test_store_degraded_load.py` pins the refuse-writes-on-damage posture that is this branch's own stated main risk. A modified pin on a shipped surface needs line-by-line review, not "new tests back it".
- **Five touched files go unmentioned** by the verdict: `python/synapse/session/tracker.py` (+89), `memory/moneta_store.py` (+21), `memory/scene_memory.py` (+8), `server/handlers.py` (+18), `mcp_tools_scene.py` (+4).
- **Consent tier.** `python/synapse/panel/bridge_adapter.py:83` maps the new `houdini_layout_network` to operation `set_parameter` — the **INFORM** gate. A tool that repositions, recolors and re-boxes an artist's entire network runs at the lowest consent tier. Defensible under one-native-undo, but make it a conscious call at merge.

**Verify after.**

```powershell
python -m pytest tests/test_network_layout.py tests/test_demo_memory_scope.py tests/test_demo_memory_recall.py tests/test_memory_lifecycle.py tests/test_memory_owner_dispatch.py tests/test_moneta_search_serialization.py tests/test_session_journal_main_thread.py -q
python -m pytest tests/ -q
```

Half B rewrote `store.py` — treat any new red as blocking. The live layout contract (undo grouping, artist-box refusal) is `hou`-side and unproven; `hython scripts/probe_network_layout.py` needs `SYNAPSE_HYTHON` pinned.

**Unblocks.** A new artist-facing tool, and it sets the tool-count precedent for stops 3 and 5.

---

### Stop 3 — `feat/cache-insert` (batch 4) · REBASE_THEN_MERGE · conf 0.86

The brief's cache_control hypothesis is **refuted** — prompt caching already shipped at `python/synapse/panel/providers/anthropic_provider.py:132,137,150,157`. This branch is the missing *action* half of the cache advisor, and master's own code documents its absence.

```powershell
git worktree add ..\syn-cacheinsert feat/cache-insert
git -C ..\syn-cacheinsert rebase master
```

Two conflicts:

1. **`CLAUDE.md`** — the branch bumps 124→125. **Recount, do not copy.** Stop 2 already moved this number. Also check `README.md:121`, which the branch does not touch and which will drift out of sync on merge.
2. **`python/synapse/server/handlers_cache.py`** — master's only drift is the 4-line docstring at `:11` asserting *"there is no ``synapse_insert_cache``"*. Delete that sentence, keep the branch body.

**Struck from the original steps:** the manual "check the registry entry against the post-v5.70.0 naming convention" step. `tests/test_activity_labels.py:92` already sweeps every live registry name automatically. Run that one file instead.

**Verify after.** `pytest tests/test_cache_insert_gates.py`, then the full suite. Then live-verify on a pinned 22.0.400 seat — and **exercise the failure path**, not just the happy one. `hou.undos.group` is grouping, not rollback; a failed insert leaves a partial network the artist must undo deliberately. "One Ctrl+Z reverses it" is a success-path claim only.

**The REVIEW-gate safety story may be inert on this tool's actual path.** Master's bridge default is `GateLevel.REVIEW` — that citation is sound. But CLAUDE.md §1.2 says the live `/synapse` transport does not route through `LosslessExecutionBridge`, and **neither pass verified that insert_cache's live dispatch consults `OPERATION_GATES` at all**. Combined with the 2026-08-18 DECIDE (the panel worker may not self-authorize gated ops), the gate must be live-verified before the flag is flipped, not assumed.

**Gate question for Joe:** merge dark (`SYNAPSE_CACHE_ADVISOR_ENABLED` unset) or flip it on. Separate call from the merge — see *Needs your word*.

**Not checked by either pass:** the 510-line `handlers_cache.py` body, the 5-line `rbac.py` drift, and the assay receipt itself. `harness/notes/cache_h22_insert_assay_22.0.400.json` being *named* 22.0.400 does not prove it ran on 22.0.400.

---

### Stop 4 — `mem/m2-pgdrm` (batch 0) · REBASE_THEN_MERGE · conf 0.85 · **GATED ON A RULING**

Master has no `pgdrm.py` at all (`git ls-tree -r master --name-only -- python/synapse/loop` lists nine files, none of them pgdrm) and `tests/` has no `test_pgdrm_kernel.py`. Not superseded. 403 commits behind, zero conflicts — both files are new.

**Do not start this stop until the §2.3 question is answered.** The branch merges a kernel with zero producers and zero consumers. That is the exact shape SYNAPSE retired once already (CLAUDE.md §2.3, router auto-promotion, whose revival bar is *"a production caller must exist first"*). `docs/BATTLEPLAN_2026-08-31.md` frames the merge as a memory-board gate — i.e. the reason to merge is board bookkeeping, not a consumer. If the M3 rung that would call it is not queued, HOLD is defensible on precisely the grounds the verdict itself cites.

If the answer is MERGE:

```powershell
git -C C:\Users\User\synapse-m2-pgdrm-wt diff       # review the +326/-1 repair before trusting it
git -C C:\Users\User\synapse-m2-pgdrm-wt add python/synapse/loop/pgdrm.py tests/test_pgdrm_kernel.py
git -C C:\Users\User\synapse-m2-pgdrm-wt commit -F <msg-file>
```

**The commit message must say REFUSED, not "materialized".** The uncommitted repair adds `_reiterable()` raising `TypeError` when `iter(value) is value`; its own docstring states *"Materializing the argument at entry does NOT repair it … The only reproducible answer is to refuse the argument."* That is a behavior-changing public API contract — a caller passing a generator to `evaluate()` / `filter_records()` / `MemoryRecord(tokens=...)` now gets a TypeError. Blast radius is zero today because nothing calls the kernel, but the next reader inherits the mental model you write down. The "materializes" phrasing was copied from `STATE.json`'s spawn_ledger scope line, written before the fix leg chose refusal.

Then rebase, re-measure against a **fresh** floor at merge-base (the 2026-08-22 `6856 passed` figure is ~2000 tests stale), and re-run `harness/memory/runs/2026-08-22/m2fix_mutate_harness.py` for 28 RED / 0 survivors.

**Verify after.** `tests/test_pgdrm_kernel.py:96` asserts `MemoryPort().query_and_filter(...).status == "UNAVAILABLE"` — that is **environment-coupled, not pure**. It is UNAVAILABLE only because `MONETA_SRC` is unset. A provisioned harness seat (`MONETA_SRC` + `PXR_PLUGINPATH_NAME`) can bind a live MemoryPort and flip that guard red. Measure on both an unprovisioned and a provisioned seat, or expect a future flake nobody traces back here.

**Post-merge bookkeeping:** flip `harness/memory/STATE.json` `rungs.m2` off "FIX LEG RUNNING" and set merged/pushed in `harness/memory/bus/memory_m2_pgdrm_kernel.json`. Both are stale.

**Treat as UNVERIFIED:** `harness/memory/runs/2026-08-22/m2fix_suite_branch.txt` has an mtime of **Sep 5**, not Aug 22 like every other artifact in that directory. A suite log written two weeks after the run it claims to record is not trustworthy provenance. Re-measure rather than citing its `3 failed, 6856 passed` tail.

---

### Stop 5 — `fix/cto-render-20260908` (batch 0) · REBASE_THEN_MERGE · conf 0.78 · **HIGH RISK, LAST**

The real work and the only branch of its pair that should survive: a durable out-of-process render farm (`python/synapse/farm/native_driver.py:216-224` — `subprocess.Popen(... CREATE_NO_WINDOW)`). 45 files, +6441/-34. Master moved **81 commits** under it.

Last in the train because it has **no open PR**, so it has had no CI at all, and because it is the only branch whose conflicts are real code.

```powershell
git worktree add ..\SYN-render-rebase fix/cto-render-20260908
git -C ..\SYN-render-rebase rebase master
```

Five conflicts, in order of danger (verified via merge-tree):

| File | Why |
|---|---|
| `python/synapse/panel/tool_executor.py` | Real code — master's Panel PD wave rewrote this |
| `python/synapse/panel/synapse_panel.py` | Real code — same wave |
| `python/synapse/server/hwebserver_adapter.py` | Real code |
| `CLAUDE.md` | Governing doc — **Joe resolves this one**, not a tool |
| `README.md` | The ADHD-friendly convention applies |

`handlers.py`, `shared/bridge.py`, `mcp/server.py`, `bridge_adapter.py` and `qss.py` all auto-merge clean.

**Four blockers to close during the rebase, not after.**

1. **The build pin.** `python/synapse/farm/package.py:12` — `QUALIFIED_BUILD = "22.0.400"`, and `native_driver.py:597` gates on `hou.applicationVersionString() != pkg.QUALIFIED_BUILD`. This host now has 22.0.429 installed too. Widen the check or downgrade it to a warning, and confirm behaviour on a real 429 seat.
2. **The 541-line uncollected harness.** `tests/native_render_workspace.py` does not match pytest's collection pattern. Either rename it to `test_native_render_workspace.py` or move it out of `tests/` so it stops reading as coverage it is not.
3. **MISSED BLOCKER — `activity.py`.** Master's `b475ee22` (2026-09-14) added `python/synapse/panel/activity.py`, the artist-facing tool-label authority pinned by `tests/test_activity_labels.py`. `git grep -n farm master -- python/synapse/panel/activity.py` returns no hits and the branch does not touch the file, so its seven `synapse_farm_*` tools and the new Render workspace fall straight through the fallback path that commit was written to fix. **It is invisible to merge-tree** (no textual overlap), so it is absent from the five-file conflict list. Populate the labels during the rebase.
4. **Layout question.** `mcp_tools_render.py` is at the **repository root**, not under `python/synapse/mcp/` (the original verdict's path citation errors with `fatal: path does not exist`). Content verified at `fix/cto-render-20260908:mcp_tools_render.py:24-25,47-53` and `python/synapse/mcp/_tool_registry.py:1276+`. A root-level MCP tool module is an unaddressed question for the rebase.

**Verify after.** Full `pytest tests/`. Then **open a PR** so this gets CI — it currently has none. Recount the tool count a third time; the branch registers seven farm tools on top of stops 2 and 3.

**One good piece of news:** `git diff --name-only 87ce354a..fix/cto-render-20260908 | grep handlers_render` returns **no match**. The known freeze path `python/synapse/server/handlers_render.py` is untouched by this branch.

**Unblocks.** The `feature/tops-renderfarm-20260907` archive (it is a strict ancestor), and it is the only branch in this run that moves RENDER from "does not complete" toward completing.

**Architecture question for Joe, before or at merge:** does `houdini_render` stay as a second road alongside the farm? See *Needs your word*.

**Not checked, stated rather than assumed:** rebase completion, post-rebase suite state, the handlers_render-untouched claim past the name-only diff, exact RBAC level assignments, real 22.0.429 seat behaviour, whether root-level `mcp_tools_render.py` pre-exists on master, and whether ~1,700 lines of farm tests still import after 81 commits of drift. Ancestry proves bytes are duplicated; it does not prove either branch is healthy.

---

## Archive list

**Two standing rules for every delete below.**

`git branch -D` is **local only**. Most of these branches are live on the **public** origin; the local delete alone leaves them published. And `git branch -D` fails outright while a branch is checked out in a worktree — `git worktree remove <path>` must come **first**, and `git worktree prune` does not remove a worktree whose directory still exists.

Where a verdict recommends `git tag archive/...`, **push the tag before deleting the public branch**, or the only surviving copy of destroyed history is one machine's local tag.

---

### Already patch-landed on master — delete, no review

`git cherry master <B>` proved every commit is already applied by patch-id.

```powershell
git worktree list                     # check each before deleting
git branch -D fix/cto-release-panel-tests
git branch -D fix/cto-release-contracts
git branch -D fix/cto-panel-20260908
git branch -D fix/cto-memory-20260908
git branch -D fix/m09-task-history-20260907
```

**UNVERIFIED:** whether any of these five has a remote ref on origin. No `git ls-remote` was run for them. Check before assuming the local delete finished the job.

---

### Superseded — the content lives elsewhere

**`feature/windows-installer-20260909`** — PR #80, DRAFT, CONFLICTING/DIRTY.

Evidence: `git log master -- installer/` → `8c23fccc|2026-09-13|Release v5.68.0 with proposal controls and Windows Setup`. 21 of 25 files are byte-identical to master; the four that differ (`README.md`, `docs/getting-started/installation.md`, `installer/README.md`, `installer/test_executable.py`) are the branch's **older** 5.67.4-preview text. `git show feature/windows-installer-20260909:docs/getting-started/installation.md:9` advertises `SYNAPSE-5.67.4-Setup.exe`.

```powershell
gh pr close 80 --comment "Superseded: this installer shipped on master in 8c23fccc (v5.68.0) and is now published as SYNAPSE-5.70.0-Setup.exe. The 4 files still differing here are the older 5.67.4-preview text; merging would regress the download link."
git worktree list                     # remove any worktree on this branch FIRST
git branch -D feature/windows-installer-20260909
```

**Refuter dissent (accepted):** the risk wording overstated the mechanics. The PR is DIRTY, so merging cannot *silently* resolve the download URL back to the preview tag — it halts with conflicts in exactly those four files and a human resolves them. The hazard is a bad conflict resolution, not an automatic regression. Direction still correct. Also: the PR head branch **survives on origin** after `gh pr close` — that is why this delete is genuinely reversible, and why the local delete is not the end state.

**Salvage (unrelated, do not take it from this branch):** master's `docs/getting-started/installation.md:10` still advertises `SYNAPSE-5.68.0-Setup.exe` while master's `README.md:13` advertises 5.70.0. One-line master-side doc fix, verified live this run.

---

**`feature/tops-renderfarm-20260907`** — **GATED on stop 5.**

Evidence: `git merge-base --is-ancestor feature/tops-renderfarm-20260907 fix/cto-render-20260908` → exit 0; the reverse is non-zero. Identical shas on both: be7cb4fe, c867f61f, 89686a3e, 52a79c53, 0c832cd5, d92b6487, 5b7f3964. `git cherry | grep -c '^+'` → render 8, tops 7; the delta is exactly one commit (b07eaa40), and the tip-to-tip diff is **pure subtraction** (-788 lines including `tests/test_farm_recovery.py`, 412 lines). It cannot hold a unique hunk.

Do not delete until `fix/cto-render-20260908` is on master. Then:

```powershell
git merge-base --is-ancestor feature/tops-renderfarm-20260907 fix/cto-render-20260908   # re-confirm
git cherry master feature/tops-renderfarm-20260907 | Select-String '^\+'                # expect none
git worktree remove C:\Users\User\OneDrive\Documents\ChatGPT\SYNAPSE_Refactor\worktrees\tops-renderfarm
git branch -D feature/tops-renderfarm-20260907
```

**Refuter dissent (accepted, two corrections):**

- The original step `git push origin --delete feature/tops-renderfarm-20260907` **errors** — `git ls-remote origin 'refs/heads/*tops-renderfarm*' 'refs/heads/*cto-render*'` returns **only** `refs/heads/fix/cto-render-20260908`. This branch was never pushed. Drop that step.
- The stated risk of "stranding shared history on one ref instead of two" is overstated: because render is on origin and tops is not, the seven shared commits already live on exactly one remote ref, and it is the pushed one.

---

**`feat/panel-ux-pass`** — the shipped Pentagram panel already does connection-state-at-a-glance on these exact two buttons.

Evidence: `master:python/synapse/panel/synapse_panel.py:1091` builds Corpus as `c.Button("Corpus", variant="primary")` and `_refresh_corpus_state()` (~:1209-1223) flips it to `Corpus ✓` off `entries.jsonl`. The connection dot + label live at `python/synapse/panel/chat_panel.py:613-616` and `:663`. The branch replaces both with raw `QtWidgets.QPushButton` + `setObjectName("DsConnPill")`.

```powershell
git tag archive/feat-panel-ux-pass 0d27a17f
git push origin archive/feat-panel-ux-pass          # BEFORE the delete
git worktree list | Select-String panel-ux
git branch -D feat/panel-ux-pass
```

**Refuter dissent (accepted, mechanism half wrong):** the original verdict claimed raw QPushButton is "what `tests/panel/test_token_authority.py` exists to catch". That test's own docstring says otherwise — it is an AST pin that the panel has exactly **one** colour authority, i.e. it flags a *module* redeclaring colour names, not a raw Qt widget. The branch adds its token inside `designsystem/tokens.py`, the sanctioned authority, so that test would plausibly stay green. The one verbatim-verified merge blocker is the **modal guard** (`tests/panel/conftest.py` + `test_modal_guard.py`). Disposition unaffected.

**Salvage:** master's `_on_corpus` announces "Corpus loaded (n)" but never names the directory. A one-line addition of `str(_scout.RAG_ROOT)` carries the only idea worth keeping, without the modal. Separate ticket.

**Not checked:** no test-merge was run for this branch by either pass. The `qss.py` +15 DsConnPill rule was never checked against master's current `qss.py` and no conflict count exists.

---

**`repair/ledger-moneta-seam`** — every code and test file is byte-identical to master.

Evidence: `git diff --stat master:python/synapse/memory/ledger.py repair/ledger-moneta-seam:...` → **empty**. Same for `python/synapse/science/deposit.py` and `tests/test_ledger_moneta_seam.py` (rc=0). Patch-id misses it only because the content landed under a different commit.

```powershell
git tag archive/repair-ledger-moneta-seam repair/ledger-moneta-seam
git branch -D repair/ledger-moneta-seam
```

**Refuter dissent (accepted, conclusion-preserving):** the verdict's risk line said one file holds branch-only bytes; **four** do — `moneta_runtime.py` (22 lines), `docs/studio/DEPLOYMENT.md` (35), `mutation_ledger_moneta.json` (33), `mutate_ledger_moneta_seam.py` (4), 94 lines total. All are predecessors of master content. The stated evidence understated the surface 4×. `DEPLOYMENT.md`'s one-line `SYNAPSE_MEMORY_BACKEND` seam-gating row — the only artist-visible doc this branch produced — is on master at `DEPLOYMENT.md:130` verbatim.

**Not checked:** whether `tests/test_ledger_moneta_seam.py` is actually *collected and green* on master. Byte-identity is proven; execution is not. If it is silently uncollected there, the two Moneta-seam defect fixes are unpinned — a master defect to raise separately, not a reason to keep this branch.

---

**`repair/h1-schemas-b`** — master already carries both reconciled TOOL_RETURN enums **and** the derived AST pin.

Evidence: in `git diff master:.../schema_set_purpose.py repair/h1-schemas-b:...`, the line `"enum": ["set", "updated", "unchanged", "noop", "not_found"]` appears as **context** (no `+`/`-` prefix). Same for `"enum": ["created", "already_exists"]` in `schema_create_variants.py`. `git grep -l TOOL_RETURN master -- tests python` → `master:tests/test_solaris_tool_registration.py` — the consumer the branch said did not exist.

```powershell
git tag archive/repair-h1-schemas-b repair/h1-schemas-b
git branch -D repair/h1-schemas-b
```

**Salvage — two prose fixes are genuinely unreplicated and unguarded:**

1. Master's `schema_set_purpose.py` still carries `"description": "The purpose that was assigned."` on the `purpose` field — which the branch's own commit documents as **false** on the `noop` path (execute() echoes the *requested* purpose while authoring nothing).
2. Master's `schema_create_variants.py` `'created'` description omits the partial-overlap behaviour: a partial overlap falls through the all-or-nothing `if all(...)` guard at `create_variants.py:163`, builds the missing variants, and still reports `created`.

Neither is guarded. Master's pin reads only `status["enum"]` and payload key *names* — no test pins description prose, so both misstatements will never go red.

**Refuter note:** `origin/repair/h1-schemas-b` exists on the public remote and `git tag` is local-only, so the branch survives upstream and reappears on any clone. The remote's fate is a separate human call. Also: `H1.json` differs by 225 insertions / 297 deletions — master carries a **different, longer** H1 receipt. Whether master's supersedes the branch's or merely diverges is **UNVERIFIED**; neither receipt was read.

---

### No remaining value

**`rope/beacon`** — a stopped 5-minute cron heartbeat.

Evidence: 20 commits, all 2026-08-03, 19 titled `beacon 2026-08-03 HH:MM:SS` at exact 5-minute spacing (14:14:13 → 15:44:46). `git diff --stat` → `STATUS.md | 25 +++++`, one file, no deletions. `git cat-file -e master:STATUS.md` → **absent** on master, so this would introduce a new root-level file. Every verdict it reports is stale against `master:harness/rope/STATE.json`.

```powershell
git show rope/beacon:STATUS.md > C:\Users\User\SYNAPSE\harness\rope\beacon_ledger_2026-08-03.md   # OPTIONAL
git worktree remove C:\Users\User\rope-beacon-wt
git branch -D rope/beacon
```

**Refuter dissent — the origin delete is NOT durable, and it breaks a documented link.** Two findings:

- `master:harness/rope/rc.ps1:5-7` recreates the worktree (`git worktree add -B rope/beacon`) and `:49-50` **force-pushes** (`git push -f origin rope/beacon`) every cycle; `rc.cmd` is a double-click launcher. So `git push origin --delete rope/beacon` holds only until someone next arms `rc.cmd`, which resurrects the branch on the **public** origin with the same stale "GATE A: HOLDING" and "You've hit your session limit" strings. Either retire rc.ps1's beacon push in the same human pass, or accept the branch as regenerable scratch and **skip the origin delete entirely**.
- `master:harness/rope/OPERATOR_CARD.md:115-117` publishes `https://github.com/JosephOIbrahim/Synapse/blob/rope/beacon/STATUS.md` as the documented remote-control readout. Deleting the origin ref 404s a link tracked on master.

Minor: `STATUS.md` on the branch carries a UTF-8 BOM; the optional extraction step's PowerShell `>` re-encodes (UTF-16LE on PS 5.1). Cosmetic, but the step's purpose is preserving evidence.

**Not checked:** whether `master:harness/rope/STATE.json`'s `log` array already replicates the 10 telemetry rows (if so, the extraction is redundant); whether any scheduled task still arms rc.ps1 on this host.

---

**`stray/audit-log-threading`** — 826 lines master does not have, zero consumers on either side.

Evidence: `git show master:python/synapse/core/audit.py | sed -n '218,236p'` — `AuditLog.log()`'s signature ends at `sequence_id: str = ""`, no `duration_ms` / `before_state_hash` / `after_state_hash`. The threading is genuinely not on master. But `git grep -n replay_info master -- python tests scripts panel` → only its own definition at `audit.py:440`, **zero callers**, so the sole reader of these fields is dead code. The branch's written revival condition (the R302 instrument lane wanting these fields) came and went without reviving it.

```powershell
git tag archive/stray-audit-log-threading stray/audit-log-threading
git branch -D stray/audit-log-threading
```

**Refuter dissent (accepted, downgrades risk):** `origin/stray/audit-log-threading` already holds `03f279fc`, so this is not the only copy — risk med → **low**, the archive loses nothing. Correspondingly, `git branch -D` leaves it on the public origin and in `git branch -a`, so a later work-graph run rediscovers it. Removing it for real needs `git push origin --delete`, a public-repo mutation for Joe alone — and leaving it is literally R308's stated "dies of natural causes in the branch list". `git worktree prune` is a no-op here; `git worktree list` shows no worktree on this branch.

**Strengthening fact the original verdict missed:** master already implements hash-scene-state-around-an-op in **four** live files (`shared/bridge.py`, `server/integrity_envelope.py`, `panel/session_integrity.py`, `memory/agent_state.py`). `state_digest.py` is a fifth duplicate at a dead layer, not an unreplicated capability.

**The one sentence that could keep it:** `master:python/synapse/loop/ports.py:90` — `SafetyPort.evaluate_path` takes a `scene_state_digest` parameter that **nothing on master produces**. A signature with no filler, adjacent to what this module computes.

---

### Salvage, then delete

**`bp2/nits`** — three of four nits still describe real defects on master; the fourth is a regression.

Evidence: `git merge-tree --write-tree --name-only master bp2/nits` exits 0 at master 67625294 → **merge clean, no rebase needed**. T1's site is still defective: `git show master:harness/battleplan/runs/2026-09-01/prove_bp2_meter_dryrun.ps1` line 73 still reads `(& git -C $repoRoot show HEAD:harness/orchestrate.ps1)`. T2's site is still defective: `master:docs/MONETA_FOLLOWUPS.md`'s status table still has `| Follow-up | Risk | Blocked on | Ship as |` with FU-1/FU-2 reading "focused PR (invert tripwire)" and "PR when sleep_pass is exposed".

**Leave behind:** `dc9e803e` (dashboard pill "open" → green) — a legibility regression on the human-gate table. And the receipt.

```powershell
git checkout -b bp2/nits-landed master
git cherry-pick 19a6697c 361cc6e7 dab6c634
```

Then **two citation fixes, as a separate fixup commit** (not `--amend`, which would fold the MONETA_FOLLOWUPS correction into the BATTLEPLAN commit):

- `docs/BATTLEPLAN.md` row 6: `memory_latency_hython_provisioned.json` → `.jsonl` (the file on disk is `.jsonl`)
- `docs/MONETA_FOLLOWUPS.md` FU-1: `test_moneta_crucible.py::test_duplicate_content_gets_distinct_ids` → `test_moneta_crucible.py::test_repeat_deposits_distinct_ids_count_equals_all_divergence_gone`

Verify the corrected pin actually collects before merging:

```powershell
python -m pytest tests/test_moneta_crucible.py::test_repeat_deposits_distinct_ids_count_equals_all_divergence_gone -q
```

Then, after `bp2/nits-landed` merges:

```powershell
git worktree remove C:\Users\User\SYNAPSE\.claude\worktrees\bp2-nits     # MUST come first
git branch -D bp2/nits
```

**Refuter dissent (accepted, three corrections):** the worktree at `.claude/worktrees/bp2-nits` (0dd5451e) blocks `branch -D`, so the order above is inverted from the original steps. T1's replacement reference is **unpinned** — `HEAD~1` on master today is `2c30f890` (docs/release), not the pre-BP2-METER parent; the branch trades a guaranteed-empty diff for a floating baseline. **Pin the sha instead.** And the original step 1 (`... >/dev/null && echo CLEAN`) is POSIX, runnable only via the Bash tool.

---

**`feat/scene-model`** — kill the 1,900-line turn-measurement instrument; re-apply two small fixes by hand.

Evidence: merge-base `0f14c9500b` (2026-07-18), **1337 commits** behind, 2 unapplied. 11 files / 1967 insertions, of which **920 are the two new test files** (`tests/test_read_ledger.py` + `tests/test_turns_ledger.py`).

**Salvage 1 — the audit session-id collision.** `master:python/synapse/core/audit.py:186` is verbatim `deterministic_uuid(f"session:{id(self)}:{threading.current_thread().ident}", "session")`. `deterministic_uuid` has no entropy and `id()`/thread idents recycle across process restarts. The branch adds `:{time.time_ns()}`. **Re-type the hunk onto a fresh branch off master; do not cherry-pick the commit.**

**Salvage 2 — the `render_farm_status` read-only classification.** `master:python/synapse/server/handlers.py:233`'s `_READ_ONLY_COMMANDS` frozenset contains `render_farm_cancel` but **not** `render_farm_status`, which is only registered at `:763`. Master's poll exemption at `handlers.py:509-520` is scoped to `cmd_type=="render"` with a poll payload only, and `handlers_render.py:1678` spells out master's own rationale ("a running render holds the C5 mutation lock for its duration") for classifying the three siblings read-only. `render_farm_status` was skipped. **The salvage closes a gap master itself argued for and then missed.**

> **CONTESTED — the verdict's verification gate is fabricated.** The original steps said to run `pytest tests/test_stress.py tests/test_studio_integration.py` because "both read `_current_session`". `git grep -n "_current_session|current_session_id" master -- python tests scripts` yields exactly **three** hits, all in `python/synapse/core/audit.py` (186, 262, 433), and **zero** under `tests/`. A human running that gate would get a vacuous green. **Corrected gate:** the real consumers are `audit.py:262` (session_id stamped on each AuditEntry) and `audit.py:433` (target_session in the verify/filter path), so gate on the **audit hash-chain / session-filter tests**.

Also: the branch's `handlers.py` comment ties `render_farm_status` to `read_ledger.INFRA_READ_COMMANDS`. Salvaging the re-classification without the read ledger is still safe, but **the hand-retyped hunk must drop that sentence** or it cites a module master does not have.

```powershell
git tag archive/feat-scene-model 15843434
git push origin archive/feat-scene-model
git worktree list | Select-String scene-model
git branch -D feat/scene-model
```

**Not checked:** whether the branch's 15-line `audit.py` hunk is only the seed fix + `current_session_id()`; whether any master audit test actually fails under a `time_ns` seed; no test-merge was run, so "claude_worker.py conflicts wholesale" is asserted, not demonstrated.

---

**`wip/panel-goalposts`** — **OVERTURNED from ARCHIVE_DELETE to SPLIT_SALVAGE.**

> **CONTESTED — the load-bearing claim was false for one of three files.** The original verdict said "master shipped all three with different APIs, so these tests pin a June surface that no longer exists." That holds for the Ollama provider (master ships `ollama_provider.py`, `model_discovery.py`, `connection_dialog.py`, `connections.py`, `providers/catalog.py` and `tests/panel/test_ollama_discovery.py`). It is **false** for the hython matrix. `master:.synapse/hytest.py:100` carries only the **singular** pin `os.environ.get("SYNAPSE_HYTHON")` and a single-best-build resolver; there is no `SYNAPSE_HYTHONS`, no per-build aggregation, and `git grep -iE 'SYNAPSE_HYTHONS|build matrix' master` over the entire tree returns **zero hits**. The idea is not superseded and not recorded anywhere else.

**Salvage: `tests/panel/test_hython_matrix.py` (182 lines).** It is not a stale pin — it is a live unimplemented spec, written pure-Python with monkeypatched hython resolution so it runs under stock `pytest -q` with no Houdini. Its subject got *more* relevant since June: this host now has both 22.0.400 and 22.0.429 and the shim picks newest. Salvage the file, or at minimum record the H-MATRIX contract in the backlog, **before** archiving.

Second, smaller break: the cited grep `git grep -li 'model_picker|ModelPicker' master -- python/synapse/panel` returns **nothing** — the two filenames attributed to it are not produced by that command. What master actually has is an engine/provider selector (`python/synapse/panel/synapse_panel.py:1225 _refresh_engine_selector`), which is **not** the same surface as the branch's goalpost (`registry.MODELS` with ≥2 Claude entries including opus + haiku, `build_provider` taking a model key). Whether master's `registry.py` carries a multi-model table is **UNVERIFIED** — that file was never read.

The rest of the evidence is real and was re-run: `git cherry master wip/panel-goalposts` = 2 unapplied (91fe5b1e, c3a60324), diffstat exactly 8 files / +1130/-0, and `test_type_scale_native.py` diverges by exactly +121/-29.

```powershell
git tag archive/wip-panel-goalposts c3a60324
git push origin archive/wip-panel-goalposts          # the original steps omitted this
git worktree list | Select-String goalposts
git branch -D wip/panel-goalposts
```

---

**`rope/gate-a`** — the engineering commit already landed; the documentation half is now factually false.

Evidence: `git cherry master rope/gate-a` → `- e69703a8` (already patch-landed), `+ de254d09`, `+ 3806af20`. BLOCKS **did** ship: master carries `python/synapse/blocks/{__init__,canonical,fixtures,plan,runtime,transport}.py` and `python/synapse/cognitive/tools/apply_fixture.py`. So the branch's own line *"Branch `blocks/m5-reconciler` (`87927076`), not merged"* and the README's *"Not on master yet"* are both false today. Every one of its four files conflicts. **Do not merge it.**

**Salvage 1 — the real gap.** Master's CHANGELOG has zero mention of BLOCKS or `apply_fixture` while the code ships. Use `git show rope/gate-a:CHANGELOG.md | sed -n '1,30p'` as **source material** for a fresh entry: keep the four-silent-failures paragraph and the F-1..F-5 invariant list, re-verify every number, delete "not merged" and the stale suite counts.

> Pin the gap check as **case-sensitive**. `grep -i 'blocks'` on master's CHANGELOG returns 8 hits (solver blocks, thinking blocks, evidence blocks, absent-evidence blocks) with nothing to do with the BLOCKS subsystem. A careless re-run concludes the gap is already closed.

> Re-probe before publishing: the branch text asserts "`mcp_server.py` in fact builds FOUR independent Dispatcher singletons, each `is_testing=True`". That number was not verified and is 794 commits old. **origin is public.**

**Salvage 2 (optional, artist-facing):** rewrite the BLOCKS section for today's 148-line README. Do not port the hunks — the README it targeted no longer exists. Drop the "*Not on master yet*" line.

**Salvage 3 — CORRECTED disposition.** The original verdict said the m5b.md doctrine change was dead archaeology because "m5b's own leg is finished". **`master:harness/legs.json:498` gives the M5b leg `"state": "ready"` — dispatchable, not finished.** So the 2-line `harness/prompts/m5b.md` delta is a **live prompt improvement a future M5b dispatch would read**. Apply the hunk to `master:harness/prompts/m5b.md` directly. It carries more than wording: the branch version records the concrete incident — *"This leg was dispatched once on the WRONG base (2026-08-06, orchestrator manifest base feat/repair-heats-01) and was stopped by hand. The worktree branch blocks/m5b-rulings has since been reset onto 87927076."*

**Drop entirely:** the mermaid theme hunks. Master's README has no mermaid diagrams left.

```powershell
# only after the salvage text is captured somewhere durable
git branch -D rope/gate-a
git worktree prune
```

**Unverified:** whether `blocks/m5-reconciler` and `blocks/m5b-rulings` still exist as refs, and whether harness receipts show M5b ever ran. If M5b *did* run under a different branch name, the `legs.json` "ready" state is itself stale and Salvage 3 changes shape again.

---

## Needs your word

**No verdict in this run carried the literal disposition NEEDS_HUMAN_RULING.** The questions below are the calls the verdicts and the artist-surface passes explicitly referred upward, plus PR #82's roster. Ordered by what unblocks the most.

**Blocks the merge train:**

1. **`mem/m2-pgdrm`: merge a kernel with zero producers and zero consumers, or HOLD on the §2.3 precedent that says the revival bar is a real caller?** — MERGE / HOLD
2. **`fix/cto-render-20260908`: does `houdini_render` stay as a second road alongside the farm?** — STAYS / GOES
3. **`feat/cache-insert`: merge dark with `SYNAPSE_CACHE_ADVISOR_ENABLED` unset, or flip it on?** — DARK / ON
4. **`houdini_layout_network` runs at the INFORM gate** (`bridge_adapter.py:83` maps it to `set_parameter`) while it repositions, recolors and re-boxes an artist's entire network. **Is INFORM the right tier?** — KEEP / RAISE

**Blocks the archive pass:**

5. **`rope/beacon`: retire rc.ps1's force-push in the same pass, or accept the branch as regenerable scratch and skip the origin delete?** (`rc.ps1:49-50` resurrects it; `OPERATOR_CARD.md:115-117` publishes the blob URL) — RETIRE / SKIP
6. **`stray/audit-log-threading`, `repair/h1-schemas-b`, `feat/panel-ux-pass`, `feat/scene-model`, `wip/panel-goalposts`, `bp2/nits` all live on the PUBLIC origin. Push-delete them, or leave the remote refs?** — DELETE / LEAVE
7. **PR #80: close it?** (master shipped the installer in `8c23fccc`; merging regresses the download link) — CLOSE / KEEP

**Blocks the artist scaffold:**

8. **TRUST-1: the consent gate cannot fire in-process** (`shared/bridge.py:2942` hardcodes `consent_callback=lambda op: True`, `:2943` sets `_gate = None`) because re-arming it re-freezes the GUI. **Restamp the docs to say auto-approve-by-construction, or attempt a re-arm?** — RESTAMP / REARM
9. **U1: carve the brakes out of `_DENIED_GATES`** — `synapse_render_stop`, `synapse_render_farm_cancel`, `synapse_emergency_halt`. Starting stays gated; stopping does not. **Approve under the 2026-08-18 DECIDE?** — YES / NO
10. **U2: route a worker denial into the existing approve/reject card** instead of an `is_error` string the artist never sees. The artist becomes the authorizer, so the worker still self-authorizes nothing. **Approve?** — YES / NO
11. **FR-3: what is the first-run pill row?** All five current pills (Explain / Make HDA / Fix Error / Optimize / VEX Help) presume something that already exists, in the scratch scene the quickstart tells the artist to open. — SWAP / KEEP
12. **DEC-4: `harness/state/DECISIONS.md` says 286 open, last written 2026-08-01; the live board says 632. Regenerate on a hook, or delete the file?** — HOOK / DELETE

**PR #82's roster — `harness/design_review/2026-09-14/RULINGS-OPEN.md`, 16 calls.**

Rule in this order. Each is one word.

13. **A1** — head of the chain; gates B2, which gates A2; A3 is a conditional guard on it. — `A1 <word>`
14. **B2** — still a real three-leg fork after A1 lands. — `B2 <leg>`
15. **A2** — falls out of B2 with a number and an owner. — `A2 <number+owner>`
16. **A3** — conditional guard on A1, one word, independent. — `A3 <word>`
17. **A4** — one word, independent, costs nothing. — `A4 <word>`
18. **C5** — one word, independent. — `C5 <word>`
19. **C6** — one word, independent. — `C6 <word>`
20. **C2a** — ship or don't ship the receipt line. *(Requires the split edit at stop 1; as written, "C2 ship" does not say which, and the ambiguous reading is the one the doc prices at -73 to -87px.)* — `C2a <word>`
21. **C2b** — scroll the content or the widget. — `C2b <word>`
22. **C1** — **defer.** Its second leg is not a ruling.
23. **C3** — **defer.** Explicitly depends on C1.

**The remaining roster ids were not enumerated in this run.** Ten of sixteen are named above because the verdict named them; the other six are in the file and their content is UNVERIFIED here. Path: `C:/Users/User/SYNAPSE/harness/design_review/2026-09-14/RULINGS-OPEN.md`.

**And the meta-question underneath all of 13-23:** answering `A1 ratify` on the PR today **changes nothing in the repo**. No ingester exists; `grep -rln "RULINGS-OPEN|rulings-2026"` over `harness/`, `scripts/`, `.claude/workflows/` returns no matches. See DEC-3.

---

## The artist scaffold

### Scaffold the decisions

There is no decision system. There are **four decision stores with zero edges between them**, and exactly one cross-surface reference in the whole tree (`harness/statusline.py:265-268` importing `decisions.py` for a count).

---

**DEC-1 · blocker · M · wire the DecisionLog that was built and never plugged in**

*Feels today:* "I watch it build my network and I never find out why it picked that node over the other one. If I want to know why it reached for Dark_Glass instead of Diamond, I have to ask it again and hope it remembers."

*Build:* Instantiate one `DecisionLog` on the panel worker, call `record(tool_name, tool_input, reasoning)` on every tool dispatch, feed `credit_rows()` into `FaceReview.set_credit` at turn end. Then make the rows survive the turn — append each cycle to a plaintext per-scene log.

*Evidence it is dead:* `grep -rn "DecisionLog(" --include=*.py python/` → **no matches**. `decision_log.py:252` `self._rows = []`, `:257` `begin_cycle` clears. No path, no `open()`, no `write_text`. Its own docstring says it was built because the credit grid "had zero product callers".

*First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/decision_log.py`

---

**DEC-2 · blocker · L · one board, one key, one word**

*Feels today:* "I answered that already. I told it in the panel, and the board still shows it open."

*Build:* `harness/decisions.py` already has both halves — `item_key()` at `:89` mints a stable id from `(kind|source|leg|text)`, and `resolved.json` + `resolve()` at `:102`/`:299` retire by that id. Teach `collect()` (`:161`) a **third source**: a `harness/state/rulings/` directory of markdown rosters with an id per item. Then PR #82's A1..C6 land on the same 632-item board with the same keys, and `--resolve A1 --reason ratify` closes a design ruling the way it closes a receipt ruling.

*First file:* `C:/Users/User/SYNAPSE/harness/decisions.py`

---

**DEC-3 · major · M · give the 16 rulings a landing zone**

*Feels today:* "I ruled on it. Weeks later somebody asks me the same question again, because my answer is sitting in a GitHub comment thread."

*Build:* Make the answer the artefact, not the comment. Machine-readable id line per roster item, plus `decisions.py --rule A1 ratify` that appends to `resolved.json` with the word and a sha **and** stamps the roster file in place.

*First file:* `C:/Users/User/SYNAPSE/harness/decisions.py`

---

**DEC-5 · major · S · the decision log is encrypted**

*Feels today:* "I open `.synapse/decisions.md` and it is a wall of base64. I cannot read my own project's decision history without going back through the tool that wrote it."

*Build:* Default the decision log to plaintext markdown; keep encryption opt-in for anything carrying scene paths or client names. If it must stay encrypted, ship `synapse decisions --show` and surface it in the panel — one door.

*Evidence:* `tests/fixtures/.synapse/decisions.md` opens `SYNAPSE_ENC_V1:gAAAAABp5TEWc025...`; `markdown.py:327-345` reads via `crypto.decrypt_file_content` and writes back encrypted.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/memory/markdown.py`

---

**DEC-4 · major · S · the durable record is 45 days and 346 items behind.** `harness/state/DECISIONS.md:5` says "286 open"; `python harness/decisions.py --count` prints **632**. Last commit `54c9d291`, 2026-08-01. Nothing regenerates it. Hook it or delete it; a derived file nobody derives reads as current. *First file:* `C:/Users/User/SYNAPSE/harness/state/DECISIONS.md`

**DEC-6 · minor · S · the aging gate cannot fire from where the number is shown.** `statusline.py:260-268` calls `collect(with_ages=False)` to stay subprocess-free, then renders `YEL` unconditionally at `:354-355`. `decisions.py:35-40` calls the 30-day gate "the whole point". Cache the age pass on write; let the segment change colour. *First file:* `C:/Users/User/SYNAPSE/harness/statusline.py`

**DEC-7 · minor · M · there is no tool for recording that a HUMAN ruled.** `tracker.py:508` stamps every `synapse_decide` entry `tags + ["ai_decision"]`. The only human channel is `decisions.py --resolve` — CLI-only, keyed to items the panel does not contain. Add the symmetric half once DEC-2 lands. *First file:* `C:/Users/User/SYNAPSE/python/synapse/session/tracker.py`

---

### Scaffold the utility

**The partition, measured.** 128 tools registered. The panel worker sees TOOL_DEFS + 6 group tools, filtered at call time by `worker_policy`. Ran headless with `SYNAPSE_WORKER_TOOL_MODE` unset → `resolve_mode() == "standard"` → **ALLOWED 92 / DENIED 36**. Everything below is conditional on that default mode.

---

**U1 · blocker · S · the panel cannot render, and cannot stop a render**

*Feels today:* "I typed 'render frame 1001 and show me' and it talked me through what it would do instead of doing it. Then when a render was already grinding I asked it to stop and it couldn't do that either."

*Build:* Split the deny set **by direction**. Starting stays gated; **stopping should not be.** Carve `synapse_render_stop`, `synapse_render_farm_cancel` and `synapse_emergency_halt` into an explicit `_WORKER_BRAKE_ALLOWLIST` beside the existing `_WORKER_BUILDER_ALLOWLIST` (`worker_policy.py:81`), with the same one-paragraph L4 rationale.

*Evidence:* `worker_policy.py:63` `_DENIED_GATES = frozenset({"review","approve","critical"})`. The denied 36 includes every render tool **and** the three brakes, while `synapse_render_farm_status`, `synapse_render_processes` and `synapse_live_metrics` stay allowed — the artist can watch a render they cannot start and cannot kill. That combines badly with the known render-blocks-the-main-thread freeze class, where the remaining recovery is killing Houdini.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/worker_policy.py`

---

**U2 · blocker · M · a denied tool dead-ends in chat; the approve card that exists is wired to a different path**

*Feels today:* "It never asks me. It just quietly does something smaller than what I asked for and tells me about it afterwards. I'd have said yes."

*Build:* One new signal on `ClaudeWorker` (`gate_proposal_requested`) carrying `(tool_name, args, reason)`; `chat_panel` routes it into the same `_gate_widget.handle_ws_proposal` path already wired at `chat_panel.py:219`. Approve dispatches the held call; reject returns today's `denial_tool_result`.

*Evidence:* `worker_policy.py:234-248` returns `is_error=True` with *"Choose a different, lower-privilege approach"* — that string goes to the **LLM**, not to the artist, and the LLM's designed response is to substitute a weaker plan. Meanwhile `gate_widget.py:196-198` already has working `approve_clicked` / `reject_clicked` / `revert_requested`, and `chat_panel.py:219` connects the **bridge's** proposal stream to it — not the worker's.

*This honors the 2026-08-18 DECIDE rather than fighting it.* An approve card does not let the worker self-authorize; it makes the artist the authorizer, which is what the ruling protected. No mode flip, no widening of `_DENIED_GATES`.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/claude_worker.py`

---

**FR-1 · blocker · M · a message typed while the bridge is down is silently queued, spins forever, then fires later**

*Feels today:* "I typed 'make a box' and the three dots just kept going. Nothing came back, so I typed it again. And again. I went to get coffee, and when I came back there were four boxes in my scene that I didn't ask for right then."

*Build:* Two decisions. (1) Make the send guard read the **socket**, not the object — `chat_panel.py:848` checks `if self._bridge is not None:` where it needs `self._bridge.connected`; the only "Not connected" message (`:867-869`) is reachable **only** when no bridge object was ever built. (2) Decide what a queued message means: drop the queue for `route_chat` entirely, or make it a visible cancellable pending item and **ask before replaying** on reconnect. Put a wall-clock ceiling on the typing indicator.

*Evidence:* `ws_bridge.py:409-417` — `send_command` finds `self._ws is None` and falls through to `self._send_queue.append(msg_json)` with no return value, no signal, no error. `ws_bridge.py:346-357` — `_drain_queue()` replays everything on the next successful connect. `_waiting_for_response` is set at `chat_panel.py:860` and cleared **only** in `_on_response` (`:875-876`).

*First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/chat_panel.py`

---

**TRUST-1 · blocker · M · consent gates are documented, coded, and unreachable**

*Feels today:* "It deleted the node. It never asked me. The docs say delete is a REVIEW gate and render is APPROVE — I was counting on that."

*Build:* **Do not naively re-arm HumanGate** — the deadlock reason at `bridge_adapter.py:189-205` is legitimate and confirmed live ("make a box" → execute_python froze the GUI). Instead: (a) one panel-header line stating the running posture in artist words, **sourced from the live bridge's actual `_consent_callback`/`_gate` state**, not a constant; (b) correct CLAUDE.md §1.1 / §1.2.1 / §11 rule 5 to say consent is auto-approve by construction in-process; (c) fix the self-contradiction inside `bridge_adapter.py` — `:202-203` claims "HumanGate still governs AUTONOMOUS / MCP operations, which use their own bridge instances" while `get_bridge()`'s docstring twelve lines below says all three surfaces "write ONE operation trail".

*Evidence:* `shared/bridge.py:2937-2945` — `LosslessExecutionBridge(consent_callback=lambda op: True)` then `bridge._gate = None`. `bridge_adapter.py:208-231` — `get_bridge()` reuses that singleton and re-pins both. `mcp/tools.py:118-124` — the MCP dispatch path calls the same adapter.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/bridge_adapter.py`

---

**TRUST-2 · blocker · S · the product never tells the artist what a given action can undo**

*Feels today:* "I save-as before every prompt, because I have no idea whether one Ctrl+Z gets my scene back or whether I'm about to spend ten minutes picking apart a half-built network."

*Build:* **The Undo Receipt.** One helper in `server/handler_helpers.py` that both opens the group and records it, attached to every mutating response:

```
undo: { label: "synapse_node_create", steps: 1, rolls_back_on_failure: false }
```

The panel prints one dim line under each result: *Undoable — 1 step: "synapse_node_create"* or *Undoable — 1 step, but a failure leaves partial work behind.*

*Evidence:* `grep -rn "Ctrl\+Z|one undo|undoable|can be undone|cannot be undone" --include=*.py` over the whole repo → **0 matches**. ~35 `hou.undos.group("<label>")` call sites across `python/synapse/server/` — `handlers_node.py:66,144,174`; `handlers.py:1013,1141,1144,1170,1295`; `handlers_cops.py` (16 sites); `handlers_usd.py:428,542,623,696,809,1132`. The label is the exact truthful answer and it is discarded at every one.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/server/handler_helpers.py`

---

**TRUST-4 · major · M · failure cleanup is a coin flip the artist cannot call**

*Feels today:* "Last time a build failed it cleaned itself up. This time it left eight half-wired LOPs in my stage. Same panel, same kind of request."

*Build:* This is the `rolls_back_on_failure` field of TRUST-2 — same one-line change. It is a **static** property of each code path, not a runtime decision. Ship the disclosure first; converging the handlers on one contract is a separate, larger job that should not block the artist knowing which one they have.

*Evidence — three populations:* **Rolls back** — `handlers_solaris_graph.py:834-841`, `handlers_solaris_compose.py:89,127`, `handlers_cops.py` (9 sites: 379,454,885,1149,1321,1445,1686,1801,1890), `handlers_hda.py:592`, `handlers_render.py:2028`, `handlers.py:1305-1310`. **Group only** — `handlers_node.py:66,144,174`, `handlers_usd.py:428,542,623,696,809`, `handlers_material.py:232,311,503`, `handlers.py:1141,1144,1170` and `:1013`, `handlers_render.py:1168`. **Third category** — `execute_python` at `handlers.py:1281-1310` rolls back coding bugs (`_ROLLBACK_ERRORS`) and **deliberately keeps** mutations on operational errors like a render timeout.

*First file:* `C:/Users/User/SYNAPSE/python/synapse/server/handlers_node.py`

---

**TRUST-5 · major · S · "failed Solaris builds orphan partial networks" is no longer true**

*Feels today:* "I was told SYNAPSE leaves junk behind when a Solaris build fails, so I clean up by hand every time. Turns out it already undid it — I've been deleting nodes that weren't there."

*Build:* Re-stamp the CLAUDE.md §Identity parenthetical and the project-memory entry, and state the **residual** honestly: build_graph and the Solaris compose handlers roll back **one** undo step on failure; a failure that produced more than one step leaves the rest. Then close the residual with a live probe — force a mid-build exception under a pinned hython and count the `undoLabels()` delta.

*Evidence:* `handlers_solaris_graph.py:669-673` snapshots `areEnabled()` / `undoLabels()` before the group; `:829-841` calls `performUndo()` on the exception path iff the label stack moved, with the comment *"Catch and explicitly undo to prevent undo stack corruption"*. `handlers_solaris_compose.py:89,127` does the same for `solaris_shotsetup_karma_xpu` and `matlib_bind`. CLAUDE.md still carries `(VERIFIED-RUNTIME, L2 2026-07-25: failed Solaris builds orphan partial networks; the undo group does not clean up)`.

*First file:* `C:/Users/User/SYNAPSE/CLAUDE.md`

---

**TRUST-6 · major · M · preview-before-commit is built and offered on 2 of 15 handler modules.** `handlers_solaris_graph.py:653-667` already returns a full `status: "preview"` payload — `nodes_created`, `nodes_reused`, `connections_made`, `merge_points`, `ambiguous_merges`, `warnings`, `display_node`. `dry_run` grep count: `handlers.py` 7 (compile-only, no scene impact), `handlers_solaris_assemble.py` 9, `handlers_solaris_graph.py` 8, **all 12 other modules: 0**. Surface a **Preview** verb on the two that already work, then extend the same contract to create_node / connect_nodes / delete_node / set_parm. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/tool_palette.py`

**TRUST-3 · major · S · the REVERT button is a global one-step undo wearing an operation's name.** `gate_widget.py:258` renders `← REVERT`; `tests/panel/test_consent_way_back.py:245-262` pins what it does — sends `houdini_undo`, which is `hou.undos.performUndo()`, *"one global step, no target — so this does NOT scope the undo"*. Either rename it `← UNDO LAST`, or compare the top undo label against TRUST-2's recorded label and refuse when they differ. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/gate_widget.py`

**TRUST-7 · minor · S · the integrity readout reports "undo: not applicable" on ops that are demonstrably undo-wrapped.** `integrity_envelope.py:20-32` records `undo_applicable=False` because verifying it per-op needs `hou.undos` members absent from the symbol table. Honest, but a false negative on every mutating op. Split the field: keep `undo_verified=False`, add `undo_declared=<label>` — a static fact the handler knows for certain. Re-stamp the docstring's "grouping only, not rollback" sentence while in the file. *First file:* `C:/Users/User/SYNAPSE/python/synapse/server/integrity_envelope.py`

**U4 · major · S · every one-call shot setup is denied while its ingredients are allowed.** `worker_policy.py:68-84` exempts exactly two composites and its own rationale is decisive — the composites are *"ONE undo-wrapped call composed entirely of inform-level primitives"* that collapse *"a 25-turn imperative build (which hit the iteration cap without finishing)"* into one turn. The same argument applies verbatim to `synapse_solaris_shotsetup_karma_xpu`, `scene_template`, `component_builder`, `create_variants`, `set_purpose`, `import_megascans`, `synapse_matlib_bind`, `houdini_shot_render_ready` — all still denied. Audit the eight against the exemption's own stated test; disk-writers go to U2's card. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/worker_policy.py`

**U6 · major · S · the panel worker has no phantom guard.** `synapse_scout` — CLAUDE.md §11 rule 15's front-line defense against SYNAPSE's #1 failure class — is defined at `cognitive/tools/scout.py:1101`, is **not** in TOOL_DEFS, and is **not** in `tool_bridge.py:20-27`'s `_GROUP_MODULE_MAP`. `_build_cache` (`:50-62`) iterates TOOL_DEFS then `_GROUP_TOOLS` and nothing else. It is pure-Python, zero-`hou`, read-only — inform-level by construction, needs no gate change. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/tool_bridge.py`

**U5 · major · L · "make the light brighter" needs a name no human can type, and the doc says so while pointing at a phantom.** `docs/MCP_TOOL_CATALOG.md`'s `houdini_set_parm` row: *"parameter names are encoded (e.g. `xn__inputsintensity_i0a` not `intensity`). Use `houdini_inspect_node` first."* **`houdini_inspect_node` is not a registered tool** — the registry has `synapse_inspect_node`. And the hand-maintained `xn__` map is majority phantom. Build a live-probing plain-name resolver; fix the phantom pointer as a one-word edit. *First file:* `C:/Users/User/SYNAPSE/docs/MCP_TOOL_CATALOG.md`

**FR-2 · major · S · the panel says "Ready." before it has connected or been given a model.** `chat_panel.py:242-245` appends it unconditionally inside `createInterface`, before `onActivateInterface` (`:250-256`) runs `_ensure_server()` — while the chip two rows up correctly reads "Disconnected" in red (`:613-622`). Two contradictory claims in the same pane in the same frame, and the conversational one is the one they read. Make the greeting a function of state: no model / model-but-no-bridge / both live. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/chat_panel.py`

**FR-5 · major · S · connection failure prints three raw exception lines, then goes permanently silent while still failing.** `ws_bridge.py:222-233` emits `"Couldn't connect ({n}/3): {e}"` where `e` falls back to `type(exc).__name__`, gated on `if attempts <= 3`; `:238-240` keeps retrying every 5s saying nothing. `chat_panel.py:925-927` pipes it verbatim into chat — while `error_translator.py` sits in the same package. Silence after three complaints reads as resolution. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/ws_bridge.py`

**FR-3 · major · M · every quick-action pill is a dead end in the scene the quickstart tells you to open.** `quick_actions.py:12-63` ships five pills, all presuming something that already exists; `docs/getting-started/quickstart.md:5-6` says "Use a scratch scene for the first run"; `README.md:34` gives the correct first move — `make a box` — which appears nowhere in the panel. Swap in build-from-nothing starters on an empty network. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/quick_actions.py`

**FR-4 · major · M · configured and never-configured look identical at rest.** The header has a dot for the Houdini bridge (`chat_panel.py:613-640`) and none for the model; `health_strip.py:273 build_cells` covers connection / memory / project / job only. Give the model the same honest chip using the existing verdict vocabulary — UNKNOWN when nothing is chosen, per `health_strip.py:194-206`'s own rule, *"never green from absence."* *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/health_strip.py`

**U3 · major · S · the "Make HDA" button names a tool the panel cannot run.** `quick_actions.py:24-31` — prompt is literally *"Package the selected subnet into an HDA…"*; `houdini_hda_create`/`promote_parm`/`set_help` are allowed, `houdini_hda_package` is in the denied 36. It is one of three buttons on the primary clickable surface. Add a test in the shape of `test_activity_labels.py::test_every_curated_key_is_a_live_tool` asserting every verb a QUICK_ACTION names is permitted under default mode. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/quick_actions.py`

**U7 · minor · M · 120 of 128 labels are transliterated tool ids.** `b475ee22` is a genuine repair — it stopped `.capitalize()` destroying domain words and pinned the map. `activity.py:1-13` is honest that *"the derivation below is the label for the other ~120 tools"*, and `:45-55` has exactly 8 curated sentences. Traced by hand: `tops_dirty_node` → "Dirty node", `synapse_sleep_pass` → "Sleep pass", `synapse_matlib_bind` → "Material library bind". Legible English, zero intention. Extend `_TOOLS` by **frequency**, not alphabet — the ~25 that fire in a normal session. *First file:* `C:/Users/User/SYNAPSE/python/synapse/panel/activity.py`

**U8 · minor · S · the only tool catalog in docs/ is wrong by two generations and says so about itself.** `docs/MCP_TOOL_CATALOG.md:1-2` — *"ARCHIVED SNAPSHOT — v5.6.0-era (80 tools)"*, then a correction line that is itself stale: *"Current truth: 115 registry tools, v5.22.0."* The registry has 128. Regenerate from TOOL_DEFS at release time and add the count to `scripts/sync_version.py`'s propagation set, so it is a produced number like every other number in README (Law 2). Generate **two columns** — registered, and reachable from the panel under default mode. *First file:* `C:/Users/User/SYNAPSE/docs/MCP_TOOL_CATALOG.md`

---

### The highest-leverage item

**Ship TRUST-2, the Undo Receipt.**

It is **S** effort. Every mutating handler already computes the exact answer — `hou.undos.group("synapse_node_create")`, `hou.undos.group("SYNAPSE: build_graph")` — and discards it. One helper in `server/handler_helpers.py` turns ~35 existing strings into the guarantee statement the product has never made.

**Why it beats the others:**

- It **carries three more findings at no extra cost.** `rolls_back_on_failure` closes TRUST-4's disclosure (a static property, no runtime inference). The recorded label is what lets TRUST-3 refuse a mis-targeted REVERT. It is TRUST-7's `undo_declared` field verbatim.
- It **does not touch the deadlock.** No new gate, no new thread, no HumanGate re-arming. TRUST-1 is the more severe finding, but the reason the gate is off is a confirmed live GUI freeze, and re-arming it naively re-freezes Houdini — which is the failure that costs an artist the most trust of all.
- It **needs no ruling first.** U2 waits on question 10, U1 on question 9, DEC-1 is M-effort and only helps the artist understand the *agent's* choices. TRUST-2 answers the question the artist is actually asking before every prompt: *if this goes wrong, do I get my scene back.*
- The measurement is unambiguous: **zero** artist-facing undo strings exist in the entire codebase today.

Do **TRUST-5** in the same pass — a two-line documentation correction that is actively making the team distrust a behaviour that was already fixed.

**One thing precedes the ranking, because it is not a scaffold.** FR-1 is a defect that silently changes the artist's scene: a message typed while the bridge is down is accepted, spun on, queued with no signal, and replayed into whatever scene is open twenty minutes later. Fix the send guard regardless of what else gets built this week.

---

## What this run did not check

**Structural, and true of every finding above.**

Nothing ran inside Houdini. No `hython`, no live bridge, no panel launch, no probe, no screenshot. No test suite was executed by any agent in this run — **the 8869 / 412 / 0 floor is inherited from `harness/notes/v2-waves-2026-09-14/suite-floor-bd65e4b6.txt`, not measured here.** No branch was rebased, so every conflict count comes from `git merge-tree`, not from a completed rebase. **A green read of a `try/except: performUndo()` block does not prove it reverses anything in a real session.**

**Merge train.**

- `design/rulings-2026-09-14`: no suite run (docs-only by construction, not by measurement). Branch protection / CODEOWNERS on `harness/` paths not queried. **None of the doc's 16 measurements were verified** — the -73 to -87px widget figure, the D1 400px faces-stack red "at every density", the D3 "3/3 profiles" reproduction, and the `gate_widget.py:360 _show_decision_tag('NOT RECORDED')` collision are all UNVERIFIED. A green merge puts them on one surface; it does not make them true.
- `fix/demo-repairs-20260909`: the four modified test files were not read line-by-line. The layout contract (undo grouping, artist-box refusal) is `hou`-side and unproven.
- `feat/cache-insert`: the 510-line `handlers_cache.py` body, the 5-line `rbac.py` drift, and the assay receipt were not read. Whether insert_cache's **live** dispatch consults `OPERATION_GATES` at all was not verified by either pass. No tests were run.
- `mem/m2-pgdrm`: `m2fix_suite_branch.txt` has a Sep 5 mtime for an Aug 22 run — treat its `6856 passed` as UNVERIFIED. The floor comparison in the steps is apples-to-oranges until the interpreter is pinned.
- `fix/cto-render-20260908`: rebase completion, post-rebase suite state, the handlers_render-untouched claim past the name-only diff, exact RBAC level assignments, real 22.0.429 behaviour, and whether root-level `mcp_tools_render.py` pre-exists on master — all unchecked. Whether ~1,700 lines of farm tests still import after 81 commits of drift is unknown.

**Archive list.**

- The five patch-landed branches: no remote refs were queried.
- `feat/panel-ux-pass`: **no test-merge was run by either pass**, so the `qss.py` +15 DsConnPill rule was never checked against master's `qss.py` and no conflict count exists.
- `repair/ledger-moneta-seam`: whether `tests/test_ledger_moneta_seam.py` is **collected and green** on master — byte-identity proven, execution not.
- `repair/h1-schemas-b`: `H1.json` differs by 225/297 lines and **neither receipt was read**.
- `rope/beacon`: whether `STATE.json`'s `log` array already replicates the 10 telemetry rows; whether any scheduled task still arms `rc.ps1`; whether `rope/gate-a` depends on the beacon beyond `STATE.json` naming it.
- `stray/audit-log-threading`: whether the 6-line hunk still applies at 919 behind; whether `tests/test_state_digest.py` passes on master; whether the 178-line scope doc records anything not already in `CTO_RULINGS_03.md`.
- `feat/scene-model`: whether the 15-line `audit.py` hunk is only the seed fix; whether any master audit test fails under a `time_ns` seed; the "claude_worker.py conflicts wholesale" claim is asserted, not demonstrated.
- `wip/panel-goalposts`: whether master's `providers/registry.py` carries a multi-model table — **registry.py was never read**.
- `rope/gate-a`: whether `blocks/m5-reconciler` and `blocks/m5b-rulings` still exist as refs; whether harness receipts show M5b ever ran; the "FOUR Dispatcher singletons" figure is 794 commits old and unverified.

**Decisions lens.**

Whether `decisions.py --count` exits 6 today on an over-age item — the output was piped through `tail`, so the read `$?` was tail's. The 632 count is real; the gate's live behaviour is not established. Whether the panel credit grid has any **other** live producer — `decision_log.py:46-48` names `synapse_panel::_turn_evidence` via `verdict.decision_from_tool_evidence`, unchecked; if it is live, DEC-1 softens from blocker toward major. Whether `.synapse/decisions.md` is encrypted **in production** or only in the committed fixture — a key-absent plaintext fallback may exist. Whether merging PR #82 changes any code path — the diff was not read. The `synapse_decide → tracker → markdown` chain is traced by reading call sites only; the composed path was not executed. The statusline number was not read from the statusline. **The 21 off-master branches were not audited for a decisions-surface change already in flight.**

**Artist-utility lens.**

The allow/deny partition ran with `SYNAPSE_WORKER_TOOL_MODE` **unset**. If Joe's Houdini environment sets it (or `SYNAPSE_WORKER_TOOL_PROFILE`) to `unrestricted`, the deny list is empty and **U1, U3 and U4 do not fire**. His live environment was not checked. The partition ran under Python 3.14 outside Houdini with an ABI-mismatch warning and was not re-run under Houdini's 3.13. It was **not verified that a worker denial has no path to gate_widget** — the grep for "proposal" found only the bridge stream; an indirect path could exist. `MCP_TOOL_CATALOG.md`'s per-tool RO/MUT/IDEM annotations may not match current registry flags; no live UsdLux node was re-probed. The six `synapse_group_*` knowledge strings were not read, so the LOOK-UP path's usefulness is unknown. Whether the panel's own Scene Doctor still works while `synapse_doctor` is denied was not checked — if it does, FIX is in better shape than rated. Whether the `/mcp` path completes a render end to end was not tested. The U7 label derivations were traced by hand, not executed.

**First-run lens.**

`_ensure_server()` was read only to ~`chat_panel.py:284`, so a fresh install's auto-start behaviour is unknown — FR-1's bridge-down window may be narrower or wider than implied. `doctor_dialog.py` was never opened; FR-4 and FR-5's scaffolds assume Doctor does not surface model state in the resting view, which is a different claim from "the information does not exist". `connection_dialog.py` was not checked for whether it blocks sends until a model is chosen, which would partially mitigate FR-4. **No search was made for tests pinning the send guard or the drain-queue replay** — they may be deliberate and test-locked. Only the *existence* of `harness/notes/release-5.70.0/` artefacts was confirmed; none of their contents were read, so no claim is made about what the installer verifies. `harness/finesse-20260906/` was not read beyond its file listing — the finesse pass may already address FR-2 or FR-3 on an unmerged branch. **The five open commits touching panel files were not diffed against these findings; one of the 16 branches may already fix FR-1.**

**Trust lens.**

Whether GateWidget cards are ever actually **raised** on the `/mcp` path — the widget's construction and REVERT wiring were read, not its call sites. The "group only, no rollback" half of TRUST-4 is **partial**: the `undos` grep over `python/synapse/server` truncated at 70 results, ending mid-way through `handlers_usd.py:1132`. `handlers_node.py` and `handlers_material.py` are whole-file solid; **`handlers_usd.py` may contain `performUndo` calls past that line that were not seen.** Whether an **out-of-process** MCP server (stdio, separate interpreter) constructs its own bridge with gates armed — the in-process path is verified; no such construction was found, but the search was not exhaustive. **`tests/test_phase0b_consent_posture.py` was never opened**, despite CLAUDE.md citing it three times as the proof of the consent posture. How `unrestricted` / `demo` / `proposal` modes resolve, and whether any is reachable by default, was not read. The `_ROLLBACK_ERRORS` tuple contents were read from a comment, not the definition. Whether `handlers_solaris_graph.py:838`'s single `performUndo()` is **sufficient** — whether a failed build_graph produces exactly one undo entry — is unmeasured and is the residual TRUST-5 names. Panel display wiring: zero artist-facing undo strings is proven, but `chat_display.py` and `activity.py` were not read, so TRUST-2's S estimate covers the handler side with confidence and the panel side by inference.