"""Windows integration tests for compiled Setup and its generated uninstaller."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from synapse_setup.safety import inside, no_links, file_hash, json_bytes


def execute(exe, arguments, log):
    result = subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART",
                             "/LOG=" + str(log), *arguments], timeout=180,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return result.returncode


if __name__ == "__main__":
    if os.name != "nt":
        raise RuntimeError("This compiled installer test requires Windows.")
    import winreg
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--previous-setup", required=True, type=Path)
    parser.add_argument("--broken-setup", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--hfs", required=True, type=Path)
    args = parser.parse_args()
    root = no_links(args.root)
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
    report = {"scope": "Compiled isolated TestSetup; synthetic 0.0.1 prior payload, never a historical release",
              "artifacts": {str(p.resolve()): file_hash(p) for p in (args.setup, args.previous_setup, args.broken_setup)}, "checks": []}

    def check(name, passed, **detail):
        report["checks"].append({"name": name, "status": "PASS" if passed else "FAIL", **detail})
        (root / "executable-report.json").write_bytes(json_bytes(report))
        print(name + ": " + ("PASS" if passed else "FAIL"), flush=True)
        if not passed:
            raise RuntimeError(name + " failed; see " + str(logs))

    code = execute(args.broken_setup, arguments, logs / "missing-dependency.log")
    check("Missing required dependency blocks compiled setup", code != 0 and not (pref / "packages/synapse.json").exists(), exit_code=code)
    failure_log = (logs / "missing-dependency.log").read_text(encoding="utf-8-sig")
    check("Failure explains the missing dependency in readable text", "Required runtime dependencies are missing:" in failure_log
          and "anthropic/__init__.py" in failure_log and "\x00" not in failure_log)
    blocked = inside(root / "write-denied", root)
    blocked.mkdir()
    # Deny only data creation/writes in this new fixture. Retain ownership and
    # ACL-edit rights, and always remove this single explicit deny afterwards.
    sid = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True).strip().split(',')[-1].strip('"')
    subprocess.run(["icacls", str(blocked), "/deny", "*" + sid + ":(OI)(CI)(W)"], check=True, capture_output=True)
    try:
        denied_arguments = [value for value in arguments if not value.startswith("/DIR=")] + ["/DIR=" + str(blocked / "application")]
        code = execute(args.setup, denied_arguments, logs / "unwritable.log")
        check("Windows write-denied destination is rejected", code != 0 and not (pref / "packages/synapse.json").exists()
              and not (blocked / "application").exists(), exit_code=code)
    finally:
        subprocess.run(["icacls", str(blocked), "/remove:d", "*" + sid], check=True, capture_output=True)
    code = execute(args.previous_setup, arguments, logs / "fresh.log")
    check("Fresh installation through compiled Setup", code == 0 and (app / "installation.json").is_file(), exit_code=code)
    check("Windows uninstall registration and shortcuts exist", registered_in_windows()
          and len(list(shortcuts.glob("*.lnk"))) == 3)
    old = json.loads((app / "installation.json").read_text())
    user_data = [seat_home / ".synapse/encryption.key", seat_home / ".synapse/panel_settings.json",
                 root / "projects/work.hip", root / "projects/.synapse/memory.jsonl", pref / "houdini.env",
                 Path(old["active"]) / "artist-custom.txt"]
    for path in user_data:
        inside(path, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"SYNAPSE test: artist-owned data must survive")
    before = {str(p): file_hash(p) for p in user_data}
    code = execute(args.previous_setup, arguments, logs / "repeat.log")
    check("Repeat installation", code == 0, exit_code=code)
    code = execute(args.setup, arguments, logs / "upgrade.log")
    current = json.loads((app / "installation.json").read_text()) if (app / "installation.json").exists() else {}
    check("Upgrade switches active payload", code == 0 and current.get("version") == "5.67.4" and current.get("active") != old["active"], exit_code=code)
    package = json.loads((pref / "packages/synapse.json").read_text())
    check("One registration points at installed files", package["hpath"] == (Path(current["active"]) / "houdini").as_posix()
          and len(list((pref / "packages").glob("*.json"))) == 1
          and not (Path(current["active"]) / "synthetic-retired-file.txt").exists())
    verify = subprocess.run([str(app / "maintenance/python/python.exe"), "-I", str(app / "maintenance/setup_cli.py"),
                             "verify", "--app", str(app), "--report", str(logs / "installed-check.json")], capture_output=True)
    check("Bundled maintenance runtime verifies installation", verify.returncode == 0)
    check("No user-data changes during upgrade", before == {str(p): file_hash(p) for p in user_data})
    for label, path in (("changed registration", pref / "packages/synapse.json"),
                        ("changed maintenance file", app / "maintenance/getting-started.html")):
        original = path.read_bytes()
        edited = original + b"\nartist edit for installer preservation test\n"
        path.write_bytes(edited)
        try:
            code = execute(app / "unins000.exe", [], logs / (label.replace(" ", "-") + ".log"))
            check("Windows uninstaller preserves " + label, code != 0 and path.read_bytes() == edited
                  and (app / "maintenance/python/python.exe").is_file() and (app / "installation.json").is_file(), exit_code=code)
        finally:
            path.write_bytes(original)
    code = execute(app / "unins000.exe", [], logs / "uninstall.log")
    check("Generated Windows uninstaller", code == 0 and not (pref / "packages/synapse.json").exists()
          and not (app / "installation.json").exists(), exit_code=code)
    check("Uninstall preserves projects, memory, credentials and custom files", before == {str(p): file_hash(p) for p in user_data})
    check("Uninstall removes unchanged payload and maintenance files", not (Path(current["active"]) / "VERSION").exists()
          and not (app / "maintenance/python/python.exe").exists())
    check("Windows uninstall registration and shortcuts removed", not registered_in_windows() and not shortcuts.exists())
    code = execute(args.setup, arguments, logs / "reinstall.log")
    check("Reinstall after uninstall with retained data", code == 0 and before == {str(p): file_hash(p) for p in user_data}, exit_code=code)
    # Simulate interruption at the boundary between the completed engine and
    # Inno's Windows cleanup, without terminating or touching any other process.
    partial = subprocess.run([str(app / "maintenance/python/python.exe"), "-I", str(app / "maintenance/setup_cli.py"),
                              "uninstall", "--app", str(app), "--sandbox", str(root),
                              "--report", str(logs / "engine-uninstalled.json")], capture_output=True)
    check("Runtime uninstall can finish before Windows cleanup", partial.returncode == 0
          and not (app / "installation.json").exists() and registered_in_windows())
    code = execute(app / "unins000.exe", [], logs / "resume-uninstall.log")
    check("Windows cleanup resumes after runtime uninstall completed", code == 0 and not registered_in_windows()
          and not (app / "maintenance/python/python.exe").exists() and before == {str(p): file_hash(p) for p in user_data}, exit_code=code)
    report["status"] = "PASS"
    (root / "executable-report.json").write_bytes(json_bytes(report))
