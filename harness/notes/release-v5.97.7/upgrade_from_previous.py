"""Qualify a genuine previous-version upgrade, in a disposable isolated sandbox.

The stock installer harness (``installer/test_executable.py``) upgrades from a
synthetic 0.0.1 payload, so it proves the upgrade machinery but not the
upgrade path a real artist takes. The release card asks for a *genuine*
previous-version upgrade. This harness supplies one: it installs a real
previous release's TestSetup, then installs the new one over it, in its own
fenced root, and records what actually happened.

Everything is disposable and inside ``--root``. The real Houdini preferences,
the real user home and the real application folder are never touched: the
previous Setup and the new Setup are both TestSetups, which pass
``--sandbox <root>`` to the engine, and the engine's sandbox branch never
consults the artist's running Houdini sessions.

Nothing is inferred. Every check reads the state the installer wrote.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "installer"))

from synapse_setup.safety import file_hash, json_bytes  # noqa: E402


def execute(exe, arguments, log):
    result = subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART",
                             "/LOG=" + str(log), *arguments], timeout=1800,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return result.returncode


def main():
    if os.name != "nt":
        raise RuntimeError("This compiled installer test requires Windows.")
    import winreg
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-setup", required=True, type=Path)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--hfs", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--previous-version", required=True)
    parser.add_argument("--previous-payload-id", required=True,
                        help="Payload id the published previous release carried.")
    parser.add_argument("--previous-source-revision", required=True,
                        help="Git commit the published previous release carried.")
    parser.add_argument("--expected-payload-id", required=True)
    args = parser.parse_args()

    root = args.root
    if root.exists():
        raise RuntimeError("Use a new test directory; this harness never deletes existing data.")
    root.mkdir(parents=True)
    app = root / "application"
    pref = root / "preferences/houdini22.0"
    seat_home = root / "home"
    logs = root / "logs"
    logs.mkdir()
    arguments = ["/TESTROOT=" + str(root), "/DIR=" + str(app), "/HFS=" + str(args.hfs), "/PREFS=" + str(pref)]
    uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SYNAPSE-Isolated-Installer-Test_is1"
    shortcuts = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/SYNAPSE (isolated test)"

    def registered_in_windows():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key):
                return True
        except FileNotFoundError:
            return False

    if registered_in_windows() or shortcuts.exists():
        raise RuntimeError("An earlier isolated test is still registered. Uninstall it before starting another test.")
    report = {
        "scope": ("Compiled isolated TestSetups: a genuine previous release, then this release, "
                  "upgraded over it in one disposable sandbox"),
        "expected_version": args.expected_version,
        "previous_version": args.previous_version,
        "artifacts": {str(p.resolve()): file_hash(p) for p in (args.previous_setup, args.setup)},
        "checks": [],
    }

    def check(name, passed, **detail):
        report["checks"].append({"name": name, "status": "PASS" if passed else "FAIL", **detail})
        (root / "upgrade-report.json").write_bytes(json_bytes(report))
        print(name + ": " + ("PASS" if passed else "FAIL"), flush=True)
        if not passed:
            raise RuntimeError(name + " failed; see " + str(logs))

    # ---- install the genuine previous release -------------------------------
    code = execute(args.previous_setup, arguments, logs / "previous-install.log")
    check("Genuine previous release installs through compiled Setup",
          code == 0 and (app / "installation.json").is_file(), exit_code=code)
    old = json.loads((app / "installation.json").read_text())
    old_manifest = json.loads((Path(old["active"]) / "payload-manifest.json").read_text())
    check("Installed previous payload is the published previous payload",
          old_manifest["version"] == args.previous_version
          and old_manifest["payload_id"] == args.previous_payload_id
          and old_manifest["source_revision"] == args.previous_source_revision,
          installed_payload_id=old_manifest["payload_id"], installed_version=old_manifest["version"],
          installed_source_revision=old_manifest["source_revision"])
    old_active = old["active"]

    # ---- artist-owned data, written before the upgrade ----------------------
    user_data = [seat_home / ".synapse/encryption.key", seat_home / ".synapse/panel_settings.json",
                 root / "projects/work.hip", root / "projects/.synapse/memory.jsonl", pref / "houdini.env",
                 Path(old_active) / "artist-custom.txt"]
    for path in user_data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"SYNAPSE test: artist-owned data must survive")
    before = {str(p): file_hash(p) for p in user_data}

    # ---- upgrade to this release --------------------------------------------
    code = execute(args.setup, arguments, logs / "upgrade.log")
    current = json.loads((app / "installation.json").read_text()) if (app / "installation.json").exists() else {}
    check("Upgrade installs the new release over the previous one",
          code == 0 and current.get("version") == args.expected_version, exit_code=code)
    check("Upgrade switches the active payload",
          current.get("active") != old_active and Path(current.get("active", "")).is_dir(),
          previous_active=old_active, active=current.get("active"))
    new_manifest = json.loads((Path(current["active"]) / "payload-manifest.json").read_text())
    check("New active payload is the expected payload",
          new_manifest["payload_id"] == args.expected_payload_id
          and new_manifest["version"] == args.expected_version,
          payload_id=new_manifest["payload_id"], version=new_manifest["version"])
    check("Previous payload is retained but no longer active",
          Path(old_active).is_dir() and old_active not in {current["active"]},
          retained=old_active)
    package = json.loads((pref / "packages/synapse.json").read_text())
    check("One registration points at the upgraded payload",
          package["hpath"] == (Path(current["active"]) / "houdini").as_posix()
          and len(list((pref / "packages").glob("*.json"))) == 1)
    check("Artist-owned data survives the upgrade",
          before == {str(p): file_hash(p) for p in user_data})
    verify = subprocess.run([str(app / "maintenance/python/python.exe"), "-I", str(app / "maintenance/setup_cli.py"),
                             "verify", "--app", str(app), "--report", str(logs / "installed-check.json")],
                            capture_output=True)
    check("Upgraded installation passes the new release's own verification", verify.returncode == 0)

    # ---- uninstall the upgraded release -------------------------------------
    code = execute(app / "unins000.exe", [], logs / "uninstall.log")
    check("Generated Windows uninstaller removes the upgraded installation",
          code == 0 and not (pref / "packages/synapse.json").exists()
          and not (app / "installation.json").exists(), exit_code=code)
    check("Uninstall preserves projects, memory, credentials and custom files",
          before == {str(p): file_hash(p) for p in user_data})
    check("Windows uninstall registration and shortcuts removed",
          not registered_in_windows() and not shortcuts.exists())
    report["status"] = "PASS"
    (root / "upgrade-report.json").write_bytes(json_bytes(report))
    print("UPGRADE REPORT: " + str(root / "upgrade-report.json"))


if __name__ == "__main__":
    main()
