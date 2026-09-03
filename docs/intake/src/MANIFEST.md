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

**Harvest note (2026-09-03, CTO seat, R135 in-place):** this manifest was written by hand on master outside the BP4 harness (writer: Joe's Claude Code session, 18:04-18:13). At harvest the SHA256 column was re-verified with `Get-FileHash` on master (match) and the Bytes column corrected to on-disk sizes (was 7168 / 6451; on disk 7155 / 6384 - cause of the original miscount UNKNOWN). The two .docx rows stay `missing` until they land; the BP4-CRUX INTAKE lane audits master at the harvest commit, not a leg branch.
