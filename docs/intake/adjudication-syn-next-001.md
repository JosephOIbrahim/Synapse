# Adjudication Appendix — SYNAPSE Next-System Blueprint (`SYN-NEXT-001`)

**Artifact:** `docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md`, self-titled a governing blueprint, self-marked **"Status: Adopted 2026-08-08 with five review amendments,"** committed to the tree as `bf3c25ea` ("docs: adopt SYN-NEXT-001 next-system blueprint"). Baseline it cites: `v5.44.0` @ `df60f639`, 2026-08-08.
**Protocol:** blueprint §10 intake. This appendix **adjudicates**; it authorizes **no code change**, revises **nothing** in the governing `SYNAPSE_H22_PROOF_LEG_BLUEPRINT` (P1–P7 / G1–G9 / §6 non-goals), and **never bumps a version**. Escalations return to the human + CTO.
**P1 framing up front:** the artifact wears full blueprint letterhead, cites a commit SHA, and declares *itself* adopted. Per **P1 (runtime is ground truth; provenance is not evidence)** none of that confers standing, and per **P4 (human gates bound autonomy)** a document cannot adopt itself over the governing blueprint. Its "Adopted" banner and the "adopt" commit subject are **provenance, not ratification.** The §10 job is to give the human + CTO a claim-by-claim basis to ratify, amend, or escalate — see Verdict.

---

## (a) Current-state claims — cheaply checkable this dispatch

| # | Claim (§2 / §14) | Tier | Verdict | Evidence |
|---|---|---|---|---|
| 1 | Three-way version split: `VERSION`=5.44.0, package/runtime `__version__`=5.43.0, README banner v5.42.0 | **VERIFIED-RUNTIME** (repo, this dispatch) | **ADOPT** the problem (Truth / One-authority law; **P1**) | `VERSION`→`5.44.0`; `python/synapse/__init__.py:123`→`__version__="5.43.0"` + docstring `Version: 5.43.0`; `README.md:9`→`v5.42.0`. Split reproduced exactly. |
| 2 | Fixture inventory is a single fixture, `solaris.basic` | **VERIFIED-RUNTIME** (repo, this dispatch) | **ADOPT** | `fixtures/` contains only `solaris.basic.json`. |
| 3 | BLOCKS reconciler exists and is oracle-pinned | **VERIFIED-ARTIFACT** | **ADOPT** | v5.43 BLOCKS release; `python/synapse/blocks/runtime.py`. |
| 4 | "SYNAPSE currently silently serves JSONL when Moneta is requested" (W1.5) | **UNVERIFIED-as-stated** | **CORRECT** (Fail-visible law is right; the *current-state* framing is likely stale) | Conflicts with recorded PR #60 (fallback made **loud**, C-0 address fix, 2026-08-01) and with `moneta_store.py`'s own repeated "never silent" / "logged, never silent" posture — **before** this artifact's `df639` baseline. Whether the silent path regressed or the claim is stale is a **runtime** question (**P1**), not a doc assertion. Route to probe. |
| 5 | Persisted 256-dim store conflicts with a 384-dim embedder; row counts 355/356 | **INFERENCE** (direction matches `moneta-deep-review-2026-08-05`) / store numbers **UNVERIFIED** | **ADAPT** into memory durability work, probe-gated | Artifact's own §14 concedes "Persisted Moneta store state: UNKNOWN from this session" — honest, and correctly P1-disciplined. Numbers are store-state facts needing a live read. |
| 6 | Recall is a DECISION-only substring scan | **INFERENCE** | **ADAPT** into existing recall work | Matches the recorded recall→RAG seam gap. |

## (b) Node-type / `hou.*` / API claims — V0 regardless of letterhead (charter step 4)

Routed to the **runbook step-9 probe list**; **none** enters code or spec as fact.

| # | Claim | Tier | Disposition |
|---|---|---|---|
| 7 | Fixture node/parm content: `solaris.karma_xpu_shot` (camera/rendersettings/renderproduct), `solaris.materialx_lookdev` (MaterialX surface skeleton), `solaris.aov_package` (cryptomatte/render-vars), `cops.texture_process` (Copernicus graph) | **V0** | Probe on 22.0.368. **MaterialX note:** G1b already shipped the `mtlxstandard_volume`→`mtlxvolume` substitute — any new MaterialX type name re-probes, never inherits. Artifact concedes "names may change during live assay; runtime truth decides" — **P6-aligned.** |
| 8 | `capture_fixture(...)` API + `parm_mode="authored_delta"` capture semantics (W6) | **V0** | Proposed API + parm/default-signature behavior — probe before any implementation claim. |
| 9 | Build-pin distribution (A4): "18× `22.0.397`, 2× `22.0.382`" against a `22.0.368` pin | direction **VERIFIED** / figures **INFERENCE** / "397 = stale drift" **UNVERIFIED** | Non-368 pins exist (repo-wide I count **77×** `22.0.397` across 30 files, not 18 — the figure is **scope-sensitive**, and the artifact's own 3 self-references inflate `22.0.382` to 5 of 5 in-tree). The load-bearing unknown: **is `22.0.397` drift-to-zero or a real newer point build?** Per **C1/P6** that needs a release-notes/runtime resolution, not the artifact's "stale" assumption. **Escalate (E2).** |

## (c) Design principles vs P1–P7 — and confabulation clearance

| # | Principle claim | Verdict | Principle / ruling |
|---|---|---|---|
| 10 | "A claim requires an observation; unobserved renders UNKNOWN" (§0 governing rule) | **ADOPT** | **P1 + P6**; identical to the fidelity-UNKNOWN posture. Strongest through-line in the doc. |
| 11 | Deterministic route carries zero model decision after it resolves; "do not use model similarity to claim deterministic routing" (W4.3) | **ADOPT** | **P7** (validation precedes mutation) + Determinism law. |
| 12 | Vector similarity confined to **memory recall**, never outranks an exact alias, never drives the deterministic/cognitive path (§3.4, W3, W4.3) | **ADOPT — C3-COMPLIANT** | **C3 clearance:** cognitive STATE stays deterministic USD/fixture; vector similarity is scoped to Moneta recall. **Moneta IS the memory backend — that is not the confabulation**, and the artifact keeps the line correctly. No leakage. |
| 13 | Fail-visible backend; no silent healthy-empty store | **ADOPT** | Fail-visible law; P-aligned. |
| 14 | UUID entity IDs + separate `content_fingerprint` dedup + WAL migration (W2, A2) | **ADAPT** | Sound memory-durability engineering; harvest into memory gap. |
| 15 | `execution_receipt/v2` unified schema + `prompt_provenance` + `timing` (§4.5, W7, A1/A3) | **ADAPT** | Schema **v2** is a data-contract bump — real and useful, but a versioned contract change; folds into RETINA receipts (G4). |

**C1 clearance:** the artifact makes **no** "H22 has launched X" claim as fact — it is build-pinned to `22.0.368` (established live) and treats other builds as pins to reconcile, not launched truth. Compliant. (The one residual — `22.0.397` provenance — is item 9 / E2.)

## (d) Workstream → EXISTING-gap harvest (G1–G9 only)

**Harvestable now** as reinforcement/evidence in existing gaps:
- **W8** freeze attribution + budgets → the live freeze area (`FRZ_REPRO.md`; render-freeze / chat-freeze-qtfallback / marshal-deadlock classes already tracked). Real, measured-ownership discipline — welcome.
- **W9 + A4** H22 knowledge classes, per-build re-stamp, stale-pin gate → **G7** (corpus reseed) + **G1a** (H21-context-served-as-H22, the exact silent-wrong twin) + **G9** (build lifecycle).
- **W10** CI lanes (Py 3.13 stock, Moneta lane mandatory for release) → **G8** dev-hygiene + the shipped honest-green CI work.
- **W11** destructive-op policy, gate `run_sleep_pass` (a real tool), collision-before-create → existing bridge gate anchors.
- **W12 + A5** governance, `STATUS.md`, mirror public defects, panel tool inventory → **G9** (public-surface drift, already a start-line ruling).
- **W1/W2/W3** Moneta recovery/durability/recall → **G5** (memory-1/2 waves) + **G8** (the owed memory-analyst section) + the already-shipped Moneta production harness (`3fb5d45d`). Fold PR #60 state in (item 4).

**No home in G1–G9 — new scope → ESCALATE (see E1/E3):**
- **W0** version-sync state machine + `sync_version.py`.
- **W4/W5** deterministic intent router + fixture-registry product (**Track A**).
- **W6** capture-network-into-structural-memory (**Track B**, the literal memory promise).

## (e) Boundary-pressure log

- **Rigging / KineFX / APEX: 0 events.** The artifact is scope-disciplined — Solaris/COPs/memory/release/CI only; W6 capture is explicitly **LOP-only** with no APEX proxy. The §6 boundary held without pressure. Credit where due.
- **1 process-boundary event:** the artifact **self-declares "Adopted"** and was **committed as adopted** without passing §10 intake first. Per **P1/P4** a document cannot ratify itself over the governing blueprint. Logged, not litigated here — it is the human + CTO's call (E1).

---

## Verdict

This artifact is **not a harvestable dossier — it is a candidate successor governing blueprint.** It ships new system laws (§1.3), a new six-plane architecture (§3), new versioned data contracts (§4), thirteen new workstreams, a new release sequence, and a new definition of done. Much of it is **genuinely good and evidence-anchored** — the version-split diagnosis is verified-exact, the observation-or-UNKNOWN spine is pure P1/P6, and it stays clean of both confabulations (C3 recall/cognitive-state separation held; no C1 has-launched claim). But adopting it **as-is** is a version bump, and **the adjudicator never bumps** (charter step 3, P4).

**Claim counts:** ADOPT 7 · ADAPT 4 · CORRECT 1 · REJECT 0 · V0-routed 3 clusters (items 7–9).
**Confabulations:** C1 clear · C3 clear.
**Boundary-pressure:** rigging/APEX 0 · self-adoption process event 1.

**Escalations (human + CTO — I flag, never execute):**
- **E1 — Possible version bump.** The whole artifact is a proposed successor blueprint. It must be ratified against `SYNAPSE_H22_PROOF_LEG_BLUEPRINT` (reconcile §1.3 laws ↔ P1–P7; §4 contracts; W0–W12 ↔ G1–G9), not self-adopted. Its committed "Adopted" status does not bind the governing blueprint (P1/P4).
- **E2 — `22.0.397` build-pin provenance.** Is it stale drift to zero out (the artifact's assumption) or a real newer point build? Load-bearing for A4/W9; unresolved; needs a release-notes/runtime probe before either reading is treated as fact (C1/P6).
- **E3 — Track A (W4/W5) and Track B (W6) are new product surfaces** with no home in G1–G9. Whether they become new gaps is the human's decision, not an intake harvest.
- **E4 — New data contracts (§4, schema v1/v2) and self-declared laws (§1.3)** overlap P1–P7 but don't map 1:1. Reconciliation is a governance/version decision.

**Appendix path:** `docs/intake/adjudication-syn-next-001.md`
