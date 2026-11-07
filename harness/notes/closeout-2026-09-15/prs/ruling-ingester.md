## What / why

Repair round for `feat/ruling-ingester` (DEC-3). The refuter blocked it on a Windows regression: the new design source puts roster D3's title `Two visible ← REVERT controls at once` on the board, and that one U+2190 glyph made `python harness/decisions.py` (and so `--write`, whose print precedes `write_markdown()`) and `--keys` die with `UnicodeEncodeError` (rc=1) on a stock cp1252 console or pipe. Reproduced on this tree before changing anything (rc=1 at positions 47 and 52407).

**Fix (harness/decisions.py):** a `tolerant_stdio()` helper that reconfigures `sys.stdout`/`sys.stderr` with `errors="backslashreplace"` (guarded by `hasattr(..., "reconfigure")` and `except (ValueError, OSError)`), called once at the top of `main()` right after `parse_args`. Placing it there covers `--keys`, the default render, `--write`, and also `--resolve`'s echo of `item["text"][:60]` and `--resolved`'s reason text, which carry the same class of risk. Board text is untouched - `item_key` hashes the verbatim title, so no key changes (D3 stays `1c0716af74d4`, D4 `46a61abfe02b`).

**Same class (scripts/ingest_rulings.py):** `main()` calls `decisions.tolerant_stdio()` so a verbatim ruling word with a non-cp1252 glyph cannot crash the echo after `resolved.json` is already written (the restore only covered `resolve()` failures, not the print). `ingest()`'s `out=sys.stdout` default is the same object, so the reconfigure reaches it.

**Regression tests (tests/test_decisions.py):** two subprocess tests with `env={**os.environ, PYTHONIOENCODING: cp1252, PYTHONUTF8: 0}`, `text=True, encoding="utf-8", errors="replace"`:
- `test_keys_survive_a_cp1252_console` - rc==0, no `UnicodeEncodeError` on stderr, `design` in stdout, the `-- N open` trailer printed, and the count of rows whose **kind column** is `design` (`l.split()[1:2] == ["design"]`, i.e. `awk '$2=="design"'`) equals the count from a `PYTHONUTF8=1` control run.
- `test_default_render_survives_a_cp1252_console` - rc in (0, `EXIT_OVERDUE`), no codec error, non-empty stdout.

Both **fail** with the one `tolerant_stdio()` call removed (verified by sed-disable / run / restore; the failures are the exact two original tracebacks) and pass with it.

## Evidence (after the fix, piped stdout cp1252, PYTHONUTF8 unset)

| check | result |
|---|---|
| `python harness/decisions.py --count; echo rc` | `649`, rc=6 (aging gate, unchanged) |
| `python harness/decisions.py --keys \| awk '$2=="design"' \| wc -l` | 17, rc=0, stderr empty; D3 renders as `←`, D4 present; UTF-8 control run also 17 |
| `python harness/decisions.py` (default render) | rc=6, 63013 bytes stdout, stderr empty |
| `pytest tests/test_ingest_rulings.py tests/test_decisions.py tests/test_decisions_resolve.py` | 28 passed |
| `pytest tests/test_statusline.py` (composed: statusline imports decisions, calls `collect(with_ages=False)`) | 13 passed |
| in-process probe (strict cp1252 pipe) | 649 items / 17 design; only non-cp1252 text = design D3; `render(items).encode('cp1252')` False; sink `strict` -> `backslashreplace` |
| `ingest(real roster, 'A1 ratify / B2 keep the accent, retarget the pin / C2a ship', who='joe', dry_run=True)` | rc=0, 3 would-record rows, roster sha256 b47d7813... |
| `ingest(real roster, 'A1 ratify / Z9 ship / A1 ratify / C4', dry_run=True)` then `dry_run=False` | both rc=2 REFUSED (C4 no word; Z9 not on roster; A1 repeated); `resolved.json` sha 22b0c6e4cdf1 unchanged |

Report hygiene, restated as asked: the design-row evidence line is `python harness/decisions.py --keys | awk '$2=="design"' | wc -l` -> 17. `grep -c ' design '` gives 19 because two ruling rows (M2-CRUX, W2-S3) merely contain the word.

## Notes for the human

- The branch was checked out here with `git checkout --ignore-other-worktrees` because the builder's worktree (`.claude/worktrees/wf_4ef50c87-4e2-11`, idle since 12:10) still has `feat/ruling-ingester` checked out at c31acd5b. Its working tree is now one commit behind the branch ref; do not commit from that worktree without updating it first.
- master has advanced one commit past the merge-base (841f742e adds `harness/notes/release-5.70.1/*`), so `git diff --stat master..HEAD` shows those files as deletions - they are not deleted by this branch. The branch was not rebased (out of scope).

## What was NOT checked

- No full `pytest tests/` or hython seat suite (per the laws); only the four targeted files.
- Not run on a real interactive Windows console (`conhost`/Windows Terminal) - the reproduction and verification used a pipe with `PYTHONIOENCODING=cp1252 PYTHONUTF8=0`, the same condition the refuter measured.
- `--write` was not executed (it writes `harness/state/DECISIONS.md`); its `print(render(items))` line is the one the default-render test exercises.
- The optional ingest-side test (a ruling word carrying a non-cp1252 glyph through `main()`) was not added; only the reconfigure call landed there, with the CLI still covered by the existing `test_cli_entry_point_runs`.
- Not verified on macOS/Linux CI (UTF-8 sinks; `reconfigure(errors=...)` is a no-op in effect there).
- Local interpreter is Python 3.14.2; `TextIOWrapper.reconfigure` exists from 3.7.

🤖 Generated with [Claude Code](https://claude.com/claude-code)