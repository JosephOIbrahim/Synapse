# H-MATRIX — multi-hython test matrix contract (PARKED)

**Status:** PARKED, unimplemented. Recorded 2026-09-15 by the closeout merge train.
**Source branch:** `wip/panel-goalposts` @ `c3a603240407df51918aebed1b41c6dbbce4a6d0` (2026-06-24).
**Spec file on that branch:** `tests/panel/test_hython_matrix.py` (182 lines).
**Never merge that test to master as-is** — it asserts a parser master does not have; its own docstring says it "FAILS NOW". Against the 8869/0 suite floor that is a guaranteed red.

Provenance: `harness/notes/closeout-2026-09-15/PLAN.md` (row `wip/panel-goalposts`, OVERTURNED from ARCHIVE_DELETE to SPLIT_SALVAGE), `harness/notes/closeout-2026-09-15/verdicts.json` (`"branch": "wip/panel-goalposts"`, `refuter_reason`), `harness/notes/first-principles-2026-09-15/AUDIT.md` (row `wip/panel-goalposts` → **PARK / RECORD**).

---

## 1. The contract the branch wanted

Verbatim module docstring — `git show wip/panel-goalposts:tests/panel/test_hython_matrix.py | head -40` (the docstring is lines 1–22 of that output):

```
"""Goalpost -- .synapse/hytest.py must support a MATRIX of Houdini builds.

Contract: hython-matrix (H-MATRIX). Encodes the goal:

    SYNAPSE_HYTHONS (comma/semicolon list of version tokens like
    "21.0.671,21.0.729" or full hython paths) -> run the given pytest selector
    under EACH resolved+usable build; pass IFF ALL pass. A TARGETED build that
    is unresolvable or unusable (no pytest+PySide) is a HARD ERROR, never a
    silent skip. SYNAPSE_HYTHONS unset -> today's single-best behavior unchanged.

PURE PYTHON by design: these exercise the shim's OWN parsing + aggregation
logic. We monkeypatch the shim's hython-resolution + per-build run functions so
NO real hython is ever spawned -- the test is a true pass/fail under stock
`pytest -q` (no PySide, no QApplication, no false-green-via-skip).

hytest.py is a script, not on the import path, so it is loaded via
importlib.util.spec_from_file_location.

The matrix entry points do NOT exist yet. To stay an ASSERTION (never an
AttributeError), every not-yet-built symbol is reached via getattr(..., None)
and asserted on. Both tests FAIL NOW for the right reason (matrix logic absent)
and PASS only once the shim grows the matrix support.
"""
```

---

## 2. What `.synapse/hytest.py` does today (master `d8ebb74a`)

Read via `grep -n 'def \|SYNAPSE_HYTHON' .synapse/hytest.py` and `sed -n '80,130p' .synapse/hytest.py`.

- **Singular pin only.** `:100` is `pinned = os.environ.get("SYNAPSE_HYTHON")`; `:102` yields it as `"SYNAPSE_HYTHON pin"`. There is no `SYNAPSE_HYTHONS` anywhere on master (`git grep -n SYNAPSE_HYTHONS master` → 0 hits outside the closeout notes).
- **Single-best resolution, first usable wins** (module docstring, rules 1–4): `$SYNAPSE_HYTHON` → `hython` on PATH → the installed build whose version equals the committed symbol-table stamp for its major (`python/synapse/cognitive/tools/data/h<major>_symbol_table.json` → `houdini_version`; 22.0.400 today) → newest installed.
- **Entry points:** `_candidates()` (`:87`, plain path strings — `scripts/solaris_v3_accept.py:hython_candidates` depends on that shape), `_candidates_with_reason()` (`:98`), `_usable(hython)` (`:120`, spawns `hython -c "import pytest, PySide6"`), `find_hython_with_reason()` (`:133`), `find_hython()` (`:144`), `main(argv)` (`:148`, exits with pytest's own rc, or non-zero when no usable hython is found).
- **One selector, one build, one rc.** No per-build loop, no aggregation, no resolver seam that maps a *token* (e.g. `21.0.729`) to a path — `_candidates_with_reason` only ever treats the pin as a full path.
- **Rule 3 exists for a reason (B10, 2026-09-05):** "newest" is folklore on a host with several 22.0.x builds; the stamped build is the one SYNAPSE is verified on. This host now has both 22.0.400 and 22.0.429 — which is exactly why a matrix got *more* relevant since June, and also why a matrix must not silently weaken the stamp rule (see §3, last bullet).

---

## 3. What a future implementation must satisfy

Derived from the two tests on the branch (`test_matrix_targets_parsed`, `test_matrix_aggregates_all_pass`). The test discovers names via `getattr` over candidate lists, so any one name per role is acceptable.

**Parser** — one of `_matrix_targets`, `_targets`, `_parse_matrix`, `_parse_hythons`, `_split_targets`, `matrix_targets`:
- Splits the `SYNAPSE_HYTHONS` string on **both** `,` and `;`.
- Strips whitespace; a trailing separator or blank segment must **not** produce an empty target (`" 21.0.671 , 21.0.729 , "` → exactly 2 targets).
- Both tokens survive as substrings of the parsed targets.
- Accepts version tokens (`21.0.671`) **or** full hython paths.

**Resolver seam** — one of `_resolve_target`, `_resolve`, `_resolve_hython`, `resolve_target`:
- `resolve(target, ...) -> str | None`: maps one token/path to a usable hython path, or `None` when unresolvable or unusable (no pytest+PySide6).
- Must be a **module-level callable** so the test can `setattr(mod, resolve.__name__, fake)` — the matrix driver must look it up through the module at call time, not bind it at import.

**Per-build run seam** — one of `_run_one`, `_run_build`, `_run_under`, `_run_selector`, `run_one`:
- `run_one(hython, argv, ...) -> int`: run the selector under one build, return its rc. Same module-level/patchable requirement.

**Matrix driver** — one of `_run_matrix`, `run_matrix`, `_matrix_run`, `_run_all`, `matrix_main`:
- `matrix_run(targets: list, selector: list) -> int`, `0` == every targeted build passed.
- Runs **every** targeted build — no short-circuit on the first pass (test counts 2 runs for 2 targets).
- Any per-build nonzero rc → aggregate nonzero.
- A targeted build that resolves to `None` → **hard error, nonzero**, never a silent skip that aggregates to 0.

**Compatibility:**
- `SYNAPSE_HYTHONS` unset → behaviour byte-for-byte as today (singular `SYNAPSE_HYTHON` pin, rules 1–4, single rc).
- `_candidates()` keeps yielding plain path strings (consumer contract at `:87–96`).
- Stock-CPython only: the shim imports no `hou`/PySide; the tests run under `pytest -q` with monkeypatched seams.
- Open design point, **not** settled by the branch: how a matrix entry that is *not* the stamped build (e.g. 22.0.429 while the table stamps 22.0.400) should be reported. Rule 3 was added after the branch (2026-09-05). At minimum the per-build output should name the build and whether a symbol table stamps it, so a matrix pass cannot be read as "verified on a build no table describes".

---

## 4. Branch disposition (human acts — none performed by this note)

- **Tip:** `c3a603240407df51918aebed1b41c6dbbce4a6d0` — `test(panel): WIP goalposts — model-picker, ollama, hython-matrix, type-scale`. Merge-base with master: `2e8ddd3a`. Two unapplied commits (`91fe5b1e`, `c3a60324`), 8 files / +1130 / −0.
- **Archive tag to create:** `archive/wip-panel-goalposts` at `c3a60324`. As of this note `git tag -l 'archive/*'` shows no such tag. Steps from `PLAN.md:425–428` (the push of the tag was the step the original verdict omitted):

```powershell
git tag archive/wip-panel-goalposts c3a60324
git push origin archive/wip-panel-goalposts
git worktree list | Select-String goalposts
git branch -D wip/panel-goalposts
```

- Origin push-delete of `wip/panel-goalposts` is PLAN.md ruling 6 (DELETE / LEAVE) — a separate human decision; the branch is already public on origin.
- The other 7 files on the branch (model-picker ×2, ollama provider, type-scale, `IMPLEMENTATION_BRIEF.md`, `harness/rescope_settings.py`, `.gitignore`) are superseded on master per the verdict; this note records only the H-MATRIX hunk.
- To recover the spec file after the branch is deleted: `git show archive/wip-panel-goalposts:tests/panel/test_hython_matrix.py`.

---

## 5. Not checked here

- The branch test was **not run** (it fails by design on master; the parking task named no tests).
- No hython was spawned; master's resolver was not re-probed against the two installed 22.0.x builds.
- Whether `scripts/solaris_v3_accept.py:hython_candidates` is the only consumer of `_candidates()`'s plain-string shape.
