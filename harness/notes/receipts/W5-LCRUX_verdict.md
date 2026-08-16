# W5-LCRUX — lifecycle-wave crucible verdict board

**Date:** 2026-08-16 · **Branch:** `wave5/lcrux` · **Base:** `df8c9ef3` (master tip) · **Mode:** A (headless) + hython 22.0.400 offscreen for Qt slices
**Gates:** W5-LIFE (`8d97f993`), W5-PANEL (`d657dd45`), W5-SHELF (`10188cec`), W5-ROPE (`661ad369`)
**Nothing inherited** — every verdict below rests on a re-execution or a git interrogation performed by this leg, not on the builder receipts.

> **Merge remains Joe's word, per leg.** This board GATES; it does not merge. Overall: **green_with_findings** — all four legs independently re-verified PASS-with-findings; zero refutations, zero laundered UNKNOWNs, zero showstoppers. Two standing merge conditions (F1, F2) named below.

---

## Per-leg verdict summary

| Leg | Crucible verdict | Predicates (independent) | Re-executed first-hand | Notes |
|---|---|---|---|---|
| **W5-LIFE** | PASS-with-findings | pass / pass / pass | R.2 CLI PASS + 29/29 scoped tests | gui session parts honestly UNKNOWN (spawned); hollow-marker attack refuted |
| **W5-PANEL** | PASS-with-findings | **UNKNOWN** / pass / pass | 20 headless + 5 (chat-leading) + 14 (token-tab) under hython 22.0.400 | P1 font-floor honestly UNKNOWN (live fix unshipped); P2/P3 hython-confirmed |
| **W5-SHELF** | PASS-with-findings | pass / pass / pass | R.7 CLI PASS + 18/18 tests | 6 distinct icon blobs verified; icon GUI-render honestly UNKNOWN (spawned) |
| **W5-ROPE** | PASS-with-findings | pass / pass / pass | 101/101 rope tests + sha256 state | tautology attack refuted (rides real compositor); density-repaint bug spawned, not hidden |

---

## Target 1 — independent re-verification (none inherited)

### The two mandated `checks.py` re-runs (run by this leg, first-hand)
- **`runtime_owns_heartbeat` (task R.2, W5-LIFE worktree):** `ok: true`, task verdict **PASS**, `guardrail_violations: []`, ratchet holds (6464p/0f vs base 6389/0). Invocation: `checks.py --task R.2 --worktree <w5-life> --mode A`.
- **`shelf_current` (task R.7, W5-SHELF worktree):** `ok: true`, task verdict **PASS**, `guardrail_violations: []`, ratchet holds. Invocation: `checks.py --task R.7 --worktree <w5-shelf> --mode A`.

### Per-leg adversarial re-execution (4 crucible agents + hython closes)
- **W5-LIFE** — all 3 predicates `pass`. Hollow-marker attack **REFUTED**: `server/runtime_beat.py` is a genuine parentless-QTimer → `_emit_beat` → `freeze_chain.beat()` → process-wide singleton watchdog (not a bare marker). RED/GREEN detach pair observes real `FreezeChain` escalation, not a mock. 29/29 scoped tests green (`test_w5_life_heartbeat` 8, `test_w5_life_session_survival` 10, `test_freeze_chain` 8, `test_panel_freeze_beat` 3). GUI session parts (live reconnect, `ClaudeWorker` rebind, transcript repaint) held **UNKNOWN**, spawned S1/S2/S3 — not simulated into a pass.
- **W5-PANEL** — P1 font-floor **UNKNOWN** (honest: both below-floor call sites `synapse_panel.py:1948`/`:2087` still unfixed on the peer-claimed surface; math helper real+green, 8/8). P2 chat-leading and P3 token-tab skip headless; **re-run under hython 22.0.400 offscreen → chat_leading 5/5 (incl. the 3 effect-provers: document height grows +1px/line and shrinks when stripped), token_tab 14/14 (incl. the 4 Qt end-to-end)** → both **PASS first-hand**. The receipt's hython evidence is reproduced, not inherited.
- **W5-SHELF** — all 3 `pass`. `from PySide6` sits on the real `_copy_to_clipboard` path (dead-branch attack refuted). Six **distinct** icon blobs (6 distinct sha + byte sizes 2479/2604/3756/2996/2749/3000, valid 64×64 RGBA) — "same image ×6" refuted. Tooltips are real operator sentences. 18/18 tests green. Icon GUI-render held **UNKNOWN** (F1), spawned.
- **W5-ROPE** — all 3 `pass`. **Central tautology attack FAILED**: `test_rope_switcher_wires_profile.py` rides the REAL `compositor.compose`/`resolve`/`_apply_spec` chain and real `_select_profile`/`_recompose`, faking only logic-free Qt leaves; per-profile assertions observe genuine compose propagation and can fail. 101/101 rope tests green. Ratified state byte-identical (sha256 recomputed first-hand: STATE `78193b80…`, PENDING `ac9b014d…`). The live-seat "does nothing" is honestly attributed to a separate dead `compositor._repolish_tree` and **spawned** (W5-ROPE-DENSITY-REPAINT), not hidden inside a green.

**UNKNOWNs preserved (never laundered):** PANEL font-floor live wiring; LIFE gui session reconnect/rebind/repaint; SHELF icon GUI render; ROPE density visible repaint — all gui_required or peer-blocked, all spawned by their legs.

---

## Target 2 — mandate table (binary per leg, git-interrogated)

| Leg | (a) product_head exists | (b) product precedes receipt (ancestry + commit-time) | (c) receipt is the leg's OWN closing tip commit |
|---|---|---|---|
| W5-LIFE | ✓ `8d97f993` | ✓ 10:37:36 < 10:44:08 | ✓ tip `f872bf80` adds `receipts/W5-LIFE.json` |
| W5-PANEL | ✓ `d657dd45` | ✓ 11:53:04 < 11:54:29 | ✓ tip `7c8cbec2` adds `receipts/W5-PANEL.json` |
| W5-SHELF | ✓ `10188cec` | ✓ 09:58:32 < 10:04:56 | ✓ tip `d288a1d4` adds `receipts/W5-SHELF.json` |
| W5-ROPE | ✓ `661ad369` | ✓ 09:52:02 < 09:53:32 | ✓ tip `97ceada2` adds `receipts/W5-ROPE.json` |

**All four legs PASS all three checks.** None operator-rescued — each committed its own receipt as its closing commit (the W5-DELTA rule the W5H receipt-commit-gap lesson demanded; contrast the `c7a6a08d`/`76ca94a0` operator close-passes of W5-BASE/DENSE/UNDO/CRUX). No receipt narrates a commit that never existed (W5H F2 check: clean).

---

## Target 3 — combined-state probe (scratch tree, cleaned up)

Built `wave5/lcrux-scratch` off `df8c9ef3` and **cherry-picked** all four legs' product commits (git merge is constitution-forbidden; cherry-pick is the allowed composition test).

- **The four legs do NOT compose cleanly — one expected conflict.** The SHELF pick collides with LIFE on **`tests/test_r_track.py::test_live_tree_gates_read_red_now`** (both legs promote their own gate — `runtime_owns_heartbeat` / `shelf_current` — out of the shared RED tuple; the docstring + assertion block are adjacent additions). This is the exact shared seam LIFE F5 and SHELF F2 both predicted and the bus short-hold claim anticipated. **Resolution = the deterministic union** (all three gates GREEN, both asserts kept) a human merge produces; the RED-list loop auto-merged (removals on different lines). Not a semantic conflict — a same-hunk textual collision.
- **Ratchet (solo, quiet env, after union reconciliation):** `suite_baseline` **passed 6508 (base 6389), failed 0 (base 0) — ratchet HOLDS**. `guardrail_violations: []`. `runtime_owns_heartbeat: True` on the combined tree. `provenance_not_bypassed` = unwired/warn-only (pre-existing, not a violation). → **the four legs compose with zero collateral regression.**
- **Environmental flake identified and dismissed:** concurrent runs showed 6 then 2 failures, all in `tests/test_harness_lock.py` (PID-liveness / lock-acquisition). A failure count that *changes between two runs of the same tree* is non-deterministic; **no leg touches harness-lock code**; run alone in a quiet env it is **10/10 green**. Cause: ~8 concurrent pytest processes (this leg's own parallelism). Named as the failing surface, ruled environmental.
- Scratch worktree + branch **removed** after the probe.

---

## Target 4 — panel/ overlap + bus discipline

**Per-leg `python/synapse/panel/` edits (base..product_head):**
- LIFE → `synapse_panel.py` (1 file)
- PANEL → `chat_display.py`, `claude_worker.py`, `designsystem/tokens.py`, `face_token.py`, `usage_sink.py` (5 files)
- SHELF → none · ROPE → none

**All pairwise `panel/` intersections are DISJOINT** → no two legs edited the same panel line. The claim discipline worked: PANEL explicitly avoided `synapse_panel.py` ("ROPE/LIFE hold it") and built in the small modules.

**Brief-premise correction (F4):** the target-4 premise "LIFE, PANEL, ROPE all touched `python/synapse/panel/`" is inaccurate — **ROPE touched zero `panel/` files** (test-only leg; it only *claimed* `synapse_panel.py` on the bus, never edited it).

**Bus (posted vs released):** all three panel-relevant legs POSTED claims; **no wave5 leg posted a `release`** — every claim remains open (systemic, F2). ROPE holds an open, never-released, over-broad claim on `synapse_panel.py` (a file it never edited); LIFE edited `synapse_panel.py` while nominally "BLOCKED behind W5-ROPE" — harmless in outcome (ROPE edited zero lines there) but the block was never cleared (F3).

**Only genuine cross-leg line collision anywhere:** LIFE ∩ SHELF on `tests/test_r_track.py` — not a `panel/` file; = the Target-3 conflict.

---

## Findings

- **F1 (combine-sequencing · condition-on-merge):** LIFE and SHELF do not cherry-pick clean onto a common base — `tests/test_r_track.py::test_live_tree_gates_read_red_now` collides. Resolution is the deterministic union of both gate promotions; after it the combined suite is 6508p/0f, ratchet holds. *Anchor:* `tests/test_r_track.py:604,637`; LIFE receipt F5; SHELF receipt F2; probe `wave5/lcrux-scratch`.
- **F2 (bus hygiene · systemic):** No wave5 leg posted a `release` — every claim (LIFE/PANEL/SHELF/ROPE + peers) is still open. Claim half used, release half unused. *Anchor:* `harness/autorevise/bus/wave5/bus.jsonl` (`open_claims`).
- **F3 (bus process irregularity · benign outcome):** ROPE holds an open, never-released, over-broad claim on `python/synapse/panel/synapse_panel.py` (never edited it); LIFE edited that file while "BLOCKED behind W5-ROPE." No line collision (ROPE edited zero lines there). *Anchor:* bus `W5-ROPE` 09:32:12, `W5-LIFE` amend2 09:55:07.
- **F4 (brief-premise correction):** target-4 premise mis-states ROPE — ROPE touched zero `panel/` files. *Anchor:* `git diff df8c9ef3..661ad369`.
- **F5 (gate-design weakness · LIFE · non-blocking):** `check_runtime_owns_heartbeat` (`checks.py:1842`) is grep-only for the marker strings — a hollow `# RUNTIME_BEAT_SOURCE` comment with no real beat would green it. LIFE's owner is genuine (verified), so the PASS is truthful, but the gate is not behavior-observing. *Mitigation:* a behavioral pin (arm the owner against a real `FreezeChain`; assert escalate-on-stall / no-escalate-when-beaten). *Anchor:* `harness/verify/checks.py:1842`.
- **F6 (test-strength weakness · SHELF · non-blocking):** `test_six_tools_have_distinct_icons` asserts distinctness of icon NAME attributes only, not file bytes — would miss two names sharing identical bytes. Independently closed here via `git ls-tree` (6 distinct blob shas + byte sizes). *Anchor:* `tests/test_shelf_current.py::test_six_tools_have_distinct_icons`.
- **F7 (disclosed inert test · ROPE · non-blocking):** `test_profile_pills_are_connected_to_the_select_handler` is a static source-regex pin (pattern, not runtime) — supplementary, not the acceptance backbone; disclosed in the receipt, not laundered. *Anchor:* `tests/test_rope_switcher_wires_profile.py:307`.
- **F8 (headless-blind slices closed under hython):** PANEL P2 (chat-leading effect) + P3 (Qt token-tab e2e) skip headless; re-run under hython 22.0.400 offscreen → 5/5 + 14/14 → both PASS first-hand. *Anchor:* `hython 22.0.400 -m pytest tests/panel/test_chat_leading.py` and `tests/test_token_tab_usage.py`.

---

## For ruling (Joe's word)

1. **Merge sequencing (F1):** LIFE and SHELF cannot both land on master without reconciling `tests/test_r_track.py::test_live_tree_gates_read_red_now` — the deterministic union of both gate promotions. Merge one, the second conflicts on that hunk; apply the union (or serialize + hand-edit). All other legs are pairwise clean against each other and the base.
2. **Bus release hygiene (F2/F3):** no leg released its claims; ROPE's over-broad `synapse_panel.py` claim should be released so the bus reflects final state.
3. **gui_required UNKNOWNs (all four legs):** live-seat verifications remain Joe's — LIFE reconnect/rebind/repaint, SHELF icon render, ROPE density repaint, PANEL font-floor live wiring — all already spawned by their legs.

## Spawn (crucible)

- **W5-LCRUX-S1 (class build → held for Joe):** behavioral pin for `check_runtime_owns_heartbeat` (F5) — arm the process-lifetime owner against a real `FreezeChain` and assert escalate-on-stall / no-escalate-when-beaten, so the gate observes the beat rather than a marker string.

---

*Probe artifacts (scratch, transient): combined ratchet 6508p/0f solo; harness_lock 10/10 isolated; hython chat_leading 5/5; hython token_tab 14/14. Scratch worktree `wave5/lcrux-scratch` removed after probe.*
