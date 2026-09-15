# Closeout — 2026-09-15

What was opened today, and where each thing ended. Written so nothing survives only in a chat
transcript. Numbers are not restated here; each line names the producer that measured it (Law 2).

---

## Shipped

| release | evidence |
|---|---|
| **v5.71.0** | `docs/releases/v5.71.0.md` · `harness/notes/release-5.71.0/` |
| **v5.72.0** | `docs/releases/v5.72.0.md` · `harness/notes/release-5.72.0/` |

Both verified the same way: `step_verify` downloads the installer GitHub is actually serving and
compares its sha256 to the qualified build. "Published" means verified, not assumed.

## Merged

Ten PRs into v5.71.0 (#83–#92), seven into v5.72.0 (#94–#97, #99–#101).

**Trap for whoever audits this:** every one was **squash**-merged, so
`git merge-base --is-ancestor <branch> master` says **not merged** for all of them. The content is
in master under a different sha. Use `git patch-id --stable` before calling any of that work
orphaned — and before pruning a worktree because its branch "isn't merged".

---

## What the gates caught

Recorded because each one is a class, not an incident.

1. **The release script emptied three governing documents.** `cut.py` wrote `CLAUDE.md`,
   `README.md` and `docs/getting-started/installation.md` to **0 bytes** via
   `io.open(p,"w").write(read(p)...)` — Python evaluates the truncating `open()` first, so `read()`
   returns `""`. Caught at `qual`, four steps before the push. `cut.py` now has a guarded
   `write(path, text)` that computes the text before opening and asserts it is non-empty.

2. **A release step that only logs a number gates nothing.** `step_suites` gated on the stock
   suite and merely *printed* the seat number, while the notes asserted "the known five reds, none
   new". The seat suite then reported six. Added `SEAT_KNOWN_REDS`, which stops the cut when the
   count moves. The sixth red is named and diagnosed in `release-5.71.0/SEAT_REDS.md`.

3. **"None is new" was never checkable.** Releases recorded a seat *count*, never the test names —
   two releases could have five completely different reds and both print it truthfully. The names
   and a re-measured v5.70.1 baseline now exist in `SEAT_REDS.md`. Promoting them to a ratcheted
   baseline is a protected-path decision and is Joe's.

4. **CodeRabbit can report `pass` because it is rate limited.** On a fresh PR it was the only
   registered check. A merge gate written as "all registered checks are non-pending and none
   failed" reports GREEN seconds after opening, before the CI matrix exists. Gate on the four
   `test (os, py)` job names only.

5. **A hook that passes `bash -n` here dies on every runner.** `harness/githooks/pre-commit` wrapped
   a `case` in `$( ... )`; the pattern's closing paren ends the substitution in some POSIX shells.
   Git for Windows' bash parses it, and so do local `bash -n` and `dash -n`. Only CI reproduced it.
   Same family as the macOS `EPERM` vs Linux `ESRCH` fix in `native_driver.py` earlier the same day.

6. **Two operator errors, both mine.** A `git commit -am … -F file` is refused by git and the commit
   silently does not happen — verify with `git log --oneline -1`. And `$!` after `nohup … &` returns
   the wrapper pid, so a kill hit nothing and a second release run started on top of the first,
   putting two `pytest tests/` runs on the shared log at once. Resolve pids from the process table
   by command line.

---

## Open — and who owns each

### Joe's rulings

| item | where |
|---|---|
| `_MCPLocalClient.available`: resilient (keep cached port) vs strict (clear it) | `release-5.71.0/SEAT_REDS.md` |
| **PR #98** — composer copy edits a constructor pinned by `_PANEL_BASE`, which moves only under a written ruling. A crit is not a ruling. | PR #98 comment |
| `DsStop:hover` is now identical to rest after `HOT_SOFT` was retired; hover feedback rides only `:pressed` | PR #100 body |
| The 19 ranked changes from the panel crit | `harness/design_review/2026-09-15/CRIT.md` |
| Promoting the six seat-red names to a ratcheted baseline | protected path |
| **PR #93** (pgdrm) | — |

### Structural, recommended

**`master` branch protection — APPLIED 2026-09-15, this section was stale.** It formerly read
"master has no branch protection … returns 404" and filed the fix under *recommended*. That was
true when written and false within the hour; the commit that added RULING 4 never came back to
update this page. The live API now returns a protection object requiring the four
`test (os, py)` contexts, with `strict: false` and `enforce_admins: false`.

`enforce_admins: false` is deliberate — `cut.py` pushes `master` and the tag directly, and enforcing
admins would brick the next release at its own push step. **But the audit is right that this limits
the claim:** with no required reviews and a single admin who is also the only merger, that identity
bypasses the gate on both merge and push. GitHub says so out loud on every push —
`Bypassed rule violations for refs/heads/master`. The protection stops an *unattended* red merge;
it does not stop a determined admin, and "the gate held because a human enforced it" is still true
of the human. Verify: `gh api repos/JosephOIbrahim/Synapse/branches/master/protection`.

### Recorded here because it exists nowhere else

- **785 tracked files at HEAD contain a hardcoded `C:\Users\User` path**, including
  `.claude/settings.json` and several agent definitions, in a public repository. `harness/CLAUDE.md`
  calls that "a bug, not a convenience".
  Reproduce: `git grep -l -I "C:[\\/]Users[\\/]User" HEAD -- . | wc -l`.

  **Corrected 2026-09-15 by adversarial audit.** This line first claimed **768** and said the count
  was "introduced by none of today's branches". Both halves were wrong. 768 was never the count at
  any commit made today — the low-water mark was 775 — and today's own commits *added* files
  carrying the path, **including this ledger**. A ledger that cites a reproduce command and then
  reports a number that command does not give is worse than one that cites nothing, because the
  command makes it look checked. The number above is re-measured at HEAD and moves whenever the
  tree does; treat the command as the authority, never the figure.
- **31 git worktrees exist.** Three under OneDrive and several `bp*` ones carry uncommitted
  changes (`bp3/probe`, `bp3/tidy`, `bp4/b7fix` — merged by ancestry but dirty). The
  `.claude/worktrees/wf_*` set is left over from this session's workflows; two of them hold
  *staged* mutation-test debris, including a staged delete of `tests/test_agent_roster.py` that is
  **not** in any commit. Inventory before pruning; see the squash-merge trap above.

### Found after the fact, by checking a claim v5.72.0 published

**"One type scale: 11 / 12 / 15 / 19" is not complete yet.** The safety half is verified — the
token scale really is `{11, 12, 15, 19}` (`SIZE_LABEL`/`SIZE_SMALL` 11, `SIZE_BODY`/`SIZE_UI` 12,
`SIZE_TITLE` 15, `SIZE_HERO` 19), `SIZE_MICRO` no longer exists, `FONT_FLOOR_PX` is 11, and the
generated stylesheet emits nothing below 11px. But the sheet also emits **14px and 18px**, which
are on no token, and `DENSITY_GAP_SCALE` governs gaps rather than type so density does not explain
them. #100 deleted the 10px size and raised the floor; two off-scale literals survived it.

Reproduce:

    PYTHONPATH=python python -c "import re;from synapse.panel.designsystem import qss;    print(sorted({int(m) for m in re.findall(r'font-size:\s*(\d+)px', qss.stylesheet())}))"

Not a defect and not a blocker — nothing is under the readable floor, which was the claim that
mattered. But "one scale" should mean one scale, and this is the remainder. It belongs with the
crit's type work rather than as a hotfix.

**A note on how this was found, because the first attempt failed.** A live census of
`widget.font().pixelSize()` across 129 design-system widgets on the running panel reported two
sizes, 25 and 27, and a verdict of HOLDS. Those values are on no scale in this codebase: the census
was reading an inherited or host-scaled font, not the QSS-applied one, so it never touched the
claim. A green verdict from an instrument that measures the wrong property is worth less than no
verdict, because it stops the next person looking.

### Mine, still queued

- ~~Panel crit measurements **M1–M7**~~ — **DONE.** All seven landed with their producer scripts
  and raw output committed beside them (`harness/design_review/2026-09-15/measure/`, commit
  `d6bb77d5`). This row was stale the moment that commit landed and is kept struck through rather
  than deleted, because a ledger that quietly removes its own rows cannot be audited.
- **A superseding test for `_MCPLocalClient.available`** — required by `CTO_RULINGS_04.md` RULING 1,
  **does not exist and has no owner.** The ruling created this work while claiming to close a loop.
  It is a real row, not a footnote.
- Farm tools still need curated `activity.py` labels; they fall back to derived ones.

---

## Design record

`harness/design_review/2026-09-15/` holds the crit (`CRIT.md`), the token map (`MAP.json`), the
canvas sources, and `SECOND_LOOK.md` — 29 adversarial findings against the three artboards,
recovered from the reviewing agent's transcript after it hit a usage limit mid-write.

**Do not republish the canvas.** The published artifact carries Joe's own later edits; any update
must read and extract the live page first and merge onto that.
