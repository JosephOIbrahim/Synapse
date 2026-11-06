# Intake adjudication — SYNAPSE Next Release Engineering Blueprint v1.1

**Status:** ADJUDICATED, not ratified. `ratified:false`. This document authorizes
no code change, no build, no release and no push. It records what the blueprint
claims, what this repo can and cannot confirm, where it collides with work
already in flight, and the graph the harness should run when the current loop
closes.

Source and hash: `docs/intake/next-release/MANIFEST.md`.

---

## 1. The one-sentence reading

The blueprint asks SYNAPSE to stop treating "a file exists" as "the render
happened", and to add one honestly-attributed GPU vision path (OpenCV 5.1 on the
RTX 4090) behind a supervised worker, with evidence that survives restart.

That is the same first principle this repo has been enforcing all week: **a
claim is worth what its weakest observation proves.** G101 proved the frame's
identity changed. G25 proved the write landed. This blueprint extends the rule
to products, pixels and backends.

## 2. Claim tiers

| Tier | Meaning here | Representative claims |
|---|---|---|
| **VERIFIED-REPO** | Re-run against this checkout at `eefa8a11` | baseline commit; CI run 42301796914 all six jobs success; every source anchor in §15 present except one (below); PR #112 and #116 OPEN; `LICENSE` is MIT |
| **STATED-UPSTREAM** | The blueprint's own reading of upstream releases | OpenCV 5.1.0 released 2026-11-06; candidate commits `e4f78fb…` (opencv) and `b67a855…` (contrib); CUDA module APIs and masked `meanStdDev` |
| **STATED-REPO** | The blueprint's source reading of SYNAPSE, not re-proved here | "T0 skips unreadable headers while aggregate checks can remain true"; "G25 inspection failures can look undriven"; "installer refuses ordinary downgrades" |
| **INFERENCE** | Reasoned, not measured | feasibility of a source-built CUDA OpenCV on Windows; the useful-chain latency; worker packaging effort |
| **UNKNOWN** | Nobody has run it | any GPU execution on this machine; live H22 host + worker pair; installed rollback |

The distinction matters for planning: only VERIFIED-REPO rows may gate a merge
today. INFERENCE rows become gates only after WP1 produces a receipt.

## 3. Corrections to the blueprint

1. **One stale anchor.** `docs/tickets/ANTHROPIC_SDK_2X_MIGRATION.md` (S12) does
   not exist at `eefa8a11`. Either the document moved or the reference is to a
   branch. It does not affect any P0 item.
2. **"OpenDV 5.1" in the request is OpenCV 5.1** in the document. This intake
   uses OpenCV throughout.
3. **The blueprint predates G32.** It was written against `eefa8a11`; the G32
   branch (`g32/render-proof`, not merged at the time of writing) already
   implements three of its WP2 asks: product identity proof, `output_file`
   carried through the farm, and a per-render nonce in the RETINA sentinel. If
   G32 lands first, WP2's G101 half shrinks to what G32 does not cover:
   original-plan reconciliation, sparse-frame retry selection, unsupported
   plan shapes, and per-product coverage in T0's header checks.

## 4. Where it collides with work in flight

| In flight | Blueprint asks | Disposition |
|---|---|---|
| G32 (branch, reviewed) | product freshness, `output_file`, sentinel nonce | **Overlaps.** Land G32 first; then remove those asks from WP2 and keep the plan/reconciliation half |
| G25 (landed at `eefa8a11`) | receipt survives every route, raw-authored comparison, preconditions | **Consistent.** The blueprint extends G25; it does not replace it |
| RETINA T0 (landed) | per-product coverage, aggregate truth | **Open.** T0 still grades readable siblings independently of unreadable ones; the blueprint's ask stands |
| Panel/worker policy | `gpu_required` profile persistence | **Open.** No GPU profile exists yet; it is new state, not a change to a shipped field |

## 5. First-principles view of the release

Three questions decide whether this release is honest, in this order:

1. **What is the product?** A file with a stable identity, produced by this
   attempt, decoded from those bytes. Not a path, not an aggregate score.
2. **What ran?** A named operation on a named backend through a named worker
   artifact. A flag, a device count or a util percentage is not evidence.
3. **What survives?** A committed terminal receipt that a restart can rebuild
   state from. A result file is not success; an orphan is not success.

Everything else in the blueprint — profiles, envelopes, packaging — exists to
make those three answerable. The graph in `harness/next-release/graph.json` is
ordered by them, not by page order.

## 6. Commercial distribution — the short version

Full analysis: `docs/reviews/next-release-licensing-2026-11-06.md`.

- SYNAPSE itself is **MIT**, so commercial distribution of the repo is already
  permitted with attribution.
- OpenCV 5.1 and its CUDA modules are **Apache-2.0**: permissive; the duties are
  a licence copy, modification notices and any NOTICE text.
- The **NVIDIA CUDA Toolkit** is the real contract, not a permissive licence:
  only listed Attachment A binaries may travel with the app, they must be part
  of a larger application, the toolkit cannot be redistributed, and use is
  limited to systems with NVIDIA GPUs. A CPU-fallback edition needs counsel's
  reading of that last clause.
- **PySide6/Qt is LGPLv3** — a pre-existing obligation of the panel, larger than
  anything OpenCV adds: ship Qt as replaceable DLLs, include the licence texts,
  keep relinkability. One-file bundlers are the usual breach.
- The `opencv-python` wheels are **CPU-only**; building OpenCV with CUDA from
  source is the honest route and also avoids the wheels' bundled FFmpeg
  (LGPLv2.1) question.
- OpenEXR is BSD-3, OpenImageIO Apache-2.0, numpy BSD-3: notices only.

**Verdict:** no OpenCV-licence conflict with commercial use. The obligations are
a third-party notices file, CUDA EULA compliance, and an LGPL audit that SYNAPSE
already owed.

## 7. Decisions that belong to Joe

These are gates, not tasks. The graph marks them as `needs_joe`.

| ID | Decision | Why it cannot be inferred |
|---|---|---|
| D1 | The support row: Windows 11, H22.0.400, host Python, worker runtime, RTX 4090 | The blueprint names them; only the owner can declare what is supported |
| D2 | First image contract colour space for OVOID (ACEScg or linear Rec.709) | Changes the Y coefficients and every analytic fixture |
| D3 | Whether general-user editions ship in this release | Optional per the blueprint; changes packaging scope |
| D4 | The first release profile's `k`, range bounds and tolerances | Profile values are frozen before evaluation and cannot be tuned later |
| D5 | The release identifier | The repo reserves none; `VERSION` is operator-write only |
| D6 | GPU build route: source-built OpenCV with CUDA (recommended) vs pinned third-party binaries | Licensing and reproducibility differ |
| D7 | Commercial posture: notices, CUDA EULA acknowledgement, PySide6 relinkability audit | Legal exposure; not an engineering call |

## 8. Handoff to the harness

The blueprint is not a checklist to start from page 1. It enters the same loop
the worldlabs lane used:

1. `harness/next-release/graph.json` is the node set — ten nodes, typed edges,
   one owner per node, a read-only closure predicate per node that exits
   non-zero on this tree today.
2. The JEV graph guard ranks it:
   `python harness/harness2/compositor.py --mode graph --input harness/next-release/graph.json --wave next-release`
3. The winning node is dispatched to a team in a worktree; the rest wait in
   waves. Dynamic workflows fan the teams out; merges stay human.
4. The trigger is the close of the current loop: G32 merged, CI green on that
   SHA, no in-flight branch touching the same files.

The runbook, including the exact commands and the stop rules, is
`harness/next-release/README.md`.

## 9. What this intake deliberately does not do

- It does not ratify the blueprint, reserve a release number, or claim any GPU,
  HOM or installer result.
- It does not start the vision build. WP1's feasibility spike is a node in the
  graph, and it needs Joe's D6 answer before it spends a day on a native build.
- It does not restate the blueprint's source readings as repo defects. Where
  this document says "open", it means the claim is unverified here, not that the
  code is wrong.
