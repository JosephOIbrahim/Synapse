# S3 — THE PLAN

**Leg** S3 · **Harness** `FORENSIC-01` · **Run** 2026-07-27 · **Branch** `forensic/s3-the-plan`
**Model** `claude-opus-5[1m]` · **Commit at run** `b608efc` (v5.36.4) · **Target** Houdini 22.0.368 / Python 3.13.10
**Mode** READ-ONLY, writes confined to `harness/notes/**` · **Governed by** `harness/AGENT_CONSTITUTION.md`
**Depends on** S0 (scout) · S1 (inventory, *recovered from transcript — §7 D1*) · S2 (pre-mortem, *two divergent copies — §7 D2*)
**Adversarially attacked** 4 hostile lenses + 8 refutation passes, 12 agents, 1.72M tokens — §6

---

## 0 · How to read this

### 0.1 The target, restated because the question was wrong

Joe asked how to make SYNAPSE *"so novel to mid-sized VFX production per Houdini artist that it is an
irrefutable positively viewed tool."*

**"Irrefutable" is not achievable and this document does not aim at it.** Nor does it aim at *novel*.
S0 measured the field: the largest Houdini-AI repository in existence has **326 stars**, and the two
commercial products have **zero third-party replies** between them across threads with 5,919 views
(S0-F3, `S0_SCOUT.md` §2.1–2.2). Novelty is cheap here and nobody is buying it. The three properties
that get a tool adopted, per the harness brief:

```
LEGIBLE VALUE       an artist can tell, in ONE session, what it did for them
SURVIVABLE FAILURE  when it is wrong the shot is not lost, and they know immediately
NO NEW BURDEN       nothing extra to remember, configure, or babysit
```

S2's ending is a **legibility** failure, not a capability failure: *"the failures had names and the
value had none."* This plan is ordered by that finding, with survivable failure first — a tool
missing it is uninstalled after one incident however good the first property is.

### 0.2 Citation map, and an ID-collision hazard to read before trusting any citation here

| Prefix | Means | Source of record |
|---|---|---|
| `S0-F<n>` | S0 scout finding | `harness/notes/receipts/S0.json`, written 15:04, `commit_at_run 11f3a79` |
| `S1-F<n>` | S1 inventory finding | recovered S1 receipt, branch `forensic/s1-tool-inventory` @ `61df5bc` (§7 D1) |
| `S1P-<name>` | S1 **re-run** live probe artifact | `harness/notes/forensic/s1_artifacts/<name>.json`, 14:50–15:03, now committed at `83a4820` |
| `S2.F<n>` / `S2#<n>` / `S2-L<n>` / `S2-U<n>` | S2 finding / ledger row / limit / unknown | **the corrected worktree copy** — see §7 D2, which explains why the *committed* copy is not the authority here |
| `R<n>` | CTO ruling | `harness/notes/CTO_RULINGS_01.md` |
| `V-S3-<n>` | **this leg's own first-hand verification** at `b608efc` | §0.3 — all 33 rows are declared there |
| `X-<n>` | a correction forced by this leg's adversarial pass | §6 |

> **⚠ HAZARD — `S0-F<n>` denotes two different things depending on which S0 receipt you hold.**
> `R120`–`R124` cite an S0 whose `F2` is *"SideFX publicly demonstrated an AI-assisted authoring
> surface and scoped it OUT of the shipped release"* and whose `F5`/`F6` concern a **shared WebSearch
> budget consumed by fan-out**. The S0 receipt **on disk** has `F2` = *"the adjacent floor moved and
> Houdini is not on it"* (Anthropic's eight MCP connectors), `F5` = seven mechanism-bearing failure
> modes from bug trackers, `F6` = Q4 largely failed, and its `oracle.producer` records **"No
> subagents dispatched."** Two runs of S0, independently renumbered; the first was destroyed (§7 D1).
>
> **Mitigation, applied rather than promised:** every `S0-F<n>` in this document is written
> `S0-F<n>` **plus** a `S0_SCOUT.md` section anchor, so the claim resolves without the number.
> *(An earlier draft claimed this mitigation and did not apply it to two thirds of its citations —
> caught as `X-5`.)* Do not resolve an `S0-F<n>` here against the rulings' numbering, or vice versa.

### 0.3 What this leg verified with its own hands

R76/R85: *a receipt is not the tree.* Every load-bearing anchor was re-read at `b608efc` — not taken
from S2's receipt. **Thirty-three checks**, all declared:

| # | Verified | Result |
|---|---|---|
| V-S3-1 | `hou.webServer.port` in the committed 22.0.368 symbol table | **ABSENT.** Parent `hou.webServer` is enumerated **1,312 descendants (1,313 counting the node itself — stating the convention, per Law 2)**, so this is a true absence, not a coverage artifact. Table: 35,903 symbols, `blake2b 265b433af49698ab`, `truncated: false`. *Control: `hou.undos` and `hou.hipFile` are present with **0** descendants — an absence there would prove nothing. This is the false-phantom trap and it was checked.* |
| V-S3-2 | `tool_executor.py:146-152` | `hou.webServer.port()` at :150 inside `except Exception: return None` |
| V-S3-3 | `system_prompt.py` H21 mentions | **FOUR**, not three: :51 *"inside Houdini 21"* · :189 *"in Houdini 21.0.671"* · :193 *"The H21 docs corpus is the authority"* · :197 *"karmaphysicalsky bug (H21)"* |
| V-S3-4 | `tool_palette.py:110,119,150` | tool rows send `"Use the \`%s\` tool." % name`; legacy rows send `_CATEGORY_PREFIX.get(cat,"") + (desc or label)`; `command_selected = Signal(str)  # emits a ready-to-send prompt` |
| V-S3-5 | `claude_worker.py:132` | `if not self._abort: self.stream_done.emit()` |
| V-S3-6 | `_note_usage` callers | **1 grep hit — its own definition.** Meter label constructed with `""` at :445 |
| V-S3-7 | `providers/base.py:60` | returns `Tuple[Optional[str], List[dict]]` — no usage slot |
| V-S3-8 | `auth.py:82-85` | no key ⇒ `_cached_key = None` ⇒ *"Authentication disabled"* |
| V-S3-9 | `hwebserver_adapter.py:330-335` | `hwebserver.run(port=…, debug=False, in_background=True, max_num_threads=4)` — **no `settings=`** |
| V-S3-10 | `foreground_guard._BUDGETS` + `:187-191` | `deny_px = 1024*1024` for all four Karma/Mantra rows ⇒ 1080p (2,073,600 px) refused. **The refusal names a sanctioned escape:** *"Reduce the resolution (<=%d px total for %s), **or pass `force_foreground=true` to accept the UI freeze deliberately**."* `allow_px` is per-engine — 65,536 for karma_cpu/karma/mantra, **262,144** for karma_xpu — with a per-engine hardware rationale at :42-52 |
| V-S3-11 | `handlers_render.py:1690-1707` | AOV presets are bare `"C"` / `"N"` / `"Z"` / `"crypto_*"` |
| V-S3-12 | `'ray:'` across `python/` | **zero hits** |
| V-S3-13 | `tests/test_render.py:606-612` | asserts `source_name == "C"/"N"/"Z"` — the suite pins the bare spellings |
| V-S3-14 | `install.py:87` + `:78` | `for major in [21, 20, 19]`; Windows search root is `~/Documents` only. `scripts/install_synapse_package.py:73-85` documents the OneDrive known-folder redirection **and handles it** (`roots = [home, home/"Documents", home/"OneDrive"/"Documents"]`). **The two installers disagree and the obvious-named one is the broken one.** |
| V-S3-15 | `handlers_tops/cook.py:150-157` | raises on any scheduler but local; the string names Deadline/Tractor/HQueue as unwired |
| V-S3-16 | `floor_gate.py:362-372` | record carries `payload_digest` + `result_digest`; no node path, parm or value |
| V-S3-17 | `doctor.py:592-602` | lists the newest **three provenance filenames** — the only reader |
| V-S3-18 | `git ls-files` for `*.hda/*.otl/*.hdanc/*.hdalc` | **zero tracked** |
| V-S3-19 | `tests/conftest.py` | fake `hou` planted when absent; `hou.undos = MagicMock()` |
| V-S3-20 | `tool_filter` importers | `command_palette.py`, `tool_palette.py`, 1 test — **not in the request path**; `synapse_panel.py:1667` hands `get_anthropic_tools()` unfiltered |
| V-S3-21 | `error_translator.translate_error` | **zero external callers** |
| V-S3-22 | `rkill` in `python/` + `shared/` | **zero call sites** |
| V-S3-23 | `TOOL_DEFS` length | **120** |
| V-S3-24 | `RecipeRegistry()` instantiated live | **62 recipes** — pipeline 12, render 11, copernicus 9, lighting 7, fx 6, tops 5, utility 3, geometry 2, materials 2, set_dressing 1, compositing 1, camera 1, environment 1, sim 1. *Second, independent producer:* `grep -c "registry.register(Recipe("` across `python/synapse/routing/recipes/*.py` = **62** (7+21+18+11+5) |
| V-S3-25 | `preflight_warning` | declared :300, emitted :360, **zero `.connect(` sites** in `python/` or `tests/`. `estimate_inline_cost` has exactly one production call site, `tool_executor.py:349-350`, inside `_preflight`, called only from `execute_tool` — the `@QtCore.Slot` at :368-369 |
| V-S3-26 | `route_chat` senders | **only** `panel/chat_panel.py:799,903` |
| V-S3-27 | the shipped panel | `houdini/python_panels/synapse_panel.pypanel:45` → `from synapse.panel.synapse_panel import onCreateInterface`. **One** `.pypanel` in the tree |
| V-S3-28 | `synapse_panel.py` references | **zero** to `chat_panel`; **zero** to recipes/`RecipeRegistry` |
| V-S3-29 | `route_chat` reachability from tools | it is one of the **7** `handler_cmds_with_no_tool` (`S1P-registry_xref`, fresh at HEAD): `assess_render_ready`, `get_help`, `matlib_bind`, **`route_chat`**, `solaris_shotsetup_karma_xpu`, `tops_pause_cook`, `tops_resume_cook` |
| V-S3-30 | panel tool array | `get_anthropic_tools()` → **126**. `synapse_scout` **absent**; `synapse_inspect_stage` **absent** |
| V-S3-31 | `build_palette_entries()` | **95** entries, `Counter({'vex': 45, 'command': 21, 'recipe': 21, 'apex': 8})`. `_CATEGORY_PREFIX` = `{recipe, apex, vex}` — **no `command` key**, so the **21 `command` rows are the only rows with neither an imperative prefix nor a tool name** |
| V-S3-32 | the **second** recipe library | `panel/recipe_book.py::RECIPES` = **7 categories, 21 recipes**, read by `command_palette.py:139-145`. Palette-reachable and prefixed *"Build this network recipe — "* |
| V-S3-33 | `mcp/server.py:803-817` + `_MCPLocalClient._post` | when `get_auth_key()` is not None the `/mcp` handler **401s** any request lacking `Authorization: Bearer <key>`; `_post` (`tool_executor.py:170-176`) sends only `Content-Type` and `Accept`. `grep -rn Authorization tests/` = **empty**. Two sibling gates: `hwebserver_adapter.py:123-134` and `websocket.py:395-401` |

**Currency — scoped, because an earlier draft overstated it (`X-3`).** `dfc02c8` (S2's snapshot) →
`b608efc` (HEAD) touches **24 files**. Under `python/`, exactly **two**:
`python/synapse/__init__.py` (version strings only — `git diff` shows `5.36.0`→`5.36.4` and nothing
else, so the `L6` win-only vendoring predicate at :62-68 is **unchanged and re-verified at HEAD**) and
`panel/message_formatter.py` (76 lines, formatter-local). **So: no S2 anchor under `python/` moved.**
Outside `python/` the range **does** move S2 anchors, and one is load-bearing:

- `harness/verify/checks.py` **+88/−6** — `S2#63` / `R-S2-5` is **SUPERSEDED**. See Gate 3.2.
- `README.md` **96 lines** — S2's two README rows moved; line numbers in S2's §1 quotes shifted
  (`README.md:109`→`:115`).
- `S2#69` (`checks.py:1557`) and `S2#70` (`checks.py:986-1001`) were re-read at HEAD and **remain
  current**.

### 0.4 Three inherited premises are dead, and the plan is different because of it

**Dead premise 1 — `synapse_inspect_scene` does not hang, but the hang *class* is still live.**
S1-F2 reported it blocking the full 1800 s MCP idle timeout, twice, controlled; `R121` ruled *"fence
it before the demo"*; `R125` refuted both proposed mechanisms by direct measurement (0.00–0.08 s).
S1's re-run closes the tool: `inspect_scene` returned **767 bytes / 10 nodes** on **both**
transports (`S1P-ws_readonly_sweep`, `S1P-mcp_surface_probe`). **No plan item fences
`inspect_scene`** — that would be building against a ghost.

**But the surface still fails to answer.** `S1P-mcp_isolate` — one fresh MCP server per case, the
tool called *first*, 180 s ceiling — records `synapse_scout`: **`elapsed 180.11`, result
`"NO_RESPONSE"`**, while every other isolated case returned in 4.02 s. So the non-answering class is
live, and its victim is the tool `CLAUDE.md` rule 15 makes the **mandatory** phantom-API pre-flight.
That is now a plan item (Gate 1.5), which the earlier draft omitted entirely (`X-6`).

**Dead premise 2 — "in-process access" is not a differentiator.** The brief supposes in-process
access lets SYNAPSE do what an outside-in tool structurally cannot. S0-F3 (`S0_SCOUT.md` §2.4)
measures otherwise: `capoomgit/houdini-mcp` (273★) runs a socket server **inside Houdini**, and
`healkeiser/fxhoudinimcp` (138★) uses **Houdini's own `hwebserver`** with
`hdefereval.executeInMainThreadWithResult()` marshalling, verified on **22.0.368** — SYNAPSE's
architecture, with **179 tools** to SYNAPSE's 120 (V-S3-23). In-process is the field's baseline.
**Any plan item resting on "we are in-process" is deleted.**

**Dead premise 3 — the palette is not broken; 9.2 % of it is.** An earlier draft carried S2's
pre-correction figure, *"95 of 228 rows (41.7 %) send prose instead of dispatching."* Both halves
are wrong and the adversarial pass caught it in two independent lenses (`X-1`). Verified at HEAD:
**no palette row dispatches — the widget is a prompt-composer by construction** (V-S3-4,
`command_selected = Signal(str)  # emits a ready-to-send prompt`), so "instead of dispatching" is a
contrast that does not exist. Of the 95 legacy rows, **74 carry an imperative `_CATEGORY_PREFIX`**
(45 vex + 21 recipe + 8 apex) and the tool rows name their tool outright. **The real defect is the
21 `command` rows (9.2 %) that carry neither** (V-S3-31) — and they are exactly the 21 slash commands
`R19` ordered removed.

**What survives as structurally distinctive**, measured against that same field:

- **62 recipes carrying real domain law** (V-S3-24) against `fxhoudinimcp`'s **6 workflow prompts**
  (S0-F3, `S0_SCOUT.md` §2.4). The live `synapse_list_recipes` payload (30,044 bytes,
  `S1P-mcp_surface_probe`) contains sensor dimensions for eight named cinema bodies — ARRI Alexa 35,
  Alexa Mini LF, RED V-Raptor [X], Komodo-X, Sony Venice 2, FX6, Blackmagic… — and lighting recipes
  stating *intensity always 1.0, brightness by exposure* with 4:1 key:fill math.
  *Tiering, corrected (`X-2`):* the **punycode parm names** (`xn__inputsintensity_i0a`,
  `xn__inputsexposure_vya`) appear in `S1P-mcp_surface_probe:synapse_recall`'s **knowledge** answer —
  a **corpus answer (documented)**, not a live parm read (observed) — and this repository's own note
  records the hand-maintained `xn__` map as **majority phantom, probe-generate never guess.** They
  are cited here as domain *content*, not as verified parm names.
- **Nothing SYNAPSE authors depends on SYNAPSE** (V-S3-18) — a touched `.hip` opens on a bare farm
  node. A real architectural achievement.
- **A host-identity-gated live test tier that deletes its mocks** (S1-F6). No competitor publishes any
  evaluation artifact except one qualitative markdown file (S0-F3, `S0_SCOUT.md` §2.3).

---

## 1 · THE THREE QUESTIONS, ANSWERED DIRECTLY

### 1.1 Q1 — What is the ONE thing an artist notices in the first session?

> **Nothing. There is no such moment today, and that is this leg's most important finding.**

Not "the moment is weak." On the shipped path at `b608efc`, a first session cannot produce a legible
win, and the reason is a chain of verified mechanisms rather than a missing feature:

1. **Every tool runs on the GUI thread.** `hou.webServer.port` does not exist on 22.0.368 (V-S3-1);
   the call is swallowed by a bare `except` (V-S3-2); `available` is `False` **permanently**;
   `try_mcp_tool_call` returns `None` on every call; every tool falls through to the Qt-main-thread
   slot (`S2#1`, `S2.F2`). The module's own comment records a 127 KB `execute_python` freezing the
   loop **>5,000 ms** (`bridge_adapter.py:230-233`).
2. **The model is told it is in Houdini 21** — four separate places (V-S3-3) — while H22 renamed seven
   Solaris LOP/SOPs and removed eleven `hou` methods (S0-F9, `S0_SCOUT.md` §1.6, §1.9).
3. **The turn ends green whatever happened.** The rail reads *"done / Result ready"* after an
   all-errors turn, tool errors never reach the chat (`S2#7`), and the integrity readout prints
   `Operations: 12 | Verified: 12 | Violations: 0 | Fidelity: 100.0%` for a session in which five
   calls failed (`S2.F3`, `S2#6`).
4. **The `/` menu's 21 command rows type a sentence under a footer reading "Enter run"** (V-S3-31).
   Narrower than the earlier draft claimed, and still the first thing an artist touches.

#### The asset that exists twice, and only the smaller copy is reachable

This is the plan's own finding, verified end to end at HEAD, and it is sharper than the earlier
draft's version (`X-7`):

```
LIBRARY A   panel/recipe_book.py::RECIPES          21 recipes, 7 categories        (V-S3-32)
            reachable: YES — command_palette.py:139-145 lists them, and the row
            sends "Build this network recipe — <description>" (prefixed, actionable)

LIBRARY B   synapse/routing/recipes/::RecipeRegistry   62 recipes                  (V-S3-24)
            the RICH one: 8 cinema bodies with sensor data, lighting law, 4:1 math,
            AND natural-language TRIGGER regexes
              e.g. "^(?:set up|setup|create)\s+(?:a\s+)?(?:area|panel)\s*light$"
            reachable by natural language: NO
```

Library B's triggers are matched by `TieredRouter` in the cascade
`Cache → Recipe → Planner → Regex → Knowledge → LLM → Agent` (`handlers.py:1591-1600`). The router is
unreachable **from all three directions at once**:

- `TieredRouter` is constructed in exactly one place, `_handle_route_chat` (`S1-F3`);
- `route_chat` is one of the **7 handler commands no registered tool reaches** (V-S3-29);
- `route_chat` is sent by exactly one module, `panel/chat_panel.py` (V-S3-26), which is **not** the
  shipped panel (V-S3-27) and is never referenced by it (V-S3-28).

Confirmed from outside on both transports: `synapse_router_stats` returns
`{"error":"Router not initialized"}` over WebSocket *and* MCP — the object is never built in the
process.

⇒ **The product ships two recipe libraries with different content, and the discoverable one is the
smaller, older, poorer one.** That is exactly the *"two competing stories about how a recipe is
invoked"* that Gate 2.2's own reasoning forbids — already true, unnoticed. It also answers `S2-U6`
more precisely than a user study could: artists *can* find 21 recipes by pressing `/`; they cannot
reach the 62 by any means except the model electing to call `synapse_list_recipes` unprompted.

#### The candidate that can be made to qualify, and why it is the only one

**"Assemble my shot" — Solaris layer scaffold + a cinema-camera prim + a three-point light rig, from
one natural-language request, with the cost stated before it runs and a plain-language diff of what
changed after.**

Derived, not chosen:

- It is the **only artist-facing family with host evidence.** Four of five Solaris tools are covered
  by a host-identity-gated live tier that skips honestly off-host; that tier immediately found two
  real defects mocks had hidden — `set_purpose` reporting success having set nothing,
  `import_megascans` raising `PermissionError` on every call — both repaired (S1-F6). Measured:
  the three live-gated files run **137 passed / 0 failed in 3.86 s** on H22.0.368.
- It is where the recipes are: of Library B's 62, **22 sit directly on this task** — 12 pipeline,
  7 lighting, 1 camera, 1 environment, 1 set_dressing (V-S3-24).
- Everything else is excluded by measurement. S1-F7: `WORKS` is **zero** in rendering (13 PARTIAL),
  lighting (4), caching (8) and comp (2); **12 of 24 `WORKS` tools are agent-internal**, and exactly
  one of those is something an artist would reach for. Promising a render-side or comp-side moment
  would be promising the unproven.

**The one thing standing in the middle of it:** `synapse_solaris_assemble_chain` — S1's *"single
highest-leverage tool in the inventory"* — has **no host evidence at all**; its three tests are
mock/registration only and it is **not** in the live tier covering its four siblings (S1-F8). The most
valuable claim in the product is the least verified one. **That is why it is now a premise test that
runs first** (P-1), not a Gate 2 item.

### 1.2 Q2 — What must be true before a pipeline TD signs off?

| # | The TD's objection | Evidence | Answer |
|---|---|---|---|
| 1 | *"It listens on the network with no password and runs arbitrary Python."* | `S2.F1`, verified twice in S2's session (`netstat TCP 0.0.0.0:9999 LISTENING pid 47540`; HTTP GET from `192.168.1.183` reached SYNAPSE's `/mcp`) and re-verified here: `run()` carries no `settings=` (V-S3-9), no key ⇒ auth disabled (V-S3-8). **REFUTES `DEPLOYMENT.md:10`.** | **ANSWERED — Gate 0.1**, non-negotiable, and it must ship **with** Gate 0.3 (V-S3-33). |
| 2 | *"Your own gate says you are not ready."* | S2 headline: `posture_declared`, `policy_single_source`, `consent_enforced`, `rbac_at_dispatch` all **RED** under studio posture ⇒ NOT READY; under declared `solo` the three security criticals become accepted trade-offs ⇒ READY (solo). | **ANSWERED by scoping — Gate 0.2**, in two parts, because the harness file an installed seat never sees cannot be the thing that tells the TD (`X-13`). |
| 3 | *"What will it cost me?"* | `S2.F10` / `S2#10`: `_note_usage` zero callers (V-S3-6); no usage slot in the stream contract (V-S3-7); no `message_start` branch, which is where `input_tokens` / `cache_read_input_tokens` arrive. | **ANSWERED — Gate 1.1.** The item S2 says decided the trial. |
| 4 | *"Can I trust your test suite as an upgrade gate?"* | `S2.F18`: GATE **5,031/0** (system python, vendor inactive) vs SHIPPING **4,891 passed / 95 failed / 8 errors** (`hython3.13`, vendor active). | **HALF-ANSWERED — Gate 3.2**, which is now much smaller than the earlier draft thought: two thirds already shipped inside this plan's own commit range (`X-17`). |
| 5 | *"Every point release you make me regenerate a table by hand."* | S2 §2: a manual, Windows-shaped four-step runbook per Houdini point release (~fortnightly), whose final confirmation step calls a tool that cannot report success on the path they would call it from. `S2-U5`. | **PARTLY — Gate 3.1.** Whether a half-time TD absorbs it is not answerable from the tree: pilot abort condition 3. |
| 6 | *"My logs are full of alarms that mean nothing."* — **missing from the earlier draft (`X-24`)** | `S2#22` / `S2.F7`: every render over 30 s trips the freeze chain — heartbeat stops at 1 s, `Watchdog` frozen at 5 s, `FreezeChain._escalate` at 30 s → telemetry dump, breaker forced OPEN, then `trigger_emergency_halt`, which is handed a `SynapseBridge` while its first statement needs `LosslessExecutionBridge` (`shared/bridge.py:2197,2284`) — so it raises and logs **`Emergency halt failed (best-effort)`**. *"Alarm fatigue, manufactured by construction."* | **ANSWERED — Gate 1.6.** This is a direct feeder of abort condition 3, which is why omitting it mattered. |
| 7 | *"Does it go to the farm?"* | `S2-L4` / V-S3-15. The thing named `RenderFarmOrchestrator` has a docstring reading *"Local render farm"*. | **ACCEPTED LIMIT, stated up front.** The pilot ends at a reviewable scaffold. A positioning fact, not debt. |
| 8 | *"What happens when the second artist opens the shot?"* | `S2.F9` / `S2-L5`: store is `<hip_dir>/.synapse` (per shot, shared storage); Fernet key is per-seat, auto-generated. Artist B fails to decrypt, `_degraded_load = True`, `save()` raises thereafter, **no recovery path**. | **ANSWERED — Gate 3.3.** |
| 9 | *"Is my show root writable?"* | `S2#30` / `S2-U10`: `claude/` created at `$JOB` by unguarded `os.makedirs`, hardcoded, no override. | **ANSWERED by asking — Gate 0.5** — a question plus an override, not a build. |
| 10 | *"Our contract has an AI clause."* | `S0-F4` (`S0_SCOUT.md` §3.1): MPA CSBP control **OR-5.0**, introduced v5.3 (2025), requires an AI/ML policy, risk management, AI/ML in the AUP, and explicitly ***"Ensure client approval for AI/ML application use"***, with the additional recommendation ***"Only use internally managed and sandboxed LLMs."*** TPN is wholly MPA-owned. The burden already produced a community **Tool Disclosure List** recording hosting model / risk level / approval status per tool. | **ANSWERED as a deliverable — P-2**, promoted to a premise test because its own logic requires it to precede the pilot proposal (`X-15`). *Caveat: read one hop from primary, not the MPA document (`S0_SCOUT.md` §5.12).* |
| 11 | *"Will it poison my scenes?"* | V-S3-18: **zero** tracked `.hda`/`.otl`; emitted-node catalog is stock namespaces only (83 bare, 11 `apex::`, 3 `kinefx::`); only inert `setUserData("synapse:*")`. *Caveat S2 added under attack: the census is over the committed **97**-entry catalog while `S2#57` records live drift to **109**, so 12 emitted types are unaudited. The zero-HDA half is independent and unaffected.* | **ALREADY TRUE, and the strongest card in the pack.** P-2 puts it in writing with its producer and its caveat. |

### 1.3 Q3 — What is the smallest credible pilot?

**One artist. One show. One bounded task. One quarter. And a week-one kill switch.**

```
WHO       ONE Houdini generalist + the pipeline TD at ~2h/week.
          NOT three artists: the install surface has NINE ways to half-succeed,
          SEVEN of them silent (S2 §1 Day 1). Rolling to three multiplies the
          silent-failure surface before anything is learned.
          NOTE the seat arithmetic: this is TWO seats, and the TD's is the one
          that already works. That is why Gate 0.6 exists (X-23).

SHOW      One sequence on one show. If the facility is TPN-assessed, the pilot
          runs on internal / non-deliverable work, or with the client AI
          disclosure already signed (S0-F4: OR-5.0 requires client approval;
          the disclosure taxonomy rates Internal Use / Non-Deliverable LOW).

TASK      Solaris shot assembly, from a natural-language request in the panel:
            department layer scaffold
            + a USD camera prim from the cinema-camera recipe
            + a three-point light rig at the recipe's 4:1 key:fill
          Ends at a REVIEWABLE SCAFFOLD.
          OUT: rendering, caching, comp, farm submission, autonomous mode.

ENFORCED  The render exclusion is a CONFIGURATION, not a request (X-22): the six
          render tools are removed from the panel's tool array for the pilot's
          duration via the Gate 1.4 filter. An unenforced scope line is not a
          scope line, and abort condition 2 depends on this being real.
```

**Success criteria — measured, and the earlier draft's design was confounded (`X-25`).**

1. **Primary — interleaved control, not a pre-period baseline.** Every 4th shot is hand-built as a
   control, **throughout the quarter**, giving ≥5 controls interleaved with ≥15 SYNAPSE shots.
   *Why the change:* an earlier draft took the baseline from the first 5 shots of the sequence, before
   conventions, templates and layer naming settle — so a learning-curve effect alone could produce the
   target reduction with no tool contribution, and the confound pointed **toward** SYNAPSE.
   Report the **full distribution**, not only the median; with n≈5 controls no confidence claim is
   available and none will be made. Success = **≥30 % median reduction, controls interleaved, and
   zero lost-scene incidents.** *(The 30 % is a chosen threshold — labelled in §5.)*
2. **Legibility — with a named instrument.** The artist logs one line per turn: *did I know what it
   changed? y/n.* The TD samples 10 turns/week as a check on the log. Target ≥90 %. *(An earlier
   draft stated this criterion with nobody assigned to record it.)*
3. **Cost — in the unit Gate 1.1 actually produces.** Dollars **per turn** and per week, plus the
   shot count, so per-shot is derived rather than asserted. Gate 1.1's DO now stamps each turn with
   the current `$HIP` precisely so this aggregates. *(An earlier draft asked for dollars per shot from
   an item that produces per-turn totals — `X-14`.)*

**Pre-agreed abort conditions. Any ONE ends the pilot that day, without debate.**

| # | Condition | Why this one |
|---|---|---|
| 1 | **Any incident in which unsaved work is lost.** | `S2-U1`: at 6:01 pm with a wrong camera, the Stop button is drawn/enabled/unclickable, the cancel tool is marshalled onto the blocked thread, `rkill` works with **zero call sites** (V-S3-22), emergency halt is unsurfaced and its one automatic caller is inert. No hip checkpoint exists around risky mutations. *Three of those five escapes are limitations the README already discloses — attribution matters (S2, under attack); the genuinely new one is the inert halt caller.* |
| 2 | **Any SYNAPSE-authored artifact that SYNAPSE reported good and was not.** | Reworded from "any frame reaching dailies" because with renders excluded and enforced there are no SYNAPSE-reported frames, so the frame version could never fire — an unmeasurable abort condition (`X-22`). The mechanism it guards is real and general: `S2#35` (AOV presets write bare source names, V-S3-11, and `ray:` appears nowhere, V-S3-12, while R101 established the prefix is REQUIRED on Karma 22.0.368 ⇒ *"a correctly-named EXR part FILLED WITH ZEROS, SILENTLY"*) and `S2#36`/`S2#56` (success reported from `exists() && size>0`; TOPS write-tools report the payload, not the readback). |
| 3 | **TD support time exceeds 4 h in any single week.** | `S2-U5` + objections 5 and 6. *"I can't support this"* is S2's predicted ending; this makes it a measurement. |
| 4 | **Week 1 gate — if the artist cannot complete the task end-to-end in the panel, unaided, at least once inside the first week: stop.** | `S2-U21`: the only end-to-end test of panel → agent turn → tool calls → scene is an unconditional `pytest.skip()` deferring to a runbook naming an uninstalled build. The artist's path has **never been observed working**. This refuses to spend a quarter finding that out. |

**What the pilot converts:** `S2-U21` (does the loop work) → observed in week 1 or stopped;
`S2-U6` (recipe discovery) → observed, already narrowed by §1.1; `S2-U14` (turns/day, round-trips/turn
— the free parameters in *every* cost figure) → measured; `S2-U3` (how an artist reads
`Fidelity: 100.0%` beside red errors) → observed; `S2-U10` → answered before install.
`S2-U1` is **deliberately not converted here** — it gets a bench probe on a scratch scene (Gate 0.4),
never a production shot. Spending a real shot to learn it is how the pilot ends at abort 1.

---

## 2 · THE PLAN

Every item: **DO / BECAUSE / INSTEAD OF / COSTS / FALSIFIED.** No item without a finding behind it;
beliefs without findings are in §5, labelled. Costs are engineer-days, rough, honest.

**Ordering, corrected under attack (`X-15`).** The two cheapest premise tests now run **first**,
because each can invalidate work the rest of the plan is spent enabling, and neither touches product
code.

---

### PREMISE TESTS — run before anything is built

#### P-1 · Put `assemble_chain` in the live tier before anyone plans around it

**DO** — Add `synapse_solaris_assemble_chain` to the host-identity-gated live tier alongside its four
siblings, with a positive control (it wires an unwired network into canonical order) **and** a negative
control (it refuses a non-LOP path). Same for `synapse_solaris_create_variants`, whose only live test
today is the negative one.

**BECAUSE** — `S1-F8`: it is *"the single highest-leverage tool in the inventory and it has no host
evidence at all"* — three tests, mock/registration only, absent from
`tests/solaris/test_live_wiring.py`. The family reads uniformly green from outside and is not uniform.
`S1-F1` is why that matters: `conftest.py` plants a canonical fake `hou` whenever a real one is absent
(V-S3-19), so `pytest.importorskip("hou")` gates nothing. **The honest figure is S2's correction, not
S1's original (`X-4`): 279 `test_*.py` at HEAD, **81** install a fake `hou`, and **3** are live-gated
and re-runnable** — worse than S1's "5 of 286", which strengthens this item. `R122` already ruled the
cure standard: *"the mock fixtures were DELETED under Law 1… that pattern is the standard for any tool
an artist actually reaches for."*

**INSTEAD OF** — more mock tests. That loses by direct precedent: `houdini_create_node` is the
**most-tested tool in the product (32 tests)** and still has no host-behaviour evidence (`S1-F10`).
Test count and evidence are independent axes here, and this codebase has already paid to learn it.

**COSTS** — ~2 days. The tier exists and is green (137 passed / 0 failed / 3.86 s on 22.0.368), so
this is authoring tests, not infrastructure. **It touches no product code and cannot regress
anything** — which is why it goes first.

**FALSIFIED** — the live test shows `assemble_chain` does not produce a canonically-ordered network on
22.0.368. Then §1.1's answer narrows to `scene_template` + `component_builder`, the pilot TASK shrinks,
and Gates 0–3 are being spent on a smaller prize. **Better to learn this in week 0 than week 9.**

---

#### P-2 · Write the disclosure row and the farm-safety proof

**DO** — Two short artifacts, before the pilot is proposed: **(a)** a **Tool Disclosure List row** for
SYNAPSE — name, website, licence type, tool type, AI functionality category, **hosting model = Hybrid**
(local tool, cloud LLM), risk level, output handling, approval status, plain-English usage description;
**(b)** a one-page **farm-safety proof** — a `.hip` SYNAPSE touched, opened and rendered on a node with
no SYNAPSE installed, with the producer named **and** the 97-vs-109 catalog caveat stated.

**BECAUSE** — **(a)** `S0-F4` (`S0_SCOUT.md` §3.1) is the only *contractual* adoption blocker found
anywhere: OR-5.0 requires client approval for AI/ML use, and the community Tool Disclosure List exists
precisely to satisfy it, rating *Generative Content* **HIGH / approval required** and *Internal Use,
Non-Deliverable* **LOW**. An AI tool in a TPN-assessed facility is not adopted on technical merit — it
acquires a classification. **Handing the TD the row they would otherwise write is the cheapest
adoption work available.** **(b)** V-S3-18 + `S2#17`: S2 names this *"the failure class that kills
most DCC tools"* and says **SYNAPSE does not have it** — *"a real architectural achievement and the
studio never notices, because nothing going wrong is invisible."*

**INSTEAD OF** — a features one-pager or a demo video. That loses on S0's measurement of what demos
achieve here: two commercial products, **zero third-party replies**, and the only substantive
practitioner reply anywhere is sceptical and points at free alternatives (`S0_SCOUT.md` §2.2).
Meanwhile the compliance artifact is a *requirement* someone must produce regardless.

**COSTS** — ~1 day for (a); ~0.5 day for (b). **Non-code, and its own logic puts it before the pilot
proposal**, which is why an earlier draft placing it last was wrong.

**FALSIFIED** — the studio is not TPN-assessed and has no AI clause, so (a) is unread. Then (a) drops
to optional *for that studio* and (b) still stands. **Answerable in one question, before writing it.**

---

### GATE 0 — Survivable failure. Before any studio sees it.

---

#### 0.1 + 0.3 · ONE COMMIT: bind loopback, mint a key, **teach the client to present it**, and repair the phantom port

> **These were two items and they cancelled each other.** The adversarial pass found it in two
> independent lenses (`X-2`): minting `~/.synapse/auth.key` arms **three** server gates
> (`mcp/server.py:806`, `hwebserver_adapter.py:124`, `websocket.py:395`) and **no in-process client
> answers any of them.** `_MCPLocalClient._post` sends only `Content-Type` and `Accept` (V-S3-33), so
> a keyed `/mcp` request 401s → `_ensure_session` raises `ConnectionError` → `try_mcp_tool_call`
> returns `None` → **silent fallback to the Qt main-thread slot: precisely the condition 0.3 exists to
> remove.** Shipping 0.1 without 0.3's client half would have re-created the defect while reporting
> both items done. They are now one commit.

**DO**
1. Pass `settings=` with `ADDRESS='127.0.0.1'` and `ALLOWED_HOSTS=['localhost','127.0.0.1']` into
   `hwebserver.run(...)` at `hwebserver_adapter.py:330-335`; have the installer mint
   `~/.synapse/auth.key`; refuse to start on a non-loopback bind with no key.
2. Replace `hou.webServer.port()` at `tool_executor.py:150` with the port SYNAPSE already knows
   (`~/.synapse/bridge.json` via `bridge_endpoint`).
3. Teach `_MCPLocalClient._post` to send `Authorization: Bearer <get_auth_key()>` when a key is
   configured, and have `panel/ws_bridge.py` answer the `auth_required` handshake if it is on any live
   path.
4. **Three checks, each with its failure condition stated (Law 1):**
   *(a)* phantom lint — fails if `hou.webServer.port` appears in the committed 22.0.368 table or the
   call site returns; *(b)* auth pin — fails if a key is configured and `_post`'s header dict lacks
   `Authorization` (`grep -rn Authorization tests/` is **empty** today, V-S3-33); *(c)* **a positive
   path assertion** — a counter the panel prints showing a real tool call *took* the MCP path, so
   "the port resolved" is never mistaken for "the fast path works."
5. **Spike first, twice.** (i) whether Houdini's C++ `hwebserver` honours a settings-supplied
   `ADDRESS` at all — SYNAPSE has never passed `settings=`; (ii) whether the panel→`/mcp` round trip
   works at all — see COSTS.

**BECAUSE** — `S2.F1` verified twice by S2 and re-verified here (V-S3-8, V-S3-9), refuting
`DEPLOYMENT.md:10`; behind that handler `execute_python` runs arbitrary code with full `__builtins__`,
no import filter, no length cap, no gate. `S0-F4` (`S0_SCOUT.md` §3.1): OR-5.0's additional
recommendation is *"only internally managed and sandboxed LLMs"* — a LAN-reachable ungated interpreter
is not survivable in a TPN-assessed facility. And `S2#1`/`S2.F2` + V-S3-1/V-S3-2: the phantom port is
what puts every tool on the GUI thread.

**Thread-safety check, because the obvious worry is real and had to be settled:** repairing the port
could in principle trade a freeze for a self-deadlock if the fast path ran on the main thread. It does
not. `try_mcp_tool_call` is called from `claude_worker.py:254`, and `ClaudeWorker` is a **`QThread`**
(`claude_worker.py:49`); the function's own docstring reads *"Safe to call from any thread… **NOT safe
to call from the main thread (will deadlock with hdefereval)**."* Worker-thread-only by construction.

**INSTEAD OF** — documenting the firewall step and leaving the default open. That loses because
`S2-U4` establishes the security review may happen **after** the pilot: a documented-but-default-open
port converts a week-0 rejection into a week-12 shutdown, which is strictly worse — the studio has
already spent the quarter and the finding arrives attached to the word "breach."

**COSTS** — ~3 days, up from the earlier draft's 2, and the increase is the honest part. `available`
has **always** been `False`, so this is not a regression being repaired — it is an **untested path
being switched on for the first time** (`X-9`). Session `initialize`, the `Mcp-Session-Id` lifecycle,
per-tool timeout budgets, and a panel-originated **mutating** call over `/mcp` have never executed.
Budget: ~1 day code, ~1 day the two spikes, ~1 day the three checks.

**FALSIFIED** — either spike fails: `hwebserver.run(settings=…)` ignores `ADDRESS` on 22.0.368
(then the remedy becomes refuse-to-start-without-a-key plus a loopback proxy, and the bind is
reclassified a documented LIMIT), **or** the panel→`/mcp` round trip proves unusable (then the fast
path is abandoned, inline execution becomes an accepted LIMIT, and Gate 0.4 carries the whole burden
of making it survivable). Either outcome rewrites this item rather than deleting it.

---

#### 0.2 · Declare the posture where the harness reads it, and print the security posture where the TD reads it

**DO** — Two parts, because one file cannot serve both readers. **(a)** Write
`harness/state/posture.json` declaring `solo`, for the harness gate. **(b)** Ship a **product-side**
posture line: `synapse_doctor` prints the effective security posture from product-side config —
bind address, whether an auth key is present, whether consent is armed — with no dependency on
`harness/`.

**BECAUSE** — S2's headline: the seven read-only S-checks at `dfc02c8` in the posture a studio has
(undeclared → strict) return four **RED** ⇒ **NOT READY**; under declared `solo` the three security
criticals become listed accepted trade-offs ⇒ **READY (solo posture)**. S2 §7: *"SYNAPSE ships a
studio-readiness gate that refuses to certify SYNAPSE."* **The split is forced (`X-13`):**
`harness/state/posture.json` is a deliberately-uncommitted harness file that an **installed seat never
has**, and `synapse_doctor` ships from `python/` with no route to it — so an earlier draft's
single-file version would have required either a product→harness dependency that cannot survive an
install, or a second posture file, which is the `policy_single_source` defect it was meant to answer.

*Two greens on that board must not be over-read, both found by S2 under attack:* `farm_headless`
passes on a **literal-string fingerprint** (`checks.py:1557`:
`if "dirtyAllTasks(remove_files=True)" in bridge_src`) while the live call reaches the same defect
through a **variable** (`shared/bridge.py:1718`) — a fingerprint artefact, not a clearance; and
`check_context_review_clean` is **not read-only** (it shells a script that rewrites a tracked file),
so S2's "all eight run read-only" was inaccurate for one of them. Both re-read at HEAD and still
current (§0.3).

**INSTEAD OF** — arming consent and RBAC first. That loses because `S2-L10` establishes the consent
gate **cannot** be armed on the panel path without a redesign: the blocking `HumanGate` poll
`time.sleep`s on the very thread that must draw the approval card. "Fix it" is a months-clock
redesign; declaring the posture is honest today and costs hours. It is **not** softening a check —
the RED criteria still print, by name.

**COSTS** — ~0.5 day for both halves.

**FALSIFIED** — a TD reads the declared `solo` posture and treats the declaration itself as
disqualifying, i.e. stated scope reads as an admission rather than a spec. Then the answer is the
`L10` redesign on a longer clock and this item was cosmetic.

---

#### 0.4 · Announce the freeze that cannot be removed, at the point that survives 0.3

**DO** — Connect `ToolExecutor.preflight_warning` to a panel surface, **and** move the
`estimate_inline_cost` call into the worker *before* dispatch so it fires on the MCP path too. Show
the artist, before a long op: what will run, that the UI will stop repainting, and roughly for how
long. **Plus the U1 bench probe, budgeted here explicitly** (`X-11`): on a scratch scene, a ~6-minute
frame, one observer, recording what an artist touches when told at t+20 s that the camera is wrong.

**BECAUSE** — `S2-L1` is arithmetic, not a defect, and the authors say so in the source: *"nothing in
Python can interrupt the main thread from the main thread, so any number here would be a lie. **The
panel freezes for the render's duration.**"* The remedy L1 names already exists and is inert:
`estimate_inline_cost` computes the verdict, `preflight_warning` is declared and emitted, and
**zero `.connect(` sites exist** (V-S3-25). **The composition is the point:** `estimate_inline_cost`
is reached only inside `_preflight`, called only from the `@QtCore.Slot` `execute_tool` — so **fixing
0.3 deletes the advisory from the path entirely** unless it moves. Two lenses attacked this coupling
and both graded it SOUND; it is the plan's strongest piece of independent reasoning.

**What this does *not* claim.** An earlier draft said that with the fast path live *"Qt keeps pumping
and the Stop button becomes clickable for every non-render tool."* **That is withdrawn (`X-10`).**
The `hou` work still executes on the main thread via `run_on_main`; while it runs, Qt cannot process
the Stop click. For this item's own motivating example — the 127 KB `execute_python` freezing
**>5,000 ms** — the freeze survives 0.3 at nearly full length. What 0.3 actually buys is a **bounded
caller wait** (FAST PATH 2 is no longer taken, so `run_on_main`'s timeout stops being discarded), the
panel's worker thread free to emit state, and the op running through the server's normal handler path.
**Responsiveness during a long main-thread op is not on offer, and no item in this plan promises it.**

**INSTEAD OF** — a progress bar or spinner. That loses because a spinner cannot paint: the event loop
that would animate it is the thing being blocked. The only honest signal is emitted *before* the block.

**COSTS** — ~1.5 days: connect + relocate (~1), the U1 bench probe (~0.5). **The render-refusal line
is deleted from this item** — the refusal already exists and already carries reason *and* a sanctioned
escape (V-S3-10). The gap is that the artist never sees it, which is Gate 1.3's work, so budgeting it
here double-counted (`X-12`).

**FALSIFIED** — artists shown the pre-flight warning proceed anyway and still report the freeze as an
unexplained hang. Then the warning is not the missing piece and the answer is out-of-process
rendering, a far larger item. *(Observable in the U1 bench probe, before the pilot.)*

---

#### 0.5 · Un-brick Stop, gate Enter on busy, and ask the TD two questions

**DO** — Emit a terminal signal on the abort path (`claude_worker.py:132` currently gates
`stream_done` on `not self._abort`); add a busy check to `_GrowingInput.submitted` / `_start_worker`;
make the `claude/` directory path overridable. Before install, ask the TD exactly two questions:
*is `$JOB` artist-writable*, and *does a plugin install need review before or after a trial*.

**BECAUSE** — `S2#3` + `S2#4`, mechanism verified (V-S3-5): after `abort()` the loop returns through an
`if self._abort: return` guard, no exception is raised, and **neither `stream_done` nor `stream_error`
ever fires** — SEND stays grey and the header reads *"Stopping — waiting on …"* indefinitely. The only
escape is Enter, which is **not** gated on busy, constructing a second worker that mutates the same
scene through the same executor. S2's note is why both halves ship together: *"the two defects
compound — the second is the only escape from the first,"* and the greyed SEND button tells the artist
input is blocked while Enter proves it is not. The two questions are `S2-U10` and `S2-U4`, answerable
by asking and by nothing else.

**INSTEAD OF** — fixing Stop alone. That loses because it removes the workaround artists will already
have learned, making the product strictly worse for exactly the users who persevered.

**COSTS** — ~0.5 day for both panel changes (the hython panel tier runs: 65 collected, 64 passed, no
segfault, 2.44 s). The questions cost an email.

**FALSIFIED** — an artist reports two interleaved answers as *useful* concurrent exploration. Then the
fix is a second panel session rather than a busy gate, and only the Stop half stands.

---

#### 0.6 · Make the installer see Houdini 22 — **added under attack**

**DO** — Extend `install.py`'s major loop to include 22 (and stop hardcoding a descending list); adopt
the OneDrive-aware search the *other* installer already implements; make `--verify` probe the six
shipping dependencies the README names; deploy the shelf icons or remove the buttons that reference
them; make the Linux path either vendor or **say** it did not.

**BECAUSE** — `S2#12`, `S2#13`, `S2#15`, all Tier 1 (install day, every seat), and verified here:
`install.py:87` iterates `[21, 20, 19]` so on an H22-only seat it exits 1 and on the dual-build seat
`CLAUDE.md` names as the target it **silently installs into the H21 preference directory and prints
"Installed: 11 files"**; its Windows search root is `~/Documents` only, while
`install_synapse_package.py:73-85` documents the OneDrive redirection at length **and handles it**
(V-S3-14); `git ls-files houdini/` returns **3 files** and there is **no `houdini/config`**, so the
shelf's five `SYNAPSE_*` icon references resolve to nothing — a first impression of blank placeholder
squares. And `S2-L6`, re-verified at HEAD (§0.3): vendoring *and* the ABI warning are both
`sys.platform.startswith("win")`-gated, so **a Linux studio gets no vendoring and no notice** — and a
40-artist VFX studio is very likely Linux.

**Why this is a Gate 0 item and not a footnote (`X-23`).** An earlier draft deferred it on the ground
that *"this plan assumes the TD's own seat works."* That ground does not cover the pilot the plan
designs: §1.3 puts **one generalist plus the TD** on it — a second, non-TD seat — and **abort
condition 4 fires precisely when that seat cannot complete the loop.** So the cheapest legibility
failure in the product sat outside every gate in a document whose thesis is legibility, with the
week-1 kill switch aimed straight at it.

**INSTEAD OF** — documenting the manual steps in the README. That loses because the README already
does, honestly, and S2's Day-1 account is what happened *with* that documentation: nine ways to
half-succeed, seven silent, closing with *"import synapse still succeeds, the version still prints,
and the panel never appears. No error. Just absence."*

**COSTS** — ~1.5 days. The OneDrive logic is a copy from the sibling installer; the icons are a file
copy plus a package path.

**FALSIFIED** — the pilot seat is provisioned by the TD by hand from a working checkout, so the
installer is never exercised. Then this drops to Gate 3 **for that studio** — and the question is
answerable in one sentence before writing any code.

---

### GATE 1 — Legible value. The spine S2 says decided the trial.

---

#### 1.1 · Wire usage end to end, stamp it with the shot, and show cost per turn

**DO** — Add a usage slot to `StreamProvider.stream`'s return contract (`providers/base.py:60`); add
the `message_start` branch to the Anthropic SSE handler where `input_tokens` and
`cache_read_input_tokens` arrive; call `_note_usage` from `_on_done`; **stamp each turn with the
current `$HIP`** so cost aggregates per shot as well as per turn; print a session total and a per-turn
cost. Never estimate: if usage is absent the meter stays blank and says why.

**BECAUSE** — `S2.F10` / `S2#10`, verified: `_note_usage` has **exactly one grep hit, its own
definition** (V-S3-6); the label is constructed with `""`; the stream contract has no usage slot
(V-S3-7). The docstring already states the intent — *"until it lands the meter stays empty — never
estimated."* This is the direct answer to S2's decisive sentence: *"a tool with four incidents and a
number on the other side survives; a tool with four incidents and a blank meter does not."* It also
closes `S2-U13` (does prompt caching hit), because `cache_read_input_tokens` is the one field that
settles it and precisely the field with no branch. The `$HIP` stamp exists so pilot criterion 3 is
measurable in the unit it asks for (`X-14`).

**INSTEAD OF** — a local `tiktoken` estimate. That loses twice: `S2-U12` establishes every cost figure
in this project is already a **tiktoken/cl100k proxy** and the point is to stop proxying; and a wrong
number on a TD's cost sheet is worse than a blank one — R127 in this project's own words, *"a wrong
number in a document about not publishing wrong numbers."*

**COSTS** — ~2 days across the provider seam and the panel.

**FALSIFIED** — usage arrives and the TD still cannot answer *"what did it cost us"* because the
missing unit was per-**artist**, not per-turn or per-shot. Then a third aggregation key is needed and
this item is extended.

---

#### 1.2 · Make the provenance record say what changed, give it one reader, and stop stamping failures as verified

**DO** — Three parts. **(a)** Add the change content to the `FloorGate` record: node path, parm name,
before → after. **(b)** Ship one reader — a `synapse_session_report` answering *"what did SYNAPSE do
to this scene today"* in plain language. **(c)** **Make a failed operation record as failed:** have
`_finalize` read `response.success` and not only `integrity.fidelity`, so the `IntegrityBlock` stops
reporting `verified / fidelity 1.0` for ops that returned `success=False`. Move the content-bearing
`AuditLog` write **before** the `handle()` except-arms so failures are recorded at all.

**BECAUSE** — `S2.F15` / `S2#47`, verified: the record carries `payload_digest` + `result_digest` and
**no node path, parm name or value** (V-S3-16); the only reader in the tree is `doctor.py`, which lists
the newest **three filenames** (V-S3-17); the content-bearing `AuditLog` is written only from
`_submit_logs`, reached only after a *successful* invoke — so **the failure case, the one the artist
asks about, is the one case not recorded.** Part (c) closes `S2#6`/`S2.F3`, a **Tier-1, install-day,
every-seat** mechanism that an earlier draft mentioned only inside this item's INSTEAD OF and never
fixed (`X-21`): `handle()` never raises — five `success=False` arms plus a bare `except` — so the
bridge's failure and rollback branches are dead code and the panel prints
`Operations: 12 | Verified: 12 | Violations: 0 | Fidelity: 100.0%` over five failures.
`harness/CLAUDE.md`: *"the differentiator vs. Houdini's native MCP is the receipts. Protect that."*
S2's verdict: **"The receipts are written. Nothing reads them."**

**INSTEAD OF** — surfacing the existing `IntegrityBlock` readout as-is. That loses because the readout
is **actively wrong**, which is why (c) is in the DO rather than the argument. Surfacing it harder
would surface a lie harder. **Fix the truth of the record before amplifying its display.**

**COSTS** — ~4 days: record fields ~0.5, the reader ~1.5, the `success` plumbing ~1 (it is on the live
path), moving the audit write ~1 with care (`handlers.py:531-535`).

**FALSIFIED** — artists shown a correct change-list ignore it and go on judging SYNAPSE by whether the
scene looks right. Then legibility is not the deciding property and S2's central thesis is wrong —
the single most valuable thing the pilot could discover, and it would reorder this whole document.

---

#### 1.3 · Let the turn end honestly

**DO** — Route tool errors into the chat surface, not only the header and the Work face. Make the
end-of-turn rail state reflect the turn's actual outcome. Connect the error translator that already
exists. **Surface the foreground guard's refusal — including its sanctioned escape — to the artist**,
which is the half Gate 0.4 deliberately does not carry.

**BECAUSE** — `S2#7`, `S2#14`: `_on_tool_status(name,'error',detail)` writes only a header string and
feeds the Work face, appends **nothing to the chat**, and the comment at `synapse_panel.py:1750-1751`
confirms there is no auto-switch, so an artist on CHAT never sees it; then `_set_busy(False)`
unconditionally sets the rail to *"done / Result ready."* **A turn in which five of six tools errored
ends with a green tick.** The translator that would make the first failure legible has **zero external
callers** (V-S3-21), so a first prompt on a credit-less account returns a raw HTTP 400 blob. The guard
half belongs here because the refusal message already exists and is good (V-S3-10) — it names the
resolution ceiling *and* `force_foreground=true`; what is missing is a path from that string to the
artist's eye.

**INSTEAD OF** — a toast or a badge on the Work face. That loses because it depends on the artist
looking at a face they are not on; S2's whole Week-2 section is failures displayed somewhere nobody
was standing.

**COSTS** — ~1.5 days.

**FALSIFIED** — errors in the chat produce alarm fatigue and artists start ignoring the chat. Then the
answer is severity tiering, not surfacing, and this item is refined rather than reversed.

---

#### 1.4 · Stop sending the whole tool catalogue to ask what frame it is

**DO** — Put `panel/tool_filter.py` in the request path: select the tool subset before handing it to
`ClaudeWorker` at `synapse_panel.py:1667`. Keep the full set reachable by an explicit escalation when
the chosen subset comes back insufficient. **Second use, same mechanism:** this filter is how the
pilot's render exclusion is *enforced* rather than requested (§1.3).

**BECAUSE** — `S2#11` / `S2.F11`: **every served tool definition is sent on every API round-trip**, up
to 25 iterations per turn. I verified the mechanism first-hand — the panel hands
`get_anthropic_tools()` **unfiltered** and that array is **126** entries (V-S3-20, V-S3-30) — and
`tool_filter` is imported **only** by two UI modules and one test, i.e. **not in the request path**.
The filter already exists; it is simply not connected.

**On the numbers, stated honestly (`X-3`).** The fixed-prefix figure S2 measured is **15,901 tokens of
tool schemas + 2,615 of system prompt = 18,516 per round-trip**, ⇒ 86 % of a trivial turn. **Producer:
S2's re-run of the token-baseline producer this session — not the committed
`harness/notes/token_baseline.json`, which still records the stale `121 tools / 14,380 tokens` and
would fail its own `check_token_baseline_fresh` today.** I re-derived the tool count (126) and not the
token count; the token figure is therefore S2-derived and is labelled so rather than borrowed as if
this leg had measured it.

**INSTEAD OF** — trimming each tool's description text. That loses because a tool's description is
what the model selects on: shortening 126 descriptions degrades selection across the board, whereas
withholding whole tools leaves every surviving description intact and puts the risk somewhere
measurable — the escalation path, which is exactly what FALSIFIED watches.
*(An earlier draft argued this from `S2-L2`'s coverage curve. That citation was wrong twice: L2
measures `inspect_scene` **scene payload**, not tool-schema text, and its direction is coverage
falling as payload **rises**, not falls. Withdrawn — `X-8`.)*

**COSTS** — ~1.5 days including a guardrail that fails when the fixed prefix grows past a declared
ceiling, and a re-measurement so the ceiling has a live producer.

**FALSIFIED** — filtering causes the model to fail tasks it previously completed because it needed a
withheld tool. Measure task completion before/after on the same prompt set; if completion drops, the
filter is wrong and the escalation path is the whole item.

---

#### 1.5 · Make the mandatory phantom pre-flight answer — **added under attack**

**DO** — Fix `synapse_scout`'s non-answer, and until it answers, **stop the prompt ordering a call the
panel cannot make.** Two halves: (a) diagnose and repair the non-response (S1's earlier run caught it
failing on SQLite **thread affinity** — *"SQLite objects created in a thread can only be used in that
same thread"* — which is a connection-per-thread fix); (b) either add `synapse_scout` to the panel's
tool array or remove the instruction that tells the model to call it.

**BECAUSE** — `S1P-mcp_isolate`, the strongest isolation this project has run on the tool: one fresh
MCP server per case, scout called **first**, 180 s ceiling ⇒ **`elapsed 180.11`, result
`"NO_RESPONSE"`**, while every other isolated case returned in 4.02 s. `S1-F4` found the mechanism on
an earlier run. `CLAUDE.md` **rule 15** makes scout the mandatory pre-flight before emitting any
unfamiliar `hou.*`/`pdg.*`/`pxr.*` call — *"the front-line defence against SYNAPSE's #1 failure class
(phantom APIs)"* — and it does not answer. Meanwhile `system_prompt.py:186-193` **instructs the model
to call `synapse_scout`** before authoring non-template LOP nodes, and I verified the panel's array
does not contain it (V-S3-30, `S2#26`/`S2.F12`): the model either narrates a scout call it never made
or authors from priors, which is the exact failure scout exists to prevent.

**Why this is in the plan at all:** an earlier draft omitted it, having concluded from
`inspect_scene`'s clean re-run that the non-answering class was closed. It is not closed; it moved to
the one tool the project's own law makes mandatory (`X-6`). Gate 0.1's phantom lint and Gate 2.3's
H22 grounding both lean on scout being real.

**INSTEAD OF** — relying on the committed symbol table alone and dropping scout. That is defensible
and cheaper, and it is genuinely the alternative — the table is the membership authority (V-S3-1 shows
it working). It loses only because scout also supplies *retrieval* (which parm names, which idiom),
which the table cannot. **If (a) proves expensive, dropping scout to a table-only check is the correct
fallback and should be taken deliberately rather than by attrition.**

**COSTS** — ~2 days for (a) if the SQLite diagnosis holds; ~0.5 day for (b) either way. **Do (b)
first** — it is the half that stops the model lying about its own grounding.

**FALSIFIED** — scout answers fine in a graphical Houdini session and only fails under the external
MCP stdio surface an artist never uses. Then (a) drops to a release-notes item and only (b) is real.
*(Settled by one call from the panel path — which is Gate 0.1's spike anyway.)*

---

#### 1.6 · Stop manufacturing alarms — **added under attack**

**DO** — Fix the class mismatch so `FreezeChain._escalate`'s `trigger_emergency_halt` call can execute
(it is handed a `SynapseBridge`; its first statement needs `LosslessExecutionBridge`'s
`session_report()`, `shared/bridge.py:2197,2284`). Then either raise the freeze-chain threshold above
a legitimate long render or teach it that a render in progress is not a freeze — so `SUSTAINED FREEZE`
means something when it appears.

**BECAUSE** — `S2#22` / `S2.F7`: **every render over 30 s** trips the chain — the 1 s heartbeat stops,
`Watchdog` reports frozen at 5 s, `_escalate` fires at 30 s with a telemetry dump, forces the circuit
breaker **OPEN**, then calls a halt that raises and logs **`Emergency halt failed (best-effort)`**. So
a TD reading logs after a normal day sees dozens of escalations that mean nothing — *"and on the day
one means something, it is the same line."* S2 names it *"alarm fatigue, manufactured by
construction."* This is objection 6 in §1.2, and it feeds abort condition 3 directly, which is why
its absence from an earlier draft's TD table mattered (`X-24`).

**INSTEAD OF** — silencing the chain. That loses because the chain is the only automatic
freeze-detection the product has, and `S2-L1` guarantees freezes will keep happening. A detector that
cannot distinguish a hang from a render is the defect; deleting the detector is not the fix.

**COSTS** — ~1 day for the class mismatch, ~1 day for the threshold/awareness half.

**FALSIFIED** — with renders excluded from the pilot (§1.3), the chain never fires and the TD never
sees the noise. Then this drops below Gate 3 *for the pilot* and returns the moment renders are in
scope. **It stays in Gate 1 because the log is read by the person holding the veto.**

---

### GATE 2 — The first-session moment.

---

#### 2.1 · Decide the router question, because two recipe libraries depend on it

**DO** — Choose one, explicitly, and write the choice down. **(a)** Construct `TieredRouter` on the
shipped panel's path so Library B's triggers can fire; or **(b)** retire the trigger regexes and
re-shape Library B as tools/prompt content the LLM selects. **Then reconcile the two libraries** —
21 in `panel/recipe_book.py`, 62 in `synapse/routing/recipes/` — into one, whichever way (a)/(b) goes.
Add a check that fails when a recipe carries a trigger no reachable code can match, **and** one that
fails when two recipe libraries are both live.

**BECAUSE** — this leg's own finding, verified end to end (§1.1): Library B's 62 recipes ship with
natural-language triggers (V-S3-24); `TieredRouter` is built in exactly one place (`S1-F3`);
`route_chat` is both a **dead handler no tool reaches** (V-S3-29) and sent only by a module that is
**not the shipped panel** (V-S3-26/27/28); `router_stats` returns `{"error":"Router not initialized"}`
on **both** transports. Meanwhile Library A's 21 recipes **are** palette-reachable and actionable
(V-S3-31/32). So the product already ships **two competing stories about how a recipe is invoked**,
with different content, and the discoverable one is the poorer one. `S2-L7` gives the shape of the
disease: 23 panel modules / **10,905 LOC — 40 % of `panel/` (27,379 LOC at HEAD) and 10.8 % of the
package (100,574 LOC excluding `_vendor`)** — are unreachable from the shipped entrypoint.
*Both denominators stated because an earlier draft carried S2's pre-correction "40 % of the package",
a 4× error the adversarial pass caught (`X-20`); `chat_panel.py` is inside that 40 %.*

**INSTEAD OF** — surfacing Library A in the UI and leaving the router question open. That loses
because it entrenches the two-library split rather than resolving it, and a live regex nothing can
match is exactly the *"built, correct, connected to nothing"* pattern `R126` found during
housekeeping.

**COSTS** — (a) ~3 days, and it inherits `R123`'s caution. (b) ~1 day. Reconciling the libraries:
~1 day either way. **(b) is the smaller, more honest move for a pilot; (a) is the larger product
bet.** A value judgement between defensible options ⇒ escalated, not decided (`for_ruling`).

**FALSIFIED** — an artist typing *"set up a three-point rig"* already gets the right result via the
LLM calling `synapse_list_recipes` unprompted, at acceptable token cost. Then the router is dead
weight, (b) is correct with no further argument, and only the reconciliation remains.
**Directly measurable before writing any code, and it should be measured first.**

---

#### 2.2 · Ground the model in the build it is actually running in

**DO** — Replace the H21 references in `system_prompt.py` with values from the injector `R99` already
landed. **The guard must match `Houdini 21|H21|21\.0\.` — not `Houdini 21` alone — and must carry an
explicit allowlist for dated historical notes.**

**BECAUSE** — `S2#2` / `S2.F12`, verified verbatim (V-S3-3): the prompt tells the model it is
*"embedded directly inside Houdini 21"*, that node types must exist *"in Houdini 21.0.671"*, and that
*"The H21 docs corpus is the authority."* `build_system_prompt()` assembles it on every send; R99's
data layer landed and **the prose layer did not.** `S0-F9` (`S0_SCOUT.md` §1.6, §1.9) prices it: H22
renamed seven Solaris LOP/SOPs (Layout→Paint Instances, Instancer→Copy to Points, five UsdSkel),
removed `hou.ChannelEditorPane` plus ten `hou.Node`/`ApexNode` methods, and made `XformCommonAPI` the
transform default. Since the pilot task **is** Solaris, this lands squarely on it.

**The guard is specified this way because the obvious version cannot fail (`X-19`).** There are
**four** H21 mentions, not three, and `grep -c "Houdini 21"` returns **2** — so after fixing :51 and
:189 the check would report clean while :193 still tells the model the **H21** corpus is authoritative,
which is the exact defect this item exists to close. Law 1: a check whose stated failure condition
does not cover its own target is a decoration. The allowlist exists because :197 is a *legitimate*
dated note (*"karmaphysicalsky bug (H21)"*) and a guard that fails forever on a correct line gets
disabled — which is how guards die.

**INSTEAD OF** — regenerating the documentation corpus first. That loses on sequencing, not merit:
`S2#58` shows `houdini21-reference` is a hardcoded path literal in **three** production modules, a
separate multi-day item. These string literals are the cheapest correction with the largest reasoning
delta, and independent of it.

**COSTS** — ~0.5 day including the guard.

**FALSIFIED** — an A/B on the same prompt set shows no difference in the validity of authored node
types between H21 and H22 prose. **Producer, corrected (`X-16`):** collect the node types each run
authors and check them against a **live `hou.nodeTypeCategories()` enumeration** (or the
`emitted_node_types` catalog). *Not* the `h22_symbol_table.json` — that enumerates `hou.*` attributes,
so it can see the removed-methods half of `S0-F9` and is **blind to the seven node-type renames**,
which is the half that lands on the Solaris task. As originally written the A/B would have returned
"no difference" for the wrong reason.

---

#### 2.3 · Fix the 21 rows that type a sentence under a footer reading "Enter run"

**DO** — Delete or wire the **21 `command`-category rows** (`_CATEGORY_PREFIX` has no `command` entry),
which are exactly the 21 slash commands `R19` ordered removed. Fix the footer so it does not read
*"Enter run"* over a row that composes a prompt. Leave the other 207 rows alone.

**BECAUSE** — verified at HEAD (V-S3-4, V-S3-31): `build_palette_entries()` returns **95** rows,
`Counter({'vex': 45, 'command': 21, 'recipe': 21, 'apex': 8})`; `_CATEGORY_PREFIX` covers
`recipe`/`apex`/`vex`, so **74 of the 95 carry an imperative prefix** and the 120 tool rows name their
tool outright (`"Use the \`%s\` tool."`). The palette is a **prompt-composer by construction**
(`command_selected = Signal(str)  # emits a ready-to-send prompt`), so 228 of 228 rows emit prose and
the defect is not "prose instead of dispatch" — it is the **21 rows (9.2 %) with neither a prefix nor
a tool name**, under a footer promising execution. `S2#5` post-correction.

**Scale, stated plainly.** An earlier draft carried the pre-correction figure — *"95 of 228 (41.7 %)
send prose instead of dispatching"* — and built a DO around *"make palette rows dispatch."* That
inflated a Tier-1 headline **4.5×** and aimed a 1.5-day item at a *design property* rather than a
defect. Caught by two independent lenses (`X-1`, `X-20`) and by this leg's own reading of S2's
corrected copy. **Cost falls from ~1.5 days to ~0.5 day** as a result.

**INSTEAD OF** — removing the `/` hint from the placeholder. That loses because it leaves a first-run
surface of one line and three verbs (`S2#16`) with no discoverable capability, and it would remove
Library A's 21 working recipe rows — the one recipe-discovery path that functions today.

**COSTS** — ~0.5 day.

**FALSIFIED** — instrumented first sessions show artists never press `/` and type prose instead. Then
the palette is not on the first-session path and this drops below Gate 3. *(Directly observable in
pilot week 1.)*

---

### GATE 3 — The TD's sign-off pack.

---

#### 3.1 · One command for the point-release upgrade, and a check that fails when it is stale

**DO** — Collapse the four-step symbol-table runbook into one cross-platform command. Add a
`synapse_doctor` check that **fails** when the committed table's build stamp ≠ the running build. Make
the final confirmation step work on the path a TD would call it from.

**BECAUSE** — S2 §2, in the TD's predicted voice: *"a manual, Windows-shaped, four-step
symbol-table regeneration runbook required on every Houdini point release (SideFX ships those roughly
fortnightly), whose final confirmation step calls a tool that cannot report success on the path they
would call it from."* The stakes are `S2#25`: on `/mcp`, `.mcp.json:5` launches stock python, so
`import hou` always raises, `_running_major()` returns `""`, the **H21** table loads, and staleness is
judged against **that same table's own stamp** — expected == actual, so the gate reports
`gate_armed: true, stale: false` while refusing real H22 APIs. That is the 100 %-by-construction defect
`Ruling 2` struck, living inside the anti-phantom gate.

**INSTEAD OF** — regenerating on every Houdini launch. That loses because introspecting a fresh build
costs real startup time on every launch to serve a fortnightly event, and `S2#1`'s lesson is that
startup-path work in this product is where silent failure accumulates.

**COSTS** — ~2 days.

**FALSIFIED** — abort condition 3 fires anyway with the upgrade automated, meaning the burden was
elsewhere. Then `S2-U5` was mis-attributed and the real burden gets named from the pilot log.

---

#### 3.2 · Recompute the one number a release claim may cite — **most of this already shipped**

**DO** — What actually remains: **a check that recomputes `suite_baseline.json`'s `shipping` block and
fails when it is more than N commits stale**, plus an explicit written statement that the shipping
number is measured by hand at release time.

**BECAUSE** — *and this BECAUSE changed under the leg's own currency check (`X-17`).* An earlier draft
asserted *"the ratchet at `checks.py:2135` compares against the file's flat top-level keys, which are
the GATE numbers"* and proposed pointing it at the `shipping` block. **`harness/verify/checks.py`
changed +88/−6 inside this plan's own commit range** (`2105453 merge(Q2): the tuple baseline reader,
built and never landed`), and at `b608efc`:

- `parse_tuple_baseline` (:2129) **hard-rejects the flat shape** with an error naming the exact
  defect — *"would silently cite the gate number as if it covered the shipping build."*
- `check_suite_baseline` (:2195-2206) reads the tuple at the merge-base anchor and binds both legs.
- `check_ci_covers_shipping_surface` (:1841) **already exists** and requires a **Windows lane + a
  vendored-load probe**.

So `S2#63` / `R-S2-5` is **SUPERSEDED**, and two thirds of the earlier DO was already done.
**The proposed remaining third was also wrong:** the ratchet runs `sys.executable -m pytest` — the
**gate** interpreter — so pointing it at the shipping block would compare a system-python run against
an `hython` baseline. That instruction is withdrawn.

**INSTEAD OF** — adding the Windows + hython CI lane now. Still the right long answer, still needs a
Houdini licence in CI: a real cost decision, **not an agent's to take** (Article I). Now with a check
already asserting the requirement, which strengthens the escalation.

**COSTS** — ~0.5 day, down from ~1.

**FALSIFIED** — the recomputed shipping number proves unstable run-to-run (flaky environment rather
than stale measurement). Then this becomes a stability investigation and the number is not yet
citable by anyone.

---

#### 3.3 · Provision the memory key, or say plainly that memory is per-seat

**DO** — Document and provision `$SYNAPSE_ENCRYPTION_KEY` studio-wide in the install path; add a
doctor check that warns when the store holds records the local key cannot read; give `_degraded_load` a
recovery path instead of a permanent latch.

**BECAUSE** — `S2.F9` / `S2#23` / `S2-L5`: the store resolves to `<hip_dir>/.synapse` — **per shot, on
shared storage** — while the Fernet key resolves per seat, auto-generating when absent. Artist B
opening artist A's shot fails to decrypt every `MAGIC_PREFIX` line, sets `_degraded_load = True`,
writes a `memory.jsonl.degraded-load-<ts>` copy beside the hip file, and `save()` raises thereafter
with **no recovery path**. S2's sentence is the product problem: *"It reads as 'the memory feature
doesn't work', not as 'the key isn't provisioned.'"* `DEPLOYMENT.md` already carries the two variables
that fix provenance scoping — this belongs beside them.

**INSTEAD OF** — switching the store to plaintext. That loses against `S0-F4` (`S0_SCOUT.md` §3.1):
OR-5.0 requires reviewing data sources and integrity and rating output handling per tool; a plaintext
store of scene notes on show storage makes the disclosure row worse, not better.

**COSTS** — ~1 day.

**FALSIFIED** — a competent TD provisions the key unprompted from `DEPLOYMENT.md` as it stands
(`S2-U18`'s shape). Then only the recovery path is needed and the provisioning half is documentation
polish.

---

## 3 · What is deliberately NOT in this plan, and the finding that excludes it

| Excluded | Why, from the findings |
|---|---|
| **Anything render-side in the pilot** | S2's *"what breaks worst"*: the 6 pm render is where **every** escape hatch is independently absent — Stop unclickable because the loop it lives in is the thread being blocked; cancel marshalled onto the thread it must preempt; `rkill` with **zero call sites** (V-S3-22); emergency halt unsurfaced with an inert automatic caller. Add `S2#20` and `S2#35`/`#36` and the lane is not pilot-ready inside a quarter. *Honest qualification the attack forced: the guard's refusal is not a dead end — it names a resolution ceiling **and** `force_foreground=true` (V-S3-10), and `allow_px` is per-engine with a hardware rationale. It is a conservative posture with a stated basis, not an unconsidered ceiling.* |
| **Fixing `synapse_inspect_scene`** | Refuted three ways: `R125` measured 0.00–0.08 s directly; S1's re-run returned **767 bytes / 10 nodes on both transports**. The 1800 s observation is real and unexplained; the tool is not the cause. Guarding it would be building against a ghost. **The non-answering *class* is not excluded — it is Gate 1.5, because it still owns `synapse_scout`.** |
| **Arming consent / RBAC for the pilot** | `S2-L10`: the blocking `HumanGate` poll `time.sleep`s on the thread that must draw the approval card — a redesign, not a fix. Auto-approve is *correct* for artist-initiated panel work. Scoped by Gate 0.2. |
| **Farm submission** | `S2-L4` / V-S3-15: localscheduler only, by explicit design and explicit error string. A positioning fact. |
| **The five COPs scaffolds** | `S1-F11`: Gray-Scott reaction-diffusion, DLA growth, pixel-sort, plus two S1 found. *"A lighting TD on a deadline has never wanted one. They are five entries on a feature list and zero minutes saved."* |
| **Per-turn undo transactions** | `S2-L3`: the undo unit is one tool call because a request is N tool calls. S2's judgement — not worth building; the fix is the undo **label** carrying the artist's request text. Recorded so it is not silently lost. |
| **Autonomous mode in the pilot** | `S2-L10`'s residual is that the same process-wide disarmed gate serves `/mcp` and autonomous paths. Not enabling them is free; hardening them is not. |
| **`R123`'s tree-wide "not live product" label, applied literally** | `R123` ordered `synapse/routing` and `synapse/agent` labelled not-live-product because the RSI loop never runs. But `RecipeRegistry` — Library B, the richest artist-facing asset — lives at `synapse/routing/recipes/` and **is** reached live by `synapse_list_recipes` on both transports (V-S3-24). A tree-wide banner would mislabel it. **The label must be per-module.** Escalated, not decided. |

---

## 4 · Believed, unverified — labelled ASSUMED

Everything here is legal, useful, and **has no finding behind it.**

1. **ASSUMED — that legibility is the deciding property for adoption.** S2's central thesis is an
   *argued conclusion*, not an observation. `S0-F6` (`S0_SCOUT.md` §4.5, §5.4) is blunt about the
   floor: how studios evaluate tools, and who decides, returned **nothing usable at any studio size**;
   `S0_SCOUT.md` §5.5 found **zero** first-hand accounts of any Houdini AI tool trialled at a studio
   and removed. Gate 1 rests on this. Pilot criterion 2 tests it. **If it is wrong, Gate 1 is the
   wrong gate and this document is ordered incorrectly.**
2. **ASSUMED — the ≥30 % median reduction threshold.** Chosen as a number a producer would find
   material. No finding sets it. The only quantified datapoint anywhere is competitor marketing
   describing a single unreproducible run (`S0_SCOUT.md` §3.3).
3. **ASSUMED — that one artist is the right pilot size.** The derived *pressure* is real (nine install
   failure modes, seven silent), but "one is better than three" is judgement. Three artists surface
   concurrency and shared-key defects (`S2.F9`, `S2#44`, `S2#45`) that one never will.
4. **ASSUMED — that a mid-sized studio has a pipeline TD with time to evaluate this.** `S0-F6`
   (`S0_SCOUT.md` §5.3): TD headcount and TD-per-artist ratio returned **nothing quantitative at any
   size**. S2's "40 artists, 3 generalists, one TD at 50 %" is the brief's scenario, tiered ASSUMED in
   S2 itself. The whole of §1.2 addresses a person whose existence is assumed.
5. **ASSUMED — that Solaris shot assembly is a task a mid-sized studio wants automated.** The tools are
   proven on the host; that the *task* is a pain point is evidenced nowhere in S0.
6. **ASSUMED — that S1's ~2 s per-call figure is a connection cost, not a per-tool cost an artist
   pays.** Both live sweeps return **~2.01 s for every read-only tool regardless of payload size
   (767 B → 30 KB)**, and the isolate probe a uniform **4.02 s**. Reading the producer
   (`s1_ws_readonly_sweep.py:77-91`) shows **no sleep and no poll**: `elapsed` spans a **fresh
   WebSocket connection per call**, so the cost is dominated by connection setup and the uniformity is
   explained. **Whether a persistent panel session pays it is NOT established**, and I decline to
   publish "every tool call costs 2 s" — a number without its conditions. *Settled by: one instrumented
   panel session, per-tool wall-clock inside a single connection.*
7. **ASSUMED — that Gate 0.1/0.3 makes long ops bounded rather than responsive.** It bounds the
   **caller's wait**; it does **not** make a render or a 127 KB `execute_python` interruptible.
   `S2-L1` still holds and the UI still freezes for the duration of main-thread `hou` work. Anyone
   reading Gate 0.1/0.3 as a responsiveness fix has read it wrong.
8. **ASSUMED — that S2's ranking is right.** S2 says so itself: *"the mechanisms are anchored, the
   order is argued."* This plan's gate ordering inherits that, now with two premise tests promoted
   ahead of it.
9. **ASSUMED — that the studio's security review happens before the pilot.** `S2-U4`. Gate 0.1 is
   ordered first *because* the answer is unknown and the cost of being wrong is asymmetric.
10. **ASSUMED — that S0's absence claims about H22 hold.** Ten independently fetched primary pages read
    **through WebFetch's summarisation layer**, which S0 flags itself: a summariser omitting something
    is indistinguishable from a page not containing it. `R120` treats it as settled and struck the
    positioning's opening premise on it. Strong. Not a grep of the raw doc tree.
11. **ASSUMED — that the corrected S2 copy is the authority rather than the committed one.** §7 D2
    explains the reasoning and it is a judgement call that inverts `R127`'s default. A human should
    ratify it.

---

## 5 · What would falsify this plan as a whole

1. **An artist completes a real shot in week 1 and the value is obvious without Gate 1.** Then
   legibility was not the binding constraint, S2's thesis is wrong, and the right plan is capability
   work on the render lane.
2. **The security review happens first and the `0.0.0.0` bind ends the conversation before any of this
   is read.** Then Gate 0.1 was not merely first, it was the *only* item.
3. **P-1 fails.** `assemble_chain` does not do on a host what its docstring says. Then the Q1 answer
   narrows, the pilot task shrinks, and Gates 0–3 are spent on a smaller prize. *This is why it now
   runs first.*
4. **The token bill makes it uneconomic at any legibility.** `S2-L2`: 443 → 113,411 tokens (**256×**)
   while single-call scene coverage falls **100/100/73/51/10/11 %** as payload rises. `S2-U12`: every
   cost figure is a proxy — the Anthropic account has no credits, so `messages.create` **and**
   `count_tokens` both return HTTP 400. **Nobody has ever seen a real bill for this product.**
5. **An artist reads `Fidelity: 100.0%` beside five red errors and stops trusting every readout,
   including the ones Gate 1 fixes** (`S2-U3`). Then trust is not additive and repair *order* matters
   more than repair content.

---

## 6 · The adversarial pass — what it broke, in both directions

S0, S1 and S2 each shipped with *"no adversarial pass ran"* as a recorded blocker (`R124`, `R-S2-1`).
This leg ran one against its own draft: **four hostile lenses** (citation integrity, reasoning and
falsifiability, independent anchor re-derivation, completeness) then **eight refutation passes**, each
lens required to return ≥2 `SOUND` entries as a specificity control (`R79`'s discipline).

```
12 agents · 351 tool calls · 1,717,339 subagent tokens · 26 min
54 entries: 5 survived refutation · 3 refuted · 25 capped-unverified · 16 SOUND controls
```

**Corrections adopted** — every one traceable, and none of them cosmetic:

| id | What it broke | Where it is now |
|---|---|---|
| `X-1` / `X-20` | **The palette headline was inflated 4.5×** — 95/228 (41.7 %) *"instead of dispatching"*. No row dispatches; the widget is a prompt-composer by design, and 74 of 95 legacy rows carry an imperative prefix | §0.4 dead premise 3, §1.1 mechanism 4, Gate 2.3 rescoped 21/228 (9.2 %); cost 1.5 d → 0.5 d |
| `X-2` | **Gate 0.1 and Gate 0.3 cancelled each other** — minting the auth key 401s the fast path 0.3 revives, silently restoring the GUI-thread fallback | merged into one item, with client-side credential propagation, an auth pin test, and a positive path assertion |
| `X-3` | Currency claim over-scoped: *"S2's ledger is current at HEAD"* | scoped to `python/`; `checks.py` re-read; `S2#63` marked SUPERSEDED |
| `X-4` | *"5 of 286 test files"* — a figure S2 §6 supersedes | 3 live-gated of 279, 81 fake-`hou`; strengthens P-1 |
| `X-5` | §0.2's promised section-anchor mitigation was absent from most `S0-F` citations | applied |
| `X-6` | *"not a live defect"* over-generalised from `inspect_scene` to the whole hang class | new Gate 1.5 — `synapse_scout` `NO_RESPONSE` at 180 s |
| `X-7` | *"the ONLY route to the recipes…"* — there are **two recipe libraries** | §1.1 rewritten; Gate 2.1 now reconciles them |
| `X-8` | Gate 1.4's INSTEAD OF cited `S2-L2` for the wrong subject **and the wrong direction** | citation withdrawn, real argument supplied |
| `X-9` | 0.3 framed as repairing a regression; the path has **never executed** | cost 1 d → 3 d, second spike added |
| `X-10` | *"Stop becomes clickable"* — contradicted by the plan's own §4.7 | withdrawn; what 0.3 buys stated precisely |
| `X-11` | U1's bench probe assigned to an item that neither contained nor budgeted it | budgeted in 0.4 |
| `X-12` | 0.4 budgeted a render refusal that already exists | deleted; pointed at Gate 1.3 |
| `X-13` | `harness/state/posture.json` is a file an installed seat never has, read by a tool with no route to it | 0.2 split into harness + product halves |
| `X-14` | Pilot criterion 3 asked for dollars/shot from an item producing dollars/turn | `$HIP` stamping added; criterion restated |
| `X-15` | The two cheapest premise tests sat last | promoted to P-1 and P-2, ahead of Gate 0 |
| `X-16` | 2.2's falsifier named an instrument **blind to node-type renames** | producer corrected to a live node-type enumeration |
| `X-17` | Gate 3.2's mechanism no longer existed at this plan's own commit; two thirds already shipped; the proposed DO would compare mismatched interpreters | rewritten; cost 1 d → 0.5 d |
| `X-19` | 2.2's guard **could not fail on its own target** (`grep "Houdini 21"` → 0 while `H21` survives); four mentions, not three | guard widened + allowlisted |
| `X-21` | Tier-1 row 6 (failed ops stamped `verified / fidelity 1.0`) was argued about and never fixed | Gate 1.2 part (c) |
| `X-22` | Abort condition 2 could never fire, and the render exclusion had no enforcement | condition reworded; exclusion enforced via the Gate 1.4 filter |
| `X-23` | The installer deferral did not cover the two-seat pilot its own abort 4 targets | new Gate 0.6 |
| `X-24` | §1.2's TD table omitted the log-noise objection that feeds abort 3 | objection 6 + new Gate 1.6 |
| `X-25` | Pilot criterion 1 was confounded **toward** SYNAPSE by a learning curve, with no variance treatment and no instrument for criterion 2 | interleaved controls, distribution reported, instruments named |

**Refuted — attacks that did not survive**, recorded because a pass that only accumulates is not
measuring anything: an attempt to promote the Gate 3.2 finding to SHOWSTOPPER (it is a bounded
line-number-and-adjective repair); an attempt to show the Q1 candidate was smuggled preference rather
than derived (S1-F7's `the_inversion` field supports the derivation verbatim); and an attempt to void
Gate 1.4 on the ground that its insertion point lacks the needed mechanism (the mechanism is there —
V-S3-20).

**What held under direct attack** (16 `SOUND` entries; the two most load-bearing): **V-S3-1** — a
lens re-derived the symbol table independently, reproduced `symbol_count` 35,903, the `blake2b` prefix,
`hou.webServer.port` absent, and **both controls** (`hou.undos`/`hou.hipFile` at 0 descendants),
concluding *"the absence is a true absence and the plan's own false-phantom control is real"*; and the
**0.3 ↔ 0.4 coupling** — two lenses independently tried to find a second caller of
`estimate_inline_cost` and could not, grading it *"the sharpest structural argument in the document —
forced by the code, not asserted."*

**Not incorporated:** 25 entries were capped from the refutation phase by an explicit budget cap the
workflow logged rather than hid. I triaged all 25 myself and adopted the ones above on my own
re-verification; the remainder are minor or duplicative. **They are unrefuted, not confirmed, and
labelled as such** — the same standing `R124` gave S0's and S1's verdicts.

---

## 7 · Drift

**D1 — S1's deliverable did not exist on disk and was recovered from a session transcript.**
`11f3a79 chore: housekeeping pass` pruned the forensic worktrees. Per `R-S2-2`, `S0_SCOUT.md`,
`S1_INVENTORY.md` and both receipts were **uncommitted** — read-only legs are denied `git commit`
(`R103`) — and were lost. This leg **recovered S1 by replaying its Write/Edit tool inputs** from
`.claude/projects/C--Users-User-SYNAPSE--claude-worktrees-s1-forensic/0e34aceb-….jsonl`: one base
`Write` (17,370 chars) plus **nine sequential `Edit`s, all nine applying cleanly and unambiguously**
to a 20,370-char document, and its receipt (20,513 chars + 8 edits) which parses as valid JSON and
carries `S1-F1`–`S1-F14`. Confidence is high: the recovered receipt's IDs and figures match what
`R121`, `R122`, `R124` and `R125` independently cite, and a refutation agent independently re-ran the
recovery and reported *"25,510 bytes, parses as valid JSON, S1-F1..S1-F14 present."*
**Nothing was written outside this leg's fence to achieve it** — the reconstruction was printed and
read. `83a4820` has since committed the concluded legs' deliverables, which is `R-S2-2`'s remedy
landing; **S1's report is still not among them.**

**D2 — S2 exists in two divergent copies, and the committed one is the earlier draft.**
`83a4820` committed `S2_PREMORTEM.md` at **1,258 lines**. The worktree copy is now **1,388 lines** and
contains the adversarial corrections `R-S2-1` said were outstanding. The committed copy therefore
still carries the palette figure at 41.7 %, *"40 % of the package"*, the escape table without its
attribution, and the foreground-guard quote without `force_foreground` — **all four of which the
worktree copy corrects.** `R127` rules that *"the committed file is the claim"*; here the committed
file is demonstrably the pre-crucible draft.

**This leg cites the corrected copy, and verified each adopted correction first-hand rather than
trusting either** (V-S3-4, V-S3-10, V-S3-31, and the `panel/` 27,379 / package 100,574 LOC
denominators). That inverts `R127`'s default, so it is flagged to `for_ruling` rather than settled
here. **The operational risk is immediate:** anyone reading the committed S2 will cite a 4.5×-inflated
Tier-1 headline in good faith.

**D3 — `S0-F<n>` is an ambiguous identifier across two S0 runs.** §0.2. `R127`'s shape again — *a
second copy nobody declared existed* — now in the citation namespace. Left as a hazard note plus
per-claim section anchors; renumbering another leg's findings from inside this one would make it worse.

**D4 — `harness/notes/forensic/INVENTORY.md` will be mistaken for S1's inventory.** `83a4820`
committed, into the forensic evidence directory beside `S0_SCOUT.md` and `S2_PREMORTEM.md`, a
**v5.4.0-era archived codebase inventory** (43 tools, dated 2026-02-15) whose own banner says the
numbers are stale — and whose "current truth" line (**115 registry tools, v5.33.0**) is *also* stale
against HEAD (**120**, v5.36.4). In a leg sequence whose S1 is literally titled *"the inventory"*, a
file named `INVENTORY.md` in that directory is a trap the next reader walks into by filename alone.
It is not S1's deliverable and nothing in this plan cites it.

**D5 — the tree advanced under this leg mid-run.** `master` moved `b608efc` → `c624ea7` → `83a4820`
while this document was being written. Neither new commit touches product code (`c624ea7` is design
PNGs, rulings and a census JSON; `83a4820` is notes and receipts), so every `V-S3-*` verification
stands at `b608efc` as declared. Recorded because a plan that silently absorbs a moving tree cannot be
re-checked.

**D6 — this leg ran in a real registered worktree**, unlike S0. `.claude/worktrees/s3-forensic` is a
genuine worktree at `b608efc`, so Article V held. `S0`'s `R-2` did not reproduce.

**D7 — this leg's own read-only fence leaked, and the mechanism is worth naming: *importing* product
code is a side-effecting act.** Several verifications in §0.3 (V-S3-24, V-S3-30, V-S3-31, V-S3-32)
were taken by importing SYNAPSE modules and counting live objects — `RecipeRegistry()`,
`get_anthropic_tools()`, `build_palette_entries()`, `recipe_book.RECIPES`. That import chain reaches
the panel package, which **wrote `SYNAPSE/.synapse/panel_settings.json` at 16:16**, inside this run's
window.

Stated precisely, because the direction matters both ways: the file is **gitignored**
(`.gitignore:43:/.synapse/`), so `git status --porcelain` is clean, **no tracked file was modified,
and nothing was lost.** But the write happened, and I described this leg as read-only.

The correct statement is: **reading the tree is read-only; importing it is not.** A leg that counts
live objects to avoid trusting a static grep buys accuracy with a side effect, and the trade is worth
making — the 62/21/126/95 figures are stronger for being live — but it must be declared rather than
assumed away. This is the **eighth** recorded instance of an instruction-level fence not holding in
this repository (`R61`'s three, `R69`'s three, S2's D2, and this one), and the first where the leak
came from *verification* rather than from product code writing where it should not.

---

## 8 · Standing

Never pushed, never merged, never tagged. Nothing outside `harness/notes/**` was written — the S1
recovery was printed and read, not saved. No product code was modified; `git status --porcelain` in
this worktree shows only `.claude/.orch_launched` (pre-existing) and `harness/notes/forensic/` (this
leg's own path). Every recommendation traces to a finding by id; everything that does not is in §4 and
labelled ASSUMED.

**The sentence:**

> SYNAPSE's problem is not that it lacks a moment — it is that its one proven artist-facing lane sits
> behind a panel that runs every tool on the GUI thread because of a single phantom attribute, a prompt
> that thinks it is in Houdini 21 in four places, and two rival recipe libraries of which the
> discoverable one is the poorer and the richer one's natural-language triggers can never fire, because
> the router that matches them is never built on the shipped path. None of that is a capability gap.
> All of it is reachable in the order written above — and the two cheapest things on the list are a
> test that could invalidate the plan and a compliance row that gets you in the door.
