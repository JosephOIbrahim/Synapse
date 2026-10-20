"""Shared source-bound Moneta grant validation for exporter and installed helper.

The published installer checksum authenticates distribution. These checks prevent
an internally rehashed dependency from silently escaping the reviewed grant.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import tomllib
from .safety import SetupError, digest, member_path

def license_policy(root=None):
    """The one grant policy, copied byte-for-byte beside the installed helper."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    if not (root / "moneta_license.json").is_file():
        # Source checkout layout; an installed helper has its policy beside it.
        root = root.parent
    policy = json.loads((root / "moneta_license.json").read_text(encoding="utf-8"))
    policy["license_text"] = member_path(root, policy["license_text_file"]).read_text(encoding="utf-8")
    return policy


def source_identity(hashes):
    return digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def declared_license(meta):
    value = meta.get("license")
    if isinstance(value, dict):
        value = value.get("text")
    if not isinstance(value, str) or not value.strip():
        raise SetupError("Moneta's source license metadata is unavailable; review it before exporting.")
    return value.strip()


def moneta_notice(policy, source_license):
    return (f"Moneta {policy['version']}\n\n"
            f"Bundled under the {policy['license']} License by its copyright holder's written grant "
            f"of {policy['grant_date']}, as part of SYNAPSE.\n"
            f"Covered source commit: {policy['source_commit']}\n"
            f"Covered source content SHA-256: {policy['source_identity_sha256']}\n"
            f"Upstream pyproject.toml declares: {source_license}. That declaration is retained in "
            "the archived source metadata and generated distribution metadata; this notice records the bundle grant.\n\n"
            + policy["license_text"])


def validate_moneta_grant(bundle, moneta, policy):
    """Return the notice and authenticated copy inventory, never an archive list."""
    fields = {"name", "version", "license", "source_license", "source_revision", "source_files",
              "source_identity_sha256", "distribution", "grant_date", "files"}
    if type(moneta) is not dict or set(moneta) != fields:
        raise SetupError("Moneta provenance inventory has unexpected or missing fields.")
    hashes = moneta.get("source_files", {})
    if (moneta.get("name") != "moneta" or moneta.get("version") != policy["version"] or moneta.get("license") != policy["license"]
            or moneta.get("source_revision") != policy["source_commit"]
            or moneta.get("source_identity_sha256") != policy["source_identity_sha256"]
            or moneta.get("grant_date") != policy["grant_date"] or moneta.get("distribution") != policy["grant_scope"]
            or source_identity(hashes) != policy["source_identity_sha256"]):
        raise SetupError("Moneta bundle is not covered by the reviewed source-bound MIT grant.")
    source_files = {"upstream/pyproject.toml" if name == "pyproject.toml" else name: expected
                    for name, expected in hashes.items()}
    metadata_name = f"src/moneta-{policy['version']}.dist-info/METADATA"
    expected_members = set(source_files) | {metadata_name, "moneta-bundle.json", "LICENSE-NOTICE.txt"}
    names = bundle.namelist()
    if (len(source_files) != len(hashes) or len(names) != len(set(n.lower() for n in names))
            or set(names) != expected_members):
        raise SetupError("Moneta archive inventory differs from the authenticated source and generated files.")
    for name in names:
        member_path(Path.cwd() / "moneta-input-check", name)
    for original, expected in hashes.items():
        name = "upstream/pyproject.toml" if original == "pyproject.toml" else original
        if digest(bundle.read(name)) != expected:
            raise SetupError("Moneta source identity mismatch: " + original)
    meta = tomllib.loads(bundle.read("upstream/pyproject.toml").decode("utf-8"))["project"]
    if meta.get("name") != "moneta" or meta["version"] != policy["version"] or declared_license(meta) != moneta.get("source_license"):
        raise SetupError("Moneta source metadata disagrees with its bundle record.")
    metadata = (f"Metadata-Version: 2.1\nName: moneta\nVersion: {meta['version']}\nLicense: {declared_license(meta)}\n").encode()
    if bundle.read(metadata_name) != metadata:
        raise SetupError("Moneta distribution metadata does not preserve the source declaration.")
    copied_files = {**source_files, metadata_name: digest(metadata)}
    if type(moneta["files"]) is not dict or moneta["files"] != copied_files:
        raise SetupError("Moneta copy inventory differs from the authenticated source and generated metadata.")
    notice = moneta_notice(policy, declared_license(meta))
    if bundle.read("LICENSE-NOTICE.txt") != notice.encode("utf-8"):
        raise SetupError("Moneta bundle notice differs from the reviewed grant and MIT text.")
    return notice, copied_files



def validate_payload(bundle, manifest, policy=None):
    """Recheck actual dependency bytes, independent of ordinary payload hashes."""
    prefix = "dependencies/moneta/"
    names = [name for name in bundle.namelist() if name.lower().startswith(prefix)]
    # Windows aliases differently cased directory components even when the full
    # filenames are distinct. Include the entire namespace before validating it.
    if any(not name.startswith(prefix) for name in names):
        raise SetupError("Moneta dependency paths must use canonical directory casing.")
    summary = manifest.get("moneta")
    if not summary:
        if names:
            raise SetupError("Moneta files exist without their manifest summary.")
        return
    if not names:
        raise SetupError("Moneta summary exists without its dependency files.")

    class DependencyView:
        def namelist(self):
            return [name[len(prefix):] for name in names]

        def read(self, name):
            return bundle.read(prefix + name)

    view = DependencyView()
    record = json.loads(view.read("moneta-bundle.json"))
    notice, _ = validate_moneta_grant(view, record, policy if policy is not None else license_policy())
    if type(summary) is not dict or not re.fullmatch(r"[0-9a-f]{64}", summary.get("archive_sha256", "")):
        raise SetupError("Moneta archive identity is missing or invalid.")
    expected = {"name": record["name"], "version": record["version"], "archive_sha256": summary["archive_sha256"],
                "distribution": record["distribution"], "license": record["license"],
                "source_license": record["source_license"], "source_revision": record["source_revision"],
                "grant_date": record["grant_date"], "license_notice": notice}
    if summary != expected:
        raise SetupError("Moneta payload summary differs from the validated grant and notice.")
