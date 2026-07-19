# SYNAPSE_RELEASE_WEEK.md

**Governing document · Release Week · Sat Jul 18 → Fri Jul 24 2026**
**Status: DRAFT v2 (H22-native) — becomes GOVERNING on commit to master. That commit is the feature-freeze marker.**

> **Revision note (v2):** The v1 draft targeted graphical H21.0.671, a "1 ported / 104 on the wire" registry, and scaffolded perception. A grounded pre-flight sweep (2026-07-18, three verifiers + synthesizer, all anchors live) found those premises dead: H21.0.671 is not installed on this machine (only 21.0.773 and 22.0.368 are), the scene-1 port wave (11 tools) merged 2026-07-16, and RETINA T0+T1 shipped live across v5.28–v5.31. Joe ruled 2026-07-18: **re-target the week to Houdini 22 / current master.** This v2 is that amendment, landed before any governed work per F3. The week's shape, lanes, gate sentence, and protocols are unchanged.

---

## 0 · INGESTION CONTRACT (read first, Claude Code)

1. Read this document fully before executing anything.
2. Every leg carries a lane marker. **DISPATCH** = the harness's. **HUMAN** = Joe's — never attempt, never simulate, never mark done.
3. Work only what is in this document's task lists. Feature freeze is in effect from the commit that lands this file. Fix-forward is the only other permitted work.
4. Update the **Status Ledger** (§2) and check off tasks as you close them. Commit anchors required.
5. You may not amend scope. Amendments follow §9 and are Joe-authorized only. If reality contradicts this plan, log **DRIFT** (§9), halt that leg, surface it.
6. Standing constraints in §8 override everything in the leg tasks if they conflict.

**Precedence:** This document defers Blueprint v2.0's remaining port waves (G1 — 9 of 10 sub-waves; blueprint = `docs/SYNAPSE_H22_GAP_BLUEPRINT.md`) by one week and lands G6 (benchmarks — the blueprint's "Numbers for the claims" gate at `SYNAPSE_H22_GAP_BLUEPRINT.md:152`, **not** the unrelated `g6_check.py` camera-rig HDA check, a pure name collision). G3's original "land the co-processor" deferral is moot — RETINA T0+T1 are already live (v5.28/v5.29); what defers is M3 worker hardening. The blueprint remains the sprint's governing document; this is the release-week overlay.

**F3:** This file is committed before any execution it governs. Amendments are committed before the amended work runs.

---

## 1 · THE GATE (definition of done)

> **A stranger on a clean machine reaches the demo result from the README alone, sees what it costs, and never writes a key to disk.**

That sentence is the release. Every task below serves it. Nothing else ships.

**Release target (THE FORK, resolved by Joe 2026-07-18):** current **master** — the v5.32.x line, **Houdini 22.0.368** (the `harness/state/drop.json` build), 115 registry tools, RETINA T0+T1 live. Runtime for every leg: **graphical H22.0.368**. H21 artifacts, where genuinely needed, name **21.0.773** explicitly as the sibling build — the retired 21.0.671 baseline is uninstalled and appears nowhere on the critical path.

---

## 2 · STATUS LEDGER (harness updates; Joe reads one table on Friday)

| Leg | Day | Name | Lane | State | Anchor |
|-----|-----|------|------|-------|--------|
| 0 | Sat | Freeze prep (this rewrite + reconciliations) | DISPATCH | DONE | this file's landing commit = **F3 freeze marker** |
| 1 | Sat | Freeze + the demo | HUMAN (+dispatch support) | IN-FLIGHT | dispatch support DONE (script refresh + 7-agent verify, 2026-07-19); HUMAN recording pending |
| 2 | Sun | The numbers | DISPATCH | PENDING | — |
| 3 | Mon | The front door | DISPATCH | PENDING | — |
| 4 | Tue | The keys | DISPATCH | PENDING | — |
| 5 | Wed | The paper | DISPATCH | PENDING | — |
| 6 | Thu | The kill test | HUMAN (+dispatch standby) | PENDING | — |
| 7 | Fri | Cut it | HUMAN gates + dispatch support | PENDING | — |

States: `PENDING · IN-FLIGHT · BLOCKED · DONE`. A leg is DONE only when its **Done-when** is true, verified, and anchored to a commit.

**Parallelism rule:** the calendar is the gating order, not a cage. A DISPATCH task may run early if its PREREQS are met and its leg is not BLOCKED. The ledger tracks actual state.

---

## 2.5 · LEG 0 · SAT · FREEZE PREP — `DISPATCH` (new in v2)

*The reconciliations the sweep proved must land before the freeze marker is honest.*

- [x] **VERSION reconciled** — root `VERSION` still reads `5.31.0` while pyproject/`__init__`/CLAUDE.md/CHANGELOG declare v5.32.0 (missed in the v5.32.0 release; `VERSION` is canonical per `harness/CLAUDE.md`). Bump to `5.32.0`. *(Done in this commit — Joe-keyed override of the harness "don't edit VERSION from an agent" convention, per this doc.)*
- [x] **Ops disposition** — (i) scene-model graft work committed to `feat/scene-model` and **parked** at `1584343` (not merged; resumes post-tag under its CTO-gate conditions); (ii) MODE-B harness workflows declared **frozen for the week** (armed `drop.json` stays, no invocations outside this doc's task lists); (iii) master `stash@{0}` (superseded render-WIP) inspected — its diff (`_handle_render_bounded` registration + bounded-wait budget) verified already on master (`handlers.py:557`, `handlers_render.py:57`) — then dropped; (iv) all 11 stale `wf_*` worktrees + branches pruned (every branch an ancestor of master; scratch reports were July-16 gate outputs for waves already merged).
- [x] **Capture dir defined** — `demo/captures/` created, gitignored.

**Done when:** VERSION matches the declared line, the graft branch is parked, and the tree is clean for the freeze commit.

---

## 3 · LEG 1 · SAT · FREEZE + THE DEMO — `HUMAN`

**Objective:** Feature freeze declared; the demo runs end-to-end on **graphical H22.0.368** and is captured raw. Everything downstream quotes this capture.

**PREREQS:** Leg 0 done; this file committed.

**HUMAN (Joe):**
- [ ] Run the demo per the **refreshed** `DEMO_SCRIPT.md` (see dispatch task below) using `demo/synapse_demo.hip` + the live-prompt flow (`demo/README.md`) in graphical H22.0.368.
- [ ] Screen-record the full run, no cuts → `demo/captures/`. Store capture path in ledger anchor notes.
- [ ] Run it a second time from the same script — repeatability is the point.

**DISPATCH (support only):**
- [x] **Refresh `DEMO_SCRIPT.md` first** — the current file is dated 2026-02-08 and describes a 23-tool / 376-test product (today: 115 tools, ~4,571 tests). Rewrite to H22 reality without redesigning the demo's shape. `run_demo_builder.py` is retired from the critical path (H21-era, machine-specific OneDrive paths — `run_demo_builder.py:8-11`); the demo entry is `demo/synapse_demo.hip`. *(Done 2026-07-19: 3 truth-mappers grounded the rewrite — 115 tools per the DOC-1 method, real artist flow incl. footer-Connect + OCIO + task 0.5, bounded-render Act 3 with the Indie in-process truth; 19 stale claims dropped, all listed in the workflow record.)*
- [x] Pre-flight the refreshed script: verify paths, node names, and every `hou.*` symbol against the **22.0.368 connectivity catalog** + the committed `h22_symbol_table.json` (35,903 symbols). Phantom discipline applies (§8). Fix-forward any breakage found. *(Phantom-check CLEAN — the script's only `hou.*` cite is `hou.lopNetworks` used deliberately AS the phantom example, correctly absent; all 10 cited tools registered; all referenced paths exist. Crucible passed with 3 minor fixes applied: phantom-count claim re-anchored, watcher labels matched to `render_watch.ps1` output, menu-independent XPU prewarm fallback.)*
- [x] Confirm the demo scene builds headlessly where possible; flag any GUI-only step so Joe isn't surprised mid-record. *(hython 22.0.368: `demo/synapse_demo.hip` loads clean — `/stage` present, child `demo_base`, zero warnings/errors. GUI-only steps flagged `[GUI]` throughout the script.)*

**Done when:** the demo runs twice in a row from one script, and both captures are on disk.

---

## 4 · LEG 2 · SUN · THE NUMBERS — `DISPATCH`

**Objective:** G6 dies. One honest table — tokens, wall time, dollars per operation — regenerated by one command, method published adjacent.

**PREREQS:** none (may start immediately after freeze).

**Tasks:**
- [ ] Audit `_benchmark_api.py`, `_benchmark_latency.py` (both exist at root, functional as named). `LATENCY_PLAN.md` is **historical baseline only** (pinned to v4.2.1); measure fresh on the frozen target. `g6_check.py` is **unbound** from this leg (name collision — it's a camera-rig HDA check).
- [ ] A/B honestly stated: **Dispatcher-routed vs legacy-registry path — both over the WS round-trip** per OD-2(a) (`docs/PORT_WAVE_MANIFEST.md:15-19`). 13 tools route via Dispatcher today (Inspector + Scout + the merged scene-1 wave of 11). An in-process arm, if measured, is labeled an explicit experiment, not a shipping path. Same scene, same prompt, same model.
- [ ] Measure: tokens in/out, wall time, dollars per operation. Dollars from current published API pricing; cite source and date in the method block.
- [ ] Distributions, not heroes: median + p95 over ≥20 runs per condition. Environment stamped: hardware, **H22.0.368**, model string, date.
- [ ] Produce `BENCHMARKS.md` (to-create) — table on top, method beneath, one command to regenerate via `scripts/run_benchmarks.py` (to-create; wraps the two existing scripts).
- [ ] Truth contract: numbers are measurements. Unflattering numbers publish anyway.

**Done when:** the table regenerates from one command.

---

## 5 · LEG 3 · MON · THE FRONT DOOR — `DISPATCH`

**Objective:** Fresh Windows + fresh **H22.0.368** + README only → `running: True` inside sixty minutes. Zero manual pip; the vendored tree carries it.

**PREREQS:** none.

**Tasks:**
- [ ] Extend **`scripts/install_synapse_package.py`** (the live installer — writes `packages/synapse.json`, H22-aware incl. the OneDrive-Documents trap). Root `install.py` is the legacy design-system installer (its pref detect loops majors `[21,20,19]` — H22-blind) — fold its useful pieces (shelf/icons, `--verify` pattern) into the package installer or retire it; do not extend it.
- [ ] Add to the package installer: clone check, key-presence probe (reusing the `host/auth.py` resolver), vendored-tree integrity check (`python/synapse/_vendor/` intact — premise holds), and `--verify` reporting each README "You're good if" check as pass/fail in one screen.
- [ ] Keep the README's "You're good if / If you see" pattern. Update it only where installer behavior changes.
- [ ] Exercise the path in the cleanest environment available (fresh Windows user profile or VM). Note honestly in the ledger which was used.

**Done when (leg exit):** install + verify runs green in a scratch environment on one pass. **Final proof lands at Leg 6.**

---

## 6 · LEG 4 · TUE · THE KEYS — `DISPATCH`

**Objective:** The key footgun dies — **completing** a mechanism that substantially ships today: `host/auth.py` already loads a repo-root `.env` process-locally (`auth.py:79-110`); nothing writes the system environment now.

**PREREQS:** none.

**Tasks:**
- [ ] `host/auth.py`: add **`SYNAPSE_ANTHROPIC_KEY` as the preferred resolver alias** (honors RB-AUTH-001, which names it but was never wired — the name exists only in guardrail docs today). Order becomes `SYNAPSE_ANTHROPIC_KEY` → `ANTHROPIC_API_KEY` (fallback) → `hou.secure` probe (quarantined phantom on H22.0.368 — probe stays guarded, returns None). New tests pin the order. No existing test weakened.
- [ ] **Verify the `.env` key** — the current `ANTHROPIC_API_KEY` in `.env` is marked UNVERIFIED (prior 401/400). Verify or replace; the demo depends on it.
- [ ] README §3 rewritten: primary instruction is the repo-root `.env` (already the shipped mechanism), `SYNAPSE_ANTHROPIC_KEY` preferred name; warning block naming the collision — a permanent system `ANTHROPIC_API_KEY` is silently billable by any Claude Code / SDK process on the seat.
- [ ] DPAPI artist login — `forge_artist_login.md` **does not exist** (never did); the spec is **to-create**, referencing `panel/shot_login.py` (the closest real surface). **Timeboxed to this day.** Constraints: `ctypes` DPAPI only, no new dependencies, no raw key writes, `ANTHROPIC_API_KEY` never written to the system, no USD customData persistence (RFC-gated).
- [ ] Timebox rule: if login is not green by end of day, park behind a disabled flag, ship the hardened `.env`/env-var path, log an amendment proposal ("login → patch one"). Do not let the timebox leak into Leg 5.
- [ ] `.env` housekeeping: **add** `OCIO` and `WS_PORT` lines (neither exists in `.env` today, despite SPEC.md:62 expecting them) — or ship `.env.example` — then the preserve rule applies to every subsequent touch.

**Done when:** a fresh user gets a key in without ever writing `ANTHROPIC_API_KEY` to the system — via GUI login if the timebox held, via the `.env` path if it didn't.

---

## 7 · LEG 5 · WED · THE PAPER — `DISPATCH`

**Objective:** A stranger TD can answer *what is it, what does it touch, what does it cost* from the docs alone.

**PREREQS:** Leg 2 (the table feeds the cost answer). Other tasks may start earlier.

**Tasks:**
- [ ] README top rewritten in stranger-TD voice: one paragraph what-it-is, then install, then first ten minutes. The honest capability table **stays**, restated true: **11 tools ported (scene-1 wave, merged) / 104 of 115 on the legacy wire** — still an honest minority, still credibility.
- [ ] `SECURITY.md` (to-create) one-pager, sourced from `docs/studio/DEPLOYMENT.md` + `docs/studio/EGRESS.md` + CLAUDE.md §1.2. What leaves the building: prompts + tool results to the provider API. What never does: keys in plaintext on disk, scene files wholesale. Every transmission claim anchored file:line to `agent_loop.py` / transport code — verified, not asserted. Tier table: 01 on-prem / 02 API / 03 Opus.
- [ ] **H22 stance paragraph, inverted to the truth:** validated on **H22.0.368** (ten releases of H22-native work, v5.23→v5.32, live-verified in a running session). H21 relationship: 21.0.773 sibling artifacts retained. Gate 0.1 (`harness/notes/gate-0.1-sidecar-vs-abi3.md`) is strictly the **packaging** decision (sidecar vs abi3), not an H22-support gate.
- [ ] **Perception language:** RETINA T0+T1 are **live** — T0 file-truth (v5.28), T1 scoped-delta proof (v5.29), receipt honesty proven across **182 real render manifests** and surfaced in the panel (v5.31). "Not yet": M3 worker hardening + the disclosed S-LIVE owed items. No first-light framing — first light already happened.
- [ ] Operator's Card: one card, glanceable — boot, verify, key, demo, stop. Commands + what each does in operator words.
- [ ] Draft `RELEASE_NOTES.md` (to-create; distilled from CHANGELOG + gh releases, which remain the deep record) in truth-contract voice: **Verified** / **Not yet**. RETINA T0+T1 sit in Verified with their proof; the 104-tool port remainder and M3 in Not-yet.
- [ ] Cross-check every doc claim against the repo. Anything unverifiable gets cut or labeled Inference.

**Done when:** the three questions answer themselves from the docs, and every load-bearing claim carries an anchor.

---

## 8 · STANDING CONSTRAINTS (override leg tasks on conflict)

- **Human gates — never automate:** Gate 0.1 packaging decision · `drop.json` mode changes · merge/tag to master · the Leg 6 stranger-run · the Leg 7 IP sweep · publishing the launch post.
- **Commandment 7:** tests are never weakened. Fix forward only.
- **Suite baseline, stated honestly:** ratchet floor **4275 / 0 / 87** (`harness/verify/suite_baseline.json`); live local **4,571✓ / 4✗** — the 4 are known `test_bridge_endpoint` live-sidecar isolation failures, pre-existing tracked debt (CI green; CI lacks a live sidecar). Gates exclude those 4; fixing them is in-scope fix-forward, weakening them is not, and release week must not grow the set.
- **Commit discipline:** atomic commits; race-safe push (fetch + rebase, max 3 attempts, halt on merge conflict).
- **Phantom discipline:** every `hou.*` symbol confirmed against the committed introspected table `python/synapse/cognitive/tools/data/h22_symbol_table.json` (22.0.368, 35,903 symbols) + `KNOWN_ABSENT_HOU` (`harness/forge_evaluator_gate.py:54`). Quarantine confirmed live: `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()` all absent. PDG surface is `pdg.*`. (`rulebook/phantoms.json` is still empty — the symbol table + harness checks are the enforcement authority, not the rulebook file.)
- **Scope guard:** no KineFX/rigging, no VOP shader authoring, no vector-similarity cognition, no polling audits. `check_no_rigging_drift` (`harness/verify/checks.py:324`) stays green.
- **Schema freeze:** no USD schema or `customData` writes this week. The RFC gate stays closed.
- **Auth guardrail:** `ANTHROPIC_API_KEY` is never set permanently on any machine this harness touches; after Leg 4 adds them, `OCIO` and `WS_PORT` survive any `.env` change.
- **Not this week (locked):** the remaining 9 port sub-waves (G1) · RETINA M3 worker hardening + M5/M6 · the scene-model graft (parked on `feat/scene-model` with its CTO-gate conditions; resumes post-tag) · Moneta/Octavius · new blueprints or papers. The WS execution path ships as-is per OD-2(a), honestly labeled.

---

## 9 · REVISIONS IN TOW (amendment + drift protocol)

The plan is allowed to be wrong. It is not allowed to be silently wrong.

**AMENDMENTS — Joe-authorized only.** Append-only ledger below. Each entry: id, date, leg, change, one-line why. The amendment commits **before** the amended work runs (F3, recursively). The harness proposes; it never self-authorizes.

**DRIFT — harness-logged.** When execution contradicts the plan: log a DRIFT entry with a **Verified** anchor, set the leg BLOCKED, propose the amendment, stop that leg. Other legs continue.

**DAY STAMPS — harness-logged.** One line at close of each working day: date · legs touched · state changes · blockers. Marathon markers at commit boundaries.

### Amendments ledger
*(append-only)*

| ID | Date | Leg | Change | Why | Auth |
|----|------|-----|--------|-----|------|
| A1 | 2026-07-18 | ALL | v1 (H21-pinned) → v2 (H22-native): runtime re-pin to 22.0.368, port ratio 11/115, RETINA-live language, installer re-target, Leg 4 rescope, Leg 0 added, suite baseline stated, to-create artifacts named | Grounded sweep found the v1 premises dead (drift table: `scratchpad grounding, 19 rows`); Joe ruled re-target 2026-07-18 | Joe (verbal, this session) |

### Drift log
*(append-only)*

| ID | Date | Leg | Finding (Verified anchor) | Proposed amendment |
|----|------|-----|---------------------------|--------------------|
| — | — | — | — | — |

### Day stamps
*(append-only)*

- **2026-07-19** · Legs 0–1 · Joe turned the freeze key ("key", 2026-07-18); Leg 0 reconciliations executed (VERSION 5.31.0→5.32.0, stash inspected+dropped, 11 worktrees+branches pruned, `demo/captures/` created+ignored) and this file landed on master = **F3 freeze marker**. Leg 1 demo-preflight dispatch queued next. No blockers. *(Calendar note: Leg 0/1 ran Sun not Sat — one day behind the printed calendar; parallelism rule applies, gating order intact.)*
- **2026-07-19 (later)** · Leg 1 · Dispatch support DONE: `DEMO_SCRIPT.md` refreshed via 7-agent workflow (3 mappers → forge → phantom-check CLEAN + headless hip ✓ + crucible survives w/ 3 minors fixed); CI green on the freeze commit. Leg 1 → IN-FLIGHT; the recording is Joe's. Patch release v5.32.1 cut (freeze + demo preflight + canonical-VERSION heal).

---

## 10 · LEG 6 · THU · THE KILL TEST — `HUMAN` (anchor leg)

**Objective:** Clean machine, docs only, no memory of the repo allowed. This day is the actual release gate; Legs 1–5 were preparation for this run.

**HUMAN (Joe):**
- [ ] Fresh Windows + fresh **H22.0.368**. Follow the README and nothing else. Every stumble spoken aloud and filed.
- [ ] Reach the demo result start to finish.

**DISPATCH (standby):**
- [ ] Every filed stumble becomes a fix-forward same day: repair the code or the doc — whichever was lying. No test weakened, no stumble deferred.
- [ ] Re-verify Leg 3's sixty-minute claim against this run and correct `BENCHMARKS.md`/README if reality disagrees.

**Done when:** a stranger-run reaches the demo result start to finish.

---

## 11 · LEG 7 · FRI · CUT IT — `HUMAN` gates + `DISPATCH` support

**PREREQS:** Legs 1–6 DONE.

**HUMAN (Joe):**
- [ ] IP sweep with counsel: MIT × pending filings; what in the public tree is high-level substrate (safe) vs claim-bearing mechanism (`build_protected.py` — exists, tracked: 7 HIGH-IP modules → `.pyd`, `--dist` source-free package). **Hard gate — no tag without counsel's yes.** *(Per Joe's standing law, patents never gate engineering decisions — this gate governs what publishes, which is his call with counsel, not a build blocker.)*
- [ ] Tag the release on master. (Merge/tag is a constitutional human gate.)
- [ ] Publish the launch post.

**DISPATCH (support):**
- [ ] Finalize `RELEASE_NOTES.md` from the Leg 5 draft against the week's actual ledger — Verified / Not-yet, nothing else.
- [ ] Assemble the launch post draft: the capture, the table, one sentence of thesis. No claim the ledger can't anchor.
- [ ] Final ledger pass: every leg DONE with anchors, day stamps complete, amendments ledger reconciled.

**Done when:** the tag is public and the post links proof, not promises.

---

*The v1 human-readable card (`design/synapse_release_week.html`) was never created; if wanted, it is a Leg 5 to-create. This file governs.*
