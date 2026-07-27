# v5.36.0 — the claim was wrong, and now the numbers are in the repo

*A demo release. One crash fixed, one central claim refuted and replaced with a measured one, and the evidence committed alongside it.*

---

## The tool that could kill a session

`houdini_network_explain` **segfaulted hython on large scenes** — `rc=139`, reproducible, on `karma_user_guide.hip`, the largest scene SideFX ships. It died inside `_get_non_default_params` evaluating material-assignment parms against the composed stage.

A segfault takes the interpreter with it. No error, no graceful degradation, no unsaved work.

**Fixed by not evaluating.** String parameters now read `rawValue()` — the authored value — rather than `eval()`, which resolves paths against the stage. For a function whose job is *"what did the artist change from default,"* the authored value is arguably the better answer, and expressions were already reported separately.

**Verified on the same scene:** 130 `/stage` children, 28 material-assignment LOPs, 1,493 non-default parms, 1.2 seconds, exit 0.

**And an unbounded exponential alongside it.** `_recurse_inputs` had no visited set, so any diamond — universal in SOP networks — re-serialised the same subgraph once per path. A 22-node diamond emitted 4,094 records at depth 11. The depth argument was agent-supplied and clamped nowhere. Now a visited set and a hard cap of 5, matching its sibling rather than inventing a number.

---

## The central claim was wrong

The positioning said:

> *"Sends only what changed — cost stays flat, even on huge scenes."*

**Both halves fail, and the second is worse.**

**Cost is not flat.** Grounding payload rises **443 → 113,411 tokens** across a 13 → 25,850 node ladder. That is **256×**. The same probe without depth bounds rises **2,788×** — so the advantage is real, but "flat" does not describe a 256× curve, and any studio would find that in an afternoon.

**"Sends only what changed" has no mechanism.** There is no delta path anywhere in the grounding surface. Every inspect is a full re-read. A quantitative claim that overstates is a calibration error; a mechanism claim for machinery that was never built is a different kind of wrong.

### What replaces it, and why it is harder

The advantage is **reduced coverage, not tighter encoding.** Single-call scene coverage by rung: **100, 100, 73, 51, 10, 11 percent.**

SYNAPSE is cheaper on large scenes because it *sees less of them* — with 100% completeness inside the window it reads.

> **Cost scales with what you ask about, not with the size of your scene.**

That is testable, it is true, and it has to be stated together with the coverage number.

**What this release does NOT establish:** no live-model arm exists — the API account had no credits, so all figures are proxy-tokenizer measurements. And no genuine outside-in comparison was built; both wide-margin arms are SYNAPSE measured against itself. The comparative half of the claim remains open in both directions.

---

## Also corrected

**The render-node refusal claim was overstated.** `hou.isUIAvailable()` gates the daemon — the Fork Bomb guard is real — but it protects a component with no production callers today, while other surfaces boot headless. The repository had previously shipped the correctly-scoped version of this claim and replaced it with a broader one. The narrow version is back.

**Seven version locations now agree**, enforced by a check that runs in the release path and fails on an unfixed tree.

**Install traps documented.** A UTF-8 BOM on the package file makes Houdini reject it silently. So does `path` instead of `hpath`. So does a `PYTHONPATH` missing the repo root. All three end the same way: `import synapse` succeeds, the version prints, and the panel never appears.

---

## Known limitations

Unchanged and stated plainly: the PDG rollback still raises `TypeError` on every call. Emergency halt is still unsurfaced in the panel. 41 node types in use are deprecated, 39 invisible to a runtime probe. Node grounding is 18.3% LOP and 6.2% Copernicus — 37.9% of LOP parameters is the realistic ceiling from documentation alone. Six shipping dependencies are not vendored.

---

## Verifying any of this

```
python harness/verify/version_agreement.py     # seven locations
python harness/verify/bom_audit.py             # every JSON, VERSION included
python scripts/c1_token_bench.py               # the ladder
python harness/notes/_segfault_repro.py        # under hython, on the real scene
```

Each fails on an unfixed tree. That was demonstrated before any of them was trusted.

**House rule:** no number enters a document without a producer path beside it. The token figures above cite `harness/notes/token_bench/`, which ships in this release for that reason.
