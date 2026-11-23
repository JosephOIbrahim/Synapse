# Release record — v5.104.1

**Prepared 2026-11-22. This record describes the state at the commit that carries
it, before the push, the tag and the release page exist.** The Gates table is
authoritative for that snapshot and for nothing later: once a tag and a page exist,
the CI, Tag and Publish rows below are superseded, and the tag is the authority.

## Candidate

- Base: the `v5.104.0` tag, `c6f8b63f`, which is also `origin/master` at preparation
  (`git ls-remote origin refs/heads/master`), so pushing this branch to master is a
  fast-forward.
- Content, in order:
  - `fix/v5.104.1-pxr-pluginpath`, merged `--no-ff` as `dfd9201d`: the Moneta schema
    path (`b62f5143`) and the MCP auth frame type (`a0ad0bdb`);
  - `feat/worldlabs-atlas`, merged `--no-ff` as `cb2a54fe`: the Atlas-only World Labs
    import (`9ddfde41`);
  - `844c4398`: the import-map classification the full suite caught, and a synthetic
    operation id in place of a real one in a test;
  - `9ba3c22c`: the review findings (sidecar beside the source file, SPZ v4 decoded only
    by a bounded decoder, the `PYTHONPATH` replace-list guard, the download-folder source);
  - `c885a8bd` and `4523c66d`: an unreadable collider is skipped instead of aborting the
    import, and is not recorded;
  - `eb8f8921`: three defects only Houdini's Python showed (seat run r2);
  - the release commit: VERSION, version propagation, the release text and this file.
- Read the exact list with `git log --oneline c6f8b63f..HEAD`.

## Evidence

**Stock suite**, `run-stock-release.sh` (the `run-stock-tree.sh` fence; the release edits are
checked by a manifest before and after), Python 3.14.2, `tests/`, `-m "not live"`, run `r7` on
`eb8f8921` with the release edits:

```
STOCK_START HEAD=eb8f8921… AT=2026-11-22T23:27:29Z PY=Python 3.14.2 EDITS=12
STOCK_DONE  HEAD_BEFORE=eb8f8921… HEAD_AFTER=eb8f8921… EXIT=0 TREE_MANIFEST=unchanged
= 13463 passed, 735 skipped, 11 deselected, 10 xfailed, 783 warnings in 545.71s (0:09:05) =
```

Against v5.104.0 (`1191fe48`: 13,418 / 0 / 732) only the lanes' test files differ
(`compare_stock.py`, 7 files). Earlier runs on this branch: `r2` (merged tree) 1 failed, the
import map; `r3` to `r6` 0 failed, each on the code of its day.

**Seat suite**, `run-seat-leg.ps1`, hython 22.0.400 (Python 3.13.10), the same tree and
edits, run `r3`, EXIT=1 as always, TREE_MANIFEST unchanged: 98 failed, 4 errors, 13,604 passed,
514 skipped. Compared by failing test (`compare_seat.py`) with v5.104.0's run `r3`
(2026-11-22 00:31Z, 96 failing): 96 shared, 0 gone, 6 here only. The 6 fail the same way on
`c6f8b63f` today under the seat's settings (targeted hython runs); Setup 5.104.0 created
`~/.synapse/auth.key` on this machine at 14:16Z, after that run, and the seat leg reads the real
home folder. Run `r1` stopped on an access violation in garbage collection inside a panel test
(code unchanged here; three reruns of the preceding tests, no crash); run `r2` found the three
defects fixed in `eb8f8921`.

**Installer.** `python -m unittest discover -s installer/tests`: 93 of 93 OK.

**Targeted.** The changed test files, every test file that reads a release document, and
the guards (except ratchet, marshal lint, d_track): 1,675 passed, 65 skipped.

**Mutations.** Each fix reverted on a scratch copy of the tree, one at a time; each was
caught by its test:

| Mutation | Caught by |
|---|---|
| schema-path list join removed | `test_schema_path_survives_houdini_list_replace` |
| sidecar resolved beside the cached PLY | `test_spz_import_reads_scale_beside_the_artists_file_not_the_cache` |
| a zstandard fallback restored | `test_v4_never_uses_an_unbounded_third_party_decoder` (and the refusal test) |
| download-folder source back to `setdefault` | `test_downloaded_operation_folder_is_recorded_as_a_download` |
| `PYTHONPATH` replace-list join removed | `test_python_path_list_is_one_string_under_replace` |
| collider looked up beside the cached PLY (hython) | `test_atlas_spz_finds_its_collider_beside_the_source_not_the_cache` |
| collider cook guard removed (hython) | `test_unreadable_collider_falls_back_to_the_splat_floor` |
| unreadable collider still recorded (hython) | `test_unreadable_collider_falls_back_to_the_splat_floor` |

The auth fix's own tests fail 4 of 6 on `c6f8b63f` (lane record, `a0ad0bdb`).

**A real Atlas splat.** One refined `posedImages2Splats` run on 2026-11-22 (operation
recorded in the private working folder, not here): SPZ version 2, gzip, 2,000,000 splats,
SH degree 0, flag byte `0x40`. Headless hython 22.0.400 (Python 3.13.10) on `eb8f8921`:
- by operation ID (`AtlasClient.prepare_import`, key from the CLI sign-in): 2.57 s to read,
  download and convert, 2.98 s to import; provenance source `atlas_operation`, splat count
  2,000,000;
- from the downloaded folder (`prepare_local_asset`): 0.51 s and 2.88 s; source
  `atlas_operation_download`.
Both: a `ParticleField3DGaussianSplat` prim of 2,000,000 points, rotation (0, 0, 0), scale 1
marked unknown, lifted 0.63 units; no URL, key, account or project id, or local path in the
provenance.

**Not checked.**
- The auth fix against a running Houdini GUI: Houdini's `hwebserver` completes no WebSocket
  handshake in headless hython (it is pumped by the UI event loop), so the composed path
  (fixed client, fixed server, real key) has not run.
- The rendered look of an Atlas import, and an SPZ version 4 file from Atlas.

## Review

- **Round 1** (independent read-only reviewer, the full diff `c6f8b63f..cb2a54fe` and every
  release sentence): no blocker; three FIX (sidecar beside the cache, unbounded v4
  fallbacks, the `PYTHONPATH` replace list) and three NIT (download source, "lists your
  operations", axes stated as fact). All fixed in `9ba3c22c` and the release text.
- **Round 2** (a second read-only reviewer, verification of `9ba3c22c` and the edited
  text): no blocker; confirmed the four fixes; asked for a collider
  test and a no-method `PYTHONPATH` test. Writing the collider test under hython found that an
  unreadable collider aborted the import (`c885a8bd`).
- **Round 3** (a third read-only reviewer, `c885a8bd`): the record still named the unreadable
  collider, which the scatter recipe would bind; fixed in `4523c66d` exactly as it proposed.
- **Final text check** (read-only, the release text at this commit): see the Gates row.

## Gates

| Gate | State at this commit |
|---|---|
| Stock suite | r7, 0 failed (13,463 passed) |
| Seat suite | r3, 102 failing tests: 96 as v5.104.0, 6 that fail on `c6f8b63f` too today (4 shown to be the auth key) |
| Review | three code rounds, all findings fixed; final text check: 1 FIX, 8 NIT, all fixed |
| Setup build and qualification (card 14-16) | after this commit |
| Push (Gate C), CI on the exact SHA | not yet |
| Tag, publish | not yet |
| Seat install | owner act, after publish |
