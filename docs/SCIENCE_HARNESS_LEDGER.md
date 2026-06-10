# SYNAPSE Science Harness — Ledger (tracked)

> v4 Floor §4a.3: provenance lives in version control. This is the interim home
> until Phase 0a's `synapse_write_file` lands the canonical Ledger in `agent.usd`
> (§2). Append-only. `verified_by` is mandatory on every entry.

---

## Session 2026-06-05 — Phase 0.0 · CONFIRM THE POSTURE (§0.7) · TRACK H

**Running build (live-verified, not trusted):** `hou.applicationVersionString()` = **21.0.631**.
**Bridge:** `ws://localhost:9999/synapse` — `pong`, protocol `4.0.0`.
**Instrument:** live `mcp__synapse__houdini_execute_python` (MCP → mcp_server → WS `/synapse` → `_handle_execute_python`). The raw-WS `phase0_0_probe.py` (envelope corrected this session) was prepared as a fallback; V1 evidence came via the MCP tool against the live `/synapse` transport.

### Confirmation — Q1: execute_python round-trips
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does `execute_python` round-trip on the running build?
- **direction:** live multi-line payload (`v=hou.applicationVersionString(); d={...}; result=...`)
- **measured_delta:** returned `SYN_P00|build=21.0.631|multiline_dict_sum=6` — multi-line + dict literal survived transport, executed, value correct, no mangling.

### Confirmation — Q2: no live transport enforces consent on execute_python
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does any live transport enforce consent on `execute_python`?
- **direction:** (a) observed — the Q1 call executed with ZERO consent interaction; (b) live `inspect.getsource(SynapseHandler._handle_execute_python)` (77 lines)
- **measured_delta:** handler has **no** `consent` / `HumanGate` / `_check_consent` / `.propose()`; does **not** route through `LosslessExecutionBridge`; exposes full `__builtins__`. Consent is NOT enforced. Confirms §0.7 ("ungated") on the `/synapse` WS transport; the shared handler path applies to both transports.

### Confirmation — Q3: the S4 blocking consent poll still exists in the running build
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does the S4 consent poll still block the event loop?
- **direction:** live `inspect.getsource(shared.bridge.LosslessExecutionBridge._wait_for_decision)` (module imports OK in the running build)
- **measured_delta:** `_wait_for_decision` uses blocking `time.sleep`, no `await` → the blocking poll IS present (S4 confirmed). **Floor-honest refinement:** on the live transport consent is bypassed (Q2), so the poll is not invoked there — the event-loop block is **latent**, activating only if consent is enforced via the bridge path (D1-A / §4c.3). The blocking *nature* is V1; "blocks the live loop today" is **not** claimed (un-triggerable → fail-closed).

### DeadEnd — retire the v3 deadlock search (§0.7)
- **kind:** DeadEnd · **verified_by:** V1 · **ts:** 2026-06-05
- **question:** "what holds the lock that never releases?" (v2/v3 Phase 0b deadlock track)
- **rejection_reason:** not a lock — an absent gate. `execute_python` is not blocked; it round-trips and is ungated (Q1/Q2). The deadlock search is **retired**; its budget moves to D1 (the consent decision) + Phase 0c. v4 §0.7 reframe confirmed live.

### DocConformance — harness target build vs running build
- **kind:** DocConformance · **verified_by:** V1 · **ts:** 2026-06-05
- **claim_text:** "harness verification target is H21.0.671"
- **claim_locus:** `SYNAPSE_SCIENCE_HARNESS_v4.md` (§4a.1 / §7 target line)
- **code_locus:** live `hou.applicationVersionString()` = `21.0.631`
- **bound_by:** value · **holds:** **false**
- **note:** operator deliberately switched 671→631 to bring up a working bridge. Posture findings are codebase-determined (build-invariant), so they transfer. **REQUIRES RATIFICATION:** re-pin the harness target to 631, or switch the host back to 671. Until ratified, the Confirmations above stand as `against_build=21.0.631`.

### Deferred — panel does not retain a reference to its SynapseServer (found during bring-up)
- **kind:** Deferred · **verified_by:** V1 · **stakes:** high · **probed:** false
- **area:** the panel creates `SynapseServer` but keeps no hard reference → it is garbage-collected → no listener binds 9999. This was the root cause of tonight's outage; the bridge came up only after a manual hard-ref start in the Houdini Python Shell (`builtins._synapse_manual_srv = srv`). Confirmed by `gc.get_objects()` finding no `SynapseServer` while `start_server`/`process_server_connections` threads were alive and three ephemeral 127.0.0.1 listeners (14725/48626/8912 — none on 9999) existed.
- **why_it_matters:** the bridge silently dies on GC; every external client loses connectivity with no error surfaced. Belongs in the hardening PRD (panel must retain the server instance; also flag the IPv4-only `127.0.0.1` bind vs `localhost`→`::1` client resolution). Not fixed — Phase 0.0 scope only.

---

## Session 2026-06-05 — Phase 0b · CONSENT POSTURE (D1) · TRACK H

**Operator ratification:** harness target re-pinned **671 → 21.0.631** (the build verified live in Phase 0.0). The Phase 0.0 build `DocConformance` now reads **holds=true** (target == running build).

### Decision — D1: consent posture for execute_python / execute_vex
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** close the doc/code gap (docs claim CRITICAL-gated; live path is ungated)?
- **decision (operator, D1):** **delete the doc claim** — keep single-user-localhost auto-approve; do NOT add a handler-layer gate now. A real gate (D1-a) is a prerequisite for multi-user/studio.
- **change_applied:** CLAUDE.md §1.2 — added a "Live-path reality" note (gate levels govern bridge-routed ops; the live `/synapse` handler path is ungated: full `__builtins__`, no consent/filter/cap). CLAUDE.md safety rule 5 — qualified "consent gates are real **on the bridge path only**". New pinning test `tests/test_phase0b_consent_posture.py`.
- **measured_delta:** test green (2 passed) against live `inspect.getsource` of `_handle_execute_python` / `_handle_execute_vex` — no `HumanGate`/`_check_consent`/`.propose(`/`GateProposal`. Conformance pinners unbroken (50 passed incl. test_router_internals + test_pass7).
- **artifact_path:** CLAUDE.md, tests/test_phase0b_consent_posture.py

### DocConformance — execute_python/execute_vex consent claim
- **kind:** DocConformance · **verified_by:** V1 · **ts:** 2026-06-05
- **claim_text:** "execute_python/execute_vex are CRITICAL-gated / consent enforced"
- **claim_locus:** CLAUDE.md §1.2 gate table + safety rule 5 (now corrected)
- **code_locus:** `handlers.py::_handle_execute_python` / `_handle_execute_vex` (no consent gate; live `/synapse` bypasses the bridge)
- **bound_by:** mechanism (`tests/test_phase0b_consent_posture.py`) · **holds:** **true** (doc now matches code; the test binds them — adding a gate forces a doc+test update together)

### INT-1 — sequenced to Phase 0c
- **kind:** Deferred · **verified_by:** V1 · **stakes:** medium · **probed:** false
- **area:** make `bridge._wait_for_decision` consent wait async (`await asyncio.sleep`, no blocking `time.sleep`). Touches `bridge.py`, which holds the uncommitted S1 change — landing INT-1 **with** S1 in Phase 0c keeps one clean bridge.py batch (avoids partial-committing around S1). Confirmed CTO sequencing call.

### Deferred — D1 residue / D2 (surfaced, not fixed)
- **kind:** Deferred · **verified_by:** V1 · **stakes:** low/medium · **probed:** false
- **area:** (1) README.md diagrams + the "consent-gated" package description — **RESOLVED 2026-06-06**: relabeled the diagram nodes (lines 31, 366) to the real live mechanism (`SynapseHandler`: undo / main-thread / integrity), fixed the three "routed through the bridge" prose claims, dropped "consent-gated" from `pyproject` description + refreshed keywords. (2) CLAUDE.md safety rule 2 "Every mutation through the bridge — the only code path to Houdini" is **false** on the live path (§0.8 master finding) — that is **D2/ARC-1**, not D1; left for the bridge-fate decision.

---

## Session 2026-06-05 — Phase 0c · S1 / GIT-0 · TRACK H

### Confirmation — S1: composition-failure rollback is single + clean (COMMITTED)
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does the bridge's composition-failure path roll back single + clean on the ratified build?
- **change_applied:** `shared/bridge.py` — inner `hou.undos.performUndo()` deleted inside the open undo group at **both** S1 sites (`_execute_houdini` + `_sync_payload`); the outer `except` performs the single rollback. This entry **commits** that fix (GIT-0) after re-verifying on 631.
- **measured_delta:** re-ran `.scout/s1_repro.py` on **631 hython** → `RESULT_ERROR='USD Composition violation on /obj'` (correct signal restored), synapse op rolled back, `ARTIST_ACTION` preserved, undo depth 1→1, `S1_VERDICT=SINGLE_UNDO_CLEAN`. Identical to the 671 result — build-stable.
- **artifact_path:** `shared/bridge.py` · **probe:** `.scout/s1_repro.py`

### SubstrateAssumption — undo-group rollback is single + clean (sync / _sync_payload paths)
- **kind:** SubstrateAssumption · **verified_by:** V1 · **ts:** 2026-06-05
- **mechanism:** "undo rollback is single + clean on the composition-failure path"
- **probe:** `.scout/s1_repro.py`, live H21.0.631 hython
- **holds:** **true** (for mutating ops) — flips from the open S1 `holds=false`. Unblocks the v4 §4b reversibility precondition for the `_execute_houdini`/`_sync_payload` paths.
- **scope/caveat:** the empty-group over-undo edge remains (pre-existing, separate — Phase 0.0/crucible). INT-1 (async consent wait, same `bridge.py`) is the next 0c increment — now a clean change since `bridge.py` is committed.

### Confirmation — SEC-0: hwebserver origin validation no longer NameErrors
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does the hwebserver `connect()` raise `NameError` before origin validation?
- **change_applied:** `python/synapse/server/hwebserver_adapter.py` — added `import os` (line 24). `connect()` calls `os.environ.get(...)` at `:108` (before `validate_origin` at `:109`) while `os` was **never imported** anywhere in the file (grep: the sole `os` occurrence was the usage) → deterministic `NameError` on every upgrade.
- **measured_delta:** BEFORE — `os` used, not imported (static-confirmed). AFTER — `import os` present; `py_compile` OK; pin test green (`tests/test_phase0c_sec0_hwebserver_os.py`, reads source by path → CI-safe). The DNS-rebinding origin check now actually runs on the hwebserver transport.
- **artifact_path:** `python/synapse/server/hwebserver_adapter.py`, `tests/test_phase0c_sec0_hwebserver_os.py`

### Confirmation — INT-3: _verify_composition fails CLOSED
- **kind:** Confirmation · **verified_by:** V1 (deterministic pin, build-agnostic — no Houdini in the except path) · **ts:** 2026-06-05
- **question:** does the Scene Integrity anchor fail OPEN on a validation exception?
- **change_applied:** `shared/bridge.py::_verify_composition` — the `except` block returned `True` (fail-OPEN: `composition_valid=True`/`fidelity=1.0` having validated nothing). Now returns `False` (fail-CLOSED, v4 §4a). The legitimate early returns (no hou / no node / no stage = nothing to validate) stay `True`.
- **measured_delta:** pin (`tests/test_phase0c_int3_fail_closed.py`) — forces the production path + makes `hou.node` raise → returns `False` (was `True`); a second test confirms the no-hou early return stays `True`. 24 passed incl. `test_evolution_bridge_internals` (no regression — the standalone path never hits the changed except).
- **artifact_path:** `shared/bridge.py`, `tests/test_phase0c_int3_fail_closed.py`

### Confirmation — S2: scene hash incorporates the composed LOP stage
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does the integrity hash detect composed-stage changes on the Solaris path?
- **change_applied:** `shared/bridge.py::_compute_scene_hash` — for LOP targets (`hasattr(node,'stage')`) hash the flattened composed stage (`stage.Flatten().ExportToString()`) into the digest. Previously `node.geometry()` was None for LOPs → the hash collapsed to children+cookCount, blind to composed-stage content. SOP hashing unchanged (block gated on `hasattr stage`).
- **measured_delta:** LIVE recon on 631 hython (`.scout/s2_lop_recon2.py`): flatten-export is **stable** (same stage → same hash, no false-positive) AND **attribute-value-sensitive** (sphere radius 1.0→3.5 changed the hash `eba71f4d`→`41e41471`; a path+type-only digest stayed SAME — too weak). Integration pinned by `tests/test_phase0c_s2_stage_hash.py`. 23 passed incl. bridge-internals (no regression).
- **artifact_path:** `shared/bridge.py`, `tests/test_phase0c_s2_stage_hash.py` · **probe:** `.scout/s2_lop_recon2.py`
- **caveat:** `stage.Flatten()` is O(stage size); on very heavy production stages a size-bounded digest may be preferable (future optimization). Recorded, not blocking.

### Confirmation — S3: blast-radius follows wires (outputs()), not just param refs
- **kind:** Confirmation · **verified_by:** V1 · **against_build:** 21.0.631 · **ts:** 2026-06-05
- **question:** does `_infer_stage_touch` miss a wired SOP chain feeding a SOP-Import LOP?
- **change_applied:** `shared/bridge.py::_infer_stage_touch._trace` — iterate `list(n.dependents()) + list(n.outputs())` instead of `dependents()` only. SOP→LOP data flow is BOTH param refs (a sopimport's `soppath` = dependents) AND wires (a SOP chain = outputs).
- **measured_delta:** LIVE recon on 631 (`.scout/s3_sopimport_recon2.py`): topology `box→(wire)→blast→(soppath)→sopimport`. `box.dependents()==[]` (blast is wired, not a param-dep) → dependents-only trace returns **None (MISS)**; `box.outputs()==[blast]`, `blast.dependents()==[sopimport]` → outputs+dependents returns **`/stage/sopimport1` (CATCH)**. NOTE: the simple case (`box→sopimport` directly) was *already* caught by `dependents()` — S3 is specifically the wired-chain case. Integration pinned by `tests/test_phase0c_s3_outputs_trace.py`. 29 passed across 0b/0c pins + bridge-internals.
- **artifact_path:** `shared/bridge.py`, `tests/test_phase0c_s3_outputs_trace.py` · **probe:** `.scout/s3_sopimport_recon2.py`

### DocConformance — DOC-1 (version slice): SYNAPSE version single-sourced + docs conform
- **kind:** DocConformance · **verified_by:** V1 · **ts:** 2026-06-05
- **claim_text:** "SYNAPSE version" as stated in the docs
- **claim_locus:** `CLAUDE.md:3` banner; `python/synapse/__init__.py:17` docstring
- **code_locus:** `pyproject.toml` `version=5.10.0` (canonical) == `__init__.__version__=5.10.0`
- **bound_by:** value (`tests/test_phase0c_doc1_version_conformance.py`) · **holds:** **true**
- **change_applied:** fixed the drift — CLAUDE.md `v5.8.0`→`v5.10.0` + build `21.0.596`→`21.0.631` (ratified); `__init__` docstring `Version: 5.8.0`→`5.10.0`. The test binds pyproject↔`__version__`↔docstring↔CLAUDE.md → future version drift fails loud (v4 §4a.4). 49 passed incl. existing conformance pinners (no regression).
- **follow-up (Deferred):** the **tool-count** slice (CLAUDE.md "108" vs registry 110 vs stdio-advertised 117) needs the "which count is authoritative" decision the review flagged — not rushed. Line-count magnitudes + the mechanism claim (bridge-presence) are the rest of DOC-1's surface.
- **artifact_path:** `CLAUDE.md`, `python/synapse/__init__.py`, `tests/test_phase0c_doc1_version_conformance.py`

### CRUCIBLE — INT-3 test-regression caught by the full-suite gate, fixed forward
- **kind:** Confirmation · **verified_by:** V1 · **ts:** 2026-06-05
- **note:** the full `pytest tests/` gate (run after the 0c batch) caught ONE new failure — `test_composition_validation.py::test_stage_traverse_exception_returns_true` pinned the OLD fail-OPEN contract (assert `True` on exception), which INT-3 reversed. Fixed **forward** (not weakened): updated to assert `False` (the fail-closed contract) + renamed the misleading sibling `test_exception_returns_true`→`test_no_houdini_returns_true` (it exercises the no-Houdini early return, not the except). Full suite back to the **17 pre-existing** failures (agent_state/design_system/scene_memory) — **zero introduced this session**. Lesson recorded: INT-3's focused check ran bridge-internals but not the directly-relevant composition test; the full-suite gate is load-bearing.
- **artifact_path:** `tests/test_composition_validation.py`

### Confirmation — INT-1: async consent wait (FastMCP event loop non-blocking; closes S4 on the async path)
- **kind:** Confirmation · **verified_by:** V1 (deterministic async pin) · **ts:** 2026-06-05
- **question:** does `execute_async` block the event loop while waiting for consent (S4)?
- **change_applied:** `shared/bridge.py` — `execute_async` now `await self._check_consent_async(operation)` (was the sync `_check_consent`). Added `_check_consent_async` / `_check_consent_gate_async` / `_wait_for_decision_async` (poll with `await asyncio.sleep`, mirroring the PDG path); extracted a shared `_propose_gate`. The **sync `execute()` path + `_wait_for_decision` are unchanged** (sync callers aren't in an event loop).
- **measured_delta:** pin (`tests/test_phase0c_int1_async_consent.py`) — `_wait_for_decision_async` returns True on approval, times out → False, and **YIELDS the loop** (a concurrent ticker keeps progressing while the wait is pending — proving non-blocking; blocking `time.sleep` would starve it). INFORM short-circuits; gate→async-wait returns True on approval (fake proposal, no real 120s wait). Full suite: **17 pre-existing failures, ZERO new**; 3153 passed.
- **caveat:** INT-1 only bites when consent is *actually* enforced on the bridge path; per D1/§0.8 the bridge isn't on the live transport and the panel neuters `_gate`, so this is correctness hygiene for when consent IS enabled (D1-a / a future studio mode).
- **artifact_path:** `shared/bridge.py`, `tests/test_phase0c_int1_async_consent.py`

---

## Session 2026-06-06 — Phase 0a · DURABLE WRITE-PATH · TRACK H

### Confirmation — Phase 0a: write_report is atomic + generationally backed up + binary
- **kind:** Confirmation · **verified_by:** V1 (deterministic pin) · **ts:** 2026-06-06
- **question:** does the harness have a durable (atomic + backed-up) write-path for Ledger/provenance, off Houdini's main thread?
- **approach (Floor: don't duplicate):** the existing `write_report` (`cognitive/tools/write_report.py`) was ALREADY atomic (tmp+fsync+os.replace), confined (traversal-rejected), and off-main-thread (zero `hou`). Phase 0a **upgraded** it with the missing durability — **generational backup** (`<name>.bak.1..N` before overwrite = the DR recovery point) + **binary** (base64) — rather than building a duplicate `synapse_write_file`.
- **change_applied:** `write_report.py` — added `_rotate_backups` + `backups`/`binary` params + schema; `handlers.py::_handle_write_report` exposes `backups`/`binary`.
- **measured_delta:** pins (`tests/test_phase0a_write_backup.py`) — backup rotation keeps N generations + drops the oldest beyond keep; binary round-trips 256 bytes; traversal rejected; no `.tmp` leftovers; atomicity preserved. `test_cognitive_boundary` (no-`hou`) green. Full suite: **17 pre-existing failures, ZERO new**; 3159 passed.
- **DEFERRED (Phase 0a downstream):** wire the Ledger / provenance / `Deferred` register to USE this durable path (today the Ledger is this `.scout`/`docs` markdown); the canonical `agent.usd` Ledger needs the §2 schema + RFC (Michael Gold's zone). The **primitive is the prerequisite — now done**.
- **artifact_path:** `python/synapse/cognitive/tools/write_report.py`, `python/synapse/server/handlers.py`, `tests/test_phase0a_write_backup.py`

---

## Session 2026-06-06 — CTO-FIX INTEGRATION · the 17-failure baseline cleared

The 4 fixes were authored by the CTO agent-team harness (workflow `wist00lt2`, commit-to-branch contract), each adversarially reviewed by a per-branch crucible, then integrated this session onto master (`c54d592`→`4d619dc`) via cherry-pick + the load-bearing **full-suite gate**. The baseline carried **17 pre-existing failures** (agent_state / design_system / scene_memory clusters) across the whole of Phase 0 — these 4 fixes targeted exactly those clusters and cleared them.

**GATE RESULT: `3180 passed, 56 skipped, 0 failed` — 17 → 0. Clean sweep, zero new failures.**

### Confirmation — scene-memory (MEM-1): canonical Pokémon evolver names; `synapse_evolve_memory` revived
- **kind:** Confirmation · **crucible:** CONFIRMED + safe · **ts:** 2026-06-06
- **root cause:** the handler imported `evolve_to_charmeleon` (didn't exist — function was `evolve_to_structured`) and gated on `check_evolution` returning `target=="charmeleon"` (it returned `"structured"`). The Charizard tests assert the canonical name; production wrote `"composed"`. Naming drift from CLAUDE.md §6 (charmander→charmeleon→charizard) broke the live `synapse_evolve_memory` tool AND 3 tests.
- **change_applied:** `python/synapse/memory/evolution.py` — `check_evolution` target `"structured"`→`"charmeleon"`; renamed `evolve_to_structured`→`evolve_to_charmeleon` and `evolve_to_composed`→`evolve_to_charizard` (both with **backward-compat aliases**); metadata tags `"structured"`→`"charmeleon"`, `"composed"`→`"charizard"`.
- **measured_delta:** scene_memory + evolution-bridge-internals clusters green; full suite 0 failures. Real fix at source (not a test edit) — restores a live MCP tool.
- **artifact_path:** `python/synapse/memory/evolution.py`

### Confirmation — agent-state: force the pxr-absent path in no-pxr fallback tests
- **kind:** Confirmation · **crucible:** CONFIRMED + safe · **ts:** 2026-06-06
- **root cause:** `TestNoOpWithoutPxr` asserted the pxr-absent fallback, but the dev/CI env HAS `pxr` installed → the asserted branch never ran → the tests failed. Assertions were correct; the env didn't reach them.
- **change_applied:** `tests/test_agent_state.py` — `no_pxr` fixture + autouse `_force_no_pxr` that `patch.object(agent_state, "PXR_AVAILABLE", False)`. **Assertions unchanged** (verified non-weakening: it forces the already-asserted code path, it does not relax any check).
- **artifact_path:** `tests/test_agent_state.py`

### Confirmation — design-system: cyan/blue 3-source token gremlin isolated (NOT unified)
- **kind:** Confirmation · **crucible:** CONFIRMED + safe · **ts:** 2026-06-06
- **root cause:** two legitimate token sources collide on `sys.modules["tokens"]` — repo `#8FB3D9` (muted light blue) vs panel `#00D4FF` (cyan) — import order decided which won, flaking `test_design_system` / `test_hda_panel`. The known TRAP: naively unifying them breaks `test_hda_panel`.
- **change_applied:** `tests/test_design_system.py` + `tests/test_hda_panel.py` — staleness guard `_deployed_is_fresh()`, autouse `_pin_canonical_tokens` re-pinning `sys.modules["tokens"]` to the repo tokens, and `test_hda_panel` evicts the bare `tokens`. **Isolates** the two sources order-independently without unifying them (avoids the trap). **Assertions unchanged.**
- **artifact_path:** `tests/test_design_system.py`, `tests/test_hda_panel.py`

### Confirmation — panel-gc: durable ref to the fallback websocket SynapseServer (narrative corrected)
- **kind:** Confirmation · **crucible:** PARTIAL + safe (additive; narrative overstated) · **ts:** 2026-06-06
- **change_applied:** `python/synapse/server/start_hwebserver.py` — `_fallback_server` module-global + `get_running_server()` accessor + assignment after `server.start()`; `tests/test_start_hwebserver_durable_ref.py` (3 tests, stubs the adapter in `sys.modules` so import-time `main()` never binds a socket).
- **Floor correction (this session):** the cherry-picked docstring overstated the GC risk ("Python is free to garbage-collect the server the moment main() returns"). The crucible **refuted** it: while `serve_forever()` runs on the daemon thread, the running bound method roots the server — a live serving server is NOT reaped mid-serve. Rewrote the comment to the honest value: **(1) recoverability** (a named handle vs scanning `gc.get_objects()` — the real pain that drove the `builtins._synapse_manual_srv` workaround) and **(2) the post-thread-exit window** (once the serve thread stops, a bare local becomes collectible with no handle for restart). Commit `4d619dc`.
- **artifact_path:** `python/synapse/server/start_hwebserver.py`, `tests/test_start_hwebserver_durable_ref.py`
- **FLAGGED follow-up (out of scope here):** `start_hwebserver.py:79-81` `else: main()` auto-runs `main()` at *import* (pre-existing; not introduced by panel-gc) — binds :9999 on bare import. Guard behind an explicit start call / `__name__` check. The durable-ref test self-protects via `sys.modules` stubbing; no other test imports the module bare, so the baseline was unaffected — but the auto-run is a latent CI footgun worth closing.

---

## Session 2026-06-06 — CTO BUILD: 0a′ Floor hook + worker-tools gate + agent.usd RFC

CTO unlocked agent teams + dynamic workflows. A **recon workflow** (`wiqu7nm7m`, 3 read-only cartographers) mapped each thread to its seam; a **build workflow** (`wopah2mga`, 3 `forge(worktree)→crucible` tracks) implemented them on `cto-fix/*` branches; cherry-picked onto master (`c3c9947`→`0ddf26d`) + full-suite gated. **GATE: `3217 passed, 56 skipped, 0 failed`** (was 3180; +37 new tests, zero new failures). Every crucible-surfaced issue was fixed forward — no masking test shipped.

### Confirmation — 0a′ Floor emit-time provenance hook (Tier-0)
- **kind:** Confirmation · **verified_by:** V0 (deterministic, non-`hou`) · **crucible:** confirmed + safe · **ts:** 2026-06-06
- **change_applied:** new `python/synapse/core/floor_gate.py` (`FloorGate.wrap` — one durable provenance record per *mutating* op via the atomic `write_report`, ZERO for read-only; payload/result sha256 digests; error-records-then-reraises; zero `hou`). `CommandHandlerRegistry.invoke()` (additive — `_submit_logs`/`audit_log` untouched, no double-fire) routes all 3 sites (`handle`/`_handle_batch_commands`/`_HandlerAdapter.call`). `Dispatcher` gets an optional `floor_gate=None` (no-op default → bare constructions unchanged). Footgun pre-step: `start_hwebserver.py` `else: main()` → `elif SYNAPSE_AUTOSTART_HWEBSERVER=='1'`.
- **crucible follow-up (fixed forward, commit `0ddf26d`):** the batch test was a **masking test** — it asserted `sub_op.parent == <a value the test set>`, never `== the envelope record's op_id`, hiding a **dangling linkage** (`_handle_batch_commands` minted a fresh phantom parent ≠ the envelope's real op-id). Fix: a contextvar op-id stack + `current_op_id()` so the envelope's REAL op-id (read on the handler thread before `run_on_main` marshals sub-ops away) reaches its children; the test now drives the real `SynapseHandler.handle()` batch path and asserts `parent == envelope.op_id`. Dispatcher docstring corrected (provenance fires on the is_testing branch only; live autonomy is covered via the registry adapter, not the unwired prod branch).
- **measured_delta:** `tests/test_floor_hook.py` (15 tests) + 2 `start_hwebserver` autostart guards. Full suite 0 failures.
- **DEFERRED:** unbounded `.synapse/provenance` (no rotation); synchronous fsync-per-op on the WS/main thread (single-user acceptable, tiny vs the Houdini floor); wiring the prod Dispatcher branch + the agent.usd Ledger sink (RFC below). Tier-1 admission/halt remains out of scope.
- **artifact_path:** `python/synapse/core/floor_gate.py`, `python/synapse/server/handlers.py`, `python/synapse/cognitive/dispatcher.py`, `tests/test_floor_hook.py`

### Confirmation — autonomous-worker tool ALLOWLIST gate (closes CTO deferred #1)
- **kind:** Confirmation · **verified_by:** V0 · **crucible:** confirmed + safe · **ts:** 2026-06-06
- **claim verified:** the panel `ClaudeWorker` armed the FULL ~110-tool set unfiltered (`claude_worker.py:67`) and dispatched any model-picked tool with no allowlist — `execute_python`/`execute_vex` included. Confirmed in live code.
- **change_applied:** new `python/synapse/panel/worker_policy.py` (`is_tool_allowed_for_worker`, classification from EXISTING `TOOL_DEFS` flags + `_TOOL_TO_OPERATION→OPERATION_GATES`). Default `standard` = read-only + `inform` allowed; `review`/`approve`/`critical` + unknown/unclassified-mutation DENIED (fail-closed). `SYNAPSE_WORKER_TOOL_MODE` = strict|standard|unrestricted (fail-closed on bad value). Advertise-side `get_anthropic_tools_for_worker()` (separate cache; `get_anthropic_tools()` untouched). **Dispatch-side** (load-bearing) check in `_execute_tool_block`, gated by `enforce_worker_policy=True`; the panel constructs the interactive worker with `enforce_worker_policy=False` (human-in-the-loop preserved). Hard-deny → structured `is_error` tool_result (LLM re-plans); HumanGate escalation NOT wired (deadlocks the Qt thread — deferred).
- **crucible follow-up (fixed forward, `0ddf26d`):** the 2 dispatch tests were **order-fragile** — the fixture trusted `import PySide6` succeeding, but a leaked `MagicMock` PySide6 (`test_chat_panel`) satisfied that while making `_execute_tool_block` return a MagicMock, flipping them red after `test_chat_panel`. Fix: require `QThread` to be a genuine class (`isinstance type`) before trusting real Qt (the documented [[synapse-panel-redesign]] guard). `pytest test_chat_panel test_worker_tool_policy` goes 2 failed → 100 passed. Security logic was sound either way.
- **measured_delta:** `tests/test_worker_tool_policy.py` (21 tests) incl. the bypass test (full toolset + `enforce=True` → `execute_python` blocked at dispatch, `try_mcp_tool_call` 0 calls). Full suite 0 failures.
- **DEFERRED:** the `synapse.autonomy.AutonomousDriver` render loop (render-domain handlers, lower risk) is NOT covered this pass — panel-worker only.
- **artifact_path:** `python/synapse/panel/worker_policy.py`, `python/synapse/panel/tool_bridge.py`, `python/synapse/panel/claude_worker.py`, `python/synapse/panel/synapse_panel.py`, `tests/test_worker_tool_policy.py`

### DocConformance — agent.usd Ledger schema RFC (built-not-Phase4) + 3 CLAUDE.md ghosts fixed
- **kind:** DocConformance · **verified_by:** V0 (citation self-check + live grep) · **crucible:** partial → fixed · **ts:** 2026-06-06
- **claim_text:** CLAUDE.md presented agent.usd as unbuilt "Phase 4" with files `src/memory/agent_state.py` + `agent_schema.usda` and a `Tf.MakeValidIdentifier` idiom.
- **holds:** **false** — corrected. The schema is BUILT + test-pinned (`python/synapse/memory/agent_state.py`, SCHEMA_VERSION 2.0.0, ~50 tests); the real gap is **dormant wiring** (5 provenance writers, zero live callers). `agent_schema.usda` does not exist (USDA generated inline). `Tf.MakeValidIdentifier` is unused (`evolution.py` imports only `Usd,Sdf`; `agent_state` hand-rolls `_safe_prim_name`).
- **change_applied:** new `docs/RFC_agent_usd_ledger.md` (438 lines, §1–§11) leading with "already built, needs wiring + a `/ledger/` subtree." CLAUDE.md fixes G1 (Status row → Built/dormant + real path), G2 (Phase-4 file list + agent_schema.usda ghost), G3 (Tf idiom flagged aspirational, → RFC D-3). **Crucible follow-up (`0ddf26d`):** RFC §3.3 widened to the fields the live Ledger actually carries (`claim_text`/`direction`/`probe`/`crucible`/`area`/notes — its own round-trip pin would have passed while dropping them) and the kind enumeration corrected (dropped the invented `Decision`; added the real `SubstrateAssumption`/`CRUCIBLE`).
- **DEFERRED:** the RFC is a DRAFT — implementing the `/ledger/` subtree + wiring the dormant writers + the one-time markdown→USD backfill is the build it specifies (needs ratification of D-1..D-6, incl. the `_safe_prim_name` vs `Tf` sanitizer call).
- **artifact_path:** `docs/RFC_agent_usd_ledger.md`, `CLAUDE.md`

### Confirmation — provenance-dir rotation (bounded FIFO cap) closes the 0a′ operational gap
- **kind:** Confirmation · **verified_by:** V0 · **crucible:** confirmed + safe (mutation-tested) · **ts:** 2026-06-06
- **question:** the 0a′ Floor hook writes one JSON per mutating op to `.synapse/provenance/` with no cap — unbounded growth over long sessions. Can it be bounded without breaking the live op?
- **change_applied:** `floor_gate.py` — `SYNAPSE_PROVENANCE_MAX_RECORDS` (default 5000; `<=0`/unparseable = unbounded opt-out) + a per-gate `deque` of record paths under the existing lock. `_record` calls `_rotate` AFTER `write_report` succeeds: a one-time on-startup reconcile (list `*.json`, sort-by-name == chronological, seed the deque — survives restarts), then append + `popleft`+`unlink` the OLDEST while over cap. Wrapped best-effort so housekeeping can NEVER propagate; read-only ops trigger nothing.
- **measured_delta:** `tests/test_floor_provenance_rotation.py` (9 tests). Crucible mutation-tested the guarantees: reversed sort → fails; evict-newest → fails 2; off-by-one (≥cap / >cap+1) → fail; reconcile-every-write → fails 4; read-only-rotation → fails. 8-thread × 200-op stress → exactly cap files, 0 double-unlinks, 0 leaked errors. Full suite: **3226 passed, 0 failed** (+9). Commit `0be31d7`.
- **artifact_path:** `python/synapse/core/floor_gate.py`, `tests/test_floor_provenance_rotation.py`

### Confirmation — agent.usd Ledger BUILT (RFC ratified D-1..D-6) — per-record files SoT + USD projection + lossless backfill
- **kind:** Confirmation · **verified_by:** V0 · **crucible:** dual-lens (usd-correctness CONFIRMED; data-loss PARTIAL→fixed) · **ts:** 2026-06-06
- **decision (operator, D-1..D-6 RATIFIED):** per-record JSON files = source of truth, `agent.usd` /ledger/ = composed read-projection (D-1); rich markdown superset + generic `extra` catch-all (D-2); `_safe_prim_name` not `Tf` (D-3); `/SYNAPSE/agent/ledger/` (D-4); file-first then project (D-5); atomic `write_report` for the primary files, accept the Save() gap on the derived USD (D-6).
- **change_applied:** new `python/synapse/memory/ledger.py` (zero `hou`): `LedgerRecord` (§3.3 superset + `extra` + mandatory `verified_by`), `record_filename` = `<kind>_<ts>_<sha8>` (content-derived sha8 = idempotent dedup), `deposit()` (reject empty verified_by; write per-record file via atomic `write_report` FIRST = SoT; best-effort `/ledger/<safe_prim>` USD projection that degrades on no-`pxr`/error), `parse_ledger_markdown()` (## Session / ### Kind / bulleted + inline-dotted forms; unknown keys → `extra`), `backfill()`. Surgical `agent_state.initialize_agent_usd` += the `/ledger/` group prim (+ USDA-stub line). Pinned by `tests/test_agent_usd_ledger.py`.
- **measured_delta:** REAL backfill of `docs/SCIENCE_HARNESS_LEDGER.md` → 28 records parsed, 24 deposited (`fields_lost=0`), 4 correctly skipped (genuinely lack `verified_by`). The data-loss crucible verified the parser is lossless via an independent oracle. Full suite: **3248 passed, 0 failed** (+22). Commits `018542a` (build) + `76c48d2` (fixes).
- **crucible follow-up (fixed forward, `76c48d2`):** (1) the round-trip test was a **self-comparison** (deposited file vs `asdict` of the SAME parsed record) — blind to PARSE loss (dropping `extra` stayed green). Added `TestParseFidelityOracle` (harvest every bulleted `**field:**` from the source markdown → assert each survives the parse); **mutation-proven to have teeth: healthy=0 missing, extra-dropped=33 missing→fails.** (2) session-preamble provenance (`**Running build/Bridge/Instrument/Operator ratification:**` between `## Session` and the first entry) was silently dropped → now captured into `LedgerRecord.session_meta`, lossless.
- **DEFERRED:** wiring the 5 dormant non-ledger writers (`log_routing_decision`/`log_handoff`/`log_integrity`/`write_verification`/`create_task`) to live pipeline emit points (§7.1); RUNNING the backfill for real (`.synapse/ledger/` is gitignored run-data — operator's call); the §3.3 note-channel fold (latent, no current collision); the Moneta deposit branch (default-off).
- **artifact_path:** `python/synapse/memory/ledger.py`, `python/synapse/memory/agent_state.py`, `tests/test_agent_usd_ledger.py`, `docs/RFC_agent_usd_ledger.md`

---

## Session 2026-06-06 — DORMANT-WRITER WIRING: liveness-gated (2 wired, 3 deferred) + backfill run

### Confirmation — real backfill materialized the Ledger end-to-end
- **kind:** Confirmation · **verified_by:** V0 · **ts:** 2026-06-06
- **change_applied:** ran `ledger.backfill('docs/SCIENCE_HARNESS_LEDGER.md', agent_usd_path=…)` into gitignored `.synapse/ledger/`. **29 parsed → 25 per-record `.json` (source of truth) + a 32 KB `agent.usd` with 25 `/SYNAPSE/agent/ledger/` prims**; 4 skipped (no `verified_by`). Independent re-verify: 25/25 files byte-identical to the re-parsed records, **0 mismatches**. The D-1 model is now real on disk (immutable files authoritative; USD is the composed projection).
- **artifact_path:** `.synapse/ledger/` (run-data, not committed)

### DeadEnd — 3 of 5 dormant writers have NO live emit point (wiring = theater)
- **kind:** DeadEnd · **verified_by:** V1 (5-agent liveness recon `wfeqrgk7h`, call-chain traced) · **ts:** 2026-06-06
- **probe:** trace each RFC §7.1 emit point's callers to a live entry (`/synapse` handler / `/mcp` server) or prove none.
- **measured_delta:** `log_routing_decision` — DORMANT: `MOERouter.route` fires only in tests + the dead `panel/tool_filter.filter_tools`; the LIVE router is `TieredRouter` (`handlers.py:1329`), no fingerprint/agent-pair. `log_handoff` — ASPIRATIONAL: `AgentHandoff` has zero callers under `python/synapse/`; `run_team.py` doesn't exist. `log_integrity` — FICTION-RISK: the one live `IntegrityBlock` (`/mcp` bridge) self-asserts its anchors (`undo_group_active=True` literal, never measured) — persisting it would launder a fiction; the live `FloorGate` carries a different/weaker signal. **All 3 left UNWIRED by design.** Recorded in RFC §7.1 (`c676999`) — the guardrail against future theater-wiring. ([[rsi-harness-updating-vs-benefit]])
- **artifact_path:** `docs/RFC_agent_usd_ledger.md` (§7.1)

### Confirmation — the 2 LIVE writers wired into autonomous-render (loop closed)
- **kind:** Confirmation · **verified_by:** V0 · **crucible:** partial → fixed (`w33gpbsww`) · **ts:** 2026-06-06
- **change_applied:** `_handle_autonomous_render` (handlers.py, registered live `:584`) now: `create_task` on dispatch (uuid id) → feeds the ALREADY-LIVE `suspend_all_tasks` consumer (which iterated an always-empty tasks group); `_record_autonomy_task` helper after `driver.execute` calls `update_task_status` (completed/failed) + `write_verification` (render-quality checks/score from the unconditionally-populated `RenderReport` — `report.verification` is None live, correctly avoided). Triple-guarded best-effort — proven it never breaks the render. Render-quality (NOT scene-hash) semantics documented.
- **measured_delta:** `tests/test_autonomy_task_provenance.py` (9 tests). The loop-closure test proves the live `suspend_all_tasks` consumer NOW finds a task it never could before. Crucible confirmed genuine-activation=true, breaks-render=false.
- **crucible follow-up (fixed forward, `f964865`):** dead `hard_fail` counter (matched `'hard'`; live value is `'hard_fail'`) → fixed + de-masked the test fixture vocabulary; render-raises path now marks `'failed'` (not orphan `'pending'`); added a handler-level activation test. **Test-isolation fix:** deferred the `handlers` import (`_SH` lazy helper) — importing it at collection made this module the first importer before any handler test installed its fake `hou`, leaving `handlers.hou` undefined and breaking `test_mcp_roundtrip`. Full suite: **3257 passed, 0 failed** (+9).
- **DEFERRED:** the autonomy *render-driver* internal step lifecycle (per-step `update_task_status` via a driver callback); the 3 theater writers (above) until a live producer exists.
- **artifact_path:** `python/synapse/server/handlers.py`, `tests/test_autonomy_task_provenance.py`

---

## Session 2026-06-07 — CTO AUTOPILOT: self-healing bridge port discovery

### Confirmation — bridge port-collision root-caused + fixed (clients follow the server's real port)
- **kind:** Confirmation · **verified_by:** V0 · **crucible:** confirmed + safe (no normal-case regression) · **ts:** 2026-06-07
- **question:** the MCP bridge couldn't reach a live Houdini — `synapse_ping` timed out on `:9999` even though Houdini was running. Why, and how to fix it end-to-end?
- **diagnosis (live, this session):** a 26h zombie Houdini (pid 53708) squatted `:9999` with a DEAD serve loop (TCP accepts, WS handshake times out — confirmed by raw socket probe). The user's live Houdini (pid 65288) couldn't bind 9999, so the server's **existing automatic failover** correctly moved it to 48626 and tracked it in `_actual_port` — but EVERY client was **hardcoded to 9999** and kept hitting the zombie. Client/server port mismatch, not a panel defect. (Panel itself = confirmed loading live: `SynapsePanel`, 87 children, v5.11.0, not the error-fallback; the earlier `FAIL` was a faulty faces-heuristic checking QLabel text instead of the switcher QAbstractButtons.)
- **change_applied:** new pure-Python (zero hou) `python/synapse/server/bridge_endpoint.py` — `publish_endpoint` (atomic tmp+os.replace to a HOME-anchored `~/.synapse/bridge.json`, `$SYNAPSE_BRIDGE_FILE` override), `resolve_endpoint` (read it, freshest-writer-wins, **hard fallback to (localhost, $SYNAPSE_PORT|9999) on ANY error/missing/malformed/dead-pid** — so with no sidecar behavior is byte-identical to today), `clear_endpoint` (own-pid only). Servers (`websocket.py`, `hwebserver_adapter.py`) publish after a successful bind / clear on stop; LISTEN defaults unchanged (still prefer 9999 then fail over). All 5 real client connect points resolve **resolved-port-then-9999** (belt-and-suspenders: a stale sidecar self-heals via handshake-failure fallthrough) — incl. the actual MCP→Houdini client `mcp_server._get_connection` (the one that was stranding), `agent/synapse_ws`, `panel/ws_bridge`, and dashboard JS (server-side port injection).
- **measured_delta:** `tests/test_bridge_endpoint.py` (27 cases: no-sidecar→9999 byte-identical, $SYNAPSE_PORT honored, malformed/empty/dead-pid→fallback-never-raises, atomic-no-.tmp, cross-process home-anchored path, own-pid clear). Crucible verified the cardinal no-sidecar path is unchanged + cross-process path identity. Full suite: **3284 passed, 0 failed** (+27).
- **integration follow-up (fixed forward):** the new test sorted alphabetically ahead of the handler tests; `from synapse.server import bridge_endpoint` runs `synapse.server.__init__` which eagerly imports `.websocket`→`.handlers` (`import hou`), so it became the first handlers-importer with no `hou` and stranded `handlers.hou` for every later handler test (collection `AttributeError`). A stub-`hou` fix made it WORSE (the cached stub broke the handler tests' own fakes + flipped `HOU_AVAILABLE`). Correct fix: load the **pure leaf** `bridge_endpoint.py` directly from its file (`importlib.util`), bypassing the package `__init__` entirely — zero side-imports, no pollution. Commit `3fcdb54`.
- **bounded weaknesses (accepted, noted):** (1) cosmetic — `mcp_server._warmup` log mislabels the endpoint (the authoritative log line prints the real URL); (2) `resolve` pid-checks but doesn't port-probe, so a *respawned live* zombie re-publishing 9999 AFTER the real server could clobber freshest-wins — exotic, and the crucible rates the whole change "strictly better than the status quo."
- **DEFERRED / operator action:** this activates on the **next Houdini restart** (which also clears the zombie). The currently-running session stays on 48626 until then. The pre-existing eager-handlers-import in `synapse.server.__init__` (the latent ordering fragility) could be made lazy as a future robustness pass — out of scope here.
- **artifact_path:** `python/synapse/server/bridge_endpoint.py`, `python/synapse/server/websocket.py`, `python/synapse/server/hwebserver_adapter.py`, `python/synapse/server/dashboard.py`, `python/synapse/panel/ws_bridge.py`, `python/synapse/panel/chat_panel.py`, `mcp_server.py`, `agent/synapse_ws.py`, `tests/test_bridge_endpoint.py`

---

## Session 2026-06-08 — v5 runbook continuation: DOC-1 tail + build-pinning + provenance · TRACK H

**Running build (tier policy):** headless/CI/logic = **21.0.631** · live/interactive/render = 21.0.671.
**Bridge:** out of scope this run (panel-v9-layer fix); everything below is **bridgeless** (CI/logic tier).
**Operator (CTO):** five decisions settled (recorded below); v5 is the committed source of truth (`53eceff`).

### Decisions — operator-settled (recorded, not re-litigated)
- **kind:** Confirmation · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **D-build-pinning (#1):** per environment — live/interactive/render/flipbook-pixel → 671; headless/CI/logic → 631. `against_build` MANDATORY on every VerifiedClaim, fail-closed if absent.
- **D-tool-count (#2):** the registry is canonical (110). CLAUDE.md derives from it. Transports may legitimately differ.
- **D-bridge (#3):** out of scope here — a panel-v9-layer fix; this run is bridgeless.
- **D-track-c (#4):** Track C stays CLOSED. The Allocation/Exposure schema RFC may be DRAFTED (a precondition to opening the gate, proposal only) — no schema implementation, no §2/§3/§8 FORGE specs, no Track-C code.
- **D-provenance (#5):** v4 and v3 move into `docs/`, tracked; supersession chain v3 → v4 → v5.

### DocConformance — DOC-1 (tool-count slice): stdio/HTTP transport relationship pinned (Task A)
- **kind:** DocConformance · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **claim_text:** "110 MCP tools registered" + the stdio/HTTP tool-count relationship
- **claim_locus:** `CLAUDE.md:3` banner; the stdio (`mcp_server.py`) vs HTTP (`synapse/mcp/server.py`) surfaces
- **code_locus:** `synapse.mcp._tool_registry.TOOL_DEFS` (110, canonical, zero dups)
- **bound_by:** value+mechanism (`tests/test_phase0c_doc1_toolcount.py`) · **holds:** **true**
- **measured_delta:** enumerated live — registry=110; HTTP `/mcp` (`get_tools`) lists EXACTLY the 110 core; stdio adds 7 NAMED local/transport tools (6 `synapse_group_*` knowledge preambles + `synapse_inspect_stage`, served without a Houdini connection) → 117. The +7 are legitimate transport tools, **not** duplicate registrations (A.3 HALT not triggered — `registry ∩ locals = ∅`). Two new pins: stdio == registry_core + the 7 named locals (mechanism: the assembly in `list_tools`); HTTP == registry core, locals are stdio-only (TEST-2). 3 passed.
- **artifact_path:** `tests/test_phase0c_doc1_toolcount.py`

### Confirmation — build-pinning policy: against_build required + fail-closed (Task B)
- **kind:** Confirmation · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **question:** is `against_build` enforced on VerifiedClaim emission (decision #1)?
- **change_applied:** no `VerifiedClaim` code struct exists (spec-only) → the emission path is `ledger.deposit()`. `deposit()` now rejects empty/whitespace `against_build` (fail-closed, same posture as `verified_by`). New `CUTOVER_BUILD="21.0.631"`. `LedgerRecord` docstring updated.
- **measured_delta:** `TestMandatoryAgainstBuild` (empty/whitespace raise; backfill stamps legacy). 25 passed. Commit `a4726af`.
- **artifact_path:** `python/synapse/memory/ledger.py`, `tests/test_agent_usd_ledger.py`

### Confirmation — POLICY CUTOVER (build-pinning) — append-only, no history mutated (Task B.2)
- **kind:** Confirmation · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **measured_delta:** **all Ledger Confirmations PRIOR to commit `a4726af` are `against_build=631` (CI/logic tier); 671 is the live/interactive tier henceforth.** The reader treats pre-cutover entries as 631-scoped. Existing entries are NOT mutated (append-only, D-1); `backfill()` stamps `CUTOVER_BUILD` onto legacy entries' DERIVED per-record files only — the source markdown is untouched.
- **artifact_path:** `python/synapse/memory/ledger.py` (`CUTOVER_BUILD`, `backfill` cutover)

### Deferred — 671 interactive re-probe of Phase 0.0, owed on bridge restore (Task B.3)
- **kind:** Deferred · **verified_by:** V0 · **against_build:** 21.0.631 · **stakes:** medium · **probed:** false
- **area:** Phase 0.0 (execute_python round-trip / consent posture / S4 poll) was V1-confirmed on **631**. A `671` interactive re-probe is OWED once the bridge is stable on the live build — the live/interactive tier per decision #1. Bridgeless this run, so deferred not skipped (fail-closed: the 671 rung is unclaimed until re-probed).
- **why_it_matters:** the posture findings are codebase-determined (build-invariant) so they transfer, but the live-tier `against_build=671` claim is not yet earned.

### Confirmation — provenance hygiene: v3/v4 tracked in docs/, supersession chain recorded (Task C)
- **kind:** Confirmation · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **change_applied:** moved `SYNAPSE_SCIENCE_HARNESS_v3.md` + `_v4.md` from the repo root into `docs/` (tracked); v5 already committed at `docs/SYNAPSE_SCIENCE_HARNESS_v5.md` (`53eceff`).
- **measured_delta:** **Canonical supersession chain: v3 → v4 → v5 (v5 current).** v4's spine remains load-bearing (the v5 diff keeps §0/§4b/§4c/§5/§7); v3 is twice-superseded, retained for lineage. All three now tracked under `docs/`.
- **artifact_path:** `docs/SYNAPSE_SCIENCE_HARNESS_v3.md`, `docs/SYNAPSE_SCIENCE_HARNESS_v4.md`, `docs/SYNAPSE_SCIENCE_HARNESS_v5.md`

### Confirmation — full-suite gate green post-v9 (Task D)
- **kind:** Confirmation · **verified_by:** V0 · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **question:** did this session's panel-v9 work (or Tasks A/B) regress the suite?
- **measured_delta:** `python -m pytest tests/` → **3289 passed, 67 skipped, 0 failed** (54.6s). Was 3284/0 before the v9 work; +5 passed = A's 2 + B's 3 new tests (v9's panel tests are hython-only → skip in CI). **ZERO new failures**; the pre-existing test_design_system→test_hda_panel ordering flake did not manifest. Track H A–D done over a GREEN suite (not a red one).
- **artifact_path:** (full suite)

### Deferred — Allocation/Exposure schema RFC DRAFTED, awaiting Gold (Task E · Track-C precondition)
- **kind:** Deferred · **verified_by:** V0 · **against_build:** 21.0.631 · **stakes:** high · **probed:** false
- **area:** `docs/RFC_allocation_exposure_schema.md` — ARCHITECT proposal for Michael Gold: the five-rung `verified_by` migration (legacy read shim, conservative, never auto-promoted), the `Allocation` Ledger kind, the derived `Exposure` projection (recommend compute-on-read, never stored), and THE core typed-USD-schema-vs-customData question (3 placement options; recommend Option C = the as-built `/ledger/` namespaced-string-attr pattern, fully D-1..D-6-consistent). **Design-only; no schema authored.**
- **why_it_matters:** Track-C gate condition (c). Blocked until Gold ratifies: the §2/§3/§8 FORGE specs and all Track-C code. The other two gate conditions are also unmet (no "begin Track C"; not ratified).
- **artifact_path:** `docs/RFC_allocation_exposure_schema.md`

---

## Session 2026-06-08 — Track C Phase 1: the rung-scale migration · TRACK C

**Gate opened:** all three Track-C conditions met — Track H green, operator "begin Track C", and the Allocation/Exposure schema RFC RATIFIED by the operator-as-substrate-authority (Option C: ledger namespaced string attrs; Exposure compute-on-read). Bridgeless run (CI/logic tier = 631).

### Confirmation — Phase 1: five-rung scale single-sourced + legacy shim + Floor VerifiedClaim hook
- **kind:** Confirmation · **verified_by:** V0_membership · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **change_applied:** new `python/synapse/science/rungs.py` (the five rungs {doc_only, V0_membership, V1_cook, V1_output, V1-degraded} single-sourced; `migrate_verified_by` legacy read shim — conservative: V1→V1_cook, NEVER V1_output; annotated-token recovery so `"V1 (deterministic pin)"` doesn't drop). New `python/synapse/science/verified_claim.py` (`VerifiedClaim` + `assert_verified_claim` — only V1_cook/V1_output/V1-degraded may back "verified"; doc_only/V0_membership rejected; layer ∈ {L0,L1,L2}; against_build mandatory; in-repo artifact required). `ledger.deposit` validates the five-token set FAIL-CLOSED (empty AND unknown); `backfill` migrates legacy→v5 before deposit and preserves the raw annotation in `extra.verified_by_raw` (D-2 lossless).
- **measured_delta:** logic/CI pins green (`tests/test_phase1_rungs.py` + updated `tests/test_agent_usd_ledger.py`). Full suite **3301 passed, 68 skipped, 0 failed**.
- **artifact_path:** `python/synapse/science/rungs.py`, `python/synapse/science/verified_claim.py`, `python/synapse/memory/ledger.py`, `tests/test_phase1_rungs.py`

### CRUCIBLE — Phase 1 adversarial review (dynamic workflow, 3 lenses) — 2 blockers fixed forward
- **kind:** CRUCIBLE · **verified_by:** V0_membership · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **measured_delta:** the Phase-1 crucible workflow (Floor / regression / spec lenses + synthesis) confirmed fail-closed on auto-promotion/fail-open/unmigrated-token axes and NO weakened tests, and caught two real blockers — both fixed forward: **BLOCKER-2 (Floor violation, fail-open):** the in-repo `artifact_path` guard split only on `/`, so on win32 `..\..\..\etc\passwd` was accepted → replaced with an `os.path.normpath` + both-separator predicate (`_is_outside_vc`), pinned with win32/POSIX traversal + drive-absolute cases. **BLOCKER-1 (D-2 loss):** `migrate_verified_by` exact-matched, silently dropping 6 verified legacy records with annotated tokens → leading-token recovery + a `test_backfill_skips_only_genuinely_empty` pin (skipped == non-migratable count) so the loss can never go silent.
- **artifact_path:** `python/synapse/science/rungs.py`, `python/synapse/science/verified_claim.py`, `tests/test_phase1_rungs.py`, `tests/test_agent_usd_ledger.py`

### DocConformance — deposit validation: runbook (closed) supersedes RFC §1.1 (open string)
- **kind:** DocConformance · **verified_by:** V0_membership · **against_build:** 21.0.631 · **ts:** 2026-06-08
- **claim_text:** "ledger.deposit accepts verified_by as an open string" (RFC §1.1) vs "validates the five-token set, fail-closed" (runbook Phase 1)
- **claim_locus:** `docs/RFC_allocation_exposure_schema.md` §1.1 · **code_locus:** `ledger.deposit` (rejects any non-RUNGS token)
- **bound_by:** mechanism · **holds:** **true (resolved)** — the runbook's CLOSED/fail-closed validation WON (it is the Floor-correct reading and supersedes the unratified RFC suggestion). Recorded so a future reader does not "fix" deposit back to open-string and reopen a fail-open hole.

### Deferred — live rung-ASSIGNMENT owed on bridge restore (671 tier)
- **kind:** Deferred · **verified_by:** V0_membership · **against_build:** 21.0.631 · **stakes:** medium · **probed:** false
- **area:** the live rung-assignment driver (probe membership → V0_membership; createNode + cook(force=True) + no errors → V1_cook; flipbook pixel sample / reproduced-then-resolved bug → V1_output) is bridge-gated. Behind `SYNAPSE_INTEGRATION`, honestly skipped this bridgeless run (the skipped test body raises — cannot masquerade as a pass). Owed on bridge restore (671 live/interactive tier).

---

## Session 2026-06-09 — CTO REMEDIATION HARNESS v1 · MILE 0 (re-ground) · HEAD 83f098b · TRACK H Leg 2

**Running build:** source confirmations @ HEAD `83f098b`; live tier = graphical 21.0.671 (PID 31428). **Bridge:** UNREACHABLE this session (see SubstrateAssumption below). **Operator gate:** HUMAN GATE 1 pending (Miles 1–3 not authorized). **Scope:** convert in-scope V0-leads C9/C10/C11 → V1/DeadEnd; capture live telemetry (0.2); HALT at capsule. Suite floor 3,377 (no code touched this mile).

### Confirmation — C9 (tops_cook_node error path NameError) V0-lead → V1
- **kind:** Confirmation · **verified_by:** V1 (source-confirmed, open-file @ 83f098b — not live-cook) · **against_build:** source @ 83f098b · **ts:** 2026-06-09
- **evidence:** `python/synapse/server/handlers_tops/cook.py` imports `time`, `typing`, `hou`, `..core.aliases`, `..core.determinism`, `..handler_helpers`, `._common` (lines 6-19) — **no `logging`, no `logger`**. The sole `logger` token in the whole module is the *use* at `cook.py:69` (`logger.error("PDG cook failed for %s: %s", node_path, e)`) inside the `node.cook()` failure branch. Resolution local→module→builtins finds nothing ⇒ `NameError` masks the structured error dict at :70-75. Deterministic source fact.
- **measured_delta:** promoted V0→V1. Live-cook reproduction (force `node.cook` to raise; assert NameError today / structured dict post-fix) **owed at Mile 2.4** as the regression pin. Suite unchanged (3,377; no code touched).

### Confirmation — C10 (freeze-safety chain dead on the v9 stack) V0-lead → V1
- **kind:** Confirmation · **verified_by:** V1 (source-confirmed, open-file @ 83f098b) · **against_build:** source @ 83f098b · **ts:** 2026-06-09
- **evidence:** `grep heartbeat python/synapse/panel/` (the LIVE v9 package the `.pypanel` loads) = **zero**. Only the LEGACY panel (`ui/panel.py`, `ui/tabs/connection.py`) calls `.heartbeat()`. `resilience.py:543-552` `Watchdog.start()` only sets `_running` and defers the monitor thread ("monitoring begins on first heartbeat()"); `heartbeat()` (`:577-586`) is the SOLE caller of `_ensure_started()` (`:564-575`) which launches the thread. No heartbeat source on the live stack ⇒ Watchdog never monitors ⇒ freeze-detection / backpressure / `_on_freeze` inert. Confirms review C10. **D3 (§6) is a real Mile-4 owner decision, not a phantom.**
- **measured_delta:** promoted V0→V1. No build this mile (decision-gated).

### Confirmation — C11 (render blocking IO on Houdini main thread) V0-lead → V1
- **kind:** Confirmation · **verified_by:** V1 (source-confirmed, code-read @ 83f098b — render NOT run, per 0.3) · **against_build:** source @ 83f098b · **ts:** 2026-06-09
- **evidence:** `handlers_render.py:342` `node.render(...)`, then inside the SAME `hou`-main-thread closure (`hou.text.expandString("$HFS")` at :363 proves it is the main-thread payload): the output-file poll `for _ in range(60): … time.sleep(0.25)` (:351-355, up to ~15 s) and `subprocess.run([iconvert,…], timeout=15)` (:369-373) both run before the closure returns ⇒ on the main thread. Read-only confirmation; no render issued.
- **measured_delta:** promoted V0→V1. Fix (split: `hou.*` on main, poll+iconvert on the WS handler thread) is **Mile 3.5**.

### DeadEnd — (carry-in, CTO review §4) worker MCP-first "undo/integrity off hot path"
- **kind:** DeadEnd · **verified_by:** V1 (refuted in review, re-affirmed) · **against_build:** source @ 83f098b · **ts:** 2026-06-09
- **claim_text:** "Worker dispatches MCP-first ⇒ undo/integrity + allowlist off the hot path." **Refuted:** the `/mcp` server runs in the SAME Houdini process (hwebserver), so undo-wrapping/IntegrityBlock are NOT bypassed. Carried in so it is never re-litigated.

### SubstrateAssumption — live WS transport UNREACHABLE for telemetry (0.2 result, negative)
- **kind:** SubstrateAssumption · **verified_by:** V1 (live probe, graphical 21.0.671 PID 31428) · **against_build:** 21.0.671 graphical (live) · **ts:** 2026-06-09
- **assumption:** "panel-reports-connected ⇒ MCP bridge reachable" — **holds = false** (re-reproduced; the known trap; corroborates review C22 and the 2026-06-07 self-healing-port session).
- **measured_delta:** 5 probe rounds, `ws://localhost:<p>/synapse`, no-auth localhost. **8765** (operator-stated): ConnectionRefused — nothing listening. **9999** (MCP `synapse_*` tools hardwired here; stale sidecar `~/.synapse/bridge.json` = `{port:9999, pid:55268, ts:2026-06-08}`): ConnectionRefused. **8912** (the ONLY Synapse listener = Houdini PID 31428's bound port per netstat): TCP connect succeeds but the **WebSocket handshake times out** at 12 s and 20 s × 4 attempts — main-thread-busy / unresponsive-upgrade signature. **0.2 telemetry: NOT CAPTURED.** Does not gate Mile 0 (C9/C10/C11 are source-confirmed, transport-independent). Owed when the 8912 handshake responds. **C6** stays V0 → "instrumented at Mile 3" (needs `dispatch_wait_ms` on a responsive live path — now also transport-blocked).
- **artifact_path:** (probe-only; no repo change)

---

## Session 2026-06-09 — CTO REMEDIATION HARNESS v1 · MILE 1 (memory-loss chain) · HEAD b5a4d4b

### Confirmation — invariant Q satisfied (quarantine-before-touch, Mile 1 gate)
- **kind:** Confirmation · **verified_by:** V1 (md5-identical copies on disk) · **against_build:** n/a (filesystem) · **ts:** 2026-06-09
- **change_applied:** before any Mile-1 code that can write the store, copied the memory artifacts to an outside-repo / outside-`$HOUDINI_TEMP` vault `C:\Users\User\synapse_quarantine_2026-06-09\`: `LIVE_untitled.hip_memory.jsonl` (977,253 B — md5-identical to the live store), `REPO_untitled.hip_memory.jsonl` (31,478 B sibling), `HOME_memory.jsonl` (0 B sibling) + `HOME_index.json`, and `encryption.key` (44 B). The live store had no sibling `index.json`.
- **measured_delta:** Q gate green — Mile 1 authorized to mutate the persistence path.

### Confirmation — C1 degraded-load guard (memory-loss chain, link 1/3)
- **kind:** Confirmation · **verified_by:** V1_cook (pure-Python repro: wrong-key load → degraded → save refused → ciphertext byte-identical) · **against_build:** stock-py 3.14 (memory layer is zero-`hou`) · **ts:** 2026-06-09
- **change_applied:** `memory/store.py` — `_load` counts encrypted lines (raw `MAGIC_PREFIX`) that fail decrypt/parse; `>0` ⇒ `self._degraded_load=True`, loud `logger.error`, `_quarantine_store()` (COPY aside, never move). `save()` raises at the TOP when `_degraded_load` (before any `open('w')`), so the truncating rewrite can never run on a wrong-key / missing-crypto load.
- **measured_delta:** `tests/test_store_degraded_load.py` (3): wrong-key→degraded+refuse+ciphertext-preserved+quarantine-copy; right-key→clean load+save; plaintext-garble→NOT degraded (C32's concern). Full suite **3380 passed / 68 skipped / 0 failed** (+3).
- **artifact_path:** `python/synapse/memory/store.py`, `tests/test_store_degraded_load.py`

### Confirmation — C2 atomic, backed-up save() (memory-loss chain, link 2/3)
- **kind:** Confirmation · **verified_by:** V1_cook (forced-crash repro: failed os.replace leaves prior file byte-intact) · **against_build:** stock-py 3.14 (zero-`hou`) · **ts:** 2026-06-09
- **change_applied:** `memory/store.py::save()` — the two truncating `open(...,'w')` writes replaced by `write_report(name, content, base_dir=storage_dir, backups=1)` (tmp + fsync + os.replace + one generational `.bak.1`). Lazy import keeps store.py's load order unchanged; `ledger.py` already proves the memory→`cognitive.tools.write_report` edge is cycle-free and zero-`hou`. The C1 degraded-guard stays the first statement (it precedes the atomic write).
- **measured_delta:** `tests/test_store_atomic_save.py` (2): monkeypatched `os.replace`→raise leaves `memory.jsonl` == prior bytes with no `.tmp` debris; a second save rotates `.bak.1` == the prior content. Full suite **3382 passed / 68 skipped / 0 failed** (+2). SubstrateAssumption "memory save is non-atomic / unbacked" false→true (link 2/3).
- **artifact_path:** `python/synapse/memory/store.py`, `tests/test_store_atomic_save.py`

### Confirmation — C3 key escrow + fingerprint guard (memory-loss chain, link 3/3)
- **kind:** Confirmation · **verified_by:** V1_cook (gen→.bak repro; changed-key-on-empty-store→degraded repro) · **against_build:** stock-py 3.14 (zero-`hou`) · **ts:** 2026-06-09
- **change_applied:** `core/crypto.py` — `_resolve_key()` auto-gen now writes `encryption.key.bak` + a loud one-time "BACK THIS UP" log (one lost 44-B file was total memory loss); new `key_fingerprint()` (sha256[:8], non-secret) + `CryptoEngine.fingerprint()`. `memory/store.py` — `save()` stamps a plaintext `key.fingerprint` sidecar; `_load` refuses (degraded) when the sidecar ≠ active key fp, catching the wrong/CHANGED-key case on an empty / all-plaintext store that C1's failed-decrypt counter misses (also blocks a mixed-key rewrite). Plaintext-on-purpose (readable when the key is wrong); torn sidecar → empty → no opinion (fail-safe).
- **measured_delta:** `tests/test_store_key_escrow.py` (3): generation writes a matching `.bak`; changed key on an EMPTY store → degraded + save refused; same key → clean. `test_crypto.py` (29) unaffected. Full suite **3385 passed / 68 skipped / 0 failed** (+3).
- **artifact_path:** `python/synapse/core/crypto.py`, `python/synapse/memory/store.py`, `tests/test_store_key_escrow.py`

### MILE 1 EXIT — memory-loss chain closed (C1+C2+C3)
- **kind:** Confirmation · **verified_by:** V1_cook (in-process second-session repro; live-Houdini-restart repro owed on bridge restore) · **against_build:** stock-py 3.14 · **ts:** 2026-06-09
- **measured_delta:** the original wipe path is dead: a wrong/changed-key load now (a) loads degraded, (b) **refuses save()** so nothing truncates the recoverable ciphertext, (c) quarantines a recovery copy, and even a clean save is now atomic (tmp+fsync+os.replace) with one `.bak` and an escrowed key. SubstrateAssumption flips, holds false→true: *"a bad load can wipe the store"*, *"memory save is non-atomic/unbacked"*, *"a single lost key file is unrecoverable-by-design"*. Residual owed: the LIVE second-fresh-session proof via a real Houdini restart (bridge-gated — see Mile 0 transport entry); the message-carries-command-id refinement (handler-layer, folds into C7).

---

## Session 2026-06-09 — CTO REMEDIATION HARNESS v1 · MILE 2 (mutation correctness + lifecycle honesty) · HEAD 19d65b3

### Confirmation — C4 zombie-mutation kill in run_on_main
- **kind:** Confirmation · **verified_by:** V1_cook (fake-hdefereval repro: timed-out payload never runs fn()) · **against_build:** stock-py 3.14 (server util, zero-`hou` via injected fake) · **ts:** 2026-06-09
- **change_applied:** `server/main_thread.py::run_on_main` — added a per-call `abandoned` flag under a `state_lock`. `_on_main` checks it (under the lock) before running `fn()`; the timeout path sets it (under the lock) before raising. A deferred payload that the main thread runs AFTER the caller timed out is now a no-op, so a timed-out mutating command can't apply late (and a retry can't double-apply). The check-vs-set is serialized; a payload already inside `fn()` at timeout is the accepted residual race.
- **measured_delta:** `tests/test_main_thread_zombie.py` (2): payload fired 0.4 s after a 0.1 s timeout → `fn()` never runs; a fast (non-timed-out) payload still runs and returns. `test_main_thread.py` (10) unaffected. Full suite **3387 passed / 68 skipped / 0 failed** (+2). SubstrateAssumption "a timed-out mutation still applies later" false→true.
- **artifact_path:** `python/synapse/server/main_thread.py`, `tests/test_main_thread_zombie.py`

### Confirmation — C5 cross-client mutation serialization
- **kind:** Confirmation · **verified_by:** V1_cook (3-thread repro: mutating serializes, read-only concurrent, main-thread skips) · **against_build:** stock-py 3.14 (fake-hou) · **ts:** 2026-06-09
- **change_applied:** `server/handlers.py` — one module-level `_MUTATION_LOCK` held around `invoke()` only for commands NOT in `_READ_ONLY_COMMANDS`, and only when the caller is NOT the main thread (`contextlib.nullcontext()` otherwise). Both WS transports funnel through `handle()`, so one lock covers both; the panel's main-thread dispatch skips it (already event-loop-serialized; locking there would deadlock against `run_on_main`). Deliberately a lock, NOT a queue — call-batching was refuted for latency (PR #28); this is sequence-coherence, not throughput.
- **measured_delta:** `tests/test_handler_mutation_lock.py` (3): two worker threads on a mutating cmd do not interleave (enter/exit/enter/exit); a main-thread mutating cmd proceeds while a worker holds the lock (no deadlock); two `search` (read-only) cmds run concurrently. Full suite **3390 passed / 68 skipped / 0 failed** (+3). SubstrateAssumption "two clients' mutation sequences can interleave on the shared scene" false→true (single-command atomicity already held; this adds sequence-level).
- **artifact_path:** `python/synapse/server/handlers.py`, `tests/test_handler_mutation_lock.py`

### Confirmation — C9 tops_cook_node error path no longer NameErrors
- **kind:** Confirmation · **verified_by:** V1_cook (forced cook-raise → structured error dict, not NameError) · **against_build:** stock-py 3.14 (fake-hou) · **ts:** 2026-06-09
- **change_applied:** `server/handlers_tops/cook.py` — `from ._common import logger` (the module referenced `logger` at the cook-failure branch :69 but never imported it, so any real PDG cook failure raised `NameError` and masked the real error). One-line fix; sibling modules already use `_common.logger`.
- **measured_delta:** `tests/test_tops_cook_error_path.py` (2): module defines a `logging.Logger`; a raising `node.cook` now returns `{status:error, error:'cook boom', work_items:2}`. **CRUCIBLE catch (fixed forward):** the behavioral test passed alone but failed in the full suite (`'cooked' != 'error'`) — a prior test had left a global `hou` bound to cook that `monkeypatch.setattr(cook, 'hou', …)` on the imported reference didn't reach. Fixed by patching the handler's actual execution namespace via `_handle_tops_cook_node.__globals__` (identity-proof) — no test weakened. Full suite **3392 passed / 68 skipped / 0 failed** (+2).
- **artifact_path:** `python/synapse/server/handlers_tops/cook.py`, `tests/test_tops_cook_error_path.py`

### Confirmation — C8 honest Stop (lifecycle honesty) — MILE 2 EXIT
- **kind:** Confirmation · **verified_by:** V1_cook (hython 671 + PySide6 offscreen: 3/3; stock suite: 3/3) · **against_build:** 21.0.671 (hython Qt tier) · **ts:** 2026-06-09
- **change_applied:** `panel/synapse_panel.py` — `_on_stop` no longer flips the rail to idle while Houdini keeps cooking: it aborts the worker (cooperative), disables the Stop button (press registered), and shows `Stopping — waiting on <tool>…` via `_set_header`; busy-state now resets ONLY when the worker actually finishes (`stream_done`/`stream_error` → `_on_done`/`_on_error`, which already call `_set_busy(False)`). `_on_tool_status` tracks the in-flight tool name (`_last_tool`, reset per send) so the message is specific. No new Qt surface (reuses `_set_header`/`setEnabled` — dir-gate trivially satisfied, verified by the hython run itself).
- **measured_delta:** `tests/test_panel_stop_honest.py` (3): Stop aborts + holds busy + says "Stopping" with the tool name; generic when no tool known; `_last_tool` tracks running-phase only. Verified under hython 21.0.671/PySide6 offscreen AND stock py3.14 (PySide6 importable there too → pins run in CI). Full stock suite **3395 passed / 68 skipped / 0 failed** (+3). SubstrateAssumption "Stop terminates work" → honest: Stop now *says* it is waiting; true in-flight CANCEL (tops_cancel_cook / render cancel off the UI thread) is **deferred to the bridge-live pass** — needs a reachable transport.
- **artifact_path:** `python/synapse/panel/synapse_panel.py`, `tests/test_panel_stop_honest.py`

---

## Session 2026-06-09 — CTO REMEDIATION HARNESS v1 · MILE 3 (latency search + timeout discipline) · HEAD 4d4d9cc

### Confirmation — C6 (3.1) dispatch_wait_ms instrumentation LANDED; measurement transport-blocked (invariant M honored)
- **kind:** Confirmation · **verified_by:** V1_cook (fake-hdefereval: injected 200 ms wake → recorded in the right bucket; abandoned payloads still sample; Prometheus emission pinned) · **against_build:** stock-py 3.14 · **ts:** 2026-06-09
- **change_applied:** `server/main_thread.py` — `t_enqueue` stamped before `executeDeferred`, `_record_dispatch_wait((t_start−t_enqueue)·1000)` first thing in `_on_main` (every wake samples, including abandoned C4 payloads — queue-sit time is the datum); module-level histogram (buckets 1…4000 ms straddling the 2000 ms T1 suspect) + `dispatch_wait_stats()`/`reset_dispatch_wait_stats()`. `server/metrics.py` — `synapse_dispatch_wait_ms` histogram block (bucket/sum/count/max; silent at count==0). `handlers.py::_handle_get_metrics` passes it, so the live `get_metrics` surface now separates wake latency from handler work.
- **measured_delta:** `tests/test_dispatch_wait_metric.py` (3). Full suite **3398 passed / 68 skipped / 0 failed** (+3). **Adjudication (3.2/3.3) NOT run:** T1/T2/T3 need ≥30 mutating calls on a LIVE graphical session, and the transport is down this run (Mile 0 entry: 8912 handshake dead) — headless hython has no Qt event loop, so its wake numbers cannot stand in for T1. Per invariant M the wake fix (`postEvent`) is NOT written. **Owed on bridge restore:** run the live measurement, adjudicate against the §1 signatures, then (T1 only) dir()-verify the wake surface in-process and apply+re-measure with second-session reproduction.
- **artifact_path:** `python/synapse/server/main_thread.py`, `python/synapse/server/metrics.py`, `python/synapse/server/handlers.py`, `tests/test_dispatch_wait_metric.py`

### Confirmation — C7 (3.4) per-tool timeout discipline + double-dispatch kill
- **kind:** Confirmation · **verified_by:** V1_cook (socket.timeout repro → raises do-not-retry; refused → None fallback preserved; budgets resolve per tool) · **against_build:** stock-py 3.14 · **ts:** 2026-06-09
- **change_applied:** new `core/timeouts.py` — THE canonical per-command budget table (moved verbatim from mcp_server.py) + `timeout_for()` (exact → alias → prefix-stripped, so MCP tool names like `houdini_render`/`synapse_render_sequence` resolve). `mcp_server.py` imports the shared table (placed AFTER its sys.path insert; the table's only earlier use resolves at call time). Panel: `_MCPLocalClient._post` takes a per-call timeout; `call_tool` budgets `timeout_for(tool)+5s` (was a fixed 35 s against 120–600 s tools); **`try_mcp_tool_call` now RAISES on socket timeout** ("may STILL be running inside Houdini — do not retry") instead of returning None — the worker's existing `except RuntimeError` branch turns that into an `is_error` tool_result, so the Qt-path **re-dispatch of a possibly-executing mutation is dead**; connection-refused still returns None (the legitimate fallback). `claude_worker._wait_budget(tool)` raises the Qt-wait floor per tool; its timeout message now says still-running/do-not-retry.
- **measured_delta:** `tests/test_timeouts_c7.py` (9; with a setdefault PySide6 import-stub so the panel-module tests are order-independent — the documented suite-vs-isolation flake genus). **Pin relocations (equal strength, not weakened):** `test_pipeline_efficiency::test_batch_in_slow_commands` and `test_v5_features::test_slow_command_timeout` moved their value pins to `core/timeouts.py` AND now pin that mcp_server imports the shared table (the second was caught by the C7 full-suite gate — exactly the conformance harness working). Suite gate shared with C11 (disjoint files): **3406 expected** — see C11 entry for the combined number.
- **artifact_path:** `python/synapse/core/timeouts.py`, `mcp_server.py`, `python/synapse/panel/tool_executor.py`, `python/synapse/panel/claude_worker.py`, `tests/test_timeouts_c7.py`, `tests/test_pipeline_efficiency.py`, `tests/test_v5_features.py`

### Confirmation — C11 (3.5) render blocking IO off the main thread
- **kind:** Confirmation · **verified_by:** V1_cook (instrumented fake-hdefereval: zero time.sleep inside any main-thread closure on a full _handle_render pass; 59 existing render tests green) · **against_build:** stock-py 3.14 (fake-hou; LIVE graphical re-verify owed on bridge restore) · **ts:** 2026-06-09
- **change_applied:** `server/handlers_render.py::_handle_render` — `_render_on_main` now ends right after `node.render()` (+ `$HFS` resolve, the one hou call the iconvert leg needs). The up-to-15 s output poll (`time.sleep` loop) and the `iconvert` subprocess moved to the WS handler thread (pure file IO, zero hou). The flipbook fallback (all hou.*) became a SECOND, conditional main-thread hop entered only when the off-main poll found nothing — the common success path never re-blocks the main thread. Logic/messages preserved verbatim otherwise (incl. the pre-existing flipbook fb_pattern quirk — not touched, surgical).
- **measured_delta:** `tests/test_render_offmain_c11.py` (1, the freeze-guard pin: sleeps-on-main == 0). Combined C7+C11 full-suite gate (disjoint file sets, one run): see number below. Residual: safe_render's auto-background interplay (review C16/C24 family) untouched — out of this run's scope.
- **artifact_path:** `python/synapse/server/handlers_render.py`, `tests/test_render_offmain_c11.py`

---

## Session 2026-06-09 — CTO REMEDIATION HARNESS v1 · MILE 4 (decision gates) + RUN CLOSE

### Decision-Surface — D3 (EmergencyProtocol / freeze chain) and D4 (SEC-1 timing) — AWAITING OPERATOR
- **kind:** Deferred · **verified_by:** V1 (Mile 0 source confirmations) · **against_build:** source @ 786215f · **ts:** 2026-06-09 · **probed:** true (C10 V1) · **stakes:** high (documented-but-unreachable safety class)
- **D3 (blocks any C10 build):** the freeze chain is dead end-to-end on the live stack (C10 V1: zero `heartbeat()` callers in v9 `panel/`; `Watchdog.start()` defers monitoring to first heartbeat; `_on_freeze` logs only; `trigger_emergency_halt` defined once, called by tests only). Options: **(a)** wire a 1 s QTimer heartbeat in the v9 panel (re-arms Watchdog + backpressure exactly as the legacy panel did) + make `_on_freeze` act after a sustained freeze (≥30 s → `circuit_breaker.force_open()`, and `EmergencyProtocol.trigger_emergency_halt` when a bridge is active); **(b)** banner CLAUDE.md §1.8 / Safety Rule 11 not-live — the same honesty treatment D2 gave the bridge. The harness refuses the rot-default. NO build until the call.
- **D4 (blocks nothing in this run):** SEC-1 (hwebserver has zero `check_permission`; an authenticated VIEWER can call `execute_python`). Documented single-user-localhost posture stands; closing is MANDATORY before any studio-lan/vpn/multi-client mode. Re-surfaces at any deploy-mode change.

### Confirmation — D3 EXECUTED (operator call: WIRE) — the freeze chain ACTS, topology-true
- **kind:** Confirmation · **verified_by:** V1_cook (real Watchdog tiny-threshold repro: sustained freeze → force_open + REAL EmergencyProtocol halt via fake active bridge → ALL_OPERATIONS_HALTED; recovery cancels + resets; no-server/no-bridge acts partially, never crashes) · **against_build:** stock-py 3.14 + hython 21.0.671 (panel leg) · **ts:** 2026-06-09
- **the topology truth that changed the design:** wiring the panel to `server.heartbeat()` literally (the ratified sketch) would have armed NOTHING — the live transport is hwebserver (no resilience layer) and the fallback `SynapseServer` is constructed `enable_resilience=False` (`start_hwebserver.py:69`), so no Watchdog instance exists anywhere on the live stack. That literal wiring = activation theater (the named anti-pattern). The chain therefore moved to a transport-independent home.
- **change_applied:** new `server/freeze_chain.py` — ONE process-wide Watchdog + the acting escalation policy: panel beat → detection at >5 s (warn + arm a cancellable timer) → still frozen at 30 s (`ESCALATION_S`, the ratified number) → `force_open()` the live SynapseServer breaker IF one runs (logged honestly when none does) + `EmergencyProtocol.trigger_emergency_halt(bridge, reason)` via an ALREADY-ACTIVE bridge only (attribute peeks on the hwebserver/module + live-server handlers — escalation never constructs a bridge); recovery cancels the timer + resets the breaker. `websocket.py` — module-level live-server registry (`start()` registers, `stop()` deregisters own-instance-guarded, `get_live_server()`), closing the recoverability gap `start_hwebserver.py:31-34` hard-ref-works-around. `panel/synapse_panel.py` — 1 s `_freeze_timer` QTimer → `_beat_freeze_chain()` (best-effort import; the panel main-thread beat IS the liveness signal). `websocket.py`'s internal watchdog/_on_freeze left untouched (surgical) — superseded as the live authority by the chain; it still works for anyone calling `server.heartbeat()`.
- **measured_delta:** `tests/test_freeze_chain.py` (6) + `tests/test_panel_freeze_beat.py` (3, hython-671-verified with real Qt alongside the C8 pins). The 6-pin set exercises the REAL `EmergencyProtocol.trigger_emergency_halt` (fake bridge `session_report`), not a mock of it. One CRUCIBLE catch fixed-forward in the TEST (stopping beats after recovery is a legitimate second freeze — the chain was right, the test now keeps beating). Suite: see run-close (gate shared A+B, disjoint files). Residual honest gaps, Ledger-recorded: hwebserver transport still has no breaker to open (ARC-2 / C24 territory, out of scope); live-fire of the full chain on a real frozen graphical session owed on bridge restore.
- **artifact_path:** `python/synapse/server/freeze_chain.py`, `python/synapse/server/websocket.py`, `python/synapse/panel/synapse_panel.py`, `tests/test_freeze_chain.py`, `tests/test_panel_freeze_beat.py`

### RUN CLOSE — C-item scoreboard + suite floor + owed residuals
- **kind:** Confirmation · **verified_by:** V1_cook (per-item entries above) · **against_build:** stock-py 3.14 / hython 671 (C8) · **ts:** 2026-06-09
- **measured_delta:** **9 of 9 in-scope C-items landed** (C1 b5a4d4b→0b66aa1, C2 85eecea, C3 19d65b3, C4 9f90a1c, C5 66973fa, C9 ae07ec8, C8 4d4d9cc, C6-instrument 66ecbd1, C7+C11 786215f). Suite floor **3,377 → 3,406** (+29 pins, 0 failures at every HEAD, no test weakened; 2 pins relocated at equal strength). Quarantine vault intact at `C:\Users\User\synapse_quarantine_2026-06-09\`.
- **OWED on bridge restore (671 live tier):** (1) C6 measurement — ≥30 mutating calls → adjudicate T1/T2/T3 → wake fix only if T1, second-session repro (invariant M held: no wake fix written); (2) Mile-1 live second-fresh-session wrong-key proof via real Houdini restart; (3) C8 in-flight cancel dispatch (tops_cancel_cook off the UI thread); (4) the Mile-0 transport finding itself (8912 WS handshake dead; MCP tools hardwired 9999 + stale sidecar — fixed-by-restart per 3fcdb54, re-verify). **Outside this harness's scope (still V0-leads):** C16, C24, C25 and the other spend-limit-cut review verdicts; C12–C35 P2/P3 backlog.
- **artifact_path:** (this Ledger; per-item entries above)
