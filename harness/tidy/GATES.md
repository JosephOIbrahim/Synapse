# TIDY — Open Human Gates

> The human decision list. Every open gate in SYNAPSE, consolidated: the exact
> ask, who decides, what closes it. Nothing here is an agent's call — each row
> is a decision only a human (Joe, as CTO) can make. When a gate closes, move
> it to the CLOSED section at the bottom with the date and the ruling.
>
> Compiled 2026-08-07 by TIDY dispatch. Sources cited per gate. Verify each
> item still exists before acting — this list is a snapshot, not a lock.

---

## 1. CI0 rulings — R-CI0-1 .. R-CI0-5

**Who decides:** Joe (all Article I — value judgements, not facts provable from the tree).
**What closes them:** a ruling on each, then the CI0 merge (Gate C, §4).
**Source:** `harness/NEXT_SESSION.md` (FIRST section), `.claude/worktrees/ci0-honest-green/harness/notes/receipts/CI0.json` → `for_ruling[]`.

CI0 turned master CI honestly green (3 failed → 0 failed, 40 deselected, +21 passing). It escalated these five rather than decide them. Read, rule, then merge.

### R-CI0-1 — moneta first-deposit force-save. **THE ONE THAT MATTERS.**
- **Ask:** `_last_save = 0.0` (moneta_store.py:205) makes the first deposit always fsync. Durability posture, not a bug. Choose:
  - **A (shipped):** keep it. First deposit survives kill -9. Docstring's "no per-deposit fsync" stays false for deposit #1.
  - **B:** `_last_save = time.monotonic()` in `__init__`. One line. Original single-deposit assertions pass verbatim; docstring becomes true; a lone deposit + kill -9 within 30s is lost (already documented).
- **Why escalated:** a real durability decision; a CI-greening leg is the wrong place to quietly change durability semantics.
- **Closes when:** Joe picks A or B; the chosen option is recorded in the CI0 receipt.

### R-CI0-2 — deprecate `synapse_evolve_memory`?
- **Ask:** It was dead since 7f7bbc39 and nobody noticed — evidence of how little it's used. CI0 rerouted it to `shared/evolution.py` so it works again. Alternative: deprecate outright, since Moneta `sleep_pass` supersedes markdown→USD evolution.
- **Why escalated:** what to deprecate is explicitly a human call (Article I).
- **Closes when:** Joe rules keep-rerouted or deprecate.

### R-CI0-3 — three zero-elapsed-time tests (Windows-only).
- **Ask:** Fail only on Windows dev (~15ms clock), never on CI's ubuntu/macos legs. Real fix = `time.perf_counter()` in routing/session product code, two subsystems. Leave, or fix.
- **Why escalated:** out of CI0's scope; touches product timing code in two subsystems. Changing `> 0` to `>= 0` would weaken a test and was not done.
- **Closes when:** Joe rules leave (report-only) or directs the `perf_counter()` fix.

### R-CI0-4 — two stale evolution sentences in governing docs.
- **Ask:** `docs/DEBUT_READINESS.md:122` and `CLAUDE.md` §6 say evolution fires under the jsonl path. It fires nowhere. Both are governing/release documents.
- **Why escalated:** Article VI — an agent does not silently amend a governing document, even to correct a fact.
- **Closes when:** Joe corrects them himself, or directs an agent to.

### R-CI0-5 — make `harness/statusline.py` worktree-aware.
- **Ask:** Every agent worktree shows a '?' branch + 4 phantom red tests because `.git` is a FILE in a linked worktree. Fix: read the `gitdir:` pointer. Explains red-test noise eaten all thread.
- **Why escalated:** not CI0's surface; the tests it breaks are green on CI.
- **Closes when:** Joe directs the fix (small, ~10 min).

---

## 2. R-M5b-1 — warn-not-refuse on the phantom gate

**Who decides:** Joe.
**What closes it:** the one-line scout change + a decision note, committed.
**Source:** `harness/notes/receipts/M5b.json` → `for_ruling[]` → `R-M5b-1`.

- **Ask:** Ruled warn-not-refuse, never committed. One-line scout change: an external/no-Houdini process should **WARN** not **refuse** on the phantom gate. Write the change + a decision note. ~10 min.
- **Context:** with no Houdini at all (stock python, CI, a farm process), `_running_build()` returns `''` and the expected build falls back to the committed package table's own stamp — so the H21 table loads as authority and reports `stale=false`. Keeping it lets CI and headless tooling ground anything at all; changing it would disarm grounding everywhere Houdini is absent, which is most of CI.
- **Closes when:** the warn-not-refuse change lands with a decision note.

---

## 3. M6 — the phrase table (the actual last mile)

**Who decides:** Joe (design decision at start).
**What closes it:** the phrase table built and merged.
**Source:** `harness/NEXT_SESSION.md` (THEN: M6 section), `harness/legs.json` (M5 note: "M6 (phrase routing) explicitly out of scope").

- **Ask:** The phrase table maps "basic Solaris setup" → fixture name so typing it FIRES. The engine underneath (`apply_fixture`) is done, merged, released. M6 is small now: exact-match table first, model only on miss, zero tokens on the common path.
- **Design decision to make when starting:** exact-match only, or aliases ("solaris basic" == "basic solaris" == "basic Solaris setup")?
- **Closes when:** the design decision is made and the phrase table ships.

---

## 4. CI0 merge — Gate C

**Who decides:** Joe (human gate; `SYNAPSE_GATE_C=1`).
**What closes it:** the merge of `ci/ci0-honest-green` → master, then CI re-runs green.
**Source:** `harness/NEXT_SESSION.md` (Execute order step 2), `harness/legs.json` → CI0 leg, CI0 receipt `status: green-with-a-stated-exception`.

- **Ask:** Merge CI0 to master. Branch `ci/ci0-honest-green` is 6 ahead of master, 0 behind, **not merged** (verified 2026-08-07). Status is green-with-a-stated-exception (the five rulings above are the stated exceptions).
- **Ordering:** rule the five CI0 items first (~20 min), then merge.
- **Closes when:** `git merge ci/ci0-honest-green` into master with `SYNAPSE_GATE_C=1`, CI badge green.

---

## 5. CLEAR L1 — commit-or-drop the 6 latency-relay files

**Who decides:** Joe.
**What closes it:** the 6 files committed at a sha OR dropped via a logged human gate.
**Source:** `harness/clear/SPEC.md` (P1.1), memory `clear-work-clearance-harness.md` ("L1 human gate (open)").

- **Ask:** commit-or-drop the 6 latency-relay files. All 6 verified present 2026-08-07:
  - `.claude/agents/latency-forge.md`
  - `.claude/agents/latency-measurer.md`
  - `.claude/agents/latency-relay-orchestrator.md`
  - `.claude/workflows/latency-relay.js`
  - `docs/latency-relay-operator-card.md`
  - `docs/reviews/synapse-latency-report-2026-07-27.md`
- **Closes when:** `git log --all` finds all 6 files committed, OR a DECISIONS/flywheel entry marks the set dropped.

---

## 6. PHANTOM SWEEP gates

**Who decides:** Joe.
**What closes them:** per-gate, below.
**Source:** `harness/phantoms/SPEC.md` (§Gates), `harness/phantoms/LOG.md`.

Joe holds: **SPEC ratification, every FIX dispatch (forge, worktree, no merge), corpus edits, `rulebook/phantoms.json` population, any merge/push.**

- **SPEC ratification:** the PHANTOM SWEEP SPEC is still `PROPOSED` (LOG: "spec remains PROPOSED"). Ratify it (same discipline as CLEAR's SPEC).
- **FIX dispatch:** every FIX row is a human-gated forge action. The corpus usdrender fix-queue (35 FIX) was dispatched in FIX-R1/R2; the claim "no corpus file teaches the usdrender node type" is now true. **Merge = Joe's gate** — the `fix/corpus-usdrender-rop` branch (14 commits) awaits Joe's merge.
- **Corpus edits:** require Joe's ratification (SPEC §Out of scope).
- **`rulebook/phantoms.json` population:** proposed in the ledger, gated, never auto-written.
- **Follow-up queued:** content_digest rebuild after the corpus merge.
- **Closes when:** SPEC ratified; the corpus fix branch merged; phantoms.json populated by Joe.

---

## 7. RSI gates

**Who decides:** Joe (human_ratified is a human flip only; no loop is promoted past L3 by an agent).
**What closes them:** per-gate, below.
**Source:** `harness/rsi/LOG.md` (open human gates line), `harness/rsi/REGISTRY.json`, `harness/rsi/CHAMPION.md`.

Open human gates (from LOG): **any L3→L4 advance · signal-semantics change (RL-2) · C substrate call · push/merge.**

- **A1 (EpochAdapter) — signal-semantics change behind the human gate.** Blocked at L2. L2 needs BOTH a `command_fn` wired at `handlers.py:1625` AND live traffic through it. Wiring the command channel is a signal-semantics change and sits behind the human gate. (L1 CLOSED 2026-08-01.)
- **A3 (memory evolution) — L3→L4 advance.** Blocked at L3, `human_ratified: false`. Any L3→L4 advance is a human flip.
- **R, O, E — rung advances.** R blocked at L2, O blocked at L1, E blocked at L2. Each advance past L3 is a human flip; L3→L4 specifically is human-only.
- **C (Moneta substrate) — ratified to L4** (`human_ratified: true`). The **flywheel flip remains Joe's (fenced)** — see §9 MONETA.
- **S — RETIREMENT-REFUSED** (blocked at L1). Rung deliberately NOT advanced: proving the mechanism runs is not proving it benefits; promoting is a human ruling.
- **A2, F — RETIRED** (closed 2026-08-01, ratified delete). No open gate.
- **push/merge** — always Joe's.
- **Closes when:** Joe flips the relevant `human_ratified` / authorizes the signal-semantics change / authorizes the merge.

---

## 8. ROPE blocked_human tasks

**Who decides:** Joe (both are HUMAN tasks, not agent tasks).
**What closes them:** the human performs the task; the ROPE task moves off `blocked_human`.
**Source:** `harness/rope/STATE.json` (tasks L3-2, L3-5, status `blocked_human`).

### L3-2 — Video above the fold
- **Ask (HUMAN):** record the L3-1 first prompt, 20-30s — prompt typed, nodes appear, viewport updates, decision credit, tab switch + local model with no key. GIF <10MB inline + MP4 on the release. Reference the orphaned `assets/synapse_logo.png` in the header.
- **Closes when:** the GIF/MP4 is produced and attached to the release.

### L3-5 — Apprentice verdict + support matrix
- **Ask (HUMAN):** one Apprentice session — doctor + the L3-1 prompt + one render attempt. Publish README support matrix: Commercial/Indie/Apprentice/Education × panel/build/husk/renders. "Watermarked" and "unavailable" are answers; "unknown" is not. Known: Indie blocks husk/Karma.
- **Closes when:** the Apprentice session runs and the support matrix is published.

*(Note: L5-13 is `blocked` (not `blocked_human`) — a QSS bug fix, agent-executable, not a human gate. L5-14..L5-23 are `needs_review`.)*

---

## 9. MONETA ratification

**Who decides:** Joe.
**What closes it:** Phase 0 (ratify + pin) executed; the flywheel flip.
**Source:** `docs/moneta-deep-review-2026-08-05.md` (Status: "ratification pending"; Phase 0), memory `moneta-deep-review-2026-08-05.md`, `harness/rsi/LOG.md` (RL-3 · C RULING: "Flywheel flip remains Joe's (fenced)").

- **Ask:** Ratify Moneta as the substrate (RSI loop C) and pin it. Phase 0 (ratify + pin, this week):
  - **P0-1:** Ratify Moneta as the substrate (RSI loop C) — Joe's decision. Low — it's already live.
  - **P0-4:** Pin Moneta dependency in `pyproject.toml` (currently unpinned; `importlib.metadata.version("moneta")` returns `1.2.0rc1` for rc1/rc2/rc2+N — cannot detect drift).
  - **P0-5:** Pin CI Moneta ref to a tagged release.
  - **P0-2/P0-3:** (per doc) — see `docs/moneta-deep-review-2026-08-05.md` Phase 0 table.
- **Also open:** `MONETA_DEPLOY_KEY` secret not yet provisioned — Joe needs to create the deploy key so Moneta tests run on CI.
- **Closes when:** Joe ratifies the substrate (RSI loop C flip), pins the dependency + CI ref, and provisions the deploy key.

---

## CLOSED (for reference — do not re-open)

| Gate | Closed | Ruling |
|---|---|---|
| RSI A2 wire-or-delete | 2026-08-01 | Ratified delete, executed by RL-3 |
| RSI F wire-or-delete | 2026-08-01 | Ratified retire, executed by RL-3 |
| RSI `python/synapse/agent/` package cut | 2026-08-01 | Ruled delete, executed by AGENT-RETIRE lane; `protocol.py` refused-and-kept |
| RSI C substrate | 2026-08-01 | RATIFY-AND-STABILIZE adopted; `human_ratified: true` (flywheel flip still fenced — §9) |
| RSI SPEC ratification | 2026-08-01 | Ratified (CTO authority granted) |
| M5 rulings R-M5-1..4 | 2026-08-06 | c3 canonicalizer / ratify-as-shipped / eject-not-delete / h22 symbol table regen |
