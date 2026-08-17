# Cook-verify goldens — W5-MEASURES

Deterministic fixtures that pin the measurement contracts in
`python/synapse/validation/measures.py` and the explosion detector in
`python/synapse/validation/explosion.py`.

## Layout

```
rulebook/goldens/<domain>/<name>.json
```

Each golden is one output of a known character. Its shape:

```json
{
  "kind":   "sim | image | geometry | channels | graph",
  "name":   "unique fixture name",
  "seed":   20260816,
  "expect": { "verdict": "MEASURED | UNKNOWN | FAIL | EXPLODING", "...": "signal/frame anchors" },
  "obs":    { "...": "the measured observation the contract judges" }
}
```

`obs` is exactly what a live cook would hand `measures.measure(kind, obs)`. The
fixtures carry the observation directly so the **contract + detector are fully
testable headless** — no Houdini needed to prove that a healthy sim reads STABLE
and a blown-up one reads EXPLODING with the offending frame.

## The two halves — and which one is UNKNOWN headless

1. **Judgement (headless, tested here).** Given `obs`, the contract renders a
   verdict. Pinned by `tests/test_measures_contracts.py`. Runs on any interpreter.

2. **Production (hython, UNKNOWN headless).** A live runner cooks the golden's
   scene in Houdini, extracts the per-frame / per-output signals, and feeds them
   to the same contract. That cook **cannot run in a headless worktree** — it is
   `gui_required` / seat-only. Per the leg's crucible criterion 2, a golden whose
   cook cannot run headless renders **UNKNOWN with the exact failing invocation**,
   never a simulated pass. The runner is therefore a live-seat gate (the same
   posture as the parity/seat probes), not a CI claim.

**Honesty rule:** never commit a golden whose `expect` claims a live-cook result
that was not actually cooked. The `obs` here are hand-authored signal fixtures for
the judgement half; a live-cooked `obs` must carry its cook provenance (hip, build,
frame range) before its verdict may be cited as cook-verified.
