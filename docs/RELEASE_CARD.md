# RELEASE · SYNAPSE

**v-bump → sync → commit → gate → tag → push**
One card per release, every release. Gate: `scripts/tag_release.py`.

---

## The ritual

```
0  cd C:\Users\User\Synapse                  all steps run from repo root
1  edit VERSION                              set X.Y.Z, one line
2  python scripts\sync_version.py --write    propagate to all six surfaces
3  git add / commit                          the version files
4  python scripts\tag_release.py --check-only    preflight, no tag
5  python scripts\tag_release.py             creates vX.Y.Z (annotated)
6  git push origin <branch> && git push origin vX.Y.Z    operator act
7  gh release create vX.Y.Z --title vX.Y.Z --notes-file harness\notes\RELEASE_vX.Y.Z.md    Releases page + Latest badge
8  reinstall -> synapse_doctor               install stamp conforms
```

Success signature: every check prints `OK`, `pytest_pre PASS`,
`tag vX.Y.Z created OK`, `pytest_post PASS`, then the push command.

---

## When it refuses

```
worktree  N tracked mod(s)   commit or revert the listed files
sync_check  DRIFT            run --write, then commit
anything  UNKNOWN            a file can't be read -- fix the file, never the gate
tag_free  vX.Y.Z exists      this number is already released
```

The gate never pushes. `--check-only` is always safe.

---

## Surfaces

**Six live:** VERSION · pyproject · `__version__` · docstring · CLAUDE.md · README banner
**Not surfaces:** `_vendor/*` · forge/retina/inspector · rope baseline strings · install stamp (conforms at next install)

Invariant: `tests/test_phase0c_doc1_version_conformance.py` — a published tag may never outrun the tree.
