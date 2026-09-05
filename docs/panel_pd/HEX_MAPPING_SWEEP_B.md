# SWEEP_B hex mapping ? inherited source sites

Source revision: `ce04dcb0`. Lines refer to that revision before migration.
Every raw six-digit occurrence, including comments and redundant fallbacks,
is listed; three-digit HTML colors are also migrated under the stricter reading.
These are removed source values, not new palette declarations.

The three historical sources were repository `design/tokens.py`, off-repo
`~/.synapse/design`, and fallback `panel/tokens.py`. This sweep reads only
`python/synapse/panel/designsystem/tokens.py`, the vendored authority that already
reconciles them. Blue type/link/action roles use SIGNAL and its existing family;
blue metadata uses the seeded neutral text ramp; blue category fills use SURFACE.
No RGB-distance calculation, external import, new token, or brand color is used.
Warnings/errors use existing status roles; non-status categories are neutral.
Existing speaker-dot semantics in message_formatter stay unchanged.

| file | line | hex | token | role rationale |
|---|---:|---|---|---|
| `python/synapse/panel/vex_tutor.py` | 817 | `#6db3f2` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/vex_tutor.py` | 819 | `#c586c0` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/vex_tutor.py` | 825 | `#dcdcaa` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 837 | `#6a9955` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/vex_tutor.py` | 844 | `#ce9178` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/vex_tutor.py` | 850 | `#b5cea8` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 878 | `#cccccc` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 879 | `#808080` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/vex_tutor.py` | 880 | `#e0e0e0` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 882 | `#1e1e1e` | `GROUND` | surface: inset code well/bar track |
| `python/synapse/panel/vex_tutor.py` | 883 | `#d4d4d4` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 885 | `#b0b0b0` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/vex_tutor.py` | 888 | `#1e1e1e` | `GROUND` | surface: inset code well/bar track |
| `python/synapse/panel/vex_tutor.py` | 889 | `#d4d4d4` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/vex_tutor.py` | 891 | `#8a8a5c` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_trace.py` | 630 | `#6ABF69` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 631 | `#7AB4CC` | `TEXT_SECONDARY` | muted: blue attribute category is metadata, not a link or active action |
| `python/synapse/panel/apex_trace.py` | 632 | `#B9B06A` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 633 | `#E8922E` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 634 | `#CC6A9E` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 635 | `#9E7ACC` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 636 | `#888888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_trace.py` | 637 | `#AAAAAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 645 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_trace.py` | 659 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 668 | `#AAAAAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 671 | `#E8922E` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/apex_trace.py` | 671 | `#555555` | `BORDER` | surface: existing hairline role |
| `python/synapse/panel/apex_trace.py` | 672 | `#2A2520` | `SIGNAL_TINT` | surface: critical-path emphasis wash from vendored signal family |
| `python/synapse/panel/apex_trace.py` | 684 | `#666` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_trace.py` | 690 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 698 | `#7AB` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 703 | `#B9B` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 708 | `#E8922E` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/apex_trace.py` | 716 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_trace.py` | 728 | `#E8922E` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/apex_explainer.py` | 806 | `#cc6666` | `ERROR` | hot: actual error/critical state |
| `python/synapse/panel/apex_explainer.py` | 819 | `#7799cc` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/apex_explainer.py` | 825 | `#2a2a2a` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/apex_explainer.py` | 826 | `#dddddd` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/apex_explainer.py` | 829 | `#aa8855` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_explainer.py` | 831 | `#ccaa77` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_explainer.py` | 833 | `#88aa66` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_explainer.py` | 835 | `#cccccc` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/apex_explainer.py` | 837 | `#444` | `BORDER` | surface: existing hairline role |
| `python/synapse/panel/apex_explainer.py` | 839 | `#8888bb` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/apex_explainer.py` | 841 | `#bbbbbb` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/apex_explainer.py` | 844 | `#666` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/scene_doctor.py` | 677 | `#e74c3c` | `ERROR` | hot: actual error/critical state |
| `python/synapse/panel/scene_doctor.py` | 678 | `#e67e22` | `ERROR` | hot: actual error/critical state |
| `python/synapse/panel/scene_doctor.py` | 679 | `#f1c40f` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/scene_doctor.py` | 680 | `#95a5a6` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/scene_doctor.py` | 695 | `#2ecc71` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/scene_doctor.py` | 702 | `#3498db` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/scene_doctor.py` | 726 | `#3498db` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/scene_doctor.py` | 731 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/performance_profiler.py` | 343 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/performance_profiler.py` | 348 | `#ccc` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/performance_profiler.py` | 352 | `#2a2a2a` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/performance_profiler.py` | 367 | `#e8a020` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/performance_profiler.py` | 367 | `#4a90d9` | `SIGNAL` | signal: actionable/type emphasis from vendored authority |
| `python/synapse/panel/performance_profiler.py` | 368 | `#d4881a` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/performance_profiler.py` | 368 | `#3a7bc8` | `SIGNAL_PRESS` | signal: bar outline from the same vendored family |
| `python/synapse/panel/performance_profiler.py` | 381 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/performance_profiler.py` | 387 | `#1a1a1a` | `GROUND` | surface: inset code well/bar track |
| `python/synapse/panel/performance_profiler.py` | 397 | `#e8a020` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/performance_profiler.py` | 406 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/performance_profiler.py` | 415 | `#2a2a2a` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/performance_profiler.py` | 416 | `#e8a020` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/network_trace.py` | 440 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/network_trace.py` | 458 | `#E8922E` | `HOT_SOFT` | hot: historical bottleneck documentation; existing behavior retained; documentation only |
| `python/synapse/panel/network_trace.py` | 458 | `#666666` | `TEXT_DISABLED` | muted: historical inactive-node documentation; documentation only |
| `python/synapse/panel/network_trace.py` | 458 | `#888888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata; documentation only |
| `python/synapse/panel/network_trace.py` | 458 | `#AAAAAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status; documentation only |
| `python/synapse/panel/network_trace.py` | 458 | `#6ABF69` | `CONIFEROUS` | muted: existing speaker/geometry semantic; remove private fallback or historical literal; documentation only |
| `python/synapse/panel/network_trace.py` | 458 | `#E05555` | `NO_SOFT` | hot: quiet error semantic already used for geometry loss; documentation only |
| `python/synapse/panel/network_trace.py` | 488 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/network_trace.py` | 494 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/network_trace.py` | 513 | `#7AB` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/network_trace.py` | 520 | `#B9B` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/network_trace.py` | 527 | `#E05555` | `NO_SOFT` | hot: quiet error semantic already used for geometry loss |
| `python/synapse/panel/network_trace.py` | 532 | `#E8922E` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/network_trace.py` | 548 | `#E8922E` | `WARN` | warm: measured caution/warning status, not a human speaker |
| `python/synapse/panel/cross_scene.py` | 415 | `#5B9BD5` | `SURFACE` | surface: blue/cyan category badge is neutral; neither historical cyan source is selected |
| `python/synapse/panel/cross_scene.py` | 416 | `#A5D6A7` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/cross_scene.py` | 417 | `#CE93D8` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/cross_scene.py` | 418 | `#FFB74D` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/cross_scene.py` | 419 | `#EF9A9A` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/cross_scene.py` | 420 | `#80CBC4` | `SURFACE` | surface: blue/cyan category badge is neutral; neither historical cyan source is selected |
| `python/synapse/panel/cross_scene.py` | 434 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/cross_scene.py` | 439 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/cross_scene.py` | 447 | `#888` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/cross_scene.py` | 449 | `#111` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/cross_scene.py` | 458 | `#666` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/message_formatter.py` | 8 | `#8FB3D9` | `SIGNAL` | signal: actionable/type emphasis from vendored authority; documentation only |
| `python/synapse/panel/message_formatter.py` | 33 | `#6E8F72` | `CONIFEROUS` | muted: existing speaker/geometry semantic; remove private fallback or historical literal |
| `python/synapse/panel/message_formatter.py` | 34 | `#FF7759` | `WARM` | warm: existing speaker dot; remove private fallback |
| `python/synapse/panel/message_formatter.py` | 278 | `#DEDEDE` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp; documentation only |
| `python/synapse/panel/message_formatter.py` | 278 | `#C5C5C5` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp; documentation only |
| `python/synapse/panel/command_palette.py` | 48 | `#00D4FF` | `SIGNAL` | signal: actionable/type emphasis from vendored authority; removed-fallback documentation only |
| `python/synapse/panel/command_palette.py` | 389 | `#00E676` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/command_palette.py` | 390 | `#FF6B35` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/command_palette.py` | 391 | `#FFAB00` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/command_palette.py` | 392 | `#888888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |

## Landing r3 (2026-09-05) - the side modules (CTO RULING-1d)

Same revision, same method, same authority: every remaining raw colour in the
nine side modules (bookmarks, dependency_map, apex_recipes, save_shot,
session_integrity, recipe_book, error_translator, session_journal, styles) maps
to an existing `designsystem/tokens.py` name by role; the five comment-only
hits are reworded so no hex survives in prose either. agent_health's
`format_agent_health_html` and render_preflight's `format_preflight_html` +
`_STATUS_ICONS` (20 sites) were DELETED - no caller, no test - so they carry no
rows: deleting dead code is cheaper than tagging it.

| file | line | hex | token | role rationale |
|---|---|---|---|---|
| `python/synapse/panel/bookmarks.py` | 164 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/bookmarks.py` | 175 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/bookmarks.py` | 196 | `#444` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/bookmarks.py` | 196 | `#ccc` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/bookmarks.py` | 209 | `#3C3C3C` | `BORDER` | surface: existing hairline role |
| `python/synapse/panel/bookmarks.py` | 210 | `#E0E0E0` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/bookmarks.py` | 212 | `#777` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/bookmarks.py` | 213 | `#999` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/bookmarks.py` | 238 | `#665500` | `SIGNAL_TINT` | signal: subtle accent wash (search-match background) |
| `python/synapse/panel/bookmarks.py` | 238 | `#FFD700` | `SIGNAL` | signal: search-match emphasis, the one accent |
| `python/synapse/panel/dependency_map.py` | 420 | `#4CAF50` | `GROW` | status: success/verified state |
| `python/synapse/panel/dependency_map.py` | 421 | `#F44336` | `ERROR` | status: error state |
| `python/synapse/panel/dependency_map.py` | 422 | `#FFC107` | `WARN` | status: warning/caution state |
| `python/synapse/panel/dependency_map.py` | 423 | `#FFC107` | `WARN` | status: warning/caution state |
| `python/synapse/panel/dependency_map.py` | 440 | `#999` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/dependency_map.py` | 466 | `#DDD` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/dependency_map.py` | 479 | `#444` | `BORDER` | surface: existing hairline role |
| `python/synapse/panel/dependency_map.py` | 481 | `#CCC` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/dependency_map.py` | 482 | `#999` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/dependency_map.py` | 483 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/dependency_map.py` | 491 | `#AAA` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/dependency_map.py` | 491 | `#555` | `BORDER_STRONG` | surface: separator rule |
| `python/synapse/panel/apex_recipes.py` | 25 | `#00D4FF` | `SIGNAL` | signal: actionable/type emphasis from vendored authority; documentation comment reworded |
| `python/synapse/panel/apex_recipes.py` | 25 | `#00E676` | `GROW` | status: success/verified state; documentation comment reworded |
| `python/synapse/panel/apex_recipes.py` | 720 | `#FF6B6B` | `ERROR` | status: error/advanced difficulty, existing error role |
| `python/synapse/panel/save_shot.py` | 378 | `#4a9` | `GROW` | status: success/verified state (saved snapshot) |
| `python/synapse/panel/save_shot.py` | 378 | `#2a2a2a` | `SURFACE` | surface: neutral container/category badge, not active/success/error state |
| `python/synapse/panel/save_shot.py` | 379 | `#4a9` | `GROW` | status: success/verified state (saved snapshot) |
| `python/synapse/panel/save_shot.py` | 381 | `#ccc` | `TEXT_PRIMARY` | ink: readable body/data from host-seeded ramp |
| `python/synapse/panel/save_shot.py` | 382 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/save_shot.py` | 388 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/save_shot.py` | 393 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/save_shot.py` | 394 | `#666` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/save_shot.py` | 456 | `#888` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/save_shot.py` | 463 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/save_shot.py` | 473 | `#3C3C3C` | `BORDER` | surface: existing hairline role |
| `python/synapse/panel/save_shot.py` | 474 | `#E0E0E0` | `TEXT_BRIGHT` | ink: heading/identifier emphasis from host-seeded ramp |
| `python/synapse/panel/save_shot.py` | 475 | `#777` | `TEXT_TERTIARY` | muted: secondary label/comment/source metadata |
| `python/synapse/panel/save_shot.py` | 476 | `#999` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/session_integrity.py` | 203 | `#FFAB00` | `WARN` | status: warning/caution state (exact existing token) |
| `python/synapse/panel/session_integrity.py` | 214 | `#FF6B35` | `FIRE` | status: execution/active warning (exact existing token) |
| `python/synapse/panel/session_integrity.py` | 220 | `#4ECDC4` | `SIGNAL` | signal: actionable recommendation from vendored authority |
| `python/synapse/panel/recipe_book.py` | 27 | `#00D4FF` | `SIGNAL` | signal: actionable/type emphasis from vendored authority; documentation comment reworded |
| `python/synapse/panel/recipe_book.py` | 761 | `#FF6B6B` | `ERROR` | status: error/advanced difficulty, existing error role |
| `python/synapse/panel/error_translator.py` | 19 | `#00D4FF` | `SIGNAL` | signal: actionable/type emphasis from vendored authority; documentation comment reworded |
| `python/synapse/panel/session_journal.py` | 249 | `#aaa` | `TEXT_SECONDARY` | muted: explanatory text/category/data, not an accent or status |
| `python/synapse/panel/session_journal.py` | 268 | `#f0a030` | `WARN` | status: warning/caution emphasis (search match) |
| `python/synapse/panel/styles.py` | 9 | `#8FB3D9` | `SIGNAL` | signal: the SIGNAL value itself; documentation comment reworded |
