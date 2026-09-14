# v5.69.0 — promoted from Preview to Latest

Kept as the record of how this release was cut, including the hour it spent on the
Preview channel and why.

## It was tagged Preview first, deliberately

`v5.69.0` was tagged and pushed with **no installer**: Inno Setup 7.1.0 was not on
the build machine. Publishing a GitHub Release without a Setup would have flipped
the README's `releases/latest` badge to a version whose download did not exist, so
the tag went out on the **Preview** channel with `v5.68.0` retained as Latest, and
the README's download button kept serving the 5.68.0 Setup — which existed and
worked.

The first attempt at that banner invented its own wording and
`test_readme_latest_tag_matches_version_file` went red. It was right to: the repo
already had a ratified Preview channel requiring `vX is Preview · vY is Latest`
with `Y < X`, plus matching notes in this file. The assertion was not widened; the
shape it pinned was used.

## What promoted it

The toolchain was fetched and verified against `installer/toolchain.lock.json`
rather than assumed:

- Inno Setup 7.1.0 — sha256 pinned, **Authenticode signature Valid, publisher
  `CN=Pyrsys B.V.`**, installed `/CURRENTUSER` into the build tree, never
  system-wide.
- Python 3.13.15 embed and both wheels — sha256 pinned and verified.
- Moneta 1.2.0rc1 — exported from the local source and **byte-identical to the
  previously reviewed archive**, `81a3d873…`. This was checked *before* the build,
  because bundling proprietary content into a public download is a licensing act,
  not a build step. A mismatch would have stopped the promotion.

## The qualification, and what binds it to the shipped file

`installer/test_executable.py` ran against the isolated **TestSetup** build in a
throwaway sandbox root: **19 of 19 PASS, exit 0** — fresh install, repeat install,
upgrade, uninstall preserving projects/memory/credentials, reinstall, write-denied
rejection, missing-dependency blocking, registration and shortcut lifecycle.

The link that makes that evidence count: the TestSetup and the published Setup
carry the **same payload sha256**, `aefefed8c25d6010f6b3ca7ec5a6d7fa…`. Qualifying
one qualifies the payload the other ships. The TestSetup uses a separate AppId and
refuses to run without `/TESTROOT`, so it could not touch a real install.

Two attempts failed on the way and are kept in `installer-verification.json`
rather than tidied away: deriving fixtures from the production report (they require
an isolated TestSetup build) and passing a pre-created sandbox root (the harness
creates its own).

## What is NOT behind this Latest

Stated here because the release body states it too, and because 5.68.0 carried
checks that 5.69.0 does not:

- The installer is **unsigned**.
- `installed_houdini` and `live_houdini` were **NOT run**. 5.68.0 had both.
- No clean Windows machine, no native wizard visual qualification.
- The upgrade path was exercised with a synthetic prior payload, not a historical
  released installer.
