# LATENCY RELAY — Operator's Card

**Charter** · `docs/reviews/synapse-latency-report-2026-07-27.md` §5

---

## Run it

```
use a workflow: latency-relay
```

Optional args:

```
{ "measureOnly": true }     — fresh numbers only, no code changes
{ "maxItems": 1 }           — one forge item this run (default 2)
```

Or conversationally, without the workflow:

```
dispatch latency-relay-orchestrator
```

---

## What it does

**Orient** → newest latency report + a real bridge ping (never trusts "connected")
**Measure** → bridge up only; read-only; writes `harness/notes/latency_measure_<date>.md`
**Act** → one worktree branch per §5 item, U1–U4 first; full pytest green
**Verify** → crucible attacks every deliverable before it reaches you

---

## What it will never do

- Merge a branch — **yours**
- Start the bridge — **yours** (Houdini → Python Panel → start Synapse server)
- Touch U5 / U6 / U7 — parked until their numeric gates fire on real session data
- Run mutation-class measurement steps — need your consent in a live session

---

## When it breaks

| Symptom | Move |
|---|---|
| "bridge down — measure leg blocked" | Start the server in Houdini, re-run |
| Forge returns `refused` | Dispatch named no §5 item or a parked one — check the item id |
| Verifier says `holds: false` | Read its findings; one bounded repair, then it halts for you |
