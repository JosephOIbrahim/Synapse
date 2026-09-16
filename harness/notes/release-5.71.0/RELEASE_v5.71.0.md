# v5.71.0 — how it was cut

Ten branches merged through a scripted train (`harness/notes/closeout-2026-09-15/merge_train.py`):
each PR rebased onto the moving master, the tool count recomputed from `len(TOOL_DEFS)` rather
than typed, CI gated on the test matrix only (CodeRabbit advisory), squash-merged in order.
Two needed a hand rebase: #84 (registry + RBAC union against #83's new tool) and #85 (the
handler mix-in line, plus both count lines).

## Order of operations

1. All ten merged to master first; `VERSION` 5.70.1 -> 5.71.0 after, propagated by
   `scripts/sync_version.py --write`; README surfaces hand-edited.
2. Moneta bundle digest checked BEFORE the build: `81a3d8735c7da49ca81302725acab6a3324311091e850c34afcea92e87ea31f7`
   — byte-identical to the reviewed, authorized 1.2.0rc1 bundle.
3. **Build, then qualify, then commit.** Stock suite, seat suite and installer unit checks ran
   serially and alone. The notes were written from the measured numbers after the build, so
   `docs/` in the payload is one edit behind the tag; `python/` and `installer/` are the tag's.
4. `scripts/tag_release.py`, then the Gate C push scoped to one command, then `gh release create`
   in a separate command — never chained with the gate.

## Measured

- Stock suite: 9369 passed, 430 skipped, 625 warnings in 337.48s (0:05:37)
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): 6 failed, 200 passed, 45 warnings in 71.97s (0:01:11)
- Installer unit checks: 37 passed, 1 warning in 6.36s
- Installer qualification: 19/19 PASS, exit 0
- Payload sha256 bc959b26b00b (the 12-hex form the published release doc quotes; this pack
  retains no fuller digest); payload_id 5.71.0-8bf8cf9c275ae547
- Tool count 137 (`len(TOOL_DEFS)`, written by script)

## Traps that still hold

The seat suite and the stock suite share `~/.synapse/logs/synapse.log` and must not run at the
same time; both numbers above were measured alone, in sequence. `python` on this shell is 3.14,
not the repo's 3.13 — the stock suite runs on 3.14 with the vendored SDK inactive; the seat suite
runs on Houdini's 3.13.10; the two are not comparable and are not compared. Two Houdini 22 builds
are installed; the hytest shim was pinned to 22.0.400.

## What is NOT behind this Latest

- The installer is unsigned; no clean Windows machine; no native wizard qualification.
- The upgrade path used a synthetic prior payload, not a historical released installer.
- Six panel seat tests are red. Five are v5.70.1's exactly; one is NEW -- #85 changed
  `_MCPLocalClient.available` to keep a cached port when discovery is lost. Names, the
  re-measured v5.70.1 baseline diff, the diagnosis and the measured blast radius are in
  `SEAT_REDS.md`. Which contract is right is an open ruling, not a defect call.
- The suite's skip population is still not stable.
- The seven farm tools have no curated `activity.py` labels — derived labels only.
- PLAN Stop 5 blockers 1, 2 and 4 (build-pin vs installed 22.0.429, an uncollected harness file,
  a root-level `mcp_tools_render.py`) were out of the rebase's scope and are untouched.
- No live-Houdini introspection beyond the seat suite.
