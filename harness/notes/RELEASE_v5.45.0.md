# SYNAPSE v5.45.0 — resource-aware cache advisor (Phase 0+1)

Released 2026-08-09. Wave R-CACHE-1: intake-adjudicated (16 ADOPT / 6 ADAPT / 16 CORRECT / 5 REJECT,
19/19 challenges sustained), CTO-ruled adopt-with-amendments, built by agent teams, live-assayed.

## Highlights

- **Read-only cache advisor**: `synapse_assess_cache` through the existing bridge registry
  (read-only class), advice card on the existing panel surface, feature-flagged OFF by default
  (`SYNAPSE_CACHE_ADVISOR_ENABLED`).
- **Pure policy package** `python/synapse/cache_policy/`: typed models, deterministic verdicts,
  UNKNOWN discipline — no `hou`, no Qt, unit-testable anywhere.
- **Evidence-first host probe** `host/cache_host_probe.py`: passive assessment, never forces a
  dirty cook (negative-control tested), ms→s conversion in exactly one place.
- **Live-observed H22.0.400 contract** (SUPPORT_MATRIX row, receipts committed):
  `lastCookTime()` = accurate milliseconds in a GUI session; **0.0 unconditionally headless**
  (perfMon irrelevant). Probe classifies non-positive readings with cook evidence as UNKNOWN
  (`lastCookTime_unreported`) — never a fabricated zero. Assay item 3 holds this as a declared delta.
- **Crucible catch shipped closed**: an LLM-reachable `policy_overrides` lever found in review
  and welded shut before CLEAR (0688a16e).

## Verification

154/0 cache tests · live assay 7/7 (exit 0) on 22.0.400 · full suite 6001 pass / 2 known
pre-existing environment failures (W1 Moneta pending, Py3.14 vendored-ABI pending).

## Explicitly not in this release

Phase 2 (cache insertion/baking) — REJECTed at adjudication pending SideFX response on
in-flight cook cancellation (`H3a_SIDEFX_ASK.md`). Phases 3–4 deferred.
