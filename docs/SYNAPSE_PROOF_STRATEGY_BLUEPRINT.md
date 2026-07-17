# SYNAPSE_PROOF_STRATEGY_BLUEPRINT

**Stop measuring by build speed. Measure by what it can prove — five sessions on one real shot.**

| | |
|---|---|
| **Doc ID** | `SYNAPSE_PROOF_STRATEGY_BLUEPRINT` v1.0 |
| **Status** | ARCHITECT output — **DRAFT until Joe ratifies** (§9 block). Paper only: this document mutates no code and no state file. |
| **Date** | 2026-07-17 |
| **Baseline** | HEAD `d441738` (`master`, verified this dispatch: `git log -1`) — two commits past tag `v5.28.0` (`72de5f1`): **C-MTLX** (PL-M1 G1b) + **C-U5** (PL-M1 G1a, = HEAD subject "major-aware Solaris CONTEXT truth"). Houdini **22.0.368** live (`harness/state/drop.json`: py 3.13.10 / USD 0.26.5 / PySide 6.8.3, verified this dispatch). |
| **Position update this doc carries** | The PL blueprint was authored at `72de5f1`; both **PL-M1 twins have since merged** (C-MTLX + C-U5). **The leg now genuinely stands at PL-M2 — the live session.** Session 1 below starts exactly where the work stands. |
| **Lineage** | **This is the strategy layer above** `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` (PL, the mile plan) and `docs/SYNAPSE_RETINA_BLUEPRINT.md` (the receipt organ). It **re-aims** their execution around the supervisor's product frame; it **never restates** their build content — one source of truth per surface. Governing rulebook: `harness/SPEC.md` (the harness) + `CLAUDE.md` (the conventions). Where this doc and the live tree disagree, the tree wins. |
| **Disclosure** | Public-safe at the level written here (matches the RETINA blueprint's own line). RETINA §5 mechanism specifics, thresholds-as-shipped, schema internals, and filing details stay **NDA/CIP-side** — the scoped-delta system claim is queued for CIP review under the existing filings before any external mechanism discussion. |
| **Truth discipline** | Every load-bearing claim carries a `file:line` **verified by this dispatch's own Read/Grep** or a **scout tier label** (VERIFIED-LOCAL / VERIFIED-LIVE / INFERENCE / DOC-CLAIM) naming its source. Counts are re-derived here, not copied. Anything unverifiable locally is tagged `[UNVERIFIED — <what would settle it>]`. |

---

## §0 · Why this document exists

The transition is banked. The drop made the receipts **true** on H22 (PL §1). The mile plan (PL) says *what to build in what order*; the RETINA blueprint says *how the render receipt works*. Neither answers the one strategic question the Creative Director is asking: **what is this product, measured by, and queued behind?**

The answer reframes the whole roadmap around **the supervisor's layer** — an in-process co-processor that answers three questions a human running a shot actually asks: **what changed, did we get what we asked for, and can we get back.** Everything that answers those questions gets promoted. Everything that only makes chat *build faster* gets parked or killed — that race was already lost (the latency roadmap proved the LLM turn + the ~2s Houdini cook floor dominate; batching and node-building convenience save nothing measurable). Speed is not the differentiator. **The receipts are** (`harness/CLAUDE.md`: "The differentiator vs. Houdini's native MCP is the receipts. Protect that.").

This document is the aim. It is not a mile ladder and it does not compete with one.

---

## §1 · Ladder declaration (non-colliding)

> **Ladder PS** (proof-strategy) — this doc runs **SESSIONS, not miles.** Cite cross-doc as **`PS-S<n>`** (`PS-S1` … `PS-S5`), the five GUI sessions of §5. A session is a *human-at-GUI sitting*; it **advances** one or more existing PL miles — it never renames or replaces them.

Three ladders already exist and stay authoritative for miles:

- **RBK-M0…5** — the rulebook (`harness/SPEC.md` domain).
- **PL-M1…6** — the proof leg (`docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` §5). **Cite PL-M`<n>` for any mile.**
- **RETINA M0…5** — subsumed into PL-M4/M5 per the reconciliation; not cited independently here.

`PS-S<n>` is a **session token**, deliberately distinct from every `M<n>` ladder (CLAUDE.md → "Mile / ladder citation"; CRUCIBLE anti-sprawl ruling: partition GUI work with a session token anchored to the S-LIVE slug, never a fourth mile ladder). The map from sessions to miles is explicit in §5.

---

## §2 · The sentence — the product thesis

> **SYNAPSE swapped the crystal to Dark_Glass — and proved that the only pixels that changed belong to the crystal.**

Unchanged from the RETINA and PL blueprints (RETINA §0, PL §0). It ships this leg as **PL-M5 = RETINA M3**, Joe at the GUI. It is the first sentence in the product because it is the whole product compressed: a mutation with a *claimed visual consequence*, and a machine-checkable proof that the consequence is exactly what was claimed and **nothing else**. Receipts, not magic — extended from node graphs and cook events (already shipped) to **pixels** (the last unreceipted claim).

**Disclosure altitude (locked).** The public statement is the sentence plus the public tier framing (RETINA §4/§5 are marked public-safe at their stated altitude): a cheap deterministic change-containment check conditioned on scene truth SYNAPSE owns — the camera, the prim IDs, the AOV authoring, and the mutation intent. Everything below that altitude — mechanism specifics, the leak-pixel and SSIM thresholds as shipped, the event schema internals — is **NDA**. No mechanism content lands in a repo-committed doc, this one included (RETINA §5 rule; PL §G9 CIP-queue line).

**One shot carries the leg.** The five sessions run **one real shot** — the Dark_Glass scoped-delta scenario (Shot-010 lookdev-revert is the same thesis told twice; PL §0) — deeper each session. "Five sessions on one real shot" is both the demo path and the weekly ritual (§7): the eval loop pointed at the product.

---

## §3 · The supervisor's three questions — the product frame

This is the reframe. Each question below carries: **what exists** (asset-map verdicts, cited), **what the local H22.0.368 install offers** (scouts, tier-labelled), and **the one promoted wiring seam** — the single highest-leverage move that closes the gap with parts that already exist.

> Frame guard (CRUCIBLE, binding): the shipped panel `bl007_flag` heuristic and the shipped RETINA **T0** are **not** "M2/T1 already done." A file-truth check (EXR headers / AOV presence / resolution) is not a pixel-truth check (change-mask / containment / SSIM). Read the gaps honestly.

### Q1 — WHAT CHANGED

**What exists.** The change-detection machinery is wired on both paths but the trail is ephemeral, and the durable per-scene ledger is half-dormant:

- `IntegrityBlock` + topological scene hashing on the audited `/mcp` path — `shared/bridge.py:290-368` (asset-map, VERIFIED-LOCAL). Delta is **hash-level** (`delta_hash`), never a human-readable diff.
- Live-path integrity envelope on `/synapse` — `record_live_block` at `integrity_envelope.py:246`, live-called at `handlers.py:497` (both verified this dispatch). Honest, path-qualified, observe-only. **But the trail is in-memory and bounded — it dies at process exit.**
- The doc claim "all `agent.usd` provenance writers dormant" is **stale**: `create_task` / `update_task_status` / `write_verification` / `log_decision` are live on the autonomy-render and graph-synth paths (asset-map, VERIFIED-LOCAL). Only `log_routing_decision` / `log_handoff` / **`log_integrity`** remain caller-less — `log_integrity` defined at `agent_state.py:329`, **zero non-def callers** (verified this dispatch: grep found only the definition).
- `houdini_network_explain` / `get_stage_info` / `synapse_inspect_stage` are WIRED (asset-map) but answer "what **is** there," never "what **changed**" — no before/after diff mode on any of them.

**What H22.0.368 offers** (HFS + vendor-lens scouts):
- The full USD toolbelt ships in `bin/`: `usddiff` (hython-driven, exit-code-disciplined stage diff), `usdcat`, `usdchecker`, `usdtree`, `usdstitch`, `usdrecord` (HFS scout, VERIFIED-LOCAL). `pxr` lives in **`python313/Lib/site-packages/pxr`, not `houdini/python3.13libs`** — code hunting the latter finds nothing (HFS scout, VERIFIED-LOCAL).
- `hou.hipFile` event enum (`BeforeSave`/`AfterSave`/…) + `saveAsBackup` in the shipped `hou.py` (HFS scout, VERIFIED-LOCAL) — hookable scene-change/save events for a what-changed trail.
- The vendor's **own** Q1 model is *node = layer delta*: LOP `setLastModifiedPrims` is a first-class per-node change contract (toolkit `LOP_Sphere.C`, VERIFIED-LOCAL), and `hou.LopNode.activeLayer()` / `UsdUtils.GetDirtyLayers` capture the exact per-op change at zero invention cost (vendor lens, VERIFIED-LOCAL). **No first-class semantic stage-diff API landed in USD 0.26.5** — `usddiff` is flatten-and-text-diff; do **not** bet on a native semantic differ (vendor lens, INFERENCE-flagged).

**The one promoted seam — persist the live-envelope trail into `agent.usd` via the dormant `log_integrity`.** Pipe `record_live_block` (`integrity_envelope.py:246`) → `agent_state.log_integrity` (`agent_state.py:329`). One call inside the live-block path makes WHAT-CHANGED durable per scene instead of dying with the process. All parts exist; nothing is fabricated. The RFC that deferred this cited a fiction-risk rationale that **predates** evidence-derived anchors (CLAUDE.md §1.3) and honest N/A live blocks — stale for the live envelope (asset-map, INFERENCE, marked as such). *Add layer-level capture (`activeLayer` / `GetDirtyLayers`) beside the R1 topo hash for stage-touching ops — vendor-lens recommendation, own ratification, do not replace the hash.*

### Q2 — DID WE GET WHAT WE ASKED FOR

**What exists — the receipt PRODUCER is live; the receipt CHECKER is dormant.** This is the sharpest gap in the product.

- **Producer (WIRED).** Manifest writer + husk `.done` sentinel + in-EXR fingerprint fire on **every** render: `install_retina_hooks` at `handlers_render.py:466/476`, sentinel `retina_sentinel_postframe` at `handlers_render.py:467`, report attached at `handlers_render.py:693` under `result["retina"]` (all verified this dispatch).
- **Checker (DORMANT).** RETINA **T0** — the shipped v5.28.0 headline — is `retina/t0.py`, and it has **zero non-test callers** (verified this dispatch: importers are `tests/test_retina_t0.py`, `tests/test_retina_manifest.py`, `tests/test_retina_exr_header.py`, and itself; `handlers_render.py`'s only retina reference is the *sentinel*, not `verify_and_emit`). **Nothing verifies a real render's manifest.** The receipt is produced and never read.
- **M2 worker + T1 (MISSING).** Spec only (RETINA §9 M2, DOC-CLAIM). `retina/` today is `t0.py` + `exr_header.py` + fixtures — no worker process, no OpenCV/OIIO code, no baseline store.
- **`cops_analyze_render` is WIRED but hollow.** `handlers_cops.py:898` advertises `["black_pixels","dynamic_range","clipping","noise"]` (`:917`) and returns `overall_quality:"pass"` whenever `issues` is empty (`:994`) — but computes **no** pixel statistics (asset-map, VERIFIED-LOCAL: body reads only resolution/planes/cook errors). A "clean" report implies checks that never ran — the exact anti-pattern the T0 honesty contract exists to kill.

**What H22.0.368 offers** (HFS + toolkit + vendor-lens scouts):
- **`husk --postframe-script` EXISTS on 22.0.368** — the RETINA key-catch (post-pixels sentinel) survives the drop; plus new `--pre/postsnapshot-script`, `--extra-metadata` (JSON EXR-header stamping), `--list-settings/-passes/-cameras` preflight (HFS scout, VERIFIED-LOCAL).
- Every husk frame auto-carries a machine-readable receipt in the EXR header: `husk:render_stats` / `husk:command` / `husk:usd_file`, plus the SYNAPSE fingerprint traveling inside the header (perception catalog, VERIFIED-LIVE). `iinfo.exe` + `OpenImageIO` ship for readback.
- `ROP_Dumper.C` is the render-receipt HDK skeleton (`startRender`/`renderFrame`/`endRender` + the pre/post script template block) — but there is **no** Hydra/Karma delegate or husk sample anywhere in the toolkit (toolkit scout, VERIFIED-LOCAL): no hookable layer exists between "ROP fires" and "pixels exist" for Karma, which **reinforces `husk --postframe-script` as the only practical Karma receipt point**.
- **Receipt-integrity hazard (vendor lens, INFERENCE):** file-existence no longer implies asked-for-quality. `husk --karma-percent-of-samples` writes a **final-path** EXR at reduced sampling; `--snapshot`/`--skip-existing-frames` write partials or skip stale frames. A percent-of-samples EXR passes every T0 existence/size check while being quantitatively not what was asked for — **mitigated for free** by parsing the auto-stamped `husk:command` header (confirming NOW-probe named in the vendor lens).
- **OCIO is a package** shipping **ACES 2.0 on OCIO 2.5**, default view **Un-tone-mapped**, and there is **no `houdini/ocio` dir** (HFS scout, VERIFIED-LOCAL). Cross-major pixel comparisons vs H21 (ACES 1.3) are **invalid unless the view is pinned** — a hard constraint on any T1 baseline.

**The one promoted seam — call `retina.t0.verify_and_emit` from the render-complete path.** `handlers_render.py:693` already carries the manifest in `result["retina"]`; `retina/t0.py:353` `verify_and_emit(manifest, now, jsonl_path)` is ready (asset-map, VERIFIED-LOCAL). One post-render (or `.done`-triggered) invocation closes the receipt loop with **zero new code in `retina/`** — the minimal honest M2 step: **T0 verdicts on a real render today, T1 worker later.** This single seam makes the shipped v5.28.0 headline actually do its job.

### Q3 — CAN WE GET BACK

**What exists — reversibility is real on `/mcp`, drifting on `/synapse`.**

- `houdini_undo` / `houdini_redo` WIRED (`handlers.py:760-780`, global stack, one level) and the `/mcp` bridge hash-guarded rollback WIRED (asset-map, VERIFIED-LOCAL).
- **The known drift, confirmed and quantified.** 40+ handler sites wrap `hou.undos.group`, but the **four highest-traffic mutators do not**: `handlers_node.py` `_handle_create_node:43`, `_handle_delete_node:120`, `_handle_connect_nodes:141` (verified this dispatch: **zero** `hou.undos.group` in the file) + `set_parm` at `handlers.py:922` (asset-map, VERIFIED-LOCAL). One `performUndo` ≠ one operation exactly where it matters most — and this is the `CLAUDE.md` Identity drift note, live.
- Panel revert is **prompt-mediated, not deterministic**: `synapse_panel.py:1143-1150` sends "Undo the last change using `houdini_undo`…" — an LLM round-trip decides what reverts (asset-map, VERIFIED-LOCAL). The Q3 close on the Review face depends on the model choosing to call the tool, compounded by the granularity gap above.

**What H22.0.368 offers** (HFS + vendor-lens scouts):
- The full `hou.undos` surface is present (`group`/`disabler`/`performUndo`/`undoLabels`/…; HFS scout, VERIFIED-LOCAL) — every API the evidence-derived `undo_group_active` mechanism reads exists.
- LOP layer isolation intact (`editableLayer`/`activeLayer`/`layersAboveLayerBreak`; HFS scout, VERIFIED-LOCAL); `usdchecker` + six validator plugin sets back the `composition_valid` anchor.
- The vendor's **own** revert story is **layer-granular, not undo-stack**: a scoped override layer you drop/mute (`Usd.Notice.LayerMutingChanged` is table-present; vendor lens, VERIFIED-LOCAL) — a revert path that **survives session end and undo-stack eviction**, which `hou.undos` cannot.

**The one promoted seam — wrap the four unwrapped mutators in `hou.undos.group`.** `handlers_node.py:43/120/141` + `handlers.py:922`, using the idiom that already appears 40+ times in sibling handler files (asset-map, INFERENCE — it is a copy of an established in-repo pattern, not new machinery). Closes the single known reversibility drift, makes `houdini_undo` deterministic for the most common ops, and retires the `CLAUDE.md` drift note. *When C.2/SOL-04 (reversible pxr-authoring) builds, adopt named-layer edit-target discipline so agent stage edits get a revert path that outlives the undo stack — vendor-lens recommendation, WAVE-COUPLED to C.2.*

---

## §4 · Triage register — the roadmap, re-aimed

> Ranked by the supervisor frame, not by build convenience. **Nothing irreversible in paper:** every KILL is PARKED-with-reopen-gate unless it is genuinely done. SSOT cite per row — dispositions live in the cited file, not here. CRUCIBLE triage overrides are binding and applied.

### PROMOTE — answers a supervisor question (critical path)

| Item | Question | One line | SSOT |
|---|---|---|---|
| **RETINA M3** (PL-M5) | Q2+Q1 | The sentence. Dark_Glass scoped-delta, PROOF line in the receipt, consent gate carries the verdict. Everything queues behind it. | RETINA §5/§9 · PL §G4 |
| **RETINA M2** (PL-M4) | Q2 | **The headless critical path feeding M3** (CRUCIBLE: T0 cannot make the containment claim; only T1 can). Worker venv + OIIO/OCIO + T1 kit + verdict events. | RETINA §9 M2 + reconciliation |
| **Q2 seam: `verify_and_emit` wiring** | Q2 | Call T0 from render-complete — makes the shipped receipt actually run (verified dormant, §3). | `retina/t0.py:353` · `handlers_render.py:693` |
| **Q1 seam: `log_integrity` persistence** | Q1 | Pipe live envelope → durable `agent.usd` ledger (verified dormant, §3). | `integrity_envelope.py:246` → `agent_state.py:329` |
| **Q3 seam: wrap the four mutators** | Q3 | Close the undo drift; deterministic revert for the common ops (verified unwrapped, §3). | `handlers_node.py:43/120/141` · `handlers.py:922` |
| **G2 live session** (PL-M2) | Q2 evidence | The great unblocker — converts every PROVISIONAL-headless stamp to trusted truth; gates C.4/C.3/C.10. Joe-at-GUI. | PL §G2 → SPEC S-LIVE |
| **RETINA M5** (PL-M6) | proof/G6 | Verdicts-per-token counters — the only thing that puts a **number** on token-frugality (proof-class, not speed). | RETINA §9 M5 · PL §G6 |
| **C.4 → C.3 → C.10** (PL-M3) | Q2 honesty | Ratified, spec-frozen COP builds that kill placebo tools (accept settings, silently do nothing). Serialized. | `SYNAPSE_COPERNICUS_EXPANSION.md` |
| **G1a U.5-H22 / G1b mtlx** (PL-M1) | Q1/correctness | **DONE at HEAD `d441738`** (C-U5 + C-MTLX merged) — the last two silent-wrong twins. Close the queue entries. | PL §G1 · HEAD subject |
| **C.1 / NWS-04** — real ImageLayer stats | Q2 honesty | Kill the hollow `cops_analyze_render` (verified advertises 4 checks, computes none, §3). Same-file, sequences after the C-cycles. | `handlers_cops.py:898-1002` |
| **KAR-14** detection wiring | Q2 | Make the Indie husk silent-no-render trap detectable; husk-on-Indie now real, so wire the anti-receipt check. | PL §8 · perception catalog |
| **D.0** diagnostic truth | Q1 | Recook-explainer + callback-diagnosis: "why did the scene recook." Ratified, phantom-first, TOPs untouched. | `flywheel_queue.json` D.0 · `spec-D-diagnostic-truth.md` |
| **C.2 / SOL-04** reversible pxr-authoring | Q3 | Replaces CRITICAL-gate raw `execute_python` for set-dressing; probe-verified on 22.0.368. Adopt named-layer discipline. | `flywheel_queue.json` C.2 · PL §8 |
| **C.7 / SOL-02** Prune-LOP | Q3 | Deactivation-not-deletion — revert path native to the op; cheapest reversibility feature. | `flywheel_queue.json` C.7 |
| **CTO-05** guarded-degradation honesty | Q1 | Silent `try/except` degradations become fidelity<1.0 receipt notes ("symbol X absent on this build"). The class fix behind SB-1..SB-5. | `flywheel_queue.json` CTO-05 · PL §G7 |
| **Panel chat/Review face** | Q2/Q3 entry | The supervisor's approve/revert surface — consent gate auto-surfaces (verified `synapse_panel.py:684-707`). PROMOTE, never kill. Harden (G2 boot, `exec_` guard). | `synapse_panel.py` · `face_review.py` |
| **N-13** `menu.exec_()` guard | Q2/Q3 robustness | Crash guard on the consent/review entry point; copy the four guarded siblings. | `chat_panel.py:499` · PL §G8 |
| **G9 public-mirror drift** | governance | Public repo teaches `setx ANTHROPIC_API_KEY` (confirmed billing-failure pattern). Ruling: refresh cadence or freeze-with-note. Silent drift is the only wrong answer. | PL §G9 (VERIFIED-WEB) |
| **W.6 corpus reseed** | correctness | Purge stale corpus (ACES 2.0, husk trap-pin, `planes()` recipe) — scout re-teaches every un-purged lie each turn. Absorb W.3b. | `flywheel_queue.json` W.6 · PL §G7 |
| **W.5b** write-path property-kind honesty | Q2-adjacent | New silent-wrongness edge; must land **before** usd-1 golden-pins the write path. | `flywheel_queue.json` W.5b |
| **CTO-02 / CTO-03** alias + instancing-intent | correctness | CTO-02: enumerate alias-propped emits (cheap G2 rider). CTO-03: intent-aware instancing successor (copytopoints vs scatterinstances). | `flywheel_queue.json` CTO-02/03 |
| **G8 memory analyst section** | evidence debt | Commission the owed Memory/substrate section before memory-wave goldens. | PL §G8 |
| **G5 port waves** (PL-M6) | correctness | scene-2 → … → memory-2, coupling-ruled; forge/assayer/crucible grind, human merge per wave. | `PORT_WAVE_MANIFEST.md` · PL §G5 |
| **C.5 / TOPS-02+05** · **C.0** · **S.0** · **R.0** | Q2/correctness | Farm-item telemetry; context/studio/release readiness truth (regression gates, harness reviews-never-rewrites). Ratify-gated. | `flywheel_queue.json` |
| **U.1b · U.2 · U.3 · U.4 · N-11 · P3-order · W.4b** | correctness (P3) | The wiring/parm/arity truth line + resolver hardening + corpus probes — headless sweeps, human-flip pending. | `flywheel_queue.json` |

### PARK — real value, wrong lane now; explicit reopen gate

| Item | One line | Reopen gate | SSOT |
|---|---|---|---|
| **C.6 / TOPS-08** warm services | Compounds the G6 verdicts-per-token **number**, but the raw value prop is the lost speed race. | **M5 counters exist to measure the gain** (CRUCIBLE-affirmed). | `flywheel_queue.json` C.6 · PL §G6 |
| **C.8 / KAR-05** husk resume | Crashed-overnight-render restart — real solo value, below every silent/receipt class. | Earns a slot after the receipt lanes; `--help` probe rides the husk bundle. | PL §8 |
| **C.9 / KAR-04** RenderPass prims | Vendor is promoting the Pass prim across CLI+schema+usdview (vendor lens) — trajectory-aligned but no judge lens carried it top-8. | Bundle with C.8; schema probe now-legal. | PL §8 |
| **CTO-04** cop2net-sunset register | Names a deadline, not an emergency; contingency has not fired. | A major-version signal, or C.4 widening. | `flywheel_queue.json` CTO-04 |
| **W.7b** reconnect-budget derive | Comfortable under solo/auth-disabled posture. | **auth/multi-user enabled.** | `flywheel_queue.json` W.7b |
| **`hou._imagePlanes`** private-API posture | Only plane-listing API on 22.0.368; quarantined from emission. | Joe rules adopt-with-pin vs keep-quarantined (start-line #10). | PL §4 item 10 |
| **N-14** panel touch-target sizing | 13 sub-26px targets; the one live G3 WARN. | Joe's taste call **against real GUI pixels** — which only exist after PS-S2. | PL §4 item 8 |
| **N-15** cyan 3-source reconciliation | Known gremlin; naive unify breaks `test_hda_panel`. | Schedule with full-suite-green + `test_hda_panel` lockstep, never naive. | PL §G8 |
| **ML TOP family · scatterinstances template · HOM-01/03 · G9 vendor asks · G9 CIP review · G8 pre-stage debt** | Greenfield/paper/design-only; no receipt or correctness debt rides on them now. | A demand signal, a demo shot, or a Joe ruling — recorded so nothing is lost. | PL §8/§G8/§G9 |

### KILL — reframed as PARK-with-reopen or close-as-done (nothing deleted)

| Item | Disposition | SSOT |
|---|---|---|
| **SOL-14** Component Builder wrapper | **PARK-with-reopen** — pure node-building convenience in the lost speed race; no receipt/reversibility/provenance angle. Reopen gate: a demo shot demands render-time component building. (CRUCIBLE: the one clean value-prop kill.) | PL §8 |
| **CTO-01** agent.usd USD round-trip probe | **CLOSE-AS-DONE** — probe already ran, PASSED fidelity 1.0 on live pxr 0.26.5 (`h22-live-reconfirm-2026-07-16.md §3`); memory-1/2 unblocked. **Flip queue status → done (belt-and-suspenders), do not delete** (CRUCIBLE). | `flywheel_queue.json` CTO-01 |
| **U.1** original H21 wiring-truth cycle | **CLOSE-AS-DONE** — shipped (PR #39), superseded by merged U.1-H22; living line continues via U.2/U.3/U.4. Flip status → done. | `flywheel_queue.json` U.1 |

---

## §5 · The five sessions — the human-at-GUI partition

> **CRUCIBLE correction, binding:** "one GUI sitting = four birds" is optimistic. The honest floor is **at least 3 GUI sittings**; **M3 is a separate PL-M5 gate**, not part of the G2 sitting. This section expands to **five** to match the weekly cadence (§7): PS-S1/PS-S2 are the crucible's Session-A/B (the G2 grind, PL-M2); PS-S5 is its Session-C (the demo, PL-M5); PS-S3/PS-S4 are the interleaved live-verification beats the headless builds need. **No session claims a mile it does not reach.**

Each session is one sitting inside graphical H22.0.368 with the bridge up, Joe at the GUI. Every listed artifact lands under `docs/reviews/` or `harness/notes/` (paper territory, `harness/SPEC.md` §2). The headless lane (§6) grinds between sessions.

### PS-S1 — the debris ruling + the Copernicus-gating probes  → advances PL-M2, gates PL-M3
- **Entry gate:** bridge up; `/obj` reachable. **Literal first act: the SCOUTMASTER debris ruling** — `/obj/_recon_planes2` (+ `_w4assay_net`): active leg or debris? P-1 was SCENE_BUSY-blocked in all three prior probe legs; **nothing cooks until `/obj` is clean** (PL §G2 step 1, start-line #7 — UNRULED).
- **Contents:** P-1(a–e) per the expansion OWED list (SAM2/MoGe-2 `provider` menus · `usdmaterial` dynamic parms · live `inputLabels` · `fractalnoise` menu tokens · minimal bound cooks) + P-2 stamp/scatter modern-target enumeration (regex over the 384 Cop types + parm capture).
- **Artifacts:** dated `harness/notes/` probe artifact + connectivity-catalog regen (hash-stamped, byte-coherent).
- **Exit:** debris ruled; P-1/P-2 artifacts committed. **This is the most-gating session — C.4 cook verdicts, C.3 provider menus, C.10 label capture all ride it.**

### PS-S2 — provisional lifts + panel + SOP parms  → completes PL-M2
- **Entry gate:** PS-S1 artifacts committed.
- **Contents:** re-stamp on the live bridge — the 10 CHANGED COP scaffold verdicts · N-5/N-3 · the 4 mtlx PASS + G1b's shipped `mtlxvolume` substitute (zero live mtlx coverage today) · the node-named-prim-path trap re-check with guard-or-document. **Panel G2** — boot the real `SynapsePanel` in the host (no `_Hou` stub): real widget geometry, GUI `QFontDatabase`, real pixels for the 13 sub-26px targets. **SOP parm probe** — names/defaults/menu values for the core driven set + the VEX `run_over`→`class` (0–3) smoke cook.
- **Artifacts:** provisional stamps lifted; `docs/reviews/` panel-G2 note; SOP parm-introspection artifact; `audit_panel.py:6` stale-"21.0.671" repoint.
- **Exit:** PL-M2 discharged. N-14 sizing becomes a live-pixel taste call for Joe (PARK reopen fires here).

### PS-S3 — Copernicus live-verification + first weekly shot run  → advances PL-M3
- **Entry gate:** C.4/C.3/C.10 built headless (§6) on the PS-S1/S2 truth; PS-S2 lifts committed.
- **Contents:** live-verify the Copernicus cook verdicts / provider menus / label capture the headless builds deferred; run the **first weekly Dark_Glass shot** through SYNAPSE end-to-end (§7), harvesting frictions.
- **Artifacts:** Copernicus live-verify note; first weekly receipt bundle (§7); friction deposits (`ratified:false`).
- **Exit:** C.4/C.3/C.10 verdicts trusted; first real-shot receipt bundle exists.

### PS-S4 — RETINA M2 live-integration + Dark_Glass dry-run  → advances PL-M4
- **Entry gate:** M2 worker + T1 crucible-passed headless (§6); Q2 `verify_and_emit` seam wired.
- **Contents:** integrate the T1 worker against a **real render** of the shot; T0+T1 verdicts land on the perception channel for actual pixels; Dark_Glass scoped-delta **dry-run** (not yet the demo — proves the change-mask ∩ ID-matte pipeline on real frames). Pin the OCIO view (ACES 2.0) so metrics are valid.
- **Artifacts:** first T1-on-real-pixels verdict events; dry-run containment result; friction deposits.
- **Exit:** the containment pipeline is proven on real frames — one step short of the sentence.

### PS-S5 — the demo  → PL-M5 (RETINA M3), **the sentence ships**
- **Entry gate:** PS-S4 dry-run clean; M2 merged.
- **Contents:** RETINA M3 end-to-end on Dark_Glass — the PROOF line lands in the receipt, the consent gate carries the verdict. Joe at the GUI.
- **Artifacts:** the demo receipt (PROOF line); the recorded run; final weekly friction harvest.
- **Exit:** **"proved that the only pixels that changed belong to the crystal"** — shipped. Human merge (PL-M5 gate).

**Session → mile map (no new ladder):** PS-S1→PL-M2(gates M3) · PS-S2→PL-M2 · PS-S3→PL-M3 · PS-S4→PL-M4 · PS-S5→PL-M5. PL-M6 (waves + M4 + M5-number + class fixes) is the long tail after PS-S5, sequenced not owed (PL §5).

---

## §6 · The headless lane — what grinds without Joe

forge/assayer/crucible run these in parallel between GUI sessions. WIP=1 per the harness, human merge per sprint (`harness/SPEC.md` §1; `harness/CLAUDE.md` "promotion to main is human"). Each points at its existing spec-of-record — **this doc adds no new spec.**

| Headless work | Feeds | Spec of record |
|---|---|---|
| **RETINA M2 worker + T1 kit** (own venv, `opencv-python-headless`, OIIO/OCIO ingest, verdict events) — crucible-testable with synthetic manifests, no Houdini until PS-S4 | PS-S4 → PL-M5 | `SYNAPSE_RETINA_BLUEPRINT.md` §9 M2 + reconciliation |
| **Q2 seam** — wire `verify_and_emit` from render-complete | the checker loop | `retina/t0.py:353` · `handlers_render.py:693` (this doc §3) |
| **Q1 seam** — `record_live_block` → `log_integrity` persistence | durable ledger | `RFC_agent_usd_ledger.md` (stale deferral) · `integrity_envelope.py:246` |
| **Q3 seam** — wrap the four mutators in `hou.undos.group` | deterministic revert | `handlers_node.py:43/120/141` · sibling idiom |
| **Review-face receipt surfacing** — draw hash-delta + T0 verdict + IntegrityBlock on the face (data exists in-process, face doesn't draw it) | Q2/Q3 UI | `face_review.py` · `panel/session_integrity.py` |
| **C.4 → C.3 → C.10** headless FORGE portions (honest-deferred envelopes designed for exactly this) | PS-S3 → PL-M3 | `SYNAPSE_COPERNICUS_EXPANSION.md` |
| **C.1 / NWS-04** real ImageLayer stats (kill the hollow analyzer) | Q2 honesty | `handlers_cops.py:898-1002` |
| **CTO-05** class fix · **W.6** corpus reseed · **W.5b** write-honesty | Q1/correctness | PL §G7 |
| **G5 port waves** (scene-2 → … → memory-2) | PL-M6 | `PORT_WAVE_MANIFEST.md` |
| **N-13** `menu.exec_` guard · **U.1b/U.2/U.3/U.4/N-11** truth sweeps | robustness/correctness | PL §G8 · `flywheel_queue.json` |
| **G8 memory analyst section** (commission before memory waves) | evidence debt | PL §G8 |

**Guard (CRUCIBLE, binding):** the M2 worker and the T1 kit are the **headless critical path** — a T0-only demo cannot ship the sentence (T0 file-truth structurally cannot make a containment claim). M2 blocks PS-S5, so it leads the headless queue.

---

## §7 · The weekly shot ritual — the eval loop pointed at the product

One real shot through SYNAPSE, every week, from PS-S3 onward. Frictions become flywheel deposits. This is the Creative Director's brief item (3) made mechanical: artist-hours **inside** the product, the eval loop aimed at the thing that ships.

**Shot selection criteria (in order):**
1. **The one shot is Dark_Glass** (the demo scenario) for the leg — depth over breadth; five runs of one shot beat one run of five shots.
2. It must exercise all three questions: a mutation with a claimed visual consequence (Q2), a recorded change (Q1), and a revert path (Q3).
3. It must be renderable at verification scale (half-res beauty + integer object-ID AOV, RETINA §5) — no full-res, no real final render inside a golden (manifest hard rule, RETINA §8).

**The receipt bundle a run must produce** (the run is not "done" until all exist):
- **Q1:** an `agent.usd` ledger entry per mutation (decision + reasoning + revert), and — once the §3 seam lands — a durable `log_integrity` block. No ledger entry ⇒ incomplete (`harness/CLAUDE.md`).
- **Q2:** a T0 verdict on the real render (via the `verify_and_emit` seam), rising to a T1 containment verdict from PS-S4.
- **Q3:** a deterministic revert that returns the scene to pre-run state (via the wrapped mutators).

**Friction → deposit protocol.** Every friction — a silent-wrong, a missing receipt, a phantom, a non-deterministic revert — is written as a `flywheel_queue/v1` candidate (verified schema this dispatch: `harness/state/flywheel_queue.json`):

```json
{ "id": "<PS-Sn>-<slug>", "title": "<what broke, in supervisor terms>",
  "status": "candidate", "evidence": ["<artifact path>", "<file:line>"],
  "ratified": false,
  "note": "Harvested from the weekly Dark_Glass run PS-S<n>. <one supervisor-frame line>." }
```

`ratified:false` is the resting state — a candidate is a proposal, never a work order (the anti-runaway anchor; only a human flips ratification). The harness appends candidates; it never self-authorizes them.

**The honest metric.** A week is measured by **receipts produced + frictions harvested** — *not* by build speed, node count, or tools shipped. A run that produced a clean receipt bundle and zero frictions is a strong week. A run that surfaced a silent-wrong is *also* a strong week — it turned an invisible lie into a ratifiable candidate. Speed is not on the scorecard (P5 posture: judgment is the product, not a tool-count race; `harness/SPEC.md` §4).

---

## §8 · Non-goals + disclosure

**Locked non-goals (inherited verbatim — CRUCIBLE false-positive guard: do not regenerate these intentional omissions as "gaps").** Sources: PL §6, RETINA §11, `harness/state/flywheel_queue.json`, `authoring_domains.json`.

- **Rigging / KineFX / APEX** — structural refusal, `check_no_rigging_drift`-enforced; twice re-affirmed this window (keynote MCP + fabricated memo both rejected). The refusal got *more* correct, not less.
- **Shader / VOP authoring** — graph plumbing only.
- **Vector similarity for cognitive state** — Non-Goal 6, the one-Moneta ruling stands (Moneta *is* the shipped memory backend; cognitive *state* ≠ vector similarity).
- **`hwebserver` core migration · polling-based background audit.**
- **CHOP · DOP/MPM sim frontier** — documented non-goals (RULED, PL §4 items 5–6); `M.DOP-recon` is scoped-recon-then-freeze, not new sim capability.
- **Component Builder / SOL-14** — parked, no receipt angle (§4).
- **Verdict-USD writes** — RFC-gated (holder: M. Gold), off this project's critical path; verdict persistence stays sidecar JSONL until the customData RFC lands (RETINA §7).
- **No golden performs a real render** (manifest hard rule) · **no agent presses `downloadmodels`** · **no disk export from bake/terrain v1.**

**No new CI machinery without a consumer.** This strategy adds **zero** new checks, no new harness track, no new mile ladder. The seams in §3 are wirings of existing code; the sessions in §5 run existing specs; the ritual in §7 deposits into the existing `flywheel_queue/v1`. A guardrail is added only when a ratified cycle needs it (the `check_c3_moneta_surface` precedent, `harness/SPEC.md` §8).

**Sprawl rules (CRUCIBLE anti-sprawl, binding).** No fourth mile ladder — `PS-S<n>` is a *session* token that advances PL miles. Cite `PL-M<n>` for miles. This doc is the strategy layer: it re-aims, it never restates build content (one source of truth per surface).

**Disclosure.** Public-safe at the altitude written here. RETINA §5 mechanism, thresholds-as-shipped, and event-schema internals are **NDA**. The scoped-delta **system claim** is queued for CIP review under the existing filings before any external mechanism-level discussion — no mechanism content in any repo-committed doc (RETINA §5; PL §G9). The vendor-facing page (PL §G9 §10 asks) stays ready; no outreach this leg unless Joe rules otherwise.

---

## §9 · Definition of Done + ratification block

**DoD for the strategy leg (this document).** The strategy leg is done when the sentence ships:

1. **PS-S1–PS-S5 discharged**, each exit criterion met, each artifact committed (§5).
2. **The three seams wired and live on a real shot** (§3): `verify_and_emit` called from render-complete (Q2), `log_integrity` persisting the live-envelope trail (Q1), the four mutators wrapped (Q3).
3. **RETINA M3 shipped** — PROOF line in the receipt, consent gate carries the verdict, on Dark_Glass, Joe at the GUI (PL-M5).
4. **≥3 weekly shot runs** produced full receipt bundles and their frictions were deposited as `ratified:false` candidates (§7).
5. **The triage register (§4) is reflected in the queue** — CTO-01 and U.1 flipped to `done`; SOL-14 parked with its reopen gate; the PROMOTE seams have ratified cycles.

The leg's DoD is satisfied at **PS-S5 + the PL-M6 items that gate it** — the rest of PL-M6 is sequenced, not owed (PL §5).

**Ratification block — what Joe flips (this doc is DRAFT until he does):**

| # | Decision | Recommendation carried | Blocks |
|---|---|---|---|
| R1 | **Adopt this strategy layer** — supervisor frame governs roadmap priority; speed is off the scorecard | adopt | the whole aim |
| R2 | **PS-S ladder** — five sessions, one real shot, as §5 | adopt (matches "five sessions on one real shot") | session dispatch |
| R3 | **The three §3 seams enter the headless queue** as ratified cycles (`verify_and_emit`, `log_integrity`, mutator-wrap) | ratify ×3 | Q1/Q2/Q3 closure |
| R4 | **SCOUTMASTER debris ruling** (`/obj/_recon_planes2` + `_w4assay_net`: clear or preserve) | — (probe-hygiene call; PS-S1 literal first act) | **PS-S1, all of PL-M2** |
| R5 | **Triage dispositions** — flip CTO-01/U.1 → `done`; SOL-14 → parked-with-reopen | adopt | queue hygiene |
| R6 | **G9 public-surface policy** — refresh cadence or freeze-with-note | — (either; not silent) | G9 |
| R7 | **Append the §Amendment to `harness/SPEC.md`** (returned as text; Joe applies by hand) | apply | dispatch authority |

Standing gates unchanged: **per-cycle human merge · `ratified:false` resting state · suite-floor promotion is human-only.** The start-line rulings already carried in PL §4 (OD-A/B/C/D, CHOP/DOP non-goals, RETINA M2 ratification) are not re-opened here.

---

*ARCHITECT writes the strategy and never the code. This document is paper: it mutates nothing. It re-aims the mile plan and the receipt organ around one question — not "how fast did it build" but "what can it prove" — and where it disagrees with the live 22.0.368 runtime or the repo at HEAD `d441738`, the runtime and the repo win. The sentence ships at PS-S5.*
