# SYNAPSE panel design review - scaffold, 2026-09-05

Master `74dc0219` (Panel PD wave landed). Scaffold only: no judgement, no review.
Every artboard is a static Design Component (`<Name>.dc.html`, exact shell, no
`data-dc-script`), fonts via Google Fonts `<link>` (Space Grotesk, Space Mono,
IBM Plex Sans) with fallback stacks, icons as inline SVG, no emoji. Every value
is lifted from source and captioned with its `path:line`; measured values cite
the JSON this directory produced. `canvas.json` lays out row 1 (Main, Type,
Rhythm, Regions - 880x700, 80px gaps) and row 2 (Curious, Expert, ML - 720x800,
120px below). Nothing outside this directory was written.

## Main.dc.html - "SYNAPSE Panel Design System" cover

The organizing idea quoted verbatim ("Monochrome restraint + one intelligent
accent. Warmth through type and voice, not decoration.") and the Pentagram bar
as written; the wordmark set exactly as shipped (Space Grotesk, 14px,
`tracked_font("WORDMARK", 14, weight=600)` which `fontload.tracked_font`
resolves to `setBold(True)` = Qt weight 700 as measured, 0.16em tracking,
TEXT_BRIGHT); the canonical palette (SIGNAL, VOID, NEAR_BLACK, CARBON, GRAPHITE,
SLATE, SILVER, BONE, WHITE, FIRE, GROW, WARN, ERROR) as swatches with hex + role;
the seeded surface ramp and the contrast-solved text ramp at their headless
values (GROUND #1F1F1F ... HAIR #303030, TEXT_BRIGHT #DEDEDE ... TEXT_DISABLED
#636363, MUSHROOM, TEXT_ON_ACCENT); the interaction ramp, WARM, and the muted
verdict hues; and the accent rule (SIGNAL family only; WARM for the human;
HOT_SOFT for BLOCKED/stop; no other colour points).
Sources: `docs/design/SYNAPSE_PANEL_REDESIGN.md:4-5, 43`;
`python/synapse/panel/designsystem/tokens.py:29-44, 49-54, 113, 118-121,
123-158, 200-206, 225-231, 237-265, 275, 294-300, 396`;
`python/synapse/panel/synapse_panel.py:677, 702-705, 712`;
`python/synapse/panel/designsystem/fontload.py:28-29, 174-175`;
`python/synapse/panel/designsystem/qss.py:251`; `docs/PANEL_BATTLEPLAN_PD.md`
section 4 (Accent line); `regions_expert.json` (wordmark x=54, mark x=30).
Headless palette values were evaluated by importing `tokens.py` under the repo
`python/` path (the `_FALLBACK_RGB` seed, no host).

## Type.dc.html - the full type scale

Specimen rows for every `TYPE_ROLES` entry (display 19/600, title 15/600, body
12/400, label 12/500, code 12/400 mono, caption 11/400, status 11/500 mono) with
family, px, weight, tracking, case and where used; then the tracked chrome fonts
actually applied via `fontload.tracked_font` (WORDMARK 14/700/0.16em, LABEL
11/0.15em on CHAT/TOKEN, profile pills and verbs, SEND 11/500/0.08em, DATA
11/0.03em on author/meter/khint, DATA 10 on the composer legend, and the rhythm
`label` (+0.08em, borrowed from SEND) and `tag` (+0.06em = DATA x 2) eyebrow
type); the TRACKING_EM map; the two-labels doctrine (RULING-4d).
Sources: `tokens.py:294-300, 308-313, 339-346, 352-354, 356-373, 389-398,
401-404, 412-413, 510`; `fontload.py:158-190`; `rhythm.py:15-25, 55-71`;
`qss.py:121-130, 135-149, 161-166, 241-248, 251-254, 367-372, 388-399`;
`synapse_panel.py:702-705, 714, 724-725, 733-734, 743-744, 769, 1002,
1065-1066, 1078-1079, 1095-1100, 1797, 1892-1893, 1905-1907, 1944-1945,
1952-1954`; `docs/PANEL_RHYTHM_SPEC.md:167-172`; `docs/PANEL_BATTLEPLAN_PD.md`
section 4 (label / tag rows).

## Rhythm.dc.html - grid, roles, gutter, docking

SPACE_GRID (4, 8, 12, 16, 24, 32, 48) as bars at 5px/unit with SPACE_XL 40 shown
off-ladder; the radius set (4/8/10/12/14/999) and fixed dims; the roles table
(shell, stack, band, group, label, row, tag, card, parm_row -> base gap, the
airy/standard/tight values from `gap()`, fixed layout margins, min-height and
paint rule, and the widgets that carry each role); GUTTER 30 drawn as the grey
ends of the docking bars; docking widths PANEL_MIN_WIDTH 280 (the contract),
PANEL_PREF_WIDTH 340, the interim per-density bounds 380/380/400 from the YAML,
and the measured composed minimums 393/361/345 from the integration receipt;
PANEL_MIN_HEIGHT 420 vs the YAML's 400.
Sources: `tokens.py:469-500, 523-536, 544-545, 553, 572-575, 622-625`;
`rhythm.py:15-43`; `qss.py:295-309, 366-449`; `synapse_panel.py:494, 503, 675,
997, 1060, 1173, 1181`; `docs/PANEL_RHYTHM_SPEC.md:53, 105-123`;
`.synapse/contracts/docking-minimums.yaml` (RULING-2A / R3-01 comments and the
width feature line); `docs/panel_pd/INTEGRATION.md:159-169`.

## Regions.dc.html - the camera regions at 340x640

A labelled diagram of the panel at 340x640 with the five in-view camera regions
from `docs/PANEL_REGION_MAP.md` (profile tab strip, header/ribbon, chat
transcript, verb rail, recall card) plus the TOKEN face as a stacked face, and
the composer marked separately. Band positions come from the standard-density
measurement (`regions_expert.json`, 340x760: rail 0-84, ribbon 84-130, tab row
130-177, chat from y=185, verb rail 36 tall, composer 176 tall); the chat
transcript, the stretch region, is shortened by 120px to fit 640 and nothing
else moves. Each region card names its widget ids, role, and source lines.
Sources: `docs/PANEL_REGION_MAP.md:13-26, 28-54`; `docs/PANEL_BATTLEPLAN_PD.md`
section 4 (camera order line); `synapse_panel.py:498-532, 655-780, 992-1007,
1009, 1058-1104, 1108-1122, 1167-1187, 1883-1918, 1920-1957`; `qss.py:34,
37-40, 117-130, 161-176, 229-248, 296-309, 420-432`; `chat_display.py:456`;
`python/synapse/panel/recall_card.py` (exists on master; ABSENT in the 09-04
census); `face_token.py:337, 447-449`; `docs/PANEL_RHYTHM_SPEC.md:142-150`;
`regions_expert.json`.

## Curious.dc.html / Expert.dc.html / ML.dc.html - the landed panel

One artboard per profile: the direct chat face screenshot
`design/rhythm_pd/after_r3/<profile>/panel_direct_chat.png` (340x760 native,
re-saved through Pillow as `shot_<profile>.png`, 16.4-16.7 KB each, under the
70 KB cap) placed at native pixel size, with the file path and pixel size in
the caption. Beside it a column of measured facts: density, rail height, ribbon
height, tab row height, chat height, verb rail height (with each verb's width),
composer height, SEND geometry, wordmark x (and mark x), the wordmark's font
as resolved (family, pixel size 14, weight 700, letterSpacing 116%), and the
bundled-font load status. Measured live with hython 22.0.400 offscreen by
`measure_regions.py` in this directory (same construction path as
`harness/notes/panel_shot.py`: SynapsePanel + `qss.stylesheet()`, resize
340x760, show, processEvents, direct face current), one run per profile with
`SYNAPSE_PANEL_SETTINGS=settings_<profile>.json`, results in
`regions_<profile>.json`. Headline numbers: rail 100 / 84 / 76, ribbon 46 / 46
/ 46, tab row 47 / 47 / 47, composer 200 / 176 / 164, wordmark x 56 / 54 / 53
(curious / expert / ml).
Sources: the three PNGs and `manifest.json` under
`design/rhythm_pd/after_r3/<profile>/`; `harness/notes/panel_shot.py:185,
205-262`; `harness/panel_pd/runs/2026-09-05/shots_R3rep.txt`;
`measure_regions.py`; `regions_<profile>.json`; `qss.py:241-248`;
`synapse_panel.py:704-705`; `tokens.py:491`.

## Evidence files in this directory

`measure_regions.py` (the probe), `settings_<profile>.json` (its inputs),
`regions_<profile>.json` (its outputs), `measure_<profile>.err` (hython stderr:
only the OpenSSL legacy-provider warning), `shot_<profile>.png`, `canvas.json`.
The probe's panel construction also wrote a session journal (`claude/`) into the
working directory as a side effect; it was removed. The `bus.jsonl` was not
posted to: this assignment is scaffold-only and carries no findings.
