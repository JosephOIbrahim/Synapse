# W8-STRUTH — Truth Scout Evidence

**Leg:** W8-STRUTH · band TRUTH · readonly recon · branch `wave8/struth`
**Source:** `harness/bastion/PROGRAM.md` anchor **B2-TRUTH**
**Method:** first-hand read-only recon of the live worktree (branch `wave8/struth`),
accelerated by a 5-agent read-only recon workflow; **every anchor cited below was
re-read first-hand by the leg before it entered this file or the receipt.**
Live-Houdini measurements that cannot run headless are recorded **UNKNOWN**, never
zero (mission constitution; the codebase's own R162 — *"a zero is a claim"*).

Live target build per `CLAUDE.md:3` = **Houdini 22.0.400** (dual-build w/ H21),
runtime safety-rule pins cite **22.0.368** — this 368/400 split is itself Finding S6.

---

## The frame: enforcement is real and widespread — the value is the *gaps*

SYNAPSE already runs a genuine honesty discipline on its **documented** claim
surfaces. The reference pattern is `face_token.py` (R162: *unmeasured renders
UNKNOWN, never zero*). The enforced cluster — verified first-hand — is broad:

| Enforced surface | Anchor | How it abstains |
|---|---|---|
| Token face (reference) | `python/synapse/panel/face_token.py:32` | `None→UNKNOWN`; unmeasured segment claims **no cells** |
| IntegrityBlock fidelity (/mcp) | `shared/bridge.py:704` | **computed** from evidence-derived anchors, not hard-set |
| Composition anchor | `shared/bridge.py:1840`, `:2706-2710` | fails **closed** — un-verifiable → invalid → rollback, never `valid=1.0` on nothing |
| Live envelope | `python/synapse/server/integrity_envelope.py:281` | un-run anchors `*_applicable=False`, never faked True |
| `synapse_doctor` | `python/synapse/server/doctor.py:11` | tri-state ok/fail/**skipped+reason**; no default-ok |
| ConductorAdvisor | `shared/conductor_advisor.py:134` | statistically silent < `MIN_OPS_FOR_VERDICT`=10 |
| Panel health strip | `python/synapse/panel/health_strip.py:13` | FACT-or-UNKNOWN grey; no default-healthy |
| `write_plane_state` | `python/synapse/server/write_plane.py:466` | genuine ok/degraded/**unknown** tri-state |
| `evolve_memory` (Law 3) | `python/synapse/server/handlers.py:351` | a path that did nothing returns `evolved=False` |
| cook-time probe | `host/cache_host_probe.py:188` | strict `>0`; `0.0`+cook-evidence → UNKNOWN `lastCookTime_unreported` |
| cache decision | `python/synapse/cache_policy/decision.py:143` | UNKNOWN cook-time → MEASURE_FIRST |
| result timing | `python/synapse/panel/result_telemetry.py:320` | headless timing → `"UNKNOWN"`, not `0.0` |
| SUPPORT_MATRIX | `docs/SUPPORT_MATRIX.md:5` | *"Unmeasured renders as pending, never as a pass"* |

**The seed class is already handled:** `lastCookTime()` headless-`0.0` is guarded
in the one production read path (`cache_host_probe.py`) and documented as a declared
delta (`SUPPORT_MATRIX.md:43-59`). So the truth-scout's value is the surfaces that
did **not** inherit this discipline. Those follow.

---

## P0 — production-blocking (a false claim shipped **now**, not saved by localhost)

### P0-1 · Cook result claimed without measurement — `tops_cook_node` / `tops_batch_cook`
- **Anchors:** `python/synapse/server/handlers_tops/cook.py:79` (single), `:482` (batch),
  `:503` (summary counts `cooked`+`cooking`). Honest counterpart:
  `python/synapse/server/handlers_tops/diagnostics.py:68,96`.
- **Claim:** `status="cooked" if blocking else "cooking"` — asserted purely because
  `node.cook(block=True)` did not raise. **No work-item-state inspection.**
- **Why P0:** on PDG a per-item `CookedFail` does **not** raise, so an *all-failed*
  cook returns `status="cooked"` and the batch summary reads `Cooked N/M nodes`. This
  is the mission's literal seed class ("a cook result claimed without measurement"),
  it is artist-facing, and localhost does not make a failed cook succeed. The honest
  form (`cook_and_validate`, `diagnostics.py:74-96`, counts `sname=='CookedFail'`)
  proves the fix exists and is not applied to the two direct handlers.
- **First-hand:** verified `cook.py:77-82`, `:480-504`; status literal ignores the
  `by_state` dict the batch path already collects.

### P0-2 · False rollback claim served to the model on the CRITICAL tool — `execute_python`
- **Anchors:** `python/synapse/mcp/_tool_registry.py:205` (served description),
  `python/synapse/server/handlers.py:85-90` (`_ROLLBACK_ERRORS`), served verbatim at
  `mcp_server.py:1080`.
- **Claim:** description says *"Wrapped in undo group — automatic rollback on failure."*
  The handler rolls back **only** on `_ROLLBACK_ERRORS` (coding bugs:
  NameError/Syntax/Type/Attribute/Index/Key/Value/UnboundLocal) and *deliberately
  keeps* mutations on operational failure (`handlers.py:86-88`).
- **Why P0:** it is a **false safety claim on the single most dangerous tool**
  (CRITICAL gate; ungated on the live `/synapse` path), served in full to the routing/
  executing model, and it directly contradicts the codebase's own constitution
  (*"Wrapping is not reversing"*, `CLAUDE.md` Identity/§1). A model told the op
  self-cleans will not prompt a manual undo, so the artist's model of scene state is
  wrong after any operational failure.
- **Mitigation (stated, not hidden):** an undo group *is* created, so a manual Ctrl+Z
  still reverses it — the artist just is not told they must. Re-rank to P1 if the
  ranking bar is "broken mechanism" rather than "false claim on a safety surface."
- **First-hand:** verified `_tool_registry.py:203-207` + `handlers.py:82-90`.

---

## P1 — hardening (real gap; guarded today by localhost / present-artist / degraded-only)

### Claim surfaces that fabricate a value when unmeasured (R162 violations)
- **S-P1a · `synapse_health.healthy` hardcoded `True`** — `python/synapse/server/handlers.py:899`.
  A liveness echo that can never be falsified; `health_strip.py:32-34` explicitly
  refuses to consume it. Mitigated by the additive real-tri-state `write_plane` field.
- **S-P1b · `live_metrics` fabricated `"healthy"` / zeroed scene on skip** —
  `python/synapse/server/live_metrics.py:64` (`health_status="healthy"` default),
  `:272` (`return SceneMetrics()` = all-zero on timeout/failure). A shed telemetry
  cycle is byte-identical to a healthy empty scene — the recon's "biggest R162
  surface." Feeds Prometheus `synapse_scene_errors 0` and the ConductorAdvisor. No
  UNKNOWN state in the model.
- **S-P1c · `render_farm_status["running"]=False` default** —
  `python/synapse/server/handlers_render.py:1613`. Masks a live bounded render when no
  `_render_farm` object exists (partially mitigated — `render_sessions` attached when
  non-empty). `health_strip.py:37-39` names this as a surface to avoid.
- **S-P1d · `validate_frame` `valid=True` with no OIIO** —
  `python/synapse/server/handlers_render.py:1316`. Pixel checks (black/NaN/clip/firefly)
  never run; headline boolean is `True` if the file merely opens. Caveated by
  `summary` + `oiio_available:False`, but a consumer keying on `valid` reads a bad
  frame as good. Should return `valid:"unknown"` on the unmeasured branch.
- **S-P1e · `render_preflight` guessed 64 GB RAM as fact** —
  `python/synapse/panel/render_preflight.py:615`. `sys_ram_gb = 64.0` when psutil
  absent, printed to the operator as the system's RAM (Joe's host is 128 GB → doubly
  wrong; can false-warn or false-pass). This is the "a5 defect" `cache_host_probe.py:24`
  cites as pattern-not-to-repeat, still live.

### Destructive-op gate bypass
- **S-P1f · `sleep_pass` "gated APPROVE" bypassed on bridge-failure fallback** —
  `python/synapse/server/handlers_memory.py:486-495`. The permanent memory prune
  routes through the bridge on the happy path (gate can fire), but `ImportError` and
  bare `Exception` both fall back to `_do_prune()` **direct**, ungated. Description
  (`_tool_registry.py:1171`) asserts "gated APPROVE" unconditionally. Guarded today by
  single-user localhost auto-approve + no-op under the default jsonl backend (only
  bites when Moneta is active).

### Catalog absence — no per-build parameter-name gate (TARGET 3)
- **S-P1g · parm names gated reactively only; builders silently no-op on drift.**
  `set_parm`/`get_parm`/`set_keyframe` resolve the name against the **live node**
  (`handlers.py:1126`, `:1056`; `handlers_render.py:1156`) and raise loudly on a miss
  (`ParameterError` + `_suggest_parms`, `handler_helpers.py:240`) — but that needs an
  instantiated node and fires *after* the op. **Worse:** the builders guard with
  `if p:` / `is not None` and **silently drop** a phantom parm, reporting the
  material/COP/render "built" while the value sits at default:
  Karma `handlers_render.py:2519` (docstring admits silent skip), render overrides
  `:1225`, material `handlers_material.py:573`, COPs `handlers_cops.py:1207`,
  solaris graph honest-post-hoc `handlers_solaris_graph.py:104`.
- **S-P1h · frozen H21 punycode map live-consumed by set_parm.**
  `python/synapse/core/usd_punycode.py:46` (map), `core/aliases.py:171`
  (`USD_PARM_ALIASES`), consumed at `handlers.py:1124`. Docstring itself: *"MUST be
  re-verified on a USD bump (H22)"*; all entries live-probed off `domelight::3.0` on
  **21.0.671**. On H22, `SUPPORT_MATRIX.md:9` records 266 apex parm deltas — the parm
  surface has drifted. **Whether any specific encoding is phantom on live H22 is
  UNKNOWN (live parm-walk required) — the structural staleness is CERTAIN.**
- **S-P1i · real parm-catalog seeds exist but are UNWIRED, and the Parm Gate is
  absent on this branch.**
  - `harness/notes/verified_nodetype_catalog_21.0.671.json` carries per-type `parms`
    lists but is read only in comments (`aliases.py:197`) — never at runtime, and
    pinned to H21.
  - `harness/notes/h22_cop_catalog_live_22.0.368.json` carries per-type `parms` for the
    target build, but its only reader `scout_eval.py:258-278` extracts **type** names
    and ignores `parms`.
  - The LOP live catalog omits parms entirely (`scripts/harvest_lop_catalog.py:45`
    `_FIELDS`).
  - The full solution (`scripts/build_node_catalog.py` → `rag/catalog/`, and the
    `gated_set`/ParmGate) is designed in `harness/autorevise/missions/w5m_catalog.json`
    and was built on other branches — but is **absent from `wave8/struth`**:
    **first-hand verified** — `build_node_catalog.py` absent, `rag/catalog/` absent,
    `grep -E "gated_set|ParmGate"` → **0 files**. The mission file is the only trace.

### Build-stamp staleness (TARGET 2)
- **S-P1j · rulebook runtime baseline pinned to uninstalled builds, freshness
  unenforced by test.** `rulebook/manifest.json:4-5` = graphical **21.0.671** / hython
  **21.0.631** / py **3.11** (live = 22.0.400 / 3.13). The only test touching it
  (`tests/rulebook/test_rulebook_meta.py:123`) asserts **key presence only**, never
  value-vs-build — so the baseline can drift arbitrarily far and stay green.
- **S-P1k · per-major CONTEXT catalogs carry a 368-vs-400 point-release drift that is
  ungated.** `connectivity_22.json` (stamp 22.0.368) and `lop_solaris_knowledge_22.json`
  (22.0.368 probe) load on a 22.0.400 host with no staleness signal, because
  `core/wiring.py:86-89` (and mirror `lop_knowledge.py`) select by **major only** and
  check schema+blake2b, never `houdini_version` vs running build. Only scout's symbol
  table has a point-release gate (`scout.py:737`, panel `gate_stamp.py:29`). The 368
  stamps are **test-pinned** (`test_wiring_major_resolution.py:70`,
  `test_lop_major_resolution.py:92`) — regenerating on 22.0.400 to match the symbol
  table would break green tests.
- **S-P1l · `h21_symbol_table.json` served WARN-not-refuse off-host.**
  `python/synapse/cognitive/tools/data/h21_symbol_table.json` (stamp 21.0.671) is
  scout's default fallback when no running major; on-host mismatch degrades verdicts to
  None (enforced), but off-host (CI/standalone) it is served as membership authority
  with only a warning (`scout.py:751-758`).

### PDG failure rollback is dead (honestly reported) — UNKNOWN on the raise
- **S-P1m · `dirtyAllTasks(remove_files=...)` phantom kwarg.** `shared/bridge.py:2318`.
  Per `CLAUDE.md §1.7` the live 22.0.368 signature is `dirtyAllTasks(remove_outputs)`,
  so the failure-rollback call raises `TypeError` every invocation → the rollback is
  dead. The code is **honest** about it (`dirtied=False`, reports "TASKS NOT DIRTIED").
  **Status UNKNOWN** — confirming the raise needs a live PDG cook; not re-run here.

---

## P2 — polish (doc drift, cosmetic, low blast radius)

- **S-P2a · `session_fidelity`=1.0 vs `success_rate`=0.0 on a zero-op session** —
  `shared/bridge.py:2834` vs `:914-917`. Two surfaces disagree on the empty case;
  neither abstains. Panel renders the 0.0 as a red "0% (0 ops)" bar
  (`agent_health.py:174-183`).
- **S-P2b · live envelope `fidelity=1.0` on `hash_unavailable`** —
  `integrity_envelope.py:263-281`. On a scene-hash capture miss both hashes are empty
  but fidelity stays 1.0; honesty lives in the sentinel + empty fields, not the number.
  A reader taking fidelity=1.0 as "scene delta verified" is misled.
- **S-P2c · standalone `_execute_direct` hard-sets anchors True** —
  `shared/bridge.py:1769`. Documented test posture (only when `_HOU_AVAILABLE` False);
  fidelity=1.0 means "no hou to check," a didn't-check pass. Labelled, not measured.
- **S-P2d · Prometheus always-on zero gauges** — `python/synapse/server/metrics.py:102,112`.
  `circuit_breaker_state` (default closed→0) and `memory_entries` (0) always emitted.
  Prometheus-conventional but a fabricated zero by R162 (scene/histogram sections are
  honestly gated behind `if live_snapshot:` / count>0).
- **S-P2e · COPs/scene GROUP_KNOWLEDGE "safe rollback" / "automatic rollback" overclaim**
  — `mcp_tools_cops.py:25`, `mcp_tools_scene.py:15`. Same false-rollback shape as P0-2,
  but the sentence sits past char 200 and the served group blurb truncates at
  `knowledge[:200]` (`mcp_server.py:1088`), so it does **not** reach the model — lives
  only in the module string. Hence P2 not P0.
- **S-P2f · `tops_cook_and_validate` "Self-healing" default-off** —
  `_tool_registry.py:494`. Description says "automatic retry ... Self-healing," but
  `max_retries` defaults to 0, so the retry/dirty branch never fires by default
  (`diagnostics.py:89`). Behavior claim contradicted by its own default.
- **S-P2g · statusline fabricated-0 decisions** — `harness/statusline.py:270`.
  `decision_count()` returns 0 on any exception → "nothing awaiting a human," the exact
  fabricated-zero the same file polices elsewhere. Developer statusline, not artist-facing.
- **S-P2h · TOPS `getattr(wi,'cookTime',0.0)`** — `handlers_tops/work_items.py:225`,
  `diagnostics.py:155`. A missing/phantom `cookTime` attr coerces to 0.0 into
  `total_cook_time`. Whether `pdg.WorkItem.cookTime` exists on 22.0.400 is **UNKNOWN**
  (live PDG required).
- **S-P2i · `apex_probes.py` H21 seed** — `python/synapse/science/apex_probes.py:4,9`.
  Seed corpus stamped/re-seeded to **21.0.671** (uninstalled); no build-freshness gate
  reads it (science-loop seed). Honest-in-prose but presented as the current APEX
  authority — the mission's named "H21-on-apex_probes" seed class.
- **S-P2j · CLAUDE.md 368/400 header-vs-body split** — `CLAUDE.md:3` (target 22.0.400)
  vs `:119,:379` (live 22.0.368). The single doc source of the 368/400 ambiguity that
  ripples through every stamped data file. Doc, not code.
- **S-P2k · assess_render_ready / SUPPORT_MATRIX / bridge topo-hash — enforced,
  logged for completeness.** `solaris_compose_tools.py:602` (bounded at max_prims=5000,
  minor over-claim on >5000-gprim stages); `shared/bridge.py:1055` (cookCount is
  change-detection, a 0 is never read as "cooked" — not a defect).

---

## UNKNOWNs (unobtainable headless — recorded UNKNOWN, never zeroed)

1. **Which 22.0.x is actually installed** (22.0.400 vs 22.0.368). Latest concrete
   evidence (`cache_h22_contract_assay_22.0.400.json` cites the 22.0.400 hython path;
   22.0.400 symbol table) points to 22.0.400; older probes cite 22.0.368. Definitive =
   gui/live host required.
2. **Whether any frozen-H21 punycode encoding is phantom on live H22** (S-P1h) — live
   parm-walk required.
3. **Whether `dirtyAllTasks(remove_files=...)` raises on 22.0.400** (S-P1m) —
   documented-verified elsewhere (`CLAUDE.md §1.7`, 2026-07-26), not re-run here.
4. **Whether `pdg.WorkItem.cookTime` exists on 22.0.400** (S-P2h) — live PDG required.
5. **Whether tops_cook_node masks a real all-failed cook in practice** (P0-1 repro) —
   the static defect is certain; a live reproduction needs a live PDG cook.

## Provenance
Recon workflow: `wf_ca130024-63e` (5 cartographer agents, read-only, 0 errors,
639k tokens). Every anchor above independently re-read by the leg. Full agent maps:
the workflow journal under the session transcript dir.
