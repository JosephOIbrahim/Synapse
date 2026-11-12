# Recall on natural phrasing: semantic fallback, no false hits

**Status:** plan only. Building starts after the 2026-10-07 demo.

**Goal:** an artist asks about a decision they recorded, in their own words, and recall finds it. Today, at scope=project, it finds 68 to 72% of unseen questions. The target is about 90%, with **zero false hits** as the hard rule.

---

## What is true today

Three read-only scouts checked these on 2026-10-07 against the demo tree at `9a48be51`. The files cited below are unchanged at `b78abfb0`. Evidence and probe scripts are in the run folder, not in the repo.

### Recall's matcher is lexical; vectors reach the tool only through the scope=all knowledge augment

- `synapse_recall` goes handler → `tracker.handle_memory_recall` → `SynapseMemory.recall` (`python/synapse/memory/store.py`, around line 2069).
- It matches folded words: filler dropped, word forms folded, a few synonym groups, and a coverage guard that returns nothing when a key word appears in no record.
- `SynapseMemory.recall` never calls the embedder. The vector search in `MonetaBackedStore.search` (`python/synapse/memory/moneta_store.py`, around line 1188) serves `synapse_search`. It also serves the knowledge augment, which `synapse_recall` runs at its default scope=all, and that augment is where the scope=all false hits come from.

### Where it stands

| Measure | Result | Source |
|---|---|---|
| Unseen (held-out) questions, scope=project | 17-18 of 25 (0.68-0.72) | recall eval at `a71eca94` |
| False hits on held-out negatives | 0 of 5 | same |
| Demo lines | 22 of 22 | same |
| Held-out at scope=all | false hits 5 of 5 | same, all from the knowledge augment |

**Why the rest miss:** of the 7 (jsonl) or 8 (moneta) misses, 5 are true synonyms, 1 uses a word recorded in no deposit, and 1 or 2 return a neighbouring record first. Word matching cannot bridge the synonyms.

### The semantic embedder has never served a real vector

- `SemanticEmbedder` (`python/synapse/memory/embedding.py`) reads `~/.synapse/models/minilm-l6-v2/model.onnx` and `tokenizer.json`. Neither exists on the dev machine.
- **With the model present it still fails.** The model's input shape is dynamic, so a size check raises `TypeError`. `embed()` catches it and returns a hash vector, while `.backend` reports `onnx`.
- **`scripts/download_embedder_model.py` provisions the wrong place.** It writes `<repo>/models/minilm-l6-v2.onnx`, not the folder and filename the embedder reads, and never fetches `tokenizer.json`.
- **So every stored vector today is a hash vector stamped with the MiniLM id.** Turning on the real model without a per-vector backend stamp would mix two 384-dimension spaces, and the dimension guard cannot see it.

### Vectors alone cannot keep zero false hits

- Real all-MiniLM-L6-v2, top-1 only, on the shared question set: 53 of 65 (0.815). Lexical recall gets 60 of 65 on the same set, with 1 false hit in 20 negatives, but its synonym and filler lists were tuned on this set's misses, so that score is in-sample.
- The highest cosine on a negative is 0.51. The 10th-percentile cosine of a true answer is 0.335. No single threshold separates them.
- **Vectors help as a second chance, not as a replacement.**

### The current test set cannot prove 90%

- 25 held-out questions over 12 deposits. To pass 90% it needs 23 hits; a true 90% recall passes that only about half the time.
- Telling 85% from 90% needs roughly 280 to 360 questions.
- 0 of 5 negatives only shows the false-hit rate is under 45%. Showing it is under 1% needs about 300 negatives.
- The held-out miss categories were posted where builders read, so that set is partly used up.

### Cost and placement

- Recall runs on Houdini's main thread (`run_on_main`).
- One MiniLM embed: about 7 ms (quint8) to 10 ms (fp32) using all cores, 24 ms (fp32) on one thread. Model load about 125-150 ms and the first embed about 225 ms, so warm it off camera.
- Moneta's vector scan is pure Python: about 230 ms per query at 10,000 memories, against about 2 ms with a numpy matrix.
- `backfill.re_embed` appends rather than replaces, so it doubles the store.

### Shipping the embedder

- Houdini 22.0.400's Python has numpy 2.3.2 but no onnxruntime or tokenizers.
- Vendoring `onnxruntime` 1.30.0 + `tokenizers` 0.23.2 (+ `flatbuffers`, `protobuf`) with `--no-deps` is about 57 MB unpacked and imports cleanly in hython. **Without `--no-deps`, pip pulls numpy 2.5.3, which would shadow Houdini's numpy.**
- The real shipping slot is `python/synapse/_vendor`, filled from pinned wheels by `installer/build_payload.py`. `.hython_deps` on the dev machine is not a shipping mechanism.
- Model files: fp32 `model.onnx` 90.4 MB, quint8_avx2 23.0 MB (needs an AVX2 CPU), `tokenizer.json` 0.47 MB.

---

## Decisions

Jev (TypeSafe) made these from the facts above. Two planted control questions came back correct, so the code accepted its answers (a failed control would have sent every call to Joe). The ledger is in the run folder.

| Question | Answer | Jev probability for this answer (scope=all row: probability of yes) | Status |
|---|---|---|---|
| **How vectors join recall** | Lexical first. Only when it finds nothing, take the nearest vectors and accept one only if it clears a cosine margin over the runner-up **and** a second check agrees | 1.00 | Decided |
| **What comes first** | Truth first: a real or loudly failing embedder, a backend stamp per vector, and a sealed larger test set, before any ranking change | 1.00 | Decided |
| **Which model to propose** | fp32 all-MiniLM-L6-v2 (90 MB), the same model and precision as Scout's index | 0.97 | Proposed to Joe |
| **What passing means** | On a sealed set of about 300 questions and 300 negatives: 95% lower bound of hit rate at least 0.85, and 95% upper bound of false hits at most 1% | 0.98 | Proposed to Joe |
| **Also fix scope=all false hits here** | Yes | 0.80 | Proposed to Joe |

## Joe's calls before building

1. **The dependency.** About 57 MB of vendored packages plus the model on every seat. This changes the installer payload.
2. **Where the model comes from.** Shipped in the installer (works offline, +90 MB) or fetched at first run by a SHA-pinned script into `~/.synapse/models/minilm-l6-v2/`.
3. **The pass bar.** The bound-based gate above, or a different one.
4. **scope=all.** Making `found` mean "a remembered decision matched" changes what `tests/test_recall_rag_seam.py` pins today (a knowledge-only hit reports found=true). Existing tests are not edited without your ruling.

---

## Phases

Each phase ends at a gate. A phase that fails its gate stops the plan there.

1. **Truth (about 2 hours).**
   - The embedder accepts the model's dynamic input shape, and any failure is loud: no silent hash fallback behind an `onnx` label.
   - Each stored vector carries the backend that made it. A store with hash vectors is re-embedded or refused, never mixed.
   - Fix the download script's path, filename and tokenizer. Pin the model by SHA.
   - The ONNX session uses the CPU provider only, with a bounded thread count.
   - **Gate:** a test that fails today proves a real vector is produced or an error is raised.
2. **A sealed test set (about 2 to 3 hours).**
   - About 300 questions and 300 negatives over **new** deposits. Half the negatives share words with real decisions.
   - Written by an agent that never sees the recall code. The file's SHA is recorded before any run.
   - The evaluator reports totals only, never items, and nothing goes on a board builders read.
   - The current 25-question set moves to the development pool.
   - **Gate:** baseline numbers for today's lexical recall on the sealed set, with confidence bounds.
3. **The semantic fallback (about 3 to 4 hours).**
   - Lexical recall answers first, unchanged.
   - When it finds nothing: nearest vectors from a numpy matrix cached per store, a cosine margin over the runner-up, and a second check (a shared content word, or a small yes/no verifier).
   - **Gate:** the pass bar on the sealed set, and no change on the 22 demo lines.
4. **scope=all (about 1 hour, after Joe's ruling).** `found` reflects remembered decisions only; knowledge rows stay as context.
5. **Re-embedding without doubling (about 1.5 to 2 hours).** Replace vectors in place, keep one copy per memory, and record the backend stamp.
6. **Shipping (about 2 hours, owner gate).** Vendor `onnxruntime` and `tokenizers` with `--no-deps` through `build_payload.py` and the toolchain lock, and provision the model the way Joe chooses.
7. **Live check (about 1 hour).** In isolated hython 22.0.400: deposit, save, clear, load, recall with paraphrases, timing on the main thread, and a cold-start warm-up.

**Total: about 12.5 to 15 hours of build, so two sessions.** Phases 1 and 2 can run in parallel.

**Honest odds.** Pure vectors scored below lexical on the shared set, so the fallback has to earn every point it adds. Reaching a 0.85 lower bound with all-MiniLM-L6-v2 is uncertain. If it plateaus, the next lever is the verifier in step 3, or a stronger model measured on the development pool only.

---

## Rules for the build

- **Zero false hits is the hard rule.** A change that raises the hit rate and adds a false hit does not ship.
- **The sealed set is never read by a builder.** Only its totals are reported.
- **Nothing is installed into Houdini's own folders.** Vendored packages go in `python/synapse/_vendor`, always with `--no-deps`.
- **No embedding or vector scan adds a visible stall on the main thread.** Measure it.
- **Every new test fails on the code before it. No existing test is edited without Joe's ruling.**
- **Merging is Joe's call.**
