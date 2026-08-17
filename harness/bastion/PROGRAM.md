# BASTION — SYNAPSE Production-Hardening Program

Ratified 2026-08-17 by Joe's word ("go"). This document is the source-of-truth
review paper for wave **W8** (BASTION Wave 0). Program goal: harden SYNAPSE for
production across seven majors — one blueprint per major, authored from W8
evidence, executed on a hardened fork of the AUTOREVISE harness.

## Position at ratification
- v5.51.0 shipped ("Close the tab, keep the session"); master @ 782b2376.
- APEXFORGE WA1 authored + pushed, PARKED AT ARM WORD — separate program,
  independent arm queue. BASTION does not touch it.
- W5 substrate crucible (WCRUX / WXA / WXB / WXC) in flight this morning.
  BASTION W8 shares no write surface with it.
- Steward alive (deadline-bounded); /rc delivery confirmed via ledger,
  /rc DEFINITION UNKNOWN — not on disk under .claude or repo. See doctrine.

## The seven majors (one blueprint each, authored in Chunk C from W8 evidence)

| BP | Codename  | Scope | Seed evidence |
|----|-----------|-------|---------------|
| B1 | LIFECYCLE | runtime/session lifetime vs UI, undo contract coverage, Qt thread discipline, crash recovery | P0.3 killed at g5 (v5.51.0); SESSCOPE shipped; `_on_main` class |
| B2 | TRUTH     | schema catalog, cook-verify contracts, per-build stamping, claim-without-observation enforcement breadth | lastCookTime() headless 0.0; face_token.py; H21-stamp staleness class |
| B3 | ENGINE    | five-backend failover/timeout/retry, cost+capability routing, offline mode, NL-to-node injection defense | Sanitize-SQ shipped (W6); defense breadth unmeasured |
| B4 | MEMORY    | Moneta hardening, SQLite+FTS5 storage (old wave-6 plan folds here), ingest-ladder readiness, capsule persistence | Moneta env-gated; perf envelope UNKNOWN |
| B5 | SURFACE   | panel/shelf/ROP UX, install + packaging (prefs-path bug class), first-run, error language, operator docs | OneDrive prefs finding; L3-5 Apprentice open |
| B6 | SHIELD    | secrets incl. git history, dependency pinning, telemetry privacy, public-repo vs patents-pending hygiene | UNAUDITED — no prior wave touched this |
| B7 | SHIP      | g1-g9 ritual automation, VERSION-sync as contract, SUPPORT_MATRIX tested-vs-asserted, CI, distribution | F-G9-ROLLBACK; sync_version.py; 6587-test verify |

Mission anchors: B1-LIFECYCLE B2-TRUTH B3-ENGINE B4-MEMORY B5-SURFACE
B6-SHIELD B7-SHIP W8-LIBRARIAN HARNESS-V2-SMITH

## Wave W8 — BASTION Wave 0 (scouts + librarian + smith)

Nine legs, Opus pinned, cap-20 respected (live agents = WX remnants + 9).

- **W8-SLIFE .. W8-SSHIP** — seven scouts, band TRUTH, readonly, one per
  blueprint. Read-only recon of the live repo + receipts + rulings. Findings
  ranked P0/P1/P2 with file:line anchors, first-hand or UNKNOWN. Bus findings
  addressed to W8-LIBR AS THEY LAND — never batched.
- **W8-LIBR** — synthesizer, band TRUTH, readonly, deps on all seven scouts.
  Dedups scout findings against existing receipts, rulings, and the W6
  failure-class ledger; emits the canonical FINDINGS INDEX (one writer) at
  harness/bastion/FINDINGS_INDEX.md on its own branch. Chunk-C blueprints
  cite the index, not raw scout output.
- **W8-SMITH** — band BUILD, touches harness/bastion/** only. Forks
  AUTOREVISE into harness/bastion/ as BASTION harness v2: schema admits a
  skills[] field per mission (compile injects skill paths into leg prompts);
  typed bus messages (CLAIM/FINDING/HANDOFF/BLOCK/RELEASE); steward
  arm/refresh clause folded into the arm-script template; /rc bake-in slot.
  TASK 1: resolve the /rc definition. No W8 leg depends on SMITH — v2
  serves the exec waves, not W8 itself.

## Rules carried (constitutional, unchanged)

commit-before-receipt · one writer per surface · no amends on master ·
crucible/synthesizer before merge · UNKNOWN never zero, never estimated ·
no pre-approval of unseen verdicts · merge / push / drop.json / ratified
flips / tags = per-act explicit human words · named-file adds only, never
`git add -A`.

## /rc doctrine

Delivery: steward (deduped ledger, observed working across W6 + W5 waves)
covers windowed legs; deadline refresh becomes part of every arm script so
steward liveness is a property of arming, not a separate manual act.
Headless (-p) legs have no window and are unreachable by SendKeys — bake-in
into the leg prompt is required for full coverage. Bake-in is blocked on the
/rc DEFINITION (UNKNOWN): filename + doc greps came back empty 2026-08-17
(.claude recursive, repo recursive, CLAUDE.md, harness/SPEC.md). W8-SMITH
task 1 resolves it — live-session interrogation or Joe states it. Until
resolved, W8 runs windowed-or-steward-covered and the UNKNOWN stays named.

## Budget + touchpoints

Fable: taxonomy, blueprint authoring, regulation only — W8 runs on Opus
while Fable idles. Touchpoints: (1) this ratification · (2) one batched
sitting: W8 findings accept + seven blueprints ratified · (3) enumerated
merge-train + Gate C words per exec wave · (4) red tier only — GUI
receipts, MCP re-record, eyes-on-viewport.

## Sequence

M0 this doc + W8 missions (DONE at commit) → M1 W8 armed, scouts land,
LIBR index committed → M2 seven blueprints authored (Chunk C, Fable) →
M3 BASTION harness v2 live (SMITH verdict + merge word) → M4-M6 exec
waves B1..B7 on v2 → destination: seven contract sets green, g1-g9 full
green, production cut.
