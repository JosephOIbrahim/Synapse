# SYNAPSE Science Harness — First-Principles Design (v4)

**Status:** ARCHITECT artifact. Design only, no implementation. Pre-FORGE.
**Edition:** v4. The v2 separated *verification* from *search* (the Floor / the elevator). The v3 turned that discipline back on the harness's own substrate (S1–S4) and re-grounded the stale `execute_python` premise. **v4 is forced by a third field test that dwarfs the first two** — a multi-agent CTO codebase review (workflow `w46nxfiu3`: 8 dimension specialists → adversarial crucible verification → synthesis + completeness critic, ~1.58M tokens, 63 verified findings). It proves three things at once, and folds in two requested capabilities — **dynamic workflows** and **long-running agent teams** — as direct consequences of what the review found.
**What forced v4:** (a) the review confirms S1–S4 **and extends them to a systemic class** — the documented central safety layer (`LosslessExecutionBridge`) is **absent from every live transport**, so Tier 1's invariants reference a mechanism that *does not run*; (b) the master failure class generalizes past *emitted claims* and *assumed mechanisms* into **doc/code drift** — the map no longer matches the building, concentrated exactly on the load-bearing safety claims; (c) the review was itself **produced by an agent team** and is **itself Floor-disciplined** (code-verified, honestly stamped V0/not-live-verified, refuted findings excluded, partials flagged) — making it both the forcing function and the template for the two new capabilities.
**Lineage:** Generalizes the AutoScientists × Harlo proposal (arXiv:2605.28655), re-grounded in SYNAPSE; v4 additionally formalizes the review's own multi-agent structure as a first-class harness capability.
**Target:** `JosephOIbrahim/Synapse`. Wire Protocol 4.0.0, ~110 MCP tools, memory Charmander. *Floor-applied note on the target line itself:* the repo states `v5.10.0` / build `21.0.671`, but CLAUDE.md's banner reads `v5.8.0` / `21.0.596` and tool counts disagree across six values (43/104/108/110/111/117). These are **doc-claimed, conformance-pending** — §4a.5 turns that into a rejectable condition rather than a footnote.

> **Read order:** §0 is the regime, once. §0.8 is the new field test and the re-founding — read it after §0.6, which it extends. §1 is agent teams; §3 is dynamic workflows; §4c is the safety spec for both. §5 is the bootstrap, now two tracks. Seven minutes: §0, §0.7, §0.8, §4 (all three tiers), §5.

---

## Δ from v3

Diff against the version you have, without re-reading it.

- **§0 holds; a third application level is added.** v2 floored what the harness *emits*; v3 floored what it *stands on*; **v4 floors what it *claims about itself*** (doc/code conformance) and extends the Floor's reach so both new capabilities run on it. The split didn't change; it acquired a third face.
- **§0.7 rewritten — the premise didn't just go stale, it inverted.** v3 asked "is `execute_python` still BLOCKED?" The review answers: it is **not blocked — it is ungated.** It runs on both live transports with full `__builtins__`, no consent, no import filter, no length cap (`handlers.py:916-973,1504`). Phase 0.0 is re-scoped from *debug-the-deadlock* to *confirm-the-posture-and-decide-the-gate (D1)*. S4 (consent poll blocks the event loop) survives regardless.
- **§0.8 added — the third field test (the systemic audit).** The review is §0.6 at 8-dimension scale. Its headline is structural, not cosmetic: **the bridge Tier 1 leans on never runs on the live path.** Undo and thread-safety genuinely hold — but via the *handlers*, not the bridge. So Tier 1 is **re-founded on the real mechanism** (this is a correctness fix to the harness's own spec, not a caveat). Includes the findings→home map.
- **§1 widened — roles become a long-running TEAM.** The three role identities (ARCHITECT/FORGE/CRUCIBLE) generalize into a persistent, multi-agent team modeled on `w46nxfiu3` — dimension specialists, an adversarial verifier, synthesis, and a completeness critic. *Long-running* means the team's **state** survives across sessions in USD even though the Windows processes can't (`/resume` constraint honored).
- **§2 extended — the Workflow graph + team coordination + two new Ledger kinds.** Adds `DocConformance` (a doc claim bound to code reality) and `Deferred` (a completeness-critic "unprobed" entry, first-class so it cannot silently vanish). The Ledger itself acquires durability requirements (atomic + backed-up) because a long-running harness that loses its Ledger on a crash is the review's DR finding realized.
- **§3 generalized — the admission gate becomes a WORKFLOW COMPOSER.** Binary *search-vs-build* → a gated DAG of nodes, persisted to USD, **recomposed at runtime.** This is *dynamic workflows*. The per-node admission test is preserved; an explicit guardrail keeps the engine from becoming the next "framework-edit avoidance" the review caught at the panel layer.
- **§4 now has three tiers.** §4a Floor gains a **fifth rule** (doc/code conformance) and a **fail-closed** principle. §4b Tier 1 is **re-founded on handlers, not the bridge** (D2-flagged). **§4c is new — Tier 2 team-execution invariants**, built directly from the completeness-critic's deferred findings.
- **§5 now has two tracks.** **Track H (Harden)** sequences the PRD into harness phases; **Track C (Capability)** lays the floors under the two new powers. **Track C is gated on Track H** — the dependency is the spine.

Kept intact and load-bearing: the §0 search definition, the §3 admission test (now per-node), the §5 bootstrap interlock, the §1 role mapping, the SYNAPSE-native refusal to import Harlo's motor-gate / RED-burnout. The bones are still yours.

---

## §0 — First principles (stated once)

The harness is **two disciplines**, not one. Conflating them was the v1 bug.

### The search (the elevator — gated)

> **A harness searches a space of hypotheses against a target, gated, recording what failed, promoting only what clears noise.**

Two inputs make it well-defined: a **target** (the thing being changed) and an **eval signal** that is **noisy with unknown direction.** A target with no noisy eval signal is a **build**, not a search; putting it through the loop is pure overhead. This is the admission test (§3).

### The floor (unconditional)

> **An artifact may not assert what it has not verified.**

A node type exists because `dir()` says so. A thing is "verified" because its eval signal fired. An artifact has lineage because provenance was written. This applies to **every output SYNAPSE emits** — and, since v3, to **every mechanism the harness stands on.**

### The one-line correction

**The admission gate decides whether you *search*. It must never decide whether you *verify*.** Verification is the floor — always underfoot. Search is the elevator — ridden only when the problem is search-shaped.

### The v4 amendment, in one line

v2 applied the floor to what the harness **emits.** v3 applied it to what the harness **stands on.** **v4 applies it to what the harness *claims about itself* — the doc/code contract — and extends its reach to two new powers: workflows composed at runtime, and teams that run long. The map must match the building; and everything the new powers do still happens on the floor.**

---

## §0.5 — The first field test: emitted claims (kept, compressed)

A `/code-review` against the docs commit (10 `.md`/`.txt` files, zero executable code) found defects that were **factual, self-contradictory claims** — the acute class for this project.

| # | Finding | Failure class |
|---|---------|---------------|
| **F1** | Fix instruction says create a `usdrender` ROP; real type is `usdrender_rop` | phantom API |
| **F2** | Recipe stamped *"Verified working"*; same-session diagnostic shows the scene was unrenderable | false promotion |
| **F3** | Three conflicting math-shape HDAs, none canonical, all `.hda` outside version control | state loss / no provenance |
| **F4** | Key light "brightest" at +1.0 while rim is +1.5; impact "~50%" while table shows ~80% | internal inconsistency |

Every defect was *an assertion nobody verified*, in a **build**. Hence the Floor. The conduct note that became a rule: when live verification is unavailable, **degrade to V0 with the caveat stated — never silently stamp "verified."** (§4a, V1-unavailable.)

---

## §0.6 — The second field test: assumed mechanisms (kept; confirmed and extended by §0.8)

A `/code-review` against the live `bridge.py` substrate found the harness **assumed mechanisms its own Tier-1 invariants depend on.** All four are **CONFIRMED by the CTO review** (and v3 earns credit in that review for marking S1 OPEN where CLAUDE.md over-claimed).

| # | Finding | Harness invariant it breaks | Review status |
|---|---------|----------------------------|---------------|
| **S1** | Double-undo: inner `performUndo()` inside the still-open group + the outer `except` calls it again | "rolls back clean" | CONFIRMED — fix exists but **uncommitted** (GIT-0) |
| **S2** | `_compute_scene_hash` digests SOP intrinsics + `cookCount`; never hashes the composed LOP stage | "verified" eval signal fires | CONFIRMED — blind on the Solaris path (INT-2) |
| **S3** | `_infer_stage_touch` traces `dependents()` only, never `outputs()` — SOP→LOP-Import is a false negative | blast-radius / idempotency | CONFIRMED (partial: test attribution mislocated, conclusion holds) (INT-2) |
| **S4** | Consent's `_wait_for_decision` busy-polls blocking `time.sleep` inside the async path | (corroboration, not a violation) | CONFIRMED — stalls the FastMCP loop up to 300s (INT-1) |

**Plus the test-suite point, now the review's loudest test finding:** the suite mocks `hou`, so it validates Python logic against *encoded assumptions about the API* — **V0-equivalent, where the mock is the spec.** S1/S2/S3 are exactly the class a mock can't catch. §0.8 shows this is not a handful of tests — it is **every CI-collected test.**

---

## §0.7 — The premise didn't go stale; it inverted (re-ground before you run)

The v2 target line read `houdini_execute_python BLOCKED`. v3 said: probe, don't trust a doc. **The review ran the probe's equivalent against the working tree and the answer is the opposite of either prior doc:**

`execute_python` is **not blocked. It is ungated.** Both live transports call `handle()` directly with no bridge (`websocket.py:623`, `hwebserver_adapter.py:211`); `_handle_execute_python` compiles and execs caller code with `exec_globals = {'hou': hou, '__builtins__': __builtins__}` — full file IO and subprocess, **no consent, no import filter, no length cap** (`handlers.py:946,1504`). The CRITICAL gate exists only inside the bridge — which the live path never touches — and the one path that *does* touch it sets `_gate = None`.

```
Phase 0.0 — CONFIRM THE POSTURE  [live probe · minutes · gates D1]      ← RE-SCOPED
   → against H21.0.671: does execute_python round-trip? (review says yes)
   → does any live transport enforce consent on it? (review says no)
   → does the S4 consent poll still block the event loop? (review says yes)
   → record each to the Ledger as a Confirmation, verified_by = V1
   → branch: this no longer feeds a deadlock search. It feeds D1 (the consent
     decision) and Phase 0b. The v3 "what holds the lock" search is RETIRED
     with a Ledger DeadEnd: "not a lock — an absent gate. v4 reframed."
```

A blocker is BLOCKED because a probe says so today. This one was never a lock; it was an **absent gate that the docs advertised as present.** That gap — not a deadlock — is the exposure, and it is the seed of §0.8's master finding.

---

## §0.8 — The third field test: the CTO review (the systemic audit, and the re-founding)

This is to v4 what §0.6 was to v3 — the field test that forces the edition. Where §0.6 found four assumed mechanisms, the review found **a systemic class across eight dimensions**, adversarially verified at `file:line`. The headline is not a bug; it is **the building diverging from the blueprint, concentrated on the safety claims.**

### The master finding

**Documentation asserts structural guarantees the running code delivers by accident, partially, or not at all.**

- *"`LosslessExecutionBridge` is the only code path / cannot be bypassed"* → **bypassed on every live transport.** Grep for `IntegrityBlock` fields across `server/` returns **zero files.** The live path produces no `IntegrityBlock` and computes no `fidelity`. The bridge is wired only into the `/mcp` HTTP path (`mcp/tools.py:124`), disjoint from the live `/synapse` client path.
- *"`execute_python`/`execute_vex` are CRITICAL-gated"* → **ungated on both live transports** (§0.7).
- *"Consent enforced via `HumanGate`"* → the only bridge-wired path sets `_gate = None`; `_panel_consent → True` unconditionally; the MCP tools share the **same neutered singleton.**
- *"Memory persistence is atomic (`.tmp + replace`)"* → the **primary store** does a truncating full rewrite (`store.py:366-393`); the atomic claim is real only for advisor telemetry (scope-confusion — but the data-loss risk is real).
- *"Evolution is lossless or aborted"* → the reachable evolver overwrites live markdown and drops parameters (`memory/evolution.py:337`), and the tool that triggers it is **dead-on-arrival** (`ImportError` on every call).
- *"Zero hallucinated APIs / verified live"* → **no emit-time mechanism exists.** Grep for `hasattr(hou`/`getattr(hou` across `mcp/` = zero. It is prose backed by manual recon + mocked tests.
- *Anchors asserted, not measured* → `undo_group_active` and `main_thread_executed` are hardcoded `= True` at the top of the method, **before the undo group opens.** The `IntegrityBlock` proves the bridge *believes* it ran safely, not that it did.

### The structural consequence for the harness (the re-founding)

v3's §4b asserts *"transaction-wrapped with undo-group rollback"* — and points at the bridge. **The bridge does not run on the live path.** So this is not a caveat to soften; it is a **mis-specification of the harness's own Tier-1 invariant**, and it gets *corrected*, not footnoted:

> The reversibility Tier 1 depends on is delivered by **inline per-handler undo-wrapping** — 37 `hou.undos.group()` sites across 8 server files, with mutating handlers marshalling `hou.*` onto the main thread via an `_on_main` closure (`handlers_node.py:51-117`). The safety *substance* holds. The *mechanism* is the handlers, not the bridge.

§4b is re-written against the mechanism that **runs** (with the S1 single-clean-`performUndo` fix as a committed precondition — GIT-0). The bridge-promotion path (measure the anchors, make it the live path) is the **D2-gated alternative**, designed-for but not assumed — exactly how v3 handled the stale `execute_python` premise: design for reality, branch on the decision.

### The recursion (why this review is also the template)

The review is **Floor-disciplined on itself**: every finding cites `file:line`; it is stamped **code-verified, NOT live-runtime or penetration-verified** (the bridge was down — its own V1-unavailable state); refuted findings are excluded; partials are flagged. And it was **produced by an agent team** — dimension specialists, an adversarial crucible verifier opening each cited location to mark CONFIRMED/PARTIAL/REFUTED, a synthesis pass, and a completeness critic enumerating what was *not* probed.

That is not a coincidence to admire — it is the **existence proof and the safety spec** for the two new capabilities. The team structure becomes §1. The team's discipline (adversarial verification, V0-honesty, refuted-excluded) becomes the team invariants. And the completeness critic's "do not assume these are safe" register becomes a **first-class Ledger kind** (§2 `Deferred`) and the **Tier-2 invariant list** (§4c).

*Reflexive provenance note:* the review's git status shows `SYNAPSE_SCIENCE_HARNESS_v3.md` sitting **untracked at repo root** — the harness's own provenance thesis (§4a.3) forbids exactly that. v4 ships to the canonical folder, **tracked.**

### Findings → home (nothing dropped)

| Review theme | Where it lands in v4 |
|---|---|
| Bridge absent / "cannot bypass" false / anchors asserted-not-measured | §0.8 master finding + **§4b re-founding** + Phase 0c (ARC-1 / **D2**) |
| `execute_python` ungated · neutered consent · S4 event-loop block | §0.7 + §4c.3 + Phase 0b (**D1** / INT-1) |
| S1 uncommitted · S2 LOP-hash blind · S3 dependents-only · `_verify_composition` fails open | Phase 0c (GIT-0 / INT-2 / INT-3) + §4a fail-closed + §4b precondition |
| **Master through-line:** doc/code drift, 6 tool counts, stale version banner, line-counts 18–44%, "zero hallucinated" = prose, `protocol_version` dead metadata, `CommandType` not source-of-truth | **§4a.5 (new Floor rule)** — extend `_conformance.py` from identifiers to **values/magnitudes/mechanisms** (DOC-1) |
| Every CI test is V0 / mock-is-spec · rollback path untested · no registry→handler parity · 38 divergent `hou` stubs | §6 **V1 test tier** (TEST-1/2); Inspector mock↔live golden as the template |
| RSI: FORGE no verify stage (`fixes_validated=0`) · `deposit_fn` unwired · router fast-paths zero-persistence · stale audit · two-tier Moneta unbuilt | §6 (**D4** → harness *is* the verify stage; RSI-S/F; DOC-RSI; **D3**) |
| Memory: non-atomic `memory.jsonl` · `agent.usd` every-write `Save()` no lock · dead `evolve_memory` · evolution detection-only | §2 durability + Phase 0a (MEM-2) + §6 (MEM-1) |
| Transport: two divergent WS servers · RBAC absent on hwebserver · `os` NameError breaks origin validation · default-localhost no-auth · no TLS/length cap | Track H — Phase 0c (SEC-0) + ARC-2 + transport-authz (SEC-1) |
| **Deferred (completeness critic):** autonomous LLM worker · multi-client concurrency · dead emergency-halt · TOPS rollback on bridge-less path · DR · data egress · supply-chain · perf envelope | **§4c team invariants** + §2 `Deferred` register + §7 |

---

## §1 — Roles: a long-running team (formalize what the review already ran)

v3 formalized the MOE workflow as three sequential identities. v4 formalizes the **structure that produced the review itself** — and makes it persistent.

| Harness role | What it does | Your identity / review analogue |
|--------------|--------------|----------------------------------|
| **Analyst** | Proposes hypotheses, ranks by expected effect size | **ARCHITECT** — design, no mutation |
| **Specialist (×N)** | A dimension-scoped reader (architecture, substrate, test, security, memory, …) that maps findings at `file:line` within its lane | the 8 dimension readers |
| **Experiment** | Executes one hypothesis / one build node, records result | **FORGE** — implementation |
| **Verifier** | Independently opens each claim and marks CONFIRMED / PARTIAL / REFUTED; refuses promotion inside noise; **enforces the Floor at emit-time** | **CRUCIBLE** — adversarial, fix-forward, never weakens the test; the review's crucible pass |
| **Synthesizer** | Reconciles specialist outputs into one assessment; resolves conflicts; emits the champion | the synthesis pass |
| **Completeness critic** | Enumerates what was **not** probed; writes each as a `Deferred` Ledger entry ("do not assume safe") | the completeness critic |

**Sequential-in-one-session on Windows still holds** — Claude Code can't spawn nested `claude` processes, teammates execute in-process, and they don't survive `/resume`. That is a constraint on **processes**, not on **state.**

> **Long-running = the team's state persists, even though its processes don't.** Champion, Forum, Ledger, the active Workflow graph, and the completeness critic's `Deferred` register all live in USD (`agent.usd`). A team is **resumed by reloading state**, not by keeping a process alive. The review's `w46nxfiu3` was one such team run; v4 lets the next session pick up its champion and its open `Deferred` entries instead of re-deriving them.

This is precisely where the review's #1 unprobed risk bites: **N autonomous LLM loops is N copies of the `claude_worker.py` exposure** — the worker loops API calls "until Claude stops requesting tools" (`claude_worker.py:123-157`), armed with the **full unfiltered** tool cache (`tool_bridge.py:82-89`) including `houdini_execute_python`, through the **same neutered-consent** bridge singleton. So the team is not safe by default. **Its invariants (§4c) are the deferred findings, promoted to blockers.** The safely-scoped counter-example already in the tree — `cognitive/agent_loop.py` via the dispatcher, registering **only** `inspect_stage` + `write_report` — is the template every team node is built against.

---

## §2 — Shared state: Champion, Forum, Ledger, the Workflow graph, team coordination

The harness coordinates through SYNAPSE's USD substrate, persisted in `agent.usd`.

**Champion** — the current best answer to the open question (working predictor / confirmed root cause / verified recipe).

**Forum** — a prim hierarchy of structured proposal / result / critique posts, cross-readable across hypothesis tracks and across team specialists.

**Workflow** *(new — the dynamic-workflow substrate)* — a persisted DAG: nodes (each tagged `search` or `build`, each carrying its admission verdict), edges (dependencies + gate criteria), and per-node status. The workflow is **data, not code** — inspectable, resumable, and **recomposable at runtime** (§3). A `DeadEnd` prunes a branch; a `Confirmation` opens the next; the completeness critic *adds* a node.

**Ledger** — durable memory of what's settled. v3 cleaned the schema and added `SubstrateAssumption`. v4 adds two kinds the review demands:

```
LedgerEntry (prim)
├── kind         : token  ∈ {DeadEnd, Confirmation, Canonical, SubstrateAssumption,
│                            DocConformance, Deferred}          ← two new in v4
├── question     : str
├── verified_by  : token  ∈ {V0, V1, V1-degraded}   # ALWAYS required
├── timestamp    : int
│
├── DeadEnd ───────────── direction, change_applied, measured_delta, rejection_reason, seed/context
├── Confirmation ──────── direction, change_applied, measured_delta, artifact_path
├── Canonical ─────────── artifact_path, supersedes : path[]
├── SubstrateAssumption ─ mechanism, probe, holds : bool, scope/caveat
├── DocConformance ────── claim_text, claim_locus : path:line, code_locus : path:line,
│                         bound_by : token ∈ {identifier, value, magnitude, mechanism},
│                         holds : bool
│                         # e.g. claim="execute_python is CRITICAL-gated"
│                         #      code_locus="handlers.py:916"  holds=false  → blocks the claim
└── Deferred ──────────── area, why_it_matters, probed : bool=false, stakes : token
                          # the completeness critic's output. "Do not assume safe."
                          # cannot be silently closed — only resolved by a probe that flips probed=true
```

`verified_by` is mandatory on **every** kind — the floor expressed as a schema constraint.

**Violations the Ledger now surfaces, not tolerates** (v3's two, plus v4's three):

1. Two artifacts answer the same `question` with no `Canonical` pointer → violation (F3). *(v3)*
2. An invariant is asserted whose `SubstrateAssumption` reads `holds=false` or is absent → violation (S1–S3). *(v3)*
3. **A "structural"/"verified"/"cannot-be-bypassed" claim about the system has no `DocConformance` entry, or one that reads `holds=false`** → violation. This is the bridge-absence finding, the six tool counts, the stale banner, "zero hallucinated APIs" — all of it — made into a single rejectable condition. *(v4)*
4. **A `Deferred` entry is closed without a probe** (`probed` flipped to true with no `Confirmation`/`DeadEnd` backing it) → violation. The completeness critic's findings cannot be wished away. *(v4)*
5. **The Ledger store is not crash-atomic or has no backup point** → violation against the harness's own durability (below). *(v4)*

**Ledger durability (new, non-negotiable for a long-running harness).** The review's DR finding — no backup/rotation for `memory.jsonl`, `agent.usd`, or `.synapse/science/*.jsonl`; one corrupting crash destroys all accreted memory — applies *first* to the harness's own nervous system. The Ledger/Forum/Workflow writes are **temp + `os.replace`** atomic and **generationally backed up.** A harness that disciplines provenance while its own provenance store truncates on `kill -9` is the bare-subfloor problem again. This binds **MEM-2** and the DR deferred finding to the substrate the harness writes through (§5 Phase 0a).

**Coaching surface (extended):** SYNAPSE can now say *"the current shape generator is the Hypotrochoid one; the others are superseded"* (Canonical), *"undo rollback via the handlers is single-and-clean once S1 is committed; the bridge is audit-only pending D2"* (SubstrateAssumption + DocConformance), **and** *"the multi-client concurrency path is unprobed — I will not run a second team node against the main thread until it has a Confirmation"* (Deferred) — instead of leaving you to discover any of it by surprise.

---

## §3 — The admission gate becomes a workflow composer (dynamic workflows)

v3's gate was binary and decided one thing per artifact: elevator or stairs. v4 keeps that test **per node** and wraps it in a composer that builds and re-builds a workflow.

### The composer

```
given a target:
  decompose into nodes
  for each node:
      target defined?  AND  eval signal is search-shaped (noisy, direction unknown)?
         ├── both yes  → SEARCH node (Tier 1 — on the Floor §4a)
         └── otherwise → BUILD node  (FORGE — on the Floor §4a)
  wire edges: a node opens only when its upstream GATE clears
  persist the DAG to the Workflow prim hierarchy (§2)

  nothing is ever below the Floor. every node — search or build — is API-verified,
  provenance-recorded, barred from a false "verified," and doc-conformant.
```

### What makes it dynamic

The DAG is **grown and pruned from results, not authored once:**

- A `DeadEnd` **prunes** its downstream branch (the search resolved upstream — retire it, don't re-walk it; cf. the v3 `execute_python` retirement).
- A `Confirmation` **opens** the next gated node.
- The **completeness critic adds nodes**: an unprobed area becomes a `Deferred` entry *and* a candidate node — so "what we didn't check" feeds back into the workflow instead of evaporating.
- A node may **re-shape** the downstream graph when its result changes the admission verdict of a later node (a build that was assumed becomes a search once its eval signal turns out noisy).

This is the AutoScientists "search over hypotheses" generalized into **search over workflows** — PDG-shaped (work items + dependencies + a scheduler), provenance-native, and resumable because the graph is USD state, not in-memory.

### The anti-sprawl discipline is preserved — and explicitly defended

Dynamism is the failure mode's favorite disguise. The review caught the exact pattern at the panel layer: the Houdini panel was **redesigned end-to-end twice** (PR #21, PR #27) while the three substrate phases sat unbuilt — *"framework edits = avoidance,"* the project's own named anti-pattern, expressed in UI velocity.

> **Guardrail (load-bearing):** the workflow composer is **not** a workflow-authoring surface to tinker with. Two checks keep it honest. (1) **Every node still passes the §3 admission test** — the composer cannot smuggle a build into the search loop, so adding nodes does not add ceremony. (2) **Recomposition must be triggered by a Ledger event** (`DeadEnd`/`Confirmation`/`Deferred`), never by hand-editing the graph for its own sake — graph edits with no backing result are the avoidance tell, and the harness surfaces them the way your constitution surfaces a third framework edit in a day. Dynamism earns its keep by *responding to evidence*, or it is scope-creep.

The scheduler **yields to foreground artist cooks** — an experiment/build cook is preemptible by a real-time artist cook (compute-yield, §7). A long-running workflow must never starve the artist whose session it shares.

---

## §4 — Invariants, in three tiers

### §4a — The Floor (Tier 0, unconditional)

Applies to **every artifact**, every node, search or build. Not gated by §3.

**1. API-verified-or-quarantined.** No artifact references an API surface, node type, or method unconfirmed by live `dir()`/`hasattr` against the *running* build (H21.0.671). Phantom surfaces are quarantined, never emitted. *(Catches F1. The review confirms this has no emit-time mechanism today — "zero hallucinated APIs" is prose; the §4a.2 hook is where it becomes real.)*

**2. "Verified" is a reserved word — a checkable contract.** A claim of "verified" is **rejected unless it carries:**

```
VerifiedClaim {
  eval_signal_fired : bool   # the signal for THIS artifact's purpose, not node-creation
  eval_signal       : str    # "render produced intended image" / "bug reproduced then resolved"
  verified_by       : token  ∈ {V1, V1-degraded}   # V0 may NOT back a "verified" claim
  artifact_path     : str    # in-repo; an outside-VC path is itself a rejection (F3)
  against_build     : str    # the H21 build / session probed
}
```

Below the bar, the honest stamp is the specific lesser claim. A "verified" claim **is** a promotion; promotions clear the bar or aren't made. *(Catches F2. The check lives in an MCP-server emit-time hook validating this struct.)*

**3. Provenance-or-it-didn't-happen.** Every artifact records, as USD provenance: producer (build/role), target build/session, **in-repo path**, and a `Canonical` pointer if a prior artifact answers the same question. An artifact outside version control is itself a violation. *(Catches F3 — and the reflexive case: an untracked `_v3.md` at repo root.)*

**4. NEW — Doc/code conformance (the map matches the building).** A claim *about the system itself* — "structural," "verified live," "cannot be bypassed," a version string, a tool count, a threshold value — is **rejected unless a `DocConformance` entry binds the claim's locus to a code locus and reads `holds=true`.** This is the master finding (§0.8) made into a Floor rule. Mechanized by **extending `_conformance.py`** from its current identifier-presence check (`assert_value_in_all_files`, the project's best idea, built after three real drift bugs) to bind **values, magnitudes, and mechanisms** (DOC-1): the bridge-presence claim, the six tool counts, the stale banner, the 18–44% line-count drift, the `protocol_version` that disagrees across the same WebSocket. *Single-source the version string and tool count; let conformance fail loud on value/magnitude/mechanism drift, not just renames.*

**Tail — self-consistency.** An artifact may not assert two incompatible facts (key "brightest" at +1.0 while rim is +1.5; "~50%" while the table shows ~80%). Lightweight; cost scales with stakes. *(Catches F4.)*

**Fail-closed (new principle, spanning the tier).** A safety check that cannot complete its verification must report **failure, not success.** The review's `_verify_composition` returns `True` on any exception (`bridge.py:831-837`) — a stage that was never validated still yields `composition_valid=True` and `fidelity=1.0`. Every Floor check inverts that default: **un-verifiable ⇒ quarantine/fail, never a silent pass** (INT-3).

**V1-unavailable degradation.** When the live probe can't run — bridge unreachable, stale-"connected"-banner — verification **degrades to V0 with the caveat stated, never silently stamps "verified"** (`verified_by = V1-degraded`). *The CTO review is the worked example: an entire 63-finding audit, honestly stamped code-verified-not-live, with a standing instruction to re-verify against a running build before claiming any security item fixed (`synapse_ping` first — the SessionStart banner is stale).*

### §4b — Search-execution invariants (Tier 1, gated) — RE-FOUNDED on the real mechanism

Applies **only inside a search node**, on top of the Floor. SYNAPSE-native — **do not import Harlo's basal-ganglia motor spine or RED-kills-everything;** SYNAPSE has no human burnout state and no motor gate.

- **One mutation per experiment.** One atomic script.
- **Idempotent guards.** Check-before-mutate so a re-run is safe. *(S3 note: the `_infer_stage_touch` inference this rides on has a false-negative class on SOP→LOP-Import — Phase 0c hardens it (trace `outputs()` as well as `dependents()`) before this is trusted on the LOP path.)*
- **Reversible via inline handler undo-wrapping — NOT the bridge.** *(The v4 correction.)* A failed experiment rolls back via the handler's own `hou.undos.group()` + main-thread marshalling (`handlers_node.py:51-117`), the mechanism that **runs on the live path.** **Precondition:** the S1 single-clean-`performUndo` fix is **committed to HEAD** (GIT-0) — a fresh clone today reintroduces the double-undo. **D2-flagged alternative:** if `LosslessExecutionBridge` is promoted to the live path *and its anchors are measured* (not asserted `=True` before the group opens), this invariant's framing returns to the bridge. Until that decision ships, the handlers are the mechanism, stated honestly.
- **Promotion rule (noise-aware).** No new champion unless the measured gain clears the noise band, **confirmed on a second seed/context.** For a bug, the "second seed" is a second reproduction under a fresh Houdini session, not a statistical band — adapt the *form* to the target (§7).
- **Halt-and-surface, not RED.** The node halts and hands back on: merge conflict, unverified API, failed transaction, noise-band ambiguity, or **a `DocConformance` violation discovered mid-run.** Mirrors constitutional dispatch's halt triggers.

### §4c — Team-execution invariants (Tier 2, gated) — NEW

Applies **inside a long-running agent team** (§1), on top of the Floor and, for any node that searches, on top of Tier 1. These are the completeness critic's deferred findings, promoted from "someday" to **invariants** — because adding the team *is* adding the unprobed autonomous path.

1. **Per-role tool allowlist.** An agent receives **only** the tools its role needs: read-only (`inspect_*`, `write_report`) for Specialist / Verifier / Completeness-critic roles; destructive tools **only** on an explicitly-scoped Experiment node, and only with §4c.3 consent. The full unfiltered `_TOOLS_CACHE` (`tool_bridge.py:82-89`) is **forbidden** to a team agent. The safely-scoped `cognitive/agent_loop.py` (inspect + write_report only) is the template; the exposed `claude_worker.py` is the anti-pattern. *(Closes completeness-critic #1.)*
2. **Bounded loops.** No "until the model stops requesting tools" (`claude_worker.py:123-157`). Every team node carries a **max-turn and max-cook budget** and **halts-and-surfaces on exhaustion** — never silently spins. *(Closes the unbounded-loop risk.)*
3. **Real consent for destructive ops.** A long-running team **cannot auto-approve** `execute_python`/`execute_vex`. Destructive nodes require enforced consent, made **async** (`await asyncio.sleep`, matching the PDG path `bridge.py:663`) so one pending decision doesn't stall the whole MCP server (INT-1). Read-only nodes need none. *(Closes the neutered-consent risk on the autonomous path — distinct from the artist path, where pre-consent is defensible.)*
4. **Main-thread concurrency control.** N agents = N clients on **one** Houdini main thread, which today has **no max-client cap and no global dispatch semaphore.** A team imposes a **global dispatch semaphore** (serialized mutation, well-nested undo across interleaved nodes) and makes the **`decision_NNNN` counter atomic** (today `len`-based, races — `agent_state.py:50-55`). *(Closes the multi-client-concurrency deferred finding.)*
5. **A working emergency-halt.** `trigger_emergency_halt` is defined once (`bridge.py:911`) and **called nowhere** — a documented panic button wired to nothing, the same "documented-but-unreachable" class as the bridge. For a long-running team it becomes **load-bearing**: wired to the `resilience.py` Watchdog (which already detects 5s main-thread freezes), to a `fidelity < 1.0` signal, and to a drift trigger; **callable, and tested.** A team you can't stop is not a team you may start. *(Closes the dead-EmergencyProtocol finding.)*
6. **Durable accreted state.** The team's Ledger / Forum / Workflow / `Deferred` register survive a crash — atomic writes + generational backup (§2), the DR finding applied to the team's memory. A long-running team whose state truncates on a crash has accreted nothing. *(Closes the DR deferred finding.)*
7. **Egress discipline (lighter — partly open, see §7).** What scene data, asset paths, and `memory.jsonl` decision records leave to `api.anthropic.com` each turn (`agent_loop.py:101-225`) is **classified and bounded** for a team that runs long and feeds tool-results back every turn — the data-egress finding at scale. Minimum: a documented "what leaves the building" boundary and an opt-out; full classification is scoped as a follow-up.

> **Operator note (kept distinct, deliberately).** The harness's *subject* (SYNAPSE) has no burnout state. The *operator* (you) does, and your constitution's RED overrides your own work. These are different controls and v4 does not conflate them: a long-running team that may run while you are away is governed by the **technical** stops above (emergency-halt, bounded budgets, the semaphore), **not** by your RED. RED governs whether *you* keep working; §4c governs whether the *team* keeps running. A team must be safe to leave unattended on its own mechanisms.

---

## §5 — Phase 0: two tracks (Harden, then Capability)

Phase 0 is no longer one sequence. It is **two tracks with a hard dependency**: you don't get the new powers until the subfloor the review exposed is fixed. The deferred findings *are* the hardening; building long-running teams on top of them would be building the elevator's penthouse on a bad subfloor.

```
══ TRACK H — HARDEN (absorb the CTO review; this is the PRD, sequenced) ══

Phase 0.0 — CONFIRM THE POSTURE                 [live probe · minutes]   (§0.7)
   → execute_python runs, is ungated, S4 still blocks the loop. Record V1. Feeds D1.

Phase 0a — synapse_write_file + ATOMIC + BACKUP  [build · ~days]
   → server-side write endpoint (path validation, UTF-8 + binary), routed through the
     MCP server's own I/O — NOT Houdini's Python (no execute_python dependency).
   → the write-path for BOTH tiers AND the new state: Ledger, provenance, the Workflow
     graph, team coordination, the Deferred register.
   → temp + os.replace atomic; generational backup. (MEM-2 + DR, applied to the harness
     substrate first.) A non-atomic provenance store fails §2 / §4c.6.

Phase 0b — CONSENT POSTURE                       [execute D1 + INT-1]
   → reframed from "debug the deadlock" (there is no lock — §0.7) to: gate
     execute_python/execute_vex at the handler layer, OR keep auto-approve for
     single-user localhost and DELETE the doc claim. Either way a test pins the choice
     and a DocConformance entry binds doc to code. Make the consent wait async (INT-1).

Phase 0c — SUBSTRATE + DOC CORRECTNESS           [builds · FORGE on the Floor]
   → S1  commit the single-clean-performUndo fix (GIT-0) → flips the SubstrateAssumption
         "undo rollback single + clean (handlers)" to holds=true; unblocks §4b.
   → S2  hash lop.stage() content for LOP ops, not SOP intrinsics + cookCount (INT-2)
         → §4a.2 eval signal fires on the Solaris path.
   → S3  trace outputs() AND dependents() in _infer_stage_touch (INT-2)
         → removes the blast-radius false negative §4b idempotency rides on.
   → SEC-0  import os in hwebserver_adapter.py — origin validation raises NameError
            today, breaking the DNS-rebinding defense on the production transport.
   → INT-3  _verify_composition fails CLOSED, not open.
   → DOC-1  extend _conformance.py to values/magnitudes/mechanisms; single-source the
            version string + tool count. This is the mechanization of §4a.4.
   → each fix: bug reproduced (live), fixed, reproduced-clean on a second session.
     deterministic eval signal → builds, not searches (§3).

══ TRACK C — CAPABILITY (the floors under the two new powers) ══
══ GATED ON TRACK H — every item below depends on the matching Track-H fix ══

Phase 0d — TEAM-SAFETY FLOOR                     [the §4c Tier-2 prerequisites]
   → before a long-running team runs a single autonomous node, the six bindings exist:
       per-role allowlist · bounded loops · async real consent (needs 0b) ·
       main-thread semaphore + atomic counter · WORKING emergency-halt ·
       durable+backed-up state (needs 0a).
   → the completeness critic's deferred list is the 0d checklist. Each item closes a
     Deferred Ledger entry only via a Confirmation (no silent closes — §2 violation 4).

Phase 0e — WORKFLOW-ENGINE FLOOR                 [the §3 composer prerequisites]
   → the Workflow prim schema, the composer, the scheduler-with-yield, the anti-sprawl
     guardrail (recomposition triggered by Ledger events only).
   → RFC-ONLY where it touches USD schema conventions (Michael Gold's zone — §7).
```

**The reframed reading.** v3's thesis was *"lay the floor under the harness's own feet before it runs"* (Phase 0c). v4 keeps that **and** adds: *lay the floor under the **team's** feet (0d) and the **workflow engine's** feet (0e) — but only after the substrate the review audited is hardened (Track H).* The dependency is the whole point: **the new capabilities are earned by fixing the subfloor, not bolted onto it.**

**Connection worth flagging (still a hypothesis).** The `execute_python` posture, S4's blocking consent poll, and **Spike 2.4** (main-thread/daemon-thread deadlock) are very likely views of one root cause; the non-blocking `submit_turn`-returns-a-Future fix you already closed Spike 2.4 with is the same shape as INT-1's async consent and §4c.4's dispatch discipline. If so, 0b, 0d's concurrency binding, and the closed Spike 2.4 resolve together. *Stated as a hypothesis to confirm, not asserted.*

---

## §6 — Forward map (after Phase 0)

Once the posture is settled, the substrate satisfies its (re-founded) invariants, the doc/code contract is mechanized, and both new floors are laid:

- **FORGE's missing verify stage IS the harness's promotion gate.** The review's one RSI item needing real engineering (D4 / RSI-E): `orchestrator.py:177` does `fixes_applied += 1 # Optimistic` with **no generate→apply→verify stage** and `fixes_validated=0` hardcoded (`:214`). The harness already *is* the verify stage — the §4b promotion rule (reproduce the fix clean on a second fresh session) is exactly what FORGE lacks. Wire FORGE's apply step into a search/build node and let the harness gate `fixes_validated`. Until then, **stop emitting the metric** (D4).
- **The two one-line RSI closures → builds on the Floor.** RSI-S: pass `deposit_fn=<moneta writer>` at `run_apex_verify.py:82` so falsifiability records reach the queryable substrate (the seam already calls it when non-None). RSI-F: `to_jsonl`/`from_jsonl` around `router.py:80 _session_fast_paths` so learned fast-paths survive restart (the only zero-persistence RSI store). Both are low-activation wiring against tested code.
- **APEX verify phase → search node.** `dir()`-based API discovery for `apex::graph`, port conventions, node types as a search; confirmed surfaces → Ledger; then FORGE builds recipes against verified APIs. Your existing hard gate, mechanized.
- **A V1 test tier — the review's loudest test finding.** **Every CI-collected test is V0** (`ci.yml:49`, ubuntu-latest, no Houdini; the mock is the spec). Add a `live`/hython tier behind the existing `SYNAPSE_INTEGRATION` gate (TEST-1): the first test drives `bridge.execute()` through `_execute_houdini` with a composition failure and asserts **single** clean rollback — a path with **zero** coverage today (the `.scout/s1_repro.py` harness is a ready start). Add a global registry→handler parity test and a stdio-vs-HTTP tool-count assertion (TEST-2). The Inspector's mock↔live shared golden is the template to copy everywhere. These move `SubstrateAssumption` entries from V0 to V1.
- **MEM-1 → build on the Floor.** Fix or remove `synapse_evolve_memory` (dead-on-arrival: `ImportError` + unreachable branch); if kept, point it at the **lossless** `shared/evolution.py`, not the markdown-overwriting `memory/evolution.py`. The Pokémon evolution model is currently **unexecuted in production** (detection-only) — decide whether it ships or is retired.
- **DOC-RSI → provenance hygiene.** Mark `SYNAPSE_RSI_AUDIT.md` superseded — its two highest-ROI claims (observability dormant, render-memory never set) are **already fixed** in live code; acting on the stale doc redoes done work. A `Canonical` pointer is the mechanism.
- **ARC-2 → transport convergence.** Converge the two WebSocket servers onto one resilience-policy layer (hwebserver has rate-limiter + backpressure only — no watchdog, no circuit breaker) so fixes aren't written twice. SEC-1 (per-command RBAC on hwebserver) lands on **both** transports — they've already drifted.
- **D3 → two-tier Moneta (Charmander ↔ Moneta bridge).** Immutable falsifiability tier + decaying tier, so never-decay dead-ends converge onto the unified substrate without the decay model eating them. Decide-or-defer so the six siloed "what we learned" stores stop multiplying. (Your scoped Sprint-4 Moneta bridge.)
- **Everything else → FORGE on the Floor.** TOPS feedback, Solaris validator, COP↔Solaris bridge, declarative SOP/DOP builder, post-render hook, intent locking. The search loop stays out of their way; the Floor does not. The recipe-report failure class (§0.5) is structurally impossible for floor-disciplined builds.
- **Multi-team self-organization → graduated, not deferred.** v3 deferred this. v4 makes it **Track C, gated on Track H** — it is the agent-teams capability, and it ships only behind §4c. The identity decision (co-pilot → co-pilot that also runs science) is real, but it is now **gated**, not open-ended.

---

## §7 — Open questions for the blueprint phase

Resolved since v3: *"is `execute_python` still the blocker"* (no — it's ungated, §0.7); *"where does the Floor's emit-time check live"* (an MCP-server hook validating `VerifiedClaim` + `DocConformance`). Still open:

- **D2 — fate of `LosslessExecutionBridge`.** The harness designs Tier 1 against the honest reading (handlers). The blueprint must **execute** D2: promote-and-measure, or retire-to-audit-only and rewrite CLAUDE.md §1's "only code path / cannot bypass." Until shipped, §4b stands on the handlers.
- **Egress classification for long-running teams (§4c.7).** Genuinely under-scoped. What scene/asset/memory content leaves to the API each turn, what gets redacted, what the opt-out is. Higher-stakes for a team than a single session. Scope it as its own pass.
- **Concurrency model specifics (§4c.4).** Semaphore granularity (per-mutation vs per-node), undo nesting under true interleave, the atomic-counter implementation. No concurrent-client test exists today — write one before trusting the semaphore.
- **The dynamism ceiling (§3).** How much runtime recomposition before the workflow engine becomes the "framework-edit avoidance" the review caught at the panel layer. Define the ceiling concretely (e.g., recomposition allowed only on Ledger events; a budget on graph edits per session) rather than by feel.
- **Cheapest viable self-consistency check (F4 tail).** Minimum that catches "key brightest but rim higher" and mismatched percentages without a heavyweight semantic checker. Probably a structured-claims pass. Scope it.
- **Cadence & compute yield.** Per-session, or a background cadence so foreground artist work stays real-time (post-render idle windows)? Per-cycle compute ceiling, and how an experiment cook yields to a foreground artist cook.
- **Second-seed form per target.** Statistical noise band for a learned scorer vs. fresh-session reproduction for a bug — the promotion rule's *form* changes by target type. Enumerate the forms.
- **Schema location — RFC-ONLY (Michael Gold's zone).** Where `VerifiedClaim`, `DocConformance`, `Deferred`, and the `Workflow` graph live in the USD schema — `customData` on the artifact prim, or typed schemas. This touches substrate conventions; **not a unilateral change.**
- **Recorded-deferred, out of harness scope (tracked as `Deferred` entries, not silently dropped):** supply-chain posture of the 22MB vendored SDK (no CVE scanning in CI); the performance/scale envelope (JSONL grows forever — evolution is detection-only — with no perf-regression guard, ironic given the latency-finish PR); TOPS live-path rollback (cooks run on the bridge-less transport, so the documented `dirtyAllTasks` rollback almost certainly doesn't apply). Each warrants its own review; none is assumed safe.

---

## One-line synthesis

The regime is now **three disciplines and two new powers, all on one floor.** The **floor** every SYNAPSE artifact stands on — *verify before you assert, "verified" is earned, provenance or it didn't happen, and the map must match the building* — plus the **search loop** ridden only when the problem is search-shaped. v2 floored what the harness *emits*; v3 floored what it *stands on*; **v4 floors what it *claims about itself*** — because a 63-finding, 8-dimension, adversarially-verified review proved the documented safety bridge **never runs on the live path**, so Tier 1 is re-founded on the mechanism that does (the handlers), and doc/code conformance becomes a Floor rule. The two requested powers fall out as consequences: the admission gate generalizes into a **workflow composer** that builds and prunes a gated DAG from evidence (*dynamic workflows*), and the roles generalize into a **persistent team** modeled on the review's own structure (*long-running agent teams*) — whose invariants **are** the review's deferred findings, and which ships only after the subfloor those findings expose is hardened. A harness that disciplines a system's outputs while trusting its untested internals — or claiming a building its blueprint no longer describes — is standing on the same bare subfloor it was built to abolish.

---

*End of ARCHITECT artifact (v4). Next, if greenlit: the FORGE spec for Phase 0a (`synapse_write_file` + atomic/backup + the §4a `VerifiedClaim`/`DocConformance` emit-time hook); the Phase 0c fix specs (S1 commit first — five-line change, highest reversibility risk; then SEC-0, INT-3, DOC-1's conformance extension); the Phase 0d team-safety spec (per-role allowlist + bounded loop + a callable, tested `trigger_emergency_halt`); and the Phase 0.0 posture-confirmation probe. Track H before Track C — the floor before the powers.*
