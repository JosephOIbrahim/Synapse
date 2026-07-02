# MCP Coexistence — SYNAPSE alongside other Houdini MCP servers

> **Scope:** how SYNAPSE's 115 registered tools coexist with other MCP servers
> talking to the *same* Houdini session — the de-facto third-party overlap
> (fxhoudinimcp, 179 tools) today, and whatever SideFX ships with H22.
> Companion to `docs/SYNAPSE_H22_BOUNDARY.md` (the ratified boundary) and the
> WS2 multi-client hardening pass (H1–H5, 2026-07-01).

## Posture: KEEP-ALL + documented differentiation

**No renames, no deprecation of the ~66 overlapping scene primitives.**

The only confirmed official H22 MCP is a *knowledge* server (APEX Script
Comfort Package: snippets + syntax rules + validator) with **zero functional
overlap** with SYNAPSE's scene primitives; an official scene-mutation MCP is
speculative. The de-facto overlap (fxhoudinimcp) has no undo wrapping, no
integrity hashing, no ledger — SYNAPSE's primitives are differentiated by
receipts, not by existence. Mass renames would break existing clients and
violate the surgical rule without evidence.

**Re-evaluation trigger:** revisit keep-all if SideFX ships a scene-mutation
MCP — the decision then is evidence-driven via a D-H22-4-style surface probe
of the shipped tool list, not speculation.

## Differentiation: receipts, not existence

| Property | SYNAPSE primitive (e.g. `houdini_create_node`) | Foreign equivalent (fxhoudinimcp) |
|---|---|---|
| Undo wrapping | `hou.undos.group()` per mutation (bridge + handlers) | none — raw `hou.*` calls |
| Integrity hashing | scene hash before/after + `delta_hash` (R1) | none |
| Rollback on failure | hash-guarded single `performUndo()` (H2) | none |
| Foreign-edit attribution | `external_change_detected` on the IntegrityBlock (H1) | none |
| Consent gates | INFORM/REVIEW/APPROVE/CRITICAL on the `/mcp` bridge path | none |
| Provenance/ledger | IntegrityBlock log + agent.usd schema | none |
| Main-thread safety | `hdefereval` / `run_on_main` marshalling with timeout + stall detector | `hdefereval` marshalling |

## Why within-op interleave is not the exposure

On both SYNAPSE hou paths, hash_before → fn → hash_after → rollback all run
inside ONE main-thread closure (`shared/bridge.py` `_execute_houdini` /
`_sync_payload`). Foreign clients also marshal via `hdefereval`, so foreign
work **cannot interleave inside a SYNAPSE op**. The real exposures are the
four hazard classes below.

## Hazard classes and shipped mitigations (WS2 Part 2)

### 1. Between-op foreign mutation (attribution, not locking) — H1
The scene can legitimately change *between* SYNAPSE ops (artist or foreign
client — indistinguishable). The bridge parks the last computed hash per
hash target at op end and compares it to the next op's `scene_hash_before`;
a difference sets `external_change_detected: true` on that op's
IntegrityBlock (`to_dict` included). **Informational only — never a fidelity
violation**: auto-reverting a "foreign" edit would revert the artist, the
worst possible failure. Zero extra hashing (compares already-computed values).

### 2. Empty-group rollback edge (undo safety) — H2
`performUndo()` after an op that raised **before mutating** pops the
artist's or a foreign client's most-recent undo block. The shared
`_guarded_rollback` (both bridge exception sites) now:
1. skips `performUndo()` when the scene hash is unchanged
   (`delta_hash = "no_mutation_no_rollback"`);
2. after a real rollback, re-hashes and reports
   `delta_hash = "rollback_incomplete"` with an attribution note when the
   scene did not return to its pre-op state (honest surfacing instead of a
   false `"rolled_back"` claim);
3. falls back to the pre-H2 unconditional single `performUndo()` when either
   hash is a sentinel (`"invalid_context"` / no-hou timestamp fallback) —
   sentinels always differ and would false-alarm.

Undo-stack label inspection was **rejected**: `hou.undos` member APIs are not
in the introspected symbol table, so not scout-verifiable.

### 3. Sticky stall detection — H3
The stall detector trips at 2 consecutive `run_on_main` timeouts and only a
successful worker-path call resets it — recovery used to depend on incidental
read-only traffic. Both fast-fail gates (`server/websocket.py`,
`mcp/server.py`) now attempt one bounded (≤2s) `probe_main_thread()` while
stalled: success resets the counter and the command proceeds; failure
fast-fails with an attribution-aware message ("a heavy cook, render, or
another MCP client may be saturating it"). Cost: ≤2s per rejected command
while genuinely stalled. `stall_state()` (stalled, consecutive_timeouts,
last_timeout_ts) is surfaced by the doctor.

### 4. Diagnostics — H5
`synapse_doctor` gained two checks:
- `mcp_coexistence`: resolves our actual bound port (sidecar discovery),
  confirms it accepts a connection, and TCP-probes `KNOWN_MCP_PORTS` for
  foreign MCPs. Info/warn only — **never fail**.
- `main_thread`: surfaces `stall_state()` + `dispatch_wait_stats()`.

## Known residuals (documented, deliberately not fixed this cycle)

- **`execute_python` empty-group edge** (`handlers.py` inline `performUndo`):
  handler-layer rollback sites run inside the same serialized main-thread
  closure (no foreign block can be pushed between), and the COPs sites carry
  the `created_any` guard — but `execute_python`'s rollback can still pop a
  foreign/artist block when the injected code raised before mutating. Not
  surgically fixable in the runway; tracked here.
- **Out-of-target hash blindness**: the hash guard inherits
  `_compute_scene_hash`'s blind spots — mutations outside the op's hash
  target (R7 blast-radius model) or edits that don't bump
  cookCount/sessionId can skip or mis-verify rollback/attribution.
- **hwebserver port coexistence** (SYNAPSE and a foreign plugin in the same
  Houdini process) is **not verifiable pre-drop**; SYNAPSE's 9999-failover +
  sidecar discovery is the current mitigation. Mode-B verification item.
- **`houdini_undo`/`houdini_redo`** operate on the *global* undo stack by
  explicit user intent — in a multi-client session they may undo another
  client's (or the artist's) most recent action. A one-sentence caveat in
  their tool descriptions is an owner decision (docs-only reserve, not
  applied this cycle).

## Port table

| Port | Owner | Notes |
|---|---|---|
| 9999 | SYNAPSE (default) | Fails over when held; real port published to `~/.synapse/bridge.json` (sidecar discovery) |
| 8100 | fxhoudinimcp | De-facto third-party MCP; no undo/integrity/ledger |
| TBD | official H22 APEX MCP | Add to `KNOWN_MCP_PORTS` in `server/doctor.py` once task 1.7 reveals it |

## Command-ID scoping

SYNAPSE command IDs (`create_node-1`, …) are **per-process** counters
(`mcp_server.py` `_cmd_id`). Verified 2026-07-01: no server-side global
keying/dedup by command id exists; responses echo per-connection. Two
concurrent SYNAPSE stdio processes reusing the same IDs is harmless (H4 =
verified NO-OP; a pid prefix is a one-liner if global keying ever appears).

## Tests pinning this document's mitigations

- `tests/test_bridge_multiclient.py` — H1 attribution (+ not-a-violation),
  H2 guarded rollback (skip / incomplete / S1 single-rollback / sentinel
  fallback).
- `tests/test_main_thread_stall.py` — H3 `stall_state()` + probe recovery.
- `tests/test_doctor_coexistence.py` — H5 foreign-port detection + main-thread
  check.
