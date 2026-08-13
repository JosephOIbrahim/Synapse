# Latency Authority — Ruling R2 (2026-08-13)

*Ruled under Joe's close-the-loop word, 2026-08-13, by the CTO session. Standing
unless Joe overrules. This document is the authoritative disposition of the
SYNAPSE latency magnitudes; all prior latency papers remain in-tree as history.*

## Ruling

**Measured numbers are authoritative. A magnitude without a producer path is
historical context, never a work-gating fact.** This is the UNKNOWN law applied
to papers: a document may motivate a probe; only a probe may motivate a fix.

## Lineage (oldest → newest, all preserved in-tree)

1. `docs/reviews/synapse-latency-report-2026-07-17.md` — earliest survey.
2. `docs/reviews/synapse-latency-report-2026-07-27.md` — ancestor of the wave-1
   source papers.
3. `docs/SYNAPSE_latency_and_karma_rendersettings_2026.md` and
   `docs/SYNAPSE_production_readiness_report_2026.md` (2026-08-12, committed
   with wave 1) — carried the 648 / 780 / 648 / 306 ms magnitudes.
4. FRZ receipt (`033f978e`) — authority: every rung-5 magnitude UNMEASURED;
   the reported freeze never reproduced under instrumentation.
5. W1-MTFIX live GUI probe (Houdini Indie 22.0.400, ui_available=true) —
   current measured truth.

## Disposition per number

| Claim | Source | Status |
|---|---|---|
| 648 ms doctor main-thread hold | 08-12 papers | **UNCONFIRMED** — no producer path (FRZ) |
| 780 / 648 ms panel finalize / append | 08-12 papers | **UNCONFIRMED** — result path unexercised in probe session |
| 306 ms dispatch-wait tail | 08-12 papers | **UNCONFIRMED** — no producer path |
| 0.63 ms max main-thread hold (general) | W1-MTFIX live probe | **MEASURED** — current |
| ~514 ms run_doctor main-thread hold on the in-Houdini hwebserver transport | W1-MTFIX live probe | **MEASURED** — current; the real remaining target (wave-2 S1) |
| ~5–6 s intermittent stickiness | FRZ candidate list | **UNREPRODUCED** — probe-first per R-FRZ-3 (wave-2 S4) |

## Consequences

- Wave-2 **S1** is gated open: its target is the measured 514 ms hwebserver
  hold, not the unconfirmed 648 ms figure.
- Wave-2 **S4** probes the stickiness discriminator before any fix ships.
- Future missions cite this document plus a probe path; citing a raw magnitude
  from the historical papers is a crucible finding.
