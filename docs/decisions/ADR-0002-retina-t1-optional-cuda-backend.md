# ADR-0002: An Optional OpenCV 5.1 CUDA Backend for Selected RETINA T1 Operations

**Date:** 2026-11-07  
**Status:** Accepted - ratified by Joe Ibrahim on 2026-11-08 for the narrow decision recorded under "Ratification and owner rulings (2026-11-08)". He ruled four G0 conflicts (R1-R4) on 2026-11-07. Decisions not ruled there stay open.  
**Authors:** Claude (integration author, this session). Proposed to Joe Ibrahim, product and ratification authority and the named G0 owner. Joe named himself G0 owner and ruled R1-R4 on 2026-11-07, and ratified this record on 2026-11-08.  
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

Bracketed citations such as `[01-trace §3]` name a G0 reconciliation report and its section. Those reports are local working papers, not committed. They are identified by file name and sha256 in the receipt's evidence table, and each one cites the repo `path:line` reproduced here. "Orchestrator record" means facts established by the workflow orchestrator outside the reports, including the owner's relayed instruction of 2026-11-07.

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

**Which job the backend serves.** In this repo's rulings, "vision" names the VLM route (R180-R182, `harness/notes/CTO_RULINGS_01.md:5464-5649`). R182 says the measured half, "by how much", still wants "OpenCV in the sidecar", and calls it "a different job" (`:5640-5645`). `harness/SYNAPSE_RETINA_VERIFY.md:89` says cv2 "earns its place on the delta MASK". So the CUDA backend proposed here is **measurement on arrays the worker has already ingested**. It is not semantic vision, not inference and not capture [03-governance §3.2].

### 2. What G0 found that changes the input blueprint's premise

The input blueprint calls RETINA an "existing out-of-process perception subsystem" (its Executive decision) and places a "T1 backend dispatcher" between OIIO ingest and an evidence sidecar (its §3). At `ef43d37a`, that pipeline does not run.

1. **T1 has no production caller.** VERIFIED. Outside `tests/` and `harness/`, the only importer of the `retina` package is `python/synapse/panel/render_receipt.py:42,50`, and it imports `retina.t0` only. `installer/build_payload.py:22-23` lists the files for packaging and calls nothing [01-trace §3; 02-ops F8; 05-claims §4.1].
2. **Nothing launches a worker.** VERIFIED. `retina/` has no entrypoint, no `__main__` and no subprocess launcher. The two files the graph assigns to the worker, `retina/worker_entrypoint.py` and `python/synapse/host/retina_worker.py`, do not exist [01-trace §3; 06-critic §1.8]. `retina/.venv` is absent from this worktree [01-trace §3].
3. **No production code writes a verdict sidecar.** VERIFIED. No production code calls `emit_verdict` (`retina/events.py:86-100`). Its only T0 wrapper, `verify_and_emit` (`retina/t0.py:409-419`), is called only by `tests/test_retina_t0.py:247`, and tests also call `emit_verdict` directly (`tests/test_retina_t0.py:233-234`; `tests/test_retina_t1_schema.py:129-130`); `retina/t1.py:52,90` re-exports it (VERIFIED: `grep -rn emit_verdict`). The panel path documents that it never writes (`python/synapse/panel/claude_worker.py:1100-1102`; `render_receipt.py:10-13`). No path convention, schema version or reader for a sidecar exists [01-trace §8-9; 05-claims 1.17].
4. **The tier that runs, T0, runs inside Houdini.** VERIFIED. `ClaudeWorker._emit_render_receipt` (`claude_worker.py:1093-1111`) calls `render_receipt.compute_receipt`, whose `_load_t0` inserts the repo root into `sys.path` inside Houdini's interpreter (`render_receipt.py:35-53`). T0 runs on the panel's worker thread. This contradicts `retina/__init__.py:9-15`, which describes the tree as running in its own venv outside every host surface [01-trace §3].
5. **The zero-cv2 host lint is lexical, not transitive.** VERIFIED. `tests/test_retina_boundary.py` scans host surfaces with a regex (`:38-57`) and keeps `retina/` out of scope on purpose (`:104-117`). If `retina/__init__.py`, `t0.py`, `events.py` or `exr_header.py` ever reached a backend module, CUDA libraries would load into Houdini and the test would stay green. That consequence is INFERENCE [01-trace §11; 05-claims 1.16].
6. **No test pins zero `hou` in the worker.** VERIFIED. `retina/` imports no `hou` today, but nothing fails if one is added [01-trace §11; 05-claims 1.15].
7. **The host installer ships T1.** VERIFIED: `installer/build_payload.py:22-23` lists `retina/t1.py` and `retina/ingest.py` in the host payload. A backend module appended to that list would ship with the host while the lint stays green. That is INFERENCE [06-critic §4.5].
8. **The scoped-delta check's target input has no supported source on Karma 22.0.368 (R100), and the check has a positive-change gap.** R100 ruled the target-source route unavailable on that build (`CTO_RULINGS_01.md:2799-2817`). R182 replaced object identity with the vision route and kept "by how much" in OpenCV (`:5580-5649`). Separately, stated abstractly: the scoped-delta check confirms that change stayed inside the claimed target and that the outside held still, but **no check requires that anything changed inside the target**. An unchanged before/after pair, or a target absent from the frame, rolls up to `pass`. Static reading: VERIFIED (`retina/t1.py:480-541`). Executed on CPU with cv2 4.12.0: report 05 reproduced both cases as `pass`. That run is artifact-read here, not re-executed [02-ops §4, F5; 05-claims §6; 06-critic §1.14].

**What this means for where a backend can go.** INFERENCE (design), grounded in the VERIFIED facts above [01-trace §12; 06-critic §5.2]:

- There is **no hot path** to insert a dispatcher into. The input blueprint's instruction to choose a chain "after profiling actual call sites" (its §4) cannot be followed, because there are no production call sites [02-ops B2].
- The narrowest existing seam is **beneath the four cv2-using primitives** in `retina/t1.py`: `ssim` (`:218`), `change_mask` (`:253`), and the two scoped-delta primitives (`:277`, `:321`). Their callers (`:433`, `:480`) stay the call boundary. `events.py`, `build_t1_event` (`:416`) and the tri-state roll-up stay untouched. The backend is chosen by explicit argument or policy, never by an import-time global. Under R2 only `change_mask` is in the first chain.
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
- **Round two:** R6 says "The GPU lane closes B1, not the build", and B2, the worker Python ABI, "is the owner's decision and stays open" (`RULING-2026-11-07-round2.md:49-53`). W7 says the GPU predicate "certifies the probe, not the build" and the node's gate is `joe` (`:105-112`). B2 is now ruled by R4 (orchestrator record).

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

**The settled sentence:** one trivial CUDA kernel, unrelated to OpenCV, compiled and ran on this machine according to a prior lane's committed receipt. No OpenCV source has been configured or built under either candidate recipe; pinned 5.1.0 source archives are staged, unbuilt, under the E: prep project (receipt §6). **No OpenCV CUDA operator has executed anywhere in this program.** The separate prep project under `E:/OpenCV5.1_Prep` ran a compile-only probe with `gpu_execution:false` (prep record, `E:/OpenCV5.1_Prep/01_Inspections/raw/preparation-20261106T194127Z/compile_conforming_result.json`) [04-prep §4].

---

## Owner rulings (2026-11-07)

**Source:** orchestrator record of the owner's relayed instruction, 2026-11-07. After reading the G0 reconcile, Joe wrote, verbatim:

> "Rule on the G0 conflicts: fold the OpenCV blueprint into the harness/next-release graph, no second board. Use the change-mask chain, build root E:\OpenCV5.1_Prep, worker CPython 3.12.10 with the isolated cp312 OIIO wheel. Record it in ADR-0002 and the G0 receipt on vision/opencv51-g0, don't push."

That rules exactly four G0 conflicts and nothing else.

| # | Conflict | Ruling | State | Supersedes |
|---|---|---|---|---|
| **R1** | Board | The OpenCV 5.1 blueprint folds into the `harness/next-release` graph. **There is no second board.** Its stages run as the existing NR nodes, plus only new nodes or node changes that Joe merges into `graph.json` | **RULED 2026-11-07** | Former decision 1, option (b), a separate G0-G6 track |
| **R2** | First GPU chain | The change-mask body in `retina/t1.py` (`absdiff`, threshold, morphological open, close; `:266-273`), not the masked `meanStdDev` chain | **RULED 2026-11-07** | Former decision 2, option (b) |
| **R3** | Build root | `E:/OpenCV5.1_Prep`, the prep project, not `C:/ocv` | **RULED 2026-11-07** | `C:/ocv`, the NR lane's planned root (`gpu_feasibility.json:259`) |
| **R4** | Worker runtime | CPython 3.12.10 with the isolated cp312 OpenImageIO wheel, not a hython-seeded venv and not the cp314 wheel | **RULED 2026-11-07** | Former decisions 3 and 4: a provisioned CPython 3.13, a hython-seeded venv, the cp314 OIIO wheel |

**What the rulings are not.** They do not ratify the P6/T1 amendment, so this ADR stays PROPOSED. They authorize no act: no clone, configure, build, install, pip or venv creation, and no GPU work (AGENTS.md Law 7; input blueprint §2 invariant 8). They leave every other decision open ("Decisions still open" below). Joe named himself G0 owner; that approves nothing beyond these four rulings.

**R3 as worded.** Joe named the root `E:\OpenCV5.1_Prep`. The staged E: recipe's own build directory is `E:/OpenCV5.1_Prep/02_OpenCV_Setup/build/cuda133-sm89-py312` and its install prefix is `E:/OpenCV5.1_Prep/02_OpenCV_Setup/install/cuda133-sm89-py312` (`E:/OpenCV5.1_Prep/02_OpenCV_Setup/preparation/Current_Configure.json:9`, `:18`, `:117`; VERIFIED by reading that file). The prep project stays read-only until a per-act authorization; G0 executed nothing there.

### Consequences of R1-R4 (stated, not done)

1. **The module list covers the change-mask chain.** VERIFIED: `Current_Configure.json:26` sets `BUILD_LIST=core,flann,geometry,imgproc,imgcodecs,cudev,cudaarithm,cudaimgproc,cudafilters,cudawarping,python3`. It contains `cudaarithm` (`absdiff`, threshold) and `cudafilters` (morphology). `cudafilters` declares `opencv_imgproc` and `opencv_cudaarithm` as its dependencies (pinned contrib `modules/cudafilters/CMakeLists.txt:9`). That `cudaimgproc` and `cudawarping` are not needed by the chain is INFERENCE from those dependencies. `geometry` and `flann` are required dependencies per the prep's scope notes (`Current_Configure.json:137`). Whether configure actually generates `python3` plus these modules is UNKNOWN (B4, B5). By contrast the NR recipe's `BUILD_LIST=core,cudaarithm,python3` (`gpu_feasibility.json:300`) has no `cudafilters`, so its artifact would lack the morphology operators: INFERENCE from the module list; its `fallback_2` (`:304`) would build the default module set instead [06-critic §2.1].
2. **`NR-GPU-QUALIFICATION` and `NR-GPU-FEASIBILITY` need a graph or receipt change that Joe merges.** FEASIBILITY's committed receipt is written around root `C:/ocv` and a masked `meanStdDev` closure (`gpu_feasibility.json:259`, `:430`). QUALIFICATION's `why` names "the 11x11 census" and "equality at the FP32 threshold" (VERIFIED, `graph.json:95`), which are that chain's fixtures (`docs/intake/src/synapse_next_release_blueprint.md:213`, `:362`; the link is INFERENCE). No `graph.json` node text names `C:/ocv` or `meanStdDev` (VERIFIED: `grep -n -i -E "ocv|meanstddev" harness/next-release/graph.json` returns nothing). VERIFIED: QUALIFICATION's predicate is `test -f harness/next-release/gpu_qualification.json` (`graph.json:96`), which cannot fail on a missing build. FEASIBILITY's committed receipt proposes a real closure built on `cv2.cuda.meanStdDev(src, mask)` over the 11x11 fixture (`gpu_feasibility.json:430`), with root `C:/ocv` (`:259`) and the `/m:32` recipe (`:282-283`). Under R1 and R2 those texts must change, or the change-mask chain must be recorded as an additional chain beside them (decision 14). Either change is a graph edit or a receipt edit that Joe merges.
3. **The shipped RETINA venv recipe conflicts with R4.** VERIFIED: `retina/requirements.txt:36-37` says a hython-seeded venv inherits Houdini's OIIO, and `:38-40` names a cp314 OIIO wheel. `retina/setup_venv.py:10-16`, `:42-45` and `retina/setup_venv.ps1:7-10` document a hython seed as an option; the default seed is the invoking interpreter. These three files are in no node's `owner_files` (receipt §5), so they must be changed later by whichever node is given them (decision 12). The recipe also installs `opencv-python-headless` (`requirements.txt:28`), which must never share a venv with the custom `cv2` [04-prep F-a].
4. **The custom `cv2` binding is built for CPython 3.12.10 without the limited API.** VERIFIED: `Current_Configure.json:27`, `:30` and `:31` point `PYTHON3_EXECUTABLE`, `PYTHON3_PACKAGES_PATH` and the NumPy include path at the prep venv `env/py312-cuda133`, and the argument list (`:5-113`) sets no `PYTHON3_LIMITED_API` (VERIFIED by grep). That the binding is therefore cp312-only is INFERENCE from CMake semantics [04-prep §1]. It compiles against that venv's NumPy 2.4.4 headers (`:31`); OIIO 3.1.15.0 requires `numpy>=2,<3` [04-prep §1]. ABI consistency of the whole stack is INFERENCE until an import succeeds.
5. **No existing artifact is the qualification artifact.** The only thing `NR-GPU-FEASIBILITY` compiled is `vectorAdd.exe`, a non-OpenCV kernel, in a gitignored scratch directory inside its own worktree, not under `C:/ocv` (VERIFIED: `gpu_feasibility.json:137`, `:461-463`). Its planned `C:/ocv` build never ran, and R3 supersedes that root. The qualification artifact must come from a future build under `E:/OpenCV5.1_Prep`.
6. **The E: recipe, as staged, does not yet produce an isolated, importable worker artifact.** It has no install step (`Current_Configure.json:115-122`), and it would install `cv2` into the prep venv (`:30`). The required deltas are listed in receipt §13 ("Still needed") and need per-act approval.

---

## Ratification and owner rulings (2026-11-08)

**Source:** orchestrator record of the owner's answers in this session, 2026-11-08. The orchestrator asked three questions and Joe chose one option for each. The questions, his choices and the option text he chose, verbatim:

1. "OpenCV 5.1 CUDA is built and the first GPU run of the change-mask chain matched the CPU exactly. To land the CUDA backend inside retina/, ADR-0002 must move from PROPOSED to Accepted, and only you can ratify it. Do you ratify ADR-0002?" Joe chose "Ratify now (Recommended)": "I record your words and flip the Status to Accepted. The decision is narrow: an optional CUDA path for the change-mask chain, worker-only, off by default, CPU stays the reference. The qualification receipt still has to pass before anything ships."
2. "Your R1 ruling folds the OpenCV lane into harness/next-release/graph.json, but merging the nodes is your act. Should I merge the OpenCV-lane half of the proposed amendment (5 new nodes, 4 changes to existing nodes; the Grow lane stays out)?" Joe chose "Merge with defaults (Recommended)": "Merge the OpenCV lane with these defaults for its open choices: the change-mask chain is added beside the meanStdDev census (OD-22); predicates stay under harness/next-release/proposals/ (OD-03); NR-GPU-QUALIFICATION's gate becomes joe (OD-23); the canary node stays parked behind the worker."
3. "Qualification compares every GPU mask against a frozen CPU reference (decision OD-10, yours). Which CPU build should be the reference?" Joe chose "Stock 5.0.0.93 wheel (Recommended)": "opencv-python-headless 5.0.0.93 in its own small venv. It's an independent binary from PyPI, so the GPU result is checked against code we didn't build. Costs one more small install under E:."

Earlier the same day Joe set the goal, verbatim: "ultrathink scaffold running work with subagent teams that are focused on the /goal of getting Open CV 5.1 GPU version up and working on synapse locally and commit, git push, git release using CTO Best Practices." That is a goal-level go. The configure, build and install acts of 2026-11-08 ran under it; it rules no numbered decision.

| Item | Settled as | Basis |
|---|---|---|
| Ratification | This record is Accepted, for the narrow decision quoted in answer 1 | Answer 1 |
| Decision 14 (OD-22) | Option (ii): the change-mask chain is recorded beside the masked `meanStdDev` census, which stays a later NR closure item | Answer 2 |
| OD-03 | The node predicates stay under `harness/next-release/proposals/predicates/` | Answer 2 |
| OD-23 | `NR-GPU-QUALIFICATION`'s gate becomes `joe` | Answer 2 |
| Decisions 12 and 13 | Settled by merging the nodes as proposed: the new nodes own the guard tests, the worker-only CUDA module and the GPU worker recipe (decision 12, option a), and `NR-VG-GPU-BUILD-LOCK` owns the build (decision 13, option b) | Answer 2 |
| Decision 8 (OD-10) | `cpu_reference` is the stock `opencv-python-headless==5.0.0.93` wheel in its own venv | Answer 3 |
| Decisions 16 and 17 | Executed under the goal-level go, not ruled: an install step was added, the build ran at `--parallel 8`, and a fresh CPython 3.12.10 worker venv took the `cv2` install (option b); the prep venv was not written. The build-lock receipt records the details | Goal-level go |

Still open: decisions 6, 7, 9, 10, 11, 15 and 18, Windows 26H2 vendor support (the build ran on 26H2 under the go; support stays UNKNOWN), and what "demo v1" means.

**Decision 5, graph order (ruled later on 2026-11-08).** After the merge, JEV re-ranked the graph and fell back below its confidence gate (receipt `harness/harness2/runs/next-release/graph_decision.json`: Jev chose `NR-SPARSE-RENDER` at 0.43 against a 0.6 gate; `land_now` `NR-GPU-FEASIBILITY` and `NR-VG-RETINA-GUARDS`; the build lock, worker environment, CUDA backend and qualification parked). The orchestrator asked: "All five OpenCV nodes are built, reviewed and passing their closing tests on the integration branch. But JEV re-ranked the merged graph, couldn't decide (0.43, below its 0.6 confidence gate), and fell back to its default: land only NR-GPU-FEASIBILITY and the Guards now, and park the build lock, worker environment, CUDA backend and qualification. Shipping those four in this release needs your explicit exception to the park (ADR-0002 decision 5, option d). Which order do we follow?" Joe chose "Exception: ship all (Recommended)": "I record your exception word for word and release all five OpenCV nodes as v5.99.0; the canary stays parked. JEV's result was a low-confidence fallback, not a real ranking, and every node has passed its review and closing test." That is option (d), an explicit owner exception to the park, for this release only. It does not change JEV's receipt or the lane's rule that JEV orders the graph.

**Consequence 1 recorded:** the RETINA blueprint gains an amendment record at its end. Its text above that record is unchanged.

## Owner ruling (2026-11-10): decision 9

**Source:** Joe's words in session, 2026-11-10, verbatim: "Two OpenCV branches are unmerged. (Please merge these)." Then, after the merged tree passed the full stock suite: "Go on slice 1: fast-forward local master to 3c40d7aa the same way (ff-only on 0 failed), record my decision 9 ruling in ADR-0002, show me the result, and don't push."

| Item | Settled as | Basis |
|---|---|---|
| Decision 9 (OD-17), the other OpenCV branches | Merged. `pd/loop2-opencv-fire` (`5ebc436f`), which already contains `feat/opencv-render-qc`, was merged `--no-ff` onto master `202902ad` as `3c40d7aa`. It adds `retina/firefly_scan.py`, `python/synapse/cv/`, four test files and `docs/plans/OPENCV_RENDER_QC.md`, and changes no existing file. Of the listed options this is closest to "absorb": both branches enter master unchanged. That mapping is the orchestrator's reading, not Joe's words. | Joe's ruling, quoted above |

Evidence: the full stock suite on `3c40d7aa` gave 12,587 passed, 500 skipped, 11 xfailed, 0 failed. Against master `202902ad` (12,511 / 481 / 11 / 0), the differences are the four new test files, plus five skips caused by the tree's location on disk.

What this does not settle: nothing calls the detector and no tool is registered for it. `retina/firefly_scan.py` is not in the host payload. Its Rec.709 luminance is outside `NR-IMAGE-CONTRACT`'s owner files. Amendment item OD-17 in `harness/next-release/proposals/` still reads open until that file is updated. The Render QC Blueprint (10 Nov 2026, sha256 `0ffa19c2…f214`) is an input under reconcile, and nothing in it is ruled by this record.

---

## Decision

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
| OIIO EXR ingest; `$OCIO` read, never set; ID and data planes never colour-transformed. **EXR ingest is never replaced by `cv2.imread`**, whatever PNG fixtures show (input blueprint §2 invariant 4) | `retina/ingest.py:81-103`, `:121-154`, `:179-197` |
| The envelope `{ch, v, tier, claim, checks, verdict, proof, at}`; tri-state checks; roll-up fail > inconclusive > pass; caller-supplied time | `retina/events.py:43-60`, `:74-83`; `retina/__init__.py:30-31` |
| Sidecar JSONL as the persistence form; no USD writes | `retina/events.py:86-100` |
| Zero `cv2` in the host, made **transitive** rather than only lexical | `tests/test_retina_boundary.py:67-101` today |
| Zero `hou` in the worker, made **pinned** | none today (Context §2 item 6) |
| T0 before T1: the ladder routes cheap-first and never skips a tier downward | `docs/SYNAPSE_RETINA_BLUEPRINT.md:97` |
| No verdict gains mutation authority | input blueprint §2 invariant 7. The graph edge `NR-WRITE-RECEIPT -> NR-WORKER-SUPERVISED` ("vision proposals may only mutate through the authored-write receipt path", `graph.json:245`) is not exercised by this ADR: the backend emits measurements, never proposals |

No new envelope field is added before a consumer-compatibility test and a contract review. Backend detail goes in the evidence sidecar first (input blueprint §3).

### Backend interface (PROPOSED, not existing APIs)

The names `probe_capabilities`, `analyze`, `cancel` and `close` are **PROPOSED**. None exists under `retina/` (VERIFIED: grep at `ef43d37a`). `analyze` and `gpu_required` do appear elsewhere in the repo with unrelated meanings (`shared/conductor_advisor.py:107`; the cache-policy tests).

- `probe_capabilities()` reports artifact identity, `cv2.__file__`, the selected device, driver and runtime, the exact operators available, the full paths of the loaded CUDA and OpenCV modules, and the last probe result. It runs only when the mode is not `off`.
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

**Parity input boundary (R2 chain).** The change-mask parity contract starts at two float32 `(H, W)` planes, after luma. The parity corpus stores those planes, not EXRs pushed through `_luma` (`retina/t1.py:112-118`, `:263-264`). That keeps parity independent of how `NR-IMAGE-CONTRACT` later derives Y (its `why`, `graph.json:112`). INFERENCE (design). Sequencing the seam against the Y change is decision 15.

---

## Sites (proposed)

| # | Site | Owner today | State |
|---|---|---|---|
| 1 | Backend selection beneath the four cv2-using primitives in `retina/t1.py` (`:218`, `:253`, `:277`, `:321`), with exactly one backend, `cpu_reference`, byte-identical to today | `NR-IMAGE-CONTRACT` (`graph.json:101-115`) | Addressed to that node, not taken. The scope widening is decision 12 |
| 2 | A worker-only CUDA module, off the host payload list and unreachable from the in-host modules | **Unowned**; its graph home is decision 12 | After a qualified artifact exists |
| 3 | The offline shadow-parity harness: the R2 chain on `cpu_reference` and CUDA over an approved corpus | `NR-GPU-QUALIFICATION` (`harness/next-release/gpu/`), after the graph change in Consequence 2 | After a build exists |
| 4 | The worker entry and host launcher | `NR-WORKER-SUPERVISED` | Planned files absent |

## Refused Sites

1. **The Houdini host process.** No cv2, CUDA or backend module runs or is reachable there, including through the `retina.t0` path. No global `PATH` change, no CUDA or Qt DLL copied into Houdini, and no replacement of the host's NumPy or Python (input blueprint §2 invariant 3).
2. **T2 and all inference.** ONNX Runtime stays. OpenCV DNN, cuDNN and TensorRT stay out.
3. **SSIM.** It stays on the CPU reference in float64. The pinned contrib source has no float64 row in the CUDA separable filter (`cudafilters/src/filtering.cpp:398`, `:409`, asserted at `:452`) [02-ops F4; 04-prep §3]. A float32 port is a new numerical design that needs separate approval (input blueprint §6).
4. **The scoped-delta primitives.** Their target input has no supported source (R100). No GPU work goes into them [06-critic §2.6].
5. **Verdict authority, consent and scene writes.** None.
6. **The independent oracle.** A CPU-vs-CUDA OpenCV comparison never substitutes for the COP-vs-OpenCV cross-check (M4).
7. **Thresholds and profiles.** Values are never loosened to absorb backend error (input blueprint §4; `harness/next-release/README.md:97`).
8. **Capture, viewport, Qt viewers, shared memory, pixel sockets and HAPI.** Out of scope (input blueprint §3).
9. **The host installer payload list** (`installer/build_payload.py:22-23`).

## Invariants Inherited

- **Input blueprint §2 invariants 1-8, inherited in full.** Summarized: (1) protect demo v1: no production integration, live GUI action, capture, render change, or sustained GPU or build load without separately approved scope and a resource window; (2) the governing texts (`CLAUDE.md`, `AGENTS.md`, the RETINA blueprint, reconciliation records, truth catalogs) are preserved, amendments are recorded separately, and ratification is never self-set; (3) the host/worker boundary as in Refused Site 1, plus zero `hou` in the worker; (4) OIIO EXR ingest, protected OCIO, linear metric planes and raw ID treatment, never `cv2.imread` for EXR; (5) T0 before T1, tri-state checks and the roll-up order, with missing capability or skipped work never satisfying a check; (6) the inference contract unchanged; (7) no automatic scene edits and no mutation authority on a verdict; (8) installs, live GUI work, merges, pushes, tags, release edits and ratification each need a human approval for that act.
- AGENTS.md Laws 1-7, especially Law 1 (honest seam), Law 4 (unmeasured renders UNKNOWN) and Law 7 (per-act human gates).
- RETINA P4 and P5 (`docs/SYNAPSE_RETINA_BLUEPRINT.md:44-45`).
- The next-release stop rules (`harness/next-release/README.md:99-108`) and round-two R4: a node's closure predicate is behavioural and able to fail (`RULING-2026-11-07-round2.md:36-42`).
- Exclusive file ownership per node (CLAUDE.md Agent Roster).

---

## Reconciliation with the ruled program

**Ruled (R1): there is no parallel board.** The input blueprint's stages run as existing `harness/next-release` nodes, plus only new nodes or node changes Joe merges into `graph.json`. JEV and Joe keep the order (`RULING-2026-11-06.md:36-38`). R1 does not depend on this ADR being ratified.

| Input blueprint stage | NR node or nodes | `owner_files` collision |
|---|---|---|
| G0 reconcile | the 2026-11-06 intake plus this ADR and receipt | None. These two files are new and unowned |
| G1 qualify artifact | `NR-GPU-FEASIBILITY` (merged, `feasible-unproven`), then `NR-GPU-QUALIFICATION` | Both own `harness/next-release/gpu/`. **No node owns the E: build itself today:** FEASIBILITY is merged with real closure UNMET, and its predicate certifies the probe, not the build (W7). Reopening it or adding a build node is decision 13. FEASIBILITY's committed receipt names `C:/ocv` and the masked `meanStdDev` closure, and QUALIFICATION's `why` names that chain's fixtures (INFERENCE); no `graph.json` node text names `C:/ocv` (Consequences of R1-R4, item 2) |
| G2 add seam (GPU off) | `NR-IMAGE-CONTRACT` for the `retina/t1.py` seam; `NR-WORKER-SUPERVISED` for any launcher | Same `retina/` files. This would widen `NR-IMAGE-CONTRACT`'s declared scope (named RGB, derived Y, invalid-sample policy; title `graph.json:102`, why `:112`) to include a backend seam. That is decision 12, not a mapping |
| G3 shadow parity | `NR-GPU-QUALIFICATION` ("an independent CPU reference", `graph.json:87`) | Same intent, same files; chain per R2 |
| G4 Joe canary | **No node** | New node needed after demo v1 |
| G5 optional beta | `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE` | Both own `installer/build_payload.py`. That double ownership already exists in the graph [06-critic §4.4] |
| G6 consolidate | `NR-FOLLOW-ON` (parked) | Loose fit. `NR-FOLLOW-ON` owns all of `harness/next-release/` (VERIFIED: its `owner_files` in `graph.json`), which overlaps `harness/next-release/gpu/`, owned by FEASIBILITY and QUALIFICATION |

### Decisions 1-4: RULED

Decisions 1 (board), 2 (first chain and build root), 3 (worker interpreter, B2) and 4 (OIIO source) are ruled by R1-R4 above. The ruling supersedes the options the draft listed for these four; the draft's case for them is not kept. The parts of former decision 2 the ruling did not settle (recipe deltas and build parallelism) move to decision 16. The open part of former decision 4, V0-R3 "who creates the worker venv", moves to decision 17.

### Decisions still open

Each item lists the options and the evidence. None is settled here. Numbers 5-11 keep the draft's numbering.

5. **Graph order.**
   - (a) Leave JEV's park in place, where every GPU and RETINA node is parked.
   - (b) Re-run the JEV graph guard now that `NR-GPU-FEASIBILITY` has merged.
   - (c) Amend the graph to decouple a CPU-only worker and sidecar from `NR-GPU-QUALIFICATION`. Today `NR-WORKER-SUPERVISED` depends on both `NR-IMAGE-CONTRACT` and `NR-GPU-QUALIFICATION` (`graph.json:125-128`).
   - (d) An explicit owner exception to the park for G1.
   - Evidence: `graph_decision.json`; `RULING-2026-11-06.md:36-38` (a seat does not overrule JEV by preference) [06-critic §5.4].
6. **CPU-reference defects a parity test would inherit.**
   - **The missing shape guard.** V0 F2 recorded a crash on shape mismatch. Neither orchestrator guards shape before the cv2 calls (`retina/t1.py:238`, `:266`, `:352`); only the scoped-delta reduction does (`:304-308`). The input blueprint's corpus requires resolution changes with identical tri-state outcomes (its §6). Options: (a) fix forward so mismatched shapes yield inconclusive; (b) exclude the case from parity by decision. The static reading is VERIFIED. That it still crashes at runtime is INFERENCE, since it was not re-run [02-ops F12, B3; 01-trace §6].
   - **The scoped-delta positive-change semantic** (abstract form in Context §2 item 8). Options: (a) a semantic contract decision that adds a positive "the claimed change happened" requirement; (b) keep the current semantics and stop citing the check as proof that a change occurred. Either way it is **not** CUDA parity work (input blueprint §6) [05-claims §6; 06-critic §1b].
   - **Related:** V0 F9, frame-health false positives on scene-linear renders, holds statically (`retina/t1.py:143-188` against `retina/qc_profiles.toml:38-41`) [01-trace §6].
7. **SSIM stays on CPU in float64.** Confirm, or commission a float32 numerical design as separate work. Evidence is in Refused Sites item 3. Report 05 adds that SSIM inputs reach the float64 path already reduced to float32 luma, so float64 protects the variance subtraction, not input precision. That is INFERENCE for the design question [05-claims 3.2].
8. **The identity of `cpu_reference`.**
   - (a) The stock `opencv-python-headless==5.0.0.93` wheel in its own venv. Report 04 calls this the safest option.
   - (b) The custom 5.1 build's CPU path, compiled with `WITH_IPP=OFF` and `WITH_TBB=OFF` (`Current_Configure.json:65-70`).
   - Whether T1 metrics differ between the two is UNKNOWN. The cv2 4.12.0 found in the default interpreter's user site must not be the oracle [04-prep F-c; 05-claims §4.3].
9. **The other OpenCV branches.** The unmerged branches `feat/opencv-render-qc` and `pd/loop2-opencv-fire` add `retina/firefly_scan.py` and `python/synapse/cv/`. Options: supersede, absorb or coexist [03-governance §6.2]. **Ruled 2026-11-10: merged** (see "Owner ruling (2026-11-10): decision 9").
10. **The RETINA.M3 queue entry.** It is `ratified: true`, but its title describes the target-source route that R100 refuted (`harness/state/flywheel_queue.json:471-473`). Options: amend or leave it [03-governance §4].
11. **Named owners** for the input blueprint's §7 roles: integration, build and package, an independent correctness reviewer who is not the build author, and release and support. Joe assigns these; none is proposed here [06-critic §4.3].
12. **Graph home and owner for G0-proposed files (Joe alone).** No node owns the proposed guard tests (`tests/test_retina_worker_boundary.py`, `tests/test_retina_scoped_delta_gap.py`), a worker-only CUDA module, or the RETINA venv recipe files (`retina/setup_venv.py`, `retina/setup_venv.ps1`, `retina/requirements.txt`) (VERIFIED: `graph.json` owner_files).
    - (a) A new NR node owning the slice-1 test files, the worker-only CUDA module and the GPU worker venv recipe, with a behavioural predicate per round-two R4, ordered by JEV.
    - (b) Widen `NR-IMAGE-CONTRACT`'s title and `owner_files` (and, for the tests, `NR-WORKER-SUPERVISED`, which already owns `tests/test_retina_worker_contract.py`).
    - Sub-item: **the `NR-IMAGE-CONTRACT` scope widening** to include a backend seam (Reconciliation, G2 row).
    - Sub-item: **the `installer/build_payload.py` allowlist coupling.** A payload-exclusion test reads a file owned by `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE`, both gate `joe`; any intended payload change by them must update the allowlist in the same commit.
13. **The node that owns the build (Joe).** (a) Reopen `NR-GPU-FEASIBILITY` as a round-three build lock; or (b) add a build node owning the E: build receipt. Either way its predicate reads the receipt's verdict and closure, not only an exit code (W7, `RULING-2026-11-07-round2.md:105-112`), and can fail. Receipt §13 gives a candidate predicate.
14. **The change-mask chain against the NR closure (Joe).** R2 makes the change-mask chain the first GPU chain. (i) Amend `NR-GPU-FEASIBILITY`'s proposed closure (`gpu_feasibility.json:430`), `NR-GPU-QUALIFICATION`'s `why` (`graph.json:95`) and the intake's "useful chain" (`docs/intake/src/synapse_next_release_blueprint.md:211-213`) to the change-mask chain; or (ii) record change-mask as an additional chain and keep the masked `meanStdDev` census as a later NR closure item. Either way, name a closure predicate for the change-mask chain. Both are graph or receipt edits Joe merges.
15. **Seam sequencing against the Y change (Joe).** `NR-IMAGE-CONTRACT` must replace today's unweighted luma with Y from the declared transform (`graph.json:112`), while the proposed seam keeps `cpu_reference` byte-identical to today, and round-one rule 3 allows one atomic commit per node (`RULING-2026-11-06.md:39-41`). Options: the seam lands before the Y change, after it, or as a separate node. The parity input boundary above keeps the R2 parity contract independent of the choice: INFERENCE (design). Colour space (D2) is still open (`RULING-2026-11-06.md:26`).
16. **Recipe deltas, parallelism and the build window (Joe; per-act).** R3 names the root. That the staged E: recipe is the starting point is INFERENCE, and it is Joe's to confirm. Open: `--target install` or a `cmake --install` step; where `cv2` lands (decision 17); an optional `BUILD_LIST` trim; `--parallel 1` (`Current_Configure.json:115-127`) or more; and a resource window while demo v1 or OVOID runs. Receipt §12-§13 give a proposed time-box.
17. **The worker venv: location and creator (Joe; V0-R3).** (a) Declare the prep venv `env/py312-cuda133` the worker, so the build writes into it (`Current_Configure.json:30`); or (b) create a fresh 3.12.10 worker venv and re-point `PYTHON3_EXECUTABLE`, `PYTHON3_PACKAGES_PATH` and the NumPy include path (`:27`, `:30`, `:31`), which is a configure-argument change. The isolated cp312 OIIO wheel (R4) lands in the same venv. Installability next to a custom `cv2` is UNKNOWN [04-prep §1].
18. **CUDA DLL resolution (Joe; environment).** The installed `cv2` loader finds CUDA DLLs through the machine-global `CUDA_PATH` and prepends them to the worker's `PATH` (receipt §6). Options: (a) the worker launcher pins `CUDA_PATH` explicitly; (b) inherit the machine value and record it per job. `NR-WORKER-SUPERVISED` already requires binaries outside Houdini's DLL search path (`graph.json:129`).

Also still open and not numbered here: ratification of this ADR; Windows 26H2 experimental scope; per-act authorization of each clone, configure, build and install; what "demo v1" means. Receipt §13 lists them.

---

## Consequences

Ratified on 2026-11-08, so these now apply:

1. P6 and the T1 row gain an amendment record. The RETINA blueprint text stays verbatim.
2. CPU-only RETINA stays the default for every user. `off` loads nothing new.
3. Nothing changes at runtime until two things exist: a worker that invokes T1, and a qualified artifact. Until then the only consumer is an offline parity harness.
4. Two new guard tests become preconditions for any backend code under `retina/`: a transitive-reachability test for the in-host modules, and a zero-`hou`-in-worker test.
5. The worker gains a second dependency profile: a custom CUDA `cv2` built for CPython 3.12.10 (R4) that must never share a venv with the stock wheel. The RETINA venv recipe installs `opencv-python-headless` (`retina/requirements.txt:28`), so a GPU worker needs its own recipe. That is INFERENCE [04-prep F-a].
6. A downstream V2-verdict reader would render an unavailable GPU operation as `fail` (Decision, honest failure).
7. GPU coverage claims stay narrower than the pipeline: decode, luma, SSIM and the numpy reductions stay on CPU unless a later decision moves one.
8. Performance is UNKNOWN. At RETINA's small verification sizes (`docs/SYNAPSE_RETINA_BLUEPRINT.md:105`), the light R2 chain may lose to CPU once transfers are counted, and the input blueprint's 1.5x target may fail. Its own rule then applies: narrow the supported workload, never revert to CPU silently [02-ops §7].

The consequences of R1-R4 hold whether or not this ADR is ratified ("Owner rulings" above).

If declined: see Alternative A1.

## Alternatives considered

| # | Alternative | Assessment |
|---|---|---|
| A1 | **Stay CPU-only.** T1 remains "ms, CPU, headless" | The cheapest and safest choice, and it changes no allocation. Not preferred: the owner's 2026-11-06 direction sets the GPU vision goal and D1 fixes a `gpu_required` row (`RULING-2026-11-06.md:7-8`, `:18`). It stays the fallback if the open decisions stall, and it keeps every guard test in this ADR useful on its own |
| A2 | **Copernicus-only GPU.** Every GPU pixel measurement is authored as COP networks, as P6 says | Keeps the allocation intact. Not preferred as the **only** route, for three reasons. COP execution means Houdini's process and a licence seat (the HAPI analysis at `docs/reviews/retina-reconciliation-2026-07-16.md:71-79`). The COP QC net and the M4 oracle have never run, because cycles C.3, C.4 and C.10 are `candidate` [03-governance §4]. And the measurement must happen in the hou-free worker where the arrays already are (R182). This ADR keeps Copernicus's role rather than replacing it |
| A3 | **A separate vision board** | **Ruled out by R1** (2026-11-07) |
| A4 | **Port every T1 metric** | Not preferred. The input blueprint says not to (its §4). SSIM cannot run on CUDA in float64 at source level. The scoped-delta target input has no supported source. Most per-frame work is numpy, not cv2 [02-ops §2, §7] |
| A5 | **Put CUDA OpenCV in the host** | Refused. It violates P5 (`docs/SYNAPSE_RETINA_BLUEPRINT.md:45`) and input blueprint invariant 3 |

## Rollback

- **This file:** revert its commit. No runtime, test or governing surface depends on it.
- **After ratification, before any code:** record a superseding ADR that keeps the old text for citation and names its replacement, by analogy with the rulebook's `superseded` status (`rulebook/RULEBOOK.md:49`, which governs RB- rules, not ADRs) [03-governance §5.1]. ADR-0001 uses "Accepted" (`docs/decisions/ADR-0001-jev-in-harvest.md:4`); this repo has no precedent for "Proposed".
- **G1 environment, when authorized:** build only into fresh build, install and venv directories; never install into `env/py312-cuda133` unless Joe rules it is the worker (decision 17). Take a hash manifest of any venv before writing to it. Rollback is deleting the new directories and re-verifying the manifest. INFERENCE (proposed procedure).
- **After code lands:** set the mode to `off` or `cpu`. That is a policy change, never a disguised success. Keep evidence and logs, and never delete frames, baselines or scenes. On the D1 `gpu_required` row this leaves GPU vision visibly unavailable while SYNAPSE stays usable (input blueprint §7); it is not a rollback of that row. **Worker-package rollback is unavailable** until `NR-WORKER-SUPERVISED` and `NR-PACKAGE-PAIR` exist (receipt §2).

## What this ADR does not authorize

The 2026-11-08 configure, build, install and GPU runs were authorized by the owner's goal-level go ("Ratification and owner rulings (2026-11-08)"), not by this record. This record still authorizes no act by itself:

- No build, configure, clone or install of OpenCV, CUDA, OIIO or anything else, and no pip install or venv creation. R3 and R4 name the root and the runtime; they authorize no act.
- No GPU work of any kind: no probe, device query, kernel, benchmark or soak.
- No pairing of a worker artifact with SYNAPSE, and no installer or payload change.
- No scene writes, live Houdini GUI actions, renders, capture or production-scene contact.
- No release-surface edits: `VERSION`, release notes or tags.
- No merge, push or tag.
- No edit to `CLAUDE.md`, `AGENTS.md`, `docs/SYNAPSE_RETINA_BLUEPRINT.md`, the reconciliation record, the perception truth catalog, `harness/state/flywheel_queue.json`, `graph.json` or any `ratified` field.
- No graph re-order. JEV and Joe keep the order.

## Proposed flywheel cycle (not appended)

If ratified, one cycle would be **appended** after the existing entries as `status: candidate, ratified: false`, citing this ADR as evidence. Suggested id: `RETINA.T1-cuda-backend`. It must not be inserted between M2 and M3, and it must not edit M3-M5 [03-governance §4]. This file appends nothing.

## Producer Paths

| Deliverable | File | Node | State at `ef43d37a` |
|---|---|---|---|
| This decision record | `docs/decisions/ADR-0002-retina-t1-optional-cuda-backend.md` | none (G0) | Accepted 2026-11-08; R1-R4 ruled 2026-11-07 |
| G0 receipt | `docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md` | none (G0) | Revised after review |
| Transitive host-boundary, zero-`hou` and payload-exclusion tests | new test file(s) under `tests/` | none yet (decision 12) | Not written |
| `cpu_reference` seam | `retina/t1.py` | `NR-IMAGE-CONTRACT` | Not written |
| Build lock and artifact receipt | `harness/next-release/gpu_feasibility.json` or a successor | `NR-GPU-FEASIBILITY` or a new build node (decision 13) | `feasible-unproven`; real closure UNMET |
| Parity receipt | `harness/next-release/gpu_qualification.json` | `NR-GPU-QUALIFICATION` | Absent |
| GPU worker venv recipe | not yet named | none yet (decision 12) | Absent |
| Worker entry and launcher | `retina/worker_entrypoint.py`, `python/synapse/host/retina_worker.py` | `NR-WORKER-SUPERVISED` | Absent |
| Sidecar publication | `retina/publication.py` | `NR-RECOVERY-RECEIPTS` | Absent |
| Worker artifact pair, notices | `installer/...` | `NR-PACKAGE-PAIR`, `NR-LICENSE-GATE` | Absent |

*A companion input, "SYNAPSE Neural Growth Creative Loop Blueprint" (7 November 2026, sha256 `070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647`), was **not** reconciled by this G0. Nothing here adopts or rejects it.*
