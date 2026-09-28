# Hardening Ratchets: The Pattern

**Ratchet:** A one-way gate that lets counts go down, never up.

A ratchet prevents silent regressions—new defects that would otherwise hide inside the noise of existing code. The pattern is used by `token_authority` (color declarations), `perf_ratchet` (performance budgets), and now `except_ratchet` (broad exception handlers).

## The Broad-Except Ratchet

**Purpose:** Prevent new silent exception handlers from entering the codebase.

A broad exception handler catches all exceptions (type is `None`, or `Exception`, or `BaseException`). A handler is silent when it catches and suppresses the error with no `raise` and no logging call.

### How the Ratchet Works

1. `scripts/except_ratchet.py` walks `python/synapse/**/*.py` (skips `_vendor/` and `__pycache__/`).
2. Each file is parsed with `ast.parse()` to find exception handlers.
3. For each broad handler, the script checks if the handler body contains:
   - A `raise` statement (re-raises or raises new)
   - A call to logging functions (log, debug, info, warn, warning, error, exception, record, report, notify, telemetry, print)
4. Counts are aggregated per file: **silent_count** = broad handlers with no raise and no logging.
5. A baseline JSON file records the silent count for each file.

### The Baseline

The baseline lives at `tests/fixtures/except_ratchet_baseline.json`:

```json
{
  "_rule": "silent broad-except ratchet: count may shrink, never grow",
  "files": {
    "python/synapse/identify/facts.py": 0,
    "python/synapse/core/session.py": 2,
    "python/synapse/panel/synapse_panel.py": 1
  }
}
```

Only files with `silent_count > 0` appear in the baseline.

### Running the Ratchet

**Check mode (default):**
```bash
scripts/except_ratchet.py
```

Exits 0 if all files are at or below their baseline. Exits 1 if any file's silent count exceeds its baseline, or if a file has silents but was not in the baseline (new regression).

**The rule, stated once:** `count may shrink, never grow`. A file's silent count may go *down* at any time (lowering a baseline is always allowed and encouraged). It may not go *up* past its baseline. Raising a baseline is Joe's word (see House Rules).

**Fail-closed on unparsable files.** A file the ratchet cannot read or parse is a defect, not a clean zero. The script prints `UNPARSED <path>` for each such file and exits 1 — it never counts an unreadable or syntactically broken module as `(0, 0)`. This is deliberate: a fail-*open* skip is exactly how a broken module (an `IndentationError`) once slipped the gate while reporting a passing baseline. `analyze_file` raises `RatchetUnparsable`; the check refuses to pass while any scanned file is unparsable.

The scan root, the relative-path base, and the baseline file are overridable with `--root`, `--rel-base`, and `--baseline`, so the controls can exercise both the positive (a planted swallow) and fail-closed (an unparsable file) paths against a temporary tree without ever touching the tracked baseline.

Reports:
- File list of all violations
- `broad_total` = all broad-except handlers in the tree
- `silent_total` = all silent broad-except handlers in the tree

**Baseline generation:**
```bash
scripts/except_ratchet.py --write-baseline
```

Scans the tree and writes the baseline file. Lowers a count only when the code improves; raising a baseline is disallowed in CI (Joe's word).

### What Counts as "Not Silent"

- **Raise:** The handler body contains `raise` (with or without an exception)
- **Logging:** The handler body calls a function whose name contains log, debug, info, warn, warning, error, exception, record, report, notify, telemetry, or print
- **Combo:** `except Exception as e: log.error(e); raise` is not silent

### What Doesn't Count

- Comments (even `# pragma: expected`)
- Variable assignment alone (`e = None`)
- Control flow alone (`continue`, `return X`)

If a handler does any of these but also catches and suppresses silently, the silent count increments.

## Token Authority: The Parallel Pattern

The `tests/panel/test_token_authority.py` uses the same ratchet logic for color declarations. Every colour used in the panel is declared in exactly one source file (`python/synapse/panel/tokens.py`). The test:

1. Parses both the bridge and the design system tokens module
2. Finds redeclarations (same name in two places with different values)
3. Fails the test if a redeclaration appears
4. Calibrates the reader against positive and negative controls first (synthetic sources with known answers)

The pattern generalizes: a ratchet + a reader = a guard that prevents specific classes of defects from growing.

## House Rules

1. **No silent regressions.** A new silent handler needs no action from the artist and will hide in review. Fail fast.
2. **Lower is better.** The goal is to shrink counts over time by adding logging or re-raising where appropriate.
3. **Raising the baseline is gated.** Only Joe's word lifts a ceiling. CI rejects pull requests that try to raise a baseline (unless a prior commit in the same PR lowers the actual count back down).
4. **Exact sources.** Token authority reads declarations from code, not comments or docs. Except ratchet reads AST, not grep patterns. Readers that infer are fragile.
5. **Readers first.** Positive and negative controls verify the reader sees what it claims to see before the reader is pointed at the tree.
