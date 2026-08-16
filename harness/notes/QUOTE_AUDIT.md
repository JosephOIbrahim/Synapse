# QUOTE_AUDIT - W6-QUOTE site audit (S1 unquoted-interpolation + S8 BOM)

*Produced by **W6-QUOTE** on `wave6/quote`, 2026-08-16. Kills two failure classes
across `harness/**/*.ps1` and `harness/autorevise/**/*.py`: **S1**
(unquoted-interpolation) and **S8** (BOM/encoding). Rows assigned by the FORGE
ledger (`harness/HARDENING-SPEC.md` Part A, S1+S8). Every disposition is
first-hand: a 5-agent read-only audit fan-out classified every candidate site;
the confirmed-live list is the workflow critic's independent re-read; the fixes
are proven by `tests/test_harness_quoting.py` (41 tests, all green) plus the
`-DryRun` parser matrix and a RED-proof.*

Evidence trail: audit run `wf_d17fb020-5fd`; parser RED-proof (an unsanitized
`'LEG O'Brien'` runner line yields ParseFile errors=1, the sanitized `''` form
yields 0); JSON census `python -c "json.load every harness/**/*.json"` = **371
files, 0 failures** after the repair below.

---

## Central helpers (the generalization)

| File | Function | Contract |
|---|---|---|
| `harness/lib/quote-safe.ps1` (new) | `Sanitize-SQ` | double `'`->`''` for a single-quoted PS literal; the generalization of the `safeName` point-fix (`orchestrate.ps1:243`) |
| `harness/lib/quote-safe.ps1` (new) | `Write-Utf8NoBom` | write UTF-8 with NO BOM (PS 5.1 `Set-Content -Encoding utf8` prepends one) |
| `harness/autorevise/quote_safe.py` (new) | `sanitize_sq` / `ps_single_quote` / `write_json_no_bom` / `has_utf8_bom` | python twin; the test oracle (PS `Sanitize-SQ` output == python `sanitize_sq`, pinned for every adversarial input) |

"Wrap, do not rewrite": no shipped code was rebuilt. Each fix dot-sources the lib
and swaps one expression.

---

## S1 - fixed sites (the launch runner in the live dispatcher)

`orchestrate.ps1`'s `Start-Leg` writes a runner here-string to
`$env:TEMP\orch_<id>.ps1` and executes it via `powershell -File`. Every
write-time interpolation becomes SOURCE inside single-quoted lines of an executed
script, so one apostrophe closes the quote and the tail runs as PowerShell - the
W5-PARITY/SEAT crash-loop and the `943e5375` truncation. **Before:** only
`$safeName` (the name) was escaped. **After:** every uncontrolled field routes
through `Sanitize-SQ`.

| # | Line (orig) | Field | Context | Before | After |
|---|---|---|---|---|---|
| 1 | 357 | `$wt` (worktree path) | `Set-Location '...'` | `'$wt'` | `'$safeWt'` |
| 2 | 359 | `$leg.id` | single-quoted Write-Host | `$($leg.id)` | `$safeId` |
| 3 | 359 | `$leg.branch` | single-quoted Write-Host | `$($leg.branch)` | `$safeBranch` |
| 4 | 360 | `$promptPath` | single-quoted Write-Host | `$promptPath` | `$safePrompt` |
| 5 | 362 | `$profile` (settings path) | **unquoted** `--settings` arg | `--settings $profile` | `--settings '$safeProfile'` |
| 6 | 362 | `$leg.id` | single-quoted `--name` value | `$($leg.id)` | `$safeId` |
| 7 | 362 | `$promptPath` | single-quoted prompt arg | `$promptPath` | `$safePrompt` |
| 8 | 365 | `$leg.id` | single-quoted Write-Host | `$($leg.id)` | `$safeId` |
| 9 | 368 | `$leg.id` | single-quoted Write-Host | `$($leg.id)` | `$safeId` |

`$safeName` (name) was already escaped at :243 - kept, now via `Sanitize-SQ`.
`$($manifest.effort)$modelArg` is operator-set config (CONFIG-LOW-RISK), left
as-is. The temp filename `orch_$($leg.id).ps1` is left un-sanitized ON PURPOSE:
leg ids are manifest-authored (not free user text) and the close-state reaper
(`orchestrate.ps1` ~:536, **W6-GATE territory**) matches that exact literal - a
change here would desync it.

Bonus (`-DryRun` control fidelity): the dry run now WRITES the real runner
(BOM-free, not launched), so the adversarial-name matrix parses exactly what a
live run builds instead of a lookalike. Verified: 14 adversarial names/branches
(apostrophe, backtick, `$`, `"`, em-dash, CJK, newline, injection payloads) all
yield a runner with **0 parse errors, 0 BOM, name present and escaped**.

---

## S1 - reviewed & NOT a live injection (with reason)

| Surface | Verdict | Why |
|---|---|---|
| `harness/rope/{closer,finisher,rc,t45}.ps1` here-strings | SAFE | build MARKDOWN report text (`AFTERNOON_REPORT.md`/`STATUS.md`), never an executed runner |
| `harness/supply_shipping_deps.ps1:43` (`hython -c` here-string) | SAFE | fixed literal module list, no `$var`/`$(...)` interpolation |
| all `Start-Process -ArgumentList` / `& git` / `git worktree add` | SAFE | array-argv (separate strings) or argv-style git; a space/quote lands as a discrete argument, cannot split |
| `harness/autorevise/**/*.py` | SAFE | no `shell=True`/`os.system`; only subprocess is a list-argv (`fold_parity_w5l.py:110`); every `json.dumps` uses `encoding="utf-8"` (BOM-free) |
| `harness/retired/run_followon.ps1:64` | RETIRED | same class (`$leg.id`/`$leg.wt` in a runner here-string), but under `harness/retired/` - frozen, not live-dispatched. Recorded, not touched. |
| `harness/run.ts` (S1 origin surface `0522ad0e`/`943e5375`) | OUT OF SCOPE | `.ts`, outside this leg's sweep globs (`*.ps1` + `autorevise/**/*.py`); already uses delivery-by-file-reference. A TypeScript quoting lint is a **spawn proposal** (below). |

The python twin is therefore provided as the central helper + test oracle
(retrofitted nowhere, because nowhere on the python surface needs it).

---

## S8 - fixed sites (committed JSON must parse)

The R26 order ("assert every JSON under `harness/` parses with `json.load`") was
never built. One committed JSON failed it:

| File | Before | After |
|---|---|---|
| `harness/notes/base_control/run_control.ps1:194` (producer) | `... \| ConvertTo-Json \| Set-Content 'resolved_lines.json' -Encoding utf8` (BOM) | `... \| ConvertTo-Json \| Write-Utf8NoBom -Path 'resolved_lines.json'` |
| `harness/notes/base_control/resolved_lines.json` (artifact) | started `EF BB BF` -> `json.load` raised "Unexpected UTF-8 BOM" | BOM stripped byte-faithfully; parses clean |
| `harness/orchestrate.ps1` runner write (orig :369) | `Set-Content $script -Encoding utf8` | `Write-Utf8NoBom` (defense-in-depth + unicode names) |
| `harness/orchestrate.ps1` lock write (orig :387) | `... ConvertTo-Json \| Set-Content $lock -Encoding utf8` | `... ConvertTo-Json \| Write-Utf8NoBom -Path $lock` |

Census after fix: **371 committed `*.json` under `harness/`, 0 fail `json.load`.**

## S8 - reviewed & left as-is (CONFIG-LOW-RISK, documented not hidden)

These write a UTF-8 BOM but to a **runtime-only** file (a lock / TEMP scratch /
pointer / flag), read back by BOM-tolerant PowerShell `ConvertFrom-Json`, never a
committed `*.json` and never a python `json.load` consumer. Left unchanged to
keep the edit surface tight (M13/scope discipline); recorded here so the gap is
named, not omitted:

`drive_autoresearch.ps1:136` (lock), `_idle_control.ps1:27,53` (TEMP legs.json),
`dispatch_lock_control.ps1:48` (`.lock` fixture), `finalize.ps1:97` (VERSION,
self-heals via `ruff --fix`), pid files (`-Encoding ascii`, no BOM), rope
markdown, `measure_shipping_residual.ps1` log. `harness/retired/*` excluded as
frozen.

---

## Gates shipped (`tests/test_harness_quoting.py`, 41 tests)

| Gate | What it pins | Proven able to fail |
|---|---|---|
| adversarial-name `-DryRun` matrix | every runner parses clean via the PS Language Parser, BOM-free, name escaped | RED-proof: unsanitized `'LEG O'Brien'` -> ParseFile errors=1 |
| `test_lint_no_inline_command_interpolation` | no committed harness `.ps1` builds `-Command "...$..."` (zero today) | negative control fixture flagged |
| `test_lint_all_harness_json_parses` (R26) | every committed `*.json` under harness parses | negative control: BOM'd json flagged |
| `test_lint_no_bom_json_writes` | no committed harness `.ps1` writes a `*.json` path with `-Encoding utf8` | negative control fixture flagged |
| `test_ps_and_python_sanitize_agree` | PS `Sanitize-SQ` == python `sanitize_sq` for every adversarial input | two-sided oracle |

PowerShell-driven tests SKIP (never a false pass) where no `powershell`/`pwsh`
exists; the pure-python lints run everywhere.

---

## Zero-remaining claim

Within the sweep scope (`harness/**/*.ps1` + `harness/autorevise/**/*.py`), every
uncontrolled mission/leg/branch/user string that reaches a breakable quoted
context is now either Sanitize-SQ'd (the 9 live orchestrate runner sites) or
verified safe-by-construction (array-argv, markdown, no-interp, python list-argv)
or explicitly out of scope (retired / `run.ts`). The producer lints keep it zero.

## Spawn proposals (class `probe`, held for Joe)

1. **TypeScript quoting lint for `harness/run.ts`** - the S1 origin surface is
   `.ts`, outside this leg's globs; a parallel `Sanitize-SQ`/no-inline-command
   lint for the TS launcher would close the last S1 surface.
2. **CONFIG-LOW-RISK BOM sweep** - migrate the runtime-lock BOM writers to
   `Write-Utf8NoBom` if any of those locks ever gains a python `json.load` reader.
