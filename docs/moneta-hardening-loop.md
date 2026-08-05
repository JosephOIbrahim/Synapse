# Moneta Hardening Loop — 2xs Production Scaffold

> **Design:** harness-architect playbook, design + evaluation  
> **Shape:** Workflow orchestrator (hardening audit)  
> **Purpose:** Second pass over all Phase 0-5 changes — verify, harden, document, production-proof

---

## 0. THE JOB

**What the harness serves:** The Moneta-SYNAPSE memory substrate — all changes from Phases 0-5.

**What job it owns:** Ensure every change is production-hardened — tested, observable, reversible, documented.

**What actions agents may take:**
- Read all modified files
- Run tests
- Add error handling
- Add logging/telemetry
- Add rollback documentation
- Add edge-case tests

**What must never happen:**
- Change the MemoryStore interface
- Break the live Moneta backend
- Remove a safety gate
- Add untested code paths

---

## 1. HARDENING DIMENSIONS

### D1: Error Handling

Every new code path must answer:
- What happens when this fails?
- Is the failure silent or loud?
- Can the caller recover?
- Is there a fallback?

**Checklist:**
- [ ] Vector recall: what if `Moneta.query()` raises? → fallback to keyword scan
- [ ] Attention signaling: what if `signal_attention()` raises? → log and continue
- [ ] Periodic save: what if `save()` raises? → log and continue (next add retries)
- [ ] Periodic consolidation: what if `run_sleep_pass()` raises? → log and continue
- [ ] Scene memory Moneta deposit: what if Moneta is unavailable? → skip gracefully
- [ ] USD schema registration: what if `PXR_PLUGINPATH_NAME` is invalid? → pxr falls back gracefully
- [ ] `use_real_usd`: what if USD target path is unwritable? → fallback to MockUsdTarget

### D2: Observability

Every new code path must answer:
- Can I see this happening in production logs?
- Can the doctor check report its status?
- Can I distinguish "not configured" from "configured but broken"?

**Checklist:**
- [ ] Vector recall active/inactive logged on search
- [ ] Periodic save fires logged with memory count
- [ ] Consolidation prunes logged with PruneAudit
- [ ] Attention signaling logged at debug
- [ ] USD schema registration status in doctor
- [ ] `use_real_usd` status in doctor
- [ ] Scene memory Moneta deposits logged at debug

### D3: Test Coverage

Every new code path must have:
- Positive test (it works)
- Negative test (it fails gracefully)
- Edge case test (boundary conditions)

**Checklist:**
- [ ] Vector recall: test with text query, test with empty text, test with Moneta unavailable
- [ ] Attention signaling: test with results, test with empty results, test with Moneta unavailable
- [ ] Periodic save: test timer fires, test timer doesn't fire, test save failure
- [ ] Periodic consolidation: test with >1000 entities, test with <1000 entities
- [ ] Scene memory Moneta deposit: test with Moneta available, test with Moneta unavailable
- [ ] USD schema: test registered, test unregistered, test invalid path
- [ ] `use_real_usd`: test enabled, test disabled, test fallback on failure

### D4: Rollback

Every change must have a documented rollback path:

| Change | Rollback |
|---|---|
| Cosine clamp in moneta package | Revert api.py and vector_index.py changes |
| Vector recall in search() | Revert search() to use `_iter_memories()` only |
| Periodic save timer | Remove `_last_save` check in add() |
| Periodic consolidation | Remove `_add_count` check in add() |
| Attention signaling | Remove `signal_attention()` call in search() |
| Sleep pass gate | Remove `sleep_pass` from OPERATION_GATES |
| Schema registration | Remove `PXR_PLUGINPATH_NAME` from packages/synapse.json |
| `use_real_usd` | Set back to False in MonetaConfig |
| Scene memory Moneta deposit | Remove try/except block in write_memory_entry() |
| evolution.py removal | Restore from git: `git checkout -- python/synapse/memory/evolution.py` |
| Unified recall | Revert _augment_with_knowledge() changes |

### D5: Documentation

Every change must be documented:
- In the source file (docstrings, comments)
- In the architecture doc (`docs/moneta-production-harness-architecture.md`)
- In the deep review (`docs/moneta-deep-review-2026-08-05.md`)

---

## 2. EXECUTION PLAN

### Agent 1: Error Handling Audit

Read every modified file and verify error handling:
- `moneta_store.py` — vector recall, attention signaling, periodic save, periodic consolidation
- `scene_memory.py` — Moneta deposit in write_memory_entry()
- `handlers_memory.py` — sleep pass gate
- `packages/synapse.json` — schema registration

For each, add try/except with appropriate logging. Failures must never propagate to the caller.

### Agent 2: Observability Audit

Read every modified file and add logging:
- INFO for significant events (save fired, consolidation pruned, vector recall active)
- DEBUG for routine operations (attention signaled, scene memory deposited)
- WARNING for recoverable failures (save failed, consolidation raised)
- ERROR for unrecoverable failures (Moneta unavailable when configured)

Add doctor check entries for:
- Vector recall status (active/inactive)
- USD schema registration status
- `use_real_usd` status
- Consolidation last-run timestamp

### Agent 3: Test Coverage Audit

Read every modified file and add tests:
- For each new code path, verify there's a positive test, negative test, and edge case test
- Add missing tests to the appropriate test file
- Run the tests to confirm they pass

### Agent 4: Rollback Documentation

Write a rollback section in `docs/moneta-production-harness-architecture.md`:
- For each change, the exact rollback command
- For each change, the data safety consideration (will this lose data?)
- For each change, the order dependencies (must roll back X before Y)

### Agent 5: Integration Test

Run the full test suite and verify:
- All moneta tests pass
- No regressions in the broader suite
- The save timer tests pass
- The vector recall parity tests pass
- The consolidation tests pass

---

## 3. ACCEPTANCE CRITERIA

| Criterion | How to verify |
|---|---|
| All error paths are caught | grep for `try`/`except` around every new code path |
| All significant events are logged | grep for `logger.info`/`warning`/`error` on every new code path |
| All new code paths have tests | pytest collects and passes them |
| Rollback is documented | `docs/moneta-production-harness-architecture.md` has rollback section |
| Full suite passes | `pytest tests/test_moneta_*.py` — 0 failures |
