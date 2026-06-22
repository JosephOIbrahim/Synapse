#!/usr/bin/env python3
"""Cross-platform verify helpers for SYNAPSE harness contracts.

Shell built-ins differ on Windows cmd.exe, so checks run in Python, not the shell —
identical behavior on Windows/macOS/Linux. Exit 0 == check passes.

ANVIL checks:
  absent-file   <path>
  present-file  <path>
  absent-symbols <dir> <symbol> [<symbol> ...]

SYNAPSE checks:
  no-importers  <module_path_or_stem> <search_root>     # passes if nothing imports the module
  importable    <dotted.module>                          # passes if it imports cleanly (headless)
  max-min-height <root> <N>                              # passes if no setMinimumHeight/Fixed > N
  symbols-in-runtime <module_file> [<manifest_json>]     # passes if no phantom hou.*/pdg.* present
"""
import json
import re
import sys
import pathlib
import subprocess

DEFAULT_MANIFEST = pathlib.Path(".synapse") / "runtime_symbols.H21_0_671.json"


# ---------------- ANVIL checks ----------------
def absent_file(path):
    return 0 if not pathlib.Path(path).exists() else 1


def present_file(path):
    return 0 if pathlib.Path(path).exists() else 1


def absent_symbols(root, symbols):
    p = pathlib.Path(root)
    if not p.exists():
        return 0
    pat = re.compile("|".join(re.escape(s) for s in symbols))
    for f in p.rglob("*"):
        if not f.is_file():
            continue
        try:
            if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                return 1
        except (OSError, UnicodeError):
            continue
    return 0


# ---------------- SYNAPSE checks ----------------
def no_importers(module, search_root):
    """Pass (0) if no .py under search_root imports `module` (by file stem). Heuristic, like
    absent-symbols: catches `import stem`, `from x import stem`, `from x.stem import ...`."""
    stem = pathlib.Path(module).stem
    root = pathlib.Path(search_root)
    if not root.exists():
        return 0
    pat = re.compile(
        r"(?m)^\s*(?:from\s+[\w.]*\b" + re.escape(stem) + r"\b[\w.]*\s+import\b"
        r"|from\s+[\w.]+\s+import\s+[^#\n]*\b" + re.escape(stem) + r"\b"
        r"|import\s+[\w.]*\b" + re.escape(stem) + r"\b)"
    )
    for f in root.rglob("*.py"):
        if f.stem == stem:                  # the module itself doesn't count
            continue
        try:
            if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
                return 1                     # found an importer => not retired
        except (OSError, UnicodeError):
            continue
    return 0


def importable(dotted):
    """Pass (0) if `python -c "import <dotted>"` succeeds (headless-safe modules only)."""
    proc = subprocess.run([sys.executable, "-c", f"import {dotted}"],
                          capture_output=True, text=True)
    return 0 if proc.returncode == 0 else 1


def max_min_height(root, limit):
    """Pass (0) if no setMinimumHeight(N)/setFixedHeight(N) with N > limit anywhere under root."""
    try:
        limit = int(limit)
    except ValueError:
        return 2
    p = pathlib.Path(root)
    if not p.exists():
        return 0
    pat = re.compile(r"set(?:Minimum|Fixed)Height\(\s*(\d+)\s*\)")
    for f in p.rglob("*.py"):
        try:
            for m in pat.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                if int(m.group(1)) > limit:
                    return 1
        except (OSError, UnicodeError):
            continue
    return 0


def _resolve_module_file(module_file):
    cand = pathlib.Path(module_file)
    if cand.exists():
        return cand
    # try treating it as a dotted name under common roots
    rel = pathlib.Path(*module_file.split(".")).with_suffix(".py")
    for base in (pathlib.Path("."), pathlib.Path("python"), pathlib.Path("python") / "synapse"):
        if (base / rel).exists():
            return base / rel
    return cand


def symbols_in_runtime(module_file, manifest=None):
    """Pass (0) if the module introduces no phantom hou.*/pdg.* symbol.

    Static, manifest-based (works anywhere, matches the write-time fence):
      - ALWAYS fail on a known phantom.
      - In allowlist mode (manifest has allowed_symbols), fail on any host symbol absent from it.
    If run under hython (hou importable), also cross-checks first-level attrs against dir(hou).
    """
    mf = _resolve_module_file(module_file)
    if not mf.exists():
        print(f"symbols-in-runtime: module not found: {module_file}", file=sys.stderr)
        return 2
    man_path = pathlib.Path(manifest) if manifest else DEFAULT_MANIFEST
    man = {}
    if man_path.exists():
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception:
            man = {}
    known = set(man.get("known_phantoms", []) or [])
    allowed = set(man.get("allowed_symbols", []) or [])
    src = mf.read_text(encoding="utf-8", errors="ignore")

    for ph in known:
        if re.search(r"(?<![\w.])" + re.escape(ph) + r"(?![\w])", src):
            print(f"symbols-in-runtime: PHANTOM '{ph}' present in {mf}", file=sys.stderr)
            return 1

    # optional live cross-check (only meaningful inside hython)
    live = None
    try:
        import hou  # noqa
        live = set(dir(hou))
    except Exception:
        live = None

    for pref in ("hou.", "pdg."):
        base = pref.rstrip(".")
        for m in re.finditer(re.escape(pref) + r"([A-Za-z_][A-Za-z0-9_]*)", src):
            attr = m.group(1)
            first = pref + attr
            full = base + "." + attr
            if allowed and first not in allowed and full not in allowed:
                print(f"symbols-in-runtime: '{first}' absent from manifest allowlist", file=sys.stderr)
                return 1
            if live is not None and base == "hou" and attr not in live:
                print(f"symbols-in-runtime: '{first}' absent from live dir(hou)", file=sys.stderr)
                return 1
    return 0


def main(argv):
    if not argv:
        print("usage: verify.py <check> ...", file=sys.stderr)
        return 2
    check, rest = argv[0], argv[1:]
    if check == "absent-file" and len(rest) == 1:
        return absent_file(rest[0])
    if check == "present-file" and len(rest) == 1:
        return present_file(rest[0])
    if check == "absent-symbols" and len(rest) >= 2:
        return absent_symbols(rest[0], rest[1:])
    if check == "no-importers" and len(rest) == 2:
        return no_importers(rest[0], rest[1])
    if check == "importable" and len(rest) == 1:
        return importable(rest[0])
    if check == "max-min-height" and len(rest) == 2:
        return max_min_height(rest[0], rest[1])
    if check == "symbols-in-runtime" and len(rest) >= 1:
        return symbols_in_runtime(rest[0], rest[1] if len(rest) > 1 else None)
    print(f"unknown or malformed check: {check} {rest}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
