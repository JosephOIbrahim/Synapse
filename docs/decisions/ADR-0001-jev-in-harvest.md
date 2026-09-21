# ADR-0001: Jev Integration on the Harvest Residual

**Date:** 2026-09-21  
**Status:** Accepted  
**Authors:** Joe Ibrahim (Creative Director), SYNAPSE CTO (Fable 5.1)

## Context

The Jev model (TypeSafe System One, jev-1.13.0) is a specialized LLM for typed classifications at scale: Choice, Noul, and Score primitives, returning calibrated probabilities over JSON state. It costs $0.042 per million input tokens and runs in 330–575 ms per guard.

The SYNAPSE harvest pipeline contains decision points currently handled by hand reads, heuristics, or exact checks. This ADR describes where Jev sits and what it does not do.

**Related documents:**
- JEV_HARVEST_BLUEPRINT.md — implementation guide
- jev-opportunities-2026-09-20 review — discovery
- JEV_BLUEPRINT.md section 4 — invariants

## Decision

**Jev sits beside the harvest gates on the residual, shadow-first, through two existing doors, and never promotes a chunk.**

Three build-time Jev guards (harvest, rerank, bench) operate in the grey band after exact checks are exhausted. They never move items from quarantine to corpus; they sort quarantine so a human reads likely renames first and likely phantoms last.

The principle: *"anything a regex, catalog lookup, symbol table, or hash answers stays an exact check."*

## Sites

### Site 1: Harvest gates (token triage + tool-fit)

When G2 quarantines a guide for a failed backticked token, Jev classifies the token (node rename, parameter name, attribute, VEX/expr, or plain word). For tool references, Jev judges whether the SYNAPSE equivalent would keep the sentence achievable.

Code first: symbol-table lookup, parm/attribute names, difflib at 0.85. Only residual reaches Jev (~40 tokens from 31 guides).

Lives in: `harness/jev/jev_harvest.py`, `questions.json` entry `guards.harvest`.

### Site 2: Retrieval rerank (scope scoring)

Harvests hand-tunes `scope_weights.py` (guides for how-to, prose for reference, H22 above H21). Jev scores top-12 retrieval hits on 25 adversarial probes, producing precision@k per scope. The table is still read by hand; the number tunes it.

This is review item 3.2 extended to new scopes.

Lives in: `harness/jev/jev_rerank.py`.

### Site 3: Benchmark verifier (failure classification)

`verify.py` tells pass from not-pass with `hou`; it cannot tell why. Jev classifies failure (refusal, attempted-and-failed, falsely-claimed-success, asked-clarification) from final text. UNKNOWN count is reported at observation time; Jev illuminates what "not-pass" meant.

Lives in: `harness/jev/jev_bench.py`, consumed by `harness/outside_in/verify.py`.

## Refused Sites

1. **Should a chunk leave quarantine?** No. Jev sorts, never promotes. Quarantine is policy.

2. **Is this under a licence SYNAPSE may commit?** No. Legal policy, not a judgment call.

3. **Did the benchmark check pass?** No. Exact, boolean predicate.

4. **Is the stamp current?** No. String compare between builds.

## Invariants Inherited

All three guards inherit six invariants from `python/synapse/jev/adapter.py` (tests/test_jev_product_boundary.py).

- No product code imports `harness/jev`
- No Jev answer grants consent, names a model, or writes a scene
- Ledgers live under `harness/jev/ledger/`
- Failures return `None`, fallback output unchanged

## Consequences

1. Gates G1–G6 pass/fail identically with or without Jev
2. Every guard runs shadow before it arms
3. Cost ~$0.003–$0.05 per full run
4. Fail-closed is documented
5. Future decisions bounded by this placement map

## Producer Paths

| Deliverable | File | Phase |
|--|--|--|
| Three guard stubs | harness/jev/questions.json | BP10 scaffold |
| Harvest code | harness/jev/jev_harvest.py | BP10-GUIDES |
| Rerank code | harness/jev/jev_rerank.py | BP10-CORPUS |
| Bench code | harness/jev/jev_bench.py | BP10-BENCH |
| Answer keys | harness/notes/harvest/ | Per shadow run |
| CI wiring | pyproject.toml, ci.yml | BP10 scaffold |
