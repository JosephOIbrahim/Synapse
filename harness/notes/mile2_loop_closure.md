# Mile 2 — Loop-Closure Note (graph-synthesis relay)

**Status: CLOSED.** master HEAD == `e6e989d` — the Mile-2 commit is atomic (single commit, all 10 files) and on master via fast-forward. Released as **v5.18.0**.

**Closure gates (all independently re-verified by a 4-lens agent panel):**
- **Contract integrity** — `git diff a8895af e6e989d -- python/synapse/cognitive/graph_proposal.py python/synapse/cognitive/interfaces.py` → **EMPTY**. Both FINAL contracts are byte-identical to pre-Mile-2.
- **Build gates** — `--mile 1` PASS · `--mile 2` PASS (boundary / dod / phantom / mutation all PASS, exit 0). 5 DoD tests green. Full suite: 3,803 passed / 0 failed.
- **Live e2e** — `harness/notes/mile2_live_e2e_result.json` `all_pass=true`, `scene_clean=true`, 6 scenarios (arity_overflow, hallucinated_type, occupied_halt, ghost_resolve, missing_parent, valid_extend).
- **Rename integrity** — zero Python importer/registry/test still expects `ScoutExistenceAdapter`; the only consumers of `HouExistenceOracle` are the file itself and the e2e harness. Cognitive boundary intact (`cognitive/*` imports zero `hou`).

No real blocker (no dangling code ref, no failing gate, no edited FINAL contract). The relay is positioned for Mile 3.

---

## Part 1 — Carried-Residual Ledger

| # | Item | Location | Owner | Status |
|---|------|----------|-------|--------|
| a | type-mismatch is called an *advisory* by the contract comment but the validator emits it as a HARD error | `graph_proposal.py:79` vs `graph_validator.py` 3b | ARCHITECT | OPEN — doc-or-code reconcile owed (FINAL file, FORGE cannot touch) |
| b | `ConnectivityOracle.types_compatible` returns **True** in production — no non-mutating, type-level wire-compat surface in 21.0.671 | `graph_oracle.py` | FORGE-Mile3 | DEFERRED — Mile-3 build-time `setInput()` enforces natively |
| c | P5 parent **TYPE-host** compat (can this container hold these categories?) — only parent *existence* is checked now | `graph_validator.py` P5 | FORGE-Mile3 | DEFERRED — Mile-3 builder re-runs P5; `createNode` enforces |
| d | `HouExistenceOracle` not wired into the MCP registry this Mile (DoD injects a mock) | `existence_adapter.py` | parked-session | PARKED — separate session |
| e | `HouExistenceOracle` is a deviation from the settled scout-backed Target | `existence_adapter.py` | ARCHITECT | **RATIFIED** by human — resolved |
| f | **No production `GraphValidator` construction site**; `configure(validator, store)` is uninvoked outside tests; nothing stamps a live `scene_fingerprint` at park, so the §7 TOCTOU compare has no baseline yet | `propose_graph.py`; `graph_proposal.py:58` | FORGE-Mile3 / host-wiring | OPEN — Mile-3 wiring must call `configure(...)` + stamp a real fingerprint |
| g | **FINAL-contract docstring drift:** `IExistenceOracle` still documented "scout-backed (§2.6-confirmed)" though §2.6 refuted scout | `interfaces.py:9` | ARCHITECT | OPEN — doc-fix owed (FINAL file); behaviorally harmless |
| h | **P3c slot-label advisory dormant in production:** `input_labels` always returns `[]` (type-level labels phantom in 21.0.671) | `graph_oracle.py` | platform-limited | DOCUMENTED |
| i | **Interactive WS-bridge live e2e:** now PASSED this session (`all_pass=true`) on the live bridge | `graph_oracle.py` / `existence_adapter.py` | — | CLOSED this turn |

*Note: Mile-1 tests now pin `live_phases_enabled=False` because the default flipped False→True — correct pinning, not a residual.*

---

## Part 2 — Mile 3 Handoff — `graph_builder.instantiate` (the construction half)

> Relay: ARCHITECT(plan) → FORGE(this Mile) → FORGE-Evaluator(gate `--mile 3`) → human merge.
> Mile 2 merged to master (`e6e989d`). WIP=1, fresh context, atomic commit, **HALT before merge** (human gate).

### Where we are
- **Validator is done.** `cognitive/graph_validator.py` runs P1-P5 live; `live_phases_enabled` default is **True**. Oracles are hou-backed and §2.5/§2.6 live-verified.
- **The only Mile-3 stub** is `host/graph_builder.py`: `GraphBuilder.instantiate()` raises `NotImplementedError`.
- **FINAL contracts — do NOT edit:** `cognitive/graph_proposal.py`, `cognitive/interfaces.py`.
- **Bench requirement met:** Mile 3 needs **graphical** Houdini 21.0.671 (undo + connect), which is **UP**.

### What Mile 3 fills — `GraphBuilder.instantiate(proposal_id)`
1. **Look up + reject unknown id** (`ProposalStore.get`; `None` → clean rejection, **zero mutation, never enter the undo group** — amendment 5).
2. **TOCTOU guard — re-validate + recompute fingerprint UNCONDITIONALLY (§7)** against the *current* live scene before any mutation. Any new INVALID, unresolvable path, or fingerprint mismatch → **HALT, zero mutation**. This is what makes the delete-between-propose-and-instantiate DoD case halt.
3. **ONE `hou.undos.group(...)` block:** create NEW nodes topologically (EXISTING already placed) → set parms (NEW only) → connect edges via `setInput` → close.
4. **Provenance receipt to `agent.usd`** — decision + reasoning + revert path.
5. **Truth contract:** read back every parm set and every connection made; never claim an unobserved outcome.

### What it REQUIRES (now unblocked)
- Graphical bridge — UP.
- Inject the **hou-backed** Mile-2 oracles (`ConnectivityOracle` + `HouExistenceOracle`) into the re-validation validator — NOT a scout adapter.
- A production construction site — call `propose_graph.configure(validator, store)` at daemon start with the **same `ProposalStore`** the builder reads.
- A real fingerprint baseline — stamp a live-scene fingerprint at park, or the §7 compare is inert (today the P5 re-validate is the only working TOCTOU guard).

### Definition of Done (gate `--mile 3`)
1. Novel-topology extend-existing build instantiates.
2. Single Ctrl+Z restores the scene.
3. Delete-between-propose-and-instantiate halts with ZERO mutation.
4. Reject unknown `proposal_id` — clean, no mutation.
5. `forge_evaluator_gate.py --mile 3` exits 0. Then **HALT** — human merges.

### Out of scope — route to ARCHITECT (FINAL files)
- (a) `graph_proposal.py:79` type-mismatch advisory-vs-error; (g) `interfaces.py:9` stale "scout-backed" docstring. Flag; don't touch.

---

## Part 3 — Cleanup (cosmetic, non-blocking)
- `harness/prompts/forge_mile2.md:32` still says "wire `ScoutExistenceAdapter`" — a historical instruction artifact, no code importer. Left as a record of the pivot.
- Merged topic branch `feat/graph-synth-mile2` left undeleted alongside master (optional `git branch -d`).
