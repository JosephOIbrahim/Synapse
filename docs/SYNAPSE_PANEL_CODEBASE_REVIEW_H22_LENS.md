# SYNAPSE Panel — Codebase Review (Houdini 22 Panel-Engineering Lens)

> Reviewer stance: a SideFX UI panel engineer working on Houdini 22, reviewing a
> third-party Python Panel as if it were an incoming PR. First-principles frame —
> a Python Panel is a **guest on Houdini's main thread**, must **read as native**,
> must **survive the host's lifecycle**, and must **defer to the host's own tools**.
>
> Companion document: `SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md` (design review).
> The two cross-reference each other by section number (§).
>
> Scope verified live: composition root (`synapse_panel.py`), design system
> (`designsystem/tokens.py`, `qss.py`, `components.py`), both faces
> (`face_work.py`, `face_review.py`), provider abstraction (`providers/`),
> streaming worker (`claude_worker.py`), and a full reachability map of the
> ~50-module `python/synapse/panel/` tree.

---

## Verdict

The redesigned `SynapsePanel` is the most disciplined thing in the tree — the
design-system / QSS / token consolidation and the worker-thread isolation are
genuinely good engineering. But it ships on top of a **large inert substrate**
(~18 of ~50 modules dead or alt-entry), it **hardcodes the host's theme instead
of reading it**, and it has **inverted a process-wide liveness concern into a UI
widget**. Approve the spine; send back the foundation.

---

## 1.1 Right: worker-thread isolation

`claude_worker.py` is a `QThread` with an enforced rule: **"No hou.* imports. No
Houdini dependency"** (line 8). Tool calls dispatch either through the MCP
endpoint or are marshalled back via a Qt signal (`tool_requested`) to a
main-thread `ToolExecutor` (`synapse_panel.py:982`). The conversation loop
consumes normalized Anthropic-shaped blocks so engine identity never leaks into
dispatch (`providers/base.py`).

Correct shape for **Law 1 (main-thread sanctity)**: the one genuinely slow,
blocking thing — the LLM round-trip — is off the UI thread, and `hou` is only
ever touched in main-thread slots and timers. This is the single most important
thing to get right in an agentic panel, and it's right.

**Caveat (flag, not fix):** `_execute_tool_block` calls `try_mcp_tool_call` **on
the worker thread** (`claude_worker.py:234`). It's only thread-safe because it's
an out-of-process hop that re-marshals to the main thread. The safety is real but
**load-bearing on an implementation detail two layers away** — if anyone ever
makes that call in-process, you get `hou` on a background thread and intermittent
crashes. Worth an assertion or comment at the call site, not just server-side.

## 1.2 Wrong: ~18 modules of dead substrate

Reachability map from `SynapsePanel` (entry confirmed:
`houdini/python_panels/synapse_panel.pypanel` → `onCreateInterface`):

| Layer | Status |
|---|---|
| chat/worker/tool spine + designsystem + 2 faces | **~30 modules live** |
| `chat_panel.py` + context_bar, ws_bridge, quick_actions, hda_views, hda_controller | **legacy second panel** — loaded only by an *uninstalled* `synapse_chat.pypanel` + tests |
| scene_doctor, network_trace, dependency_map, performance_profiler, explain_mode, apex_explainer/trace, save_shot, cross_scene, shot_login, bookmarks, prompt_to_hda, image_prep, error_translator, exposure_seam, agent_prompts | **fully orphaned** — zero importers anywhere |

The redesign kept the spine and **abandoned the entire "feature panel" layer in
place**. Only the *knowledge tables* (`recipe_book.RECIPES`, `apex_recipes`,
`vex_tutor.VEX_REFERENCE`) survived — flattened into the ⌘K palette as prompt
text; their widgets are never instantiated.

A SideFX engineer would block on this: **you cannot tell, from the tree, what
ships.** `scene_doctor.py` (737 lines) and `network_trace.py` (589 lines) look
load-bearing and are dead. This is the #1 maintenance hazard — not a style nit.
Either delete them or move them under a `legacy/` / `_attic/` boundary so the
live surface is legible. Right now ~40% of a 24k-line tree is a decoy.

## 1.3 Two token systems, two stylesheets, coexisting

`designsystem/tokens.py` + `designsystem/qss.py` are the redesign's single source
of truth and are well-built (one palette, one type-role table, one generated
sheet, `repolish()` for dynamic-property restyle — `components.py:26`). The
docstring claims it *"replaces the 314 inline-style occurrences and the 30 one-off
`get_*_stylesheet()` helpers."*

It doesn't — it **adds a fourth source**. `panel/tokens.py` and `panel/styles.py`
are still live, dragged in transitively because **`chat_display` and `gate_widget`
were carried into the redesign verbatim, unreskinned** (`chat_display.py:23-24`,
`gate_widget.py:21-22`). So the two widgets the artist stares at most — the chat
transcript and the consent gate — are styled by the *old* system while everything
framing them uses the new one. This is the literal "cyan/blue 3-source token
gremlin," still open. **→ Design §2.2:** why the panel can look subtly two-toned.

## 1.4 `except Exception: pass` as an architecture

"Graceful degradation is a contract" is stated repeatedly and implemented with
broad guards around every import and every `hou` read. Defensible — a panel must
instantiate headless for tests. But it's applied so widely that **it converts
failures into silent no-ops**: `_on_open_render` silently returns (line 599),
gate wiring silently passes (line 791-794), `_populate_review`,
`refresh_provenance`, health poll, copy-conversation — all swallow everything.

First-principles problem: *you cannot distinguish a degraded panel from a broken
one.* The codebase already knows this — it fixed it in exactly one place (the
**loud** stale-API-gate banner, `synapse_panel.py:1120-1126`, "must be LOUD, not
a one-line console warning"). That instinct should generalize: bare excepts
around real runtime paths should at minimum `logger.debug` with the exception, so
a field failure leaves a trail. Most don't.

## 1.5 Inverted concern: the panel is the process heartbeat

`synapse_panel.py:234-238`: a 1s `QTimer` beats `freeze_chain`, and the comment
admits *"The panel rebuild had removed the only heartbeat source — this restores
it."* Plus a periodic telemetry flush started from panel `__init__`
(line 227-231).

Architecturally backwards against **Law 3 (survive the lifecycle)**. A
process-wide watchdog's liveness must not depend on an *optional pane tab* being
open. Python Panels get closed, torn off, and not-restored-on-desktop-load
constantly. The moment the artist closes this tab, the freeze detector goes blind
— and the freeze chain's whole point is to fire when things are already going
wrong. The heartbeat belongs on a `hdefereval` idle event or a server-side timer,
with the panel as *one optional contributor*, never the source. **→ Design §2.4.**

---

## Cross-reference map (codebase → design)

| Codebase finding | Design consequence | Law |
|---|---|---|
| §1.3 two token/style systems coexist | §2.2 panel reads subtly two-toned (chat+gate vs frame) | Native fit |
| §1.2 feature layer orphaned | ⌘K palette is the only surviving discoverability for 14 dead tools → prompt text | Legibility |
| §1.5 panel = process heartbeat | §2.4 forced 1s main-thread timer; dies when the tab closes | Lifecycle + main thread |
| §1.1 worker correctly off-thread | §2.1 the faces model can exist because the slow path doesn't block paint | Main thread |
| Hardcoded `.hcs`-matched hex | §2.2 breaks on theme/gamma change | Native fit |

---

## Prioritized punch list (codebase)

**Ship-blockers:**
1. **Seed tokens from `hou.qt.color()` at construction**, hardcoded hex as headless fallback. Invert the current source-of-truth. (§1.3 / Design §2.2)
2. **Move the freeze-chain heartbeat off the panel** onto an idle event / server timer. (§1.5)
3. **Quarantine the dead tree** — `legacy/` for the chat_panel subtree, delete or `_attic/` the 14 orphans. (§1.2)

**Should-fix:**
4. Reskin `chat_display` + `gate_widget` onto the design system; retire `panel/tokens.py` + `styles.py`. (§1.3)
5. Replace bare `except: pass` on runtime paths with `logger.debug(exc)`. (§1.4)

The interaction model (Design §2.1) and the worker isolation (§1.1) are the parts
to least want touched. The foundation — theme-coupling, the orphan tree, the
heartbeat inversion — is where this comes back from review.
