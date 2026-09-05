# v5.65.0 — the panel became the conversation, and the model got its name back

Release notes. Every claim is receipt-backed on master (HEAD at draft time
`f41c6694` plus the release bump, 2026-09-05 evening). Where a claim needs
Joe's eyes it says GUI-GATE; where it was measured inside his running Houdini
it says LIVE.

Scope: the panel direction B + C wave (`design/bc-wave`, merged `90c9fda2`),
built the same afternoon Joe ruled it, under his pre-approval of all of the
day's changes. One design warden wrote the spec from the ruling and the Bierut
review, one forge built it in nineteen red-then-green commits, two referees
(referee lens, design lens) attacked it, one repair round closed their list,
and the CTO ruled the seven calls they escalated (Addendum 3) and applied them
by hand when the referees' session limit hit. Then the panel was reloaded in
Joe's live Houdini and measured.

## For artists

**The panel is the conversation now.** The verb rail (EXPLAIN / FIX / OPTIMIZE /
BUILD HDA) is gone from the header; those verbs live in the `/` palette and the
overflow menu. The profile row (CURIOUS / EXPERT / ML) folded into the overflow
too. At 340 px wide the conversation holds 56 to 62 percent of the pane in every
profile; it was 37 to 48.

**The model you are talking to is always in the top right.** `ollama/deepseek-v4-flash`,
`claude/sonnet-4.6`: provider first, so local-versus-cloud and cost are one
glance. LIVE, measured in Joe's Houdini after the reload: the token is 414 px
wide at the right edge of the header. This morning it was there with a width
of 0 px. Joe's ruling, verbatim: "Not having it visible is a serious detriment
to the user interaction."

**Consent comes to you.** An approval request lands as a card in the chat, in
the panel's own vocabulary (one accent on APPROVE, mono ids, sans body), and
REVIEW gets a REVERT verb. The old rule that a gate pulled you to the Work face
is retired. REVERT is disabled while a turn is still streaming.

**The `/` palette breathes.** Rows sit on the spacing grid (40 px rows, 48 px
group heads, 4 to 6 px gaps by density), the popup takes the composer's width,
and no row is cut mid-word at 340 px any more.

**One state sentence that never gives way.** "Not connected", "Working on it",
"Stopping…" - one line under the identity row, never elided; the rest of the
header chrome reads from the overflow. The wordmark is 15 px and 5 px farther
from the mark, as Joe asked on the review canvas.

**Two things you may have hit this week, fixed.** The empty floating "houdini"
title bar beside the panel at launch: a retired 3 px widget with no parent that
the compositor kept showing; now parented and never shown, pinned by a test
that counts the windows the panel creates. And the composer clipping its own
placeholder on a tall, high-DPI pane: the pane cap could not relax once taken;
now it recomputes from your height every time and never squeezes below one
readable line. LIVE: viewport 21 px before, 71 px after.

**GUI-GATE, Joe's eyes:** the three profiles at your dock width, the palette
open, a consent card, and the token at 280 px, where nothing fits and the
docking contract says so.

## Under the hood

- Rulings on record: `harness/cto/runs/2026-09-05/RULING_DIRECTION_BC.md`
  (direction B + C, the wordmark addendum, the model-token addendum, Addendum 3
  with the seven referee escalations, and the as-shipped amendment for the `/`
  telling).
- Docking: composed minimumSizeHint per density 352 / 336 / 328 (airy /
  standard / tight), all above the 280 contract, so the interim per-density
  widths from R3-01 stay; B11 (a rail that collapses to icons) remains the real
  fix.
- Landing receipts retired or narrowed with reasons in the tests: the SWEEP_B
  QSS byte-freeze and constructor counts, the SWEEP_B tokens byte-freeze, the
  camera lifecycle byte-identity pins re-anchored at the landing, the stale
  BRAND wordmark pin (red since 2026-07-27) now pins WORDMARK. The compositor
  vocabulary drops the six hidden or deleted rail widgets; the paneltruth
  profile-diff artifact is regenerated from its producer.
- Live reload recipe (used twice today, from the bridge):
  `hou.ui.paneTabs()` → the PythonPanel tab → `setActiveInterface(hou.pypanel.interfaces()["synapse_panel"])`;
  `installFile` alone does not rebuild an open panel.

## Tests

Full suite on master `f41c6694` (stock Python 3.14.2, no `hou`):
**7605 passed, 0 failed, 346 skipped** (`harness/notes/h22/pytest_v5650_master.txt`). At the wave merge
`90c9fda2` it was 7605 passed / 0 failed / 345 skipped. Panel tier on Houdini
22.0.400 offscreen: `tests/panel` plus docking **228 passed / 1 failed** (the D1
render-view dead verb, pre-existing); G3 strict **pass, 0 WARN** (the "3 targets
under 26 px" warning is gone). Stock panel set 733 passed.

## Not in this release

The `/` palette's five-row target at a 396 px popup (physically impossible with
the search and two axis grids; the popup grows toward its opener instead). The
type doctrine items from the Bierut review (tracking values, weights, which
family the pills use) and the docking contract at 280 (B11). The recipe
vocabulary ruling. Joe's golden HIP. The verb rail's return in any form.

## Standing RC blockers — waiver carried

The four standing RC blockers from v5.62.0 (`mutation_fail_closed`,
`hot_reload_gated`, `installer_host_targeted`, `ci_covers_shipping_surface`)
are unchanged by this release; Joe's release word ("once you commit then git
push then git release and bump version", 2026-09-05) carries the waiver forward.
