# MONETA ↔ SYNAPSE INTEGRATION HARNESS — v1

### Refactored from the AutoScientist × K+S general harness for **one specific job**.

> **One-line:** Make Moneta SYNAPSE's memory substrate — the *"Replace done right"* that Contract 1
> pointed at — introduced **shadow-first** behind the existing `MemoryStore` interface, gated on
> **(a)** the H21 API-existence check and **(b)** a deterministic, offline-capable embedding source.

**Provenance:** This is a *specialization*, not a fresh harness. It folds the generic
AutoScientist × K+S arc into Joe's existing system (MOE roles, capsule format, FORGE ledger,
marathon miles) and **cuts the anti-divergence machinery the generic version carries** — because the
divergence this job faced was already resolved in `MONETA_SYNAPSE_CONNECTION_REPORT.md`. What it
**keeps and sharpens** is the verifier-gating spine, which this job genuinely needs: the API
hallucination risk (your hard-won H21 lesson) and the parity requirement both demand it.

---

## 0. WHAT CHANGED IN THE REFACTOR

*Why this isn't the generic harness. Read once, then ignore — it's reasoning, not procedure.*

| Generic harness | This refactor | Why |
|---|---|---|
| ANALYST / BUILDER / CRITIC | **= your ARCHITECT / FORGE / CRUCIBLE** | One role vocabulary. CRUCIBLE's *fix-forward, never weaken* is stronger than the generic Critic — kept as the rule. |
| Mode decided at end of SKETCH | **Pre-resolved: SIMULATED TEAM** | The report already gives the dependency graph. No need to discover the mode. |
| Full ORCHESTRATED apparatus (roster, claim-lock, launch spec) | **Cut** | Claude Code can't spawn nested processes; you run on master sequentially. Honesty constraint, not a limitation to apologize for. |
| Contention Probe | **Cut** | Independence is plain from the graph; the only parallel line (embedder) is obviously independent. |
| DIGEST file (new compression format) | **= your capsule format** | No second compression format. |
| LEDGER (new skill ledger) | **= your FORGE friction system** | No second ledger. The recursive-self-improvement loop already plays this role. |
| Generic L0–L4 | **Instantiated against the report's invariants** | The `dir()` gate becomes L0; the gauge invariant + parity become L2; consent/IntegrityBlocks/determinism become L3. |
| Heavy stagnation-reorganization ceremony | **Principle kept, ceremony cut** | Job is linear; reorganization only matters if the embedder bake-off stalls. |

---

## 1. HARD INVARIANTS

*Above the arc. Never violated, at any mile, by any lens. These are yours, plus the two this job adds.*

1. **API verification is L0, not a suggestion.** No bridge/adapter code is written until `dir()`-based
   runtime introspection in the **actual H21.0.671 hython env** confirms every API the report assumes
   exists. Docs and Gemini Deep Think hallucinate H21 APIs. Confirmed-absent already:
   `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`. Treat Moneta's surface
   the same way until proven.
2. **Atomic scripts** — one mutation per call.
3. **Idempotent guards** — check-before-mutate.
4. **Transaction wrappers** — undo-group rollback on error.
5. **USD provenance** — every AI action writes its reasoning as custom USD attributes. The Moneta
   backend slots **under** SYNAPSE's `HumanGate` + `IntegrityBlock`, never around them.
6. **Backup-first before any migration.** The 176-entry backfill is one-time and reversible.
7. **`exec()` in Python Source Editor, not Python Shell** (Shell breaks on multi-line class defs).
8. **`execute_python` over WebSocket chokes on multi-line dict literals** — sequential single-line calls.
9. **Race-safe push** — fetch + rebase on non-fast-forward, max 3 attempts, halt on merge conflict.
10. **Fidelity = 1.0 or rollback.** Shadow cutover happens only when parity holds. Mirrors your
    existing replay-determinism property.

---

## 2. LENSES = YOUR MOE ROLES

*Standing roles, not phases. CRUCIBLE is always available — not only at STRESS.*

| Harness lens | Your role | Owns | The rule |
|---|---|---|---|
| **ANALYST** | **ARCHITECT** | Search knowledge. Reads the Log, ranks candidate moves, maintains DEADENDS + hypothesis docs. Design docs only. | Favor underexplored; deprioritize consistently-small effects. |
| **BUILDER** | **FORGE** | Claims one proposal, executes against the champion, runs the verifier, records outcome — win **or** fail. | Pulls from the ranked queue; does not invent what to build. |
| **CRITIC** | **CRUCIBLE** | (1) Kills weak proposals on the record before cost is paid. (2) Attacks the realized champion at STRESS with real adversarial cases. | **Fix-forward. Never weakens a test.** If CRUCIBLE finds nothing, CRUCIBLE isn't trying. |

Sequential within one session (relay handoffs). One context holds all three in turn.

---

## 3. MODE — PRE-RESOLVED

**SIMULATED TEAM** = one context, team discipline. Mostly a **SOLO spine**, with **one bounded
parallel bake-off** (the embedder).

**The dependency graph (from the report's §8):**

```
[Mile 0] ratify reversal (Reconcile → Replace)         ── gate, your call
   │
[Mile 1] L0: dir() confirm Moneta API exists in H21    ── hard gate, INVARIANT #1
   │        + seed champion = the spike
   ├─────────────────────────────┐
   │                              │
[Mile 2] embedder bake-off    [Mile 3] MockUsdTarget    ── the ONLY two independent lines
   (3 competing candidates)       CI path                  (embedder ⟂ pxr path)
   │                              │
   └──────────────┬───────────────┘
                  │
[Mile 4] MonetaBackedStore adapter (flag-gated)
   │
[Mile 5] shadow / dual-write + parity diff harness
   │
[Mile 6] INTEGRATE — compose, system-level L0–L3
   │
[Mile 7] STRESS — CRUCIBLE L4
   │
[Mile 8] SHIP — cutover + backfill 176 + ship report
```

Everything is a chain **except** Miles 2 and 3, which are genuinely independent (the embedder choice
doesn't touch the pxr/CI path). That's the entire parallel surface. No Contention Probe needed — the
independence is structural, not in doubt.

**ORCHESTRATED is off the table** (no nested processes). If a line ever splits into 4+ independent
sub-problems with a launcher present, re-derive — but it won't on this job.

---

## 4. SHARED STATE — FOLDED INTO YOUR SYSTEM

| Harness file | This job uses | Note |
|---|---|---|
| `SPEC.md` | **§6 below** | Ratify at FRAME. Changed only at ratification points. |
| `CHAMPION.md` | The spike → adapter → shadow-parity → cutover | Exactly one at a time. |
| `LOG.md` | Append-only attempt record (wins **and** fails) | Standard. |
| `FORUM.md` | Deliberation (proposals, critiques, results) | Where CRUCIBLE kills weak proposals before cost. |
| `DEADENDS.md` | **§9 — pre-seeded** | Read before proposing. |
| `PLAN.md` | The mile structure (§5) | Re-written only if a line reopens. |
| ~~`LEDGER.md`~~ | **= your FORGE friction system** | No second ledger. |
| ~~`DIGEST.md`~~ | **= your capsule format** | No second compression format. |
| `TRACE.md` | Append-only: every verifier result, branch decision, external call | Standard. |

**The capsule IS the digest.** At every mile boundary, write a capsule in your format
(`WHERE WE ARE / MILE MARKER / WHAT I WAS THINKING / NEXT ACTION / BLOCKERS / ENERGY REQUIRED /
IDEAS PARKED`). That is the authoritative compressed state downstream reasoning consumes.

---

## 5. THE ARC AS MILES

*Gate criteria are verified by line-number citations into the codebases. No advancing on unverified state.*

| Mile | Arc gate | Deliverable | Gate criterion |
|---|---|---|---|
| **0** | FRAME | Ratified SPEC + ratified reversal | Joe signs off on §6 and §10. |
| **1** | SKETCH | Seed champion = the spike; mode locked | L0 passes: `dir()` confirms Moneta API in H21.0.671. One deposit/query round-trips against `MockUsdTarget`. |
| **2** | DELIBERATE⇄EXECUTE | Embedder chosen | One candidate clears the embedder verifier (determinism dominant). Champion: `synapse.memory.embedding`. |
| **3** | DELIBERATE⇄EXECUTE | pxr/CI path | `MockUsdTarget` path import-guarded, exercised in CI, no `pxr` required. |
| **4** | DELIBERATE⇄EXECUTE | `MonetaBackedStore` adapter | Implements `add/search/get_recent/count/get_decisions`; L1 passes; flag-gated, default off. |
| **5** | DELIBERATE⇄EXECUTE | Shadow + parity harness | Dual-write to JSONL + Moneta; shadow-read diff; L2 parity meets threshold. |
| **6** | INTEGRATE | Composed system | Every SPEC predicate verified at system level (L0–L3). Seam: URI-lock ownership under async server. |
| **7** | STRESS | CRUCIBLE L4 | No showstoppers; bounded weaknesses documented in SPEC limitations. |
| **8** | SHIP | Cutover + backfill + ship report | Flag flipped; 176 entries backfilled (backup-first); markdown kept as export view; `evolution.py` retired; gauge invariant + consent gates + determinism all intact. |

Marathon marker format at each boundary: **`Mile X of ~8 — <what's done>, <what's next>`.**

---

## 6. SPEC.md — DRAFT (ratify at FRAME, Mile 0)

### Outcome
SYNAPSE's memory operations (`add / search / get_recent / count / get_decisions`) are served by an
in-process Moneta engine behind the unchanged `MemoryStore` interface. Callers
(`synapse_context / search / recall`) are unmodified. The two-store divergence, the dead gauge, the
empty stubs, and the read/write path divergence are **structurally impossible**, not patched. Memory
gains consolidation, time-decay, attention-weighting, vector recall, and durability for free.

### Acceptance Predicates *(the bar — each checkable)*
- **AP1** — `dir()` in H21.0.671 hython confirms `Moneta`, `MonetaConfig`, `deposit`, `query`,
  `signal_attention`, `get_consolidation_manifest`, `run_sleep_pass`, `MockUsdTarget` all exist and
  are callable. *(L0)*
- **AP2** — A deposit→query round-trip against `MockUsdTarget` returns the deposited memory. *(L1)*
- **AP3** — `MonetaBackedStore` satisfies the `MemoryStore` contract for all five ops; existing
  callers run unchanged. *(L1)*
- **AP4** — The Mile-0 gauge invariant holds: `gauge == Moneta count` via a count accessor
  (manifest length / ECS count). *(L2)*
- **AP5** — Shadow-read parity between JSONL store and Moneta meets the ratified threshold over a
  representative query set. *(L2)*
- **AP6** — Every memory mutation still routes through `HumanGate` and produces an `IntegrityBlock`.
  *(L3)*
- **AP7** — Replay determinism preserved: identical inputs + pinned embedder → identical state.
  *(L3)*
- **AP8** — Pinned decisions survive decay (mapped to high `protected_floor`) and surface on
  `get_decisions`. *(L2/L3)*
- **AP9** — CI runs the full memory path standalone with **no `pxr`** via the `MockUsdTarget` path.
  *(L2)*

### Out of Scope *(explicitly fenced — do not scope-creep)*
- Michael Gold's USD codeless-schema flag — separate work item.
- Copernicus / COPs expansion (the 15–20 tools).
- Shot-template tools (`synapse_solaris_shotsetup_karma_xpu`, etc.).
- BL-007 / BL-008 (EXR-not-writing, Karma asset-reference visibility).
- The Spike 2.4 main-thread/daemon deadlock — *referenced* as a known hazard class for the
  URI-lock ownership seam (Mile 6), but its resolution is not this job.

### Falsification Conditions *(failures that prove the approach wrong)*
- **FC1** — `dir()` shows Moneta's documented API is **absent or different** in H21.0.671.
  → Stops at L0. Same failure class as `hou.pdg.*`.
- **FC2** — **No embedding source is simultaneously deterministic, offline-capable, and acceptably
  fast/cheap.** Embedding is the hard prerequisite; if every candidate fails, the integration is
  **blocked at the spec level** → bounce to FRAME.
  *Sub-claim to verify, not assume:* the report lists "Anthropic SDK embeddings" — confirm an
  embedding API actually exists and is callable offline/deterministically before counting it as a
  candidate. It may resolve to a third-party/Voyage path, not a native endpoint.
- **FC3** — Vector recall diverges from keyword recall **persistently** beyond threshold on
  SYNAPSE's actual queries (behavior change too large to ship).
- **FC4** — The single URI-locked Moneta handle **deadlocks or races** under the async FastMCP server
  + main-thread bridge. (Known hazard — you already have a main-thread/daemon deadlock open.)
- **FC5** — Memory mutations can route **around** `HumanGate` / `IntegrityBlock` under the Moneta
  backend.

### Verification Strategy *(per predicate → layer + stochastic?)*
| Predicate | Layer | Stochastic? |
|---|---|---|
| AP1 (API exists) | L0 | No |
| AP2, AP3 (round-trip, contract) | L1 | No |
| AP4 (gauge), AP9 (no-pxr CI) | L2 | No |
| AP5 (parity) | L2 | **Yes** — query-set dependent; replicate before promoting |
| AP8 (decision survival) | L2/L3 | No |
| AP6 (consent gates), AP7 (determinism) | L3 | No (AP7 is *the* determinism check) |
| FC1–FC5 (the attacks) | L4 | Mixed |

---

## 7. VERIFIER LAYERS — INSTANTIATED

| Layer | This job's checks |
|---|---|
| **L0** Well-formed | Imports resolve; lints; **`dir()` confirms Moneta API in H21.0.671** (INVARIANT #1, AP1). *Nothing advances until this passes.* |
| **L1** Behavioral | Deposit→query round-trip returns the memory (AP2); `MonetaBackedStore` honors the five-op contract (AP3). |
| **L2** Property | Gauge invariant `gauge == count` (AP4); shadow-parity threshold (AP5); idempotent guards hold under repeat deposits; URI-lock single-owner respected; no-`pxr` CI path (AP9); decision survival under decay (AP8). |
| **L3** Semantic | `HumanGate` + `IntegrityBlock` wrap every mutation (AP6); replay determinism (AP7); recall *intent* satisfied — salient memories surface, not just "N rows returned." |
| **L4** Adversarial (CRUCIBLE) | `pxr`-absent CI; 176-entry migration w/ backup-first + rollback; decay-reorders-`recent_activity` edge (does the LLM-on-connect view degrade?); URI-lock contention under async server (FC4); embedder offline/failure behavior; the two-USD-models collision risk (`evolution.py` vs Moneta). |

**Noise-aware:** AP5 (parity) is stochastic — a within-noise parity gain is not real until replicated
on a fresh query set. Never promote on a single sample.

---

## 8. SEED CHAMPION — THE SPIKE

*Mile 1's deliverable. Weak, but it's the bar. Mirrors the Comfy bridge's first call.*

The smallest real artifact:
1. In a SYNAPSE hython session, `from moneta import Moneta, MonetaConfig`.
2. Construct a handle against `MockUsdTarget` (no `pxr` needed): `MonetaConfig.ephemeral()` or a
   mock-backed config.
3. `with Moneta(config) as m:` — round-trip **one** deposit and one query.

If this round-trips, connectability is proven and the champion exists. Every later champion must beat
it on the acceptance predicates: flag-gated adapter passing L1 → adapter passing L2 parity in shadow
→ cutover passing L3 → full system passing L4.

**Reference to lift from:** `Comfy_Moneta_Bridge` — `capsule.py:130-131` (query),
`ingest.py:93-94` (deposit), its own `vector.py` (owns embedding), `run_sleep_pass()` after deposits.
The connection mirrors this: a thin adapter that imports Moneta as a library, owns embeddings, wraps
deposit/query/sleep.

---

## 9. DEADENDS.md — PRE-SEEDED

*Banked so they are never re-litigated. Read before proposing.*

| Axis | Direction | Why rejected |
|---|---|---|
| Recall mechanism | Keep keyword-only recall | It's the **status quo being replaced** — the bug-prone subsystem, not a candidate. |
| "Reconcile vs Replace" answer | `sqlite_store.py` (the dormant 750-line vector scaffold) | **Rejected.** Moneta is the answer — built, tested, patent-backed. (Report §0, §6.6.) |
| USD memory maturity | Keep bespoke `evolution.py` (charmander→charizard) | **Retired.** Hand-rolled stand-in for what Moneta's `run_sleep_pass` / consolidation does properly. Two USD memory models must not coexist. (Report §5, §7.) |
| Connection topology | Out-of-process RPC bridge | Both run in the same hython — in-process embed is cleaner, no marshalling. (Report §4 Option A.) |
| Prior session decision | "Reconcile" (Contract 1) | **Superseded by Replace-done-right.** *Requires explicit ratification — see §10.* (Report §6.6.) |

---

## 10. THE TWO RATIFICATION GATES — JOE'S CALL (at FRAME)

The harness pauses here. Neither is mine to decide.

**Gate 1 — The reversal.** `[PRIOR-SESSION ASSERTED → needs your ratification]`
You chose **"Reconcile"** last session as the low-churn fix. Moneta-as-backend is **"Replace done
right"** — it makes the divergence class unrepresentable instead of patched, but it is a deliberate
reversal of a decision you made. Ratify the reversal, or hold at Reconcile.

**Gate 2 — Confirm the mode.** `[PRE-RESOLVED → confirm or redirect]`
SIMULATED TEAM, SOLO spine + one embedder bake-off, ORCHESTRATED cut. Confirm, or tell me the
dependency graph is wrong.

---

## 11. FIRST MOVE

After ratification, the first action is **L0 / Mile 0→1 boundary**, and it is the cheapest possible
high-information check:

> Write the `dir()` introspection script. Run it in the **graphical H21.0.671 hython env**
> (Python Source Editor, not Shell). Confirm `Moneta`, `MonetaConfig`, the four ops, `run_sleep_pass`,
> and `MockUsdTarget` exist and are callable. **If any is absent → stop at FC1.** This is the same
> gate that caught `hou.pdg.*`. Body check before the GUI work — fresh-paste catches what tired-paste
> misses.

Nothing downstream is written until this returns green.

---

**BEGIN:** Mile 0 — present SPEC (§6) and the two gates (§10) for ratification.
