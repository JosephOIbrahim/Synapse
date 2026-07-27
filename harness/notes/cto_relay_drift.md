# CTO-RELAY-01 — drift log

Reality contradicting `harness/SYNAPSE_CTO_RELAY.md`. Cosmetic ⇒ resume. Structural ⇒ §5.

---

## D-R1 · checks.py oracle invocation is wrong in the relay doc — STRUCTURAL

**Leg** L0 (and L1, L2 — every leg whose oracle cites checks.py)
**Doc claim** `harness/SYNAPSE_CTO_RELAY.md:161` — `python harness/verify/checks.py --all`; `:191` — `--check lop_emission_grounded`; `:193` — `--check no_phantom_api`.
**Reality** `VERIFIED-RUNTIME` — `checks.py` accepts `--task TASK --worktree WORKTREE [--hython] [--mode]`. Neither `--all` nor `--check` exists; the process exits 2 on both.
**Impact** The L0/L1/L2 oracles cannot execute as literally written. The check *functions* (80 of them) exist; only the CLI surface differs.
**Disposition** Resumed. Oracles re-expressed against the real CLI (`--task`/`--worktree`). Escalated to §5 as a ruling item because three legs' acceptance criteria are affected, not one.

---

## D-R2 · baseline sha moved — COSMETIC

**Doc claim** `:6` — `Baseline master @ e4b5916`.
**Reality** `VERIFIED-RUNTIME` — branch HEAD is `25e0166`; `e4b5916` is 3 commits back. The intervening commits (`0b3e377`, `2f63e78`, `25e0166`) are relay-authoring/amendment commits, not product changes.
**Disposition** Resumed. L2's "re-run seam-gate acceptance on `e4b5916`" is honoured by running against the branch HEAD that *contains* `e4b5916` — running against a stale sha would answer a question nobody is asking.

---

## D-R3 · L1 gap-closure is gate-REFUSED — STRUCTURAL

**Doc claim** `:184-186` — L1 work item 4: "Close the top 5" LOP/COP gaps.
**Reality** `VERIFIED-STATIC` — `harness/state/flywheel_queue.json:80`, cycle `C.0`, `"ratified": false`. GATEWARDEN returns **REFUSE** for the per-context capability *rebuild* and for gap *closure*; the census and delta probe are ALLOW.
**Impact** L1 can produce the COP census, the LOP delta and the ranked gap list. It cannot author the closing code. `harness/agent-settings.json` is deny-listed and `flywheel_queue.json` sits under the fenced `harness/state/**` — the agent cannot and must not flip its own gate.
**Disposition** Leg proceeds in census-only scope. The unflippable half escalates to §5 as a ruling item; the human flip is one boolean at `flywheel_queue.json:80`.

---

## D-R4 · `_cto_recon.py` does not exist — COSMETIC

**Doc claim** `:154` names `_cto_recon.py` among the root-hygiene suspects.
**Reality** `VERIFIED-STATIC` — no such path on the tree. The suspect list is itself stale on this one item.
**Disposition** Resumed; recorded so the next census does not hunt a ghost.

---

## D-R5 · `untitled.hip/` is data, not debris — COSMETIC (but load-bearing)

**Doc claim** `:153` lists `untitled.hip` as a hygiene suspect alongside `MagicMock/`.
**Reality** `VERIFIED-STATIC` — it is a directory holding `claude/agent.usd` (6,220 B) + `claude/memory.md` + `.synapse/`: the live unsaved-scene memory store, previously flagged at `docs/SYNAPSE_CTO_REVIEW_2026-06-09.md:118`.
**Disposition** Reclassified `live — do not delete`. Deleting it on the doc's suggestion would have destroyed the only copy of the unsaved-scene ledger.

---

## D-R6 · the branch is not exclusively the relay's — STRUCTURAL (process)

**Leg** L4 (detected), affects all legs.
**Reality** `VERIFIED-RUNTIME` — a concurrent process committed `6b41e1a`, `19dca4d`, `5a88cee` and `aaf12fe` to `feat/cto-relay-01` while the relay was mid-leg, authored as `Joseph Ibrahim`. One of them silently undid a `git reset --soft` the L4 agent issued to split a commit.
**Impact** Cohere rules 2 and 5 share one commit (`8411aad`) instead of being separate. Rule 1 stayed isolated, which is the one that had to be. No work was lost — but only by luck.
**Disposition** Resumed. Escalated to §5 as L4.R2: the relay's premise is that subagents are a context-isolation device; branch isolation is the missing half. Recommend per-leg worktrees.

---

## D-R7 · a parallel ruling file already exists — COSMETIC

**Reality** `VERIFIED-STATIC` — `harness/notes/CTO_RULINGS_01.md` was created by the concurrent process and already carries rulings up to R24, including an L3 addendum (rulings 17–23) covering emergency halt and the consent gates.
**Impact** The relay's §5 deliverable is `harness/notes/CTO_RELAY_01_RULING.md` — a different file. No collision, but two ruling surfaces now exist for one run.
**Disposition** Resumed. `CTO_RELAY_01_RULING.md` is written as specified and cross-references the other file rather than merging into it. Reconciling the two is itself a ruling item.

---

## D-R8 · L4's ORPHAN-removal instruction was declined, deliberately — STRUCTURAL

**Doc claim** `:277` — "Anything the L3 matrix marks `ORPHAN` is **removed from the surface, not restyled**."
**Reality** `VERIFIED-DERIVED` — all 17 ORPHANs are the `chat_panel.py` tree, whose loader (`synapse_chat.pypanel`) is never installed. They are already invisible to users. Removing the tree decides what belongs on the product surface — a T.4-adjacent call — and T.4 is frozen by three concordant sources.
**Impact** The instruction and the T.4 freeze are in direct tension. The freeze wins.
**Disposition** Resumed; neither restyled nor removed. Escalated to §5.

---

## D-R9 · hython-offscreen denied for the whole panel arc — STRUCTURAL

**Reality** `VERIFIED-RUNTIME` — every `hython.exe` invocation was refused by the permission system across L3 and L4 (observed 4× in L3, again throughout L4).
**Impact** 2 of 5 G3 slices have no baseline and no after-state: the live offscreen build and the v9 invariants. No screenshots were produced. Nothing in the restyle has been seen rendering.
**Disposition** Resumed with the gap reported honestly rather than papered over. Escalated to §5 as L4.R1 — the cheapest unblock in the relay, being a permission grant rather than engineering work.

---

## D-R10 · L1.F1 REFUTED — the bridge was never down; the probe was pointed at the wrong endpoint

**Leg** L1 (finding F1, severity `blocker`, tier `REFUTED-LIVE`)
**Claim** *"The live SYNAPSE WS bridge is NOT reachable, despite a fresh sidecar advertising it.
9/9 WebSocket upgrade attempts returned `InvalidStatus`."*
**Reality** `VERIFIED-RUNTIME`, 2026-07-25 13:03, Houdini pid 37456, build 22.0.368:

```
ws://localhost:9999            FAIL   server rejected: HTTP 400
ws://localhost:9999/synapse    OK     protocol_version 4.0.0, sequence 0
ws://127.0.0.1:9999            FAIL   server rejected: HTTP 400
```

The server requires the **`/synapse` path** — as Wire Protocol 4.0.0 specifies.
`harness/notes/.assayer_scratch/ws_probe.py:7` connects to `ws://localhost:9999` with no path.
All nine "failures" were HTTP 400 path rejections from a healthy server.

**Impact.** A `blocker`-severity finding in a shipped receipt is false. L1 concluded the transport
layer was dead and fell back to direct `hou` import; the census it produced is unaffected and
remains valid. But R11 in the ruling block ranks this defect above the entire relay, and that
ranking is now wrong.

**Second finding, real, surfaced by the same probe.** The envelope shape is also wrong. The
server answered:

> `Missing required parameter. Expected one of: 'content', 'text', 'message', 'body'`

The probe sent `params.code` / `code`. So the harness has **never** successfully driven Houdini
over this transport — the path error masked an envelope error behind it.

**Disposition.** L1.F1 struck. Ruling-block R11 must be re-ranked. `_ws_retest.py` retained at
`harness/notes/` as the corrected reference probe.

### The lesson, which is not the same as Law 1

Constitution Law 1 says *every check must be able to fail*. This check could fail, did fail, and
was **wrong** — the exact mirror of the four defects found this morning. Those passed while
proving nothing; this one failed while testing nothing.

**Law 1 gets you an honest instrument. It does not guarantee you aimed it at the right thing.**

Corollary, adopted: **a `blocker` derived from a negative result requires a positive control
before it ships.** If the probe cannot demonstrate success against a known-good target, its
failure is uninterpretable. Nine identical failures are one failure with a sample size, not nine
pieces of evidence — and the repetition made it read as more certain, not less.

---

# V1 — CAPTURE PROBE (2026-07-27)

Three entries. Two structural, one cosmetic. Recorded per Article VI, which says the drift log is
not an apology but the record of the document being wrong.

## D1 (structural) — V1 had already run, and its evidence is not in the tree

V1 executed at **10:19 on 2026-07-27** and was ruled as **R100–R106** (commit `098125f`). The brief
this run was dispatched with opens *"Nobody has established how, on 22.0.368"* — a premise that was
already false when it was written down.

But the prior run left nothing behind:

```
branch retina/v1-capture-probe   0 commits ahead of the line, 0 diff
worktree .claude/worktrees/v1-capture-probe   EMPTY
harness/notes/receipts/V1.json   ABSENT
any v1_* probe script            ABSENT
```

**R103 already records the cause**: the read-only fence denies `Bash(git commit:*)`, so a read-only
leg's product cannot be made durable, and the worktree was later pruned.

**Impact.** Every figure in R100–R106 — `7.74 ms`, `50 ids each with 49 shared`, `7.4% of pixels`,
`91.9% on prim boundaries` — currently has **no producer path in the tree**. Law 2 says no number
travels without one. This is a Law 2 violation produced by the fence design rather than by the
agent that obeyed it.

**Disposition.** This run re-executed the leg independently and left eleven producer scripts beside
the JSON they emit. Every re-tested R100–R106 claim **reproduced**. Two refinements are offered
rather than corrections: `V1-F6` supplies the *mechanism* behind R100-F3's blending (the shipped
`idcover` filter errors on every render and the fallback is what blends), and `V1-F8` corrects
R102's positive-control list (`getPixel` is absent on `Cop2Node` too, so it does not license
anything).

## D2 (structural) — the leg has no worktree, and the tree moved underneath it mid-run

`legs.json` declares `worktree: .claude/worktrees/v1-capture-probe`. **That directory is empty and
is not a registered git worktree.** So this leg ran against the **shared main checkout** — and
mid-run a concurrent leg re-pointed that same directory:

```
started   2105453  feat/repair-heats-01
ended     6983c73  docs/how-we-know
```

All Q1–Q4 findings are `VERIFIED-RUNTIME` against the live Houdini build and are unaffected by a
branch switch. The single `VERIFIED-STATIC` finding (`retina/ingest.py:65`, `:164`) was
**re-verified against the new commit** and holds.

**This is precisely the failure Constitution Article V's one-worktree-per-agent rule exists to
prevent**, and it is the same mechanism that lost the first V1's receipt. The rule was not
violated by an agent — it was never applied, because the manifest declares a worktree that nothing
creates.

**The general shape, and it is this week's shape again:** a mechanism written correctly and
connected to nothing. `legs.json` expresses the isolation; no step enforces it; the leg reports
normally either way.

## D3 (cosmetic) — the brief slightly overstates R73

The brief states *"R73 established the only render stop is `rkill`"*. R73's own evidence table also
lists `hou.IPRViewer.killRender` as **PRESENT**. Does not change V1's conclusions — `killRender`
requires a GUI, so a headless Karma-to-disk capture remains uninterruptible from the calling
thread. Recorded because a brief is a reader too (R105), and this one rounded a two-item finding
down to one.
