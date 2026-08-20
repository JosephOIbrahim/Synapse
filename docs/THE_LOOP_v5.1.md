# THE LOOP v5.1 — Master Architecture Specification

> **Status:** UNRATIFIED working blueprint — law once Joe says the word. Until then the
> harness treats this document as the spec it builds against, and every seam below is
> honest about what is installed vs. what is spec-grounded.
>
> **Provenance:** Grounded 2026-08-19 against published shelf specifications
> (Synapse v5.54.0, Moneta v1.2.0-rc1, Hanish v0.1.2, SALUS v1.0.0, Octavius v0.9.0,
> jacobian-monologue v0.1.0) and August 2026 AI Agent Governance Formalisms
> (arXiv:2603.16586, arXiv:2605.17830, arXiv:2608.10218). Persisted to this file
> 2026-08-20 from the original paste, source-faithful.
>
> **Source-fidelity note (cleaned tokens):** the original paste carried a few garbled
> tokens. They are cleaned here and flagged once, not silently: `frcords`→"free of
> blocked-action records", `outammar/`→"out of turn", `stD quines`→"stage quines",
> `Res`→"Result", `dependon`→"runtime dependency", `ction`→"Contribution", `trix`→"matrix",
> `Contaminatedchunks`→"Contaminated chunks", `eeply`→"deeply". No numbers, signatures, or
> gate semantics were altered.

## Core House Idiom & Operational Axioms

Derive from prohibitions, not from boxes.
Runtime is truth, docs are the referee, model memory is hypothesis.
Unmeasured renders UNKNOWN — extended here: unpredictable renders no forecast.

---

## 0 · Architectural Topology: Dual-Plane Bisection

The blueprint bisects the six-repository shelf into two distinct operational planes: the
**Operational Runtime Loop** (managing active turns, state transitions, and path safety
boundaries) and the **Metrology Plane** (executing off-loop context position probing and
ablation benchmarks).

```
                     METROLOGY PLANE (Off-Loop Diagnostics)
        ┌─────────────────────────────────────────────────────────┐
        │                   jacobian-monologue                    │
        │       (Position Bias / Attention Probing / K2 Null)     │
        └───────────────────────────┬─────────────────────────────┘
                                    │ Evaluates V0.5 Ablations
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OPERATIONAL PLANE (Runtime Loop)                      │
│                                                                             │
│   PAST MEMORY           PRESENT BOUNDARY & HOST           FUTURE STAGE      │
│ ┌──────────────┐      ┌──────────────┬──────────────┐    ┌──────────────┐   │
│ │ Moneta       │ <--> │ Synapse      │ SALUS        │ <->│ Octavius     │   │
│ │ Hanish       │      │ (Host Engine)│ (Path Gate)  │    │ (Stage USD)  │   │
│ └──────────────┘      └──────────────┴──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 1 · Substrate Prohibitions & Formal Laws Matrix

The seam module inside Synapse is forced almost entirely by what the substrates forbid:

| Substrate | Temporal Focus | Core Prohibitions & Formal Laws | Seam Responsibility |
|---|---|---|---|
| Moneta | PAST (Memory) | No LLM calls · No background threads · No implicit config · Max 1 handle per storage_uri · No 4th decay point. | Retains decaying facts (U = e^{−λt}); executes Pre-Generation Diagnostic Retrieval Monitoring (PG-DRM). |
| Hanish | PAST (Ledger) | No raising to host · No MISS from absence · Append-only · Adjudication before evidence · No rescoring retries. | Records immutable precommit forecasts and settles HIT / MISS / UNRESOLVABLE outcomes. |
| SALUS | PRESENT (Boundary) | No execution of unvalidated path sequences S_k · No bypass of path policy gates · No LLM self-attestation. | Evaluates f(I, S_k, a_{k+1}, Ω) deterministically prior to precommit and main-thread execution. |
| Synapse | PRESENT (Host) | No claiming unobserved outcomes · No estimating unmeasured values · No hou.* off main thread · No un-attested acts. | Owns model/embedder execution, main-thread Houdini execution, and panel observation channel. |
| Octavius | FUTURE (Stage) | No message passing · No state changes out of turn · No unsanitized metadata propagation. | Composes parallel multi-agent stage states with AST quine sanitization. |
| jacobian-monologue | OFF-LOOP (Probe) | No operational runtime dependency. | Measures context position bias (ρ = +1.0) and drives V0.5 domain ablation benchmarks. |

## 2 · Hardened Architectural Invariants (3x Production Hardening Loop Result)

1. **O(1) Bounded Path Evaluation (S_k):** Evaluates a sliding window of N=20 recent
   actions combined with a rolling SHA-256 digest of historical path state, locking SALUS
   latency under 2ms: `S_k ≈ (SHA256(a_1 … a_{k-20}), t)`.
2. **Pre-Precommit Interception Gate:** SALUS path policy evaluation (f(I, S_k, a_{k+1}, Ω))
   acts as a strict circuit breaker at Step 5. Blocked actions abort before
   `LedgerPort.author()` is invoked, keeping Hanish's 3-state ledger 100% free of
   blocked-action records.
3. **In-Memory Copy-on-Write (CoW) Stage Sanitization:** StagePort sanitizes Octavius USD
   layers inside an isolated in-memory buffer within Synapse's layer stack, stripping
   metadata quines without writing back to disk or triggering out-of-tick cooks.
4. **Deterministic PG-DRM Context Filtering:** Moneta's memory retrieval filter relies
   strictly on deterministic string tokens, metadata flags, and vector distance
   thresholds — never LLM inference — preserving Moneta's zero-LLM rule:
   `(Context, Task Context) → {ALLOW, DROP}`.

## 3 · Master 10-Step Execution Pipeline

| Step | Phase | Execution Substrate | Operational Function & Latency Contribution | Failure Fallback |
|---|---|---|---|---|
| 0 | Intent | Synapse Panel | User inputs prompt or triggers automated TOPS graph action. | Empty prompt drops turn. |
| 1 | Compose | StagePort (Octavius) | Reads local scene + Octavius stage quines. (<15ms) | Fallback: local Houdini scene context only. |
| 2 | Wake | MemoryPort (Moneta) | USD relation predicate evaluates scene memory set (U = e^{−λt}). | No matching relations: proceed with flat prompt. |
| 3 | Recall & Filter | MemoryPort (Moneta) | PG-DRM filters retrieved task-contaminated context prior to prompt assembly. | Contaminated chunks dropped; clean context passed. |
| 4 | Plan | Synapse Model Host | Model proposes candidate next action given intent I and scene context Ω. | Model timeout (30s): turn marked UNAVAILABLE. |
| 5 | Path Gate | SafetyPort (SALUS) | Computes f(I, S_k, a_{k+1}, Ω); evaluates S_k bounded window. (<2ms) | P(violation) > 0 ⟹ BLOCK. Aborts turn prior to precommit. |
| 6 | Precommit | LedgerPort (Hanish) | Deterministic mapper derives confidence P ∈ [0.0, 1.0]. Authors claim. | Precommit write failure: logs error, sets state to EXPOSED. |
| 7 | Act | Synapse Host | Main-thread Houdini execution (hou.*). | Python/Houdini exception: captured as observation error. |
| 8 | Observe | Synapse Panel Path | Handler emits cook result, prim counts, or scene node hashes on WebSocket observation channel. | WebSocket timeout: marks forecast UNRESOLVABLE. |
| 9 | Settle & Learn | LedgerPort → MemoryPort | Hanish settles HIT/MISS/UNRESOLVABLE. Synapse writes settlement deposit to Moneta with protected_floor. | UUID expired: written as new deposit with protected floor. |

## 4 · Substrate Interface Contracts (`python/synapse/loop/ports.py`)

```python
from typing import NamedTuple, Optional, List, Dict, Any

class PortResult(NamedTuple):
    status: str  # "SUCCESS" | "UNAVAILABLE" | "BLOCKED"
    payload: Optional[Dict[str, Any]]
    error_message: Optional[str] = None

class SafetyPort:
    """Out-of-prompt path policy evaluator backed by SALUS."""
    def evaluate_path(
        self,
        agent_id: str,
        path_history_hash: str,
        recent_actions: List[Dict[str, Any]],
        proposed_action: Dict[str, Any],
        scene_state_digest: str
    ) -> PortResult:
        ...

class MemoryPort:
    """Decaying semantic memory & PG-DRM retrieval filter backed by Moneta."""
    def query_and_filter(
        self,
        relation_keys: List[str],
        task_context_tokens: List[str]
    ) -> PortResult:
        ...

class LedgerPort:
    """Epistemic precommit and observation ledger backed by Hanish."""
    def author_precommit(
        self,
        claim_predicate: str,
        probability: float,
        world_ref: str
    ) -> PortResult:
        ...

class StagePort:
    """In-memory Copy-on-Write USD stage reader backed by Octavius."""
    def compose_sanitized_stage(
        self,
        stage_identifier: str
    ) -> PortResult:
        ...
```

## 5 · Version Ladder 5.1 & Verification Metrics

| Version | Primary Scope & Capabilities | Gate to Next Version |
|---|---|---|
| V0.0 | Recipe builds. StagePort CoW read-only. GREEN predicates from mapper. Precommit authored before hou.* mutations. All turns marked EXPOSED. | closure_rate = 1.0, zero false verdicts, closes without Octavius stage present. |
| V0.1 | SafetyPort (SALUS) path policy evaluator f(I, S_k, a_{k+1}, Ω) active with N=20 sliding window. | Path state S_k successfully tracked across multi-step turns; unauthorized sequences blocked. |
| V0.2 | PG-DRM active inside MemoryPort. SALUS separation control attested for narrow tool paths. First BLIND calibration samples logged to Hanish. | Contaminated memory chunks dropped prior to prompt assembly; first BLIND sample recorded. |
| V0.3 | StagePort USD metadata quine filter active. Drain points wired (LedgerPort.process()). Prediction debt displayed in panel. | Zero USD metadata quine propagation; prediction debt visible in panel and falling over sessions. |
| V0.4 | Outer ring formation over MCP. Multi-agent stage formations propose plans; SALUS evaluates path sequence; Synapse executes. | Multi-agent formation plan builds and settles under full path governance. |
| V0.5 | Metrology & Domain Ablation. Execute benchmark suite via jacobian-monologue measuring K2 position control, PG-DRM, and path policy latency under Houdini 22. | Quantitative bounds established for position bias and memory safety in production. |

## 6 · Architectural Evolution Comparison Matrix

| Dimension | The Loop v3.0 | The Loop v4.0 | The Loop v5.1 (Master) |
|---|---|---|---|
| Safety Model | Single-parameter checks (e.g., voxel_size >= 0.01). | High-level sequence checks. | Formal Path Governance: Evaluates f(I, S_k, a_{k+1}, Ω) deterministically out-of-prompt under 2ms. |
| Memory Risk Defense | Time-based decay (U = e^{−λt}) only. | Passive longitudinal entropy caps. | PG-DRM Pre-Generation Filter: Drops contaminated context before prompt construction without LLMs. |
| Multi-Agent Defense | Out-of-process runtime isolation. | Prompt warning headers. | In-Memory CoW Sanitizer: Strips prompt quines from USD customData before LOP composition. |
| Pipeline Interception | Step 4 (Plan & Gate). | Step 5 (Path Gate). | Step 5 Circuit Breaker: Evaluates S_k bounded window before precommit logging overhead. |
| Metrology Integration | K2 position bias probing. | K2 position bias matrix. | K2 position bias matrix: Combines K2 position control with PG-DRM memory safety benchmarks. |

---

## Honest-seam addendum (harness contract, not part of the source spec)

The shelf has **six repositories; Synapse owns one.** At the time of the V0.0 build only
Moneta is integrated and live (the current `python/synapse/memory/` substrate). Hanish,
SALUS, Octavius, and jacobian-monologue are **spec-grounded, not installed**. The seam
therefore obeys the phantom-API law from CLAUDE.md: a port whose substrate is absent
reports `UNAVAILABLE` with the reason — **never** a fabricated `SUCCESS`, never a claimed
`BLOCK`, never a guessed verdict. Absence is a measured fact, not a missing feature.

- **MemoryPort** wraps the live Moneta seam (in-Houdini reachable; headless reports
  UNAVAILABLE unless the seam resolves).
- **LedgerPort** authors real, durable, append-only precommits (V0.0 invariant); its
  `settle()` reports UNAVAILABLE until Hanish lands — which is exactly why every V0.0 turn
  is marked EXPOSED.
- **SafetyPort** reports UNAVAILABLE until SALUS lands (V0.1 target). The deterministic
  predicate policy (`python/synapse/loop/mapper.py`) is the *spec* of f; it is exercised
  by tests and probes, never claimed as a live gate.
- **StagePort** reports UNAVAILABLE until Octavius lands, with zero side effects — which
  is the V0.0 gate's "closes without Octavius stage present."
- **jacobian-monologue** is off-loop by construction; nothing in the runtime depends on it.
