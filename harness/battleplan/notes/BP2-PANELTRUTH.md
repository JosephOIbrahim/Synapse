# BP2-PANELTRUTH — panel truth (T1 profile diff · T2 TOKEN refresh · T3 float fix · T4 contract)

Branch `bp2/paneltruth`, worktree `.claude/worktrees/bp2-paneltruth`. Three
things on camera, each with a receipt and a test that fails on the defect.

## T1 — profile diff with receipt

Producer `harness/battleplan/notes/bp2_paneltruth_profile_diff.py` composes all
three manifests through the SAME production path the panel uses
(`compositor.resolve` for the widget tree, `system_prompt.build_system_prompt`
for the base prompt, the panel's own overlay join). Receipt:
`harness/battleplan/runs/2026-09-01/profile_diff.json` (posted on the bus as a
finding — BP2-PANELDESIGN input).

**Finding (computed, not asserted):** across curious/expert/ml the resolved
surface differs **only** in

- **density** — airy / standard / tight (the panel-wide root property),
- the **system-prompt overlay** — curious narration / expert `""` / ml terse, and
- two per-widget knobs, **collapsed** + **prominence**:
  - curious: `token_meter` + `activity_meter` collapsed; `token_meter` /
    `token_pill` quiet.
  - ml: `author_token` / `token_meter` / `token_pill` hero.

Capability is identical in all three (the widget-id set matches
`compositor.known_widget_ids()`), every widget stays `visible=True` (folding is
collapse, never hide, L5), and the composed system prompts differ **only** by
the overlay (identical base sha `d06fd7e21aa6f4f3` on this seat — TONE.md
present). No widget ever changes `visible` or `stretch` between profiles.

### Density repolish — the mutation record (08-04 / J4.3)

The 08-04 finding: a Qt dynamic property set on the panel root does **not**
cascade to children, so the density QSS descendant rules never repaint unless
the whole subtree is repolished. `compositor.compose()` fixes it by stamping
`density` on the root then calling `_repolish_tree(panel)`.

Test `tests/test_bp2_paneltruth_density_repolish.py::test_compose_stamps_density_and_repolishes_root_and_descendants`
observes that the panel **root** — repolished ONLY by `_repolish_tree(panel)`,
never by `_apply_spec` (which touches region/widget targets) — and its
descendants are repolished during `compose()`.

**Mutation run (recorded):** with the call neutered in `compositor.py:compose`

```
        # whole subtree, root first.
-       _repolish_tree(panel)
+       pass  # BP2-PANELTRUTH mutation proof: _repolish_tree(panel) removed
```

the test went RED:

```
E   AssertionError: compose() must repolish the panel ROOT so the density property takes
E   assert 'PANEL_ROOT' in {'_build_context_ribbon', '_build_faces', '_build_mode_bar',
                            '_build_rail', 'activity_meter', 'author_token', ...}
FAILED tests/test_bp2_paneltruth_density_repolish.py::test_compose_stamps_density_and_repolishes_root_and_descendants
```

`compositor.py` was then restored from HEAD (`git checkout`) and the file
re-ran GREEN (7 passed). The same mutation is also pinned automatically without
editing source by `test_compose_repolish_call_is_load_bearing` (monkeypatch
neuters `_repolish_tree` -> root + descendants no longer repolished).

### Profile persist

`tests/test_bp2_paneltruth_profile_diff.py::test_profile_persists_select_save_load_same`
drives `settings.SwitcherState` (schema v3): construct -> `select("ml")` (write
through) -> `load_settings` reads `ml` -> a fresh `SwitcherState` (reopen) lands
on `ml`. (`tests/test_rope_switcher_state.py` already pins SwitcherState; this
is the BP2 acceptance restatement.)

## T2 — TOKEN face + rail refresh on task completion

`usage_sink` already carried a real per-task token receipt and `face_token`
already read it on tab-open. T2 adds the completion path: `claude_worker`
emits `stream_done` -> `synapse_panel._on_done` -> new `_refresh_token_surfaces`
-> `token_readout.refresh_surfaces` refreshes the TOKEN face and sets the rail
meter (`token_meter` / `_meter_lbl`) + pill (`token_pill` / `_face_pills['token']`)
text from `USAGE_SINK.snapshot()`.

- **Event-driven, never a timer** (V3: a probe must not trip the limit it
  reports on). Pinned by `test_refresh_rides_token_readout_and_is_not_timer_driven`.
- **UNKNOWN stays UNKNOWN** (R162): an unmeasured task leaves the meter empty and
  the pill at its base label — never a fake zero, never a fuel-gauge bar/ratio
  (V3-F4: headroom is not obtainable).
- New module `python/synapse/panel/token_readout.py` holds the pure display rule
  (Qt-free, hou-free), so it tests headless; `synapse_panel` supplies the live
  surfaces. `claude_worker.py` is **untouched** (no `hou.` introduced) and the
  edit to `synapse_panel.py` is confined to `_on_done` + the new method — the
  W5L-LIFE lifecycle/timer surface is not touched.

`tests/test_bp2_paneltruth_token_refresh.py` proves it headless (the real
`_on_done` on a fake self, fed sink -> meter `155` + pill carries the figure +
face refreshed; unfed -> empty meter, base pill, no bar) and end-to-end under
hython (real `FaceToken` + real `Pill`; skips in stock CPython — skip != pass).

## T3 — docked-open float fix

`houdini/scripts/python/synapse_shelf.py::open_panel` used to
`createFloatingPaneTab` whenever no PythonPanel pane existed — a loose window a
restart loses. Now three branches, in preference order: (1) an existing Synapse
tab is surfaced (`setIsCurrentTab`), never re-created; (2) a PythonPanel tab is
docked into the Network Editor's pane (`pane().createTab` + `setActiveInterface`),
or any existing pane; (3) float ONLY when no pane exists. Pinned by
`tests/test_bp2_paneltruth_float_fix.py` (mocked hou, all three branches + the
no-Network-Editor guard). Help line added at `docs/help/panel_docking.md`.

## T4 — contract

`.synapse/contracts/panel-truth.yaml` (`git add -f`; `.synapse/` is gitignored),
every feature `passing: false` — the flips are Joe's word.

## GUI (gui_required — UNKNOWN headless)

Ctrl+K opens docked, the TOKEN face + rail meter/pill update after a task, and a
profile switch survives close -> reopen: these are Joe's eyes in the live
22.0.400 GUI. Recorded UNKNOWN here — no headless probe can honestly assert
them, and a skipped Qt end-to-end is skip != pass.

## Suite

`pytest -q` on the branch: **6866 passed, 186 skipped, 0 failed**
(`test_expert_resolved_equals_v5420_snapshot` included, green).
