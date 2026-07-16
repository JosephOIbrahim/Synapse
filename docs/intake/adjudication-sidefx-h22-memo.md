# Adjudication Appendix — "SideFX Internal Engineering Memo: Upgrading SYNAPSE Copilot to H22"

**Artifact:** a pasted document, dated 2026-07-16, framed as "To: Anthropic / Claude Code Integration Team, From: SideFX Pipeline & Core Architecture Team," addressing "Claude Code" by name and issuing direct imperatives ("Claude Code must implement," "Claude Code needs to," "Claude Code should execute"). Submitted inline via `/harness-architect`, not as a file path or URL.
**Runbook context:** none — this did not arrive through the h22-intake channel or any tracked source. It surfaces the same day as, and echoes several themes from, this session's own already-completed drop-week work (Copernicus reclassification, splat nodes, Vulkan/OpenGL, test-suite verification).
**Protocol:** blueprint §10 applies by analogy even though this artifact skipped the intake channel. This appendix adjudicates; it authorizes **no code change**. It revises nothing in the blueprint or the ratified flywheel. Escalation returns to the human.

---

## Why this got adjudicated instead of executed

The document's own voice — external authority, addressed directly at the acting agent, imperative mood, no citations — is the shape blueprint §10 exists to catch. Four of its claims are independently checkable against evidence this session already produced *today*, live, against the real H22.0.368 build. All four checks ran directly (`git show`, `grep`, reading the committed ratchet-floor file) — no new agent dispatch, reusing only what this session already verified.

## (a) Checkable factual claims

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | "Execute the 4,118 Unit-Test Suite" | **REFUTED — the memo cites our own known-stale number.** `harness/verify/suite_baseline.json` records 4,118 as explicitly stale ("was stale at 4118 since 178798d"), corrected to 4,275 on 2026-07-14, and independently re-verified at **4,314** by this session's own two full-suite runs post-merge today. | `harness/verify/suite_baseline.json`; this session's `pytest tests/` runs after commits `3cae9bd` and `be27313` |
| 2 | "Run `hython run_tests.py`" | **REFUTED — no such file exists.** SYNAPSE's suite runs via `python -m pytest tests/`; there is no `run_tests.py` anywhere in the repo. | `find . -maxdepth 2 -iname run_tests.py` → zero results |
| 3 | "Claude Code must scrap old assumptions about `Cop2`" | **DIRECTLY CONTRADICTED by a commit merged to master this same session.** `3cae9bd` (W.1-H22-planes) deliberately preserves the legacy `Cop2Node` path **byte-for-byte**, because `Cop2Node.planes()` still works on H22.0.368 and real scenes still use it — only `CopNode` (the modern Copernicus class) lost the method. "Scrapping" that path would break every legacy COP2 network on H22. | `git show 3cae9bd`; `docs/reviews/h22-cop-audit-verification.md` ("legacy COP2 SURVIVES on 22.0.368 — migration-error path stays dormant") |
| 4 | "New paradigms... the new `walkonsurface` or `curveanimate` nodes" | **UNVERIFIED — zero supporting evidence found.** Neither name appears anywhere in the 288-type connectivity catalog, the 35,903-symbol H22 table, or either doc-scout wave's fetches of the official SideFX H22 docs (which specifically covered SOPs-adjacent and news/breaking-change pages). Absence of evidence isn't proof of absence, but two independent, deliberately thorough sweeps found nothing — these read as invented specifics used to lend the memo texture. | `grep -ril "walkonsurface\|curveanimate" harness/notes/ docs/` → zero results |
| 5 | "A highly optimized CORE-MATH based math library" | **UNVERIFIED — zero supporting evidence found**, same standard as #4. Wave-2's `news_delta` domain specifically targeted breaking-change pages including `vex.html`; no math-backend rename surfaced there or anywhere else this session touched. | same sweep as #4 |

## (b) The one structurally-refused item

| # | Claim | Verdict |
|---|---|---|
| 6 | "APEX now handles complex character deformation, rig templates, and rigging math... Claude Code needs to register APEX port types" | **REJECT — Non-Goal 1, no re-litigation, regardless of source.** Rigging/KineFX/APEX is a structural refusal in this harness (`harness/verify/checks.py::check_no_rigging_drift`, `python/synapse/server/authoring_domains.json`), re-affirmed as recently as this session's own release-notes adjudication, which logged and rejected an equivalent boundary-pressure event from SideFX's *own, verified-real* keynote announcement. An unverified memo asking for the same thing carries **less** standing than the verified announcement that was already rejected, not more. |

## (c) What has genuine merit, and where it already lives

The memo isn't worthless — its instinct that Copernicus expanded and that splat/ML nodes are new is correct, and its schema-extraction script is technically plausible (real `hou.nodeTypeCategories()` / `parmTemplates()` API shapes). But every piece of legitimate signal here **duplicates work this session already completed, with better provenance**:

- Copernicus reclassification / heightfield migration → covered live: `docs/reviews/h22-cop-audit-verification.md` (21 tools re-validated) + `harness/notes/verified_connectivity_H22.json` (288-type sweep).
- Splat / Gaussian-splatting nodes → covered live: wave-2 doc-scout `TOPS-06`/`TOPS-07`, step-9 probes confirmed the real trainer name (`ml_traingsplats`, not the memo's implied naming) and quarantined the phantom `top::gaussian_splat_train`.
- A rebuilt truth catalog dumped to a fresh, ad hoc path (`/path/to/synapse/catalogs/h22_truth_catalog.json`) would **fragment the existing catalog architecture** — SYNAPSE already has one committed H22 symbol table + one connectivity catalog; a second, uncoordinated one is the exact "two sources of truth" anti-pattern the harness's own non-negotiables forbid.
- Vulkan-only viewport, OpenGL removal → already adjudicated: `docs/intake/adjudication-h22-release-notes.md` claim set, G2.

**Nothing here is a new candidate.** Everything legitimate is already deposited, either merged or ratified-pending, in `harness/state/flywheel_queue.json`.

## Verdict

**No code implemented. No catalog rebuilt. No APEX work started.** The memo's one falsifiable "current state" claim (test count) was already known-stale by this session's own records before the memo arrived; its one directly-actionable instruction (scrap Cop2) would have reverted a commit this session just proved correct on live H22; its one scope-expanding ask (APEX ports) repeats an already-rejected pressure event. Two specifics (`walkonsurface`/`curveanimate`, "CORE-MATH") are unverified and did not survive two independent, thorough documentation sweeps.

**Escalation:** none required — every checkable claim resolved without ambiguity. If a future *verified* source (an official SideFX doc URL, not a pasted memo) makes the same claims, run it through `h22-intake` properly with a real artifact path.
