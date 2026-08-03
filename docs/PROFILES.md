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

## Design gaps for human decision

Found by the L5-11 conformance pass. `tests/test_rope_design_conformance.py` scans the
panel modules the pass touched for hardcoded hex colours and bare px values; a site may
be waived only by a `DESIGN-GAP(L5-11)` marker on the offending line, and every marker
must be registered here. Nothing below is fixed — conform, don't invent.

- **Rail activity meter radius — `synapse_panel.py`, `DsRailMeter`, 2 sites
  (`_build_rail`, `_set_busy`).** The 3px meter strip rounds at `border-radius:2px`.
  Colours are tokenized (`SIGNAL_TINT` idle / `WARM` busy); the radius is not — the
  smallest radius token is `RADIUS_SM = 4`, and a 4px radius on a 3px-high widget
  mis-renders in QSS. The designsystem's own cook bar (`#DsCookBar`,
  `designsystem/qss.py`) hardcodes the same 2px-on-3px inside the vendored source of
  truth, so the value is established design intent without a name. Decide one:
  **(a)** add a `#DsRailMeter` rule beside `#DsCookBar` in `qss.py` (the busy/idle
  colour swap becomes a dynamic property + `repolish`, the `_set_face` idiom), or
  **(b)** name the token (e.g. `RADIUS_METER = 2` in `tokens.py`) and consume it at
  both sites. Until ruled, the literal stays put and the sites stay marked.

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
