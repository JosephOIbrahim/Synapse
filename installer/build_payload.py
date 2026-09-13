"""Create a deterministic allowlisted runtime. No dependency discovery/downloads."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import zipfile

from synapse_setup.registration import ui_assets
from synapse_setup.safety import SetupError, digest, json_bytes, member_path, no_links

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TREES = ("python/synapse/", "shared/", "houdini/", "rag/catalog/", "rag/corpus/",
                 "rag/skills/", "rag/documentation/", "docs/help/")
RUNTIME_FILES = {"VERSION", "LICENSE", "TONE.md", "pyproject.toml", "host/cache_host_probe.py",
                 "rulebook/manifest.json", "rulebook/phantoms.json", "rulebook/VERSION",
                 "retina/__init__.py", "retina/events.py", "retina/exr_header.py",
                 "retina/t0.py", "retina/t1.py", "retina/ingest.py", "retina/qc_profiles.py", "retina/qc_profiles.toml",
                 *(f"mcp_tools_{group}.py" for group in ("scene", "render", "usd", "tops", "memory", "cops"))}
WHEELS = {
    "filelock-3.20.0-py3-none-any.whl": "339b4732ffda5cd79b13f4e2711a31b0365ce445d95d243bb996273d072546a2",
    "websockets-15.0.1-cp313-cp313-win_amd64.whl": "e09473f095a819042ecb2ab9465aee615bd9c2028e4ef7d933600a8401c79561",
}


def zip_bytes(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            member_path(path.parent / "zip-check", name)
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def permitted(name):
    parts = Path(name).parts
    if any(p in {"__pycache__", "tests", ".synapse", ".git", ".pytest_cache"} for p in parts):
        return False
    if any(p.startswith(".env") for p in parts) or Path(name).suffix.lower() in {".pyc", ".pyo", ".key", ".log", ".hip", ".hiplc", ".hipnc"}:
        return False
    # No pip provenance paths or scripts from the build machine.
    if Path(name).name in {"direct_url.json", "INSTALLER", "REQUESTED"}:
        return False
    return (name in RUNTIME_FILES or name.startswith(RUNTIME_TREES)
            or (name.startswith("fixtures/") and name.endswith(".json")))


def export_moneta(source, output):
    source = no_links(source)
    meta = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if meta["name"] != "moneta":
        raise SetupError("The explicit dependency source is not Moneta.")
    files = {}
    for item in sorted((source / "src/moneta").rglob("*.py")):
        no_links(item)
        files[item.relative_to(source).as_posix()] = item.read_bytes()
    for name in ("plugInfo.json", "generatedSchema.usda", "MonetaSchema.usda"):
        item = no_links(source / "schema" / name)
        files["schema/" + name] = item.read_bytes()
    # The exporter creates real distribution metadata from the source project.
    files[f"src/moneta-{meta['version']}.dist-info/METADATA"] = (
        f"Metadata-Version: 2.1\nName: moneta\nVersion: {meta['version']}\nLicense: Proprietary\n").encode()
    provenance = {"name": "moneta", "version": meta["version"], "license": meta.get("license"),
                  "distribution": "Local evaluation only. Public redistribution rights have not been confirmed.",
                  "files": {name: digest(content) for name, content in files.items()}}
    files["moneta-bundle.json"] = json_bytes(provenance)
    files["LICENSE-NOTICE.txt"] = b"Moneta is proprietary. This local evaluation artifact does not grant redistribution rights.\n"
    zip_bytes(Path(output), files)
    return {"path": str(output), "sha256": digest(Path(output).read_bytes()), "version": meta["version"]}


def build(output, wheel_dir, moneta_bundle=None, moneta_sha256=None, source=ROOT):
    source, output = Path(source), Path(output)
    result = subprocess.run(["git", "-c", "safe.directory=" + source.as_posix(), "-C", str(source), "ls-files", "-z"], capture_output=True, check=True)
    names = result.stdout.decode().split("\0")
    files = {}
    for name in names:
        if name and permitted(name):
            path = no_links(source / name)
            files[name] = path.read_bytes()
    for path, target in ui_assets(source):
        files["houdini/" + target] = no_links(path).read_bytes()
    if not (source / "design/icons/svg/synapse_32.svg").is_file():
        raise SetupError("Required SYNAPSE icon source is missing.")
    for name, expected in WHEELS.items():
        path = Path(wheel_dir) / name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise SetupError(f"Missing or changed dependency wheel: {name}; see installer/toolchain.lock.json.")
        with zipfile.ZipFile(path) as wheel:
            for item in wheel.infolist():
                if not item.is_dir():
                    member_path(output.parent / "wheel-check", item.filename)
                    files["python/synapse/_vendor/" + item.filename] = wheel.read(item)
    moneta = None
    if moneta_bundle:
        data = Path(moneta_bundle).read_bytes()
        if not moneta_sha256 or digest(data) != moneta_sha256.lower():
            raise SetupError("Moneta archive must match the explicitly supplied SHA-256.")
        with zipfile.ZipFile(moneta_bundle) as bundle:
            if len(bundle.namelist()) != len(set(n.lower() for n in bundle.namelist())):
                raise SetupError("Duplicate files in Moneta archive.")
            moneta = json.loads(bundle.read("moneta-bundle.json"))
            for name, expected in moneta["files"].items():
                content = bundle.read(name)
                member_path(output.parent / "moneta-check", name)
                if digest(content) != expected:
                    raise SetupError(f"Moneta dependency checksum failed: {name}")
                files["dependencies/moneta/" + name] = content
            files["dependencies/moneta/moneta-bundle.json"] = bundle.read("moneta-bundle.json")
            files["dependencies/moneta/LICENSE-NOTICE.txt"] = bundle.read("LICENSE-NOTICE.txt")
        moneta = {"name": moneta["name"], "version": moneta["version"], "archive_sha256": moneta_sha256,
                  "distribution": moneta["distribution"]}
    version = files["VERSION"].decode().strip()
    project_version = tomllib.loads(files["pyproject.toml"].decode())["project"]["version"]
    module_version = re.search(r'__version__\s*=\s*"([^"]+)"', files["python/synapse/__init__.py"].decode()).group(1)
    if version != project_version or version != module_version:
        raise SetupError("SYNAPSE version surfaces disagree; use the repository version process before packaging.")
    notice = ("SYNAPSE " + version + "\n\nIncluded: Anthropic SDK and dependencies (see _vendor/*dist-info licenses), "
              "websockets 15.0.1, filelock 3.20.0, and bundled fonts (OFL licenses included).\n"
              "Houdini supplies Python, Qt and OpenUSD. Setup has its own CPython maintenance runtime.\n"
              "Optional components not installed: external MCP SDK/server environment, semantic models, "
              "Hanish, SALUS, Octavius, dense retrieval and optional image-analysis tools. "
              "Optional capabilities report unavailable when their substrate is absent.\n"
              + ("Moneta and USD schema included for local evaluation; proprietary redistribution rights unconfirmed.\n" if moneta else "Moneta not included; JSONL project memory is selected.\n"))
    files["DEPENDENCIES.txt"] = notice.encode()
    revision = subprocess.check_output(["git", "-c", "safe.directory=" + source.as_posix(), "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    manifest = {"schema": "synapse-payload-1", "version": version, "source_revision": revision,
                "tested_houdini": "22.0.400", "tested_python": "3.13", "moneta": moneta,
                "wheels": WHEELS, "files": {name: digest(content) for name, content in sorted(files.items())}}
    files["payload-manifest.json"] = json_bytes(manifest)
    zip_bytes(output, files)
    from synapse_setup.engine import load_manifest
    validated = load_manifest(output)
    return {"path": str(output), "version": version, "sha256": digest(output.read_bytes()), "files": len(manifest["files"]), "payload_id": validated["payload_id"], "moneta": moneta}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--wheel-dir", type=Path)
    parser.add_argument("--moneta-bundle", type=Path)
    parser.add_argument("--moneta-sha256")
    parser.add_argument("--export-moneta", type=Path)
    args = parser.parse_args()
    result = export_moneta(args.export_moneta, args.output) if args.export_moneta else build(args.output, args.wheel_dir, args.moneta_bundle, args.moneta_sha256)
    print(json.dumps(result, indent=2))
