"""Reproducible Windows Setup builder. Tool download/install is explicit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from build_payload import ROOT, build
from synapse_setup.safety import SetupError, digest, json_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--moneta-bundle", type=Path)
    parser.add_argument("--moneta-sha256")
    parser.add_argument("--test-build", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "installer/toolchain.lock.json").read_text())
    python_zip = args.downloads / lock["python"]["filename"]
    if digest(python_zip.read_bytes()) != lock["python"]["sha256"]:
        raise SetupError("Embedded Python archive does not match toolchain.lock.json.")
    version_check = subprocess.run([str(args.iscc), "--version"], capture_output=True, text=True)
    if "7.1.0" not in version_check.stdout + version_check.stderr:
        raise SetupError("The reproducible build requires Inno Setup 7.1.0.")
    args.output.resolve().mkdir(parents=True, exist_ok=True)
    # Each invocation gets a new empty staging directory. Never recursively
    # delete an earlier build or accidentally include its stale helper files.
    stage = Path(tempfile.mkdtemp(prefix="test-stage-" if args.test_build else "stage-", dir=args.output.resolve()))
    maintenance = stage / "maintenance"
    stage.mkdir(parents=True, exist_ok=True)
    maintenance.mkdir(exist_ok=True)
    with zipfile.ZipFile(python_zip) as archive:
        archive.extractall(maintenance / "python")
    (maintenance / "python/python313._pth").write_text("python313.zip\n.\n..\n", encoding="utf-8")
    shutil.copyfile(ROOT / "installer/setup_cli.py", maintenance / "setup_cli.py")
    shutil.copytree(ROOT / "installer/synapse_setup", maintenance / "synapse_setup", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(ROOT / "installer/windows/getting-started.html", maintenance / "getting-started.html")
    helper_files = {p.relative_to(maintenance).as_posix(): digest(p.read_bytes())
                    for p in sorted(maintenance.rglob("*")) if p.is_file()}
    (maintenance / "maintenance-manifest.json").write_bytes(json_bytes({"schema": "synapse-maintenance-1", "files": helper_files}))
    payload = build(stage / "payload.zip", args.downloads, args.moneta_bundle, args.moneta_sha256)
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if payload["moneta"]:
        license_text += "\n\nMONETA: PROPRIETARY. This build is for local evaluation. Public redistribution rights have not been confirmed.\n"
    (stage / "license.txt").write_text(license_text, encoding="utf-8-sig")
    (stage / "before.txt").write_text(
        f"SYNAPSE {payload['version']}\n\nValidation target: Windows, Houdini 22.0.400, Python 3.13.\n\n"
        "This setup installs SYNAPSE for your Windows account. It includes the model SDK, WebSocket support and file locking. Houdini provides Qt and OpenUSD.\n\n"
        + ("Moneta memory and its USD schema are bundled for this local evaluation build. Proprietary redistribution rights remain unconfirmed.\n\n" if payload["moneta"] else "JSONL project memory is included. Optional Moneta is not bundled in this build.\n\n")
        + "Save and close Houdini before installing, upgrading or uninstalling. Setup never terminates Houdini.\n\n"
        "You will connect a model after installation. No model, API key or internet connection is required by Setup.\n\n"
        "This local installer is unsigned. Public distribution and code signing are separate release steps.\n", encoding="utf-8-sig")
    command = [str(args.iscc.resolve()), "--quiet", "/DStageDir=" + str(stage), "/DAppVersion=" + payload["version"]]
    if args.test_build:
        command.append("/DTestBuild=1")
    command.append(str(ROOT / "installer/windows/Synapse.iss"))
    subprocess.run(command, check=True)
    filename = f"SYNAPSE-{payload['version']}-{'TestSetup' if args.test_build else 'Setup'}.exe"
    exe = stage.parent / "output" / filename
    report = {"installer": str(exe), "installer_sha256": digest(exe.read_bytes()), "signing": "unsigned",
              "test_build": args.test_build, "payload": payload, "toolchain": lock,
              "maintenance_files": helper_files}
    (exe.with_suffix(".build.json")).write_bytes(json_bytes(report))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
