# BP4-CRUX · PANELFONT lane — independent typography grep

Tree: scratch clone of `bp4/panelfont` @ 4b3b3967. Surface: `python/synapse/panel/**/*.py`.

## Method A — the crucible's broad grep (LINES, excludes designsystem/tokens.py)

`grep -rn -E "font-(size|family|weight)\s*:|line-height\s*:|setPointSize\(|setPixelSize\(|setPointSizeF\(|QFont\("`

**TOTAL 260 matching lines.** Per file (top 15):

| hits | file |
|--:|---|
| 75 | `python/synapse/panel/styles.py` |
| 22 | `python/synapse/panel/hda_views.py` |
| 21 | `python/synapse/panel/gate_widget.py` |
| 15 | `python/synapse/panel/message_formatter.py` |
| 14 | `python/synapse/panel/recipe_book.py` |
| 13 | `python/synapse/panel/context_bar.py` |
| 10 | `python/synapse/panel/designsystem/qss.py` (all token refs — see Method B) |
|  9 | `python/synapse/panel/apex_recipes.py` |
|  6 | `python/synapse/panel/vex_tutor.py` |
|  6 | `python/synapse/panel/save_shot.py` |
|  6 | `python/synapse/panel/render_preflight.py` |
|  6 | `python/synapse/panel/apex_explainer.py` |
|  5 | `python/synapse/panel/scene_doctor.py` |
|  5 | `python/synapse/panel/performance_profiler.py` |
|  5 | `python/synapse/panel/face_review.py` |

Per pattern (line counts): font-size 164 · font-family 87 · font-weight 33 ·
line-height 7 · setPixelSize 6 · QFont( 9 · setPointSize 0 · setPointSizeF 0.

## Does the audit's inventory (167 / 88 / 33 / 13) reproduce?  YES — exactly.

The audit counts OCCURRENCES of the bare property word (no colon required)
across all of `python/synapse/panel/**/*.py` INCLUDING `designsystem/tokens.py`:

| property | audit | crux, bare-word occurrences | crux, `\s*:` line count (excl tokens.py) |
|---|--:|--:|--:|
| font-size   | 167 | **167** | 164 |
| font-family |  88 | **88**  | 87  |
| font-weight |  33 | **33**  | 33  |
| line-height |  13 | **13**  | 7   |

Method difference, stated: occurrence-vs-line and word-vs-`word:`. The
line-height gap (13 vs 7) is the largest and is explained by the same rule —
6 of the 13 `line-height` mentions are prose/comment references (chiefly the
"Qt does not implement CSS line-height" notes), not `line-height:` declarations.
**The audit's numbers are reproducible under a stated method. No inflation found.**

## Method B — the TEST's own regex, applied to EVERY panel file

`font-(?:size|weight|family)\s*:\s*(?!\{)[^\s;\n]` after stripping `/* */`.
The shipped test runs this against exactly ONE file (`designsystem/qss.py`).
The crux ran it against all 92 `.py` files under `python/synapse/panel/`.

**TOTAL 174 hits in 23 files.** Split for fairness:
- **166 truly hardcoded** (the value is a literal: `13px`, `9pt`, `monospace`, `bold`)
- **8 `%`-interpolated** (token-fed at runtime: `font-size: %dpx` filled from
  `t.scaled(...)`) — in `face_token.py` ×3, `health_strip.py` ×2,
  `synapse_panel.py` ×2, `face_review.py` ×1. These are NOT hardcoded; the test's
  regex only whitelists `{`-interpolation, so `%`-style token feeds read as literals.

Truly-hardcoded per file: styles.py 44 · hda_views.py 33 · context_bar.py 14 ·
gate_widget.py 13 · render_preflight.py 9 · apex_explainer.py 7 ·
performance_profiler.py 6 · save_shot.py 6 · scene_doctor.py 6 · vex_tutor.py 6 ·
bookmarks.py 5 · apex_trace.py 2 · chat_display.py 2 · cross_scene.py 2 ·
dependency_map.py 2 · error_translator.py 2 · quick_actions.py 2 ·
session_journal.py 2 · face_review.py 2 · face_token.py 3 · agent_health.py 1.

### designsystem/*.py under the test's own regex — ALL ZERO

```
0  python/synapse/panel/designsystem/__init__.py
0  python/synapse/panel/designsystem/components.py
0  python/synapse/panel/designsystem/fontload.py
0  python/synapse/panel/designsystem/loader.py
0  python/synapse/panel/designsystem/motion.py
0  python/synapse/panel/designsystem/qss.py
0  python/synapse/panel/designsystem/theme_source.py
0  python/synapse/panel/designsystem/tokens.py
```
So the design-system authority is clean — CLEANER than the test proves, since the
test only reads `qss.py` while all eight files are in fact at zero.

## The two readings of acceptance 2 (referee decides)

Predicate as WRITTEN: *"token module defines family + scale + weights +
line-heights; test_panel_typography finds no typography literal outside it."*

- **As WRITTEN (panel-wide, "outside the token module"): FAIL.** 166 truly
  hardcoded typography literals live outside `designsystem/` in 22 modules, and
  `test_panel_typography` does not scan a single one of them — it opens
  `designsystem/qss.py` and nothing else. Sub-clause: the token module has no
  per-role line-height token; it has `CHAT_LEADING_PT` (a 0.75pt leading), which
  the builder argues is the only mechanism Qt honours.
- **As the builder SCOPED it (design-system authority only): PASS.** Every file
  under `designsystem/` is at 0 literals, the scope limit is declared in the test's
  own module docstring and in audit §3/§9, the out-of-territory count is
  inventoried per file, and four named spawns carry the remainder forward.

The builder did not hide the gap — the receipt routes exactly this question to the
referee as `for_ruling[0]`. The disagreement is about SCOPE, not about honesty.
