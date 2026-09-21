# BP9 rulings, 2026-09-21

Source: Joe's reply to section 8 of `docs/reviews/synapse-improvement-scout-2026-09-21.md`: "1. yes 2. recommend best option 3. yes 4. use recommended 5. use recommended". Where he asked for the recommendation, the CTO seat's recommendation and its reason are recorded here and treated as the ruling.

| # | Question | Ruling | Reason (where recommended) |
|---|---|---|---|
| 1 | May the panel pick a cheaper or local model per turn? | **YES.** A third routing mode `auto_per_turn`, downgrade-only, local first, inside the permission already granted, shadow-first, armed only after the usage ledger holds at least 100 keyed rows and the shadow agreement is measured. | Joe's word. |
| 2 | Does rails gain a `none` tier so probe legs run inside the orchestrator? | **YES, add `none`.** A `none` tier launches no model: the orchestrator runs the leg's probe command directly (hython or python), captures stdout to the receipt, and the SCREEN/EDGE guards read it like any receipt. | Recommended: it unblocks typed edges and the PROBE → FIX → REPROBE loop, and it is the only way "isolated green hides composed regressions, always on the second action" (memory solaris-harden) gets a re-probe inside the same wave. The alternative (probe legs outside the orchestrator) keeps the loop manual forever. |
| 3 | Retire the legacy surface? | **YES**, in two steps. Step A now: delete `chat_panel.py`, `quick_actions.py`, `synapse_chat.pypanel` and the `route_chat` WS command, with a test that exactly one pypanel is installable. Step B after the code-first prefilter lands in the panel send path: remove Tier 2/3 of `TieredRouter` and their env-key reads. | Joe's word on retirement; the two-step order is the seat's: Tier 2/3 carry the BP8-TIMEOUTS tests shipped in v5.77.0, and deleting them before the prefilter exists throws away tested code for nothing. |
| 4 | Should Stop hard-block on an unresolved Houdini cook error, and does a `codebase-transition` skill get written? | **YES to both.** Stop and TaskCompleted exit 2 on an unresolved CookError (an `unresolved` set replaces the consume-on-prompt watermark). The `codebase-transition` skill gets written under `~/.claude/skills/` from the protocol the global CLAUDE.md already describes (startup-cost ramp, handoff formatting, transition-moment beat, post-handoff silence). | Recommended: a gate that only prints to stderr is not a gate (memory gate-width-failure-class), and CLAUDE.md names the skill on nine lines while the loader finds nothing. |
| 5 | Which basis does the 70M wave cap mean? | **Cost-weighted**: input x1, cache create x1.25, cache read x0.1, output x5 (or the current price table), enforced by `rails.py`; the ledger row shows all four raw fields, the rails total and the cost-weighted total, plus `max_ctx` per leg. | Recommended: BP8's 79.8M was 93 to 97 percent cache reads and halted TIDY on a metering artefact; cost-weighted it was about 12M. A per-leg context ceiling is recorded, not enforced, until the DRIFT guard is live. |

Merge of the BP9 branches stays a separate human act (harness/CLAUDE.md: promotion to main is human). Nothing here arms a merge.

## Correction after BP9-CAPBASIS (2026-09-21)

The report and ruling 5 said BP8 was "about 12M" cost-weighted. That estimate ignored output at x5. The builder and the crucible independently recomputed from the three BP8 transcripts under the ruled weights: input 4,354 + cache create 3,562,469 x 1.25 + cache read 74,611,466 x 0.1 + output 1,639,912 x 5 = **20,118,147** cost-weighted (rails total 79.8M unchanged), max context 373,507. The weights stand as ruled; the number in the report is corrected here. The 70M cap on the cost-weighted basis would still not have halted TIDY. Pinned by `tests/test_cap_cost_basis.py`.

## Panel typography and Commands rulings (2026-09-21)

Source: Joe's word "implement the spec (docs/design/PANEL_TYPE_AND_COMMANDS_2026-09-21.md)". The spec's section 5 recommendations are treated as ruled as recommended. Recorded here because the round-3 items (R3-*) have no RULINGS-OPEN roster for `scripts/ingest_rulings.py`; the round-2 items (R2-A1, R2-B1) are also landed through that script.

| Group | Ruling | Ruled |
|---|---|---|
| 1 ramp | R2-A1 | ratify: airy is a spec, not a target |
| 1 ramp | R3-A | YES: retire 11 px; SIZE_SMALL/SIZE_LABEL alias SIZE_BODY; ramp 12/15/19; `test_type_scale_native.py:29` floor 4 -> 3 by declaration |
| 1 ramp | R3-B | quiet = caps + tracking in sans 500 at body size; mono is data; 700 only at 15/19 |
| 2 transcript | R3-D | YES: untracked sans body, mono for code/paths, `_MEASURE_CHARS` 90 -> 66 |
| 2 transcript | R3-E | YES: transcript-own gap keys 24/8, re-measured offscreen |
| 3 floor | R3-C | YES as an offscreen assertion min-chrome-px >= host-px; coupled to R3-A; FONT_FLOOR_PX stays 11 |
| 4 Commands | R2-misc | rename overflow "Palette" -> "Commands"; delete no hidden widget; "Connect" -> "Bridge" stays unruled |
| 4 Commands | NEW list | order PANEL / ASK / RECIPES / TOOLS / PRESETS; 20 raw slash rows dropped or rewritten; ASK verbs get empty-scene prompts |
| 5 accent | R2-B1 | drop the Doctor yellow; Doctor takes the shipped SIGNAL action family |

Build: legs L1-L6 of the spec (L3 split into L3a/L3b), each in its own worktree, Jev-routed, crucible-verified under hython offscreen; composed gate on the integrated branch before any merge to master. Merge to master stays a separate human act.

## Release-cut rulings, 2026-09-21 (v5.79.0)

| id | call | ruling | limit |
|---|---|---|---|
| REL-BP10 | A concurrent BP10 orchestrator committed its harvest scaffold straight to master mid-cut. Release onto it, or onto the v5.78.0 tag? | **Joe: "merge is pre-approved... BP10 is pre-approved."** Release onto master as it stands. | Covers the two named shas 5ab7ee9d + 357bf1e7 only. A later unverified commit from another wave still stops a cut. Does not excuse a red gate. |
| REL-WAIVE | Every finished panel leg reported `merge_ready=false`, so the composed gate would have refused all of them. | **Waive, mechanically and narrowly.** A leg merges despite that flag when its verdict is not BROKEN and *every* acceptance line it failed matches one of the two gates proven dead (`audit_panel.py --strict exits 0`, `hytest test_bc_wave.py exits 0`). Encoded as `DEAD_GATES` in `compose_panel_gate.py`; any other failure still refuses the leaf. | Not a judgement call per leg. A new failure does not match the patterns and stops the merge. `panel_gate.py` is the replacement arbiter, and it ran green on the trial integration. |
| REL-JEV-CI | BP10 added `harness/jev/tests` to pyproject `testpaths` and to a CI step, but the composed gate only ran `pytest tests/`. | **Add it as a gate row.** CI would otherwise have been the first thing to run that suite -- after the tag was cut. | 55 passed locally at 357bf1e7. Both prior releases needed a tag re-cut; this closes one way that happens again. |

### Why the verifiers all said no

Three independent verifiers set `merge_ready=false` while writing in their notes that
the leg was clean. PNL-L3A put it plainest: *"Strict reading of the merge rule: acceptance
line 4 did not pass in my own rerun, so merge_ready is false by the letter. Substantively
the leg is clean: I reproduced that same 2-failed/11-passed at master in an independent
worktree, so the red is pre-existing."* Each of them also ran the full stock suite green
at 9701/0. The verifiers were right and the gate was wrong; the fix belongs in the gate.

### What the rehearsal caught

Running the composed gate on a trial integration of L2 + L3A, before the graph finished,
found three things a release-day run would have hit cold:

1. **A merge conflict with one correct answer.** Both legs deleted their own row from the
   audit baseline. Resolved as the intersection -- a row survives only if both sides kept
   it -- so a ratchet baseline can only shrink. A side *adding* a row still stops for a human.
2. **A fourth dead gate, this one inverted.** `panel_gate.py` matched only
   `G3 RESULT: <n> FAIL` and the audit prints `G3 RESULT: pass` when nothing fails, so a
   fully green audit parsed as a crash. Fixed in PNL-L0c. A gate that cannot recognise
   success is as dead as one that cannot pass.
3. **The instruments had to be merged first.** `pnl/gate-fix` is now merged ahead of any
   leaf, so the gate judging the integration is the current one rather than whatever
   version a leaf inherited when it branched.

## OPEN — needs Joe's word (raised 2026-09-21 by PNL-L4)

| id | the ruling as written | what the code says | what shipped |
|---|---|---|---|
| R3-B-CAPS | "quiet = caps + tracking in sans 500 at body size" | `caption` is not the tiny-label role the ruling describes. It is handed whole SENTENCES at about twenty call sites: the connection dialog's consent copy ("The check sends credentials and asks for model metadata only..."), project_rules ("Allowed background requests may send prompts, conversation, scene context..."), notifications, saved_recipes, and tool_palette's empty state. | The MECHANISM, wired and tested: `tokens.ROLE_CAPS`, read by `components.apply_font_role`, verified live to reach `QFont.Capitalization.AllUppercase` when armed. The SET ships **empty**, and the code says why. |

**Why it was not just done.** Upper-casing a paragraph is the opposite of the
readability this leg exists for, and doing it silently under a ruling written for
chips would have been the wrong kind of obedience. The leg measured first and
declared the gap instead of half-applying it.

**Three ways to close it, your call:**

1. **Split the role.** `caption` becomes a metadata chip (caps, tracking) and a
   separate prose role for explanatory sentences. Most faithful to R3-B, most work.
2. **Narrow the ruling.** R3-B applies to the chip voice only; prose captions stay
   sentence case. Then `ROLE_CAPS` gains the chip role and nothing else.
3. **Apply as written.** Add `"caption"` to `ROLE_CAPS` — a one-word change — and
   accept ALL CAPS consent copy in the connection dialog.

The tracking half of R3-B is already applied: both `caption` and `status` derive
tracking from `TRACKING_EM` at their own size, so a tracking change now has one
owner instead of two hand-picked values.

### Second open question (raised 2026-09-21 by PNL-L5)

| id | the brief as written | what the geometry says | what shipped |
|---|---|---|---|
| L5-CPL-BAND | the measurement probe must print four characters-per-line corners, all inside 45-75 | At the narrowest dock the lower bound is **unreachable, not merely unmet**. The transcript column IS the 340px dock, and the probe measures 7.7px per character at Aa 1.00, so 45 characters need 346px -- wider than the dock itself -- and 572px at Aa 1.60. | A sound probe. It measures rendered QTextLines, exits 0, reds at 90, and reports both narrow corners as PANE-LIMITED by name rather than pretending they pass. Measured corners: 44.4 and 26.9 cpl at 340px; 59.2 and 60.5 at 1100px. |

**Three ways to close it, your call:**

1. **Floor the band by width.** 45-75 applies only above some dock width; below it the
   probe asserts PANE-LIMITED and nothing else. Keeps the band honest where it can hold.
2. **Drop the lower bound for a pane-limited column.** The upper bound still bites at 90.
3. **Change the panel, not the band.** A 340px dock cannot show 45 characters at this size;
   only a smaller type size or a wider minimum dock would, and both are larger decisions.

The two wide corners already sit inside the band, so this is a question about narrow docks
only. Nothing in the probe was weakened to get here -- the verifier reproduced every number
under hython within rounding.

