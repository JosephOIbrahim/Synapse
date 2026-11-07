## What

`rebase/cto-render` is the eight-commit farm feature (`fix/cto-render-20260908`, original tip b07eaa40) replayed onto master, plus two follow-ups: the builder's adaptation commit (tool recount to 135, farm tests adapted to master's typed MCP outcomes, hweb rig seeded) and this repair round's commit `d024641e`.

## Repair round (this commit)

**Blocker 1 -- composed regression in `tests/test_loop_mcp_observation.py` (9 failed / 5 passed on a16e34ca vs 14 passed on master).**

The refuter's pinpoint (`tool_executor.py:630`) was the wrong file; the mechanism was right. That rig execs `handlers.py::SynapseHandler.handle` and `mcp/server.py::MCPServer._handle_tools_call` through an AST loader that strips module-level imports, and the farm commits added three module-level imports the rig never seeded:

- `is_farm_control` -- `python/synapse/mcp/server.py:45`, read at `:653` and `:698`
- `SynapseServiceError` -- `python/synapse/server/handlers.py:43`, caught at `:586`
- `FARM_CONTROL_COMMANDS` -- `python/synapse/server/handlers.py:52`, read at `:523` and `:609`

Fix (test-side, same shape as the a16e34ca fix to `test_loop_hweb_dispatch.py`): seed the real objects into `handler_globals` / `server_globals`, and extend the `synapse.panel.bridge_adapter` stub with `is_farm_control` (real) + `execute_farm_control` (raises `AssertionError` if ever taken) so `dispatch_tool`'s four-name import no longer drops the marshalled path into the ImportError fallback. An AST free-name audit of both exec'd methods now reports `handle()` fully seeded; the only unseeded names in `_handle_tools_call` sit behind `_STALL_DETECT_AVAILABLE=False` / SSE branches that master's baseline never reaches either. No production code changed for this blocker.

Sweep: every test file that rigs `tool_executor`, `hwebserver_adapter`, `bridge_adapter` or `_execute_single` (33 files) -> **810 passed, 7 skipped**. No sibling rig has the hole.

**Blocker 2 -- public-repo path leak in `docs/tops/`.**

All `C:/Users/User/OneDrive/...` link targets are gone: in-tree targets became repo-relative links (`../../python/synapse/farm/backend.py#L37`, `native_driver.py#L544`, `models.py#L131`, `service.py#L25`, sibling docs by filename -- each target line verified to exist and be the cited object), out-of-tree targets became plain text "(local research notes, not in tree)", the pypanel path is `$HOUDINI_USER_PREF_DIR/python_panels/tops_farm.pypanel`, and all 19 `G:/KARMA_TRIAGE_FARM/...` links in `TRIAGE_FARM_MIGRATION.md` are inline code with no link. `ARTIST_RENDER_IMPLEMENTATION.md:54` already had `G:/` as inline code and is untouched. Post-commit scan `git diff master..HEAD | grep -nE "sk-|AKIA|ghp_|xox[bp]-|BEGIN [A-Z ]*PRIVATE KEY|C:\\\\Users|/Users/"` -> **zero hits**.

**Non-blocking, done -- rebased onto master.** `git rebase master` replayed 10/10 commits with zero conflicts. `git diff --stat master..HEAD` is now `47 files changed, 6492 insertions(+), 41 deletions(-)` (the 702 master-side deletions are gone).

## Evidence

| Check | Result |
|---|---|
| `len(TOOL_DEFS)` from the registry | 135 |
| `test_phase0c_doc1_toolcount.py` + `test_farm_integration.py` | 69 passed |
| `test_loop_mcp_observation.py` + `test_loop_hweb_dispatch.py` + `test_offmain_fallback.py` | 27 passed (was 9 failed / 5 passed on the first file) |
| Branch-touched pytest files (9) | 231 passed, 6 skipped |
| Refuter's composed batch (18 files) | 549 passed, 6 skipped |
| Exec-rig sweep (33 files) | 810 passed, 7 skipped |
| Post-rebase re-run (5 files) | 96 passed |
| Master baseline, `test_loop_mcp_observation.py` | 14 passed |
| Scope grep (VERSION / harness/state / .claude / settings) | only `tests/test_farm_usd_settings.py`, a filename regex match, not a settings file |
| Guard grep on added python lines | 4 hits, all pre-existing farm feature content: `subprocess.Popen` (farm backend / native driver own the Houdini processes) and `run_on_main(inspect, timeout=5.0, label="farm_inspect")` |

## Note: master moved during this session

`git rev-parse master` read `841f742e` at session start; after `git rebase master` the merge-base is `5ec9c6cd`, and `git log master..HEAD` lists exactly the ten branch commits. By rebase mechanics that means master's tip is now `5ec9c6cd` (one or more commits landed after 841f742e). The rebase, the post-rebase runs and the 14-pass baseline all ran against that current tip. I did not read what 841f742e..5ec9c6cd contains.

## Note: sibling worktree

`rebase/cto-render` was also checked out in `.claude/worktrees/wf_4ef50c87-4e2-4` (the builder's worktree, at a16e34ca). I checked the branch out here with `--ignore-other-worktrees` and the ref now points at d024641e, so that worktree's index and working copy are stale relative to its own branch. Before removing or reusing it, `git status` there first (the isolation guard would not let me inspect it); if clean, `git worktree remove` it or `reset --hard rebase/cto-render`.

## Ruling the human must give

`_MCPLocalClient.available` (`python/synapse/panel/tool_executor.py:210-216`) keeps the cached port when discovery is lost and lets the first failed `_post` invalidate it. That is a third behaviour (master: `return port is not None`; original tip: cached forever), documented in its own docstring and protected by the typed `except MCPUnavailable: return None` fallback, but **no test pins it**. Left as-is this round (call budget). Either accept it unpinned, require a pin test ("adapter stopped -> cached port retained -> first `_post` raises `MCPUnavailable` and clears it"), or ask for master's `return port is not None` back.

## What was NOT checked

- The builder's exact two 23-file batches were not recorded in `verdicts.json` / `PLAN.md`; the branch-touched set, the refuter's composed batch and the 33-file exec-rig sweep were run instead.
- Full `pytest tests/` and the hython seat suite (by law; run serially on the parent's side / CI).
- `tests/native_render_workspace.py` and anything needing hython -- not run.
- Line-level three-way review of `tool_executor.py` / `hwebserver_adapter.py` against b07eaa40 -- stat-level only, backed by the green rigs above.
- Contents of master's move 841f742e -> 5ec9c6cd.
- The sibling worktree's uncommitted state.

🤖 Generated with [Claude Code](https://claude.com/claude-code)