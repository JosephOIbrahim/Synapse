# PD-CENSUS report - 2026-09-04

Status: **BLOCKED delivery; T1/T2 evidence complete; full-suite floor FAIL**.
Source base: `5e29bf9e` on `pd/panel-census`, containing the
orchestrator's baseline and briefs; product sources are unchanged from `6e3dd963`.

## Milestone T1

`harness/notes/panel_rhythm_census.py` reads source with stdlib AST, regex and
tokenize. It records spacing arguments (literals and unevaluated expressions),
inline sheets, object names, raw/distinct hex, comment exemptions, lexical scopes
and layout constructor owners. `--panel-dir` supports independent fixtures;
`--json` and `--md` select outputs. It never imports panel code or evaluates QSS.

Command:

```powershell
python -I -S harness/notes/panel_rhythm_census.py --json harness/panel_pd/runs/2026-09-04/rhythm_census.json --md harness/panel_pd/runs/2026-09-04/rhythm_census.md
```

Result: measurement_complete=true; outputs_complete=true. Source artifacts:
`harness/panel_pd/runs/2026-09-04/rhythm_census.json` and `.md`.
84 files outside designsystem; 107 spacing sites; 106 inline sheets; 135 raw
six-digit hex sites; 75 distinct values; 0 exemptions. Every site has a source
path and line; every file has a normalized-source SHA-256.

Validation: 46 passed across the census tests, Expert pin, density rule and
density repolish tests. Negative controls exclude comments/string call lookalikes,
wrong method names, non-Ds names, malformed hex and false exemption strings.
The subprocess fixture uses `python -I -S` and contains a raising statement plus
an unavailable import, proving that fixture code is read without execution.

Proved it bites: temporarily replaced per-file integer counters with zero;
`tests/test_panel_rhythm_census.py` produced 8 failed / 13 passed (exit 1),
covering spacing, sheets, object names, Ds sites, distinct Ds names, exemptions,
grid spacing and hex. Restored the source byte-for-byte, then 46 passed.

## Choices and limits

- The user's explicit fourth deliverable authorizes `tests/test_panel_rhythm_census.py`,
  omitted from the contract's ownership-table row. No other test is edited.
- The PD contract's STATUS/REPORT handoff replaces the general AGENTS bus and
  constitution receipt locations. Evidence remains inside this worktree, as
  explicitly instructed; no writes to the main tree.
- Hex means all raw six-digit occurrences outside designsystem, even comments
  and existing-token fallbacks. This reproduces the contract's raw count rather
  than pretending every occurrence introduces a distinct foreign palette colour.
  Recorded hex strings are measured source evidence, never new palette literals.
- Runtime widget cardinality and visibility are UNKNOWN. Direct naming sites
  are not instances; loops and factories may execute zero, one or many times.
  Camera flags apply to selected scopes, not to every descendant.
- CLI exit is always 0, including invalid arguments and output errors, per brief.
  `measurement_complete`, `errors`, `outputs_complete`, stderr and actual artifact
  existence must be checked; exit 0 is never a guard verdict.
- Test temporary outputs are confined to the worktree under the run's `.tmp/`
  directory and will not be committed. Python bytecode/cache writes are disabled.
- Ownership sweep: `git worktree list` showed one `pd/panel-census` checkout;
  STATUS/bus had no existing competing entries. `Get-Process` read process IDs;
  CIM command-line access was denied, so exact process-to-worktree attribution
  could not be verified. No second conductor on this leg was identified.
- `Get-Command hython` returned no binding. Screenshots and GUI checks are
  NOT_RUN; this source-only leg neither launches nor touches the host.

## Milestone T2

`docs/PANEL_REGION_MAP.md` contains all six camera regions in the requested
review order, semantic widget/HTML surface tables, and an appendix covering all
107 spacing calls plus 4 horizontal/vertical grid-spacing calls across 33 scopes.
Direct factory names are separated from variable ids and unnamed children.
The map states role targets from plan section 4 without inventing role properties.

The real header/ribbon visual owner is `synapse_panel.py:608` and `:927`, already
CAMERA-owned. An external shelf callback file exists at
`houdini/scripts/python/synapse_shelf.py:106`; its protected docked-open path is
not added to CAMERA's write set. `panel/synapse_shelf.py` is absent.

Findings, with producer evidence in the census JSON and region map:

| Measurement | Plan | Observed | Delta / interpretation |
|---|---|---|---|
| Spacing calls | 108 / 12 files | 107 / 14 files | -1 stated total; plan's per-file list itself sums to 103, omitting health_strip and integrity_readout's 2 each |
| Inline setStyleSheet calls | 106 | 106 | 0; includes 2 in chat_display, whose 4 HTML style attributes are a separate metric |
| Six-digit hex | approximately 60 distinct | 135 raw / 75 distinct | +15 versus approximate distinct estimate; raw count exactly matches contract |
| Exemption tags | contract: 0 | 0 | 0 |
| Ds widgets/names | 24 | outside designsystem: 34 sites / 18 names; including factories: 40 sites / 24 names | 24 is distinct names, not widget instances; runtime instances UNKNOWN |
| Density QSS | 3 rules | 13 blocks / 15 selectors | 3 margin targets x 2 densities = 6 margin blocks, plus 7 pre-existing padding blocks; no standard block |
| Grid-spacing methods | not counted | 4 | face_review:261/262 and face_token:448/449; separate counter |
| Unassigned primary sites | not stated | 46 in 12 files | 4 spacing + 1 sheet + 41 raw hex; exceeds the wave's 20-site target even if every assigned file goes to zero |

No role/ownership contradiction is silently corrected in the contract. The
unassigned residue, legacy density padding, non-counted spacing methods, and
external shelf wording are nits for the orchestrator/LEVER to resolve. No scope
expansion is made. Census absence reports do not satisfy CAMERA's zero-site gate.

## Commit delivery blocker

Milestone commit attempted with subject
`pd(census): add source-only rhythm inventory and counter controls` and trailer
`Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`.
Both staging and committing failed with:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-census/index.lock': Permission denied
```

`Get-Acl C:/Users/User/SYNAPSE/.git/worktrees/pd-panel-census` reports explicit
write-deny entries for the sandbox identity. This is an OS/filesystem denial,
not an approval-review rejection. No allowed local Git alternative was found;
remote tools would violate the no-push instruction. No ACL/permission bypass,
alternate index, merge, push, branch switch or write to the main checkout was
attempted. All deliverables remain uncommitted in this worktree at this milestone.

## Validation and baseline comparison

All runs used Python 3.14.2, `QT_QPA_PLATFORM=offscreen`,
`SYNAPSE_REDUCED_MOTION=1`, and `PYTHONDONTWRITEBYTECODE=1`. The full run used
worktree-local TEMP/TMP/TMPDIR and `--basetemp`, respecting the instruction never
to write outside the worktree. Commands (PowerShell, from this worktree):

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:SYNAPSE_REDUCED_MOTION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path (Get-Location) 'harness/panel_pd/runs/2026-09-04/.tmp'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest tests/test_panel_rhythm_census.py tests/test_rope_expert_pin.py tests/test_bp2_paneldesign_density.py tests/test_bp2_paneltruth_density_repolish.py -q -p no:cacheprovider --basetemp harness/panel_pd/runs/2026-09-04/.tmp/restored
python -m pytest tests -q -p no:cacheprovider --basetemp harness/panel_pd/runs/2026-09-04/.tmp/full
```

| Check | Outcome | Evidence |
|---|---|---|
| Census fixtures | PASS, 21 tests | `tests/test_panel_rhythm_census.py:34` through `:141`; 14 parametrized controls and 7 additional tests |
| Expert pin | PASS, 2 tests | `tests/test_rope_expert_pin.py`; targeted and full runs |
| Density rule | PASS, 16 tests | `tests/test_bp2_paneldesign_density.py`; targeted and full runs |
| Density repolish | PASS, 7 tests | `tests/test_bp2_paneltruth_density_repolish.py`; targeted and full runs |
| Targeted group | 46 passed, 1 warning, 0.64 s; exit 0 | Command above, after restoration of the counter mutation |
| Full suite, run once | **6920 passed, 11 failed, 224 skipped**, 84 warnings, 205.82 s; exit 1 | `python -m pytest tests -q -p no:cacheprovider --basetemp .../.tmp/full` |
| Published baseline | 6941 passed, 1 failed, 192 skipped | `harness/panel_pd/BASELINE.md:8` |
| Difference | **21 fewer passes, 10 additional failures, 32 additional skips** | Outcome total 7155 vs 7134 = 21 new census tests. Existing-test passes are 6899 = 6941 - 10 - 32. The pass floor is NOT met. |

The full suite is **not green**. The known baseline failure is
`tests/test_backfill.py::test_backup_is_taken_and_source_intact`.
The additional failures were reproduced in a focused run that does not collect
the census tests (10 failed, 1 skipped in 15.89 s):

```powershell
python -m pytest tests/test_m2_path_policy.py::test_compose_parms_keep_tokens tests/test_orchestrate_close_gate.py tests/test_orchestrate_liveness.py tests/test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir -q -p no:cacheprovider --tb=short -rA --basetemp harness/panel_pd/runs/2026-09-04/.tmp/diagnostic
```

| Additional failure | Observed failure / producer anchor |
|---|---|
| `test_m2_path_policy.py::test_compose_parms_keep_tokens` | `tests/test_m2_path_policy.py:354` calls the existing compose helper; `solaris_compose_tools.py:165` raises through a patched SimpleNamespace that lacks `ComposeError` |
| `test_orchestrate_close_gate.py::test_receipt_uncommitted_holds_at_closing` | `:124`: returned state is empty, expected closing |
| `test_orchestrate_close_gate.py::test_receipt_not_head_holds_at_closing` | `:141`: empty, expected closing |
| `test_orchestrate_close_gate.py::test_receipt_head_but_no_release_holds_at_closing` | `:155`: empty, expected closing |
| `test_orchestrate_close_gate.py::test_clean_leg_passes_end_to_end_in_dry_run` | `:180`: empty, expected done |
| `test_orchestrate_close_gate.py::test_operator_harvested_main_tree_receipt_is_done` | `:196`: empty, expected done |
| `test_orchestrate_close_gate.py::test_manifest_pinned_done_bypasses_gate` | `:208`: empty, expected done |
| `test_orchestrate_liveness.py::test_subagent_workflow_write_moves_last_write` | `:101`: Get-LastProgress returned None |
| `test_orchestrate_liveness.py::test_fresh_subagent_beats_stale_main_transcript` | `:129`: Get-LastProgress returned None |
| `test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir` | `:388`: probe returned writable=True, expected False |

No out-of-scope source/test repair or weakened assertion was made. The exact
environmental/root causes of these extra failures and all 32 extra skips are
not proven. One focused skip explicitly says the temporary root contains
`SYNAPSE`, preventing isolation (`test_orchestrate_liveness.py:144`). Published
baseline counts were not overwritten or reinterpreted as passing here.

Independent source checks (no panel imports): regex over all 84 original files
reproduced **107 / 106 / 135**; every emitted call's line/receiver/source matched
a separately walked AST. Neither new Python file contains a six-digit hex
literal. `git diff --name-only HEAD` returned empty for tracked files: all
production code, existing tests, fonts, tokens, lifecycle and shelf paths remain
byte-identical to branch HEAD. This does not claim a clean worktree: the seven
authorized deliverables are untracked because staging is denied.

Mutation replay, after setting the test environment above:

```powershell
@'
from pathlib import Path
import subprocess, sys
p = Path('harness/notes/panel_rhythm_census.py')
original = p.read_bytes()
source = original.decode()
mutated = source.replace('result["counts"] = summarize([result])',
    'result["counts"] = {k: (0 if isinstance(v, int) else v) for k, v in summarize([result]).items()}')
assert mutated != source
try:
    p.write_text(mutated, encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'pytest',
        'tests/test_panel_rhythm_census.py', '-q', '-p', 'no:cacheprovider',
        '--basetemp', 'harness/panel_pd/runs/2026-09-04/.tmp/mutation'])
    assert result.returncode == 1
finally:
    p.write_bytes(original)
'@ | python -
```

## Acceptance and handoff receipt

| PD-CENSUS acceptance / deliverable | Verdict | Producer |
|---|---|---|
| Per-file census with values, styles, raw/distinct hex, object names, exemptions | PASS | `harness/notes/panel_rhythm_census.py:63`; JSON `files` and `totals` |
| Per-camera named / inline / layout reach | PASS (static only; recall ABSENT) | script `:208`; JSON `camera_regions`; region map `:13` |
| Every visible/source-declared region mapped to owner and target role; all six cameras first | PASS for static map; actual visibility UNKNOWN | `docs/PANEL_REGION_MAP.md:13`, `:56`, `:85`, `:139` |
| Name the actual shelf/header/ribbon owner | PASS | region map `:28`; visual owner `synapse_panel.py`; external shelf launcher explicitly excluded |
| Totals reproduced or deltas stated; Ds counts and density rules | PASS | JSON totals; script `:150`, `:170`; findings table above |
| Pure Python stock-CI CLI, explicit JSON/MD paths, reporting-only exit | PASS | script `:316`; isolated `-I -S` subprocess fixture at test `:120` |
| Positive and negative controls; mutation bites | PASS | 21 new tests; 8 failures under zero-counter mutation, restored green |
| Expert pin and density rule green | PASS | 46-test targeted run and full suite |
| Full suite once, counts vs baseline | RUN, **FAIL floor** | counts above; no baseline modification |
| REPORT / dated STATUS milestones | WRITTEN | this file; `harness/panel_pd/STATUS_CENSUS.md` |
| Commits after milestones, required subject/trailer | **BLOCKED** | Git metadata write deny; no new commit exists |
| Hython screenshots / 380 px docking / GUI sign-off | **NOT_RUN** | No hython binding; this source-only CENSUS leg owns no screenshots or GUI checks |
| Independent CRUX certification | **NOT_RUN** | Separate downstream CRUX leg; builder verification is not an independent verdict |

Files touched (exclusive write set plus the explicitly requested test):

1. `harness/notes/panel_rhythm_census.py`
2. `tests/test_panel_rhythm_census.py`
3. `docs/PANEL_REGION_MAP.md`
4. `harness/panel_pd/runs/2026-09-04/rhythm_census.json`
5. `harness/panel_pd/runs/2026-09-04/rhythm_census.md`
6. `harness/panel_pd/STATUS_CENSUS.md`
7. `docs/panel_pd/REPORT_CENSUS.md`

Receipt fields: `leg=panel_pd:CENSUS:TRUTH`; `verdict=BLOCKED` (commit delivery;
full-suite floor also FAIL); touched/commands/artifacts above;
`proved_it_bites=zero per-file integer counters -> 8 red, restore -> 46 green`;
`could_not_verify=[runtime widget cardinality/visibility, Qt/host measurements,
screenshots, GUI sign-off, independent CRUX, comparable baseline environment,
root causes of additional failures/skips, exact PID-to-worktree attribution]`;
`needs_human=[]` for gated repo acts (no merge/push/release requested).
The environment must permit normal Git metadata writes before the already
authorized commits can occur. Do not treat this uncommitted handoff as done.

Cleanup limit: test fixtures remain under
`harness/panel_pd/runs/2026-09-04/.tmp/` as uncommitted disposable outputs.
The resolved directory was verified inside this worktree and contained no
reparse points. Automatic approval review rejected both the cleanup command and
a narrowed command restricted to that exact directory, returning only
`blocked by policy`. No deletion bypass was attempted. Do not stage `.tmp/`;
only the seven enumerated deliverables are intended for the leg commits.
