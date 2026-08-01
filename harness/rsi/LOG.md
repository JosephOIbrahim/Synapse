# LOG — the RSI closure harness

*Run log. One row per attempt. Reads actual state; never narrates. `?` where a check could not be made.*

| date | phase | what happened |
|---|---|---|
| 2026-08-01 | FRAME | Harness framed. SPEC + PLAN + REGISTRY + verify.py + CHAMPION + LEDGER + DEADENDS written. **SPEC AWAITING RATIFICATION.** |
| 2026-08-01 | VERIFY | `harness/rsi/verify.py` first run: **7 PASS / 2 FAIL**. P1 failed naming 3 unregistered surfaces; P4 failed on a parser defect in this file (the `def` line at `router.py:917` was counted as a call site because `"    def ".strip().startswith("def ")` is False). |
| 2026-08-01 | FIX | P4 parser corrected to `^\s*(async\s+)?def\s+$`. Registry gained `shared/conductor_advisor.py` (O), `shared/constants.py` (F), `shared/evolution.py` (O). Re-run: **9 PASS / 0 FAIL / 0 PENDING**. |
| 2026-08-01 | CROSS-CHECK | P4's live grep independently re-derived the eight `_record_metric` call sites named by `harness/notes/RSI_SURFACE_AUDIT.md` — `router.py` :285, :448, :515, :554, :584, :706, :742, :819 — with no shared source. Audit Q4 finding **VERIFIED-AT-HEAD** at `f427320`. |
| 2026-08-01 | BOARD | `harness/progress.py` built (discovers `harness/*/verify.py`). Verified against CLEAR: **5/8 clear, 3 open**, matching CLEAR's own logged run. This harness auto-appeared with no edit to the tool. |

| 2026-08-01 | RATIFY | **SPEC RATIFIED** (human sanction, CTO authority granted). Recorded explicitly that ratification opens the lines but promotes no rung — permission cannot manufacture proof. |
| 2026-08-01 | GATE-FIX | Symbol table regenerated against the live build: was stamped `22.0.368`, running `22.0.397`. New table `version=22.0.397 symbols=35908 blake2b=2b6d06030628`; sanity checks green (`hou.LopNode`, `hou.SopNode`, `pdg.EventType`, `pxr.Usd`, `pxr.Sdf`). **The phantom-API gate was DOWN and is now up.** |
| 2026-08-01 | RL-1 | RECONCILE run for all six June lines. `R` → L0+L1 (blocked L2). `O` → L0 (blocked L1). `S` → L0 (blocked L1; operative L2). `E` → L0 (blocked L1, confirmed exact lines). `F`/`C` unchanged. verify.py re-run: **9 PASS / 0 FAIL**, 10 proven rungs all carrying evidence. |
| 2026-08-01 | RL-1 CATCH | `tests/rsi/eval_line_r_closure.py` collects **ZERO** tests under pytest — its `eval_` prefix matches neither `test_*.py` nor `*_test.py`. Run directly (`python tests/rsi/eval_line_r_closure.py`) it returns **OVERALL: PASS**. A pytest-based existence check would have read live evidence as absent. |

| 2026-08-01 | RL-2 `F` CONFIRM | Claimed defect **CONFIRMED at HEAD** `f427320` before any edit. `shared/router.py` `MOERouter.route(self, features)` takes no outcome argument; the promotion block gated on `self._fingerprint_counts[fp] >= FAST_PATH_PROMOTION_THRESHOLD` alone. Live-path cross-check: `grep -c "_session_fast_paths" python/synapse/routing/router.py` → `0`; `grep -n "promot" …` → exit `1`. **TieredRouter has no promotion at all** — the fix is panel-side only, as believed. Second finding not in the brief: `RoutingLog.apply_learned_fast_paths` (`panel/routing_log.py:100-117`) writes the same table via `learn_fast_path()` off its own **frequency** list — the identical defect through a side door. |
| 2026-08-01 | RL-2 `F` FIX | R18 landed. `record_outcome(fingerprint, success)` + failure veto on **both** writers; `learn_fast_path()` returns `bool`; entries carry `outcome_confirmed` at index 3; a recorded failure also **evicts** an already-promoted entry. `_session_fast_paths` left in-memory — L4 not attempted, per the loop's own hazard note. **Negative control:** `git checkout HEAD -- shared/router.py` then `pytest tests/test_router_internals.py::TestOutcomeVetoedPromotion` → **`8 failed`**; restored → **`30 passed`** for the whole file. Suite (three runs, because the first two disagreed): baseline at HEAD **4 failed / 5341 passed**; after **5 failed / 5348 passed** (×2, reproducible). The extra failure is `test_m3_logs_doctor.py::test_dump_failure_never_blocks_escalation` — a `time.sleep(0.6)` watchdog race that **passes isolated** (`18 passed`) and, decisively, **also fails at HEAD with this lane's work `git stash`ed: 5 failed / 5340 passed**. Pre-existing full-suite timing flake, not this change; `5340 + 8 new tests = 5348` accounts for every passing test. Floor held: identical failure set. Consumers: `-k "router or routing or tool_filter or conductor or advisor or pass7 or pass8 or panel"` → **619 passed, 69 skipped**. |
| 2026-08-01 | RL-2 `F` VERIFY | Registry updated in the same commit: `F` `rungs_proven` `[] → ["L0","L1"]`, `blocked_at` `L1 → L2`, `verification` `unverified → verified-at-head`, `panel/routing_log.py` added as a surface. `python harness/rsi/verify.py` → **9 PASS / 0 FAIL / 0 PENDING**, 12 proven rungs. **P4 line (unchanged, and correctly so — P4 greps A1's `routing/router.py`, which this lane did not touch):** `PASS — structural rule holds; live signal still constant and registry agrees — all 8 call sites pass only (tier, latency) — success defaults True (lines 285, 448, 515, 554, 584, 706, 742, 819)`. |
| 2026-08-01 | RL-2 `F` CAVEAT | The honest limit of this rung: **nothing calls `record_outcome()`.** Every promotion written today is stamped `outcome_confirmed=False`. Further, the only live caller of `MOERouter.route()` is `panel/tool_filter.py:245`, and **no production code calls `filter_tools()`** — only `classify_tool` is imported (`command_palette.py:69`, `tool_palette.py:28`). So loop F's promotion path is currently **dormant**, not merely unfed. That is the L2 work, and it is why `blocked_at` is `L2` and not a closure claim. |
| 2026-08-01 | RELAY | Execution arm built: `.claude/workflows/rsi-closure.js` (3 phases, ~7/5/4 agents, args-as-string parsed defensively) + `rsi-closure-orchestrator` agent + `RELAY.md` + operator card. No new predicates, no new bar (R140). File-overlap check for parallel SIGNAL worktrees: A1→routing/router.py, F→shared/router.py only, E→forge/engine/ — disjoint, verified by grep. |

---

## Standing state at frame

- **Registry honesty:** 9 PASS / 0 FAIL.
- **Closure:** 0 of 9 loops beneficial. 0 of 9 reach L3 CONSUMED. Highest rung anywhere is `A3` at **L2**.
- **L1 failures:** 3 at frame (`A1` verified at HEAD; `F` and `E` carried). **`F` closed by `RL-2` on
  2026-08-01** — confirmed at HEAD first, then fixed (R18). 2 remain: `A1`, `E`.
- **Next action:** `RL-1 RECONCILE` — re-derive `R/O/S/F/E/C` at HEAD under this ladder. Blocked on SPEC
  ratification.
- **Open human gates:** SPEC ratification · any L3→L4 advance · signal-semantics change (`RL-2`) ·
  `A2` wire-or-delete · `C` substrate call · push/merge.
