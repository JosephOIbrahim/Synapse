# H2 — HALTED before Part A. Concurrent-writer collision in the dispatch worktree.

**Session:** interactive, `claude-opus-5[1m]`, worktree `.claude/worktrees/h2-requalify`
**Date:** 2026-07-26 · **Halted at:** ~15:02, before any H2 probe was dispatched
**Reason:** Constitution Article V — two agents in one directory.

---

## 1 · Why I stopped

A second H2 run is executing this same brief in this same worktree concurrently.

**Evidence (read-only, this session):**

| Observation | Producer | Time |
|---|---|---|
| HEAD moved `70ed8ef` → `c1d194b` without my action | `git reflog` shows `cherry-pick` at HEAD@{0} and HEAD@{1} | ~14:50 |
| `harness/notes/mutation_matrix_h2.py` appeared (17,121 bytes) — Part B instrument I did not write | `ls -la` | 14:58 |
| `.mm_h2_tmp/` created with per-mutation subdirs | `ls` | 14:59 |
| Matrix advanced `M1–M5` → `M1–M9` → `M1–M14` across three consecutive tool calls | `ls .mm_h2_tmp/` ×3 | 15:00–15:02 |
| `python/synapse/mcp/tool_impls/solaris/set_purpose.py` observed **modified then restored** between calls | `git status` / `git diff` | 15:00–15:01 |

That last row is a live mutation cycling (break → run pin → restore). Reading or running
against the tree while it cycles produces findings that cannot be attributed — the exact
defect RES's adjudicator raised ("the tree moved under the reviewers") and the exact reason
Article V requires one worktree per parallel agent.

**I did not commit, did not write `harness/notes/receipts/H2b.json`, and ran nothing after 14:47.**
Writing the receipt would have collided with the other session's receipt for the same leg.

---

## 2 · What I did establish, and it is still valid

My three hython runs completed at **14:44–14:47**, which **predates** the cherry-pick at 14:50.
They therefore measured the genuine pre-RES tree and are attributable to this session.

### The dispatch-base defect — VERIFIED-RUNTIME, 22.0.368, this session

H2 was dispatched into a worktree whose base commit `70ed8ef` **did not contain the RES fix.**
RES landed on `repair/fake-hou-residency` (`c0cc415`, `0b5806c`); `git merge-base --is-ancestor
c0cc415 70ed8ef` → **false**. At dispatch the tree had no `HOU_REIMPORT_GUARD` in
`tests/conftest.py`, no `tests/test_hou_reimport_guard.py`, and all 10 eviction sites live.

Reproduced the residency defect on that tree:

| Command (hython3.13, `PYTHONPATH=.hython_deps`) | Result |
|---|---|
| `pytest tests/solaris/test_live_wiring.py` | **27 passed** |
| `pytest tests/panel/test_theme_source.py tests/solaris/test_live_wiring.py` | **18 failed**, `AttributeError: 'Parm' object has no attribute 'set'` |

So the brief's STOP clause was substantively met on arrival: RES eliminated the residency on
its own branch, not on the tree H2 was told to probe. The other session evidently reached the
same conclusion and resolved it by cherry-pick.

**Note the count: 18, not 17.** RES.json and R43 both say bucket 2 is "~17 tests" and RES
confirmed "exactly 17". On this composition the failure count is 18. Whichever H2 run completes
should reconcile that delta rather than inherit either number — Law 2, no number without a
producer.

### The oracle's own Law-1 hole — VERIFIED-RUNTIME

The brief's oracle says `pytest -k solaris -> 0 failed, count strictly increases`.

`-k` selects on **test name**, not path. From the repo root it matches **one** test, which
skips:

```
1 skipped, 4508 deselected, 2 errors in 11.59s
```

A clause that selects a single skipping test cannot fail and cannot increase. It is a
decoration in exactly the sense R34 and Law 1 name, sitting inside the oracle of the leg
written to remove decorations. The path-scoped form (`pytest tests/solaris/`) is what the
clause intends. **This needs restating before either H2 run can claim its oracle.**

The 2 collection errors are `ModuleNotFoundError: pywintypes` reaching in through
`.hython_deps/mcp` — an artifact of R47's measurement side-directory (`pywin32` installed
without its post-install step), not a tree defect.

### An F1 signal worth carrying forward — VERIFIED-STATIC

L2's F1 anchors the Solaris tools at `synapse/mcp/tools/solaris/`, "outside the installable
`python/synapse/` package". This tree also contains
**`python/synapse/mcp/tool_impls/solaris/{import_megascans,create_variants,set_purpose}.py`** —
*inside* the package. F1's premise may have changed since L2. Not adjudicated here; flagged so
the completing run probes both trees rather than only the path F1 names.

---

## 3 · Disposition

Nothing in this session is committed. Untracked artifacts in the worktree
(`.mm_h2_tmp/`, `harness/notes/mutation_matrix_h2.py`, `shot_layers/`) belong to the other
session — **Law 4: classified, not deleted.**

`shot_layers/` in the repo root is RES-F11 recurring, now confirmed on a second branch.

**For the human:**
1. Decide which H2 run is canonical and stop the other. Two receipts for one leg is worse than
   none.
2. If mine is canonical, re-dispatch into a *fresh* worktree off `c1d194b` (which now carries
   RES), not this one.
3. If the other run is canonical, it should be handed §2 of this file — the base-commit
   history, the 18-vs-17 delta, the `-k solaris` oracle hole, and the `tool_impls` F1 signal
   are all things it cannot see from inside its own run.
4. Independent of either: the in-flight matrix currently mutates
   `python/synapse/mcp/tool_impls/solaris/*.py` in place. If that process is killed mid-cycle
   it leaves a deliberately broken implementation in the working tree. Check
   `git status` / `git diff` on that directory before trusting the tree again.
