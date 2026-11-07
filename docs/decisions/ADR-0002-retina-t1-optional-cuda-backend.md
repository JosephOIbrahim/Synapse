# ADR-0002: An Optional OpenCV 5.1 CUDA Backend for Selected RETINA T1 Operations

**Date:** 2026-11-07  
**Status:** PROPOSED - not ratified. Ratification is Joe's alone; this file changes no governing document.  
**Authors:** Claude (integration author, this session). Proposed to Joe Ibrahim, product and ratification authority and the named G0 owner. Naming Joe G0 owner approves nothing in this file.  
**Input under reconciliation:** "SYNAPSE: OpenCV 5.1 GPU Integration Blueprint", dated 7 November 2026, sha256 `bbaeed26669b945c2811399b9bbae0a1a183dbd18b6bb57d121f7391d271bf43`. It is cited by section here and is not reproduced.  
**Companion record:** `docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md` (the G0 receipt).  
**Baseline:** branch `vision/opencv51-g0` at `ef43d37aaedb677bebc548a5fc921d4bea4565fd`. `retina/` is byte-identical to tag `v5.98.0` (`6a5f68dd`) and to `origin/master` (`e3846b22`).

**G0 observed no GPU execution and measured no performance.** Every speed, VRAM or latency figure below is UNKNOWN unless a receipt is named.

### Evidence key

Every factual sentence carries one of these:

- **VERIFIED** - a repo `path:line`, a git object, or a command and its output.
- **INFERENCE** - reasoned, not observed. Never promoted to VERIFIED here.
- **UNKNOWN** - nobody has measured it.
- **REFUTED** - a claim the code contradicts.

Bracketed citations such as `[01-trace §3]` name a G0 reconciliation report and its section. Those reports are local working papers, not committed. They are identified by file name and sha256 in the receipt's evidence table, and each one cites the repo `path:line` reproduced here. "Orchestrator record" means facts established by the workflow orchestrator outside the reports.

---

## Context

### 1. The allocation this ADR would amend

The governing RETINA design allocates the work three ways. All quotations are VERIFIED at the cited line.

| Allocation | Governing text | Where |
|---|---|---|
| **GPU-heavy pixel work goes to Copernicus; OpenCV is the independent oracle** | P6: "GPU-heavy per-pixel work becomes **COP networks SYNAPSE builds itself**; OpenCV serves as CRUCIBLE's independent oracle — the same metric computed both ways must agree within ε." | `docs/SYNAPSE_RETINA_BLUEPRINT.md:46` |
| **T1 runs on CPU** | T1 row, cost column: "ms, CPU, headless" | `docs/SYNAPSE_RETINA_BLUEPRINT.md:93` |
| The GPU tier is T2, and it is ONNX, not OpenCV | T2 row: "ONNX: FLIP perceptual error, segmentation" ... "GPU when present" | `docs/SYNAPSE_RETINA_BLUEPRINT.md:94` |
| One inference stack | "**onnxruntime** for all model inference" | `docs/SYNAPSE_RETINA_BLUEPRINT.md:73` |
| The host stays eye-free | "**Zero `cv2` imports host-side, ever**" | `docs/SYNAPSE_RETINA_BLUEPRINT.md:45` |
| Where the oracle runs | M4: "oracle cross-check (COP vs OpenCV within ε)" | `docs/SYNAPSE_RETINA_BLUEPRINT.md:167` |
| Why the oracle matters | "OpenCV remains the only genuinely independent oracle." | `docs/reviews/retina-reconciliation-2026-07-16.md:74` |

**Why only Joe can move it.** The RETINA blueprint lets the reconciliation record and the truth catalog outrank its INFERENCE lines (`docs/SYNAPSE_RETINA_BLUEPRINT.md:14-16`). The "CPU" in the T1 row and the P6 allocation are design allocations, not INFERENCE lines, so that clause cannot move them [03-governance §2.3]. A ratification flip is a per-act human gate (`AGENTS.md:76`) and is never relayed through another agent (`AGENTS.md:69-70`).

**This amendment has been asked for before and never written up.** The next-release source blueprint asks for "a small P6 design amendment" (`docs/intake/src/synapse_next_release_blueprint.md:242`) and says a CPU/GPU OpenCV comparison "is not an independent COP/OpenCV oracle comparison" (`:234`). The intake, both rulings, `graph.json` and the next-release README never carried that ask forward [03-governance §2.3, §6.1]. This ADR is the first write-up.

**Which job the backend serves.** In this repo's rulings, "vision" names the VLM route (R180-R182, `harness/notes/CTO_RULINGS_01.md:5464-5649`). R182 keeps the measured half, "by how much", in OpenCV in the worker, and calls it "a different job" (`:5640-5645`). `harness/SYNAPSE_RETINA_VERIFY.md:89` says cv2 "earns its place on the delta MASK". So the CUDA backend proposed here is **measurement on arrays the worker has already ingested**. It is not semantic vision, not inference and not capture [03-governance §3.2].

### 2. What G0 found that changes the input blueprint's premise

The input blueprint calls RETINA an "existing out-of-process perception subsystem" (its Executive decision) and places a "T1 backend dispatcher" between OIIO ingest and an evidence sidecar (its §3). At `ef43d37a`, that pipeline does not run.

1. **T1 has no production caller.** VERIFIED. Outside `tests/` and `harness/`, the only importer of the `retina` package is `python/synapse/panel/render_receipt.py:42,50`, and it imports `retina.t0` only. `installer/build_payload.py:22-23` lists the files for packaging and calls nothing [01-trace §3; 02-ops F8; 05-claims §4.1].
2. **Nothing launches a worker.** VERIFIED. `retina/` has no entrypoint, no `__main__` and no subprocess launcher. The two files the graph assigns to the worker, `retina/worker_entrypoint.py` and `python/synapse/host/retina_worker.py`, do not exist [01-trace §3; 06-critic §1.8]. `retina/.venv` is absent from this worktree [01-trace §3].
3. **No production code writes a verdict sidecar.** VERIFIED. `emit_verdict` (`retina/events.py:86-100`) is reached only through `retina/t0.py:409-419`, which only `tests/test_retina_t0.py:247` calls. The panel path documents that it never writes (`python/synapse/panel/claude_worker.py:1100-1102`; `render_receipt.py:10-13`). No path convention, schema version or reader for a sidecar exists [01-trace §8-9; 05-claims 1.17].
4. **The tier that runs, T0, runs inside Houdini.** VERIFIED. `ClaudeWorker._emit_render_receipt` (`claude_worker.py:1093-1111`) calls `render_receipt.compute_receipt`, whose `_load_t0` inserts the repo root into `sys.path` inside Houdini's interpreter (`render_receipt.py:35-53`). T0 runs on the panel's worker thread. This contradicts `retina/__init__.py:9-15`, which describes the tree as running in its own venv outside every host surface [01-trace §3].
5. **The zero-cv2 host lint is lexical, not transitive.** VERIFIED. `tests/test_retina_boundary.py` scans host surfaces with a regex (`:38-57`) and keeps `retina/` out of scope on purpose (`:104-117`). If `retina/__init__.py`, `t0.py`, `events.py` or `exr_header.py` ever reached a backend module, CUDA libraries would load into Houdini and the test would stay green. That consequence is INFERENCE [01-trace §11; 05-claims 1.16].
6. **No test pins zero `hou` in the worker.** VERIFIED. `retina/` imports no `hou` today, but nothing fails if one is added [01-trace §11; 05-claims 1.15].
7. **The host installer ships T1.** VERIFIED: `installer/build_payload.py:22-23` lists `retina/t1.py` and `retina/ingest.py` in the host payload. A backend module appended to that list would ship with the host while the lint stays green. That is INFERENCE [06-critic §4.5].
8. **The scoped-delta target source is refuted, and the check has a positive-change gap.** R100 ruled that no usable per-object integer ID mask exists on Karma 22.0.368 (`CTO_RULINGS_01.md:2799-2817`). R182 replaced object identity with the vision route and kept "by how much" in OpenCV (`:5580-5649`). Separately, stated abstractly: the scoped-delta check confirms that change stayed inside the claimed target and that the outside held still, but **no check requires that anything changed inside the target**. An unchanged before/after pair, or a target absent from the frame, rolls up to `pass`. Static reading: VERIFIED (`retina/t1.py:480-541`). Executed on CPU with cv2 4.12.0: report 05 reproduced both cases as `pass`. That run is artifact-read here, not re-executed [02-ops §4, F5; 05-claims §6; 06-critic §1.14].

**What this means for where a backend can go.** INFERENCE (design), grounded in the VERIFIED facts above [01-trace §12; 06-critic §5.2]:

- There is **no hot path** to insert a dispatcher into. The input blueprint's instruction to choose a chain "after profiling actual call sites" (its §4) cannot be followed, because there are no production call sites [02-ops B2].
- The narrowest existing seam is **beneath the four cv2-using primitives** in `retina/t1.py`: `ssim` (`:218`), `change_mask` (`:253`), `id_matte` (`:277`) and `ssim_outside` (`:321`). Their callers, `assess_frame` (`:433`) and `assess_scoped_delta` (`:480`), stay the call boundary. `events.py`, `build_t1_event` (`:416`) and the tri-state roll-up stay untouched. The backend is chosen by explicit argument or policy, never by an import-time global.
- **Placement constraint:** no backend module may be reachable from `retina/__init__.py`, `retina/t0.py`, `retina/events.py` or `retina/exr_header.py`, because those load inside Houdini. No backend module may join the host payload list.
- **Until a worker exists, the only honest consumer of a backend is an offline shadow-parity harness.** A backend with no production invoker would repeat the pattern this repo retired in R20 (CLAUDE.md §2.3: a mechanism with no producer and no consumer).
- **Production use needs work this ADR does not do:** a worker entry and host launcher (owned by `NR-WORKER-SUPERVISED`), and a sidecar path, schema and reader (closest owner: `NR-RECOVERY-RECEIPTS`, which owns `retina/publication.py`; that fit is INFERENCE).

### 3. A ruled program for this goal already exists

The input blueprint does not cite it [05-claims §4.2]. All rows VERIFIED unless tagged.

- **Owner direction, 2026-11-06:** "incorporating OpenCV 5.1 with GPU use for SYNAPSE ... not replacing currently running tasks but development in tandem or consecutively" (`harness/next-release/RULING-2026-11-06.md:7-8`).
- **Closed decisions:** D6, the build route, is "source-built OpenCV 5.1 + opencv_contrib with CUDA". D1, the support row, is Windows 11, H22.0.400, RTX 4090, `gpu_required` (`:15-18`). Host and worker Python ABI are WP1 outputs, never assumptions (`:20-22`).
- **Operating rules:** tandem, not replacement; "JEV decides the order"; every node lands in a worktree with failing-first tests, one commit, adversarial review and an owner-only merge; "The GPU track starts as a probe" (`:31-43`).
- **The graph:** `harness/next-release/graph.json` holds `NR-GPU-FEASIBILITY` (gate joe), `NR-GPU-QUALIFICATION`, `NR-IMAGE-CONTRACT` (owns `retina/events.py`, `ingest.py`, `t1.py`, `qc_profiles.toml`), `NR-WORKER-SUPERVISED`, `NR-RECOVERY-RECEIPTS`, `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE` (`graph.json:72-180`).
- **Ordering:** the last recorded JEV graph decision (`harness/harness2/runs/next-release/graph_decision.json`, generated 2026-11-07T01:58Z) lands `NR-PLAN-TRUTH` and `NR-WRITE-RECEIPT` and parks every GPU and RETINA node. Its reason is "fallback: Jev chose NR-PLAN-TRUTH @ 0.44, below the confidence gate 0.6" [03-governance §6.1].
- **Round two:** R6 says "The GPU lane closes B1, not the build", and B2, the worker Python ABI, "is the owner's decision and stays open" (`RULING-2026-11-07-round2.md:49-53`). W7 says the GPU predicate "certifies the probe, not the build" and the node's gate is `joe` (`:105-112`).

#### What NR-GPU-FEASIBILITY proved, and what it did not

Merged as `d9a325bc` on 2026-11-07 with the subject "merge: NR-GPU-FEASIBILITY, B1 closed by a real compile and run". It is an ancestor of `ef43d37a` and of the `v5.98.0` tag (VERIFIED: `git merge-base --is-ancestor`). Everything below is VERIFIED as the content of its committed receipt, `harness/next-release/gpu_feasibility.json`. **G0 did not re-observe that execution:** the probe's worktree is no longer in `git worktree list` [06-critic §3.15], and G0 ran no GPU probe [03-governance §6.1; 06-critic §2.11].

| Question | Answer from the receipt | Where |
|---|---|---|
| What was compiled | A trivial 2,300-byte CUDA kernel, `vectorAdd.cu` (sha256 `65ea0871...6180`), which describes itself as "Not a product artifact". It is **not OpenCV code.** | `gpu_feasibility.json:460-466` |
| With what | `nvcc -arch=sm_89` (CUDA 13.3, V13.3.73) under MSVC `cl` 19.44.35222, toolset 14.44.35207, from a `vcvars64` shell. Exit 0 | `:449-458`, `:470-475` |
| What ran | `vectorAdd.exe` on the RTX 4090 (cc 8.9): n=1024, 0 mismatches, exit 0. The first invocation was a shell lookup failure (exit 9009), recorded as such | `:478-491` |
| Where | A gitignored scratch directory inside the probe's own worktree. **Not under any build root.** The planned root `C:/ocv` did not exist | `:461-463`, `:137`, `:259` |
| What it closed | B1: nvcc 13.3 accepts MSVC 19.44 as its host compiler | `:325-332`, `:493-494` |
| Verdict | `feasible-unproven`: "no OpenCV source build exists, so no CUDA chain is proven" | `:37-39` |
| What it did **not** prove (its own list) | No CMake configure of OpenCV; no OpenCV module (`cudaarithm` included) compiled; no Python binding for either candidate interpreter; no masked `cv2.cuda.meanStdDev`; no OpenCV CUDA chain executed | `:51-58`, `:495-501` |
| Closure | `real_closure_state`: "UNMET: no build, no device count, no executed masked meanStdDev". B2 to B6, B9 and B10 remain open | `:431`, `:333-404` |

**The settled sentence:** one trivial CUDA kernel, unrelated to OpenCV, compiled and ran on this machine according to a prior lane's committed receipt. No OpenCV source has been fetched, configured or built under either candidate recipe, and **no OpenCV CUDA operator has executed anywhere in this program.** The separate prep project under `E:/OpenCV5.1_Prep` ran a compile-only probe with `gpu_execution:false` (prep record, `E:/OpenCV5.1_Prep/01_Inspections/raw/preparation-20261106T194127Z/compile_conforming_result.json`) [04-prep §4].

---

## Decision (proposed)

**RETINA T1 may gain an optional OpenCV 5.1 CUDA execution backend for a small, named set of classical measurement operations. It runs only inside the out-of-process worker, behind RETINA's existing tri-state contract. The CPU path stays the reference. Copernicus keeps its production image-processing role and its place in the independent COP-vs-OpenCV oracle. The backend grants no verdict any mutation authority.**

### Proposed amendment wording

This is the text Joe would ratify. It is **not applied anywhere** by this file.

- **P6, appended:** "Copernicus keeps production GPU image processing and authoring, and the COP-vs-OpenCV oracle (M4) keeps its independence. In addition, the RETINA worker may run selected T1 classical measurements on an optional OpenCV CUDA backend. A CPU-vs-CUDA OpenCV comparison is backend parity. It never stands in for the independent oracle."
- **T1 row, cost cell:** "ms; CPU reference; optional CUDA per named operation (worker only); headless".

**Where it would live once ratified.** The RETINA blueprint was committed verbatim and is not edited (`docs/SYNAPSE_RETINA_BLUEPRINT.md:14-16`) [03-governance §5.2]. The ratified ADR is the amendment record. Whether the reconciliation record also gains a pointer line is Joe's call.

### What it preserves

| Preserved | Anchor |
|---|---|
| ONNX Runtime for all inference; T2 unchanged | `docs/SYNAPSE_RETINA_BLUEPRINT.md:73`, `:94` |
| OIIO EXR ingest; `$OCIO` read, never set; ID and data planes never colour-transformed | `retina/ingest.py:81-103`, `:121-154`, `:179-197` |
| The event envelope `{ch, v, tier, claim, checks, verdict, proof, at}`; tri-state checks; roll-up fail > inconclusive > pass; caller-supplied time | `retina/events.py:43-60`, `:74-83`; `retina/__init__.py:30-31` |
| Sidecar JSONL as the persistence form; no USD writes | `retina/events.py:86-100` |
| Zero `cv2` in the host, made **transitive** rather than only lexical | `tests/test_retina_boundary.py:67-101` today |
| Zero `hou` in the worker, made **pinned** | none today (Context §2 item 6) |
| T0 before T1: the ladder routes cheap-first and never skips a tier downward | `docs/SYNAPSE_RETINA_BLUEPRINT.md:97` |
| No verdict gains mutation authority | input blueprint §2 invariant 7. The graph edge `NR-WRITE-RECEIPT -> NR-WORKER-SUPERVISED` ("vision proposals may only mutate through the authored-write receipt path", `graph.json:245`) is not exercised by this ADR: the backend emits measurements, never proposals |

No new envelope field is added before a consumer-compatibility test and a contract review. Backend detail goes in the evidence sidecar first (input blueprint §3).

### Backend interface (PROPOSED, not existing APIs)

The names `probe_capabilities`, `analyze`, `cancel` and `close` are **PROPOSED**. None exists under `retina/` (VERIFIED: grep at `ef43d37a`). `analyze` and `gpu_required` do appear elsewhere in the repo with unrelated meanings (`shared/conductor_advisor.py:107`; the cache-policy tests).

- `probe_capabilities()` reports artifact identity, `cv2.__file__`, the selected device, driver and runtime, the exact operators available, and the last probe result. It runs only when the mode is not `off`.
- `analyze(request)` takes already validated arrays and an immutable request naming an **allowlisted operation** and constrained parameters. It returns measurements, per-operation execution provenance and structured failures. It never accepts Python, command strings, module names or executable paths. It validates dimensions, dtype, channels, bounds and total allocation before it touches a device.
- `cancel(job_id)` and `close()` release only resources the job owns. Neither may terminate Houdini or a renderer.

### Backend modes

| Mode | Use | When CUDA or an operator is missing |
|---|---|---|
| `off` | Default for every user until opt-in | No GPU probe and no CUDA load at startup. T1 runs `cpu_reference` |
| `cpu` | Existing behaviour and the reference path | `cpu_reference` runs, and the sidecar records CPU provenance |
| `gpu_required` | Joe's GPU profile (the D1 row) | Each GPU-required operation that cannot run on CUDA makes its check **inconclusive with a reason**. It is never a silent CPU pass |
| `auto` | A possible later customer policy; not proposed for the first slice | May pick CPU only with explicit per-operation provenance |

**Honest failure, concretely.** The envelope is tri-state, and "unavailable" is not one of its values (`retina/events.py:43-60`). So a `gpu_required` operation that cannot run on CUDA yields a check with `pass=None`. Its `detail` gives the reason, for example "no CUDA device", "operator not present in the artifact" or "dtype unsupported". The sidecar receipt records `UNAVAILABLE` for that operation, with the reason (AGENTS.md Law 1). The roll-up then reads `inconclusive`, never `pass`. Two existing facts constrain this:

- `T1Unavailable` is an **exception** today (`retina/t1.py:94-109`), with no mapping to an event. A worker must catch it and map it, and that mapping is new work [05-claims 1.9].
- `python/synapse/panel/verdict.py:84-92` is two-state, and `check_from_tristate` maps inconclusive to `fail`. If a future reader routes RETINA events through that verdict, an unavailable GPU operation would render as **fail**, not as unavailable. That is INFERENCE; the function has no production caller today [06-critic §4.6].

**Per-operation coverage-map rule.**

1. Every allowlisted operation has exactly one designation per mode: `cuda`, `cpu_reference`, or `cpu_disclosed`. `cpu_disclosed` covers work that always stays on CPU, such as OIIO decode, luma, numpy reductions and SSIM.
2. GPU success may be claimed for an operation only if that operation dispatched on CUDA in this job. The sidecar records the executed dispatch branch and a backend witness per operation, as `harness/next-release/README.md:93-95` requires.
3. No GPU-required operation may fall back to CPU internally. A fallback turns that operation's check inconclusive.
4. The map is versioned and frozen before evaluation. A coverage claim is always narrower than the mixed pipeline.
5. A check's verdict depends only on its inputs and profile, never on the backend. The backend is provenance.

---

## Sites (proposed)

| # | Site | Owner today | State |
|---|---|---|---|
| 1 | Backend selection beneath the four cv2-using primitives in `retina/t1.py` (`:218`, `:253`, `:277`, `:321`), with exactly one backend, `cpu_reference`, byte-identical to today | `NR-IMAGE-CONTRACT` (`graph.json:101-115`) | Addressed to that node, not taken |
| 2 | A worker-only CUDA module, off the host payload list and unreachable from the in-host modules | **Unowned**; a new file needs an owner | After a qualified artifact exists |
| 3 | The offline shadow-parity harness: the same chain on `cpu_reference` and CUDA over an approved corpus | `NR-GPU-QUALIFICATION` (`harness/next-release/gpu/`) | After a build exists |
| 4 | The worker entry and host launcher | `NR-WORKER-SUPERVISED` | Planned files absent |

## Refused Sites

1. **The Houdini host process.** No cv2, CUDA or backend module runs or is reachable there, including through the `retina.t0` path.
2. **T2 and all inference.** ONNX Runtime stays. OpenCV DNN, cuDNN and TensorRT stay out.
3. **SSIM.** It stays on the CPU reference in float64. The pinned contrib source has no float64 row in the CUDA separable filter (`cudafilters/src/filtering.cpp:398`, `:409`, asserted at `:452`) [02-ops F4; 04-prep §3]. A float32 port is a new numerical design that needs separate approval (input blueprint §6).
4. **The ID matte.** Its source was refuted (R100). No GPU work goes into it [06-critic §2.6].
5. **Verdict authority, consent and scene writes.** None.
6. **The independent oracle.** A CPU-vs-CUDA OpenCV comparison never substitutes for the COP-vs-OpenCV cross-check (M4).
7. **Thresholds and profiles.** Values are never loosened to absorb backend error (input blueprint §4; `harness/next-release/README.md:97`).
8. **Capture, viewport, Qt viewers, shared memory, pixel sockets and HAPI.** Out of scope (input blueprint §3).
9. **The host installer payload list** (`installer/build_payload.py:22-23`).

## Invariants Inherited

- AGENTS.md Laws 1-7, especially Law 1 (honest seam), Law 4 (unmeasured renders UNKNOWN) and Law 7 (per-act human gates).
- RETINA P4 and P5 (`docs/SYNAPSE_RETINA_BLUEPRINT.md:44-45`).
- The next-release stop rules (`harness/next-release/README.md:99-108`) and R4: a node's closure predicate is behavioural and able to fail (`RULING-2026-11-07-round2.md:36-42`).
- Exclusive file ownership per node (CLAUDE.md Agent Roster).

---

## Reconciliation with the ruled program

**This ADR does not create a parallel board.** If ratified, the input blueprint's stages run as existing `harness/next-release` nodes. JEV and Joe keep the order (`RULING-2026-11-06.md:36-38`).

| Input blueprint stage | NR node or nodes | `owner_files` collision |
|---|---|---|
| G0 reconcile | the 2026-11-06 intake plus this ADR and receipt | None. These two files are new and unowned |
| G1 qualify artifact | `NR-GPU-FEASIBILITY` (merged, `feasible-unproven`), then `NR-GPU-QUALIFICATION` | Both own `harness/next-release/gpu/`. G1 runs **as** these nodes |
| G2 add seam (GPU off) | `NR-IMAGE-CONTRACT` for the `retina/t1.py` seam; `NR-WORKER-SUPERVISED` for any launcher | Same `retina/` files. **This widens `NR-IMAGE-CONTRACT`'s declared scope** (named RGB, derived Y, invalid-sample policy; `graph.json:102`, `:111`) to include a backend seam. That is a ruling, not a mapping |
| G3 shadow parity | `NR-GPU-QUALIFICATION` ("an independent CPU reference", `graph.json:87`) | Same intent, same files |
| G4 Joe canary | **No node** | New node needed after demo v1 |
| G5 optional beta | `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE` | Both own `installer/build_payload.py`. That double ownership already exists in the graph [06-critic §4.4] |
| G6 consolidate | `NR-FOLLOW-ON` (parked) | Loose fit |

### Decisions that need Joe's ruling

Each item lists the options and the evidence. None is settled here.

1. **Governance: fold in or run separately.**
   - (a) This blueprint runs as the existing NR nodes. Recommended.
   - (b) A separate G0-G6 track.
   - Evidence: the mapping above. The input blueprint's own rule, "do not build a second vision architecture" (its Executive decision). [03-governance §0, §7; 05-claims §8.1]
2. **The first GPU chain and the build recipe and root, as one coupled ruling.** The chain decides the module set, and the module set decides the recipe.
   - (a) **Change-mask body:** difference, then threshold, then open, then close (`retina/t1.py:266-273`). Its dtypes appear in the CUDA source tables (`absdiff_mat.cu:151`, `threshold.cu:352`, morphology 8UC1 at `filtering.cpp:648`). Its output is binary, so parity is exact byte equality. It ports cv2 calls T1 already makes [02-ops §7, F10]. It needs `cudafilters`. The NR recipe builds `BUILD_LIST=core,cudaarithm,python3` (`gpu_feasibility.json:282`, `:300`), so that artifact **would not contain the morphology operators**. That is INFERENCE from the module list [06-critic §2.1]. The E: recipe builds `cudafilters` (`E:/OpenCV5.1_Prep/02_OpenCV_Setup/preparation/Current_Configure.json`, BUILD_LIST at `:26`) [04-prep §2].
   - (b) **Masked `cv2.cuda.meanStdDev`:** "split + addWeighted -> masked meanStdDev -> compare/mask/countNonZero" (`gpu_feasibility.json:56`). It replaces numpy reductions in T1 (the firefly census at `retina/t1.py:199-207`), not an existing cv2 call. Choosing it adds a new GPU operation rather than porting one [02-ops §2 row 5]. Its Python binding is unverified (B6, `gpu_feasibility.json:365-371`).
   - **Build root and recipe:** `C:/ocv`, with the NR recipe and `/m:32` parallelism (`gpu_feasibility.json:259`, `:283`, `:302`), or `E:/OpenCV5.1_Prep/02_OpenCV_Setup`, with the E: recipe, `--parallel 1` and threads pinned to 1 (`Current_Configure.json:115-127`) [04-prep §2; 06-critic §2.4]. Parallelism decides how safe a build window is while demo v1 or OVOID runs.
   - **An honest caveat for (a):** at the small verification sizes RETINA names (`docs/SYNAPSE_RETINA_BLUEPRINT.md:105`), a light chain may lose to CPU once transfers are counted. UNKNOWN until measured [02-ops §7].
3. **The worker interpreter ABI (B2).**
   - (a) CPython 3.12.10.
   - (b) CPython 3.13. Only a Microsoft Store alias exists on the box; a provisioned interpreter would be needed (`gpu_feasibility.json:266`).
   - Constraints: the staged E: configure bakes 3.12.10 with `PYTHON3_LIMITED_API` unset, so the binding would be cp312-only. That is INFERENCE [04-prep §1]. The NR lane's 3.12.10 and the E: venv share **one base interpreter**. The real divergence is venv location and build root [06-critic §2.3]. The RETINA venv recipe seeds from the PATH `python`, which was 3.14.2 at inspection [04-prep §1].
   - Owner: Joe, per R6 (`RULING-2026-11-07-round2.md:51-53`).
4. **The OIIO source.**
   - (a) An isolated wheel. `OpenImageIO==3.1.15.0` publishes a `cp312` win_amd64 wheel on PyPI (VERIFIED by report 04's fetch; installability next to a custom `cv2` is UNKNOWN) [04-prep §1].
   - (b) The repo's documented hython-seeded venv, which inherits Houdini's OIIO (`retina/setup_venv.py:10-16`; `retina/requirements.txt:34-37`).
   - The input blueprint forbids (b) (its §4), and so does the NR lane (`gpu_feasibility.json:271`). The shipped recipe recommends it. Also open: V0-R3, "who creates the worker venv" [01-trace §3; 05-claims 3.7].
5. **Graph order.**
   - (a) Leave JEV's park in place, where every GPU and RETINA node is parked.
   - (b) Re-run the JEV graph guard now that `NR-GPU-FEASIBILITY` has merged.
   - (c) Amend the graph to decouple a CPU-only worker and sidecar from `NR-GPU-QUALIFICATION`. Today `NR-WORKER-SUPERVISED` depends on both `NR-IMAGE-CONTRACT` and `NR-GPU-QUALIFICATION` (`graph.json:125-128`).
   - Evidence: `graph_decision.json`; `RULING-2026-11-06.md:36-38` [06-critic §5.4].
6. **CPU-reference defects a parity test would inherit.**
   - **The missing shape guard.** V0 F2 recorded a crash on shape mismatch. Neither orchestrator guards shape before the cv2 calls (`retina/t1.py:238`, `:266`, `:352`); only `containment` does (`:304-308`). The input blueprint's corpus requires resolution changes with identical tri-state outcomes (its §6). Options: (a) fix forward so mismatched shapes yield inconclusive; (b) exclude the case from parity by decision. The static reading is VERIFIED. That it still crashes at runtime is INFERENCE, since it was not re-run [02-ops F12, B3; 01-trace §6].
   - **The scoped-delta positive-change gap** (abstract form in Context §2 item 8). Options: (a) a semantic contract decision that adds a positive "the claimed change happened" term, which `harness/SYNAPSE_RETINA_VERIFY.md:38` already names as `miss`; (b) keep the current semantics and stop citing the check as proof that a change occurred. Either way it is **not** CUDA parity work (input blueprint §6) [05-claims §6; 06-critic §1b].
   - **Related:** V0 F9, frame-health false positives on scene-linear renders, holds statically (`retina/t1.py:143-188` against `retina/qc_profiles.toml:38-41`) [01-trace §6].
7. **SSIM stays on CPU in float64.** Confirm, or commission a float32 numerical design as separate work. Evidence is in Refused Sites item 3. Report 05 adds that SSIM inputs reach the float64 path already reduced to float32 luma, so float64 protects the variance subtraction, not input precision. That is INFERENCE for the design question [05-claims 3.2].
8. **The identity of `cpu_reference`.**
   - (a) The stock `opencv-python-headless==5.0.0.93` wheel in its own venv. Report 04 calls this the safest option.
   - (b) The custom 5.1 build's CPU path, compiled with `WITH_IPP=OFF` and `WITH_TBB=OFF` (`Current_Configure.json:65-70`).
   - Whether T1 metrics differ between the two is UNKNOWN. The cv2 4.12.0 found in the default interpreter's user site must not be the oracle [04-prep F-c; 05-claims §4.3].
9. **The third OpenCV surface.** The unmerged branches `feat/opencv-render-qc` and `pd/loop2-opencv-fire` add `retina/firefly_scan.py` and `python/synapse/cv/`. Options: supersede, absorb or coexist [03-governance §6.2].
10. **The RETINA.M3 queue entry.** It is `ratified: true`, but its title describes the ID-matte route that R100 refuted (`harness/state/flywheel_queue.json:471-473`). Options: amend or leave it [03-governance §4].
11. **Named owners** for the input blueprint's §7 roles: integration, build and package, an independent correctness reviewer, and release and support. Joe assigns these; none is proposed here [06-critic §4.3].

---

## Consequences

If ratified:

1. P6 and the T1 row gain an amendment record. The RETINA blueprint text stays verbatim.
2. CPU-only RETINA stays the default for every user. `off` loads nothing new.
3. Nothing changes at runtime until two things exist: a worker that invokes T1, and a qualified artifact. Until then the only consumer is an offline parity harness.
4. Two new guard tests become preconditions for any backend code under `retina/`: a transitive-reachability test for the in-host modules, and a zero-`hou`-in-worker test.
5. The worker gains a second dependency profile: a custom CUDA `cv2` that must never share a venv with the stock wheel. The RETINA venv recipe installs `opencv-python-headless` (`retina/requirements.txt:28`), so a GPU worker needs its own recipe. That is INFERENCE [04-prep F-a].
6. A downstream V2-verdict reader would render an unavailable GPU operation as `fail` (Decision, honest failure).
7. GPU coverage claims stay narrower than the pipeline: decode, luma, SSIM and the numpy reductions stay on CPU unless a later decision moves one.
8. Performance is UNKNOWN. The input blueprint's 1.5x target may fail on a light chain. Its own rule then applies: narrow the supported workload, never revert to CPU silently [02-ops §7].

If declined: see Alternative A1.

## Alternatives considered

| # | Alternative | Assessment |
|---|---|---|
| A1 | **Stay CPU-only.** T1 remains "ms, CPU, headless" | The cheapest and safest choice, and it changes no allocation. Not preferred: the owner's 2026-11-06 direction sets the GPU vision goal and D1 fixes a `gpu_required` row (`RULING-2026-11-06.md:7-8`, `:18`). It stays the fallback if the decisions above stall, and it keeps every guard test in this ADR useful on its own |
| A2 | **Copernicus-only GPU.** Every GPU pixel measurement is authored as COP networks, as P6 says | Keeps the allocation intact. Not preferred as the **only** route, for three reasons. COP execution means Houdini's process and a licence seat (the HAPI analysis at `docs/reviews/retina-reconciliation-2026-07-16.md:71-79`). The COP QC net and the M4 oracle have never run, because cycles C.3, C.4 and C.10 are `candidate` [03-governance §4]. And the measurement must happen in the hou-free worker where the arrays already are (R182). This ADR keeps Copernicus's role rather than replacing it |
| A3 | **A separate vision board.** Run the input blueprint's G0-G6 as its own track | Not preferred. The input blueprint itself forbids a second vision architecture, and the NR graph already owns the same files (`retina/t1.py`, `harness/next-release/gpu/`, `installer/build_payload.py`). Two boards on one set of `owner_files` is the silent-corruptor case (AGENTS.md Law 6; `harness/next-release/README.md:107-108`) |
| A4 | **Port every T1 metric** | Not preferred. The input blueprint says not to (its §4). SSIM cannot run on CUDA in float64 at source level. The ID matte's source is refuted. Most per-frame work is numpy, not cv2 [02-ops §2, §7] |
| A5 | **Put CUDA OpenCV in the host** | Refused. It violates P5 (`docs/SYNAPSE_RETINA_BLUEPRINT.md:45`) and input blueprint invariant 3 |

## Rollback

- **This file:** revert its commit. No runtime, test or governing surface depends on it.
- **After ratification, before any code:** record a superseding ADR. Per the rulebook's status vocabulary, the old text is kept for citation and its replacement is named (`rulebook/RULEBOOK.md:49`) [03-governance §5.1].
- **After code lands:** set the mode to `off` or `cpu`. That is a policy change, never a disguised success. Restore the previous known-good worker package and restart only the worker. Keep evidence and logs, and never delete frames, baselines or scenes. In `gpu_required` mode, rollback may leave GPU vision visibly unavailable while SYNAPSE stays usable (input blueprint §7).

## What this ADR does not authorize

- No build, configure, clone or install of OpenCV, CUDA, OIIO or anything else, and no pip install or venv creation.
- No GPU work of any kind: no probe, device query, kernel, benchmark or soak.
- No pairing of a worker artifact with SYNAPSE, and no installer or payload change.
- No scene writes, live Houdini GUI actions, renders, capture or production-scene contact.
- No release-surface edits: `VERSION`, release notes or tags.
- No merge, push or tag.
- No edit to `docs/SYNAPSE_RETINA_BLUEPRINT.md`, the reconciliation record, the perception truth catalog, `harness/state/flywheel_queue.json`, `graph.json` or any `ratified` field.
- No graph re-order. JEV and Joe keep the order.

## Proposed flywheel cycle (not appended)

If ratified, one cycle would be **appended** after the existing entries as `status: candidate, ratified: false`, citing this ADR as evidence. Suggested id: `RETINA.T1-cuda-backend`. It must not be inserted between M2 and M3, and it must not edit M3-M5 [03-governance §4]. This file appends nothing.

## Producer Paths

| Deliverable | File | Node | State at `ef43d37a` |
|---|---|---|---|
| This proposal | `docs/decisions/ADR-0002-retina-t1-optional-cuda-backend.md` | none (G0) | Proposed |
| G0 receipt | `docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md` | none (G0) | Draft |
| Transitive host-boundary, zero-`hou` and payload-exclusion tests | new test file(s) under `tests/` | unowned (receipt §11) | Not written |
| `cpu_reference` seam | `retina/t1.py` | `NR-IMAGE-CONTRACT` | Not written |
| Build lock and artifact receipt | `harness/next-release/gpu_feasibility.json` and its successor | `NR-GPU-FEASIBILITY` | `feasible-unproven`; real closure UNMET |
| Parity receipt | `harness/next-release/gpu_qualification.json` | `NR-GPU-QUALIFICATION` | Absent |
| Worker entry and launcher | `retina/worker_entrypoint.py`, `python/synapse/host/retina_worker.py` | `NR-WORKER-SUPERVISED` | Absent |
| Sidecar publication | `retina/publication.py` | `NR-RECOVERY-RECEIPTS` | Absent |
| Worker artifact pair, notices | `installer/...` | `NR-PACKAGE-PAIR`, `NR-LICENSE-GATE` | Absent |

*A companion input, "SYNAPSE Neural Growth Creative Loop Blueprint" (7 November 2026, sha256 `070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647`), was **not** reconciled by this G0. Nothing here adopts or rejects it.*
