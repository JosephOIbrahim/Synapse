# The suite floor moves for reasons no commit can see

**Found:** 2026-09-14, while checking an unexplained 3-test delta between two gate runs.
**Status:** live at `d2f403a6`. Nothing here is fixed; it is recorded.

---

## What set it off

Two consecutive gate runs, both `pytest -q -p no:randomly`, both exit 0:

```
d13a84f5   8911 passed, 427 skipped, 0 failed
d2f403a6   8908 passed, 430 skipped, 0 failed
```

Between them: one commit of markdown under `harness/design_review/`, one probe script
under `harness/` (not collected — `testpaths = ["tests"]`), and one comment-only edit to
`tests/panel/test_docking.py` whose entire executable diff is the deletion of `# 400`
from the end of one line.

**Total collected is identical at 9338 in both runs.** No test appeared or disappeared.
Exactly three moved from *passed* to *skipped*.

---

## What I found looking for them

I did not isolate the specific three. I found something worth more.

```
27  hython tests/solaris/run_live.py
24  PySide unavailable - run via hython
21  cannot import name 'canonical_world_commitment' from 'hanish.future.claims'
        (G:\Hanish\hanish\future\claims.py)
17  Qt not available
10  evolution.py not found (deprecated)
10  No live transport configured
 9  requires real Houdini (hython)
 ...
```

**Twenty-one tests in this repository are disabled by a symbol that does not exist in
another repository, on another drive.**

Verified:

```
G:/Hanish/hanish/future/claims.py       exists, dated 2026-08-19
grep -c canonical_world_commitment      0          <- the symbol is gone
python -c "import hanish"               G:\Hanish\hanish   <- on sys.path, out of tree
grep -rln hanish tests/                 3 files
```

Three test files, twenty-one tests, gated on an external package that has drifted out
from under them. No commit in this repo can fix it, and — more to the point — **no gate
in this repo can see it.**

---

## Why this matters more than the three tests

Every merge gate I have quoted this session has the shape *"N passed, M skipped, 0
failed."* The discipline has been that a failure after a merge is attributable to that
merge. That holds for **failures**. It does not hold for **skips**.

A test that silently becomes a skip is a coverage loss, and:

- a skip **exits 0**;
- a skip is **invisible to a pass/fail gate**;
- the passed count **goes down**, which reads like tests were removed rather than
  disabled;
- and here the cause is **outside the repository entirely**, so it can move between two
  runs with no commit in between.

This is the same lesson as *"412 skipped is 412 proving nothing"* — with the sharper
edge that **the skip population is not static.** It can grow silently, and when it does,
the floor I gate on moves for reasons no diff explains.

## What would actually close it

Not attempted here; named so it can be.

1. **Gate on the skip count, not only on failures.** A run that skips more than the
   recorded floor should be as loud as a red. That is one number in the ratchet.
2. **Pin the out-of-tree dependency, or cut it.** Three test files reaching onto `G:\`
   is a coupling the repo cannot defend. Either vendor what they need, or mark them
   `xfail` with the reason, so the loss is declared rather than absorbed.
3. **Never quote a floor without its skip count.** I have been doing this; it is what
   made the delta visible at all. Keep it.

---

## What this does NOT say

It does not say my two commits caused the delta — comments and uncollected files cannot,
and the arithmetic (identical total, three moved) points at environment, not collection.
It does not claim the `hanish` family *is* the specific three: that family measured 21 in
the run I broke down, and I did not capture a per-test skip list from the earlier run to
diff against. The honest statement is that a large environment-dependent skip family
exists, it is exactly the shape that moves between runs, and the gate cannot see it
either way.
