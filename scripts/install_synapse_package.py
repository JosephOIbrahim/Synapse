#!/usr/bin/env python
"""Install the SYNAPSE Houdini package into your Houdini user prefs.

Writes a resolved ``<pref>/packages/synapse.json`` that points at THIS repo, so
the SYNAPSE panel + shelves load on Houdini launch. Uses absolute paths (no
reliance on Houdini package-var resolution) and auto-detects a sibling Moneta
checkout for the optional memory backend.

Usage:
    python scripts/install_synapse_package.py             # auto-detect prefs, install
    python scripts/install_synapse_package.py --dry-run   # show, do not write
    python scripts/install_synapse_package.py --verify     # read-only: did it work?
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


# --------------------------------------------------------------- verify -----
# --verify is STRICTLY READ-ONLY. It never writes packages/synapse.json, never
# writes the install stamp, never mutates Houdini prefs and never mutates the
# environment. It reports each README "You're good if" check on one screen as:
#
#   PASS    the probe ran and the condition holds
#   FAIL    the probe ran and the condition does NOT hold  (-> exit 1)
#   MANUAL  no probe exists outside a running Houdini -- the human must look
#
# MANUAL is never rendered as PASS and never counts toward the exit code.
# Same honesty contract as synapse.server.doctor: a check reports a verdict
# ONLY if its probe actually executed.

PASS = "PASS"
FAIL = "FAIL"
MANUAL = "MANUAL"

# Mirrors tests/test_vendored_deps.py so the installer's verdict and the test
# suite can never disagree. typing_extensions is deliberately absent: it ships
# as a top-level .py module, not a package dir, so an __init__.py loop would
# false-MISS it.
VENDOR_PKGS = ("anthropic", "httpx", "httpcore", "anyio",
               "pydantic", "pydantic_core", "idna", "sniffio")
# (subdir, stem) of each vendored native extension.
VENDOR_NATIVE = (("pydantic_core", "_pydantic_core"), ("jiter", "jiter"))
# H22.0.368 embeds Python 3.13, so cp313 is THE load-bearing ABI -- its absence
# is the highest-value front-door failure to catch. cp311 covers H20.5/21.x and
# is reported but not gated.
H22_ABI = "cp313-win_amd64"
LEGACY_ABI = "cp311-win_amd64"

DOTENV_NAME = ".env"
# The key the brain needs, then the optional extra panel engines.
REQUIRED_KEYS = ("ANTHROPIC_API_KEY",)
OPTIONAL_KEYS = ("GEMINI_API_KEY", "NVIDIA_API_KEY")


def _dotenv_key_names(repo_root: Path) -> set:
    """Names of vars that carry a NON-EMPTY value in <repo>/.env.

    Parser semantics mirror ``synapse.host.auth._load_dotenv`` exactly (strip,
    skip blank/#/no-"=" lines, drop an ``export `` prefix, strip surrounding
    quotes) so this probe can never disagree with what Houdini actually loads.

    Import-free on purpose: importing ``synapse.host.auth`` would trigger the
    vendor sys.path prepend plus a possible ABI RuntimeWarning, and would also
    fold .env into os.environ at import time -- but this installer must run on
    any stock python (see ``synapse_version``, which regex-scrapes for the same
    reason) and --verify must not mutate the environment.

    SECURITY: values are tested for emptiness and immediately discarded. This
    returns NAMES ONLY -- no key material, not even a prefix, is ever stored,
    returned, printed or logged.
    """
    names: set = set()
    try:
        env_path = repo_root / DOTENV_NAME
        if not env_path.is_file():
            return names
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, rhs = line.partition("=")
            name = name.strip()
            if name.startswith("export "):
                name = name[len("export ") :].strip()
            if name and rhs.strip().strip('"').strip("'"):
                names.add(name)  # name only -- rhs is discarded here
    except Exception:
        pass  # a missing/malformed .env is an absent key, not a crash
    return names


def _key_source(var: str, dotenv_names: set) -> str | None:
    """Where the key WOULD come from, or None if absent. Presence only.

    auth._load_dotenv uses setdefault, so an exported shell var wins over the
    file -- report the same precedence so the two can't disagree.
    """
    if os.environ.get(var, "").strip():
        return "shell env"
    if var in dotenv_names:
        return DOTENV_NAME
    return None


def check_clone(repo_root: Path) -> list:
    """README step 1: a real SYNAPSE checkout, not a partial/zip-stripped tree."""
    need = [
        ("python/synapse", (repo_root / "python" / "synapse").is_dir()),
        ("scripts", (repo_root / "scripts").is_dir()),
        ("README.md", (repo_root / "README.md").is_file()),
        # Beyond the README's literal promise: hpath points at <repo>/houdini,
        # so a tree that lost the panel passes the README check and still fails
        # step 4 with no explanation.
        ("houdini/python_panels/synapse_panel.pypanel",
         (repo_root / "houdini" / "python_panels" / "synapse_panel.pypanel").is_file()),
    ]
    missing = [n for n, ok in need if not ok]
    if missing:
        return [(FAIL, "clone", "missing: " + ", ".join(missing))]
    return [(PASS, "clone", f"{len(need)} key paths present")]


def package_points_here(data: dict, repo_root: Path) -> bool:
    """Does a deployed synapse.json point at THIS checkout?"""
    if not isinstance(data, dict) or data.get("name") != "synapse":
        return False
    env = {e.get("var"): e.get("value")
           for e in data.get("env", []) if isinstance(e, dict)}
    pythonpath = env.get("PYTHONPATH")
    if not isinstance(pythonpath, list):
        return False
    want = {(repo_root / "python").as_posix(), repo_root.as_posix()}
    return want.issubset(set(pythonpath))


def pref_names_for(installs: list) -> set:
    """Pref-dir names the discovered Houdini builds actually read.

    "Houdini 22.0.368" -> "houdini22.0" (Houdini keys prefs on major.minor).
    """
    names: set = set()
    for p in installs:
        m = re.search(r"(\d+)\.(\d+)", p.name)
        if m:
            names.add(f"houdini{m.group(1)}.{m.group(2)}")
    return names


def check_package_file(repo_root: Path, prefs: list, targets: set | None = None) -> list:
    """README step 2 + the two troubleshooting rows that reduce to it.

    State, not stdout -- the success line is long gone by the time a stranger is
    confused, but the deployed json is still on disk.

    A bare "something is wired" verdict is not enough: this seat carries eight
    candidate pref dirs and several share a name. What decides whether the panel
    appears is whether the pref dir belonging to the INSTALLED build is wired --
    a wired houdini21.0 next to an unwired houdini22.0 is exactly the drop-day
    trap (installer reports success, H22 never sees the package).
    """
    if not prefs:
        return [(FAIL, "package file",
                 "no Houdini user pref dir found -- launch Houdini once, or "
                 "pass --pref-dir"),
                _stamp_row(repo_root)]
    wired, stale, bad = [], [], []
    for pref in prefs:
        target = pref / "packages" / "synapse.json"
        if not target.is_file():
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            bad.append(pref)
            continue
        (wired if package_points_here(data, repo_root) else stale).append(pref)

    detail = f"{len(wired)}/{len(prefs)} pref dirs wired here"
    if stale:
        detail += f"; {len(stale)} point at another checkout"
    if bad:
        detail += f"; {len(bad)} unparseable"

    status = PASS if wired else FAIL
    if not wired:
        detail += " -- run the installer (no --dry-run)"
    elif targets:
        # Which of the installed builds can actually see us?
        wired_names = {p.name for p in wired}
        covered = sorted(targets & wired_names)
        missed = sorted(targets - wired_names)
        if missed:
            status = FAIL
            detail += (f"; but {', '.join(missed)} is NOT wired -- that build "
                       f"will not show the panel")
        else:
            detail += f"; covers {', '.join(covered)}"
    return [(status, "package file", detail), _stamp_row(repo_root)]


def _stamp_row(repo_root: Path) -> tuple:
    """The install stamp is a DIAGNOSTIC, not the contract -- the deployed
    package json is what Houdini reads. So an absent stamp is reported, not
    failed (the portable HOUDINI_PACKAGE_DIR route legitimately has none);
    only a stamp naming a DIFFERENT checkout is a real wrong-install signal."""
    sp = stamp_path()
    if not sp.is_file():
        return (PASS, "install stamp", "absent (fine if you use HOUDINI_PACKAGE_DIR)")
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return (FAIL, "install stamp", f"unreadable: {sp.as_posix()}")
    stamped = data.get("repo_root")
    if stamped != repo_root.as_posix():
        return (FAIL, "install stamp", f"names another checkout: {stamped}")
    live = synapse_version(repo_root)
    was = data.get("synapse_version")
    drift = "" if was == live else f" (stamped v{was}, repo v{live} -- re-run to refresh)"
    return (PASS, "install stamp", f"this checkout{drift}")


def check_vendor(repo_root: Path) -> list:
    """The zero-manual-pip promise. Filesystem-only: no import can be attempted
    here, because importing a mismatched-ABI .pyd is exactly the crash we are
    trying to predict."""
    vendor = repo_root / "python" / "synapse" / "_vendor"
    if not vendor.is_dir():
        return [(FAIL, "vendored deps", f"missing: {vendor.as_posix()}")]
    missing = [p for p in VENDOR_PKGS if not (vendor / p / "__init__.py").is_file()]
    h22, legacy = [], []
    for sub, stem in VENDOR_NATIVE:
        if not (vendor / sub / f"{stem}.{H22_ABI}.pyd").is_file():
            h22.append(f"{sub}/{stem}")
        if not (vendor / sub / f"{stem}.{LEGACY_ABI}.pyd").is_file():
            legacy.append(f"{sub}/{stem}")
    if missing:
        return [(FAIL, "vendored deps", "incomplete packages: " + ", ".join(missing))]
    if h22:
        return [(FAIL, "vendored deps",
                 f"no {H22_ABI} binary for: " + ", ".join(h22) + " -- H22 (py3.13) will not load")]
    note = "" if not legacy else f"; {LEGACY_ABI} absent (H20.5/21.x only)"
    return [(PASS, "vendored deps",
             f"{len(VENDOR_PKGS)} packages + {H22_ABI} natives{note}")]


def check_api_key(repo_root: Path) -> list:
    """README step 3. Reports PRESENT / ABSENT and the source that would win.
    The value is never read into the report -- see _dotenv_key_names."""
    dotenv_names = _dotenv_key_names(repo_root)
    rows = []
    for var in REQUIRED_KEYS:
        src = _key_source(var, dotenv_names)
        if src:
            rows.append((PASS, "claude key", f"{var} present (via {src})"))
        else:
            rows.append((FAIL, "claude key",
                         f"{var} absent -- add it to {repo_root.as_posix()}/{DOTENV_NAME}"))
    extra = [v for v in OPTIONAL_KEYS if _key_source(v, dotenv_names)]
    rows.append((PASS, "extra engines",
                 (", ".join(extra) + " present") if extra else "none (optional)"))
    return rows


def houdini_installs() -> list:
    """Discoverable Houdini installs, newest-first. $HFS wins."""
    found: list = []
    hfs = os.environ.get("HFS")
    if hfs and Path(hfs).is_dir():
        found.append(Path(hfs))
    roots = [Path(os.environ[v]) / "Side Effects Software"
             for v in ("ProgramW6432", "ProgramFiles") if os.environ.get(v)]
    roots.append(Path("C:/Program Files/Side Effects Software"))
    roots.append(Path("/opt"))  # Linux convention
    seen: set = set()
    uniq: list = []
    for root in roots:
        if root.is_dir():
            found.extend(sorted(root.glob("Houdini [0-9]*"), reverse=True))
            found.extend(sorted(root.glob("hfs[0-9]*"), reverse=True))
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def check_houdini(installs: list) -> list:
    """Is there a Houdini for the package to load into, and is it an H22?"""
    if not installs:
        return [(FAIL, "houdini", "no install found -- set $HFS if it lives "
                                  "outside Program Files/Side Effects Software")]
    names = [p.name for p in installs]
    h22 = [n for n in names if "22." in n]
    detail = ", ".join(names[:3]) + ("" if len(names) <= 3 else f" (+{len(names) - 3})")
    if not h22:
        return [(PASS, "houdini", detail + " -- no H22 found (H21 dual-build supported)")]
    return [(PASS, "houdini", detail)]


def manual_rows() -> list:
    """The in-Houdini-only checks. No process outside Houdini can observe a
    menu registry, an undo stack or Qt widget text -- so these are printed with
    the exact action for the human and are NEVER inferred from a green probe."""
    return [
        (MANUAL, "pane tab menu", "restart Houdini -> New Pane Tab > Synapse (title-case in the menu)"),
        (MANUAL, "make a box", 'type "make a box" in the panel -> a real geo node you can Ctrl+Z'),
        (MANUAL, "bridge button", "if the panel can't reach Houdini: click Connect in the panel footer"),
    ]


def collect_rows(repo_root: Path, prefs: list) -> list:
    # Discover once: the Houdini builds on disk decide WHICH pref dir has to be
    # wired, so the package check and the houdini check share one probe.
    installs = houdini_installs()
    rows: list = []
    rows += check_clone(repo_root)
    rows += check_package_file(repo_root, prefs, pref_names_for(installs))
    rows += check_vendor(repo_root)
    rows += check_api_key(repo_root)
    rows += check_houdini(installs)
    rows += manual_rows()
    return rows


def verify(repo_root: Path, prefs: list) -> int:
    """Print the one-screen report. Returns 1 if any programmatic check FAILED.
    Writes nothing, anywhere."""
    rows = collect_rows(repo_root, prefs)
    print(f"SYNAPSE verify : {repo_root.as_posix()}")
    print(f"version        : {synapse_version(repo_root)}")
    print("")
    for status, label, detail in rows:
        print(f"  {status:<6}  {label:<15}  {detail}")
    print("")
    failed = sum(1 for r in rows if r[0] == FAIL)
    passed = sum(1 for r in rows if r[0] == PASS)
    manual = sum(1 for r in rows if r[0] == MANUAL)
    print(f"{passed} pass, {failed} fail, {manual} manual "
          f"(manual = check it yourself in Houdini; never assumed)")
    if failed:
        print("Not ready. Fix the FAIL rows above, then re-run --verify.")
    else:
        print("All programmatic checks pass. Finish the MANUAL rows in Houdini.")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Install the SYNAPSE Houdini package.")
    ap.add_argument("--pref-dir", help="Houdini user pref dir (e.g. .../houdini21.0). Default: auto-detect.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be written without writing.")
    ap.add_argument("--verify", action="store_true",
                    help="Read-only: report each install check as PASS/FAIL/MANUAL. Writes nothing.")
    args = ap.parse_args(argv)

    repo_root = resolve_repo_root()

    prefs = [Path(args.pref_dir)] if args.pref_dir else candidate_pref_dirs()

    # Before the install-only guard: an empty pref list is a FAIL *row*, not a
    # reason to print install advice and bail.
    if args.verify:
        return verify(repo_root, prefs)

    package = build_package(repo_root)

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
