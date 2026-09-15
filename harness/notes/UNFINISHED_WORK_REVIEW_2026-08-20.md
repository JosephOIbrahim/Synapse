# Unfinished-Work Review — 2026-08-20

Scope: master @ bb348abe / v5.55.0 / H22.0.400. Method: 2 agents (mapper = ledger sweep, assayer = hostile check on fresh work), 1 adversarial cross-round, both converged. All claims verified against live tree; every STATE claim checked had its artifact on disk.

**Headline: no fabricated greens anywhere. The debt is almost entirely governance — stale boards, unflipped human gates, unmerged finished work — plus four code items and seven untracked surfaces.**

---

## Ranked by (cost to Joe × what it unblocks)

**1. Hardening needs_joe disposition list — one sitting closes the next-run blocker.**
`harness/hardening/PASS_STATE.json` — 11 items (7 DECIDE / 2 AMEND / 1 NOTE / 1 OPTIONAL), complete + corroborated (clean-room 9/9 REPRODUCED, 0 BROKEN).
The sharpest item: `loop-orchestrator.md:87-89` still halts on "THE_LOOP_v5.1.md is UNRATIFIED" while `harness/loop/STATE.json:108` records that gate CLOSED by Joe's word and bb348abe sits on master tip. **The post-ratification dispatch path has never been exercised — the next LOOP run stalls on a closed gate.** Also in the list: STATE base_version 5.54.0→5.55.0, `loop.js:41` GROUND banner, contract wording.

**2. Merge queue — finished, green, one word each.**
- `clear/l5-phantom-scanner` @ eb1e110 (G2 scanner + 24 tests + P5.1, needs ratify/merge)
- `fix/corpus-usdrender-rop` (14 commits, attacks SOUND)
- `wave5/wxa|wxb|wxc` (closing receipts green_with_findings)
- PHANTOM SWEEP SPEC ratification + `rulebook/phantoms.json` population.

**3. Rope L5-14..L5-23 — 10 built panel-design items awaiting your verdict (yes/no, not code).**
Evidence suggests this review *happened today*: 17 `panel_diag_*` artifacts in `docs/harness/notes/`, stamped 13:14–13:25, live Qt introspection of the running panel (DsRailMeter geometry ↔ L5-17 verb-rail). Referenced by zero STATE files and zero commits — **the review's evidence is landing on no board.** Action: record outcomes into `rope/STATE.json`, note the evidence dir.

**4. REACH hygiene.**
- Stale row: gate0 `ENG-INJ-GATE-OFF` reads "gated — human DECIDE"; actually DECIDED ON (v5.54.0, `synapse_panel.py:2285-2294`, `enforce_worker_policy=True`). Zero-cost board edit.
- Real p2 unblockers — two live code P0s: `handlers_tops/cook.py:78-80` (PDG all-failed reports "cooked", zero state inspection) and `_tool_registry.py:204-205` (execute_python advertises "automatic rollback on failure" it doesn't have).
- Posture question (needs your word): REACH runs under an explicitly UNRATIFIED blueprint *by design* (ratification is not a halt in `reach-orchestrator.md:88-95`), while LOOP halts on the same class of gate. P1 merged pre-ratification (d10fbebe, bb8247ab, contract flip 006c6834). Violated no REACH gate — but the two harnesses hold opposite ratification postures. Worth a ruling on which is doctrine.

**5. RSI code blockers (real engineering + human gate each).**
- A1: `command_fn` never wired, `handlers.py:1625`.
- A3: `evolve_to_charmeleon` unreachable automatically — caller `handlers_memory.py:263`, dry_run defaults TRUE at :252. (Caveat: registry cites `evolution.py:217`, which is now `evolution.py.deprecated` — stale path, right number.)

**6. Flywheel ratification flips — deliberate session, none merge-urgent.**
Candidate `ratified:false`: U.2, U.3, U.4, C.0, S.0, R.0, RETINA.M3-worker-hardening. Note: `C.3/C.4/C.10` "blocked until W.4 merges" is stale — W.4 merged 2026-07-16; these are simply unstarted. U.1/U.5 read "building" (the memory note "merged" referred to H22 variants).

**7. Branch prune.**
`rope/beacon` 20 ahead (stale since Aug 3), `rope/gate-a` 3 ahead / 391 behind, 14 other unmerged locals + `wcrux-scratch` worktree. Keep/drop decisions, lowest urgency.

---

## Stale records to correct (memory + boards)

| Record | Live truth |
|---|---|
| Memory: W5-MEASURES leg open, measures.py absent | `python/synapse/validation/measures.py` exists on master (31de38b8); harness-side leg record gone — reconcile, don't just flip |
| Memory: websocket.py:471 cancel unreachable | Fixed — cancel-aware recv loop `websocket.py:93-103` + committed test |
| Memory: "U.1+U.5 merged" | Queue says "building"; merged = H22 variants |
| Memory: RSI "next = C ratification" | C is closed (blocked_at=None, L0-L4 proven) |
| REACH base_version 5.52.0 | Two releases stale (master 5.55.0); loop STATE pinned at 5.54.0 (in hardening list) |

## Exposure note

7 untracked entries (`docs/REACH_BLUEPRINT.md`, `harness/reach/`, `harness/hardening/`, `docs/harness/`, rope L3-5 card, reach workflow+agent). Origin is a **public** GitHub repo; Backup-Branches autopushes feature branches while an orchestrator runs. Untracked files don't move until committed — the risk is "one commit + any orchestrated run," not the current state. REACH predates LOOP (grounded 8-18 @ v5.52.0 vs 8-19 @ v5.54.0) and is still open.

## Open substrate installs (LOOP v01+ — human gates, not code)

v01 SafetyPort/SALUS (absent, spec-grounded) → v02 PG-DRM/Hanish → v03 StagePort/Octavius → v04/v05. Chain-gated; v01 is the head.

---

*Agents: mapper (Explore) + assayer-of-fresh (Explore). Challenge round: assayer conceded 4 points (ENG stale — a stale row inside its own T1; U.1/U.5 "building"; RSI C closed; LOOP hedge), found 4 mapper misses (merge-before-ratify inversion, REACH seniority, docs/harness orphan, public-repo exposure) + 2 citation errors (A3 stale filename evolution.py.deprecated; needs_joe count 10→11). Mapper narrowed assayer's T1 "contradiction" to cross-harness posture drift and refuted rope "abandoned" (runner alive Aug-06, needs_review = review queue). Assayer hit a 429 budget cap after delivering — report complete first.*
