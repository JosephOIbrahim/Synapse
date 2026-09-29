# Release preparation: v5.85.3

Publish two commits on top of v5.85.2 (`bbee2ce5`). Joe's word: "git push, git
release & update mermaid diagrams to two tones orange and black type"
(2026-09-29).

| Commit | What it does |
|---|---|
| `a773969f` | BP12 items 15 and 16: reads return `raw` and `expression`; the R1 scene hash drops cook counts when the stage is hashed in full; 12 tests |
| `fd8c7d82` | 19 mermaid blocks in 10 files restyled to two orange tones with black type |

## Evidence

- **Item 16, the cause.** A hython probe on Houdini 22.0.400
  (`hython_hash_drift_probe_v1.py`): the hash after a same-value set equalled
  the one before it (`48c0ccd1...`), and the next hash with nothing changed was
  `900c28ad...`. The stage signature stayed `3bba889e...` throughout, and a
  stage set back to its original engine matched the first signature but not
  the first hash.
- **Item 16, the fix.** The same probe on the fixed bridge showed no drift, a
  real write still moved the hash, and the restored stage hashed like the
  original (`fc2fc5d2...`).
- **Item 15.** A hython probe showed `unexpandedString()` raising
  hou.OperationFailed for non-string and keyframed parms, and `expression()`
  raising it when a parm is not animated. Those are the only errors swallowed.
- **Mutation.** The old `shared/bridge.py` fails 3 of the 5 hash tests. The old
  `handlers.py` fails the get_parm handler test.
- **Live, 2026-09-29.** Houdini restarted into an empty session, so the seat
  opened `Desktop/untitled.hiplc` through File > Open Recent. A direct read
  returned `raw` = `$HIP/render/$HIPNAME.$OS.$F4.exr`. Claude Code headless
  (`claude-sonnet-5-5`, synapse tools only, 6 turns, 26 s) reported the picture
  write as taken from `raw`. Three writes returned
  `external_change_detected: false` and `composition: true`, with the hash
  steady at `8bbe5db65e31b742`.
- **Diagrams.** mermaid-cli 12.0.0 in Chromium rendered 38 of 38 on the default
  and dark themes. The README, sequence, base-theme and subgraph diagrams were
  checked by eye. GitHub's own render was not checked. Nothing outside the
  mermaid blocks changed.
- **Tests.** The `tests/` suite passed on Windows with Python 3.14 before the
  docs-only diagram commit: 10,123 passed, 457 skipped, 0 failed. The tests
  that read the restyled docs passed after it: 202 passed, 33 skipped.
- **Known, not fixed.** `harness/notes/readme_check.py` is stale on three
  counts (palette, `classDef default`, version rule) and is not wired into CI.
  It is BP12 item 17.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
