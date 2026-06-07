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
