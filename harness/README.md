# SYNAPSE → H22 harness  (v2 — boundary-synthesized)

A long-running, self-verifying harness that grinds your H22 preparedness checklist.
Your own `probe → delta → patch` loop, made autonomous, with an adversarial gate.

It runs headless for cooks, renders, patches, and worktree commits. It will **not** merge
to main, decide your architecture, or fire the post-drop pipeline before H22 exists — those
are deliberate human gates.

**v2 synthesizes `docs/SYNAPSE_H22_BOUNDARY.md`:** orchestrating H22's native APEX MCP is now a
first-class, drop-week-critical leg (not a stretch), and the boundary's non-goals are enforced
as cross-cutting guardrails that fail any sprint that erodes the moat.

## How it runs

**Now (Mode A, on H21):**
```bash
export HYTHON="/path/to/Houdini 21.x/bin/hython"   # Windows: ...\bin\hython.exe
bun run harness/run.ts            # grinds Phase 0 (incl. 0.8/0.9 against the mock MCP)
bun run harness/run.ts --dry      # plan only — see the queue + gates, spawn nothing
bun run harness/run.ts --task 0.8 # one task
bun run harness/run.ts --force    # re-run tasks the completion ledger (done.json) already banked
```

**On drop (Mode B, mid-July):** install H22, read the three numbers, then write the trigger:
```bash
cat > harness/state/drop.json <<'JSON'
{ "python": "3.x.x", "usd": "x.y.z", "pyside": "6.x.x", "houdini": "22.0.xxx" }
JSON
export HYTHON="/path/to/Houdini 22.x/bin/hython"
bun run harness/run.ts            # probe fires, delta becomes the worklist, loop runs
```

## The loop
`fresh Generator (WIP=1) → checks.py (hython · doctor · ledger · render · probe · MCP) →
deterministic guardrail gate → adversarial Evaluator → PASS or repair-ticket → loop`, capped
at `MAX_ROUNDS` (default 3) before a task is flagged for you. Passing features wait in
worktrees for **your** merge. Two facts the arrow compresses: a task already banked in
`done.json` (refs byte-identical) is **skipped** before generation, and a guardrail `ok:false`
short-circuits to a repair ticket **before** the Evaluator runs.

## Guardrails (boundary non-goals — run every sprint)
`checks.py` runs the `guardrails` set on **every** task in addition to its own `verify` list:
`scout_no_apex_corpus`, `no_rigging_drift`, `provenance_not_bypassed`, and `phantom_clean` (no
newly-introduced phantom `hou.*` API in the sprint's changed `.py`, dir()-symbol-table-gated). A guardrail with
`ok:false` is a **deterministic FAIL** — run.ts writes a repair ticket and loops *before*
the Evaluator is called. A guardrail with `ok:null` ("not wired yet") only **warns**. This is
how `SYNAPSE_H22_BOUNDARY.md §8` stays true no matter what any Generator round does.

## The three human gates
1. **`0.1` sidecar vs abi3** — architecture decision. Harness recommends sidecar, verifies the bridge, doesn't choose.
2. **The drop trigger** — install H22, read Python/USD/PySide, write `drop.json`.
3. **Merge to main** — harness commits in worktrees only.

The harness also adds one **read-only** touchpoint that is *not* a gate: at run end it surfaces
flywheel candidates awaiting ratification — each `ratified:false` cycle with its evidence and the
exact `harness/state/flywheel_queue.json` line to flip. It never writes `ratified` itself; the flip
is yours, but nothing blocks on it.

## The v6 track — the second state-file trigger
Peer of `drop.json`: the v6→H22 build plan (`docs/v6/PLAN.md`) stays **held** until a human
drops blueprints. Arming marker: `docs/v6/BP00_manifest.md` — exact name, and it must be
**committed** (worktrees branch from HEAD; an uncommitted drop is invisible to every check).
Held → all `blocked_on:"blueprints"` tasks are filtered out and a read-only intake surface
prints the drop list; armed → the V-queue runs. Full contract: `docs/v6/INTAKE.md`.

- `V.1` scaffold the skeleton — stub every module in BP00's `## Module Manifest` (Mode A)
- `V.2` write BP09, the Iteration Controller spec (Mode A)
- `V.3` spec + BUILD BP10, the Global Knowledge Base — pure Python, zero hou (Mode A)
- `V.4` pure-Python layers, test-first — gsplat_compare, rubrics, meta-cognitive stats (Mode A)
- `V.5` Miles 1–2 — BP01 Perception + BP02 G-Splat vs shipped H22 (Mode B)
- `V.6` Miles 3–4 — BP08 three-tier evaluator, the keystone (Mode B)
- `V.7` Miles 5–7 — BP09+BP10 integration, first autonomous cycle, pyro only (Mode B)

## The context track — the third state-file trigger
Peer of `drop.json` and `BP00_manifest.md`: measures what SYNAPSE can actually CREATE in each
Houdini context (SOP · LOP · COP · TOP · DOP · MAT) by driving its own live handler surface
(`SynapseHandler.handle()`) under hython — golden create→verify→revert per context plus
extended gap probes — and deposits the truth as `harness/notes/context_capability_21.json`.
That catalog file is the arming marker (and it must be **committed** — worktrees fork from
HEAD): absent → `C.1`–`C.6` are held and a read-only intake surface says to run `C.0`;
present → the improvement queue grinds, each sprint gated by its context's golden AND a
ratchet (the context's gap count must strictly decrease unless already 0). Renders stay out
of every golden (Indie husk no-ops silently); APEX/rigging stays out structurally
(`no_rigging_drift`). Full contract: `harness/notes/spec-C-context-capability.md`.

- `C.0` probe all six contexts → catalog + review sweep (Mode A, runnable now)
- `C.1`–`C.6` close the top create-gap per context — sop, lop, cop, top, dop, mat — golden+ratchet-gated (Mode A, armed by the committed catalog)

## The studio-readiness track — the fourth state-file trigger
Peer of `drop.json`: wraps the 24 adversarially-verified findings of
`docs/reviews/synapse-studio-readiness-2026-07-06.html` into **durable regression gates** — each
S-check reads RED while its finding's fingerprint is live in the code and flips GREEN when the fix
lands (and stays green, so a finding can never silently regress). Prose review → executable gate wall.
Trigger: a human declares the deployment posture in `harness/state/posture.json`
(`{mode: solo|studio|farm, identity_model, auto_approve}`) — the report's Step-1 hinge, since
consent auto-approve and RBAC default-deny can't be enforced until the mode is a committed fact.
Held → the safety tasks (`blocked_on:"posture"`) are filtered out and a read-only intake surface
prints the declaration template. The three **security-critical** clusters are `human_gate` (the
harness owns the acceptance check and the review; a human authors the auth/consent change and the
harness never merges); the memory/eval/farm clusters are loop-gradable. Full contract:
`harness/notes/spec-S-studio-readiness.md`.

- `S.0` declare the deployment posture → write `posture.json` (human gate, Mode A)
- `S.1`–`S.3` unify policy · consent-at-dispatch · RBAC + per-user identity (human-authored, harness-gated; armed by posture)
- `S.4`–`S.6` memory provenance · eval backbone (wire `validate_frame` + guard fake-hou) · farm-headless (PDG/scout + C.4/C.5) — loop-gradable, Mode A
- `S.R` capstone review — aggregate every S-check, require the criticals green, emit the verdict (the review at the end)

## The diagnostic-truth track — the fifth trigger (the first JSON-predicate one)
What the scene observably DOES when poked — dirty-propagation, recook triggers, time-dependence,
callback runtime errors — probed into version-stamped catalogs, then wired into artist-facing
explainers ("why did this recook?"). Born from the ODFORCE intake
(`harness/notes/SYNAPSE_ODFORCE_HARNESS.md`); frozen contract `harness/notes/spec-D-diagnostic-truth.md`.
Two-stage HUMAN gating, as an AND (the catalog can never out-rank the ratification anchor):
1. a human flips `D.0`'s `ratified` in the git-tracked `harness/state/flywheel_queue.json` → arms
   `blocked_on:"cook_ratified"` (D.1/D.2, the probes);
2. D.2's committed `harness/notes/cook_truth_<major>.json` (major-agnostic — the H22 drop needs
   zero edits here) → arms `blocked_on:"cook_truth"` (D.3–D.5).
Held → a read-only intake surface prints the exact next human act; `--task` cannot pierce either hold.

- `D.1` cook-API confirmation probe → `verified_cook_api_<build>.json` (dir()-membership authority; absences quarantine)
- `D.2` perturbation catalog → `cook_truth_<major>.json` (the D.3+ arming trigger)
- `D.3` review sweep + per-context goldens (exact dirty-set reproduction, render-free)
- `D.4` `synapse_explain_recook` · `D.5` `synapse_diagnose_callback` — the two CROWN handlers, on the existing `SynapseHandler` seam
- guard on every D task: `tops_path_untouched` (the shipped TOPs diagnostic surface is quarantined)

## Files
| path | role |
|---|---|
| `harness/run.ts` | orchestrator — gate loop, guardrail short-circuit, completion-ledger skip, ratification surface, worktree routing, Mode A/B switch |
| `harness/tasks.json` | machine source of truth (sync with the checklist — that's task 0.3); holds `guardrails` |
| `harness/prompts/generator.md` | fresh-instance builder, WIP=1 |
| `harness/prompts/evaluator.md` | adversarial Houdini TD — the keystone; 5 rubrics incl. boundary |
| `harness/verify/checks.py` | deterministic checks (the Playwright analog) + MCP checks + guardrails |
| `harness/state/manifest.schema.json` | verdict / repair-ticket contract (incl. `boundary` score) |
| `harness/state/claude-progress.md` | state continuity the Generator reads each boot |
| `harness/state/done.json` | completion ledger — per-task PASS + refs-hash; skips already-banked work on re-run (runtime state, untracked) |
| `harness/state/flywheel_queue.json` | flywheel cycle candidates; a human flips `ratified`, the harness only surfaces them read-only |
| `.claude/settings.json` | pre-approved tool allowlist + format hook |
| `docs/v6/INTAKE.md` | blueprint paper→disk contract — arming rule, manifest table format, drop checklist |
| `docs/v6/PLAN.md` | the v6→H22 build plan reconciled against repo truth (Sessions→V.1–V.4, miles→V.5–V.7) |
| `tests/test_v6_track.py` | pins the six v6 checks + V-task/vocabulary conformance |
| `harness/notes/spec-C-context-capability.md` | context-track frozen contract — catalog trigger, goldens, ratchet, builder split |
| `host/introspect_context_capability.py` | per-context create-capability probe (hython; drives SynapseHandler.handle(), never raw hou for mutations) |
| `scripts/flywheel_review_context.py` | context-catalog review sweep (stock python; CRITICAL/ADVISORY findings) |
| `harness/notes/context_capability_21.json` | the capability catalog — C.1–C.6 arming trigger, peer of drop.json (commit it) |
| `tests/test_ctx_track.py` | pins the eight context checks + C-task/vocabulary conformance |
| `harness/notes/spec-S-studio-readiness.md` | studio-readiness frozen contract — posture trigger, finding-fingerprint gates, capstone review |
| `docs/reviews/synapse-studio-readiness-2026-07-06.html` | the 24-finding review the S-track wraps into gates (the "why" for S.x) |
| `harness/state/posture.json` | deployment-posture declaration — S.1–S.3 arming trigger, peer of drop.json (runtime state, untracked) |
| `harness/state/studio_readiness_verdict.json` | S.R capstone output — per-check verdict + READY/NOT-READY (runtime state) |
| `tests/test_s_track.py` | pins the eight S-checks + S-task/vocabulary/human-gate conformance |
| `docs/SYNAPSE_H22_BOUNDARY.md` | the boundary doc this harness enforces (the "why") |
| `docs/SYNAPSE_H22_PROVIDER_APEX.md` | provider-registration spec — what 0.8/2.7 implement |
| `CLAUDE.md` | distilled conventions (<2,500 tokens, cached) |

## ADAPT — the only wiring you owe it
Search the tree for `ADAPT`. The real ones, mostly in `checks.py`:
1. **`claude` CLI flags** in `run.ts` `runAgent()` — verify against your `claude --help`.
2. **Module + bridge ping** — `check_import_panel` / `check_brain_answers` (your real `ping`).
3. **doctor + probe entrypoints** — how `server/doctor.py` signals green; how `apex_probes.py` writes its delta.
4. **`agent.usd` schema** — prim type + `decision`/`reasoning`/`revert` attr names in `check_ledger`, and the revert + stage-hash diff in `check_revert_clean`.
5. **Render** — the USD to render + a real non-black pixel check in `check_render`.
6. **MCP provider** — `server/providers/apex_mcp.py` registry accessor + tool round-trip envelope (`check_mcp_registered` / `check_mcp_truth_contract`); the mock at `science/mcp_mock.py`; the shipped-surface probe `science/mcp_surface_probe.py` (`check_mcp_surface_probe`).
7. **Scout federation** — `server/scout_sources.json` (APEX source = federated `provider`) and the query API in `check_scout_federates`.
8. **Guardrail anchors** — `server/scout_sources.json`, `server/authoring_domains.json`, and the provenance-gateway sentinel in `check_provenance_not_bypassed`.

Until wired, those checks report `ok:false` (or `ok:null` for guardrails) with a reason — by design. Nothing here fakes a pass.
