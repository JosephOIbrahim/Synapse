## What / why

Builds **TRUST-2, the Undo Receipt** -- ranked #1 in `harness/notes/closeout-2026-09-15/PLAN.md` ("The highest-leverage item"), lens `trust` in `artist_findings.json`. Fact base (verified again on this branch): every mutating handler already computes the artist's answer to *"what does one Ctrl+Z reverse?"* as its `hou.undos.group("<label>")` label (48 call sites under `python/synapse/server/`) and discards it; before this branch a grep for `Ctrl+Z|undoable|can be undone` across `*.py` returned zero artist-facing strings.

Also carries **TRUST-5** (the two-line CLAUDE.md correction) and the **TRUST-4 disclosure field** (`rolls_back_on_failure`, static per code path, as PLAN specifies).

### The helper (pure, no `hou`, unit-tested)

`python/synapse/server/handler_helpers.py`:

```python
undo_receipt(label, *, rolls_back_on_failure=False) -> {
  "undo": {
    "label": "synapse_set_parm",                       # the exact group label, verbatim
    "artist": "One Ctrl+Z reverses: set parameter",     # plain words derived from the label
    "rolls_back_on_failure": False,                     # STATIC property of the code path
    "on_failure": "If it fails partway, the partial work stays in the scene until you undo it."
  }
}
```

`undo_label_words()` strips the `synapse_` / `SYNAPSE: ` namespace and unpacks abbreviations (`parm`→parameter, `copnet`→COP network, `usd`→USD, ...). It **records** a group; it never opens one. No new undo group, no new gate.

The prefix string and the panel-side reader (`undo_receipt_line(result)`) live in `python/synapse/core/tool_results.py` (json-only module, already imported by the worker) so server and panel share one spelling and cannot drift. The reader only honours a receipt that carries the minted prefix -- a hand-built `undo` block renders nothing.

### Handlers that now carry the receipt

Exactly the set CLAUDE.md §Identity names as undo-wrapped:

| handler | file | label |
|---|---|---|
| `_handle_create_node` | `handlers_node.py` | `synapse_node_create` |
| `_handle_delete_node` | `handlers_node.py` | `synapse_node_delete` |
| `_handle_connect_nodes` | `handlers_node.py` | `synapse_node_connect` |
| `_handle_set_parm` (all 3 result sites) | `handlers.py` | `synapse_set_parm` |
| `_handle_set_keyframe` | `handlers_render.py` | `synapse_set_keyframe` |

All five are `rolls_back_on_failure=False` (grouping-only paths) -- the receipt says so in artist words. Every `hou.undos.group("...")` literal is untouched: `tests/test_node_undo_grouping.py::test_set_parm_now_wraps_in_handlers_py` pins the literal, and the new `test_set_parm_group_literal_survives_the_wiring` pins 3 groups + 3 receipts in that function body.

### Handlers that do NOT yet carry it (still discard their label)

`handlers_cops.py` (17 sites), `handlers_usd.py` (12), `handlers_material.py` (3), `handlers_hda.py` (2), `handlers_solaris_graph.py` / `_compose.py` / `_assemble.py` (4), `handlers.py` `synapse_batch` + `synapse_execute`, `handlers_render.py` `SYNAPSE: render` + `configure_render_passes`, `solaris_lookdev.py`. These include the *rolls-back* population (build_graph, the two compose handlers, the 9 cops sites, hda_package, execute_python) -- wiring them is where `rolls_back_on_failure=True` first becomes reachable. Deliberately out of scope per the task ("do NOT touch handlers that are not undo-wrapped" / start with the five named).

### Panel surface (smallest)

- `claude_worker.py`: the two `"done"` `tool_status` emits (MCP path + Qt-executor fallback) now lead the detail string with the receipt: `with_undo_receipt(summary, result)` → `"One Ctrl+Z reverses: set parameter · {request summary}"`. The request summary survives after the separator so `_populate_review`'s node-path scan and DECISION credit still see it.
- `activity.py`: `tool_status(name, phase, detail=None)` renders `Finished: Set a parameter — One Ctrl+Z reverses: set parameter` when the detail leads with a minted receipt; the two-argument form is byte-identical to before (pinned). `running`-phase detail (`json.dumps(tool_input)[:120]`) never leaks onto the line (pinned).
- `face_work.py`: `set_tool_status` passes `detail` through (one-token change).

### TRUST-5 (CLAUDE.md, byte-neutral)

Line 13's `(VERIFIED-RUNTIME, L2 2026-07-25: failed Solaris builds orphan partial networks; the undo group does not clean up.)` is replaced with the honest residual: `build_graph` + the Solaris compose handlers `performUndo()` **one** step on failure (evidence read on this branch: `handlers_solaris_graph.py:669-673` snapshots `undoLabels()`, `:834-841` calls `performUndo()` iff the stack moved; `handlers_solaris_compose.py:89,127` same idiom); a multi-step failure leaves the rest; node/parm/keyframe handlers stay group-only. File went 40026 → 40020 bytes -- it sits at the 40k limit, so the edit had to shrink, not grow. `test_claude_md_section1_records_wrapped_state` pins (`synced by W5-UNDOB`, `_handle_set_parm`, `_handle_set_keyframe`) still hold -- green in the run below.

**Not done for TRUST-5:** the *project-memory entry* PLAN also names lives under `~/.claude/projects/.../memory/` -- `.claude/**` is outside my allowed scope, so it still carries the stale "orphan partial networks" phrasing. A human (or a later pass with that scope) should re-stamp it.

## Evidence

- `python -m pytest tests/test_undo_receipt.py tests/test_activity_labels.py tests/test_node_undo_grouping.py tests/test_undob_live_undo_grouping.py tests/test_offmain_fallback.py tests/test_panel_faces.py tests/test_retry_breaker.py tests/test_worker_tool_policy.py tests/test_panel_stop_honest.py tests/test_panel_worker_ownership.py tests/panel/test_bc_wave.py tests/test_panel_sweep_a.py -q -p no:cacheprovider` → **136 passed, 82 skipped** (skips = PySide-gated panel tests; the four named files are all in the passed set). The extra eight files are the ones that grep `tool_status`, since I touched the worker and the Work face.
- `tests/test_undo_receipt.py` (new): a 16-label → words table, every label pinned to a live `hou.undos.group` call site under `server/`; the no-receipt-without-a-group invariant (`undo_receipt("X")` may only appear in a file that opens `hou.undos.group("X")`); the five wired labels present; AST purity (no `hou`/`undos`/`group` names in the helper bodies); reader/renderer round-trips.
- `tests/test_node_undo_grouping.py` / `tests/test_undob_live_undo_grouping.py`: key-set pins gain `"undo"` and assert `result["undo"]["label"] == rec.groups[0]` -- the receipt names the group the fake recorder actually saw entered.
- Smoke with no `hou` resident: `undo_receipt('synapse_set_parm')` → `{'undo': {'label': 'synapse_set_parm', 'artist': 'One Ctrl+Z reverses: set parameter', 'rolls_back_on_failure': False, 'on_failure': '...'}}`; `'hou' in sys.modules` → `False`; `py_compile` on the 5 edited modules OK.
- `git log master..HEAD --oneline` → `18f39adf feat(trust): the Undo Receipt -- tell the artist what one Ctrl+Z reverses`; `git status --short` → clean. Base is `329bd5b3` (master had advanced past the worktree's original `d8ebb74a` by the time of `git checkout -b feat/undo-receipt master`; the branch is one commit on top of current master).

## Ruling needed

none

## What was NOT checked

- **No hython / live Houdini.** The receipt is asserted against fake `hou` recorders, never against a real `undoLabels()` delta. The claim "one Ctrl+Z reverses X" for the five handlers rests on W5-UNDO/W5-UNDOB's existing grouping evidence, not on a new probe.
- **Full `pytest tests/` and the hython seat suite were not run** (per the eleven-agent log-contention law); the parent runs them serially.
- **The panel line was not seen in a live Qt session** -- `face_work.set_tool_status` is exercised only through `tests/test_panel_sweep_a.py` (many of whose cases skip without PySide) and the pure `activity.tool_status` tests.
- `_populate_review` now receives `"One Ctrl+Z reverses: … · {summary}"` as the done-detail for mutating tools; its `[:70]` / `[:90]` truncations mean the receipt words lead and the summary may be cut in the review flags. Read, reasoned about, not rendered.
- The stdio/out-of-process MCP path: the receipt rides in the handler result dict, so it should reach any transport that serialises the dict, but only the panel worker's two `done` emits were changed and tested.
- TRUST-3 (REVERT compares the top undo label against the recorded label) and TRUST-7 (`undo_declared`) are enabled by this label but not built here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)