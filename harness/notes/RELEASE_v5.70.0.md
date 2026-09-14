# v5.70.0 — cut straight to Latest

Kept as the record of how this release was cut, and of what the qualification does
and does not cover.

## Why this one did not need the Preview channel

`v5.69.0` went out on **Preview** because Inno Setup 7.1.0 was not on the build
machine and a Release without a Setup would have flipped the README's
`releases/latest` badge to a version whose download did not exist.

That is no longer true. The toolchain provisioned for 5.69.0 is still in
`C:\synapse-build` and still matches `installer/toolchain.lock.json`, so 5.70.0 was
built and qualified **before** the version bump was committed. The banner claimed
`v5.70.0 is Latest` only once there was a qualified Setup to stand behind it.

## Order of operations, and why

1. `VERSION` 5.69.0 → 5.70.0, propagated by `scripts/sync_version.py --write` to all
   six surfaces.
2. README / CHANGELOG / release notes written.
3. **Build, then qualify, then commit.** The payload a build embeds is the working
   tree at build time; nothing in `python/` changed between the build and the commit,
   so the qualified payload is the payload the tag names.
4. `scripts/tag_release.py` (refuses on a dirty tracked tree, so the commit comes
   first), then the Gate C push ritual, then `gh release create`.

## Moneta was checked before the build, not after

`moneta-local.zip` hashed to `81a3d873…` — byte-identical to the previously reviewed
and authorized 1.2.0rc1 bundle. Bundling proprietary content into a public download
is a licensing act, not a build step; a mismatch would have stopped the build.

## What binds the qualification to the shipped file

`installer/test_executable.py` ran against the isolated **TestSetup** build in a
throwaway sandbox root: **19 of 19 PASS, exit 0**.

The TestSetup and the published Setup carry the same payload sha256,
`50244e9a4022fd09…`, and the same `payload_id`, `5.70.0-caf329c319d3215a`. Qualifying
one qualifies the payload the other ships. The TestSetup uses a separate AppId and
refuses to run without `/TESTROOT`, so it could not touch a real install.

## A measurement hazard found while cutting this release

The first seat-suite run reported **6 failed, 200 passed** — one more than the known
five. The sixth, `test_ollama_discovery.py::test_closing_parent_during_discovery_never_calls_deleted_qt`,
failed as "Discovery did not settle", and its captured stderr carried
`PermissionError: [WinError 32]` rotating `~/.synapse/logs/synapse.log`.

Cause: the stock suite was running **concurrently** and holding the same log file.
Re-run alone, the seat suite is **201 passed, 5 failed**, the known five.

**The seat suite and the stock suite share `~/.synapse/logs/synapse.log` and must not
be run at the same time.** Nothing in either suite detects the collision; it surfaces
as a plausible-looking timing failure in whichever one loses the race. Related:
`harness/notes/` already records that pytest writes to that production log at all.

## What is NOT behind this Latest

- The installer is **unsigned**.
- No clean Windows machine, no native wizard visual qualification.
- The upgrade path was exercised with a synthetic prior payload, not a historical
  released installer.
- Five panel seat tests remain red; two are recorded design conflicts awaiting Joe's
  ruling, three are named and undiagnosed. None is new in 5.70.0.
- The suite's skip population is still not stable — see
  `harness/notes/SUITE_FLOOR_IS_NOT_STABLE.md`.
