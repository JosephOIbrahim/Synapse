# program.md — SYNAPSE competence research org

You run an autonomous loop that makes SYNAPSE better at Houdini.

Joe edits this file. You do not. If you think it is wrong, write that in the
ledger and stop.

Repo `C:\Users\User\SYNAPSE` · Houdini **22.0.400** · ledger
`harness/bench/ledger.tsv`

---

## The metric

```
hython harness/bench/run_bench.py
```

Prints **competence** (0–1) plus per-category. The only number you may
optimise.

**Structure is not the test. Behaviour is.** Six of twelve tasks perturb an
upstream parameter and require downstream to respond. A network that builds
correctly and does not move is `NOT PROCEDURAL` — a real failure, and the one
this project exists to fix.

**Fixed budget.** Never raise a timeout to make a task pass.

**Unmeasurable is not zero.** `inconclusive` leaves the denominator. Never
convert one into a pass or a fail to move the number.

---

## Read this before your first iteration

The 2026-08-03 capability audit found a **wall, not a hill**:

> SYNAPSE cannot create expressions on parameters. `set_parm` sets literal
> values. So you cannot build the "wire this parameter to that parameter"
> patterns that make Houdini procedural.

**No prompt, corpus entry or recipe fixes that.** The tool does not exist.
Until `set_expression` ships, every `expression` task fails and every
perturbation task is capped.

**If the bench reports `NOT PROCEDURAL` on expression tasks, do not iterate on
them.** Write one ledger row naming the missing capability and move to a
category you can actually move. Burning iterations against a wall is the
failure mode this note exists to prevent.

---

## What you may edit

```
harness/bench/recipes/     deterministic parameterised operations
harness/bench/corpus/      Houdini knowledge injected into context
harness/bench/prompts/     system-prompt overlays
harness/bench/routing.json cascade thresholds
```

## Never, under any circumstance

```
python/synapse/**            the engine
shared/**                    integrity, marshalling, bridge
tests/**                     the product suite
harness/bench/manifest.json  THE BENCH
harness/bench/run_bench.py   THE SCORER
program.md                   this file
```

Editing the bench to raise the score is the one unforgivable move — CRUCIBLE
weakening a hostile test, one level up.

---

## The loop

**One hypothesis per iteration.** Two changes and the delta means nothing.

1. **Read** the last 20 ledger rows. Do not retry a discarded hypothesis
   without saying why it is different now.
2. **Read** per-category scores. Attack the weakest category you can actually
   move — see the wall note above.
3. **State the hypothesis** before editing, one sentence:
   *"<category> fails because <cause>; <change> should fix it."*
4. **Edit** the knowledge surface. Smallest change that tests the hypothesis.
5. **Run** the bench.
6. **Decide.** KEEP if the total improved AND no category dropped more than
   0.02. Otherwise DISCARD — `git checkout -- harness/bench/`.
   *A total that rises by starving a category is a regression in disguise.*
7. **Commit** kept changes, one per hypothesis, message = the hypothesis.
8. **Append** to the ledger: ts, hypothesis, before, after, per-category
   deltas, verdict, one line of why.

**Stop and summarise** at ten consecutive discards, twenty flat iterations, or
if you are about to touch a forbidden path.

---

## Roles

Extends `docs/crucible_protocol.md`. Rotate deliberately — the context that
built a thing must never be the context that certifies it.

**ARCHITECT** decides what and why. Writes the hypothesis. Never edits files.
**FORGE** implements and runs the bench. Never judges sufficiency.
**CRUCIBLE** attacks a KEPT change: N=0, missing path, wrong input order, a
context where it makes no sense.

**Commandment 7 holds.** A hostile test that finds a real defect goes back to
FORGE. CRUCIBLE never weakens the test.

Run CRUCIBLE after every third KEEP, and always after a recipe lands.

---

## What the categories are asking

**expression** *(weight 15 — the ceiling)* — does a parameter READ another
parameter? `ch()`, relative refs, `npoints()`, `$F`. Blocked on a missing tool.

**sop** *(13 — graded C+, 80% of real work)* — the daily chains: scatter/copy,
heightfield, VDB, attribute transfer. No SOP builder exists to match
`solaris_build_graph`.

**arity** *(8)* — asked for one, made one. On 2026-08-03 "an area light"
produced three and reported success.

**topology** *(5)* — inputs in the right ORDER. `copytopoints` takes geometry
in 0, points in 1. Reversed it cooks fine and yields garbage.

**context** *(4)* — right node in the right context. A sphere SOP in `/stage`
is the classic error.

**memory** *(3 — graded C+)* — does it recall a real decision, or re-derive
from the scene? Infrastructure exists; intelligence does not.

**usd** *(2 — graded A-)* — deliberately low. Already strong; little headroom.
Do not spend iterations here.

---

## Priors — do not rediscover these

- **Recipes beat prompting.** A recipe removes a failure mode permanently; a
  prompt asks a model to behave. Prefer a recipe when the operation has exactly
  one correct outcome.
- **Arity is a parameter, default 1**, never inferred from prose.
- **Corpus grounds names.** Hallucinated node types are a corpus gap, not a
  reasoning gap. Note: Houdini **22.0.400**, and the symbol table is stamped
  22.0.397 — a known mismatch. Treat symbol-table answers as suspect until the
  GATE loop fixes it.
- **Small local models need one instruction per turn.** Compound prompts fail
  on a 30B in ways a frontier model survives. That is a fact about the target
  environment, not a bench flaw.
- **Some COPs tools are scaffolds that do not cook.** Do not bench them, and do
  not let a recipe depend on one.

---

## Ledger

Tab-separated, append-only, `harness/bench/ledger.tsv`:

```
ts  hypothesis  before  after  delta  per_category_deltas  verdict  note
```

`verdict` ∈ `keep` | `discard` | `blocked` | `stopped`.

**The ledger is the product.** A run that improves nothing but records twenty
well-formed disproven hypotheses has done real work. Write it so a human
reading only the ledger knows what was learned.
