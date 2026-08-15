# Panel ↔ Codebase Capability Parity — 2026-08-14

*Lane B of the freeze-relief mission. 3-agent read-only workflow
(`panel-capability-parity-wf_63b2002b-40c.journal.jsonl`), all offline
code evidence — bridge down, nothing live. Denominator derived from the
registry AST, not the live catalogue (the 384/218/169 numbers are this
host's installed packages, not H22).*

## Verdict

**The panel is within 5 tools of 1:1 with the true model-dispatchable surface.**

All **124** registry tools are advertised verbatim to interactive chat.
Every registry command has a WS handler. The **131-command** WS denominator
reconciles exactly: 124 advertised + 7 WS-only.

The gaps are real but small, and they cluster in three places:

1. **The Solaris compose trio** is WS-only while panel policy code holds
   dead prefixed aliases that anticipated registry entries never added.
2. **tops_pause_cook / tops_resume_cook** are WS-only with zero panel
   surface — only Cancel cook got the overflow-menu treatment.
3. **The read-only reconciliation comment** in `mcp/server.py` is doubly
   stale (says 38/35/3; actual is 40/36/4).

None of these are behavioral risk today — the dead aliases can never
resolve, the live `read_only_set_divergence()` mechanism is correct. It's
documentation debt plus unfinished promotion.

## The denominator (code-derived)

| Set | Count | Source |
|---|---|---|
| MCP registry (advertised tools) | **124** | `_tool_registry.py` TOOL_DEFS — AST-verified at HEAD; exactly matches the CLAUDE.md header claim |
| WS commands (total registrations) | **131** | `server/handlers.py` |
| WS-only (not model-dispatchable) | **7** | `tops_pause_cook`, `tops_resume_cook`, `solaris_shotsetup_karma_xpu`, `matlib_bind`, `assess_render_ready`, `route_chat`, `get_help` |
| Registry read-only set | **40** | readOnlyHint=True, field index 5 of the 8-field tuple |
| bridge_adapter read-only set | **36** | `bridge_adapter.py:51-71` |
| Read-only divergence | **4** | `synapse_validate_frame`, `synapse_propose_graph`, `cops_temporal_analysis`, `synapse_render_processes` |

WS `_READ_ONLY_COMMANDS` = 40, and deliberately includes the kill-switch
trio (`render_farm_cancel`, `render_stop`, `emergency_halt`) with a
documented rationale. RBAC viewer floor = 31. OPERATION_GATES = 20
(default REVIEW, `touches_disk` → APPROVE).

## How the panel actually advertises tools

**There is no filter.** `tool_bridge._build_cache()` converts every entry
of the canonical TOOL_DEFS (124) plus up to 6 `synapse_group_*` knowledge
tools into Anthropic format once at import and freezes it as `_TOOLS_CACHE`.

| Path | What the model sees |
|---|---|
| **Interactive chat** (artist-initiated) | `_start_worker` passes the FULL cache with `enforce_worker_policy=False` — the artist is the human in the loop, no advertisement filter (`synapse_panel.py:2248-2256`) |
| **Autonomous worker** (no human) | `get_anthropic_tools_for_worker()` subsets via `worker_policy.is_tool_allowed_for_worker`: standard mode allows registry tools whose derived OPERATION_GATES level is `inform`, always allows the 6 group tools, plus a 2-item Solaris composite-builder exception (`synapse_solaris_build_graph`, `synapse_solaris_assemble_chain`) (`tool_bridge.py:97-114`, `worker_policy.py:50-71`) |

The old router-based narrowing (`tool_filter.filter_tools`, MOERouter
domain subsets) is **retired/deleted 2026-08-01** — zero repo references.
What survives (`classify_tool`) only feeds the Ctrl+K palette taxonomy.

**Execution path** of what is advertised: `ClaudeWorker._execute_tool_block`
tries `try_mcp_tool_call` first (local MCP HTTP endpoint, worker-thread
safe), then falls back to Qt-signal main-thread dispatch resolving names
through `get_tool_dispatch` → TOOL_DISPATCH.

## Gap classification

| Class | Items |
|---|---|
| **never-promoted-to-registry** — panel policy anticipated them, registry entry never landed | `solaris_shotsetup_karma_xpu`, `matlib_bind`, `assess_render_ready` |
| **WS-only by intent** — transport plumbing / non-model surface | `route_chat` (reached via `ws_bridge.send_command` at `chat_panel.py:884, :988` — chat plumbing, correctly excluded), `get_help` (functionally covered: Help button opens local docs via `hou.ui.showHelp`) |
| **WS-only, unfinished panel wiring** | `tops_pause_cook`, `tops_resume_cook` — zero panel references; only Cancel cook got the menu item |
| **Dead code** | `bridge_adapter.py:155-157` `_TOOL_TO_OPERATION` entries + `:163-165` `_DISK_WRITING_TOOLS` — prefixed aliases for the compose trio that can never resolve |
| **Stale-comment drift** | `mcp/server.py:112` (says 38, actual 40), `:121-123` (says 35/3, actual 36/4 — omits `synapse_render_processes`), `tool_bridge.py:53` ("Registry tools (102)", actual 124) |
| **Provider limitation** | None at tool-set level — all 5 providers translate the same schema cache; vision attach is capability-gated per model_identity but gates media, not tools |
| **Filter-excluded by design** | None — interactive path deliberately bypasses worker policy |

## Findings ranked

**F1 — Dead panel policy for the compose trio (bridge_adapter).**
`_TOOL_TO_OPERATION` maps three prefixed names that exist nowhere in
TOOL_DEFS; `get_tool_dispatch` can never resolve them. Evidence the tools
were planned for registry promotion and never landed. Two dispositions:
promote the trio into TOOL_DEFS (they're real WS handlers at
`handlers.py:741-743` / `handlers_solaris_compose.py:33-35`), or delete
the dead aliases and accept WS-only. Either closes the lie; today the
policy file describes a surface that doesn't exist.

**F2 — pause/resume cook unreachable from the panel.**
`tops_pause_cook` / `tops_resume_cook` (handlers.py:694-695) have no
registry entry and no UI hook. If the artist can cancel a cook from the
overflow menu but can't pause one, that's an asymmetric surface — worth
either promoting both or noting the asymmetry as intent.

**F3 — mcp/server.py reconciliation comment doubly stale.**
Says 38 read-only / 35 bridge / 3 divergent; actual is 40 / 36 / 4 with
`synapse_render_processes` newly divergent. The mechanism
(`read_only_set_divergence()`) is live and correct — only its
documentation lags. One-line comment fix.

**F4 — tool_bridge.py header count drift.**
"# Registry tools (102)" vs. actual 124. Cosmetic.

**F5 — 9 panel modules with no confirmed in-panel importer.**
`scene_doctor.py`, `working_indicator.py`, `bookmarks.py`,
`decision_log.py`, `cross_scene.py`, `apex_explainer.py`, `shot_login.py`,
`save_shot.py`, `exposure_seam.py` — grep found no `panel.<mod>` /
`panel import <mod>` matches. Mount-vs-dead status is **UNKNOWN**, not
dead: they may be standalone entry points. Needs a live-panel check or a
side-channel import scan before any claim.

## Not load-bearing (recorded, not re-verified)

- `shared/constants.py` READ_ONLY_OPS count (regex missed the format).
- README/docs capability claims beyond the CLAUDE.md 124 header.
- F5's nine modules (see above).

## What this means for the mission

For the freeze work (Lane A), the panel side is clean: tool advertisement
isn't a variable. The full 124 tools flow through one cache, one dispatch,
one worker — nothing in the parity gap touches the main-thread marshal
the freeze lives in. The two findings worth routing to a forge are
F1 (dead aliases → delete or promote) and F3/F4 (comment freshness);
F2 is a design call for Joe, not a bug.

---

## Post-release dispositions (v5.48.0 loop closure, 2026-08-14)

- **F3/F4 — closed.** Both stale comments were refreshed in the freeze-relief
  branches themselves (`mcp/server.py` now states 40/36/4; `tool_bridge.py`
  header says 124). Nothing left to do.
- **F1 — resolved as *staged*, not dead.** Deleting the compose-trio aliases
  failed `test_compose_offmain_wp3.py::test_bridge_adapter_marks_touches_disk`,
  which pins that the shotsetup tool gets `touches_disk=True` elevation. The
  test is evidence the entries are intentional forward-staging: WS-side real
  handlers, registry promotion pending. `bridge_adapter.py` now says that
  in plain words at both sites (comment-only change, zero behavior delta).
  The remaining design call — *promote the trio into TOOL_DEFS* — is Joe's.
- **F2 (pause/resume UI wiring)** and **F5 (nine unmounted-module check)** —
  open, Joe's calls. F2 needs an overflow-menu decision; F5 needs a live-panel
  or side-channel import scan before any dead/mount claim.

*Dispositions shipped on branch `chore/parity-dead-aliases`.*

*Evidence: full workflow result at
`C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE/panel-parity-full.json`;
journal `panel-capability-parity-wf_63b2002b-40c.journal.jsonl` (3 agents,
0 errors). 377,393 subagent tokens.*
