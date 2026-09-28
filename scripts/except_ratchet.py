#!/usr/bin/env python
"""
Ratchet: silent broad-except detector.

Walks python/synapse/**/*.py (excludes _vendor/, __pycache__/), parses each file,
identifies broad exception handlers (type=None or name in {Exception, BaseException}
or tuple containing either), checks if each is silent (no Raise, no Call to log/warn/etc).

Usage:
  scripts/except_ratchet.py                    # Check against baseline
  scripts/except_ratchet.py --write-baseline   # Write baseline
"""

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Words that signal the handler is not silent
LOGGING_KEYWORDS = {
    "log", "warn", "warning", "error", "exception", "record",
    "report", "notify", "telemetry", "print", "debug", "info"
}


def is_broad_handler(handler: ast.ExceptHandler) -> bool:
    """Check if an except handler catches everything (broad exception)."""
    if handler.type is None:
        # bare `except:`
        return True

    # Check for Exception or BaseException directly
    if isinstance(handler.type, ast.Name):
        if handler.type.id in ("Exception", "BaseException"):
            return True

    # Check for tuple containing Exception or BaseException
    if isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                if elt.id in ("Exception", "BaseException"):
                    return True

    return False


def is_silent_handler(handler: ast.ExceptHandler) -> bool:
    """Check if an except handler body has no Raise and no logging calls."""
    # Walk the handler body looking for Raise nodes or logging calls
    for node in ast.walk(handler):
        # Any Raise means it's not silent (re-raises or raises new)
        if isinstance(node, ast.Raise):
            return False

        # Check for calls that look like logging
        if isinstance(node, ast.Call):
            func_name = None

            # Handle direct Name calls: log(...), warn(...)
            if isinstance(node.func, ast.Name):
                func_name = node.func.id.lower()

            # Handle attribute calls: logger.warn(...), log.error(...)
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr.lower()

            # Check if this looks like a logging call
            if func_name and any(keyword in func_name for keyword in LOGGING_KEYWORDS):
                return False

    return True


class RatchetUnparsable(Exception):
    """A scanned file could not be read or parsed.

    The ratchet fails closed on it (prints ``UNPARSED <path>`` and exits 1)
    rather than silently counting an unreadable file as a clean zero. Fail-open
    is exactly how a broken file (an IndentationError) slipped this gate before
    (BP11-HARDFIX defect 6).
    """

    def __init__(self, filepath):
        super().__init__(str(filepath))
        self.filepath = filepath


def analyze_file(filepath: Path) -> Tuple[int, int]:
    """
    Analyze a Python file.

    Returns: (broad_count, silent_count)
    where silent_count is the number of silent broad handlers.

    Raises :class:`RatchetUnparsable` when the file cannot be read or parsed.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        raise RatchetUnparsable(filepath) from exc

    broad_count = 0
    silent_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if is_broad_handler(node):
                broad_count += 1
                if is_silent_handler(node):
                    silent_count += 1

    return broad_count, silent_count


def walk_python_files(root: Path) -> List[Path]:
    """Walk all .py files under root, excluding _vendor/ and __pycache__/."""
    files = []
    for path in root.rglob("*.py"):
        # Skip vendor and cache directories
        parts = path.parts
        if "_vendor" in parts or "__pycache__" in parts:
            continue
        files.append(path)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="Check or baseline silent broad-except handlers."
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write baseline to tests/fixtures/except_ratchet_baseline.json"
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Directory to scan (default: python/synapse under the repo). "
             "Lets a control point the ratchet at a temporary tree."
    )
    parser.add_argument(
        "--rel-base",
        default=None,
        help="Base directory for the relative-path keys (default: repo root)."
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Baseline JSON path (default: tests/fixtures/except_ratchet_baseline.json)."
    )
    args = parser.parse_args()

    # Determine repo root (assume script is at scripts/except_ratchet.py)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    scan_root = Path(args.root).resolve() if args.root else (repo_root / "python" / "synapse")
    rel_base = Path(args.rel_base).resolve() if args.rel_base else repo_root
    if args.baseline:
        baseline_path = Path(args.baseline).resolve()
    else:
        baseline_path = repo_root / "tests" / "fixtures" / "except_ratchet_baseline.json"

    if not scan_root.exists():
        print(f"Error: scan root not found at {scan_root}", file=sys.stderr)
        sys.exit(1)

    def rel_key(path: Path) -> str:
        try:
            return path.relative_to(rel_base).as_posix()
        except ValueError:
            return path.as_posix()

    # Analyze all files
    files_data: Dict[str, int] = {}
    unparsed: List[Path] = []
    repo_wide_silent = 0
    repo_wide_broad = 0

    for filepath in walk_python_files(scan_root):
        try:
            broad_cnt, silent_cnt = analyze_file(filepath)
        except RatchetUnparsable:
            unparsed.append(filepath)
            continue

        if silent_cnt > 0:
            files_data[rel_key(filepath)] = silent_cnt

        repo_wide_silent += silent_cnt
        repo_wide_broad += broad_cnt

    # Fail closed: a file we cannot read or parse is a defect, never a clean 0.
    if unparsed:
        for filepath in sorted(unparsed, key=str):
            print(f"UNPARSED {rel_key(filepath)}")
        print(
            f"{len(unparsed)} file(s) could not be read or parsed; "
            "ratchet fails closed.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.write_baseline:
        # Write baseline fixture
        baseline_path.parent.mkdir(parents=True, exist_ok=True)

        baseline = {
            "_rule": "silent broad-except ratchet: count may shrink, never grow",
            "files": files_data
        }

        with open(baseline_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(baseline, f, indent=2, sort_keys=True)

        print(f"Baseline written to {baseline_path}")
        print(f"Files with silent handlers: {len(files_data)}")
        print(f"Total silent broad-except handlers: {repo_wide_silent}")
        print(f"Total broad-except handlers: {repo_wide_broad}")
        sys.exit(0)

    # Check mode: compare against baseline
    baseline_data = {}
    if baseline_path.exists():
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline_obj = json.load(f)
            baseline_data = baseline_obj.get("files", {})

    # Check for violations
    violations = []
    for filepath, silent_cnt in files_data.items():
        baseline_cnt = baseline_data.get(filepath, 0)
        if silent_cnt > baseline_cnt:
            violations.append((filepath, baseline_cnt, silent_cnt))

    # Report
    print(f"broad_total={repo_wide_broad}")
    print(f"silent_total={repo_wide_silent}")

    if violations:
        print(f"\nFILE VIOLATIONS ({len(violations)}):")
        for filepath, baseline_cnt, actual_cnt in sorted(violations):
            print(f"  {filepath}: {baseline_cnt} -> {actual_cnt}")
        sys.exit(1)

    # Also check for new files with any silent handlers (baseline absent = 0)
    new_files = [f for f in files_data if f not in baseline_data]
    if new_files:
        print(f"\nNEW FILES WITH SILENT HANDLERS ({len(new_files)}):")
        for filepath in sorted(new_files):
            print(f"  {filepath}: 0 -> {files_data[filepath]}")
        sys.exit(1)

    print("OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
