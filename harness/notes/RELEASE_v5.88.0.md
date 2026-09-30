# Release preparation: v5.88.0

Publish three commits on top of v5.87.0 (tag `v5.87.0` on `fd225f6b`). Joe's word,
2026-09-30: "Gut push, then Git release", read as git push, then git release. Before
that he had said "Continue", taken as a yes to rulings R-5 and R-6 in
`claude/LEVEL1_BLUEPRINT.md`, with R-7 later as its own milestone.

| Commit | What it does |
|---|---|
| `3496737c` | Level 1 M1b (R-6 and M0+): a failed tool call is a result flagged `isError` on `/mcp` and on the stdio bridge, with the outcome line first and the outcome in `_meta`; `-32006` and `-32007` withdrawn; an unknown tool refused with `-32602` on `/mcp`; 34 tests |
| `86faa156` | Level 1 M2 (R-5): the readiness check inside `synapse_health`, and the gate on `/mcp` and both WebSocket servers; 38 tests |
| `90246aea` | Farm controls pass the readiness gate, as they pass the stall gates; 2 tests |

The three commits went to master first, on that word, with Gate C set for that one push
(`fd225f6b..90246aea`).

## Evidence

- **Tests and mutation.** M1b adds 34 tests, and 14 mutants, one per piece, each made one
  fail. M2 and its follow-up add 40 tests, and 24 mutants (20, then 1 for the version
  message, then 3 for the farm exemption) each made one fail.
- **Houdini's own Python.** `tests/test_farm_integration.py` and `tests/test_level1_m2.py`
  under hython 22.0.400: 80 passed, 1 skipped. On `86faa156`,
  `test_http_control_remains_off_main_when_houdini_is_stalled[synapse_farm_submit]` failed
  there, because the gate hopped onto the main thread before a farm launch; `90246aea`
  fixes it. The standard suite could not see it, since the gate does not apply without
  Houdini.
- **Houdini calls confirmed in hython 22.0.400** before M2 was built:
  `hou.hipFile.isLoadingHipFile()`, `hou.undos.areEnabled()`, `undoctrl off` and
  `undoctrl on` switching it, `hou.__file__` set on the real module, and psutil 5.8.0.
- **Full suite on the release tree.** Windows, Python 3.14, Houdini-only tests
  deselected: 10,558 passed, 426 skipped, 119 deselected, 5 xfailed, 0 failed. Except ratchet: 1,360 broad and 983 silent, unchanged from v5.87.0.
- **Not checked live.** The running Houdini loaded v5.87.0's code at 19:04 on 2026-09-29
  and was not restarted before this release, so neither change has run in a live
  session. A live check script is ready on the seat's machine.
- **Jev.** Jev checked 13 claims from the notes against the code that could contradict
  them (citation-check pattern; supports at 0.8 or more stands). Seven stood. Six went to
  a direct code read: four stood as written (a ready answer is remembered for 10 seconds
  and a failure never is; `synapse_health`'s fields; 137 tools; the version stamp and its
  refusal), and two were tightened (the protocol errors are `/mcp`'s, and the stdio bridge
  answers an unknown tool with a flagged result; a read the gate lets through is a tool
  read-only mode lets through, since four tools MCP marks read-only are routed as
  changes). Ledger: `harness/jev/ledger/v5.88.0.release.notes.jsonl`.
- **Advice.** An advisor model reviewed the approach before M2 and again before it was
  declared done. The second review found the farm gap and a flaw in the live check
  script's busy test.

## Decisions

- **Source release.** Joe did not ask for an installer, so no v5.88.0 Setup is built.
  The v5.86.0 Setup stays the download, and the README, the installation page and the
  status page say it lacks the MCP changes in v5.87.0 and v5.88.0.
- **5.88.0.** The error wire changes and a new check runs before every session's first
  change, so the minor version moves.
- **Withdrawn codes.** The notes say `-32006` and `-32007` were withdrawn one release
  after they shipped, and what a client that matched `-32006` should read instead.

## Incidents

- `device_commit_files` delivered a stale copy of a file that had been edited in place
  after it was first written: a commit message, the seat state file and the Jev script.
  A placeholder check or a hash check caught each before use. Files now go to the machine
  under a fresh name, and their hash is checked before they run.

This record does not claim that the later CI, push or publication steps have completed.
They are checked after publication.
