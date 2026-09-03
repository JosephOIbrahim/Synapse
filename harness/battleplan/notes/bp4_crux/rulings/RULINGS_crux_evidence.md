# BP4-RULINGS — CRUX audit evidence

**Lane:** RULINGS · **Target:** branch `bp4/rulings` @ a62267f9 (product ff3d6f73), base 28a0e183
**Method:** fresh `git clone --shared` scratch checkout (SCR_R), own Python re-derivation of every check, own mutations.

## T-A: Recount

Per-file `for_ruling` length, recomputed directly from the seven `harness/notes/receipts/BP3-*.json` files in SCR_R (`python3 -c "import json,glob..."`, re-run twice, identical both times):

| File | for_ruling len | banked/open/for_joe keys present |
|---|---|---|
| BP3-CORPUS.json | 7 | none |
| BP3-CRUX.json | **1** | none |
| BP3-PANEL.json | 1 | none |
| BP3-PROBE.json | 5 | none |
| BP3-RECON.json | 3 | none |
| BP3-STUBS.json | 2 | none |
| BP3-TIDY.json | 3 | none |
| **TOTAL** | **22** | |

This matches the brief's own expected breakdown exactly (RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 1, TIDY 3 = 22) and the referee's pre-count hint (BP3-CRUX.json for_ruling length 1).

`BP3-CRUX_verdicts.md` (grep -n -i "ruling"): one hit, line 97, "**Confirmed for-ruling (builder's own, re-anchored by crux):** the lane diff's verbatim contract path `schemas/world_manifest.schema.json`...". This restates/re-anchors the BP3-STUBS item (table rows 17/18 territory) — it does not introduce a *new* distinct item beyond what BP3-CRUX.json's own `for_ruling[0]` already states (which is itself a near-duplicate wording of the same restatement — the two are companion texts, not two separate findings). No additional ruling items found here beyond the receipt array.

`BP3_TIDY.md` "## Ruling" section (lines 141-149): four `For Joe/CTO:` bullets restating T1-T4 conclusions (no action / no action / no action / optional git mv). These correspond to TIDY-R1/R2/R3 already counted in `BP3-TIDY.json:for_ruling` — no new items.

**Product recount:**
- Summary table: 21 data rows (parsed by `| # |` header + pipe-row scan)
- "Full Item Details": 21 `### Row N` sections (N = 1..21, no gaps, no dupes)
- Count line (verbatim): `**Row count:** 21 (expected 22; RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 0, TIDY 3)`
- Delta note (verbatim): `**Delta note:** CRUX expected 1 item, found 0. BP3-CRUX_verdicts.md contains verdict rows on receipts, not distinct for_ruling entries. No new ruling items elevated from CRUX verdicts.`

**Verdict: FAIL.** Table row count (21) does NOT equal the crucible's own recount (22). The missing item is:

> **id:** none (plain string entry, not a dict) · **source:** `harness/notes/receipts/BP3-CRUX.json:for_ruling[0]`
> **verbatim text:** "Confirmed and re-anchored the BP3-STUBS ruling item: the lane diff's verbatim §3.2 contract path 'schemas/world_manifest.schema.json' (BP3_lane_spatial.diff L19) points at a directory with 0 tracked files; actual schema_home is docs/intake/ (blueprint L9 Sidecars line already agrees). The verbatim lane text must be reconciled BEFORE the diff is ever applied. The diff itself remains unapplied and apply-check-clean."

**Root cause:** the builder's brief names the source glob as `harness/notes/receipts/BP3-*.json` `for_ruling` arrays — a pattern that unambiguously includes `BP3-CRUX.json` (present in SCR_R at the base commit, same directory as the other six files the builder DID read correctly). The builder instead searched `harness/battleplan/notes/BP3-CRUX_verdicts.md` (a markdown analysis doc with no `for_ruling` array) for the CRUX contribution and, finding none there, concluded "found 0". It never opened `BP3-CRUX.json` itself. Credit where due: the builder's own brief instructs "a different count is a FINDING you report... never a rounding," and the builder DID surface the 21-vs-22 gap rather than silently claiming 22 or hiding the shortfall — but the stated root cause ("no new for_ruling array" in the verdicts.md) is incomplete/wrong because it never checked the one file that actually holds CRUX's array. The acceptance predicate ("table row count equals the for_ruling total the crucible recounts") still fails on the facts, honest flagging notwithstanding.

## T-B: Verbatim claims (21/21 rows present)

Per-row equality between the "Full Item Details" blockquote and the anchored receipt's `for_ruling[i]` (PANEL's entry is a dict `{item, context}` — the table correctly extracts the `item` subfield, not the whole dict):

| Row | Anchor | Exact match | Table-cell prefix-of-verbatim |
|---|---|---|---|
| 1 | BP3-RECON.json:for_ruling[0] | EXACT | OK |
| 2 | BP3-RECON.json:for_ruling[1] | EXACT | OK |
| 3 | BP3-RECON.json:for_ruling[2] | EXACT | OK |
| 4 | BP3-PANEL.json:for_ruling[0] (dict.item) | EXACT | OK |
| 5–9 | BP3-PROBE.json:for_ruling[0..4] | EXACT ×5 | OK ×5 |
| 10–16 | BP3-CORPUS.json:for_ruling[0..6] | EXACT ×7 | OK ×7 |
| 17–18 | BP3-STUBS.json:for_ruling[0..1] | EXACT ×2 | OK ×2 |
| 19–21 | BP3-TIDY.json:for_ruling[0..2] | EXACT ×3 | OK ×3 |

**21/21 exact matches, 0 mismatches, 0 whitespace-only matches** (exact == whitespace-normalized count, so no hidden reformatting either). Every summary-table "claim (truncated)" cell strips to a true string-prefix of its row's verbatim claim (21/21 OK) — the truncation mechanism itself is sound.

**Column-spec discrepancy (judgment call, not a listed acceptance predicate):** the brief's T1 target specifies a 9-column table `# | leg | item id | severity | claim (verbatim) | anchor | receipt recommendation (verbatim or 'none stated') | CTO ruling | ratification (Joe) yes/no`. The actual table has **8 columns**: `# | leg | item_id | claim (truncated) | anchor | recommendation | CTO ruling | ratification` — the **severity column is entirely absent**, and the claim column is self-labeled "(truncated)" rather than "(verbatim)". The full verbatim text does exist (in the Full Item Details section, confirmed 21/21 exact above), so no claim content is lost — but the summary table itself does not match the brief's literal column shape, and `severity` (available on RECON's `findings[]` entries as "ruling"/"hazard"/"info" for M-1/M-2/D-DEP-03, but never carried into `for_ruling` strings) was dropped rather than cross-referenced.

## T-C: Anchors, recommendations, PENDING

- **Anchor resolution:** 21/21 anchors parse (`<file>:for_ruling[<idx>]`) and the index resolves inside that file's array. 0 failures.
- **Recommendation provenance:** non-"none stated" cells appear only on rows 1, 2, 4 (RECON M-1/M-2, PANEL). All three are drawn verbatim from their source receipt's `findings[]`/acceptance-evidence text (M-1 → RECON findings[0].claim; M-2 → RECON findings[1].claim; PANEL-SCOPE → PANEL acceptance[1].evidence, second sentence). All other 18 rows correctly show "none stated" (their source receipts genuinely give no separate recommendation for those for_ruling strings).
- **PENDING count:** summary table 21/21 PENDING; detail sections 21/21 "**CTO Ruling:** PENDING". (The brief's own T-C task text anticipates "21 + 21" — consistent with what's actually in the table, but both counts inherit the T-A undercount: a correct 22-row table would need 22+22 to satisfy the same "all-PENDING" property.)

## T-D: Ratification column

**Receipt finding #3 (verbatim):** "Ratification flags set per brief criteria: M-1, M-2, D-DEP-03, D3.1, D3.2 marked yes; all others no." Anchor given: "harness/notes/CTO_RULINGS_BP3.md summary table, ratification column."

**Actual values, read directly from the table:**

| Row | Item | Ratification |
|---|---|---|
| 1 | M-1 | yes |
| 2 | M-2 | yes |
| 3 | D-DEP-03 | yes |
| 17 | D3.1 (STUBS[0]) | **no** |
| 18 | D3.2 / STUBS-2 | **no** |

**Finding: the receipt's own claim is FALSE for 2 of its 5 named items.** Rows 17 and 18 (D3.1, D3.2) are marked "no" in the actual product, not "yes" as the receipt asserts. This is a receipt self-report that does not match its own committed product.

**Judgment-call findings (not an acceptance predicate — flagged as instructed):** rows whose claims explicitly propose flipping a corpus tier or a settings fence, per the brief's own ratification rule ("yes when the item would flip... a corpus tier... or a settings fence"), yet carry "no":
- Row 10 CORPUS-1 — proposes ratifying 8 Table-A tier promotions to VERIFIED-RUNTIME/FIXTURE-VERIFIED. ratification=no.
- Row 11 CORPUS-2 — proposes promoting BLU-04 UNKNOWN→FIXTURE-VERIFIED. ratification=no.
- Row 12 CORPUS-3 — proposes promoting node-existence to VERIFIED-RUNTIME. ratification=no.
- Row 20 TIDY-R2 — proposes an explicit settings/permissions-fence edit (readonly-settings.json allow/deny lists). ratification=no.

These four read as textbook corpus-tier/settings-fence flips under the brief's own stated rule; whether they should have been "yes" is a judgment call for the CTO seat, not a mechanical failure, but it is inconsistent with how rows 1-3 were classified from materially similar language ("a human may promote...").

## T-E: Capsule mapping (T2 section)

Confirmed against the product's own "Capsule Recommendations Mapping (T2)" table: M-1→row 1, M-2→row 2, D-DEP-03→row 3, PANEL scope→row 4 (item_id PANEL-SCOPE), TIDY-R1→row 19. All 5 rows carry the claimed item_id. **PASS.**

## T-F: Bus finding

`grep` over `harness/battleplan/bus/bp4/bus.jsonl` for `frm==BP4-RULINGS, type==finding`:

```json
{"ts": "2026-09-03T18:14:10", "n": "18d1ef4f2f56f2b8", "wave": "bp4", "frm": "BP4-RULINGS", "to": "*", "type": "finding",
 "body": {"claim": "rulings table compiled: 21 rows (expected 22; CRUX yielded 0 distinct items)",
          "anchor": "harness/notes/CTO_RULINGS_BP3.md"}}
```

Record exists exactly as the receipt's acceptance[2] cites (n, ts, frm match). **PASS** on the acceptance predicate itself ("bus finding posted with the row count and the file anchor") — the record exists and carries both. Note the bus claim text also bakes in the same wrong "CRUX yielded 0 distinct items" conclusion, propagating the T-A error onto the wave-visible record.

## T-G: Nits

1. **Row 17 item_id is a claim fragment, not an id.** Table/detail header both read `D3.1 lane diff is a proposal (ratified` as the item_id — confirmed verbatim in both the table cell and the `### Row 17:` header. Root cause (inferred from the pattern, not asserted as fact): the source STUBS `for_ruling[0]` string is `"D3.1 lane diff is a proposal (ratified:false). Before it is applied..."` with no clean short-id prefix; an "everything before the first colon" extraction heuristic would grab exactly `D3.1 lane diff is a proposal (ratified` (stopping at the colon inside `(ratified:false)`) — which is what appears. STUBS's second item, by contrast, got a clean synthesized id `STUBS-2`. The extraction logic is inconsistent across the two STUBS entries.
2. **Encoding: the product file is not valid UTF-8.** `open(path, encoding='utf-8')` raises `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 14: invalid start byte`. A full-file scan found exactly 2 bad byte offsets in 12,721 bytes: offset 14 (`0x97`, cp1252 em dash "—", in the H1 title `CTO RULINGS — BP3 Compilation`) and offset 74 (`0xb7`, cp1252 middle dot "·", in the byline `(Haiku 4.5) · 2026-09-03`). Both are cp1252 single-byte encodings of characters that should have been multi-byte UTF-8 (the file elsewhere correctly uses UTF-8 `\xc2\xa7` for "§", e.g. in row 1's claim), so this is a mixed-encoding artifact confined to the header/byline — it does not corrupt any claim, anchor, or ruling cell content.

## T-H: Mutations (all in SCR_R only; baseline confirmed green before each; restored + re-greened after each; final `git status --short` empty)

| id | description | targeted check | result | evidence |
|---|---|---|---|---|
| RULINGS-M1 | Row 6 detail blockquote: "this fixture is 46,993 tris." → "...46,994 tris." (byte-level replace, unique substring, isolated 1-line diff) | T-B verbatim-equality for row 6 | **REDDENED** | Exact matches 21→20; Row 6 flips EXACT→MISMATCH; rows 1-5,7-21 stay EXACT |
| RULINGS-M2 | Row 9 summary-table ruling cell: `PENDING`→`ACCEPT` (single cell, table only, detail line untouched) | T-C all-PENDING count (table column) | **REDDENED** | Table PENDING count 21/21→20/21; detail-section PENDING count correctly stays 21/21 (proves the two counters are independent, not double-counting the same text) |
| RULINGS-M3 (bonus) | Delete summary-table row 21 (TIDY-R3) entirely, 1 line removed | Internal consistency: table row count == "### Row N" detail-section count | **REDDENED** | Table rows 21→20; detail sections stay 21; 20≠21 (was 21==21) |

All three: restored via `git show HEAD:harness/notes/CTO_RULINGS_BP3.md > harness/notes/CTO_RULINGS_BP3.md`, re-run confirmed re-green (M1: 21/21 exact; M2: 21/21 PENDING both counters; M3: 21 table rows / 21 detail sections), and `git status --short` printed nothing after the final restore. Byte-level restore also verified: header bytes at offset 14/74 are back to `0x97`/`0xb7` (the original mixed-encoding bytes), not corrupted by the restore path.

**Process note:** an early pass at M1 used a text-mode Python read/write (`encoding='utf-8', errors='replace'`) which silently re-encoded the two pre-existing bad header bytes into U+FFFD replacement characters as a side effect of the round-trip — an unintended second mutation beyond the targeted one-word change. Caught before recording a result; discarded via `git show HEAD:... >` restore and redone with a binary-mode byte-level replace that touches only the targeted substring. Recorded here because it is itself a small illustration of how easy silent corruption is on a file with a real encoding defect.
