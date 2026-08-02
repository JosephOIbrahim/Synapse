# P0 VERIFICATION — the Kimi K3 write-plane report, checked against the live bridge

**By:** Claude Fable (repo + live-bridge access) · **2026-08-02** · companion to
`P0_integrity_blocks_write_plane.md` (Kimi K3's filing). This doc CORRECTS that ticket's
root cause. Read this first.

## Verdict: the P0 as filed does NOT reproduce. The diagnosis is wrong; one narrow real bug remains.

Kimi K3 concluded "every mutating tool fails with `fidelity=0.0`; the integrity gate treats
an empty cold-start store as fatal." Live probes on the current bridge refute the headline
and the root cause both.

### Live probe results (this bridge, 2026-08-02, protocol 4.0.0)

| Call | Kimi said | Actually |
|---|---|---|
| `write_report` | ❌ fidelity=0.0, writes to temp | ✅ `ok:true, 211 bytes` → **`C:\Users\User\SYNAPSE\docs\...`** (repo, not temp) |
| `memory_status` | 0 entries | ✅ **`entries_total: 5`** |
| `decide` | ❌ fidelity=0.0 | ✅ **`recorded:true, id mem_45e22ffe7abf`** |
| `memory_write` | ❌ fidelity=0.0 | ❌ but **`WinError 5 Access denied: C:\Program Files\...\Houdini 22.0.397\bin\claude`** — NOT fidelity=0.0 |
| `doctor` | ❌ blocked | ✅ returns full checks (2 fail / 7 ok / 1 skip) |
| `ping`/`health`/`scene_info` | ✅ | ✅ |

**The write plane is broadly ALIVE.** `write_report`, `decide`, `doctor`, `memory_status`
all work. The "100% of mutations fail with fidelity=0.0" claim is false here.

## Root cause — corrected against the code

1. **The fidelity gate is real but not the cause.** `shared/bridge.py:1962` (`_finalize`)
   rejects `fidelity < 1.0`; `mcp/server.py:126` names the true trigger:
   `main_thread_executed=False → anchors_hold False → fidelity 0.0` — hou.* running OFF the
   main thread (an anchor-evidence failure), **not** an empty-store hash. Kimi's
   "hash-of-nothing → bootstrap to 1.0" fix would patch a cause that isn't the cause.
   That fast-path-divergence bug is ALREADY FIXED on master (the two-set `is_transport_fast_path`
   reconciliation at `mcp/server.py:148`).
2. **The one reproducing write failure is store-address, not integrity.** `memory_write`
   throws `WinError 5` writing under Houdini's `bin/` (the process CWD for an unsaved
   scene). This is the **C-0 unstable-store-address class fixed on master by PR #60**
   (`store.py:801 hip_is_unsaved()` routes unsaved scenes to `$HOUDINI_TEMP_DIR`).
   ⚠ CAVEAT: the failing path ends in `bin\claude` (a filename, possibly a spawn/subprocess
   resolution), so PR #60 alone is NOT proven to fix `memory_write` — RE-PROBE after redeploy
   before closing.
3. ~~The running bridge is a STALE deploy.~~ **RETRACTED on the second check pass** — the
   install is repo-direct (no deploy exists); the 5.23 figure is a stale installer stamp
   file, cosmetic only. Kimi's session most likely ran BEFORE today's/yesterday's merges
   (a bridge process holding older loaded modules), which is a *process restart* matter,
   not a deploy pipeline. Current bridge (pid published 2026-08-02T14:44) runs current code.

## What is genuinely real (keep from Kimi's ticket)

- **memory_write is broken** on this bridge (WinError 5) — narrow, real.
- **`health` says healthy while a write path is broken** — monitoring blind spot, valid.
  Surface write-plane state in `synapse_health`.
- **moneta schema unregistered / no cortex_root.usda** — the substrate's "stabilize" half
  (deferred per CTO_RULINGS_02 R205) is genuinely not stood up.

## The real fix order (CORRECTED 2026-08-02, second check pass)

⚠ SELF-CORRECTION: fix-order #1 originally said "redeploy master." WRONG — the install is
REPO-DIRECT (packages/synapse.json sets PYTHONPATH to C:/Users/User/SYNAPSE; hpath to
<repo>/houdini). There is no deployed copy and no deploy step. The "5.23 stamp" is a stale
install_stamp.json (doctor.py:62, M3-A installer bookkeeping) — cosmetic. Today's bridge
loaded today's master, so:

1. **Trace the `bin\claude` resolver FIRST** — memory_write fails IN CURRENT CODE. No
   `claude` entry exists in Houdini's bin/ and nothing in python/synapse/memory references
   'claude': something builds a RELATIVE path resolved against the unsaved-scene CWD
   (Program Files/Side Effects Software/Houdini 22.0.397/bin) and is denied creating it.
   Same CWD-dependence class as C-0, second location.
2. Refresh/remove the stale install_stamp.json (cosmetic; kills the doctor false alarm).
3. `synapse_health` surfaces `write_plane: ok|degraded(reason)`.
4. Regression: fresh unsaved scene → `memory_write` succeeds; `health` reflects it.
5. THEN the CTO call's real content — consolidation (−20 tools/−32 recipes, behind
   deprecation shims, not hard deletes) and Pillars A/B — as deliberate fast-follow.

## What NOT to do
- Do not implement Kimi's empty-store→bootstrap-1.0 fix. Wrong cause.
- Do not fire a code firefight at the fidelity gate — it is not broken.
- Do not build a "redeploy" pipeline step — there is no deploy; the install is repo-direct.
