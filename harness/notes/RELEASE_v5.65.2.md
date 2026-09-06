# v5.65.2 — the loop audited itself and found a lie it had told

A record-integrity release. No product code changed; the panel an artist opens
is byte-for-byte v5.65.1. What changed is whether this project's own backlog can
be believed, plus one CI timing fix.

Scope: the second crank of the CTO review loop (`harness/cto/`, 2026-09-06,
master `918a58b7`). Its SWEEP phase ran before the FIND lanes and audited the
loop's own record. Full account: `harness/cto/runs/2026-09-06/SWEEP_REPAIR.md`.

## What the crank found, in the loop, not the product

**B6 was closed on evidence that could not have been true.** The 2026-09-05
entry read *"predicate re-run on master after merge, exit 0"*. Two of that
predicate's three clauses held. The third asks whether the recipe path is
declared proposal-only or wired to a command channel; neither string exists in
either file, and merge `6659b7dc`, the merge the evidence cites, touched
neither. The predicate never exited 0. The closure was false, it was written by
this loop's own conductor, and the loop caught it on the next crank. Withdrawn
in place with the reason rather than deleted; the item is open and stays gated
on the vocabulary ruling.

**Eight predicates were stored clipped at exactly 500 characters.** D-F1, D-F2,
D-F4, D-F5, D-F6, D-F9, D-F10 and D-F11 ended mid-expression (`...if v['w']<`).
The ingest that filed the Bierut findings sliced every field. Eight items had
been reported open for a day on no measurement at all. Restored whole from
`harness/design_review/2026-09-05/review_report.json`.

**All eight could not fail honestly.** Each ran its hython probe under
`>/dev/null 2>&1` and then read whatever JSON sat on disk. The B+C wave retired
`_font_btn`, the probes now crash on it, and four predicates were returning a
confident FAIL describing a verb rail that no longer exists. A failed probe now
exits 2 = UNKNOWN and returns no verdict. Once they could speak: D-F1, D-F2,
D-F10 and D-F11 report UNKNOWN (broken instrument); D-F4, D-F5, D-F6 and D-F9
are real failures with measured numbers.

**B4 was measured by a string, not by the thing.** Its second clause required
the literal `G3 RESULT` inside a release note; `RELEASE_v5.65.1.md:37` states
`G3 strict **pass, 0 WARN**` in prose. The requirement was always that the
release carries the verdict, so the predicate now accepts either spelling. The
G3 gate itself never regressed: `hython audit_panel.py --strict` exits 0,
`G3 RESULT:  pass  ·  0 WARN`.

## The guard

`harness/cto/check_backlog.py` refuses both classes: a predicate whose length
sits exactly on a slice boundary or ends on a dangling operator, and a `closed`
item whose `closure_evidence` is missing or too thin to re-run. It was proven
against both defects by mutation before it was committed, and it is the first
thing the next crank runs.

Its truncation test is deliberately narrow. A predicate carries regexes and
character classes; a delimiter-balance parser flags healthy
`rg -c "createNode\(['\"]karma['\"]"`, and a guard that cries wolf is worse than
no guard.

## Also in this release

`tests/test_f3_emergency_net.py` — the WS-halt pin now waits for the halt call
rather than for the `escalated` latch that precedes it by a few milliseconds. A
macOS runner asserted in that gap (CI run 34000206968, *"Expected 'mock' to have
been called once. Called 0 times"*). Anchored to the act, not a proxy; no
widened sleeps. CI green on `918a58b7`, all four runners.

## Record

| | before | after |
|---|---|---|
| items | 25 | 25 |
| open | 16 (8 unmeasurable) | 13 |
| unknown, instrument broken | 0, hidden as FAIL | 4, stated |
| closed on false evidence | 1 | 0 |

## Tests

Full suite on master (stock Python 3.14.2, no `hou`): **7613 passed, 0 failed, 357 skipped**
(`harness/notes/h22/pytest_v5652_master.txt`). No product code changed since
v5.65.1, so the panel tier and G3 numbers from that release stand unmodified:
`tests/panel` + docking 239 passed / 1 pre-existing failure, G3 strict pass with
0 warnings.

## Not in this release

The crank's seven FIND lanes were still running when this was cut; their
findings ride the next one. The design probes under
`harness/design_review/2026-09-05/` still measure the pre-B+C panel — repairing
them is design work, and the loop reports UNKNOWN until someone does it rather
than inventing a number.

## Standing RC blockers — waiver carried

Unchanged; nothing here touched their surfaces.
