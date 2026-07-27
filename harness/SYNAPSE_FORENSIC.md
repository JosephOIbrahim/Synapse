# SYNAPSE — FORENSIC

**Harness ID** `FORENSIC-01` · **Authored** 2026-07-27 · **Runs independently of every other harness**
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Ruled by** `harness/notes/CTO_RULINGS_01.md`

---

## 0 · The question, and why the obvious framing is wrong

Joe's question: *where is SYNAPSE, where does it seem to be going, and how could a mid-sized VFX
studio use it as a production tool — such that a Houdini artist finds it irrefutably positive?*

**A post-mortem needs a corpse.** SYNAPSE has **zero production users.** No artist has run it on a
shot. Every statement about "how a studio would use this" is currently a hypothesis with no
observation behind it, and a retrospective framing would produce confident narrative resting on
nothing — the same defect as the health report's *"ALIGNMENT RATING: 8/10"*, which this project
ruled out this morning for having no producer path.

**So: a PRE-MORTEM.**

> It is Q2 2027. A mid-sized studio ran SYNAPSE on real shots for one quarter and stopped.
> **What happened?**

That question is falsifiable. It forces named failure modes with mechanisms, and each one can be
checked against the codebase today. "Strategy" cannot be checked against anything.

### And "irrefutably positive" is not achievable — the honest target is different

No tool is irrefutable. Artists reject good tools for bad reasons and keep bad tools for good ones.
What is achievable, and what this harness aims at:

```
LEGIBLE VALUE      an artist can tell, in one session, what it did for them
SURVIVABLE FAILURE when it is wrong, the shot is not lost and the artist knows immediately
NO NEW BURDEN      it does not add a thing to remember, configure, or babysit
```

A tool with those three is adopted. A tool missing the second is uninstalled after one incident,
however good the first is.

---

## 1 · The evidence tiers, and the rule that governs this harness

This is a strategy harness, which makes it the **most** vulnerable to unfounded confidence, not the
least. Every claim carries a tier:

```
OBSERVED    measured in this repo, or read from a primary source, with an anchor
REPORTED    a third party states it — cite who, and treat marketing as marketing
INFERRED    reasoned from OBSERVED facts — show the reasoning
ASSUMED     believed, unverified. LEGAL, and must be LABELLED.
```

**An unlabelled ASSUMED claim is the failure mode of this entire harness.** Five days of rulings
say the same thing in different subsystems: a judgement written in the grammar of a measurement is
more misleading than an obvious guess.

---

## 2 · Miles

```
S0  scout        READ-ONLY, research-first. What is OBSERVABLE about the floor,
                 the market, and what kills tool adoption in VFX pipelines.
S1  inventory    What SYNAPSE actually DOES today, per tool, mapped to real
                 artist tasks. Repo-grounded, zero speculation.
S2  pre-mortem   It failed. Why? Ranked by likelihood, each with a mechanism
                 that can be checked against the code TODAY.
S3  the plan     What makes it novel — DERIVED from S0-S2, never asserted.
```

**S0 first and alone.** The research is the only part not already in the repository, and doing it
after forming a view produces confirmation rather than evidence.

**S2 is the leg that matters.** A ranked list of specific, mechanism-bearing failure modes is worth
more than any positioning document, because each entry is either fixable or it is a known limit —
and both are actionable in a way that "we should emphasise memory" is not.

---

## 3 · What is already OBSERVED, so no leg re-derives it

Carried from five days of audits. Anchors in `CTO_RULINGS_01.md`.

**Working, verified:** in-process `hou.*` access; the WebSocket bridge on 9999; the render-node
boot refusal (`hou.isUIAvailable()`, the Fork Bomb guard); undo GROUPING; five Solaris tools
reachable; 4,989 gate tests; Moneta backend on.

**Broken or absent, verified:** PDG rollback raises `TypeError` on every call; no render cancel
from `RopNode` (`rkill` works, unused); emergency halt unsurfaced; 41 deprecated node types in
use, 39 invisible to a runtime probe; three COP tools are scaffolds that build topology and never
cook; 41% of panel affordances ORPHAN or SILENT; grounding 18.3% LOP / 6.2% COP.

**Unknown, and it matters:** what a token turn costs (C1 is measuring); whether any of this
survives contact with a real shot.

---

## 4 · Standing rules

- **No claim without a tier.** OBSERVED / REPORTED / INFERRED / ASSUMED, per claim, not per section.
- **Marketing is REPORTED, never OBSERVED** — including SideFX's, including ours.
- **A number without conditions is not a number** (Law 2, R31).
- This harness produces **findings and a ranked plan**. It does not edit product code.
- Never push, never merge, never tag.
