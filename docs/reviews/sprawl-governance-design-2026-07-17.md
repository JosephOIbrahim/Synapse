# SPRAWL GOVERNANCE — build-ready design (mile-namespace collision + ruling-home sprawl)

**`docs/reviews/sprawl-governance-design-2026-07-17.md`** · Repo: `C:\Users\User\SYNAPSE` (branch `master`). All paths repo-relative; every load-bearing claim below carries a `file:line` I verified read-only this dispatch.
**Status: DESIGN — no ratification, no mutation.** This file specifies edits; it makes none. Execution is a separate, human-ratified cycle (§8).
**Governing gate:** rulebook amendment protocol — `draft → ratified` is a human (Joe) action recorded in the manifest (`SYNAPSE_RULEBOOK.md:130`); per-cycle human merge, no agent merges (`harness/CLAUDE.md` → Commits).
**Relay leg:** governance / debt pass — the same harness-architect debt lane that produced `docs/reviews/proof-leg-grounding-2026-07-17.md` and the Copernicus OD rulings (`docs/SYNAPSE_COPERNICUS_EXPANSION.md:14`).

---

## OPEN DECISIONS (human rules only; the rest of this design is complete either way)

Naming and scope-trade calls are Joe's. Each carries a recommendation with evidence; none is invented as a ruling.

- **OD-1 — the ladder token.** The task brief suggested `RB-M<n>` for the rulebook ladder. **Recommend `RBK-M<n>` instead**, because `RB-<DOM>-NNN` is already the Rulebook's *rule-ID* grammar (`RB-THR-001`, declared at `SYNAPSE_RULEBOOK.md:76` and `rulebook/RULEBOOK.md:44`); `RB-M0` would read as a confusable sibling of that namespace. Options: **(a)** `PL-M<n>` / `RBK-M<n>` (recommended); (b) name-not-number for the rulebook ladder (`Charter / Harvest / Backfill / …`) so the two ladders never share the word "Mile"; (c) qualifier-only, no ID token (`"proof-leg Mile N"` / `"rulebook Mile N"`), which is what `flywheel_queue.json` already does.
- **OD-2 — one cycle or two.** Both bites are cheap prose edits with no code surface. **Recommend one ratified cycle** covering both. Option (b): split (mile-namespace first, ruling-sprawl second) if Joe wants the ruling de-stale reviewed independently.
- **OD-3 — register RETINA as a third ladder now?** **Recommend no.** RETINA's `M<n>` form (e.g. `Mile 5 = RETINA M3`, `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:21`) is already lexically distinct from `Mile <n>` and does not collide. Register it only if a future doc starts writing RETINA miles as `Mile N`.

---

## Definition of Done (the whole design)

This design is **done** when a human can dispatch the §5 cycle with zero open design questions. The *executed* cycle is done when all of:

1. Each of the **4 ladder docs** carries a one-line ladder-ID header naming its ladder (`PL` / `RBK`), its mile range, and the cross-doc citation form. No mile is renumbered or renamed (`net readability delta = 0`).
2. **One** convention line lands in the project `CLAUDE.md` and the commit-message convention: cross-ladder mile citations carry a qualifier (`proof-leg Mile N` / `rulebook Mile N`, short `PL-M<n>` / `RBK-M<n>`).
3. The **three genuinely-misleading ruling artifacts** are corrected (blueprint §4 RULED-annotated; `flywheel_queue.json:405` de-staled; `PORT_WAVE_MANIFEST.md` cops-3 addendum written), and each of the 6 OD rulings has one designated SSOT with the other homes reduced to honest pointers.
4. The **branch-only post-mortem** (`docs/reviews/h22-per-context-postmortem-2026-07-17.md`, commit `a3f3dd9`, not on master) is merged, closed, or given a master pointer — decided, not left latent.
5. Full `pytest tests/` stays green; **no new CI machinery** ships in the MVP (that is the "if it grows" phase, §4).

---

## 1. Problem statement — the two bites

Two governance surfaces sprawled the same week (2026-07-17). Neither is a live break today; both are **latent traps** that bite cross-context.

### Bite 1 — two both-governing "six-mile" ladders, no index tells them apart

Two independent ladders, each literally titled "six miles," both committed, born one day apart:

| | Ladder A (proof-leg) | Ladder B (rulebook) |
|---|---|---|
| Head | `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:164` (`## §5 · The six miles`) | `SYNAPSE_RULEBOOK.md:136` (`## 5 · Execution plan — six miles`) |
| Table | `:168`–`:175` | `:140`–`:147` |
| Range | **Miles 1–6** (no Mile 0 — table starts at 1) | **Miles 0–5** |
| Mile 1 means | **the twins** — G1a U.5-H22 context fold · G1b mtlx phantom kill (`:170`) | **Harvester + differ** (`:143`) |
| Mile 0 | *does not exist* | **Charter** (`:142`, prose `:149`) |
| 2nd home | `SPEC.md:36` table, Mile 1 = C-U5/C-MTLX (`:38`), mission "Miles 1–5" (`:11`) | `rulebook/RULEBOOK.md:80` (`## Where the miles go`), full 0→5 chain (`:82`) |

**Premise correction (verified):** the proof-leg blueprint has **no Mile 0** — its §5 table begins at Mile 1 (`:168`–`:170`). Any brief that says "the blueprint's Miles 0–6" is off by the low end; `Mile 0` belongs only to Ladder B.

Bare `Mile N` collides for **N = 1..5** (each names a different deliverable in each ladder). `Mile 0` is B-only and `Mile 6` is A-only — each unambiguous by exclusion.

**Where it is safe:** inside any single doc, every reference is unambiguous — each doc uses exactly one ladder consistently, and no doc yet cites the *other* ladder's mile by number. There is **no broken pointer today.**

**Where it bites (cross-context):**
- **git log** — same-day `7b82cd9` "Rulebook Mile 0 — charter…" sits beside `96ff51a` "deposit(proof-leg): C-U5 … + C-MTLX Mile-1 cycles" and `dd18bbb` "…(F3, before Mile 0)". A reader scanning `git log --oneline` sees "Mile 0" and "Mile-1" with no shared token telling them these are two different ladders. The only (informal, inconsistent) disambiguator is the `proof-leg` vs `Rulebook` prefix each subject happens to carry.
- **Any agent or human citing "Mile N"** without a ladder tag.
- **A third labeling layer** — RETINA's `M0–M5`, called "RETINA miles" in `flywheel_queue.json` (6 lines: `:446, :457, :468, :479, :490, :501`), which the proof-leg blueprint renumbers into its own Miles 4/5 (`Mile 5 = RETINA M3`, blueprint `:21`). One body of work wears two mile-numbers — though RETINA's `M<n>` is already lexically distinct from `Mile <n>`.

**The fix pattern already exists but is unenforced:** `flywheel_queue.json` consistently qualifies — `"SPEC C-U5 Mile-1 cycle"` (`:415`), `"C-MTLX (proof-leg Mile 1, blueprint §G1b)"` (`:539`). Every other surface uses bare `Mile N`. That missing qualifier **is** the drift.

*Occurrence counts (my own `grep -oiE '\bmile'`, case-insensitive, includes plurals and "milestone" — a different metric than the intake brief's numbered-reference count, cited here as color, not load-bearing): `SYNAPSE_RULEBOOK.md`=31 · `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md`=21 · `SPEC.md`=10 · `rulebook/RULEBOOK.md`=10 · `README.md`=1 (rhetorical "milestone", `:114`, non-ladder) · `CLAUDE.md`=0. The structural facts above are table-verified, not count-derived.*

### Bite 2 — six ruling dispositions scattered across homes, three of them misleading

Six start-line rulings were decided (`docs/SYNAPSE_COPERNICUS_EXPANSION.md:14`, `RULED 2026-07-17 (Joe, harness-architect debt pass)`) and again for CHOP + DOP/MPM (`flywheel_queue.json:515`–`:525`, `ratified: true` at `:523`). **No disposition collision exists** — every home resolves to the same outcome the blueprint's carried recommendation predicted. The sprawl is **framing/staleness**, in four shapes:

1. **Blueprint never flipped.** `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` §4 (`:147`–`:152`) still presents all six as **open options with a "Carried rec"** under the banner "no ruling invented … it's the gun" (`:143`), and §6 still lists CHOP + DOP/MPM as "Pending start-line rulings 5–6 … (recommended)" (`:186`). A reader landing there cannot tell the gun was fired.
2. **Queue stale on OD-C.** `flywheel_queue.json:405` still calls the terrain verb `"Provisional verb name cops_terrain_setup (OD-C)"` where the ruling confirms it **stands, no rename** (`Copernicus:14`). OD-A/B/D have no queue home at all.
3. **Richest home is branch-only.** `docs/reviews/h22-per-context-postmortem-2026-07-17.md` (commit `a3f3dd9`) carries both the resolved dispositions and the original analyst options — but it is **not tracked on master** (verified: `git ls-files` misses it; the commit lives on branch `docs/h22-per-context-postmortem`). If that branch is abandoned, master loses the fullest CHOP/DOP-MPM narrative.
4. **Unexecuted follow-through.** OD-A ruled `(a)` = add a cops-3 addendum to `docs/PORT_WAVE_MANIFEST.md` (`Copernicus:14`, `:16`–`:19`). The manifest carries **no such addendum** (verified: `grep` for `cops-3|118` hits only the `4118` suite floor). The ruling is recorded but not carried out.

**Mitigant already on master:** `docs/reviews/proof-leg-grounding-2026-07-17.md:34`–`:39` is a tracked audit that already tabulates all six as RULED with SSOT citations — so the *decided* state is not lost, but it lives in an audit snapshot, not in the governing blueprint a reader trusts.

---

## 2. The thesis — and its temper

**The thesis (Joe's, and the Rulebook's own §0):** a rule in `docs/` is prose, and prose drifts; a rule in the Rulebook — indexed in the manifest, pinned by a green meta-test — is law. `rulebook/RULEBOOK.md:68` states it directly: the meta-tests are "written at Mile 0, green forever after." The durable fix moves bookkeeping **out of human memory into the build**.

**The temper (binding).** The CRUCIBLE proportionality verdict ruled the full "manifest registry + scanning meta-test" design **not solo-dev-proportionate** for this collision, and its `net_drift_reduced` verdict is **false** for that heavier design. Three findings make the temper binding here:

- **The registry would be self-referential.** Grep-verified: nothing under `python/`, `harness/`, `scripts/`, or `shared/` reads `rulebook/manifest.json` — its only consumer is the meta-test suite (`tests/rulebook/test_rulebook_meta.py`). A new `governing_ladders` block's sole reader would be the test that exists to validate it. "A queryable index agents use" is vaporware until a real consumer exists.
- **The proposed gate breaks its own convention.** The intake design's meta-test 6 regex `\bMile[s]?\s+(\d+)` captures `Mile 0` *inside* the blessed cross-citation `"rulebook Mile 0"` — the exact natural-language form the design licenses and that `flywheel_queue.json` already uses. If that qualified citation ever lands in a proof-leg doc, the gate flags `PL` (0 < mile_min 1). The gate would punish the convention it was built to enable.
- **The regex guard is blind to the real vector.** It only checks each ladder's mentions against its *own* declared range, so a *deliberate* renumber (author adds "Mile 0" to the proof-leg doc **and** widens `mile_min`) passes green while creating the exact ambiguity the fix targets. It guards two boundary integers (0 and 6) against typos, not the collision.

**Therefore the recommendation is the crucible's simpler option**, not the intake design's fuller one. The thesis still holds — the disambiguation stops living in folklore — but it is discharged by **co-locating the fact where it is read** (a one-line header in each doc, which cannot drift from the doc it heads) plus a lightweight qualifier convention, not by a self-validating registry. The heavier machinery is recorded as "if it grows" (§4), and *if* built, in the crucible-corrected form (schema-only, no doc-text regex).

---

## 3. Recommended architecture

### Bite 1 — mile-namespace: co-located ladder-ID headers + qualifier convention

- **Canonical IDs (per OD-1):** proof-leg ladder = **`PL`**, miles **1–6**, cross-doc ID `PL-M<n>`. Rulebook ladder = **`RBK`**, miles **0–5**, cross-doc ID `RBK-M<n>`. `RBK-` (not `RB-`) keeps the ladder namespace off the rule namespace `RB-<DOM>-NNN` (`SYNAPSE_RULEBOOK.md:76`).
- **SSOT of the ladder-identity fact:** each doc's own **header line**, co-located at point-of-use. There is no central registry in the MVP — the fact is stated in the four docs that carry the ladders, where it cannot skew from the thing it describes.
- **Header form (additive one-liner, no renumber):**
  - Blueprint + SPEC: `> Mile IDs: this is Ladder PL (proof-leg), miles 1–6. Cite cross-doc as PL-M<n> (e.g. PL-M1 = the twins). The rulebook's ladder is RBK (miles 0–5) — a different plan.`
  - `SYNAPSE_RULEBOOK.md` + `rulebook/RULEBOOK.md`: `> Mile IDs: this is Ladder RBK (rulebook), miles 0–5. Cite cross-doc as RBK-M<n> (e.g. RBK-M0 = Charter). The proof-leg's ladder is PL (miles 1–6) — a different plan.`
- **Pointer/qualifier form the other surfaces adopt:** bare `Mile N` stays legal *in-doc* (each doc is single-ladder). On cross-doc surfaces — commit subjects, flywheel notes, cross-ladder citations — the qualifier is required: `proof-leg Mile N` / `rulebook Mile N`, short `PL-M<n>` / `RBK-M<n>`. This promotes the convention `flywheel_queue.json:415, :539` already models to a stated rule.
- **RETINA:** not registered (OD-3). Noted in the headers only if a future doc writes RETINA miles as `Mile N`.

### Bite 2 — ruling-home: one SSOT per ruling + honest pointers + three corrections

No new machinery. The rulings agree; the fix is pointer-hygiene plus the three real corrections.

| Ruling | Designated SSOT (full text) | Pointer homes reduced to `→ SSOT` | Correction needed |
|---|---|---|---|
| OD-A (115→118, cops-3 addendum) | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:14` | blueprint §4 row 1 (`:147`), `SPEC.md:41`, grounding `:34` | **Write the addendum** in `PORT_WAVE_MANIFEST.md` (unexecuted) |
| OD-B (RD rides C.4 as D4.5) | `Copernicus:14` (+ D4.5 body `:112`) | blueprint `:148`, `SPEC.md:41`, grounding `:35` | annotate blueprint row |
| OD-C (`cops_terrain_setup` stands) | `Copernicus:14` | blueprint `:149`, `SPEC.md:41`, grounding `:36` | **De-stale** `flywheel_queue.json:405` ("Provisional" → "OD-C RULED, name stands") |
| OD-D (C.4 subsumes W.4b(3)) | `Copernicus:14` | blueprint `:150`, `SPEC.md:41`, grounding `:37` | annotate blueprint row |
| CHOP scope (non-goal) | `flywheel_queue.json:524` (sibling clause, master, ratified) | blueprint §4 row 5 (`:151`), §6 (`:186`), grounding `:38` | annotate blueprint; resolve branch-only postmortem home |
| DOP/MPM scope (non-goal + scoped recon, then freeze) | `flywheel_queue.json:515`–`:524` (`ratified: true`) | blueprint §4 row 6 (`:152`), §6 (`:186`), grounding `:39` | annotate blueprint; resolve branch-only postmortem home |

- **Blueprint §4 annotation follows the repo's own established pattern:** add a `RULED 2026-07-17 → see <SSOT>` banner atop §4, **preserving the options text below** — exactly what `Copernicus:14` did ("The per-OD rationale below is preserved"). Annotate, do not rewrite; §4 is a start-line ask-block by design, so the honest change is "the gun was fired, here is where the disposition lives."
- **Pointer form other homes adopt:** `OD-X → RULED (see docs/SYNAPSE_COPERNICUS_EXPANSION.md §OPEN DECISIONS)` — a one-line pointer, not a restated disposition.

---

## 4. MVP boundary vs "if it grows"

### MVP (build now — crucible-endorsed, no new CI machinery)

**Bite 1:**
1. Four one-line ladder-ID headers (§3) in `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md`, `SPEC.md`, `SYNAPSE_RULEBOOK.md`, `rulebook/RULEBOOK.md`. Prose-only, no renumber.
2. One convention line in the project `CLAUDE.md` and the commit convention (§3 pointer form).

**Bite 2:**
3. Designate the six SSOTs (§3 table); reduce the pointer homes to `→ SSOT` one-liners.
4. Three corrections: blueprint §4 RULED-annotation; `flywheel_queue.json:405` de-stale; the `PORT_WAVE_MANIFEST.md` cops-3 addendum (115→118) that OD-A already ordered.
5. Resolve the branch-only postmortem (merge / close / master pointer).

Enforcement of the MVP is **convention + human review + the existing suite staying green** — *not* a new gate. That is the deliberate proportionality tradeoff: the collision is latent (no broken pointer today), the ladder set is two and human-curated, the maintainer is one. Policing it with CI costs more than the latent risk warrants.

### "If it grows" (defer; build only on a real trigger)

**Trigger:** a real consumer for a machine-readable ladder map is built (a tool/agent that must resolve `Mile N → ladder` programmatically), **or** a third governing ladder appears and the two-doc convention stops scaling.

**Then, and only then:** add a `governing_ladders` block to `rulebook/manifest.json` — two entries (`PL`: docs `[blueprint, SPEC.md]`, `1–6`; `RBK`: docs `[SYNAPSE_RULEBOOK.md, rulebook/RULEBOOK.md]`, `0–5`; prefixes `PL-M` / `RBK-M`) — validated by a **schema-only** check (§6), **not** the intake design's doc-text regex. The regex invariant is dropped for the two reasons in §2: it false-positives on `"rulebook Mile N"` and is blind to the deliberate renumber. `manifest.json` lives *outside* `contracts/`, so the amendment-lock meta-test (below) does not fire on the edit.

**Explicitly gold-plated (skip):** the intake design's cross-surface bare-`Mile N` lint + commit-msg hook (high false-positive, latent problem); boundary-present strictness (`max(seen)==mile_max`, brittle on incidental prose); an auto-generated `PL-M<n> ↔ RBK-M<n> ↔ RETINA M<n>` crosswalk doc (the registry already carries the map); registering RETINA (OD-3).

**Explicitly NOT in scope, ever:** renaming or renumbering any mile; moving any file (the Rulebook indexes in place — `SYNAPSE_RULEBOOK.md` §7 "no file migration"); touching the existing meta-tests 1–5 beyond an additive schema assertion; any `contracts/` edit.

---

## 5. Phased execution plan (uses the new namespace)

One ratified cycle (OD-2 recommends not splitting). Runs on Opus after human go; SCRIBE persists, human merges.

**Phase 0 — grounding re-verify (MODE A-legal, read-only).** Re-confirm the four `file:line` anchors this design cites still hold at dispatch HEAD (blueprint `:164`/`:168`, rulebook `:136`/`:140`, `Copernicus:14`, `flywheel_queue.json:405`/`:515`). If any moved, STOP and re-anchor — the edits are exactness-sensitive.

**Phase 1 — Bite 1 headers + convention (Ladder PL / RBK).** Add the four headers (§3) and the one `CLAUDE.md` + commit convention line. No renumber. This is prose; it touches no `contracts/`, no `manifest.json`, so **no meta-test fires** and there is **no manifest rehash** — a low-friction edit.

**Phase 2 — Bite 2 corrections + pointers.** Annotate blueprint §4 (RULED banner, options preserved); de-stale `flywheel_queue.json:405`; write the `PORT_WAVE_MANIFEST.md` cops-3 addendum (115→118 — the tool-count banner "115 MCP tools registered" in the project `CLAUDE.md` is test-bound via `tests/test_phase0c_doc1_toolcount.py` per `Copernicus:16`, so the addendum is documentation of an already-forced count, not a count change here); reduce the pointer homes to `→ SSOT`.

**Phase 3 — branch-only postmortem.** Per the resolution chosen in review: merge `docs/h22-per-context-postmortem` (commit `a3f3dd9`) to master, close it, or add a master pointer to it. Do not leave it latent.

**Phase 4 — verify + ratify.** Full `pytest tests/` green (the existing meta-tests 1–5 and the tool-count binding must stay green). Human ratifies and merges (governing gate). No agent merge.

**"If it grows" (separate future cycle, P6-gated):** add the `governing_ladders` block + the schema-only meta-test (§6). Because `manifest.json` is outside `contracts/`, the amendment-lock (`test_meta4_contracts_amendment_lock`, `tests/rulebook/test_rulebook_meta.py:229`, which hashes `contracts/` only — `:47`–`:62`) does **not** require a `contracts_checksum` rehash; the edit needs meta-test 1's schema pass plus the new assertion, under human ratify.

---

## 6. Acceptance criteria + meta-tests

### MVP acceptance (reviewer-checked, no new test)

- Each of the 4 ladder docs opens its mile section with the `Ladder PL`/`Ladder RBK` header naming range + cross-doc ID form.
- `CLAUDE.md` + commit convention state the qualifier rule.
- Blueprint §4 no longer reads as an open ask (RULED banner present, pointing to SSOTs; options preserved).
- `flywheel_queue.json:405` no longer contains the word "Provisional" for `cops_terrain_setup`.
- `PORT_WAVE_MANIFEST.md` carries the cops-3 addendum (115→118).
- The branch-only postmortem has a decided disposition.
- `pytest tests/` green; meta-tests 1–5 unchanged and passing.

### "If it grows" meta-test (deferred; spec here so it is build-ready when the trigger fires)

A **schema-only** guard, following the file's established trio pattern (one helper, one live-manifest test, one fail-by-id fixture, one accepts-real fixture — mirroring `test_meta2_*` at `tests/rulebook/test_rulebook_meta.py:143`–`:200`). It checks registry *integrity* — unique ids, unique canonical prefixes, docs claimed by at most one ladder, `mile_min ≤ mile_max` as ints — and reads **no doc text**, so it cannot false-positive on a `"rulebook Mile N"` citation:

```python
def ladder_registry_violations(manifest: dict) -> list[str]:
    """IDs of governing ladders whose registry entry collides with another's.
    Schema-only: NO doc-text scan (that regex false-positives on the blessed
    'rulebook Mile N' citation and is blind to a deliberate renumber).
    Empty/absent 'governing_ladders' => []. Flags a ladder when its id or
    canonical_prefix duplicates another's, when a doc is claimed by two
    ladders, or when mile_min > mile_max."""
    offenders: set[str] = set()
    seen_ids: set[str] = set()
    seen_prefix: dict[str, str] = {}
    doc_owner: dict[str, str] = {}
    for lad in manifest.get("governing_ladders", []):
        lid = lad["id"]
        if lid in seen_ids:
            offenders.add(lid)
        seen_ids.add(lid)
        pfx = lad["canonical_prefix"]
        if pfx in seen_prefix:
            offenders.add(lid); offenders.add(seen_prefix[pfx])
        seen_prefix[pfx] = lid
        if int(lad["mile_min"]) > int(lad["mile_max"]):
            offenders.add(lid)
        for doc in lad.get("docs", []):
            if doc in doc_owner and doc_owner[doc] != lid:
                offenders.add(lid); offenders.add(doc_owner[doc])
            doc_owner[doc] = lid
    return sorted(offenders)
```

- **Live test:** `assert ladder_registry_violations(_load_manifest()) == []`.
- **Fail-by-id fixture:** two ladders sharing a `canonical_prefix` (or one doc) → returns both offending ids (proves the gate bites on the empty real set, as `test_meta2_binding_gate_fails_by_rule_id` does at `:150`).
- **Accepts-real fixture:** the two real entries → `[]`.

**Honest limitation of the "if it grows" gate (stated, not hidden):** it protects the integrity of the ladders it *knows*; a brand-new **unregistered** ladder is invisible until someone adds it (a deliberate manifest edit under human ratify). It also does **not** enforce that the four doc headers agree with the manifest (header↔manifest skew is unguarded) — which is itself a reason the MVP prefers the co-located headers *as the SSOT* and treats the manifest block as an optional, consumer-driven convenience, not the source of truth.

---

## 7. Net-drift ledger

**Verdict: net drift surface goes DOWN for both bites under the MVP, and no self-referential artifact is introduced** (the crucible's core objection to the heavier design is avoided).

**Bite 1 — the ladder-identity fact:**

| | Homes / surface |
|---|---|
| Before | **0 explicit durable homes.** Implicit in 2 mile tables (`blueprint:168`, `rulebook:140`); 2 incidental qualifier strings in `flywheel_queue.json` (`:415`, `:539`). No way to answer "which ladder is Mile 1" without already knowing which doc. |
| After (MVP) | **4 co-located self-consistent headers**, 0 new files, **0 cross-file sync obligation** — a header names its own doc's ladder, so it cannot drift from the thing it heads. Surface **DOWN**: the fact is externalized where it is read. |
| If it grows (+registry) | +1 manifest block (5th home) + 1 schema meta-test. Adds an *unguarded* header↔manifest sync surface (crucible Q2) — net homes neutral-to-up; justified **only** by a real consumer's need for machine-queryability. |

**Bite 2 — the six ruling dispositions:**

| | Homes / surface |
|---|---|
| Before | Full-text at `Copernicus:14` (OD-A/B/C/D) and `flywheel_queue.json:515`–`:524` (CHOP/DOP-MPM); **but** 3 contradicting/stale spots (blueprint §4 reads UNRULED `:147`–`:152`; queue `:405` "Provisional"; `PORT_WAVE_MANIFEST.md` addendum missing) + the richest narrative branch-only (`a3f3dd9`). |
| After (MVP) | **1 SSOT per ruling**; other homes are honest `→ SSOT` pointers; the 3 misleading spots corrected; the branch-only home decided. Full-text converges; contradictions removed. Surface **DOWN**. |

**Added artifacts, MVP:** none beyond one-line prose in existing files. **Added enforcement, MVP:** none (deliberate). The design does **not** add a ruling registry (would repeat the Bite-1 gold-plating the crucible rejected).

---

## 8. Non-goals + execution gate

### Non-goals (locked)

- **No mile is renumbered or renamed.** Miles keep their numbers; only additive headers + qualifiers change.
- **No file is moved.** The Rulebook indexes in place (`SYNAPSE_RULEBOOK.md` §7 "no file migration").
- **No `contracts/` edit and no `contracts_checksum` rehash** in either phase (the registry, if ever built, lives in `manifest.json`, outside the amendment lock).
- **No cross-surface bare-`Mile N` lint, no commit-msg hook** — rejected as gold-plating for a latent, single-maintainer, two-ladder problem.
- **No ruling is re-adjudicated.** Dispositions are settled (`Copernicus:14`, `flywheel_queue.json:523`); this design changes *where they are read*, never *what they say*.
- **RETINA is not registered as a third ladder** (OD-3).

### Execution gate

This document is **DESIGN**. It mutates nothing. Execution is a **human-ratified cycle**, exactness-sensitive (prose edits to governing docs + a decided disposition for a branch), run on Opus after Joe's go and merged by a human — no agent merge (`harness/CLAUDE.md` → Commits; governing gate per `SYNAPSE_RULEBOOK.md:130`). The "if it grows" registry + schema meta-test is a *separate* future cycle, gated on a real consumer and on human ratify.

---

## DoD per deliverable

| Deliverable | File(s) | Done when | Gate |
|---|---|---|---|
| PL/RBK ladder headers | `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md`, `SPEC.md`, `SYNAPSE_RULEBOOK.md`, `rulebook/RULEBOOK.md` | each mile section opens with its ladder-ID header (range + cross-doc form); no mile renumbered | human review + suite green |
| Qualifier convention | project `CLAUDE.md` + commit convention | one line states `proof-leg/rulebook Mile N` (short `PL-M<n>`/`RBK-M<n>`) required cross-doc | human review |
| OD-A cops-3 addendum | `docs/PORT_WAVE_MANIFEST.md` | addendum records the 3 new tools (115→118) per `Copernicus:14` | tool-count binding stays green (`test_phase0c_doc1_toolcount.py`) |
| OD-C de-stale | `harness/state/flywheel_queue.json:405` | "Provisional" replaced with the RULED-stands note | human review |
| Blueprint §4 RULED-annotation | `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:143`–`:152` | RULED banner + SSOT pointers atop §4; options preserved | human review |
| Ruling pointers | `SPEC.md:41`, grounding `:34`–`:39` (already consistent) | non-SSOT homes read `→ SSOT`, not restated dispositions | human review |
| Branch-only postmortem resolution | `docs/reviews/h22-per-context-postmortem-2026-07-17.md` (`a3f3dd9`) | merged / closed / master pointer — decided | human decision |
| Full suite | `tests/` | `pytest tests/` green; meta-tests 1–5 unchanged | INTEGRATOR/CI |
| Registry + schema meta-test | `rulebook/manifest.json`, `tests/rulebook/test_rulebook_meta.py` | **DEFERRED** — build only on a real consumer trigger (§4) | P6 human ratify |

---

*Authored by SCRIBE, read-only evidence only. Every `file:line` above was opened this dispatch. Claims I could not resolve locally are absent rather than asserted; none required an `[UNVERIFIED]` tag.*

---

## Execution log — 2026-07-17 (Opus 4.8, FORGE; human "Execute")

MVP cycle run per §4/§5. OD calls taken as recommended: **OD-1 = `RBK-M`** · **OD-2 = one cycle** · **OD-3 = RETINA not registered**.

**Edits applied — prose only; no renumber, no `contracts/` touch, no manifest rehash, no meta-test change:**
- **Bite 1 — four ladder-ID headers** declaring `PL` vs `RBK`: `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` §5, `SPEC.md` §Dispatch table, `SYNAPSE_RULEBOOK.md` §5, `rulebook/RULEBOOK.md` §"Where the miles go". One convention stanza in `CLAUDE.md` → "Mile / ladder citation".
- **Bite 2** — blueprint §4 RULED banner (options table preserved as the start line); `harness/state/flywheel_queue.json` OD-C de-staled ("Provisional" → RULED, stands); `docs/PORT_WAVE_MANIFEST.md` `cops-3` addendum written (115→118 follow-through per OD-A). Pointer homes (`SPEC.md:41`, grounding `:34`–`:39`) were already consistent — untouched.

**Phase 3 — branch-only post-mortem DECISION: merge PR #46.** `docs/reviews/h22-per-context-postmortem-2026-07-17.md` (commit `a3f3dd9`) lands on master via `! gh pr merge 46 --merge --delete-branch` (Joe's action — the auto-mode classifier blocks the agent from `gh pr merge`). The rulings' **dispositions are already SSOT-safe on master** (Copernicus §OPEN DECISIONS + flywheel + this grounding audit), so only the fuller narrative is branch-pending. Decided, not latent.

**Verify:** full `pytest tests/` green; meta-tests 1–5 unchanged; the tool-count binding green (no tool added — the `cops-3` addendum documents a *future* 115→118, not a present change).
