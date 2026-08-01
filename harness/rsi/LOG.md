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

| 2026-08-01 | RL-2 A1 | SIGNAL fix landed for `A1`. All three defects re-confirmed at HEAD `c574d49` before touching anything, then fixed together: (1) `success` made a REQUIRED parameter of `_record_metric` (`router.py:937-962`) and all nine call sites pass a real outcome; (2) `_try_tier0` computes `all(r.success for r in responses)` (`router.py:557`) instead of hardcoding `success=True` — `_try_tier2` carried the identical defect (`router.py:713`) and was fixed in the same commit; (3) the `no_tier_matched` fallback records a failure under the reserved `NO_TIER_KEY="no_tier"` (`router.py:386`) where it previously recorded nothing. Safety fact re-verified BEFORE landing: `TierThresholds.get()` has zero non-test callers, so honest recording changes no routing decision today. Pinned by `tests/test_routing.py::TestRewardSignalHonesty` (10 tests reading `_epoch._current_epoch.outcomes` — what the adapter was TOLD, not what `RoutingResult` claimed). Mutation-verified: 3 mutants, each killed (tier-0 hardcode -> 4 failed; fallback recording deleted -> 2 failed; default restored + one call site silenced -> 6 failed). `verify.py` **9 PASS / 0 FAIL**, P4 flipped to "live signal now carries an outcome and registry agrees — 9/9 call sites". `A1` L0 -> **L1**, blocked_at L1 -> **L2**. |
| 2026-08-01 | RL-2 CATCH | One existing test *asserted the defect*: `tests/test_routing.py::TestTieredRouter::test_tier0_command_fn_error` asserted `result.success` on the reasoning "routing succeeded even if execution failed". That comment is exactly how the tier-0 reward signal became a constant. Rewritten to the new truth. A green suite was pinning the bug — the suite passing is not the same as the suite being right. |
| 2026-08-01 | RL-2 A1 L2 | New `A1` blocker is NOT a code defect. `synapse_live_metrics` against a live bridge (`synapse_ping` -> `pong=true`, protocol 4.0.0) returned `routing.total_requests=0`, `tier_counts=[]`. The router has never routed a production request. An honest signal nothing has exercised is honest and unread; L2 needs traffic, not another patch. |
| 2026-08-01 | RELAY | Execution arm built: `.claude/workflows/rsi-closure.js` (3 phases, ~7/5/4 agents, args-as-string parsed defensively) + `rsi-closure-orchestrator` agent + `RELAY.md` + operator card. No new predicates, no new bar (R140). File-overlap check for parallel SIGNAL worktrees: A1→routing/router.py, F→shared/router.py only, E→forge/engine/ — disjoint, verified by grep. |

---

## Standing state at frame

- **Registry honesty:** 9 PASS / 0 FAIL.
- **Closure:** 0 of 9 loops beneficial. 0 of 9 reach L3 CONSUMED. Highest rung anywhere is `A3` at **L2**.
  `A1` reached **L1** on 2026-08-01; that moved no closure number.
- **L1 failures:** 2 open (`F` and `E`, carried, pending `RL-1`). `A1` **CLOSED** by `RL-2`.
- **Next action:** `RL-1 RECONCILE` — re-derive `R/O/S/F/E/C` at HEAD under this ladder. Blocked on SPEC
  ratification.
- **Open human gates:** SPEC ratification · any L3→L4 advance · signal-semantics change (`RL-2`) ·
  `A2` wire-or-delete · `C` substrate call · push/merge.
