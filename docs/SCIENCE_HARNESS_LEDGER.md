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
