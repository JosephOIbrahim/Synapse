# AGENTS.md — How agents work on SYNAPSE

> Law for every subagent, workflow leg, and orchestrator that touches this repo.
> `CLAUDE.md` says what SYNAPSE *is*. This says how you are allowed to *build* it.
> If the two disagree, `CLAUDE.md` wins and you file the contradiction.

---

## 0 · Prime directive

**Produce evidence, not confidence.**

Every claim you make must be traceable to something a hostile reader can re-run:
a file path with a line number, a probe artifact, a test name, a command and its
output. A sentence with no producer path is a rumor.

The single most expensive failure mode in this repo is not a bug. It is a
**green receipt for work that did not happen.** Everything below exists to make
that failure structurally hard.

---

## 1 · The Seven Laws

### Law 1 — Honest seam

A capability whose substrate is not installed reports `UNAVAILABLE` **with the
reason**. Never a fabricated `SUCCESS`. Never a guessed `BLOCK`. Never a
placeholder that returns the shape of an answer without the answer.

> A stub that returns `SUCCESS` is worse than no stub. No stub fails loud;
> a lying stub fails silent and takes a test suite hostage with it.

### Law 2 — Absence has a shape

Absence is a **measured fact**, not a missing feature — and *how* you degrade
depends on which side of the seam the absent substrate sits. See §2.

### Law 3 — Runtime is truth

A live-introspected surface beats a doc claim. A probe artifact beats a pinned
constant. If the doc and the runtime disagree, the runtime is right and the doc
is a bug you now own.

Before emitting any `hou.*` / `pdg.*` / `pxr.*` symbol you are not certain of,
call `synapse_scout`. Phantom APIs are this repo's #1 historical failure class.

### Law 4 — Unmeasured renders UNKNOWN

No estimates. No "should be roughly." An unmeasurable goalpost is written
`UNKNOWN` and the leg does **not** go green on it.

### Law 5 — Receipts or it did not happen

Every leg posts a receipt to its board's `bus/` before it reports done. The
receipt carries: what you touched, the command you ran, the artifact path, the
verdict, and what you could **not** verify. The last field is not optional, and
"none" is rarely the honest answer.

### Law 6 — One conductor per board

Before writing to a board (`STATE.json`, `bus/`), sweep for a live second run:
`git worktree list`, a PID check, and the mtimes in `bus/`. Two conductors
writing one board is a silent corruptor. If you find another run, **stop and
report** — do not merge your view over theirs.

### Law 7 — Human gates are per act (Article V)

These are **never** an agent's to perform, and **never** relayed through another
agent's message. Only the human's own word, for that specific act:

| Gated act | Why |
|---|---|
| `git merge` / `push` / `tag` | Origin is a **public** GitHub repo |
| `VERSION` edits, release commits | Six version surfaces must move together |
| Contract / blueprint ratification flips | Ratified text is law; flipping it is legislating |
| Substrate installs | Hanish / SALUS / Octavius / jacobian-monologue |
| Removing a registered MCP tool | Public API break for every downstream caller |
| Anything touching the live Houdini GUI | The freeze class is real and unrecovered |

A green receipt is a **precondition** for asking, never a substitute for the answer.

---

## 2 · Absence has a shape

The most-repeated design mistake in this repo is treating every absent substrate
the same way. They are not the same. Degrade by **which side of the seam** the
substrate sits on.

```
                   substrate absent
                          |
        +-----------------+-----------------+
        |                 |                 |
    READ-side         WRITE-side         GATE-side
   (Octavius)          (Hanish)           (SALUS)
        |                 |                 |
  degrade to the    durable local        FAIL CLOSED
  narrower TRUE     OUTBOX; return       never open,
  source, with a    UNAVAILABLE;         never "allow
  capability flag   drain when it        for now"
  on the payload    lands
```

**Read-side absent → narrow, don't fake.**
You still have a true but smaller source. Return it, and mark the payload with
what you could not do: `{"sanitization": "none", "source": "local_stage"}`.
The caller gets truth plus a known limit. It does *not* get a claim of
sanitization that never ran.

**Write-side absent → outbox, don't drop, don't fake.**
You cannot settle a claim with a substrate that isn't there. You *can* durably
record the unsettled claim locally and return `UNAVAILABLE`. Absence then costs
**latency, never truth** — when the substrate lands it drains the backlog.
This is exactly why every LOOP turn today is `EXPOSED` rather than fake-`HIT`.

**Gate-side absent → fail closed.**
A safety evaluator that cannot evaluate must not allow. An unevaluable path is a
blocked path. "Allow until the gate lands" is how a gate becomes decorative.

**Present-but-contended is a fourth case.** Moneta is *live*. Its failure mode is
not absence — it is **ownership**. See §3.

---

## 3 · Ownership boundaries

A live substrate with two owners is less safe than an absent one, because the
corruption is silent.

1. **One handle per storage URI, one owner per handle.** Before adding a store
   accessor, find the existing one. This repo has been bitten by *competing*
   singletons — two module globals, two keys, no shared authority. Adding a
   third authority is not enforcement; it is a third way to be wrong.
2. **The main Houdini thread owns store initialization and execution.** Every
   `hou.*` call goes through `run_on_main` / `hdefereval`. No exceptions, no
   "just this one read."
3. **The panel observes; it does not construct.** Panel code reads memory state
   over the WebSocket observation channel, or *peeks* an existing singleton
   without building one. `python/synapse/panel/health_strip.py` is the reference
   implementation of the disciplined read — copy its shape.
4. **Workers never hold a handle.** A worker that needs memory asks the host.

---

## 4 · Test discipline

### Never pin the brief's figure

A control whose expected value is copied out of the document under test passes
green while pinning that document's error. Derive expectations **independently**
— from first principles, from a second source, or from a hand-computed value
whose work you show.

> Repo precedent: a control asserted `161` because the brief said 161.
> The true value was 171. The test was green the whole time.

### The test must be able to fail

Before committing a test, break the code on purpose and watch it go red. A test
you have never seen fail is a decoration. Name the mutation in your receipt.

### Isolated green hides composed regressions

The bug is almost always on the **second** action, not the first. If your change
touches a sequence, test the sequence.

### Never weaken an assertion to make a suite pass

Fix forward. If the assertion is genuinely wrong, that is a finding you report —
with evidence — not a diff you quietly land.

---

## 5 · Working discipline

**WIP = 1.** One claim at a time. Finish it or release it. Two half-legs are
worth less than one closed leg.

**Work in a worktree.** Code legs run in `<board>/<rung>-<leg>` worktrees, one
atomic commit per leg. Run `git worktree list` first — the repo root
`C:\Users\User\SYNAPSE` is a *separate* checkout on `master`, and an absolute
repo-root path written from inside a worktree lands on master's tree, not your
branch. Evidence artifacts land in the main tree as untracked files.

**Read-only means holding no write tools.** Telling an agent "you are read-only"
while it holds `Write` is a suggestion, not a fence. Fence it in the agent
definition's tool list.

**Two eyes on every build.** Nothing reaches a human gate on the builder's word
alone. A crucible that did not build it, and is motivated to break it, attacks
it first.

**Falsification watch.** Two consecutive bookkeeping-only legs — no code
touched, no contract authored, no evidence created — means the harness is
spinning. **Stop and say so.**

---

## 6 · Talking to each other

Agents coordinate through two channels, and they are not interchangeable:

- **`bus/` (durable).** Append-only JSONL. Claims, releases, receipts, handoffs.
  This is the record. If it isn't on the bus, the next agent cannot see it.
- **`SendMessage` (live).** Cross-talk while both are running — a question, a
  correction, a heads-up. Ephemeral. Anything that matters is also written to
  the bus.

**Handoffs carry provenance.** Who touched it, what they did, what fidelity the
output claims. A handoff with a degraded source is not forwarded — it is
surfaced.

**Do not take another agent's word at face value.** A confident subagent report
is evidence of confidence. Check the artifact it names.

---

## 7 · Receipt format

```json
{
  "leg": "<board>:<rung>:<role>",
  "verdict": "PASS | FAIL | BLOCKED | UNKNOWN",
  "touched": ["path:line", "..."],
  "commands": ["the exact command, re-runnable"],
  "artifacts": ["harness/<board>/runs/<date>/<file>"],
  "proved_it_bites": "the mutation that turned the new test red",
  "could_not_verify": ["the honest gaps — 'none' is rarely true"],
  "needs_human": ["gated acts, verbatim, or []"]
}
```

---

## 8 · Tools and skills

**Use the skill when one covers the task.** `synapse-feature`, `solaris-harden`,
`solaris-render`, `deploy`, `debug-env`, `project-insights` encode workflows that
already went wrong once. Improvising past them repeats the mistake.

**Use the narrow tool over the shell.** `Grep` over `rg`, `Glob` over `find`,
`Read` over `cat` — they integrate with permissions and produce clickable paths.

**`synapse_ping` before any live-bridge claim.** A SessionStart "bridge
connected" line can be stale. Ping first, or write UNKNOWN.

**Never trigger a browser dialog, and never run an unbounded render.** Both
freeze the host and cost the human their session.

---

## 9 · When you are stuck or wrong

- **Blocked by a gate** → stop, state the gate verbatim, name what is ready
  behind it. Do not route around it.
- **The spec is wrong** → say so in one or two sentences with the evidence, then
  build the rest under a stated assumption. Do not silently "fix" a ratified
  contract, and do not down-scope the work because part of it is awkward.
- **You broke something** → what broke, what you know, what you don't. One
  acknowledgement, then the correction. No performance.
- **You cannot verify a claim** → it goes in `could_not_verify`. A short honest
  list beats a long confident one.

---

## 10 · The one-line version

> Build small, prove it bites, write the receipt, name what you could not check,
> and stop at the gate.
