# OpenCV 5.1 CUDA Lane — G0 Receipt — 2026-11-07

**Status:** G0, revised after adversarial review, then corrected once more after re-verify on the owner's go (2026-11-08). Read-only reconciliation. **Not ratified.** It records four owner rulings and authorizes no act.

| Field | Value |
|---|---|
| **G0 owner** | Joe Ibrahim. He named himself G0 owner on 2026-11-07 and ruled four G0 conflicts (R1-R4); he ratified nothing and authorized nothing (orchestrator record). Joe remains product and ratification authority |
| **Owner ruling** | 2026-11-07: fold into the `harness/next-release` graph with no second board (R1); the change-mask chain first (R2); build root `E:/OpenCV5.1_Prep` (R3); worker CPython 3.12.10 with the isolated cp312 OIIO wheel (R4). Joe's words are quoted verbatim in §13 and in ADR-0002, "Owner rulings (2026-11-07)" |
| **Author** | Claude, integration author for this session. The independent reviewers are this workflow's attack agents |
| **Date** | 2026-11-07 |
| **Worktree branch and SHA** | `vision/opencv51-g0` at `ef43d37aaedb677bebc548a5fc921d4bea4565fd` (reports' baseline) |
| **Master head** | `origin/master` = `e3846b22d224fcbd2b2f3c4167e4d342bf96f62e` |
| **Release tag** | `v5.98.0` = `6a5f68ddbb66901685cbab2235e644198253e03d`, published (orchestrator record) |
| **Input blueprint** | "SYNAPSE: OpenCV 5.1 GPU Integration Blueprint", 7 November 2026, sha256 `bbaeed26669b945c2811399b9bbae0a1a183dbd18b6bb57d121f7391d271bf43`. Cited by section; not reproduced |
| **Companion proposal** | `docs/decisions/ADR-0002-retina-t1-optional-cuda-backend.md` (PROPOSED; R1-R4 ruled) |
| **Not reconciled here** | "SYNAPSE Neural Growth Creative Loop Blueprint", 7 November 2026, sha256 `070904d4e06b202dbeeb86bccfd6041ae99ee455e13a82bcd34ce49412dd9647` |

**Protocol:** the house style of `docs/reviews/retina-reconciliation-2026-07-16.md`. An external blueprint is reconciled against the repo **before** execution. Its claims are checked here, not trusted, and nothing in a governing document is edited.

**Labels:** **VERIFIED** (a `path:line`, git object, or command and output) · **INFERENCE** (reasoned, not observed; never promoted) · **UNKNOWN** (nobody measured it) · **REFUTED** (the code contradicts it).

**G0 observed no GPU execution and measured no performance.**

### Evidence sources

The six G0 reports are local working papers. They are not committed, and they are cited here by name and section, for example `[01-trace §3]`. Each one cites the repo `path:line` that is reproduced in this receipt.

| Report | Lens | sha256 |
|---|---|---|
| `01-trace.md` | The RETINA invocation path, end to end | `39d92e398cc08fd257bfc3088cce6ff277324285d57a7d4f924eb5dc494667d0` |
| `02-ops.md` | The operation inventory for a CUDA backend | `b5a6384b6d6f02a0849fe567f7cbf6d695b5af786fdf0d5caf6561dcd0f84d08` |
| `03-governance.md` | Governance, rulings, ownership | `03edf527db20268d76e816bdffd68e528d3be39639409d8b824ac18537775b17` |
| `04-prep.md` | `E:/OpenCV5.1_Prep` evidence and the runtime matrix | `2bdd72bdc931852a44cca44069958063f20b2fd2e0328d640194fd90659b9035` |
| `05-claims.md` | Blueprint claims and the measured test baseline | `d57c085b7308921fa9e0b50bd2a7835cf136c7727be6fb9c2cd40a8881969281` |
| `06-critic.md` | Completeness critic over 01-05 | `2439168f1a9bcb8092a645005639a89793c8e1a3e135cfc91156f693cfb071a2` |

"Orchestrator record" means facts the workflow orchestrator established outside the reports, including the owner's relayed instruction of 2026-11-07. Where this revision cites the pinned OpenCV sources or the prep configure file directly, the citation is a read made while authoring this revision (VERIFIED by read).

---

## 0 · Verdict

1. **The input blueprint describes a design, not the running system.** T1 has no production caller, nothing launches a worker, no production code writes a verdict sidecar, and the only tier that runs, T0, runs inside Houdini (§3).
2. **A ruled program for this goal already exists**, and the input blueprint does not cite it. It is the `harness/next-release` graph, with D6 and D1 closed. **Joe ruled on 2026-11-07 that the blueprint folds into that graph, with no second board (R1).**
3. **No OpenCV CUDA operator has executed anywhere in this program.** The only GPU execution on record is a trivial, non-OpenCV CUDA kernel in the `NR-GPU-FEASIBILITY` receipt. G0 did not re-observe it (§6, ADR-0002 Context §3).
4. **The P6/T1 amendment needs Joe's ratification before any GPU backend code lands under `retina/`.** That it does not gate an out-of-tree build is INFERENCE from input blueprint §5 and §9; Joe decides it (§13).
5. **G1 cannot start on day one as things stand.** No graph node owns the build; JEV's last decision parks every GPU node; `NR-GPU-FEASIBILITY`'s committed receipt is still written around root `C:/ocv` and a masked `meanStdDev` closure (`gpu_feasibility.json:259`, `:430`), and `NR-GPU-QUALIFICATION`'s `why` names that chain's fixtures, the 11x11 census and FP32-threshold equality (`graph.json:95`; the link is INFERENCE), while no `graph.json` node text names `C:/ocv`; and the staged E: recipe has no install step (§13 "Still needed"). INFERENCE from the VERIFIED facts cited there.

---

## 1 · Exact revision and dirty state

| Fact | Label | Evidence |
|---|---|---|
| Worktree HEAD `ef43d37a...`, clean when the reports ran | VERIFIED | `git rev-parse HEAD`; `git status --porcelain` empty [01-trace header; 05-claims §1; 06-critic header] |
| At commit time the only changes are this file and ADR-0002 | VERIFIED at commit | `git status --porcelain` before `git add` |
| `ef43d37a` = `v5.98.0` plus one docs-only commit; `origin/master` `e3846b22` = `ef43d37a` plus one docs-only commit; both touch only `docs/releases/v5.98.0.md` | VERIFIED | `git diff --stat ef43d37a e3846b22` → one file, 6 insertions, 3 deletions; [03-governance §1.2]; orchestrator record (both commits CI-green) |
| `retina/` and `tests/test_retina*` are byte-identical between `v5.98.0` and `ef43d37a` | VERIFIED | `git diff --stat v5.98.0 ef43d37a -- retina tests/test_retina*` → empty [02-ops F1; 05-claims §1] |
| **Trap:** the local ref `master` is `67282edc`, 10 commits behind `ef43d37a`, checked out in worktree `g32-merge`. G1 must key on `origin/master` or an explicit SHA | VERIFIED | `git rev-list --count` both ways [03-governance §1.4] |
| `NR-GPU-FEASIBILITY` (`d9a325bc`) is an ancestor of `ef43d37a` and of `v5.98.0` | VERIFIED | `git merge-base --is-ancestor` |
| The live checkout (Houdini's package source) is on `feat/worldlabs-audit` at `36148779` with uncommitted and untracked work. G0 did not touch it | VERIFIED (orchestrator record) | — |
| That checkout's committed head is 77 commits behind `ef43d37a` and 0 ahead. It differs in six RETINA-touching files (`retina/t0.py`, the two host hooks, `render_receipt.py`, `claude_worker.py`, `handlers_render.py`) | VERIFIED (committed side) | `git rev-list --left-right --count`; `git diff --stat` [06-critic §4.1] |
| So the seat runs pre-G32 RETINA, and live evidence gathered there today would exercise different code | INFERENCE | no `--contains` check; working tree fenced [06-critic §4.1] |
| No Houdini process ran when G0 started. Installed builds: 21.0.773 and 22.0.368, .397, .400, .417, .429, .466, .492 | VERIFIED (orchestrator record) | — |

---

## 2 · Active work ownership

### Branches and worktrees touching `retina/` or vision

| Branch | Head | State | Evidence |
|---|---|---|---|
| `vision/opencv51-g0` | `ef43d37a` plus G0 commits | This G0 | VERIFIED |
| `feat/opencv-render-qc` | `8490b80b` | Unmerged: 7 ahead, 236 behind. Adds `retina/firefly_scan.py`, the host package `python/synapse/cv/`, and `docs/plans/OPENCV_RENDER_QC.md`, which leaves "Where OpenCV runs" as Joe's call | VERIFIED [03-governance §6.2] |
| `pd/loop2-opencv-fire` | `5ebc436f` | Unmerged: extends the branch above, 9 ahead | VERIFIED [03-governance §6.2] |
| `origin/archive/retina-m2-orphan` | `f3be38c3` | Archived; V0 closed "archive branch rejected"; a tidy item still recommends keeping it | VERIFIED [03-governance §6.2] |
| `g32/render-proof` | `d6aafd7b` | Fully merged (0 ahead). G32 last edited `retina/t0.py` on 2026-11-06 | VERIFIED [03-governance §6.2] |
| `nr/gpu-feasibility` | `2714d534` | Merged as `d9a325bc`. Its worktree `nr-gpu-feas` is gone from `git worktree list` | VERIFIED [06-critic §3.15] |

Whether the two unmerged OpenCV branches are abandoned or waiting on Joe is UNKNOWN [03-governance §8]. Their disposition is still open (ADR-0002 decision 9).

### Graph nodes whose `owner_files` touch `retina/` or vision (`harness/next-release/graph.json`)

| Node | Gate | `owner_files` (abridged) | Depends on | Repo state · JEV decision |
|---|---|---|---|---|
| `NR-GPU-FEASIBILITY` | joe | `harness/next-release/gpu/`, `gpu_feasibility.json` (`:75-78`) | — | Repo: merged, `feasible-unproven` · JEV: parked |
| `NR-GPU-QUALIFICATION` | crux | `harness/next-release/gpu/`, `gpu_qualification.json` (`:88-91`) | FEASIBILITY | Repo: not built · JEV: parked |
| `NR-IMAGE-CONTRACT` | crux | `retina/events.py`, `retina/ingest.py`, `retina/t1.py`, `retina/qc_profiles.toml` (`:103-108`) | FEASIBILITY | Repo: not built · JEV: parked |
| `NR-WORKER-SUPERVISED` | crux | `retina/worker_entrypoint.py`, `python/synapse/host/retina_worker.py`, `tests/test_retina_worker_contract.py` (`:120-124`) | IMAGE-CONTRACT, QUALIFICATION | Repo: not built · JEV: parked |
| `NR-RECOVERY-RECEIPTS` | crux | `retina/publication.py`, `python/synapse/loop/coordinator.py`, `tests/test_retina_publication.py` | WORKER-SUPERVISED | Repo: not built · JEV: parked |
| `NR-PACKAGE-PAIR` | joe | `installer/build_payload.py`, `installer/worker_lock.json`, ... | RECOVERY-RECEIPTS | Repo: not built · JEV: parked |
| `NR-LICENSE-GATE` | joe | `installer/licenses/`, `installer/build_payload.py`, ... | — | Repo: not built · JEV: parked |

The JEV column is from `harness/harness2/runs/next-release/graph_decision.json`, generated 2026-11-07T01:58Z, before `NR-GPU-FEASIBILITY` merged. VERIFIED by JSON read. "Merged" is repo state, not a JEV state.

**Predicates that are still not behavioural.** `NR-IMAGE-CONTRACT` (`grep -q`, `graph.json:113`), `NR-GPU-QUALIFICATION` (`test -f`, `:96`), `NR-WORKER-SUPERVISED` (`test -f`, `:130`), `NR-RECOVERY-RECEIPTS` (`grep`, `:146`), `NR-PACKAGE-PAIR` (`test -f`, `:163`) and `NR-LICENSE-GATE` (`test -f`, `:177`) still carry predicates that a comment or an empty file could satisfy, despite round-two R4 (`RULING-2026-11-07-round2.md:36-42`). VERIFIED by reading `graph.json` at `ef43d37a` (the last three per the truth reviewer's grep).

**Flywheel queue** (`harness/state/flywheel_queue.json`): `RETINA.M3`, `M4` and `M5` are `candidate` and `ratified: true` (`:471`, `:482`, `:493`). `RETINA.M3-worker-hardening` is `candidate` and `ratified: false` (`:572`). The M3 title still describes the target-source route that R100 refuted [03-governance §4].

**Active-run sweep (AGENTS.md Law 6):** G0 enumerated worktrees and graph state only. No PID or `bus/` sweep was made [06-critic §4.2]. **Bus posting (AGENTS.md Law 5):** this receipt is not posted to a board `bus/`; G0 is not a graph node and R1 rules out a second board. Whether G1 posts there is for the owning node (ADR-0002 decision 13).

---

## 3 · The RETINA invocation path as it runs today

All steps VERIFIED unless tagged [01-trace §1-§9].

1. The `render` command registers to a bounded wrapper (`python/synapse/server/handlers.py:777-778`), which delegates to `_handle_render` (`handlers_render.py:393`, `:611`, `:657`).
2. Inside `_render_on_main`, just before `node.render()`, the host hooks install a manifest and the `.done` sentinel (`handlers_render.py:936-960`). **This is the only call site** of `install_retina_hooks`. The farm, `_handle_render_sequence`, TOPs and the husk-offload paths write no manifest.
3. No caller supplies `payload["retina"]`, so every manifest carries an empty AOV list, an empty target list and no camera matrix, and flags each one honestly (`retina_manifest.py:442-465`). That this holds for every live render is INFERENCE.
4. The manifest gets a per-render nonce (`retina_manifest.py:477`) and is written atomically beside the product. The sentinel is wired only if the manifest landed (`:511-535`), through the husk-level `husk_postframe` (`:368`).
5. After the render, the result gains a `retina` key (`handlers_render.py:1236-1240`).
6. **In the panel only**, `ClaudeWorker._emit_render_receipt` (`claude_worker.py:1093-1111`) calls `render_receipt.compute_receipt`. That loads `retina.t0` **inside Houdini** by inserting the repo root into `sys.path` (`render_receipt.py:35-53`), then runs `check_manifest_against_disk` on the panel's worker thread.
7. The event goes out on a Qt signal to the Review face, which keeps it **in memory** (`synapse_panel.py:2532-2544` → `face_review.py:465-489`). Nothing is written to disk.
8. External MCP clients get the raw `retina` dict and **no verdict**. No `retina` reference exists in `python/synapse/mcp/` or `mcp_server.py`.
9. **T1, OIIO ingest, the QC profiles and the sidecar writer have no production caller.** Nothing launches a worker. No image-baseline store exists, so SSIM and scoped-delta would be inconclusive on every production frame even if T1 were invoked. That consequence is INFERENCE [01-trace §6].

**Open on this path:**

- Whether `husk_postframe` fires on a GUI `usdrender_rop` render on 22.0.400 under this box's licence is **UNKNOWN**. The catalog evidence is provisional headless hython on 22.0.368. `handlers_render.py:396-400` says husk cannot load Karma on Indie, and `retina_manifest.py:310-316` contradicts itself on ROP-script timing [01-trace §2; 06-critic §2.10].
- Slow renders return `render_in_progress` with no `retina` block. That a later poll runs T0 is INFERENCE [01-trace §3].

---

## 4 · Contracts

| Contract | Definition | Pinned by | Label |
|---|---|---|---|
| Envelope | `{ch, v, tier, claim, checks, verdict, proof, at}`, with `ch="perception"`, `v=1` (`retina/events.py:74-83`; `retina/__init__.py:30-31`) | `tests/test_retina_t0.py`, `test_retina_t1.py`, `test_retina_t1_schema.py` | VERIFIED |
| Check record | `{name, pass ∈ {True, False, None}, detail, **extra}` (`events.py:43-49`) | same | VERIFIED |
| Roll-up | fail > inconclusive > pass (`events.py:52-60`). Time is caller-supplied (`:26-28`) | same | VERIFIED |
| Sidecar | `emit_verdict` appends sorted-key JSONL and never writes USD (`events.py:86-100`). **No path convention, no reader, no production caller.** Its only T0 wrapper, `verify_and_emit` (`t0.py:409-419`), is called only by `tests/test_retina_t0.py:247` | tests only: `tests/test_retina_t0.py:233-234`, `:247`; `tests/test_retina_t1_schema.py:129-130` (VERIFIED: `grep -rn emit_verdict`) | VERIFIED |
| Manifest | `retina_manifest/v1` (`retina_manifest.py:47`), nonce-tied to `.done`. T0 fails on a nonce mismatch and is inconclusive on a missing nonce (`t0.py:152-210`) | `tests/test_retina_manifest.py`, `test_retina_t0.py` | VERIFIED |
| Profiles | `retina_qc_profiles/v1` (`qc_profiles.toml:25`). It validates only `[default]` (`qc_profiles.py:30-62`) and records **no provenance** of the table that won (V0 F6). Its values are self-described "ILLUSTRATIVE ... NOT tuned production thresholds" (`qc_profiles.toml:14-18`). No production selector exists, and no code maps the manifest's `render_profile` onto `sample_tier` / `denoiser_policy` | tests only | VERIFIED [01-trace §10; 02-ops §5] |
| Host boundary: zero cv2 | Regex over `python/synapse`, `shared`, `houdini`, `mcp_server.py` (`tests/test_retina_boundary.py:38-57`, test at `:67-101`). **Lexical, not transitive**; `retina/` is out of scope by design (`:104-117`) | itself | VERIFIED; the transitive gap is INFERENCE |
| Worker boundary: zero hou | `retina/` imports no `hou` today. **No test pins it** | none | VERIFIED (absence) |
| Panel tri-state honesty | `None` renders as "no receipt yet" (`face_review.py:465-489`) | `tests/test_panel_render_receipt.py` | VERIFIED |
| V2 verdict (adjacent) | Two-state; `check_from_tristate` maps inconclusive to `fail` (`python/synapse/panel/verdict.py:84-92`); no production caller | — | VERIFIED [06-critic §4.6] |
| T1 unavailable | `T1Unavailable` is an exception (`t1.py:94-109`), not an event; no mapping exists | — | VERIFIED [05-claims 1.9] |

---

## 5 · Affected files and owners

| File | Graph owner | Role in this lane |
|---|---|---|
| `retina/t1.py`, `retina/events.py`, `retina/ingest.py`, `retina/qc_profiles.toml` | `NR-IMAGE-CONTRACT` | The backend seam and the envelope |
| `retina/worker_entrypoint.py`, `python/synapse/host/retina_worker.py`, `tests/test_retina_worker_contract.py` | `NR-WORKER-SUPERVISED` | Worker and launcher (absent) |
| `retina/publication.py` | `NR-RECOVERY-RECEIPTS` | Durable publication (absent) |
| `harness/next-release/gpu/`, `gpu_feasibility.json`, `gpu_qualification.json` | `NR-GPU-FEASIBILITY`, `NR-GPU-QUALIFICATION` (and `NR-FOLLOW-ON`, which owns all of `harness/next-release/`) | Build lock and parity |
| `installer/build_payload.py` | `NR-PACKAGE-PAIR` **and** `NR-LICENSE-GATE` (two owners on one file) | It ships `retina/t1.py` and `ingest.py` in the host payload (`:22-23`) |
| `retina/requirements.txt`, `retina/setup_venv.py`, `retina/setup_venv.ps1` | **unowned in the graph** | The venv recipe. **Conflicts with R4** (hython seed documented; cp314 OIIO wheel named) and must change later under whichever node is given it (ADR-0002 decision 12) |
| `tests/test_retina_boundary.py`, `python/synapse/panel/render_receipt.py`, any new backend module or guard test | **unowned in the graph** | Boundary pin, in-host T0 loader; graph home is ADR-0002 decision 12 |
| `retina/t0.py`, `retina/__init__.py`, `retina/exr_header.py` | unowned in the graph | Loaded inside Houdini. Must never reach a backend |

Source: [06-critic §4.4], checked against `graph.json`. Under the CLAUDE.md roster, `tests/` is INTEGRATOR territory; INTEGRATOR is a Claude persona, not a graph owner, so graph ownership of new test files is Joe's ruling (ADR-0002 decision 12).

---

## 6 · Runtime matrix

Cell labels: **V** = VERIFIED, **V(p)** = VERIFIED as a prep record quoted but not re-measured, **V(r)** = VERIFIED as receipt content not re-observed, **I** = INFERENCE, **U** = UNKNOWN, **RULED** = owner ruling 2026-11-07 (orchestrator record).

The E: column is the ruled build root (R3). R4 rules the interpreter and OIIO wheel, but whether the prep venv is the worker stays open (decision 17). The NR-lane column is kept as history; its root and chain are superseded.

| Dimension | Houdini host | RETINA worker | `E:/OpenCV5.1_Prep` (ruled root, R3) | NR lane (`gpu_feasibility.json`; root superseded) |
|---|---|---|---|---|
| Houdini build | Target 22.0.400: V (CLAUDE.md; D1). Running build: U. The prep snapshots observed 22.0.466 in use: V(p) [04-prep §4]. The perception catalog is stamped 22.0.368, provisional: V [03-governance §2.4] | n/a (hou-free) | n/a | n/a |
| Python | 3.13.10: V on 22.0.368 (`docs/reviews/retina-reconciliation-2026-07-16.md:14`); on 22.0.400: U | **RULED: CPython 3.12.10** (R4). No worker venv exists: V. The shipped recipe seeds from the invoking `python`, 3.14.2 at inspection: V(p); it conflicts with R4 | 3.12.10, an isolated venv `env/py312-cuda133`: V (`pyvenv.cfg`) [04-prep §1]. Whether this venv **is** the worker: open (decision 17) | B2 was open; now ruled 3.12.10 |
| NumPy | U | Unpinned; OIIO 3.1.15.0 needs `numpy>=2,<3`: V [04-prep §1] | 2.4.4 (wheel hash matches): V. The binding compiles against these headers (`Current_Configure.json:31`), so the worker's NumPy must be ABI-compatible: I | Not probed: V(r) |
| OpenCV | Zero cv2 by design: V (lexical) | Shipped recipe: `opencv-python-headless==5.0.0.93`, CPU abi3 (`retina/requirements.txt:28`): V. Never in the same venv as the custom `cv2` [04-prep F-a]. The machine's default CPython 3.14.2 resolves **cv2 4.12.0** from the user site: V [05-claims §4.3] | 5.1.0 source archives staged, **not built**; `build/` and `install/` empty: V [04-prep §1] | No sources; `C:/ocv` absent: V(r) (`:136-139`) |
| OpenCV commits | n/a | n/a | core `e4f78fbc...`, contrib `b67a8551...` from archive bytes: V | Same SHAs via `git ls-remote`: V(r) (`:236-253`) |
| BUILD_LIST | n/a | n/a | core, flann, geometry, imgproc, imgcodecs, cudev, cudaarithm, cudaimgproc, **cudafilters**, cudawarping, python3 (`Current_Configure.json:26`): V. **Covers the R2 chain** (`cudaarithm` + `cudafilters`; `cudafilters` depends on imgproc and cudaarithm, contrib `modules/cudafilters/CMakeLists.txt:9`): V. `cudaimgproc` and `cudawarping` unneeded by R2: I | core, cudaarithm, python3 (`:300`): V(r). **No cudafilters**, so no morphology: I. `fallback_2` builds the default set (`:304`): V(r) |
| Build root and parallelism | n/a | n/a | **RULED root** (R3). Recipe dirs `02_OpenCV_Setup/build/cuda133-sm89-py312`, `install/cuda133-sm89-py312` (`:9`, `:18`, `:117`): V. `--parallel 1`, threads pinned to 1 (`:115-127`): V. Parallelism: open (decision 16) | `C:/ocv`, `/m:32` (`:259`, `:283`): V(r). Superseded by R3 |
| Install step | n/a | n/a | **None.** `later_build_arguments` has no `--target install` (`:115-122`): V. No `cmake --install` step elsewhere in the prep tree, sources excluded: V (feasibility reviewer's grep) | `--target install` (`:283`): V(r) |
| Where `cv2` lands | n/a | n/a | `PYTHON3_PACKAGES_PATH` = the prep venv's site-packages (`:30`): V. So an install writes into `env/py312-cuda133`: I. Location ruling: open (decision 17) | U |
| Python binding ABI | n/a | n/a | `PYTHON3_EXECUTABLE`, packages path and NumPy include point at the 3.12 venv (`:27`, `:30`, `:31`); no `PYTHON3_LIMITED_API` in the argument list (`:5-113`): V. So the binding is cp312-only: I [04-prep §1] | The venv must exist before configure: V(r) (`:272`) |
| DLL resolution | Must never load CUDA or OpenCV DLLs (Refused Site 1) | The installed loader's `config.py` adds `os.path.join(os.getenv('CUDA_PATH', <toolkit root>), 'bin/x64')` for CUDA ≥ 13 (pinned `modules/python/python_loader.cmake:70-78`): V. The build-tree `config.py` carries no CUDA path (`:48-58`): V. At import, `cv2/__init__.py:145-151` calls `os.add_dll_directory` **and prepends those paths to the worker's `PATH`**, which child processes inherit: V (source). `CUDA_PATH` is the machine value, currently the v13.3 toolkit, with v13.1 and v13.2 also installed: V (`env` at authoring). Runtime DLLs are named by major version only (`cudart64_13.dll`, `nppc64_13.dll`): V (`ls` of the v13.3 `bin/x64`). So a later 13.x installer moving `CUDA_PATH` would swap the runtime under a qualified artifact: I. Policy: open (decision 18) | same toolkit | 13.3 first on PATH: V(r) |
| OIIO | Not used | **RULED: the isolated cp312 wheel** (R4), `OpenImageIO==3.1.15.0`. The shipped recipe names a cp314 wheel (`requirements.txt:38-40`): V; superseded. **Never executed on this box (0 of 3 tests ran)**: V [05-claims §5] | Absent from the prep tree: V. A cp312 win_amd64 wheel exists on PyPI: V [04-prep §1]. Install and coexistence with a custom `cv2`: U | OIIO version for the delivered worker: U (`:423`) |
| CUDA toolkit | n/a | n/a | 13.3.1 (cudart 13.3.29); 13.1-13.3 installed: V(p) | 13.3, V13.3.73, first on PATH: V(r) |
| Host compiler | n/a | n/a | Toolset 14.44.35207 pinned (`:15`): V | cl 19.44.35222 accepted by nvcc (B1): V(r) |
| CMake | n/a | n/a | 4.2.1: V(p). In the pinned sources only `3rdparty/zlib-ng` declares a numeric minimum and `WITH_ZLIB_NG=OFF` (`:102`), so the B4 policy risk is lower than feared: I (feasibility reviewer's read). The E: recipe has no `CMAKE_POLICY_VERSION_MINIMUM` fallback | 4.2.1; whether it configures OpenCV is B4: U |
| GPU and driver | n/a | n/a | RTX 4090, 24,564 MiB, driver 621.14: V(p) | Same; driver reports CUDA UMD 13.5 (`:70-72`, `:149`): V(r). Newer than the 13.3 toolkit, so compatibility is favoured: I (`:401`). Vendor-table minimum (B10): U |
| Target arch | n/a | n/a | `89-real`, no PTX (`:21`): V | `CUDA_ARCH_BIN=8.9`, PTX empty: V(r) |
| Windows | 10.0.26300 (26H2) | same | Vendor support: U [04-prep §1] | same |
| GPU execution | none | none | Compile-only, `gpu_execution:false`: V(p) | **One trivial non-OpenCV kernel ran** (n=1024, 0 mismatches): V(r). **No OpenCV CUDA operator**: V(r) |
| Readiness | n/a | n/a | `prepared=true`, `ready_to_configure=false`, `ready_to_pair=false`, `build_window_confirmed=false`: V(p). Before execution it still requires a production-safe window, a 26H2 review, `Check_Readiness.py` from an isolated worker, and an offline hook review (`:128-133`): V | `real_closure_state: UNMET` (`:431`): V(r) |

---

## 7 · Operation inventory

**Every `cv2` call site in RETINA is in `retina/t1.py`. There are 13** (VERIFIED: `grep -n "cv2\.[A-Za-z]*(" retina/t1.py` → 13 lines). No other RETINA module calls cv2 [02-ops F2; 04-prep §3].

**Shapes.** Real product shape and channel count are **UNKNOWN**. The test fixtures are 64×64×3 float32 with a 64×64 float32 ID plane. RETINA's design names small verification renders, for example 960×540 (`docs/SYNAPSE_RETINA_BLUEPRINT.md:105`). Luma is `(H, W)` float32: the mean over **every** channel ingest returns, alpha included if present (`t1.py:112-118`) [02-ops §2, F14].

**Parameters.** No border mode, anchor or iteration count is passed to any cv2 call. Kernel sizes come from the profile or from code constants (`t1.py:223-224`). Profile values are not restated here; they live at `retina/qc_profiles.toml:27-52`.

**Every CUDA counterpart below is a source-level candidate. Verify each in the built artifact at G1.** None is "available". Rows 6-9 are the **R2 chain** (ruled 2026-11-07).

| # | `t1.py` line | Function | Call | Input dtype and shape | Candidate CUDA counterpart (verify in the built artifact at G1) | Source-level note |
|---|---|---|---|---|---|---|
| 1-5 | `:236`, `:237`, `:239`, `:240`, `:241` | `ssim` | `GaussianBlur` ×5 | **float64** C1 `(H, W)` | `cv2.cuda.createGaussianFilter` | **No CV_64F row** in the separable filter (`cudafilters/src/filtering.cpp:398`, `:409`, asserted at `:452`). Not runnable as written [02-ops F4] |
| 6 | `:266` | `change_mask` (R2) | `absdiff` | float32 C1 `(H, W)` luma | `cv2.cuda.absdiff` (cudaarithm) | Depth ≤ CV_64F allowed (`cudaarithm/src/cuda/absdiff_mat.cu:151`) |
| — | `:267` | `change_mask` (R2) | **numpy** strict `>`, then cast to uint8 | float32 in, uint8 {0,1} out | `cv2.cuda.threshold(THRESH_BINARY)` then `convertTo(CV_8U)`, or `cv2.cuda.compare` | **`cv2.threshold` is called 0 times**, although the docstring (`:41-43`) and `requirements.txt:24-25` name it: REFUTED doc claim [02-ops F9]. Strictness and float32 scalar precision must match (U4) |
| 7 | `:269` | `change_mask` (R2) | `getStructuringElement(MORPH_ELLIPSE)` | host kernel | Host-side; passed to `cv2.cuda.createMorphologyFilter` | — |
| 8 | `:272` | `change_mask` (R2) | `morphologyEx(MORPH_OPEN)` | uint8 {0,1} C1 `(H, W)` | `cv2.cuda.createMorphologyFilter(MORPH_OPEN, CV_8UC1, k)` (cudafilters) | 8UC1 allowed (`filtering.cpp:648`). **Border semantics differ:** CUDA pads `BORDER_DEFAULT` (`:695`), and the CPU call passes no border. Equivalence on symmetric kernels is INFERENCE (U5) [02-ops F11] |
| 9 | `:273` | `change_mask` (R2) | `morphologyEx(MORPH_CLOSE)` | uint8 C1 | same, `MORPH_CLOSE` | same |
| 10-13 | `:287`, `:290`, `:348`, `:351` | the scoped-delta primitives (`:277-351`) | structuring elements and morphology | uint8 C1 | not proposed | Internals described abstractly per the hygiene rule. **Not in the ruled first chain**; their target input has no supported source (R100) [06-critic §2.6]. Depth notes on request |

**Numpy work a CUDA chain could replace, though no cv2 call exists today** [02-ops §2]:

- The firefly census (`t1.py:199-207`), a mean, standard deviation and count. Its candidate is `cv2.cuda.meanStdDev` plus `compare` and `countNonZero`. This is the territory of the NR lane's masked-`meanStdDev` chain (`gpu_feasibility.json:56`), which R2 displaced as the first chain; whether it stays a later NR closure item is ADR-0002 decision 14. The Python overload is unverified (B6).
- The NaN/inf census and the black/blown and clip counts (`:126-188`). These are memory-bound reductions, and float32 reduction order would need a tolerance. The scoped-delta reductions (`:294-318`) are covered by row 10-13.

**Stays on CPU in any design:** OIIO decode (`ingest.py:146`), luma (`t1.py:112-118`), the SSIM arithmetic in float64, and `project_bbox` (`:369-414`).

---

## 8 · Blueprint-claim adjudication

| Input blueprint claim (section) | Label | Evidence |
|---|---|---|
| RETINA is an "existing out-of-process perception subsystem" (Executive decision) | **REFUTED** as running reality · VERIFIED as design | §3 above; `tests/test_retina_boundary.py:3-7` [01-trace §14; 05-claims 3.5] |
| v5.98.0 is the published release at `6a5f68dd` (§1) | **VERIFIED** (tag; orchestrator record). "Latest on GitHub" was not checked by G0 | `git rev-parse v5.98.0^{commit}` [05-claims 1.1-1.2] |
| Stock suite 12,366 passed, 474 skipped, 11 xfailed (§1) | **VERIFIED**, measured on `1edb9450`, which is code-identical to the tag | `docs/releases/v5.98.0.md:337-339`; `git diff --stat 1edb9450 6a5f68dd` → three docs files only: `README.md`, `docs/releases/v5.98.0.md`, `docs/status.md` [05-claims 1.3] |
| The Houdini seat suite is red on both compared trees (§1) | **VERIFIED** | `docs/releases/v5.98.0.md:352` [05-claims 1.4] |
| Clean-machine install, live render and cancellation probes, and GUI behaviour are unqualified (§1) | **VERIFIED** | `docs/releases/v5.98.0.md:249-250`, `:265-267` [05-claims 1.5] |
| The RETINA source has t0, t1, ingest, events, qc_profiles and host hooks (§1) | **VERIFIED** | `ls retina/`; `handlers_render.py:936-960` [05-claims 1.6; 06-critic §1] |
| T1 has CPU metrics and guarded cv2 (§1) | **VERIFIED** | `t1.py:54-68` |
| T1 has "honest unavailable outcomes" (§1) | **VERIFIED with nuance.** A missing cv2 **raises** `T1Unavailable`. A missing baseline or AOV yields `pass=None`. Nothing maps the exception to an event | `t1.py:94-109`, `:503-525` [05-claims 1.9] |
| The worker requirements file pins OpenCV headless 5.0.0.93 and OIIO 3.1.15.0, and forbids installing them in Houdini (§1) | **VERIFIED** | `retina/requirements.txt:5-6`, `:28`, `:40` |
| The 4.13 fallback is "not approval to downgrade" (§1) | **REFUTED (half).** The file calls it "the sanctioned substitute". It is right that it is no GPU alternative | `retina/requirements.txt:20-27` [05-claims 1.12] |
| Manifests and sentinels sit beside products (§1) | **VERIFIED** (code). Live firing on 22.0.400: **UNKNOWN** | §3 [01-trace §14] |
| OIIO owns EXR ingest (§1) | **VERIFIED** (code). **Executed 0 of 3** on this box | `retina/ingest.py:121-154` [05-claims 1.14] |
| The worker imports no `hou` (§1) | **VERIFIED, unpinned** | grep empty [05-claims 1.15] |
| The host imports no `cv2` (§1) | **VERIFIED** lexically. The transitive gap is INFERENCE | §4 [05-claims 1.16] |
| "Verdicts persist to sidecar JSONL" (§1) | **VERIFIED** as capability · **REFUTED** as running behaviour | §4 [05-claims 1.17] |
| The E: prep facts and toolchain (§1) | **VERIFIED** (prep record) | `E:/OpenCV5.1_Prep/02_OpenCV_Setup/Preparation_Status.md:3`, `:11-16`, `:22-33` [05-claims 1.18-1.19] |
| "No ... GPU execution" (§1) | **VERIFIED for E:.** The repo receipt a day later records one trivial non-OpenCV kernel run. That is receipt-read and does not contradict "no OpenCV GPU execution" | `gpu_feasibility.json:445-501` [05-claims 1.20; 06-critic §2.11] |
| The local revision was not established (§1) | **Superseded:** established in §1 | — |
| Envelope fields `ch, v, tier, claim, checks, verdict, proof, at` (§3) | **VERIFIED** | `events.py:74-83` |
| A worker directory does not prove a launched service (§3) | **VERIFIED:** nothing launches it | [01-trace §3] |
| The staged build: processing modules plus PNG; no DNN, GUI, video, EXR or tests; SM89 native (§4) | **VERIFIED** | `Current_Configure.json:21` (arch), `:26` (BUILD_LIST), `:38-39` (PNG), `:45-56` (no highgui, videoio, dnn, tests, apps), `:109` (no OpenEXR) [04-prep §2] |
| Pick the first chain "after profiling actual call sites" (§4) | **Cannot be followed:** there are no production call sites. **Superseded by R2** (owner ruling, change-mask chain) | [02-ops B2] |
| Do not inherit Houdini's site-packages for OIIO (§4) | **Contradicted by the repo's own recipe**, which documents a hython-seeded venv as an option. **R4 rules the isolated cp312 wheel** | `retina/setup_venv.py:10-16`, `:42-45`; `requirements.txt:36-37` [05-claims 3.7] |
| The G2 gate cites "zero-worker-hou checks" (§5) | **No such check exists** | [01-trace §11] |
| Current SSIM uses float64 CPU GaussianBlur (§6) | **VERIFIED.** The inputs are already float32 luma, so float64 protects the variance arithmetic | `t1.py:112-119`, `:231-241` [05-claims 3.2] |
| GPU depth support for SSIM (§6) | **UNKNOWN** in an artifact. At source level, no float64 row | [02-ops F4] |
| The scoped-delta path has no positive expected-change check (§6) | **VERIFIED** statically. Executed cases A and B (identical pair; target absent) roll up to `pass`; artifact-read. No test covers either | `t1.py:480-541`; `tests/test_retina_t1.py:186-221` [05-claims §6; 06-critic §1.14] |
| "An OIIO/GPU skip is not a pass" (§6) | **Applies:** the OIIO lane ran 0 of 3. That T1 and OIIO tests skip in CI is INFERENCE (config read, no CI log) | `.github/workflows/ci.yml:86` [01-trace §11] |
| The installer refuses while Houdini runs (§7) | **VERIFIED** (release verification record) | [05-claims 3.8] |
| Verify tag-to-worktree parity (S2) | **VERIFIED:** `retina/` is identical | §1 |

---

## 9 · RETINA test baseline

Measured by report 05 on `ef43d37a`. **This author did not re-execute it.**

| Passed | Failed | Skipped | Not run |
|---:|---:|---:|---:|
| **127** | **0** | **3** | **0** |

- **Command:** `python -B -m pytest tests/test_retina_boundary.py tests/test_retina_exr_header.py tests/test_retina_ingest.py tests/test_retina_manifest.py tests/test_retina_t0.py tests/test_retina_t1.py tests/test_retina_t1_schema.py tests/test_panel_render_receipt.py tests/test_render_proof.py -q -rs -p no:cacheprovider`, run from the worktree with `PYTHONPATH="<wt>/python;<wt>"`. It ran on the machine's default CPython 3.14.2, with `TEMP`, `TMP` and `SYNAPSE_LOG_DIR` redirected to scratch [05-claims §5].
- **Result:** "127 passed, 3 skipped, 2 warnings in 5.32s", exit 0. `--collect-only` gave 130. "Not run" = 130 − (127 + 0 + 3) = 0 [05-claims §5].
- **Re-run by the truth reviewer** with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` on the same interpreter: "127 passed, 3 skipped" (review record, G0 workflow 2).
- **Skip reasons:** 3 × "OpenImageIO + numpy not installed (RETINA worker venv only)", at `tests/test_retina_ingest.py:67`, `:86`, `:107`. **The OIIO EXR pixel-ingest lane ran 0 of its 3 tests. That is not a pass for that lane.**
- **Off-pin cv2 note:** the 22 T1 tests ran because `find_spec("cv2")` found **cv2 4.12.0** in the default interpreter's user site (`tests/test_retina_t1.py:22-28`). 4.12.0 is below both the pin (5.0.0.93) and the sanctioned floor (`>=4.13,<5`). **This green is evidence for cv2 4.12.0 on CPU only.** It says nothing about the pinned wheel or any CUDA build [05-claims §4.3].
- **Fence disclosure:** in report 05's run, pytest autoloaded third-party plugins that imported `torch`, which imported `pynvml`. Whether that import made any driver call is **UNKNOWN**. Future fenced runs set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` [05-claims §0].
- **Mutation evidence:** V0 recorded that the identical-input SSIM test passes with `GaussianBlur` stubbed to zeros, and that the scoped-delta exterior primitive can be replaced by an unconditional green (V0 F15). Not re-run; INFERENCE that it still holds [02-ops §3].

---

## 10 · Missing runtime evidence

Nobody has measured any of these. Each is UNKNOWN.

1. Any OpenCV CUDA operator, on any artifact. No artifact exists.
2. Whether CMake 4.2.1 configures OpenCV 5.1 under the E: recipe, and whether its `BUILD_LIST` generates `python3`, `cudaarithm` and `cudafilters` (B4, B5).
3. Python exposure and signatures of `cv2.cuda.absdiff`, `threshold`, `compare` and `createMorphologyFilter` (the R2 chain), and of `createGaussianFilter`, `countNonZero` and `meanStdDev`, in the built artifact (U3, B6).
4. Byte-identical CUDA morphology at frame edges and corners (U5), and `threshold` scalar precision against numpy's float32 strict `>` (U4).
5. Real product shape, channel count and alpha-in-luma. CPU time per operation and transfer cost at real sizes. Build duration and artifact size (U1, U2, B9).
6. Whether `husk_postframe` fires on a 22.0.400 GUI render, and whether a `.done` has ever been produced outside tests.
7. The cp312 OIIO wheel's installability and DLL coexistence with a custom `cv2` in one 3.12.10 venv; the worker's NumPy against the 2.4.4 build headers.
8. The vendor-table minimum driver for the CUDA 13.3 runtime (B10). Driver 621.14 reports UMD 13.5, which favours compatibility (INFERENCE, `gpu_feasibility.json:401`); it can be resolved offline from vendor documentation.
9. Windows 26H2 vendor support.
10. Whether V0 F2 (the shape-mismatch crash) and F9 (frame-health false positives on scene-linear) still bite at runtime on `ef43d37a`.
11. Where a T1 "before" frame would come from. No baseline store exists.
12. Whether T1 metrics differ between the stock 5.0.0.93 wheel and a custom 5.1 build's CPU path (the `cpu_reference` identity).
13. That the T1 and OIIO tests skip in CI (config read only).
14. Which Houdini build Joe runs today, and what "demo v1" denotes and whether it is complete.
15. The live checkout's working-tree state (fenced; see Hygiene).

Sources: [01-trace §15; 02-ops §9; 04-prep §9; 05-claims §7; 06-critic §3].

---

## 11 · Proposed first patch: scope, tests, rollback

**The smallest repo slice is tests only, with zero product code.** It is proposed, **not taken**, and **not dispatchable today:** under R1 it needs a graph home that Joe merges (ADR-0002 decision 12), and JEV orders it. It is not the next increment ahead of JEV.

### Slice 1: guard tests (a proposed node or `owner_files` amendment)

Proposed file `tests/test_retina_worker_boundary.py`, owned by whichever node decision 12 names (for example a new NR node, or `NR-WORKER-SUPERVISED`, which already owns `tests/test_retina_worker_contract.py`).

| Test | Asserts | How it fails (named mutation) |
|---|---|---|
| `test_in_host_retina_modules_cannot_reach_a_backend` | The static import closure of `retina/__init__.py`, `t0.py`, `events.py` and `exr_header.py` stays inside that set and the standard library, resolved by AST with nothing imported or executed. It also fails on any `importlib.import_module(...)` or `__import__(...)` call in those four modules | Add `from . import t1` to `retina/t0.py` → red. Add `importlib.import_module("retina.t1")` to `retina/t0.py` → red |
| `test_retina_worker_tree_imports_no_hou` | No module under `retina/` imports `hou` at any indentation, conditional imports included | Add `import hou` inside a function in `retina/t1.py` → red |
| `test_host_payload_ships_no_new_retina_module` | The `retina/` entries in `installer/build_payload.py` (parsed by AST, never imported) equal today's exact set of eight (`:22-23`) | Append `"retina/backend_cuda.py"` to `RUNTIME_FILES` → red |

The third test reads a file that `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE` own, both gate `joe`. Any intended payload change by those nodes must update the allowlist in the same commit. That coupling is a sub-item of ADR-0002 decision 12, for Joe.

**Optional fourth test**, in a separate file `tests/test_retina_scoped_delta_gap.py`: the two scoped-delta cases (identical pair; target absent) assert `verdict != "pass"`, marked `xfail(strict=True)` with the reason "positive-change contract undecided". It records the gap without pinning the defect as correct. When the contract changes, a strict XPASS forces the marker out. It needs cv2 and numpy, so it **skips in CI**, which is INFERENCE from the config. Whether to land it before Joe's semantic decision is his call (ADR-0002 decision 6).

- **Acceptance:** the boundary tests are hermetic and run in CI with no cv2, numpy or OIIO. For the existing RETINA files, acceptance is per-file collected and ran counts unchanged from §9, with the `cv2` provenance (`cv2.__version__`, `cv2.__file__`) recorded, not a single 127 total: the 22 T1 tests run only because an off-pin cv2 sits in the user site, and removing it would skip them for reasons unrelated to the patch.
- **Rollback:** revert the single commit. No runtime surface depends on it.

### Slice 2: the `cpu_reference` seam

**Addressed to `NR-IMAGE-CONTRACT`, which owns `retina/t1.py`. Not taken.** Widening that node's scope is ADR-0002 decision 12; sequencing against its Y change is decision 15.

- An explicit backend argument beneath `change_mask` (the R2 chain) and, if later decided, the other cv2-using primitives. Its default is `cpu_reference`, byte-identical to today, with no `cv2.cuda` symbol referenced and no import-time global.
- A mapping from `T1Unavailable` to an inconclusive check with a reason.
- **Parity input boundary:** the change-mask parity contract starts at two float32 `(H, W)` planes, and the corpus stores those planes, not EXRs pushed through `_luma`, so a later Y change does not alter the parity contract's meaning (INFERENCE, design).
- **Parity fixtures carried from report 02** [02-ops §7]: changes touching frame edges and corners; |diff| exactly at, and one float32 ulp either side of, `diff_threshold`; non-contiguous and odd-stride arrays; sizes that are not multiples of 16 or 32; an empty change set. Parity criterion: identical mask bytes.
- **Tests:** `tests/test_retina_t1.py` unchanged and green. A new test showing that a `gpu_required` request with no CUDA backend yields `pass=None` with a reason, never `pass`.
- **Rollback:** revert. **Precondition:** slice 1 merged, and ADR-0002 ratified.

### Toward G1: the smallest failable step

A **configure-only window** under the E: recipe is the smallest step that can fail on the G1 question: bounded, with an observable exit, it answers B4 and B5 and shows whether `python3`, `cudaarithm` and `cudafilters` generate. It needs per-act approval and an owning node (decisions 13, 16). Proposed, not taken; nothing in G0 configured anything.

**Out of scope for both slices:** a launcher, a sidecar writer, any GPU module, and any change to `events.py` (graph owners: `NR-WORKER-SUPERVISED`, `NR-RECOVERY-RECEIPTS`, `NR-IMAGE-CONTRACT`).

---

## 12 · Scope bounds

**No number here is a measurement, and no gate goes green on any of it (AGENTS.md Law 4).**

- **Slice 1:** one commit, one new test file with three test functions, plus an optional second file with one strict-xfail test. No product file touched.
- **Slice 2:** one commit inside `NR-IMAGE-CONTRACT`, touching `retina/t1.py` and one test file. Under R2 the seam covers `change_mask` first.
- **The input blueprint's own staffing figures** (its §5): G1 3-5 days plus bounded build time, G2 3-5 days, G3 5-7 days. These are its estimates, not measurements, and G0 does not adopt them.
- **Build duration and artifact size:** UNKNOWN (B9). The staged E: recipe (under the R3 root) runs at `--parallel 1` with thread counts pinned to 1 (`Current_Configure.json:115-127`), so the duration could be long; no conversion from core count is made. Parallelism is open (decision 16).
- **Every GPU speed, latency, VRAM or transfer figure:** UNKNOWN.

**Proposed time-box protocol for G1 (limits are Joe's to set).** INFERENCE (proposed procedure).

1. **Window 0, configure only:** bounded by a wall-clock limit Joe sets; exit is a configure log and the generated module list. Abort on any download attempt the hook rejects, or on a module missing from the generated list.
2. **Build windows:** `cmake --build` is incremental, so the build runs in resumable windows, each with a limit Joe sets and abort criteria: Houdini or a render starting, GPU memory or CPU load above a limit Joe sets, or the window expiring. Each window ends with a short receipt.
3. **No build window can be approved until "demo v1" is defined** (§10 item 14) and the build node exists (decision 13).

---

## 13 · Approvals for G1

G1 means building and qualifying the 5.1 CUDA artifact under the E: root, through a graph node Joe merges. Every item is Joe's unless marked environment. A relayed owner instruction to this workflow counts as his word for R1-R4 only; it is never banked for any per-act gate.

### Ruled 2026-11-07

Source: orchestrator record of the owner's relayed instruction, 2026-11-07. Joe's words, verbatim (the same text ADR-0002 quotes under "Owner rulings (2026-11-07)"):

> "Rule on the G0 conflicts: fold the OpenCV blueprint into the harness/next-release graph, no second board. Use the change-mask chain, build root E:\OpenCV5.1_Prep, worker CPython 3.12.10 with the isolated cp312 OIIO wheel. Record it in ADR-0002 and the G0 receipt on vision/opencv51-g0, don't push."

- **R1 · Board:** the OpenCV 5.1 blueprint folds into the `harness/next-release` graph. No second board. Its stages run as the existing NR nodes, plus only new nodes or node changes Joe merges into `graph.json`.
- **R2 · First GPU chain:** the change-mask body in `retina/t1.py` (`absdiff`, threshold, morphological open, close), not the masked `meanStdDev` chain.
- **R3 · Build root:** `E:/OpenCV5.1_Prep`, not `C:/ocv`.
- **R4 · Worker runtime:** CPython 3.12.10 with the isolated cp312 OpenImageIO wheel, not a hython-seeded venv and not the cp314 wheel.

None of these ratifies ADR-0002 or authorizes an act.

### Ruled 2026-11-08

Joe ratified ADR-0002, chose to merge the OpenCV lane of the graph amendment with its stated defaults (OD-22, OD-03, OD-23), and chose the stock `opencv-python-headless==5.0.0.93` wheel in its own venv as `cpu_reference` (OD-10). He also gave a goal-level go for the 2026-11-08 configure, build and install. His words and the items they settle are quoted in ADR-0002, "Ratification and owner rulings (2026-11-08)". Items 1-22 below are left as written at G0; that section says which are now settled.

### Still needed

**Graph and ownership**

1. **Graph order (Joe or JEV):** re-run the JEV graph guard after the `NR-GPU-FEASIBILITY` merge, or Joe rules an explicit exception to the park for G1, or the graph is amended (ADR-0002 decision 5).
2. **Build node (Joe):** reopen `NR-GPU-FEASIBILITY` as a round-three build lock, or add a build node owning the E: build receipt (decision 13). Its predicate must read verdict and closure, not only an exit code (W7), and be able to fail. Candidate predicate: the worker venv's `python` imports `cv2`; `cv2.__file__` resolves inside that venv; `cv2.cuda.getCudaEnabledDeviceCount() == 1`; `cv2.cuda.absdiff`, `cv2.cuda.threshold` and `cv2.cuda.createMorphologyFilter` exist; and the R2 chain matches `cpu_reference` byte-for-byte on the §11 fixtures. INFERENCE (proposed).
3. **Closure for the R2 chain (Joe):** amend the FEASIBILITY/QUALIFICATION closure and the intake's "useful chain" to the change-mask chain, or record it as an additional chain beside the meanStdDev census (decision 14). Graph or receipt edits Joe merges.
4. **Graph home for G0-proposed files (Joe):** the guard tests, a worker-only CUDA module and the GPU worker venv recipe, including the `NR-IMAGE-CONTRACT` scope widening and the `build_payload.py` allowlist coupling (decision 12).
5. **Seam sequencing against the Y change (Joe):** decision 15.

**The build under the E: root**

6. **Recipe deltas (Joe; per-act):** (a) add `--target install` or a `cmake --install` step, since the E: recipe has none (`Current_Configure.json:115-122`); (b) where `cv2` and the OIIO wheel land (item 7); (c) optionally trim `BUILD_LIST` to what R2 and its declared dependencies need, keeping `geometry` and `flann` (`:137`); the build-time saving is INFERENCE; (d) optionally a `CMAKE_POLICY_VERSION_MINIMUM` fallback, as the NR recipe has (decision 16).
7. **Worker venv location and creator (Joe; V0-R3):** declare the prep venv the worker, or create a fresh 3.12.10 worker venv and re-point `PYTHON3_EXECUTABLE`, `PYTHON3_PACKAGES_PATH` and the NumPy include path (`:27`, `:30`, `:31`) (decision 17).
8. **CUDA DLL resolution (Joe; environment):** the worker launcher pins `CUDA_PATH` explicitly instead of inheriting the machine value, or the value is recorded per job. The G1 build lock records `BINARIES_PATHS` from the installed `cv2/config*.py` and the full paths of the loaded CUDA and OpenCV modules as part of the backend witness. The in-process `PATH` prepend is added to `NR-WORKER-SUPERVISED`'s constraints (decision 18).
9. **Parallelism and a build window with resource limits:** `build_window_confirmed=false`. Demo v1 and OVOID protection come first; the §12 time-box applies; `--parallel 1` or more (decision 16).
10. **What "demo v1" means**, and whether it is complete. No build window before this.
11. **Windows 26H2:** approve or decline an explicit experimental scope. Vendor support is UNKNOWN.
12. **Per-act authorization** for each clone, configure, build and install (AGENTS.md Law 7, `:67-79`; input blueprint §2 invariant 8). The `AGENTS.md:77` row names specific substrates; extending it to an OpenCV build is INFERENCE, and invariant 8 covers installs directly.
13. **G1 environment rollback (Joe):** build only into fresh build, install and venv directories; hash-manifest any venv before writing; rollback is deleting the new directories and re-verifying the manifest. Worker-package rollback is unavailable until `NR-WORKER-SUPERVISED` and `NR-PACKAGE-PAIR` exist. INFERENCE (proposed procedure).
14. **Environment:** run the prep's own `Check_Readiness.py` from the isolated worker, and the offline hook review (`Current_Configure.json:131-132`).
15. **Environment:** confirm offline, from vendor documentation, that driver 621.14 meets the CUDA 13.3 runtime minimum (B10). No probe.
16. **Environment:** record the toolchain decision actually in use (prep D04 and D05 are still "Open"), and the hash of the base CPython 3.12.10 interpreter [04-prep F-f; 06-critic §2.13].
17. **Environment, isolation hygiene:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for fenced runs; the custom `cv2` never in a venv that installs `retina/requirements.txt` [04-prep F-a, F-d].

**Reference, people and ratification**

18. **The `cpu_reference` identity:** the stock 5.0.0.93 wheel in its own venv, or the custom build's CPU path. Never the user-site 4.12.0 (decision 8).
19. **A trusted GPU runner.** The origin is a public repo (AGENTS.md:74), so qualification runs stay local or on a private trusted runner (input blueprint §6).
20. **Named owners:** at least a build and package owner, and an independent correctness reviewer who is not the build author (input blueprint §7; decision 11).
21. **The scoped-delta positive-change semantic** (decision 6), and the disposition of the other OpenCV branches (decision 9).
22. **Before any GPU backend code lands under `retina/`:** ratify or decline ADR-0002. Whether this also gates the out-of-tree build is Joe's call (INFERENCE that it does not; §0 item 4).

Source: [06-critic §6], the three G0 workflow-2 review verdicts, and the owner ruling, reconciled with ADR-0002.

---

## 14 · Per-release status block

Field labels are from the input blueprint's §8 template, filled for G0.

```text
Vision milestone: G0 (revised after review; R1-R4 ruled 2026-11-07; ADR-0002 unratified) /
  previous: none in the input blueprint's ladder; ruled-program predecessor
  NR-GPU-FEASIBILITY (merged d9a325bc, feasible-unproven)
Changed this release: nothing shipped. Two docs files on local branch vision/opencv51-g0,
  unpushed: this receipt and ADR-0002 (PROPOSED, with the owner's four G0 rulings)
CPU behavior preserved: yes. No code changed; retina/ is byte-identical to v5.98.0
GPU operations actually executed: none by G0. No OpenCV CUDA operator anywhere in the
  program. One trivial non-OpenCV CUDA kernel per the NR-GPU-FEASIBILITY receipt
  (receipt-read, not re-observed)
Artifact and source identities: no OpenCV artifact exists. Pinned sources staged under
  E:/OpenCV5.1_Prep (ruled root): opencv e4f78fbcf1a773fbed69e14500e8b734963eb585,
  opencv_contrib b67a855188a3d683813731010f6d39ac614733a4 (not built). SYNAPSE ef43d37a;
  origin/master e3846b22; tag v5.98.0 6a5f68dd
Tests: 127 passed / 0 failed / 3 skipped / 0 not run (RETINA subset, report 05,
  off-pin cv2 4.12.0 on CPU; the OIIO lane ran 0 of 3)
Performance: UNKNOWN (nothing measured)
Installed-host and customer qualification: none. Not paired, not packaged
Known blockers and owner: ADR-0002 decisions 5-18; section 13 "Still needed" items 1-22.
  No graph node owns the build; JEV parks every GPU node; the E: recipe has no install
  step. Owner: Joe
Default/opt-in state: no backend exists. RETINA is CPU-only; T1 has no production caller
Rollback evidence: n/a. Docs only; revert the commits
Next bounded increment and target window: Joe's rulings on ADR-0002 decisions 5, 12, 13
  and 14, with a JEV re-run or an owner exception; then a configure-only window under
  the E: root once authorized. Window: UNKNOWN; JEV and Joe set the order
Human approvals still required: ADR-0002 ratification; every "Still needed" item in
  section 13; merge and push of this branch
```

---

## 15 · What G0 did not do

- **No GPU probe of any kind.** No build, configure, clone, install, pip or venv. No Houdini, hython or husk launch. Nothing executed in `E:/OpenCV5.1_Prep`; this revision only read files there.
- **No edits to governing text:** `CLAUDE.md`, `AGENTS.md`, the RETINA blueprint, the reconciliation record, the perception catalog, the flywheel queue, `graph.json` and every `ratified` field are untouched.
- **No merge, push, rebase, reset, amend, tag, stash or checkout.**
- **One network read,** a PyPI JSON fetch for the OIIO wheel list [04-prep §0]. No network writes.
- **One executed test run and one CPU reproduction** by report 05, on the default interpreter, with the plugin-import caveat in §9. The truth reviewer re-ran the subset with plugin autoload disabled (§9).

---

## Hygiene

The orchestrator snapshotted the live checkout's status and every file in the OpenCV prep project before G0 began, and **verifies the before/after snapshots after this run** (orchestrator record). The after-W1 comparison matched the before snapshot for both, per the orchestrator's snapshot notes. The comparison after this authoring step is the orchestrator's, not this receipt's.

This authoring step wrote only these files:

- this file and ADR-0002, in the G0 worktree;
- the commit message and staging copies, in a G0 build folder outside every repository.

Following public-repo hygiene, neither committed file contains a user-profile path, a build-folder path or a credential. The RETINA scoped-delta check is described by what it checks, not how.

---

## Review record (G0 workflow 2)

Three independent attack agents reviewed draft commit `b4b6cb8a`. Every blocker was fixed in this one revision; none was rebutted. One premise in the computed task was corrected rather than repeated: `NR-GPU-FEASIBILITY` compiled nothing under `C:/ocv` (ADR-0002 Consequence 5).

| Id | Lens | Disposition | Where |
|---|---|---|---|
| T1 | truth | fixed | ADR-0002 "Owner rulings (2026-11-07)", Status line, "Decisions 1-4: RULED"; receipt header, §0 item 2, §6, §13 "Ruled 2026-11-07", §14 |
| T2 | truth | fixed | ADR-0002 Context §3, the settled sentence |
| T3 | truth | fixed | ADR-0002 Context §2 item 3; receipt §4 Sidecar row |
| T4 | truth | fixed | ADR-0002 Context §2 item 8 heading and text, seam bullet, Refused Site 4, decision 6; receipt §7 rows 10-13 collapsed |
| G1 | governance | fixed | ADR-0002 Status, Authors, "Owner rulings", Reconciliation ("If ratified" removed); receipt header "G0 owner" row, §13, §14 |
| G2 | governance | fixed | ADR-0002 decision 12 (graph home, `NR-IMAGE-CONTRACT` widening, allowlist coupling; no INTEGRATOR); receipt §5, §11 (slice 1 not dispatchable, not the next increment) |
| G3 | governance | fixed | ADR-0002 decisions 5(d) and 13, Reconciliation G1 row; receipt §13 "Still needed" items 1-2 |
| G4 | governance | fixed | ADR-0002 "Invariants Inherited" (§2 invariants 1-8), Refused Site 1, OIIO preserve row (`cv2.imread`), no-edit list (`CLAUDE.md`, `AGENTS.md`) |
| G5 | governance | partly fixed at `1400a43e`; the §9 residual (G5r) was fixed on 2026-11-08 | receipt §7 rows 10-13 and the scoped-delta bullet; ADR-0002 seam bullet |
| F1 | feasibility | fixed | ADR-0002 "Owner rulings", Consequence 4, decisions 16-17; receipt §13, §14 |
| F2 | feasibility | fixed | ADR-0002 Consequence 2, decision 14; receipt §13 item 3 |
| F3 | feasibility | fixed | ADR-0002 decisions 5 and 13; receipt §13 items 1-2 (candidate failable predicate) |
| F4 | feasibility | fixed | ADR-0002 Consequence 6, decisions 16-17; receipt §6 "Install step" and "Where cv2 lands" rows, §13 items 6-7 |
| F5 | feasibility | fixed | receipt §6 "DLL resolution" row, §13 item 8; ADR-0002 decision 18, `probe_capabilities` |
| F6 | feasibility | fixed | receipt §12 renamed "Scope bounds" with a time-box protocol, §11 configure-only step, §13 items 9-10 |
| F7 | feasibility | fixed | ADR-0002 Rollback (G1 environment; worker-package rollback unavailable; D1 row); receipt §13 item 13 |
| F8 | feasibility | fixed | ADR-0002 "Parity input boundary", decision 15; receipt §11 slice 2 |
| F9 | feasibility | fixed | receipt §11 (graph home per decision 12, per-file acceptance with cv2 provenance, `importlib`/`__import__` check) |

**Nits folded in:** graph.json cites for `NR-IMAGE-CONTRACT` scope (`:102`, `:112`); `AGENTS.md:77` extension tagged INFERENCE beside invariant 8; three more non-behavioural predicates; three files in `1edb9450..6a5f68dd`; "JEV state" split from repo state; `PYTHONPATH` in the §9 command; "documents", not "recommends", for the hython seed; R182's "OpenCV in the sidecar"; `WITH_*`/`BUILD_*` cites for §8; `fallback_2`; §0 item 4 tagged INFERENCE; status-block labels attributed to the template; the autoload-off re-run cited in §9; rulebook vocabulary scope and ADR-0001 "Accepted"; the `NR-FOLLOW-ON` overlap; bus posting (Law 5); relayed-instruction scope in §13; driver 621.14 / UMD 13.5 as INFERENCE; the B4 CMake note; the prep's own readiness items; the five parity fixtures; the NumPy-header row; the GPU worker venv recipe's owner; the D1-row rollback wording.

## Re-verify and fix round (2026-11-08)

The three re-verify lenses closed every round-one blocker but refuted revision `1400a43e` on four residuals. On 2026-11-08 Joe authorized one narrow fix round in the reviewers' own wording across both lanes (orchestrator record). The four G0 items are below; the two C0 items are in the C0 report's review record. This round changed only these sentences and the bookkeeping they made untrue.

| Id | Lens | Disposition | Where |
|---|---|---|---|
| T5 | truth | fixed | ADR-0002 "Consequences of R1-R4" item 2 and the Reconciliation G1 row; receipt §0 item 5. `C:/ocv` and the masked `meanStdDev` closure are attributed to `NR-GPU-FEASIBILITY`'s committed receipt; `graph.json:95` names only that chain's fixtures (the link is INFERENCE) |
| G5r | governance | fixed | receipt §9 mutation-evidence bullet names the scoped-delta exterior primitive abstractly; ADR-0002 decision 6 likewise. The G5 row above now says "partly fixed" |
| G6, F1 | governance, feasibility | fixed | receipt §6 lead sentence and §12 build-duration bullet; ADR-0002 decision 16. R3 rules the root only: the staged recipe as starting point is INFERENCE, parallelism is open (decision 16), and whether the prep venv is the worker is open (decision 17) |
| G7 | governance | fixed | receipt §13 "Ruled 2026-11-07" quotes Joe's words verbatim, byte-identical to ADR-0002 "Owner rulings (2026-11-07)"; the header row points to both |

Re-verify nits that restate these blockers are closed with them. Every other re-verify nit was outside this round and stays open.
