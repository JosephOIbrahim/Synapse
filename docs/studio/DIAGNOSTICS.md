# SYNAPSE Diagnostics — Logs, Telemetry, Doctor

> M3-C (studio-operable hardening, 2026-06-11). Where the evidence is after
> a crash, what the telemetry artifacts mean, and how to health-check a seat.

## 1. Log file

The in-Houdini SYNAPSE process writes a rotating file log:

| Property | Value |
|----------|-------|
| Path | `~/.synapse/logs/synapse.log` |
| Rotation | 5 MB × 3 backups (`synapse.log.1` … `.3`, worst case ~20 MB) |
| Level | INFO |
| Coverage | every `synapse.*` logger inside the Houdini process (handler attached to the `synapse` logger only — Houdini/vendor noise is never captured) |
| Relocate | `SYNAPSE_LOG_DIR` |
| Disable | `SYNAPSE_FILE_LOG=0` |

It is attached idempotently from three bootstrap sites — the hwebserver
adapter's `start_hwebserver()`, `start_hwebserver.main()` (covers the
websocket-fallback branch), and the panel's freeze-heartbeat init (the panel
is the freeze chain's beat source, so it produces a durable trail even when
no server was started).

**Two processes, two trails — deliberately.** The external stdio
`mcp_server.py` process keeps logging to its own stderr (Claude Desktop
captures it). Pointing a second process's `RotatingFileHandler` at the same
file is unsafe on Windows: the rotation rename fails on open handles. The
file above covers the Houdini process; the MCP client captures the stdio
process.

Before M3-C there was **no** FileHandler anywhere: WARNING+ fell to
`logging.lastResort` (the unsaved Houdini console) and INFO and below —
including the freeze chain's recovery breadcrumbs — were dropped outright.

## 2. Telemetry artifacts

Written to the same directory (`SYNAPSE_LOG_DIR`, default `~/.synapse/logs`):

| Artifact | When | Semantics |
|----------|------|-----------|
| `telemetry.json` | periodic, default every 60 s (`SYNAPSE_TELEMETRY_FLUSH_S`; `<=0` disables) | atomic overwrite (tmp + `os.replace`) — always the latest snapshot |
| `freeze_dump_<UTC>.json` | written by `FreezeChain._escalate` at the 30 s sustained-freeze deadline, before the breaker/halt actions | new file per event, newest 5 kept — bounded evidence the periodic flush can never overwrite |

Snapshot sections (truth contract: each section is real data or an explicit
`*_absent` marker — never fabricated):

| Section | Meaning |
|---------|---------|
| `dispatch_waits` | the C6 enqueue→start histogram from `server/main_thread.py` — how long deferred payloads sat in Houdini's event queue |
| `tool_durations` | per-tool handler duration histogram from the live `SynapseHandler` (`tool_durations_absent` when no handler is live) |
| `freeze` | freeze-chain Watchdog stats (absent until the first panel beat constructs the chain) |
| `live_metrics_latest` | **null on the live hwebserver transport** — the metrics aggregator is only constructed by the websocket fallback server. Known limitation, reported honestly, not fabricated. |

## 3. synapse_doctor (the install/ops doctor)

> Distinct from the panel **Scene Doctor** (`panel/scene_doctor.py`), which
> diagnoses scene content. `synapse_doctor` diagnoses the **seat**: install,
> logs, keys, endpoint.

Run via the MCP tool `synapse_doctor` or the live `doctor` command. Core
logic lives in `python/synapse/server/doctor.py` (`run_doctor`).

**Truth contract: the doctor reports only checks it actually ran; "skipped"
is not "ok".** Every check is `ok` / `fail` / `skipped`, and `skipped`
always carries the reason.

| Check | ok | fail | skipped |
|-------|----|------|---------|
| `version` | synapse + protocol versions read; install stamp (`~/.synapse/install_stamp.json`, M3-A) matches or is absent | stamp present and disagrees with the running `synapse.__version__` | probe failed |
| `log_file` | `synapse.log` exists (size + mtime reported) | file logging enabled but no file — nothing has logged, or bootstrap failed | `SYNAPSE_FILE_LOG=0` |
| `telemetry` | `telemetry.json` younger than 2× the flush interval | stale — the flusher thread is not running | file absent, or flush disabled |
| `memory_key_fingerprint` | active key fingerprint matches the store's `key.fingerprint` sidecar | mismatch — the seat's key is not the store's key (remediation: provision the show key via `SYNAPSE_ENCRYPTION_KEY`; do NOT delete or resave the store) | `no_store_dir` / `no_sidecar` / `no_crypto` / `no_key` |
| `symbol_table` | committed `h21_symbol_table.json` stamp == running `hou.applicationVersionString()` | table missing/corrupt, or stamp != running build (regenerate per build) | table read fine but no `hou` — runtime comparison skipped |
| `bridge_endpoint` | `~/.synapse/bridge.json` parses (host/port/pid reported) | present but corrupt | absent — server not started on this machine |
| `houdini` | live handler passed and `hou` available | handler live but `hou` unavailable | doctor run outside the bridge |

The key-fingerprint check is **read-only by construction**: it resolves key
bytes itself (`$SYNAPSE_ENCRYPTION_KEY` else `~/.synapse/encryption.key`)
and never instantiates `CryptoEngine` — the engine auto-generates and
*writes* a key when none exists, which a diagnostics run must never do.
Both fingerprints are non-secret (sha256, first 8 hex).

### Bundle mode

`synapse_doctor` with `bundle: true` writes a zip to
`~/.synapse/diagnostics/synapse_diag_<UTC>.zip`. The result manifest
records what was **collected** (name + size), what was **absent** (with the
reason: missing / unreadable / too large), and what was deliberately
**excluded**. Candidates:

- `logs/synapse.log` + rotations, `telemetry.json`, `freeze_dump_*.json`
- `bridge.json`, `deploy.json`
- newest 3 audit files (per-file cap 5 MB)
- `agent_health_history.jsonl` (tail-capped 1 MB)
- newest 3 Floor provenance + ledger records (when resolvable)
- the doctor's own report as `doctor_report.json`

Global per-file cap 10 MB. **Hard-coded exclusion denylist (test-pinned —
secrets are never collected):** `encryption.key`, `encryption.key.bak`,
`auth.key`, `users.json`, `memory.jsonl`. Each appears in the manifest as
excluded so the operator sees what was deliberately not collected.

`doctor` is **not** read-only-classified: bundle mode writes a zip, so a
run takes the C5 mutation lock and leaves audit + Floor provenance records
(zero `hou` work — the lock hold is milliseconds).

## 4. Durable artifact map

Where the evidence is after a crash — every durable writer in the tree:

| Location | Writer | What it answers |
|----------|--------|-----------------|
| `~/.synapse/logs/synapse.log` (+`.1..3`) | `core/logfile.py` | what every `synapse.*` logger said (INFO+) |
| `~/.synapse/logs/telemetry.json` | `server/telemetry_dump.py` | last periodic snapshot: dispatch waits, tool durations, freeze stats |
| `~/.synapse/logs/freeze_dump_*.json` | `server/freeze_chain.py` `_escalate` | process state at the sustained-freeze deadline (newest 5) |
| `~/.synapse/diagnostics/synapse_diag_*.zip` | `server/doctor.py` | operator-collected support bundles |
| `~/.synapse/bridge.json` | `server/bridge_endpoint.py` | which host/port/pid the live server published |
| `~/.synapse/audit/` | `core/audit.py` | hash-chained audit trail of agent actions |
| `~/.synapse/gates/` | `core/gates.py` | consent proposals + decisions |
| `~/.synapse/encryption.key` (+`.bak`) | `core/crypto.py` | the per-user auto-generated memory key (secret — never bundled) |
| `~/.synapse/auth.key` | `server/auth.py` | shared WS auth key (secret — never bundled) |
| `~/.synapse/users.json`, `deploy.json` | `server/sessions.py` | user directory + deployment mode |
| `$HIP/.synapse/` (memory store + `key.fingerprint`) | `memory/store.py` | scene memory; which key the store was last saved under |
| `$HIP/.synapse/render_reports/` (+`~/` fallback) | `server/handlers_render.py`, `render_farm.py`, `render_notify.py` | render outcomes |
| `<repo>/.synapse/provenance/` | `core/floor_gate.py` | Tier-0 per-mutation provenance records |
| `<repo>/.synapse/ledger/` | `memory/ledger.py` | agent.usd ledger records |
| `$SYNAPSE_ROOT/.synapse/agent_health_history.jsonl` | `panel/agent_health.py` | advisor recommendation history |
| `<claude_dir>/agent.usd` | `memory/agent_state.py` | orchestrator execution state |
| show.json (`$HIP`/`$JOB`) | `core/show_config.py` | show-scoped configuration |
| `<repo>/.synapse/scout_corpus/` | `cognitive/tools/scout_ingest.py` | materialized scout retrieval corpus |
