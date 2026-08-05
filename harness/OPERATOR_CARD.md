# LONG HARNESS — Operator's Card

Three workstreams. Different problems. Do not mix them.

---

## CAPABILITY — build what is missing

A missing tool is a **wall, not a hill**. No loop climbs it.

**The wall:** `set_expression`. SYNAPSE cannot write `ch()`, relative
references, `npoints()` onto a parameter. Until it can, every network it builds
is correct-once and static, and the `expression` category floors at zero.

Build it first. Everything else is capped beneath it.

---

## GATE — known-correct work

Binary accepts, rope harness, 29-for-29 today.

```
python harness\rope\runner.py gate
python harness\rope\merge_pending.py
python harness\rope\runner.py run --model claude-fable-5 --confirm-model
python harness\rope\runner.py verify <ID> --passed
harness\rope\watch.cmd
```

Local model, zero API tokens:

```
$env:SYNAPSE_ROPE_ENGINE = "ollama"
python harness\rope\runner.py run --model gpt-oss:20b --confirm-model
```

**Queue:** 7 red tests · symbol table 22.0.397 vs running 22.0.400 · router not
initialised · COPs scaffolds that do not cook (implement or label honestly) ·
SOP graph builder + SOP templates.

---

## BENCH — the metric

```
hython harness\bench\run_bench.py              score
hython harness\bench\run_bench.py --only sop   one category
hython harness\bench\run_bench.py --baseline   record the incumbent
```

12 tasks, 50 weight. **Expression 15, SOP 13** — weighted toward the audit's
weak spots, not its strong ones. Six tasks perturb.

**Structure is not the test.** Build the network, move an upstream parameter,
cook, require downstream to respond. A graph that builds and does not move
reports `NOT PROCEDURAL` — the T4 ceiling, visible as a number.

---

## LOOP — hill climbing

```
/token-saver
Read harness/program.md and run one iteration.
```

Overnight:

```
/token-saver
Read harness/program.md. Run iterations until ten consecutive discards
or twenty with no movement, then write a summary.
```

```
harness\bench\ledger.tsv       every hypothesis, kept or discarded
harness\bench\incumbent.json   the score to beat
```

---

## Rules that keep it honest

**Never edit the bench to raise the score.** `manifest.json` and
`run_bench.py` are off-limits. CRUCIBLE never weakens a hostile test.

**Unmeasurable is not zero.** Inconclusive leaves the denominator. If
inconclusives climb, fix the harness before trusting the number.

**One hypothesis per iteration.**

**A total that rises while a category falls is a regression.** Discard.

**Do not iterate against a wall.** If expression tasks report NOT PROCEDURAL,
log it once and move on. The tool has to exist first.

---

## Order

1. Green the 7 red tests
2. **Build `set_expression`** — removes the ceiling
3. GATE: symbol table, router, scaffold honesty
4. BENCH `--baseline`
5. GATE: SOP builder + templates
6. BENCH loop overnight, ARCHITECT → FORGE → CRUCIBLE
7. Parallel bench workers, then parallel hypotheses

**2 before 4.** Benchmarking a wall gives a flat zero and teaches nothing.
