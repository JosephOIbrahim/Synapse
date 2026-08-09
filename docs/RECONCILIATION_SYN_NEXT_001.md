# RECONCILIATION PROPOSAL — SYN-NEXT-001 ↔ H22 governing blueprint

**Status: RATIFIED 2026-08-08.** E1 (`ratify`) and E4 (`reconcile`) ruled by the CTO this
session; the merge of this document is the binding act (see §6 rulings record). Drafted as a
proposal under P1/P4 — no document self-adopts — and bound only by those human acts.

**Inputs:** `docs/intake/adjudication-syn-next-001.md` (c073af0) · E2 probe 2026-08-08
(22.0.397 installed on workstation; refs are dated 2026-08-01 receipts + worktree mirrors) ·
live version-split verification (5.44.0 / 5.43.0 / 5.42.0).

---

## 1 · Laws ↔ Principles map (§1.3 vs P1–P7)

| SYN-NEXT law | Relation to governing blueprint | Proposal |
|---|---|---|
| Truth | Identical to **P1** | Cite P1; no new law |
| Fail-visible | No P-analog; operationalizes P1 for subsystems | Adopt as extension **L-FV** |
| Artist sovereignty | P4-adjacent but distinct (artist data, not gates) | Adopt as extension **L-AS** |
| Determinism | Complements **P7** (validation precedes mutation) | Adopt as extension **L-DET**, cites P7 |
| Reversibility | Identical intent to **P3** | Cite P3; no new law |
| Build pinning | Identical to **P6** | Cite P6; no new law |
| Boundedness | No P-analog; W8's law | Adopt as extension **L-BND** |
| One authority | Already operational (single-writer rule, playbook §0) | Cite playbook §0; no new law |

P1–P7 are not renumbered. Extensions carry the L- prefix and never override a P-law.

---

## 2 · Corrections folded (adjudication item 4 · E2 probe)

**W1.5 reframed — regression guard, not current-state fact.** PR #60 (2026-08-01, pre-baseline)
made the Moneta→JSONL fallback loud. W1.5 therefore reads: *a negative control proves no
silent-JSONL regression*; the current runtime state is confirmed by probe, not asserted.
The fail-visible law stands unchanged.

**A4 rewritten — historical vs live.** The stale-pin gate distinguishes:
- **Dated historical receipts** (e.g. `docs/reviews/synapse-review-2026-08-01.md`, stamped on
  22.0.397 when it was the running build, mirrored across worktrees): **retained**, declared
  historical. Zeroing them destroys provenance and is prohibited.
- **Live support claims** (README banners, health snapshots, fixture pins): **must match** the
  current verified pin or fail the gate.
Pin counts are scope-declared henceforth (repo-wide vs source-tree) — the 18-vs-77 divergence
was a scope artifact, not a dispute.

**E2 residual stays open:** the current verified support target (368 / 397 / 400 — three builds
installed) is a W9 support-event ruling. This proposal encodes the gate shape; the CTO picks
the build.

---

## 3 · Workstream → home map (ratifies adjudication §d)

**Harvest into existing gaps:** W8 → freeze-attribution track (FRZ classes) · W9 + A4 → G7,
G1a, G9 · W10 → G8 + honest-green CI · W11 → bridge gate anchors · W12 + A5 → G9 ·
W1/W2/W3 → G5 memory waves + G8 + shipped Moneta production harness, PR #60 state folded.

**New scope, placement per E3 word (`gaps` or `program`):** W0 (release-truth machine) ·
W4/W5 (Track A: deterministic router + fixture registry) · W6 (Track B: network capture).

---

## 4 · Contracts registered

The §4 schemas — `intent_route/v1` · `fixture_registry/v1` · `memory_store/v2` (incl. A2 `wal`
block) · `memory_record/v2` · `execution_receipt/v2` (incl. A1 `prompt_provenance`, A3 `timing`)
· `health/v1` — are registered as the SYN-NEXT contract set, versioned independently; a schema
change is explicit and migratable. Receipt work folds into RETINA/G4 receipts per adjudication
item 15.

---

## 5 · Effect of ratification

On **E1 `ratify`** + **E4 `reconcile`** + merge of this document: SYN-NEXT-001 governs the
next-system program; the H22 gap blueprint continues governing G1–G9 closure; and this document
is the bridge between them. The E2 residual (support-target build) and E3 (Track A/B placement)
are recorded here when ruled. Until those human acts, everything above is proposal — including
this sentence.

---

## 6 · Rulings record — 2026-08-08

- **E1 — `ratify`.** SYN-NEXT-001 stands as the governing blueprint of the next-system program.
- **E3 — `program`.** W0, Track A (W4/W5), and Track B (W6) form the SYN-NEXT program board;
  G1–G9 remain under the H22 gap blueprint.
- **E4 — `reconcile`.** Sections 1–4 above are binding as the bridge between the two.
- **E2 residual — `22.0.400` selected** as the next verified support target, under engineering
  authority delegated by the CTO this session. Evidence: three H22 builds installed
  (368 / 397 / 400); `drop.json` declares 368 (2026-07-15); the package `hpath` pins no build;
  400 is the newest installed and the daily driver, and targeting it retires the
  stamp-vs-runtime mismatch class. **22.0.368 remains the verified pin of record until the W9
  re-stamp verifies 400** — selection is a target, not a teleport. The `harness/state/drop.json`
  update is a human file-write (single-writer rule): flagged for Joe, not performed.

Enacted via CTO ruling: `go — E1 ratify · E3 program · E4 reconcile · build pick delegated ·
merge + push` (session 2026-08-08). Precedent for the instrument pattern is recorded in
`drop.json` itself: *"typed by Claude as instrument at explicit 'go, take the lead' direction."*
