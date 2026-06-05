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
