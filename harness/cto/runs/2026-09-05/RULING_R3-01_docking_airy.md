# CTO ruling R3-01 - composed panel width at AIRY (2026-09-05, under Joe's delegation)

**Finding.** `tests/test_panel_rhythm_docking.py::test_every_composed_region_and_face_at_docking_bound[airy]`
is red on pd/panel-integrate-r3: DsRoot minimumSizeHint 393 > 380 (verb rail 237 + 4x24 group gap + 2x30 GUTTER).
Standard 361, tight 345. Nothing fits the PANEL_MIN_WIDTH 280 contract. At PANEL_PREF_WIDTH 340 under airy the
WORDMARK clips to "SYNAPS" and CURIOUS to "URIOUS".

**Ruling.**
1. The interim width feature in `.synapse/contracts/docking-minimums.yaml` becomes per density:
   airy 400, standard 380, tight 380. `_bounds()` in the docking test reads one width per density.
   The 280 contract stands; the feature is written as interim with this ruling as its provenance.
2. Wordmark non-shrinking policy: the brand is never the element that elides. The wordmark label gets a
   minimum width equal to its natural width at its pinned size; "Ignored"-priority labels elide first.
   Pin with a Qt test at PANEL_PREF_WIDTH under airy: wordmark text is not elided.
3. Not in this landing: a verb rail that collapses to icons (or wraps) below ~360px. That is the real fix
   toward 280 and belongs to the next design wave (queued in the Bierut review brief).

**Why.** (a) is the only option that closes the red without departing from battleplan T2 (rail role) or
faking a fit (GUTTER 26 still measures 385). A per-density bound is honest: airy IS wider by design.
The wordmark policy is Bierut's rule, not mine: the identity is the last thing that gives way.
