# v5.40.0 — the loop closes

*Six commits plus a recovery. The harness could find problems and fix problems; what it could not do was remember a finding existed once the receipt was written. 221 rulings addressed to the human sat in files no code ever opened. Now everything waiting on a decision has a reader, a place on screen, and a clock.*

---

## The harness reads its own mail

`for_ruling[]` is what the constitution calls "the only channel to the human." An audit traced a finding from birth to merge and found nothing was listening on it — receipt `findings[]` and `for_ruling[]` were read by **no code, script, workflow, or check in the tree**.

`harness/decisions.py` is the consumer that did not exist. It joins every receipt ruling, every non-green receipt, and every unratified flywheel cycle into one board, oldest first:

```
python harness/decisions.py            # 289 open items today
python harness/decisions.py --write    # ranked board with the exact flip per cycle
python harness/decisions.py --count    # the number; exits 6 if anything is 30+ days old
```

That exit code is the point. "Nobody got to it" is now a failing state instead of the ambient condition — the difference between a loop that is *observable* and one that is *closed*.

It decides nothing: a test pins that it never writes `ratified` and never opens the flywheel queue for writing. The first diagnosis — that the queue was over-gated — was wrong and the triage refuted it: 20 of 26 parked cycles are genuine human judgement calls, but **24 of 26 gate nothing mechanically**. The bottleneck was attention, not authority. So the fix is a count you cannot avoid, not an agent with more power.

## A status bar that refuses to vouch for a tree it didn't measure

`harness/statusline.py` renders the harness state at the bottom of every Claude Code turn:

```
feat/repair-heats-01 │ !14 armed  !6 attention  289 decisions  5316 ok 50s
```

- **No cache.** Every figure recomputes per render (~94 ms — the first draft spawned git once per orphan and took 919 ms; the render path is now subprocess-free and a test explodes if that regresses).
- **Zero segments vanish.** A bar that says "0 armed" daily trains the eye past the day it says 14.
- **The suite figure has a producer or does not render.** It comes only from piping a real pytest run into `--stamp` — never `.pytest_cache`, which claimed 43 failures on a tree whose suite had just passed clean. And it carries the commit it measured: change the tree without re-stamping and the segment goes yellow and says `other tree` instead of showing a fresh-looking age. That drift detector fired correctly on its own release cycle, twice.

## The lock, the verdict, and the orphans

Three defects in the harness's own instruments, all the same defect wearing different coats:

1. **The lock had a reader and no writer** outside PowerShell. `status.py:62` read `harness/state/locks/`; nothing in Python or TypeScript ever wrote there, so the board said `ready` while an agent was live in the worktree — the exact collision documented twice in `.claude/h2-halt/`. `harness/lock.py` writes the same dialect `orchestrate.ps1` already used (atomic `O_CREAT|O_EXCL`, refuses pids 0/4 that `Get-Process` resolves forever, reap requires dead pid **and** quiet clock).
2. **The board read presence as verdict.** 17 of 41 receipts are not plain green — including one that says `held_not_started` — and all 17 printed as done. `verdict_of()` now reads the `status` field; non-green legs surface as `attention` with the receipt's own word, and no longer satisfy downstream dependencies.
3. **Orphan worktrees routed agents into the main tree.** 14 directories under `.claude/worktrees/` existed but were not registered worktrees, so git run from them resolved to the main repo on the live branch — and `orchestrate.ps1` skipped creation for any directory that merely existed. Root cause closed: the `git worktree add` exit code is now checked (its stderr was being silently swallowed by `$ErrorActionPreference`), and the launch-marker write no longer conjures the directory as a `-Force` side effect. Reproduced before and after in a throwaway repo. `worktree_guard.py audit` reads **deliberately red** (exit 5) until the 14 existing orphans are remediated — it goes green by remediation, never by silencing.

## The recovery

`orchestrate.ps1:148` says "The receipts are lost." They were not. Claude Code transcripts record every Write and Edit an agent ever made, so the work reconstructs deterministically: last Write per path as base, later Edits replayed in order.

`harness/notes/recovery/recover_orphan_writes.py` (dry-run by default, **never overwrites**) recovered **40 files, 0 errors**: the three "lost" receipts byte-for-byte at their predicted sizes (C0 28,877 · H9 35,541 · S1 25,136), all 17 v1 capture-probe scripts, the s1 forensic producers, and the rsi0 evidence behind the "pytest pollutes the production log" finding. Provenance per file in `recovery_manifest.json`.

The moment the receipts landed, the decisions board moved 266 → 289 on its own — the recovered rulings entered the channel with nobody asked to look. The release's one-line proof of itself.

## Numbers, with producers

| Figure | Producer |
|---|---|
| 5,316 passed · 0 failed · 137 skipped | `python -m pytest tests/ -q \| python harness/statusline.py --stamp` |
| 289 open decisions | `python harness/decisions.py --count` |
| 14 legs armed | `python harness/worktree_guard.py audit` |
| 40 files / ~481 KB recovered | `harness/notes/recovery/recovery_manifest.json` |
| 35 new tests, 13 mutation-proved | `tests/test_{harness_lock,worktree_guard,statusline,decisions}.py` |

Suite floor moved 5,285 → 5,316 across the release. Two of the new tests were decorations when first written — one passed against a mutant that rendered every zero segment — and were caught by running the mutations, then fixed. Law 1 applied to its own enforcement.

## Known limitations — what this release does not claim

- **The 14 existing orphans are not remediated.** The guard reports them; nothing deletes them (Law 4 — recovery preceded cleanup, and cleanup is a human act). `!14 armed` stays on the bar until then.
- **`orchestrate.ps1:151` presence-is-done is deliberately unfixed.** It is currently the only thing suppressing re-dispatch of H2 into an orphan; the blast-radius verdict was UNSAFE-NEEDS-MORE. Remediate the orphans first.
- **Something non-orchestrator strips worktrees and it is unidentified.** Seven were emptied in an 8-second window on 2026-07-26; another lost its `.git` the next day. Transcripts are the proven backup, but the process is still loose.
- **`harness/lock.py` is on no dispatch path yet.** It protects direct callers; `orchestrate.ps1` uses its own equivalent lock, `run.ts` takes none. Wiring the dispatchers through one lock is open work, and the module's own comment now says so instead of claiming otherwise.
- Two claims in this release's own history were **refuted by its adversarial pass** and corrected in-tree (`13cacba`): the dispatcher manufactures 6 of the 14 orphans, not all; and the failed-add path lands the agent in the freshly-manufactured orphan, not the repo root — it loses that race by ~1.2 s.
