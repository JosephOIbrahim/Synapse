# G1 acceptance — run AFTER merging crucible-cleared lanes

## 1. Live re-probe (the wave's whole point)
Bridge must be RESTARTED first — it loads modules at startup, so a merged fix is
NOT live until Houdini reloads the package. Re-probing without a restart proves nothing.

  synapse_memory_write {entry_type:"decision", scope:"project", content:{...}}
    PASS = ok/written:true          FAIL = WinError 5 on <install>/bin/claude
  synapse_health
    PASS = write_plane present and == ok
  synapse_memory_status
    PASS = entries_total increments vs the pre-probe read
  synapse_doctor
    PASS = version check no longer a false FAIL (G1c, if that lane landed)

## 2. Pre-fix baseline — CAPTURED LIVE 2026-08-02 11:34 (master, pre-G1)
  memory_status entries_total = 13
  memory_write {entry_type:"note", scope:"project"} =>
    [WinError 5] Access is denied:
    'C:\Program Files\Side Effects Software\Houdini 22.0.397in\claude'
  health => healthy:true, NO write_plane field (the G1b blind spot, reproduced)
  This is the exact signature the fix must eliminate. Binary test: same call
  post-fix returns written:true, or the fix did not work.

## 3. If memory_write STILL fails post-restart
Do NOT re-dispatch blind. Capture the exact path in the error and compare against
scene_memory.resolve_hip_dir / ensure_scene_structure's resolved dirs — a THIRD
resolver would be the finding (store.py = PR#60, scene_memory.py = G1a).

## COLD-BOOT CONTROL — 2026-08-02, Houdini+Synapse restarted BEFORE any merge
Fresh Houdini 22.0.397, fresh bridge, ping OK (protocol 4.0.0).
memory_write => IDENTICAL [WinError 5] on <install>/bin/claude.
=> The defect is DETERMINISTIC ON COLD BOOT. Not session rot, not a long-run
artifact, not restart-fixable. Every user with an unsaved scene hits it on every
launch. This is the true first-run experience and raises the severity.
Before/after now compares like with like: cold-bridge pre-fix FAILS; the
post-merge cold-bridge probe must PASS.

## 3. POST-FIX VERDICT — 2026-08-02, after fc1c9e1 merged + Houdini restarted

Probe: scripts/live_probes/probe_g1_acceptance_ws.py (direct WS, /synapse mount,
no MCP — the MCP server did not re-register in the CLI session after restart).

  ping                => pong, protocol 4.0.0                       PASS
  memory_write        => {written:true, scope:scene}, no WinError,
                         no Program Files path in reply             PASS
  memory_status       => entries_total 21 -> 23 across the write    PASS
  doctor version      => ok — "install stamp says 5.23.0 but the
                         running package IS the stamped tree"       PASS (G1c live)
  on disk             => %TEMP%\houdini_temp\untitled\claude\memory.md
                         appended (scene layer 0.0 -> 0.19 kb)      PASS (G1a live)

Baseline comparison: pre-fix the same call raised WinError 5 on
<install>\bin\claude with entries_total stuck at 13. Post-fix it writes to the
relocated unsaved-scene address. THE P0 IS CLOSED.

Note (payload shape, not a defect): a "decision" entry renders its choice/
reasoning fields; the probe sent plain content, so the rendered entry shows
empty Choice/Reasoning. Address + permission were the acceptance question.

Not covered: health write_plane surfacing — that was G1b, ruled BROKEN by its
crucible and NOT merged (pinned at g1b-health-write-plane-DO-NOT-MERGE).
