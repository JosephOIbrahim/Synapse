# W5-WXB — crucible shard B audit: explosion-detector goldens + tier projection

**Leg:** W5-WXB (wave5 crucible team, shard B) · **Model:** Opus 4.8
**Audited:** `wave5/measures` tip `520a10d4` (product `a6db2286`) — the cook-verify
charter delivered by the re-dispatched second agent after the divergence ruling.
**Method:** first-hand re-execution in a **detached** side worktree `_m` at the tip
SHA, Python 3.14.2, zero-`hou` (the judgement half runs on any interpreter).
**Remit:** re-run the explosion-detector golden pair + one fresh variant (A2);
audit the measurement→exposure-rung projection for extends-not-forks + honest S1
absence (A3). Read-only on all deliverables.

---

## Method deviation (recorded honestly)

The brief's literal step was `git worktree add _m wave5/measures`. That branch is
**already checked out** in a live worktree (`.claude/worktrees/w5-measures`, tip
`520a10d4`); git refuses the same branch in two worktrees. I created the side tree
detached at the tip SHA instead:

```
git worktree add --detach _m 520a10d4
```

Same re-execution target (the tip), and it honors "never touch `wave5/measures` or
the side tree state" — the branch ref and its worktree are untouched.

---

## Target 2 — explosion detector (Acceptance A2): PASS, first-hand

Detector: `python/synapse/validation/explosion.py::detect_explosion`. Rule order:
NaN/inf → `max_strain > 10` → monotonic KE growth over a 5-frame window with ratio
`> 2.0` (baseline = first non-zero frame). On EXPLODING it returns `signal` +
`offending_frame = frame_no(window_end)` (`explosion.py:139-146`).

Invoked directly (not merely via a green test) — the shipped detector's own output:

| Fixture | Verdict | signal | offending_frame | detail |
|---|---|---|---|---|
| `healthy_sim.json` (shipped) | STABLE | — | — | silent, as required |
| `exploding_sim.json` (shipped) | EXPLODING | `ke_growth` | **5** | KE 1.0→60.0 (×60 over baseline 1.0) across 5 frames |
| `wxb_fresh_late_ke_growth` (**my variant**) | EXPLODING | `ke_growth` | **8** | KE 1.8→40.0 (×22.22 over baseline 1.8) across 5 frames |
| `wxb_fresh_control_flat` (**my control**) | STABLE | — | — | flat KE → silent |

**Anchor is computed, not pinned.** The exploding golden's KE `[1,2.5,7,20,60]` over
frames 1–5 is the single 5-frame window; window-end = frame 5; `max_strain` peaks at
3.1 (< bound 10) so `ke_growth` is *genuinely* the firing rule, not strain. My fresh
9-frame variant keeps the first four frames flat/decaying (three windows correctly
rejected as non-monotonic) and only the runaway window (frames 4→8) qualifies — the
detector returned `offending_frame=8`, i.e. it **located the first qualifying window**
rather than trivially returning the last frame (9). That exercises the anchoring path
the shipped 5-frame golden cannot.

**Test assertion is drift-proof.** `tests/test_measures_contracts.py:125-126` uses
chained equality `ev.offending_frame == g["expect"]["offending_frame"] == 5` (and the
same for `signal == ... == "ke_growth"`) — it pins to the **literal** `5`/`"ke_growth"`
independent of the golden's own `expect` field, so it is *not* the
control-pinned-to-the-brief's-figure trap.

**Contract suite green first-hand:** `tests/test_measures_contracts.py` → **24 passed /
0 failed** @520a10d4 on Python 3.14.2 (deterministic pure-Python; passing on a newer
interpreter than the receipt's 3.13 is stronger evidence).

Probe: `wxb_probe.py` (scratchpad) — all 12 first-hand checks PASS, exit 0.

---

## Target 3 — measurement→exposure tier projection (Acceptance A3): PASS

### Extends-not-forks — verified structurally + by test

- `measures.py:239-244` `_RUNG_FOR_VERDICT` maps every verdict to a rung **string that
  exists verbatim in `science/exposure.py`**: `MEASURED→V1_output`,
  `UNKNOWN→V0_membership`, `FAIL/EXPLODING→V1-degraded` (all three grep-confirmed
  present in `exposure.py`'s `RUNG_ORDER`/`TIER_FOR_RUNG`).
- `measures.py:252-261` `exposure_tier` calls the **real**
  `synapse.science.exposure.highest_tier([rung])`; guarded import returns the rung as
  an honest fallback if the module is absent — never a fabricated tier.
- The branch **never touched** `python/synapse/science/exposure.py`
  (`git log $(merge-base)..520a10d4 -- …/exposure.py` is empty) → structural proof it
  extends, does not fork.
- `tests/test_measures_contracts.py:211-219` asserts
  `exposure.highest_tier(["V1_output"]) == "foreground"` — a **live coupling** to the
  real system ("fails loud if exposure.py drifts these rungs"), not a mock.
- Exposure suites byte-green: `test_phase3_exposure.py` + `test_m1_truth_contract.py`
  → **16 passed / 0 failed**.

### S1 (deferred MCP disclosure) — honestly absent, not silently claimed

- The **only** consumers of `exposure_rung`/`exposure_tier` on the branch are
  `measures.py` (definition) and `test_measures_contracts.py` (tests). **Zero**
  references anywhere under `python/synapse/mcp/`.
- The branch **never touched** `python/synapse/mcp/_tool_registry.py`
  (`git log $(merge-base)..520a10d4 -- …/_tool_registry.py` empty).
- The delivering receipt marks A3 `PARTIAL - EXTENDS, honest scope`, files **F-A3**
  as "NOT DELIVERED (honest gap)", and holds **S1** as a spawn. The wiring's absence
  is disclosed at both the code and the receipt level — no laundered claim.

---

## Findings (crucible)

- **WXB-F1 (positive):** A2 + A3 re-execute green first-hand at the tip; the anchor is
  computed, the projection couples to the real exposure system, S1 absence is honest.
- **WXB-F2 (LOW, for WCRUX to weigh — receipt honest overall):** the receipt's
  `status_note` prose says all three acceptance predicates are "satisfied and
  demonstrated (predicate 3 via an exposure-rung extension)". The word *satisfied*
  applied to predicate 3 reads a touch stronger than its own structured verdict
  (`acceptance[2].verdict = PARTIAL`, registry-disclosure half not delivered). The
  parenthetical + the structured `PARTIAL` + F-A3 + held S1 make the gap unmissable,
  so this is a summary-prose-vs-structured-verdict tension, **not** an FP2 fabrication.
- **WXB-F3 (design, out of remit — for CTO):** `FAIL` and `EXPLODING` both project to
  `V1-degraded → surfaced_caveat` (visible + enabled, "degraded" badge). That reuses
  the rung minted for "live verification unavailable" for a *measured-and-bad* cook,
  conflating "couldn't measure" with "measured, it failed". Defensible product choice,
  honestly mapped and tested; whether a failed cook-verify should demote harder than
  `surfaced_caveat` is Joe/CTO's call. `measures.py:241-242`.
- **F-PANEL confirmed (not my scope, CTO disposition):** the branch's diff carries the
  prior unmeasured-honesty audit riding the same branch, including a **+21-line edit to
  `python/synapse/panel/health_infographic.py`** — the surface the leg's own crucible
  criterion 3 fences off. The delivering leg already flagged this as F-PANEL "FOR
  RULING"; I confirm the edit is present on the branch. Disposition is Joe/CTO's.

## Unmeasurable (honest UNKNOWN — not in my acceptance predicates)

The live hython golden cook (spawn **S2**: cook `rulebook/goldens/sim/*` in Houdini
22.0.400 and feed the same contract) is `gui_required` and rendered UNKNOWN headless
by the delivering leg. My predicates cover only the **judgement half** (goldens +
projection), which is fully headless-testable; I did not simulate the live cook.

---

## Acceptance verdict (W5-WXB)

| Predicate | Verdict | Evidence |
|---|---|---|
| both goldens + one fresh variant re-executed first-hand | **PASS** | probe table above; `test_measures_contracts.py` 24 passed @520a10d4 |
| tier projection: extends-not-forks verified; S1 absence confirmed honest | **PASS** | `exposure.py` untouched; `exposure_tier`→`highest_tier`; 16 exposure tests green; no `mcp/` consumer; receipt defers A3 honestly |

**Status: green_with_findings.** Both predicates PASS; findings WXB-F2/F3 + F-PANEL
are surfaced for WCRUX/CTO to weigh, not blockers.
