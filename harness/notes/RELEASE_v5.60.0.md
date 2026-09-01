# v5.60.0 — the panel breathes and the harness pays its own bill

Draft release notes. **Draft only — not published, no tag cut.** Publish is
gated on the release ritual (R.R verify) and Joe's re-signed waiver for the
four standing RC blockers. Every claim is receipt-backed on master (HEAD at
draft time `a87d2f9c`). Where a claim needs eyes on a live Houdini it says
UNKNOWN, not green.

Scope: wave **BP2 closing legs** — HEALTHWIRE, METERLIVE, PANELDESIGN and
their crucible (CRUXB), all **SOUND-WITH-NITS**, chain intact, merged
zero-conflict on an integrated tree at **6928 passed / 186 skipped / 0 failed**.
One leg (NITS) was ruled **BROKEN** by the crucible and does not ride; its
targets return in a fresh session.

## For artists

**The health row tells you what you're actually talking to.** The panel's
operator health row now carries requested backend, active backend, embedder
id, embedding dimension and a ratified verdict — SUCCESS, UNAVAILABLE or
BLOCKED — alongside the words it already used. Asked for Moneta and served
JSONL now reads UNAVAILABLE where you can see it. The live-strip half is
UNKNOWN until eyes on 22.0.400.

**The panel has rhythm.** The Cohere-reference spacing pass lands on the five
camera regions — profile tab strip, verb rail, recall card, TOKEN face,
`.hip` ribbon — as spacing tokens and QSS keyed on the existing density
property. Curious gets the airy multiplier; Expert reads the same tokens at
×1 and its structural pin stays green. Zero new colours, widgets or font
families. Two disclosed test gaps (fixed paddings and a non-density font are
not yet pinned). GUI sign-off on the five regions is UNKNOWN until your eyes.

## Under the hood

**The harness pays its own bill, proven live.** A scratch orchestrator run
dispatched a leg, saw it reach `done`, settled its real transcript into the
rails ledger as integers, crossed a one-token ceiling at settle and refused
the next dispatch. First orchestrator-measured leg: 75,356 in / 278 out on a
trivial Haiku task; a real Opus leg measured 21.5 M in / 275 k out. A leg
hard-reaped before its transcript flushes settles as UNKNOWN, never a fake
zero.

**The close gate reads the right bus.** Battleplan legs post releases to the
battleplan bus; the gate was reading the autorevise bus, so no battleplan leg
had ever reached `done` and the settle never fired on a live wave. Fixed by
resolving the bus per harness family. Effective on the next armed wave.

**Leg permissions match the work.** The relay profile now allows the commands
legs actually run (git in all forms, PowerShell, `gh` read verbs); the deny
list holds and grows (tags, force pushes, master checkout, all `gh release`
writes). Master pushes remain refused by the Gate C hook regardless. Legs stay
out of auto mode: the classifier blocked a harness proof artifact's `git add`
as if it were exfiltration.

**Drift check skips closed legs.** A finished leg cannot answer a refocus.

## Known and disclosed

- NITS (BROKEN): the regenerated METER dry-run proof still compared a file
  with itself, and the `MONETA_FOLLOWUPS.md` flip cited test names that do
  not exist. Returns as a reasoning-tier leg.
- CXB-F3: rails may double-count usage rows within one API response
  (over-counts, never under). Held as a METER-DEDUPE spawn.
- Three `gui_required` rows remain UNKNOWN pending Joe's eyes on 22.0.400.

## Standing RC blockers (waiver re-signed per release)

`mutation_fail_closed · hot_reload_gated · installer_host_targeted ·
ci_covers_shipping_surface` — unchanged since v5.51; published-over under
Joe's waiver at v5.56.0, v5.58.0 and v5.59.0. This release publishes only if
that waiver is re-signed by Joe's word.
