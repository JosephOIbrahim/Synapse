# SYNAPSE — CLAIMS

**Harness ID** `CLAIMS-01` · **Authored** 2026-07-27
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Ruled by** `harness/notes/CTO_RULINGS_01.md`
**Subject** the positioning document's SHIPPING claims

---

## 0 · Why this exists

The positioning document makes seven claims marked **Shipping**. It also says, correctly:

> *a technical evaluator will open the repo.*

So will we. This harness applies to the positioning exactly what the last four days applied to
the codebase: **every load-bearing claim gets a producer path, or it comes off the document.**

Roadmap items are exempt. They are honest by construction — they say what they are.

### The claims, and what is known about each today

| claim | marked | status |
|---|---|---|
| "Sends only what changed — cost stays flat, even on huge scenes" | Shipping | **architecturally sound, numerically unproven** |
| "Persistent project memory that carries across sessions and shots" | Shipping | true as of **2026-07-26**, presented as established |
| "Physically refuses to boot on a render node" | Shipping | **unverified — one probe away** |
| "Inside Houdini, native" | Shipping | true, and the strongest claim in the document |

**The first is the document's spine.** Everything else hangs off it, it leads the page, and it is
the number a studio will ask for first.

---

## 1 · The benchmark, from first principles

The claim is comparative: *ours is flat, theirs climbs with scene size.*

```
measurable   tokens per agent turn
variable     scene size
arm A        SYNAPSE, inside-out - sends the question
arm B        outside-in - sends the scene
control      same task, same scene, twice -> same count?
```

### Three ways this benchmark lies, and how each is closed

**Benchmarking a competitor's product is neither fair nor necessary.** We cannot run their code
honestly, and we do not need to. **Arm B is computable without them:** serialise the scene the way
an outside-in tool must, and count the tokens. That is not a claim about their implementation —
it is a floor on what *any* tool that sends the scene must pay. Stated that way it is defensible
and does not require reverse-engineering anyone.

**Flat cost on a failed task is not a feature.** A system that answers nothing has beautifully
flat token usage. **Every measurement pairs cost with outcome**, and a turn that failed its task
is reported separately, never averaged into the cost curve. This is the single thing that makes
the benchmark honest rather than flattering.

**Token counts are not deterministic.** Same task, same scene, twice — do they match? If not,
there is a noise floor, and it is *measured*, not assumed. Same discipline RETINA applies to
render deltas, for the same reason.

### The axis must be defensible

"Scene size" is not a number until it is defined. Candidates: node count, USD prim count,
`.hip` bytes, serialised-scene tokens. **The last is the one that matters for arm B**, and it
should be reported alongside whichever is chosen as the x-axis — a curve against an undefined
axis is a picture, not evidence.

---

## 2 · Miles

```
C0  claim census    READ-ONLY. every Shipping claim -> producer path or NONE
C1  token bench     the spine. instrument, ladder, both arms, paired with outcome
C2  render-node     one probe: does it actually refuse to boot on a farm node
C3  memory proof    does state genuinely survive a session boundary, demonstrated
```

C0 is cheap and gates nothing — it tells us how big the gap is before we start closing it.

**C1 is the leg.** C2 and C3 are each roughly an afternoon and each closes a Shipping claim.

---

## 3 · Standing rules

- **Every number carries a producer path and its conditions** (Law 2, R31). A token figure
  without model, scene, task and date is not a figure.
- **A check must be able to fail** (Law 1). The benchmark must be demonstrated producing a
  *non-flat* curve for arm B, or it has not shown it can measure a difference.
- **Cost is never reported without outcome.** Non-negotiable.
- Commit product before the receipt (R93). Declare `touches` (R92).
- Never push, never merge, never tag.
