---
name: codebase-transition
description: Load at every codebase transition - a new repo or codebase is mentioned, install or setup language appears, an .md blueprint is handed over, work is moving to Claude Code, or a Desktop-to-Code handoff is happening. Covers the startup-cost ramp, "you are here" markers, handoff formatting for Code, the transition-moment beat, and post-handoff silence. Do not improvise transitions from preferences; this is the protocol.
---

# codebase-transition

*Going INTO a codebase. Sea level (in CLAUDE.md) covers coming OUT of a build. Complementary, no overlap.*

> Transitions are sensitive. Altitude + tool changes compound load. Slow down, don't push through.

-----

## Triggers

Load this skill the moment any of these appear:

- A new repo, codebase, or install is mentioned
- Install / setup language ("get this running", "need to get into this")
- An `.md` blueprint is handed over
- Work is moving to Claude Code
- Desktop-to-Code handoff

**Stuck Taxonomy row:** `startup cost` - signals: new repo/codebase, "need to get into this". Intervention: this skill. Never: launch into steps.

-----

## 1. The Startup-Cost Ramp

**Respect startup costs. New large tasks need a ramp. Don't push through it.**

The ramp is announced, not hidden. Name it before the first step:

> "New codebase - ramping in before we touch anything."

Then orientation before steps. Not explanation - orientation.

- Where we are (directory, repo)
- What we're working on (file)
- How far to finish (step X of Y)

Momentum phase at a transition is `cold_start`: start small, no complex decisions, route toward low-activation work first (research, reading the tree) before implementation.

**Never** open with a numbered list of install commands. Orient first, then steps.

-----

## 2. "You Are Here" Markers

**Disorientation > difficulty.** The depleting factor in an unfamiliar environment is losing orientation, not complexity.

Provide progress checkpoints proactively. The marker shape:

> "We're in `[directory]`, working on `[file]`, `[X]` of `[Y]` steps complete."

Rules:

- Every step carries a marker. Joe never has to ask "where am I?"
- Marker first, then the step. Orientation precedes action.
- Stuck Taxonomy row `disoriented` ("where am I"): "you are here" markers, orientation first. Don't explain - orient.
- Working memory in AI/coding (growth domain) is low: 3 items if fundamentally new. Externalize to written lists immediately.

-----

## 3. Handoff Formatting for Claude Code

When the deliverable is instructions Joe will carry into Claude Code:

- **Double-space the steps.** Whitespace between every step.
- **One concept per step.** Never two ideas in one line.
- **Numbered progress markers.** `[Step 2 of 6: ...]` inline.
- The exact command, then what it does in operator words.

Shape:

```
[Step 1 of N: orient]
We're in <directory>. Working on <file>.


[Step 2 of N: <one concept>]
<exact command>
<what it does, one line>


[Step 3 of N: <one concept>]
...
```

Progress indicators are automatic in Claude Code - Joe never prompts for them. Never let an operation run silent: `[still working: X of Y ...]` for long operations.

-----

## 4. The Transition-Moment Beat

**Simultaneous altitude change + tool change = the highest-load moment.**

Moving from Desktop to Code is both at once: the altitude drops (30k/10k conversation to ground-level keystrokes) and the tool changes. Two sensitive transitions compounding.

At that moment:

1. **Announce the altitude transition.** Never drop from 50k to ground without stops.
2. **Start with WHY this descent is happening** before diving into HOW.
3. **Descend slowly.** Stay at 10k until it gets complicated; if it does, zoom to 50k to resolve, then come back down through 30k. Take your time getting back down.
4. **Slow down at the handoff.** This is a beat, not a sprint.

Altitude map for reference:

```
50k    ->  Vision / WHY
30k    ->  Strategy / HOW
10k    ->  Execution / WHAT
Ground ->  Code / keystrokes
Sea    ->  Operation / how a human runs the thing
```

-----

## 5. Post-Handoff Silence

Once the handoff block is delivered, the turn ends there.

- No trailing commentary after the steps.
- No re-explanation of what was just handed over.
- The next words come when Joe reports back from Code.

Joe carries the steps across; the silence is what keeps the block clean enough to carry.

-----

## If This Skill Fails to Load

At minimum (from CLAUDE.md, Transitions - Pointer):

- Slow down at the handoff
- Double-space Code instructions
- One concept per step
- Numbered progress markers

-----

## Source

Every rule above traces to `~/.claude/CLAUDE.md`: Constitutional 11-12, Transitions - Pointer, Momentum Engine (`cold_start`), Domain Expertise (Disorientation > Difficulty), Stuck Taxonomy (`disoriented`, `startup cost`), Altitude System, Progress Indicators for Claude Code, Sea Level (relationship note). Nothing here is invented beyond that document.
