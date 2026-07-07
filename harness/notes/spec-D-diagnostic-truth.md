# D TRACK — frozen spec (diagnostic-truth graft)

**`harness/notes/spec-D-diagnostic-truth.md`** · Repo: `C:\Users\User\SYNAPSE` (branch per orchestrator). All paths repo-relative.
**Status: PROPOSAL — `ratified: false`.** This file is the evidence artifact that makes `D.0` a legal `flywheel_queue/v1` entry. It becomes a work order only when a human flips ratification (the anti-runaway anchor). Authored per `SYNAPSE_ODFORCE_HARNESS.md` intake; grounded against HEAD `d34f2f7` / 21.0.671.

## Mission

Graft a **diagnostic-truth track** onto the EXISTING harness (`harness/run.ts` loop — DO NOT rebuild it): capture what is *observably true about cook behavior* — dirty-propagation, recook triggers, time-dependence, and callback/expression runtime errors — as a probed, version-stamped catalog, then wire it into an artist-facing explainer that answers "**why did/will this recook?**" and "**what did my callback actually do?**" with live truth, never doc reasoning.

**Why this is a new cycle class.** WIRING truth (U.1–U.4) proves connections; CONTEXT truth (U.5) proves per-LOP knowledge; CAPABILITY truth (C.0) proves what SYNAPSE can *create*; READINESS truth (S.0) proves findings persist. None proves what the scene will *do when poked* — the dynamic axis. DIAGNOSTIC truth is that axis. It is also the scour's highest-moat finding: no external LLM holds live cook flags; only an in-process agent can answer these questions without guessing.

## Ground truth (verified this session — do not re-litigate)

- **Precedent exists and is TOPs-only:** `python/synapse/server/handlers_tops/diagnostics.py` (dirty→re-cook→repeat with per-attempt details) and `handlers_tops/cook.py:361` (`_handle_tops_dirty_node`, `dirty_upstream`). The D track generalizes this *pattern* to SOP/LOP/COP/DOP **without touching the TOPs path** — TOPs dirty/cook stays where it is; `hou.pdg.*` remains quarantined and is not on any D critical path.
- **Runtime-error substrate exists:** `python/synapse/cognitive/dispatcher.py` carries `traceback_str` on the error envelope (truncated to context budget, `:71-91`). D.1 consumes this seam; it does not reinvent capture.
- **Scope-safe under the declared allowlist** (`authoring_domains.json` = cop/lop/sop/karma/usd): the probe *reads* cook state and *reverts* residue; it authors nothing renderer/material/rigging. No drift term is approached.
- **The live dispatch seam is `SynapseHandler.handle(SynapseCommand)`** (`handlers.py:353`) — any new artist-facing tool lands as a handler on this surface, same as every shipped tool. The *probe* is host-layer and never imports the package (spec-0.2 / `host/introspect_*.py` pattern).
- **Binding trap inherited from spec-C:** renders are NEVER part of a golden (Indie husk no-ops headless). All D goldens are cook-state-only. Guardrails (`phantom_clean` etc.) already run every sprint — D-tasks inherit them for free.

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. Phantom-first deliverable — the API confirmation probe

Every `hou.*` symbol on D's critical path is **UNVERIFIED until dir()-confirmed** against live 21.0.671 hython. Candidate set (candidate *means candidate* — the probe decides, not this spec):

`hou.Node.cookCount` · `hou.Node.needsToCook` · `hou.Node.isTimeDependent` · `hou.Node.cook` · `hou.Node.infoTree` · `hou.NodeEventType.ParmTupleChanged` / `.InputRewired` · `hou.Node.addEventCallback` · `hou.expressionGlobals` · `hou.Parm.expressionLanguage` · `hou.Parm.evalAsString`

Output: `harness/notes/verified_cook_api_21.0.671.json` — `{schema:"cook_api/v1", houdini_version, confirmed:[...], absent:[...], blake2b}`. **Absent symbols auto-quarantine** (join the phantom table's authority); the catalog probe (§2) may only use `confirmed`. This file is D's first committed artifact and the precondition for everything below.

### 2. The probe — `host/introspect_cook_truth.py` (hython-only, zero-synapse-import)

Mirrors `host/introspect_context_capability.py`. For each context in `(sop, lop, cop, dop)` — TOP excluded (shipped surface), MAT folded under LOP:

- Build a tiny throwaway graph (3–5 nodes, the C.0 golden species: `Sop/{box,scatter}`, `Lop/{sphere,materiallibrary}` etc.), then run **perturbation trials**: set one parm → record which downstream nodes report needs-cook / cookCount delta; rewire one input → same; toggle a time-dependent expression → record time-dependence propagation.
- Record per-trial: `{context, graph_fingerprint, perturbation, expected_dirty:[paths], observed_dirty:[paths], cookcount_deltas, time_dependent:[paths]}`.
- All mutations inside one undo block per trial; **revert and verify residue-free** before the next (spec-C rule: `hou` reads allowed to VERIFY and revert only).
- Output: `harness/notes/cook_truth_21.json` — `{schema:"cook_truth/v1", houdini_version, blake2b, trials:[...]}`, major-pinned name. **This catalog file is the D.1+ arming trigger**, peer of `drop.json` / `context_capability_21.json`.

### 3. New checks — `harness/verify/checks.py` (vocabulary additions)

`cook_api_confirmed` (verified_cook_api file exists, schema valid, zero critical-path symbols unprobed) · `cook_truth_fresh` (catalog exists, build-stamp matches live hython, blake2b intact — the `check_connectivity_catalog_fresh` pattern) · `cook_review_clean` (review sweep, §4, zero unexplained divergences) · `cook_golden_sop` / `cook_golden_lop` / `cook_golden_cop` / `cook_golden_dop` (one frozen perturbation trial per context reproduces its cataloged dirty-set exactly — deterministic, render-free) · `tops_path_untouched` (git-diff guard: no D sprint modifies `handlers_tops/`).

### 4. The review sweep — `scripts/flywheel_review_cook.py`

The U.1/U.5 pattern: sweep SYNAPSE's own emitters and the explainer's claims against the catalog. Any claim of the form "changing X recooks Y" that the catalog can't back is a finding. Ledger deposit via `--deposit` under hython post-merge, exactly like U.1/U.5.

### 5. The artist surface — two handlers on the existing seam (post-ratification sprints)

- **D-sprint 1 — `synapse_explain_recook`** (read-only): given a node path (+ optional hypothetical parm change), answer from catalog + live flags what will recook and *why*, citing the trial fingerprint. Registered via `CommandHandlerRegistry` like every shipped tool; no new transport, no new panel surface.
- **D-sprint 2 (= staged D.1) — `synapse_diagnose_callback`**: given a node whose parm callback/expression errored, replay under capture, return the dispatcher-style envelope (`traceback_str` seam) + the cook-state before/after. Consumes §1's event-callback symbols **only if confirmed**; otherwise degrades to expression-evaluation diagnosis and says so (truth contract: never claim capture it didn't perform).

### 6. New tests — `tests/test_d_track.py`

Style of `test_ctx_track.py` / `test_phantom_guardrail.py`: schema round-trip for both JSON artifacts; golden fixtures per context; the `tops_path_untouched` guard; a fix-forward pin — **Commandment 7: a golden that starts failing is a bug to fix forward, never an assertion to soften.**

### 7. Docs + queue (orchestrator-owned, not builders)

Paste-ready `flywheel_queue/v1` entry — evidence paths are this spec plus the four grounding anchors that already exist at HEAD:

```json
{
  "id": "D.0",
  "title": "Diagnostic truth (COOK/RUNTIME): cook-API confirmation probe -> perturbation catalog -> review sweep -> recook-explainer + callback-diagnosis handlers gated by per-context goldens",
  "status": "candidate",
  "evidence": [
    "harness/notes/spec-D-diagnostic-truth.md",
    "python/synapse/server/handlers_tops/diagnostics.py",
    "python/synapse/cognitive/dispatcher.py",
    "harness/notes/spec-0.2-api-delta-probe.md",
    "harness/notes/spec-C-context-capability.md"
  ],
  "ratified": false,
  "note": "NEW cycle CLASS — DIAGNOSTIC truth (what the scene observably DOES when poked: dirty-propagation, recook triggers, time-dependence, callback runtime errors), a different axis from WIRING (U.1-U.4), CONTEXT (U.5), CAPABILITY (C.0), READINESS (S.0). Sourced from the ODFORCE scour's two CROWN findings (cook-graph explainer, callback debugger) — the only scour candidates whose moat is impossible without in-process truth. Phantom-first: every candidate hou.* symbol is UNVERIFIED until the §1 probe confirms it; absences auto-quarantine. TOPs dirty/cook surface is shipped and untouched (tops_path_untouched guard). Scope-safe under the declared allowlist AND under a future procedural-only narrowing — the track only reads and reverts. Queued per the anti-runaway anchor for the same human sign-off U.5 received."
}
```

## Style & traps (binding)

No render in any golden. No `hou.pdg.*` anywhere. No edits under `handlers_tops/`. Probe = host layer, zero-synapse-import; handlers = the `SynapseHandler` seam, nothing bespoke. Every mutation undo-wrapped, residue-verified. Catalog files carry `houdini_version` + `blake2b` or they are invalid. A claim the catalog can't back is a finding, not a footnote.

## Deliverable split (for builders, post-ratification)

**Mile 1** — §1 API probe + `cook_api_confirmed`. **Mile 2** — §2 catalog probe + `cook_truth_fresh` (arming trigger lands). **Mile 3** — §4 sweep + `cook_review_clean` + goldens. **Mile 4** — `synapse_explain_recook`. **Mile 5 (D.1)** — `synapse_diagnose_callback`. Each mile is one committed sprint gated by its checks; no mile starts before the previous one's checks are green.
