# REACH — Blueprint, from first principles

> **Provenance:** authored by Joe (Creative Director) and pasted into the
> harness-architect dispatch on **2026-08-18**. Grounded against the
> fAI-vs-SYNAPSE dossier (compiled 2026-08-18), the live repo at **v5.52.0**,
> `harness/DESIGN.md`, `BLUEPRINT_WEAK_DOMAINS.md`, and the governance model in
> force. Execution state lives in `harness/reach/STATE.json`; the conductor is
> `.claude/agents/reach-orchestrator.md`; the dispatch mechanism is the dynamic
> workflow `.claude/workflows/reach.js`. This file is the spec — it is read,
> never rewritten by the harness.

Written in the harness's own idiom: **GATE / CAPABILITY / BENCH**, perturbation
over structure, evidence artifacts over assertions, **unmeasurable ≠ zero**.

**Provenance, stated before anything is built on it:**

- The dossier's **fAI claims** are single-source (vendor site, storefront,
  changelog, retrieved 18 Aug 2026). *Reported, not measured.* Nothing below
  depends on them being exact — the **shape** of the gap is what is load-bearing,
  and the shape is confirmable from SYNAPSE's own side without touching fAI.
- The dossier's **SYNAPSE claims read the public face** (README v5.5.0, April
  2026), not the runtime (v5.52.0, H22.0.400, 3 open P0s). It says so itself.
  Where public face and runtime disagree, that disagreement is **finding #1**,
  not a mistake in the dossier.

---

## 1. First principles — what the dossier actually observed

Strip the competitive framing. There are three claims, each independently
checkable, and each one is a rule SYNAPSE already holds — pointed somewhere it
has not yet been pointed.

### 1.1 Unreachable capability is UNKNOWN, not present

The constitution's oldest rule is *unmeasured renders UNKNOWN, never zero and
never an estimate.* It is enforced against renders, cook times, and now all
output kinds. It has never been enforced against **the product**.

A capability only the author can run has a measured user population of one, and
that one is the author — the least independent instrument in the building. The
2,874 tests measure whether the code does what the code says. They do not measure
whether anyone else can reach the code. That number is currently **UNKNOWN**, and
by SYNAPSE's own rule, UNKNOWN is not a small green.

> **The installer is not a marketing act. It is an instrumentation act.**

### 1.2 SYNAPSE is afferent-only — sensors wired, effectors absent

The dossier's sharpest line is *"eyes with no reflex attached."* Structurally it
is stronger than that: SYNAPSE has a complete sensory path and **no motor path**.

- Cook completion pushes a typed event → nothing is bound to it.
- Work items land → nothing is bound to them.
- Reasoning appends to USD, in order, with alternates as siblings → nothing reads
  it back to the artist.

Three of the six gaps are the *same missing half*, seen three times. That is not
three features. It is one architectural absence with three symptoms, and it
prices accordingly.

### 1.3 The public artifact is a claim; the runtime is truth; drift is a finding

This is the exact defect class already prosecuted twice in this repo:
`apex_probes.py` stamped **H21.0.671** while running under H22; the symbol table
stamped **22.0.397** against a running **22.0.400**. The README lag is that same
bug wearing a marketing shirt — a claim that was true once and silently aged.

The remedy is the one already built: `verify/version_agreement.py` makes drift a
**red check**, not a discovery. Extend its contract to public artifacts and this
failure class closes permanently rather than being manually re-noticed each
quarter.

> **Note before spending on it:** the README was rewritten 2026-08-17 at v5.52.0.
> The dossier's snapshot may predate that. *Verify current public state before
> booking work — do not fix a thing that closed yesterday.*

### The corollary the whole blueprint hangs on

> **Depth is unfalsifiable until it is reachable.**
> Every priority below is ordered by how much **evidence** it unlocks, not by how
> much **capability** it adds.

That single sentence resolves the apparent tension in the dossier — "SYNAPSE is
ahead on everything underneath" and "nothing else matters until a stranger can
run it" are not in conflict. Depth is real and unmeasured. Reach is the
instrument that measures it.

---

## 2. The six gaps, restated as testable claims

| # | Dossier phrasing | Testable form | Workstream | Cost class *(estimate — unmeasured)* |
|---|---|---|---|---|
| **R1** | "An install a stranger can finish" | On a machine that has never seen SYNAPSE: how many discrete human steps to first agent response? Does it complete without editing a file by hand? | **GATE** | Small |
| **R2** | "The public face is four months stale" | Does the public artifact's claimed version equal the tagged version? Binary. | **GATE** | Hours |
| **R3** | "Broader version and licence coverage" | For each (Houdini build × licence tier × OS): runs / fails / **UNKNOWN**. Today the honest matrix is one cell green and the rest unnamed. | **GATE** | Hours + hython time |
| **C1** | "Scheduled work, one finished step starting the next" | Given a typed event and an armed binding, does the bound act fire, exactly once, with the failure path halting rather than continuing? | **CAPABILITY → BENCH** | Small–moderate |
| **C2** | "A skill library — teach it once, it keeps the method" | Same prompt, skill absent vs present: does the emitted graph change, and does the changed graph cook where the other didn't? | **CAPABILITY → BENCH** | Moderate |
| **C3** | "A job list that outlives the session" | After a host restart, does the board still show what ran, what failed, and the **real** Houdini error — with unmeasured cells rendering UNKNOWN? | **CAPABILITY** | Small–moderate |
| **C4** | "Fenced connections to everything outside Houdini" | Can a named, typed action reach FFmpeg/farm/Nuke **without** an open command channel existing anywhere in the path? | **CAPABILITY** | Moderate |
| **C5** | "Runs on models other than Claude" | At what response-schema width does the local leg's grammar fail? That number is the portability budget. | **CAPABILITY + measurement** | Moderate |

Note the asymmetry, and it is the same asymmetry as the APEX blueprint's W3:
**R1–R3 are GATE, not BENCH.** Each has one right answer obtainable by doing it
once. Hill-climbing them would be strictly worse. C1–C5 carry real gradients —
chain depth, skill coverage, schema width — so they carry bench weight.

---

## 3. The skill library, from first principles

This is the one flagged for elevation, so it gets built from the ground rather
than copied from the dossier's summary.

### 3.1 What a skill actually is

A skill is **an opinion about how to do something**, plus the evidence it worked,
plus **the build it was proved against**.

Drop any of the three and it degrades into something already known to fail here:

- Opinion without evidence → a hoped-for capability (the scaffold problem).
- Opinion with evidence but no build stamp → `apex_probes.py`, June edition:
  verified once, silently aged.
- Evidence without opinion → an artifact nobody consumes.

> **A skill that cannot name the build it was verified against is a hypothesis
> wearing a method's clothes.**

### 3.2 Three properties any skill system must have — SYNAPSE has two and a half

**(a) Storage with variants.** A method has alternates: the fast way, the safe
way, the studio's way. USD stores structured documents with variant sets. Already
built, already the memory substrate. **Free.**

**(b) A total order over competing opinions.** Every skill system in the
comparable landscape invents this: a priority integer, a "most recent wins" rule,
a scoring function. All of them are ad hoc and all of them are non-deterministic
under conflict.

USD already has a total order over competing opinions, and it is the one thing
SYNAPSE's substrate carries natively:

> **Skill precedence is LIVRPS, not a priority integer.**
> Studio method **sublayers**. Project method **references**. Shot override is a
> **stronger local opinion**. Composition resolves it, deterministically, the
> same way it resolves everything else in the stage.

That is not a clever mapping — it is the mapping the substrate was chosen for.
It also means precedence is *testable*: two conflicting skills, one prompt, one
predicted winner, binary assert. **Free, and it is the moat.**

**(c) Membership honesty — a skill cannot name something that doesn't exist.**
This is the phantom-namespace failure (`apex::rig::`, `apex::sop::`) with a new
delivery vector: instead of the model inventing a node type, a *written method*
carries one forever. Worse than the original bug, because a document looks
authoritative.

The armour already shipped in **APEXFORGE WA1**: the catalog-membership goalpost
test, which fails loudly on a missing catalog artifact and makes phantom-name
emission structurally unshippable. Point it at the skill corpus and skills
inherit phantom-immunity **on day one**. **Half free** — the test exists, the
wiring to the corpus does not.

**What is actually missing is the loop:**

```
author → install → compose → resolve → apply → verify → stamp
```

Six of seven arrows have a substrate underneath them. None of them are connected.

### 3.3 The collapse — skills and the weak-domain waves are one roadmap

The weak-domain wave sequence is: **A** COP de-stub · **B** DOP sim doctor ·
**C** VOPs/CHOPs/L-systems · **D** KineFX mechanical · **E** APEX recipe corpus.

The dossier names fAI's shipped method domains: Solaris/USD, COPs/Copernicus,
KineFX, procedural curve rigs, Gaussian Splats, materials, cameras, lighting,
rendering.

Those are the same list. Which means:

> **A wave and a skill are the same work seen from two ends.**
> The wave is the cook that proves the domain. The skill is that proof written
> down so the next run doesn't depend on the model remembering.

The skill loop is therefore **not a seventh workstream competing with the wave
sequence**. It is the wave sequence's *delivery format*. Every wave that closes
without emitting a skill has thrown away the transferable half of its own output.

**Consequence for sequencing:** the loop must land **before** Wave A, or Wave A's
output has nowhere to go. That is the argument for promoting it — not that it is
more valuable than the installer, but that it is **upstream of work already
scheduled**.

### 3.4 The corpus is not a cold start

Six domain methods already exist in prose, authored and used for months:
`solaris-usd-composition`, `vex-pattern-library`, `pdg-tops-patterns`,
`materialx-cross-renderer`, `houdini-performance-profiling`, `hdk-build-recipes`.

They map onto the wave sequence close to 1:1. The authoring practice — what a
method contains, how it is scoped, when it triggers — has been running at
production volume already. **What is absent is the in-Houdini resolution layer,
not the corpus and not the craft.**

This is transposition, not invention. It is also the single largest de-risking
fact in this document, and it is the reason the skill loop's cost class reads
*moderate* rather than *large*.

**Honest caveat:** transposition is not free. A Claude-side skill triggers on
conversational intent; a SYNAPSE-side skill must resolve against a **stage** and
emit **catalog-valid node types**. The prose survives; the trigger model and the
membership check are new. Budget the transposition, don't assume it.

---

## 4. GATE — binary work, first

Binary accepts. Done before any bench run, in this order.

### R1 · Cold-start install
One artifact that performs clone, config, key prompt, and **verification** — the
verification step is the part that matters, because an install that completes
silently and fails at first prompt is worse than one that fails loudly at step 2.

- **Measure in steps a stranger takes, not minutes.** Minutes are the author's
  metric; steps are the stranger's. Every hand-edited file is a step. Every
  environment variable is a step. Every "restart Houdini" is a step.
- **Goalpost:** clean machine → first agent response, no file authored by hand,
  step count recorded in the artifact.
- **The clean-room leg is human** — a container proves the script runs; only a
  machine that has genuinely never seen SYNAPSE proves the install works.

### R2 · Public-face agreement
Extend `verify/version_agreement.py` to cover public artifacts: README claimed
version == tagged version, or red. Byproduct, at no extra cost: **the changelog
is not new work — it is the existing `bump, verify, tag` ritual's output,
published.** The dossier calls a visible changelog "nearly free"; it is free.

### R3 · Reach matrix
`reach_matrix_<date>.json` — (Houdini build × licence tier × OS), each cell
**runs / fails / UNKNOWN**. Today's honest state is one cell green (22.0.400,
Windows) and the rest **unnamed**, which is worse than UNKNOWN: an unnamed cell
can't be planned against.

Apprentice and Indie tiers matter disproportionately — they are where beta
testers actually live, and the **Gate A L3-5 Apprentice session** is already an
outstanding human task. Same work, two purposes; do it once.

---

## 5. CAPABILITY — the five builds

Each produces a versioned evidence artifact, following the pattern that already
works (`lop_truth_<build>.json`, `apex_truth_<build>.json`).

### C1 · Reflex — event → action binding, and the constitutional wrinkle

The build is small: typed event → predicate → named dispatcher action. The
sensors exist; the dispatcher exists; the binding does not.

**The wrinkle is not technical and it must be solved first.** An overnight loop
executes acts *while no human is present*. The constitution is unambiguous:
merge words, pushes, `drop.json` writes, ratified flips, tags and publishes are
**per-act human words**, never banked, never relayed through an agent message.
A naive scheduler is a machine for banking human words.

The resolution already exists in the governance model: **blanket pre-approval is
prohibited; enumerated batches with explicit execute direction are valid.**
Therefore:

> **Arming, not scheduling.**
> A human arms a chain by enumerating it — *these steps, this scene, this
> night.* Anything the chain encounters that is not in the enumeration **halts
> and waits**. The chain cannot widen itself, cannot promote an amber act to
> green, and cannot substitute a step.

Two hard properties fall out, and both are testable:

- **Fail closed.** A failed step halts the chain and reports the *real* error. It
  never continues, and it never summarises the error away — that is the exact
  round-trip loss that "inside Houdini, not beside it" was built to avoid.
- **Exactly once.** A typed event that fires twice must not run the bound act
  twice. Idempotency is a bench rung, not an assumption.

Constitutional acts (push, tag, publish, drop) are **never armable**. If a chain
ends at a governed act, it ends *at* it — producing the artifact and stopping,
with the human word still required. That is not a limitation to work around; it
is the feature that lets the overnight loop exist at all without breaking the
model that keeps this project honest.

### C2 · Skill loop
The seven arrows from §3.2, with three non-negotiable properties:

1. **Precedence is composition.** No priority integers anywhere in the
   implementation. If two skills conflict, the stage resolves it.
2. **Membership is enforced.** Catalog-membership goalpost applied to the corpus;
   a skill naming an absent type fails to install, not at run time.
3. **Every skill carries its stamp.** Build verified against, date, evidence
   artifact reference. Unstamped skills load in **hypothesis** mode and say so.

Evidence out: `skill_corpus_<build>.json` — installed skills, their stamps, their
resolution order, their last verification.

### C3 · Job board — where UNKNOWN becomes visible

The dossier's most useful sentence about SYNAPSE's own principle:
*a principle the artist can't see doesn't count for anything.*

The board is the first place where UNKNOWN discipline stops being an internal
virtue and becomes the visible product difference. A competitor's board shows a
number. This board shows **UNKNOWN** where nothing was measured — and that is the
thing worth naming loudly, because it is the thing an artist learns to trust.

**One design constraint, derived rather than copied:** the board must survive a
host restart, therefore its substrate must **outlive the host process**,
therefore the board is a **file** (append-only, already in USD) and any future
surface — browser page, phone — is a **reader**, not a service.

That constraint costs nothing today and buys the "second surface" item outright
later. Take it now; it is free only before the board is written.

### C4 · Outward dispatch, fenced
The dispatcher is already the right shape: a fixed set of named, typed
operations. It points inward. Pointing it outward is a **direction** change, not
an architecture change.

The fence is the safety story and it is stated in the negative:
**no open command channel exists anywhere in the path.** A named action can be
called or refused; it cannot be talked into being a different action. This holds
under adversarial prompting in a way that a shell wrapper never can.

First pass is **red tier** — anything that writes outside the repo or the scene
is human-gated until the fence has been attacked on purpose by CRUX.

### C5 · Portability seam, and the number that governs it
The wall is procurement, not preference: a studio that cannot send scene context
to a third party cannot use SYNAPSE at all.

The design already exists (small local model triaging, stronger model reasoning).
The swap point does not. But the important part is the constraint the dossier
pulled out of fAI's changelog, which is a genuine engineering finding and free to
inherit:

> **Local models fail when the required response format exceeds their grammar.**
> Therefore portability is not a model swap — it is a **schema-width budget**.

That budget is measurable. Bind the local leg to progressively wider response
schemas until it fails; the width at failure is `grammar_ceiling`, it goes in an
evidence artifact, and every future contract on the local leg is checked against
it. Until it is measured, local-leg support is **UNKNOWN** and is claimed as
UNKNOWN.

---

## 6. BENCH — perturbation, the reach edition

DESIGN.md §4, instantiated: *a literal-wired network does not move; a
procedurally-coupled one does.* The same test applies to skills and reflexes,
and it is what separates a skill library from a folder of documents.

| Rung | Task | Perturb | Assert changed |
|---|---|---|---|
| **S1** | Same prompt, one weak domain | skill **absent → present** | emitted graph structure differs **and** the skill-present graph cooks where the other didn't |
| **S2** | Two conflicting skills on one prompt | which arc is stronger | predicted skill wins, deterministically, repeat-2 identical |
| **S3** | Weak-domain rung (Wave A: COP de-stub) | written method applied | real cook, real measured output — not a scaffold's return value |
| **S4** | Reflex chain, depth 1 → 2 → 3 | inject failure at step 2 | chain **halts**, real error preserved, step 3 never runs |
| **S5** | Armed chain, event fires twice | duplicate event | bound act runs **exactly once** |
| **S6** | Same skill, cloud leg → local leg | response schema width | `grammar_ceiling` recorded; contract narrower than ceiling passes, wider fails **loudly** |

**Scoring:** existing `competence = Σ(weight·passed)/Σ(weight)`.

**Weights, per the audit posture:** heaviest on **reach and reflex** (absent
today), heavy on **skill precedence** (the differentiator, and the thing that
silently rots if untested), medium on weak-domain cooks, **lightest on substrate
depth** — which is where SYNAPSE is already strong. Weighting toward existing
strength is the classic benchmark mistake (DESIGN.md §5) and would produce a
flattering number that measures nothing.

S3 and S6 touch live cooks and a live local model: `.synapse/hytest.py` shim
discipline applies, **skip ≠ pass**, and anything needing eyes on a live viewport
is **autonomy: red**.

---

## 7. Contracts to author (`.synapse/contracts/`)

| Contract | Tier | Goalpost sketch |
|---|---|---|
| `reach-install-coldstart.yaml` (R1) | green + **amber human leg** | script completes unattended in clean container; step count recorded; genuine clean-machine run human-verified |
| `reach-public-agreement.yaml` (R2) | green | README claimed version == tag; drift is red; changelog emitted by the tag ritual |
| `reach-matrix.yaml` (R3) | green | every (build × tier × OS) cell is runs/fails/**UNKNOWN**; **an unnamed cell fails the contract** |
| `skill-loop.yaml` (C2) | green | author→install→resolve→apply round-trips; precedence deterministic under repeat-2 |
| `skill-catalog-membership.yaml` (C2) | green | inherits APEXFORGE WA1 goalpost: no skill emits a type absent from the catalog; missing catalog artifact fails loudly |
| `skill-stamp.yaml` (C2) | green | every installed skill carries build + date + evidence ref; unstamped loads in hypothesis mode and announces it |
| `reflex-arming.yaml` (C1) | **red** | arming is a per-act human word; enumerated batch only; chain cannot widen itself; halts on non-enumerated act |
| `reflex-failclosed.yaml` (C1) | green | injected failure halts chain, real error preserved verbatim, downstream never runs; duplicate event runs act once |
| `board-persistence.yaml` (C3) | green | board survives host restart; unmeasured cells render UNKNOWN; **zero estimated values anywhere on the surface** |
| `dispatch-outward.yaml` (C4) | **red** | fixed named actions only; goalpost proves no open command channel exists in the path; CRUX attacks it before green |
| `portability-grammar.yaml` (C5) | amber | `grammar_ceiling` measured and recorded; local-leg contracts checked against it; unmeasured = UNKNOWN, never assumed-supported |

Worker entry unchanged: `python .synapse/harness.py run --autonomy <tier>
--budget <N>`.

---

## 8. Priority order — and where it departs from the dossier

The dossier's order is **installable → reflex → skill loop**. That order is
right. Its stated reason is one step short, and the missing step changes what
gets built in parallel.

**Stated reason:** installer first because it unlocks beta testers.
**Actual reason:** installer first because **every other priority's evidence is
unobtainable without it.** With N=1 and the author in the loop, you cannot
measure whether a skill helped, whether a reflex is trustworthy, or which weak
domain matters most. The installer is the instrument. Everything downstream is
measurement, and unmeasured is UNKNOWN.

That reframe produces one concrete change:

> **The skill loop does not wait for the installer.**
> Its correctness goalposts are entirely internal — precedence determinism,
> catalog membership, stamp presence. None of them need a stranger.
> What needs strangers is **ranking which domains to write methods for**.

So: **build the loop now, in parallel; fill the corpus after reach lands.** The
loop is upstream of Wave A (§3.3) and Wave A is already scheduled — the schedule
forces the promotion regardless of the competitive argument.

The final ordering:

1. **R1 installer** — sequential, first, blocking. Nothing else produces
   trustworthy evidence until it lands.
2. **C2 skill loop** — parallel with 1. No external dependency. Upstream of
   Wave A. Corpus seeded from existing prose methods (§3.4).
3. **C1 reflex** — after the arming contract is ratified, not before. The
   governance design is the long pole; the code is small.
4. **C3 board** — small, and it is where UNKNOWN discipline becomes visible.
   Take the file-not-service constraint while it is still free.
5. **R2 / R3** — hours each, slot into any gap. R2 may already be closed.
6. **C4 outward dispatch** — after CRUX has attacked the fence.
7. **C5 portability** — measure `grammar_ceiling` before claiming anything.

**Not in the list, deliberately:** the second surface (browser/phone) is bought
by C3's file constraint rather than built. Reference-image input is a **type
addition to the input contract**, not a feature — it lands when the contract is
next opened, and costs a row. Neither earns a slot of its own.

**Interaction with open P0s:** B1/B2/B3 remediation is not competing with this
list — it precedes it. Shipping an installer that hands strangers a cook
success-noop lie, an overstated reversibility claim, and a disabled worker-policy
gate would convert three internal findings into three public ones. **Close the
P0s, then open the door.**

---

## 9. Sequence

| Phase | Work | Cost *(estimate)* | Gate to next |
|---|---|---|---|
| 0 | B1–B3 P0 remediation | in flight | three P0s closed |
| 1 | R2 verify + R3 reach matrix | hours | honest coverage picture exists; UNKNOWN cells named |
| 2 | R1 installer + clean-room run | 1–2 days | a stranger reaches first response, step count recorded |
| 3 | C2 skill loop (parallel with 1–2) | 2–3 days | round-trip works; precedence deterministic; membership enforced |
| 4 | Corpus transposition, 2 domains | 1–2 days | two prose methods become stamped skills; S1 shows a real delta |
| 5 | `reflex-arming.yaml` ratified → C1 build | 1 day gov + 1 day code | armed chain runs overnight, halts correctly, fires once |
| 6 | C3 board | 1 day | status survives restart; zero estimates on the surface |
| 7 | C4 fence + C5 grammar ceiling | days | outward actions attacked and passed; portability budget is a number |

**Mile markers** — this is ~8 miles. Phases 0–2 are miles 1–3 and are almost
entirely *evidence and access*, no new architecture. Phase 3 is mile 4 and is the
first thing that changes what the agent can do. Phase 5 is mile 6 and is the
first night SYNAPSE works while nobody is watching. Phase 7 is mile 8.

The first number worth tracking arrives at phase 4: **S1's skill-absent vs
skill-present delta.** That is the number that says whether the biggest quality
lever in the dossier is real in this codebase.

---

## 10. The failures this prevents

**Building depth nobody can measure.** The UNKNOWN rule turned inward. 2,874
tests prove the code does what it says; they say nothing about reach, and reach
is currently unnamed rather than merely unknown. R1 and R3 convert an unnamed
quantity into a measured one, which is the only kind SYNAPSE is permitted to
report on.

**An overnight loop that banks human words.** The convenient version of C1 is a
scheduler that pre-approves a night's worth of acts — which is precisely the
prohibited pattern, arriving disguised as a feature request from a competitor
analysis. Arming-with-enumeration keeps the loop constitutional. *This is the
failure this document exists to catch:* every other item on the list is safe to
build fast.

**Skills that carry phantoms forever.** The June re-seed caught the model
inventing `apex::rig::` and `apex::sop::`. A written method carrying an invented
type name is the same bug with a longer half-life and more authority. The
catalog-membership goalpost already exists and makes the class unshippable —
wiring it to the corpus is the cheapest defence in this document.

**A portability promise that dies on schema width.** Claiming local-model support
before `grammar_ceiling` is measured is exactly the estimate-instead-of-UNKNOWN
failure, aimed at the one audience — locked-down studios — that will test it
hardest and tell everyone.

**A comparison lost on the public artifact rather than the runtime.** v5.52.0 is
four months ahead of what a prospective user reads. That is not a capability gap;
it is a version-agreement bug in the one file strangers actually see, and it is
already a solved defect class in this repo.

---

*Unmeasurable is not zero. It is unknown, and it is excluded — including when the
thing unmeasured is whether anyone but the author can run this at all.*
