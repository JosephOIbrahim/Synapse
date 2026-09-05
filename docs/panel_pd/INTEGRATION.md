# Panel PD wave -- Integration report

Orchestrator: Claude (Fable 5.1), 2026-09-04 22:40. Branch `pd/panel-integrate` = `pd/panel-lever` + camera + sweep_a + sweep_b, then the QSS splice repair, then CRUX round 2. Head c9429bdd. Nothing pushed; merge to master is Joe's word and **CRUX says no merge**.

## Wave result

| Leg | Commit | CRUX round-2 verdict | chain_broken_at |
|---|---|---|---|
| CENSUS | a5b975c1 | SOUND | -- |
| LEVER | 7b17c0c3 | BROKEN | global residual guard lets an exact removed owner return below the 226 cap |
| CAMERA | da5aac31 | BROKEN | strict raw-zero not met: 2 spacing / 1 sheet in recall_card.py + synapse_panel.py |
| SWEEP_A | ed41ce61 | BROKEN | raw census 12 / 0 / 0 (all tagged); four obsolete chat CSS pins; whole-tail append pin |
| SWEEP_B | ae046513 | BROKEN | HDA Result visual parity beyond gap/label/tag; four sequence probes stop at layout spacing |
| CRUX | 20094e1b | delivered (round 1 verdict captured verbatim, round 2 written by the referee) | -- |

Every worker was committed on its behalf (the Codex sandbox cannot write the worktree index; writable_roots did not help, ACL deny entries).

## The one defect that was the orchestrator's

Merge 0998cc9e resolved the qss.py conflict by keeping A-then-B per hunk; the second hunk had split `sweep_a_style`, so SWEEP_B's block was spliced mid-function and the unpolish/polish/update calls vanished. That was the real cause of the three state-colour failures. Repaired at 38cd9b46 (LEVER prefix + complete SWEEP_A tail + complete SWEEP_B tail, both tails hash-equal to the leg commits per CRUX). Post-repair Qt receipt `harness/panel_pd/runs/2026-09-04/qt_INTEGRATE_post_repair.txt` (Houdini 22.0.400 python313 + PySide6 6.8.3, module bound to this tree): **243 passed, 22 failed**; all three state-colour cases green.

## Suite counts

| Run | passed | failed | skipped |
|---|---:|---:|---:|
| base 6e3dd963 (orchestrator shell) | 6941 | 1 | 192 |
| integrate c5c086cb (orchestrator shell, Python 3.14, no Qt) | 7069 | 8 | 318 |
| CRUX fresh archive (sandbox, Python 3.14) | 7014 | 30 | 351 |

The 8 in the orchestrator shell: 1 pre-existing (test_backfill), 4 obsolete chat-panel CSS-consolidation pins, 3 isolated-green sweep pins. CRUX's extra 22 are archive/sandbox environment classes it names (no git metadata in the archive, orchestration, ACL probe, aging gate) and are not substituted for the shell run.

## Qt tier on the repaired tree (22 reds)

- **15 docking widths**, inherited and unchanged: composed panel 433, QuickActionPills 587-602, HDA ResultView 382-388, HealthStrip 708, SynapseChatPanel 502-514, all vs the 380 px bound, all three densities. Identical widths on the pre-LEVER tree, so the debt predates the wave, but the strict accept is still unmet.
- **4 SWEEP_B sequence probes** stop at layout spacing before geometry; CRUX says the probe conflates control-internal layouts with owned ones. Probe needs splitting by real owner.
- **3 isolated-green test pins** (block order, block prefix, sibling-file freeze) that contradict the append-only contract. CRUX: fix the pins at their real seams, do not delete or weaken.

## CRUX rulings that need Joe (crux.json `for_ruling`)

1. **Residual.** 62 sites remain (18 spacing, 2 sheets, 42 hex), 47 untagged, against the plan's "at most 20, all tagged"; the guard cap sits at 226 with 164 sites of slack and a seed that lets a removed owner come back. Assign the remaining colour/rhythm owners (health_strip, integrity_readout, agent_health, render_preflight are the named unowned files) or waive the 20-site target explicitly.
2. **Docking scope + HDA parity.** The fifteen widths and SWEEP_B's HDA Result surface/button change (white table + native buttons became dark surfaces + a filled SIGNAL action, also serving Describe/Building) need a decision: fix, or waive with a written parity exemption. No GUI approval is requested by the receipt; your eyes on .400 remain the red gate.

## Blocking nits before any merge word (CRUX R2-01..07)

R2-01 residual/guard seed (LEVER + integrator) · R2-02 move the four chat CSS oracles to the QSS seam (SWEEP_A) · R2-03 fence-scope the three pins (sweep test owners) · R2-04 the fifteen widths (CAMERA/SWEEP_A/SWEEP_B/unassigned health_strip) · R2-05 split the SWEEP_B probes by owned layout · R2-06 HDA parity · R2-07 CLOSED by the post-repair Qt receipt above. Non-blocking: R2-08 archive git-history loop is vacuous (verification gap), R2-09 inherited doubled-brace rule, R2-10 receipt provenance wording.

## What the wave did deliver

One owner of rhythm: `designsystem/rhythm.py` + role rules in `designsystem/qss.py` + a compositor hook (5 lines added / 1 removed), spec v2, guard + docking tests, the census CLI + region map, five camera regions on roles, the recall card, 18 modules migrated, 104 hex sites mapped to existing tokens (no new tokens, no new fonts, no Cohere branding, verified by CRUX), before/after screenshot sets (now un-gitignored under design/rhythm_pd), and receipts for everything. Panel-wide imperative spacing went 107 -> 18, inline sheets 106 -> 2, raw hex 135 -> 42.

## Next actions

1. Joe rules on the two `for_ruling` items.
2. A follow-up leg (or legs) for R2-01..06 on top of `pd/panel-integrate`, then CRUX round 3.
3. Joe's GUI sign-off on H22.0.400: profile tab strip, header/ribbon, chat transcript, verb rail, recall card, TOKEN face, in three profiles.
4. Merge word.
