# RELEASE · SYNAPSE

**build → qualify → bump → commit → gate → tag → push → publish**
One card per release, every release. Gate: `scripts/tag_release.py`.

---

## Order matters

**Build and qualify BEFORE you commit the bump.** The payload an installer embeds is
the working tree at build time, so a build run after the bump but before the commit
ships exactly what the tag will name. Do it in this order and the README banner can
claim `is Latest` truthfully the moment it is written — no Preview leg, no second
promotion commit. Do it the other way and you either publish a banner pointing at a
download that does not exist, or you pay for a Preview cycle you did not need.

Preview is for when you **cannot** build — toolchain missing, machine unavailable.
It is not a default.

---

## The ritual

```
0   cd C:\Users\User\SYNAPSE                        every step runs from repo root

--- version ---------------------------------------------------------------
1   edit VERSION                                    set X.Y.Z, one line
2   python scripts\sync_version.py --write          propagate to six surfaces
3   edit README download/checksum/what's-new links  NOT auto-synced, hand-edit
    edit README banner  tags: vX.Y.Z is Latest      pinned by the toolcount test
4   write docs\releases\vX.Y.Z.md                   public notes
    write harness\notes\RELEASE_vX.Y.Z.md           how it was cut (internal)
    promote the CHANGELOG entry

--- build + qualify (before the commit) -----------------------------------
5   verify the Moneta bundle digest FIRST           bundling is a licensing act
6   installer\build_windows.py --downloads --iscc --output
        --moneta-bundle --moneta-sha256             production Setup
7   same again + --test-build                       isolated TestSetup
    -> both build.json must carry the SAME payload sha256. That is the link
       that binds the qualification to the shipped file.
8   installer\create_test_fixture.py --kind previous
    installer\create_test_fixture.py --kind missing-dependency
    -> from the TESTSETUP report, never the production one
9   installer\test_executable.py --setup <TestSetup> --previous-setup
        --broken-setup --root <MUST NOT EXIST> --hfs <Houdini dir>
    -> 19 of 19 PASS, exit 0

--- gates -----------------------------------------------------------------
10  pytest tests\                                   full stock suite, alone
11  hytest tests/panel  (SYNAPSE_HYTHON pinned)     seat suite, ALONE. see traps
12  pytest installer\tests

--- tag + push ------------------------------------------------------------
13  SYNAPSE_GATE_C=1 git add / git commit           tree must go clean. VERSION
                                                    is a Gate C path (the
                                                    pre-commit hook): the bump
                                                    commit is REFUSED without
                                                    the override, and an
                                                    unchecked failure tags an
                                                    un-bumped HEAD
14  python scripts\tag_release.py --check-only      preflight, always safe
15  python scripts\tag_release.py                   creates vX.Y.Z (annotated)
16  SYNAPSE_GATE_C=1 git push origin master vX.Y.Z  scoped to ONE command,
                                                    cleared immediately, never
                                                    unattended
--- publish ---------------------------------------------------------------
17  compose SHA256SUMS.txt
    compose <Setup>.public-build.json               REDACTED: drop payload.path,
                                                    basename the installer field
    compose installer-verification.json             PARSE the 19 lines, do not
                                                    retype them
18  gh release create vX.Y.Z --latest --notes-file <public body> + 4 assets
    -> NEVER in the same && chain as the gate (gh mints its own tag if the
       gate refused and no tag exists)
19  verify: /releases/latest == vX.Y.Z, every asset 200, and re-download the
    Setup and hash it -- served sha must equal the qualified sha
20  reinstall -> synapse_doctor                     install stamp conforms
```

Success signature at step 15: every check prints `OK`, `pytest_pre PASS`,
`tag vX.Y.Z created OK`, `pytest_post PASS`, then the push command.

---

## When it refuses

```
worktree   N tracked mod(s)    commit or revert the listed files
sync_check DRIFT               run --write, then commit
anything   UNKNOWN             a file can't be read -- fix the file, never the gate
tag_free   vX.Y.Z exists       this number is already released
fixtures   RuntimeError        you passed the PRODUCTION report; use --test-build
harness    "use a new dir"     the qual root must not pre-exist; it makes its own
```

The gate never pushes. `--check-only` is always safe. Untracked files do not block.

---

## Traps

**Never run the stock suite and the seat suite at the same time.** Both attach a
rotating file handler to `~/.synapse/logs/synapse.log`. The loser of the rollover race
raises `PermissionError [WinError 32]` *inside whatever test was mid-wait*, so it
reports as an ordinary timing failure in the other suite's subject matter. It faked a
sixth seat red on 5.70.0. Nothing in either suite detects it.

**A live Houdini keeps the old modules.** Source-tree changes do not reach an open
panel until it is reloaded or Houdini restarts. Say so in the release notes; a live
check that imports the module proves the *tree*, not the *open panel*.

**Redact before you publish.** The raw `build.json` carries local paths in
`installer` and `payload.path`. The producer script refuses to write a report
containing one — keep that check, and keep it path-shaped (a bare username match
false-positives on the check name "No user-data changes during upgrade").

---

## Surfaces

**Six auto-synced:** VERSION · pyproject · `__version__` · docstring · CLAUDE.md ·
README banner version

**Hand-edited, every time:** README download button · README checksums link · README
"New in X.Y.Z" block · README `tags:` channel line · developer release-notes link ·
CHANGELOG heading

**Not VERSION surfaces:** `_vendor/*` · forge/retina/inspector · rope baseline
strings · install stamp (conforms at next install)

**The product surface — one definition, `scripts/product_surface.py`.** The
*product unchanged* sentence every release makes is proved with

```
python scripts/product_surface.py --diff v<prev> HEAD --expect-empty
```

not with a hand-typed `-- python installer`. That pathspec is blind to the
nineteen tracked `.py` files at the repo root, seven of which are the shipped
MCP surface. Measured: `c6221f3b` moved 65 lines of `mcp_server.py` — the file
`.mcp.json` launches — and returns EMPTY under `-- python installer`, so the
ritual would have reported the product unchanged over it. The script refuses a
pathspec term that matches nothing (an empty diff from a dead term is an
abstention printed as a pass) and reports the command it actually ran.

*Not a VERSION surface ≠ not product.* `_vendor/*` is correctly skipped by
version sync — upstream packages carry no SYNAPSE version — and is correctly
**inside** the product surface, because it ships in the payload.

Invariants: `tests/test_phase0c_doc1_version_conformance.py` (a published tag may
never outrun the tree) · `tests/test_phase0c_doc1_toolcount.py::_assert_release_tags`
(the README channel banner is real) · `tests/test_product_surface.py` (the product
pathspec cannot be narrowed back past the entry points, nor widened into
`harness/`/`tools/` until it stops meaning anything).

---

## The four release assets

```
SYNAPSE-X.Y.Z-Setup.exe                 the thing
SHA256SUMS.txt                          one line, ' *' separator
SYNAPSE-X.Y.Z-Setup.public-build.json   schema synapse-public-build-1, redacted
installer-verification.json             schema synapse-release-verification-1
```

The verification report states what was **not** run, and keeps failed attempts rather
than tidying them away. If a check is still running at publication, say
`PENDING_AT_PUBLICATION` and amend in place afterwards with an `amended` field — never
guess, never swap silently.

Worked example with its producer script: `harness/notes/release-5.70.0/`.
