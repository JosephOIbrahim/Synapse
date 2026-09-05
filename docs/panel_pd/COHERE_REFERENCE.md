# Cohere × Pentagram — reference notes for the PD wave

Source: https://www.pentagram.com/work/cohere (Pentagram, partners Jody Hudson-Powell and Luke Powell; launched 2021, page updated 2026). Read on 2026-09-04. These are **rules to learn from, not pixels to copy** (battleplan §1-3, §4). Nothing Cohere-branded enters SYNAPSE: no Voronoi cells, no Cohere colours, no new typeface. The bundled Space Grotesk stays; sizes floor at the host; accent stays the `SIGNAL` family.

## What the case study actually says

- **Concept:** "new nature" — organic fluidity paired with computational rationality; the platform pictured as an ecosystem of "users, projects, inputs and models coming together".
- **Type system:** one custom family in four roles — Headline (variable, Voronoi cuts), Text (bold/regular/light + italics, described as a "faux mono style" that "references our digital, code-centric world"), Outline, and **Mono** for code environments and snippets. "Small tags and notes provide contrast and focus."
- **Colour:** natural tones (coniferous green, mushroom grey, volcanic black) against synthetic hues (simulated coral, synthetic quartz, acrylic blue); gradient atmospheres add texture "without dominating layouts".
- **Iconography:** functional set drawn at 24 px, single monolinear line; separate endpoint pictograms as identifiers.
- **Tooling:** a bespoke Figma plug-in and two layout component libraries so teams generate the pattern themselves — the identity is a **system others operate**, not a set of finished pictures.
- **Product surfaces:** personalised dashboard, playground, extensive documentation.

## The structural lessons the battleplan spends (§1-3, §4)

These are the transferable moves. Each maps to a role in `docs/PANEL_RHYTHM_SPEC.md` v2 (LEVER writes it) and to the role table in `docs/PANEL_BATTLEPLAN_PD.md` §4.

1. **Mono is a role, not a flavour.** Tags, labels, ids, notes are mono, upper, tracked, small — and *that contrast* is what makes the sans body read as content. → `label`, `tag`.
2. **Hardworking assets at small scale.** Everything is designed to survive at 24 px / small tags. → sizes floor at the host; glyph cells 44×44; nothing decorative that needs room.
3. **Groups are separated by hairlines, rows do not touch.** Structure is drawn with hairlines and whitespace, never with filled boxes. → `row` (min-h 44, radius 8, hairline border), `group` hairline under the *group*, never under the label.
4. **Three-band cards.** Header / body / footer with hairlines between bands; the footer carries one text action left and one status pill right. → `card` (40 / pad 16 / 40), the recall card (§1-6).
5. **One accent does the pointing.** Everything else is neutral surface. → `SIGNAL` for active tab / SEND / hero; `WARM` for the human; `HOT_SOFT` only for BLOCKED/stop. Zero new colour points.
6. **A system others can operate.** Pentagram shipped tooling, not mockups. → `designsystem/rhythm.py` + QSS roles are the tooling; the census + guard test make the reach measurable and monotonic.
7. **Grid-aligned parameter rows.** Dense technical UI reads calm when columns are fixed. → `parm_row` (label 128 · value 64 · control fills · row 24).

## Anti-patterns (what "referencing Cohere" must not become)

- Importing the Voronoi language, gradients, or the Cohere palette. BROKEN under PD-CRUX.
- Adding a font family or a hex value. BROKEN (battleplan §1-3, SWEEP-B crucible).
- Re-styling widgets so their look changes beyond gap / label / tag treatment. BROKEN (SWEEP-A crucible).
- Treating the screenshots as truth. `panel_shot.py` PNGs are a diff instrument; truth is Joe's eyes on H22.0.400 (§1-7).
