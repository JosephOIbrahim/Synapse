$ErrorActionPreference = 'Stop'
Set-Location C:\Users\User\SYNAPSE
git add README.md docs/BLUEPRINT_WEAK_DOMAINS.md harness/notes/h22/panel-observations-2026-08-16.md
git add harness/autorevise/missions/w5l_crux.json harness/autorevise/missions/w5l_life.json harness/autorevise/missions/w5l_panel.json harness/autorevise/missions/w5l_rope.json harness/autorevise/missions/w5l_shelf.json
git add harness/autorevise/missions/w5m_catalog.json harness/autorevise/missions/w5m_measures.json harness/autorevise/missions/w5m_parmgate.json harness/autorevise/missions/w5m_wcrux.json
git add harness/autorevise/missions/archive/w5h/
git add harness/autorevise/prompts/W5-LIFE.md harness/autorevise/prompts/W5-PANEL.md harness/autorevise/prompts/W5-ROPE.md harness/autorevise/prompts/W5-SHELF.md harness/autorevise/prompts/W5-LCRUX.md
git add harness/autorevise/prompts/W5-CATALOG.md harness/autorevise/prompts/W5-MEASURES.md harness/autorevise/prompts/W5-PARMGATE.md harness/autorevise/prompts/W5-WCRUX.md
git add harness/autorevise/prompts/W5-UNDOB.md harness/autorevise/prompts/W5-STATWT.md harness/autorevise/prompts/W5-CRUXS1.md harness/autorevise/prompts/W5-HYGIENE.md harness/autorevise/prompts/W5-HCRUX.md
git add harness/autorevise/waves/wave5.rows.json harness/autorevise/waves/wave5l.live.json harness/autorevise/waves/wave5h.live.json harness/autorevise/waves/wave5h.rows.json
git add harness/autorevise/arm_w5l.ps1 harness/autorevise/build_manifest_w5l.py harness/autorevise/fold_blueprint_w5l.py
git add harness/notes/h22/status_w5l.ps1 harness/notes/h22/watch_w5l_verdict.ps1 harness/notes/h22/merge_train_w5l.ps1
git commit -m "close(w5l): kits tracked (w5l + substrate + w5h archive), weak-domain blueprint dropped to docs/, panel observations on record, README refreshed (session-survival headline, two mermaid diagrams, tag-truth line) - waves merged on Joe's enumerated word; docket 'track kit or drop' settled: tracked"
git log --oneline -2
git status -sb | Select-Object -First 1
