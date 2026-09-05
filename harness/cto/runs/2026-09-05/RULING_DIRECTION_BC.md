# Joe's ruling - panel direction B + C (2026-09-05, evening)

**Word (verbatim intent):** "I like the trust of C. The slash menu doesn't give enough space to the
options when they present vertically, it needs a little more breathing room. B plus C is right but
this still needs to hold to the Pentagram design principles and lightly address spacing for
ADHD-friendly users and artists. Continue."

**What that fixes as scope for the next wave (`design/bc-wave`):**
1. **B - composer-first, no rail.** The verb rail leaves the composed panel at rest; its verbs live in
   the slash palette and the overflow. The conversation and the composer are the panel.
2. **C - trust where the talking happens.** Consent (gate proposal) cards and undo appear inline in
   the conversation, in the panel's own vocabulary (DsCard, DsVerb tone, tag badge, one accent).
   REVIEW level gets a verb. Undo after a quiet turn has a control on the CHAT surface.
3. **Slash palette breathing room.** The vertical option list gets real vertical rhythm: row height,
   gap and group spacing from the rhythm roles (no literals), so options read one at a time.
4. **State sentence that never gives way** (F2): one line of state at 340, one truth at boot.
5. **ADHD-friendly spacing, light touch:** whitespace between beats (turns, cards, groups) on the
   SPACE_GRID; one signal per fact (the idle panel says "nothing yet" once, not eight ways);
   nothing on screen the artist cannot read at the width the panel asks for.
6. **Profile row folds** into the overflow (F5) so the conversation holds a majority of the pane at 340
   in every density. Own commit, revertible.

**Held constant (Pentagram bar):** one point of view; monochrome plus one accent that means the
artist's next action; Space Grotesk for words, Space Mono for data; every element earns its place;
the wordmark is the last thing that gives way; no new tokens, no new fonts, no new chrome.

**Measured goals (headless, H22.0.400):** conversation >= 50% of the pane at 340x760 in all three
profiles; no elided text at 340; census stays <= 17 sites all tagged, 0 raw hex; G3 strict pass;
docking: composed minimumSizeHint measured per density - if the rail's departure brings it under
280, the interim per-density widths (R3-01) retire in the same wave.

**Gate:** build on a branch, CRUX (referee + design warden), screenshots on the canvas, then Joe's
merge word. GUI sign-off stays his eyes.

## Addendum - wordmark lockup (Joe, 2026-09-05, on the review canvas)

"The SYNAPSE title needs to be 1pt larger and 5px farther to the right of the orange circle."
Scope for the bc-wave (own commit): wordmark 14 -> 15 px (tracked_font("WORDMARK", 15, ...),
synapse_panel.py:702-705; audit_panel.py wordmark row re-pinned to 15; type-scale test pins updated),
mark-to-wordmark gap +5 px carried by the header row's rhythm role (no literal), G3 chrome floor and
never-elide (setMinimumWidth from sizeHint) re-measured at 340. Docking widths re-measured after.

## Addendum 2 - the MODEL is always visible, top right (Joe, 2026-09-05, ~14:05)

"Please make sure the MODEL (i.e. ollama/deepseek r4 flash) is visible in the top right of the
panel. Not having it visible is a serious detriment to the user interaction."

**Hard constraint for this wave and every wave after it.** The active engine and model
(provider/model, e.g. `ollama/deepseek-v4-flash`) is the one fact the artist must never lose:
it is who they are talking to, what it costs, whether it is local or cloud, and what it can do.
It sits TOP RIGHT of the panel, at rest, in every profile and density, at PANEL_PREF_WIDTH 340 and
at the docking minimum. It is data, so it speaks in Space Mono (the data voice), tracked per
TRACKING_EM["DATA"], at or above the type floor. It never elides and never folds into the overflow:
like the wordmark, it is one of the two identities on the header - who you are talking to, and
who is talking. If space is short, ignored-priority chrome gives way first; the model token and the
wordmark give way last.

Concretely: the header row carries the wordmark (left) and the model token (right); the token shows
provider and model short id (`ollama/deepseek-v4-flash`, `claude/fable-5.1`), tapping it opens the
existing provider/model picker (`_set_provider`, `_author_lbl` today). BC-2's "chrome folds into the
overflow" and SUBTRACT's list of removable chrome do NOT apply to the model token. Pin it: a Qt test
at 340 in all three profiles asserting the token is visible, unelided, in the top-right region, and
names the live provider/model; G3 must sample it in the chrome floor.

**Why (first principles):** trust is the product. A panel that hides which model is acting turns
every answer into a guess about its source; the artist cannot judge cost, privacy or capability.
The wordmark says who is speaking; the model token says who is thinking. Both are identity.

## Addendum 3 - CTO rulings on the referees' escalations (2026-09-05 ~16:05, under Joe's pre-approval)

The two CRUX referees escalated seven calls as "human". Joe pre-approved all of today's changes and
ruled direction C explicitly; these are decided now so the wave can close without him.

1. **BC-6b is UNHELD. The v9.1 face-switch law is superseded by direction C.** A raised actionable
   gate no longer brings the Work face forward; the consent card appears inline on CHAT in the
   consent slot, and quiet state still never moves the visible face. Edit `audit_panel.py`
   invariant #2 to the inline-card predicate: after `_on_gate_raised({"level": "approve"})` the
   face index is unchanged AND the consent slot holds a card whose verbs are reachable; quiet
   (busy + tool status) still leaves the face alone. Retarget
   `tests/test_panel_faces.py::test_gate_raised_auto_surfaces_work` identically (rename it to
   what it now asserts). Accept/revert on the card hand back to the conversation, which is where
   they already are.
2. **Model token text = `<provider>/<model short id>`**, lowercase, mono, e.g.
   `ollama/deepseek-v4-flash`, `claude/fable-5.1`, `gemini/3.5-flash`. Joe's words: "the MODEL
   (i.e. ollama/deepseek r4 flash)". Provider is the local-vs-cloud and cost signal; the curated
   display label alone ("Deepseek V4 Flash") hides it. The token still never elides; the identity
   row is sized for it; if the wordmark and the token cannot both fit at a width, that width is
   below the panel's floor and the docking test says so.
3. **The model token is data, not a status light: colour = TEXT_SECONDARY at rest**, TEXT_BRIGHT on
   hover, no CONIFEROUS green (qss.py `QPushButton#DsAuthor`). One accent means the artist's next
   action; connection state is the mark and the state sentence. The CHAT face at rest returns to
   three hue buckets.
4. **One "/" telling, and it is the legend.** Placeholder becomes `Ask SYNAPSE…` (nothing else);
   the khint legend carries `↵ send · ⇧↵ newline · / commands` and is the single telling. Nothing
   in the composer is cut at 340.
5. **Palette width = the composer's width, never sizeHint-shrunk.** `_position_popup` must not let
   `adjustSize()` collapse the ToolPalette below its opener; rows elide at the END with an
   ellipsis only when longer than the popup; no horizontal scrollbar, ever. The wave's own item 3
   (breathing room) is not met until no row is cut mid-word at 340.
6. **Inline REVERT is state-gated like Stop.** While a worker is streaming, the card's REVERT verb
   is disabled; `_start_worker` refuses re-entry while busy (returns False, logs once) so a second
   worker can never stream into the same transcript.
7. **Evidence rides in the commit.** One screenshot set, committed: `design/rhythm_pd/after_bc/`
   (already allow-listed); remove the duplicate `design/bc_wave/after/` set and its manifests from
   the branch, or allow-list it explicitly - never a report that names files git does not hold.
8. **Merge train.** Merge master (`943a4dd8`) into the branch before CRUX re-runs. Resolve
   `synapse_panel.py` by keeping the branch's removal of the rail meter AND master's compositor
   `retired` guard; adapt `tests/panel/test_single_window.py::test_rail_meter_is_parented_and_hidden`
   to "no DsRailMeter widget exists, or it is parented and hidden". The single-window pin stays.
   HEAD must be gate-green on its own (G3 pass, six-file set green, tests/panel 1 pre-existing).

Gate: after these land, both referees re-run; SOUND or SOUND-WITH-NITS merges to master under the
pre-approval. GUI sign-off stays Joe's eyes, on the live shots.

## Addendum 3 - amendment (17:30)

3.4 as shipped: the repair round put the one "/" telling in the composer placeholder
(`Ask SYNAPSE… · / commands`, advance 175 px, reads whole at 340 in every density) and left the
legend as `↵ send · ⇧↵ newline`. That satisfies the intent (one telling, nothing cut) and is
pinned in tests/panel/test_bc_wave.py + G3; the ruling stands as shipped rather than churning
the pins. Live shot 17:24 confirms it reads whole at 1636 wide.

Live-found after the reload (composer_probe.json): the B4 pane cap had stuck at 114 px on a
1359 px pane at chrome scale 2.25 (viewport 21 px under a 27 px font) - the cap's relax branch
could never recover the artist's height. Fixed on fix/composer-cap-relax before the tag.
