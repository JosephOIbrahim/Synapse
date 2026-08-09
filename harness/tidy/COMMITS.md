# TIDY dispatch — prepared commits (draft only, NOT committed)

Prepared 2026-08-07 by the tidy prepare-commits work package.
All items verified present, staged (`git add`), and grouped into 5 logical
commits. **No `git commit` was run** — these are drafts for review.

Convention: `feat(area): TIDY-0X <what>` / `chore(area): TIDY-0X <what>` /
`docs(area): TIDY-0X <what>`.

---

## Commit 1 — TIDY-01 + TIDY-02 (harness handoff docs)

```
feat(harness): TIDY-01..02 CI0 leg brief + next-session handoff

- harness/prompts/ci0.md: CI0 honest-green-CI leg brief (CTO-ruled: honesty
  over a green badge; three pre-triaged failures A/B/C; base off master
  c4187d01). Referenced by legs.json and NEXT_SESSION.md.
- harness/NEXT_SESSION.md: standing next-session handoff (loop closed,
  v5.43.0 released, CI0 rulings + execute order). Read by every harness.
```

Staged: `harness/prompts/ci0.md`, `harness/NEXT_SESSION.md`

---

## Commit 2 — TIDY-03 (release note)

```
docs(release): TIDY-03 v5.43.0 release note

THE release note for the shipped+tagged v5.43.0 (BLOCKS deterministic scene
setups). Matches released state exactly: F-1..F-7 invariants, c3
canonicalizer, suite 5765/9/147, c2 baseline 8bb05761.
```

Staged: `harness/notes/RELEASE_v5.43.0.md`

---

## Commit 3 — TIDY-04 (rope state flip)

```
chore(rope): TIDY-04 L5-13 needs_review -> blocked

Producer's own legitimate state write: L5-13 is blocked because L5-14 AMENDs
it (hero takes the accent). Not stale or broken; tracked file, commit the flip.
```

Staged: `harness/rope/STATE.json`

---

## Commit 4 — TIDY-05 (tidy harness)

```
feat(tidy): TIDY-05 tidy harness

The tidy harness itself (the tool running this recon): SPEC.md, STATE.json,
runner.py, workflow.js. __pycache__/runner.cpython-314.pyc excluded by the
existing .gitignore (__pycache__/ + *.py[cod]) — no gitignore edit needed.
```

Staged: `harness/tidy/SPEC.md`, `harness/tidy/STATE.json`,
`harness/tidy/runner.py`, `harness/tidy/workflow.js`

---

## Commit 5 — TIDY-06 + TIDY-07 + TIDY-08 (autoresearch campaign runs)

```
feat(autoresearch): TIDY-06..08 completed campaign runs

- fixture_verify_20260805_183316: completed fixture_verify run (DONE, 1/1
  100%, 0 probe failures) — LOP truth for H22.0.368.
- scout_20260805_181349: completed scout/triage run — dead literals
  usdrender/usd/graft/geometryclipsequence + successors;
  karmarenderproperties->karmarendersettings.
- solaris_basic_20260805_181026: completed solaris_basic run (DONE, 32/32
  100%, 0 probe failures) — LOP truth.

Only evidence files tracked (lop_truth / triage.json / triage.md); session
scratch (DONE, state.json, logs, raw_model_output.json) gitignored per
harness/autoresearch/.gitignore, matching committed sibling runs.
```

Staged:
- `harness/autoresearch/runs/fixture_verify_20260805_183316/lop_truth_22.0.368.json`
- `harness/autoresearch/runs/scout_20260805_181349/triage.json`
- `harness/autoresearch/runs/scout_20260805_181349/triage.md`
- `harness/autoresearch/runs/solaris_basic_20260805_181026/lop_truth_22.0.368.json`

---

## Notes / gates

- **Branch:** current branch is `master`, not `ci/ci0-honest-green` (TIDY-01's
  description referenced the CI0 feature branch). The ci0.md brief is a leg
  brief and is staged on master as-is; the CI0 branch itself is not touched.
- **No .gitignore change needed for TIDY-05:** `__pycache__/` and `*.py[cod]`
  are already ignored at repo root; the pyc is correctly excluded.
- **Autoresearch scratch correctly excluded:** `harness/autoresearch/.gitignore`
  already ignores `runs/**/{DONE,state.json,run.out.log,run.err.log,raw_model_output.json}`.
  Only evidence files are staged, matching the committed sibling runs.
- **Not staged (out of scope for this dispatch):** `$null`, `docs/pkg_info.json`,
  `docs/project.md`, `harness/notes/MONETA_WATCH.txt`,
  `harness/notes/RELEASE_v5.43.0_DRAFT.md`, the `harness/notes/_*.py` probe
  scripts, `harness/notes/watch_moneta.ps1`, `harness/rope/OPERATOR_CARD.md.bak`,
  `models/`, `shot_layers/`, and the `harness/legs.json` modification.
