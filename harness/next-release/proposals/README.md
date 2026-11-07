# Vision and Grow lanes — a PROPOSED graph amendment

**Status: PROPOSED. Not ratified. Nothing here is in `graph.json`.**

This folder scaffolds two lanes onto the next-release graph:

- the **OpenCV 5.1 vision lane**, folded in per the owner ruling of 2026-11-07 (R1-R4);
- the **Grow lane** from the Neural Growth Creative Loop blueprint, which **no ruling covers yet**.

It is graph engineering only. No product code, no build, no GPU work, no Houdini.

The written case is in `docs/reviews/neural-growth-c0-report-2026-11-07.md` (the C0 report).

---

## What is here

| File | What it is |
|---|---|
| `vision-grow.amendment.PROPOSED.json` | 10 new `NR-VG-` nodes and 33 new edges, in `graph.json`'s own schema |
| `predicates/test_nr_vg_*.py` | One closure predicate per new node. **Red today, on purpose** |
| `validate_amendment.py` | Offline checker. Standard library only |

---

## Run the validator

From the repository root:

```bash
python harness/next-release/proposals/validate_amendment.py
```

**What you see when it works:** one `PASS` line per check, some `INFO` lines, then

```text
SUMMARY: 41 checks, 41 passed, 0 failed - amendment structurally valid; every new predicate red for its declared reason
```

Exit code 0 means every check passed. Anything else exits 1 and names the failing check.

That count was produced by `C:/Python314/python.exe harness/next-release/proposals/validate_amendment.py` on CPython 3.14.2 with pytest 8.4.2, run from the worktree root (C0 report, section 13).

---

## What the validator checks

- **Structure.** Unique ids; new ids start with `NR-VG-`; new nodes use exactly `id, title, owner_files, depends_on, why, predicate, gate, effort`; edges use only the edge types `graph.json` already uses.
- **Wiring.** Every `depends_on` and edge endpoint resolves. Every `dep` edge agrees with its target's `depends_on`. The dependency graph has no cycle.
- **Ownership.** No new node's `owner_files` overlaps any other node. The check is **prefix-aware**: `dir/` owns everything under it.
- **Gates.** Every gate is `crux` or `joe`. Every new node that waits on an owner decision is `joe`.
- **The one exception.** Each entry in `_proposed_changes_to_existing` must name an existing node and field, quote that field's current value exactly, and cite R1-R4. Each entry is printed.
- **Coverage.** OpenCV stages G1-G6 and Grow stages C1-C6 each map to a node.
- **Not collected.** `pyproject.toml` testpaths and every `pytest` line in `.github/workflows/` miss `predicates/`. Red-by-design files must never turn CI red.
- **Red for the right reason.** Each predicate runs (120 s limit, plugin autoload off, temp folders redirected) and must exit **1** with its declared marker on a pytest `E` line. Exit 0, 2, 4 or 5 fails the check.

**Known limit — pre-existing collisions.** `graph.json` already has five owner-file collisions among existing nodes (K1-K4 below). The validator prints them as `INFO` and requires them to match the amendment's declared list. It cannot fix them: that is Joe's call, and this folder never edits `graph.json`.

**Known limit — receipts.** A predicate that reads a receipt cannot tell a real receipt from a fabricated one. It proves shape and internal consistency. Provenance comes from the crux reviewer and Joe's per-act review.

---

## How adoption works

1. **Joe rules** on the owner decisions below. At minimum OD-01 (adopt the Grow lane at all) and OD-03 (where predicates and receipts live).
2. **Joe merges** the nodes and edges into `harness/next-release/graph.json`, applies the `_proposed_changes_to_existing` entries he accepts, and moves the predicate files where OD-03 says. The predicate for the changed `NR-GPU-QUALIFICATION` does not exist yet; it lands in that same commit.
3. **JEV ranks the graph** — the lane README, section 2. The committed JEV decision ranks an older graph, so this re-run is needed anyway.
4. **Nodes land the usual way:** worktree, failing-first tests, one atomic commit, adversarial review, owner-only merge.

**The graph guard will not catch ownership or dependency mistakes.** In graph mode `compositor.py` applies JEV's judgments only (`decide_graph`, `harness/harness2/compositor.py:423`). Its single-writer check, `files_disjoint` (`:279`), runs in compose mode only and compares exact strings. Joe's merge review, plus this validator, is the guard.

---

## The new nodes

All ten are `gate: joe`. All ten predicates are red today.

| Node | Stage | Red today because |
|---|---|---|
| `NR-VG-GPU-BUILD-LOCK` | G1 build | no committed build-lock receipt |
| `NR-VG-RETINA-GUARDS` | G2 guards | guard tests not committed |
| `NR-VG-GPU-WORKER-ENV` | G2 recipe | no R4 worker-runtime contract; the shipped recipe still conflicts with R4 |
| `NR-VG-RETINA-CUDA-BACKEND` | G2 backend | ADR-0002 is PROPOSED, not ratified |
| `NR-VG-GPU-CANARY` | G4 | no canary receipt |
| `NR-VG-NCA-SANDBOX` | C1 | no sandbox receipt |
| `NR-VG-GROW-CONTROLS` | C2 | no control-package contract |
| `NR-VG-GROW-JOB` | C3 | no Grow job contract |
| `NR-VG-GROW-COMPARE` | C4 | no creative-sidecar contract |
| `NR-VG-GROW-PROMOTION` | C5 | no promotion contract |

**Existing nodes keep their work.** G1 qualification and G3 parity stay with `NR-GPU-QUALIFICATION`. The `retina/t1.py` seam stays with `NR-IMAGE-CONTRACT`. G5 and C6 stay with `NR-PACKAGE-PAIR` and `NR-LICENSE-GATE`. G6 points at the parked `NR-FOLLOW-ON`.

**New receipts live under `harness/vision/`,** not `harness/next-release/`. `NR-FOLLOW-ON` owns all of `harness/next-release/`, so any new owner file there would collide.

---

## Proposed changes to existing nodes

Only what R1-R4 requires:

| Node | Field | Change | Ruling |
|---|---|---|---|
| `NR-GPU-QUALIFICATION` | `why` | meanStdDev census and implicit `C:/ocv` → the change-mask chain on the E: artifact | R2, R3 |
| `NR-GPU-QUALIFICATION` | `predicate` | `test -f …` → a behavioural pytest that reads the qualification receipt | R2, R3 |
| `NR-GPU-QUALIFICATION` | `depends_on` | adds `NR-VG-GPU-BUILD-LOCK` | R3 |
| `NR-WORKER-SUPERVISED` | `why` | states the R4 worker runtime | R4 |

---

## Owner decisions this needs

The full text is in `_owner_decisions` in the amendment.

**Graph and ownership**

- **OD-01** — adopt the Grow lane at all, and widen the graph objective. R1 covers the OpenCV blueprint only.
- **OD-02** — the build: this new node, or `NR-GPU-FEASIBILITY` reopened.
- **OD-03** — K4: `NR-FOLLOW-ON` owns all of `harness/next-release/`, including this folder.
- **OD-04** — K1: `harness/next-release/gpu/` is owned by two nodes.
- **OD-05** — K2: `installer/build_payload.py` is owned by two nodes, and the payload guard reads it.
- **OD-06** — K3/K6: Grow registration needs files `NR-SPARSE-RENDER` and `NR-WRITE-RECEIPT` own.
- **OD-07** — K5: widen `NR-IMAGE-CONTRACT` for the backend seam, and order it against the Y change.
- **OD-08** — K7: model and reference licensing is outside `NR-LICENSE-GATE`'s scope.
- **OD-09** — graph home for the guard tests, the venv recipe and the CUDA module.
- **OD-13** — unpark the GPU and RETINA nodes (JEV re-run or exception); define what satisfies `depends_on`.
- **OD-20** — home for G6. **OD-21** — canary before or after packaging.

**Still open from the ruling**

- **OD-11** — ratify ADR-0002 (stays PROPOSED).
- **OD-12** — demo v1, build window, parallelism, Windows 26H2, per-act build and install authorization.
- **OD-10** — the `cpu_reference` identity. **OD-14** — the scoped-delta positive-change semantic.
- **OD-15** — build/package owner and an independent correctness reviewer.
- **OD-16** — worker venv location and creator; CUDA DLL resolution. **OD-17** — the other OpenCV branches.

**Grow lane**

- **OD-18** — launching a separate Houdini session for C1, and which build.
- **OD-19** — the amendment for reference-driven control generation; CPU-first or GPU path for C2.

---

## Safe to touch

- This folder: yes, on a branch. Re-run the validator after any edit.
- `graph.json`, the RULING files, the lane README, `graph_decision.json`, `harness/harness2/`: **no.** Joe's merge only.
