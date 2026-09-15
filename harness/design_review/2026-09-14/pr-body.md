**Nothing is built here.** One file, no code. This PR exists to be a place you can rule from — the sixteen design questions that have been measured as far as measurement takes them and now need your word.

They were spread across four notes written for four different purposes and never reconciled into one list. Now they are one list.

## How to rule

Comment on this PR with the item id and your word. One line each:

```
A1 ratify
B1 keep the accent, retarget the pin
C4 fallback
```

Anything you don't name stays open. **You are not expected to clear all sixteen.**

Merging this PR does **not** ratify anything — it just puts the roster in the tree. The rulings are your comments.

## If you only do one thing

**Rule A1** — airy is specification, not binding. It's the only item other items wait on. Answering it collapses A2, A3 and B2 from open questions into bookkeeping with a number attached. You already ruled it in J4 on 2026-09-05; the code has enforced it since. What never got the memo is several contracts and suites.

## Sorted by what it costs you, not by importance

**RATIFY — recommendation on file, one word closes it**

| | |
|---|---|
| **A1** | Airy is specification, not binding |
| **A3** | Bar D1 from the airy reclassification — its red is at standard too |
| **A4** | Add the pin J4 lacks (`_select_profile` has zero production callers) |
| **C5** | One counter, and it is the turn — four lenses converged unprompted |
| **C6** | The squared corner survives the ordinal; the full-bleed does not |

**FORK — a real choice, both legs cost something**

| | the tension |
|---|---|
| **B1** | The Doctor button's yellow vs "monochrome + one accent" — two of your own rulings |
| **B2** | J5's edge air vs BC-5's airy share — two of your own rulings, 13px apart |
| **C1** | `BORDER == SURFACE`: every hairline in the panel is invisible. Record it, or rule it |
| **C2** | The per-turn receipt line — and one placement ruling that must be explicit |
| **C3** | Square the receipt's corner — a card that stops reading as *waiting for you* |
| **C4** | The turn ordinal — 22–26px of a contested 264px column, or 0px and no scannability |

**ASSIGN — not a choice, a missing owner**

| | |
|---|---|
| **A2** | Encode BC-5's airy deficit as a number (−13px) with an owner |
| **D1** | The faces-stack 400px red — `+54 / +38 / +30`, red at **every** density |
| **D2** | R3-01's named remedy no longer exists — F1 retired the verb rail |
| **D3** | Two visible `← REVERT` controls on CHAT at once, 3/3 profiles |
| **D4** | `UNDO SENT` is authored and hidden in the same beat |

## Two things worth knowing before you read

**R1 and R2 are struck.** They shipped in v5.70.0 today — the tool-label fallback and the four dead curated keys, with the registry-reading guard R2's own conditions demanded.

**B1's instrument is coarser than the rule it enforces.** The monochrome test names three allowed *tokens*, but SIGNAL (210.8°) and its own sanctioned ink (205.7°) straddle a 15° bucket boundary, so the ink silently eats a slot. Even with the Doctor yellow gone, the count sits at exactly 3 with zero headroom. And it isn't a SYNAPSE defect: the same instrument run over the Pentagram Cohere board finds its PARAMETERS column at two buckets `[18, 19]` — a single orchid accent split across a boundary. **One of your four buckets is the instrument, not the design.**

## What is deliberately not on the list

A section at the bottom keeps the four items that look like design calls and aren't — so nothing quietly goes missing:

- **The `row` KeyError** is a product defect, not a ruling. Both F12 options delete a key that `chat_display.py:190-191` hard-indexes, and F12's own acceptance probe greens on exactly the deletion that breaks the transcript. Not gate joe.
- **SUBTRACT and SYSTEM are not mutually exclusive.** The README's "only one can land" is pre-crucible framing that was never updated; `SCAFFOLD.html` §7 supersedes it inside the same document.
- **The live 340px dock beside the network editor** stays blocked on a GUI seat.
- **Three seat reds** are undiagnosed rather than contested, and are named as such.

## Verification

Every `file:line` citation was re-checked against HEAD before commit. Two were corrected in the process — one line number, and one claim that put the REVERT verb's identity hedge in a docstring when it's in the prompt text itself. That correction makes the point better: the code already asks the model to verify an identity it was never given.

Every pixel number was measured under hython 22.0.400 offscreen with the bundled fonts loaded at devicePixelRatio 1. HiDPI is **UNKNOWN** and was not inferred.

---

Sources reconciled into this roster: `DECISION-BRIEF.md` · `AIRY-ANSWER.md` · `REFINEMENT-COHERE.md` · `harness/notes/v2-waves-2026-09-14/SEAT-CONFLICTS-FOR-JOE.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01XgRyALnfufUs8t3Zk5B6yD
