# SYNAPSE — Battle Plan · Panel Design Only · 2026-09-03

Grounded Thu 2026-09-03 against the LIVE repo: origin/master `26af4c68`, **v5.61.0** Latest (tag `ad589fe5`),
BP2 + BP3 merged. Panel commits since v5.58.0: `d9b0c06` PANELTRUTH (profile-diff receipt, TOKEN refresh on
completion, docked-open float fix) · `3371ba6` PANELDESIGN (4-pt grid + density gap multiplier on the *reachable*
regions) · `1276fed` BP3-PANEL (audit + qss token substitutions, byte-identical). 239 lines in 5 files.
Also read: `docs/PANEL_RHYTHM_SPEC.md` (v1, its §5 honesty ledger), `runs/2026-09-01/profile_diff.json`,
`docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md`, `compositor.py` (density stamp + `_repolish_tree`),
`designsystem/{tokens,qss,fontload}.py`, `harness/notes/panel_shot.py`.

**Scope: the Python panel's design. Nothing else.** No memory, harness, MCP, corpus, or World Labs work rides this
plan. Supersedes the 09-01 plan's panel sections only; everything else there is already merged or parked.
**Executes as** wave **PD** in `harness/battleplan/` (own bus, worktrees `pd-*`). Fable 5 referees, Opus 4.8 builds,
Haiku sweeps. Demo window: **Sep 13** (takes carry). Fri's 2 h panel timebox is the camera-regions ship point.

---

## 0 · The finding — the design system reaches about a tenth of the rhythm

| Owner of spacing / style in `python/synapse/panel/` | Count | Reach of `designsystem/` |
|---|---|---|
| `QLayout.setSpacing` / `setContentsMargins` (imperative gaps + paddings) | **108** in 12 files — `synapse_panel.py` 23 · `chat_panel.py` 16 · `face_review.py` 13 · `gate_widget.py` 12 · `hda_views.py` 9 · `face_token.py` 7 · `context_bar.py` 7 · `quick_actions.py` 4 · `face_work.py` 4 · `tool_palette.py` 3 · `command_palette.py` 3 · `working_indicator.py` 2 | none — QSS cannot set layout spacing |
| inline `setStyleSheet(` | **106** in 14 files | none — each one overrides the sheet |
| hardcoded hex outside `designsystem/` | ~60 distinct, concentrated in `vex_tutor` 13 · `apex_trace` 10 · `apex_explainer` 10 · `scene_doctor` 6 · `performance_profiler` 6 · `network_trace` 6 · `cross_scene` 6 · `message_formatter` 5 | none |
| widgets with a `Ds*` objectName (QSS-addressable) | **24** | the whole reach |
| density-keyed QSS rules landed 09-01 | **3** (`#DsTabRow`, `#DsVerb`, `#DsHeader` margins) | this is what "the panel breathes" meant |
| legacy `panel/tokens.py` + `panel/styles.py` | still present | second token system, un-retired |

`profile_diff.json` proves the profiles differ by **density + overlay + three meter folds** and nothing else. So the
profiles *are* a rhythm story — and rhythm has ~215 owners, three of which listen to density. That is why Curious,
Expert and ML still look like one panel in three tints, and why the Cohere references don't land: the references
are systems of spacing, and here spacing is not a system yet.

The H22 design review's verdict stands underneath all of it: the interaction model is good; the panel doesn't read
as native, is hostile to docking, and ships a dead affordance. Rhythm is how a guest reads as native.

---

## 1 · First principles → calls (override by number)

1. **One owner of rhythm.** Every gap, padding, radius, hairline, type role and colour resolves from `designsystem/`.
   Two levers, one property: a `rhythm_role` Qt dynamic property that **QSS** keys on (`[rhythm_role="label"]`) and
   that a new **`designsystem/rhythm.py`** walks to set the layout spacing QSS cannot (`QLayout.setSpacing`,
   `setContentsMargins`) at compose and on every recompose. Same tokens, same density, two appliers.
2. **Reach before rhythm.** A census runs first and the census is the accept: imperative spacing → 0, inline styles →
   0, foreign hex → 0 on the camera path; a stated residual elsewhere, each site tagged `# rhythm-exempt: <why>`.
   A guard test makes the count monotonic — it fails on any new untagged site. Zero tokens at runtime.
3. **Native, not branded.** The Cohere lesson is structural: floating tracked labels, hairlines between groups, rows
   that don't touch, three-band cards, grid-aligned parm rows, one accent doing the pointing. Zero new colours, zero
   new families (bundled Space Grotesk stays; sizes floor at the host), zero new hex. The 4-pt ladder already in
   `tokens.py` (`SPACE_GRID`, `gap()`, `ROW_MIN_H`, `RADIUS_CARD/ROUND`) is the vocabulary; this plan spends it.
4. **Three rhythms, one panel.** No new folds, no new profile knobs. Density (airy ×1.5 / standard ×1 / tight ×0.75,
   gaps only) becomes reachable everywhere → the three profiles become visibly three. Expert stays structurally
   pinned (`test_expert_resolved_equals_v5420_snapshot`).
5. **Docking is a rhythm constraint.** Airy must not push the minimum width past `docking-minimums.yaml`; every
   region is tested at 380 px width in all three densities. A gap that breaks docking is a gap that's wrong.
6. **One greenfield widget, named.** The recall card (the beat's display: three bands, footer pill from the
   contract's STATUS set `HIT / NO HIT / UNAVAILABLE / BLOCKED`). It displays an existing result; it is not a
   capability. If you read it as a feature under this week's "no new features" rule, cut it by this number.
7. **Eyes sign off.** Headless proves the numbers; `panel_shot.py` produces the before/after PNG pair per profile;
   your eyes on .400 are the red gate for the five camera regions. Ship at Friday's timer whatever the sweep's state.

**Done =** every gap/padding/radius/hairline/type role/colour in the shipped panel resolves from `designsystem/`
(camera path 0 / 0 / 0; panel-wide residual ≤ 20 tagged sites, guarded), and a before/after screenshot pair per
profile shows three visibly different rhythms with Expert structurally unchanged.

---

## 2 · The wave — one graph, five legs, one referee

```
   PD-CENSUS ──► PD-LEVER ──┬──► PD-CAMERA   (synapse_panel · face_token · recall card · shelf)  ── Joe's eyes (red)
   probe · 12t   design-   │    45t · Opus
                 system    ├──► PD-SWEEP-A   (chat_panel · face_review · gate_widget · context_bar · face_work · quick_actions)
                 40t·Opus  │    40t · Opus
                           └──► PD-SWEEP-B   (hda_views · palettes · working_indicator · the 8 hex modules · legacy token pair)
                                25t · Haiku
                                       └──────────► PD-CRUX (referee, read-only, 20t) ──► merge words
```

Edges are bus messages. CAMERA, SWEEP-A and SWEEP-B are parallel-safe by construction — their `touches` lists are
disjoint files; `synapse_panel.py` belongs to CAMERA only. A leg with an unmet dep sleeps until the receipt posts.
Caps: turns as written; tokens from the BP2 ledgers (`runs/2026-09-01/ledger_*.json` — measured since METERLIVE):
set each leg to 1.5× the closest BP2 leg (PANELDESIGN for LEVER/CAMERA, NITS for SWEEP-B). ≤ 182 turns for the wave.

---

## 3 · Leg briefs

Common: read `harness/AGENT_CONSTITUTION.md`. Bus `claim` before edit; `progress` every 5 turns citing a target;
commit before receipt; one bounded repair then `block`. No contract flips. No new hex, no new font family, no new
widget except the one named in §1-6. `pytest -q` green and the Expert pin green are preconditions for every receipt.

### PD-CENSUS · TRUTH · probe · mechanical tier · cap 12
- T1 `harness/notes/panel_rhythm_census.py` (pure Python, AST + regex): per file — `setSpacing`/`setContentsMargins`
  sites with values, inline `setStyleSheet` sites, foreign hex, objectNames present; per camera region — reachability
  (named? styled inline? layout-owned?). Emits `harness/battleplan/runs/<date>/rhythm_census.json` + a markdown table.
- T2 `docs/PANEL_REGION_MAP.md`: every visible region → widget ids → file:line of its spacing owners → target role.
  Camera regions first: profile tab strip · verb rail · chat transcript · recall result · TOKEN face · header/ribbon.
- Accept: census JSON with the totals above reproduced (108 / 106 / ~60 / 24 — a mismatch is a finding, not a fail);
  region map lists all six camera regions with owners.
- Crucible: the script reads source only; no `hou`, no Qt; runs in stock CI.

### PD-LEVER · BUILD · `designsystem/` + `compositor.py` + `tests/` · reasoning tier · cap 40 · amber
- Session A — `/design` spec → `docs/PANEL_RHYTHM_SPEC.md` **v2**: the role table (§4 below) with px per density, the
  five component patterns, the region map from CENSUS, the docking bound. ADAPT: confirm `/design` syntax with
  `/help`; absent, author by hand from §4 — same output, same accept.
- Session B — build:
  - `designsystem/rhythm.py`: `ROLE_GAPS` (role → base px from `SPACE_GRID`), `apply(root, density)` walks widgets
    carrying `rhythm_role`, sets `layout().setSpacing(gap(base, density))` and fixed `setContentsMargins` per role;
    idempotent; unknown role → standard, logged once.
  - `compositor.py`: call `rhythm.apply` after `_repolish_tree` at compose and in the recompose path — one property,
    two appliers, one call site each.
  - `qss.py`: generic role rules — `[rhythm_role="label"]` (mono, upper, tracked, muted, 24 above / 12 below),
    `[rhythm_role="tag"]` (mono, upper, neutral surface, 6/10), `[rhythm_role="row"]` (min-h 44, radius 8, hairline,
    glyph cell), `#DsCard` bands (40 / pad 16 / 40, hairlines), `[rhythm_role="parm_row"]` (label 128 · value 64 ·
    control fills · row 24). Density blocks carry **margin only** (the existing `test_rope_density` rule).
  - `tests/test_panel_rhythm_owner.py` — the guard: fails on any `setStyleSheet(`, `setSpacing(`, `setContentsMargins(`
    or 6-digit hex in `panel/` outside `designsystem/` that lacks a `# rhythm-exempt:` tag on the same line; the
    allowed residual is a checked-in number that may only go down.
  - `tests/test_panel_rhythm_docking.py` — every region at 380 px in airy/standard/tight ≥ `docking-minimums.yaml`.
- Accept: `rhythm.apply` changes layout spacing per role per density (headless test, negative control: role removed →
  spacing unchanged); guard test green at the current residual; docking test green; Expert pin green; zero new hex.
- Crucible: `fontload.py` untouched; no density-keyed rule carries colour/font/size/radius/border; standard emits no
  density block (the pin is manifest-only and must stay so); `compositor.py` diff ≤ 20 lines.

### PD-CAMERA · BUILD · `synapse_panel.py` · `face_token.py` · `token_readout.py` · `synapse_shelf.py` · reasoning tier · cap 45 · amber → red sign-off
- T1 Profile tab strip → `rhythm_role="row"` pills, active in `SIGNAL`; zero the compounding `setSpacing(28)`.
- T2 Verb rail → label-style, hairline under the group (`DsDivider`), gap via role; zero `setSpacing(24)`.
- T3 Chat transcript (`chat_display.py` is token-clean: 4 inline attrs, 0 hex) → reply leading +0.75 pt (W5L-PANEL
  T2, still binding), section labels for turn headers, message gap by role; the biggest surface on camera.
- T4 **Recall card** (§1-6): three bands from `#DsCard`; header = "what I remember"; body = the deposit; footer =
  text action left, status pill right from `STATUS ∈ SUCCESS|UNAVAILABLE|BLOCKED` + `payload.hit` → `HIT / NO HIT /
  UNAVAILABLE / BLOCKED`; `HOT_SOFT` only for BLOCKED; UNKNOWN as text. Built from tokens; no new colour.
- T5 TOKEN face → parm rows with objectNames (`rhythm_role="parm_row"`); zero `setSpacing(18)`; UNKNOWN as text in the
  value column, never a bar at zero (already the rule — keep it).
- T6 Header/ribbon → one row, label style; the `?` glyph opens docs (08-04 decision) — the shelf's docked-open path is
  already landed; do not touch it.
- Accept: census for these files → 0 / 0 / 0; `panel_shot.py` before/after PNGs per profile committed under
  `design/rhythm_pd/{before,after}/`; docking test green at 380 px; Expert pin green; **GUI sign-off red — Joe, .400,
  Fri timebox**.
- Crucible: lifecycle/timer lines in `synapse_panel.py` untouched (W5L-LIFE); no `hou.*` in worker; `face_token`
  refresh-on-completion path (09-01) unchanged.

### PD-SWEEP-A · BUILD · `chat_panel.py` · `face_review.py` · `gate_widget.py` · `context_bar.py` · `face_work.py` · `quick_actions.py` · reasoning tier · cap 40
- Per file, in that order: every `setSpacing`/`setContentsMargins` → a role on the owning widget; every inline
  `setStyleSheet` → objectName or role + QSS rule in `qss.py` (append-only, grouped by file with a comment header);
  nothing changes structurally.
- Accept: census for these six files → 0 / 0 / 0; `panel_shot.py` diff shows rhythm-only change; Expert pin green.
- Crucible: a migrated widget whose look changed beyond gap/label/tag treatment is BROKEN (compare PNGs).

### PD-SWEEP-B · BUILD · mechanical tier (Haiku) · cap 25
- `hda_views.py` · `tool_palette.py` · `command_palette.py` · `working_indicator.py`: same migration as SWEEP-A.
- The eight hex modules (`vex_tutor` · `apex_trace` · `apex_explainer` · `scene_doctor` · `performance_profiler` ·
  `network_trace` · `cross_scene` · `message_formatter`): each hex → the nearest existing token by role (ink, muted,
  surface, signal, warm, hot) — a lookup table checked in beside the diff so CRUX can audit the mapping; no new tokens.
- Legacy pair: `python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel`; if only
  `styles.py` imports it and nothing imports `styles.py`, delete both; else post a `finding` and leave them.
- Accept: census → 0 for these files; mapping table exists; `pytest -q` green.
- Crucible: any hex not in the mapping table is BROKEN; any token added is BROKEN.

### PD-CRUX · TRUST · referee tier (`claude-fable-5`, else reasoning) · read-only · cap 20
Re-run every accept in a fresh checkout. Mutations, each must turn a test red: remove `rhythm.apply` from the
recompose path · set `density` to an unknown value · re-add one untagged `setStyleSheet` · add one hex · widen airy
until 380 px docking fails. Verdict per leg `SOUND | SOUND-WITH-NITS | BROKEN` with `chain_broken_at`. BROKEN does
not ride. Verdicts are read before merge words fire.

---

## 4 · The role table — what "Cohere rhythm" means in tokens

Derived from the attached references (endpoint list, model cards, the parameter panel) and the Pentagram case text —
hardworking assets at small scale, mono for tags and notes as contrast, one accent. **Rules, not pixels to copy.**

| Role | Base gap | Padding (fixed) | Type | Notes |
|---|---|---|---|---|
| `label` (section) | 24 above · 12 below | — | mono · upper · +0.08 em · body size · muted | hairline under the **group**, never on the label |
| `row` (list item) | 12 between rows | 12 / 16 | body size, normal weight | min-h 44 · radius 8 · hairline border · 44×44 glyph cell with hairline right · optional trailing `tag` |
| `tag` / pill | 16 from label | 6 / 10 | mono · upper · +0.06 em · body size | neutral surface; colour only for BLOCKED (`HOT_SOFT`) |
| `card` (three bands) | 16 between cards | header 40 · body 16 · footer 40 | body | hairlines between bands · radius 10 · footer = one text action left, one pill right |
| `parm_row` | 4 between rows · 16 between groups · 32 section head | — | body | columns label 128 · value 64 · control fills; row 24 |
| `group` (any region) | 16 | — | — | the gap density scales |

Density: **gaps ×1.5 / ×1 / ×0.75; paddings, radii, hairlines, type fixed.** Label/tag type is body size (landing r3, RULING-4e: the type-floor gate made the former 0.72×/0.68× ratios unreachable; contrast by case, tracking, colour). Curious airy · Expert standard · ML tight.
Accent: `SIGNAL` family only (active tab, SEND, hero); `WARM` for the human; `HOT_SOFT` for BLOCKED/stop. No other colour points.
Type: families from `fontload.py` (bundled Space Grotesk; host family on fallback); sizes floor at the host default; mono = labels/tags/ids; sans = body.

Camera regions, in the order they're seen: profile tab strip → header/ribbon → chat transcript → verb rail → recall card → TOKEN face.

---

## 5 · The days

| Day | Work | Done = |
|---|---|---|
| Thu 9/3 | CENSUS (1 h) → LEVER armed. Commit `PANEL_RHYTHM_SPEC.md` v2. | census JSON + region map on the bus; LEVER receipt by end of day |
| Fri 9/4 | CRUX-lite on LEVER → merge word → arm CAMERA ∥ SWEEP-A ∥ SWEEP-B. **2 h timebox, your eyes on .400: the five camera regions in three profiles.** Ship at the timer. | CAMERA GUI-signed or its nits listed; merge word |
| Sat 9/5 | CRUX on the sweeps → merge words. `panel_shot.py` PNG pair per profile committed. Nits → `harness/notes/panel_nits_pd.md`. | census residual ≤ 20 tagged; guard test green |
| Sun 9/6 | Dry run includes the panel. Nothing new. | — |
| Mon–Fri 9/7–11 | Residual sweep only if the census says so; otherwise parked. Beta-W1 opens. | — |
| Sun 9/13 | Demo-ready predicate (takes ×2). | — |

If Friday's timebox ends with CAMERA unsigned: merge what's signed, list the rest as nits, the sweep continues
Saturday. The panel never blocks the takes; the takes never wait on the panel.

---

## 6 · Words and the operator's card

- [ ] ratify §1 calls (or override by number — 6 is the one to look at)
- [ ] Fri: LEVER merge word after CRUX-lite; arm the three parallel legs
- [ ] Fri 2 h timebox: GUI sign-off on the five regions × three profiles; merge word for CAMERA
- [ ] Sat: merge words for the sweeps after CRUX
- [ ] release only on your word, only if Sunday's dry run is clean: v5.62.0 — "the panel keeps one rhythm"
  (release ritual: bump → `_rr.ps1 --mode B` → triple-check → tag; the four RC blockers re-sign or fix)

```
python harness\notes\panel_rhythm_census.py                                  the number: sites the design system can't reach
python harness\battleplan\mission_schema.py missions\PD-*.json               validate the six missions
python harness\battleplan\compile_wave.py → make_control.py → manifest        in order, always
powershell -File harness\battleplan\arm_pd.ps1                               arm (copy of arm_bp1.ps1, wave id only)
python harness\battleplan\bus.py read pd --types finding,block,refocus        what the agents are saying
python harness\battleplan\status_pd.py                                       board
$env:QT_QPA_PLATFORM='offscreen'; $env:SYNAPSE_REDUCED_MOTION='1'
hython harness\notes\panel_shot.py --out design\rhythm_pd\before             PNG pair, before (run once on the untouched tree)
hython harness\notes\panel_shot.py --out design\rhythm_pd\after              PNG pair, after
pytest -q tests\test_panel_rhythm_owner.py tests\test_panel_rhythm_docking.py the guard + the docking bound
$env:SYNAPSE_GATE_C=1; git push origin master; Remove-Item Env:SYNAPSE_GATE_C  push (Gate C, yours)
```

Verify once before arming: `claude --model claude-fable-5 -p ok` · `/help` shows `/design` · `hython harness\notes\panel_shot.py --help` runs on the .417 lane (screenshots are a diff instrument, not a truth surface — truth is your eyes on .400).

---

## 7 · Not on the path

Host-scheme token seeding (`theme-seed-tokens` second half) · the ~18 dead/alt-entry panel modules (foundation, beta) ·
new folds or profile knobs · any new widget beyond the recall card · main-thread idle cost (design review 2.x, its own
contract) · memory, harness, MCP, corpus, World Labs — all untouched by this wave.

## 8 · Unknowns, stated

`/design` syntax (ADAPT) · Fable 5 alias in Claude Code (ADAPT) · whether every one of the 108 spacing sites maps to a
role without structural change (CENSUS answers; the ones that don't are the tagged residual) · whether the recall card
survives your "no new features" rule (call 6) · the exact px the host font floor gives on your rig (the shot pair shows it).
