# P0 — Integrity/attestation layer blocks the entire write plane on cold install

**Severity:** P0 (product front door is broken)
**Status:** Triaged · Awaiting fix
**Filed:** 2026-08-02
**Environment:** Houdini 22.0.397 · Synapse protocol 4.0.0 · untitled.hip · fresh/empty install (0 memories, 0 sessions)

---

## Summary

On a fresh/empty install, every tool that **mutates state or persists anything** fails with
`Bridge: Integrity check failed: fidelity=0.0`. Purely read-only/ephemeral calls succeed. The
mandated session entry point (`synapse_project_setup`) is among the first to fail, so the very
first thing a new user sees is an unrecoverable error. The system reports `healthy: true` the
whole time.

Net effect: a brand-new SYNAPSE cannot build, write, render, remember, or even run the setup
sequence the system prompt demands. It can answer health pings and describe an empty scene.

---

## Repro

1. Start Houdini with Synapse on a fresh install (no `~/.synapse` state, no scene memory).
2. Call any of the tools below.

### Fails with `fidelity=0.0` (14/14 mutations)
```
synapse_project_setup          synapse_decide                 synapse_write_report
synapse_doctor                 synapse_memory_write           synapse_write_report (overwrite)
synapse_doctor(bundle)         synapse_add_memory             houdini_create_node
synapse_memory_query  ✱        synapse_evolve_memory   ✱      houdini_execute_python
                              (✱ = returned benign, but any real content write also fails)
```
(Every persistent-write API, both memory APIs, the report writer, the Houdini node graph,
and raw python — all identically rejected.)

### Succeeds (the intact read plane)
```
synapse_ping        synapse_health      synapse_context       synapse_router_stats(→not initialized)
synapse_list_recipes synapse_metrics    synapse_memory_status synapse_knowledge_lookup(→empty)
houdini_scene_info  synapse_live_metrics(→not running)
```

---

## Boundary (what's broken vs. what isn't)

| Plane | Verdict |
|---|---|
| Bridge handshake / protocol | OK (pong, protocol 4.0.0) |
| Read / introspection | OK |
| Telemetry exporters | OK (metrics render) |
| Scene-graph mutation (`create_node`, `execute_python`) | BROKEN |
| Persistence (`memory_write`, `add_memory`, `decide`, `write_report`) | BROKEN |
| Resilience / attestor path (`doctor`, `project_setup`, `evolve`) | BROKEN (throws, not graceful) |
| Subsystem init (router, aggregator, Moneta store) | NOT RUNNING (secondary) |

**Single fault domain:** the integrity/attestation checker that every mutation/persistence call
routes through. On an empty store the fidelity it computes is `0.0`, and `0.0` is treated as
**fail-closed ⇒ reject**. The cold-start case was never given a "trust-but-bootstrap" path, so an
empty-but-legitimate install is indistinguishable from a compromised one — and gets blocked.

Two distinct bugs are stacked:
- **(a) Fail-closed vs. cold-start.** The checker has no concept of "nothing to attest yet." It should
  emit a *bootstrap/trust-on-first-use* token on first successful bridge handshake, not `0.0/fail`.
- **(b) Non-graceful callers.** `project_setup` and `doctor` should degrade to "no memory yet" instead of
  surfacing the integrity error to the artist. Right now they leak the raw fault.

---

## Why this is P0

- It breaks the **CTO call's two pillars before either can run**: live-oracle grounding needs
  `propose/instantiate` (mutations) and the memory flywheel needs `memory_write` (persistence).
  Both are behind this gate.
- It is the **first-run experience** — the moment a user decides whether the tool is trustworthy.
- It makes **RSI scaffolding inert**: the stores stay at 0 entries / evolution "none" forever,
  so nothing ever compounds.
- `synapse_health` says `healthy: true` while the product is fully write-blocked — a monitoring
  blind spot that will hide this in the field.

---

## Recommended fix (in order)

1. **Add the cold-start trust path.** Distinguish "empty store" from "integrity violated."
   `fidelity=0.0 && store_empty ⇒ bootstrap`, not `fail`. Fail-closed only when attested content
   *should* exist and doesn't match.
2. **Make the checker attestation-only, not execution-blocking, for reads/health.** Health should
   report `write_plane: blocked` as a first-class status instead of `healthy: true`.
3. **Graceful degradation in mandated-entry tools.** `project_setup`/`doctor` return
   `{memory_state: "cold", write_plane: "bootstrap"}` and proceed — never throw to the artist.
4. **Regression test:** fresh-install integration test asserting `project_setup` + one
   `memory_write` + one `create_node` all succeed on first boot. (The canary that would have
   caught this.)
5. **Init-order fix (secondary):** router/metrics-aggregator "not initialized/not running" should
   either auto-start or be removed from the surfaced schema until they do.

## Acceptance criteria
- Fresh install: `project_setup` → `memory_write` → `create_node` all succeed; `health` reflects
  write-plane state accurately.
- `fidelity` only ever blocks when content was *supposed* to exist and mismatched — never on cold.
- No raw integrity string is ever returned to the artist.

---

*Filed from live triage: 26 calls, 14 writes blocked, 8 reads OK, boundary confirmed by the
read/write split. Repro is deterministic on a cold install.*
