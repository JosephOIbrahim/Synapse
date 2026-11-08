# Vision and Grow lanes — a graph amendment, half merged

**Status: the OpenCV lane is MERGED into `graph.json` (2026-11-08, Joe's choice). The Grow lane is still PROPOSED.**

Joe's choice, verbatim (ADR-0002, "Ratification and owner rulings (2026-11-08)", answer 2):

> "Merge with defaults (Recommended)": "Merge the OpenCV lane with these defaults for its open choices: the change-mask chain is added beside the meanStdDev census (OD-22); predicates stay under harness/next-release/proposals/ (OD-03); NR-GPU-QUALIFICATION's gate becomes joe (OD-23); the canary node stays parked behind the worker."

This folder scaffolded two lanes onto the next-release graph:

- the **OpenCV 5.1 vision lane**, folded in per the owner ruling of 2026-11-07 (R1-R4). **Merged 2026-11-08:** 5 nodes, 18 edges, 4 changes to existing nodes, and `NR-GPU-QUALIFICATION`'s gate moved to `joe`.
- the **Grow lane** from the Neural Growth Creative Loop blueprint. **Not merged.** No ruling covers it yet (OD-01).

It is graph engineering only. No product code, no build, no GPU work, no Houdini.

The written case is in `docs/reviews/neural-growth-c0-report-2026-11-07.md` (the C0 report).

---

## What is here

| File | What it is |
|---|---|
| `vision-grow.amendment.PROPOSED.json` | 10 `NR-VG-` nodes and 33 edges in `graph.json`'s own schema. The merged half stays as history; `_merge_record` names what merged and the ruled why edits |
| `predicates/test_nr_vg_*.py` | One closure predicate per node. They stay here (OD-03, ruled 2026-11-08) |
| `validate_amendment.py` | Offline, merge-aware checker. Standard library only |

---

## Run the validator

From the repository root:

```bash
python harness/next-release/proposals/validate_amendment.py
```

**What you see when it works:** one `PASS` line per check, some `INFO` lines, then

```text
SUMMARY: 76 checks, 76 passed, 0 failed - merge-aware: merged OpenCV lane matches the amendment and its rulings; every unmerged predicate red for its declared reason
```

Exit code 0 means every check passed. Anything else exits 1 and names the failing check.

That count was produced by `python harness/next-release/proposals/validate_amendment.py` on 2026-11-08, on a local CPython 3.14.2 with pytest 8.4.2, run from the worktree root with plugin autoload and bytecode writing off and `PYTHONPATH` set to the worktree's `python` folder and root.

**It can still fail.** A scratch copy of `graph.json`, outside the repo, carried three named mutations:

- `NR-VG-RETINA-GUARDS` gate flipped to `crux`;
- an unruled sentence appended to `NR-VG-GPU-CANARY`'s why;
- the merged edge `NR-VG-GPU-BUILD-LOCK -> NR-PACKAGE-PAIR` dropped.

`validate_amendment.py --graph <that copy>` exited 1 with `SUMMARY: 76 checks, 72 passed, 4 failed - amendment INVALID`: both merged-node checks, the owner-decision gate check and the merged-edges check failed. The repo `graph.json` was not touched.

---

## What the validator checks

**Merged nodes** (now in `graph.json`):

- **Exact merge.** Each graph entry equals its amendment entry on `id, title, owner_files, depends_on, predicate, effort` and uses the node schema.
- **Gate.** The amendment gate, or the gate a ruled owner decision sets (OD-23 moved `NR-GPU-QUALIFICATION` to `joe`).
- **Why.** The amendment why with exactly the ruled edits in `_merge_record.ruled_why_edits` applied. An edit may drop only cites of owner decisions ruled on 2026-11-08, keeps every open one, and carries the date.
- **Changes to existing nodes.** The four merged changes are applied as proposed, plus the ruled why edit.
- **Edges.** Every amendment edge between graph nodes is in `graph.json` verbatim. No other `NR-VG-` node or edge is in `graph.json`.
- **Predicates.** Each runs. Its result is `INFO`: green, or red with its first failure line. Only "it runs" (exit 0 or 1) is a check.

**Unmerged nodes** (the Grow lane) keep every earlier check:

- **Structure.** Unique ids; ids start with `NR-VG-`; nodes use exactly `id, title, owner_files, depends_on, why, predicate, gate, effort`; edges use only the edge types `graph.json` already uses, and each touches an unmerged node.
- **Red for the right reason.** Each predicate runs (120 s limit, plugin autoload off, temp folders redirected) and must exit **1** with its declared marker on a pytest `E` line. Exit 0, 2, 4 or 5 fails the check.
- **The Grow lane stays out.** The unmerged nodes are exactly OD-01's, and OD-01 is unruled.

**Across the merged view** (`graph.json` plus the unmerged nodes and edges):

- **Header.** `_status` records the merge and quotes Joe's choice; the quote appears verbatim in ADR-0002's ratification section.
- **Wiring.** Every `depends_on` and edge endpoint resolves. Every `dep` edge agrees with its target's `depends_on`. The dependency graph has no cycle.
- **Ownership.** No amendment node's `owner_files`, merged or not, overlaps any other node. The check is **prefix-aware**: `dir/` owns everything under it.
- **Gates.** Every gate is `crux` or `joe`. Every node an open owner decision names is `joe`.
- **Coverage.** OpenCV stages G1-G6 and Grow stages C1-C6 each map to a node.
- **Not collected.** `pyproject.toml` testpaths and every `pytest` line in `.github/workflows/` miss `predicates/`. Red-by-design files must never turn CI red.
- **Movable.** No predicate finds the repo root by folder depth. Each is copied to a temporary folder at another depth: its `ROOT` must resolve to this repository, an unmerged copy must stay red for its marker, and a merged copy must end with the same exit code as in place.
- **No missing file.** A changed node's new predicate file is in the repo, or its full draft rides in the change entry (`proposed_file`). `harness/next-release/gpu/test_qualification_contract.py` is in the repo now; an `INFO` line says whether it still equals the carried draft.
- **Receipts are scheduled.** Every `.json` a predicate reads that a node owns belongs to the node or to a `depends_on` ancestor.
- **Cites trace.** No bare `ADR-0002 Consequence N`: ADR-0002 has two numbered consequence lists.

**Known limit — pre-existing collisions.** `graph.json` has five owner-file collisions among pre-amendment nodes (K1, K2, K3, K4a, K4b, listed in `_known_existing_collisions` in the amendment). The validator prints them as `INFO` and requires them to match the declared list. It cannot fix them: that is Joe's call.

**Known limit — receipts.** A predicate that reads a receipt cannot tell a real receipt from a fabricated one. It proves shape and internal consistency. Provenance comes from the crux reviewer and Joe's review.

---

## Merged predicates, 2026-11-08

From the `INFO` lines of the validator run above:

| Node | Result | Why |
|---|---|---|
| `NR-VG-RETINA-GUARDS` | **green** | 3 passed |
| `NR-VG-GPU-BUILD-LOCK` | red | no committed build-lock receipt (it is on the build-lock branch, not merged here) |
| `NR-VG-GPU-WORKER-ENV` | red | no committed R4 worker-runtime contract |
| `NR-VG-RETINA-CUDA-BACKEND` | red | no committed backend receipt. ADR-0002 is ratified, so its ratification test passes now |
| `NR-VG-GPU-CANARY` | red | no committed canary receipt; parked behind the worker by Joe's default |
| `NR-GPU-QUALIFICATION` (changed node) | red | no committed qualification receipt |

**`NR-VG-GPU-WORKER-ENV` and the shipped recipe.** Once the contract is committed, the predicate checks the three recipe files against the reviewed text the contract pins by sha256. Its one token check, no `cp314` pin on a non-comment requirement line, matches nothing today: `cp314` appears in `retina/requirements.txt` only in a comment.

Ratification checks read a Status line beginning `**Status:** Accepted`, letter case ignored: the form ADR-0001 uses. ADR-0002's Status line reads that way since 2026-11-08.

---

## The Grow lane (not merged)

All five are `gate: joe`, and all five predicates are red today, each for its declared marker. `NR-VG-GROW-CONTROLS` depends on `NR-VG-NCA-SANDBOX` (a `dep` edge), because its predicate pins the sandbox receipt.

| Node | Stage | Red today because |
|---|---|---|
| `NR-VG-NCA-SANDBOX` | C1 | no sandbox receipt |
| `NR-VG-GROW-CONTROLS` | C2 | no control-package contract |
| `NR-VG-GROW-JOB` | C3 | no Grow job contract |
| `NR-VG-GROW-COMPARE` | C4 | no creative-sidecar contract |
| `NR-VG-GROW-PROMOTION` | C5 | no promotion contract |

**Existing nodes keep their work.** G1 qualification and G3 parity stay with `NR-GPU-QUALIFICATION`. The `retina/t1.py` seam stays with `NR-IMAGE-CONTRACT`. G5 and C6 stay with `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE`. G6 points at the parked `NR-FOLLOW-ON`.

**New receipts live under `harness/vision/`,** not `harness/next-release/`. `NR-FOLLOW-ON` owns all of `harness/next-release/`, so any new owner file there would collide.

---

## How adoption works

1. **Joe rules** on the owner decisions below. For the OpenCV lane this happened on 2026-11-08 (answers 1-3 in ADR-0002's ratification section). The Grow lane needs OD-01 at minimum.
2. **Joe merges** the nodes and edges into `harness/next-release/graph.json` and applies the `_proposed_changes_to_existing` entries he accepts. **The predicates find the repo root from the working directory, not from their own folder, so a move to any depth inside the repo keeps them working;** the same commit must update every `predicate` string that names a moved file. `_merge_record` then tells the validator what merged.
3. **JEV ranks the graph** — the lane README, section 2. The 2026-11-08 re-rank after the OpenCV merge is recorded there.
4. **Nodes land the usual way:** worktree, failing-first tests, one atomic commit, adversarial review, owner-only merge.

**The graph guard will not catch ownership or dependency mistakes.** In graph mode `compositor.py` applies JEV's judgments only (`decide_graph`, `harness/harness2/compositor.py:423`). Its single-writer check, `files_disjoint` (`:279`), runs in compose mode only and compares exact strings. Joe's merge review, plus this validator, is the guard.

---

## Changes to existing nodes — merged 2026-11-08

These follow from R1-R4 and the 2026-11-08 rulings. Each text states only what was ruled; anything G0 proposed beyond it stays labelled G0-proposed or INFERENCE.

| Node | Field | Change | Ruling |
|---|---|---|---|
| `NR-GPU-QUALIFICATION` | `why` | adds the R2 chain and the R3 root; the ruled edit records the change-mask chain beside the `meanStdDev` census, which stays a later closure item (OD-22, option ii), the stock 5.0.0.93 `cpu_reference` (OD-10) and gate `joe` (OD-23) | R2, R3; OD-22, OD-10, OD-23 |
| `NR-GPU-QUALIFICATION` | `predicate` | `test -f …` → `harness/next-release/gpu/test_qualification_contract.py`, already in the repo and equal to the carried draft | R2, R3 |
| `NR-GPU-QUALIFICATION` | `depends_on` | adds `NR-VG-GPU-BUILD-LOCK` | R3 |
| `NR-WORKER-SUPERVISED` | `why` | states the R4 worker runtime, nothing more | R4 |

**Gate, changed:** `NR-GPU-QUALIFICATION` is `joe` (OD-23, ruled 2026-11-08).

**Ruled why edits.** In the merged whys, each "Waits on OD-n" clause for a decision ruled on 2026-11-08 now says what was ruled and when; the open ones stay. `NR-VG-RETINA-GUARDS` also records ADR-0002's ratification (OD-11), and `NR-VG-GPU-CANARY` records that it stays parked behind the worker. The exact edits, each with its basis, are in `_merge_record.ruled_why_edits`.

---

## Owner decisions

The full text is in `_owner_decisions` in the amendment. **Ruled 2026-11-08** (`_merge_record.ruled`): OD-02 and OD-09 (settled by the merge), OD-03, OD-10, OD-11, OD-22, OD-23.

**Graph and ownership**

- **OD-01** — adopt the Grow lane at all, and widen the graph objective. **Open.**
- **OD-02** — the build: a new node, or `NR-GPU-FEASIBILITY` reopened. **Settled 2026-11-08 by the merge:** `NR-VG-GPU-BUILD-LOCK` owns the build.
- **OD-03** — K4: `NR-FOLLOW-ON` owns all of `harness/next-release/`, including this folder. **Ruled 2026-11-08:** the predicates stay here. The K4 collision itself stays.
- **OD-04** — K1: `harness/next-release/gpu/` is owned by two nodes, and the qualification test lives there. **Open.**
- **OD-05** — K2: `installer/build_payload.py` is owned by two nodes, and the payload guard reads it. **Open.**
- **OD-06** — K3/K6: Grow registration needs files `NR-SPARSE-RENDER` and `NR-WRITE-RECEIPT` own. **Open.**
- **OD-07** — K5: widen `NR-IMAGE-CONTRACT` for the backend seam, and order it against the Y change. **Open.**
- **OD-08** — K7: model and reference licensing is outside `NR-LICENSE-GATE`'s scope. **Open.**
- **OD-09** — graph home for the guard tests, the venv recipe and the CUDA module. **Settled 2026-11-08 by the merge:** the new nodes.
- **OD-13** — unpark the GPU and RETINA nodes; define what satisfies `depends_on`; whether `NR-WORKER-SUPERVISED` may close on the old hython-seeded recipe. **Open.** The JEV re-run it asked for is done (lane README, section 2).
- **OD-20** — home for G6. **OD-21** — canary before or after packaging. **Both open.**

**From the ruling**

- **OD-11** — ratify ADR-0002. **Ruled 2026-11-08:** Accepted.
- **OD-12** — demo v1, build window, parallelism, Windows 26H2, build and install authorization. **Open.** The 2026-11-08 build ran under Joe's goal-level go, which rules no numbered decision.
- **OD-10** — the `cpu_reference` identity. **Ruled 2026-11-08:** the stock `opencv-python-headless` 5.0.0.93 wheel in its own venv. **OD-14** — the scoped-delta positive-change semantic. **Open.**
- **OD-22** — ADR-0002 decision 14. **Ruled 2026-11-08:** option (ii), the change-mask chain beside the census. **OD-23** — `NR-GPU-QUALIFICATION`'s gate. **Ruled 2026-11-08:** `joe`.
- **OD-15** — build/package owner and an independent correctness reviewer. **Open.**
- **OD-16** — worker venv location and creator; CUDA DLL resolution. **OD-17** — the other OpenCV branches. **Both open.**

**Grow lane**

- **OD-18** — launching a separate Houdini session for C1, and which build. **Open.**
- **OD-19** — the amendment for reference-driven control generation; CPU-first or GPU path for C2. **Open.**

---

## Safe to touch

- This folder: yes, on a branch. Re-run the validator after any edit.
- `graph.json`, the RULING files, the lane README, `graph_decision.json`, `harness/harness2/`: **no.** Joe's merge only.
