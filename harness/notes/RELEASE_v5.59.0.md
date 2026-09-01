# v5.59.0 — the day the numbers replaced the guesses

Draft release notes. **Draft only — not published, no tag cut.** Publish is
gated on the operator seat (g1/g5/g6/g9 · Ctrl+Z · drop.json · R.R verify),
per the release ritual, and on Joe's re-signed waiver for the four standing
RC blockers. Every claim below is receipt-backed on master (HEAD at draft
time `ac76bf3f`; CI in flight on the merge). Where a claim needs eyes on a live
Houdini it says UNKNOWN, not green.

Scope: wave **BP2 pairs 1+2** of `docs/BATTLEPLAN.md` (2026-09-01) — four
builder legs plus an adversarial crucible, all **SOUND-WITH-NITS**, chain
intact, merged zero-conflict on an integrated tree that ran **6905 passed /
186 skipped / 0 failed**.

## For artists

**Memory has a number, and it is small.** Deposit acknowledges in ~70 ms,
recall answers in ~3 ms, and closing the scene and reopening it with the
memory layer costs ~130 ms — measured five times each on the demo shape
(Moneta backend, 200 memories, Houdini 22.0.400 in-process), against camera
budgets of 500 / 1,500 / 3,000 ms. No bucket, no fix leg. The number that
matters most — the one taken in the GUI — is still yours to take: the probe
pastes into the Python shell. UNKNOWN until you do.

**The panel opens where you left it.** Ctrl+K now prefers your docked Synapse
tab, then a tab in the network editor's pane, and only floats when there is
nowhere to dock — the float hijack is gone in code. **The TOKEN face updates
when a task finishes**, from the real usage sink, never from a timer.
Both verified headless; **the live-GUI half is UNKNOWN** until eyes on .400.

**Profiles differ exactly as much as the receipt says.** Curious / Expert / ML
resolve to the same widget set; what differs is density, the system-prompt
overlay, and per-widget collapsed/prominence knobs. That receipt
(`profile_diff.json`) is the spacing pass's input, not an assumption.

**The store says which backend it is.** `backend_health()` reports requested
backend, active backend, embedder, dimension, rows and a ratified verdict
(SUCCESS | UNAVAILABLE | BLOCKED). Asking for Moneta and being served JSONL
is now UNAVAILABLE, never a healthy green. The server-side health row that
mirrors it into the panel is a closing-wave item, not in this release.

## Under the hood

**The harness meters tokens.** A leg's real transcript settles into the rails
ledger at its done transition — integers or the literal UNKNOWN, never an
estimate. First measured builder leg: 59.4 M tokens in / 726 k out. Per-leg
tiers (referee / reasoning / mechanical) resolve from one lookup table; the
closing wave's first Haiku dispatch went through it. A bus-driven drift check
refocuses a leg that stops citing its targets. A live ledger now reads
`open`, not `complete`.

**FU-1 and FU-2 were already done.** `MONETA_FOLLOWUPS.md` lagged #16; the
STORE leg found it in ten minutes and pinned it with tests instead of
re-fixing it. The docs get flipped in the closing wave.

**Integration is a gate.** Two failures existed only on the merged tree —
six harnesses each ship a `mission_schema.py` and a bare import returned the
wrong one; JSON-Lines artifacts wore `.json`. Both fixed on their branches,
the suite re-run green, then merged. The crucible re-audits both in CRUXB.

**One territory breach, remediated in-session.** A leg wrote into the master
working tree instead of its worktree; caught on the bus at 12:20, moved,
master restored, nothing reached master's history.

## Not in this release (closing wave, in flight)

Panel rhythm / spacing pass (PANELDESIGN) · server health row wiring
(HEALTHWIRE) · METER's proof artifact regenerated parent-vs-HEAD and the
`MONETA_FOLLOWUPS.md` flip (NITS) · live end-to-end settle proof (METERLIVE)
· their crucible (CRUXB).

## Standing RC blockers (waiver re-signed per release)

`mutation_fail_closed · hot_reload_gated · installer_host_targeted ·
ci_covers_shipping_surface` — unchanged since v5.51; published-over under
Joe's waiver at v5.56.0 and v5.58.0. This release publishes only if that
waiver is re-signed by Joe's word.
