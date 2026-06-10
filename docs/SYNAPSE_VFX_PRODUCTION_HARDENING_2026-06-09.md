# SYNAPSE — VFX Production Hardening Report

**Date:** 2026-06-09 · **HEAD:** `ef58fa0` (v5.12.0) · **Suite:** 3,415 passed / 0 failed
**Lens:** *What breaks on a real show.* Not generic code review — every finding is judged by shot-data risk, farm hours, reproducibility, multi-seat reality, and artist trust.
**Relationship to prior reviews:** the 06-05 review audited safety-claims-vs-code; the 06-09 review audited latency/usability/blind-spots and fed the remediation run (C1–C11 + D3, all shipped in v5.12.0). **This report does not re-litigate any of that.** It derives, from first principles, what production demands of a scene-mutating AI agent — and measures the *capability surface* (the 110 tools and the subsystems no prior pass probed) against those demands.

---

## §0 — How this was produced (calibrate trust)

Six read-only subsystem probes (Solaris/USD authoring, routing/recipes/planner, APEX/COPs, agent/autonomy, pipeline citizenship, ops/upgrade surface) over the areas all prior reviews left unprobed — 36 findings — synthesized with three review passes' and one remediation run's worth of first-hand verified context.

**Tags:** **[V1]** = I opened the cited code myself (all four P0s are V1; several key claims were verified during the C5/C11 remediation reads). **[F]** = fleet-read, citation-grounded but *not* adversarially verified — treat as a strong lead, reproduce before acting on specifics. Live-runtime behavior was **not** exercised (no render was run; no live Houdini probe) — several findings explicitly carry "verify live" as their first step.

---

## §1 — First principles: what production demands of a scene-mutating AI agent

Derived from what a show actually is — hundreds of artists' hours crystallized into scene files, farm time, and approved frames — six demands, in priority order:

1. **Truth over success-shaping.** A production tool's cardinal sin is not crashing — it is *lying*. A crash costs minutes; a confident success report for work that didn't happen costs farm submissions, dailies round-trips, and (worst) trust, because artists stop believing the tool *and* stop checking it at the same rate. For an LLM-driven tool this is doubly binding: the agent *reads its own tool results* — a false "success" poisons the agent's reasoning loop, not just the artist's mental model.
2. **Reversibility & artist ownership.** Ctrl+Z must fully unwind any agent action; the agent must never destroy artist-authored state (parm expressions, tokens, files) as a side effect; the `.hip` belongs to the artist.
3. **Reproducibility.** The same scene must render the same way tomorrow, on another seat, on the farm. Anything that mutates global state (playhead, render settings, output parms) without restoring it breaks the approved-dailies contract.
4. **Pipeline citizenship.** Paths are tokens, not literals. Color is managed, not assumed. Frame conventions vary. Assets resolve through resolvers. The farm is not localhost.
5. **Bounded autonomy.** Anything that runs unattended has an iteration bound, a wall-clock bound, a reachable kill switch, and an evaluator that cannot be fooled by its own blindness.
6. **Operability at N seats.** Config is enumerable, logs are findable, upgrades have a runbook, keys/stores work when a shot moves between artists.

**Where SYNAPSE stands, in one sentence:** the *core engine* — transport, handlers, memory, panel, provenance — has been through three review→fix cycles and genuinely satisfies demands 2/3 *at the engine level*; the *capability surface* contains a tier of tools that violate demand 1 outright, and demands 4–6 are largely unbuilt because the system has only ever lived on one seat.

---

## §2 — The verified strengths (the foundation is real)

These are first-hand verified and worth protecting — they are *why* hardening the surface is worth it:

- **The artist's `.hip` is never written.** Zero `hipFile.save()` callers anywhere in server/panel/autonomy **[V1]**. Exactly right.
- **The engine-level mutation contract holds:** inline `hou.undos.group` + main-thread marshalling on the live handler path; cross-client mutation serialization (C5); zombie-mutation abandonment (C4); per-tool timeout discipline with a no-retry contract (C7); render IO off the main thread (C11) **[V1, test-pinned]**.
- **Memory cannot self-destruct anymore:** degraded-load guard, crash-atomic backed-up saves, key escrow + fingerprint (C1–C3) **[V1, test-pinned]**.
- **The freeze chain acts** (D3): 1 s panel heartbeat → 5 s detection → 30 s sustained → breaker + emergency halt via active bridge **[V1, test-pinned]**.
- **Provenance is real:** every mutating op on the live path leaves a durable Floor record; curated verdicts live in the agent.usd Ledger with lossless backfill **[V1]**.
- **The phantom-API gate works** (scout + introspected symbol table, false-phantom rate 0.0) **[V1]** — *with one upgrade-time hole, §4.6*.
- **The USD authoring idiom is correct** where used: in-cook `editableStage()` via pythonscript LOPs is the right, reproducible Solaris pattern; the compose tier's verification machinery (`winning_layer`, `composition_errors`, `assess_render_ready`) is genuinely strong **[F]**.
- **Conformance discipline:** doc/code value pins, suite 3,415 with the floor enforced per commit.

---

## §3 — The headline pattern: **confident fiction**

The single most important production finding is not one bug — it is a *class*. Across four independent probes, the same shape recurs: **a tool reports success for work it did not do, cannot do, or cannot know it did.** For an agent-driven system this is the worst failure class, because the LLM consumes these results as ground truth and compounds them.

| # | The fiction | Reality | Where | Tag |
|---|---|---|---|---|
| 1 | Chat: **"Executed recipe (N steps)"** | Nothing executes — no production caller passes `command_fn`; `success=True` is unconditional | `routing/router.py:392-405`, `handlers.py:1357` | **[V1] P0** |
| 2 | Autonomous render "passed quality checks, score 1.0" | Evaluator scores **unverifiable** frames (EXR without OIIO, or directory paths) as perfect — a black sequence passes | `autonomy/evaluator.py:218-225`, `driver.py:414-423` | [F] P1 |
| 3 | `cops_bake_textures`: "baked normal/AO maps" | Nothing is baked; `high_res`/`low_res` inputs silently dropped; no file ever written | `handlers_cops.py:1337-1406` | [F] P1 |
| 4 | `cops_reaction_diffusion` / `pixel_sort`: "kernel configured" | The "kernels" are `#define` lines with no kernel body; node never cooked | `handlers_cops.py:1008-1019,1099-1109` | [F] P1 |
| 5 | Planner "AOVs configured / OIDN denoiser enabled" | Pure stub steps — `execute_python` bodies that do nothing and return success strings | `routing/planner.py:488-505` | [F] P2 |
| 6 | `tops_configure_scheduler(scheduler_type='deadline')` → "configured" | `scheduler_type` is read, echoed, and ignored; PDG is structurally localscheduler-only | `handlers_tops/cook.py:146,197-198` | [F] P2 |
| 7 | USD edit "success" (`set_usd_attribute`, light-link, collections…) | The edit lands on a **dangling, never-displayed LOP branch** — viewport, Karma, and USD export never see it; `reference_usd` creates a fully disconnected island | `handlers_usd.py` (10 sites; zero `setDisplayFlag` in the file) | [F] P1 |
| 8 | Collections / light-linking / variant-select "success" | The generated LOP is **never cooked** — genuine USD errors (nonexistent collection, typo'd variant) surface nowhere | `handlers_usd.py:881-1185` | [F] P1 |
| 9 | `quality_threshold=0.95` accepted for hero frames | Parsed, documented (0.85 default), never used — the real gate is hardcoded 0.7 | `handlers.py:1562,1578`, `evaluator.py:321` | [F] P2 |
| 10 | APEX rig recipes "build an FK rig" | Recipes ship **phantom node types** (`apex::rig::fkfull` etc.) the project's own science run disproved and mapped to real names on 2026-06-02 — and the prompt tells the LLM to *guess* when creation fails | `panel/apex_recipes.py` (8+ sites) vs `science/apex_probes.py:22-38` | [F] P1 |
| 11 | Flipbook fallback returns `image_path` at the artist's beauty path | A GL viewport grab is written **to the resolved render output path** — on disk, indistinguishable from a real render | `handlers_render.py:398-446` | [F] P1 |
| 12 | `set_payload_loadstate` "unloaded" | `stage.Load()/Unload()` inside a pythonscript cook is per-stage population state, not a composable opinion — likely doesn't propagate downstream | `handlers_usd.py:1394-1409` | [F] P2, verify live |

**The first-principles rule to adopt (one sentence, enforceable in CI):**
> *A tool result may not claim an outcome the handler did not observe.* "Success" requires the effect to be verified (cooked, stat'd, read back) or the result must say `proposed` / `scaffolded` / `unverified` — and a registry-wide test should grep every handler's success path for unobserved-outcome claims.

This is the same honesty discipline the project already applied to itself three times (bridge → docs, consent → docs, freeze chain → wired). It now needs to be applied to the *tool results*.

---

## §4 — Axis-by-axis assessment

### 4.1 Reversibility & artist ownership — engine ✅, surface has four holes

- **[V1] P0 — `houdini_render` destroys the artist's output-path tokens.** `p.eval()` (expanded — `$JOB`/`$HIPNAME`/`$F4` baked to literals at the *current frame*) is written **back into the artist's ROP parm** (`handlers_render.py:237→287→335-340`) with no restore and no undo group. One AI-assisted render converts a show-convention tokenized path into a frozen literal; a later farm submission renders **every frame to one filename, overwriting itself**. Fix: capture `unexpandedString()`, restore in `finally` (same pattern for the resolution/override sets). *Small, urgent.*
- **[V1] P0 — the Solaris compose tier mutates off the main thread with zero undo, and writes `.usd` files ungated.** `handlers_solaris_compose.py` has **0** `run_on_main`/`undos.group` hits; `solaris_compose.py`'s own docstring says it assumed bridge dispatch; it's registered as a plain WS command; `Sdf.Layer.CreateNew(fp).Save()` writes five department layers to disk with no consent affordance (`solaris_compose_tools.py:123`). This is the same defect class C11 just fixed for render — intermittent crash/corruption territory plus un-undoable 7-node scaffolds. Fix: wrap like `handlers_solaris_graph.py` already does. *Small.*
- **[F] P1 — auto-fix/memory-warmup render-settings mutations persist** with no restore, no undo group, and no per-parm provenance (`render_farm.py:324-328,461-481` — `initial_settings` captured, never re-applied). Approved-dailies look silently drifts. *(Overlaps review C18 — now with the autonomy-loop evidence.)*
- **[F] P1 — exceptions mid-undo-group strand orphan nodes** (COPs builders: `block_begin/block_end` pairs abandoned; all `if node is None` fallbacks are dead code because `createNode` raises). Make builders transactional: close group + undo on exception. (`handlers_cops.py:984-1002` et al.)

### 4.2 Reproducibility & determinism

- **[V1] P1 — `cops_temporal_analysis` moves the global playhead in a loop and never restores it — while classified read-only**, so it bypasses the C5 mutation lock *and* audit logging (`handlers_cops.py:1456-1463`; `handlers.py:202` — I read that list when building C5). Next render/flipbook silently executes at the wrong frame, with no audit trail. Fix: save/restore `hou.frame()` in `finally`; remove from `_READ_ONLY_COMMANDS`. *Small, sharp.*
- **[F] P2 — generated FX graphs are not re-run deterministic:** hardcoded node names + name-based re-lookup (`parent.node('vellum_solver')`) cross-wire a second run's forces into the *first* run's solver after Houdini auto-renames; FX builders also create SOP types directly under `/obj` (raises — proving this layer never ran end-to-end). (`planner.py:279-330`, `fx_recipes.py:75-96`)
- **[F] P1 — recipe/plan partial application has no rollback story:** per-step failures are swallowed, later steps continue, `success=True` unconditionally, undo groups are per-command only — a 6-step lighting setup failing at step 3 leaves an un-attributable half-build. Fix: one undo group per recipe, stop-and-undo on first failure, `success = all(steps)`.
- **[F] P2 — timestamped, unversioned default outputs** (`render_{timestamp}.$F4.exr`) make reruns incomparable.

### 4.3 Pipeline citizenship — the largest unbuilt axis

- **[F] P1 — zero color management anywhere in the repo.** The only "aces" hit is a test string. EXR→JPEG previews go through bare `iconvert` (no `-g`, no OCIO), and `specialist_modes.py:191` *institutionalizes* the pattern. On an ACES show, **every visual judgment the AI makes — exposure verdicts, autonomous-render quality scores, "push the rim warmer" — is made on a wrong-transform image.** Fix: OIIO with the active `$OCIO` display/view (fallback sRGB, last-resort `-g 2.2`), and record the transform used in the tool result.
- **[F] P1 — asset paths are baked absolute and resolver-hostile:** verbatim Windows paths into reference/sublayer parms; `$HIP` *pre-expanded* into the layer stack and RenderProduct `productName` (frame-token-free — a farm sequence overwrites one file); the `os.path.isfile` gate rejects any `ArResolver` URI (`asset:`/`shot:`), walling SYNAPSE off from resolver-based studios. Fix: keep tokens unexpanded in parms, pass through scheme'd URIs, advisory on every baked absolute path. *(Which convention per show is pipeline-config — see §5 M2.)*
- **[F] P2 — `$F4`-only frame handling** (`str.replace('$F4', …)` at 3+ sites; validation hardcodes `{prefix}.NNNN.{ext}` with zfill(4)) — any other padding yields false "missing frames" → pointless farm resubmits. Centralize one Houdini-token expander.
- **[V1] P2 — farm story is localscheduler-only** (auto-created; no Deadline/Tractor/HQueue anywhere) — fine *if stated*; today `scheduler_type='deadline'` returns "configured" (§3 #6). Fail loudly until real.
- **[F] P2 — USD-legal names crash node creation:** hyphens/brackets in asset names (`hero-asset`) make 9 `createNode` sites raise mid-undo-group. One `_safe_node_name()` — align its rules with whatever **D-3** ratifies for prim names (RFC zone respected: flagged, not prescribed).

### 4.4 Bounded autonomy

- **[F] P0 — the autonomy pipeline is contract-broken against the live handlers** (one leg *reproduced live by the probe*): the default plan's first step sends `{"frame": N}` where the handler requires `image_path` → dies at step 1 every run; the driver parses a render-result shape (`frames`/`output_path`) that `BatchReport.to_dict()` doesn't produce (`frame_results`/`image_path`) → every good render evaluated as failed → identical replan burns the remaining iterations. The flagship unattended tool cannot complete on the live path. Fix: pin the planner→handler→evaluator contracts with one integration test that drives the *real* planner output through the *real* registry headless.
- **[F] P1 — no wall-clock bound, unclamped payload-controlled `max_iterations` multiplying with per-frame farm retries, and both kill switches (`driver.emergency_stop`, `farm.cancel`) unreachable** — no handler retains them. *(Extends review C17.)* Plus `prediction`/`verification` `UnboundLocalError` on early exit the day the predictor is wired.
- **Cost bounds:** the worker loop's only bound is 25 iterations — no token/dollar budget **[V1]**. Acceptable single-seat; state it, and add a per-run budget before any unattended use.

### 4.5 Multi-seat reality

- **[F] P1 — scene memory is effectively single-seat on shared storage:** the store travels with `$HIP`, the Fernet key lives in `~/.synapse/` per user — seat B opening the shot gets a (correctly, post-C1/C3) *loud* refused store instead of artist A's accumulated context. Pure ops fix: provision one show-scoped `SYNAPSE_ENCRYPTION_KEY` (already takes priority) via the studio launcher; document the per-user auto-gen as single-seat-only; doctor check comparing active key fingerprint vs the store sidecar.
- **SEC-1 / D4 stands** (hwebserver has zero per-command RBAC) — unchanged, documented localhost posture; *mandatory before any non-local mode* (06-09 review; not re-litigated).
- **[F] P2 — egress posture still undocumented** for multi-seat (scene/selection/memory content to api.anthropic.com; review C19) — a studio's "what leaves the building" question has no written answer.

### 4.6 Operability at N seats

- **[F] P1 — a Houdini upgrade silently disarms the phantom-API gate:** the symbol table is build-stamped (correct), but on mismatch the default `warn` policy degrades every verdict to `None` with one warning line — *precisely the week API drift peaks*. No upgrade runbook exists (table regen lives in a docstring; vendor ABI in `_vendor/README`; installer re-run requirement written nowhere). Fix: `docs/studio/UPGRADE.md` (regen table → verify ABI → re-run installer → confirm fonts/corpus) + make a verdict-less scout *loud* in the panel.
- **[F] P1 — config surface: ~25–32 `SYNAPSE_*` env vars, ~7 documented** **[V1: 32 distinct names counted]**, including `SYNAPSE_RAG_ROOT` carrying two incompatible meanings (store-layout root for scout vs repo-rag root for recall) and a documented `SYNAPSE_MEMORY_BACKEND=sqlite` that is a silent no-op. Fix: one env reference table in DEPLOYMENT.md + a DOC-1-style conformance test that fails on undocumented vars.
- **[F] P2 — no log file, no diagnostic bundle:** the freeze chain's forensic trail goes to the unsaved Houdini console (no `FileHandler` anywhere); durable artifacts scatter across 6+ locations. Fix: rotating `~/.synapse/logs/synapse.log` + `synapse_doctor --bundle`.
- **[F] P2 — all performance telemetry is process-local** (tool durations, the new C6 dispatch-wait histogram, live-metrics ring) — the crashed/frozen sessions they exist to explain leave zero evidence. Fix: periodic flush + a best-effort flush inside `FreezeChain._escalate` (dump the evidence before the process dies). *(Extends the review's reopen-gates finding.)*
- **[F] P2 — installer:** idempotent (good), but new-build pref dirs don't exist until first launch, absolute repo paths are baked per seat, and none of this is documented → "panel is gone" ticket wave on every Houdini upgrade.

---

## §5 — Hardening roadmap (three milestones, dependency-ordered)

### M1 — *Stop the fictions* (≈1 week; the trust milestone)
1. **The four P0s:** recipe-execution honesty (`router.py` — propose-or-execute, never "Executed" unexecuted) · autonomy contract pins (planner→handler→evaluator + one real-registry integration test) · compose-tier `run_on_main`+undo+disk-write consent · render output-parm capture/restore.
2. **The truth contract, enforced:** every §3 fiction either does the work, verifies the work, or says `scaffolded`/`unverified` (placebo kernels, bake facade, AOV/denoise stubs, scheduler_type, quality_threshold, evaluator's unverifiable-frames=1.0). Add the registry-wide "no unobserved-outcome claims" test.
3. **The two cheap sharp ones:** `cops_temporal_analysis` playhead restore + read-only declassification; APEX recipe phantom-name migration (the verified mapping already exists in `science/apex_probes.py` — mechanical) + delete the "guess similar names" prompt instruction (route through `synapse_scout`, per CLAUDE.md §11.15).

### M2 — *Pipeline citizen* (≈2 weeks; the show-integration milestone)
4. USD authoring display/rewire policy (end the dangling branches — or return `needs_rewire` honestly) + cook-and-verify in all five uncooked mutators + `_safe_node_name()`.
5. Path policy: tokens stay unexpanded; resolver-URI passthrough; `$JOB`-aware defaults with `$HIP` fallback; frame-token generalization (one expander); flipbook never writes to the beauty path.
6. Color-managed previews (OIIO + `$OCIO`; transform recorded in the result).
7. Recipe-tier rollback (one undo group per recipe, stop-on-failure, honest step accounting) + show-config lookup for resolution/output roots (per-show convention = pipeline config, **not** hardcoded — and any agent.usd/USD-schema record placement stays in the **D-3/Gold RFC** lane).

### M3 — *Studio-operable* (≈2 weeks; the N-seats milestone)
8. `docs/studio/UPGRADE.md` + loud verdict-less scout; env-var reference + conformance pin; installer update-procedure + version stamp.
9. `~/.synapse/logs/` FileHandler + `synapse_doctor --bundle`; telemetry flush (incl. freeze-escalation dump).
10. Show-scoped key provisioning docs + doctor fingerprint check; egress documentation (C19); bounded-autonomy budget + reachable cancel (with C17's `render_farm_cancel`).
11. *Gate, not work:* SEC-1/RBAC before any non-local deploy mode (D4 — unchanged).

**Sequencing logic:** M1 before M2 because every M2 improvement flows through tool results that must first be honest; M3 last because it is ops surface, not correctness — but item 8's upgrade-runbook is worth pulling forward if a Houdini build change is imminent.

---

## §6 — What this report did not probe + verification debt

- **Live behavior:** no renders run, no live Houdini probes — findings #12 (payload load-state semantics), the COPs node-type vocabulary (`cop2net` vs `copnet`), and the iconvert default-transform specifics each carry "verify live on 671" as step one.
- **Adversarial verification:** the 30 [F]-tagged findings are citation-grounded fleet reads, not crucible-verified. The four P0s and the C5-bypass were verified by me directly. Recommend the same reproduce→fix→reproduce-clean discipline the remediation run used; expect some severity adjustment, little outright refutation (the prior fleet's refutation rate was 1/24).
- **Unprobed still:** KineFX *handlers* (none exist — the rigging surface is panel content only, itself a finding), the science/FORGE internals, hwebserver resilience parity (ARC-2), and everything behind `SYNAPSE_INTEGRATION` live gates.
- **Spend note:** this fleet completed 6/6 with no spend-limit casualties (770k tokens).

---

## One-line synthesis

SYNAPSE's engine has been hardened into something genuinely production-shaped — reversible, provenance-recorded, crash-safe, freeze-safe — but its capability surface still contains a tier of tools that *narrate* production work instead of doing it, and the system has never been asked the show-floor questions (whose color? whose paths? whose farm? whose seat?); the hardening path is therefore not more engine work but a truth contract on tool results (M1), pipeline citizenship (M2), and an N-seats ops surface (M3) — in that order, because an agent that reports fiction poisons its own loop before it ever reaches the farm.

---

*Provenance: 6-probe read-only fleet `wf_a19208f4-1ba` (36 findings; digest at `.synapse/_vfx_probe_digest.md`, full transcripts in the session workflow dir) + first-hand verified context from the 06-05 review, the 06-09 review (`docs/SYNAPSE_CTO_REVIEW_2026-06-09.md`), and the v5.12.0 remediation run (Ledger: `docs/SCIENCE_HARNESS_LEDGER.md`). No code was changed by this report.*
