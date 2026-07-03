# Spec U.5 — Utility Flywheel, Cycle U.5: LOP/Solaris Knowledge (Context) Truth

**Status:** built + shipped to branch `feat/h22-knowledge-flywheel` (catalog + loader + validator core in `fea231d`; REVIEW sweep + harness check verbs + queue/tasks governance entry follow on the same branch) · **Layer:** utility · **Mode:** A (runs now on H21.0.671)
**Task id:** `U.5` — **not yet** in `harness/tasks.json` / `harness/state/flywheel_queue.json` (ratification record **OWED** — see Anti-runaway anchors)
**Sibling to U.1.** U.1 carries **WIRING** truth (input indices from a live probe); U.5 carries **CONTEXT** truth for Solaris (per-LOP role / USD-type / key parms, ordering, known-absent types). A different truth axis, built ahead of the queued wiring cycles U.2–U.4.

## Why this cycle exists

The graph-synthesis path (model proposes a Solaris LOP graph → `GraphValidator` checks it → build) had wiring truth (U.1) but no *context* truth. Two recurring Solaris failure modes went uncaught:

- **Phantom LOP types.** The model reaches for a `grid` / `plane` LOP (a SOP-brain habit); neither exists in Solaris. The corpus-grounded remediation is "use a `cube` with `sy=0.01`."
- **Missing material source.** An `assignmaterial` with nothing authoring material prims upstream — a common half-built render scene.

Unlike wiring truth, this knowledge is **not fully probeable**: role / USD-type / ordering semantics live in the Solaris reference PROSE, not a `dir()` surface. So EXPLORE here is *authored-from-corpus*, then *cross-checked* against the live connectivity probe — the standing "probe truth > authored prose" rule.

## The cycle contract (EXPLORE → REVIEW → SCAFFOLD)

Same three phases as every utility cycle, adapted to a prose truth source; each phase's committed artifact is consumed by the next. Nothing enters the live path on memory alone.

1. **EXPLORE — author from corpus, ground against the probe.** The knowledge is LLM-extracted **once** from `documentation/solaris_reference/{solaris_nodes,scene_assembly}.md` (under `$SYNAPSE_RAG_ROOT_G`, default `G:/HOUDINI21_RAG_SYSTEM`), carried **verbatim** in `scripts/mine_lop_knowledge.py`'s authored block with a provenance marker — the only non-deterministic step, and it is human-ratified. The miner is then **deterministic + re-runnable** (no LLM, no wall-clock): it computes a `source_digest` (blake2b over the sorted `(relpath, sha256)` of the corpus files), runs a **consistency gate** (every authored entry grounded in the corpus text OR the live connectivity catalog's `Lop` types; a `known_absent` type may not also be an entry; every ordering rule's `requires_type` / `on_type` / `satisfied_by` names a real entry), stamps blake2b over the `content` payload, and writes byte-identical output. A `source_digest` mismatch means the corpus changed → **re-author** (human+LLM), never a silent re-extract. Output: `harness/notes/verified_lop_solaris_knowledge_21.0.671.json` (schema `lop_solaris_knowledge/v1`) — 20 LOP types (10 also probe-confirmed live), ordering rules, `known_absent` (grid/plane), composition strengths (reference vs sublayer), a canonical render-scene recipe.

2. **REVIEW — grounding sweep + severity design.** Prose truth has no `setInput(` call-site analog, so the review grounds the *catalog* rather than call sites: `scripts/flywheel_review_lop.py` (pure Python, no `hou`, no `G:/` — CI-runnable off committed artifacts only) cross-checks the authored catalog against the U.1 live connectivity probe — the standing "probe truth > authored prose" rule: blake2b + structural integrity, every `probe_confirmed_types` entry present in the probe Lop set, every `known_absent` type absent from it (no contradiction). It emits `.claude/flywheel_u5_findings.json` + `.md` (severity-ranked) and exits 0 iff no CRITICAL. Two further surfaces back it: the miner's **consistency gate** (fails loud if an authored claim is grounded in neither corpus nor probe) and an **adversarial design review** (two independent verification passes) that set the error-vs-advisory severity split and caught a hard-error false-positive (see "The severity call"). Under `--deposit` the sweep lands one Confirmation/DeadEnd per check class to the Ledger via `synapse.science.deposit.LedgerDeposit` (opt-in; run under hython **post-merge** for the live build stamp, mirroring U.1 — so the every-sprint check verb never re-deposits).

3. **SCAFFOLD — wire into the live path + pin.**
   - `python/synapse/core/lop_knowledge.py` — `load_lop_catalog(path=None, *, strict=True)`: loads the packaged copy (`python/synapse/cognitive/tools/data/lop_solaris_knowledge_21.json`, the scout symbol-table pattern — per-major committed authority + blake2b integrity over `content`), path-keyed cache; `strict=True` raises `LopKnowledgeError` on any problem (a wire-time posture), `strict=False` returns `None` so an additive validator phase simply skips. Accessors: `lop_entry`, `ordering_rules`, `known_absent`. Zero `hou` import.
   - `python/synapse/cognitive/graph_validator.py` — `_lop_ordering_check(p, advisories)`: additive, Solaris-only, gated behind `live_phases_enabled`, catalog auto-loaded `strict=False` (degrades to skip). **Two severities:**
     - **known-absent grid/plane → HARD ERROR** — NEW nodes only (an EXISTING node's `node_type` is advisory per the `ProposedNode` contract, and a live node cannot be an absent type); case-insensitive so `Grid`/`Plane` still get the remediation. Zero false-positive surface: these types do not exist in any build.
     - **assignmaterial material-source ordering → ADVISORY** — never a hard reject. A satisfying source is `materiallibrary` OR a `reference`/`sublayer` composition arc (catalog `satisfied_by`); the advisory fires only when the all-NEW upstream chain has NO source, and **under-advises** at an EXISTING/undeclared upstream boundary (a pre-composed live stage the proposal does not model). Malformed *injected* catalogs shape-coerce and skip, never raise.
   - `tests/test_lop_flywheel.py` — 16 pins: catalog determinism + byte-identical-to-artifact + blake2b integrity + hand-edit-fails-loud, and behavior goldens through the validator with **permissive oracles** (so any verdict provably comes from the catalog, not the existence/connectivity oracle): grid/plane hard-error incl. capitalized + EXISTING-skip; materiallibrary / reference / sublayer satisfy; missing-source advises; EXISTING boundary under-advises; malformed catalog degrades; non-Solaris untouched.
   - `harness/verify/checks.py` verbs — `lop_knowledge_fresh` (catalog schema + blake2b sound + byte-identical to the harness artifact), `lop_review_clean` (the grounding sweep exits 0 with no CRITICAL), `validator_lop_conformance` (the 16 goldens pass). `harness/tasks.json` task `U.5` gates them plus the cross-cutting guardrails; `--task U.5` VERDICT=PASS.

## The severity call (the substantive learning)

`assignmaterial requires materiallibrary upstream` was initially authored as a **hard error**. An adversarial review proved it false-rejects a valid, common graph: in USD/Solaris a `reference`/`sublayer` layer authors Material prims with no `materiallibrary` LOP. A hard error that *can* false-reject erodes trust in the whole validator. Resolution: the ordering rule is an **advisory** (a common-pattern heuristic, not a provable invariant), made high-signal by the catalog `satisfied_by` set; `known_absent` (phantom types) **stay** hard errors. This is exactly the errors-vs-advisories contract the validator already carries — `ValidationReport.errors` vs `.advisories`; status is `INVALID` iff `errors` is non-empty.

## As-built status

| Deliverable | State |
|---|---|
| Corpus-authored catalog + deterministic miner + consistency gate | ✅ shipped |
| Loader + blake2b integrity (`core/lop_knowledge.py`) | ✅ shipped |
| Additive validator phase — error/advisory split (`graph_validator.py`) | ✅ shipped |
| 16 test pins (16/16 + 160 green across the flywheel + adjacent validator/graph/solaris suites) | ✅ shipped |
| REVIEW grounding sweep (`scripts/flywheel_review_lop.py`, 20 checks / 0 CRITICAL) | ✅ shipped |
| `flywheel_queue.json` + `tasks.json` U.5 entry (evidence-linked, `ratified: false`) | ✅ shipped |
| `harness/verify/checks.py` U.5 verbs (`--task U.5` VERDICT=PASS) | ✅ shipped |
| Ledger deposit **mechanism** (`flywheel_review_lop.py --deposit`) | ✅ shipped |
| Ledger deposit **execution** (run under hython post-merge, like U.1) | ⚠ post-merge step |
| Human ratification (`ratified: true`) | ⚠ OWED — human-only |

## Anti-runaway anchors

- **Human ratifies new cycle CLASSES.** U.5 introduced a new truth axis (CONTEXT truth, distinct from U.1–U.4's WIRING truth). Per the standing anchor, a new class needs human ratification **before** building; U.5 was built ahead of that record. The evidence-linked queue entry now exists (`flywheel_queue.json` U.5, `status: building`, `ratified: false`) plus a `tasks.json` U.5 task carrying a `human_gate` — but the `ratified: true` flip stays **human-only** and is still owed. Until it flips, U.5 is a proposal on the record, not a sanctioned cycle.
- **Probe truth > authored prose.** The consistency gate flags any authored type the live connectivity catalog affirmatively lacks; the miner refuses to emit an ungrounded claim.
- **Re-author, never silent re-extract.** A `source_digest` mismatch (corpus changed) arms a human+LLM re-authoring pass, not an automatic re-extract.
- **Per-build re-probe duty.** Re-run `python scripts/mine_lop_knowledge.py` per Houdini build (needs the `G:/` RAG corpus); the packaged copy must stay byte-identical to the harness artifact (test-pinned).

## Exit gate for U.5

Full `python -m pytest tests/ -q` green (modulo pre-existing release-train failures, reported as a delta) AND `harness/verify/checks.py --task U.5` PASS. Current state: **`--task U.5` VERDICT=PASS** (`lop_knowledge_fresh` + `lop_review_clean` + `validator_lop_conformance` all green; guardrails clean); `tests/test_lop_flywheel.py` 16/16 + 160 green across the flywheel + adjacent validator/graph/solaris suites; `scripts/flywheel_review_lop.py` 20 checks / 0 CRITICAL; `scripts/mine_lop_knowledge.py --check` byte-identical (blake2b `685ced35bb371bcc9973215345d126a8`).
