# SYNAPSE_RETINA_BLUEPRINT

**The perception co-processor — the render receipt.**

| | |
|---|---|
| **Doc ID** | `SYNAPSE_RETINA_BLUEPRINT` v1.0 |
| **Status** | ARCHITECT output — governing document. Per F3, this commits **before** any FORGE execution it governs. |
| **Date** | 2026-07-16 |
| **Baseline** | SYNAPSE v5.26.0 · Houdini 22.0.368 (live-verified) · Wire Protocol 4.0.0 |
| **Audience** | Internal governing doc, written to vendor-brief standard. §10 is the SideFX-facing page. |
| **Disclosure** | **Public-safe at the level written here.** Mechanism claim language, thresholds-as-shipped, and schema internals are NDA-only. The scoped-delta system claim (§5) is queued for CIP review under the existing filings before any external mechanism-level discussion. |

> **Administration note (2026-07-16):** committed verbatim as received (F3). INFERENCE-column closures and
> corrections live in `docs/reviews/retina-reconciliation-2026-07-16.md` — per this document's own §12 rule,
> the reconciliation record and the perception truth catalog outrank any INFERENCE line below.

---

## §0 · The demo sentence

> **SYNAPSE swapped the crystal to Dark_Glass — and proved that the only pixels that changed belong to the crystal.**

That sentence is the whole system. v5.26.0 keeps receipts on every mutation (`agent.usd`: decision, reasoning, revert) and every cook event (perception channel, Phases A/B). The **frame itself** is the last unreceipted claim in the product. RETINA is the organ that notarizes it: the render receipt, completing *receipts, not magic* for what the work **looks like**.

---

## §1 · Why now

- **H22 shipped** (22.0.368). Copernicus is SideFX's declared image substrate; the keynote-announced first-party MCP is **rigging-scoped and unshipped** — squarely inside SYNAPSE's enforced non-goal. The ratified boundary (`docs/SYNAPSE_H22_BOUNDARY.md`) names **in-process perception** as an unclaimed differentiator. RETINA is that line item, built.
- **SYNAPSE v5.26.0 is live-verified on H22** — 32 verdicts flipped provisional→verified-live against the running interpreter. The verification *culture* exists; RETINA extends it from node graphs and cook events to pixels.
- **OpenCV 5.0.0 shipped 2026-06-06**; `opencv-python-headless` **5.0.0.93** wheels landed on PyPI **2026-07-02** as **cp37-abi3 / win_amd64** — one wheel spans cp311 and cp313, neatly sidestepping the exact ABI churn H22's dual Python builds created. The upstream world independently chose the abi3 path from our own Gate 0.1 memo.
- **The moat logic compounds.** The utility flywheel holds four truth classes (wiring, Solaris context, diagnostic cook-truth, H22 re-sweep). Perception truth is cycle ⑤ — and like cook-truth, it is a truth class that **only exists live**, unavailable to any doc-trained model or out-of-process bridge.

---

## §2 · First principles → derived moves

| # | Principle | Derived move |
|---|---|---|
| **P1** | **A render is a claim.** Verification is comparison against a *declared expectation*. | Every mutation claiming a visual consequence emits a machine-checkable postcondition — an **expectation contract**. No expectation → nothing to verify → no Accept. |
| **P2** | **The scene is the ground-truth generator.** | The host exports camera + prim IDs into the manifest; verification is delta **conditioned on scene truth**, not blind CV. Structurally unavailable to screenshot bridges — they don't own the scene or the intent. |
| **P3** | **Judgment is a ladder, not a model.** | T0→T3 cascade (§4). Most verdicts are arithmetic; few need models; almost none need an LLM. Mirrors the provider tiers; feeds G6 token-frugality. |
| **P4** | **Pixels stay put; verdicts travel.** | A 1080p float EXR is ~24 MB/AOV. Nothing that size crosses the wire. The worker lives *at the data* and publishes small versioned events onto the **existing** perception channel. Proxies cross only on T3 escalation. |
| **P5** | **The eye never destabilizes the hand.** | **Zero `cv2` imports host-side, ever** — a CRUCIBLE pin mirroring the zero-`hou` cognitive-boundary lint. The worker runs in its own venv, host-ABI-independent by construction: only thin host hooks re-ground per Houdini major (same pattern as the major-aware connectivity catalogs). |
| **P6** | **The agent authors its own instruments.** | GPU-heavy per-pixel work becomes **COP networks SYNAPSE builds itself**; OpenCV serves as CRUCIBLE's independent oracle — the same metric computed both ways must agree within ε. |

---

## §3 · Architecture

```
HOUDINI HOST (in-process, thin)          DISK OUTBOX                 RETINA WORKER (own venv)
─────────────────────────────           ─────────────               ─────────────────────────
SYNAPSE core ──── manifest.json ──────▶ manifest.json ────────────▶ T0 · file truth
Karma render ──── EXR + ID AOV ───────▶ EXR products + .done ─────▶ T1 · OpenCV 5 classical
COPs lane (agent-authored QC nets)      baseline store             T2 · ONNX (FLIP / seg)
                                        (last-accepted frames)     T3 · VLM escalate (proxy only)
                                                                        │
Panel CHAT ◀── consent gate ◀── verdict events · perception channel ◀──┘
IntegrityBlock receipt gains a PROOF line
```

**Host hooks (the only in-process code):**
- **Manifest writer** — on render submit, alongside the products: product paths, expected AOV list, resolution, **camera 4×4**, target prim paths + world bboxes, expectation blocks, scene fingerprint, renderer/denoiser/samples profile, frame range.
- **Post-render sentinel** — a `.done` drop via the ROP post-render script param *(INFERENCE — `dir()`-verify per §6 before FORGE; ancient stable surface, low risk)*.

Because the manifest carries camera and geometry truth, the worker **projects prim bboxes to screen space itself** and stays completely `hou`-free — host exports truth, worker judges. CRUCIBLE can feed it synthetic manifests: the whole organ is testable without Houdini running.

**Worker stack:**
- `opencv-python-headless==5.0.0.93` (abi3 — VERIFIED on PyPI; `4.13.x` is the API-stable fallback for every op named in this doc).
- **OpenImageIO** for ingest — color-managed via the protected `OCIO` env: **linear float32 planes for metrics; display-transformed 8-bit proxies for T3 and panel thumbnails.** `cv2.imread` is explicitly not the EXR path (CVE-gated, color-blind).
- **onnxruntime** for all model inference — one inference stack, matching the host's own ML direction. OpenCV's new DNN engine is CPU-only at 5.0; not used.

**Event contract** (versioned; illustrative shape — final schema is a FORGE artifact):

```json
{"ch":"perception","v":1,"claim":"material_swap:/geo/crystal","tier":1,
 "checks":[{"name":"delta_containment","pass":true,"leak_px":14,"eps":32},
           {"name":"ssim_outside","val":0.9971,"min":0.995,"pass":true}],
 "verdict":"pass","proof":"<qc_path>/f0001_delta.png"}
```

Verdicts flow through the **existing** consent gate that already auto-surfaces in CHAT; the `agent.usd` receipt's credit block gains its third line — **DECISION · VIA · PROOF**.

---

## §4 · The tier ladder

| Tier | Question | Tooling | Cost | Catches |
|---|---|---|---|---|
| **T0 — file truth** | Did anything render? | OpenEXR headers, fs | µs | The BL-007 class — EXR not written, missing AOVs, wrong resolution |
| **T1 — deterministic pixels** | Did the *right thing* change? | OpenCV 5 classical: NaN/inf census, black/blown frames, clip %, firefly outlier count, SSIM vs baseline, change masks, **containment** | ms, CPU, headless | Silent visual regressions; scope leaks; the scoped-delta proof lives here |
| **T2 — learned local** | Is it perceptually right? | ONNX: FLIP perceptual error, segmentation; adjacent to the Copernicus expansion's **neural-COP preflight honesty** | GPU when present | Perceptual drift, denoiser smear, semantic checks |
| **T3 — escalated judgment** | Does it *read* correctly? | VLM via provider tiers, cost-gated; 512px display-referred proxy + T0–T2 evidence | tokens | "Does this read as glass at scene IOR" — ambiguity only |

**Routing rule:** cheap-first, escalate on inconclusive, never skip a tier downward. G6 alignment is structural: the ladder's *purpose* is that most verdicts cost zero tokens — and M5 lands the counters that finally put a number on it.

---

## §5 · The flagship primitive — scoped-delta proof

*(High level; public-safe. Mechanism specifics beyond this section: NDA. System claim queued for CIP review.)*

1. Verification renders go out **small** (e.g. 960×540) with beauty + an **integer object-ID AOV** (preferred over full cryptomatte for QC — exact, cheap, no hash-rank decode; crypto is the later fidelity upgrade).
2. Worker computes the before/after **change mask** (difference → threshold → morphological cleanup).
3. Intersects it with the target prim's **ID matte** (small dilation for AA edges).
4. Asserts **containment**: changed pixels ⊆ target matte within a leak-pixel ε, **and** an SSIM floor *outside* the matte.

**Pass** means: the claimed change happened, where it was claimed, and nowhere else. **Fail** localizes the leak. Deterministic, milliseconds, zero tokens.

**Why only SYNAPSE can run this play:** the proof requires owning the camera, the prim IDs, the AOV authoring, *and* the mutation intent — the full inside-out position. An out-of-process screenshot tool has pixels and guesses; RETINA has pixels and **provenance**.

**Lineage note:** Cosmos (Filing #3) *predicts* renders without ray tracing; RETINA *verifies* them without judgment calls. Prediction plus verification brackets the expensive step from both sides — high-level pairing only; mechanism discussion under NDA.

---

## §6 · Flywheel integration — truth cycle ⑤: perception truth

RETINA is not a new subsystem bolted on. It is the **fifth ratified cycle** of the existing loop, run on the same EXPLORE → REVIEW → SCAFFOLD contract, human-ratified like ①–④.

- **EXPLORE** — live-probe the render/readback surface on the running 22.0.368 and commit an integrity-checked **perception truth catalog**. Every symbol below is INFERENCE until it appears in that catalog:
  - Karma's integer object-ID render-var name (CPU and XPU)
  - ROP pre/post-render script params; husk callback surface
  - Copernicus buffer↔numpy readback path
  - Flipbook / viewport-grab symbols (GUI-session convenience only — never the farm path)
- **REVIEW** — sweep every render-touching tool against the catalog; findings → fixes; 0-critical bar.
- **SCAFFOLD** — manifest hooks and verdict wiring into the consent gate.

Where the catalog and a code comment disagree, **the catalog wins.** Probes beat memory — including RETINA's own.

---

## §7 · Verification governance

- **`qc_profiles.toml`** — tolerance profiles per renderer × denoiser × sample tier, versioned in-repo and ratified on the U.1 pattern. GPU renders are not bit-stable; thresholds, never equality. QC cooks compare like-for-like on denoiser policy.
- **Commandment 7 extends to thresholds.** A threshold is a test assertion. It is never loosened to green a verdict; a red verdict is fixed forward in the scene or the contract.
- **Verdict persistence** — sidecar JSONL (matching the live memory default) **until the customData RFC lands**. USD writes of any verdict schema are **RFC-gated (holder: M. Gold)** and stay off this project's critical path. Target state, one paragraph, no schema authored here: verdict records as siblings to `agent.usd` receipts under the existing customData state-tracking pattern, with a filtered **VerdictInspector** lens later on the derivative-tool pattern.
- **Honesty flags** — scaffolds self-report. A tier that cannot run (no GPU, missing model, absent AOV) returns `inconclusive`, never a silent pass. The Copernicus expansion's preflight-honesty rule applies verbatim.

---

## §8 · Risk register

| Risk | Mitigation |
|---|---|
| GPU/denoiser nondeterminism poisons baselines | `qc_profiles.toml`; fixed denoiser policy for QC cooks; thresholds not equality |
| ID-AOV render cost | Half-res verification renders; full-res only on Accept |
| `cv2` creep into the host process | Zero-cv2 CRUCIBLE pin lands in M0, before any perception code exists |
| Wheel availability shifts | 5.0.0.93 abi3 VERIFIED live on PyPI; 4.13 fallback is API-stable for every named op |
| H21 dual-build claim rots (H21 uninstalled at v5.25.0) | State plainly — "H21 catalogs frozen at 21.0.671" — or keep one H21 instance for release gates |
| SideFX ships first-party perception | RETINA **consumes** it as a T2 source; boundary doc gains an amendment, not a competitor |
| Verdict spam floods the channel | Event contract is bounded and versioned; Mile-6-style hostile pass (flood, malformed, cancellation) is M4's crucible scope |

---

## §9 · Delivery — six miles, gated

Discipline is the shipped port-wave pattern end-to-end: **gatewarden admits → FORGE builds in an isolated worktree → assayer live-verifies every symbol on the running build → hostile crucible attacks what it didn't build → a human merges → post-merge full-suite re-verify.** Live-verify posture replaces the retired H21-first rule; the v5.24 "before photo" is the standing baseline instrument.

| Mile | Deliverable | Gate |
|---|---|---|
| **M0** | This document committed + the **zero-cv2 host pin** test | Human merge (F3 satisfied) |
| **M1** | Perception-truth EXPLORE probe → committed catalog · manifest writer + `.done` sentinel · **T0** live (kills the BL-007 blind-spot class) | Assayer on 22.0.368 |
| **M2** | Worker skeleton in its own venv · OIIO/OCIO ingest · **T1** metric kit · verdict events on the channel | Crucible hostile pass |
| **M3** | **Scoped-delta proof end-to-end on the Dark_Glass scenario** — PROOF line lands in the receipt, consent gate carries a verdict | Joe at the GUI · **the demo** |
| **M4** | **T2** ONNX (FLIP/seg) · agent-authored COP QC net · oracle cross-check (COP vs OpenCV within ε) · flood/malform/cancel crucible | Paired with the Copernicus expansion cycle |
| **M5** | **T3** escalation via provider tiers, cost-gated · panel Review polish · **verdicts-per-token counters** | G6 finally gets its number |

---

## §10 · If we're in the room — the SideFX page

**Positioning, one line:** RETINA consumes what SideFX ships — Karma AOVs, COPs, PDG events, ROP hooks — and returns something no first-party roadmap has claimed: **scene-conditioned proof that an AI's change did what it said, and nothing else.** The ratified boundary holds; rigging stays yours; perception receipts are ours.

**Three asks:**

1. **A stable object-ID contract.** A documented integer object-ID render var, stable across Karma CPU/XPU and across majors. Verification quality is bounded by matte quality; a semver'd ID AOV makes every Houdini render self-verifying by construction.
2. **Hook stability.** ROP pre/post-render script params and husk callbacks treated as supported, versioned surface — so verification hooks survive a major without a re-audit cycle.
3. **A blessed Copernicus readback path.** A documented buffer↔numpy pattern, so agent-authored QC COP nets can hand mattes and scalars to in-process verifiers without a file round-trip.

**On the table from our side:** the boundary doc as a standing non-compete contract; NDA available for mechanism-level discussion (drafted, guarded purpose clause); and one strategic note worth SideFX's time — **Karma plus an ID AOV makes every studio render a labeled training sample.** The archive your customers already own is pre-qualified fine-tuning data for world-model pipelines. RETINA's manifests make it labeled *by construction*.

---

## §11 · What this is not

- **Not rigging.** KineFX/APEX is an enforced drift term; the APEX MCP boundary holds unchanged.
- **Not shader authoring.** VOP scope stays graph plumbing.
- **Not vector similarity.** Verdicts are deterministic events, not embeddings.
- **Not polling.** Event-driven only, on the channel that already exists.
- **Not a replacement for artist eyes.** T3 exists because judgment escalates — to models, then to humans, in that order of cost and that reverse order of authority.

---

## §12 · Truth-label appendix

| Claim | Label | Source |
|---|---|---|
| OpenCV 5.0.0 released 2026-06-06; new DNN engine CPU-only | VERIFIED | Release coverage + docs.opencv.org |
| `opencv-python(-headless)` 5.0.0.93 abi3 win_amd64 wheels on PyPI, 2026-07-02 | VERIFIED | PyPI file listings |
| H22 = 22.0.368; USD 26.05; Python 3.13.10 default, separate 3.11 build; Qt5 dropped | VERIFIED | Launch coverage (verify against installed build for the drop record) |
| SYNAPSE v5.26.0 live-verified on 22.0.368; 4,387/0; consent gate; IntegrityBlock; boundary doc | VERIFIED | Repo master README |
| SYNAPSE host build = H22 py3.11 (`_vendor` remains CP311) | INFERENCE | Close in drop record |
| Karma integer object-ID render-var name (CPU/XPU) | INFERENCE | §6 EXPLORE probe |
| ROP pre/post-render script params; husk callbacks | INFERENCE (low-risk) | §6 EXPLORE probe |
| Copernicus buffer↔numpy readback | INFERENCE | §6 EXPLORE probe |
| `Usd.GetVersion()` python symbol | INFERENCE | Runtime check |

**Nothing in the INFERENCE column is coded against until it appears in the perception truth catalog.** Probes beat memory.

---

*ARCHITECT writes the design and never the code. FORGE implements against this contract. CRUCIBLE attacks what it didn't build. The human merges.*
