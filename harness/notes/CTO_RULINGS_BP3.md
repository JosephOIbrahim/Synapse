# CTO RULINGS � BP3 Compilation

**Compiled by:** BP4-RULINGS (Haiku 4.5) � 2026-09-03
**Source:** Seven BP3 receipt files + CRUX verdicts
**Note:** All CTO ruling cells PENDING (leg extracts, never rules)

## Summary Ruling Table

| # | leg | item_id | claim (truncated) | anchor | recommendation | CTO ruling | ratification |
|---|---|---|---|---|---|---|---|
| 1 | RECON | M-1 | M-1: is docs/intake/world_manifest.schema.json the canonical home, or ... | BP3-RECON.json:for_ruling[0] | Blueprint §3.2 contract + D3.2 cite schemas/world | PENDING | yes |
| 2 | RECON | M-2 | M-2: should SYNAPSE_HYTHON be pinned to 22.0.400 at the wave/env level... | BP3-RECON.json:for_ruling[1] | SYNAPSE_HYTHON unset + no hython on PATH => .synap | PENDING | yes |
| 3 | RECON | D-DEP-03 | D-DEP-03: existing bounds code is hou-based; confirm (a) match-existin... | BP3-RECON.json:for_ruling[2] | none stated | PENDING | yes |
| 4 | PANEL | PANEL-SCOPE | Scope interpretation of 'layout files': the change set was confined to... | BP3-PANEL.json:for_ruling[0] | T4 acceptance names 'designsystem/manifests/qss/la | PENDING | no |
| 5 | PROBE | PROBE-1 | Promotion of runtime-confirmed claims (P-1/P-3/P-5/P-7/P-8/P-9/B-1/B-4... | BP3-PROBE.json:for_ruling[0] | none stated | PENDING | no |
| 6 | PROBE | PROBE-2 | WL-EX-03 '100-200k tris' should be re-tiered to fixture-dependent: thi... | BP3-PROBE.json:for_ruling[1] | none stated | PENDING | no |
| 7 | PROBE | PROBE-3 | 6 probe defects (above) need a human decision to fix the probe script ... | BP3-PROBE.json:for_ruling[2] | none stated | PENDING | no |
| 8 | PROBE | PROBE-4 | G-1 evidence: <=200k + proxy landing found; manifold check + scatter-a... | BP3-PROBE.json:for_ruling[3] | none stated | PENDING | no |
| 9 | PROBE | PROBE-5 | D-DEP-01 (GSOPs) can lean 'native-only' given B-5, but the decision is... | BP3-PROBE.json:for_ruling[4] | none stated | PENDING | no |
| 10 | CORPUS | CORPUS-1 | Ratify the 8 Table-A promotions (7 VERIFIED-RUNTIME node/parm/menu on ... | BP3-CORPUS.json:for_ruling[0] | none stated | PENDING | no |
| 11 | CORPUS | CORPUS-2 | BLU-04: B-4 resolved it TRUE (stdout.txt:300). A human may promote UNK... | BP3-CORPUS.json:for_ruling[1] | none stated | PENDING | no |
| 12 | CORPUS | CORPUS-3 | WL-HOU-02/WL-HOU-03: B-5 confirms native splat node types exist on 22.... | BP3-CORPUS.json:for_ruling[2] | none stated | PENDING | no |
| 13 | CORPUS | CORPUS-4 | WL-EX-03 tri-count refutation (46,993 < 100k) contradicts the DOC-STAT... | BP3-CORPUS.json:for_ruling[3] | none stated | PENDING | no |
| 14 | CORPUS | CORPUS-5 | 167-vs-138 scatterinstances parm count: reconcile the counting method ... | BP3-CORPUS.json:for_ruling[4] | none stated | PENDING | no |
| 15 | CORPUS | CORPUS-6 | P-6 probe defect (label-search ambiguity) is BP3-PROBE territory; fix ... | BP3-CORPUS.json:for_ruling[5] | none stated | PENDING | no |
| 16 | CORPUS | CORPUS-7 | Dossier + coffee notes are not in the repo (dossier_in_repo=false); do... | BP3-CORPUS.json:for_ruling[6] | none stated | PENDING | no |
| 17 | STUBS | D3.1 lane diff is a proposal (ratified | D3.1 lane diff is a proposal (ratified:false). Before it is applied by... | BP3-STUBS.json:for_ruling[0] | none stated | PENDING | no |
| 18 | STUBS | STUBS-2 | D3.2 blueprint V0 path for the schema is 'schemas/' (sec.3.7 D3.2) but... | BP3-STUBS.json:for_ruling[1] | none stated | PENDING | no |
| 19 | TIDY | TIDY-R1 | TIDY-R1: accept the T1..T4 census as read-only evidence with T1 merged... | BP3-TIDY.json:for_ruling[0] | none stated | PENDING | no |
| 20 | TIDY | TIDY-R2 | TIDY-R2: profile fix - remove Bash(git add:*) and Bash(git commit:*) f... | BP3-TIDY.json:for_ruling[1] | none stated | PENDING | no |
| 21 | TIDY | TIDY-R3 | TIDY-R3: T4 scratch migration (54 files, 146 KB) is optional; recommen... | BP3-TIDY.json:for_ruling[2] | none stated | PENDING | no |

**Row count:** 21 (expected 22; RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 0, TIDY 3)

**Delta note:** CRUX expected 1 item, found 0. BP3-CRUX_verdicts.md contains verdict rows on receipts, not distinct for_ruling entries. No new ruling items elevated from CRUX verdicts.

## Capsule Recommendations Mapping (T2)

CTO recommendations pre-identified in docs/intake/blueprint-h22-worldlabs-intent.md capsule 2026-09-03:

| Capsule Item | Maps to Row | Item ID | Match Status |
|---|---|---|---|
| M-1 schema stays docs/intake | 1 | M-1 | Matched |
| M-2 pin hython 22.0.400 now | 2 | M-2 | Matched |
| D-DEP-03 hou | 3 | D-DEP-03 | Matched |
| PANEL narrow scope accepted | 4 | PANEL-SCOPE | Matched |
| TIDY-R1 T1 merged status UNKNOWN | 19 | TIDY-R1 | Matched |

---

## Full Item Details (verbatim)

### Row 1: RECON / M-1

**Claim:**
> M-1: is docs/intake/world_manifest.schema.json the canonical home, or should it move to schemas/ (and the schema-consuming legs follow)? Human + CTO word.

**Anchor:** harness/notes/receipts/BP3-RECON.json:for_ruling[0]

**Receipt Recommendation:** Blueprint §3.2 contract + D3.2 cite schemas/world_manifest.schema.json, but the schema landed at docs/intake/world_manifest.schema.json; schemas/ has 0 tracked files.

**CTO Ruling:** PENDING

**Ratification:** yes

### Row 2: RECON / M-2

**Claim:**
> M-2: should SYNAPSE_HYTHON be pinned to 22.0.400 at the wave/env level so PROBE runs on the symbol-table build?

**Anchor:** harness/notes/receipts/BP3-RECON.json:for_ruling[1]

**Receipt Recommendation:** SYNAPSE_HYTHON unset + no hython on PATH => .synapse/hytest.py picks NEWEST install = 22.0.429 (no 22.0.429 symbol table). Pin SYNAPSE_HYTHON to the 22.0.400 hython so probes match the recon'd symbol table.

**CTO Ruling:** PENDING

**Ratification:** yes

### Row 3: RECON / D-DEP-03

**Claim:**
> D-DEP-03: existing bounds code is hou-based; confirm (a) match-existing=hou for the §3.4 spatial tools (reported, not decided — D-1).

**Anchor:** harness/notes/receipts/BP3-RECON.json:for_ruling[2]

**CTO Ruling:** PENDING

**Ratification:** yes

### Row 4: PANEL / PANEL-SCOPE

**Claim:**
> Scope interpretation of 'layout files': the change set was confined to designsystem/qss.py (the token-authority stylesheet). synapse_panel.py (a layout module) and the ~30 inline-styled feature modules were AUDITED but not edited - synapse_panel.py because its lifecycle/timer ranges are untouchable and its 13 px are layout margins better migrated with objectNames (BP2 follow-up), and the feature modules because they are outside designsystem/ authority and BP2's 'leave the pair' ruling covers styles.py. If the intended scope was broader (touch feature-module inline styles), that is BP3-INLINE-HEX / BP3-STYLES-MIGRATE, held below.

**Anchor:** harness/notes/receipts/BP3-PANEL.json:for_ruling[0]

**Receipt Recommendation:** T4 acceptance names 'designsystem/manifests/qss/layout files'; the safe, byte-identical, in-authority reading is designsystem/qss.py. Best achievable verdict is SOUND-WITH-NITS regardless (the gui_required acceptance is structurally UNKNOWN, crucible criterion 4).

**CTO Ruling:** PENDING

**Ratification:** no

### Row 5: PROBE / PROBE-1

**Claim:**
> Promotion of runtime-confirmed claims (P-1/P-3/P-5/P-7/P-8/P-9/B-1/B-4/B-5/B-6) to VERIFIED-RUNTIME is D-1's (human+CTO), not this leg's.

**Anchor:** harness/notes/receipts/BP3-PROBE.json:for_ruling[0]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 6: PROBE / PROBE-2

**Claim:**
> WL-EX-03 '100-200k tris' should be re-tiered to fixture-dependent: this fixture is 46,993 tris.

**Anchor:** harness/notes/receipts/BP3-PROBE.json:for_ruling[1]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 7: PROBE / PROBE-3

**Claim:**
> 6 probe defects (above) need a human decision to fix the probe script - the mission forbids the leg editing harness/probes/.

**Anchor:** harness/notes/receipts/BP3-PROBE.json:for_ruling[2]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 8: PROBE / PROBE-4

**Claim:**
> G-1 evidence: <=200k + proxy landing found; manifold check + scatter-accepts-proxy still owed before D-1 could consider opening.

**Anchor:** harness/notes/receipts/BP3-PROBE.json:for_ruling[3]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 9: PROBE / PROBE-5

**Claim:**
> D-DEP-01 (GSOPs) can lean 'native-only' given B-5, but the decision is the human's.

**Anchor:** harness/notes/receipts/BP3-PROBE.json:for_ruling[4]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 10: CORPUS / CORPUS-1

**Claim:**
> Ratify the 8 Table-A promotions (7 VERIFIED-RUNTIME node/parm/menu on 22.0.400 + WL-EX-02 FIXTURE-VERIFIED PLY-500k). Promotion is human+CTO per D-1; this leg only proposes.

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[0]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 11: CORPUS / CORPUS-2

**Claim:**
> BLU-04: B-4 resolved it TRUE (stdout.txt:300). A human may promote UNKNOWN -> FIXTURE-VERIFIED; this leg's rule held it put (not a WL-* row).

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[1]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 12: CORPUS / CORPUS-3

**Claim:**
> WL-HOU-02/WL-HOU-03: B-5 confirms native splat node types exist on 22.0.400 (bakegsplat/labs::relight_gsplats::1.0-1.1/rasterizegsplats, stdout.txt:305-316), clearing R-4 and informing D-DEP-01 (native path exists). B-5 is outside the B-1..B-4 window so this leg left them DOC-STATED; a human may promote node-existence to VERIFIED-RUNTIME.

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[2]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 13: CORPUS / CORPUS-4

**Claim:**
> WL-EX-03 tri-count refutation (46,993 < 100k) contradicts the DOC-STATED 100-200k window for this fixture -> re-tier / re-read on drift (R-3), do not overwrite.

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[3]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 14: CORPUS / CORPUS-5

**Claim:**
> 167-vs-138 scatterinstances parm count: reconcile the counting method before any corpus cites a parm count.

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[4]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 15: CORPUS / CORPUS-6

**Claim:**
> P-6 probe defect (label-search ambiguity) is BP3-PROBE territory; fix constrains the search to the exact imagefilter type before sec.5 Q4 can be answered.

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[5]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 16: CORPUS / CORPUS-7

**Claim:**
> Dossier + coffee notes are not in the repo (dossier_in_repo=false); dossier sec.5 Q1/Q3/Q5-Q10 tensions remain unreachable until the human drops them (RECON T4).

**Anchor:** harness/notes/receipts/BP3-CORPUS.json:for_ruling[6]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 17: STUBS / D3.1 lane diff is a proposal (ratified

**Claim:**
> D3.1 lane diff is a proposal (ratified:false). Before it is applied by human+CTO (D-1, two keys): reconcile the lane's `contract` field from the verbatim 'schemas/world_manifest.schema.json' to the reconciled schema_home 'docs/intake/world_manifest.schema.json', and confirm the new top-level "lanes": [ ... ] container shape.

**Anchor:** harness/notes/receipts/BP3-STUBS.json:for_ruling[0]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 18: STUBS / STUBS-2

**Claim:**
> D3.2 blueprint V0 path for the schema is 'schemas/' (sec.3.7 D3.2) but the schema landed at docs/intake/ (schema_home). No move performed. If the ratifiers want the schema under schemas/ instead, that is a git mv + a blueprint Sidecars-line edit (T4) to run in a follow-up -- not done here because RECON's reconciled schema_home is docs/intake/.

**Anchor:** harness/notes/receipts/BP3-STUBS.json:for_ruling[1]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 19: TIDY / TIDY-R1

**Claim:**
> TIDY-R1: accept the T1..T4 census as read-only evidence with T1 merged status marked UNKNOWN (not not-merged); no prune proposals stand from this leg.

**Anchor:** harness/notes/receipts/BP3-TIDY.json:for_ruling[0]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 20: TIDY / TIDY-R2

**Claim:**
> TIDY-R2: profile fix - remove Bash(git add:*) and Bash(git commit:*) from readonly deny (keep push/merge/checkout/reset denied) and add Bash(git branch --merged:*) to allow; one-line PR for the hardening wave.

**Anchor:** harness/notes/receipts/BP3-TIDY.json:for_ruling[1]

**CTO Ruling:** PENDING

**Ratification:** no

### Row 21: TIDY / TIDY-R3

**Claim:**
> TIDY-R3: T4 scratch migration (54 files, 146 KB) is optional; recommend a single git mv batch post-demo.

**Anchor:** harness/notes/receipts/BP3-TIDY.json:for_ruling[2]

**CTO Ruling:** PENDING

**Ratification:** no

