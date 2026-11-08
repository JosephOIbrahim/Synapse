# Neural Growth — C0 Report — 2026-11-07

**Status:** C0 only. Read-only reconciliation plus a PROPOSED graph amendment. **Not ratified. Authorizes no act.** On 2026-11-08 Joe merged the amendment's OpenCV lane into `graph.json` (ADR-0002, "Ratification and owner rulings (2026-11-08)", answer 2); the Grow lane is not in `graph.json`.

| Field | Value |
|---|---|
| **Input reconciled** | "SYNAPSE Neural Growth Creative Loop Blueprint", 7 November 2026, sha256 `070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647`. Cited by section; not reproduced |
| **Companion input** | "SYNAPSE: OpenCV 5.1 GPU Integration Blueprint", 7 November 2026, sha256 `bbaeed26669b945c2811399b9bbae0a1a183dbd18b6bb57d121f7391d271bf43`. Reconciled at G0; folded into the graph by R1 |
| **Companion records** | `docs/decisions/ADR-0002-retina-t1-optional-cuda-backend.md` (PROPOSED) and `docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md` (the G0 receipt), both at `1400a43e` |
| **Graph amendment** | `harness/next-release/proposals/` (same commit as this report) |
| **Branch and base** | `vision/opencv51-g0` at `1400a43e4369c4de2953fc2e04aff82368808219` before this commit |
| **Owner** | Joe Ibrahim: G0 owner, product and ratification authority (orchestrator record). **He has not ruled on this blueprint** |
| **Author** | Claude, integration author for this session. Independent reviewers: this workflow's attack agents |

**G0 observed no GPU execution and measured no performance. Neither did this C0.** Every speed, VRAM, duration or latency figure is UNKNOWN.

### Evidence key

- **VERIFIED** — a repo `path:line`, a git object, a command and its output, or a cited report line that is itself VERIFIED.
- **DOCUMENTED** — SideFX's installed help or a blueprint says so. Not executed.
- **INFERENCE** — reasoned, not observed. Never promoted.
- **UNKNOWN** — nobody has measured it.
- **REFUTED** — the code or probe contradicts it.

### Evidence sources

The reports are local working papers, not committed. They are cited by file name and line, for example `[w3/01-nca-native.md:32]`. "Orchestrator record" means facts the workflow orchestrator established outside the reports.

| Report | Lens | sha256 |
|---|---|---|
| `w1/01-trace.md` … `w1/06-critic.md` | The six G0 reports | as listed in the G0 receipt, "Evidence sources" |
| `w3/01-nca-native.md` | Native H22 NCA capability | `f058f0ca911f6a5164b60c21780cfff99e41b7ebdb074e593b8b28a2d5188c2f` |
| `w3/02-grow-surface.md` | Where a Grow job would live | `dd6e36c99f6f392f5a6ffd4cfd06e8dd0f0479f07b0575caf7dd8d6f16c903d2` |
| `w3/03-graph-map.md` | Both blueprints on the ruled graph | `61fbaabc4aaafde41e72cecf5b2b6bb58e248e6cc5d38b5f10a40b444857d18d` |
| `w3/probe/out_22.0.400.txt` (P400) | Fenced parameter probe, 22.0.400 | `4c74e675e5ace033ff466866aa77515c0cccb3b83fe3cfae8604ee195aa7ef52` |
| `w3/probe/out_22.0.466.txt` (P466) | Same probe, 22.0.466 | `8cbce4824ee004407f14c7f662f5ec6d784b4c696dc06f3a24c27d9be91d06b2` |
| `w3/probe/nca_probe.py` | Probe script | `f6647bd40caf2d19d2b932b153968450ce09d05f6f0044455d57c653f77b878c` |

---

## 0 · Verdict

1. **Native NCA exists on the installed builds; SYNAPSE exposes none of it.** Core, Decode and the training TOP are present on 22.0.400 and 22.0.466 (VERIFIED, §4). No handler, registry tool, recipe or panel action references NCA (VERIFIED, `[w3/02-grow-surface.md:36]`).
2. **Nothing about NCA execution is known.** No node was created or cooked, no model loaded, no provider exercised (§4).
3. **There is no in-process sandbox.** Every SYNAPSE mechanism that builds COP or LOP nodes does so in the artist's open scene (VERIFIED, `[w3/02-grow-surface.md:55]`). The blueprint's isolated sandbox needs a separate session.
4. **The Grow lane is outside the owner's ruling.** R1 folds the OpenCV blueprint into the graph; it says nothing about this blueprint (VERIFIED, `[w3/03-graph-map.md:64]`; G0 receipt header "Not reconciled here"). The C-nodes are proposals that need OD-01.
5. **The amendment validates:** 57 of 57 checks pass; all ten new predicates and the draft qualification predicate are red for their declared reason, also when copied to another folder depth (§13).

---

## 1 · Current revision and dirty state

| Fact | Label | Evidence |
|---|---|---|
| This branch was at `1400a43e` (G0 revision) on `b4b6cb8a` (G0 draft) on `ef43d37a` | VERIFIED | `git log --oneline -3` at authoring |
| Before this commit, `git status --porcelain` listed only the new files of this change | VERIFIED | command at authoring (§13) |
| `origin/master` is `e3846b22`; `v5.98.0` is `6a5f68dd`, published | VERIFIED (orchestrator record) | G0 receipt §1 |
| `retina/` is byte-identical between `v5.98.0` and `ef43d37a` | VERIFIED | G0 receipt §1 |
| The live checkout is on `feat/worldlabs-audit` at `36148779` with uncommitted work; untouched by G0 and by C0 | VERIFIED (orchestrator record) | G0 receipt §1 |
| `harness/next-release/graph.json` sha256 `3e848b1f…7315` | VERIFIED | `sha256sum` at authoring; `[w3/03-graph-map.md:11]` |

---

## 2 · Active ownership

The G0 receipt §2 and §5 carry the branch and file-owner tables. They are not repeated. What C0 adds:

| Fact | Label | Evidence |
|---|---|---|
| Four NR nodes are merged: `NR-SPARSE-RENDER`, `NR-PLAN-TRUTH`, `NR-WRITE-RECEIPT`, `NR-GPU-FEASIBILITY` | VERIFIED | `[w3/03-graph-map.md:28]` (`git log --merges`) |
| The committed JEV decision ranks an older graph (`af547698`), not today's `3e848b1f` | VERIFIED | `[w3/03-graph-map.md:27]` |
| In graph mode the guard applies JEV's judgments only; it runs no ownership, dependency or cycle check and never reads `gate` | VERIFIED | `harness/harness2/compositor.py:423-493`; `files_disjoint` at `:279-284` is called in compose mode only and compares exact strings; `[w3/03-graph-map.md:26]` |
| `NR-FOLLOW-ON` owns all of `harness/next-release/` (K4) | VERIFIED | `graph.json` owner_files; `[w3/03-graph-map.md:66]` |
| The RETINA venv recipe files are in no node's `owner_files` | VERIFIED | G0 receipt §5 |
| No node owns NCA, a Grow panel, a Grow handler or a control package | VERIFIED | `[w3/02-grow-surface.md:36]`; `graph.json` |

**Consequence.** Joe's merge review is the only mechanical guard on ownership and dependencies for anything proposed here. INFERENCE `[w3/03-graph-map.md:26]`.

---

## 3 · RETINA invocation and event contracts

**Cited, not repeated:** G0 receipt §3 (the invocation path as it runs today) and §4 (contracts).

The facts that bind the Grow lane:

- T1 has no production caller, nothing launches a worker, and no production code writes a verdict sidecar (VERIFIED, ADR-0002 Context §2 items 1-3).
- The envelope is `{ch, v, tier, claim, checks, verdict, proof, at}`; checks are tri-state; the roll-up is fail > inconclusive > pass (VERIFIED, G0 receipt §4).
- T0 runs inside Houdini through the panel (VERIFIED, ADR-0002 Context §2 item 4).
- The zero-cv2 host lint is lexical, not transitive; no test pins zero `hou` in the worker (VERIFIED, ADR-0002 Context §2 items 5-6).

**For Grow this means:** a creative sidecar, a control package and a candidate manifest all have nothing to attach to yet. The worker (`NR-WORKER-SUPERVISED`) and durable publication (`NR-RECOVERY-RECEIPTS`) come first. INFERENCE.

---

## 4 · Houdini builds, native NCA and providers

Probe fence: headless hython with a scrubbed environment, flags `-s -P`, a scratch preference folder outside the repo, a 120 s kill of its own PID only; it read parameter templates and created no node `[w3/01-nca-native.md:27-36]`. Both runs exited 0 (22.0.400 in 7 s, 22.0.466 in 28 s) `[w3/01-nca-native.md:32]`. **This C0 stage launched nothing.**

**Authority for those two launches.** The probe ran in this workflow's w3 stage. The workflow's general limits, set by the orchestrator rather than relayed from Joe, forbid any Houdini, hython or husk launch. The orchestrator's brief to the w3 nca-native scout made one exception: a fenced, read-only, headless hython run for each of two builds, 22.0.400 and 22.0.466 (orchestrator record; the brief is not committed). So the two launches were within that scout's brief, but **no owner authorization was on record when they ran.** On 2026-11-08 Joe acknowledged both and kept their evidence (§14 item 14). They created no node, loaded no scene, touched no GPU and used a scratch preference folder `[w3/01-nca-native.md:27-36]`. Every parameter fact in §4 and §7.1 marked P400 or P466 rests on them.

### 4.1 Builds

| Fact | Observed | Documented | Unverified |
|---|---|---|---|
| Installed: 21.0.773; 22.0.368, .397, .400, .417, .429, .466, .492 | VERIFIED (orchestrator record) | | |
| SYNAPSE targets 22.0.400 | | CLAUDE.md; D1 | |
| The prep's resource snapshots saw 22.0.466 in use | VERIFIED (prep record, G0 receipt §6) | | |
| Which build Joe runs today | | | UNKNOWN (G0 receipt §10 item 14) |
| The probe ran on 22.0.400 and 22.0.466 | VERIFIED (P400:1; P466:1) | | |

### 4.2 Native NCA node types

| Node type | 22.0.400 | 22.0.466 | Source |
|---|---|---|---|
| Cop `neural_cellularautomatacore` | VERIFIED | VERIFIED | P400:7; P466:7; `rag/catalog/h22.0.400/Cop.json:52945` |
| Cop `neural_cellularautomatadecode` | VERIFIED | VERIFIED | P400:7; `Cop.json:53212` |
| Top `ml_trainneuralcellularautomata` | VERIFIED | VERIFIED | P400:19; `rag/catalog/h22.0.400/Top.json:48685` |
| Recipes `…::neural_cellularautomata`, `…_block`, `…::ml_trainneuralcellularautomata`, preset `…::model_denim` | VERIFIED | VERIFIED | P400:10 |

The two probes are byte-identical after the version line except one label on the training TOP `[w3/01-nca-native.md:58]`. The 22.0.466 parity rests on one probe; there is no 22.0.466 catalogue. All help citations are from the 22.0.400 install `[w3/01-nca-native.md:58-63]`.

### 4.3 Execution providers

| Item | Observed | Documented | Unverified |
|---|---|---|---|
| Core `provider` default 0; Decode `provider` default −1 | VERIFIED (P400:125, :142) | | Which provider each default means: UNKNOWN |
| Provider menu tokens | Script-generated; not listable without creating a node | | UNKNOWN `[w3/01-nca-native.md:127]` |
| Provider list: Automatic, CPU, CUDA (needs CUDA and cuDNN), DirectML (Windows), CoreML (macOS) | | DOCUMENTED, installed help `[w3/01-nca-native.md:128]` | |
| Training device menu `cpu` / `cuda` / `mps`; **no DirectML** | VERIFIED (P400:332) | | |
| Whether CUDA loads inside Houdini's ONNX Runtime on this machine; what Automatic picks | | | UNKNOWN `[w3/01-nca-native.md:166-176]` |
| Any cook, wall time or VRAM | | | UNKNOWN |

### 4.4 Blueprint NCA claims, adjudicated

`[w3/01-nca-native.md:135-152]`. None REFUTED. One qualifier.

| Claim | Verdict |
|---|---|
| Rotation is in turns | DOCUMENTED. The parm's ±360 range is a soft slider range, not a unit (P400:117) |
| Scale is clamped to 0.2–1 internally | DOCUMENTED. The parm range is non-strict, so the UI does not enforce it (P400:118) |
| `ncaiteration` metadata matters | DOCUMENTED. It is a layer property, not a parm |
| Update mask: amplitude vs probability | VERIFIED: `updatemasktype` 0 Amplitude-Weighted, 1 Probabilistic (P400:115) |
| Decoder selection can follow `decodemodel` metadata | DOCUMENTED; `modelsource` defaults to From Metadata (P400:129) |
| Decode's raw output is Linear Rec709 | **Qualified.** DOCUMENTED for Raw, but the node defaults to OCIO with output `scene_linear` (P400:137-138) |
| Core and Decode models are paired | VERIFIED as shipped: both defaults sit in one `denim/v1` folder (P400:108, :130). Whether a mismatched pair is rejected: UNKNOWN |
| A training TOP with partial training exists | VERIFIED (exists, parms); never run |
| Decode outputs RGB, not PBR | DOCUMENTED |

---

## 5 · Relevant truth catalogs

| Catalog | State | Evidence |
|---|---|---|
| `rag/catalog/h22.0.400/` (node-type authority) | Present; lists all three NCA node types and their parms | §4.2 |
| `python/synapse/cognitive/tools/data/h22_symbol_table.json` (`hou.*` existence authority) | Present. Not needed here: NCA is node types and parms, not `hou` symbols | file listing |
| `harness/notes/perception_truth_22.0.368.json` (perception catalog) | **Only build 22.0.368, PROVISIONAL.** No 22.0.400 catalog exists. One item still reads VERIFIED-LIVE for a route R100 refuted; it was never amended | `[w1/03-governance.md:75-88]` |
| A 22.0.466 node catalogue | **Absent** | `[w3/01-nca-native.md:58]` |

---

## 6 · Smallest safe sandbox experiment (C1) — PROPOSAL

From `[w3/02-grow-surface.md:70-80]`. **Needs Joe's per-act authorization. Nothing here was run.**

1. **Joe opens a fresh, untitled Houdini session himself** — a second instance, never the live seat's scene, with a scratch preference folder. No SYNAPSE tool in the loop.
2. He builds the SideFX `neural_cellularautomata` recipe by hand: Core → Decode, the shipped `denim` pair, fixed `seed`, fixed `modeliterations`. No training, no production asset, no reference image.
3. Outputs go to a fresh job folder outside the repo, the live checkout and `E:/OpenCV5.1_Prep`. The scene is never saved, or saved only there.
4. He records: build string, node types, model file hashes, seed, iterations, provider as displayed, the Decode colour settings, and two decodes of one seed. Then restarts the session and replays once.
5. **Only after step 4 replays:** read-only SYNAPSE observation, if the second session can stay off the live seat's bridge (UNKNOWN). No mutation, no worker, no render.

**It would prove** that the shipped pair cooks on this build in a disposable session, and whether a fixed seed replays. **It cannot prove** custom training, GPU use, VRAM, timing, the Grow panel or any automation.

Its receipt is what `NR-VG-NCA-SANDBOX`'s predicate reads.

---

## 7 · The Grow experience around ONE bounded job

**The job.** One sandbox session; the shipped `denim` pair (no training); one Region mask; four candidates from four fixed seeds at a fixed iteration count; proxy decode; one refinement round; then Keep or Discard. The four-and-one budget is the blueprint's own example (§5), a proposed UI limit, not a measured throughput. Nothing writes to a production scene.

### 7.1 Artist controls → native semantics

**Observed** = the parameter exists (probe). **Documented** = SideFX help says what it does. **Unverified** = nobody has cooked it.

The probe observed parameter templates and the Core input count (6, `rag/catalog/h22.0.400/Cop.json:52950`). The Core **input names** used below (`updatemask`, `rotation`, `scale`) are DOCUMENTED (installed help), not observed.

| Panel control | Native parameter or input | Observed | Documented | Unverified |
|---|---|---|---|---|
| **Reference** | For a *new* pattern family: training TOP `targetimage` | Parm exists (P400:238) | Training learns from a target texture | Training never run. **For this first job the reference drives nothing native**; the shipped model is fixed. Mapping: UNKNOWN |
| **Direction** | None | — | — | No native parameter. An orchestration recipe only: UNKNOWN |
| **Region** | Core `updatemask` input (name DOCUMENTED) + `updatemasktype` | `updatemasktype` 0/1 (P400:115); 6 inputs on Core (catalogue) | Amplitude-weighted vs probabilistic | Whether freezing updates protects final pixels: UNKNOWN (blueprint §4 says do not assume it) |
| **Scale** | Core `scale` (2 floats, default 1,1) and `scale` input (name DOCUMENTED); `sizerefscale` for growth resolution | P400:118, :123 | Final scale clamped to 0.2–1 | Direction of effect: UNKNOWN |
| **Flow** | Core `rotation` and `rotation` input (name DOCUMENTED); `adjacencydir` | P400:117, :121 | Rotation in turns | Units of the per-cell rotation input: UNKNOWN `[w3/01-nca-native.md:139]` |
| **Variation** | Core `seed` (float, soft 0–10); `modeliterations` (1–250) | P400:111-112 | `ncaiteration` feeds the seed per iteration | Fixed-seed replay: UNKNOWN |
| **Grow** | A cook of the Core → Decode network | Node types exist | | Cook behaviour, time, VRAM: UNKNOWN |
| **Stop** | None | — | — | No native stop; interrupting a cook or ending the sandbox process. SYNAPSE has no cancel for it: UNKNOWN |
| **Proxy / full** | Decode `factor` (default 8x); Core `sizerefscale` (default 1/8) | P400:123, :133 | Help recommends a 1x proxy decoder plus a full-res decoder | UNKNOWN |
| **Colour** | Decode `colortransform` (default OCIO), `tospace` (default `scene_linear`) | P400:137-138 | Raw = Linear Rec709 | Must be pinned in every test, never assumed |
| **Model** | Core `modelfile`; Decode `modelsource` (From Metadata) and `modelfile` | P400:108, :129-130 | Decoder follows `decodemodel` metadata | Mismatched-pair behaviour: UNKNOWN |
| **Provider** | Core and Decode `provider`, `deviceid` | P400:125-126, :142-143 | Provider list in help | Tokens and actual provider: UNKNOWN |
| **Keep / Refine / Discard** | None | — | — | Orchestration and promotion (C5). No native meaning |

### 7.2 What already exists in SYNAPSE, and why Grow cannot reuse it

- Four COP growth/pattern tools exist. **None is NCA or a learned model.** All create nodes inside the open scene at a caller-given parent (VERIFIED, `[w3/02-grow-surface.md:13-28]`).
- The autonomous panel worker may call all four with **no prompt**: they map to `create_node`, gate `inform` (VERIFIED, `[w3/02-grow-surface.md:42]`).
- The worker is **denied** a preview render by policy (`houdini_render` → `submit_render` → `approve`) (VERIFIED, `[w3/02-grow-surface.md:64]`).
- Adding a registry tool moves two tool-count pins (VERIFIED, `[w3/02-grow-surface.md:48]`), and the registry file is owned by two merged nodes (K3).

**So** a Grow job needs its own separate-process sandbox and its own publication contract. INFERENCE, owned by `NR-VG-GROW-JOB`.

### 7.3 Preserved

ONNX inference contracts unchanged; Houdini keeps native NCA inference; no `cv2` in Houdini and no `hou` in RETINA; OIIO/OCIO ingest unchanged; the envelope, tri-state checks and sidecar persistence unchanged; creative ranking in a separate sidecar. These are the blueprint's own rules (§3, §7) and the ADR-0002 invariants.

---

## 8 · The amendment for reference-driven control generation

**What exists.** RETINA is perception. Its governing allocation sends GPU-heavy pixel work to Copernicus and keeps OpenCV as the independent oracle (VERIFIED, `docs/SYNAPSE_RETINA_BLUEPRINT.md:46`, quoted in ADR-0002 Context §1).

**What ADR-0002 proposes.** An optional CUDA backend for named T1 *measurements*, worker-only, behind the tri-state contract, with no mutation authority. It is "measurement on arrays the worker has already ingested", not semantic vision, inference or capture (ADR-0002 Context §1, Decision).

**What Grow needs that ADR-0002 does not grant.** RETINA would emit **control fields that steer synthesis** — orientation, scale, region masks — as a new artifact type. That is a new allocation: measurement output becomes a creative input. INFERENCE.

**Proposed shape (not written, not ratified):**

1. A **separate** amendment record, not a widening of ADR-0002. ADR-0002 stays scoped to the CUDA backend.
2. A control package is a **new artifact**, not an envelope field. The envelope and roll-up are unchanged.
3. It runs in the worker, on the **CPU reference by default**. A GPU path uses only operations `NR-GPU-QUALIFICATION` qualified (ADR-0002 mode rules).
4. Low-confidence evidence becomes a neutral field, never a wild one; an artist-painted field always wins (blueprint §4).

**Relation to the CPU-T1/GPU boundary.** Unchanged: T1 stays CPU reference by default; CUDA is opt-in per named operation in the worker only (ADR-0002 "Backend modes"). The C2 node can start CPU-only; the edge from `NR-GPU-QUALIFICATION` is `evidence`, not `dep`, for that reason (OD-19).

`NR-VG-GROW-CONTROLS`'s predicate requires that amendment's Status line to read ACCEPTED.

---

## 9 · Acceptance fixtures

The blueprint's minimum test suite (§10), mapped to the node that owns each:

| Fixture family | Node |
|---|---|
| Absent model, wrong decoder, unavailable provider, matched model hashes | `NR-VG-NCA-SANDBOX` |
| Fixed-seed replay within a frozen tolerance; replay after restart; extended rollout; stop and restart | `NR-VG-NCA-SANDBOX` |
| Asymmetric orientation fixture, rotation in turns, scale clipping, invalid ranges, update-mask semantics, coordinate contract (origin, UV domain, tile, wrap, channel order, range, resampling), malformed input | `NR-VG-GROW-CONTROLS` |
| Missing control map, corrupt product, stale completion marker, path escape, oversized allocation, duplicate job, cancellation race, no result from partial work | `NR-VG-GROW-JOB` |
| Admission refusal, OOM recovery, responsive cancellation, one GPU-heavy job at a time | `NR-VG-GROW-JOB` |
| Protected-region integrity; empty mandatory-check list refused; style never overrides a failed check | `NR-VG-GROW-COMPARE` |
| Unguided vs guided NCA vs the prior manual workflow, judged by Joe | `NR-VG-GROW-COMPARE` |
| Exact-target diff, explicit approval, recovery rehearsal | `NR-VG-GROW-PROMOTION` |
| No host `cv2`, no worker `hou`, no training dependencies in the host | `NR-VG-RETINA-GUARDS` |

**Profiles freeze before evaluation.** The NCA tolerance lives in a committed profile that the receipt pins by hash; a receipt never carries its own threshold `[w3/03-graph-map.md:181]`.

---

## 10 · Recovery plan

- **This commit:** revert it. No runtime, test or governing surface depends on it.
- **C1 sandbox:** a separate session, never saved to production; outputs only in a fresh job folder. Recovery is closing the session and deleting that folder. The live seat is never touched. INFERENCE (proposed procedure).
- **Grow jobs (C3):** Stop cancels owned work, keeps the last complete candidate and marks incomplete products unusable; Discard deletes no source, asset or prior accepted work (blueprint §1).
- **Promotion (C5):** undo grouping is not rollback (CLAUDE.md §1). Every promotion carries the original state and a rehearsed recovery before approval.
- **Never:** kill Houdini or a renderer to recover a creative job (blueprint §9).

---

## 11 · Resource requirements

| Resource | Known | Unknown |
|---|---|---|
| GPU | RTX 4090, 24,564 MiB, driver 621.14 (prep record; G0 receipt §6) | Every NCA VRAM figure; contention with Karma XPU or an OpenCV worker |
| Policy | One GPU-heavy job at a time, inside an approved window; production and demo first (blueprint §9) | The window itself (OD-12, OD-18) |
| Training | The TOP has a `venvpath` parameter (P400:327). That it builds a Python venv with pip, which would make training an install-class act, is DOCUMENTED and INFERENCE, not observed `[w3/01-nca-native.md:146]` | Venv contents, network need, time for 3,000 steps |
| Disk | Fresh job folders outside the repo | Sizes |
| People | Joe for every per-act gate | A build/package owner and an independent reviewer (OD-15) |

**No number in this section is a measurement.**

---

## 12 · Revised estimate basis — no calendar promise

- The blueprint itself says a 6–8 week commitment is **not evidence-backed** (§10). G0 adopted none of the OpenCV blueprint's figures (G0 receipt §12).
- **The basis is a timed C1 spike.** After it, a bottom-up forecast for C2–C5 needs: C1's measured cook and replay times, approval latency, compute windows, named owners and contingency.
- **The critical path runs through RETINA, not NCA.** C3–C5 depend on `NR-RECOVERY-RECEIPTS` and, through it, on `NR-WORKER-SUPERVISED`, both unbuilt and parked. INFERENCE from the graph.
- C1 alone has no graph predecessor (blueprint §10: it may proceed independently in an approved sandbox).

---

## 13 · Graph amendment summary

**Location:** `harness/next-release/proposals/` — `vision-grow.amendment.PROPOSED.json`, `predicates/test_nr_vg_*.py` (10), `validate_amendment.py`, `README.md`.

**Shape.**

- **10 new nodes**, all `gate: joe`, plus one **draft predicate** for the changed `NR-GPU-QUALIFICATION`, carried in full inside its change entry (`proposed_file`) and written to the repo only by the merge that adopts it. OpenCV lane: `NR-VG-GPU-BUILD-LOCK` (G1 build), `NR-VG-RETINA-GUARDS`, `NR-VG-GPU-WORKER-ENV`, `NR-VG-RETINA-CUDA-BACKEND` (G2), `NR-VG-GPU-CANARY` (G4). Grow lane: `NR-VG-NCA-SANDBOX` (C1), `NR-VG-GROW-CONTROLS` (C2), `NR-VG-GROW-JOB` (C3), `NR-VG-GROW-COMPARE` (C4), `NR-VG-GROW-PROMOTION` (C5).
- **33 new edges**, types `dep`, `evidence`, `seam`, `invariant` only. `NR-VG-NCA-SANDBOX → NR-VG-GROW-CONTROLS` is a `dep`, because the controls predicate pins the sandbox receipt.
- **Existing nodes keep their work:** G1 qualification and G3 → `NR-GPU-QUALIFICATION`; the `t1.py` seam → `NR-IMAGE-CONTRACT`; G5 and C6 → `NR-PACKAGE-PAIR` + `NR-LICENSE-GATE`; G6 → `NR-FOLLOW-ON`.
- **4 proposed changes to existing nodes**, each tied to the ruling: `NR-GPU-QUALIFICATION` `why`, `predicate` (R2, R3) and `depends_on` (R3); `NR-WORKER-SUPERVISED` `why` (R4). Their texts state only what R1-R4 rules. The change-mask fixtures and the identical-mask-bytes criterion are labelled G0-proposed (G0 receipt slice 2; 02-ops §7), the NaN fixture INFERENCE, and the choices the ruling left open are owner decisions: replace or add beside the census (OD-22, ADR-0002 decision 14), the `cpu_reference` identity (OD-10), the test's location (OD-04) and the node's gate, crux or joe (OD-23).
- **New owner files live under `harness/vision/`**, because `NR-FOLLOW-ON` owns all of `harness/next-release/` (OD-03).
- **No new node takes a file another node owns.** The registry and panel files Grow needs stay with their owners (OD-06).

**The ruling's consequences, stated:**

- **Module list (R2, R3).** `E:/OpenCV5.1_Prep/02_OpenCV_Setup/preparation/Current_Configure.json:26` sets `BUILD_LIST=core,flann,geometry,imgproc,imgcodecs,cudev,cudaarithm,cudaimgproc,cudafilters,cudawarping,python3`. It **contains both `cudaarithm` and `cudafilters`**, so the requested list covers the change-mask chain. VERIFIED by read (file sha256 `102bf6f8…56f6`). Whether configure **generates** them is UNKNOWN; the build-lock predicate requires the generated list.
- **`NR-GPU-QUALIFICATION`** named the 11x11 census in its `why` (`graph.json:95` at C0) and its predicate was `test -f` (`graph.json:96` at C0). The masked `meanStdDev` closure and the `C:/ocv` root are in `NR-GPU-FEASIBILITY`'s receipt (`harness/next-release/gpu_feasibility.json:430`, `:259`). Changes 1-3 rewrite the qualification node; Joe merged them on 2026-11-08, with OD-23's gate change to `joe`.
- **The RETINA venv recipe** (`retina/setup_venv.py`, `retina/setup_venv.ps1`, `retina/requirements.txt`) documents a hython seed and names a cp314 OIIO wheel. It conflicts with R4. `NR-VG-GPU-WORKER-ENV` would own and change it. Its predicate is red today only because the worker-runtime contract is not committed; it enforces the R4 recipe conflict later, through the contract's reviewed sha256 pins of the three recipe files (`harness/next-release/proposals/predicates/test_nr_vg_gpu_worker_env.py:91-101`). Its one mechanical check, no `cp314` pin on a non-comment requirement line (`:102-105`), skips comments, so it matches nothing in today's `retina/requirements.txt`, where `cp314` appears only in a comment (`:39`). VERIFIED by read.
- **The custom `cv2` binding** is configured to be built for CPython 3.12.10 without the limited API; no binding exists yet, and that it is cp312-only is INFERENCE from CMake semantics (ADR-0002 section "Consequences of R1-R4", item 4). The build-lock predicate requires `abi_tag cp312` and `limited_api false`.
- **The `NR-GPU-FEASIBILITY` artifact is not the qualification artifact.** It compiled one trivial non-OpenCV kernel, `vectorAdd`, in a scratch folder and ran it on the RTX 4090 (exit 0, 0 mismatches; `harness/next-release/gpu_feasibility.json:25`, `:39`). That earlier node's GPU run is recorded in its receipt; G0 and C0 observed no GPU execution. Nothing was compiled under `C:/ocv` (ADR-0002 section "Consequences of R1-R4", item 5). The qualification artifact must come from the E: build.

**Validator — exact command and result.** Merge-aware run of 2026-11-08, after Joe merged the OpenCV lane into `graph.json`, from the worktree root with a local CPython 3.14.2:

```text
python harness/next-release/proposals/validate_amendment.py
SUMMARY: 76 checks, 76 passed, 0 failed - merge-aware: merged OpenCV lane matches the amendment and its rulings; every unmerged predicate red for its declared reason
```

Exit 0. Interpreter CPython 3.14.2, pytest 8.4.2. The first scaffold commit recorded 41 of 41 and the C0 review rounds 57 of 57 (review record below); the merge-aware validator reports the five merged predicates as `INFO` instead of requiring them red, and keeps every check for the unmerged Grow nodes (`harness/next-release/proposals/README.md`). Each predicate ran with plugin autoload off, bytecode writing off, the cache provider off and `TEMP`/`TMP`/`SYNAPSE_LOG_DIR` in a temporary folder.

**Not collected by CI.** VERIFIED: `pyproject.toml:132` testpaths are `tests`, `harness/jev/tests`, `harness/harness2/tests`, `harness/attest/tests`; every `pytest` line in `.github/workflows/ci.yml` (`:113-144`, `:186`) names other paths. The validator re-checks both on every run. The repo-walking lints read at authoring scan other roots: `tests/test_marshal_lint.py:73-76` and `tests/test_jev_product_boundary.py:13` walk `python/synapse` and `shared`; `tests/test_hou_reimport_guard.py:417` walks `tests/`; the phantom lint walks `python/synapse` (`tests/rulebook/test_rulebook_meta.py:255`). None reaches `harness/next-release/` (VERIFIED by read). Other repo-walking tests were listed by grep but not each opened: INFERENCE that none reaches it.

---

## 14 · Exact human approvals needed

All Joe's. **None is granted by this report.** A relayed instruction is never banked for a per-act gate.

**To adopt the scaffold**

1. **OD-01** — adopt the Grow lane into the next-release graph and widen its objective.
2. **OD-03** — narrow `NR-FOLLOW-ON`, or leave the predicate files unowned.
3. Merge the amendment into `graph.json` (whole, in part, or not), then let JEV rank it (lane README §2). This also covers **OD-13**.
4. Merge and push of this branch.

**OpenCV lane (open after R1-R4)**

5. **OD-11** — ratify or decline ADR-0002.
6. **OD-02** — the build node. **OD-12** — demo v1, the build window, parallelism, Windows 26H2, per-act authorization of every configure, build and install.
7. **OD-22** — replace the `meanStdDev` census with the change-mask chain, or add it beside the census (ADR-0002 decision 14) · **OD-23** — `NR-GPU-QUALIFICATION`'s gate, crux or joe · **OD-10** `cpu_reference` identity · **OD-14** scoped-delta positive-change semantic · **OD-15** named owners · **OD-16** worker venv and CUDA DLL policy · **OD-17** the other OpenCV branches.
8. **OD-04, OD-05, OD-07, OD-09** — the K1, K2 and K5 collisions and the graph home for the G0-proposed files.

**Grow lane**

9. **OD-18** — per-act authorization to launch a separate Houdini session for C1, which build, how it stays off the live bridge, and the resource window.
10. **OD-19** — the control-generation amendment; CPU-first or GPU path for C2.
11. **OD-06** — who edits the registry and panel files for Grow. **OD-08** — model and reference licensing before any C6.
12. Any NCA training run (INFERENCE: an install-class act, since the TOP appears to build a venv with pip), any checkpoint download, and every promotion into a working scene.
13. **OD-20, OD-21** — G6's home; canary before or after packaging.

**Already done; acknowledged 2026-11-08**

14. **The two w3 hython launches** (22.0.400 and 22.0.466, fenced, headless, no node created) ran under the orchestrator's brief for that scout, with no owner authorization on record at the time (§4). **Joe acknowledged both on 2026-11-08 and kept their evidence:** "I acknowledge the two w3 hython probes — keep their evidence." (orchestrator record). The acknowledgement covers those two launches only; it authorizes no further launch.

---

## 15 · Assumptions register

| Assumption | Label | Would change if |
|---|---|---|
| A separate Houdini session can stay off the live seat's bridge | UNKNOWN | It cannot — then C1 step 5 is dropped |
| The shipped `denim` pair cooks on 22.0.400 | UNKNOWN | It does not — C1 stops |
| A fixed seed replays within a useful tolerance | UNKNOWN | It does not — Variation needs a different meaning |
| Region masks protect final pixels | UNKNOWN; the blueprint says do not assume it | — |
| Grow needs a separate-process sandbox | INFERENCE from `[w3/02-grow-surface.md:55]` | An isolating in-process mechanism is found |
| Control generation is a new RETINA allocation | INFERENCE from the RETINA allocation | Joe rules it is within P6 |
| The critical path for C3-C5 is the RETINA worker, not NCA | INFERENCE from the graph | The graph changes |

---

## 16 · What C0 did not do

- **No Houdini, hython or husk launch in this stage.** The parameter probe in §4 was a prior stage of this workflow (w3), and it **did** launch hython twice, under the orchestrator's brief for that scout and with no owner authorization on record at the time; Joe acknowledged both on 2026-11-08 (§4; §14 item 14).
- **No GPU probe, build, install, pip, venv, training or checkpoint download.**
- **Nothing executed in `E:/OpenCV5.1_Prep`.** One file read there.
- **No edit** to `graph.json`, the RULING files, the lane README, `graph_decision.json`, `harness/harness2/`, ADR-0002, the G0 receipt or any governing text, in this C0 stage. The 2026-11-08 fix round edited ADR-0002 and the G0 receipt; see the round record below.
- **No merge, push, rebase, reset, amend, tag, stash or checkout.**
- **No document marked ratified.**

The only commands run against the repo were reads, `git status`/`log`, and the validator, whose predicates read committed files only.

---

## Review record (C0 scaffold)

Two independent review lenses (graph; truth and scope) refuted the first scaffold commit `280ccf79` on eight blockers. Every blocker was checked against the code, the ADR and the w3 records before it was acted on; the reviewers' evidence held in every case, so none is rebutted. The one constraint that shaped a fix: this revision may create no new file, so G2's draft predicate rides inside the amendment instead of as a new file in `predicates/`.

| Id | Lens | Disposition | Where |
|---|---|---|---|
| G1 | graph | fixed | All ten predicates find `ROOT` by walking up from the working directory to the folder holding `.git` and `harness/next-release/graph.json` (fallback `git rev-parse --show-toplevel`), never by `parents[4]`. The validator rejects any `parents[` in a predicate, copies each predicate to a temporary folder at another depth, loads it and requires its `ROOT` to equal this repository, then requires it red for its marker. A negative control (the `280ccf79` build-lock predicate copied five folders deep) resolved `ROOT` to the wrong folder, so the check discriminates. Temp-folder runs pin pytest's rootdir to the copy's own folder: an unpinned run once returned rc 2 while pytest scanned the system temp folder. README "How adoption works" step 2 states the move rule |
| G2 | graph | fixed | The full draft of `harness/next-release/gpu/test_qualification_contract.py` is carried in `_proposed_changes_to_existing[1].proposed_file` (no new repo file, by this revision's constraint). It implements the P2 design in `[w3/03-graph-map.md:142]`. `_red_markers` gains `NR-GPU-QUALIFICATION`; the validator checks the draft is carried at the exact path the predicate names, writes it to its temporary folder only, and requires rc 1 with that marker |
| G3 | graph | fixed | `NR-VG-NCA-SANDBOX → NR-VG-GROW-CONTROLS` is now `dep` and `NR-VG-GROW-CONTROLS.depends_on` includes `NR-VG-NCA-SANDBOX`. New validator check: every owned `.json` a predicate reads belongs to the node or a `depends_on` ancestor (17 reads across 11 predicates) |
| G4 | graph | fixed | OD-04 and OD-10 now list `NR-GPU-QUALIFICATION`; OD-22 is ADR-0002 decision 14 (replace the census or add beside it); OD-23 proposes the gate change crux → joe as an owner decision, not applied. The proposed `why` no longer pre-selects option (i). The fixture list and identical-mask-bytes criterion are tagged G0-proposed (G0 receipt slice 2; 02-ops §7). The validator's owner-decision gate check now covers existing nodes |
| G5 | graph | fixed | Both ratification checks match `**Status:** Accepted` case-insensitively, the ADR-0001 form; the marker for `NR-VG-RETINA-CUDA-BACKEND` says so; OD-11 and OD-19 state the required Status string |
| T1 | truth-scope | fixed | Every ADR-0002 consequence cite names its list: "Consequences of R1-R4", item N, or "Consequences", item N (§13 here; `NR-VG-RETINA-GUARDS.why`, `NR-VG-GPU-WORKER-ENV.why`, the guards edge and change 4's note in the amendment). New validator check fails on a bare cite in the amendment, README or this report |
| T2 | truth-scope | fixed | "Only what R1-R4 requires" is gone from the README and the amendment's `_comment`. Change 1's `why` keeps R2/R3 as ruled and labels the fixtures and the parity criterion G0-proposed, the NaN fixture INFERENCE. Change 4's `why` states R4 only; the cp312-only binding and the no-shared-venv point move to a note tagged INFERENCE |
| T3 | truth-scope | fixed; wording superseded on 2026-11-08 (see the round below) | No authorization for the two w3 hython launches is on record. §4 and §16 now say plainly that they ran outside this workflow's stated hard limits; §14 item 14 asks for Joe's acknowledgement. The commit message says no Houdini launch in this stage and that the parameter evidence came from the prior w3 probe |

**Nits also addressed:** the worker-env recipe test reaches its declared marker first and pins reviewed recipe text by sha256 instead of a token search; every `*_is_committed` test rejects an empty receipt; the backend import check flags only computed or backend-naming dynamic imports; the build-root check compares path components; OD-13 asks whether `NR-WORKER-SUPERVISED` may close on the old recipe; §13 cites `gpu_feasibility.json:430`, `:259` and records the `vectorAdd` run (`:25`, `:39`); §7.1 marks Core input names DOCUMENTED; §11 marks the pip reading INFERENCE; the README names the five collision pairs and drops the machine-local interpreter path; the 12-token field list in `NR-VG-GROW-CONTROLS.why` is paraphrased. **Not addressed:** moving the predicates out of `harness/next-release/` (that is OD-03), and the ignored `__pycache__` from the earlier w3 predicate run, which is outside this commit's file list.

**Validator after this revision**, run from the worktree root with a local CPython 3.14.2 and pytest 8.4.2:

```text
SUMMARY: 57 checks, 57 passed, 0 failed - amendment structurally valid; every new predicate red for its declared reason
```

Superseded on 2026-11-08 by the merge-aware run recorded in section 13 (`SUMMARY: 76 checks, 76 passed, 0 failed`), after Joe merged the OpenCV lane into `graph.json`. This block records the round as it ran.

No GPU execution was observed and no performance was measured in this revision either.

## Re-verify and fix round (2026-11-08)

The scaffold re-verify confirmed all eight round-one blockers closed and the validator at 57 of 57, but refuted `9c3b0026` on one blocker (T4) and flagged the T3 wording. On 2026-11-08 Joe authorized one narrow fix round in the reviewers' own wording across both lanes and acknowledged the two w3 probes (orchestrator record). The two C0 items are below; the four G0 items are in the G0 receipt's review record.

| Id | Lens | Disposition | Where |
|---|---|---|---|
| T4 | graph + truth-scope | fixed | §13 recipe bullet: the worker-env predicate is red only because the contract is not committed; the R4 recipe conflict is enforced later through the contract's sha256 pins, and the comment-skipping `cp314` check matches nothing today. README "Red today because" cell names the contract only; the recipe conflict is a separate note under the table |
| T3 (wording) | graph + truth-scope | fixed | §4, §14 item 14, §16: the launches ran under the orchestrator's brief for the w3 scout, with no owner authorization on record at the time; Joe's 2026-11-08 acknowledgement is quoted in §14 item 14 |

The other re-verify nits were outside this round and stay open. No predicate, validator check or amendment field changed.

**Validator after this round**, same command, interpreter and pytest as above, with plugin autoload and bytecode writing off:

```text
SUMMARY: 57 checks, 57 passed, 0 failed - amendment structurally valid; every new predicate red for its declared reason
```

Superseded on 2026-11-08 by the merge-aware run recorded in section 13 (`SUMMARY: 76 checks, 76 passed, 0 failed`), after Joe merged the OpenCV lane into `graph.json`. This block records the round as it ran.
