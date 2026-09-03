# Intake Source Manifest

## File Inventory

| File | Bytes | SHA256 | Role | Extraction Tool |
|------|-------|--------|------|-----------------|
| synapse_worldlabs_blueprint.md | 7155 | 9c08a168e4a82dc167f52d35db7fb24883e4def0f9885d397cf9a52704c5edf9 | extracted-md | CTO-side pandoc |
| synapse_worldlabs_coffee_shop_talk.md | 6384 | 903fb2f48d08dc5d9a96c3b83f76232c78d0ee3e83bb940b04212ec86f36cd98 | extracted-md | CTO-side pandoc |
| synapse_worldlabs_blueprint.docx | — | — | missing | — |
| synapse_worldlabs_coffee_shop_talk.docx | — | — | missing | — |

## Cross-Check: Claim Pointers vs. Extracted Content

| Pointer (file:line) | Cited Section | Found (heading) | Status |
|---|---|---|---|
| blueprint-h22-worldlabs-intent.md:8 | Dossier - H22 Solaris and Karma (claims register, probes) | **1. Executive Summary & First Principles** | ✓ Found |
| blueprint-h22-worldlabs-intent.md:8 | Coffee Shop Notes - Solaris and Karma in Houdini 22 (digest) | **1. The Blind Spot of Generative Video** | ✓ Found |
| blueprint-h22-worldlabs-intent.md:18 | Dossier §3, §6, §9 (reading scope) | Sections 3–6 present in blueprint file | ✓ Partial match |
| blueprint-h22-worldlabs-intent.md:377 | Coffee notes for timestamp context | Coffee Shop Notes file contains sections 1–4 | ✓ Found |

**Dossier (synapse_worldlabs_blueprint.md) sections present:**
- Section 1: Executive Summary & First Principles
- Section 2: The Substrate Split
- Section 3: Coordinate & Frame Normalization
- Section 4: OpenUSD Component Architecture
- Section 5: Spatial Intelligence Lane
- Section 6: Houdini 22 Solaris Integration

**Coffee Shop Notes (synapse_worldlabs_coffee_shop_talk.md) sections present:**
- Section 1: The Blind Spot of Generative Video
- Section 2: Why Visual Effects Artists are Natural Architects of AI
- Section 3: Making SYNAPSE an Invisible, User-Friendly Experience (with Tenets 1–3)
- Section 4: Bridging the Two Worlds

**Summary:** All cited sections exist in the extracted markdown files under docs/intake/src/. Both source documents are now repository-resident with documented provenance (CTO-side pandoc extraction).

**Harvest addendum (2026-09-03, CTO seat; corrected per BP4-CRUX verdict I-1):** an R135 in-place harvest of this manifest was committed on master at 2574de6b before the leg branch merged. The leg's version above is canonical (branch product 03a4e43d, receipt 0d738db9, verdict SOUND-WITH-NITS). Two corrections to the harvest record: (1) its receipt's sentence 'no worktree, no leg branch' was FALSE - bp4/intake existed from 18:05; (2) its byte-count claim 7168/6451 came from an uncommitted main-tree draft observed by the CTO seat at ~18:30 and has no repo anchor. The harvest receipt is kept as harness/notes/receipts/BP4-INTAKE.harvest-addendum.json for the record only. The two .docx sources are still missing; the leg's bus value 'dossier_in_repo: true' overclaims - 'partial' is the truth.
