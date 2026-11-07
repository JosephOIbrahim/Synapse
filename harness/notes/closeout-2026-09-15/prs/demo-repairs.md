## What

`fix/demo-repairs-20260909` (one commit, 72de0881) rebased onto master `d8ebb74a` (v5.70.1 + fixes) as `rebase/demo-repairs`, head `a3ad7796`. Closeout **Stop 2** in `harness/notes/closeout-2026-09-15/PLAN.md`; the room's correction for this branch is in `harness/notes/first-principles-2026-09-15/AUDIT.md`.

The branch adds `houdini_layout_network` (bounded native network layout: position / color / comment / network box only, single labelled `hou.undos.group`, artist-box refusal, `dry_run`), scoped memory (`synapse_decide` / `synapse_recall` `scope=scene|project|all` -> `MemoryTier.SHOT|SHOW`), a stricter refuse-writes-on-damage posture in `memory/store.py`, Save/Load memory ownership (`host/memory_lifecycle.py`), serialized Moneta text search, and main-thread-marshalled cold journal reads. Branch doc: `docs/demo-repairs.md`.

**Exactly the two expected conflicts**, both one line. Resolution per the LAW: master's line kept, number recomputed from the producer (129), not typed.

| File | Conflict | Resolution |
|---|---|---|
| `CLAUDE.md:3` | v5.70.1/128 vs v5.67.4/129 | master's line, count -> **129** |
| `README.md:109-115` (not :121 -- master rewrote the README in v5.70.1) | master's "Ask SYNAPSE to remember a decision" vs the branch's "129 tools, two paths" paragraph | master's block kept, branch paragraph dropped; master's own count line at `README.md:128` bumped -> **129** |

`git diff master..HEAD -- CLAUDE.md README.md` is exactly those two `128 -> 129` substitutions.

## Evidence

```
PYTHONPATH=python python -c "from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"
  -> 129   (m.__file__ resolved to this worktree's registry, not the editable install)

PYTHONPATH=python python -m pytest tests/test_network_layout.py tests/test_demo_memory_scope.py \
  tests/test_demo_memory_recall.py tests/test_memory_lifecycle.py tests/test_memory_owner_dispatch.py \
  tests/test_moneta_search_serialization.py tests/test_session_journal_main_thread.py \
  tests/test_phase0c_doc1_toolcount.py -q
  -> 131 passed, 2 warnings in 6.76s

PYTHONPATH=python python -m pytest tests/test_store_degraded_load.py tests/test_memory_handle_law.py \
  tests/test_loop_integration.py tests/test_rsi_stage0_panel.py -q
  -> 55 passed, 6 skipped, 2 warnings in 2.09s

git log master..HEAD --oneline   -> a3ad7796 Repair demo layouts and scoped memory ownership
git diff --stat master..HEAD     -> 32 files changed, 2771 insertions(+), 242 deletions(-)
git status --short               -> (clean)
```

## Line-by-line review of the four modified existing test files (PLAN Stop 2)

- **`tests/test_store_degraded_load.py`** -- the pin **flips direction, stricter**. Old: a garbled *plaintext* line (no MAGIC_PREFIX) was "a separate concern (C32)", `_degraded_load is False`, `save()` allowed. New: same input -> `_degraded_load is True`, `save()` raises `RuntimeError(... DEGRADED ...)`, and the source bytes are asserted byte-identical afterwards. `store.py` backs it: `_require_writable_load()` now gates `save()` and the append path (`_wait_loaded()` + refuse while loading or degraded), `_degraded_reason` recorded, log text changed to "Refusing writes; recover the source or encryption key, then reopen." Artist-facing consequence: **one torn plaintext line makes the memory store read-only until the file is recovered** -- by design per `docs/demo-repairs.md` ("Recovery is explicit; a new decision does not silently repair a damaged store"). This is the branch's stated main risk and the test now pins the conservative side of it.
- **`tests/test_memory_handle_law.py`** -- autouse fixture now `monkeypatch.setattr(store_mod, "HOU_AVAILABLE", False)`. Coverage narrows: the handle-law concurrency tests no longer run against conftest's fake `hou`. Rationale in-file: fake hou is not a main-thread dispatcher; host construction is exercised with a real pump in `tests/test_memory_lifecycle.py` (new, 428 lines, passes).
- **`tests/test_loop_integration.py`** -- `rebind_project_memory` contract changed: `snapshot_copied` is now **False**; publication follows a real close/reopen (`len(replacements) == 2`, first one `_closed`); the pending outbox (`loop/pending/source-only.json`) **stays at the source** and is not carried to the new location. Matches the doc ("Pending outboxes and approvals stay in their original locations").
- **`tests/test_rsi_stage0_panel.py`** -- public `synapse_recall` schema widens from `{"query"}` to `{"query","scope"}` with `scope.enum == ["all","scene","project"]`. The guard's purpose (no private lookdev-assistance controls in the model-facing contract) is kept.

## The five touched files the verdict missed (reviewed by diff)

- `python/synapse/session/tracker.py` (+89): `_scope_tier()`; `refresh_memory_owner()`; `handle_memory_decide` validates scope + non-empty text, returns `recorded=False` (instead of raising) on persistence failure, reads `hou.hipFile.path` via `_read_on_main`, uses the host-resolved project dir instead of raw `$JOB` for the Markdown mirror, collects mirror failures as `warnings`, invalidates the context cache; recall/search pass `tier=`.
- `python/synapse/memory/moneta_store.py` (+21): `search()` embeds outside the lock, then takes the owner lock (`_search_locked`) so text search + `signal_attention` no longer bypass add/prune/save/close serialization; raises if closed. Docstring at `:169` corrected (the WAL can hold attention updates). **Nit left as-is:** the inline comment at `:289-294` still says "signal_attention, which SYNAPSE never calls" -- contradicted by `:169` and by the actual call at `:966`. Not fixed here (rebase-only branch); one-line follow-up.
- `python/synapse/memory/scene_memory.py` (+8): `write_decision(..., *, project_dir=None)`; writes `**Memory ID:**` into the md entry.
- `python/synapse/server/handlers.py` (+18): registers `layout_network`, `NetworkLayoutMixin`, PIPELINE audit category; the automatic `bridge.log_action` now runs via `run_on_main(label="memory:automatic_action")` with an owner/`_memory_binding` identity check, failure degrades to a warning and keeps the audit entry. This runs on `_log_executor` (ThreadPoolExecutor, 2 workers) -- worker -> main, not main -> main, so the H22 self-deadlock class does not apply; it does add one main-thread wait per command to the fire-and-forget log path (can queue behind a busy main thread; observation, not a red).
- `mcp_tools_scene.py` (+4): tool added to the scene group's `TOOL_NAMES` / `DISPATCH_KEYS` (`identity` shape) and the group knowledge string.
- Also: `rbac.py` puts `layout_network` in `_ARTIST_COMMANDS` (same tier as `set_parm`/`create_node`); `core/protocol.py` adds `CommandType.LAYOUT_NETWORK`.

## Ruling needed (consent tier)

**`houdini_layout_network` -> `set_parameter` (INFORM) at `python/synapse/panel/bridge_adapter.py:83` while it re-boxes the whole network -- KEEP or RAISE?**

What the handler actually does (`server/handlers_network_layout.py:60-160`):
- Mutates only `position`, `color`, `comment`, `display_comment` flag, network boxes, and its own layout metadata (`mutation_scope` in the result). Never node names, parms, connections, output flags.
- **Destroys network boxes** in two cases: boxes the caller names in `replace_boxes` (`destroy(destroy_contents=False)`, only if every item is in the selection), and boxes the tool itself owns that end up empty.
- Refuses before any change when: an artist box contains unselected items; a target box name exists but is not tool-owned; Undo is disabled. `dry_run` returns the plan without touching the scene.
- One `hou.undos.group("SYNAPSE: <summary>")` -- grouping only, no rollback on exception (same caveat as the rest of the tree).

For comparison: `delete_node` is REVIEW; `create_node` / `connect_nodes` / `set_parameter` are INFORM. The map is per-tool, not per-payload, so a "REVIEW only when `replace_boxes` is non-empty" middle path would be new code, not a one-line remap. KEEP is defensible (content-preserving, single undo, refusal guards, dry_run); RAISE is defensible if destroying a named artist box counts as delete-class. Human call.

## NOT checked

- **Full stock suite** (`pytest tests/`) and the **hython seat suite** -- not run per the closeout LAW (shared-log contention). The original commit message's "8686 stock tests pass, 447 skip" was measured on the pre-rebase base (v5.67.4), not on this head. Treat as UNVERIFIED until the parent/CI runs it serially.
- **Live layout contract on H22.0.400** (`hython scripts/probe_network_layout.py`, undo grouping, artist-box refusal) -- not run. `hou`-side behaviour is unproven by this rebase.
- **Bodies not reviewed line-by-line:** `memory/store.py` beyond the degraded-load hunks (+345/-~100 rewrite), `host/memory_lifecycle.py` (+394), `server/network_layout.py` plan logic, `handlers_network_layout.py` outside `:60-160`, `handlers_memory.py`, `host/memory_loop.py`, `panel/session_journal.py`, `panel/system_prompt.py`, `scripts/probe_network_layout.py`.
- **CI** -- nothing pushed.
- `RELEASE-DRAFT-vNEXT.md:64` records "129 -> 128 MCP tools" for 5.56.0 (historical, still true for that release) -- untouched; after this merge the net is 128 -> 129 again and no release note in the tree says so yet.
- No new commit was authored (rebase folded the resolution into the original commit), so no `Co-Authored-By` trailer was added; the commit message is the branch author's, unchanged.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## CTO ruling (pre-approved 2026-09-15; overrule by comment)

**KEEP `houdini_layout_network` at INFORM.** Rationale: the handler mutates position/color/comment/network-box only, never names, parms, connections or flags; the whole operation is one labelled `hou.undos.group` so a single Ctrl+Z reverses it; it refuses before any change when an artist box would be touched; `dry_run` exists. INFORM matches `set_parm`/`create_node`, which have the same one-undo reversibility. RAISE to REVIEW would add a consent card to an operation the artist can already reverse in one keystroke. Revisit if the tool ever gains a destructive scope beyond tool-owned boxes.
