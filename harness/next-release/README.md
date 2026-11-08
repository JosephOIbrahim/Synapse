# Next-release runbook

The blueprint is landed as **evidence and a graph**, not as a checklist. This
directory is how the lane enters the existing harness when the current loop
closes.

- Blueprint (verbatim): `docs/intake/src/synapse_next_release_blueprint.md`
- Provenance and anchors: `docs/intake/next-release/MANIFEST.md`
- Adjudication and decisions: `docs/intake/next-release-intake-2026-11-06.md`
- Commercial-use review: `docs/reviews/next-release-licensing-2026-11-06.md`
- Graph: `harness/next-release/graph.json`

---

## 1. Do not start before these are true

1. **The current loop is closed.** G32 is merged into `master`, CI is green on
   that SHA, and no branch is in flight against the files this lane touches.
2. **The owner has answered D1 and D6** in the adjudication — the support row
   (Windows 11 / H22.0.400 / host Python / worker runtime / RTX 4090) and the
   GPU build route. WP1 spends real time on a native build; it should not start
   on an unowned assumption.
3. **Houdini is closed for the packaging steps** (WP5). The live checkout is
   Houdini's package source.

Everything else can be planned now.

## 2. First move: let JEV rank the graph

```bash
python harness/harness2/compositor.py \
  --mode graph \
  --input harness/next-release/graph.json \
  --wave next-release
```

The decision lands in `harness/harness2/runs/next-release/graph_decision.json`.
The first landing is JEV's call, not the seat's.

**First decision, recorded 2026-11-06** (receipt committed with this PR): no
node cleared the confidence gate for a single first landing (JEV chose
`NR-PLAN-TRUTH` at 0.43 against a 0.6 gate), so the fallback opened two —
`NR-PLAN-TRUTH` and `NR-WRITE-RECEIPT` — and parked the rest.
`NR-PACKAGE-PAIR` is flagged as needing the owner. `NR-GPU-FEASIBILITY` is
parked, which is the guard saying the GPU track waits on D6 (build route) and
D1 (support row) rather than on any engineering dependency; answering those two
decisions is what unparks the second track.

The lane is designed for two parallel tracks; the receipt is evidence of what
the guard chose today, not a change to the design.

**Second decision, recorded 2026-11-08**, after Joe merged the OpenCV lane
(receipt `harness/harness2/runs/next-release/graph_decision.json`, generated
2026-11-08T14:51:29+00:00 from `graph.json` sha256 `67d59ee2…ce61e`; one row
appended to `harness/jev/ledger/next-release.graph.jsonl`). **JEV fell back again:** its pick sits below the confidence gate, so no
single first landing is designated. Verbatim from the receipt:

- `first_landing`: `null`
- `land_now`: `["NR-GPU-FEASIBILITY", "NR-VG-RETINA-GUARDS"]`
- `park`: `["NR-SPARSE-RENDER", "NR-PLAN-TRUTH", "NR-WRITE-RECEIPT", "NR-GPU-QUALIFICATION", "NR-IMAGE-CONTRACT", "NR-WORKER-SUPERVISED", "NR-RECOVERY-RECEIPTS", "NR-LICENSE-GATE", "NR-FOLLOW-ON", "NR-VG-GPU-BUILD-LOCK", "NR-VG-GPU-WORKER-ENV", "NR-VG-RETINA-CUDA-BACKEND"]`
- `needs_joe`: `["NR-PACKAGE-PAIR", "NR-VG-GPU-CANARY"]`
- `reason`: `fallback: Jev chose NR-SPARSE-RENDER @ 0.43, below the confidence gate 0.6`

That is the order. Against the 2026-11-06 receipt: `NR-GPU-FEASIBILITY` park -> land_now; `NR-PLAN-TRUTH` land_now -> park; `NR-VG-RETINA-GUARDS` absent -> land_now; `NR-WRITE-RECEIPT` land_now -> park.
`NR-VG-GPU-CANARY` is in `needs_joe`, not `park`; it does not land either way.
Joe's default for the canary is his answer 2 in ADR-0002, verbatim: "the canary
node stays parked behind the worker". No graph field encodes that default; the
node's why states it in words. Producer:
`python harness/harness2/compositor.py --mode graph --input
harness/next-release/graph.json --wave next-release`, CPython 3.14.2, run from
the repo root. After this receipt was generated, the revise that answered the
referee restored the word "per-act" in `NR-VG-GPU-BUILD-LOCK`'s why, so the
committed `graph.json` no longer hashes to `67d59ee2…ce61e`; the guard was not
re-run on the revised graph.

## 3. Fan-out, wave by wave

Each node is a work package for one team, in its own worktree:

1. **Probe or fix in a worktree** off `master`. Never in the live checkout.
2. **Tests that can fail.** Every closure predicate in the graph exits non-zero
   on today's tree; the node's own predicate must flip to zero only when the
   real work lands.
3. **Adversarial review** through Codex for `crux` nodes, the way G101 and G25
   were reviewed.
4. **Merge is human.** One atomic commit per node; no push on your own.

Suggested teams, reusing the existing roster:

| Node | Lead | Reviewers |
|---|---|---|
| `NR-PLAN-TRUTH` | CONDUCTOR (autonomy) | INTEGRATOR + codex crucible |
| `NR-WRITE-RECEIPT` | HANDS (handlers) | INTEGRATOR + codex crucible |
| `NR-GPU-FEASIBILITY` | HANDS (render) | assayer probe + sidefx-cto |
| `NR-GPU-QUALIFICATION` | HANDS | crucible + codex |
| `NR-IMAGE-CONTRACT` | OBSERVER | INTEGRATOR + codex |
| `NR-WORKER-SUPERVISED` | SUBSTRATE | seam-hunter + codex |
| `NR-RECOVERY-RECEIPTS` | SUBSTRATE | crucible + codex |
| `NR-PACKAGE-PAIR` | INTEGRATOR | codex + human |
| `NR-LICENSE-GATE` | INTEGRATOR | human (counsel if the CPU edition ships) |

Dynamic workflows fan the teams out; the graph's typed edges decide what may run
in the same wave.

## 4. Checkpoints that are worth stopping at

- **WP1 first checkpoint.** One generated flat RGB EXR through the useful GPU
  chain, with the exact build and API result. No launch date is defensible
  before this exists.
- **WP3 integrated slice.** One immutable EXR through the installed adapter →
  a GPU measurement → a scoped verdict visible to the artist.
- **WP5 pair qualification.** Final loaded bytes, fresh install, incompatible
  pair refusal, data-preserving rollback.

## 5. What the graph will not let you skip

- A GPU flag, a device count or a utilisation percentage is not a receipt. The
  executed dispatch branch and the backend witness are.
- A result file is not success. The committed terminal receipt is.
- A readable sibling product cannot vouch for an unreadable one.
- A profile value is frozen before evaluation; nobody loosens it to get a pass.

## 6. Stop rules

Stop and surface, do not improvise:

- The graph names a `gate: joe` node and D1–D7 are unanswered.
- CI is red on the SHA a node is based on.
- A probe contradicts a blueprint claim. The probe wins; update the intake, not
  the probe.
- A file in `owner_files` is claimed by two in-flight nodes. That is a finding,
  not a race.
