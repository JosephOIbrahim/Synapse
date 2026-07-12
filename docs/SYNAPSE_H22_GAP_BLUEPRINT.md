<!--
  HARNESS METADATA (not part of the blueprint text):
  Committed to docs/ 2026-07-12 as blueprint §7 Leg-0 Mile 0 (F3 — "commit this blueprint before any
  execution it governs"). Verbatim v2.0 as authored; the text below is unmodified.
  Companion spec (the harness that runs this): harness/SPEC.md.
  v2.1 correction (2026-07-12): C3 corrected inline (one-Moneta ruling) — see §1 + docs/reviews/h22-c3-moneta-decision.md.
  Executor playbook: docs/H22_AGENT_HARNESS.md. Reconciliation crosswalk: harness/SPEC.md §4.
-->

# SYNAPSE_H22_GAP_BLUEPRINT — v2.0

**Status:** MODE A · Phase-0 (paper/design) · F3-compliant — committed before any execution it governs.
**Supersedes:** v1.0 (2026-07-11, same day). v2 is standalone; v1 is retained in history only.
**Scope:** Gap closure between SYNAPSE (master, pinned Houdini 21.0.671 / hython 21.0.631) and the Houdini 22 release horizon.
**Window:** H22 keynote 2026-06-22; public release expected mid-July 2026 — potentially days from authoring (2026-07-11).
**Revision cause:** Adjudication of an external "Synapse co-processor" technical whitepaper (July 2026, provenance unconfirmed, synthesis-shaped). Deltas from v1: one new principle (P7), one new gap (G9), four refinements, one correction (C3), one standing protocol (§10). Everything else survived contact unchanged.

---

## Provenance & evidence tiers

| Tier | Meaning |
|---|---|
| **VERIFIED-WEB** | Confirmed via live fetch/search on 2026-07-11 (repo master README + file tree, SideFX/press/community sources). |
| **VERIFIED-RUNTIME** | Confirmed via live probe against H21.0.671 in a prior session. Version-pinned; expires at H22 drop (P6). |
| **INFERENCE** | Carried from prior working sessions; not re-anchored this pass. Each is one local `ls`/grep away — verify at commit. |
| **UNVERIFIED** | Claim from an input document, not independently confirmed. |

**Inputs:** (a) July-2026 Houdini+AI ecosystem dossier (external, corrected in v1); (b) "Synapse: A Stateful, In-Process AI Co-Processor Architecture" whitepaper (external, adjudicated in §3); (c) `github.com/JosephOIbrahim/Synapse` master, fetched 2026-07-11; (d) H22 keynote coverage (SideFX, CG Channel, DIGITAL PRODUCTION, daily.dev, SideFX forums); (e) prior-session repo state.

---

## 0 · Definition of done

1. Committed to `docs/` on master (F3).
2. Each gap G1–G9 has a named Phase-0 deliverable, a governing gate, and a relay leg.
3. The drop-week runbook (§9) is executable by a human + Claude Code pair with no design decisions left open.
4. The intake protocol (§10) is in force for all future external research artifacts.

Execution of the gaps is **not** part of done. MODE A holds until `drop.json`, except items marked **paper** or **human-at-GUI**.

---

## 1 · Corrections (cumulative)

**C1 — H22 has not launched. [VERIFIED-WEB]** Keynote 2026-06-22; release expected mid-July. Both external documents assert a completed launch; both are wrong. All "H22 shipped" reasoning reads as "H22 announced." The preparation window is real and short.

**C2 — No public evidence of a SideFX first-party MCP/agent surface. [VERIFIED-WEB]** APEX is the H22 *character* story (rigging, animation, retargeting, motion mixing with KineFX). Community demand for built-in agent connectivity is documented and unanswered on SideFX's own forum. Posture: plan for a first-party vacuum; confirm/deny at runbook step 7. The whitepaper is silent on first-party MCP, consistent with the vacuum.

**C3 — Moneta is the Nuke host, not a memory service. [VERIFIED-WEB — README portfolio section]** *New in v2.* The whitepaper reassigns "Moneta" to a decoupled vector-backed memory substrate. That is a confabulation. Moneta remains the planned Nuke inside-out host; the memory layer is the Cognitive Substrate / Cognitive Bridge. Recorded here so the misassignment doesn't propagate into any downstream doc, pitch, or search result. If a *named* telemetry service is ever wanted, it gets a new name — naming is Joe's call and out of scope here.

> **C3 CORRECTION — v2.1 (2026-07-12 · CTO ruling: "one Moneta").** Superseded on the memory point. Moneta **is** SYNAPSE's memory substrate (repo `JosephOIbrahim/Moneta`; shipped `moneta_store.py`; `SYNAPSE_MEMORY_BACKEND=moneta`) — the name is from Juno *Moneta* ("she who reminds"). The whitepaper's actual error was narrower: calling it a *vector-index* service. **Corrected rider:** cognitive **state** is deterministic USD/LIVRPS, never vector similarity (Non-Goal 6); "Moneta" names the memory layer, **not** a DCC host; the Nuke inside-out host is a separate, differently-named product. Full ruling + evidence: `docs/reviews/h22-c3-moneta-decision.md`.

---

## 2 · First principles

If a proposed work item can't be traced to a principle, it's scope creep — reject it.

**P1 — The runtime is the only ground truth.** No `hou.*` / `pdg.*` symbol is trusted without live introspection against the pinned runtime. External documents are V0 at best — including documents bearing the product's own name.

**P2 — Composition beats serialization.** The ecosystem grounds LLMs by dumping serialized scene state into prompts and recalls memory by vector similarity. SYNAPSE grounds through in-process introspection and recalls through deterministic USD/LIVRPS composition. The bet still lacks published numbers (→ G6).

**P3 — Reversibility is the license to act.** Every mutating action undo-wrapped, provenance-recorded. No surveyed competitor does this; the whitepaper correctly reproduced the *concept* (`hou.undos` rollback), confirming it is the legible half of the trust story.

**P4 — Human gates bound autonomy.** `drop.json`, flywheel ratification, merge-to-main: never automated. This blueprint adds no automation across any gate.

**P5 — Judgment is the product; the render is its proof.** Not a tool-count race. A truth race (P1), a trust race (P3), and now — with the thesis going consensus-legible (§3, Reflection) — a *shipping* race.

**P6 — Verification is runtime-scoped.** Every VERIFIED-RUNTIME claim is pinned to 21.0.671. A major version release is the single legitimate re-litigation event for quarantined APIs. At H22 drop, the whole quarantine re-enters probe scope exactly once, then re-pins.

**P7 — Validation precedes mutation.** *New in v2, harvested and generalized from the whitepaper's one genuine architectural contribution.* The truth contract defends at three points, in order: symbols are probed before use (P1); **proposed graphs are validated before any node exists** (P7); transactions roll back on violation (P3). Refuse-before-failure beats roll-back-after-failure. The rulebook for P7 already exists: the U.1 connectivity catalog, pointed backward — from generation aid to admission gate. (→ G9.)

---

## 3 · Adjudication — the co-processor whitepaper

**Character of the document:** synthesis-shaped, provenance unconfirmed, seeded with SYNAPSE's public materials. It reproduces everything the README states (in-process, undo transactions, USD memory, co-processor framing) and substitutes the ecosystem default for every mechanism it cannot see: `hwebserver` for the daemon, vector similarity for LIVRPS, a 2-second polling thread for event-push perception, and rigging inside scope. Followed as written, it rebuilds SYNAPSE into a generic outside-in bridge wearing the product's name.

| # | Whitepaper claim | Actual | Verdict |
|---|---|---|---|
| 1 | In-process execution layer reading live `hou` | Matches shipped daemon + Dispatcher [VERIFIED-WEB] | **CONVERGENT** |
| 2 | `hwebserver` bridge (port 9191) as primary entry point | In-process dispatch is the architecture; WS is a thin migration adapter; hwebserver core migration = Non-Goal 4. Whitepaper's own RPC sample mutates the graph with **no main-thread marshaling** — the bug class `hdefereval`/the executor exist to prevent | **REJECT** mechanism |
| 3 | Moneta = memory service with vector index | C3. Cognitive state is USD/LIVRPS, deterministic; vector-graph similarity is the competitor category | **CORRECT + REJECT** |
| 4 | Async session-telemetry streaming to background store | Real counterpart: FTS5/BM25 execution-trace sidecar, deliberately distinct from cognitive state [INFERENCE] | **ADAPT** → sidecar spec sharpened (G6b) |
| 5 | "Revert lookdev to Shot 010's layout, keep current point-cloud density" | Append-only turn history + rollouts-as-sibling-prims already enable it [VERIFIED-WEB]. Only composition answers it cleanly; similarity returns "something about Shot 010" | **ADOPT** → flagship demo + benchmark scenario (G6) |
| 6 | `hou.undos` transaction isolation, rollback on validation failure | Convergent with the reversibility guardrail [INFERENCE + README posture] | **HOLD** |
| 7 | Copernicus Dual-Pass Pre-Flight Compiler (resolution + OCIO conformity, auto-injected fix nodes) | No equivalent named capability; U.1 catalog is the natural rulebook | **ADOPT, generalized** → **G9** |
| 8 | TOPs 3DGS training orchestration; `top::gaussian_splat_train` | Posture fits G8 (orchestrate, never author); node names are phantom-shaped [UNVERIFIED] — intake via re-sweep only | **ADAPT** → G8 candidate, `ratified:false` |
| 9 | APEX rigging: IK chains, constraints, Rig Pose configuration via MCP | Enforced drift term. Structurally dead. v1 predicted the boundary pressure; it arrived one revision later wearing the product's name | **REJECT** — guardrail re-affirmed (§6) |
| 10 | PredictiveDriftHarness: daemon polling thread, 2s interval, audit body `pass` | Event-push perception exists: two bridges, 71 hostile tests, Mile 5 from live [VERIFIED-WEB]. Polling loses on latency, cost, and thread-safety (their loop would touch `hou.*` off-main) | **REJECT** mechanism; **ADOPT** audit checklist into the sentinel seed (G3) |
| 11 | H22 has launched | C1 stands — second document carrying the error | **CORRECT** |
| 12 | Three-phase studio rollout; loopback-only security posture | Useful *adoption* narrative (v1 legs = development sequencing; phases = deployment sequencing); loopback-only is cheap explicit hardening language | **ADOPT framing** → G4, G7 |

Noise: "viewport systems like CarWash" — unrecognized against all verified sources; dropped.

**Reflection (recorded because it changes priority, not just posture):** two independent syntheses in one week converged on the stateful in-process co-processor thesis. The thesis is now consensus-legible. Validation, and a countdown: ideas this reproducible in synthesis get implemented by others. The differentiation window for "inside-out + stateful" as a *claim* is finite; the durable position is inside-out + stateful as *shipped, measured fact*. This raises G1 (ports), G3 (Mile 5/6), and G6 (numbers) relative to all further paper. Corollary moat signal: the whitepaper correctly reproduced exactly the README-stated concepts and mangled exactly the non-obvious mechanisms (LIVRPS-as-mechanism, event-push perception, scope discipline) — consistent with the IP posture that concepts are public and mechanisms are not reconstructible from public material.

---

## 4 · Ecosystem delta map

Unchanged from v1 except row 11 gains the whitepaper as corroborating absence-evidence. Reproduced for standalone completeness.

| # | External claim | Verified reality (2026-07-11) | SYNAPSE position | Verdict |
|---|---|---|---|---|
| 1 | H22 launched | Keynote 6/22; release ~mid-July [VERIFIED-WEB] | Pinned to H21.0.671 | **CORRECTED** → G2 |
| 2 | Grounding = serialize topology + attrs + parms + errors | Ecosystem-standard recipe [VERIFIED-WEB] | `synapse_inspect_stage` ported; manifests not first-class [VERIFIED-WEB] | **GAP** → G5 |
| 3 | `hwebserver` is the standard bridge | FXHoudiniMCP: hwebserver + hdefereval [VERIFIED-WEB] | In-process daemon; WS thin adapter [VERIFIED-WEB] | **HOLD** — their ceiling is the floor |
| 4 | Mature MCP servers (35–179 tools) | oculairmedia 43 · Conare 35 · FXHoudiniMCP 179/22 categories, PyPI, live integration suite [VERIFIED-WEB] | 104 registry tools on legacy WS path; **1** through Dispatcher [VERIFIED-WEB] | **GAP** → G1, G4 |
| 5 | Prompt→HDA authoring exists (Rart) | Product on Gumroad [VERIFIED-WEB] | `rebuild_all_hdas.py` exists; prompt-driven authoring not known [INFERENCE] | **CANDIDATE** → G8b |
| 6 | H22 Copernicus ML expansion | Heightfields migrated SOPs→COPs; Copernicus as AI-orchestration platform; ripple solver, NCA, UV Shapes [VERIFIED-WEB] | 21 COP tools audited on H21 [INFERENCE] | **GAP** → G2, G8 |
| 7 | ML/rigging in KineFX+APEX | H22 headline is the character pipeline [VERIFIED-WEB] | `kinefx` enforced drift term | **NON-GOAL** — pressure confirmed (§3 row 9) |
| 8 | Background co-processor / drift analysis | Predicted by both external docs; no shipping product found | Perception channel scaffolded, 71 tests; Mile 5 = first live event, <50ms budget [VERIFIED-WEB] | **CONVERGENT** → G3 |
| 9 | Local-first LLMs, firewalled MCP | Trend consistent with studio IP posture | Harness v1; D2 unratified; DPAPI vault [INFERENCE] | **CONVERGENT** — D2 priority raised |
| 10 | (docs silent) | Full Vulkan viewport, OpenGL removed; native splats incl. rig/relight/render in Karma; Solaris layout/scatter procedurals [VERIFIED-WEB] | Panel is PySide/Qt; Solaris core scope | **RISK + INTAKE** → G2, G8 |
| 11 | (docs silent) | No competitor found doing undo-wrapping, provenance, USD-substrate memory, or pre-flight graph validation [VERIFIED-WEB absence; whitepaper corroborates by reproducing only the concepts] | Core differentiators, partially realized | **HOLD** — make legible via G6 |

---

## 5 · The gaps

Ordered by strategic weight. v2 changes marked **[Δ]**.

### G1 — Port debt: 104 tools on the legacy path *(the race)*
Unchanged from v1. 1 tool through the Dispatcher, 104 on the Sprint 2 WS path [VERIFIED-WEB]; pattern documented and mechanical.
**Phase-0 (paper, now):** `docs/PORT_WAVE_MANIFEST.md` — waves by family (scene → usd → render → tops → cops → memory), 10–15 tools per FORGE session, DoD per wave (FORGE basic + CRUCIBLE hostile, Commandment 7 intact), adapter-retirement criteria for legacy `mcp_server.py` branches.
**Execution:** MODE B. **Gate:** merge per wave.
**[Δ]** Priority reinforced by §3 Reflection: the thesis is now reproducible in synthesis; the port waves are what make it non-reproducible in fact.

### G2 — H22 re-grounding *(the gate)*
Unchanged from v1. All VERIFIED-RUNTIME artifacts expire at drop (P6). Confirmed churn: heightfield SOPs→COPs migration, Copernicus expansion, full Vulkan/Qt refactor, possible `hou.secure` arrival, KineFX/APEX expansion pressing the drift boundary.
**Phase-0:** runbook §9 frozen pre-release, with baseline freeze so the diff has a fixed left side.
**Gate:** `drop.json`; cp311 deviation re-opens gate-0.1 (sidecar; re-vendor list starts `pydantic_core`, `jiter` [INFERENCE]).

### G3 — Land the co-processor *(the prize)* **[Δ refined]**
Miles 5–6 remain the last two miles to the capability both external documents predict the industry converges on. Event-push beats their polling architecture on latency (in-process sub-ms vs 2s interval), cost, and thread-safety.
**Owned recommendation (unchanged):** run Mile 5 on H21.0.671 *before* installing H22 — audited runtime, attributable diffs, Sprint 3 closure. Human-at-GUI; MODE A interpretation is Joe's ruling.
**[Δ] Sentinel seed list (harvested §3 row 10):** the whitepaper's audit *content* survives even though its mechanism dies — uncompiled-VEX detection, broken-dependency flags, performance-bottleneck warnings, and the **pre-farm gate** product framing ("resolve before submission to the farm"). These seed the D-cycle probe catalog the sentinel runs once perception is live. Sentinel spec remains Phase-0 paper; build is MODE B.
**Gate:** human-at-GUI (Mile 5); MODE B (Mile 6, sentinel).

### G4 — MCP provider posture (D-H22-1) *(the vacuum)* **[Δ refined]**
First-party vacuum verified (C2, whitepaper-corroborated). Don't contest tool count; after G1, the MCP face is thin adapter work over the same 104 tools.
**[Δ] Differentiation columns, now externally confirmed:** the whitepaper's own comparison table used *Persistent State Capability* as its discriminating column — independent confirmation that state is the legible differentiator. The four columns only SYNAPSE fills: in-process perception events · undo-wrapped mutation · provenance recording · substrate memory. **[Δ]** Add the whitepaper's three-phase **adoption narrative** (transaction safety → context tools → stateful intelligence) to the D-H22-1 pilot deck: v1's legs sequence development; the phases sequence a studio's *deployment*. Both are true simultaneously.
**IP hygiene:** patent-pending mechanisms stay at claim level in anything public. §3 Reflection notes the whitepaper could not reconstruct the mechanisms — keep it that way.
**Gate:** D-H22-1 ratification; C2 closes at runbook step 7.

### G5 — Scene-grounding contract
Unchanged from v1. Four read-only manifest tools (`graph_manifest`, `attr_manifest`, `parm_manifest`, `error_manifest`), token-budgeted, degradation ladder (counts → names → typed samples), thread posture per the Spike 3.1 lesson, explicit non-dependency on USD schema changes (Michael Gold RFC stays off the critical path).
**Gate:** design review → MODE B.

### G6 — Numbers for the claims *(the proof)* **[Δ refined]**
`_benchmark_api.py` / `_benchmark_latency.py` exist at root [VERIFIED-WEB]; FXHoudiniMCP publishes per-command timing.
**Latency track:** identical operation set, in-process dispatch vs hwebserver HTTP round-trip, cold and warm.
**Token track:** identical tasks, SYNAPSE grounding vs the dossier's serialization recipe as naive baseline; tokens/turn, tokens/task, turns-to-green; three scene tiers.
**[Δ] Memory track — the Shot-010 scenario (harvested §3 row 5):** *"Revert the lookdev network to the layout used for Shot 010 two weeks ago, keeping the current point-cloud density."* Named benchmark + flagship demo. It is answerable only by composition over append-only history (select the historical opinion, retain the current density opinion, compose deterministically); similarity retrieval cannot produce the clean delta. One sentence that demonstrates the entire substrate — use it everywhere the substrate needs explaining.
**[Δ] G6b — telemetry sidecar spec sharpened:** the whitepaper's async session-telemetry instinct maps onto the existing FTS5/BM25 execution-trace sidecar [INFERENCE, horizon item]. Sharpened boundary for the spec: **telemetry (lexical, sidecar) records what happened; cognitive state (USD, substrate) records what is true.** Streaming is asynchronous and never on the tool-dispatch path. No vector store — determinism is the product (P2).
**Gate:** MODE B; results publish through README with methodology.

### G7 — Doc drift on the public claim surface *(small, now)* **[Δ refined]**
Unchanged core: (a) README's permanent `setx ANTHROPIC_API_KEY` instruction contradicts the auth guardrail (`SYNAPSE_ANTHROPIC_KEY`; permanent `ANTHROPIC_API_KEY` silently bills Claude Code to the API account) [README: VERIFIED-WEB; guardrail: INFERENCE]; (b) repo About line still carries the outside-in framing [VERIFIED-WEB]; (c) badge/version reconciliation.
**[Δ]** Add one sentence of explicit **loopback-only security posture** to the README/MCP docs (harvested §3 row 12) — the WS/MCP surface binds localhost only, no external ingress; cheap language, real question studios ask.
**[Δ]** C3 rider: ensure no public surface describes Moneta as a memory service.
**Gate:** merge-to-main. MODE A-legal, this week.

### G8 — H22 surface intake *(after the gate, through the flywheel)*
Unchanged posture: no H22 node type enters except through the re-sweep, as evidence-mandatory flywheel entries, `ratified:false`. **Orchestrate, never author.**
**[Δ]** Splat-training orchestration (whitepaper §4.II) is pre-registered as a C-class candidate contingent on the re-sweep confirming the actual TOP node surface — the whitepaper's `top::gaussian_splat_train` name is treated as phantom until probed (P1).
**G8b:** prompt-driven HDA scaffolding (SOP-lane only) remains a candidate; precondition unchanged: `authoring_domains.json` allowlist check [INFERENCE — verify at commit].
**Kinefx boundary:** re-affirmed, again, at §3 row 9. The pressure now arrives in documents wearing the product's name; the checks vocabulary treats "a document about Synapse says so" as zero evidence. The answer stays no, including proxy variants.
**Gate:** flywheel ratification per entry.

### G9 — The pre-flight gate *(new in v2 — P7 made operational)*
**Evidence:** Whitepaper §4.I (COP resolution/colorspace pre-flight with auto-injected fix nodes) names a real defect class: structurally legal-looking graphs that fail at cook time (mismatched resolutions, wrong colorspaces, illegal wires, wrong input counts). SYNAPSE currently has no named admission gate between "intent generated" and "nodes created" [INFERENCE — verify no equivalent exists in `checks.py` vocabulary at commit].
**Derivation:** P7 (+ P1, P3). The U.1 282-type connectivity catalog is a ratified rulebook of legal wiring [INFERENCE: ratified state]; today it aids generation. Pointed backward, it *admits or refuses* proposed graphs before mutation.
**Design shape (Phase-0 spec, paper, now — `docs/PREFLIGHT_GATE.md`):**
1. **Input:** proposed graph IR (nodes, parms, connections) from the agent, before any `hou` mutation.
2. **Pass 1 — structural admission:** every node type exists in the catalog for the pinned runtime; every wire is catalog-legal (type compatibility, input arity). Violations → typed refusal with the failing rule, no mutation.
3. **Pass 2 — context conformity (per-context passes, COP first):** resolution conformity policy, OCIO/ACEScg colorspace policy (pipeline-real: OCIO is a preserved environment invariant). Conformable violations may auto-inject fix nodes *inside the same undo block*, recorded in provenance as gate-injected.
4. **Output:** admitted IR → single undo-wrapped transaction (existing P3 machinery) → post-mutation verification → commit or rollback.
5. **Symbols:** the whitepaper's `hou.imageResolution` and any header-reading path go to V1 probe before use; nothing is inherited from the document.
**What this buys:** the trust story gains a third clause — *SYNAPSE refuses illegal work before your scene ever changes* — which no surveyed competitor offers and which composes with the perception channel (the sentinel flags drift; the gate blocks new violations).
**Execution:** MODE B. **Gate:** design review; COP pass lands after the G2 COP re-audit (the heightfield migration changes the rulebook it validates against).

---

## 6 · Non-goals (deliberate concessions, cumulative)

1. **Rigging / KineFX / APEX authoring** — conceded lane, enforced drift term. v2 note: pressure now arrives via documents bearing the product's own name; provenance of the request does not change the answer.
2. **Pixel/tensor authoring** — generative creation is orchestrated via TOPs, never replicated.
3. **Tool-count parity racing.**
4. **hwebserver migration of the core** — reaffirmed against the whitepaper's doubling-down. At most a later *optional additional ingress*; no leg assignment. (Multi-line `execute_python` wart [INFERENCE] stays a parked MODE B hygiene item — temp-file script handoff inside the existing wire protocol.)
5. **USD schema changes** — RFC-only with Michael Gold; every v2 deliverable remains off that dependency.
6. **Vector similarity for cognitive state** — *new, explicit.* Deterministic LIVRPS composition is the mechanism and the moat; similarity stores are the competitor category (and the whitepaper's default substitution). Lexical FTS5/BM25 for *telemetry* is fine (G6b); vectors for *state* are not.
7. **Polling-based background audit** — *new, explicit.* Perception is event-push. No timer loops touching scene state.

---

## 7 · Relay sequencing

**Leg 0 — now → H22 release (days). Paper + one human-at-GUI option.**
- Mile 0: commit this blueprint (F3). ← *you are here (v2 refresh of the same mile)*
- Mile 0.1: G7 doc PR (auth, About line, badges, loopback language, C3 rider).
- Mile 0.2: runbook §9 frozen; pre-drop baselines frozen (catalog hash, quarantine snapshot, test-pass count).
- Mile 0.3: G1 wave manifest · G5 grounding contract · G6 benchmark design (incl. Shot-010 + G6b sidecar boundary) · **G9 pre-flight spec**.
- Optional, recommended: **Mile 5 (Spike 3.3) live at the GUI on H21** — human-driven.

**Leg 1 — release day.** Human installs H22, writes `drop.json` {houdini, python, usd, pyside, hython}. Nothing else. P4.

**Leg 2 — drop week.** Runbook §9 top to bottom. Exit: quarantine re-pinned, sweep diff ratified, COP audit refreshed, C2 closed, Qt smoke green, ABI verdict recorded.

**Leg 3 — MODE B.** Priority: G1 port waves → G4 MCP surface → G5 grounding tools → **G9 gate (structural pass first, COP pass after re-audit)** → G6 numbers → Mile 6 hostile perception crucible → sentinel build → G8 intake per ratification.

**Distance:** still Mile 0–1 of ~8 to "H22-grounded, ports complete, gate live, co-processor live, numbers published." v2 added one mile of scope (G9) and removed none.

---

## 8 · Gate registry

| Gate | Governs | State |
|---|---|---|
| `drop.json` | All H22 runtime work (Legs 2–3) | Closed until human writes it |
| Flywheel ratification | Catalog/tool/capability entries (G2 sweep, G8, G8b, splat candidate) | `ratified:false` resting state |
| Merge-to-main | Every wave, every doc PR | Human, per commit |
| D-H22-1 | MCP surface + comparison table + adoption narrative | Open; spec in Leg 0 |
| D2 | Local (Nano) vs cloud (Ultra) provider | Unratified; priority raised |
| gate-0.1 (sidecar vs abi3) | Re-opens iff H22 Python ≠ cp311 | Conditional on `drop.json` |
| G9 design review | Pre-flight gate spec → MODE B build | Opens at Mile 0.3 |
| RFC — Michael Gold | Any USD schema / `customData` write | Deliberately off the critical path |

---

## 9 · Drop-week runbook

Executed once, in order, after `drop.json` exists. Each step produces an artifact; no output is trusted without one.

1. **Baseline check.** Leg-0 frozen baselines exist (H21 catalog hash, quarantine snapshot, test-pass count). Missing → stop; the diff has no left side.
2. **ABI verdict.** `drop.json` Python version. cp311 → vendored tree holds. Else → gate-0.1 sidecar path; re-vendor from `pydantic_core`, `jiter` [INFERENCE].
3. **Quarantine re-litigation (P6).** Probe every quarantined symbol once against live H22: `hou.secure` (auth resolver auto-adopts if present — README-documented), `hou.pdg.*`, `hou.lopNetworks()`, `hou.updateGraphTick()` [list: INFERENCE]. Re-pin each with the H22 runtime tag.
4. **Sweep re-run** (147 sites [INFERENCE]) against H22; diff vs U.1 282-type catalog. Expected churn: Copernicus heightfield set, ML/ONNX nodes, splat nodes, Solaris procedurals. Output: `U.1-H22` flywheel entry, `ratified:false`.
5. **COP audit refresh.** 21 tools [INFERENCE] re-validated against H22 Copernicus; flag everything touched by the SOPs→COPs heightfield migration. G9's COP conformity pass depends on this output.
6. **Qt/PySide smoke.** Panel boot on the Vulkan-era build; `drop.json` PySide field vs panel assumptions; QFont letter-spacing path included.
7. **Release-notes scan.** Confirm/deny first-party MCP/agent surface (closes C2). Record KineFX/APEX scope; re-affirm the drift term in `checks` vocabulary.
8. **Perception re-audit.** Spike 3.0-style `dir()` audit of the `pdg` surface; diff vs Mile 2 findings before trusting the bridges on H22. If Mile 5 ran on H21 (recommended), compare event traces.
9. **New-symbol probes from adjudicated documents.** `hou.imageResolution` and any image-header path (G9 Pass 2); actual TOP splat/ML node names (G8 candidate). Nothing from either external document enters code without a V1 probe.
10. **Ratify.** Human reviews flywheel entries. MODE B opens per §8.

---

## 10 · Intake protocol for external research artifacts *(new in v2, standing)*

Two external documents were adjudicated this week; the blueprint's deltas were one principle, one gap, four refinements. The design is stable under new evidence. To protect the paper/build ratio from here:

1. Any inbound research artifact (dossier, whitepaper, thread, video transcript) gets a **one-page adjudication appendix**, not a blueprint revision: tier-label its claims, run each against P1–P7 and the non-goals, verdict per claim (ADOPT / ADAPT / REJECT / CORRECT), harvest into *existing* gaps.
2. A blueprint version bump requires at least one of: a new principle, a new gap, or a corrected load-bearing fact. Refinements append; they don't re-version.
3. Claims about `hou.*` / `pdg.*` / node types are V0 regardless of the document's confidence or letterhead — including documents that name SYNAPSE. Provenance is not evidence (P1).
4. Rigging-scope inclusions in any inbound document are logged as boundary-pressure events and rejected without re-litigation.

---

## 11 · Open verifications carried out of this pass

Cheap, local, non-blocking — each one `ls`/grep at `C:\Users\User\SYNAPSE`:

- `authoring_domains.json` allowlist contents (gates G8b).
- Quarantine list exact membership and storage location (runbook step 3).
- `checks.py` vocabulary — confirm no existing pre-flight-gate equivalent before G9 spec work (avoid the phantom-hardening trap: never rebuild shipped code).
- Multi-line `execute_python` wart status (Non-Goal 4 parking note).
- README badge vs local test count / version reconciliation direction (G7).
- Multi-provider harness + D2 document paths (§8 accuracy).
- FTS5/BM25 sidecar design notes, if any exist yet (G6b boundary).

---

*Blueprint v2.0 ends. Next baton unchanged: Mile 0.1 (G7 doc PR) + Mile 0.2 (runbook + baseline freeze). Future inbound documents route through §10.*
