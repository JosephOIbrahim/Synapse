# W6-FCRX — flow crucible verdict

> **Leg:** W6-FCRX (wave 6, flow 4/4) · **Band:** TRUTH · **Verdict:** `green_with_findings`
> **Attack lens (SPEC house rule):** laundered personas · speculative polish. CRX0 (commit-before-receipt) + W5H (receipt-is-closing-commit) carried.
> **Seat:** hython **22.0.400** / Python 3.13.10 / PySide6 offscreen, live user prefs (`HOUDINI_USER_PREF_DIR=…/houdini22.0`) — the W5-PARITY/W5-SEAT recipe. SYNAPSE loads from the **main tree** (`C:/Users/User/SYNAPSE/python/synapse`, master `8e278b65`).
> **Deps re-verified first-hand:** W6-JRNY (`10d3746f`) · W6-FLOWRIG (`9a78ad30`) · W6-FLOWFIX (`2880bace`). None merged (Joe word per leg); each read from its own branch/worktree.

Flow = measured usability. The map, the rig, and the fixes were re-executed first-hand, not read. Every number below traces to a committed evidence file under `harness/notes/receipts/w6-fcrx-evidence/`.

---

## Verdict at a glance

| Target | What it demanded | Verdict | Evidence anchor |
|---|---|---|---|
| **1 · journey audit** | every USER-FLOW-MAP step traced to its evidence anchor first-hand; unanchored → fails | **PASS** — 30/30 anchored, **0 laundered** (+3 bounded map-accuracy nits F1–F3) | this doc §1 + independent crucible pass |
| **2 · re-run the rig** | own hython stdout; diff my `flow_results.json` vs FLOWRIG; divergence enumerated | **PASS** — byte-identical (timing excluded), **0 divergence** | `evidence/rig_rerun_*` |
| **3 · fix audit** | revert-simulate every FLOWFIX row; a green that never reds is a fake pin | **PASS** — both rows real pins (green↔red under revert) | `evidence/revert_sim_{green_flowfix,red_master}.json` |
| **4 · adversarial journeys** | garbage-mid-build · panel-close-mid-journey (P0.3) · rapid mode-switch — session survives all three, first-hand | **PASS** — **3/3 SURVIVED** | `evidence/adversarial_*` |
| **5 · mandate table** | binary per leg incl. bus RELEASE; token-discipline spot-check | **PASS** (with findings) | this doc §5 |
| **6 · verdict/receipt/flag** | verdict + `W6-FCRX.json` as own closing commit; drop landed flag | **done** | this commit + closing commit + `harness/notes/h22/w6f-landed.flag` |

**Bottom line:** the map is honestly anchored (no invented personas), the rig is honest and reproducible, both shipped fixes are genuine pins (not tautologies), and three unrun adversarial journeys survive first-hand. Findings are process/accuracy nits and gui-only UNKNOWNs — none is a correctness failure. **`green_with_findings`.**

---

## 1 · Journey audit — every step traced first-hand

The USER-FLOW-MAP declares **6 journeys · 30 steps · 30 predicates · 0 unanchored** (26 headless-direct + 4 headless-proxy). I dereferenced every load-bearing friction anchor against committed source. All hold:

| Anchor class | Cited | First-hand check | Result |
|---|---|---|---|
| Launcher icon ref (J1.1) | `synapse.shelf:13` `icon="SYNAPSE_synapse"` | line 13 of the shipped shelf | ✓ exact |
| Undo-group literals (J1.4/J2.2/J2.3) | `synapse_node_create` / `_connect` / `synapse_set_parm` | `handlers_node.py:66`, `:174`; `handlers.py:1145` | ✓ all three literals live |
| pypanel help (J1.2/J3.2/J5.4) | onCreateInterface except; `setReadOnly(True)`+`traceback.format_exc()`; `"/" command palette` + "115 built-in tools" | `synapse_panel.pypanel:41/55/56/75` | ✓ exact (help literally says "browse the 115 built-in tools") |
| Chat leading (J1.3) | `chat_display.py::_apply_leading` | `chat_display.py:401` + `tokens.py::chat_leading_px:448` | ✓ |
| Pill wiring (J4.1) | `pill.clicked → _select_profile` | `synapse_panel.py:1026` | ✓ |
| Clipboard (J5.3) | `_copy_to_clipboard` PySide6-first | `synapse_shelf.py:19/28/31`; gate `checks.py:1989` | ✓ |
| Compositor friction (J4.3/J4.4) | `_repolish_tree` qtpy+break; `_apply_spec` one-way collapse | `compositor.py` (master blob `73446271`) | ✓ both defects present (see §3) |
| Freeze beat (J6.4) | `RUNTIME_BEAT_SOURCE` under `server/` | `runtime_beat.py:4` | ✓ |
| Observation-doc line map | obs1=6-9, obs3=11, obs5=14, obs6=21-22, obs7=23-25 | `panel-observations-2026-08-16.md` (committed, blob `13d11f41`) | ✓ line map accurate |
| Receipt anchors | W5-ROPE/W5-PANEL/W5-LIFE/W5-SHELF/W5-UNDO | `harness/notes/receipts/*.json` | ✓ all five present |

**Finding F1 — J1.1 today-state stale, not laundered (corroborates FLOWRIG).** J1.1's annotation "today: FAIL — absent" is **stale**: `git ls-tree HEAD houdini/config/Icons/SYNAPSE_synapse.png` returns blob `23149fd8` — the icon is **PRESENT**. The independent crucible pass sharpened this: the blob is present not only at master HEAD but at the map's **own** commit `10d3746f` (added by ancestor `2dd6bab6`, "commit SYNAPSE_synapse.png panel-open icon") — so the annotation was already false in the author's own tree, not mere drift against a moved master. The *anchor* (`shelf:13`) is correct; only the current-state claim is wrong. The rig measured J1.1 **PASS** and threaded the divergence back to JRNY. Not a laundered persona.

**Finding F2 — J5.1 inline count literal "= 6 PNGs" stale (map accuracy, no verdict change).** The J5.1 parenthetical `git ls-tree HEAD houdini/config/Icons/ = 6 PNGs` is stale by the **same** `2dd6bab6` regression as F1: the Icons dir holds **7** PNGs (six action icons + the launcher `SYNAPSE_synapse.png`) at both master HEAD and the map commit `10d3746f`. The step's *intent* — six distinct committed action icons — holds, and the rig's J5.1 measurement is correct because it checks the **six named** action icons (`SYNAPSE_{project_setup,inspect_selection,inspect_scene,last_result,health_check,generate_docs}.png`), not a bare directory count. Only the map's inline predicate wording would mis-fire. Fix: change the inline check to a name-scoped count over the six, not a bare `ls-tree … = 6`.

**Finding F3 — J4.2 cites drifted line numbers (map accuracy, cosmetic).** The map cites `_select_profile:499 → _recompose:520 → compose:566`; live master is `_select_profile:510 → _recompose:539 → compose():577` (the cited lines were copied verbatim from `W5-ROPE.json` at an older product head and have since drifted). The named functions all exist and `test_rope_switcher_wires_profile.py` + W5-ROPE acc1 support the predicate, so this is not laundered — but the map drift-corrected J4.1 (`:1015→:1026`) and inconsistently left J4.2 uncorrected. Fix: refresh to 510/539/577 or drop to function-name anchors per the map's own convention.

**Laundered-persona count: 0/30.** Every step's friction is anchored to observed (live-seat log) or coded (committed source/receipt) evidence. This is a first-hand trace by this leg (target 1 "yourself"), **independently CONFIRMED** by a second read-only, no-inheritance crucible pass over the same 30 anchors — which reproduced the three load-bearing undo-group literals verbatim, all 7 observation-doc line-map entries, all 5 receipt files, and all 6 pinning tests, and found **no misquote, no wrong-file anchor, and no nonexistent-line anchor**. Its only additions are F1/F2/F3 above — bounded map-accuracy nits, none of which laundered a step. Reconciliation detail in §7.

---

## 2 · Rig re-run — byte-identical, zero divergence

Ran a **copy** of FLOWRIG's `probe_flow.py` under the seat recipe (copy so `flow_results.json` lands in my scratch, never overwriting the flowrig worktree's committed file). My own hython banner: `repo=C:/Users/User/SYNAPSE product_head=8e278b65 hou.undos.areEnabled()=True`.

```
# SUMMARY  predicates=30  PASS=28  FAIL=2  UNKNOWN=0
# expected-red confirmed (friction): ['J4.3', 'J4.4']
# divergences from map: ['J1.1']
```

Semantic diff of my `flow_results.json` vs FLOWRIG's committed one (excluding `wall_latency_ms` / `panel_drive_ms`): **every step's verdict and measure is identical.** `product_head`, `repo_root`, `predicate_counts`, `expected_red_confirmed` all MATCH. **Divergence enumerated: none.** The rig is deterministic (LLM stage bypassed by construction) and honest — it produced 2 REDs, so it is not a rubber-stamp.

---

## 3 · Fix audit — both FLOWFIX rows are real pins

FLOWFIX's two rows are J4.3 (`_repolish_tree`) and J4.4 (`_apply_spec`), both in `compositor.py`. Revert-simulation ran FLOWRIG's exact predicate logic against two real python-roots:

| Row | post-fix ref (flowfix `/python`) | pre-fix ref (main tree = master `/python`) | Real pin? |
|---|---|---|---|
| **J4.3** | **PASS** — no qtpy, no break, live-reach **5/5**, returns 5 | **FAIL** — qtpy import + premature break, live-reach **0/5**, returns None | ✓ reds under revert |
| **J4.4** | **PASS** — restore branch present, uncollapse → **16777215** | **FAIL** — one-way, uncollapse stays **0** | ✓ reds under revert |

Both `all_as_expected=true` **and** `signature_attribution_ok=true` (red shows the defect signatures, green shows the fix signatures) — so the flip is attributable to the code change, not to the harness. **A green that never reds under revert would be a fake pin; both reds return under revert to master.** The shipped regression fence `tests/panel/test_flowfix_j4.py` passes **5/5** first-hand on the fixed tree.

**Speculative-polish check (attack lens):** the FLOWFIX product diff touches **only** `compositor.py` (34 insertions / 12 deletions) — exactly the two measured reds, no drive-by polish. "Wrapping not rebuilding" holds; the cap (2 reds only) is respected.

---

## 4 · Adversarial journeys the builders did not run — 3/3 survive

Driven first-hand against the LIVE offscreen `SynapsePanel` under the seat recipe (`evidence/adversarial_*`):

| # | Journey | Survival evidence | Verdict |
|---|---|---|---|
| **A1** | garbage prompt **mid-build** | good build *before* lands; garbage tool errors clean (`Unknown tool: …`, no traceback); provider fault reads human ("We hit a snag"); good build *after* lands (session not wedged); post-fault liveness OK | **SURVIVED** |
| **A2** | panel close **mid-journey** (P0.3 interplay) | `closeEvent` no-raise; **freeze beat SURVIVES the close** (`is_beating()` stays True — P0.3 fix holds, protection not torn down); `detach_panel` recorded (`detach_count≥1`, `panel_attached=False`); in-flight build finished; conversation persisted via `save_conversation` | **SURVIVED** |
| **A3** | rapid mode-switch **during execution** | 12 rapid `_select_profile` switches while a build is in flight → 0 exceptions; in-flight build still lands (recompose rides the worker across untouched); final density consistent (expert→standard); post-switch liveness OK | **SURVIVED** |

P0.3 grounded: the H22-readiness finding "freeze protection owned by the panel widget," fixed by W5-LIFE moving the beat to a process-lifetime owner (`server/runtime_beat.py`); A2 exercises that contract, not reads it.

---

## 5 · Mandate table (binary per leg)

| Leg | receipt present | receipt == branch HEAD (closing commit) | bus RELEASE posted | self-reported acceptance | FCRX independent re-verification |
|---|:--:|:--:|:--:|:--:|---|
| **W6-JRNY** (`6270bce4`) | ✓ | ✓ | ✓ `docs/USER-FLOW-MAP.md` | 2/2 pass | ✓ 30/30 anchored, 0 laundered; J1.1 stale flagged |
| **W6-FLOWRIG** (`9261e7ff`) | ✓ | ✓ | ✓ `harness/probes/flow/` | 2/2 pass | ✓ re-run byte-identical 28/2/0; see F2 |
| **W6-FLOWFIX** (`24d45578`) | ✓ | ✓ | **✗ NONE** (see F3) | 2/2 pass | ✓ revert-sim proves both pins; fence 5/5 |

**Token-discipline spot-check (receipts cite anchors, not dumps):** PASS. All three dep receipts cite `file:line`, blob shas, receipt paths, and commit shas rather than pasting content (e.g. FLOWRIG finding anchors on blob `23149fd8`; FLOWFIX cites `compositor._repolish_tree`/`_apply_spec`). This verdict follows the same discipline — the evidence bundle holds the raw output; the prose cites it.

**Finding F4 — FLOWRIG over-claim (accuracy nit, no verdict change).** FLOWRIG's receipt states "all four headless-proxy predicates were reachable — none had to be weakened to a source-presence assertion." That is inaccurate for **J4.3**, whose `evidence_method` is `source-pin` (a static grep of the two defects), not a behavioral reach-probe. J1.5/J2.4/J6.5 are genuinely behavioral; J4.3 is source-presence. (FLOWFIX's own probe later added the behavioral live-reach count the rig omitted.) The J4.3 verdict is correct either way; only the "none weakened" wording over-reaches.

**Finding F5 — FLOWFIX left its bus claim open.** W6-FLOWFIX posted a `claim` (`n=18cc6765`, files incl. `python/synapse/panel/compositor.py`) but **no `finding` and no `status`/RELEASE**. Its receipt IS its closing commit (`24d45578`=HEAD, so the product half is closed per W5H), but the bus half is incomplete: the W6-GATE close gate wants a bus RELEASE line, and the compositor.py claim remains open on the shared bus. Product-correct, process-incomplete. (Directly parallel to the wave-5 precedent F-PCRUX-1, where W5-PARITY's RELEASE was likewise missing.)

---

## 6 · UNKNOWNs — named, with what the Joe seat must observe

Per the leg constitution (unobtainable → UNKNOWN, never zero, never an estimate). These are gui-only truths neither the rig nor this crucible can reach headless; each names the observation only a live Joe seat can close:

| ID | Headless half (measured) | `gui_required → UNKNOWN` — Joe seat must observe |
|---|---|---|
| **J4.3** (post-fix) | code now reaches every descendant (5/5, first-hand) | do CURIOUS/EXPERT/ML now render **visibly different densities** (airy/standard/tight) at the seat? |
| **J4.4** (post-fix) | collapse is two-way (uncollapse → 16777215) | does a folded readout **visibly re-expand** on mode switch-back? (note: those readouts are currently `setVisible(False)`, so may be unobservable even after the fix) |
| **J1.5** | per-task usage fold proven (150 == Σ; None→UNKNOWN) | does the **Token tab live counter** render per-task spend? |
| **J2.4** | exception-path group closes, partial survives | does **one artist Ctrl+Z** reverse a whole completed rig? |
| **J5.1** | 6 distinct committed icon blobs | do the six shelf icons **render** distinctly? |
| **J6.5** | restored `self._messages` round-trips | does the chat transcript **visibly repaint** on reopen? |
| **J1.spine** | node built through the panel's ToolExecutor | LLM narration half (provider stage bypassed by construction) |
| **J5.4 advisory** | help says 115, live registry `TOOL_DEFS==129` | doc-fix flag: reconcile the "115 built-in tools" help string to 129 |

---

## 7 · Independent adversarial cross-check — result

A second read-only crucible pass independently dereferenced all 30 anchors against committed git blobs with **no inheritance** of §1's conclusions. Its verdict:

- **"0 laundered / 30": CONFIRMED.** The strict laundering test (nonexistent line / misquote / wrong file / unsupported seam-predicate) failed to catch a single step. It reproduced verbatim: the three load-bearing undo-group literals (`synapse_node_create`@`handlers_node.py:66`, `synapse_node_connect`@`:174`, `synapse_set_parm`@`handlers.py:1145`), all 7 observation-doc line-map entries, all 5 receipt files' attributed acceptance/findings/spawns, and all 6 pinning test files.
- **J1.1 "today: FAIL/absent": REFUTED as stale** — icon blob `23149fd8` present at master HEAD **and** at the map's own commit `10d3746f` (F1).
- **Three bounded map-accuracy weaknesses**, no showstopper: F1 (J1.1 stale) + F2 (J5.1 inline "6 PNGs" stale, same `2dd6bab6` root cause) + F3 (J4.2 line-drift `499/520/566`→`510/539/577`). The other three "today: FAIL" annotations (J4.3, J4.4, J5.4-advisory) were independently re-verified **ACCURATE** against master.

The independent pass strengthened the first-hand trace and added F2/F3; it broke nothing. These three are map-authoring corrections for W6-JRNY to fold before any publish — filed `for_ruling` in the closing receipt, not blockers.

---

## Evidence bundle (`harness/notes/receipts/w6-fcrx-evidence/`)

- `rig_rerun_hython_stdout.txt` · `rig_rerun_flow_results.json` — target 2 first-hand receipt
- `revert_sim_green_flowfix.json` · `revert_sim_red_master.json` — target 3 revert-simulation, both sides
- `adversarial_hython_stdout.txt` · `adversarial_results.json` — target 4, 3/3 survived

Every number in this verdict traces to one of these files or to a `file:line` / blob-sha / receipt anchor. No anchor, no claim.
