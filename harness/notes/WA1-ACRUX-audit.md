# WA1-ACRUX — adversarial crucible audit of wave WA1

*Read-only crucible. Builds nothing, fixes nothing. Findings + verdict only.
Green ACRUX is a **precondition** for Joe's merge words, never a substitute.
Merge words remain Joe's, **per branch** (`--no-ff`), after this receipt.*

- **Wave verdict: `green_with_findings`**
- **BLOCKs raised: 0** (zero unanswered at receipt close)
- Precondition met: all four builder receipts exist, each `green_with_findings`,
  each committed as its own closing commit on its branch.
- Independent verification method: ACRUX re-derived every acceptance claim from
  the **committed evidence artifacts** (not the builders' self-claims), and
  **re-executed** the two pure-Python goalposts (RECIPE membership, XREF parser)
  itself.

## Builder receipts under audit (branch : product HEAD : receipt HEAD)

| Leg | Branch | Product HEAD | Receipt HEAD | Status |
|---|---|---|---|---|
| WA1-TRUTH | wavea1/truth | 27d609a7 | 1efdd080 | green_with_findings |
| WA1-XREF | wavea1/xref | ac2f8e1b | 3d675f62 | green_with_findings |
| WA1-WIRE | wavea1/wire | 6e02ccf6 | dee58340 | green_with_findings |
| WA1-RECIPE | wavea1/recipe | c9c34026 | 5a61ae21 | green_with_findings |

---

## T1 — per-leg acceptance audit (verdict + anchor, ACRUX-verified)

### WA1-TRUTH (4/4 pass, 2 ACRUX findings)

1. **catalog exists, build==runtime, rank≥70 seeds re-confirmed/UNKNOWN with evidence → PASS.**
   `apex_truth_22.0.400.json` meta.build=22.0.400, target_build_match=true, 39
   entries all stamped 22.0.400, **0 entries missing provenance** (claim/build +
   probe|value). Seeds re-derived by ACRUX: invokegraph/autorigbuilder/
   buildfkgraph/graph/rigdoctor `exists=True`; twoboneik/blendtransforms
   `exists=True` in **Vop** (category drift recorded, not absent);
   configuregraph::2.0 + fusegraph `exists=False` (phantoms falsified live).
2. **docstring re-stamped, H21.0.671 gone → PASS.** `apex_probes.py:9`
   `APEX-TRUTH-BUILD: 22.0.400`, read from `hou.applicationVersionString()` under
   hython; **grep `21.0.671` = 0 matches** (ACRUX via git show).
3. **version_agreement covers apex stamp + suite green → PASS (partial re-exec).**
   ACRUX verified the stamp-agreement inputs match (docstring 22.0.400 == artifact
   meta.build 22.0.400 == filename), and `tests/test_apex_truth_wa1.py` is present
   (+177 LOC, pins drift/no-artifact/green). *Caveat: ACRUX did not re-run
   `version_agreement.py` headless — it lives on the truth branch and needs the
   artifact co-resident; verified by input agreement + test existence, not by
   re-execution.*
4. **P2 invoke determinism repeat-2 identical → PASS (caveat, see F-TRUTH-2).**
   `invoke_geo_hash:apex_invoke_smoke` hashes identical
   `fd80b8ce43ad268ca…6417c487` on both passes, `stable=true`.

### WA1-XREF (3/3 pass)

1. **parser parses all cache entries, tests green under stock pytest → PASS.**
   ACRUX **re-ran** `pytest tests/test_xref_help.py` → **42 passed, 0 skipped**.
2. **referee artifact, per-node three-way verdicts, 0 unclassified → PASS.**
   `apex_help_xref_22.0.400.json` summary: rows_total=55, confirmed 17 /
   undocumented 27 / quarantine-candidate 2 / type-mismatch 0 / runtime-unknown 9,
   **unclassified=0** (ACRUX re-derived). type-mismatch=0 is honestly labeled
   `runtime_port_types_measurable=false` (UNMEASURABLE), never dressed as clean.
3. **doc-present/runtime-absent names filed with both anchors → PASS.**
   `quarantine_candidates[2]` each carry `docs_anchor` **and** `runtime_anchor`;
   `harness/phantoms/XREF-CANDIDATES.md` table repeats both anchors and encodes the
   low-recall + runtime-consumed guards. (T4 XREF, below.)

### WA1-WIRE (3/3 pass)

1. **matrix full ordered-pair product, each cell connects|coerces|rejects(+exc)|UNKNOWN → PASS.**
   `apex_wire_matrix_22.0.400.json`: 441 cells (=21²), connect 21 / reject 420,
   **0 cells missing a verdict**, **0 rejects without exception text** (ACRUX
   recomputed over all cells; sample reject `"Mismatched type: /s:value:Bool ->
   /d:parm:Int"`). type_present all True → 0 UNKNOWN cells (fixture fully
   catalog-proven). (T4 WIRE, below.)
2. **repeat-2 idempotence hash match → PASS.** artifact `value.repeat`: repeat=2,
   sample_count=81, `idempotent=true`; cross-run `matrix_hash 8bde4bb5…`. *ACRUX
   verified structure + counts by re-derivation; relied on the artifact's recorded
   hashes for the idempotence claim (did not re-run hython).*
3. **@/$ table one row per (token, context), unmeasured UNKNOWN → PASS.**
   `apex_token_resolution`: **68 rows (17×4)**, 0 missing resolved_to, **0 UNKNOWN
   rows without a reason**; the 17 invoke-binding rows are UNKNOWN **with reason**
   (skip ≠ pass).
   Type-set honesty: WIRE used a **declared fixture** (21 catalog-proven types),
   NOT TRUTH's null-typed port artifact, and its receipt **states** which set was
   used — exactly the crucible criterion.

### WA1-RECIPE (3/3 pass)

1. **zero catalog-absent emitted names, goalpost green vs fresh catalog → PASS.**
   ACRUX **re-ran** the goalpost with `APEX_TRUTH_CATALOG` → TRUTH's committed
   catalog: **4 passed, 0 skipped** (incl. `test_emitted_recipe_types_are_catalog_present`).
2. **goalpost fails LOUD (not skip) when catalog absent — RED leg → PASS.**
   ACRUX **re-ran** with no catalog reachable: **2 failed, 2 passed, 0 skipped**;
   both failures are a hard `CatalogNotFound` raised from `discover_catalog_path()`
   (fail-loud, never a skip). Discovery searched the recipe branch's two runs dirs
   and found **zero** candidates — confirming the hidden state was honest. (T3.)
3. **rename ledger anchored to supersession map → PASS.**
   `harness/notes/WA1-RECIPE-migration-ledger.md` (+188 LOC) anchors each rename to
   `apex_probes.py` supersession map L24-33; `apex_recipes.py` byte-unchanged
   (absent from the recipe diffstat — corroborated).

---

## T2 — stale-stamp hunt

- **Build stamp runtime-observed, not typed:** artifact `meta.build=22.0.400`
  with `target_build_match=true` and in-run timestamps
  (`started/finished 2026-08-17T16:26:5x`); every one of 39 entries carries its own
  `build` + `ts`. Probe reads `hou.applicationVersionString()`. **No typed/assumed
  stamp.**
- **Docstring matches artifact stamp:** `apex_probes.py:9` `22.0.400` ==
  `meta.build 22.0.400` == filename `apex_truth_22.0.400.json`. `21.0.671` count
  on the file = **0**. → **T2 pass.**

## T3 — false-green hunt (ACRUX-reproduced, own hands)

| Run | Command surface | Result | Skipped |
|---|---|---|---|
| Normal (catalog present via env) | `pytest tests/panel/test_apex_catalog_membership.py` | **4 passed** | 0 |
| Hidden (no catalog reachable) | same | **2 failed (CatalogNotFound), 2 passed** | 0 |

Fail-loud confirmed; skip absent in both directions. → **T3 pass** (also ACRUX
acceptance predicate #2).
*Terminology note: RECIPE's receipt called the hidden failure a "hard ERROR"; pytest
reports it as FAILED because `CatalogNotFound` is raised in the test body, not a
fixture. Substance identical — a raised hard failure, never a skip.*

## T4 — phantom-class audit

- **XREF quarantine candidates carry both anchors:** 2/2 candidates
  (`component::MappedConstraints`, `controlgadget::SnapXFormToAxes`) each carry
  `docs_anchor` (`nodes/apex/…`) + `runtime_anchor`
  (`apex_truth_22.0.400.json#…:apex_callback_catalog:*`) — in the artifact **and**
  the `XREF-CANDIDATES.md` ledger. Both honestly flagged as *likely non-callback
  concepts* (namespaces with zero registered callbacks), human-dispositioned. ✓
- **WIRE reject cells carry exception text:** 420/420 rejects carry
  `exception` text; **0 rejects without it** (ACRUX recomputed). ✓
- → **T4 pass.**

## T5 — shared-surface audit (`probes.py`, TRUTH + WIRE)

Bus timeline on the shared seam:
`TRUTH claim 12:15:16 → TRUTH release 12:43:20 → WIRE claim 12:58:25 (post-release)
→ WIRE release 13:15:15`. **No overlapping OPEN claims; both releases posted.**
`mission_schema.py`/`runner.py` were also both-touched (additive branches) and
disclosed (TRUTH `for_ruling`, WIRE R1). XREF/RECIPE never claimed `probes.py`.
The merge-time union of `VALID_KINDS` / dispatch chains is **Joe's** (flagged, not
resolved by ACRUX). → **T5 pass.**

## T6 — UNKNOWN audit

No zero/estimate found standing where UNKNOWN belongs:
- XREF type-mismatch=0 → labeled **UNMEASURABLE**, not clean.
- WIRE @/$ invoke-binding rows → **UNKNOWN with reason**, not 0, not guessed.
- WIRE matrix UNKNOWN cells = 0 **because** the fixture is fully catalog-proven
  (`type_present` all True) — a legitimate zero, not a masked unknown.
- TRUTH port `type=null` → the **honest rendering of an unobtained value** (the
  artifact does not fabricate a type or a zero). See F-TRUTH-1: the receipt should
  disclose it, but no green is claimed over it.
→ **T6 pass, no BLOCK.**

## T7 — BLOCKs

**Zero BLOCKs.** No false-green (T3 proven both ways), no fabricated value (all
provenance present, nulls honest), no UNKNOWN-as-pass (T6 clean), no unserialized
shared-surface edit (T5 clean). ACRUX crucible findings posted to the bus
(`WA1-ACRUX → WA1-TRUTH`, `→ *`). Zero unanswered BLOCKs at close.

---

## ACRUX findings (green_with_findings material — none blocking)

- **F-TRUTH-1 — receipt omission of the null-port-type defect.** All 41
  `apex_port_signature` ports carry `type:null` (arity/`input_count` correct),
  root-caused by WIRE-F1 (`_safe_str(fn)=str(fn())` calls the string *property*
  as a function → raises → null). The artifact is honest (null, not fabricated),
  and WIRE+XREF both routed around it (type dimension UNMEASURABLE/UNKNOWN) — so
  **not a false-green, not a T6 violation.** But TRUTH's own receipt marks the
  provenance criterion green without disclosing F1. *Disposition (for Joe):* TRUTH
  should amend its receipt to disclose F1; the declared-port-type surface must not
  be relied on until the one-line fix (read `p.name`/`p.type_name` as properties)
  lands. Owner: WA1-TRUTH (already filed as WIRE-R2).
- **F-TRUTH-2 — P2 determinism proven over empty geometry.** The repeat-2 hash is
  over `point_count=0, prim_count=0`. Predicate met as written; a stronger
  determinism claim would exercise a non-trivial invoke output. Non-blocking.

## Carried-forward builder disclosures (corroborated, acceptable, → for Joe)

- TRUTH: `mission_schema.py`/`runner.py` prerequisite scope; surgical
  `emitted_node_types.json` apex-only edit (solaris/blocks drift routed to spawn
  `EMITTED-TYPES-RESYNC`); sibling stale stamp in `science/__init__.py` (spawn
  `APEX-INIT-RESTAMP`).
- XREF: 2 quarantine candidates likely non-callback concepts — human doc-fix vs
  quarantine; runtime artifact lives cross-branch (merge/orchestration decision).
- WIRE: F2 (APEX wire typing is exact-match; no implicit direct-wire coercion —
  coercion is explicit via `Convert<A,B>`); spawn `APEX-CONVERT-MATRIX` (probe
  class, in `spawn_classes`).
- RECIPE: `apex::sop::parentconstraint`/`aimconstraint` recognisers **removed**
  (no SOP successor; real surface is `rig::*Constraint` graph callbacks) —
  behavior-preserving, lost intent flagged for ruling; disclosed classifier
  reclassification into the autorig bucket (no test pinned the old classification).

*All builder `spawn[]` proposals are `probe`-class or `build`-class follow-ups and
land held for Joe.*
