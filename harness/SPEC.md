# SPEC.md — H22 Gap-Blueprint Harness

> **Governs:** execution of `docs/SYNAPSE_H22_GAP_BLUEPRINT.md` (v2.0).
> **Companion to:** the blueprint (the *what* — the gaps) — this is the *how* (the harness that runs them).
> **Status (2026-07-12):** MODE A. `harness/state/drop.json` absent. **RECONCILE-ONLY** — the harness is
> built and shipped; v2 needed a reconciliation layer, not a subsystem. Assembled, not yet fully run.
> **Operational playbook:** `docs/H22_AGENT_HARNESS.md` (dispatch protocol, failure modes) — not duplicated here.

---

## 0 · Why this file exists

The blueprint defines the gaps (G1–G9), principles (P1–P7), and legs (0–3). The harness that runs it was
built for blueprint **v1.0** across four commits (`3c2076b` … `42f32ba`). v2.0 added **P7**, **G9**, **C3**,
the **§10** standing protocol, and four refinements. A reconnaissance sweep (10 parallel readers + adversarial
synthesis, 2026-07-12) returned one verdict: **the harness already runs v2 — all four Phase-0 specs exist and
match v2 shape, the 10-agent / 6-workflow team maps 1:1 to §11 / Legs 0–3 / §9 / §10, and P7→G9 plus §10 intake
are already operationalized.** What v2 genuinely lacked was **an authority that maps each gap to its in-repo
artifact** (so both engines and all agents can answer "does the harness run G4?" against a spec, not memory) and
**a cross-leg relay**. This file is that authority. §4 is the crosswalk; §6 is the relay.

**First principle applied:** *never rebuild shipped code* (blueprint §11; global CLAUDE.md "Surgical changes").
Everything in §4 marked ✅ is do-not-touch.

---

## 1 · Recommended shape (two engines + one human orchestrator + one relay)

The harness is deliberately **two decoupled engines** joined at a **human seam**, not one monolith. This is a
solo-dev-correct choice, not an oversight — the seam is where `drop.json`, `ratified`, and merge-to-main live (P4).

```
                         ┌─────────────────────────────────────────────┐
   HUMAN ORCHESTRATOR ──▶│ the main Claude Code session (the CTO)        │
   (you, per playbook §0)│  routes work by class; owns every gate        │
                         └───────────────┬───────────────┬──────────────┘
                                         │               │
                    ┌────────────────────▼──┐        ┌───▼───────────────────────────┐
                    │ ENGINE 1: run.ts       │        │ ENGINE 2: .claude/workflows/  │
                    │ headless grinder       │        │ interactive blueprint executor│
                    │ tasks.json · WIP=1     │        │ 6 dynamic workflows fanning to│
                    │ worktrees · checks.py  │        │ 10 role-constrained agents    │
                    │ Generator→checks→Eval  │        │ agent()/parallel()/pipeline() │
                    │ completion ledger      │        │ adversarial verify→revise→re- │
                    │ suite ratchet (4118)   │        │ verify; gate-refuse in-band   │
                    │ tracks: 0.x 1-3.x      │        │ ── NEW: h22-relay chains legs │
                    │ U/V/C/S/D/R            │        │    A→A and B, halts at gates  │
                    └────────────────────────┘        └───────────────────────────────┘
                    owns: mechanical readiness         owns: blueprint Legs 0–3, §9, §10, §11
                    (armed by state-file predicates)   (dispatched per work class)
```

- **Do not merge the engines.** No `run.ts`↔workflow bridge. `tasks.json` (readiness tracks) and the blueprint
  gaps (G1–G9) are **separate programs** that share state files under single-writer rules (playbook §0).
- **The orchestrator is human by design.** "Autonomous cross-leg driver" is explicitly *not* the goal — the
  human-in-the-loop seam at `drop.json`/merge is the P4 guarantee made physical.
- **The relay (§6) is the only v2 structural addition** — it upgrades "orchestrated-within-a-leg, human-glued-
  across-legs" into "one command drives the current-MODE spine and stops at the next human gate."

---

## 2 · Primitives & subsystem boundaries

| Primitive | Where | Rule |
|---|---|---|
| **Gate state** | `harness/state/{drop.json, posture.json, flywheel_queue.json, leg0_baselines.json}` | Single-writer: humans write `drop.json` + `ratified:true`; the harness appends `ratified:false` candidates only; gatewarden reads, never writes. |
| **Deterministic guardrails** | `harness/verify/checks.py` (~65 checks / 75 slugs) + `suite_baseline.json` (ratchet floor **4118**/0/87) | run.ts's gate layer. Ratchet floor read at merge-base(master,HEAD) — a sprint cannot lower its own bar. |
| **Runtime truth** | `python/synapse/cognitive/tools/data/h21_symbol_table.json` (33,255 syms) + `scripts/h22_api_delta.py` + `synapse_scout` | `dir()` symbol table is the membership authority (P1). Regenerate per Houdini build (P6). |
| **Agent roster** | `.claude/agents/*.md` (10, hard cap) | 4 permission bands: TRUTH · TRUST · PAPER · BUILD. Each line is a permission boundary (playbook §1). |
| **Dynamic workflows** | `.claude/workflows/h22-*.js` (6 legs + **1 new relay**) | Builders ≠ reviewers; closed gate refuses (never skips); every step yields an artifact; nothing writes `ratified:true`. |
| **Paper artifacts** | `docs/` (specs, intake, reviews) + `harness/notes/` (track specs) | scribe/adjudicator/docsurgeon territory; merge-to-main is the human gate that makes any of them binding. |

---

## 3 · The 10-agent team (roster is the permission model)

Full table in playbook §1. The split exists so **no agent can both authorize and consume a gate**, **no builder
self-certifies**, and **the public claim surface is walled off from code**:

- **TRUTH** — `cartographer`, `librarian` (map), `assayer` (live-runtime V1 probe), `prospector` (candidate contracts).
- **TRUST** — `crucible` (adversarial review, builds nothing), `h22-gatewarden` (read-only gate oracle, flips nothing).
- **PAPER** — `h22-scribe` (specs + baseline freeze → `docs/`,`harness/notes/`), `h22-adjudicator` (§10 intake → `docs/intake/`).
- **BUILD** — `h22-forge` (gated build in worktrees; refuses any dispatch lacking a verbatim gatewarden ALLOW), `h22-docsurgeon` (README/docs only).

---

## 4 · Reconciliation crosswalk — the authority (blueprint ↔ in-repo artifact)

Every G1–G9, P1–P7, §10, §11 mapped to the artifact that discharges it. This is what an agent reads to answer
"does the harness cover X?" **✅ = present, do-not-touch. ◻ = spec-only / MODE-B-gated. ⚠ = genuine v2 delta.**

### Gaps

| Gap | Blueprint intent | In-repo artifact(s) | Mode | Status |
|---|---|---|---|---|
| **G1** Port debt | legacy-path tools → Dispatcher, by wave | `docs/PORT_WAVE_MANIFEST.md` · `.claude/workflows/h22-port-wave.js` | B | ✅ spec merged · ◻ build MODE-B-gated |
| **G2** H22 re-grounding | re-litigate quarantine at drop | `.claude/workflows/h22-drop-week.js` (§9) · `drop.json` gate · `leg0_baselines.json` (frozen left side) | B | ✅ runbook armed · awaits `drop.json` |
| **G3** Host truth | symbol/node tables per build | `h21_symbol_table.json` · `scripts/h22_api_delta.py` · `check_phantom_clean` · `check_tops_path_untouched` | A | ✅ **LIVE — strongest track** |
| **G4** MCP provider posture (D-H22-1) | first-party vacuum; thin adapter over ported tools | tasks `0.8`/`0.9` (scaffold) · `2.7`/`2.8`/`1.7` (live, MODE B) · `check_mcp_registered`/`_surface_probe`/`_truth_contract` | A→B | ✅ scaffold + checks · ◻ live gated |
| **G5** Scene-grounding contract | 4 read-only manifest tools | `docs/SCENE_GROUNDING_CONTRACT.md` | A→B | ✅ spec merged · ◻ build MODE-B |
| **G6** Numbers | latency/token/memory tracks | `docs/BENCHMARK_DESIGN.md` · `_benchmark_api.py`/`_benchmark_latency.py` | B | ✅ spec merged (Shot-010 + G6b) · ◻ execution unbuilt |
| **G7** Doc drift | auth · framing · badge · loopback · C3 | `h22-docsurgeon` · `h22-leg0.js` §5 | A | ⚠ **PARTIAL** — badge stale (4186→**4118**), loopback sentence missing, **C3 OPEN (§8)** |
| **G8** H22 surface intake | new node types via flywheel, `ratified:false` | `flywheel_queue.json` · `h22-drop-week.js` step-4 sweep · `authoring_domains.json` (rigging refused) | B | ✅ armed · awaits drop + ratify |
| **G9** Pre-flight gate (P7 operational) | 2-pass admission before mutation | `docs/PREFLIGHT_GATE.md` (Pass 1 structural over U.1 catalog + Pass 2 COP conformity) | B | ✅ spec merged · ◻ build MODE-B (COP pass blocks on G2 COP re-audit) |

### Principles

| Principle | Enforced by | Status |
|---|---|---|
| **P1** Runtime is ground truth | `synapse_scout` · `h21_symbol_table.json` · assayer V1 gate · `check_phantom_clean` | ✅ LIVE |
| **P2** Composition > serialization | USD substrate; G6 memory track is the pending proof | ◻ proof pending G6 |
| **P3** Reversibility = license to act | bridge `hou.undos` + `agent.usd` provenance + `check_ledger`/`check_revert_clean` | ✅ LIVE (revert_clean is an honest-false stub) |
| **P4** Human gates bound autonomy | gatewarden read-only · no agent writes `drop.json`/`ratified` · relay halts at every gate | ✅ STRUCTURAL |
| **P5** Judgment is the product | posture; not a tool-count race | ✅ posture |
| **P6** Verification is runtime-scoped | `leg0_baselines.json` freeze · quarantine re-litigation at drop (runbook step 3) | ✅ armed for drop |
| **P7** Validation precedes mutation | G9 `PREFLIGHT_GATE.md` · adjudicator "run each claim vs P1–P7" axis · product `GraphValidator` (`check_validator_catches_miswire`) | ✅ spec + product-side live · ◻ admission wrapper MODE-B |

### Standing protocols

| § | Blueprint intent | In-repo artifact | Status |
|---|---|---|---|
| **§10** Intake protocol | one-page adjudication per inbound artifact; never re-version the blueprint | `.claude/workflows/h22-intake.js` · `h22-adjudicator.md` · crucible Attack phase | ✅ **WIRED · unexercised** (no `docs/intake/` yet — run-once, not a build gap) |
| **§11** Open verifications | resolve INFERENCE-tier claims against the repo | `.claude/workflows/h22-ground-truth.js` (8 probes) | ✅ LIVE |

---

## 5 · Gate registry → concrete files (blueprint §8 made mechanical)

Full mechanical table in playbook §2. State right now:

| Gate | Concrete check | State (2026-07-12) |
|---|---|---|
| `drop.json` | `harness/state/drop.json` exists + parses | **CLOSED** (absent → MODE A) |
| Flywheel ratification | `flywheel_queue.json` per-cycle `ratified` | U.1/U.5/D.0/S.0 ratified; V/R held |
| Merge-to-main | no file — always human, per commit | human |
| Posture | `posture.json` (present → solo/auto-approve) | **OPEN** for S-track |
| gate-0.1 (sidecar) | `drop.json.python != cp311` re-opens it | conditional on `drop.json`; decided → sidecar (`50a135d`) |
| D-H22-1 / D2 | decision docs (`docs/SYNAPSE_MULTI_PROVIDER_*`) | unratified |
| G9 design review | `docs/PREFLIGHT_GATE.md` merged to main | ✅ merged → G9 MODE-B build unblocked at drop |
| Michael Gold RFC | any USD-schema write | off the critical path |

---

## 6 · The meta-relay (`.claude/workflows/h22-relay.js`) — the v2 cohesion piece

**One command that drives the blueprint in its current mode and stops at the next human gate.** Every workflow it
calls already existed; the relay only sequences them (verified: none of the 6 legs nest `workflow()`, so one-level
composition is legal) and halts where a human must act.

```
Orient  → h22-gatewarden (read-only) → { mode, posture, blueprintCommitted, leg0ArtifactsPresent, openGates }
Drive   → MODE A: h22-ground-truth (§11) → [leg0 if specs absent | h22-reverify drift-scan if present]
                  → optional h22-intake(artifact,slug)  ── read-only except a new docs/intake/ appendix
          MODE B: h22-drop-week (§9 steps 1–9, STOPS before step 10 ratify)  ── port waves stay human-dispatched
Report  → consolidated status + standing open decisions (incl. C3) + the single next human act
```

- **Idempotent in reconcile mode:** with the four specs merged, MODE A runs `h22-reverify` (adversarial drift-scan
  against HEAD), **not** `h22-leg0` — it verifies the reconciled state, it does not redraft merged work.
- **Halts, never crosses:** it returns before merge, before `drop.json`, before ratify. It cannot open a gate.
- **Surfaces C3 every run** until a human rules (see §8) — and instructs `h22-reverify` to *flag* the Moneta
  contradiction, never to *fix* it.
- **Launch:** `Workflow({ name: "h22-relay" })` — or with a pending document,
  `Workflow({ name: "h22-relay", args: { intakeArtifact: "<path|url>", intakeSlug: "coprocessor-whitepaper" } })`.

---

## 7 · MVP boundary & phases (blueprint Legs 0–3)

- **Live now (MODE A):** `h22-relay` → orient → ground-truth → reverify → (optional) intake. Leg 0 is complete:
  blueprint committed (Mile 0), four specs + baselines frozen (Mile 0.3), G7 *partially* fixed (Mile 0.1 — see §8).
- **One human file-write away (Leg 1):** write `harness/state/drop.json {houdini,python,usd,pyside,hython}`. That
  is the *entire* leg. It flips MODE B.
- **Armed for drop week (Leg 2):** `h22-relay` in MODE B → `h22-drop-week` §9 steps 1–9; ratify at step 10 (human).
- **MODE B build order (Leg 3):** G1 port waves → G4 MCP surface → G5 grounding tools → G9 gate (structural pass
  first, COP pass after the G2 COP re-audit) → G6 numbers → Mile 6 hostile perception crucible → sentinel → G8 intake.
- **Not in this harness (human-at-GUI):** Mile 5 (Spike 3.3 live perception on H21) · G6 benchmark *execution*
  (author only after `BENCHMARK_DESIGN.md` survives crucible — write the spec before the meter) · sentinel build.

---

## 8 · Open decisions (surfaced, not resolved — human/CTO rulings)

1. **C3 — the "Moneta" naming contradiction. [SHARPEST — blocks the G7 doc fix]**
   The blueprint C3 rider says Moneta is the *Nuke inside-out host* and must **not** be described as a memory
   service. But SYNAPSE's own surface contradicts this: `README.md:322-348` describes *"Moneta … a private,
   encrypted memory substrate (repo `JosephOIbrahim/Moneta`)"*, `SYNAPSE_MEMORY_BACKEND=moneta` selects it, and
   `python/synapse/memory/moneta_store.py` + `moneta_runtime.py` **ship it as the memory backend**. (Note
   `README.md:273` *does* use the Nuke-host framing — `Moneta/Nuke` — so the README is internally split.)
   **A blind docsurgeon cut per C3 would make the README contradict the shipped code.** Ruling needed:
   **(a)** narrow C3 to the Nuke-host referent and keep the `moneta` memory backend named as-is, or
   **(b)** rename the shipped backend away from "Moneta." Route via `h22-intake` (adjudicate the C3 rider vs
   shipped reality) or a direct CTO ruling. **Until then: no doc surgery on the Moneta lines.**
   **RESOLVED (2026-07-12, CTO — "one Moneta"):** `docs/reviews/h22-c3-moneta-decision.md`. Code proves Moneta
   **is** the shipped memory backend (`moneta_store.py`; live recall keyword, vector staged in shadow), so C3 as
   written was factually wrong. Ruling: Moneta keeps the name (the memory substrate); the Nuke inside-out host is
   a separate, differently-named product. Corrected rider = cognitive *state* ≠ vector similarity (Non-Goal 6).
   Applied: `README.md:273` corrected · guardrails softened · blueprint → v2.1 C3 correction. No open C3 action.

2. **G7 residuals (independent of C3, safe now).** README test badge `4,186` → ratchet floor **`4118`**
   (`README.md:364`; re-derive from `suite_baseline.json`, never copy). Add a loopback-only ingress sentence to the
   MCP/WS surface (grep confirms none present). Both are on the docsurgeon worklist; merge-to-main is the gate.

3. **§10 first exercise.** The intake protocol is wired but has produced zero appendices (`docs/intake/` absent).
   Running it on the co-processor whitepaper (the artifact that drove v2) both proves the protocol and produces
   the C3 adjudication in #1. `Workflow({ name: "h22-relay", args: { intakeArtifact, intakeSlug } })`.

4. **Optional MODE-B pre-staging.** `checks.py` has no G9/P7 pre-flight slug and no C3 guardrail (they live only
   in the agent permission layer). Correct-by-design deferral: G9 is MODE-B, §10 is agent-enforced. When C3 is
   ruled, add one cheap `check_c3_moneta_surface` guardrail so run.ts fails loud on regression.

---

## 9 · Verification & acceptance (defined before first dispatch)

Permission-boundary smoke tests (E1–E5) and golden tasks (G1–G3) are in playbook §6. Acceptance for **this
reconciliation layer**:

- **Blueprint committed:** `docs/SYNAPSE_H22_GAP_BLUEPRINT.md` exists and matches the v2.0 text.
- **Crosswalk true:** every ✅ row in §4 resolves to a real file (spot-check: the four specs, the six workflows,
  `h21_symbol_table.json`, `suite_baseline.json`).
- **Relay honest:** `Workflow({name:"h22-relay"})` in MODE A returns `MODE_A_VERIFIED`, writes nothing but a
  possible `docs/intake/` appendix, re-surfaces the C3 open decision, and halts before any merge/drop/ratify.
- **Relay refuses forward:** with `drop.json` still absent, the relay never runs `h22-drop-week` or `h22-port-wave`.
- **No autonomy leak:** after any MODE-A relay run, `git diff` touches only `docs/`, `harness/notes/`,
  `harness/state/leg0_baselines.json`, `README.md` — and no diff anywhere contains `ratified:true`.

---

## 10 · How to run it

The orchestrator is the human CTO session (playbook §0). Launch sequence:

1. **(done)** Commit the blueprint (Mile 0) + this SPEC. Merge is yours.
2. Smoke the boundaries (cheap): E1 (forge with no verdict → REFUSED), E2 (gatewarden MODE-B item, no drop → REFUSE), E4 (docsurgeon asked to touch `python/synapse/` → decline).
3. **`Workflow({ name: "h22-relay" })`** — drives the MODE-A spine, returns the consolidated status + open decisions.
4. Resolve **C3** (§8 #1). Then apply the safe G7 residuals. Merge each artifact (your gate).
5. **Leg 1 (H22 install day):** write `harness/state/drop.json`. Re-run `h22-relay` → it now drives drop-week. Ratify at §9 step 10 yourself.
6. **Leg 3 (per ratified wave):** `Workflow({ name: "h22-port-wave", args: { wave: "<family>" } })`.

> **Model note:** the interactive engine (§1 Engine 2) is Claude-agent-team work — run it on **Opus 4.8**.
> The headless grinder (`run.ts`) picks its own model per its config; leave it.

---

*SPEC v1.0 — assembled 2026-07-12 under MODE A as the v2 reconciliation authority. This document is itself a
Leg-0 paper artifact; merge-to-main is the human gate that makes it binding.*
