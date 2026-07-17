# SYNAPSE_H22_PROOF_LEG_BLUEPRINT

**The proof leg — the drop made the receipts true; this leg makes them prove something.**

| | |
|---|---|
| **Doc ID** | `SYNAPSE_H22_PROOF_LEG_BLUEPRINT` v1.0 |
| **Status** | ARCHITECT output — governing document. Per **F3**, this commits **before** any FORGE execution it governs. |
| **Date** | 2026-07-17 |
| **Baseline** | SYNAPSE **v5.28.0** (HEAD `72de5f1`, tag `v5.28.0`) · Houdini **22.0.368** live (py 3.13.10 / USD 0.26.5 / PySide 6.8.3, `harness/state/drop.json`) · Wire Protocol 4.0.0 |
| **Lineage** | Successor to `docs/SYNAPSE_H22_GAP_BLUEPRINT.md` v2.1 (drop week, discharged). Synthesizes: `h22-cto-roadmap-2026-07-16.md` · `h22-per-context-postmortem-2026-07-17.md` §5 · `SYNAPSE_RETINA_BLUEPRINT.md` v1.0 + `retina-reconciliation-2026-07-16.md` · `SYNAPSE_COPERNICUS_EXPANSION.md` · `h22-sidefx-cto-lens-2026-07-16.md` · `h22-live-reconfirm-2026-07-16.md` · both doc-intel waves · both intake adjudications. It **points at** the frozen specs; it never duplicates them (one source of truth per surface). |
| **Provenance tier** | Every claim below is **RECORDED** from a committed artifact (cited) unless tagged otherwise. This document was authored off-repo; it re-derives nothing against the live tree. **SPEC.md step 0 (grounding pass) re-verifies every load-bearing pin before any dispatch.** Where this document and the live runtime or repo disagree, the repo and runtime win. |
| **Disclosure** | Public-safe at the level written here (matches the RETINA blueprint's own line). Mechanism claims, thresholds-as-shipped, and filing specifics stay NDA/CIP-side. |

---

## §0 · The demo sentence

> **SYNAPSE swapped the crystal to Dark_Glass — and proved that the only pixels that changed belong to the crystal.**

Unchanged from the RETINA blueprint. Drop week earned the right to say it; **this leg ships it** (Mile 5 = RETINA M3, Joe at the GUI). The Shot-010 lookdev-revert story and the Dark_Glass scoped-delta proof are the same thesis told twice: deterministic substrate truth, receipts not magic. One of them lands this leg.

---

## §1 · Position — what the transition banked

Verified in `h22-per-context-postmortem-2026-07-17.md` (SCRIBE-verified HEAD/tag/queue) and `h22-live-reconfirm-2026-07-16.md` unless noted:

| Banked | Evidence |
|---|---|
| Dual-ABI vendor tree (cp311 + cp313), enforcement chain test-pinned | `h22-abi-verdict.md` · commit `38b33b6` |
| W.1/W.1b planes migration + **loud `api_drift`** instinct — VERIFIED-LIVE | live-reconfirm §1.1 · merge `cd3983f` |
| W.3 set-dressing renames (`paintinstances`/`copytopoints`/`pointinstancer`, canonical spellings) | postmortem LOP §4 · `b5570f8` |
| W.5 karma **relationship** read/write fallback in `handlers_usd.py` — VERIFIED-LIVE | live-reconfirm §1.3 · `dab186d` |
| U.1-H22 **major-aware wiring** (`connectivity_22.json`, fail-loud resolver) | postmortem LOP §4 · `9b36b4d`/`2c17149` |
| W.4 solver blocks: explicit `block_begin.blockpath` binding (fix shape live-decided) | live-reconfirm §2.1 · `34f41f7` |
| Quarantine settled: `hou.secure` **REFUTED-LIVE**, GUI caveat retired; 4 phantoms re-pinned; auth resolver never auto-adopts | live-reconfirm §4 |
| **CTO-01 moat probe PASS** — memory-evolution round-trip fidelity **1.0** on live pxr 0.26.5; memory-1/2 waves unblocked | live-reconfirm §3 |
| **RETINA M0 + M1 shipped as v5.28.0** — zero-cv2 pin, perception truth catalog (`perception_truth_22.0.368.json`, buffer→numpy VERIFIED-LIVE incl. bottom-left origin), T0 render receipt; crucible caught + fixed the dead `.done` sentinel (`64e49fc`) | postmortem §1/§6 · `f9032e4` → `72de5f1` |
| Copernicus expansion **ratified** (`C.4`/`C.3`/`C.10` `ratified:true`) with a frozen build spec | `SYNAPSE_COPERNICUS_EXPANSION.md` · `09d265a` |
| Two intake adjudications held the line: fake "SideFX memo" refuted (fabricated specifics, APEX pressure rejected twice); Copernicus scope-expansion language rule set (cite the feature list, never "unified world-building") | `adjudication-sidefx-h22-memo.md` |
| Suite floor of record **4275 / 0 / 87** (`harness/verify/suite_baseline.json`); last observed green 4387/0/97 post-W.4 — floor advances are **human-promoted only** | expansion §Grounding |

**Standing constraints carried forward:** H21.0.671 uninstalled (H21-diff claims are H22-truth-vs-code, never proven deltas); H21.0.773 present as the second-major release-gate instance (same-major-stale caveat on the frozen 21.0.671 catalogs — `U.1b` deposit). Port waves: **scene-1 has run**; the rest of the manifest order is pending. MODE B.

---

## §2 · The three races (energy thesis)

1. **Truth debt before goldens.** Two known places SYNAPSE is still quietly false on H22 — the **context twin** (`graph_validator` serving H21 Solaris CONTEXT truth to H22 stages) and the **mtlx phantom** (`mtlxstandard_volume` still emitted in recipe text) — plus a stack of PROVISIONAL-headless stamps and three PENDING-BEHAVIORAL cook verdicts. Same rule as drop week: an unfixed silent-wrong that reaches its wave gets golden-pinned as spec. Fix-before-freeze.
2. **Paid-for paper, zero code.** C.4→C.3→C.10 are ratified with a frozen spec; RETINA M2→M3 are governed by a reconciled blueprint with six aimed probes already banked. The design debt is discharged — this leg is FORGE's.
3. **The proof.** M3's Dark_Glass demo is the one-sentence product proof; M5's verdicts-per-token counters finally put a **number** on the token-frugality claim (the original G6, still numerically unproven). Two independent external syntheses already converged on the in-process co-processor thesis — the differentiation window is consensus-legible. Ship proof, not more paper.

---

## §3 · Gap register

> Ranked by (blocking-power × silent-wrongness), the drop-week merge rule's spirit. Each entry names its lane, its gate, and where its full spec lives.

| # | Gap | Class | Lane | Gate |
|---|---|---|---|---|
| **G1** | The two silent-wrong twins: **U.5-H22 context fold** + **mtlx phantom kill** | silent-wrong | two small ratified cycles | ratify + per-cycle merge |
| **G2** | **The live session** — P-1/P-2 probes, provisional lifts, panel G2, SOP parms | evidence debt | one structured GUI sitting | SCOUTMASTER debris ruling · Joe at GUI |
| **G3** | **Copernicus builds C.4 → C.3 → C.10** | ratified build | per frozen spec | OD-A/B/C/D · per-cycle merge |
| **G4** | **RETINA M1b → M2 → M3** — the demo | ratified build | per RETINA blueprint + reconciliation | M2 ratify · M3 = Joe at GUI |
| **G5** | **Port waves resume** (scene-2 → … → memory-2) with coupling rules | port debt | manifest order | OD-1/2/3 state confirm · per-wave merge |
| **G6** | **The number** — M5 counters land the token-frugality benchmark | proof | RETINA M5 (+ pool: TOPS-08 warm services) | rides M5 ratify |
| **G7** | **The class fix + corpus reseed** — CTO-05 guarded-degradation → fidelity receipts; W-6 stale-corpus purge | class fix / corpus | own ratifications | ratify |
| **G8** | **Coverage rulings + honest debt** — CHOP & DOP/MPM scope, memory section owed, opalias enumeration, SOP census, OpenPBR posture, dev-hygiene pins | debt ledger | rulings + small cycles | start-line rulings |
| **G9** | **Vendor posture + public surface** — boundary, §10 asks, intake discipline, **public-mirror drift**, CIP queue item | strategy | paper + one ruling | Joe |

### G1 — the twins (P1, silent-wrong; the last known lies)

- **G1a · U.5-H22 context fold.** `core/lop_knowledge.py:25-26` hardcodes the H21 catalog with no major-aware resolution — so `graph_validator.py:61/77` **silently validates H22 stages against H21 (and itself partially stale) Solaris CONTEXT truth**. WIRING went major-aware in U.1-H22; CONTEXT did not. Fix = give `lop_knowledge` the `_running_houdini_major()` / `_pkg_catalog_path()` pattern its sibling `wiring.py` already has, then **re-probe** Solaris context truth on 22.0.368 and commit `lop_solaris_knowledge_22.json` (roles, USD types, key parms, ordering, `known_absent`) — including the renamed instancers, dropping the stale per-shape light entries. The re-probe is hython-runnable; the live lift rides G2. *P3 rider (same domain, own commit or deferred):* extend `_SOLARIS_NODE_ORDER` to the new instancing family (`scatterinstances`, `mergepointinstancers`, `splitpointinstancers`, `extractinstances`, `modifypointinstances`, `retimeinstances`) at the ~300 tier. Evidence: postmortem LOP §4 + §5-P1.
- **G1b · mtlx phantom kill.** `render_recipes.py:701` still emits `mtlxstandard_volume` — **table-absent on 22.0.368**; the destruction recipe raises at `createNode` the moment it's instantiated. Fix = probe-verify a substitute (`mtlxvolume` / `mtlxvolumematerial`, both listed in the N-6 dump), swap the one call site, drop/repoint `MTLX_STANDARD_VOLUME` in `mtlx_types.py:25,33`. **Recommend a standalone small cycle rather than waiting for usd-2** (the assigned wave hasn't run and has no schedule); if usd-2 later re-touches the surface, its goldens capture the fixed truth — the correct order. Evidence: postmortem VOP §4 + §5-P1 · `h22-now-probes` §N-6.

### G2 — the live session (P1, the great unblocker)

One structured sitting inside graphical H22.0.368 with the bridge up, Joe at the GUI. Sequenced checklist (each item's artifact lands in `docs/reviews/` or `harness/notes/`):

1. **SCOUTMASTER debris ruling first** — `/obj/_recon_planes2` (+ `_w4assay_net`): active leg or debris? P-1 was SCENE_BUSY-blocked in all three expansion probe legs; nothing cooks until `/obj` is clean. (Start-line ruling #7.)
2. **P-1(a–e)** per the expansion's OWED list: SAM2/MoGe-2 instance-level `provider` menus · `usdmaterial` dynamic parms · live `inputLabels` for `fractalnoise`/`maskbyfeature`/`visualize`/`geotolayer::2.0`/`layertogeo::2.0` · `fractalnoise` `noisetype`/`fractaltype` menu tokens · minimal cooks (bgt::2.0 bake, bound RD pair; SAM2 empty-vs-real gated on models). Output: dated `harness/notes/` artifact + connectivity-catalog regen, hash-stamped, byte-coherent (the D10.1 mechanism).
3. **P-2** — stamp/scatter modern-target enumeration (regex over the 384 Cop types + parm capture). D4.3 does not build without it.
4. **Provisional lifts** — re-stamp on the live bridge: the 10 CHANGED COP scaffold verdicts · N-5/N-3 (layout/instancer create+cook, `light:filters` round-trip) · the 4 mtlx PASS + G1b's substitute (zero live mtlx coverage today) · the node-named-prim-path trap re-check (`/Render/<node>` vs `/Render/rendersettings`) with a guard-or-document decision.
5. **Panel G2** — boot the real `SynapsePanel` in the host (no `_Hou` stub): real widget geometry, GUI QFontDatabase, real pixels for the 13 sub-26px targets (then the sizing **taste call is Joe's** — start-line #8-adjacent, warden item 2). Re-point `audit_panel.py:6`'s stale "21.0.671" G2 reference and the N-16 stale hython help pointer in the same pass.
6. **SOP parm probe** — parm names/defaults/menu values for the core driven set (`attribwrangle`, `scatter`, `copytopoints`, `merge`, `object_merge`, `switch`, `group`, `blast`) + the VEX `run_over`→`class` (0–3) mapping smoke cook; attach `_handle_execute_vex` to the artifact instead of the H21 assumption. (Mirror `introspect_connectivity.py` into a parm-introspection artifact.)
7. *Optional rider if time allows:* **CTO-02 opalias enumeration** — grep `$HFS/houdini/OPcustomize`, cross-ref `emitted_node_types.json`, list every alias-propped emit; feeds the connectivity-note correction class. (Pool item; cheap here because the session is already open.)

Evidence: expansion §OWED · postmortem §5-P1/P2 · `h22-cto-roadmap` N-1 lineage.

### G3 — Copernicus builds (P1, ratified, spec-frozen)

Execute `docs/SYNAPSE_COPERNICUS_EXPANSION.md` **verbatim** — order **C.4 → C.3 → C.10, strictly serialized** (same-file collisions force it; C.4's fractalnoise helper is C.10's shared source). This blueprint adds nothing to that spec except: the four **OD rulings are start-line items** (below), C.3's Download Models run is a **Joe-side parallel task** (GUI, `$SHFS` under Program Files — likely elevation), and the cops-1/cops-2 **golden interplay rule** in the spec's §Sequencing is binding either way the order falls. Honesty contracts (`<key>_applied` envelopes, model-absent refusal, wire-by-label-only) are the spec's own DoD — not restated here.

### G4 — RETINA M1b → M2 → M3 (P1, the demo)

- **M1b first** — close the sibling-honesty tail on the shipped T0 cycle (`0039026`) before any new tier. (Postmortem §5-P1 item 1.)
- **M2 — worker + T1.** Own venv on `opencv-python-headless==5.0.0.93` (abi3, PyPI-re-verified; 4.13 API-stable fallback) · OIIO/OCIO ingest under the protected `OCIO` env (linear float32 for metrics, display-referred 8-bit proxies) · T1 metric kit · verdict events on the existing channel · **consume the committed perception truth catalog; any symbol not in it stays INFERENCE** (the blueprint's own §6 rule). Design facts already banked by the HDK/HAPI passes: multi-part-aware EXR header checks; per-AOV format read from the header, never assumed; bottom-left origin (twice-confirmed); sentinel on the husk-flag path per the shipped, crucible-corrected T0; `driver:parameters:` manifest-in-EXR as the free receipt upgrade. Gate: crucible hostile pass.
- **M3 — the Dark_Glass scoped-delta demo, end-to-end.** PROOF line lands in the receipt; consent gate carries a verdict; **Joe at the GUI**. Sequencing note from the reconciliation stands: M1's render-submit hooks already shipped **before** the render port wave — fix-before-freeze honored; the render wave's goldens will capture the hooked truth.
- M4 (T2 + COP QC oracle) is **paired with the shipped expansion** (shared `cops_create_node`/recipe surface, shared preflight-honesty rule) and M5 carries G6 — both sequenced in Mile 6, not this leg's critical path.

### G5 — port waves resume (P2, coupling-ruled)

Manifest order with scene-1 done: **scene-2 → usd-1 → usd-2 → render → tops-1 → tops-2 → cops-1 → cops-2 → memory-1 → memory-2.** Coupling rules (all inherited, restated once):

| Wave | Coupled fix / state |
|---|---|
| usd-1 | W.5 landed + live-verified — clear |
| usd-2 | G1b's mtlx fix lands **before** (standalone rec) or **with** it; materials surface live-lifted in G2 first |
| render | RETINA M1 hooks already shipped — goldens capture hooked truth |
| cops-1 / cops-2 | Land **after** C.4 (expected); if a cops wave somehow front-runs, the spec's PORT-FREEZE + golden-update-in-cycle rule governs |
| memory-1 / memory-2 | Unblocked by CTO-01 (fidelity 1.0) · the **memory analyst section is owed** (G8) — commission it before memory-wave goldens |

[RECORDED-INFERENCE — grounding pass confirms:] OD-1/2/3 manifest rulings were presumably discharged before scene-1 dispatched; SPEC step 0 verifies the manifest's ruling block and the merged-wave set (`scene-1/W.3/W.5/W.7+W.8/W.1b/W.4/U.1` per the postmortem's git-log line) before any wave dispatch.

### G6 — the number (P1-by-strategy, rides M5)

The original G6 (token-frugality, architecturally sound, numerically unproven) resolves through RETINA M5's **verdicts-per-token counters** — the ladder's purpose made measurable. Pool adjacency: TOPS-08 warm services (`pdg.ServiceManager`) attacks the ~2s cook floor and compounds the same number; stays unratified in the pool until M5's counters exist to measure it against.

### G7 — the class fix + corpus reseed (P2)

- **CTO-05** — generalize W.1b's `api_drift` instinct: load-bearing `try/except(AttributeError)` / None-guard degradations emit a **fidelity<1.0 IntegrityBlock note** ("symbol X absent on this build") instead of a clean-empty envelope. Fixes the *class* behind SB-1..SB-5 so the next major surfaces drift instead of hiding it. Own ratification; pairs with the C-1 acceptance note (numeric receipts need tolerance-based hython fixtures, never mock-`hou` CI equality). Evidence: `h22-sidefx-cto-lens` F7/F3.
- **W-6 corpus reseed** (one ratified cycle, probes already banked): ACES **2.0** config truth (`aces_color_management.md:25` is actively wrong) · husk full-frame-range + **"always `-o` + explicit frame flag"** trap-pin (the F5 compound: the no-op safety is gone; a naked call now multi-frame-renders into the working tree) · Pixel Filter Scale · the `planes()` recipe (`copernicus_python_api.md:315` still teaches the break) · CHOP doc re-namespace-or-retire · COP-02 seed rides C.3 per its spec. Code/corpus rule: both or neither.

### G8 — coverage rulings + honest debt (P2/P3 ledger)

- **Rulings (start line):** CHOP scope (rec: documented non-goal) · DOP/MPM sim frontier scope (rec: documented non-goal) · `hou._imagePlanes` private-API posture (still quarantined from emission) · OpenPBR default-surface posture (**hold — probe-gated, no ruling owed yet**).
- **Owed:** the Memory/substrate analyst `section_md` (truncated in dispatch — SCRIBE correctly refused to fabricate). Commission the re-dispatch; its P2 (probe the deprecated live-caller module vs the verified caller-less library path) precedes memory-wave goldens.
- **Debt cycles (small):** `menu.exec_()` guard at `chat_panel.py:499` (P2, copy the four guarded siblings) · `rewire_assess.py:40` `DEFAULT_VCC` derive-from-env (P3 — unblocks the NWS-11/12 vcc probes gating 18 new-VEX corpus seeds) · SOP `connect_nodes` catalog seam (P3) · exhaustive SOP census (P3, only if a real question demands it) · cyan 3-source reconciliation (P3, deliberate, full-suite-green + `test_hda_panel` lockstep, never naive) · shortened-QFont-enum touch-list pre-stage (P3).

### G9 — vendor posture + public surface (strategy paper + one ruling)

- **Boundary holds, twice-tested:** APEX pressure rejected from both the *real* keynote announcement and the *fabricated* memo — the refusal got more correct, not less. Rigging/KineFX/APEX stays structurally refused.
- **§10 asks, sharpened and ready:** ask #1 now has its exact form ("`HUSD_RenderTokens` has `color` and `cameraDepth` but no `id` — that's the missing token"); #2 carries the documented husk-hook inventory; #3 is the strongest (the HDK contains **no Copernicus surface at all**), and HAPI's semver'd Engine readback contract is SideFX's own precedent for the discipline being requested. No outreach action this leg unless Joe rules otherwise — the page stays ready.
- **Intake discipline reaffirmed:** external documents get **one adjudication page**, never a blueprint revision (§10 rule); **inline pastes without a tracked artifact path get adjudication-only treatment** — the fake-memo precedent is now the house example.
- **Public-mirror drift [VERIFIED-WEB, fetched 2026-07-17 — cause INFERENCE]:** the public `github.com/JosephOIbrahim/Synapse` page still serves the **v5.5.0-era README** (Sprint 3 Mile 4, "2874 passing", latest release Apr 20) — including the **pre-ruling "Moneta (Nuke)" portfolio line** the 2026-07-12 C3 ruling corrected, a `hou.secure` forward-compat note now REFUTED-LIVE, and — sharpest — **install step 3 teaching `setx ANTHROPIC_API_KEY`**, the exact pattern the `SYNAPSE_ANTHROPIC_KEY` guardrail exists to prevent (bun auto-loads `.env` into every child process; this was a confirmed billing-failure root cause). Whether local master's pushes lag, a mirror stopped syncing, or the public surface is deliberately frozen is **Joe's ruling** (start-line #9): refresh policy, or an explicit "public snapshot frozen at vX" note. Either answer is fine; silent drift that teaches the forbidden auth pattern is not.
- **IP queue item (public-safe reference only):** the scoped-delta **system-claim CIP review** stays queued under the existing filings **before any external mechanism-level discussion** (RETINA §5's own rule). No mechanism content belongs in repo-committed docs; this blueprint holds that line.

---

## §4 · Start line — the human ruling block

> Options stated, recommendations carried from the analysts' own text, **no ruling invented**. Nothing below is a mile; it's the gun. Items 1–7 unblock Miles 1–3 directly.

| # | Ruling | Options | Carried rec | Unblocks |
|---|---|---|---|---|
| 1 | **OD-A** — port-manifest absorbs the 3 new tools (115→118)? | (a) addendum to cops-2/cops-3 · (b) born-on-legacy-WS exception | **(a)** | C.3/C.10 merge |
| 2 | **OD-B** — native RD pair rides C.4? | (a) include (D4.5 pre-written) · (b) hold at scaffold | **(a)** | C.4 scope |
| 3 | **OD-C** — C.10 verb name | `cops_terrain_setup` (spec-provisional) · alternatives | keep provisional | C.10 build |
| 4 | **OD-D** — C.4 subsumes W.4b(3)? | yes (record in queue note) · no (two cycles, same lines) | **yes** | C.4 / D4.4 |
| 5 | **CHOP scope** | (A) documented non-goal · (B) lift + one intentional probe | **(A)** | G8 ledger honesty |
| 6 | **DOP/MPM scope** | (A) documented non-goal · (B) admit frontier + doc-scout pass | **(A)** | G8 ledger honesty |
| 7 | **SCOUTMASTER**: `/obj/_recon_planes2` (+`_w4assay_net`) — debris or active? | clear · preserve | — (probe-hygiene call) | **G2 entire session** |
| 8 | **Panel touch-target sizing** (after G2 real pixels) | padding · hit-area expansion · ratify the WARN | — (taste call, warden item 2) | N-14 close |
| 9 | **Public-surface policy** (G9 drift) | refresh cadence · deliberate freeze + note | — (either; not silent) | G9 |
| 10 | **`hou._imagePlanes`** private-API posture | adopt-with-pin · keep quarantined | — | COP read-surface completeness |
| 11 | **Commission** the owed Memory/substrate analyst section | — | do it before memory waves | G5/G8 |
| 12 | **RETINA M2 ratification** (miles enter the queue as gated cycles per the reconciliation) | flip · hold | flip after M1b closes | Mile 4 |

Standing gates unchanged: **per-cycle human merge · `ratified:false` resting state · suite-floor promotion is human-only.** OpenPBR posture is explicitly **not** owed a ruling yet (probe-gated).

---

## §5 · The six miles

> Relay framing: two hurdles, then the anchor stretch. Miles 1 and 2 are parallel-legal (different surfaces); everything else serializes as shown. Each mile's gate is named; each cycle's full DoD lives in its spec or in SPEC.md.

| Mile | Deliverable | Gate | Spec of record |
|---|---|---|---|
| **1 — the twins** | G1a U.5-H22 context fold (resolver + `_22` catalog re-probe) · G1b mtlx phantom kill | ratify ×2 · human merge ×2 | this doc §G1 → SPEC C-U5 / C-MTLX |
| **2 — the live session** | G2 checklist 1–7 discharged; artifacts committed; provisional stamps lifted; panel G2 run; SOP parm artifact | ruling #7 first · **Joe at GUI** · artifacts land | this doc §G2 → SPEC S-LIVE |
| **3 — Copernicus** | C.4 → C.3 → C.10, serialized; models download runs Joe-side in parallel | OD-A/B/C/D · per-cycle merge | `SYNAPSE_COPERNICUS_EXPANSION.md` (frozen) |
| **4 — RETINA M1b + M2** | M1b tail closed · worker venv + T1 + verdict events | M2 ratify · crucible hostile pass | `SYNAPSE_RETINA_BLUEPRINT.md` §9 + reconciliation |
| **5 — the demo** | RETINA M3: scoped-delta proof on Dark_Glass, PROOF line in the receipt | **Joe at GUI** · human merge | RETINA §5/§9 |
| **6 — waves + number + class** | Port waves per §G5 coupling · RETINA M4 (paired w/ expansion) · **M5 counters = G6's number** · CTO-05 · W-6 reseed | per-wave/per-cycle merges | manifest + RETINA + this doc §G5–G7 |

Dependency notes: Mile 2's P-1 gates C.4's cook verdicts, C.3's provider menus, and C.10's label capture — **run Mile 2 before or interleaved with Mile 3's first merge-ready claim**; C.4 unit-level FORGE work may start in parallel (its honest-deferred envelopes are designed for exactly this). Mile 4 consumes Mile 2's live catalog regen only incidentally; it does not block on Mile 3. Mile 6 is deliberately the long tail — the leg's Definition of Done (SPEC) is satisfied at **Mile 5 + the Mile-6 items that gate it having landed**, with the rest sequenced, not owed.

---

## §6 · Non-goals (locked; two pending ratification as *documented* non-goals)

- Rigging / KineFX / APEX — structural refusal, `check_no_rigging_drift`-enforced; twice re-affirmed this window.
- Shader authoring (VOP = graph plumbing only) · vector similarity for cognitive state (Non-Goal 6, one-Moneta ruling stands) · polling-based background audit · `hwebserver` core migration.
- No golden performs a real render (manifest hard rule) · port waves never change behavior · no agent presses `downloadmodels` · no disk export from bake/terrain v1 (APPROVE surface untouched).
- **Pending start-line rulings 5–6:** CHOP and DOP/MPM as *documented* non-goals (recommended) — so byproduct catalog rows stop reading as partial coverage.
- Nuke-host build (the un-named SYNAPSE sibling — one-Moneta ruling): out of leg scope; naming is a future brand call, horizon only.

---

## §7 · Risk register

| Risk | Mitigation |
|---|---|
| A cops wave front-runs C.4 → goldens pin scaffold semantics | Expansion §Sequencing PORT-FREEZE rule: wave carries no C-diff; the later C-cycle updates goldens in its own commit |
| P-1 stays blocked (debris ruling drifts) | Start-line #7 is Mile 2's literal first step; escalation to Joe is immediate, not queued |
| SAM2/MoGe-2 models never downloaded → C.3 cook path unarmed | By design: v1's testable path is the model-absent honest refusal; models-present test arms automatically (`skipif`) |
| GPU/denoiser nondeterminism poisons M2 baselines | `qc_profiles.toml`, thresholds-never-equality, Commandment 7 extended to thresholds (RETINA §7 — unchanged) |
| Backend-precision drift under numeric receipts (ACES 2.0 / linear mips / MtlX 1.39.5) | F3/CTO-05 acceptance note: tolerance-based hython fixtures, never mock-`hou` equality goldens |
| Silent cross-major context truth (the G1a class) recurs elsewhere | CTO-05 turns the *class* into fidelity-noted receipts; U.5 closes the known instance |
| Alias-propped emits expire in a future major | CTO-02 enumeration (pool → G2 rider) makes the exposed set enumerable instead of discoverable-by-breakage |
| Public mirror keeps teaching the forbidden auth pattern | Start-line #9 — either refresh or freeze-with-note; never silent |
| This blueprint itself drifts from the live tree | SPEC step-0 grounding pass is mandatory before any dispatch; runtime > repo > this paper |

---

## §8 · Candidate pool (unratified — recorded so nothing is lost)

`ratified:false`, resting state correct: **C.1** ImageLayer pixel stats (sequences after the C-cycles; same-file) · **CTO-02** opalias enumeration (G2 rider candidate) · **CTO-04** cop2net-sunset dependency register (six tools incl. `create_network`/`composite_aovs`; trajectory-driven, not urgent — contingency has not fired) · **CTO-05** (G7, promote when ready) · **W.4b(1)(2)** solver follow-ups · **U.1b** resolver same-major-granularity hardening · **SB-6/KAR-01** detection wiring beyond the corpus pin · **C-2/SOL-04** reversible pxr-authoring (probe-verified, ratification-ready) · **C-5/TOPS-02+05** per-work-item perception telemetry · **C-6/TOPS-08** warm services (pairs with G6's number) · **C-7/SOL-02** Prune-LOP · **C-8/KAR-05** husk resume · **C-9/KAR-04** RenderPass prims (bundle the `--pass` CLI probe into the next husk session) · **HOM-01** `hou.CopVerb` headless COP cooking · **HOM-03** `hou.data` recipe substrate · **SOL-14** Component Builder wrapper · **NWS-11/12** VEX probes (post-`DEFAULT_VCC` fix) · KAR-14 detection wiring.

---

## §9 · Truth-label appendix

| Claim class | Tier | Note |
|---|---|---|
| Repo state (HEAD, tag, queue flags, merged waves, suite floor) | RECORDED — postmortem/expansion self-verified | **Grounding pass re-verifies** |
| Live-runtime verdicts cited (planes surface, relationships, fidelity 1.0, quarantine, solver binding) | VERIFIED-LIVE per `h22-live-reconfirm-2026-07-16.md` | |
| Headless probe data (N-3/N-5/N-6/N-8/N-9/N-10, COP audit, connectivity) | VERIFIED-ARTIFACT · PROVISIONAL-headless where so stamped | G2 lifts |
| Public-mirror drift | VERIFIED-WEB (observed mismatch, fetched 2026-07-17) · INFERENCE (cause) | Ruling #9 |
| OD-1/2/3 discharged pre-scene-1 | RECORDED-INFERENCE | Grounding pass confirms |
| Everything in §G3/§G4 build content | Governed by the frozen specs — not restated | One source of truth |

---

*ARCHITECT writes the design and never the code. FORGE implements against the contract. CRUCIBLE attacks what it didn't build. ASSAYER verifies on the running build. The human merges — every time. This document is paper: it mutates nothing, and where it disagrees with the live 22.0.368 runtime or the repo at HEAD, the runtime and the repo win.*
