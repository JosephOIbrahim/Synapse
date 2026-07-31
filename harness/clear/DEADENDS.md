# CLEAR — DEADENDS

*Append-only registry of rejected directions + reasons. Read before proposing. Never re-pay for a known dead end.*

## Pre-registered (known at FRAME — do not retry without a gate flip)

### husk-render-cure
- **axis:** husk-render-cure
- **direction:** out-of-process husk/hython renders
- **observed change:** would fix the residual in-process render freeze
- **rejection reason:** Indie silently no-ops husk (no errors, no output). Blocked on the Indie license. **PARK** behind a named gate; do not retry until a real gate flips. (See `[[synapse-render-freezes-houdini]]`, `[[synapse-h21-render-husk-indie]]`.)
- **status:** P3.4 — register the deferral, do not queue a fix.

### decisions-board-team
- **axis:** decisions-board
- **direction:** spawn a multi-agent team to decide the 289 open items
- **observed change:** would "close" the queue automatically
- **rejection reason:** `decisions.py` proved only 5 of 26 unratified cycles are agent-decidable; 20 are genuine human judgement calls. The bottleneck is human **ATTENTION**, not authority. A team is theater. Do not retry.

### latency-report-direct-edit
- **axis:** latency-report
- **direction:** edit `docs/reviews/synapse-latency-report-2026-07-27.md` directly
- **observed change:** append the §1 addendum
- **rejection reason:** Joe's gate. The report is checked-in and gated. Flag only; do not edit without Joe. P3.5 clears on an addendum file OR a "gated, deferred" entry, never on a silent edit.

### version-VERSION-agent-edit
- **axis:** version-VERSION
- **direction:** agent edits the `VERSION` file
- **observed change:** would bump version
- **rejection reason:** `harness/CLAUDE.md` says don't edit `VERSION` from an agent; `harness/verify/version_agreement.py` governs the 5-location agreement. Do not edit `VERSION` from the harness.