# spec-K6  -  the vex-corpus re-wire admission harness

> Frozen contract for the Knowledge track's re-wire question (K.4's open condition:
> "re-wiring vex-corpus needs dedup + VEX-validation + chunking first"). Grounded in
> a 4-probe recon + a live `vcc` smoke test on 2026-07-13; every factual claim below
> was verified against the real Houdini 21.0.671 install and the real vex-corpus corpus,
> not assumed. This document is the "why" the K.6 tasks + checks enforce.

## The reframe (first principles)

"**Whether to ever re-wire vex-corpus**" is unanswerable as a standing boolean  -  the
answer depends on the content, which changes every time vex-corpus runs. The answerable
question is per-entry: **"does *this* candidate earn a place in the RAG?"** Re-wiring is a
continuous **admission process** where the generator *proposes* and a gate *disposes*.
The harness makes that verdict cheap, deterministic, and repeatable; then "should we
re-wire this batch?" is a number the harness prints, not an argument.

## Why the last sync failed (root cause)

`vex-corpus/scripts/sync_to_synapse.py` validated **metadata only** (agent maps, category
refs, broken links) and **never inspected the code**. It trusted an unvetted generator
(tiny local Ollama models) and bulk-promoted straight into `rag/`. Three structural
absences  -  this is what K.6 closes:

| Absence | What shipped (verified, since pruned) |
|---|---|
| No **code validation** | `vector pts = pts[];`  -  broken VEX (`vcc` -> Error 1019) served as "how-to" |
| No **semantic dedup** (only exact-equality, sync_to_synapse.py:284-288) | ~304 near-duplicate variants of one snippet |
| No **chunking** | a 5,639-line file, whole-file-embedded (all-MiniLM caps ~256 tokens -> only ~2% encoded) |

The fix is not better prompts. It is an **adversarial admission gate between generator and
RAG**, and **quarantine-first promotion** so bad content can never reach retrieval at all.

## The ground-truth gate: `vcc` is "dir() is a hard gate" for VEX

SYNAPSE already refuses to trust model recall for `hou.*` (scout.py loads an introspected
33,255-symbol `dir()` table as the membership authority). The VEX analog is exact and
**confirmed present**: `vcc.exe` (Houdini's VEX compiler) at
`...\Houdini 21.0.671\bin\vcc.exe`, runs **headless, license-free, exit 0/nonzero**.

**Validator contract (verified live):**
- Translate `@attr` binds -> context globals (the 15 authoritative `sop` globals from
  `vcc --list-context-json=sop`: `Cd Frame N Npt P Pw Time TimeInc accel age id life
  pstate ptnum v`) or declared locals (prefix-typed: `f@`->float, `v@`->vector, ...; bare
  unknown -> float).
- Wrap as a context function: `sop\nwrangle(){ <decls> <snippet> }` (point/prim/detail/
  vertex all map to the single `sop` VEX context; shaders -> `surface`/`cvex`).
- `vcc.exe -o NUL wrapped.vfl` -> **exit 0 = admit, nonzero = reject**, capturing
  `Error <code>` from stderr. `-F/--Werror` for strictness.
- Empirically: `vector pts = pts[];` -> exit 251 Error 1019; undefined fn -> exit 42
  Error 1066; raw `@P` unwrapped -> exit 85 Error 1109 (why the translate+wrap step exists).

**Degraded tier (host-absent, no Houdini/vcc):** static-check each function call + attribute
write against a committed `vex_symbol_table.json` frozen from `vcc --list-context-json`
(1,023 sop functions + globals with read/write flags)  -  the exact VEX analog of
`h21_symbol_table.json`. Record which tier validated each admitted entry; **never silently
skip validation** (that is the original failure).

## The two-axis gate  -  asymmetric risk (the load-bearing insight)

- **Validity axis -> strict, reject freely.** `vcc` is deterministic ground truth; a
  non-compiling snippet has zero value.
- **Redundancy axis -> conservative, admit-then-FLAG, never silent-drop.** The cost is
  asymmetric: a wrongly-*rejected* net-new snippet is invisible and unrecoverable; a
  wrongly-*admitted* redundant one is flagged bloat  -  cheap, visible, prunable.

And the redundancy threshold cannot be guessed  -  recon **measured the corpus geometry**:
among the 103 deliberately-distinct rag/ files, nearest-neighbour cosine median **0.697**,
p90 **0.777**, max **0.901** (`rag_render_branch_convention <-> rag_render_usd_pipeline`,
both legitimately admitted). **Any hard-reject <= 0.90 nukes files the corpus itself deemed
net-new.** So on the current whole-file vectors, redundancy is a *flag*, not a gate  -  until
section-level embeddings exist (Phase 3).

## Architecture  -  a linear admission pipeline

Shape: **workflow orchestrator**, single script, one human gate. Level-2 durable (the
wait-state is ratification). Not multi-agent  -  no coordination problem, just a pipeline.

```
vex-corpus/output/corpus/merged_corpus.jsonl  (2,513 chunks; 2,083 carry code_blocks)
  0 INTAKE      normalize to {id, code, context, source}; DON'T trust its bugs/explanation
                (recon: same code yields bugs=[] in some runs, populated in others  -  unreliable)
  1 CHUNK       one candidate per code_block (atomic = unit of validate+dedup+embed)
  2 VALIDATE  * translate @attr->globals/locals, wrap, vcc compile; exit 0 = pass, else REJECT
  3 DEDUP       canonicalize (strip comments/ws + alpha-rename locals)->hash; then embed, collapse cos>=0.95
  4 REDUNDANCY  embed vs existing rag/; cos>=0.90 -> ADMIT-THEN-FLAG (never silent drop)
  5 SCORE       scorecard: in->chunked->compiled->deduped->net-new->admitted + sample rejects
  6 QUARANTINE  survivors -> staging store (NOT rag/) + provenance (source id, verdict, scores)
  7 RATIFY      <- human flips ratified:false->true (flywheel_queue pattern) after reading scorecard
  8 PROMOTE     copy to rag/ + one topic per chunk -> refresh_knowledge.py -> freshness gate green
```

Stages 0-6 are automated and structurally safe (nothing touches `rag/`). Stage 7 is the
only human gate. Stage 8 is entirely the existing **K.5** machinery.

## Reuse vs net-new (lean, solo-maintainable)

| Reused (already in SYNAPSE) | Net-new (build) |
|---|---|
| Quarantine = scout ephemeral-store pattern (`scout_ingest`) | `@attr->globals` translator + context wrapper |
| Ratify = `flywheel_queue.json` flip (D.0/R.0 pattern) | `vcc` compile-gate subprocess wrapper |
| Promote+verify = **K.5** `refresh_knowledge.py` + `check_semantic_index_fresh` | VEX canonicalizer (strip + alpha-rename) for dedup |
| Embed = K.1 all-MiniLM + `embeddings.npy` (103x384, L2-norm) | `vex_symbol_table.json` (frozen `vcc --list-context-json`) |
| Coverage/suite gates = K.2 + `suite_baseline` | scorecard + `check_rewire_*` gates |
| `type:"vex_function"` + `domain:"vex"` already in scout |  -  |

The promotion tail is done. K.6 only has to **produce vetted `rag/` entries**.

## Phases

- **Phase 1  -  Assessment (MVP, `scripts/rewire_assess.py`).** Chunk + `vcc`-gate +
  redundancy-flag + scorecard -> `harness/notes/rewire_assessment.json`. Read-only, writes
  nothing to `rag/`. **Answers the re-wire question with a number.** Runnable now.
- **Phase 2  -  Admission.** Only if Phase 1's usable-entry count justifies it. Add the
  alpha-rename dedup cascade, quarantine store, provenance, `flywheel_queue` ratify gate, and
  promote->K.5-refresh. Calibrate thresholds on the golden set.
- **Phase 3  -  Section-level embeddings.** Upgrade redundancy from *flag* to *gate* (fixes
  whole-file coarseness); also lifts K.1 retrieval quality corpus-wide (shared win).

## Failure modes

- **`vcc` absent** -> degrade to `vex_symbol_table.json` membership, loudly flagged; never skip.
- **Imperfect `@attr` translation** -> false-reject a valid snippet -> log wrap-fails
  SEPARATELY from compile-fails (a wrap-fail is a harness bug, not a verdict).
- **Redundancy false-reject** -> structurally mitigated by admit-then-flag.
- **vex-corpus's unreliable `bugs`/`explanation`** -> rebuild `searchable_text` from the
  *validated* code + deterministic template, don't trust the generator's prose.
- **Threshold drift on model change** -> version thresholds against `manifest.content_digest`.

## Acceptance criteria (the eval; golden set from recon)

- **G1 (safety):** no candidate reaches `rag/` without a recorded `vcc` exit-0 (or
  symbol-table pass). Force the broken snippet through -> must be rejected, must never
  reach `rag/`.
- **G2 (dedup calibrated):** the 304 known-variants collapse to 1; the corpus's own
  0.77-0.90 distinct pairs stay separate. Measured P/R/F1, zero false-merge on hard negatives.
- **G3 (gated promotion):** nothing auto-promotes; a human ratification flip is required.
- **G4 (no regression):** after promotion, K.2 coverage + K.5 freshness + `suite_baseline` green.
- **G5 (provenance):** every admitted chunk carries source id + validator verdict + scores.
- **G6 (decision):** the scorecard alone answers "how many usable entries would re-wiring add."

## The verdict is computable, not standing

K.4 is no longer "should we ever re-wire"  -  it is `rewire_assessment.json`'s
`usable_entries_estimate`. If that number is small (recon's evidence  -  ~65% redundant with
existing `joy_of_vex_*.md`, much broken  -  predicts it will be), the honest answer is "not
worth it as-is," reached by measurement in a day, not by shipping garbage. Re-run the
assessment whenever vex-corpus grows dedup + VEX-validation + chunking; the number is the
arming condition.
