# SYNAPSE Long Harness — first principles

**Grounded** 2026-08-03 on `rope/gate-a`, v5.42.0, Houdini **22.0.400**,
5,646 tests (7 red), 62 recipes, ~110 MCP tools, and the capability audit of
the same date (GLM 5.2).

---

## 1. What a Houdini network actually is

Not a pipeline of operations. A **dependency graph with parameter-level
coupling**. Two layers:

- **Topology** — which nodes exist, in which context, wired in which order.
- **Coupling** — which parameters read other parameters. `ch()`, relative
  references, `npoints()`, `$F`, point/prim expressions.

A TD builds both. The second layer is what makes the network *procedural*:
change something upstream and the rest adapts. Without it you have a graph that
was correct once, at the moment it was authored.

**This is what "Houdini systems thinking" means.** Not knowing more node names.
Knowing that a network is a system of relationships, and building the
relationships.

---

## 2. The competence ladder

| Tier | Capability | SYNAPSE today |
|---|---|---|
| T0 | Produce nodes | yes |
| T1 | Right node, right context (SOP vs LOP) | partial — Solaris A-, SOP C+ |
| T2 | Wired in the right ORDER | untested |
| T3 | Parameters set to values | yes |
| **T4** | **Parameters COUPLED — expressions, references** | **absent** |
| T5 | Network survives upstream change | unreachable without T4 |

The audit's finding, in its own words: *"SYNAPSE can't create expressions on
parameters — set_parm sets literal values. This means you can't build the
'wire this parameter to that parameter' patterns that make Houdini
procedural."*

**T4 is the ceiling.** Everything above it is unreachable, and no amount of
prompting, corpus or recipe work moves it, because the underlying tool does not
exist. That is the single most consequential fact in this document.

---

## 3. Therefore: three workstreams, not two

My first pass had two loops. The audit forces a third, and getting the
distinction right is what stops the loop wasting itself.

**CAPABILITY — build what is missing.**
A missing tool is a **wall, not a hill**. No hill climb reaches expression
support while `set_expression` does not exist; the loop would simply rediscover
a floor of zero, iteration after iteration. Audit the tool surface first, build
the walls down, then climb.

**GATE — known-correct work.**
7 red tests. Symbol table stamped 22.0.397 against a running 22.0.400. Router
not initialised. COPs scaffolds that do not cook. Each has one right answer, so
each is a binary accept in the rope harness that went 29-for-29 today. A
passing test has no gradient — hill climbing here is strictly worse.

**BENCH — hill climb on competence.**
Everything with no known-correct answer: which recipe, which corpus entry,
which prompt overlay. Needs a scalar, which is the next section.

---

## 4. The metric: perturbation, not structure

My first bench checked **structure** — did the right nodes appear, wired the
right way. That is gameable by a static graph, and a static graph is exactly
the failure we are trying to detect.

**So test behaviour instead:**

1. Run the artist's prompt.
2. Assert structure. Cheap, fast, necessary but not sufficient.
3. **Perturb** an upstream parameter.
4. Cook.
5. Assert downstream **changed**.

A literal-wired network does not move. A procedurally-coupled one does. The
perturbation step cannot be satisfied by producing plausible nodes — it can
only be satisfied by real coupling.

```
competence = Σ(weight × passed) / Σ(weight)
```

One number. Per-category breakdown. Fixed budget per task.

**Unmeasurable is not zero.** A task whose assertion cannot run is
`inconclusive` and leaves the denominator. Never scored 0. This is the
`face_token.py` rule applied to evaluation — a zero would let an
infrastructure failure look like incompetence and send the loop optimising the
wrong thing.

---

## 5. Weights come from the audit, not from taste

The 2026-08-03 review graded the surface. Weight the bench toward the
weaknesses, or the score measures what SYNAPSE is already good at:

| Domain | Audit grade | Bench weight | Why |
|---|---|---|---|
| **expression / coupling** | absent | **highest** | The T4 ceiling |
| **SOP** | C+ | **high** | 80% of real work, no SOP graph builder |
| topology / wiring order | untested | high | Silent wrongness — cooks fine, wrong result |
| arity | broken 2026-08-03 | high | One light requested, three delivered |
| memory / continuity | C+ | medium | Infrastructure without intelligence |
| USD / Solaris | A- | low | Already strong; little headroom |
| render | A | minimal | Strongest area in the product |

Weighting toward strength is the classic benchmark mistake. It produces a
number that rises while the product does not improve.

---

## 6. What the loop may edit

```
harness/bench/recipes/    deterministic parameterised operations   EDITABLE
harness/bench/corpus/     Houdini knowledge injected               EDITABLE
harness/bench/prompts/    system-prompt overlays                   EDITABLE
harness/bench/routing.json cascade thresholds                      EDITABLE

python/synapse/**         the engine                               FORBIDDEN
shared/**                 integrity, marshalling, bridge           FORBIDDEN
tests/**                  the product suite                        FORBIDDEN
harness/bench/manifest.json  THE BENCH                             FORBIDDEN
harness/bench/run_bench.py   THE SCORER                            FORBIDDEN
```

Two reasons. **Safety** — the 2026-08-03 marshalling bug is the argument; an
autonomous loop must not touch thread dispatch or the integrity envelope.
**Locus** — the competence lives in the knowledge layer. A correct recipe makes
the agent understand `copytopoints`; a better engine does not.

**Corollary:** every point gained is a readable artifact — a recipe, a corpus
entry — not an opaque weight.

**Editing the bench to raise the score is the one unforgivable move.** It is
CRUCIBLE weakening a hostile test, one level up.

---

## 7. Roles — extending what already exists

`docs/crucible_protocol.md` already defines the team. Keep it.

**ARCHITECT** decides what to change and why; writes the hypothesis; never
edits files. **FORGE** implements and runs the bench; never judges sufficiency.
**CRUCIBLE** is adversarial — takes a KEPT change and attacks it: N=0, a path
that does not exist, wrong input order, a context where it makes no sense.

**Commandment 7 holds.** A hostile test that finds a real defect goes back to
FORGE. CRUCIBLE never weakens the test.

CRUCIBLE is the piece the rope currently lacks, and today is the argument for
it: every task passed its own accepts and the four-lights bug still shipped,
because nothing adversarial ever ran.

---

## 8. Where parallelism actually pays

**Bench evaluation — yes.** Tasks are independent; N hython workers score N
tasks. Embarrassingly parallel, no coordination.

**Role rotation — yes, but for separation, not speed.** CRUCIBLE must not be
the context that wrote the implementation, or it inherits the blind spots.

**Parallel task execution — no, not yet.** Two executors in one repo need
locking and merge policy. Today's bottleneck was never throughput; it was
task-card quality. Every failure traced to a card written poorly.

**Parallel hypothesis search — later.** Real autoresearch parallelism: N agents,
one incumbent, different hypotheses. Requires the metric first.

**Do the metric before the swarm.**

---

## 9. Sequence

| Phase | Work | Cost | Why here |
|---|---|---|---|
| **0** | Green the 7 red tests | hours | Nothing is trustworthy while tests are red |
| **1** | **CAPABILITY: build `set_expression`** + channel refs | 1–2 days | Removes the T4 wall. Nothing above it moves until this lands |
| **2** | GATE: symbol-table version, router init, scaffold honesty | 1 day | Known-correct; also the audit's trust issues |
| **3** | Build BENCH, run `--baseline` | 1–2 days | The metric everything else needs |
| **4** | GATE: SOP graph builder + SOP templates | days | The C+ domain, 80% of real work |
| **5** | BENCH loop overnight, ARCHITECT → FORGE → CRUCIBLE | ongoing | The compounding part |
| **6** | Parallel bench workers, then parallel hypotheses | later | Only once 0–5 hold |

**Phase 1 before Phase 3.** Benchmarking a wall produces a flat zero and a
loop that learns nothing. Build the capability, then measure it.

---

## 10. The failure this is built to prevent

2026-08-03 produced four instances of one shape: **a claim asserted where
nothing was observed.** Four lights (count knowable, never checked).
`fidelity=0.0` (cause recorded, never surfaced). Density (property set, never
repolished). The marshal (thread measured, never acted on).

An autonomous loop optimising an unmeasured objective is that bug with a
budget. Perturbation testing is the answer: the loop cannot claim a network is
procedural without moving something and watching the network respond.

**Unmeasurable is not zero. It is unknown, and it is excluded.**
