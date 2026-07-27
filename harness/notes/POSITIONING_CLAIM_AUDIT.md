# POSITIONING CLAIM AUDIT — leg C0

**Harness** `CLAIMS-01` · **Leg** C0 (claim census) · **Date** 2026-07-27
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/c0.md`
**Mode** READ-ONLY. Writes confined to `harness/notes/**`.
**Build** Houdini 22.0.368 (Python 3.13.10) · repo `C:/Users/User/SYNAPSE` @ branch `feat/repair-heats-01`

---

## 0 · Verdict

```
SUPPORTED             0
PARTIALLY_SUPPORTED   2
UNSUPPORTED           2
UNVERIFIABLE          0
```

| # | claim (as transcribed) | verdict | age of the load-bearing mechanism |
|---|---|---|---|
| 1 | "Inside Houdini, native" | **PARTIALLY_SUPPORTED** | true since 2026-02-05; true of one of two shipped paths |
| 2 | "Sends only what changed — cost stays flat, even on huge scenes" | **UNSUPPORTED** | never true; no delta mechanism has ever existed |
| 3 | "Persistent project memory that carries across sessions and shots" | **PARTIALLY_SUPPORTED** | persistence since 2026-02-05; cross-shot carry needs 4 unstated conditions |
| 4 | "Physically refuses to boot on a render node" | **UNSUPPORTED** | gate real since 2026-04-20; never covered what the sentence says |

**Zero of four are SUPPORTED as worded.** Two are real capabilities described too broadly. Two are false as written.

None of the four is a fabrication. Every one has a real mechanism underneath it. The defect in all four cases is the same: **the sentence claims a wider scope than the mechanism covers**, and none of the four states the conditions it depends on.

---

## 0.1 · Scope finding, and it limits everything below

**The positioning document is not in the repository and never has been.**

```
$ git log --all --oneline -- "*POSITIONING*" "*positioning*"
(no output)
```

The only in-repo text carrying these four sentences is `harness/SYNAPSE_CLAIMS.md:24-27` and
`harness/prompts/c0.md:13-16` — both authored **today**, both part of this harness, and they
**disagree with each other on punctuation** (`—` vs `-`). Two independent transcriptions, no
source of truth.

**Consequence:** every verdict below grades a transcription, not a versioned artifact. A claim with
no file has no producer, no history, no blame, and no diff. This audit cannot tell you whether the
document says today what it said last week.

**This is itself the most durable finding in the leg.** The rest of this document is a snapshot of
text that lives outside version control.

### A prior C0 ran and its output does not exist

`harness/notes/CTO_RULINGS_01.md:3214` (RULING 117) records verdicts from an earlier C0 run —
`SUPPORTED 0 / PARTIALLY_SUPPORTED 3 / UNSUPPORTED 1` — and cites findings `C0-F1` … `C0-F4`.

```
$ git log --all --oneline -- "*POSITIONING_CLAIM_AUDIT*" "*C0.json*"
(no output)
$ ls harness/notes/POSITIONING_CLAIM_AUDIT.md harness/notes/receipts/C0.json
ls: cannot access ...: No such file or directory   (both, before this leg)
```

The artifacts were never committed. Under Article II a ruling is a conversation summary —
**UNVERIFIED**. This leg therefore re-derived all four verdicts from the tree and from live probes
rather than inheriting them. Where the two runs disagree it is noted per claim.

**A rulings document that cites finding IDs with no producer artifact has the same defect the
rulings document was written to catch** (Law 2). Flagged, not fixed — `for_ruling`.

---

## 1 · CLAIM 1 — "Inside Houdini, native"

**VERDICT — PARTIALLY_SUPPORTED**

True of the panel path, which is genuinely in-process and is the stronger engineering story than
the sentence sells. False of the `/mcp` path, which the same repository ships, documents, and
routes through a separate process over a localhost socket. The sentence does not say which path.

### PRODUCER

**P1.1 — the vendored SDK is active on Houdini's own interpreter.** VERIFIED-RUNTIME

```
$ "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" -c "
import sys; sys.path.insert(0, r'C:\Users\User\SYNAPSE\python')
import synapse, anthropic
print('python', sys.version.split()[0])
print('_VENDOR_ABI_RISK =', synapse._VENDOR_ABI_RISK)
print('anthropic', anthropic.__version__, anthropic.__file__)"

python 3.13.10
_VENDOR_ABI_RISK = False
anthropic 0.96.0 C:\Users\User\SYNAPSE\python\synapse\_vendor\anthropic\__init__.py
```

The Anthropic SDK resolves **from inside the repo**, on the interpreter Houdini itself runs. No
pip install, no external environment. This is the claim's strongest evidence and it holds.

**P1.2 — the model call runs on a thread inside the Houdini process.** VERIFIED-STATIC
`python/synapse/panel/claude_worker.py:49` — `class ClaudeWorker(QThread)`, described at `:2-4` as
"QThread with full tool-use conversation loop … Runs on a background QThread." No subprocess, no
`Popen`, no RPC.

**P1.3 — the panel is a real Houdini Python Panel.** VERIFIED-STATIC
`houdini/python_panels/synapse_panel.pypanel` exists and is shipped.

**P1.4 — the counter-evidence, from the same repo.** VERIFIED-STATIC
`mcp_server.py:3-21`, the file's own docstring:

```
Synapse MCP Server v2 — Bridge between Claude Desktop and Houdini via WebSocket.

Architecture:
    Claude Desktop  <-[stdio/JSON-RPC]->  mcp_server.py  <-[WebSocket]->  Synapse (Houdini)
```

`mcp_server.py:153` — `SYNAPSE_URL = f"ws://localhost:{SYNAPSE_PORT}{SYNAPSE_PATH}"`.

On this path the model is in Claude Desktop, **outside Houdini**, across three processes and two
hops. Houdini is the tool server, not the host.

### CONDITIONS

| condition | stated by the document? |
|---|---|
| The artist uses the **panel**, not the `/mcp` integration | **UNSTATED** — and the two paths give opposite answers |
| Houdini runs Python 3.13 (cp313 matches the vendored wheels) | **UNSTATED** |
| A manual three-step install: clone, hand-author a package JSON, verify | **UNSTATED** — `README.md:75-111`, "Three steps. The third is the one people miss." |
| The package JSON is saved **without a BOM** or Houdini rejects it silently | **UNSTATED** — `README.md:115` |

### AGE

**Long-established, and genuinely so.** `python/synapse/server/handlers.py` and the in-process
architecture date to the initial commit `a21c1ed` (2026-02-05) — 172 days. This is not a young
claim wearing an old coat. It is the one claim of the four whose maturity matches its tone.

### FINDINGS

- **C0-F1.1** *(high, VERIFIED-STATIC, `README.md:5`)* — README asserts **"No external bridge, no
  RPC hop, no second copy of the scene."** The repository ships `mcp_server.py`, whose own first
  line calls it a **"Bridge … via WebSocket"** carrying stdio/JSON-RPC. The README sentence is
  *stronger* than the positioning claim and is contradicted by a shipped file in the same tree.
  A technical evaluator finds this by opening the repo root and reading one docstring.
- **C0-F1.2** *(favourable, VERIFIED-RUNTIME)* — `_VENDOR_ABI_RISK = False` under hython. On
  system Python 3.14 the same flag is `True` and the vendor tree is inactive, but **that is not the
  artist's interpreter**. The claim survives on the path that matters. Stated here because the
  ABI warning is alarming out of context and would otherwise read as a defect against this claim.

---

## 2 · CLAIM 2 — "Sends only what changed — cost stays flat, even on huge scenes"

**VERDICT — UNSUPPORTED**

A compound sentence. Both halves fail, for different reasons, and the first half fails harder.

### PRODUCER

**P2.1 — "sends only what changed" has no mechanism.** VERIFIED-STATIC

```
$ grep -rn "def .*delta\|changed_since\|since_hash\|dirty_only\|only_changed\|incremental" \
    python/synapse/server/introspection.py python/synapse/server/handlers*.py shared/bridge.py
(no output)
```

The only `delta` in the grounding path is `shared/bridge.py:453` — `delta_hash`, an `IntegrityBlock`
audit field that records that a change happened. It never reduces what is sent. The one candidate
mechanism is explicitly parked: `LATENCY_PLAN.md:288` — *"3b dirty-flag inspect cache — build ONLY
if `synapse_tool_duration_ms` p95 …"*, under a heading at `:285` reading *"stay parked behind
numeric reopen-gates."*

**P2.2 — a live re-read sends the whole scene again.** REFUTED-LIVE
Independently run this session by the C0 claim-2 investigator under hython 22.0.368: after changing
**exactly one parameter** in a 4,010-node scene, the shipped `inspect_scene` re-emitted the entire
**339,575-byte** scene tree **byte-for-byte identical** — a zero-byte delta for a real mutation.

**P2.3 — "cost stays flat" is measured false.** VERIFIED-RUNTIME
Leg C1's committed artifact, re-verified against its own receipt by this leg:

```
$ python -c "compare harness/notes/receipts/C1.json headline_integers
             against harness/notes/token_bench/summary.json"
  MATCH   ladder_node_counts               [13, 22, 85, 169, 7207, 25850]
  MATCH   ladder_parm_counts               [106, 572, 1922, 7703, 142850, 1187573]
  MATCH   arm_A_grounding_payload_tokens   [443, 741, 3277, 3047, 38555, 113411]
  MATCH   arm_A_payload_growth_x           256
  MATCH   arm_B_ablation_tokens            [443, 741, 4922, 6504, 466520, 1234946]
  MATCH   flat_control_tokens              [36, 35, 34, 37, 33, 35]
  MATCH   is_flat (arm A)                  False
```

**7 of 7 headline integers in the C1 receipt are reproduced by its artifact.** The measurement is
real and its repeatability control is real (`summary.json:repeatability_control.pairs` — 31 pairs,
max absolute delta **0** tokens). Grounding payload rises **256×** across the ladder; **8.62×** at
turn level once the measured 14,380-token tool prefix is included. Neither is flat.

`scripts/c1_token_bench.py` and `scripts/c1_summarize.py` are both present — the measurement is
re-runnable today.

### CONDITIONS

There is no condition under which the sentence as worded holds. The first half has no
implementation to be conditional on. The second half is false at every rung of the only ladder ever
measured, and C1 records that no threshold makes it flat.

**One thing the claim gets right, and it deserves saying:** the read is not degraded. At every rung
arm A returns **100%** of the nodes inside its configured depth window. The falling scene-wide
share (100% → 11%) is a fixed window over a deepening scene, not truncation. *(C1-F1.)*

### AGE

**Never true.** The load-bearing surface `inspect_scene` landed 2026-02-09 as a full re-walk and is
still a full re-walk today, proven live 169 days later. The parked cache was written down as parked
on 2026-06-02. The measurement that could test the second half first existed on **2026-07-27** —
today — in commit `b816f4b`.

**Risk class:** this is not a claim that was true and went stale. It is a claim that was **never
true and was never measured**, published as an established property. That is the worse of the two
classes named in the brief.

### FINDINGS

- **C0-F2.1** *(blocker-for-the-claim, VERIFIED-STATIC)* — "Sends only what changed" is not merely
  unproven, it is **unimplemented**. No measurement can rescue it.
- **C0-F2.2** *(favourable, VERIFIED-RUNTIME)* — C1's receipt is honest and its numbers reproduce
  from its artifact 7/7. When this repository measures something, the measurement holds up. The
  gap is between the measurements and the positioning, not inside the measurements.
- **C0-F2.3** *(favourable, VERIFIED-STATIC, `README.md:29-35`)* — **the README already carries the
  corrected claim**, with its producer path and its limits: *"That is 256× — not flat … There is
  currently no delta path — every inspect is a full re-read. Producer: `harness/notes/token_bench/`."*
  The repository is ahead of the positioning document on this claim.

---

## 3 · CLAIM 3 — "Persistent project memory that carries across sessions and shots"

**VERDICT — PARTIALLY_SUPPORTED**

"Persistent" and "across sessions" are demonstrated true on the **default** configuration. "Across
shots" has a real, wired mechanism that works — behind **four conditions the sentence does not
state**, one of which silently disables it and reports success anyway.

### PRODUCER

**P3.1 — persistence across a process boundary, default config.** VERIFIED-RUNTIME
Two separate interpreter invocations, isolated temp dirs, `SYNAPSE_MEMORY_BACKEND` **unset** (i.e.
the `jsonl` default a studio gets):

```
######## PROCESS 1 (write) ########
{ "backend_env": "<unset -> jsonl default>",
  "shotA_storage_dir": "...\\shots\\sh010\\.synapse",
  "written_id": "mem_ed6b46f12db1",
  "storage_dirs_differ": true }

######## PROCESS 2 (FRESH interpreter, read) ########
{ "P1_shotA_hits": ["C0PROBE the beauty pass uses karma XPU at 512 samples"],
  "P1_PERSISTS_ACROSS_PROCESSES": true,
  "P3_CARRIES_ACROSS_SESSIONS_SAME_SHOT_DIR": true,
  "P2_CARRIES_ACROSS_SHOTS": false,
  "shotA_memory_jsonl_exists": true,  "shotA_memory_jsonl_bytes": 821,
  "shotB_memory_jsonl_exists": false, "shotB_memory_jsonl_bytes": 0 }
```

**"Persistent" and "across sessions" are SUPPORTED.** A fresh process reads back what a dead one
wrote. Shot B's store file does not even exist.

**P3.2 — the `$HIP` scoping that breaks cross-shot carry.** VERIFIED-STATIC
`python/synapse/memory/store.py:5` — *"Stores data in `$HIP/.synapse/` alongside the Houdini project
file."* `store.py:906-921` derives the storage dir from the `.hip` file's **own parent directory**.
In the standard one-directory-per-shot layout, two shots are two stores.

**P3.3 — the `$JOB` project tier DOES carry across shots.** VERIFIED-RUNTIME
A second, separate memory system — `python/synapse/memory/scene_memory.py`, the one the live
handlers import — maintains a `$JOB/claude/project.md` tier above the scene tier:

```
{ "project_dir_shared": true,
  "sanity_shotA_sees_scene_needle":   true,
  "sanity_shotA_sees_project_needle": true,
  "S1_scene_needle_visible_from_shotB":   false,
  "S2_project_needle_visible_from_shotB": TRUE }
```

A decision written at `scope="project"` from shot A **is visible from shot B**. The mechanism the
claim needs exists, is wired, and works.

**P3.4 — but only 1 of 9 entry types honours `scope`.** VERIFIED-RUNTIME
`scene_memory.py:470-480` dispatches nine entry types; only `decision` forwards `scope`. Probed by
passing `scope="project"` on three types:

```
{ "DEC_NEEDLE":   { "reached_project_tier": true,  "in_scene_tier": false },
  "NOTE_NEEDLE":  { "reached_project_tier": false, "in_scene_tier": true  },
  "BLOCK_NEEDLE": { "reached_project_tier": false, "in_scene_tier": true  } }
```

`session_start`, `session_end`, `parameter_experiment`, `blocker`, `blocker_resolved`,
`asset_reference`, `wedge_result` and `note` write scene-only regardless of the scope requested.

**P3.5 — the path is genuinely live in production.** VERIFIED-RUNTIME
`synapse_memory_write` is a registered MCP tool (`_tool_registry.py:TOOL_DEFS` → `memory_write`),
`handlers.py:778` registers the handler, `handlers_memory.py:151-167` plumbs `scope` through, and
`session/tracker.py:500` escalates to `scope="both"` when a decision carries a `project` tag.
*This corrects the C0 claim-3 investigator, which reported the `$JOB` tier as having zero
production callers. It has them.*

### CONDITIONS

| condition | stated by the document? |
|---|---|
| Both shots live under a **shared `$JOB`** | **UNSTATED** |
| **`$JOB` is actually set** to the show root. `handlers_memory.py:47` — `job_path = hou.getenv("JOB", hip_dir)`. Unset ⇒ project tier collapses onto the scene dir and cross-shot carry silently fails | **UNSTATED**, and it fails **silently** |
| The write uses `entry_type="decision"` — 8 of 9 types ignore `scope` | **UNSTATED** |
| The caller passes `scope="project"`/`"both"` explicitly, or tags it `project`. Default is `"scene"` | **UNSTATED** |

### AGE

**Both halves are 172 days old — same commit.** `$HIP/.synapse` persistence *and* the `$HIP` keying
that breaks cross-shot carry both arrived in the initial commit `a21c1ed` (2026-02-05).

```
$ git log -S'".synapse"' --oneline --date=short --format="%h %ad %s" --all -- python/synapse/memory/store.py
a21c1ed 2026-02-05 Initial commit: Synapse v4.0.0 — AI-Houdini Bridge
```

**This corrects the brief.** `harness/prompts/c0.md:30-33` states claim 3 "became defensible on
2026-07-26 when `SYNAPSE_MEMORY_BACKEND` was first set and the ledger seam was closed. Before that,
`_deposit_to_moneta()` was a hardcoded `return None`."

That is accurate about the **Moneta/USD substrate** (`097ae69`/`eb25abe`, 2026-07-26; `189180d`,
2026-07-27 — one and two days old). It is **not** accurate about the claim as worded. Persistence
across sessions has been true on the default `jsonl` backend since day one, and `jsonl` is still
the default today (`store.py:810` — `os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl")`).

**Risk class: not the two-days-old class.** This claim reads as long-established and *is*
long-established. Its defect is scope, not youth.

### FINDINGS

- **C0-F3.1** *(high, VERIFIED-RUNTIME)* — "across shots" is false on the standard per-shot
  directory layout unless four unstated conditions all hold. A studio TD tests this in ten minutes
  by opening a second shot.
- **C0-F3.2** *(high, VERIFIED-RUNTIME, `handlers_memory.py:151-167`)* — **Law 3 violation.**
  `_handle_memory_write` returns `{"written": True, "scope": scope}` echoing the *requested* scope,
  for all nine entry types — including the eight whose writers discard it. The status describes
  what was attempted, not what happened. An agent writing a `note` at `scope="project"` is told it
  succeeded at project scope and it did not.
- **C0-F3.3** *(medium, VERIFIED-STATIC)* — **two memory systems coexist.** `store.py`
  (`SynapseMemory`, `$HIP`-only, JSONL) and `scene_memory.py` (`$JOB`+`$HIP`, markdown). Only the
  second has a project tier. "Project memory" is accurate for one and inaccurate for the other, and
  the sentence does not distinguish them.
- **C0-F3.4** *(medium, VERIFIED-STATIC)* — "**project** memory" is a misnomer for the `store.py`
  path, which is keyed to the scene file's directory. That is *scene* memory. The word "project"
  describes the tier that most writes cannot reach.

---

## 4 · CLAIM 4 — "Physically refuses to boot on a render node"

**VERDICT — UNSUPPORTED**

The most specific, most falsifiable, and most damaging of the four. The gate is real and it fires.
It does not guard what the sentence says it guards, and "physically" is refuted by the gate's own
error message.

### PRODUCER

**P4.1 — the gate exists and fires headless.** VERIFIED-RUNTIME

```
$ hython 22.0.368 -c "<construct SynapseDaemon, call start()>"
{ "hou_isUIAvailable": false,
  "hou_version": "22.0.368",
  "Q1_gate_fires": true,
  "Q1_detail": "DaemonBootError: hou.isUIAvailable() returned False. SynapseDaemon will
                not boot in headless / PDG contexts (Render Farm Fork Bomb prevention).
                Pass boot_gate=False to override." }
```

The gate works. `python/synapse/host/daemon.py:329-361`, called first in `start()` at `:236`.

**P4.2 — "physically" is refuted by one keyword argument.** VERIFIED-RUNTIME

```
{ "Q2_bypassable": true,
  "Q2_detail": "_check_boot_gate() returned cleanly with boot_gate=False" }
```

`daemon.py:337-339` — `if not self._boot_gate_enabled: return`. The constructor takes
`boot_gate: bool = True` (`:142`). **The gate's own error message advertises the bypass**:
*"Pass boot_gate=False to override."* A guard that documents its escape hatch in its refusal
message is a default, not a physical impossibility.

**P4.3 — the gate guards a component with zero production constructions.** VERIFIED-STATIC

```
$ grep -rn "SynapseDaemon(" --include=*.py . | grep -v _vendor | grep -v /.claude/worktrees/
./tests/test_daemon_event_loop.py:23:    return SynapseDaemon(api_key="test", boot_gate=False)
./tests/test_graph_synth_wiring.py:312:  daemon = SynapseDaemon(api_key="test", boot_gate=False)
./tests/test_host_layer.py:508 … :1993   (≈30 further constructions)
```

**Every construction is in `tests/`.** Nothing in `python/`, `scripts/`, or `mcp_server.py` builds
one.

**P4.4 — the falsifier. The shipping surface boots and mutates on the gate's own render-node
predicate.** REFUTED-LIVE

```
$ hython 22.0.368 <SynapseHandler + create_node, headless>
{ "hou_isUIAvailable": false,
  "Q5_handler_constructs_headless": true,
  "Q6_response": "SynapseResponse(id='c0-probe-1', success=True,
                   data={'path': '/obj/c0_probe_headless', 'type': 'geo', ...}, error=None)",
  "Q6_NODE_CREATED_HEADLESS": true,
  "Q6_node_path": "/obj/c0_probe_headless",
  "Q6_node_type": "geo" }
```

And the CRITICAL-gated arbitrary-code tool, same context:

```
{ "key_content": { "success": true, "error": "None", "NODE_CREATED": true },
  "key_text":    { "success": true, "error": "None", "NODE_CREATED": true },
  "ARBITRARY_CODE_RAN_HEADLESS": true }
```

`execute_python` executed arbitrary Python and created nodes with `hou.isUIAvailable() == False` —
**the exact predicate the gate uses to mean "render node."**

The C0 claim-4 investigator independently reproduced this against `synapse.mcp.server.MCPServer`
and inside a PDG-work-item-shaped environment (`PDG_ITEM_NAME`, `PDG_ITEM_ID`,
`PDG_RESULT_SERVER`, `PDG_SCRIPTDIR` all set) — the literal render-farm case the docstring names.

**P4.5 — there is no gate anywhere else.** VERIFIED-STATIC

```
$ grep -rln "isUIAvailable" --include=*.py python/ mcp_server.py | grep -v _vendor
python/synapse/host/daemon.py
python/synapse/host/main_thread_executor.py
```

Two files tree-wide. Neither is a shipping server surface. `python/synapse/server/`,
`python/synapse/transport/`, `python/synapse/mcp/` and `mcp_server.py` contain **zero** occurrences.

### CONDITIONS

| condition | stated by the document? |
|---|---|
| "SYNAPSE" must mean **`SynapseDaemon` specifically**, not the product | **UNSTATED** — and the daemon has no production callers |
| Nobody passes `boot_gate=False` | **UNSTATED**, and the error message recommends it |
| "Render node" must mean `hou.isUIAvailable() == False` | **UNSTATED**, and the two are not the same set |

On the last point, the predicate mismatch runs **both ways**:

- **False positives** — the gate also refuses hython scripting, headless batch, CI, and any TD
  running a script. Those are not render nodes.
- **False negatives** — a GUI workstation enrolled in the farm out of hours returns
  `isUIAvailable() == True`. The gate lets it boot. That is a render node, and it is the exact
  configuration small studios use.

### AGE

**The mechanism is 98 days old; the claim was never true.**

```
$ git log -S"_check_boot_gate" --oneline --date=short --format="%h %ad %s" --all
c6d232b 2026-04-20 spike(2.1): Sprint 3 — Agent daemon scaffolding + bootstrap locks
```

The ungated, headless-mutating surfaces **predate the gate by two months**:
`python/synapse/server/handlers.py` landed 2026-02-05 (`a21c1ed`). From the instant the gate first
existed, SYNAPSE could already boot and mutate a scene headless. **The claim was false on the day
its mechanism was born.**

**Risk class: both, stacked.** The mechanism reads long-established and *is* — 98 days, unit-tested.
The *coverage* the sentence asserts has never existed. An evaluator who greps for the gate finds it
and is reassured; one who greps for its callers is not.

### FINDINGS

- **C0-F4.1** *(blocker-for-the-claim, REFUTED-LIVE)* — the shipping handler creates nodes and runs
  arbitrary Python on the gate's own render-node predicate. The claim is false as worded.
- **C0-F4.2** *(high, VERIFIED-RUNTIME)* — "physically" is refuted by `boot_gate=False`, which the
  refusal message itself recommends.
- **C0-F4.3** *(high, VERIFIED-STATIC)* — **the true, narrower sentence existed in this repository
  for two months and was deleted.** From `4faaa3a` (2026-04-20) through `d7f5b04` (2026-06-02) the
  README read:

  > *"The daemon refuses to boot in PDG / render-farm contexts (Fork Bomb prevention). For tests,
  > pass `boot_gate=False`."*

  Correctly scoped to **the daemon**, and it **disclosed the bypass**. It was removed on
  **2026-06-25** (`45584d4`, "artist/ADHD-friendly README"). The positioning sentence is that
  sentence with the subject widened from "the daemon" to the product, the bypass disclosure
  dropped, and the word "physically" added.

  ```
  $ git log -S"refuses to boot in PDG" --oneline --date=short --format="%h %ad %s" --all -- README.md
  45584d4 2026-06-25 docs: artist/ADHD-friendly README + CHANGELOG split; VERSION 5.16.0
  4faaa3a 2026-04-20 docs: Sprint 3 closeout — README refactor with architecture diagrams
  $ grep -c "refuses to boot in PDG" README.md
  0
  ```

  **The accurate version was written first.** A readability pass removed it. That is a documentation
  process finding, not an honesty one — and it is the most repeatable failure mode in this set.

- **C0-F4.4** *(favourable, VERIFIED-STATIC, `README.md:71`, blame `fed023a`, 2026-07-27)* — the
  README has **already re-acquired an honest version**, and it matches this leg's live findings
  almost exactly:

  > *"**Refuses to boot on a render node** — narrowly. `hou.isUIAvailable()` gates the daemon, the
  > Fork Bomb guard. But it protects a component with no production callers today while other
  > surfaces boot headless. A guard that exists, not a guarantee that holds."*

  The repository is ahead of the positioning document on this claim too. The gap to close is in the
  positioning text, not in the code or the README.

---

## 5 · Method, and what would falsify this audit

**Every PRODUCER above is a command that was run in this session, or a `file:line` opened in this
session.** No producer is a plan, a test that was not executed, or a number inherited from a
conversation. Where nothing demonstrates a claim, the producer is `NONE` — that case did not arise;
all four claims have real mechanisms, which is why all four are gradeable rather than UNVERIFIABLE.

**Law 1 — how each verdict could have failed:**

| claim | this verdict flips if |
|---|---|
| 1 | the `/mcp` path is out of scope for the sentence, or is deprecated — then SUPPORTED |
| 2 | a delta path exists somewhere I did not grep, or a flat curve exists on an unmeasured axis |
| 3 | shots are normally co-located in one directory, or `$JOB` + `decision` + explicit scope is the documented default workflow — then SUPPORTED |
| 4 | `SynapseHandler` had refused to construct headless, or `create_node` had returned an error. It returned `success=True` and the node existed |

**Probe defects found and corrected in-flight**, recorded so the outputs above can be trusted:

1. The first claim-3 project-tier probe passed `{"decision": ...}` where `write_decision` expects
   `{"name", "choice", ...}`. Every needle wrote as "Decision: Untitled" and **all four checks
   including both sanity controls returned false.** Had the sanity controls not been in the probe,
   that run would have produced a confident, wrong "the project tier does not work" finding. Fixed;
   re-run; sanity controls then passed, which is the only reason the S2 result is trustworthy.
2. The first claim-4 probe guessed handler names (`_handle_create_node` as a module function) and
   found zero handlers. Corrected to the real `SynapseHandler` + `SynapseCommand` dispatch.
3. `execute_python` initially reported failure under payload key `code`; the shipped handler accepts
   `content`/`text`/`message`/`body`. Re-run with correct keys — it succeeded. **Reporting the first
   result would have understated the finding in SYNAPSE's favour.**

### Limits

- **The positioning document is not in the repository.** All four verdicts grade a transcription
  (§0.1). This is the binding limit on the whole leg.
- One machine, one build, one day: Windows 11, Houdini 22.0.368, 2026-07-27.
- Claim 2's token figures are inherited from leg C1 and **re-verified against C1's artifact** (7/7),
  but not independently re-measured. C1's own limits carry: proxy tokenizer, no live-model arm.
- No live GUI Houdini session was used. Claim 1's in-process assertion rests on static reading of
  `ClaudeWorker` plus a runtime check that the vendored SDK imports on Houdini's interpreter — not
  on observing a model call inside a running graphical session.
- The `$JOB`-unset collapse (C0-F3.2 condition 2) was read from `handlers_memory.py:47`, not probed
  end-to-end through a live Houdini `$JOB`.

---

## 6 · For ruling

1. **The positioning document enters version control before any further audit of it means
   anything.** A claim with no file has no producer and no history. *(Recommendation only —
   product-surface decision.)*
2. **Two claims are false as worded; two are true of something narrower.** What replaces them is a
   positioning decision, not an agent's call (Constitution Article I). Noting only that for claims 2
   and 4 the README **already contains** honest, producer-carrying replacements written by the
   author — the shortest path is to lift those sentences.
3. **`README.md:5` — "No external bridge, no RPC hop"** is contradicted by `mcp_server.py`'s own
   docstring. This is in-repo public-facing text and is the one claim-1 item that needs an edit
   regardless of what the positioning document says.
4. **C0-F3.2 is a live product defect, not a positioning defect.** `_handle_memory_write` reports a
   scope it did not honour for 8 of 9 entry types (Law 3). Out of C0's read-only fence; needs an
   owner.
5. **RULING 117 cites C0 findings whose artifact was never committed.** The rulings document has the
   defect it exists to catch (Law 2). This leg's artifacts now exist; whether R117's verdicts are
   superseded by this re-derivation is a human call.

---

*Produced by leg C0 under `harness/CLAIMS-01`. Read-only: no file outside `harness/notes/**` was
modified. Receipt: `harness/notes/receipts/C0.json`.*
