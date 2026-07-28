# SYNAPSE — ECONOMIST

**Harness ID** `ECON-01` · **Authored** 2026-07-28
**Governs** the token-economist axis of `synapse_economist_blueprint.md`
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Ruled by** `harness/notes/CTO_RULINGS_01.md`
**F3** — this document commits before the execution it governs.

---

## 0 · The premise that must be checked before Mile 1 is built

The blueprint's Mile 1 is T.1: reduce the tool surface from **17,310 tokens to ≤ 2,000**, on the
reasoning that *"you cannot be a credible token economist while your own tool surface runs 8.6×
over its ceiling."*

**The reasoning is right and the number may be measuring the wrong thing.**

Anthropic's prompt caching charges a cache **write** at 1.25× and a cache **read** at 0.1×. Tool
definitions are the most cache-stable content in any request — byte-identical every turn, at the
front of the prompt, which is exactly where a cache prefix wants to be.

```
uncached          17,310 per turn          8.6x over ceiling
cached (read)     ~1,731 effective         UNDER the ceiling
```

**Those are opposite engineering programmes.** One is a months-long surface reduction. The other
is a cache-control header. And the difference between them is a single measurement nobody has
taken.

This is the same shape as three findings already in the rulings: C1 refuted *"cost stays flat"*
by measuring it, S0 refuted the H22 AI floor by probing for it, and I1 refuted my own Copernicus
count by re-deriving it. **A governing number that has never been measured under the conditions
that actually apply is a hypothesis wearing a unit.**

So `E0` runs first, alone, read-only. It does not shrink anything.

---

## 1 · What this harness inherits, and what it must not repeat

**The multi-agent pattern has failed three times in two days.** R78: two H6 agents ran 70 minutes
past their receipt. R91: LEDGER and H6 edited one function from separate worktrees. R134: four I1
windows, one of them overwriting another's calibration mid-run.

The pattern that has **worked** is sequential legs with fenced briefs, declared `touches`, and
dependency gating. Every green receipt in this project came from that shape.

**So "agent teams" here means legs that hand off, not agents that share a tree.** The dispatch
lock (R134) now refuses a second dispatcher; it does not make concurrent writers safe, and
nothing in this harness asks it to.

Where genuine parallelism helps — and it does — it is **read-only legs on disjoint questions**,
declared in `touches` and verified disjoint before dispatch. S0 and S1 ran that way successfully
while S2 waited on both.

---

## 2 · Miles

```
E0  cache + cost truth      READ-ONLY. Is the tool surface cached? What does a
                            turn actually cost? Settles T.1's premise.
E1  tool surface census     READ-ONLY. WHAT is the 17,310 - per tool, per
                            schema. Runs parallel to E0; disjoint touches.
E2  the reduction OR the    Gated on E0+E1. Which programme is right is E0's
    cache fix               finding, not this brief's assumption.
E3  probe layer             Availability, quota, latency, probe age. Returns a
                            structure. No panel work.
E4  verdict schema +        The structured object and the one free field.
    voice contract          Blueprint Mile 3 - a dependency of tier rotation,
                            not polish.
```

**Panel work is not in this harness.** T.4's freeze holds until E2 and E4 land, which is the
blueprint's own rule and the right one — a rail that reports a number the product cannot yet
produce is instrumentation ahead of its subject.

---

## 3 · The invariants this harness is accountable to

From the blueprint, restated as things a leg can fail:

1. **No model name in code.** Tier constants only.
2. **Availability colour is computed at render time** from probe age and quota. Never persisted,
   never typed.
3. **One dispatch spine.** Voice, typed and ⌘K enter through it.
4. **Every rendered decision carries a `by` block.** No anonymous work.
5. **Transcription never charges a token.**
6. **Register output is byte-comparable across tiers** for the same structured input.

Invariant 6 is the one that makes frontier rotation survivable, and it is why the verdict schema
is Mile 3 rather than Mile 7. **Rotate the tier manifest without it and every rotation is a
re-onboarding event.**

---

## 4 · Standing rules

- **Every number carries a producer path** (Law 2), and producers are `<leg>_<name>.py` — no
  leading underscore, which `.gitignore` silently discards (R132).
- **Every reader is calibrated before it is trusted** (R60), and its controls are mutation-tested
  (R133) — I1 found a control that pinned nothing by doing this.
- Commit product before the receipt (R93). Read committed paths, never worktree globs (R127).
- Declare `touches`; the orchestrator refuses intersecting legs (R92).
- Never push, never merge, never tag. Gate C is human-only.
