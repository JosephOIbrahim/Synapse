# FORGE Spec — APEX-verify probe harness (the Science Harness's first run)

**Status:** ARCHITECT → FORGE handoff. The Science Harness's debut (see `SYNAPSE_SCIENCE_HARNESS.md`). Scaffold is standalone-buildable; the probes are hython-gated.
**Lineage:** the §0 harness, pointed at the one Scaffold item §3 still admits as a genuine search.

## The two §0 inputs (this is why it's admitted, not a build)
- **Target:** the Houdini 21.0.671 **APEX API surface** — `apex.Graph` / `apex::graph`, port conventions, node-type names, callback shapes. Direction unknown; the H21 surface diverges from training data (the Spike 3.0 PDG audit already proved this for `pdg.*` — `hou.pdg.*` absent, `PyEventCallback` mis-named, `addEventCallback` returns `None`).
- **Eval signal:** `dir()` / `getattr` presence + callability in a live 21.0.671 interpreter. Binary per-probe, but the *space* is noisy and unknown → search-shaped. Promotion = confirmed-present on a **second independent hython env** (the second-seed form for an API surface, per harness §4).

This is the existing **"verify the API before you spend on it"** invariant (harness §4), mechanized — recording confirmations *and* absences so they're never re-walked.

## Key dependency insight
The probes need a live 21.0.671 interpreter, but **NOT the blocked WS `execute_python`** — they run via **headless `hython`** (referenced in `cognitive/dispatcher.py`; the memory note "use 21.0.671 hython for headless API checks"). So **this search is independent of the `execute_python` fix** — it can run today. Registry persistence uses the already-shipped `synapse_write_report` (blocker-free) or the Moneta backend.

## Architecture

Roles are sequential session identities (harness §1): ARCHITECT proposes the probe set + ranks, FORGE runs one probe at a time, CRUCIBLE kills weak probes pre-spend and refuses unconfirmed promotions.

```
proposal:  ProbeSpec { surface: "apex.Graph.addNode", kind: attr|call|construct,
                       expect: present|absent|unknown, rationale, rank }
experiment: one hython dir()/getattr probe per spec — atomic, idempotent,
            read-only (no transaction needed; nothing mutates)
critic:     drops probes already in the registry (confirmed/dead-end) before spend;
            refuses to promote a "present" without a second-env confirmation
record:     Champion (confirmed surface) / DeadEnd (absent or mis-shaped) written
            via synapse_write_report or a Moneta deposit (protected_floor pinned)
```

## Module layout (new — `python/synapse/science/`)
| File | Responsibility | Standalone? |
|---|---|---|
| `science/probe.py` | `ProbeSpec` + `ProbeResult` dataclasses; the dir()/getattr probe *body* (a pure function `probe(surface) -> ProbeResult` that runs inside hython) | dataclasses yes; body runs in hython |
| `science/registry.py` | `DeadEnd`/`Champion` write+read over `synapse_write_report` and/or Moneta; dedup by `(surface, kind)`; "already known?" lookup | **yes** |
| `science/loop.py` | the named loop: rank proposals, skip known, dispatch probe, record, halt-and-surface on ambiguity | **yes** (with the probe dispatch injected) |
| `science/apex_probes.py` | the seed `ProbeSpec` set for APEX (lifted from `panel/apex_recipes.py` + `apex_explainer.py` assumptions, turned into verifiable claims) | **yes** |
| `scripts/run_apex_verify.py` | headless-hython entrypoint: imports the probe bodies, runs them in-process under hython, emits `ProbeResult`s | runs in hython |

The loop, registry, dedup, and ranking are **pure Python → fully unit-testable without Houdini.** Only the probe *bodies* execute in hython.

## Probe protocol
- **One probe = one atomic, idempotent, read-only `dir()`/`getattr` check.** No undo group (nothing mutates). Re-running is free and safe.
- A probe records: surface, kind, `present` (bool), `callable` (bool), `signature` (if introspectable), `error` (if `getattr` raised). 
- **Verify before spend:** a recipe-build experiment may NOT reference an APEX surface whose probe isn't a confirmed Champion.
- **Second-seed:** a `present` result promotes to Champion only after a second independent hython invocation confirms it (guards against a dirty session / stale module).

## Registry (re-grounded persistence)
A `DeadEnd`/`Champion` is a JSON record (harness §2 schema). Write path:
1. **Preferred:** Moneta deposit — payload = the record JSON, `protected_floor` pinned (a verified API surface must not decay), `memory_type` tag `science:apex`. Auditable, queryable, dedup-friendly.
2. **Fallback:** `synapse_write_report` to `science/apex_registry.jsonl` (blocker-free; works with Moneta default-off).
The registry is also a **coaching surface**: "we confirmed `apex.Graph` exists but `addNode` takes `(nodetype, name)` not `(name, nodetype)`" beats silently re-guessing.

## Tests (standalone — the scaffold is the testable part)
- `registry.py`: write→read round-trip; dedup by `(surface, kind)`; "already known?" returns True for a recorded surface; both backends (Moneta when available, JSONL fallback).
- `loop.py`: ranks proposals by `rank`; **skips probes already in the registry** (no re-spend); halts-and-surfaces on an ambiguous result; records Champion vs DeadEnd correctly; promotion requires the second-seed flag.
- `probe.py`: `ProbeResult` serialization; a mocked probe body (inject a fake namespace) classifies present/absent/mis-shaped correctly without Houdini.
- `apex_probes.py`: the seed set parses and is non-empty; each spec has a rationale + expectation.

## Houdini-gated (headless hython, manual or scripted)
- `scripts/run_apex_verify.py` under 21.0.671 hython: runs the seed probes, emits `ProbeResult`s, and the loop records them to the registry. The **first real search run**: confirm/refute the APEX surfaces `apex_recipes.py` currently *assumes*.

## Gates & invariants (harness §4)
- One probe per experiment; idempotent; read-only (no transaction needed).
- **Verify-before-spend is the search itself** — no recipe build against an unconfirmed surface.
- USD/Moneta provenance on every Champion/DeadEnd (the audit trail is the thesis).
- Halt-and-surface on: hython unavailable, probe raises unexpectedly, or a result contradicts a prior Champion (drift → re-verify, don't silently overwrite).
- **No silent re-walk:** the loop MUST consult the registry before proposing a probe (the anti-sprawl payoff).

## Risks / notes
- Low blast radius — read-only probes, scaffold is pure Python. The only "spend" is hython startup per probe batch (amortize: run the whole seed set in one hython session, not one process per probe).
- Don't over-build the loop before the seed run proves value (harness §6: single-track first; multi-team deferred).

## Definition of done
Scaffold green standalone (registry round-trip, loop skip-known + record + second-seed gate, probe classification). Then **one real headless-hython run** of the APEX seed probes that writes confirmed/absent surfaces to the registry — the harness's first genuine search, recorded losslessly. CRUCIBLE attacks: can a probe falsely report "present" (dirty session)? does the loop ever re-walk a dead-end? does a drift contradict a Champion silently?

---
*Pairs with `FORGE_SPEC_execute_python_fix.md`. This one needs only headless hython; that one unblocks the interactive WS path. Independent — either can ship first.*
