# Wave-3 memory wave — receipts index

**Wave:** wave3 ("Moneta materialization") · **Source:** `docs/SYNAPSE-memory-blueprint.md`
(§4 phases 0–6, S5 acceptance, S6 guardrails) · **Base:** `5e933c13`
(`fix/memory-store-recovery` tip == wave-3 base) · **Compiled:** 2026-08-13 by W3-PAPER.

This is the durable provenance ledger for the wave. It is **not** a merge verdict — the
whole-wave gate is W3-CRUX (`BLOCKED`; substance sound). Merge is Joe's word, per act.

## Read this first — the wave's durability state

**7 of the 7 builder legs are committed** (DIM, VEC, STORE, KIND, EVOLVE, MIGRATE, HARDEN),
each with its `W3-<LEG>.json` receipt committed in-tree on its own branch — the five that
were still at base during early recon committed their named files at **16:47 on 2026-08-13**.
The **only** uncommitted leg is the **CRUX gate** (`wave3/crux @ 5e933c13`, `W3-CRUX.json`
still untracked) and this **PAPER** leg. So the builder-leg durability gap is closed; what
remains is committing the CRUX gate receipt and — the real gate — **merge**, which is Joe's
word. W3-PAPER cannot commit peer work; each leg owns its own commit.

> **Provenance note (staleness caught):** an early W3-PAPER draft mirrored the W3-CRUX
> receipt, which was grounded before those five legs committed and recorded them at base.
> An adversarial re-derive from git corrected it to the state below. Doctor/git is the
> source of truth, not a same-day snapshot.

## Legs

| Leg | Blueprint phase | Status | Committed? | Branch tip | Receipt (canonical) |
|---|---|---|---|---|---|
| **W3-DIM** | 0 · honest signal (dim authority) | green_with_findings | ✅ yes | `wave3/dim @ 16cf1543` | `harness/notes/receipts/W3-DIM.json` (committed) |
| **W3-STORE** | 1 · materialize store (dual-write) | green_with_findings | ✅ yes | `wave3/store @ e8b691de` | `harness/notes/receipts/W3-STORE.json` (committed) |
| **W3-KIND** | 2 · typed schema + kind routing | green_with_findings | ✅ yes | `wave3/kind @ a82492a3` | `harness/notes/receipts/W3-KIND.json` (committed) |
| **W3-VEC** | 3 · derived vector recall | green_with_findings | ✅ yes | `wave3/vec @ 6600295b` (code `a7112bd1`) | `harness/notes/receipts/W3-VEC.json` (committed) |
| **W3-EVOLVE** | 4 · consolidation dry-run/approve | green_with_findings | ✅ yes | `wave3/evolve @ c2bedf31` | `harness/notes/receipts/W3-EVOLVE.json` (committed) |
| **W3-MIGRATE** | 5 · migration parity + cut-over | green_with_findings | ✅ yes | `wave3/migrate @ 0c87a835` | `harness/notes/receipts/W3-MIGRATE.json` (committed) |
| **W3-HARDEN** | 6 · production hardening (concurrency) | green_with_findings | ✅ yes | `wave3/harden @ 1b8d1e80` | `harness/notes/receipts/W3-HARDEN.json` (committed) |
| **W3-CRUX** | crucible gate | blocked (durability) | ❌ no | `wave3/crux @ 5e933c13` (== base) | `.claude/worktrees/w3-crux/harness/notes/receipts/W3-CRUX.json` (working-tree, untracked) |
| **W3-PAPER** | paper (this leg) | — see receipt | (this branch) | `wave3/paper` | `harness/notes/receipts/W3-PAPER.json` |

Commit state re-derived 2026-08-13 via `git rev-parse wave3/<leg>`,
`git rev-list --count 5e933c13..wave3/<leg>`, and
`git ls-tree -r wave3/<leg> -- harness/notes/receipts` (each committed leg returns 1 commit
past base with its `W3-<LEG>.json` blob present); `git cat-file -e` on each committed receipt
succeeds; each committed receipt blob is byte-identical (sha1) to the sibling worktree file.
`wave3/crux` alone returns 0 commits past base with `W3-CRUX.json` untracked.

## Per-leg one-liners (observed scope; anchors in each receipt)

- **W3-DIM** — one dim authority read from the active embedder; stale snapshot re-embedded
  from source before hydrate, so a provider change rebuilds derived vectors, not fallback.
  Live seat degraded by the pre-fix bug *today* (`moneta_substrate=fail`, dim 384≠256);
  live `moneta_substrate=ok` conjunct honestly **UNKNOWN** (schema-registration lane +
  restart-gated). `moneta_store.py:266`.
- **W3-STORE** — authored `cortex_root.usda` (typed `MonetaMemory` root); `add` dual-writes
  cortex + JSONL net byte-for-byte, no moneta-only path. `in_use=True` is real, but overall
  `moneta_substrate` stays `fail` (`schema_registered=False`, DEAD BYTES). `moneta_store.py:550`.
- **W3-KIND** — additive typed schema (`decision`=reasoning+alternatives, `task`=status) +
  kind routing via `store.get_by_type` (jsonl by-type index; Moneta per-kind non-scan is
  STORE cortex territory). `tracker.py` wiring is a scope-glob (for_ruling). `store.py:708`.
- **W3-VEC** — derived NN recall as a new module `vector_recall.py`, ranked with **real
  cosine scores**, dim read from provider, rebuildable-from-source (index never truth). Tool
  wiring (`synapse_recall`) is a held spawn — not reachable via the tool yet. `vector_recall.py`.
- **W3-EVOLVE** — charmeleon→charizard consolidation: dry-run `plan_consolidation` is pure;
  `apply` refuses without a plan-bound token, backs up all memories first, unions survivor
  fields before pruning, never prunes protected. Real-Moneta apply raises
  `ConsolidationUnsupported` (deferred). `consolidation.py`; `handlers_memory.py:389`.
- **W3-MIGRATE** — JSONL→Moneta copy-and-verify: hard backup gate (sha256, sources
  byte-untouched), keep-both id-preserving exporter, disk-independent parity + spot-checks,
  `WriteThroughStore` net. No source-write primitive exists. Go-live human-gated (needs DIM +
  STORE). `migrate.py`; `writethrough_store.py`.
- **W3-HARDEN** — crash-recovery (process-kill-durable, not power-loss), concurrency
  (single-owner in-process; **cross-process CLOBBER carried**), store-level `write_plane`
  truth, non-mutating evolve dry-run. All 4 predicates PASS, 5 skeptics CONFIRMED.
  `write_plane.py`; `doctor.py`; `moneta/api.py:199` (F1).
- **W3-CRUX** — read-only adversarial gate over all 7 legs: per-leg CLEAR/BLOCKED + whole-wave
  verdict. Substance sound; wave BLOCKED (durability — the gate receipt itself is uncommitted
  and nothing is merged). Both failure classes (silent-fallback-claiming-moneta;
  data-loss-in-migration/consolidation) re-attacked and **CLOSED**. Live doctor honest.

## Failure classes re-attacked (W3-CRUX)

- `silent-fallback-claiming-moneta` — **CLOSED**, absent on the live seat (fallback is loud:
  `served=jsonl` reported, doctor `fail`, downstream skipped-not-faked). Re-confirmed by a
  first-party `synapse_doctor` probe 2026-08-13 (`fail=1, ok=8, skipped=4`).
- `data-loss-in-migration/consolidation` — **CLOSED** in-scope; two carried risks named
  (cross-process snapshot clobber; `_union_into` drops differing non-empty scalars — both
  recoverable / bounded, both receipted, neither silent).

## Coordination provenance

All claims/findings/releases for this wave are on the shared wave3 bus
(`harness/autorevise/bus.py post/read/claims wave3`). W3-KIND↔W3-STORE contested
`moneta_store.py`; resolved at source (KIND took no `moneta_store.py` edit). W3-PAPER's
own claim covers `docs/` + `harness/notes/` only — disjoint from every peer claim.
