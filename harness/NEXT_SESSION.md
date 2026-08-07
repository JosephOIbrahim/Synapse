# NEXT SESSION - 2026-08-07 (or whenever)

One file. The loop you opened this thread with is CLOSED - Solaris setups
that hold are built, verified, merged to master, tagged v5.43.0, released.
What follows is finish-work and decisions, not the core problem.

---

## State at close of 2026-08-06

```
master        c4187d01   BLOCKS live (M5 + M5b), synced to remote
release       v5.43.0  -> c4187d01, tag correct, published
CI0           14ad01e7   on ci/ci0-honest-green, +2 ahead of master, NOT merged
                         status: green-with-a-stated-exception
```

CI0 turned master CI honestly green (3 failed -> 0 failed, 40 deselected,
+21 passing = 3 real-rot fixes + 18 marker-invariant tests). It corrected
its own brief with a probe (the moneta durability test was mislabelled
environmental - it fails with pxr present too) and found a real production
regression: synapse_evolve_memory has been DEAD since 7f7bbc39 and untested.

Nothing is running. Nothing is at risk.

---

## FIRST: five CI0 rulings (all Article I - your call, not an agent's)

CI0 escalated these rather than decide them. Read, rule, then the merge.

**R-CI0-1  moneta first-deposit force-save. THE ONE THAT MATTERS.**
`_last_save = 0.0` makes the first deposit always fsync. Durability posture,
not a bug.
  A (shipped): keep it. First deposit survives kill -9. Docstring's
     'no per-deposit fsync' stays false for deposit #1.
  B: `_last_save = time.monotonic()` in __init__. One line. Original
     single-deposit assertions then pass verbatim; docstring becomes true;
     a lone deposit + kill -9 within 30s is lost (already documented).
  This is a real durability decision. Rule it deliberately.

**R-CI0-2  deprecate synapse_evolve_memory?**
It was dead since 7f7bbc39, nobody noticed - evidence of how little it's used.
CI0 rerouted it to shared/evolution.py so it works again. Alternative:
deprecate outright, since Moneta sleep_pass supersedes markdown->USD evolution.

**R-CI0-3  three zero-elapsed-time tests (Windows-only).**
Fail only on Windows dev (~15ms clock), never on CI's ubuntu/macos legs. Real
fix = time.perf_counter() in routing/session product code, two subsystems.
Leave, or fix.

**R-CI0-4  two stale evolution sentences in governing docs.**
docs/DEBUT_READINESS.md:122 and CLAUDE.md A6 say evolution fires under jsonl.
It fires nowhere. Article VI - agent will not touch governing docs unasked.
Correct them yourself, or direct it.

**R-CI0-5  make statusline.py worktree-aware.**
Every agent worktree shows '?' branch + 4 phantom red tests because .git is a
FILE in a linked worktree. Fix: read the gitdir: pointer. Explains red-test
noise weve been eating all thread.

Then: merge CI0 to master (Gate C), CI re-runs green.

---

## THEN: the small committed-but-open items

**R-M5b-1** (ruled warn-not-refuse, never committed). One-line scout change:
external/no-Houdini process should WARN not refuse on the phantom gate. Write
the change + a decision note. ~10 min.

**Two bugs CI0 surfaced**, both logged above as R-CI0-3 and R-CI0-5.

---

## THEN: M6 - the actual last mile

The phrase table. Maps "basic Solaris setup" -> fixture name so typing it
FIRES. The engine underneath (apply_fixture) is done, merged, released. M6 is
small now: exact-match table first, model only on miss, zero tokens on the
common path. This is what makes the thread's opening ask literally work at the
keyboard, not just via a fixture name.

Design decision to make when you start M6: exact-match only, or aliases
("solaris basic" == "basic solaris" == "basic Solaris setup")?

---

## Dispatch note - READ BEFORE running the orchestrator

The orchestrator cuts worktrees from its OWN HEAD via `worktree add -b`, and
REFUSES if the branch already exists. Two legs this thread (M5b, CI0) hit
wrong-base because the manifest base != the leg's needed base. The real gap:
orchestrate.ps1 has NO per-leg base support. Either add it, or make base a
documented human pre-step (cut the worktree by hand, commit the brief on the
branch, then dispatch).

AND: launching agents headless through DC does not work - they start and stall
with no session log. Agents must be launched from a REAL terminal (that is how
CI0 actually ran). This is a hard constraint, not a preference.

---

## Execute order

```
1. read + rule the five CI0 items (~20 min, R-CI0-1 is the real one)
2. merge CI0 -> master (Gate C: $env:SYNAPSE_GATE_C=1)  -> badge green
3. commit R-M5b-1 warn-not-refuse
4. M6: phrase table  (fresh, full density - the last mile)
```

Nothing here is urgent. The release shipped. This is finish-work.
