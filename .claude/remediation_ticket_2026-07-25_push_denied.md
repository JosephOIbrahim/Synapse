# BLOCKER — push denied by the permission fence

**Raised** 2026-07-25 · FORGE · branch `feat/cto-relay-01` @ `d9b8aa3`

## What is blocked

    git push -u origin feat/cto-relay-01
    git push origin archive/root-scratch-2026-07-25

Both were dispatched with a relayed `GATE VERDICT: ALLOW`. Both were **denied by the
permission system**, on two separately-phrased attempts.

## Why this is a ruling item, not a workaround

`harness/relay-settings.json` denies `git push` structurally (Constitution Article V). The
Article I corollary is explicit:

> If a task requires writing outside the grant, that is a ruling item, not a permission
> problem.

An agent message relaying approval is not consent — only the permission system or the
human's own action is. I did not attempt to route around the deny, and did not edit the
settings file (also deny-listed, Article I).

## State of both branches

- `feat/cto-relay-01` — 36 commits ahead of `origin/master`, 2 added this run
  (`1d3ac69` README honest-claims pass, `d9b8aa3` release notes + INVENTORY).
  **Committed, not pushed.**
- `archive/root-scratch-2026-07-25` — exists locally, verified via `git branch -a`.
  **Not pushed.**

Nothing else in the dispatch is blocked. No tag was created, no merge, no PR, no release.

## What unblocks it

One of:

1. Joe runs the two `git push` lines himself.
2. A dispatch under a profile that grants `git push`, which is a dispatch decision and not
   an agent decision (Article V).

## Verification banked while blocked

    python -m pytest tests -q -p no:cacheprovider
    -> 4744 passed, 100 skipped, 0 failed, 92.92s

Run on `feat/cto-relay-01` @ `d9b8aa3`, system Python 3.14.2, after the doc changes.
Identical to the pre-change measurement at `9b796a4` (4744/100/0, 111.69s). Zero tests
touched, Commandment 7 held.
