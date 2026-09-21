# JEV-RERANK shadow (Site 2)

**Verdict header: unjudged.**

Producer: `python harness/jev/jev_rerank.py --shadow` · guard `rerank` · ledger `harness/jev/ledger/bp10.rerank.jsonl`.
Probes: 9 adversarial retrieval probes (`PREFLIGHT` + `REGRESSION_TOPICS`, `tests/test_knowledge_retrieval_repair.py`, read not invented). Top-12 hits per probe, scope order by `rag/retrieval/scope_weights.py`.

> **unjudged** — no `TYPESAFE_API_KEY`, so no `rel` was produced (fail closed, invariant 4: no fabricated probability). The `rel(top)` column reads `-`; the observable delta below is scope coverage (`#h22` / `#h21`). `precision@k` and `answer@1` need a judged run; the ledger carries a fallback row per phase.

## Before — H21-only corpus (baseline)

The rerank run with the H22 prose corpus excluded: every hit is `h21`. This is the "we have more text" baseline the after-table is measured against.

| probe | top scope | top hit | #h22 | #h21 | rel(top) |
| --- | --- | --- | ---: | ---: | --- |
| how do I blur an image in copernicus | h21 | Code | 0 | 12 | - |
| what parameters does the copernicus chromake… | h21 | Layer Data Access | 0 | 12 | - |
| how do I set up a karma render node in solar… | h21 | Code | 0 | 12 | - |
| how do I use the copernicus flip node | h21 | Code | 0 | 12 | - |
| how do I set the noise node in copernicus | h21 | Code | 0 | 12 | - |
| vex attribute wrangle | h21 | Code | 0 | 12 | - |
| tops wedge parameter sweep | h21 | Triggers | 0 | 12 | - |
| scene assembly merge reference | h21 | Code | 0 | 12 | - |
| what is the light intensity parameter name | h21 | Context | 0 | 12 | - |

## After — H22 prose corpus present (delta)

The same run with the generated `rag/corpus/h22_prose/` corpus included. Where h22 hits appear they lead (reference phrasing) per the scope table; `#h22 > 0` is the delta a judged run would grade for relevance. `#h22 = 0` everywhere means the corpus was not built before this run (build it with `hython rag/ingest/help_archive.py --build`).

| probe | top scope | top hit | #h22 | #h21 | rel(top) |
| --- | --- | --- | ---: | ---: | --- |
| how do I blur an image in copernicus | h22_prose | Environment variables | 12 | 0 | - |
| what parameters does the copernicus chromake… | h22_prose | Working with Copernicus nodes | 12 | 0 | - |
| how do I set up a karma render node in solar… | h22_prose | Karma Render Properties | 12 | 0 | - |
| how do I use the copernicus flip node | h22_prose | Environment variables | 12 | 0 | - |
| how do I set the noise node in copernicus | h22_prose | Environment variables | 12 | 0 | - |
| vex attribute wrangle | h22_prose | Graphs for viewport animation | 12 | 0 | - |
| tops wedge parameter sweep | h22_prose | Schedule and Execute using TOP | 12 | 0 | - |
| scene assembly merge reference | h22_prose | Component Builder | 12 | 0 | - |
| what is the light intensity parameter name | h22_prose | Scene Import LOP object translator | 12 | 0 | - |

## How to read this

A judged run (with a key) fills `rel(top)`; then `jev_grade.py --guard rerank` prints agreement against each probe's expected outcome (a no-answer probe must return no hit judged `answers`; an answerable probe's top hit should be `answers`/`on_topic`). The table tunes `scope_weights.py` by hand; the guard never edits it (no retrieval side effect).

