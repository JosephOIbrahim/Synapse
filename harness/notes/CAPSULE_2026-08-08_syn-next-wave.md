# CAPSULE — 2026-08-08 · SYN-NEXT wave (closed)

## Position
- `master` = `origin/master` = **619d28a8**. Tonight's commits: `bf3c25ea` (SYN-NEXT-001
  adopted, five amendments integrated inline) → `c073af0` (§10 intake adjudication appendix)
  → `619d28a8` (reconciliation **RATIFIED**).
- **SYN-NEXT-001 is the governing blueprint of the next-system program** (E1). Bridge doc
  `docs/RECONCILIATION_SYN_NEXT_001.md` is in force (E4). Program board = W0 + Track A
  (W4/W5) + Track B (W6); G1–G9 stay under the H22 gap blueprint (E3).
- **Support target = 22.0.400** (E2, delegated pick, evidence-locked). Pin of record stays
  22.0.368 until the W9 re-stamp verifies 400. `drop.json` rewrite = Joe's file-write, after.
- Intake §10 first real exercise: **7 ADOPT / 4 ADAPT / 1 CORRECT / 0 REJECT**, C1+C3 clear.

## Decisions made (do not re-litigate)
- The four rulings above, plus adoption itself.
- **A4 rewritten:** dated historical receipts retained + declared; live support claims must
  match the current pin; pin counts are scope-declared. Zeroing provenance is prohibited.
- **W1.5 = regression guard**, not current-state fact (PR #60 made fallback loud 2026-08-01);
  runtime probe confirms present state before any claim.
- **Gate discipline:** blanket pre-approval invalid; a batch of enumerated, specified rulings
  is valid; push/merge take per-act words; `drop.json` and `ratified` flips are human-only.

## Tomorrow's stack (in order)
1. **W0 — `hotfix/v5.44.1-release-truth`.** Fresh session. `scripts/sync_version.py`, root
   `VERSION` canonical, refuse-dirty-tag gate. Done when every surface reports 5.44.1 and
   `test_phase0c_doc1_version_conformance.py` passes pre- and post-tag.
2. **W9 re-stamp on 22.0.400** under the new A4 (historical vs live). Then Joe rewrites
   `drop.json` — human file-write, single-writer.
3. **Phase-1 debris ruling:** `$null` · `harness/tidy/*` · `harness/notes/*` (incl. tonight's
   runners, logs, this capsule) · `OPERATOR_CARD.md.bak` · `models/` · `shot_layers/`.
   `GITIGNORE_PROPOSAL.md` already drafted in-tree.
4. Then **W1 Moneta recovery** per the ratified sequence — memory stays the P0 merge priority.

## Gotchas / operational state
- DC dropped 2× tonight; the launch shape that survives it: detached `Start-Process` runner +
  log file + watcher (`harness/notes/run_*.ps1`, `watch_intake.ps1`). Resume = read-then-append.
- `claude -p` is **non-streaming**: total silence until the full result lands. Not a stall.
- The relay in MODE B drives drop-week; intake must be invoked directly (`h22-intake`), never
  via relay args — they're inert in MODE B.
- 22 agent files vs the roster's 10-cap: observed, unreconciled — orient/gatewarden business.
- Console mojibake on §/– is decode-side; the write path is hash-proven byte-clean.

## Artifact map
- `docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md` @ bf3c25ea · `docs/intake/adjudication-syn-next-001.md`
  @ c073af0 · `docs/RECONCILIATION_SYN_NEXT_001.md` @ 619d28a8 (§6 = rulings record)
- Scratch (debris-ruling pending): intake + relay logs, `run_*.ps1`, `watch_intake.ps1`, this file.

*Open ritual for next session: read this capsule → connect DC → `git status` → wait for direction.*
