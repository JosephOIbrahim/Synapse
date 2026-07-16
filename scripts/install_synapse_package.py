#!/usr/bin/env python
"""Install the SYNAPSE Houdini package into your Houdini user prefs.

Writes a resolved ``<pref>/packages/synapse.json`` that points at THIS repo, so
the SYNAPSE panel + shelves load on Houdini launch. Uses absolute paths (no
reliance on Houdini package-var resolution) and auto-detects a sibling Moneta
checkout for the optional memory backend.

Usage:
    python scripts/install_synapse_package.py             # auto-detect prefs, install
    python scripts/install_synapse_package.py --dry-run   # show, do not write
    python scripts/install_synapse_package.py --pref-dir "C:/Users/me/Documents/houdini21.0"

Portable alternative (no install): add ``<repo>/packages`` to
``HOUDINI_PACKAGE_DIR`` and Houdini loads the version-controlled package
(packages/synapse.json) directly.

This lives in scripts/ (outside python/synapse/), so print() is fine here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def moneta_src_for(repo_root: Path) -> str | None:
    """A sibling ``../Moneta/src`` checkout, if present (else None)."""
    cand = repo_root.parent / "Moneta" / "src"
    return cand.as_posix() if cand.is_dir() else None


def build_package(repo_root: Path) -> dict:
    """The resolved (absolute-path) package dict. Pure — easy to test."""
    env = [
        {"var": "SYNAPSE_ROOT", "value": repo_root.as_posix()},
        # BOTH paths: python/ (the `synapse` package) AND the repo ROOT (so
        # `import shared` works — shared/ lives at the root, NOT under python/).
        # Omitting the root made SynapseHandler fail to import inside the panel
        # and surfaced a misleading "hou not responding" to the artist.
        {"var": "PYTHONPATH",
         "value": [(repo_root / "python").as_posix(), repo_root.as_posix()],
         "method": "prepend"},
    ]
    moneta = moneta_src_for(repo_root)
    if moneta:
        env.append({"var": "MONETA_SRC", "value": moneta})
    return {
        "name": "synapse",
        "enable": True,
        # Guard against a double-load if both this deployed copy AND
        # HOUDINI_PACKAGE_DIR point at the repo (would double-prepend PYTHONPATH).
        "load_package_once": True,
        "env": env,
        # hpath = the HOUDINI_PATH keyword ("path" is deprecated as of H22);
        # points Houdini at <repo>/houdini (shelves, python panels, scripts).
        "hpath": (repo_root / "houdini").as_posix(),
    }


def candidate_pref_dirs() -> list[Path]:
    """Houdini user pref dirs to install into. $HOUDINI_USER_PREF_DIR wins,
    then any ``houdini2*`` under the home dir, ~/Documents, and the OneDrive
    Documents root. The last one matters on Windows: H22's pref dir is
    ``~/OneDrive/Documents/houdini22.0`` when Documents is redirected to
    OneDrive (a Windows known-folder default), which the plain ~/Documents
    glob would miss — bare auto-detect then silently installs into a stale
    non-OneDrive dir H22 never scans."""
    found: list[Path] = []
    env = os.environ.get("HOUDINI_USER_PREF_DIR")
    if env:
        found.append(Path(env))
    home = Path.home()
    roots = [home, home / "Documents", home / "OneDrive" / "Documents"]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        roots.append(Path(onedrive) / "Documents")
    for root in roots:
        if root.is_dir():
            found.extend(sorted(root.glob("houdini2*"), reverse=True))
    seen: set = set()
    uniq: list[Path] = []
    for p in found:
        if not p.is_dir():
            continue
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def deploy(pref_dir: Path, package: dict, dry_run: bool) -> Path:
    """Write <pref_dir>/packages/synapse.json. Returns the target path."""
    target = pref_dir / "packages" / "synapse.json"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(package, indent=4) + "\n", encoding="utf-8")
    return target


STAMP_NAME = "install_stamp.json"


def stamp_path() -> Path:
    """~/.synapse is SYNAPSE's per-seat state home (encryption.key,
    deploy.json) -- NOT <pref>/packages/, where Houdini parses every
    *.json as a package."""
    return Path.home() / ".synapse" / STAMP_NAME


def synapse_version(repo_root: Path) -> str:
    """Regex, not import -- the installer must run on any stock python."""
    try:
        text = (repo_root / "python" / "synapse" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


def write_stamp(repo_root: Path, targets: list) -> Path:
    """M3-A: the install stamp synapse_doctor reads/compares (version drift,
    missing re-run after a Houdini upgrade)."""
    sp = stamp_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps({
        "schema": "synapse_install_stamp/v1",
        "synapse_version": synapse_version(repo_root),
        "repo_root": repo_root.as_posix(),
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "targets": [t.as_posix() for t in targets],
    }, indent=2) + "\n", encoding="utf-8")
    return sp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Install the SYNAPSE Houdini package.")
    ap.add_argument("--pref-dir", help="Houdini user pref dir (e.g. .../houdini21.0). Default: auto-detect.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be written without writing.")
    args = ap.parse_args(argv)

    repo_root = resolve_repo_root()
    package = build_package(repo_root)

    prefs = [Path(args.pref_dir)] if args.pref_dir else candidate_pref_dirs()
    if not prefs:
        print("No Houdini user pref dir found. Pass --pref-dir explicitly "
              "(e.g. your Documents/houdini21.0).", file=sys.stderr)
        return 1

    print(f"SYNAPSE repo : {repo_root.as_posix()}")
    print(f"package      : {json.dumps(package)}")
    targets = []
    for pref in prefs:
        target = deploy(pref, package, args.dry_run)
        targets.append(target)
        print(f"  {'would write' if args.dry_run else 'wrote'}: {target.as_posix()}")
    if not args.dry_run:
        print(f"stamp        : {write_stamp(repo_root, targets).as_posix()}")
    if args.dry_run:
        print("(dry run -- re-run without --dry-run to install)")
    else:
        print("Done. Restart Houdini to load the SYNAPSE package + panel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
