# Drafts for the v5.79.0 README and CHANGELOG edits

Exact edit points, measured 2026-09-21 on master at `357bf1e7`:

| File | Line | Current |
|---|---|---|
| README.md | 7 | `<p align="center"><sub>v5.78.0 · Houdini 22.0.400 · Python 3.13 runtime<br>tags: v5.78.0 is Latest</sub></p>` |
| README.md | 122 | `**New in 5.78.0** — the artist sees why, and Jev routes the work.` |
| README.md | 128 | closing paragraph linking `docs/releases/v5.78.0.md` |
| README.md | 242 | `- [Release notes](docs/releases/v5.78.0.md) · [Changelog](CHANGELOG.md)` |
| CHANGELOG.md | 25 | `## v5.78.0 - The artist sees why, and Jev routes the work` (new entry goes directly above) |

---

## README line 7

    <p align="center"><sub>v5.79.0 · Houdini 22.0.400 · Python 3.13 runtime<br>tags: v5.79.0 is Latest</sub></p>

## README "New in" block (replacing 122-128)

**New in 5.79.0** — one Commands list, and six dead gates.

Type `/` into an empty composer and the list you get is called Commands everywhere, ordered by a decision rather than by the alphabet, and the first eight rows each lead somewhere on an empty scene. Before this, the top of that list was usually a registry row whose only honest answer was "nothing is selected".

The panel also scales properly now. Roughly 25 sizes inside one stylesheet block were frozen pixels — status dots and chevrons among them — so on a high-DPI host the text grew and they did not.

On the build side, four of the gates guarding this work could not pass on any branch, master included, and two of them printed green from a worktree for code that branch did not contain. One instrument replaced them: it proves which tree it measured before it measures anything, and ratchets against committed baselines instead of demanding a green that does not exist. Rehearsing it caught a fifth dead gate and a "read-only" probe that was destroying the artist's parked session. Full notes in [docs/releases/v5.79.0.md](docs/releases/v5.79.0.md).

## README line 242

    - [Release notes](docs/releases/v5.79.0.md) · [Changelog](CHANGELOG.md)

---

## CHANGELOG entry (insert above `## v5.78.0`)

## v5.79.0 - One Commands list, and six dead gates

*Product change in `python/synapse/panel/` (tool_palette, command_palette, synapse_panel, designsystem/qss, designsystem/tokens, designsystem/rhythm, message_formatter) plus a new first-click probe under `panel/scripts/`. Product-surface diff v5.78.0..v5.79.0: {{PRODUCT_DIFF}}.*

**ONE COMMANDS LIST, ORDERED BY A DECISION.** The overflow action said "Palette" while the rest of the panel said something else, and rows arrived in alphabetical order. The name is now Commands everywhere; every row carries a group, a head and an order, and `tool_palette._load_entries` sorts on (group rank, hand order, context, verb, title). Adding a band means giving its rows a group, not re-sorting the list. The five commands the panel answers itself are a single frozen set (`command_palette.PANEL_ANSWERED_COMMANDS`) with a `panel_answered` field set at the one build path, so the list and the handler cannot drift. `/restore-session` had been intercepted by the panel since W7-SESSCOPE and never listed; adding it is what makes the panel group five, and it corrected the brief's "20 rows" to 21.

**THE FIRST CLICK CANNOT DEAD-END.** `panel/scripts/probe_first_click.py` walks the first eight rows on an empty scene and asserts each leads somewhere: four open a local view without reaching a model, one restores the last session and answers plainly when there is none, three send a prompt stating its own empty-selection fallback. It names the row that dead-ends and always prints the eight titles.

**THE WHOLE PANEL SCALES WITH THE HOST.** `qss.stylesheet()` now threads the scale into all six `_sweep_a_builders` entries, each binding its own floored `s`. About 25 sizes ride it, including the three `GLYPH_*` sizes that would otherwise have stayed frozen at 18/14px while the rules around them grew. Five letter-spacing declarations are gone and five arithmetic `700`s are `t.WEIGHT_BOLD`. Nothing moves at scale 1.0; at 2.25 the chat rules go 12px to 27px, measured.

**A COMMENT WAS THE BUG.** The strict audit's "no bundled font in QSS" row was caused by a code comment naming the bundled face at `qss.py:208` — comments ship inside the generated stylesheet string. `get_chat_display_stylesheet(1.0)` was already clean and the sheet carries no font-family rule at all.

**THE FONT FLOOR STOPPED LYING ABOUT ITSELF.** `FONT_FLOOR_PROVENANCE` said "nothing in the panel scales to the host" while `synapse_panel.py:552` seeds `_chrome_scale` from the host font.

**SIX DEAD GATES, ONE INSTRUMENT.** Every panel leg was handed an acceptance line that could not pass on any branch: `audit_panel.py --strict exits 0` (the audit read a deleted token and crashed on its first table, hiding two real FAIL rows) and `hytest tests/panel/test_bc_wave.py exits 0` (master is 2 failed, 11 passed). Both also **lied from a worktree** — `HOUDINI_PACKAGE_DIR` aims Houdini at the main checkout and beats `PYTHONPATH`, so hython imported `synapse` from the main tree whatever branch was out — and a seat test needing a gitignored `.env` key added a phantom third failure in every worktree. `harness/notes/bp9/panel_gate.py` replaces all of them: it prints the path hython imported from and refuses on the wrong tree, supplies the key in memory without writing it into a worktree, and ratchets both instruments against committed baselines that may only shrink.

**A FIFTH, FOUND BY REHEARSING.** Run on a trial integration before the graph finished, `panel_gate.py` matched only `G3 RESULT: <n> FAIL`; the audit prints `G3 RESULT: pass` when nothing fails, so a fully green audit parsed as a crash. A gate that cannot recognise success is as dead as one that cannot pass.

**A READ-ONLY PROBE WAS EATING THE ARTIST'S PARKED SESSION.** The first-click probe's docstring claimed READ-ONLY; its verifier disproved it with evidence. `SYNAPSE_PANEL_SETTINGS` isolates the panel's settings only, while the conversation store resolves from the HIP directory (`server/session_store.py:57`), so constructing the panel ran `load_conversation_scoped()` and `os.replace(target, prev)` at `session_store.py:250`. Seeded with a live conversation and an older parked one, the probe left the live slot `[]` and destroyed the older one. `_prepare_env` now pins `_resolve_store_dir` at a fresh mkdtemp before any panel is built; measured after the fix, both files are byte-intact. Pinned by `tests/test_probe_first_click_is_read_only.py`, which needs neither Qt nor hython and reddens without the three-line fix.

**TWO REDS NO LEG COULD SEE.** A leg runs only the tests its acceptance names, so it structurally cannot catch what it breaks elsewhere; the composed gate runs the whole suite over the integrated leaves. It caught the eleven `print()` calls in the new probe (a pin forbids them anywhere under the package; the probe now writes through a `_w()` helper on stdout, the convention `panel/scripts/probe_ui_font.py` already set) and a SECOND constructor pin nobody amended — moving the `/` telling into the composer edits `_GrowingInput.__init__`, which `tests/test_panel_camera_rhythm.py` also holds verbatim. Declared through that file's own `CRIT_20260915_CONSTRUCTOR_AMENDMENTS` mechanism ("baseline + exactly the ruled deltas, never a carve-out"), with the entry generated from the real base and current sources. Both proven by deliberate break; both files restored byte-identical.

**R3-B REFUSED WITH EVIDENCE, AND WAITS ON A RULING.** R3-B reads "quiet = caps + tracking in sans 500 at body size". Measured against the code, `caption` is handed whole sentences at ~20 call sites (connection_dialog consent copy, project_rules, notifications, saved_recipes, tool_palette's empty state); upper-casing a paragraph is the opposite of the readability the leg is for. So `tokens.ROLE_CAPS` ships **wired and tested and EMPTY**, saying so in the code, read by `components.apply_font_role`. Unblocked by splitting caption into metadata-chip vs explanatory-prose, or by a ruling — adding one word to the set is then the whole change.

**A TEST COUPLED TO LIVE REPO STATE.** `tests/test_ingest_rulings.py` seeds its temp board by copying the real `harness/state/resolved.json`, then rules on `A1` and asserted `A1` appears exactly once. Ruling on A1 for real made that count 2. Amended by declaration to the invariant it exists to pin — the second ingest records nothing, measured from a baseline — which also pins the first ingest to exactly one new entry, so the amendment is stricter than the literal it replaces.
