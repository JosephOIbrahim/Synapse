# Crank 2 — what the SWEEP found in the loop itself (2026-09-06, master 918a58b7)

The second crank's SWEEP ran before the FIND lanes and found three defects **in
the loop's own record**. All three are the same failure class the harness was
built to catch — a verdict that was never measured — and one of them was mine.

## 1. B6 was closed on evidence that could not have been true

`BACKLOG.json` carried B6 as `closed`, `closure_evidence: "predicate re-run on
master after merge, exit 0"`. Its predicate has three clauses. Clauses 1 and 2
hold (zero `createNode('karma')` under `python/synapse/routing`, no `'grade'` in
`scene_recipes.py`). Clause 3 —

```
(rg -n 'proposal-only' python/synapse/routing/recipes/base.py matches
 OR rg -n 'command_fn=' python/synapse/server/handlers.py matches)
```

— returns nothing in either file, and merge `6659b7dc`, the merge the evidence
cites, touched neither file. The predicate never exited 0.

**Ruling:** B6 is open. The false closure is withdrawn in place, with the
reason, rather than deleted. The crux slice that *did* land (karma →
usdrender_rop ×5, the phantom `grade`, the extractor gate) is recorded in the
item's note. Clause 3 measures the vocabulary / `route_chat` ruling, which is
Joe's and still outstanding.

The loop caught its own conductor. That is the loop working.

## 2. Eight predicates were stored truncated at exactly 500 characters

D-F1, D-F2, D-F4, D-F5, D-F6, D-F9, D-F10 and D-F11 ended mid-expression
(`...if v['w']<`, `...print('PASS' if o`). The 2026-09-05 ingest that filed the
Bierut findings sliced every field (`[:500]` on the predicate, `[:600]` on
action and evidence). Eight of the loop's own items were unmeasurable and had
been reported as open for a day on no measurement at all.

**Fixed:** all eight restored whole from
`harness/design_review/2026-09-05/review_report.json`, along with their action
and evidence text.

## 3. Four of those predicates could not fail honestly

Every one of the eight ran its hython probe with `>/dev/null 2>&1` and then read
whatever JSON was on disk. After the B+C wave deleted `_font_btn`, the probes
crash —

```
census_subtract.py:73  AttributeError: 'SynapsePanel' object has no attribute '_font_btn'
```

— and the predicates read the 2026-09-05 JSON and returned a confident **FAIL
describing a panel that no longer exists** (D-F1 reporting EXPLAIN / OPTIMIZE /
BUILD HDA clipped, when the verb rail was retired; D-F2 reporting the rail
cannot say its state, when BC-2 landed the state sentence).

**Fixed:** a probe that exits non-zero now exits 2 = UNKNOWN, with no verdict.
D-F1, D-F2 and D-F11 immediately flipped from a false FAIL to an honest UNKNOWN.

**Not fixed here (new item):** the probe scripts themselves still measure the
pre-wave panel. Repairing them is design work, not a record fix, and faking a
pass would be the very thing this page is about.

## 4. B4 was measured by a string, not by the thing

B4 read REGRESSED. Clause 1 was green (`hython audit_panel.py --strict` exit 0,
`G3 RESULT:  pass  ·  0 WARN`). Clause 2 required the literal `G3 RESULT` in a
release note; `RELEASE_v5.65.1.md:37` states `G3 strict **pass, 0 WARN**` in
prose. The requirement was always "the release carries the verdict", so the
predicate now accepts either spelling. Substance never regressed.

## The guard

`harness/cto/check_backlog.py` — run it before trusting the record. It refuses:

- a predicate whose length sits exactly on a slice boundary, or that ends on a
  dangling operator or opener (the truncation class);
- a `closed` item with no `closure_evidence`, or evidence too thin to re-run
  (the B6 class).

Proven against both defects by mutation before it was committed. Current
record: **25 items, 17 open, every predicate runnable, every closure evidenced.**
