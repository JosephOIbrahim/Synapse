# Release preparation: v5.85.5

Publish three commits on top of v5.85.4 (`f3da32b8`). Joe's word: "You are CTO
use recommended", after "Should I push all three, fix that release page, and
cut the next release? I'd call it 5.85.5" (2026-09-29). He had said "Retire th
older panel" for the panel itself.

| Commit | What it does |
|---|---|
| `5bb0f9c0` | Corrects the v5.85.4 release notes, the CHANGELOG line and the seat record: the Clear All button was on the older panel |
| `036724b2` | BP12 items 20 and 22: removes `python/synapse/ui` (8 files), turns the four `synapse.*` panel names into an `AttributeError` with a pointer, drops the mypy override and five ratchet baseline lines; 6 tests |
| `74d1a211` | Comment only: the lazy-import note in `synapse/__init__.py` no longer names the UI |

## Evidence

- **The premise.** `git grep` finds one caller of `store.clear()`, in
  `python/synapse/ui/panel.py`. `houdini/python_panels/synapse_panel.pypanel`
  loads `synapse.panel.synapse_panel`. Nothing tracked builds the older panel.
  I had told Joe the button would hang Houdini and did nothing on Moneta; that
  overstated it, and the plan doc records the correction.
- **hython.** Houdini 22.0.400: `synapse.panel.synapse_panel` imports,
  `onCreateInterface` is present, `synapse.ui` is not in `sys.modules`,
  `synapse.create_panel` raises the pointer (`hython_panel_import_probe_v1.py`).
- **Mutation.** A detached worktree at the previous HEAD with the new test file:
  5 of 6 fail; the pypanel test passes on both trees.
- **Tests.** The `tests/` suite passed on Windows with Python 3.14 with the
  Houdini-only tests deselected: 10,177 passed, 457 skipped, 119 deselected,
  5 xfailed, 2 xpassed, 0 failed (339 s), before `74d1a211`. After it, the
  retirement, feature and version tests passed (137).
- **Ratchet.** `broad_total` 1379 to 1366, `silent_total` 995 to 987.
- **Survey.** `INVENTORY.md` still lists the old panel; it is marked an archived
  snapshot and was left alone. Historical reviews and ledgers that mention the
  panel were left alone.
- **The v5.85.4 release body.** Replaced from `docs/releases/v5.85.4.md` with
  `gh release edit`, on Joe's word above.
- **Advice.** Fable 5.1 reviewed the approach and the result. Jev was not used.
- **Known, not fixed.** BP12 items 18, 19 and 21, and the open queue in the plan.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
