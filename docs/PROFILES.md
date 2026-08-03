# SYNAPSE Profiles

> **The Axiom.** Synapse is measured by what the artist can do without it. A rope gives reach
> you haven't earned and safety while you earn it — load-bearing, never self-propelling.

**The invariant: every profile runs with identical agent capability.** A profile changes how
work is shown and paced — never what the agent can do. Switching profiles adds or removes
nothing: no tools, no gates, no permissions. Verbatim from `harness/rope/program.md`:

- **L5 Pays out at your pace** — 3 designs, 1 widget library + manifests + compositor;
  identical capability in every profile; expert == v5.42.0 exactly.
- **L6 Never climbs for you** — explanation may rise, automation may not; notify on change,
  switch only on user action.

## The three profiles

One widget library, three compositions (manifests + compositor). The same operation renders
in all three — only the altitude of explanation differs. Producers:
`python/synapse/panel/manifests/{curious,expert,ml}.py`.

| Tab label | Built for | What the screen shows |
|---|---|---|
| **Curious** | finding your footing | orientation steps forward (Connect / Corpus go hero), diagnostic chrome goes quiet; the overlay narrates each decision, translates errors into plain language, and defines jargon on first use |
| **Expert** | the panel as it ships (== v5.42.0 exactly) | every widget at standard prominence, no overlay, no added narration |
| **ML** | the economist's read | token economics step forward (TOKEN pill + rail meter go hero); replies terse and technical |

Two presentation axes distinguish them (L5-18): **prominence** — where the accent lands,
per-widget — and **density** — one panel-wide rhythm (Curious `airy`, Expert `standard`,
ML `tight`), declared in each manifest's defaults and stamped on the panel root as a
single Qt property the stylesheet keys on.

## Where the copy lives

Each manifest carries its own display copy — `TAB_LABEL` and `PICKER_COPY` module
constants — so the manifest is the single source of copy for its profile. Voice per
`TONE.md`: collaborative, plain-spoken, options over commands, no jargon gatekeeping.

The first-run picker shows each profile's `PICKER_COPY` once. The choice is the
artist's, switching later is one click, and Synapse never switches on its own —
it may notify, the switch is yours (L6).

The jargon overlay — plain-language errors, inline decision narration, jargon
defined on first use — is the `system_prompt_overlay` string in `curious.py`.
It paces the same capability; it builds with you and explains as it goes,
load-bearing, never self-propelling.

## Derived design decisions

- The rail meter radius derives from `#DsCookBar` (`designsystem/qss.py`) because the vendored source of truth already establishes 2px-on-3px for the identical widget shape.
- Hero/quiet prominence derived from the `tokens.py` emphasis ladder (up: `TEXT_BRIGHT` and the `SIGNAL` slots a widget already reserves; down: `TEXT_TERTIARY`, then `TEXT_DISABLED` where standard already sits at tertiary) because the ladder already encodes emphasis — stepping it changes colour weight only, leaves every standard rule untouched, and so keeps expert == v5.42.0 exactly (L5-5).
- Hero takes the accent derived from the comp's DIRECT/WORK left rules and the tokens' recorded WARM=human / SIGNAL=technical split (amending the ladder line above: an ID-qualified hero now lifts to its role's accent — orientation/action widgets to `WARM`, meter/economic/connectivity widgets to `SIGNAL`; quiet and the bare roleless fallback keep the ladder), because the two-accent ceiling forbids a per-profile colour, so profiles are distinguished by WHERE the accent lands, not by owning one.
- Hero buttons knock out derived from the existing `[variant="primary"]` treatment (`designsystem/qss.py`) because the fill+`TEXT_ON_ACCENT` construction is already the system's sanctioned way to say "this is the action", so hero promotes to it rather than inventing an emphasis.
- The hero/SEND deep blue (`SIGNAL_DEEP`) derived from `SIGNAL` ×0.85 — a shade within the existing accent, like `SIGNAL_HOVER`/`SIGNAL_PRESS` — because Joe's seat call found the coral knockout too loud on buttons, and darkening only the rest state frees `SIGNAL` itself to serve as the hover step, so the fill still responds to touch without adding a third accent (buttons only; non-button hero rules keep their L5-14 accents).
- The verb rail's type and air derived from the tab row — the same `fontload.tracked_font("LABEL", SIZE_SMALL, mono=True)` call the CHAT/TOKEN pills use, and the `tokens.py` spacing scale stepped one rung (`SPACE_SM`→`SPACE_MD` above the rail's rule) — because the verbs are chrome siblings of the tabs, and stepping an existing scale adds air without inventing a number (L5-17).
- The context ribbon's left inset derived from `t.GUTTER` — the inset `_build_mode_bar` gives the tab row — because the `.hip` filename's first glyph must sit on the same vertical as the C of CHAT, and reusing the tab row's token aligns them without a nudged pixel (L5-17).
- The density steps (airy / tight) derived from the `tokens.py` spacing scale (`SPACE_XS`/`SPACE_SM`/`SPACE_MD`/`SPACE_LG`) stepped one rung per surface — airy up from each rest value in `designsystem/qss.py`, tight down, surfaces resting at zero stepping up only — because stepping an existing scale changes rhythm without inventing a number, and writing NO rule for `standard` leaves the unstyled sheet as the baseline, keeping expert == v5.42.0 exactly (L5-5/L5-18).
- Stop takes `WARM` (`#DsStop` in `designsystem/qss.py`: `WARM` knockout with `TEXT_ON_ACCENT` ink, `WARM_HOVER`/`WARM_PRESS` on touch) derived from MarkDot's documented one-warm-note rule because the mark and the button are two surfaces of a single control — `MarkDot.set_halt_handler` fires the same `_on_stop` the rail button fires — and one control must read as one; the danger red made the two surfaces read unrelated, and the danger variant itself stays untouched for other widgets (L5-20, not profile-conditional: identical in all three profiles).
- The verb gap doubles (`SPACE_MD`→`SPACE_LG` between the `#DsVerb` buttons in `_build_act`) derived from the `tokens.py` SPACE ladder's own doubling steps because EXPLAIN / FIX / OPTIMIZE / BUILD HDA were reading as a single continuous phrase rather than four controls — one rung up is the ladder's own "double", no invented number; base spacing only, so all three density profiles shift together and their relative rhythm is preserved (L5-21).
- The composer's first-run height derived from the pane's own measure — half the space the chat and the composer share, clamped to the grip's existing 64/600 rails (`settings.composer_start_height`, applied at show/resize where the height is real, never `__init__`) — because the fixed 132 landed the divider above centre in every tall pane and Joe re-dragged it each session; the height settles once, a grip drag persists on release, and the artist's persisted height is restored in preference to the centred default thereafter (L5-22, L6: remember their answer, never re-impose ours). Identical in curious / expert / ml.

`tests/test_rope_design_conformance.py` scans the panel modules the L5-11 pass touched
for hardcoded hex colours and bare px values; a site may be waived only by a
`DESIGN-GAP(L5-11)` marker on the offending line, and every marker must be registered
here.

## The hand-me-the-pen gradient

```
build-while-you-watch  →  build-with-pauses  →  explain-then-you-try
```

The pen moves toward the artist at the artist's pace: first the agent builds while you watch,
then it builds with pauses so you can follow and object, then it explains the move and you
make it yourself. Explanation rises along the gradient; automation never does (L6). Every
position on the gradient is reachable from every profile — identical capability means the
gradient is a request, not a restriction — and the system never advances your position for
you: it may notify, the switch is yours (L6).
