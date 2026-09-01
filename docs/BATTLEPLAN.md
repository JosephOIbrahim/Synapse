# SYNAPSE — Battle Plan · 2026-09-01

> **Lineage.** The 2026-08-31 plan lives at `docs/BATTLEPLAN_2026-08-31.md`. This document supersedes its §3–§4
> (board and week) and keeps its §2 Gate 0 and the BP1 receipts in force. §12 below is the grounding addendum
> written when this text met the live tree — where §12 and the body disagree, the missions follow §12.

Grounded Tue 2026-09-01 against the LIVE repo (origin/master `8c01a066` = v5.58.0 "the night the loops
closed honest", local `f75c94cd` +1 docs commit riding a push word), `CAPSULE_2026-09-01` (boot),
`docs/BATTLEPLAN.md` (08-31), BP1 receipts + ledgers in `harness/battleplan/runs/2026-08-31/`,
`harness/rails_exec.json`, the three ratified contracts, the panel tree (`python/synapse/panel/`,
2,721-line composition root), `docs/SYNAPSE_PANEL_CODEBASE_REVIEW_H22_LENS.md`, `docs/MONETA_FOLLOWUPS.md`,
"One Mission, Budget-First" (08-26), and the August threads in this project (Middle Lane 08-04,
Context Sensitive 08-17, State of the Union 08-31).

**Supersedes** `docs/BATTLEPLAN.md` (08-31) §3–§4 (board and week). **Keeps** its §2 Gate 0 and the receipts.
**Does not supersede** `BETA_DONE.md` (definition of done) or any ratified contract.
**Executes as** harness wave **BP2** — `harness/battleplan/`, own bus, worktree prefix `bp2-*`.
**Seats:** Fable 5 = scaffold + referee (this document, the mission JSONs, CRUX verdict reading).
Opus 4.8 = every builder leg. Haiku 4.5 = mechanical sub-tasks only. Model names live in `harness/rails_exec.json` and nowhere else.

Position: **demo-week mile 2 of 8.** Today's hands work is unchanged — the on-camera round-trip is the
18:00 predicate. Everything below runs in the agent lane while your hands are on the rig.

---

## 0 · The review — what the repo actually says

Every row names its evidence. UNKNOWN is a measurement, not a shrug.

### 0.1 Memory store

| # | Finding | Evidence | Status |
|---|---|---|---|
| M-1 | In-session deposit → recall works in the .400 GUI. G1 ENV and G2 PLUGIN pass in GUI; hython lane ran on .417 (agent lane, off demo path). | `runs/2026-08-31/silent_recall_gui.json` (build 22.0.400, 5 rows), `silent_recall_hython.json` (22.0.417) | GREEN (in-session) |
| M-2 | Cross-session recall (close → reopen → recall) has **never been measured**. Contract features all `passing:false` by design. | `.synapse/contracts/demo-round-trip.yaml` | **UNMEASURED — today, your hands** |
| M-3 | `memory-recall-honesty` code merged (BP1-HONESTY, SOUND-WITH-NITS) but every feature is still `passing:false` on origin. The flips are a ratification act, not a merge side-effect. | contract file on origin | AMBER — flips ride your word after you read the receipts |
| M-4 | **`Memory.id` collision (FU-1):** id is generated before `created_at` defaults, so id = f(content, type) — time-independent. Two identical deposits collide. JSONL dedups by dict overwrite; `MonetaBackedStore` appends both → `count()` and `get()` diverge. **Repeat-2 takes deposit identical content twice on a Moneta backend — this is exactly today's shape.** Camera won't show it; the store's truth breaks. | `docs/MONETA_FOLLOWUPS.md` FU-1, `python/synapse/memory/models.py` `__post_init__` / `_generate_id`; tripwire `tests/test_moneta_crucible.py::test_duplicate_content_id_collision_is_documented` | RED, fix is small (§6 STORE) |
| M-5 | "Requested Moneta, silently served JSONL" — the Sol-review W1 policy (08-09) was designed; whether it shipped is UNKNOWN from the clone. If a healthy JSONL can still masquerade as Moneta, that is the green-light-that-cannot-report-failure class again. | `docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md` W1 | UNKNOWN — probe first |
| M-6 | FU-2 (gate `run_sleep_pass`, the one destructive op) and FU-3 (CI never exercises the Moneta backend) are open. Neither is on camera. | `docs/MONETA_FOLLOWUPS.md` | parked to beta-W1 |

### 0.2 Latency

| # | Finding | Evidence | Status |
|---|---|---|---|
| L-1 | **There is no timing instrument on the memory path.** Zero `perf_counter` / `wall_ms` / `elapsed` in `python/synapse/memory/*.py`. | grep, 19 modules | **UNKNOWN** — cardinal rule: it cannot be called "resolved," it cannot be called slow |
| L-2 | `LATENCY_PLAN.md` is v4.2.1-era and covers the MCP → server → `hou` path (names sync JSONL `log_action()` at 5–15 ms per command). `harness/latency/LEDGER.md` covers USD `Flatten()` (330–347 ms/call on a 10k-prim stage; cost tracks authored array volume). Neither touches deposit/recall/reopen. | both files; `REGISTRY.json` has no memory entries | suspects on file, not conclusions |
| L-3 | "Evaluate Rigs in Parallel" / "Cache Animation" default-on in H22 change cook-timing assumptions — irrelevant to memory latency, relevant to any bench number quoted this week. | APEX blueprint §3 | note only |

### 0.3 Panel

| # | Finding | Evidence | Status |
|---|---|---|---|
| P-1 | **Float hijack.** `open_panel()` → `paneTabOfType(PythonPanel)` → `None` → `createFloatingPaneTab`. Every Ctrl+K without a docked tab spawns a float and hijacks any PythonPanel. No `.desk` file exists, so nothing persists. | `houdini/scripts/python/synapse_shelf.py:126–137`; capsule diagnosis | RED — on camera |
| P-2 | **Profiles ("experience level").** Three manifests exist (`manifests/{curious,expert,ml}.py`), switch persists (`settings.py` schema v3, `SwitcherState`), recompose is live (`synapse_panel.py:516 _select_profile → _recompose`). Curious folds `token_meter` (collapsed) and sets `density: airy`. 08-04 finding: "Qt doesn't cascade a root property to children; repolish the whole tree — this is why profiles looked identical." Whether that fix still takes, and whether anything beyond layout (system-prompt overlay, defaults) differs per profile, has **no receipt**. Your seat says it doesn't work. | `docs/PROFILES.md`; manifests; 08-04 thread | UNKNOWN → measure (§6 PANEL-TRUTH) |
| P-3 | **TOKEN readout.** The sink is honest and fed: `claude_worker.py:196 begin_task` / `:219 add(last_usage)`; `face_token.py:579 refresh_from_probe` reads it. But the **only refresh call site is `_show_token_face` (on open)**; no task-completion handler refreshes the face or the rail meter. Numbers are right when you click TOKEN, stale otherwise. | `synapse_panel.py:1038–1051`; grep of `panel/*.py` for done-handlers touching the meter: none found | RED — small wire |
| P-4 | **Two design-token systems.** `panel/tokens.py` (184 lines, legacy) survives only because `panel/styles.py` imports it; `designsystem/tokens.py` (605) is the real one. Contract `theme-seed-tokens.yaml` (amber, all `passing:false`): collapse to one system + seed from `hou.qt.color()`. Host-scheme seeding is invisible on a dark-theme camera. Retiring the dead pair is mechanical. | contract; grep of importers | collapse = Haiku sub-task; seeding = parked |
| P-5 | The H22-lens review stands: ~18 of ~50 panel modules dead or alt-entry; theme hardcoded not read; a process-wide liveness concern inverted into a UI widget. Approve the spine; send back the foundation. `python/synapse/ui/panel.py` (381 lines) is not what `synapse_panel.pypanel` loads. | `docs/SYNAPSE_PANEL_CODEBASE_REVIEW_H22_LENS.md`; `houdini/python_panels/synapse_panel.pypanel` | foundation = beta; spine = this week |
| P-6 | Spacing vocabulary exists and is under-used: `SPACE_XS/SM…`, `TYPE_ROLES`, `TRACKING_EM`, per-profile `density` root property. "Pentagram character preserved by TYPE_ROLES + TRACKING_EM" is already a comment in `tokens.py`. | `designsystem/tokens.py`; 08-04 thread | the spacing pass has a home |
| P-7 | W5L-PANEL (08-17) targets still binding: font floor derived from host (never a hardcoded pt), chat leading +0.75 pt, token spend from a real usage source. | `harness/autorevise/missions/w5l_panel.json` | constraints on §7 |

### 0.4 Harness

| # | Finding | Evidence | Status |
|---|---|---|---|
| H-1 | **Token meter is UNKNOWN in every ledger.** All six BP1 ledgers: `enforced_unit: turns`, `token_meter: UNKNOWN`, `tokens_in/out: UNKNOWN`, `cap.tokens: null`. Rails are honest and they cap turns; they cannot cap tokens because nothing parses executor usage. Same gap as 08-04 ("`tokens` reads unavailable on all 33 rows"). | `runs/2026-08-31/ledger_*.json` (6) | RED — first leg of the wave |
| H-2 | Execution seam is a lookup table: `mechanical → claude-haiku-4-5-20251001`, `reasoning → claude-opus-4-8`; `ollama` engine documented, not built. No referee tier. | `harness/rails_exec.json` | add `referee` (Fable 5) |
| H-3 | `harness/rope/` night loop (tiers.json, `--night`, digest) from the 08-26 doc is **not built**; BP1-RAILS built rails in `harness/` instead. Both want the same usage parser. | `ls harness/rope` (no tiers.json) | rope stays parked; parser shared |
| H-4 | Bus is free-form (`post(wave, frm, mtype, body, to)`); mission schema requires `id name band source targets acceptance deps readonly touches crucible_criteria`; `gui_probe` evidence requires `gui_required:true`. No on-task/drift check exists. | `bus.py:27,39`; `mission_schema.py:10–13,55` | drift check = 40 lines, zero tokens |
| H-5 | Four standing RC blockers (`mutation_fail_closed · hot_reload_gated · installer_host_targeted · ci_covers_shipping_surface`) published-over under your waiver twice. | v5.58.0 release body; `HARDENING_BACKLOG.md` | not this week; every release re-signs |

---

## 1 · What "10% more demo-ready" means — the ledger

Demo-ready is the 60-second story running clean on camera. Count, don't feel.

| # | Demo-readiness item | Today | After BP2 (HIT branch) |
|---|---|---|---|
| 1 | Build .400 pinned; launch-path env bucket closed | GREEN | GREEN |
| 2 | v5.58.0 published, CI green | GREEN | GREEN |
| 3 | In-session deposit + recall in GUI | GREEN | GREEN |
| 4 | Cross-session round-trip on camera ×2 | UNMEASURED | your hands, today |
| 5 | Recall never silent (honesty contract) | AMBER (unflipped) | GREEN (your word) |
| 6 | Memory latency inside a stated camera budget | UNKNOWN | MEASURED (number on file) |
| 7 | Repeat deposits don't corrupt the store (FU-1) | RED | GREEN |
| 8 | Panel opens docked; no float hijack | RED | GREEN (GUI-verified) |
| 9 | Profiles visibly differ; switch persists | UNKNOWN | MEASURED + fixed if red |
| 10 | TOKEN readout updates per task | RED | GREEN |
| 11 | Panel spacing at the Cohere rhythm (camera regions) | RED | GREEN (timeboxed) |
| 12 | Harness spend measured in tokens, caps enforceable | RED | GREEN |
| 13 | 60-second narrative + rough cut | RED | Thu |
| 14 | Full dry run | RED | Sun |

3 of 14 green today. The 10% is one honest step: **everything on camera stops lying (8, 9, 10, 11) and the
memory beat gets numbers (6, 7).** Not a redesign. A truth pass with a spacing pass on top.

---

## 2 · First principles → calls (override by number)

1. **Unmeasured stays UNKNOWN.** No latency claim, no "profiles work," no token cap until an instrument exists. The first leg in every lane is a probe. Probes are pure Python / hython where possible — zero tokens.
2. **Same failure class, same weapon.** Silent recall, cook-success noop, stale token readout, identical-looking profiles — all green-lights-that-cannot-report-failure. Each gets a test that must fail under mutation, not a patch.
3. **Memory ahead of harness, harness ahead of paint.** STORE + LATENCY receipts before any panel merge word; METER before any leg that wants a token cap; PANEL-TRUTH before PANEL-DESIGN. The graph in §3 encodes this.
4. **Fable 5 referees, Opus 4.8 builds, Haiku does chores.** Referee calls are few and read-only (scaffold, verdicts). Builder legs never escalate model tier on their own; a failed accept is a DISCARD row and a bus `block`, then one bounded repair, then stop.
5. **WIP is 2 pairs, never 7.** Parallelism only where surfaces don't overlap (harness/ ∥ panel/; memory/ read-only ∥ memory/ write).
6. **Design is truth-gated.** The spacing pass lands on the measured panel, uses the existing token scale, adds zero colours, zero widgets, zero families. The Expert pin (`test_expert_resolved_equals_v5420_snapshot`) stays green — spacing is QSS, not structure.
7. **Camera profile = Curious.** The story is an artist; airy is the rhythm the references have. Your call to override (→ Expert stays pinned either way).
8. **Camera latency budgets (proposed; ratify or override):** deposit ack ≤ 500 ms · recall ≤ 1,500 ms p95 · reopen-with-memory-layer ≤ 3,000 ms, on the demo scene, N ≤ 200 memories. Over budget → a fix leg opens with the bucket named. Under → done, no optimisation.
9. **FU-1 fix is the small one.** Generate the id after `created_at` defaults (time-dependent hash, format unchanged, no migration). UUID + `content_fingerprint` (Sol-review W2) is beta-W2 — it drags legacy `mem_*` ids and the WAL with it.
10. **Words stay words.** Merge · push · tag/publish · drop.json · ratified flips · waivers — per act, spelled out. A green CRUX receipt is a precondition for a merge word, never a substitute.

---

## 3 · The board — three lanes and one graph

**HANDS** — Joe, in Houdini (RED, never simulatable)
- Tue — round-trip takes ×2 in the .400 GUI, screen-recorded; Ctrl+Z receipt in the same sitting. Float workaround first (30 s): dock a Python Panel tab set to Synapse in the main desktop → Windows → Desktop → Save Current Desktop As.
- Wed — GUI verify: panel float fix, TOKEN refresh, profile switch → close → reopen. Paste `memory_latency_probe.py` into the Python shell (GUI half). Read CRUX verdicts.
- Thu — narrative; GUI verify the spacing pass on the camera regions.
- Fri — Solaris 2 h · panel nits 2 h. Ship at the timer.
- Sun — dry run.

**AGENT** — wave BP2, Opus 4.8, `harness/battleplan/`, worktrees `bp2-*`

```
           ┌──────────────┐        ┌──────────────────┐
  pair 1   │  BP2-METER   │        │  BP2-PANEL-TRUTH │       (harness/ ∥ panel/+tests/)
           │  harness/    │        │  panel/ tests/   │
           └──────┬───────┘        └────────┬─────────┘
                  │ measured tokens          │ profile_diff.json · refresh test
                  │ (caps recalibrate)       │
           ┌──────┴───────┐        ┌────────┴─────────┐
  pair 2   │ BP2-LATENCY  │        │    BP2-STORE     │       (memory/ read-only probe ∥ memory/ write)
           │ probe only   │        │ FU-1 + M-5 probe │
           └──────┬───────┘        └────────┬─────────┘
                  │ p50/p95 + bucket         │ receipt
                  ▼                          ▼
        [over budget?] ──yes──► BP2-LATENCY-FIX (amber, spawned, bucket named)
                  │ no
                  ▼
           ┌──────────────────┐
  solo     │ BP2-PANEL-DESIGN │  deps: PANEL-TRUTH merged · /design spec first · amber
           └────────┬─────────┘
                    ▼
           ┌──────────────┐
  solo     │   BP2-CRUX   │  read-only · referee tier · blocked on all builders
           └──────────────┘
```

Edges are bus messages, not hopes. A leg with an unmet dep sleeps until the dep's receipt is posted.

**WORD** — Joe, per act
push `f75c94cd` · merge BP2 legs after CRUX · ratify `memory-recall-honesty` flips after reading receipts ·
ratify §2 calls 7–8 · v5.57.0 draft: publish-or-delete · Tue 18:00 branch (§4) · tag/publish v5.59.0 only if
Sun's dry run is clean (release ritual: bump → verify `--mode B` → tag).

---

## 4 · The week, with the branch

| Day | Mile | Done = |
|---|---|---|
| Tue 9/1 | 2 / 8 | Push word. BP2 pairs 1+2 armed with `-Budget`. Round-trip takes ×2 on camera. **18:00 branch.** |
| Wed 9/2 | 3 / 8 | CRUX verdicts on pairs 1+2 read; merge words. METER's first measured ledger → token caps set. LATENCY number on file; FIX spawned only if over budget. PANEL-DESIGN dispatched (spec first). |
| Thu 9/3 | 4 / 8 | 60-second narrative + OpenMontage rough cut (ugly is the plan). PANEL-DESIGN implement session; GUI verify camera regions. |
| Fri 9/4 | 5 / 8 | Solaris 2 h · panel nits 2 h. Ship at the timer. CRUX on PANEL-DESIGN. |
| Sat–Sun | 6–8 / 8 | Finesse the edit. Dry run. Demo-ready. |

**Tue 18:00 branch.** Two HITs on camera → the table stands, Sep 6. No HIT → demo-ready moves to **Sun Sep 13**;
STORE + LATENCY(-FIX) become the beta-W1 opener with the bucket the takes named; the PANEL legs continue
unchanged — beta needs them regardless. Decided by a receipt, not a feeling.

---

## 5 · Contracts (`.synapse/contracts/`, `git add -f`; ratification is your word)

| Contract | Tier | Goalpost | State |
|---|---|---|---|
| `demo-round-trip.yaml` | red | two HITs on camera, repeat-2 | armed 08-31, your hands today |
| `memory-recall-honesty.yaml` | green | recall never empty-success | code merged; **flips pending your read** |
| `harness-budget-rails.yaml` | green | cap · halt · ledger · seam | merged; **extend**: tokens measured when the engine reports (METER) |
| `memory-latency-receipt.yaml` (new) | green → amber | `memory_latency_<env>.json` exists, repeat-5, p50/p95 per op, build runtime-observed; every unmeasured field literal UNKNOWN; fix leg may open only against a named bucket | author in BP2-LATENCY, ratify Wed |
| `panel-truth.yaml` (new) | green | float fix; TOKEN face + rail refresh on task completion (UNKNOWN discipline intact); `profile_diff.json` proves what differs per profile; Expert pin green | author in BP2-PANEL-TRUTH |
| `panel-rhythm.yaml` (new) | amber | spacing tokens + QSS only; zero new colours/widgets/families; density steps on gaps only; Expert pin green; GUI sign-off on the five camera regions is red (your eyes) | author in BP2-PANEL-DESIGN |
| `theme-seed-tokens.yaml` | amber | one token system + host seeding | **split**: retire dead `tokens.py`/`styles.py` if no importers (Haiku chore inside PANEL-DESIGN); host seeding stays parked |

---

## 6 · Leg briefs — targets · accept · crucible

Common to every leg: read `harness/AGENT_CONSTITUTION.md` first. Bus `claim` before any edit; overlapping open
claim stops the leg. Commit before receipt (CRX0). Receipts claim observed scope only. One bounded repair per
failed accept, then `block` on the bus and stop. Post `progress` every 5 turns (see §8). Never flip a contract
feature — flips are Joe's word.

### BP2-METER · BUILD · harness/ · reasoning tier · cap 40 turns
**Demo needs it?** Yes as multiplier — every leg this week runs under it. Cut the drift check first if it runs long.
- T1 `harness/usage_envelope.py`: parse the `claude -p --output-format json` envelope → `{input_tokens, output_tokens, cache_read, cache_creation, cost_usd?, turns}`; absent field → `None`. Recorded fixture envelope in `tests/fixtures/`. `rails.py` charges tokens when present; `enforced_unit` becomes `tokens` when a token cap is set and the engine reports, else `turns`. Ledger fields become integers where measured, literal `UNKNOWN` otherwise. `orchestrate.ps1 -Budget "40turns,120000tokens"` halts on whichever crosses first.
- T2 `rails_exec.json`: add `referee: {engine: claude, model: claude-fable-5}` (lookup only; nothing else decides the model). ADAPT: `claude --model claude-fable-5 -p ok` — if the alias does not resolve, CRUX runs on `reasoning` and the receipt says so. Referee tier is read-only by convention: scaffold and verdicts, never builds.
- T3 `harness/battleplan/drift.py` (≤ 60 lines, pure Python): reads the wave bus; per leg, on-target ratio = messages citing a `T<n>`/acceptance id ÷ `progress` messages over the last 5; < 0.6 → orchestrator posts `refocus` with the leg's targets verbatim; two `refocus` without improvement → `halt` via rails. Add `progress`/`refocus` to the prompt template. Zero model calls.
- Accept: (a) parser unit tests incl. negative control (envelope without usage → every field `None` → ledger `UNKNOWN`); (b) `prove_rails.py` proof run whose ledger shows integer tokens for at least one leg; (c) tiny-token-cap run halts with `status blocked, reason budget`; (d) `-DryRun` control log byte-identical before/after (the BP1 baseline); (e) `drift.py` unit test on a synthetic bus with one drifting leg.
- Crucible: no estimate anywhere (a token count that is not from the envelope is worse than UNKNOWN); the seam stays a lookup table; `orchestrate.ps1` without `-Budget` unchanged.

### BP2-PANEL-TRUTH · TRUTH · panel/ + tests/ · reasoning tier · cap 30 turns
**Demo needs it?** Yes — three things on camera have no receipt.
- T1 **Profile diff.** Headless Qt (the `test_rope_*` harness): compose all three manifests; diff resolved widget tree (visible/collapsed/stretch/prominence/density), the composed system prompt (hash + overlay text), and `defaults`. Emit `harness/battleplan/runs/<date>/profile_diff.json`. Assert the density root property repolishes descendants (08-04 finding) with a test that fails if the repolish is removed. Persist test: select → save → load → same profile.
- T2 **TOKEN refresh.** Wire the worker's task-completion path → `face_token.refresh_from_probe()` and the rail meter/pill (`compositor` ids `token_meter`, `token_pill`) via the existing `USAGE_SINK.snapshot()`; UNKNOWN stays UNKNOWN; never poll on a timer (V3 rule: a probe must never trip the limit it reports on). Test: feed the sink, emit completion, assert the face/pill text changed; negative control: unfed sink → UNKNOWN.
- T3 **Float fix.** `synapse_shelf.py open_panel()`: prefer a tab whose `activeInterface().name() == 'synapse_panel'` → else `paneTabOfType(NetworkEditor).pane().createTab(PythonPanel)` → float only if no panes. ~15 lines. Unit test with a mocked `hou`; GUI verify is red (Joe). Write `docs/help/` one line: "Save your desktop once."
- Accept: `profile_diff.json` exists and states what differs (even if the answer is "only prominence + density" — that is a finding, posted to the bus for PANEL-DESIGN); refresh test + negative control; float unit test; Expert pin green; `pytest -q` green.
- Crucible: `synapse_panel.py` lifecycle/timer lines untouched (W5L-LIFE surface); no `hou.*` in `claude_worker.py`; no hardcoded pt sizes introduced.

### BP2-LATENCY · TRUTH · probe only, no edits under memory/ · reasoning tier · cap 20 turns
**Demo needs it?** Yes — the beat has no number.
- T1 `harness/battleplan/notes/memory_latency_probe.py`: wraps the public calls — store open, deposit (ack), recall (`MemoryPort.query_and_filter` of a known deposit), close → reopen → layer-in-stack check → recall — with `perf_counter`; repeat 5; records `wall_ms` per op, p50/p95, N memories, backend + embedder id + dim (from the health line), build runtime-observed. Runs under `.synapse/hytest.py` (agent) and pasted into the GUI shell (Joe). Headless Moneta may render UNAVAILABLE by construction — that is a measurement.
- T2 Bucket the number if over §2-8 budget: embedding time · stage/layer compose (`Flatten()` class) · sync JSONL I/O · lock wait · predicate scan. Name it on the bus with the row that says so. Author `memory-latency-receipt.yaml`.
- T3 If over budget → post `spawn` for BP2-LATENCY-FIX (amber, memory/ write, deps: STORE merged) with the bucket as its only target. Not before.
- Accept: `memory_latency_hython.json` (agent) + `memory_latency_gui.json` (Joe, `gui_required:true`); every field measured or UNKNOWN; no code under `python/synapse/memory/` changed (diff is empty there).
- Crucible: repeat-5 not repeat-1; p95 reported, not mean; build stamp equals `hou.applicationVersionString()` observed in the same process.

### BP2-STORE · BUILD · memory/ · reasoning tier · cap 30 turns
**Demo needs it?** Yes — repeat-2 takes on a Moneta backend.
- T1 FU-1: generate `Memory.id` after `created_at` defaults (time-dependent, format unchanged, backfill unaffected). Invert the tripwire so the collision test now asserts distinct ids; keep a test that identical content+type+created_at still dedups (that is the intended overwrite).
- T2 M-5 probe: with `SYNAPSE_MEMORY_BACKEND=moneta` and Moneta made un-importable in-test, the store must report BLOCKED/UNAVAILABLE in the health row and memory tool responses — never a healthy JSONL. If already so, the receipt cites the line; if not, fix inside the existing status vocabulary (`SUCCESS|UNAVAILABLE|BLOCKED`, §4 surface byte-identical).
- T3 Health line carries requested backend · active backend · embedder id · dim · row count (the W1 operator acceptance) if it doesn't already.
- Accept: tests for T1 (+ negative control), T2; `tests/test_loop_contracts.py` unchanged and green; diff adds no third store authority (`store.py:1514`, `ledger.py:320` remain the two — the honesty contract's rule).
- Crucible: no fsync/durability posture change (R-CI0-1 pending); no UUID migration; no `run_sleep_pass` gating (FU-2 parked).

### BP2-PANEL-DESIGN · BUILD · designsystem/ + qss + manifests · reasoning tier · cap 60 turns (two sessions: spec, implement) · amber
**Demo needs it?** Yes (P5, on camera) — timeboxed; Fri's 2 h absorbs nits.
- Session A — `/design` spec. Input: §7 of this doc + `profile_diff.json` + the five camera regions. Output: a handoff spec (token table, per-region QSS rules, density multipliers, before/after measurements in px) written to `docs/PANEL_RHYTHM_SPEC.md`. **ADAPT:** confirm the skill's invocation syntax with `/help` before dispatch; if `/design` is unavailable in the leg's session, the spec is authored by hand from §7 — same output, same accept.
- Session B — implement: extend `designsystem/tokens.py` spacing scale to §7 values (map onto the existing `SPACE_*` names, don't rename), QSS descendant rules keyed on the existing `density` root property, five camera regions only, `fontload.py` untouched, zero new colours.
- Haiku chore (mechanical tier, own tiny mission): `python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel` — if only `styles.py` imports it and nothing imports `styles.py`, delete both; else post a `finding` and leave them.
- Accept: spec file exists with px numbers; QSS diff touches no colour token; Expert pin green; a headless test asserts gap tokens step by the density multipliers; `pytest -q` green; GUI sign-off on the five regions is red (Joe, Thu/Fri).
- Crucible: any new hex string in the diff is BROKEN; any new `QFont` family is BROKEN; any manifest structural change to Expert is BROKEN.

### BP2-CRUX · TRUST · read-only · referee tier (else reasoning) · cap 25 turns
Same shape as BP1-CRUX: re-run every acceptance predicate in a fresh checkout; author ≥ 4 mutations per builder
(restore the stale-refresh path; remove the density repolish; re-order id generation; strip usage from the envelope)
— every one must turn a test red; verdict `SOUND | SOUND-WITH-NITS | BROKEN` with `chain_broken_at`. BROKEN
does not ride. Verdicts are read before merge words fire.

### Mission JSON — schema-valid example (`harness/battleplan/missions/BP2-METER.json`)

See the authored file — it is the example. (The draft example that rode into this document used
`"evidence": "artifact"`, which the schema rejects; the vocabulary is `probe|check|test|receipt|gui_probe` — §12 R-7.)

---

## 7 · Panel rhythm — the spec the `/design` leg starts from

Derived from the Pentagram/Cohere references you attached (endpoint list, model cards, the parameter panel of
the pebble tool) and the Pentagram case text ("hardworking functional assets built to perform at a small scale";
mono for tags and notes as contrast and focus; natural + synthetic palette — coniferous green, mushroom grey,
volcanic black with simulated coral, synthetic quartz, acrylic blue). Your tokens already carry that palette
(`SIGNAL`, `SIGNAL_DEEP #627A93`, `WARM`, `HOT_SOFT`, `CONIFEROUS`). **This pass adds no colour.** It adds rhythm.

**What the references do, as rules (not pixels to copy):**
- Section labels float; hairlines separate groups. A label is small, mono, uppercase, tracked, muted — it never carries a border of its own.
- List rows are cards that don't touch: a leading glyph cell separated from the label by a vertical hairline, the label at body size and normal weight, an optional tag at the far right in the label style. Rows breathe (gap ≈ ¾ of the row's inner padding).
- Cards have three bands — header, body, footer — separated by hairlines; the footer carries one text action left and one status pill right. Nothing is bold; hierarchy is size, tracking, and air.
- Parameter rows align to fixed columns (label · value · control); the panel reads as a grid because every row obeys the same three stops.
- One accent does the pointing. Everything else is surface steps of one grey ramp.

**Tokens (4-pt grid; map onto the existing `SPACE_*` names, never rename):**

```
SPACE      4 · 8 · 12 · 16 · 24 · 32 · 48
ROW_MIN_H  44        list rows (glyph cell 44×44, hairline right)
RADIUS     8 rows · 10 cards · 999 pills
HAIRLINE   1 px BORDER token — never 2 px, never a shadow
LABEL      mono · uppercase · tracking +0.08 em · 0.72× body · TEXT_MUTED · 24 above / 12 below · hairline under the GROUP
TAG/PILL   mono · uppercase · 0.68× body · tracking +0.06 em · neutral surface · padding 6/10
CARD       header 40 · body pad 16 · footer 40 · hairline between bands
PARM ROW   label col 128 · value 64 · control fills · row 24 · group gap 16 · section head 32
DENSITY    airy ×1.5 · standard ×1 · tight ×0.75 — GAPS only, paddings fixed (root property + repolish, 08-04)
TYPE       families from fontload.py only; sizes floor at the host default (W5L-PANEL T1); mono = labels/pills/ids, sans = body
```

**Five camera regions, in order — stop at five:**
1. Profile tab strip → pill toggles, one active in `SIGNAL` (the Setup/Style/Render idiom).
2. Verb rail (EXPLAIN / FIX / OPTIMIZE / BUILD HDA) → label style, doubled gaps kept, hairline under the group.
3. **Recall card** (the beat) → three-band card; footer pill mirrors the contract's status set: `HIT` / `NO HIT` / `UNAVAILABLE` / `BLOCKED`. Never a colour for HIT — a pill in the label style; `HOT_SOFT` only for BLOCKED.
4. TOKEN face → parameter rows (label · value · bar), UNKNOWN rendered as text in the value column, never a bar at zero.
5. `.hip` ribbon + header status line → one row, label style, the `?` glyph opens docs (08-04 decision).

Curious gets the airy multiplier; Expert is untouched in structure and reads the same tokens at ×1 — the pin proves it.

---

## 8 · Orchestrator mechanics — agents talking, budgets aligned, nobody wandering

**Arming.** `arm_bp1.ps1` → `arm_bp2.ps1` (wave id only): `build_manifest_bp2.py` → `waves/bp2.live.json` →
`orchestrate.ps1 -ManifestPath … -Budget "<turns>turns"` detached with the pid file; `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`;
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`. Never headless through DC; DC polls the log.

**Bus protocol (mtype strings on the existing `post()`):**
`claim` (before any edit, path globs) · `finding` (evidence row, consumed by name) · `block` (failed accept after one repair) ·
`spawn` (class `probe` only, cap 8 turns, admitted by the orchestrator only if wave remaining > 2× the spawn cap) ·
`progress` (every 5 turns: `{target, evidence_path}`) · `refocus` (orchestrator → leg, targets verbatim) · `halt` (rails).
Cross-talk that matters this week: LATENCY `finding` → STORE (if the bucket is id/lock) and → LATENCY-FIX spawn;
PANEL-TRUTH `finding` (`profile_diff.json`) → PANEL-DESIGN; METER `finding` (first measured ledger) → orchestrator
recalibrates every later cap (below).

**Dynamic rules.** Caps are re-read from the ledger after METER's first measured run: a leg at 80% of cap gets a
`wrap_up` note; a leg over cap halts (`blocked: budget`) and its partial work stays on its branch for a fresh session
with a capsule — never an in-place continue. The Tue 18:00 result changes deps, not legs: no HIT → LATENCY-FIX
and STORE go first Wed; PANEL legs unchanged.

**On-task.** `drift.py` (METER T3) is the mechanism; `stop_when` in contracts is the ceiling; CRUX is the audit.
A leg that posts three `progress` messages citing no target is drifting by definition — the orchestrator answers
with its own targets, not with new ideas.

**Model tiers (rails_exec.json):** `referee → claude-fable-5` (scaffold, CRUX; read-only; ADAPT alias) ·
`reasoning → claude-opus-4-8` (all builders) · `mechanical → claude-haiku-4-5-20251001` (chores: importer
retirement, fixture recording, boilerplate). Opus 5 is GA; the pin stays 4.8 this week — a model swap mid-demo is
scope creep, and the pin is what your receipts were measured on.

**Budget (this is the `/token-budget-advisor` read).** Turn caps are the only enforceable unit today:
METER 40 · PANEL-TRUTH 30 · LATENCY 20 · STORE 30 · PANEL-DESIGN 60 · CRUX 25 · spawns ≤ 2 per leg × 8 → **≤ 300 turns**
for the wave. Token envelope: **UNKNOWN until METER's first ledger.** The 08-26 estimate (small Haiku task 30–60k in /
3–6k out; Opus roughly an order of magnitude more per token) is the only prior; it is an estimate and is labelled
one. After METER lands, set `-Budget` per leg to 1.5× its first measured run and the wave to 10% of the weekly
quota, leaving the day for you. (Unit correction: a rails turn is a leg dispatch — §12 R-3.)

**`/token-saver` inside the wave.** Each brief carries its mission JSON + the exact file list, never a transcript.
`--strict-mcp-config` + `no-mcp.json` for leg sessions (already in rope). Probes are Python/hython (zero tokens).
One bounded repair, then DISCARD. CRUX reads receipts and diffs, not transcripts. METER's first ledger measures the
fixed prefix; if `tokens_in` on a trivial leg exceeds ~10k, trim `CLAUDE.md` to what the executor needs
(it is ~4,600 words against its own <2,500-token note) and point the brief at files instead.

---

## 9 · Words and the operator's card

**Your checklist (open here next session):**
- [ ] push — `a1cfab1f` (docs + capsule, two commits). One word.
- [ ] **Round-trip ×2 on camera** — the 18:00 predicate. Float workaround first (30 s). Every take is footage; stamp it.
- [ ] arm BP2 pairs 1+2 with `-Budget` (agent lane, while your hands are on the rig).
- [ ] ratify §2 calls 7 (camera profile) and 8 (latency budgets) — or override by number.
- [ ] Wed: read CRUX verdicts → merge words → ratify `memory-recall-honesty` flips → set token caps from METER's ledger.
- [ ] v5.57.0 draft — publish (non-Latest, tag at `adfe59e0`) or delete. Your call.
- [ ] `_rr.ps1` → pass `--mode B` for release verifies (one-line hygiene).

```
git -C C:\Users\User\SYNAPSE status --short                                  position
python harness\battleplan\mission_schema.py --all                            validate the six missions
python harness\battleplan\compile_wave.py bp2 → make_control.py bp2 → build_manifest_bp2.py   in order, always
powershell -File harness\battleplan\arm_bp2.ps1                              arm (detached; pid file; -Budget inside)
powershell -File harness\battleplan\watch_bp2.ps1                            poll the log; toasts
python harness\battleplan\bus.py read bp2 --types finding,block,refocus       what the agents are saying
python harness\battleplan\status_bp2.py                                      board (text)
python harness\battleplan\dashboard_bp2.py                                   board (html) → harness\battleplan\board_bp2.html
type harness\battleplan\runs\<date>\ledger_<run>.json                         spend — integers or UNKNOWN
python harness\battleplan\drift.py bp2                                       who is off target (after METER T3)
hython .synapse\hytest.py harness\battleplan\notes\memory_latency_probe.py    the number (agent half)
$env:SYNAPSE_GATE_C=1; git push origin master; Remove-Item Env:SYNAPSE_GATE_C  push (Gate C, yours)
harness\rails_exec.json                                                       the only place a model name lives
```

Verify once before arming: `claude --model claude-fable-5 -p ok` · `claude --model claude-opus-4-8 -p ok` ·
`claude --help` shows `--output-format` · `/help` shows `/design`. (Done 2026-09-01: `harness/battleplan/runs/2026-09-01/preflight.json`.)

---

## 10 · Not on the path (kept, parked)

`harness/rope/` night loop (tiers.json, `--night`, digest — adopts the usage settle in one line later) · host-scheme
token seeding · UUID ids + WAL migration (W2) · FU-2 / FU-3 · the four RC blockers · BASTION B1/B2/B3 (= beta-W2) ·
APEX H22 phases 1–7 · WA2 rungs · REACH + FLOW · panel foundation (the ~18 dead modules) · overnight reflex loop
(needs governance ratification before a line is written) · Hanish settle on camera (october label).

---

## 11 · Unknowns, stated

Fable 5 alias availability in Claude Code (ADAPT — resolved 09-01, see preflight receipt) · `/design` skill syntax (ADAPT) ·
whether the 08-04 density repolish still takes in the shipped panel (PANEL-TRUTH measures) · whether M-5 shipped
(STORE probes) · every token number in this document (METER measures) · every latency number (LATENCY measures).
None of these is assumed anywhere above; each has a leg whose first act is to replace the unknown with a receipt.

---

## 12 · Grounding addendum — 2026-09-01 recon (Fable 5 referee seat, DC session)

Written after §0–§11 met the live tree. Each row is a finding with its anchor and the call it forced.
The missions in `harness/battleplan/missions/BP2-*.json` follow this section wherever it and the body disagree.

| # | Finding | Evidence | Call |
|---|---|---|---|
| R-1 | Local HEAD is `a1cfab1f` (boot capsule) — two commits ahead of origin `8c01a066`, not one. | `git rev-parse HEAD origin/master` | Push word covers both. |
| R-2 | Mission id TAG is `[A-Z0-9]{2,12}` — no hyphens. `BP2-PANEL-TRUTH` fails admission. | `harness/battleplan/mission_schema.py:14` | Ids are `BP2-PANELTRUTH`, `BP2-PANELDESIGN`, `BP2-LATENCYFIX`. The gate is unchanged. |
| R-3 | A rails "turn" is **one leg dispatch** through `Rails-Charge`, not a conversational turn. `max-turns` exists nowhere in `harness/`; legs launch as interactive sessions; Claude Code 2.1.252 `--help` has no `--max-turns`. | `runs/2026-08-31/ledger_orch_budget_halt.json` (CTRLB refused at turn 2 > 1); `orchestrate.ps1:102–115, 406`; `runs/2026-09-01/preflight.json` | The §6/§8 per-leg caps are **self-reported brief guidance** policed by `drift.py`. Enforceable rails today = wave dispatch count + `StaleMinutes 40` / `MaxHours 12`. Arm line: `-Budget "10turns"` (4 dispatches + 6 slack for re-dispatch and spawns). |
| R-4 | `rails.py:176 measure_transcript_tokens()` and `charge --transcript` already exist; nothing calls them because `Rails-Charge` is a pre-dispatch gate. | `harness/rails.py:176, 472, 525`; `orchestrate.ps1:102–115` | METER T1 = a **post-close settle** from the leg's transcript JSONL. The `-p --output-format json` envelope parser belongs to rope's runner (parked); orchestrate legs never emit an envelope. |
| R-5 | One model string per manifest (`$manifest.model` → launch line); no per-leg tier resolution. | `orchestrate.ps1:363` | CRUX runs Opus 4.8 this wave whatever the alias check says; per-leg `tier` → model is METER T2. Referee alias resolves (preflight). |
| R-6 | Deps go `blocked → ready` on **receipt presence**, not on merge. | `orchestrate.ps1:337–341` | PANELDESIGN arms `state: held` (manifest builder); the Wed flip is Joe's word. CRUX deps = the four pair builders (BP1 shape); PANELDESIGN gets its own crucible leg Fri, authored Wed. |
| R-7 | `acceptance.evidence` vocabulary is `probe|check|test|receipt|gui_probe`; the drafted §6 example used `artifact`. | `mission_schema.py:44` | `artifact` → `receipt`. |
| R-8 | `spawn` admits class `probe` only (cap 8). A fix leg cannot be spawned from the bus. | §8 bus protocol; schema OPTIONAL fields | LATENCY posts the `spawn` proposal with the bucket; the referee authors `BP2-LATENCYFIX.json` on Joe's dispatch. |
| R-9 | Mission JSON has no `tier`/`cap` field (unknown fields are rejected). | `mission_schema.py:10–11` | Tier and self-cap live in `note` until METER T2 adds `tier` to OPTIONAL + row + launch line. |
| R-10 | Latest local tag is `v5.56.0`; v5.57/v5.58 tags are not in the clone. | `git tag --sort=-v:refname` | Not this week's path; reconcile before Sunday's tag ritual. |
| R-11 | `prompts/_template.md` carries BP1's territory sentence ("TRIAGE is read-only, RAILS owns harness/, HONESTY owns the recall path"). | template §bus | Replaced with the BP2 territory map; `progress`/`refocus` protocol added (METER T3 wires the orchestrator side). |
