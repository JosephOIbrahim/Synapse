## What / why

Repair round for `rebase/cache-insert` against the refuter's four findings. One commit, `d5ad587f`, rebased onto **current** master `841f742e` (the task text said `329bd5b3`; master had moved one docs commit further, and rebasing onto `329bd5b3` alone would have re-created a spurious deletion of `harness/notes/release-5.70.1/*` in `git diff master..HEAD`, so the branch sits on `841f742e`; `git merge-base master HEAD` = `841f742e`, diff lists only the branch's own 11 files).

Honesty note on provenance: when I checked the branch out, this worktree already held **uncommitted** edits from an earlier repair pass that had rebased onto `329bd5b3` and re-run the assay but never committed. I verified each edit against the blocker list below, rebased onto current master, **re-ran the assay on the rebased tree**, and committed. Nothing was taken on trust from that pass; every claim below was re-measured.

### Blocker 1 - PATH LEAK in the committed receipt
- `tests/assay_h22_cache_insert.py` item 5 now records `parm("file").rawValue()` (`$HIP/cache/src_box/src_box.$F4.bgeo.sc`), `cache_dir_basename='src_box'` and `cache_dir_exists=False`. The `$HIP`-expanded absolute path is computed only for the on-disk `isdir` check and never written (see the docstring "Receipt hygiene" paragraph).
- Receipt item 5 detail on disk and in the committed blob: `file_raw='$HIP/cache/src_box/src_box.$F4.bgeo.sc' cache_dir_basename='src_box' cache_dir_exists=False ...`. Mandated `/Users/` scan: 0 hits in the blob; 0 hits in any added line of the full diff.
- Receipt now carries a `certifies` block: `assay_script_sha256` and `handlers_cache_sha256` (both verified equal to the committed files) plus `git_head_at_run = 255d61fb`. That SHA is the rebased commit the assay ran on; the amend that ships the receipt necessarily post-dates the run (a receipt cannot carry the SHA of the commit it ships in), so the content hashes are the load-bearing certification. `255d61fb` is the immediate pre-amend parent state of `d5ad587f` (identical tree except the receipt file), reachable via this worktree's reflog.

### Blocker 2 - Rebase
Done onto `841f742e` (see above). Conflict-free (`git rebase master`: "Successfully rebased").

### Blocker 3 - Failure path (PLAN Stop 3)
Assay items 7-8 added. A `_Delegate` wrapper chain (`_FaultAfterCreate -> _FaultParent -> _RaiseOnSetInput`) keeps the REAL insert core, REAL source node, REAL `hou.undos.group` and a REAL `createNode`, and makes the very next call after creation (`setInput`) raise inside the group.
- Item 7 (pass): `raised='RuntimeError: assay-injected failure...'`; partial network SURVIVED: one unwired `filecache::2.0` (`src_box_cache`), downstream still wired to the source; undo depth 4->5 - the group closed, nothing unwound. Grouping is not rollback, now measured.
- Item 8 (pass): one `performUndo()` removed `['src_box_cache']`; children back to the pre-failure set; downstream wiring unchanged. Recorded as "the artist must undo it deliberately", not as automatic rollback.
- Fail/not_run branches are real: item 7 fails if the fault does not fire or the scene is not the expected partial state; item 8 stays `not_run` if 7 did not raise.

### Nit - `shared/bridge.py:767`
Verified live: the REVIEW default is `shared/bridge.py:768-769` (`def gate_level` / `OPERATION_GATES.get(self.operation_type, GateLevel.REVIEW)`), so the cited `:767` was already off by one. Both comments (`bridge_adapter.py`, `test_cache_insert_gates.py`) now cite `Operation.gate_level` by name, no line number.

## Evidence
See `tests_run`: builder suite 89 passed; refuter suite 251 passed / 1 skipped; registry count 129 matches CLAUDE.md:3 and README.md:128 and the pinning test passes; hython assay 8/8 pass on the rebased tree; leak scans clean on the working file, the committed blob, and every added diff line; sha256 of both certified files match the receipt; full 1732-line `git diff master..HEAD` read end to end.

## Ruling the human may want to give
The receipt's `command` field carries the Houdini **install** path (`C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe`, via `sys.executable`). It is not a user path, does not match the mandated `/Users/` pattern, and is byte-for-byte the convention of the sibling `cache_h22_contract_assay` receipt (`tests/assay_h22_cache_contract.py:464,488`). Left as-is for consistency; say the word and I strip it to the basename.

## NOT checked
- Full `pytest tests/` and the hython seat suite (forbidden in this round; parent/CI run them serially).
- CI on this branch.
- `git range-diff` output beyond its first 40 lines.
- `git_head_at_run` (`255d61fb`) is resolvable only through this worktree's reflog; the content hashes are what a reviewer should re-verify (`sha256` of the two files vs `certifies`).
- No push, no tag, no PR opened (per LAWS).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## CTO ruling (pre-approved 2026-09-15; overrule by comment)

**KEEP the Houdini install path in the receipt's `command` field.** It is `sys.executable` under `C:\Program Files\Side Effects Software\...`, not a user path; it passes the `/Users/` scan; and the sibling contract-assay receipt already records the same field, so stripping it here would make the two receipts disagree. **Merge DARK:** `SYNAPSE_CACHE_ADVISOR_ENABLED` stays unset; flipping it on is a separate, observable change.
