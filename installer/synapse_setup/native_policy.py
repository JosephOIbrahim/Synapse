"""Pinned optional native artifact and explicit per-registration choices."""
import json
import os
from pathlib import Path
import zipfile

from . import registration
from .safety import SetupError, digest, file_hash, json_bytes, member_path, no_links

PREFIX = "dependencies/moneta-native/"
MANIFEST = "native-bundle.json"
OFF = {"0", "false", "off", "no"}


def policy():
    root = Path(__file__).resolve().parent
    if not (root / "native_artifact.json").is_file():
        root = root.parent
    data = json.loads((root / "native_artifact.json").read_text(encoding="utf-8"))
    if data.get("schema") != "synapse-native-policy-1" or data.get("execution_required") is not True:
        raise SetupError("Native artifact policy is invalid; no native setting was activated.")
    return data


def metadata(p):
    m = p["manifest"]
    return {"name": m["name"], "version": m["version"], "bundle_sha256": p["bundle_sha256"],
            "pyd_sha256": m["pyd_sha256"], "source_tree_sha256": m["source_tree_sha256"],
            "license": m["license"], "source_license": m["source_license"], "grant_date": m["grant_date"]}


def bundle_files(archive, expected):
    p = policy()
    if expected != p["bundle_sha256"] or digest(Path(archive).read_bytes()) != expected:
        raise SetupError("Native artifact must match both the supplied SHA-256 and independently reviewed policy.")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(n.casefold() for n in names)):
            raise SetupError("Native artifact contains duplicate Windows paths.")
        required = set(p["manifest"]["files"]) | {MANIFEST}
        if set(names) != required or sum(i.file_size for i in z.infolist()) > 20 * 1024 * 1024:
            raise SetupError("Native artifact inventory/size differs from reviewed policy.")
        files = {}
        for name in names:
            member_path(Path.cwd() / "native-validation", name)
            content = z.read(name)
            want = p["manifest_sha256"] if name == MANIFEST else p["manifest"]["files"][name]
            if digest(content) != want:
                raise SetupError("Native artifact checksum differs from reviewed policy: " + name)
            files[name] = content
        if json.loads(files[MANIFEST]) != p["manifest"]:
            raise SetupError("Native artifact manifest differs from reviewed policy.")
    return files, metadata(p)


def compatible_moneta(manifest, p):
    m = manifest.get("moneta") or {}
    return m.get("version") == p["manifest"]["moneta_version"] and m.get("source_revision") == p["manifest"]["moneta_commit"]


def validate_payload(archive, manifest):
    names = {n for n in manifest["files"] if n.startswith(PREFIX)}
    rogue = [n for n in manifest["files"] if "moneta_native" in n.casefold() and n.casefold().endswith(".pyd") and not n.startswith(PREFIX)]
    if rogue or (names and not manifest.get("native")):
        raise SetupError("Native files are not declared by the reviewed native artifact policy.")
    if not manifest.get("native"):
        return
    p = policy()
    if manifest["native"] != metadata(p) or not compatible_moneta(manifest, p):
        raise SetupError("Native artifact metadata or compatible Moneta identity differs from reviewed policy.")
    expected = {PREFIX + n: h for n, h in p["manifest"]["files"].items()}
    expected[PREFIX + MANIFEST] = p["manifest_sha256"]
    if names != set(expected) or any(manifest["files"][n] != h for n, h in expected.items()):
        raise SetupError("Native payload inventory differs from the independently pinned artifact.")
    if digest(archive.read(PREFIX + MANIFEST)) != p["manifest_sha256"]:
        raise SetupError("Native payload manifest is not the reviewed artifact.")


def supported(target, p):
    return any(all(target.get(key) == want for key, want in row.items())
               for row in p["manifest"]["supported_hosts"])


def _external(previous, p):
    row = next((r for r in registration.environment_entries(previous) if r["var"] == "PYTHONPATH"), None)
    for name in registration._paths(row) if row else []:
        site = Path(name)
        if not site.is_absolute():
            continue
        for approved in p["external_artifacts"]:
            if all(file_hash(no_links(site / n)) == h for n, h in approved["files"].items()):
                return site, approved["files"]
    return None, None


def resolve(manifest, target, runtime, previous=None, environ=None):
    env = os.environ if environ is None else environ
    value = registration.native_choice(previous)
    source = "existing_package" if value is not None else "inherited_environment"
    inherited = env.get("MONETA_NATIVE")
    if value is None:
        value = inherited
    if value is not None and (not isinstance(value, str) or value.strip().lower() not in OFF | {"", "1", "true", "on", "yes", "auto", "require"}):
        raise SetupError("MONETA_NATIVE needs a literal OFF/AUTO/REQUIRE choice; no configuration was changed.")
    if value is not None and value.strip().lower() in OFF:
        return {"status": "OFF", "value": value, "source": source, "reason": "Explicit OFF choice preserved."}
    if value is not None and inherited is not None and inherited.strip().lower() in OFF:
        raise SetupError("MONETA_NATIVE choices conflict with an inherited OFF switch; no configuration was changed.")
    if value is None and previous:
        return {"status": "OFF", "value": "0", "source": "legacy_default", "reason": "An existing default-off registration is not automatically opted in."}
    if not manifest.get("native") and value is None:
        return {"status": "UNAVAILABLE", "value": "0", "source": "fresh_default", "reason": "No verified native artifact is bundled; Python memory remains available."}
    p = policy()
    if not compatible_moneta(manifest, p):
        raise SetupError("Native artifact qualification requires the pinned compatible Moneta Python backend.")
    if not supported(target, p):
        if value is None:
            return {"status": "UNAVAILABLE", "value": "0", "source": "fresh_default", "reason": "Native artifact is not qualified for this exact Houdini/Python/platform; native stays OFF."}
        raise SetupError("Native artifact qualification is unavailable for the selected Houdini/Python/platform; existing configuration is preserved.")
    backend = next((r for r in registration.environment_entries(previous) if r["var"] == "SYNAPSE_MEMORY_BACKEND"), None)
    if backend and backend.get("value") != "moneta":
        raise SetupError("Native qualification requires SYNAPSE's primary Moneta backend; no configuration was changed.")
    if manifest.get("native"):
        site = runtime / "dependencies/moneta-native"
        files = {n: h for n, h in p["manifest"]["files"].items() if n in {
            "moneta_native/__init__.py", "moneta_native/moneta_native.pyd",
            "moneta_native-0.1.0.dist-info/METADATA", "moneta_native-0.1.0.dist-info/WHEEL"}}
        kind = "bundled"
    else:
        site, files = _external(previous, p)
        kind = "existing_verified_artifact"
    if site is None:
        raise SetupError("Native artifact qualification cannot find an approved existing wheel; original registration is unchanged.")
    return {"status": "PENDING_EXECUTION", "value": "1" if value is None else value,
            "source": "fresh_verified_artifact" if value is None else source, "kind": kind,
            "site": str(site), "files": files, "pyd_sha256": files["moneta_native/moneta_native.pyd"],
            "reason": "Pinned artifact and exact host match; actual primary-backend scan/decay checks are still required."}


def recheck(choice):
    if choice.get("site") and any(file_hash(no_links(Path(choice["site"]) / n)) != h for n, h in choice["files"].items()):
        raise SetupError("Native artifact changed during qualification; activation refused and existing registration preserved.")


def report(choice):
    return {k: v for k, v in choice.items() if k not in {"site", "files"}}
