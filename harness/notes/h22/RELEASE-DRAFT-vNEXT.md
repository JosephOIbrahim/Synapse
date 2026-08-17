# v5.51.0 (proposed) - Close the tab, keep the session

Draft release notes for the build after v5.50.0. Publish is gated at ritual step g9; this document tracks everything merged to master and pushed as of 2026-08-16 evening. All claims below are receipt-backed on master.

## For artists

**Closing the SYNAPSE panel tab no longer kills your session.** The runtime heartbeat was parented to the panel widget (defect P0.3); it now lives in the runtime itself. Build something, close the tab mid-operation, reopen the panel - the session, its history, and its undo stack are still there. This is the headline fix, and it is now pinned by a behavioral test that fails if anyone ever re-parents the beat.

**The panel you see is provably the code in the repo.** An adversarial crucible re-executed the parity probes under real hython 22.0.400: all 90 panel modules load byte-identical from the repo, zero shadow installs anywhere on the path, all seven shelf icons resolve in-repo, and the panel's exec/flush loader genuinely re-imports fresh on every reopen. Close and reopen the panel after a code change and you are running that change - no Houdini restart.

**Text never shrinks below the floor.** Both font-scale entry points (the Aa button and the "Larger text" menu) now route through the token ladder - the R1 regression class is closed at both sites.

**Flow fixes, measured not opined.** Six canonical user journeys (first build, multi-node rig, error recovery, mode switch, palette, close-reopen) were mapped from lived evidence and driven end-to-end by a journey rig under hython. Two panel-side fixes shipped, each proven red-then-green by the rig, and three adversarial journeys - garbage prompt mid-build, panel close mid-journey, rapid mode-switch - all survive with the session intact.

**Sessions now scope to the Houdini boot.** Closing the panel tab reattaches to the same session (the headline fix, unchanged) - but a fresh Houdini launch now starts clean instead of auto-loading yesterday's conversation. The previous boot's work is parked, never destroyed: one command, `/restore-session`, brings the full history back. Pre-existing stores from older builds park safely on first contact and restore the same way.

## Under the hood

**The harness now enforces what it used to merely say.** A failure-class ledger (`harness/HARDENING-SPEC.md`) mined every receipt, finding, and ruling in the project's history into named classes with a one-token honesty vocabulary (WIRED / WIRED-BUT-HOLLOW / WARN-ONLY / PROSE-ONLY / NONE). Four builders then moved the worst classes to enforced gates, and a crucible proved every gate goes RED on a simulation of its original defect:

- **Injection class killed.** `Sanitize-SQ` helpers plus a 41-test adversarial-name matrix through the real PowerShell parser; 17 fresh payloads in crucible re-attack, zero reached a command position.
- **Provenance is fail-closed.** The check that had returned warn-only by construction since June now fails task verdicts; a forced bypass in a scratch tree reads RED.
- **The heartbeat gate reads behavior, not source strings.** Marker present but beat hollowed = RED.
- **A leg is not done until its receipt commit IS the branch HEAD and a RELEASE line is on the bus.** The receipt-without-commit class (~12 lived instances across four waves) is structurally closed in the orchestrator state machine.
- Composed tree: 6572 passed / 0 failed, ratchet +67, zero regressions.

One operator close-pass was performed per R135 and recorded openly in the W6-HCRX verdict: the GATE leg's own receipt commit and two missing RELEASE lines - the wave's thesis, caught live on its own authors by its own gate.

The gates are not just merged - they are the running supervisor. On first boot of the hardened orchestrator it retroactively audited the full 22-leg wave history and held eight historical legs at `closing` with exact-missing messages (unposted RELEASE lines, one uncommitted receipt), touching nothing on master. The enforcement is live, honest about the past, and on duty for every future wave.

**Substrate progress.** The compiled parameter-name catalog (W5-CATALOG) and the parameter gate (W5-PARMGATE) are complete; the cook-verify measurement layer (W5-MEASURES) is in flight with its crucible (W5-WCRUX) queued behind it. Those land in the next update to this draft.

## Honest state

Still RED, unchanged by this span: `mutation_fail_closed`, `hot_reload_gated`, `installer_host_targeted`, `ci_covers_shipping_surface`. G3 remains pending-drop (human-only `drop.json` write). GUI-required checks remain UNKNOWN until the operator's seat exercises them - the seat checklist is three items: print `hou.applicationVersion()` + a panel module `__file__` from the live panel; edit a panel module and see the edit after close/reopen with no restart; launch explicitly from the `22.0.400\bin` (five builds share one prefs dir and nothing pins the default).

Corrected from the previous draft of these notes: `provenance_not_bypassed` is no longer unwired - it is WIRED and fail-closed on master.

## Ritual state

Operator gates walked at the live seat this evening, all receipt-backed on master: **g1 clean install - g5 lifecycle (the halted gate, now PASS on the fixed build: P0.3 dead by operator hands) - g6 core smoke - g7 reversibility (one Ctrl+Z reversed an entire multi-part build; the long-standing W5-UNDO-GUI receipt is discharged) - g8 restart.** The machine verify on this HEAD is the cleanest on record: 6580 passed / 0 failed, guardrail violations empty, guardrail unwired empty.

**g9 (rollback) surfaced a real finding and awaits ruling:** removing the package with a stale desktop still referencing the panel crashes Houdini's native icon paint (`QIcon::operator=` in libUI - a SideFX-side segfault our uninstall residue triggers; zero Python or SYNAPSE frames in the dump). The gate did its job. Publish follows the g9 ruling, the version bump across six surfaces, a final verify, and the tag - in that order. v5.50.0 remains Latest until then.
