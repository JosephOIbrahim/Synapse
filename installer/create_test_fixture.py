"""Build an explicitly synthetic previous/broken Setup for lifecycle tests only."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from build_payload import zip_bytes
from synapse_setup.safety import digest, json_bytes

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-report", type=Path, required=True)
    p.add_argument("--iscc", type=Path, required=True)
    p.add_argument("--kind", choices=["previous", "missing-dependency"], required=True)
    args = p.parse_args()
    report = json.loads(args.build_report.read_text())
    if not report["test_build"]:
        raise RuntimeError("Fixtures can be derived only from an isolated TestSetup build.")
    original_stage = Path(report["payload"]["path"]).parent
    stage = Path(tempfile.mkdtemp(prefix="fixture-" + args.kind + "-", dir=original_stage.parent))
    for name in ("license.txt", "before.txt"):
        shutil.copyfile(original_stage / name, stage / name)
    shutil.copytree(original_stage / "maintenance", stage / "maintenance")
    with zipfile.ZipFile(original_stage / "payload.zip") as bundle:
        files = {name: bundle.read(name) for name in bundle.namelist()}
    manifest = json.loads(files.pop("payload-manifest.json"))
    if args.kind == "previous":
        version = "0.0.1"
        files["VERSION"] = b"0.0.1\n"
        text = files["python/synapse/__init__.py"].decode()
        files["python/synapse/__init__.py"] = re.sub(r'__version__\s*=\s*"[^"]+"', '__version__ = "0.0.1"', text).encode()
        files["synthetic-retired-file.txt"] = b"This tests removal of an obsolete code file. It is not a historical SYNAPSE release.\n"
        manifest["version"] = version
    else:
        version = manifest["version"]
        del files["python/synapse/_vendor/anthropic/__init__.py"]
    manifest["fixture"] = args.kind + ": synthetic test only, not a released SYNAPSE build"
    manifest["files"] = {name: digest(data) for name, data in sorted(files.items())}
    files["payload-manifest.json"] = json_bytes(manifest)
    zip_bytes(stage / "payload.zip", files)
    subprocess.run([str(args.iscc.resolve()), "--quiet", "/DStageDir=" + str(stage), "/DAppVersion=" + version,
                    "/DTestBuild=1", "--output-filename=SYNAPSE-fixture-" + args.kind,
                    str(Path(__file__).parent / "windows/Synapse.iss")], check=True)
    print(str(stage.parent / "output" / ("SYNAPSE-fixture-" + args.kind + ".exe")))
