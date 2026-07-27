# S2 — THE PRE-MORTEM

**Leg** S2 · **Harness** `FORENSIC-01` · **Run** 2026-07-27 · **Branch** `forensic/s2-pre-mortem`
**Model** `claude-opus-5[1m]` · **Commit at run** `dfc02c8` (v5.36.0) · **Target** Houdini 22.0.368 / Python 3.13.10
**Mode** READ-ONLY, writes confined to `harness/notes/**` · **Governed by** `harness/AGENT_CONSTITUTION.md`
**Depends on** S0 (scout) · S1 (inventory) — *both read in full before their worktrees were destroyed; see §10*

> It is Q2 2027. A mid-sized VFX studio — 40 artists, 3 Houdini generalists, one pipeline TD at
> 50% — ran SYNAPSE on real shots for one quarter. **They stopped using it.**
>
> This is the account of what happened.

---

## 0 · How to read this

### It is a pre-mortem, not a prediction

SYNAPSE has **zero production users.** Nothing here is a forecast of what will happen. Every
entry is a mechanism that **exists in the tree today**, at `dfc02c8`, with a `file:line` anchor —
assembled into the sequence those mechanisms would produce if a studio met them in the order a
studio meets things.

The story is a device for ordering evidence. The evidence is the deliverable.

### Every claim carries a tier

```
VERIFIED-RUNTIME   observed on the live build this session
VERIFIED-STATIC    read from the tree at dfc02c8
VERIFIED-DERIVED   computed from a VERIFIED input, producer named
REFUTED-LIVE       tested and found false — outranks anything above it
UNVERIFIED         everything else, including anything anyone remembers
```

**There are no unlabelled ASSUMED claims in this document.** That is this harness's stated
failure mode (`SYNAPSE_FORENSIC.md` §1) and the one thing that would make it worthless.

### Three buckets, because they have different answers

```
FIXABLE   a defect. The fix is named, with a rough cost.
LIMIT     true of the architecture. It gets DOCUMENTED, not fixed. The honest question is
          whether a studio can live with it.
UNKNOWN   cannot be told without a user. The observation that would settle it is named.
```

### Ranked by LIKELIHOOD, not severity

A catastrophe requiring six coincidences matters less than the mundane thing that happens every
Tuesday. Studios do not drop tools over the worst case; they drop them over the Tuesday case.
The ledger in §3 is ordered accordingly, and the first fifteen entries all fire on **install day
or the first prompt, on every seat.**

### What this leg did that makes it checkable

Ten read-only domain probes against the live tree and, where possible, the live build — install,
grounding, render, transport, provenance, panel, version-decay, cost, farm, proof — plus the
orchestrator's own first-hand verification of every load-bearing anchor. All ten returned,
~90 anchored mechanisms.

**Several findings below were refuted in-run and are recorded as refutations rather than
deleted,** including one of the orchestrator's own (§6). A pre-mortem that only accumulates is
not measuring anything.

---

## 1 · THE ACCOUNT

> **Tier declaration for this section, stated once and binding on all of it.**
>
> Every **mechanism** below — every `file:line`, every quoted comment, every behaviour attributed
> to the code — is VERIFIED-STATIC or VERIFIED-RUNTIME at `dfc02c8` and is tagged inline where
> the tier is not obvious.
>
> Every **studio fact** — that there are three generalists, that the TD is half-time, that they
> trial between shows, what an artist feels, what is said in the meeting — is **ASSUMED**. It is
> the scenario the brief specifies, and it is the ordering device. It is not evidence and nothing
> in §3–§5 rests on it.
>
> Where the two meet — *"the artist force-quits and loses their scene"* — the **mechanism** is
> verified (no escape exists) and the **reaction** is UNKNOWN. Those are tracked separately in
> §5 (U1, U3, U6, U15).
>
> The narrative frame is REPORTED-supported where S0 found sources: mid-size evaluations are led
> by a pipeline supervisor or head of technology (S0 §4.5, Orca / LMN case studies), and tool
> deployment happens between shows (S0 §4.5, Cinesite's Shahidi, Whiskytree's Monroy). Both are
> vendor-adjacent sources and are tiered accordingly.

### Week −2 · Why they said yes

The pipeline TD reads the README. This matters more than anything else in the account, because
**the README is honest.** It says cost is not flat — it is 256×. It says there is no delta path.
It says the PDG rollback has never executed. It says `hou.undos.group()` groups but does not
reverse, in a section headed *"Undo, precisely"* that opens *"This used to say every mutation is
reversible. That was overstated."* It publishes two test numbers and explains why neither
substitutes for the other.

*(`README.md:33-39, 143-152, 160-186` — VERIFIED-STATIC.)*

**ASSUMED (and it is the load-bearing assumption of the whole account):** that this candour is
what buys the trial.

**Scoped by the adversarial pass.** What is verified is that the README's **posture** is honest —
it volunteers its own failure modes, which almost no vendor document does. What is *not* true is
that its **numbers** are current. By this document's own §6, at `dfc02c8` the README publishes a
Gate figure of 4,989/0 against a measured 5,031/0, a Shipping figure of 4,048/110/771 against a
measured 4,891/95/8, and still lists the `network_explain` segfault under *Known limitations* as
*"Fix in flight"* when it was repaired at `672b247` — **two commits before HEAD**.

So the honest form of the premise is narrower: *the ending cannot be explained by a document that
oversells.* It **can** partly be explained by one whose published evidence has gone stale — and a
TD who takes an honest document at its word and then checks it is exactly the person who finds
that. Stale published evidence is its own trust failure, and the account does not get to rule it
out by assertion.

They pick the gap between two shows (S0 §4.5 — REPORTED, two practitioners). Three generalists,
one quarter, no client work at risk.

### Day 1 · The install, and the first thing that is not there

The TD installs on their own seat first. It works — they wrote the machine that works.

Then they roll it to three artists, and the install surface turns out to have **nine distinct
ways to half-succeed, seven of them silent.** The README names three of them honestly and by
name (the BOM, `hpath`-not-`path`, both `PYTHONPATH` entries) and closes with the sentence that
turns out to describe the whole quarter:

> *"Get any of these wrong and `import synapse` still succeeds, the version still prints, and
> the panel never appears. No error. Just absence."* — `README.md:115`

What the README does not name:

- **Install day forks, and neither branch is clean.** This is a *branch*, not two independent
  certainties — the adversarial pass caught the original draft asserting both on every seat.

  | Route | Houdini major targeted | Shelf icons |
  |---|---|---|
  | **Documented** (`scripts/install_synapse_package.py`, the one the README names) | correct — writes into every existing `houdini2*` pref dir | **none** — `grep -ci icon` returns **0**; there is no `houdini/config/Icons` in the tree, and the SVGs sit unused in `design/icons/svg/` |
  | **Retired** (`install.py`, at the repo root, the obvious name) | `for major in [21, 20, 19]` — **22 is not in the list**. Exits 1 on an H22-only seat; on the dual-build seat CLAUDE.md names as the target it silently installs into **H21** and prints *"Installed: 11 files"*. Also searches only `~/Documents`, never `~/OneDrive/Documents` | **deployed** — `install.py:154-160` copies the 32 px SVGs to `<prefs>/config/Icons` |

  `docs/studio/UPGRADE.md:119` says plainly: *"The legacy root `install.py` is retired — never
  run it."* So the correct severity is second-order rather than install-day-certain: **two
  shipping strings still point a stuck user at a retired installer whose major loop stops at
  21** — and a TD whose panel did not appear is exactly the person who goes looking for a file
  called `install.py`. (`install.py:78,87,139,154-160`, `UPGRADE.md:119` — VERIFIED-RUNTIME,
  FIXABLE. All four facts verified independently by the orchestrator.)
- **`--verify` is green on a machine missing all six shipping dependencies.** It runs five
  checks — clone, package file, vendored SDK, API key, Houdini — and never probes `websockets`,
  `mcp`, `orjson`, `xxhash`, `filelock` or `pytest-asyncio`, the six the README itself names at
  `README.md:160-163` as *"shipping dependencies that are not shipped."*
  (`scripts/install_synapse_package.py:351,441` — VERIFIED-RUNTIME, FIXABLE.)
On the documented route the shelf's seven buttons reference five `SYNAPSE_*` icons resolved from
`<HOUDINI_PATH>/config/Icons` — a directory that does not exist in the tree
(`synapse.shelf:13`, `packages/synapse.json:27`, `git ls-files houdini/` → 3 files).

**So on the route the README prescribes, the artist's first impression is a toolbar of blank
placeholder squares.** Nothing has been typed yet.

**And on a Linux seat, none of the vendoring happens and nothing says so.**
`python/synapse/__init__.py:62-68` prepends `_vendor` only when the interpreter is 3.11/3.13
**and** `sys.platform.startswith("win")`; lines 90-94 compute the ABI-risk warning behind the
same win-only predicate. So on Linux the vendor tree is inert *and* the loud warning that names
the remediation cannot fire. A 40-artist VFX studio is very likely Linux.
(VERIFIED-STATIC, **LIMIT** — the natives are `win_amd64`-locked by construction,
`_vendor/README.md`.)

### Day 2 · The first prompt

An artist opens the panel. It contains one line — *"Ready. What are we building?"* — three verbs
(EXPLAIN / FIX / OPTIMIZE), a BUILD HDA button, and an input box whose placeholder reads
**`Ask SYNAPSE…  ·  / for commands`** (`synapse_panel.py:96, 679-681`).

There is no tool list, no capability summary, no example, and no key check at boot. Nothing on
screen indicates that 120 registered tools or a **62-recipe library** exist. The recipes —
S1 called them *"the most substantial and most undersold asset in the product"*, with real
sensor dimensions for eight cinema cameras and a correct 4:1 three-point lighting ratio — have
no UI surface at all.

So the artist does the one thing the placeholder tells them to do. They press `/`.
*(**Depends on U6** — whether an artist presses `/` or Ctrl+K unprompted is unobserved. If they
never do, the 95 dead palette rows cost trust without ever generating a ticket, which is worse,
not better.)*

**95 of the 228 palette rows (41.7%) send an English description to the model instead of
dispatching** — including all 21 slash commands that CTO Ruling 19 ordered *removed* three days
earlier. `tool_palette.py:119` builds the payload as
`send = (_CATEGORY_PREFIX.get(e.category,"") + (e.description or e.label)).strip()`, and
`_CATEGORY_PREFIX` has entries only for `recipe`/`apex`/`vex`. Picking `/help` sends the string
*"Show help and available commands"* to the model, which invents a command list SYNAPSE does not
have. The palette footer says **"↑↓ navigate · Enter run"**.
(`tool_palette.py:61-65,119`, `command_palette.py:92-114` — VERIFIED-RUNTIME, FIXABLE.)

The panel's single piece of onboarding points at the one feature family that does nothing.

### Day 2, later · The freeze that is not a bug in the render

The artist types a real request. Houdini goes *(Not Responding)*.

This is the master mechanism of the whole account, and it is one line:

> `_MCPLocalClient._detect_port()` calls **`hou.webServer.port()`** — which does not exist on
> H21 or H22. On H22.0.368 `hou.webServer` **is** the `hwebserver` module and has no `port`
> attribute. The `AttributeError` is swallowed by a bare `except` at `tool_executor.py:151-152`,
> `_port` stays `None`, `available` is `False` **forever**, `try_mcp_tool_call` returns `None`
> on every call, and every tool falls through to the Qt signal path — where
> `ToolExecutor.execute_tool` is a `@QtCore.Slot` delivered on the **Qt main thread**.
>
> `tool_executor.py:146,157,480` · `claude_worker.py:251` — **VERIFIED-RUNTIME, FIXABLE.**

**Be precise about what this costs, because the adversarial pass corrected an earlier draft that
overstated it.** Repairing `_detect_port` would *not* make tool execution non-blocking — behind
that endpoint every `hou.*` call still marshals onto Houdini's main thread, and the GUI still
stops repainting for the payload's duration. That part is L1, and it is arithmetic.

What the dead path actually costs is everything the fast path's own docstring promises
(`tool_executor.py:466-479`, read directly):

- **the per-call bound** — a C7 socket timeout, 35 s default and 120 s for render. Without it,
  `run_on_main` fast-path-2 runs the payload inline with **no bound of any kind**.
- **the no-retry discipline** — on timeout it raises *"timed out client-side but may STILL be
  running inside Houdini — do not retry"*, explicitly so the caller cannot re-dispatch a
  possibly-mutating tool a second time. **That protection is lost too**, which is a
  mutation-safety consequence, not a latency one.
- **the deadlock guard** — *"NOT safe to call from the main thread (will deadlock with
  hdefereval)."*

So the honest statement is: **every tool runs unbounded on the GUI thread, with the
double-dispatch guard gone.** The module's own comment records a 127 KB `execute_python` freezing
the loop for over 5,000 ms (`bridge_adapter.py:230-233`). A pre-flight freeze warning exists
(`tool_executor.py:300`) and has zero consumers.

The artist is not told. There is no progress bar, no spinner, no explanation. Houdini simply
stops repainting for as long as the agent is working.

### Day 3 · Stop

The artist, sensibly, tries to stop a run that is going the wrong way.

**Pressing Stop bricks the panel.** `_on_stop` calls `worker.abort()`, disables the Stop button,
and deliberately does *not* call `_set_busy(False)` — its docstring says it lets the worker's
real completion reset to idle. But `ClaudeWorker.run` ends with
`if not self._abort: self.stream_done.emit()` (`claude_worker.py:132`). After `abort()` sets
`_abort=True`, the loop returns through one of its three `if self._abort: return` guards, no
exception is raised, and **neither `stream_done` nor `stream_error` ever fires.** SEND stays
grey, STOP stays disabled, the header reads *"Stopping — waiting on `<tool>`…"* indefinitely.
(`synapse_panel.py:1761-1764,1723,1736` — VERIFIED-RUNTIME, FIXABLE.)

The only escape is pressing Enter — and **Enter is not gated on busy.** `_GrowingInput`
emits `submitted` on any un-shifted Return with no busy check; `_start_worker` has no
running-worker check. It constructs a second `ClaudeWorker`, connects seven signals, and starts
it while the first is still parented to the panel with its connections live. Two answers stream
into the same chat interleaved; two tool loops mutate the same scene through the same
main-thread executor. (`synapse_panel.py:146-148,1599-1603,1653-1683,1767` — VERIFIED-STATIC,
FIXABLE.)

**The two defects compound: the second is the only escape from the first.** The greyed SEND
button tells the artist input is blocked, and Enter proves it is not.

### Week 2 · The things that succeed at doing nothing

None of these produce an error. That is what they have in common.

**The model thinks it is in Houdini 21.** `_IDENTITY` at `system_prompt.py:51` opens *"You are
SYNAPSE, an AI co-pilot embedded directly inside Houdini 21."* Line 189 tells the model node
types must exist *"in Houdini 21.0.671"*; line 193 says *"The H21 docs corpus is the
authority."* `build_system_prompt()` assembles it verbatim on every send. `git grep` for
"Houdini 22" across the prompt layer returns **zero hits.** R99's data-layer fix landed — the
injector exists and the panel calls it — and the **prose layer did not.** An artist asking about
Copernicus, which barely existed in H21, gets legacy-COP reasoning.
(`system_prompt.py:51,189,193`, `synapse_panel.py:258-260` — VERIFIED-STATIC, FIXABLE.)

**The panel orders the model to call a tool the panel does not advertise.**
`system_prompt.py:186-193` instructs: *"before issuing `synapse_solaris_build_graph` with any
NON-template nodes, call `synapse_scout` to confirm each LOP node type…"* — but `synapse_scout`
is registered only in `mcp_server.py`, is absent from `TOOL_DEFS`, and therefore absent from the
126-tool array `tool_bridge.py` hands the panel. The model either narrates a scout call it did
not make or authors from priors, which is the exact failure class scout was built to prevent.
(`tool_bridge.py:50-54` — VERIFIED-RUNTIME, FIXABLE.)

> **Audience correction from the adversarial pass, and it sharpens rather than softens.** An
> earlier draft placed a second grounding finding here — that on the `/mcp` path the phantom
> gate loads the **H21** symbol table while reporting `gate_armed: true, stale: false`, because
> `.mcp.json:5` launches stock python outside Houdini so `import hou` always raises and staleness
> is judged against that same table's own stamp (a self-referential comparison, structurally the
> defect Ruling 2 struck).
>
> **That finding is real and stays in the ledger as row 25 — but it is not on this artist's
> path.** `.mcp.json` is a stdio config consumed by Claude Code / Claude Desktop: a **developer
> and TD surface**. The artist in this account opens a Houdini python panel, whose client is
> `_MCPLocalClient` against the in-Houdini `hwebserver`.
>
> On the artist's path the situation is *worse and simpler*: the model is told to ground itself
> and **has no scout tool at all**, so the symbol table — H21 or H22 — is never consulted.

**Every turn ends green.** `_on_tool_status(name,'error',detail)` writes only a header string and
feeds the Work face; it appends **nothing to the chat**, and the comment at
`synapse_panel.py:1750-1751` confirms there is no auto-switch, so an artist sitting on CHAT never
sees it. Then `_set_busy(False)` unconditionally sets the rail to **"done / Result ready."** A
turn in which five of six tools errored ends with a green tick.
(`synapse_panel.py:1738-1751,1781-1784` — VERIFIED-STATIC, FIXABLE.)

**And the integrity readout agrees with the rail, not with reality.** Both dispatch paths route
through `execute_through_bridge`, whose `Operation.fn` is `handler.handle(command)` — and
`handle()` has five `success=False` return arms plus a bare `except Exception`. **It never
raises.** The bridge's failure and rollback branches are entered only when `operation.fn` raises,
so a failed op reaches `_finalize`, which reads `integrity.fidelity` and never
`response.success`. The panel's Session Integrity readout says
**`Operations: 12 | Verified: 12 | Violations: 0 | Fidelity: 100.0%`** for a session in which five
tool calls errored and left half-built networks in the scene.
(`bridge_adapter.py:366-371`, `handlers.py:544-574`, `shared/bridge.py:1750-1774` —
VERIFIED-RUNTIME, FIXABLE.)

The chat shows the errors. The receipt shows a clean sheet. **The two never reconcile, and the
receipt is the product's stated differentiator.**

### Week 3 · The afternoon

6:00 pm. An artist asks SYNAPSE to render the shot.

If the model reaches for `houdini_render`, the foreground guard fires: `_BUDGETS` sets
`deny_px = 1024*1024` for every Karma engine, and 1920×1080 is 2,073,600 px — so the render is
**refused**, with a suggestion to reduce the resolution to ≤65,536 px total. That is 256×256.
(`foreground_guard.py:53-59`, `handlers_render.py:473-485` — VERIFIED-RUNTIME.)

If the model reaches for `safe_render`, `render_progressively`, `shot_render_ready` or
`render_sequence` — and the shipping system prompt steers it toward exactly those words — it
calls `_handle_render` **directly**, bypassing the guard, the session token and the bounded
wait. (`handlers.py:658`, `handlers_render.py:2017,2148,1533`, `handlers_usd.py:1945-1954` —
VERIFIED-STATIC.) The same prompt also tells the model to set **`soho_foreground=1`**, the
maximum-freeze flag, while the `/mcp` tool preamble says the opposite
(`system_prompt.py:165` vs `mcp_tools_render.py:13-14`).

So the render starts, on the Qt main thread, inline. The authors documented what happens next
themselves, in the source:

> *"panel-inline — the Qt slot IS the main thread, so `run_on_main` takes FAST PATH 2 and again
> discards this timeout; the payload runs inline with NO bound of any kind. That is honest by
> construction: nothing in Python can interrupt the main thread from the main thread, so any
> number here would be a lie. **The panel freezes for the render's duration.**"*
> — `handlers_render.py:109-113`

At 6:01 the artist realises the camera is wrong. Here is everything they can do about it:

| Escape | State at `dfc02c8` |
|---|---|
| **Stop button** | drawn, enabled, **unclickable** — the Qt event loop is not pumping. The queued click fires when the render finishes. |
| **`synapse_render_farm_cancel`** | registered `_ro=False`, so `/mcp` marshals it **onto the blocked main thread** with a 10 s budget. Returns *"Houdini's main thread didn't respond in time."* Forever. (`_tool_registry.py:1206-1210`, `mcp/server.py:621-626`, `core/timeouts.py:16`) |
| **`rkill`** | R73 established it works. `grep rkill` across `python/` and `shared/` returns **zero hits.** SYNAPSE does not call it. |
| **Emergency halt** | not surfaced in the shipped panel. R29 ordered it into the rail overflow; the overflow at `synapse_panel.py:1474-1494` contains Copy conversation / Engine / Larger text / Default text. |
| **`hou.RopNode` cancel** | does not exist on the build (R58, R73). |

There is no correct action. **What the artist does next is UNKNOWN (U1)** — wait, click the dead
Stop, alt-tab, or reach for Task Manager — and each branch produces a different downstream state.
The branch narrated here is force-quit, which loses everything since the last save: there is no
hip checkpoint or autosave around risky mutations. *The absence of a correct action is VERIFIED;
the choice among four wrong ones is not.*

**Two things then happen that nobody sees.**

First, every render over 30 seconds trips the process freeze chain. The panel's 1 s main-thread
heartbeat stops, `Watchdog` reports frozen at 5 s, and `FreezeChain._escalate` fires at 30 s:
telemetry dump, circuit breaker forced **OPEN**, then
`EmergencyProtocol.trigger_emergency_halt(bridge, …)`. That call is handed
`hwebserver_adapter._handler._bridge` — a `SynapseBridge` — while `trigger_emergency_halt`'s
first statement expects the `shared.bridge` class. It raises, is caught best-effort, and logs
**`Emergency halt failed (best-effort)`**. So a TD reading logs after a normal day sees dozens
of `SUSTAINED FREEZE` escalations that mean nothing — and on the day one means something, it is
the same line. (`freeze_chain.py:47,138-173,202-208`, `session/tracker.py:73` —
VERIFIED-STATIC, FIXABLE.) *That is alarm fatigue, manufactured by construction.*

Second, the truncated frame the killed render left behind **validates as good.** `_handle_render`
sets `render_ok = True` on `exists() and st_size > 0`; `_validate_file_integrity` — the
always-on check that `synapse_validate_frame` and the render farm's per-frame validation both
call — is identically `isfile()` plus `getsize() != 0`. With OIIO absent, `validate_frame`
returns `valid: len(issues)==0` with the summary *"OIIO unavailable — only file integrity
checked."* There is no header or scanline check anywhere.
(`handlers_render.py:966-970,2355-2377,1302-1312` — VERIFIED-STATIC, FIXABLE.)

The corrupt frame reaches dailies. *(**Depends on U20** — whether Karma leaves a non-zero-length
partial file when its host is killed mid-frame is unprobed. If it leaves nothing, the validator's
`exists() && size>0` criterion catches this case and only the lost scene remains.)*

### Weeks 4–8 · The erosion, which is quieter and worse

The trial does not end here. This is the part that matters, because the studio keeps using it.

**Comp stops trusting the AOVs.** `synapse_configure_render_passes` maps beauty→`"C"`,
depth→`"Z"`, normal→`"N"`, crypto→`"crypto_*"`. CTO Ruling 101, from a live probe, established
that on Karma 22.0.368 the **`ray:` prefix is REQUIRED** and that bare source names emit *"a
correctly-named EXR part FILLED WITH ZEROS, SILENTLY. No error, no warning."* `grep 'ray:'`
across `python/` returns zero hits. The EXR opens in Nuke with a correctly-named,
correctly-shaped `Z` channel that is entirely black. Comp spends a day blaming Karma, then
blaming SYNAPSE. **Ten tests pin the bare spellings** (`tests/test_render.py:607-612`) — the
suite is a conformance lock on the defect. (`handlers_render.py:1690-1707,1771` —
VERIFIED-STATIC, FIXABLE.)

**The second artist to open a shot loses its memory permanently.** `MemoryStore`'s storage dir
resolves to `<hip_dir>/.synapse` — per shot, on shared storage. The Fernet key resolves to
`$SYNAPSE_ENCRYPTION_KEY`, else `~/.synapse/encryption.key`, else **auto-generate-and-write** —
per seat, per user profile. Artist B opening artist A's shot fails to decrypt every
`MAGIC_PREFIX` line, sets `_degraded_load = True`, writes a
`memory.jsonl.degraded-load-<ts>` copy beside the hip file, and `save()` raises from then on.
`_degraded_load` has no recovery path. (`store.py:337-363,393-400,446-451`, `crypto.py:88-108` —
VERIFIED-STATIC, **LIMIT** as designed / FIXABLE as provisioned.)

It reads as *"the memory feature doesn't work"*, not as *"the key isn't provisioned."*

**Undo stops meaning what the artist thinks it means.** The undo unit is one **tool call**, not
one request. An LLM answering *"build me a three-point rig"* with 9 `create_node` + 6 `set_parm`
+ 5 `connect_nodes` calls produces 20 undo entries on `/mcp` — and on the raw `/synapse` path,
`handlers_node.py`'s create/delete/connect and `handlers.py:1051`'s `set_parm` contain **zero**
`hou.undos.group` calls, so each `hou` call is its own native entry. The undo menu is a wall of
`SYNAPSE: houdini_create_node: {…}` with truncated payloads. The artist presses Ctrl+Z, one node
disappears, presses it nineteen more times, and overshoots into their own work.
(`handlers_node.py:43,120,141`, `handlers.py:1051`, `shared/bridge.py:1263` — VERIFIED-RUNTIME,
LIMIT + FIXABLE half.)

**The session dies mid-afternoon.** `self._messages` is initialised once and **never cleared
anywhere in the tree**; the worker appends assistant blocks and tool results across up to 25
round-trips and `_on_done` replaces the panel's list with the grown copy. There is no
compaction, no cap, and no "New chat" affordance. Eventually the request exceeds the model's
context window and every message fails permanently. The only way out is closing and reopening
the panel, which silently discards the conversation.
(`synapse_panel.py:278,1720`, `claude_worker.py:191` — VERIFIED-DERIVED, FIXABLE.)

**And a 429 rewinds history without saying so.** `ClaudeWorker` deep-copies the message list, so
tool_use/tool_result blocks live only in the worker; `_on_done` syncs them back and **`_on_error`
does not.** `AnthropicProvider.stream` raises on any non-200 with no retry and no backoff. A 429
after four successful mutating tool calls leaves the scene changed and the transcript unaware.
The artist retries; the model, with no record of the four nodes it created, creates them again.
(`claude_worker.py:84`, `synapse_panel.py:1718-1736`, `anthropic_provider.py:137-142` —
VERIFIED-STATIC, FIXABLE.) Three generalists sharing one key will see 429s routinely.

**Nothing ever tells them anything.** The inside-out perception channel is fully built and never
constructed. `TopsEventBridge` subscribes PDG cook events; `SceneLoadBridge` subscribes
`hou.hipFile.addEventCallback`. A repo-wide grep for either constructor outside `tests/` returns
**exactly one hit** — `host/capture_perception_baseline.py:93`, a standalone script. Not the
server, not the panel, not `mcp_server.py`. A farm cook finishes, a scene is opened, a TOP graph
errors: nothing surfaces. SYNAPSE only answers when asked.
(`scene_load_bridge.py:144`, `tops_bridge.py:303` — VERIFIED-STATIC, FIXABLE.)

### Week 9 · The shot goes to the farm

It does not go to the farm.

`_handle_tops_configure_scheduler` raises before touching the scene on any scheduler other than
local: *"SYNAPSE's PDG integration is localscheduler-only (Deadline/Tractor/HQueue farm
submission isn't wired up)."* The one thing named *"render farm"* is `RenderFarmOrchestrator`,
whose own docstring says *"Local render farm"* and which drives frames through in-process render
callbacks on the artist's own Houdini. (`handlers_tops/cook.py:152`, `render_farm.py:1` —
VERIFIED-STATIC, **LIMIT**.)

Ask for a farm render and you get either a hard error naming three schedulers as unwired, or a
"farm" that pegs the artist's workstation for the whole sequence.

**One thing here is genuinely excellent and must be said with the same precision as the
defects:** a `.hip` that SYNAPSE touched **opens cleanly on a render node with no SYNAPSE
installed.** The emitted-node catalog contains only stock namespaces — 83 bare, 11 `apex::`,
3 `kinefx::`. There are no `.hda`/`.otl` files in the repo at all. The only scene-resident
metadata is inert `setUserData("synapse:*")` strings Houdini reads without SYNAPSE.
(`emitted_node_types.json`, `component_builder.py:46` — VERIFIED-STATIC.)

**This is the failure class that kills most DCC tools** — the Nuke gizmo registered only by
`menu.py` that passes an artist trial and fails on first farm submission; the Maya plug-in that
stamps unknown node types into every scene it touches (S0 §3.2). SYNAPSE does not have it. That
is a real architectural achievement and the studio never notices, because nothing going wrong is
invisible.

### Week 12 · The meeting

The pipeline TD has half a day a week and is asked two questions.

**"What did SYNAPSE cost us this quarter?"**

**Corrected by the adversarial pass, and the corrected version is weaker and more defensible.**
An earlier draft said *"they cannot answer, at any tier."* That is false, and this document
established why two sections earlier: three generalists share one API key, so the **aggregate**
sits on the provider's billing console, outside SYNAPSE entirely.

What is genuinely unavailable is **attribution and the denominator**:

- no per-artist, per-shot, per-turn, or per-session breakdown — anywhere, at any tier;
- no in-product moment where cost becomes visible to the person incurring it;
- and nothing on the other side of the ratio, which is the half that actually decides a renewal.

So the TD can say *"we spent $X."* They cannot say **which shots, which artists, which of it was
the 18,516-token fixed prefix on trivial turns, or what any of it bought.** A number with no
attribution and no denominator does not survive a budget conversation — but it is a different
and smaller claim than "they cannot answer," and the document is only entitled to the smaller
one.

The instrument absence itself is real and fully verified:

The panel ships a session token meter: a rail label, a formatter, a counter, and an accumulator
called `_note_usage`. **A whole-tree grep for `_note_usage` returns exactly one hit — its own
definition.** The label is created with `""` and re-set only inside that dead function, so it
renders permanently blank. Its docstring says so: *"No provider surfaces usage yet… until it
lands the meter stays empty — never estimated."* Upstream, `StreamProvider.stream` returns
`(stop_reason, blocks)` with **no slot for usage**, and the Anthropic SSE handler has no
`message_start` branch at all — which is where `input_tokens` and `cache_read_input_tokens`
arrive. Every provider drops usage on the floor.
(`synapse_panel.py:445-447,530-540`, `providers/base.py:60`, `anthropic_provider.py:169` —
VERIFIED-STATIC, FIXABLE.)

Not the panel. Not telemetry — seven surfaces, zero token fields. Not the journal, which records
durations. Not `agent.usd`. The single usage reader that exists (`agent_loop.py:204`) is on a
daemon path artists do not use, has never seen a live response, and its output is garbage
collected at the end of the turn.

What *is* measurable is the shape of the bill. **Every one of the 126 tool definitions is sent
on every API round-trip** — `synapse_panel.py:1667` hands the full unfiltered tuple to
`ClaudeWorker`, which passes it inside `for iteration in range(_MAX_TOOL_ITERATIONS)`, up to 25
times per user turn. `panel/tool_filter.py:222` exists and is imported only by a UI widget; it
is not in the request path. Measured at HEAD: **15,901 tokens of tool schemas + 2,615 tokens of
system prompt = 18,516 fixed tokens per round-trip.** Asking *"what frame am I on"* costs the
same prefix as asking for a Solaris lighting rig, and **tool definitions are 85.9% of that fixed
prefix** (15,901 / 18,516 — denominator named per Law 2; a turn additionally carries the user
message, the assistant output, and every tool result across up to 25 iterations).
(`synapse_panel.py:1667`, `claude_worker.py:153`, `anthropic_provider.py:115` —
VERIFIED-DERIVED, producer re-run this session.)

**"And what did we get?"**

Partially — by hand, from `$HIP/claude/journal.log` files scattered across every artist's shot
directory, with no turn boundaries, no artist attribution, no aggregation tool anywhere in the
tree, and no outcome measure beyond a 60-character error prefix.

Meanwhile the durable provenance the product is built around **is written and nobody reads it.**
`FloorGate` — genuinely production-grade, on the live path, atomic tmp+fsync+replace — writes one
JSON record per mutating op containing op id, type, timestamp, session, parent, outcome, and
payload/result **SHA-256 digests**. No node path, no parm name, no value. And the only reader of
that directory in the entire tree is `doctor.py:594-601`, a health check that lists the newest
three **filenames**. (`floor_gate.py:117-122,362-372`, `doctor.py:594` — VERIFIED-STATIC.)

The content-bearing record does exist — `AuditLog` persists full input/output with a hash chain
to `~/.synapse/audit/*.jsonl` — but it is written **only** from `_submit_logs`, reached only
after a *successful* invoke. Every `handle()` except-arm returns before it. **The failure case —
the one the artist actually asks about — is the one case not recorded.**
(`core/audit.py:327-339`, `handlers.py:531-535` — VERIFIED-STATIC, FIXABLE.)

And three of the five `agent.usd` provenance writers still have zero production callers:
`log_routing_decision`, `log_handoff`, `log_integrity`. The two that fire — `create_task` and
`write_verification` — are reachable only from `synapse_autonomous_render`, one tool out of 120.
The `/SYNAPSE/agent/routing_log/`, `/handoff_chain/` and `/integrity/` sections of the v2.0.0
schema are never written on any path an artist uses.
(`agent_state.py:329,403,512`, `handlers.py:1803,1902` — VERIFIED-STATIC, LIMIT-until-wired.)

The TD brings four incidents: a frozen Houdini and a lost scene, black cryptomatte channels that
cost comp a day, a shot whose memory silently died when the second artist opened it, and a
render that reported failure and delivered a frame anyway.

They cannot bring a single number on the other side.

**The trial ends.**

---

## 2 · The five questions, answered directly

### What breaks first?

**`hou.webServer.port()` — a phantom API in a bare `except`.** It does not announce itself. It
strips the panel's per-call timeout, its explicit no-retry-after-timeout discipline and its
deadlock guard, so **every tool runs unbounded on the GUI thread with the double-dispatch guard
gone** — from the first prompt on install day, on every seat.

It is *not* the reason Houdini freezes — that is L1, and it is arithmetic. It is the reason the
freeze has no ceiling and the reason a timed-out mutating tool can be dispatched twice.
(`tool_executor.py:146,466-479` — VERIFIED-RUNTIME.)

Competing for the same slot, and hitting the same afternoon: the panel says `/ for commands` and
95 of 228 palette rows send prose to the model; Stop bricks the panel; and the system prompt
tells the model it is inside Houdini 21.

### What breaks worst?

**The 6 pm render.** Not because a render is dangerous, but because it is the one operation where
*every* escape hatch is independently absent: the Stop button cannot be clicked because the
event loop it lives in is the thread being blocked; the cancel tool is marshalled onto the thread
it must preempt; `rkill` works and is not called; emergency halt is not surfaced and its one
automatic caller is broken by a class mismatch. The only exit is killing the process, and the
partial frame that leaves behind passes validation.

One afternoon, one lost scene, one corrupt frame in dailies. That is the incident that makes
SYNAPSE a topic in a meeting.

### What does the artist blame?

**SYNAPSE — including for things it did not do.**

Three of the four install traps the README names end in *"no error, just absence."* This leg
found **nine mechanisms, seven of them silent.** That teaches the artist, correctly and early,
that when something is wrong there will be no message. After that, every unexplained thing in
the session is a candidate.

The specific, checkable consequence is the zero-filled AOV: comp opens a correctly-named,
correctly-shaped, entirely black `Z` channel and spends a day on Karma before arriving at
SYNAPSE. By then the tool has spent its credibility on a defect that is genuinely its own —
and will spend the rest on ones that are not.

### What does the pipeline TD say in the meeting?

They are half-time, and they say the thing a half-time TD says: **"I can't support this."**

Their quarter contained: a manual, Windows-shaped, four-step symbol-table regeneration runbook
required on **every Houdini point release** (SideFX ships those roughly fortnightly), whose final
confirmation step calls a tool that cannot report success on the path they would call it from;
an installer that silently targets H21 on a dual-build seat; logs full of `SUSTAINED FREEZE` and
`Emergency halt failed` on normal days; and a `claude/` directory appearing at `$JOB` — the show
root — created by `os.makedirs` with no override and no error handling if that path is
read-only. (`docs/studio/UPGRADE.md`, `scene_memory.py:116` — VERIFIED-STATIC.)

And if they ever ran their own security review before the pilot rather than after, the
conversation ends earlier. **The shipped bridge binds `0.0.0.0:9999` with authentication off by
default.** `start_hwebserver` calls `hwebserver.run(...)` with no `settings=`, so Houdini's own
default applies — `ADDRESS='0.0.0.0'`, `ALLOWED_HOSTS=['*']`. `get_auth_key()` returns `None`
when neither `$SYNAPSE_API_KEY` nor `~/.synapse/auth.key` exists, and the installer never creates
one, so the adapter sets `_authenticated=True` on connect.

**Verified live this session, twice, independently** — by the transport probe and again by the
orchestrator:

```
netstat            TCP  0.0.0.0:9999  LISTENING  pid 47540   (houdini.exe)
HTTP GET from      192.168.1.183  ->  reached SYNAPSE's own /mcp handler (406 body)
~/.synapse/auth.key   does not exist
$SYNAPSE_API_KEY      unset
auth.py:16            "# None means auth disabled"
grep auth.key across scripts/ + install.py   ->  no installer mints one
```

Behind that handler, `execute_python` runs arbitrary code with full `__builtins__` and `hou` in
scope, no import filter, no length cap, and no gate.
(`hwebserver_adapter.py:330-335`, `auth.py:82-85`, `handlers.py:1222` — **VERIFIED-RUNTIME,
FIXABLE**, and it **REFUTES** `docs/studio/DEPLOYMENT.md:10`, which states mode `local` binds
`127.0.0.1`.)

**SYNAPSE's own studio-readiness gate says the same thing, and it says it today.** Running the
**eight** read-only S-checks at `dfc02c8` in the posture a studio has (undeclared → strict) —
the ninth, the `studio_readiness_review` capstone, was deliberately **not** run because it
writes an artifact:

```
posture_declared        RED   harness/state/posture.json not declared
policy_single_source    RED   bridge default-open fallback live; 4 divergent policy taxonomies
consent_enforced        RED   panel/bridge_adapter.py disarms consent (_gate = None);
                              mcp/tools.py dispatches through the DISARMED singleton
rbac_at_dispatch        RED   check_permission only on the WS transport; `if user_session:`
                              with no else — an unresolved session skips RBAC entirely
memory_provenance       ok
eval_backbone           ok
farm_headless           ok
context_review_clean    ok
```

*Producer: `harness/verify/checks.py::check_*`, run read-only this session; the S.R capstone was
deliberately NOT run because it writes an artifact.*

**Four rows read RED; three of them are the security criticals** — `policy_single_source`,
`consent_enforced`, `rbac_at_dispatch`. The fourth, `posture_declared`, is the trigger rather
than a critical: it is what puts the board into strict mode in the first place.

Verdict under studio posture: **NOT READY**. Under a declared `solo` posture the same three
criticals are listed as *accepted trade-offs* and the verdict is **READY (solo posture)**.

That is the cleanest sentence available about where SYNAPSE actually is: **it is ready in the
posture it was built for, and its own gate refuses the posture a studio has.**

And the TD asks the question a TD always asks: **can I trust the suite as an upgrade gate?**

| At `dfc02c8` | Number | Interpreter |
|---|---|---|
| GATE | **5,031 passed / 0 failed** | system python 3.14.2, vendor tree INACTIVE |
| SHIPPING | **4,891 passed / 95 failed / 8 errors / 3 collection errors** | `hython3.13`, vendor tree ACTIVE |

*Producer: `hython3.13 -m pytest -q --continue-on-collection-errors`, this session, 137.5 s.*

The shipping suite is **far healthier than the committed baseline says** — 771 errors have become
8. But three things sit behind that number:

- **Nothing reads it.** The ratchet at `checks.py:2135` compares against the file's *flat*
  top-level keys, which are the GATE numbers. The `shipping` block — the one the file itself
  calls *"the ONLY number a release claim may cite"* — is 8 days stale, off by 843 passes and
  763 errors, and no check recomputes it.
- **CI has no Windows lane and no hython lane.** `.github/workflows/ci.yml:12` is
  `os: [ubuntu-latest, macos-latest]`, and `:42` runs `pip install -e ".[dev,websocket,mcp]"` —
  so CI *supplies* the very dependencies that are missing on an artist's seat and can never see
  the problem.
- **Of 95 failures, 60 are async tests that cannot run without `pytest-asyncio`** (which the
  shipping interpreter lacks). The real residual is **35 synchronous failures**, and a sample of
  three found three distinct classes — product code emitting a path the host rejects
  (`hou.hda.installFile` → `hou.OperationFailed`, which the mock accepted silently), a genuine
  TOPS behavioural disagreement, and a test asserting on a Mock API. *Extrapolating from n=3 is
  exactly the error this document exists to name.*
  (`ci.yml:12,42`, `checks.py:2126-2135`, `handlers_hda.py:111` — VERIFIED-RUNTIME.)

**And 9 of 120 registered tools have re-runnable live-gated automated coverage.** The other 111
have never been watched executing against a Houdini that could refuse them. The nine are the
four COPs solver/stylize/wetmap/growth tools and the five Solaris tools — the family whose mock
fixtures were deleted. (`_tool_registry.py:124`, `tests/solaris/test_live_wiring.py`,
`tests/test_h22_cops_solver_live.py`, `tests/test_h22_setdressing_live.py` — VERIFIED-DERIVED.)

**The only end-to-end test of the artist's actual path — panel → daemon → agent turn → tool
calls → scene — is an unconditional `pytest.skip()`**, and the manual runbook its docstring
defers to names Houdini **21.0.671**, which is not installed on this machine.
(`tests/test_host_layer.py:1137-1157` — VERIFIED-RUNTIME.)

So the honest answer to the TD's question is: **the studio's first real shot is the product's
first real test.** That is not a criticism of the engineering; it is the arithmetic of zero
production users, and it is why §5 is the most important section of this document.

### And the one that decides everything: why did they stop?

**There are two endings in this evidence, and the document owes you both.**

> **Ending A — week 0, security.** The studio's own review meets a bridge on `0.0.0.0:9999` with
> auth off, serving ungated `execute_python`, and SYNAPSE's own gate reading NOT READY with three
> security criticals red. The trial never starts. *(VERIFIED-RUNTIME, §2.)*
>
> **Ending B — week 12, illegibility.** The review happens after the pilot, or not at all. The
> quarter runs, and it ends in the meeting above.
>
> **Which obtains is decided entirely by U4** — whether a security review precedes or follows a
> DCC-plugin pilot at a mid-size facility. That is a fact about studios, not about this codebase,
> and **this leg cannot settle it.** §3's ordering assumes Ending B, because Ending A ends the
> account before any other mechanism fires and would make the ledger a list of things nobody met.

**Within Ending B**: not because it failed, but because it could not produce evidence of its own
value while every failure produced a memory. The incidents made SYNAPSE a topic. The illegibility
made it indefensible.

> **UNVERIFIED — and this is the most load-bearing sentence in the document, so it gets the
> loudest possible label.** *"A tool with four incidents and a number on the other side survives;
> a tool with four incidents and a blank meter does not."* That is a counterfactual about
> procurement behaviour, asserted from a project with **zero production users**. It has no anchor
> and no tier because none is available. Tracked as **U23**. Read it as the document's
> hypothesis, not its finding.
>
> The adversarial pass caught this and was right to: §0 declares unlabelled assumption the one
> thing that would make this document worthless, and this was the sentence doing the most work
> without a label.

What **is** verified — and what the hypothesis rests on — is that the asymmetry is **structural,
not incidental.** Look at what is built:

- The provenance spine is real, durable, atomic — and stores **digests, not changes**, in a
  directory whose only reader counts files.
- The one record with content is written **only on success**.
- The cost meter exists, is drawn on the rail, and its feeder has **zero callers**.
- Three of five `agent.usd` provenance writers have **zero production callers**.
- 23 panel modules / **10,905 LOC — 40% of the package** — are unreachable from the shipped
  entrypoint, including the entire error-translation layer, the scene doctor, the preflight and
  the session journal surface.
- Half of everything S1 could mark WORKS (12 of 24) is a tool the **agent** uses to orient
  itself. Rendering: 0. Lighting: 0. Caching: 0. Comp: 0.

**SYNAPSE's instrumentation is aimed at SYNAPSE.** It can tell you its own session fidelity, its
own health, its own router stats, its own memory status. It cannot tell an artist what it did to
their scene, or a TD what it cost, or a producer what it saved.

That is the same defect class this repository has spent five days cataloguing in its own
instruments — the mock that cannot disagree, the coverage metric that is 100% by construction,
the runner built not to see the fault — pointed at the business case instead of at the code.

`harness/CLAUDE.md` states the differentiator in one line: *"every action reversible and
recorded. The differentiator vs. Houdini's native MCP is the receipts. **Protect that.**"*

The receipts are written. **Nothing reads them.**

---

## 3 · THE RANKED LEDGER

Ranked by **likelihood** — how certainly a studio meets it, and how early. Not by severity.

`SILENT` = fails with no error, or with a wrong-but-plausible result.

> **Metric correction from the adversarial pass, and it matters for how you read the tiers.**
> The original ranking conflated **ACTIVE** (the mechanism fires) with **ENCOUNTERED** (a human
> notices). For a silent defect those are not the same date, and the gap between them *is* the
> account: row 10 (no cost readout) is active from the first prompt and encountered at the Week-12
> meeting, which is the entire point of this document.
>
> Tiers below are keyed to **ACTIVE**. Where the encounter date differs materially, the row says
> so. The two dates for the most important rows:
>
> | Row | Active | Encountered |
> |---|---|---|
> | 8 · `0.0.0.0` bind, auth off | install day, first Connect | at the security review — **week 0 or never** (U4) |
> | 9 · consent disarmed everywhere | first destructive action | when someone asks where the approval log is |
> | 10 · no cost readout | first prompt | **week 12**, or the first invoice |
> | 11 · 18,516-token fixed prefix | every round-trip from turn one | the first invoice |
> | 39 · mid-turn 429 discards tool history | first 429 — *"routinely"* on one shared key | immediately, as duplicated nodes |
>
> Row 39 sits in Tier 3 on the original ordering and is **Tier-2 on encounter frequency**. It is
> left in place with this note rather than silently moved, because the reordering is a judgement
> and the evidence for it is right here.

### Tier 1 — ACTIVE on install day or the first prompt, on every seat

| # | Mechanism | Anchor | Class | Silent | Tier |
|---|---|---|---|---|---|
| 1 | `hou.webServer.port()` is a phantom in a bare `except` → panel MCP fast path permanently dead → **every tool runs inline on the GUI thread** | `tool_executor.py:146,157,480` | FIXABLE | ✔ | RUNTIME |
| 2 | System prompt declares **"inside Houdini 21"** and names H21.0.671 as the grounding authority; zero "Houdini 22" hits in the prompt layer | `system_prompt.py:51,189,193` | FIXABLE | ✔ | STATIC |
| 3 | **Stop bricks the panel** — worker emits no signal after `abort()`, SEND stays disabled forever | `claude_worker.py:132`, `synapse_panel.py:1761-1764` | FIXABLE | ✔ | RUNTIME |
| 4 | **Enter not gated on busy** → second concurrent worker mutating the same scene; also the only escape from #3 | `synapse_panel.py:146-148,1653-1683` | FIXABLE | ✔ | STATIC |
| 5 | **95 of 228 palette rows (41.7%) send prose, not dispatch** — incl. all 21 slash commands R19 ordered removed; the placeholder advertises `/` | `tool_palette.py:119,61-65` | FIXABLE | ✔ | RUNTIME |
| 6 | **Bridge records failed ops as `fidelity=1.0` / verified** — `handle()` never raises, so the rollback branch is dead code | `bridge_adapter.py:366-371`, `handlers.py:544-574` | FIXABLE | ✔ | RUNTIME |
| 7 | Rail reads **"done / Result ready"** after every turn including all-errors; tool errors never reach the chat | `synapse_panel.py:1738-1751,1781-1784` | FIXABLE | ✔ | STATIC |
| 8 | **Bridge binds `0.0.0.0:9999`, auth off by default** → LAN-reachable ungated `execute_python` | `hwebserver_adapter.py:330-335`, `auth.py:82-85` | FIXABLE | ✔ | RUNTIME |
| 9 | **Consent gates disarmed on every path** — `_gate = None` on the process-wide bridge + auto-approve callback | `shared/bridge.py:2239-2241`, `bridge_adapter.py:192,216-217` | FIXABLE | ✔ | STATIC |
| 10 | **No cost readout anywhere** — `_note_usage` has zero callers; providers drop usage; meter permanently blank | `synapse_panel.py:445,530`, `providers/base.py:60` | FIXABLE | ✔ | STATIC |
| 11 | **18,516 fixed tokens per round-trip** (15,901 tools + 2,615 system), ×25 iterations/turn. `panel/tool_filter.py::filter_tools` **exists, with a safe full-list fallback**, and is imported only by two UI widgets — never by the request path | `synapse_panel.py:1667`, `claude_worker.py:153`, `tool_filter.py:222` | FIXABLE | ✔ | DERIVED |
| 12 | `--verify` **green with all six shipping deps absent** — probes the vendored SDK, never the six | `install_synapse_package.py:351,441` | FIXABLE | ✔ | RUNTIME |
| 13 | **`install.py` cannot see H22** (`for major in [21,20,19]`); silently installs to H21 on a dual-build seat | `install.py:78,87,139` | FIXABLE | ✔ | RUNTIME |
| 14 | **Error translator has zero callers** → first prompt on a credit-less account returns a raw HTTP 400 JSON blob | `error_translator.py:354`, `synapse_panel.py:1733` | FIXABLE | ✘ | STATIC |
| 15 | **Shelf ships 7 buttons, 5 icons that are never deployed** — no `houdini/config/Icons` in the tree | `synapse.shelf:13`, `packages/synapse.json:27` | FIXABLE | ✔ | STATIC |
| 16 | **First-run surface is one line + three verbs**; the 62-recipe library has no UI at all | `synapse_panel.py:78-82,679-681` | UNKNOWN | ✔ | RUNTIME |

### Tier 2 — first real work, week one

| # | Mechanism | Anchor | Class | Silent |
|---|---|---|---|---|
| 17 | **Panel renders run inline; Stop is drawn, enabled and unclickable** for the render's duration | `handlers_render.py:109-113,517,543` | LIMIT | ✔ |
| 18 | **No render cancel exists in any shipping path** — `rkill` works, zero call sites | `handlers_render.py:899`, `render_session.py:26-144` | FIXABLE | ✔ |
| 19 | **Cancel tool is marshalled onto the blocked main thread** with a 10 s budget — inoperative exactly when needed | `_tool_registry.py:1206-1210`, `mcp/server.py:621-626` | FIXABLE | ✘ |
| 20 | **Foreground guard denies every ≥1 MP frame** — 1080p refused, "reduce to ≤65,536 px" | `foreground_guard.py:53-59` | FIXABLE | ✘ |
| 21 | 4 of 6 render entry points **bypass the guard and the bounded wrapper**; the system prompt steers to them | `handlers.py:658`, `handlers_render.py:2017,2148,1533` | FIXABLE | ✔ |
| 22 | **Freeze chain fires on every render >30 s**; the emergency halt it calls is handed the wrong bridge class and always fails | `freeze_chain.py:138-173,202-208` | FIXABLE | ✔ |
| 23 | **Second artist to open a shot loses its memory permanently** — per-seat key, per-shot store, no recovery from `_degraded_load` | `store.py:393-400,446-451`, `crypto.py:88-108` | LIMIT | ✔ |
| 24 | **Undo unit is one tool call, not one request**; 4 highest-traffic mutators have no undo group on `/synapse` | `handlers_node.py:43,120,141`, `handlers.py:1051` | LIMIT | ✔ |
| 25 | **Phantom-API gate grounds against H21 on `/mcp`** and reports `gate_armed:true, stale:false` (self-referential staleness check) | `scout.py:141,438,449-454`, `.mcp.json:5` | FIXABLE | ✔ |
| 26 | **The prompt orders a `synapse_scout` call the panel does not advertise** — scout is absent from `TOOL_DEFS` | `tool_bridge.py:50-54`, `system_prompt.py:186-193` | FIXABLE | ✔ |
| 27 | **Conversation is append-only forever** — no compaction, no cap, no "New chat"; session dies on context overflow | `synapse_panel.py:278,1720` | FIXABLE | ✘ |
| 28 | **`tops_cook_node` defaults `blocking=True`** on the main thread; 2 timeouts arm the stall gate that blocks the cancel | `handlers_tops/cook.py:38,67`, `main_thread.py:311` | FIXABLE | ✘ |
| 29 | **No farm submission path** — localscheduler only; the "render farm" renders on the artist's workstation | `handlers_tops/cook.py:152`, `render_farm.py:1` | LIMIT | ✘ |
| 30 | **Un-namespaced `claude/` created at `$JOB`** and beside every `.hip`, hardcoded, no override, unguarded on a read-only show root | `scene_memory.py:116-139` | FIXABLE | ✘ |
| 31 | **Memory singleton binds to the first `.hip` forever** — open a second shot, its memories go to the first shot's `.synapse/` | `store.py:1215,896`, `tracker.py:104` | FIXABLE | ✔ |
| 32 | **`inspect_scene` returns 343 KB at default depth 3** on a real scene; `max_depth` clamped nowhere (672b247's cap is `inspect_selection` only) | `introspection.py:310,337,339` | FIXABLE | ✔ |
| 33 | **Inside-out event bridges never constructed** — SYNAPSE never volunteers anything | `scene_load_bridge.py:144`, `tops_bridge.py:303` | FIXABLE | ✔ |
| 34 | **`synapse_router_stats` returns `{"error":"Router not initialized"}`** on every `/mcp` call — the router is built only in a handler no tool reaches | `handlers.py:1604,1566` | FIXABLE | ✘ |

### Tier 3 — weeks two to four; silent until something downstream is wrong

| # | Mechanism | Anchor | Class | Silent |
|---|---|---|---|---|
| 35 | **AOV presets write bare source names** → correctly-named, entirely zero-filled EXR parts (R101); **10 tests pin the defect** | `handlers_render.py:1690-1707,1771`, `tests/test_render.py:607-612` | FIXABLE | ✔ |
| 36 | **Partial frame from a killed render validates as good** — success criterion is `exists() && size>0` at both layers | `handlers_render.py:966-970,2355-2377` | FIXABLE | ✔ |
| 37 | **Failed Solaris build leaves a half-wired subnet; the retry reports `already_exists`** | `import_megascans.py:196-198,202,368` | FIXABLE | ✔ |
| 38 | **`synapse_batch` defaults `stop_on_error=False`** → partial build returns success + one clean undo entry | `handlers.py:921,966-983` | FIXABLE | ✔ |
| 39 | **Mid-turn API error discards tool history** → retry duplicates every node already created | `claude_worker.py:84`, `synapse_panel.py:1725-1736` | FIXABLE | ✔ |
| 40 | **`tops_render_sequence` permanently rewrites the ROP's output path, samples, res and camera** with no restore | `render_sequence.py:242-269` | FIXABLE | ✔ |
| 41 | **`tops_multi_shot` generates per-shot attributes nothing consumes** → N identical renders overwriting each other | `render_sequence.py:430,470,475` | FIXABLE | ✔ |
| 42 | **PDG work-item fields are phantoms** — `wi.cookTime` / `wi.attribs` absent on 22.0.368 → every cook time 0.0, every query matches zero | `work_items.py:87,93,315` | FIXABLE | ✔ |
| 43 | **TOPS cancel silently substitutes dirtying for cancelling** and reports `cancelled` either way | `handlers_tops/cook.py:243,253` | FIXABLE | ✔ |
| 44 | **One shared `SynapseHandler`; `set_session_id` is last-writer-wins** → audit attributes to the wrong session | `hwebserver_adapter.py:67,226-230` | FIXABLE | ✔ |
| 45 | **One `~/.synapse/bridge.json`, one port** → `/mcp` talks to whichever Houdini started last | `bridge_endpoint.py:76,217`, `mcp_server.py:171` | FIXABLE | ✔ |
| 46 | **`synapse_doctor` reports the bridge healthy from a file's existence** — no pid, socket or upgrade probe; the coexistence check is hard-coded never to fail | `doctor.py:426-441,497` | FIXABLE | ✔ |
| 47 | **Provenance stores digests, not changes**; the content-bearing audit log is written **only on success** | `floor_gate.py:362-372`, `handlers.py:531-535` | FIXABLE | ✔ |
| 48 | **Provenance dir is install-scoped** — 40 artists on one shared install share one directory and one 5,000-file FIFO | `floor_gate.py:117-122,126` | FIXABLE | ✔ |
| 49 | **3 of 5 `agent.usd` provenance writers have zero production callers**; the other 2 fire from one tool. The writers are built — the defect is wiring, not architecture | `agent_state.py:329,403,512` | FIXABLE | ✔ |
| 50 | **Deprecated `karma` LOP still emitted** by 3 recipes + the Solaris planner; the wiring validator never sees generated `execute_python` | `render_recipes.py:596,728`, `planner.py:703` | FIXABLE | ✘ |
| 51 | **`deploy.json`, studio-lan/vpn modes, RBAC and TLS are unreachable** — `load_deploy_config` has zero production callers | `sessions.py:333`, `websocket.py:121-126` | FIXABLE | ✔ |
| 52 | **`filelock` unshipped** → project-memory markdown appends interleave across Houdini processes on show storage | `scene_memory.py:24,53,583` | FIXABLE | ✔ |
| 53 | **Package file forces `SYNAPSE_MEMORY_BACKEND=moneta`** at a sibling path no studio has; the two install routes configure different backends | `packages/synapse.json:18-25`, `store.py:829-836` | FIXABLE | ✔ |
| 54 | **`safe_render` reports `forced_background: true`** without evidence the parm was set | `handlers_render.py:1988-2004,2024` | FIXABLE | ✔ |
| 55 | **`shot_render_ready` composes a full Karma render behind a 10 s budget** → reported failure beside a frame that lands minutes later; a retry double-renders | `handlers_usd.py:1945-1954`, `core/timeouts.py:16` | FIXABLE | ✘ |
| 56 | **TOPS write-tools report the payload, not the readback** — every parm write is `if parm:`, a miss is invisible | `wedge.py:127,163` | FIXABLE | ✔ |
| 57 | **Emitted-node catalog drifted 97 → 109** with no freshness test — the drop-day upgrade probe reads a stale list | `emitted_node_types.json`, `tests/test_emitted_node_types.py:52-115` | FIXABLE | ✔ |
| 58 | **`houdini21-reference` is a hardcoded path literal in 3 production modules** — dropping in `houdini22-reference/` is a silent no-op | `scout_ingest.py:65-67`, `knowledge.py:156`, `seed_corpus.py:48` | FIXABLE | ✔ |
| 59 | **`version_agreement.py` covers 5 of the 7 locations** the README says it covers; both skipped ones drift hardest | `version_agreement.py:19`, `README.md:193` | FIXABLE | ✔ |
| 60 | **`houdini_undo` / `houdini_redo` skip `run_on_main`** — the only hou-touching handlers that do — while the receipt asserts `main_thread_executed=True` | `handlers.py:882-902`, `integrity_envelope.py:270` | FIXABLE | ✔ |

### Tier 4 — the proof state: why every entry above lands on an artist rather than on CI

These do not bite the artist directly. They are the reason the ones that do were never caught.

| # | Mechanism | Anchor | Class | Silent |
|---|---|---|---|---|
| 61 | **`conftest.py` plants a permissive fake `hou` before collection** — `hou.ui`, `hou.hda`, `hou.undos`, `hou.text`, `hou.hipFile` are bare `MagicMock()`s, so any call returns a truthy Mock. 81 test files install a fake `hou` | `tests/conftest.py:104-117,133-135` | FIXABLE | ✔ |
| 62 | **CI has no Windows lane and no hython lane**, and installs the six missing deps itself — so the shipping-environment defect is structurally invisible to it | `.github/workflows/ci.yml:12,42` | FIXABLE | ✔ |
| 63 | **The ratchet reads the GATE numbers, not the shipping block** the file calls "the ONLY number a release claim may cite"; nothing recomputes it | `checks.py:2126-2135`, `suite_baseline.json` | FIXABLE | ✔ |
| 64 | **9 of 120 tools have re-runnable live-gated coverage**; 111 have never been watched against a host that could refuse them. §7 names the fix and calls the Solaris live tier "the template for the other 111" | `_tool_registry.py:124`, the 3 live-gated files | FIXABLE | ✔ |
| 65 | **The undo guarantee is pinned exclusively by MagicMock call-counts** — `hou.undos.group.reset_mock()` / `assert_called_once_with(...)`. On real Houdini `hou.undos.group` is a function, so the assertion is not merely unrun on the host, it is **unrunnable** | `tests/test_introspection.py:560-586` | FIXABLE | ✔ |
| 66 | **The only end-to-end test of the artist's path is `pytest.skip()`**, deferring to a manual runbook that names an uninstalled Houdini build | `tests/test_host_layer.py:1137-1157` | UNKNOWN | ✘ |
| 67 | **42 of 48 autonomy tests cannot execute under hython** (no `pytest-asyncio`); the 6 that can are mock-driven. Plan→Validate→Execute→Evaluate has zero live evidence | `tests/test_autonomy_{driver,predictor,validator}.py` | FIXABLE | ✔ |
| 68 | **The `live` pytest marker is inert** — declared "not collected by default in CI", but `addopts` carries no `-m 'not live'` deselection and only 2 sites use it | `pyproject.toml` addopts | FIXABLE | ✔ |

---

## 4 · LIMITS — true of the architecture, to be documented rather than fixed

Each of these is a property of the design. The honest question for each is whether a studio can
live with it — not how to close it.

**L1 · Nothing in Python can interrupt the main thread from the main thread.** *Split, per the
adversarial pass — the original over-scoped this and retired a fixable defect as architecture.*

**L1a — the arithmetic core (a genuine LIMIT).** Once a payload is executing on the main thread,
nothing interrupts it. The authors say so in the source: *"any number here would be a lie"*
(`handlers_render.py:109-113`).

**L1b — the fixable shell (NOT a limit).** *Whether the render is in-process and foreground at
all* is routing and configuration, and this document classes both as defects elsewhere: row 21
(4 of 6 entry points bypass the guard and the bounded wrapper) and the direct contradiction
between `system_prompt.py:165` telling the model to set `soho_foreground=1` and
`mcp_tools_render.py:13-14` forbidding it. Those are FIXABLE.

**And L1's studio-facing consequence is U7-conditional.** The entire in-process foreground
posture was derived on, and only ever verified on, **Indie**. On a commercial licence the
background husk path may work — nobody has run it. §1's Week 3 should be read with that
conditional attached, not only §5.

*Can a studio live with L1a?* Only if the freeze is **announced** before it starts.
`estimate_inline_cost` already computes exactly that verdict and nothing consumes it. The
dishonesty is fixable even where the freeze is not.

**L2 · Cost scales with what you ask about, and the mechanism is that it sees less.** Arm A's
payload rises 443 → 113,411 tokens (256×) while single-call scene coverage falls
**100 / 100 / 73 / 51 / 10 / 11 percent**. Within-window completeness is 100% at every rung, and
per-node encoding is marginally *worse* than the ablation (146.5 vs 140.0 non-path chars/node).
The design is defensible; the sentence must include the coverage number or it is the same defect
one layer up. *Producer:* `harness/notes/token_bench/summary.json:curve.A_inspect_scene_d3`.

**L3 · The undo unit is one tool call.** A request is N tool calls, so a request is N undo
entries. Per-turn transactions are not worth building; the fix is documentation plus making the
undo **label** carry the artist's request text instead of a truncated JSON payload.

**L4 · No farm submission path.** localscheduler only, by explicit design and an explicit error
string. This is a positioning fact, not debt.

**L5 · Memory is per-shot on shared storage, encrypted with a per-seat key.** Correct for a solo
artist; structurally wrong for a team.

> **CORRECTED by the adversarial pass, and the correction makes this weaker.** An earlier draft
> said *"nothing in the install path or `DEPLOYMENT.md` says so."* **That is REFUTED.**
> `docs/studio/DEPLOYMENT.md:269-300` carries a dedicated *"Scene-Memory Encryption Keys"*
> section — how the key resolves, the single-seat warning (*"recall/search return empty (amnesia,
> not an error dialog)"*), and *"Show-scoped provisioning (the fix)"* with the
> `Fernet.generate_key()` command and the launcher injection. `doctor.py:194` has a
> `check_memory_key_fingerprint`. *(Verified independently by the orchestrator.)*
>
> **The accurate finding is narrower and better:** the remediation is documented in full and is
> doctor-detectable — and **the install path and the panel surface neither, and nothing forces
> the check.** A documented, detectable fix that no shipped surface mentions is a
> *discoverability* defect, not an absence. It moves this from LIMIT toward FIXABLE.

**L6 · The vendored SDK is `win_amd64`-locked and both its activation and its warning are
Windows-only.** A Linux studio gets no vendoring and no notice.

**L7 · 40% of `panel/` is unreachable from the shipped entrypoint** — 23 modules, 10,905 LOC,
including the error translator, scene doctor, preflight and session journal. Either wire them or
retire them; carrying them means every description of the product describes features an artist
cannot reach.

**L8 · The Fork Bomb guard protects a component with zero production callers.** `README.md:51`
already says this, narrowly and honestly. Keep it that way.

**L9 · One slow handler stalls its whole WebSocket connection** — a serial per-connection loop
with keepalive disabled. A wedged connection looks alive to both liveness mechanisms.

**L10 · The consent gate cannot be armed on the panel path without a redesign.** The blocking
`HumanGate` poll `time.sleep`s on the thread that must draw the approval card. The auto-approve
is *correct for artist-initiated panel work* — the artist typed the request and is watching. The
defect is that the same process-wide instance also serves `/mcp` and autonomous paths, and that
`bridge_adapter.py:189-190`'s docstring claims the opposite two lines above the code that shares
it.

---

## 5 · THE UNKNOWN LIST

**This is the most important section in the document.** SYNAPSE has zero production users, so
everything about how an artist reacts, what they try, and what they conclude is unknown. Naming
it precisely is what tells the next quarter where its evidence has to come from.

Each entry names the single observation that would settle it.

| # | What is unknown | The observation that settles it |
|---|---|---|
| U1 | **What an artist does in the first 60 seconds of an unstoppable render.** Wait, click the dead Stop, alt-tab, or Task Manager — each produces a different downstream state (preserved partial frame that validates as good, lost scene, or a 40-minute stall that reads as a hung workstation). | Sit one generalist down with a ~6-minute frame, ask them to render, and at t+20s tell them the camera is wrong. Record what they touch, in order, and how long before they force-quit. **This one observation prices every render finding.** |
| U2 | **The transport mechanism behind S1's `inspect_scene` hang.** The payload explanation is **REFUTED-LIVE**: an empty 10-node scene returns in <1 ms; `karma_user_guide.hip` at depth 6 completes in 0.32 s; and `node.errors()` does **not** force a cook (`cookCount()` stays 0 before and after). S1 blocked past 120 s on the empty case. The cause is not in `introspection.py`. | In one live GUI session, log `threading.current_thread().name` and `is threading.main_thread()` at the top of `SynapseWS.receive` and `_handle_inspect_scene`, then reproduce. |
| U3 | **Whether an artist reads "Fidelity: 100.0%" beside five red errors as a bug, as noise, or as a reason to stop trusting the readout.** | Put one artist in front of a session with three deliberately-failing tool calls and ask what the integrity panel is telling them. |
| U4 | **Whether the studio's security review happens before or after the pilot.** If after, the `0.0.0.0` bind is a week-12 shutdown rather than a week-0 rejection — and the entire ranking above changes. | Ask one head of technology what gates a DCC plugin install at their facility. |
| U5 | **Whether a half-time TD absorbs a per-point-release symbol-table regeneration.** SideFX ships point releases roughly fortnightly; the runbook is manual, Windows-shaped, and its own final confirmation step is unreachable on `/mcp`. | Watch a real half-time pipeline TD attempt the four-step `UPGRADE.md` runbook on a point release and record where they stop. |
| U6 | **Whether artists discover the 62-recipe library at all.** It has no UI surface; the palette exposes a different, smaller 21-recipe list. | Three generalists, fresh install, no verbal instruction, 15 minutes: did they press `/` or Ctrl+K unprompted; what did they type first; did they ever find a recipe. |
| U7 | **Whether the whole render posture behaves differently on a commercial licence.** Every live verification in this project ran on `hou.licenseCategoryType.Indie`. The shipped package never probes licence, so the Indie-derived posture — in-process foreground render, the 1 MP ceiling, the GL-flipbook substitution — is applied unconditionally on a tier nobody has run. | One 1920×1080 Karma frame through `houdini_render` on a Core or FX seat: does husk load the karma delegate out-of-process; does the guard's `RuntimeError` fire; does the flipbook substitute. |
| U8 | **What `hou.undos.performUndo()` actually does on the WebSocket worker thread on 22.0.368** — benign, wrong entry popped, or crash. The defect (no `run_on_main` at `handlers.py:882,893`) is verified; the consequence is not. | Connect over `/synapse` from a worker thread while the main thread is mid-cook, call `houdini_undo`, observe. **Highest-value live probe in the provenance domain.** |
| U9 | **Whether `hou.undos.group()` creates one undo entry when the wrapped block raises.** Every claim in this repo about "the group closes on the raise, so one Ctrl+Z reverses it" rests on context-manager semantics, not on an observation. | Wrap a two-node build that raises; diff `hou.undos.undoLabels()`. |
| U10 | **Whether a studio's `$JOB` is artist-writable.** The `claude/` `os.makedirs` is unguarded; a locked publish root makes session start throw `PermissionError`. | Ask the pipeline TD. |
| U11 | **Whether the comparative cost claim holds in either direction.** Both wide-margin arm-B variants are SYNAPSE calling SYNAPSE. The one competitor-shaped arm — full composed USD flatten — came in at **0.57×**, *cheaper* than SYNAPSE's grounding read (and is marked not-comparable-across-rungs, so it withdraws the claim without inverting it). | Build the outside-in arm R-C1-2 names: a full `.hip` node+parm dump through `c1_token_bench.py::emit_payloads`, then re-run the ladder. ~1 day. |
| U12 | **What a turn actually bills.** Every figure in this document is a **tiktoken/cl100k proxy payload count**. The Anthropic account has no credits; `messages.create` *and* `count_tokens` both return HTTP 400, so even the unbilled counting endpoint is gated. | Fund the account; one `count_tokens` call. |
| U13 | **Whether prompt caching hits.** The tools and system blocks are cache-marked, but the system prompt is rebuilt per turn from live selection/frame/network/hip, so it plausibly misses. The one field that would settle it — `cache_read_input_tokens` — is the field the SSE handler has no branch for. | Fix the usage wiring, run one live turn. |
| U14 | **Turns per day, round-trips per turn, grounding reads per turn.** Every day-cost figure is a formula with these three as free parameters. | One instrumented week of one artist. |
| U15 | **Whether artists notice the undo-grouping difference between transports** or simply learn "Ctrl+Z several times." If they adapt silently, it costs trust without ever generating a ticket. | Watch one artist's first undo after an agent-built network. |
| U16 | **Whether any of the 17 `tops_*` tools has ever been executed against a live TOP network.** No receipt records a runtime `tops_*` invocation. | One hython run that builds a topnet + ropfetch, calls `tops_cook_node` / `get_work_items` / `query_items` / `setup_wedge`, and prints the returned dicts against the node's actual state. |
| U17 | **Whether the studio's farm copies the `.hip` to node-local temp.** If it does, every `$HIP`-relative artefact SYNAPSE authored — `$HIP/cache`, `$HIP/<shot>_layers`, `$HIP/render` — resolves to a directory that does not exist on the node. | Read the submitter's scene-staging policy. |
| U18 | **Whether a competent TD finds `SYNAPSE_PROVENANCE_DIR` unprompted.** Nothing in `packages/synapse.json`, `install.py` or `DEPLOYMENT.md` mentions it. | Ask one. |
| U19 | **Whether two concurrent `/synapse` clients serialize on the haio loop, the mutation lock, or the main thread.** Two ESTABLISHED sockets were observed live; contention was not measured. | Two-client latency probe under a deliberate 20 s cook. |
| U20 | **Whether Karma leaves a non-zero-length partial file when its host is killed mid-frame.** Decides whether the `exists() && size>0` criterion catches the kill case or blesses a corrupt frame. | One live kill probe. |
| U21 | **Whether the panel → daemon → agent-turn loop works at all in a graphical Houdini 22.0.368 session.** The only test is `pytest.skip()`, and the manual runbook it defers to names an uninstalled build. | **One graphical session, one artist, three prompts: create a node, set a parameter, undo.** This single observation settles more of the proof domain than any further static analysis. |
| U22 | **How many of the 35 non-async shipping failures are product defects versus harness incompatibilities.** A sample of three found one of each of three distinct classes. | Classify all 35. Extrapolating from n=3 is the error this document exists to name. |
| **U23** | **Whether a studio's tool-retention decision actually turns on cost legibility rather than incident count.** This is the document's central hypothesis (§2) and it is UNVERIFIED — a counterfactual about procurement behaviour from a project with zero users. Added by the adversarial pass, which correctly refused to let the thesis stand unlabelled. | Ask three heads of pipeline what actually killed the last DCC tool they dropped, and whether a cost number on the other side would have changed the decision. |
| **U24** | **Whether SYNAPSE would have been *worth* the incidents.** The whole account measures what it cost and never establishes what it saved. S1 named three candidates — the Solaris set-dressing family ("the closest thing in the product to twenty minutes off every shot setup"), the 62 recipes, and `solaris_assemble_chain` — and the third, the highest-leverage tool in the inventory, has **no host evidence at all**. | Time three shot setups by hand against three with `synapse_solaris_scene_template` + `component_builder`, on the same shots, same artist. That is the denominator the meeting needed and nobody has. |

---

## 6 · Stale seed facts, corrected

A pre-mortem that cites a repaired defect as live destroys itself. Every seed fact and widely-held
belief was re-checked at `dfc02c8`. **These are no longer true and must not be cited:**

| Belief | Status at `dfc02c8` | Anchor |
|---|---|---|
| `houdini_network_explain` **segfaults** on `karma_user_guide.hip` (C1-F3) | **FIXED** at `672b247` — string parms read `rawValue()` not `eval()`; verified same scene, exit 0 | `introspection.py` |
| `inspect_selection` recursion is 2^depth, depth clamped nowhere (C1-F10) | **FIXED** at `672b247` — `DEPTH_CAP=5` + a visited set. *But it covers `inspect_selection` only; `inspect_scene`'s `max_depth` is still unclamped* | `introspection.py:24,253,268` |
| `_node_issues` → `node.errors()` **forces cooks** — S1's named candidate for the hang | **REFUTED-LIVE** on 22.0.368: `cookCount()` is 0 before and after `errors()` and `warnings()` | `introspection.py:186,190` |
| The marshal deadlock class — 9 raw `executeInMainThreadWithResult` sites, 5 confirmed deadlock | **FIXED AND LINT-ENFORCED** — zero live call sites outside comments; all nine migrated to `run_on_main` | repo-wide grep |
| `karmarenderproperties` emitted in ≥11 / 31 places (H7-F2, R86) | **GONE** — zero `createNode` sites remain; the extractor lists it removed, `karmarendersettings` as replacement | static extractor at HEAD |
| The panel injects an out-of-repo `~/.synapse/design/tokens.py` (R21); the fallback is not a faithful copy (R104) | **REPAIRED** — `tokens.py:45-71` is now a hard in-repo import; the six `except ImportError` palette arms are gone | `panel/tokens.py:45-71` |
| A hardcoded `C:\Users\User\SYNAPSE` fallback exists in shipping code | **NOT FOUND** as an executable path — only in non-executing docstrings | grep across `python/`, `shared/`, `houdini/` |
| R106: the R18 consent pins use `object.__new__(GateWidget)` and skip on both interpreters | **FIXED** — now `GateWidget.__new__`; all 3 PASS under hython3.13 this session | `tests/panel/test_gate_consent_honesty.py:83` |
| R27/R28: `tests/panel/` segfaults / the panel has no test surface | **FIXED and better than R30 recorded** — 65 collected, 64 passed, 1 failed, no segfault, 2.44 s | hython3.13 at HEAD |
| The six unshipped deps break SYNAPSE on a clean machine (R47) | **OVERSTATED for the panel, true for `/mcp`** — with none of the six present, the panel builds a real widget under hython3.13 | live build this session |
| `synapse_configure_render_passes` has **no test anywhere** (S1 §7) | **FALSE — and worse.** Ten tests exist and assert the exact bare source names R101 says render as silent zeros | `tests/test_render.py:574-728` |
| `configure_render_passes` calls `editableStage()` outside a LOP cook | **MISLEADING** — the code is set on a `pythonscript` LOP and force-cooked, where `hou.pwd().editableStage()` is the correct idiom | `handlers_render.py:1792-1798` |
| `safe_render`'s forced-background is a no-op because `usdrender_rop` has no `soho_foreground` | **REFUTED** — it is parm 148 of 166 on 22.0.368 | live parm sweep |
| R99: nothing ever assigns `EXPECTED_HOUDINI_VERSION` | **PARTLY FIXED** — the injector exists and fires inside Houdini (panel, daemon). **Still fully true on `/mcp`**, which runs stock python | `version_injector.py`, `.mcp.json:5` |
| `websocket.py:471`'s serial loop makes cancel unreachable | **Real but non-load-bearing** — `websocket.py` is not the shipped transport. The live equivalent is `handlers._MUTATION_LOCK` + no cancel command at all | `synapse_panel.py:555` |
| The PDG rollback `TypeError` (R67) | **UNCHANGED** — `bridge.py:1718` still passes `remove_files=`. But the *reporting* is now honest: the caught exception surfaces as *"TASKS NOT DIRTIED — a retry may recook against stale work items"* | `shared/bridge.py:1718,1723-1730` |
| Emergency halt is unsurfaced (R29) | **HALF STALE and worse** — R29 was not executed *and* the one automatic caller (`freeze_chain._escalate`) is inert from a bridge class mismatch | `synapse_panel.py:1474-1494`, `freeze_chain.py:160-170` |
| `hou.undos.group()` has no effect inside parm callbacks (SideFX HOM) | **DOES NOT APPLY** — no SYNAPSE path runs in a parm callback; zero callback-script authoring, no shipped HDAs. *(Positive control: 53 `hou.undos.group` sites found by the same scan.)* | `synapse_panel.pypanel` |
| husk silently no-ops on Indie | **UNRESOLVED and contradicted in-tree** — asserted in four artifacts, while `retina_manifest.py:302-308` records live husk timing that only exists if husk produced pixels | see §9 |
| "COP grounding 6.2%" is a semantic figure | **MISLABELLED** — its producer records D2 (literal emission) = 6.2%; **D3, the semantic axis, is ZERO** | `harness/notes/receipts/L1.json` |
| The panel prefix is 14,380 tokens over 121 tools | **STALE** — 15,901 over 126 at HEAD (+10.6%), from five Solaris tools added 2026-07-23..25. `check_token_baseline_fresh` would fail today and is not a standing guardrail | `token_baseline.json:24,52` |
| Tool count is 120 | **120 registered, 128 served** — 120 `TOOL_DEFS` + 6 group-info + `inspect_stage` + `scout` | `mcp_server.py:909-941` |
| Three of four install traps end in silent absence | **The shape is right; the count is low on both axes** — nine mechanisms, seven silent | §1, Domain A |
| `shot_layers/` is written to the repo root (RES-F11) | **Corrected in-run** (this leg's own claim): production writes `hou.expandString("$HIP/<shot>_layers")`, which lands **beside the `.hip`**. The repo-root artefact is the no-`hou` fallback | `solaris_compose_tools.py:133-136` |
| The shipping suite is **4,048 / 110 / 771** (R39/R40, `suite_baseline.json`) | **STALE by 8 days and 12 test-touching commits.** At HEAD: **4,891 passed / 95 failed / 131 skipped / 8 errors**. Errors fell 771 → 8. GATE is **5,031/0**, not 4,875/0 | measured this session, hython3.13 |
| R47's residual: **57 failures that did not move when the environment did** | **Superseded.** At HEAD the residual is **35 synchronous failures** (60 of 95 are async tests unrunnable without `pytest-asyncio`) | AST classification of the 95 failing node IDs |
| S1: **286 test files, 101 mock, 5 host-behaviour** | **Moved.** 279 `test_*.py` at HEAD; **81** install a fake `hou` by one of four idioms; **3** files are live-gated and re-runnable | producer regex, this session |
| S1: **24 WORKS of 128 tools** | **Denominator is 120** (`len(TOOL_DEFS) == len(TOOL_NAMES) == 120`). The numerator depends on the definition: re-runnable live-gated **automated** coverage is **9 tools**; S1's 24 counted live calls made by hand during its own run. Both are true of different questions | `_tool_registry.py:124` |
| RES-F3: the fake-`hou` residency guard returns early under hython | **FIXED and verified working** — `conftest.py:682-700` now compares the resident against `_HOU_AT_IMPORT` **by object** and is armed in both modes | `tests/conftest.py:682-700,724-742` |
| `tests/solaris/test_live_wiring.py`: *"EXPECTED RED — several tests here are expected to FAIL live on 22.0.368"* | **Stale docstring.** M4 (`de53153`) repaired them. Measured: the three live-gated files → **137 passed, 0 failed, 3.86 s** on H22.0.368 | this session |

**One of the corrections above is the orchestrator's own.** The `node.errors()` cook hypothesis
was about to be published as the root cause of the week-one failure. A live probe refuted it.
Recorded per Constitution Article II — observed beats documented beats assumed, including when
the assumption is mine.

---

## 7 · What is genuinely good

A pre-mortem that cannot see the strengths cannot rank the risks. Each of these is verified, and
each would be load-bearing in a repair.

**Nothing SYNAPSE authors carries a dependency on SYNAPSE.** No custom node types, no HDAs, no
callbacks — only inert `setUserData` strings. A touched `.hip` opens and renders on a bare farm
node. This is the single most common way a DCC tool poisons a pipeline, and SYNAPSE is immune to
it by construction.

**The README is the most honest public artifact in the project.** It publishes the refuted claim,
the 256× curve, the coverage collapse, both suite numbers with their interpreters, and a
"Known limitations" section that names the PDG `TypeError` by file and line.

**`docs/studio/DEPLOYMENT.md` is production-grade.** A full environment-variable table with a
per-row Studio/Dev column, including the two variables that fix the provenance-scoping defect.

**The main-thread marshal layer is careful and its trade-offs are documented in the source.**
`run_on_main` replaced a vendor primitive that self-deadlocked, with a per-call result holder, a
timeout, and a zombie-kill flag. The comment block at `handlers_render.py:59-132` is a model of
honest engineering: it states which of the three caller paths the 3,600 s budget actually bounds,
names the two that discard it, and says plainly that a number on the panel path *"would be a
lie."*

**`synapse_batch` has the best undo behaviour in the product** — one `hou.undos.group` around
the whole batch.

**`synapse_doctor` surfaces its own bad news unprompted.** S1 watched it report 7 ok / 2 fail /
1 skipped, including an install-stamp divergence against itself.

**The Solaris live tier is the right pattern, it worked, and it is green.** The `MagicMock` `hou`
fixtures were *deleted*, citing Constitution Law 1 by name, and replaced with
host-identity-gated tests that skip honestly off-host. That tier immediately found real defects —
`set_purpose` reporting success having set nothing, `import_megascans` raising `PermissionError`
on every invocation. **The mock said green while the tool set nothing; deleting the mock is what
found it.** Measured this session, the three live-gated files run **137 passed / 0 failed in
3.86 s** on H22.0.368. This is the single most transferable thing in the repository: it is the
template for the other 111 tools.

**The fake-`hou` residency guard is armed and works.** `conftest.py:682-700` now compares the
resident module against `_HOU_AT_IMPORT` **by object**, in both modes — closing RES-F3, where
the guard disabled itself under hython, the one interpreter where residency matters.

**The shipping suite is far better than its own baseline records** — 771 errors have become 8.
The defect is that nothing re-measures it, not that it is bad.

**The 62 recipes are real domain knowledge** — actual sensor dimensions for eight cinema cameras,
a correct 4:1 three-point ratio, destruction and vellum chains. It is the most undersold asset in
the product and it has no UI.

**`FloorGate` is a real provenance spine** — neutral module, zero `hou`, atomic durable writes,
never swallows an exception, writes nothing for read-only ops. The defect is what it stores and
who reads it, not that it exists.

**SYNAPSE ships a studio-readiness gate that refuses to certify SYNAPSE.** Four checks read RED
today under studio posture, by name, with the fix criterion in the failure message. Very few
projects can be told what is wrong with them by their own CI.

---

## 8 · Method, artifacts, producers

**Law 2 — every number above names the thing that emitted it.**

| Producer | What it emitted |
|---|---|
| `harness/verify/checks.py::check_posture_declared`, `_policy_single_source`, `_consent_enforced`, `_rbac_at_dispatch`, `_memory_provenance`, `_eval_backbone`, `_farm_headless`, `_context_review_clean` | The 4-RED / 4-green studio-readiness board in §2. Run read-only this session; the S.R capstone was **not** run because it writes `harness/state/studio_readiness_verdict.json` |
| `harness/notes/token_bench/summary.json:curve.A_inspect_scene_d3` | the 443 → 113,411 ladder and the 100/100/73/51/10/11 coverage collapse |
| `harness/notes/token_baseline.json:24,52` + its own producer re-run this session | 126 tools / 15,901 tokens (recorded: 121 / 14,380 — stale) |
| `hython3.13 -m pytest -q --continue-on-collection-errors` + `python -m pytest -q`, **run this session at `dfc02c8`** | GATE **5,031/0** · SHIPPING **4,891 passed / 95 failed / 131 skipped / 8 errors / 3 collection errors**, 137.5 s. *Supersedes the committed `suite_baseline.json` figures (4,875/0/129 and 4,048/110/771), which are 8 days and 12 test-touching commits stale* |
| AST classification of the 95 failing node IDs against `ast.AsyncFunctionDef` | 60 async (unrunnable without `pytest-asyncio`) / **35 synchronous** — the real residual |
| `harness/notes/receipts/L1.json` | LOP 18.3% (D2∪D3) · COP D2 6.2%, **D3 = 0** |
| `harness/notes/CTO_RULINGS_01.md` | R1, R11, R19, R25, R29, R47, R58, R67, R73, R87, R96, R99–R118 |
| `docs/reviews/synapse-studio-readiness-2026-07-06.html` | the 24 adversarially-verified findings the S-track gates |
| `python/synapse/cognitive/tools/data/h22_symbol_table.json` | 35,903 symbols, 22.0.368, blake2b `265b433a…` — the membership authority for every phantom verdict |
| ten read-only domain probes, this session | ~90 anchored mechanisms; journal at `<session>/subagents/workflows/wf_e2b4efd4-ccd/journal.jsonl` |

**Method.** Ten `cartographer`-class probes (Read/Grep/Glob/Bash, no Edit/Write in the agent
definition), one per domain, each required to return a mechanism, a `file:line`, an evidence
tier, a bucket, a likelihood and a falsifier — and each explicitly instructed to check currency
at HEAD, because citing a fixed defect would destroy the document. The orchestrator independently
verified every load-bearing anchor before it entered the account (R76/R85: *a receipt is not the
tree*).

---

## 9 · What this leg did NOT establish

Stated plainly, because a document that hides a gap is worse than one that names it.

**An adversarial pass DID run, and it changed the document.** S0, S1 and L5 all shipped with
*"adversarial pass did not run"* as a recorded blocker; this leg dispatched three hostile lenses
(evidence / reasoning / fairness), each required to return at least two SOUND claims as a
specificity control (R79 — an audit that flags everything detects nothing).

**The reasoning lens returned first and its verdict is the honest headline:**

> *"Safe to act on as a repair backlog; NOT safe to act on as a causal account. I sampled the
> load-bearing anchors directly and could not break the mechanism layer — `_note_usage`, `rkill`,
> the `handlers_render` quotation, the panel's unfiltered tool tuple, the shelf/icon absence, the
> frame-validation criterion all survived hostile checking, several against a specific
> alternative hypothesis. **The failures are all in the argument.**"*

Fourteen attacks landed. Every one is applied above rather than noted, and the material ones were
**re-verified by the orchestrator at the anchor before being accepted** (R85 — an instrument that
passes its control is not thereby correct on every claim, and that cuts toward the crucible too):

| What it broke | Where it is now |
|---|---|
| The cost thesis conflated *"no instrument"* with *"cannot know"* — the studio shares one key, so the aggregate is on the provider's bill | §2, rewritten to attribution + denominator |
| *"Only the second is decisive"* — the single most load-bearing sentence — had no tier, no anchor, no falsifier | §2, labelled UNVERIFIED + **U23** |
| L5 claimed `DEPLOYMENT.md` says nothing about the encryption key. **REFUTED** — §Scene-Memory Encryption Keys documents the fix in full, and `doctor.py:194` checks it | §4 L5, rewritten as a discoverability defect |
| The document named its own ending-invalidator (U4) and then proceeded as if disclosure were resolution | §2, **Ending A / Ending B fork** |
| Row 1's consequence overstated — repairing the phantom would not make execution non-blocking | §1, §2, restated as bound + no-retry + deadlock guard |
| `install.py` is documented-retired (`UPGRADE.md:119`), and rows 13/15 are **mutually exclusive** on one seat | §1, rewritten as a two-route branch table |
| Rows 11, 49, 64 classed LIMIT while the fix exists in-tree, unwired | reclassified **FIXABLE** |
| L1 over-scoped — foreground *routing* is fixable, only the uninterruptible thread is arithmetic | split into **L1a / L1b** |
| The account resolved its own UNKNOWNs into fact three times, always in the plot's direction | annotated inline with U6 / U1 / U20 |
| Tier 1 conflated ACTIVE with ENCOUNTERED | §3, ACTIVE/ENCOUNTERED table added |
| *"Not oversold"* rested on README numbers this document's own §6 calls stale | §1, scoped to posture-vs-numbers |
| `.mcp.json` is a developer surface, not the artist's path | §1, moved and sharpened |
| Eight S-checks, not seven; four RED, three of them criticals | §2, corrected and named |
| *"86% of a trivial turn"* — denominator unnamed (Law 2) | §2, *"85.9% of the fixed prefix"* |

**Two lenses — evidence and fairness — had not returned when this was written.** Their scope was
re-deriving the numbers independently and auditing §7 for understatement. Anything they find is
unincorporated, and the receipt's `for_ruling` R-S2-1 records that.

**What survives, and it is the part that matters:** the mechanism layer was attacked directly and
held. Ranking positions remain the weakest claims here — the *mechanisms* are anchored, the
*order* is argued, and the argument has now been argued against.

**The husk-on-Indie question is unresolved and contradicted inside the tree.** The belief is
asserted in four artifacts including a safety guard; `host/retina_manifest.py:302-308` records
live husk timing that only exists if husk produced pixels. `harness/notes/receipts/V1.json` —
the receipt that would settle it — **does not exist at HEAD, on any branch, in any commit**,
because V1 ran under a read-only fence that denied `git commit` (R103).

**No live mutation was performed.** This leg read; it did not drive a tool against a scene. Every
artist-visible symptom is derived from the code path, not observed on a running session.

**The `0.0.0.0` bind fix is not yet safe to promise.** Houdini's C++ `hwebserver` may or may not
honour a settings-supplied `ADDRESS` override; SYNAPSE has never passed `settings=`, so that path
has never been exercised. The finding is verified; the remedy needs a live spike.

**Every cost figure is a proxy.** No model has ever been in the loop.

---

## 10 · Drift

Two items, both structural, both recorded rather than cleaned.

**D1 — S0's and S1's artifacts were destroyed mid-run by the housekeeping commit.**
`11f3a79 chore: housekeeping pass, and the fresh-clone review nobody had run` pruned the
forensic worktrees. `S0_SCOUT.md` (78 KB), `S1_INVENTORY.md` (17.5 KB), both receipts and ~1.5 MB
of producer artifacts were **uncommitted** — read-only legs are denied `git commit` by the fence
(R103) — and are now gone from disk. `origin/forensic/s0-forensic-scout` and
`…/s1-tool-inventory` both sit at `61df5bc`, the pre-work commit. No blob exists in any ref.

This is **R91/R93 reproducing exactly**, on the two legs S2 depends on: R93 ruled that a leg's
terminal condition requires its product committed on its own branch; R103 amended it for
read-only legs on the grounds that *"a read-only leg's product IS its receipt."* S0's and S1's
products were not their receipts — they were 96 KB of markdown in a worktree.

**S2 is not blocked:** both documents were read in full before the prune and every quotation in
this file is from that read. **And both are recoverable** — the Write tool inputs survive in the
session transcripts:

```
S0_SCOUT.md      .claude/projects/C--Users-User-SYNAPSE--claude-worktrees-s0-forensic/
                 e4ee3645-c975-4a9f-a406-f02fbdba48c5.jsonl   (11 MB, 2 hits)
S1_INVENTORY.md  .claude/projects/C--Users-User-SYNAPSE--claude-worktrees-s1-forensic/
                 0e34aceb-0245-47ad-94fb-99cff55a76fb.jsonl   (27 MB, 2 hits)
```

This is the repository's own crash-recovery pattern (mine the agent transcripts). Recovery should
happen before anything else cites S0 or S1.

**D2 — the read-only fence leaked, and produced a finding.** A tree snapshot was taken before
fan-out (`dfc02c8`, clean but for `.claude/.orch_launched`). After it, `shot_layers/` appeared in
the worktree root at 14:24:55 — five USDC department layers written by
`solaris_compose_tools.py:133-136`, where `os.makedirs(hou.expandString("$HIP/" + shot +
"_layers"))` has no absolute-path guard and resolves relative to the process CWD when `$HIP` is
empty. **Left in place, not deleted** — Law 4: classification and deletion are separate,
human-confirmed acts, and it is evidence.

Instruction-level read-only fences do not hold. That is now **seven** recorded instances in this
repository (R61's three, R69's three, and this one).

---

## 11 · The sentence

> SYNAPSE did not fail the studio by breaking. It broke in the ordinary ways every young tool
> breaks, and those were survivable. It failed because every one of its instruments is pointed at
> itself: it can report its own fidelity, its own health, its own router, its own memory status —
> and it cannot tell an artist what it did to their scene, or a TD what it cost. The receipts
> that were meant to be the differentiator are written, durable, atomic, and read by nothing.
> When the meeting came, the failures had names and the value had none.

---

*S2 ends here. §3 is ranked by likelihood; §5 is where the next quarter's evidence has to come
from; §9 is what this leg could not do. No claim above is unlabelled.*
