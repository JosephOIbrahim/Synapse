## What / why

Salvage 1 of `rope/gate-a` per `harness/notes/closeout-2026-09-15/PLAN.md` (verdict SPLIT_SALVAGE). The branch's engineering commit (e69703a8) already patch-landed on master; its docs asserted "not merged" about code shipped since v5.43.0. This commit is documentation only, written fresh against the v5.70.1 tree:

- `CHANGELOG.md` (+20): "Unreleased - backfill: BLOCKS" entry -- the setup problem, the M5 engine (`synapse_apply_fixture` / `synapse_remove_fixture`), invariants F-1..F-7, the four silent failures the harness caught, seam drift re-verified at v5.70.1 (four Dispatcher singletons in `mcp_server.py`), the four closed M5b rulings, and what was not re-checked (marked in the entry).
- `README.md` (+1): one "What's ready" bullet naming `synapse_apply_fixture`. No tool-count change.
- `harness/prompts/base.md` (+10): the m5b.md "wrong base means halt, not self-repair" doctrine carried into the BASE leg brief.

## Repair round (refuter blocker, closed)

The first cut `99da35bd` (parent d8ebb74a) also carried an identical-blob add of `harness/design_review/2026-09-14/RULINGS-OPEN.md` (blob 6b01912f = master's 329bd5b3) -- out of scope and a latent add/add conflict. Fix applied as the refuter prescribed: `git rebase master`. A prior pass had rebased onto 329bd5b3 (5773ad0a); this pass rebased onto current master `841f742e` and amended only the message (`git commit --amend -F msg.txt`) to record the real base.

Proof:
- `git show --stat HEAD` -> 7a81a7f1 parent=841f742e; CHANGELOG.md +20, README.md +1, harness/prompts/base.md +10; **3 files, 31 insertions**. RULINGS-OPEN.md absent.
- `git log master..HEAD --oneline` -> exactly one commit.
- `git diff --stat master..HEAD` -> same 3 files / 31 insertions (no phantom deletions now that the base is master's tip).
- `git merge-tree --write-tree master HEAD` -> dc01f6a0, rc=0.

Optional wording nit also closed: the CHANGELOG entry's gap-check now reads `git grep -nE '\bBLOCKS\b|apply_fixture' 329bd5b3 -- CHANGELOG.md` (pinned to the v5.70.1 tree). Verified: rc=1, no hits on 329bd5b3; 6 hits on HEAD (the entry itself).

## Evidence

- `python -m pytest tests/test_phase0c_doc1_toolcount.py -q` -> 28 passed.
- `python -m pytest tests/test_blocks_reconciler.py tests/test_phase0c_doc1_version_conformance.py tests/test_reach_public_agreement.py -q` -> 95 passed.
- `python -c "from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"` -> 128; CLAUDE.md:3 and README.md:129 both say 128.
- `git merge-tree --write-tree master 99da35bd` -> cbac546b, rc=0 (the refuted commit; recorded for the ledger, superseded).

## Ruling the human must give

None. Push + merge is the human's call (no push, tag, or PR opened from here).

## Not checked

- Full `pytest tests/` and the hython seat suite were not run (by law; parent/CI run them serially).
- Tests ran at fc6f0966 (post-rebase, pre-amend). The amend changed only the commit message; `git show --stat` is byte-identical between fc6f0966 and 7a81a7f1.
- `TOOL_DEFS` imported through the editable install rooted at `C:\Users\User\Synapse` (the ABI warning names that path), not the worktree copy. `_tool_registry.py` is untouched on this branch, so the count is the same file; the pinning test ran inside the worktree.
- Sibling worktree `wf_4ef50c87-4e2-6` also lists `salvage/rope-gate-a`; its working files now trail the moved ref (the sandbox refused `git -C` into it). Nothing should be committed from that worktree without refreshing it first.
- The CHANGELOG entry's own "not re-verified" items (SD-2 main-thread seam, the autoresearch dead-literal findings, M6 phrase routing) stay marked unverified in the entry; this pass did not re-probe them.

🤖 Generated with [Claude Code](https://claude.com/claude-code)