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

---

## (d) Copernicus scope-expansion claim — dedicated scout verdict

**Claim under test:** "In H22, COPs is no longer just a compositing engine; it is a unified, GPU-accelerated world-building, texturing, and terrain layer."

**Method:** live `WebFetch` of the official SideFX H22 docs — the Copernicus index and six subpages it links to — read for exact wording, not paraphrase. Cross-referenced against this project's own already-verified evidence rather than re-deriving tool-level facts: `docs/reviews/h22-cop-audit-verification.md` (21 COP tools re-validated live, 384 types in the `Cop` category including 18 height* + ocean* types), `harness/notes/verified_connectivity_H22.json` (288-type connectivity sweep), `docs/reviews/h22-doc-intel-2026-07-15.md` (wave-1 `cops` domain section), `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` (wave-2, karma/husk interplay).

**Sources read (URL + section):**

| URL | Section read |
|---|---|
| `copernicus/index.html` | Full TOC + introductory line |
| `copernicus/intro.html` | "Introduction to Copernicus" — the conceptual definition page |
| `heightfields_cop/index.html` | "Copernicus heightfields and terrains" index + TOC |
| `copernicus/substance_designer.html` | "Copernicus for Substance 3D Designer™ users" |
| `copernicus/slap_comp.html` | "Slap comp" |
| `copernicus/transition.html` | "Copernicus for Houdini users" (compositing network differences) |
| `news/22/copernicus.html` | "What's new in Houdini 22" — Copernicus release-notes page |

### Sub-claim verdicts

| # | Sub-claim | Verdict | Evidence |
|---|---|---|---|
| 1 | "No longer just a compositing engine" | **VERIFIED.** SideFX's own docs explicitly demote the old system and promote Copernicus as its successor: *"Use Copernicus nodes instead of Compositing nodes. Though both networks still exist, the Compositing network is now designated as `COP Network - Old`."* This is a real, official scope-change, not paraphrase. | `heightfields_cop/index.html` intro text (quoted verbatim); corroborated by this session's own `h22-cop-audit-verification.md` (legacy `Cop2Node` survives, but the modern `CopNode`/Copernicus path is the forward one) |
| 2 | "Unified... layer" | **UNSUPPORTED.** The word "unified" does not appear verbatim on any of the seven pages read, including the two most likely candidates (`intro.html`, `news/22/copernicus.html`). SideFX's own definition is narrower and more literal: *"Copernicus (COP) is a 2D and 3D GPU image processing framework."* / *"COP nodes provide real-time image manipulation within a 3D space."* "Unified" is memo/marketing paraphrase, not a SideFX term. | `copernicus/intro.html` |
| 3 | "GPU-accelerated" | **VERIFIED, but narrower than the memo implies.** SideFX does use this exact phrase — but scoped to heightfields, not the whole system, and hedged with "many" not "all": *"Many Copernicus operations are GPU-accelerated."* The system-level definition itself says "GPU image processing framework," not "GPU-accelerated." | `heightfields_cop/index.html` |
| 4 | "World-building... layer" | **UNSUPPORTED.** The phrase "world-building" (or any close variant — "world assembly," "scene assembly," "landscape generation") does not appear verbatim on any page read, including the release-notes page that lists every H22 Copernicus feature category. SideFX frames the expansion as new *node categories* (terrain, grunge/procedural-texture nodes, simulation, ML), never as a general-purpose world-building claim. | `news/22/copernicus.html`; `copernicus/intro.html`; `copernicus/transition.html` (no scope-beyond-compositing language found at all on the transition page) |
| 5 | "Texturing layer" / primary texturing tool | **PARTIALLY CONFIRMED.** Real texturing-adjacent capability exists and is documented — H22 adds "Grunge maps (13+ procedural texture nodes)" and adjacency nodes "for texture seam handling" per the release notes — but SideFX does **not** claim Copernicus replaces or supersedes dedicated texturing/look-dev tools. The Substance Designer transition page is explicitly a compatibility/mapping guide ("for users that are familiar with Substance 3D Designer™ and want to accomplish similar tasks... using Copernicus"), not a superiority or replacement claim. Slap comp — the closest thing to a "texturing pipeline" entry point — is defined as *"a fast image manipulation you can use to view approximate and live results of a final composite"* and *"primarily... a filter authoring network,"* not as Houdini's primary texturing/look-dev surface. | `news/22/copernicus.html`; `copernicus/substance_designer.html`; `copernicus/slap_comp.html` |
| 6 | "Terrain layer" (full absorption of terrain workflows) | **REFUTED at the "unified/absorbed" framing; capability itself is real and substantial.** SideFX's own heightfields_cop index states the opposite of absorption in so many words: *"Currently, Copernicus-based heightfields are_not_ a replacement for Houdini's traditional SOP-based approach."* Both terrain systems coexist as parallel entries in the docs nav (`heightfields/index.html` classic SOP-based, `heightfields_cop/index.html` new COP-based). The real capability is genuine and well beyond what was already confirmed in the tool-level COP audit: base terrain, workflows, projection, terrain recipes, masking, erosion, slump, terracing, strata, boulders, VEX scripting, terrain colors, and conversion nodes are all documented sections — and *"Copernicus-based heightfields work with 2D maps instead of voxel grids... incomparably faster"* with GPU acceleration on "many" operations. | `heightfields_cop/index.html` (verbatim quotes above); `copernicus/index.html` nav (both heightfield entries present) |

### Composite verdict

**PARTIALLY CONFIRMED — real, substantial, officially-documented scope expansion; "unified" and "world-building" are not SideFX's own words.**

The underlying capability claim is directionally correct and well-supported: Copernicus in H22 is the SideFX-designated successor to the old Compositing network, ships genuine GPU-accelerated terrain/heightfield tooling (base terrain, erosion, masking, strata, boulders, etc.), genuine procedural-texture node categories (grunge maps, adjacency/seam handling), plus simulation and ML node families — a real breadth expansion beyond pure compositing, consistent with what the COP audit and doc-scout waves already found live on H22.0.368. But the pasted memo's specific *framing words* — "unified" and "world-building" — do not exist anywhere in SideFX's own H22 documentation (index, intro, heightfields_cop, transition, substance_designer, slap_comp, or the news/22 release-notes page). Two structural claims implicit in "world-building... terrain layer" are actively contradicted by the source: (1) Copernicus heightfields are explicitly documented as *not* a replacement for the SOP-based terrain system (coexistence, not takeover), and (2) Copernicus is explicitly positioned as compositing's successor and a Substance-Designer-workflow-equivalent, never as a primary texturing/look-dev tool replacing dedicated texturing software. Treat the memo's phrase as marketing paraphrase of a real capability expansion, not a quotable SideFX claim — cite the underlying feature list (terrain, grunge maps, ML, sim) if this needs to go into any SYNAPSE-facing doc, never the "unified world-building layer" wording itself.

## (e) HDK cross-check on the two remaining unverified claims

Claims #4/#5 from section (a) ("CORE-MATH" math library, "Vulkan-based OpenCL interoperability") were UNVERIFIED against the artist-facing HOM/docs surface. Since these are internals-level claims, the HDK (`sidefx.com/docs/hdk/`) is the correct place to look for them if real. Direct `WebFetch` of the HDK index and its "Major Changes in the HDK" page (fetched 2026-07-16):

- The HDK's own changelog page **stops at "Major Changes in Houdini 21.0"** — there is no H22.0 changes entry published at this URL as of today.
- Neither page contains any mention of a renamed/rewritten core math library, `UT_Vector`/`UT_Matrix`/SIMD changes, or Vulkan/OpenCL interoperability, in any version.

**Consequence:** the verdict on claims #4/#5 stays **UNVERIFIED**, now on firmer ground — not merely "our searches didn't find it," but "the one HDK resource built specifically to document this class of change has no H22 entry to search." This does not upgrade to REFUTED (the information could exist in a not-yet-indexed HDK page, or have been stated verbally in the keynote without a written HDK counterpart) — but it removes any residual benefit of the doubt for treating these as established fact.

