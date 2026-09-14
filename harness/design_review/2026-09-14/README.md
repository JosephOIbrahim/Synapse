# SYNAPSE panel design crit — 2026-09-14

Advances the 2026-09-05 review in the sibling directory. Does **not** replace it:
that review's point of view stands verbatim and its restraint floor (0.82–0.84%
chromatic pixels, three hue buckets, one warm mark, a wordmark that never elides)
is unchanged.

**Method.** Five lens partners — IDEA, TYPE, SYSTEM, SUBTRACT, USE — filed
positions, critiqued each other by name, then answered the critiques of their own
work. 25 critiques, 15 concessions. Synthesis, then three crucibles, then revision.
One partner's respond round died on schema validation (4 of 5 completed).

**Scope.** The two things the 2026-09-05 review left open: the spacing system and
the artist-utility floor.

## The headline

**F1 is closed, not open.** The verb rail was already retired before this crit ran —
`synapse_panel.py:1417-1423` documents the removal, `verb_rail` has zero grep hits
panel-wide, and EXPLAIN / FIX / OPTIMIZE are slash-palette rows with BUILD HDA as an
overflow action. The 333/301/285 clip arithmetic is historical.

## Two defects re-opened, both live at HEAD bd65e4b6

- **F2** — `_run_direct_tool` (`synapse_panel.py:2734-2737`) writes header phrases
  outside `_state_phrases()`, putting a full Houdini path into an 83px bare QLabel
  with no ellipsis. The rule that prevents it already exists at `_on_stop:3482-3487`.
- **F4 (verb half)** — `mark_decided` (`gate_widget.py:347-358`) hides every verb
  unconditionally, including `_revert_btn`, including on REVIEW's auto-resolve path.
  The hue half of F4 was already fixed; the docstring says so. The verb half was not.

Neither is assigned to a builder. Both are artist-facing.

## The collision that must be decided before any spacing work

SUBTRACT and SYSTEM both resolve F12 by editing `rhythm.py:26-36`, mutually
exclusively — `shell`, `group`, `card` and `tag` all currently equal 16.
SUBTRACT deletes one role for zero visual delta. SYSTEM redistributes so no two
roles share a value, which closes F12 properly but **invalidates the 393/361/345
floor numbers the moment it ships**, because those were measured under `shell=16`.

Only one can land. Whichever merges second silently overwrites the first.

## Contents

- `SCAFFOLD.html` — the revised scaffold, 12 sections. §8 carries six live decisions
  plus two blocked on unrun probes; §11 contests three crucible findings; §12 is the
  one-screen card.
- Published copy: https://claude.ai/code/artifact/41830a3b-c9fc-4d7d-a3e2-3d701700aec2

Nothing here has been built. Every decision in §8 is gate `joe`.
