# Audit State Capture — Scope

**Status:** scoped, not started
**Target:** `python/synapse/core/audit.py`
**Dated:** 2026-08-02

---

## Why

Measured against the live corpus (`~/.synapse/audit/`, 90 daily files,
22,025 records decoded at a 400/file cap, 11 decrypt failures):

| Field | Fill rate |
|---|---|
| `operation`, `category`, `level`, `session_id` | 100% |
| `entry_hash`, `previous_hash` | 100% |
| `output_data` | 97.5% |
| `input_data` | 92.5% |
| `sequence_id` | 1.4% |
| `agent_id` | 1.3% |
| `before_state_hash` | **0%** |
| `after_state_hash` | **0%** |
| `tool`, `user_id` | **0%** |
| `duration_ms` | always `0.0` |

This is not a bug. `AuditEntry` declares all of these fields, but
`AuditLog.log()` — the only method that constructs entries — accepts no
parameter for `duration_ms`, `before_state_hash`, `after_state_hash`, or
`user_id`. The slots were designed in and never wired up.

---

## The enabler

`AuditEntry._compute_hash()` hashes only:

```
timestamp_utc, level, category, operation,
message, tool, agent_id, operation_id, previous_hash
```

It does **not** cover `input_data`, `output_data`, `duration_ms`,
`before_state_hash`, or `after_state_hash`.

Consequence: filling those fields is **chain-safe**. Every existing entry
still verifies. No migration, no version bump, no reprocessing of six
months of logs.

One caveat — `tool` and `agent_id` *are* hash inputs. Passing them going
forward is fine (new entries hash whatever they carry). Backfilling them
into historical entries would break the chain. Never rewrite old lines.

---

## Piece 1 · Plumb the fields

One file, ~6 lines, zero downstream risk.

```python
# AuditLog.log() signature — add:
    duration_ms: float = 0.0,
    before_state_hash: str = "",
    after_state_hash: str = "",

# AuditEntry(...) construction — add:
    duration_ms=duration_ms,
    before_state_hash=before_state_hash,
    after_state_hash=after_state_hash,
```

Callers that don't pass them behave exactly as today.

**Done when:** a hand-written entry round-trips
`_persist_entry` → decrypt → `from_dict` with values intact, *and*
chain verification still passes on a file holding both old and new entries.

---

## Piece 2 · Define what a state hash *is*

The only real design work here, and it is deciding rather than typing.

Whole-scene hashing is correct and unusable — it would dominate the
latency of every call the bridge makes. Scope the hash to blast radius:

| Operation class | Corpus volume | Hash target |
|---|---|---|
| `set_parm` | 4,311 | touched node's parm dict (name → evaluated value) |
| `cops_create_*`, `create_node`, `create_network` | ~3,500 | parent's child list, `(name, type)` sorted |
| `batch_commands` | 984 | union of touched node paths, hashed as a set |
| `execute_python` | 2,089 | **null** — unbounded blast radius |
| read-only (`cops_read_*`, `ping`) | — | skip; before == after by definition |

`execute_python` gets `""` and stays honest. A fabricated hash is worse
than an absent one: it would teach a downstream failure predictor that
unscoped operations are always clean.

Canonical form matters more than the algorithm choice:

- sort keys before hashing
- fix float formatting explicitly
- **exclude cook-time-varying parms** — `$F`-dependent values evaluate
  differently per frame and would generate spurious diffs on every call

---

## Piece 3 · Capture site

The middleware already wrapping every call for atomicity. One decorator:

```python
before = state_digest(op, args)
t0     = time.perf_counter()
result = fn(*a, **kw)
dt     = (time.perf_counter() - t0) * 1000
after  = state_digest(op, args)

log(..., duration_ms=dt,
    before_state_hash=before,
    after_state_hash=after)
```

`duration_ms` falls out of the same wrapper for free.

**Cost to watch:** `state_digest` runs twice per call. On `set_parm` it
must be sub-millisecond or it becomes the bridge's dominant cost. Measure
before rollout; the budget belongs in `LATENCY_PLAN.md`.

---

## Do not bundle

Extending `_compute_hash()` to cover `input_data` / `output_data`.

It is the right call eventually — those fields currently sit *outside*
the tamper-evident envelope, which materially weakens what the ledger
claims to prove. But changing hash inputs invalidates every existing
entry. Own change, own chain version bump (`hash_version` field, or
`SYNAPSE_ENC_V1` → `V2`).

---

## Choose deliberately, before Piece 2

A hash gives **change detection**, not state content.

- Enough for: *did this operation change anything? did it change what it
  claimed to?* — which is the failure predictor.
- Not enough for: learning state transitions, or predicting resulting
  values.

If the second is wanted, store the parm dict itself rather than its
digest. Costs disk and raises the encryption load. This decision changes
what `state_digest` returns, so make it first.

---

## Not solved by this

The routing classifier. `input_data` holds the arguments passed *to the
tool*, never the natural-language request that prompted it — predicting
`operation` from its own arguments is close to circular. That needs a
separate field carrying the inbound request text. Orthogonal to this
scope; do not let it creep in here.

---

## Where things live

| What | Path |
|---|---|
| Writer | `python/synapse/core/audit.py` |
| Encryption | `python/synapse/core/crypto.py` |
| Live audit stream | `~/.synapse/audit/audit_YYYY-MM-DD.jsonl` |
| Gate stream | `~/.synapse/gates/proposals_YYYY-MM-DD.jsonl` |
| Key | `~/.synapse/encryption.key` |
| Probe scripts | `~/Downloads/synapse_schema_probe.py`, `synapse_fill_probe.py` |
