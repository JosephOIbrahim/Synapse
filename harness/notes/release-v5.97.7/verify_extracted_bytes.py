"""Verify the bytes Inno Setup actually extracted, against the build record.

What this is for
----------------
The production Setup refuses to install while a Houdini session is open, and
it refuses in PrepareToInstall, which runs BEFORE Inno copies a single file.
Its embedded tree is therefore never extracted on a host with Houdini open,
and Inno deletes its temporary directory when it deinitialises, so the
production executable's own embedded bytes cannot be read back directly.

The compiled TestSetup can be installed on the same host, and when Inno
installs it, the bytes Inno extracts land in ``app\\maintenance``. This
script compares those extracted bytes - the ones that came out of a compiled
executable, not out of the builder's staging directory - against the builder's
private record for the PRODUCTION build, and closes the chain with the two
build records and the installer's own [Files] section.

Usage
-----
    python harness/notes/release-v5.97.7/verify_extracted_bytes.py \\
        --app <installed application folder> \\
        --record <SYNAPSE-X.Y.Z-Setup.build.json> \\
        --test-record <SYNAPSE-X.Y.Z-TestSetup.build.json> \\
        --iss <installer/windows/Synapse.iss> \\
        --out <report path>

Everything it writes goes under --out, which must be a disposable folder
outside the repository. It modifies nothing it reads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qualify_production import (Report, compare_maintenance, digest_tree,
                                iss_files_section_mentions_testbuild)

# The isolated TestSetup writes this one extra file into app\maintenance, and
# it is not one of the bytes the builder embedded, so it is excluded from the
# comparison. It is the ONLY file the TestBuild conditional adds.
TESTBUILD_ONLY_FILES = ("test-root.ini",)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, required=True,
                    help="the installed application folder")
    ap.add_argument("--record", type=Path, required=True,
                    help="the PRODUCTION build record")
    ap.add_argument("--test-record", type=Path, required=True,
                    help="the TestSetup build record")
    ap.add_argument("--iss", type=Path, required=True,
                    help="the installer's .iss, for the [Files] section check")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    test_record = json.loads(args.test_record.read_text(encoding="utf-8"))
    expected = record["maintenance_files"]

    report = Report()

    # ------------------------------------------- 1. the bytes Inno extracted
    installed = args.app / "maintenance"
    if not installed.is_dir():
        report.add("the_installed_maintenance_folder_exists", "FAIL",
                   "there is no maintenance folder at %s" % installed)
        report.write(args.out, {"verdict": "FAIL"})
        return 1
    report.add("the_installed_maintenance_folder_exists", "PASS",
               "the installer populated %s" % installed.name)

    actual = digest_tree(installed)
    extras = [name for name in TESTBUILD_ONLY_FILES if name in actual]
    for name in extras:
        actual.pop(name, None)
    manifest = actual.pop("maintenance-manifest.json", None)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    differing = sorted(k for k in set(expected) & set(actual)
                       if expected[k] != actual[k])
    if missing or extra or differing:
        report.add("bytes_inno_extracted_match_the_production_build_record", "FAIL",
                   "missing=%s extra=%s differing=%s"
                   % (missing[:6], extra[:6], differing[:6]))
    else:
        report.add("bytes_inno_extracted_match_the_production_build_record", "PASS",
                   "all %d maintenance files Inno extracted from the compiled executable are "
                   "byte-identical to the production build record%s"
                   % (len(actual),
                      (", ignoring the TestSetup-only file %s" % ", ".join(extras))
                      if extras else ""))

    # ------------------------------------ 2. the extracted manifest's own map
    if manifest is None:
        report.add("the_extracted_manifest_agrees_with_the_build_record", "FAIL",
                   "the installed maintenance folder carries no manifest")
    else:
        try:
            body = json.loads((installed / "maintenance-manifest.json").read_text(
                encoding="utf-8"))
        except (ValueError, OSError) as exc:
            body = None
            report.add("the_extracted_manifest_agrees_with_the_build_record", "FAIL",
                       "the installed manifest does not parse: %s" % exc)
        if body is not None:
            if body.get("schema") != "synapse-maintenance-1":
                report.add("the_extracted_manifest_agrees_with_the_build_record", "FAIL",
                           "the installed manifest declares schema %r" % body.get("schema"))
            elif body.get("files") != expected:
                report.add("the_extracted_manifest_agrees_with_the_build_record", "FAIL",
                           "the installed manifest's own file map differs from the "
                           "production build record")
            else:
                report.add("the_extracted_manifest_agrees_with_the_build_record", "PASS",
                           "the manifest Inno installed declares schema "
                           "synapse-maintenance-1 and its own %d-entry file map is equal to "
                           "the production build record" % len(expected))

    # ------------------------------- 3. the two builds embed the same bytes
    differences = []
    if test_record.get("maintenance_files") != expected:
        differences.append("maintenance_files")
    for key in ("sha256", "files", "version", "payload_id"):
        if test_record.get("payload", {}).get(key) != record.get("payload", {}).get(key):
            differences.append("payload.%s" % key)
    if test_record.get("toolchain") != record.get("toolchain"):
        differences.append("toolchain")
    conditional = iss_files_section_mentions_testbuild(args.iss)
    if differences:
        report.add("the_two_builds_embed_the_same_bytes", "FAIL",
                   "the production and TestSetup build records differ: %s" % differences[:6])
    elif conditional is not False:
        report.add("the_two_builds_embed_the_same_bytes", "UNKNOWN",
                   "the installer's [Files] section could not be shown to be free of a "
                   "TestBuild conditional")
    else:
        report.add("the_two_builds_embed_the_same_bytes", "PASS",
                   "the two build records agree on every embedded byte and the installer's "
                   "[Files] section carries no TestBuild conditional, so the bytes proven "
                   "above are the bytes the production executable embeds")

    # ------------------------------------------------------- 4. the payload
    if test_record.get("payload", {}).get("sha256") == record.get("payload", {}).get("sha256"):
        report.add("both_builds_embed_the_same_payload_archive", "PASS",
                   "the production and TestSetup executables embed a payload archive with "
                   "the same SHA-256, carrying %s files"
                   % record.get("payload", {}).get("files"))
    else:
        report.add("both_builds_embed_the_same_payload_archive", "FAIL",
                   "the two builds embed different payload archives")

    body = report.write(args.out, {
        "production_record_sha256_note": "the record's own hashes were compared, not the file",
        "maintenance_files_compared": len(expected),
    })
    passed = sum(1 for c in body["checks"] if c["status"] == "PASS")
    print("extracted bytes: %d/%d PASS" % (passed, len(body["checks"])))
    for check in body["checks"]:
        print("  %-56s %s" % (check["name"], check["status"]))
    unknown = [c for c in body["checks"] if c["status"] == "UNKNOWN"]
    return 0 if not unknown and passed == len(body["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
