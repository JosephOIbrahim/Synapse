# SPRINT2_EXECUTE.md — Claude Code Agent Team Execution Plan (v4.7)

**Scope:** Wire the Inspector subsystem into the live SYNAPSE codebase.
**Method:** MOE agent team via Claude Code with `--dangerously-skip-permissions`.
**Constitution:** Agent Commandments (embedded in §1).
**Build:** v4.7 production-hardened. See `CHANGELOG_4.6_to_4.7.md`.

---

## §1. Agent Constitution

These rules are non-negotiable. Every agent role reads this section first.
Violation of any commandment is grounds for immediate halt and escalation.

### Commandment 1: SCOUT BEFORE YOU ACT
- **Targeted discovery.** Search for relevant files/context first.
- **Convention matching.** Read 2-3 existing examples before creating.
- **Scope mapping.** Identify what you CANNOT touch before what you can.

### Commandment 2: VERIFY AFTER EVERY MUTATION
- **Immediate verification.** Run tests after every file create/modify.
- **Regression is sacred.** Existing 890 tests are invariants.
- **Net-positive test count.** You leave more tests than you found.

### Commandment 3: BOUNDED FAILURE → ESCALATE
- **3 retries max.** After 3 attempts, reclassify from task to blocker.
- **Escalation, not surrender.** Surface what you tried and what failed.
- **No silent degradation.** Never weaken a test to make it pass.

### Commandment 4: COMPLETE OUTPUT OR EXPLICIT BLOCKER
- **No stubs, no TODOs.** Write the whole thing.
- **No truncation.** No `// ... existing code ...` corruption.
- **Blocker protocol.** Say exactly what's missing if you can't complete.

### Commandment 5: ROLE ISOLATION
- **Authority boundaries are explicit.** No freelancing.
- **Implementing agents don't "improve" the design.** Flag disagreements as notes.
- **Competence ≠ authority.** You CAN doesn't mean you SHOULD.

### Commandment 6: EXPLICIT HANDOFFS
- **Handoff artifact.** Specific named output, not ambient context.
- **Interface precision.** Types, signatures, state transitions.
- **State checkpoints.** Commit between every phase.

### Commandment 7: ADVERSARIAL VERIFICATION
- **Separate builder from breaker.** Different agents.
- **Edge cases are mandatory.** Not bonus.
- **Fix forward, not down.** Fix the code, not the test.

### Commandment 8: HUMAN GATES AT IRREVERSIBLE TRANSITIONS
- **Gate after design, before implementation.**
- **Surface what was decided, tradeoffs, and cost of proceeding.**
- **Minimal gates.** Every gate is a momentum break.

---

## §2. The "Do Not Touch" List

These components are load-bearing and verified. Modifying any of them
requires explicit architect approval before proceeding.

| Component | Location | Why frozen |
|---|---|---|
| 890 existing tests | `tests/` | Regression invariant |
| 43 MCP tools | `mcp_server.py` + handlers | External consumer contract |
| WebSocket transport | `python/synapse/server/websocket.py` | Verified H21.0.631 |
| Wire protocol v4.0.0 | `python/synapse/core/protocol.py` | Breaking = breaking contract |
| RELAY-SOLARIS tools | `python/synapse/` | 86 mock + 7 live smoke passing |
| FORGE pipeline | `python/synapse/` | Merged, operational |
| Agent executor | `python/synapse/agent/` | prepare/propose/execute/learn |
| Gate system | `python/synapse/core/gates.py` | INFORM/REVIEW/APPROVE/CRITICAL |
| Audit chain | `python/synapse/core/audit.py` | Hash-chain integrity |
| Determinism primitives | `python/synapse/core/determinism.py` | He2025 alignment |

---

## §3. MOE Agent Roles

Claude Code cannot spawn nested processes. The executing agent adopts
each role sequentially within the same session. Git-commit between role
transitions.

### AGENT-RES (Research)
**Scope:** Read-only reconnaissance.
**Authority:** Read any file. No create/modify/delete.
**Deliverable:** Integration Map (§4.1).

### AGENT-ENG (Engineering)
**Scope:** Implementation of new files. Wiring of imports.
**Authority:**
  - May create new files in `python/synapse/inspector/` and `tests/`
  - May modify `mcp_server.py` ONLY to add the new tool registration
  - May modify `python/synapse/__init__.py` ONLY to add inspector exports
  - May modify `pyproject.toml` ONLY per the `pyproject_patch.toml` snippet
  - May NOT modify any file in the §2 frozen list
**Deliverable:** Wired, importable, runnable code (§4.2).

### AGENT-SUP (Supervision / Verification)
**Scope:** Run tests. Verify regression. Audit code quality.
**Authority:** Run pytest. Read any file. No source modification.
If tests fail, produces Bug Report — does NOT fix. Fix goes back to AGENT-ENG.
**Deliverable:** Test Report (§4.3).

### AGENT-PRO (Production / Ship)
**Scope:** Git commit. Final validation. Handoff capsule.
**Authority:** `git add`, `git commit`. Documentation. No source modification.
**Deliverable:** Commit hash + Sprint 2 Week 1 capsule (§4.4).

---

## §4. Execution Phases

### §4.1 Phase 1: AGENT-RES — Reconnaissance

**Objective:** Map the existing codebase to determine exact integration points.

**Steps:**

1. Read `mcp_server.py` — identify how existing tools are registered.
   Find the decorator pattern (likely `@mcp.tool()` via FastMCP).
   Note import style.

2. Read `python/synapse/__init__.py` — identify public API export pattern.

3. Read `python/synapse/server/websocket.py` — identify the execute_python
   transport. Note:
   - Function signature (does it accept `timeout` kwarg?)
   - How it accepts code, returns stdout
   - Method on a client class or standalone function?
   - Module path for import

4. Read `tests/test_core.py` (or similar) — identify test conventions:
   - Import patterns
   - Fixture usage
   - Assert style

5. Check `pyproject.toml` — note existing pytest config, markers list,
   dependencies (is pydantic already present?).

6. Read `.claude/` contents if present — any existing agent directives.

**Deliverable: Integration Map**

```
TRANSPORT_MODULE_PATH: <e.g. synapse.server.websocket>
TRANSPORT_FUNCTION: <e.g. execute_python OR SynapseClient.send_command>
TRANSPORT_SIGNATURE: <exact signature>
TRANSPORT_ACCEPTS_TIMEOUT: <yes|no>
MCP_REGISTRATION_DECORATOR: <e.g. @mcp.tool()>
MCP_SERVER_INSTANCE: <e.g. the `mcp` variable in mcp_server.py>
PUBLIC_API_EXPORT_STYLE: <how existing modules export>
PYDANTIC_ALREADY_PRESENT: <yes|no>
EXISTING_PYTEST_MARKERS: <list>
```

**GATE:** Architect reviews Integration Map before Phase 2.
If transport signature differs from assumptions in `tool_inspect_stage.py`,
Phase 2 adapts before proceeding.

### §4.2 Phase 2: AGENT-ENG — Implementation

**Objective:** Wire the Inspector files into the live codebase.

**Input files to place** (from the v4.7 file set):

```
python/synapse/inspector/__init__.py
python/synapse/inspector/exceptions.py
python/synapse/inspector/models.py
python/synapse/inspector/transport.py
python/synapse/inspector/tool_inspect_stage.py
tests/conftest.py
tests/fixtures/inspector_week1_flat.golden.json
tests/test_inspect_mock.py
tests/test_inspect_live.py
docs/verification_ledger.md
```

**Steps:**

1. Copy the 10 files into their target locations.

2. **Check for conftest.py collision.** If `tests/conftest.py` already
   exists, MERGE — do not overwrite. Add the Inspector fixtures to the
   existing file. Preserve all existing fixtures.

3. **Apply `pyproject.toml` patch** per `pyproject_patch.toml`:
   - Add `live` marker to `[tool.pytest.ini_options].markers`
   - Add `pydantic>=2.0` to dependencies (if not already present)
   - Add mypy strict override for `synapse.inspector.*`

4. **Wire the default transport.** In
   `python/synapse/inspector/tool_inspect_stage.py`, the module currently
   requires explicit `execute_python_fn` or `configure_transport()` call.

   Option A (recommended): do nothing. Document that consumers must call
   `configure_transport()` at startup. This is the clean approach.

   Option B: auto-configure at import time by importing the SYNAPSE
   transport function and calling `configure_transport()`. Creates an
   import-time side effect. Only do this if existing SYNAPSE tools follow
   this pattern.

   Prefer A unless AGENT-RES found evidence for B.

5. **Update `python/synapse/__init__.py`** — add Inspector exports
   following the discovered existing pattern. Typically one line:

   ```python
   from synapse.inspector import synapse_inspect_stage, StageAST
   ```

6. **Register MCP tool in `mcp_server.py`** — following the pattern
   discovered in Phase 1. Tool name: `synapse_inspect_stage`. Description:
   "Extracts the AST of the Houdini Solaris /stage context. Returns USD
   prim paths, topology, error states, and flags for every node. Enables
   scene-aware responses across sessions."

   The tool wrapper must:
   - Call `configure_transport()` if not already configured
   - Call `synapse_inspect_stage()`
   - Serialize the returned StageAST via `.to_json()` (deterministic)
   - Return the JSON string to the MCP protocol layer
   - Wrap in try/except to convert Inspector exceptions to JSON-safe errors

7. **VERIFY IMMEDIATELY** (Commandment 2):
   ```
   python -m pytest tests/test_inspect_mock.py -v
   ```
   All 85 mock tests must pass before proceeding.

8. **REGRESSION CHECK** (Commandment 2):
   ```
   python -m pytest tests/ -v --timeout=120 -m "not live"
   ```
   All 890 existing tests + 85 new mock tests must pass. Total ≥975.

9. **TYPE CHECK** (if existing codebase uses mypy):
   ```
   python -m mypy python/synapse/inspector/ --config-file pyproject.toml
   ```
   Zero errors on the Inspector module.

**Deliverable:** All files wired. Mock tests pass. No regressions.

### §4.3 Phase 3: AGENT-SUP — Verification

**Objective:** Adversarial validation of Phase 2 output.

**Steps:**

1. Run full test suite:
   ```
   python -m pytest tests/ -v --timeout=120 -m "not live"
   ```

2. Verify net-positive test count:
   - Before: 890 tests
   - After: ≥975 tests (890 + 85 new mock tests)
   - If count is not ≥975, FAIL.

3. Verify no frozen files were modified (only these should be diff'd):
   ```
   git diff --name-only
   ```

   Expected additions (10 files):
   - `python/synapse/inspector/__init__.py`
   - `python/synapse/inspector/exceptions.py`
   - `python/synapse/inspector/models.py`
   - `python/synapse/inspector/transport.py`
   - `python/synapse/inspector/tool_inspect_stage.py`
   - `tests/conftest.py` (new OR merged)
   - `tests/fixtures/inspector_week1_flat.golden.json`
   - `tests/test_inspect_mock.py`
   - `tests/test_inspect_live.py`
   - `docs/verification_ledger.md`

   Expected modifications (3 files, minimal additions only):
   - `python/synapse/__init__.py` (added exports)
   - `mcp_server.py` (added tool registration)
   - `pyproject.toml` (marker + dependency + mypy override)

   Any other file in the diff = FAIL. Escalate.

4. Type check:
   ```
   python -m mypy python/synapse/inspector/ --config-file pyproject.toml
   ```

5. Import verification:
   ```
   python -c "from synapse.inspector import (
       ASTNode, StageAST, synapse_inspect_stage,
       configure_transport, SCHEMA_VERSION,
       InspectorError, StageNotFoundError,
   ); print('Import OK')"
   ```

6. Marker registration verification:
   ```
   python -m pytest --markers | grep -i live
   ```
   Should show the `live` marker registered.

7. Live test collection (should all skip cleanly, not fail):
   ```
   python -m pytest tests/test_inspect_live.py --collect-only
   ```

**Deliverable: Test Report**

```
TOTAL_TESTS: <number, must be ≥975>
NEW_TESTS: <number, must be ≥85>
REGRESSIONS: <0 or list>
MYPY_ERRORS: <0 or list>
IMPORT_CHECK: <OK or FAIL>
MARKER_REGISTERED: <yes or no>
LIVE_TESTS_COLLECT: <N collected, N skipped — no errors>
FROZEN_FILES_TOUCHED: <none or list>
VERDICT: PASS / FAIL
```

If FAIL → back to AGENT-ENG with specific bug report. Max 3 cycles (Commandment 3).

### §4.4 Phase 4: AGENT-PRO — Ship

**Objective:** Commit, document, produce handoff capsule.

**Steps:**

1. Stage changes:
   ```
   git add python/synapse/inspector/ tests/ docs/verification_ledger.md
   git add python/synapse/__init__.py mcp_server.py pyproject.toml
   ```

2. Commit:
   ```
   git commit -m "feat(inspector): Sprint 2 Week 1 — synapse_inspect_stage v1.0.0

   Production-hardened Inspector subsystem for Solaris scene-memory.

   New module: python/synapse/inspector/
   - Flat /stage AST extraction via WebSocket
   - lastModifiedPrims() for usd_prim_paths (verified H21.0.631)
   - Base64 transport wrapper bypasses multi-line parser constraint
   - Typed exception hierarchy (InspectorError + 8 subclasses)
   - Thread-safe transport registration
   - Input sanitization blocks path-injection attempts
   - Schema versioning (SCHEMA_VERSION=1.0.0) prevents silent drift
   - Per-node graceful degradation — one bad node doesn't abort AST
   - Deterministic output (sorted keys, sorted node order)
   - StageAST container with 15+ query helpers

   New MCP tool: synapse_inspect_stage (tool #44)

   Tests: 85 mock tests (100% passing), live smoke test scaffold
   with env-var-configurable transport + proper marker isolation.

   Sprint 1 gate: 7 GREEN, 1 RED-mitigated (hdefereval headless)
   Sprint 2a: lastModifiedPrims() discovery, fixture generation
   Target: H21.0.631 | Daily driver: 21.0.631"
   ```

3. Generate capsule:
   ```
   +== PROJECT CAPSULE: SYNAPSE 2.0 ===================+
   | WHERE WE ARE:        Sprint 2 Week 1 SHIPPED       |
   | MILE MARKER:         5 of ~10                      |
   | WHAT I WAS THINKING: Inspector flat AST complete    |
   |                      with production hardening      |
   | NEXT ACTION:         Sprint 2 Week 2 — subnet      |
   |                      recursion into sopcreate,      |
   |                      materiallibrary (locked HDAs)  |
   | BLOCKERS:            Live transport wiring for     |
   |                      test_inspect_live.py          |
   | ENERGY REQUIRED:     Implementation (activation 3)  |
   | IDEAS PARKED:        inputPrims(idx) enrichment,    |
   |                      FORGE ↔ Inspector integration, |
   |                      schema evolution migration     |
   +====================================================+
   ```

**Deliverable:** Commit hash + capsule.

---

## §5. File Manifest (v4.7)

| Source | Target | Action |
|---|---|---|
| `python/synapse/inspector/__init__.py` | same | CREATE |
| `python/synapse/inspector/exceptions.py` | same | CREATE |
| `python/synapse/inspector/models.py` | same | CREATE |
| `python/synapse/inspector/transport.py` | same | CREATE |
| `python/synapse/inspector/tool_inspect_stage.py` | same | CREATE |
| `tests/conftest.py` | same | CREATE or MERGE |
| `tests/fixtures/inspector_week1_flat.golden.json` | same | CREATE |
| `tests/test_inspect_mock.py` | same | CREATE |
| `tests/test_inspect_live.py` | same | CREATE |
| `docs/verification_ledger.md` | same | CREATE |
| `pyproject_patch.toml` | merge into `pyproject.toml` | PATCH |
| — | `python/synapse/__init__.py` | MODIFY (exports) |
| — | `mcp_server.py` | MODIFY (tool registration) |

**Fixture HIP file (already on disk):**
`C:\Users\User\SYNAPSE\tests\fixtures\inspector_week1_flat.hip`

---

## §6. Success Criteria

Sprint 2 Week 1 is SHIPPED when:

1. All 890 existing tests pass (zero regressions)
2. 85 new mock tests pass
3. `synapse_inspect_stage` is registered as MCP tool #44
4. `from synapse.inspector import ASTNode, synapse_inspect_stage, StageAST, configure_transport` works
5. mypy clean on `python/synapse/inspector/`
6. `live` marker registered and recognized
7. Verification ledger committed to repo
8. Git commit with descriptive message on `master`

Sprint 2 Week 1 is NOT shipped until:
- Live smoke tests pass against running Houdini (requires manual transport
  wiring + Houdini session). This is a known gap; mock tests validate
  schema, parsing, error handling, and query helpers.

---

## §7. Failure Modes

| Failure | Response |
|---|---|
| Import path mismatch | AGENT-RES missed a convention. Re-scout. |
| Existing test breaks | AGENT-ENG introduced a side effect. Revert. |
| Mock test fails | Code bug. Fix in AGENT-ENG. Do NOT weaken test. |
| mypy errors on inspector | Fix types. Do not add `# type: ignore`. |
| Transport signature differs | Adapt `tool_inspect_stage.py`. Do not modify transport. |
| MCP registration differs | Adapt registration. Do not modify `mcp_server.py` structure. |
| Pydantic version conflict | Surface to architect. Do not pin older version. |
| 3 failed attempts on same issue | STOP. Surface blocker. |

---

## §8. Post-Sprint 2 Week 1 Horizon

**Week 2:** Recursive subnet descent into `sopcreate`, `materiallibrary`,
`copnet`. These are locked HDAs — `allowEditingOfContents()` required.
`key_parms` field populated. Schema version may bump to 1.1.0 if
extraction script changes.

**Sprint 3:** USD provenance layer. `synapse:*` attributes stamped by
every RELAY-SOLARIS tool. `provenance` field on ASTNode populated.
Patent review gate.

**Sprint 4:** Session-start handshake. Inspector auto-runs on connect.
Provenance digest as first-turn context. Ship validation: Joe opens
scene, walks away, returns days later, Claude knows what's there.

---

*End of execution plan.*
