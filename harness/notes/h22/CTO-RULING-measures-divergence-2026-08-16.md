# CTO RULING — W5-MEASURES charter divergence — 2026-08-16

**Author:** Orchestrator (CTO delegation: Joe's word "you do this using best practices as CTO").
**Scope:** branch `wave5/measures`. **Binding on:** the leg's close/receipt/merge decision.
**Law under test:** FP2 — *never assert what you haven't measured.* This ruling applies FP2 to
the leg itself: a green receipt over unbuilt acceptance criteria would be the exact
unmeasured-as-measured lie the wave exists to kill.

---

## Finding (evidence-anchored, Law 2)

The branch delivered the **unmeasured honesty audit**, not the leg's chartered deliverable.

| Claim | Evidence |
|---|---|
| Live charter is cook-verify contracts | `harness/autorevise/waves/wave5l.live.json` → leg `W5-MEASURES.name` = "substrate P2: cook-verify contracts…"; full targets in `harness/autorevise/prompts/W5-MEASURES.md` |
| Charter targets: `validation/measures.py` (5 output kinds + UNKNOWN conds), explosion detector, tier ladder on `tool_exposure`, golden harness under `rulebook/goldens/` | prompt `targets[1..5]`; `touches` = `validation/` + `rulebook/` + `tests/` |
| `validation/measures.py` exists **nowhere** | `git ls-files` on branch AND master → absent |
| Branch touched **zero** of `validation/` or `rulebook/` | `git diff --stat master...HEAD -- python/synapse/validation/ rulebook/` → empty |
| 0 of 3 acceptance predicates met | prompt `acceptance[]` (measures module / explosion detector / tier field) — none built |
| A crucible criterion was violated | prompt `crucible_criteria[3]` = "no overlap with W5-PANEL's `python/synapse/panel/`"; branch commit `9bd298c4` edits `panel/health_infographic.py` |
| Delivered instead | Bug A/B + siblings in `server/live_metrics.py`, `metrics.py`, `dashboard.py`, `panel/health_infographic.py` (commits `5320da97`, `9bd298c4`, `e544534b`, `eeebca16`, `a1e3fa03`, `d44b750f`) |
| Prior session's own framing | `harness/notes/h22/AUDIT-2026-08-16-unmeasured.md` calls the work "Layer-6's deferred item 3", not the cook-verify charter |

## Ruling

1. **The audit work is KEEP.** Green (546 tests), honest, valuable, advances FP2. Not deleted,
   not discounted. It stays banked + pushed on `wave5/measures`.
2. **It is NOT the W5-MEASURES charter deliverable.** By the prior session's own note it is
   Layer-6 / metrics-honesty lineage. Correct attribution — **not** goalpost-moving.
3. **W5-MEASURES (cook-verify charter) is UNMET → stays OPEN.** Its honest board state is
   **DIVERGED**, not done. It must **NOT** close with a green receipt: 0/3 acceptance predicates
   are built, so any "acceptance pass" would be a fabricated claim (FP2 violation, and the exact
   laundered-receipt failure the harness already caught this wave — HCRUX F2).
4. **No receipt, no merge, no state-flip, no drop.json — by the orchestrator/CTO agent.** The
   leg constitution reserves push/merge/tag/state-flips as *human words, per act*; a live
   orchestrator (`orchestrate.ps1 wave5l.live.json`, PID 70408; `orch_W5-MEASURES.ps1`, PID 35232)
   owns the leg state machine, so editing live manifest state or writing `W5-MEASURES.json` would
   race it. Deliberately withheld — this doc is the artifact instead.

## Forward path (human / orchestrator words — not mine)

- **(a) Re-attribute the audit** as its own deliverable (spawn `W5-MEASURES-AUDIT`, or fold into
  the honesty/Layer-6 layer) so it can promote on its own merits with an HONEST receipt scoped to
  "metrics-honesty audit" — never cook-verify.
- **(b) Keep W5-MEASURES open** for the real cook-verify build (`validation/measures.py` + explosion
  detector + tier ladder + `rulebook/goldens/` hython runner). **Route it through the orchestrator's
  own worker**, not a second session in this worktree — building it from here risks the dual-launch
  collision (same class as `harness-dual-launch-collision`).
- **(c) If the charter is being retired/rescoped**, do it explicitly in `wave5l.live.json` (a human
  word), never by a silent receipt.

## Why not "just build it now"

The cook-verify charter is a full leg's worth of substrate (5 targets, a hython golden runner much
of which is `gui_required` → legitimately UNKNOWN headless). More decisively: the live
`orch_W5-MEASURES` may already have a worker on this leg; a second builder in the same worktree is
the collision this house has been burned by before. Best practice is to record the divergence and
let the orchestrator route the build cleanly — not to gamble a public-repo collision on it.

*No `harness/state/drop.json` touched. No `ratified` flipped. No merge/push/tag performed.*
