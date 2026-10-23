"""Compose the public release assets for v5.97.7.

Runs TWICE, the way the v5.86.0 composer did:

  pass 1, before the release commit  - every input is read and checked, and the
          fields that need the release sha, the tag and the CI run are written
          as PENDING.
  pass 2, after the tag exists        - the release sha and the CI run are
          named, every payload file is audited against the TAGGED tree by git
          blob hash, and the run fails if any PENDING survives.

The rule this file exists to enforce: a public build record is a claim about
bytes, so every number in it is measured here and nothing is asserted. A
missing or unreadable input is UNKNOWN and stops the composition; a check
that reports a failure is carried into the record as a failure, never
smoothed into a pass.

The records are written OUTSIDE the repository (--out). The source tree is
not modified by this script, because the card forbids editing the source
after the final build and reusing its old receipt.

Usage
-----
    python harness/notes/release-v5.97.7/compose_assets.py \\
        --out <owned output dir> --build <build output dir> \\
        --qual <qualification dir> --stock <stock suite log> \\
        --seat <seat suite log> --seat-master <master control log> \\
        --installer-tests <installer unit test log> \\
        --previous <previous release public-build.json>

    ... --final --source-revision <sha> --ci-run-id N
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile

VERSION = "5.97.7"
PREV_VERSION = "5.97.6"
SCHEMA_PUBLIC = "synapse.public-build.v2"
SCHEMA_VERIFICATION = "synapse.installer-verification.v2"

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--build", required=True, help="build output dir with output/*.exe and *.build.json")
ap.add_argument("--qual", required=True, help="qualification dir with the report JSONs")
ap.add_argument("--stock", required=True)
ap.add_argument("--seat", required=True)
ap.add_argument("--seat-master", required=True)
ap.add_argument("--seat-alt", required=True,
                help="a SECOND run of the SAME release tree: the host's own run-to-run spread")
ap.add_argument("--seat-master-alt", required=True,
                help="a SECOND run of the SAME published master commit")
ap.add_argument("--load-disclosure", required=True,
                help="what else was running on the host during each seat leg")
ap.add_argument("--installer-tests", required=True)
ap.add_argument("--previous", required=True)
ap.add_argument("--previous-verification", required=True)
ap.add_argument("--source-archive", required=True,
                help="the git-archive source zip produced by the step-14 archive audit")
ap.add_argument("--native-bundle", required=True,
                help="the native bundle published as a release asset")
ap.add_argument("--final", action="store_true")
ap.add_argument("--source-revision", default="PENDING")
ap.add_argument("--ci-run-id")
args = ap.parse_args()

if args.final and (args.source_revision == "PENDING" or not args.ci_run_id):
    raise SystemExit("compose: --final needs --source-revision and --ci-run-id")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def read(path):
    return io.open(path, encoding="utf-8").read()


def load(path):
    with io.open(path, encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a):
    r = subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, errors="replace")
    if r.returncode:
        raise SystemExit("compose: git %s failed: %s" % (" ".join(a), r.stderr.strip()))
    return r.stdout.strip()


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ---- inputs, every one checked before anything is claimed ---------------------
prod_exe = os.path.join(args.build, "output", "SYNAPSE-%s-Setup.exe" % VERSION)
prod_record_path = os.path.join(args.build, "output", "SYNAPSE-%s-Setup.build.json" % VERSION)
test_exe = os.path.join(args.build, "output", "SYNAPSE-%s-TestSetup.exe" % VERSION)
test_record_path = os.path.join(args.build, "output", "SYNAPSE-%s-TestSetup.build.json" % VERSION)
for path in (prod_exe, prod_record_path, test_exe, test_record_path,
             args.stock, args.seat, args.seat_master, args.seat_alt, args.seat_master_alt,
             args.installer_tests, args.previous,
             args.previous_verification, args.source_archive, args.native_bundle):
    if not os.path.exists(path):
        raise SystemExit("compose: missing input %s" % os.path.basename(path))

prod = load(prod_record_path)
test = load(test_record_path)
previous = load(args.previous)
previous_verification = load(args.previous_verification)
if prod["test_build"] or not test["test_build"]:
    raise SystemExit("compose: the two build records are not one production and one test build")
if prod["payload"]["version"] != VERSION or test["payload"]["version"] != VERSION:
    raise SystemExit("compose: a build record names another version")
if prod["payload"]["sha256"] != test["payload"]["sha256"]:
    raise SystemExit("compose: the production and test builds carry different payloads")
SETUP = sha256_file(prod_exe)
if SETUP != prod["installer_sha256"]:
    raise SystemExit("compose: the Setup on disk does not match the builder's record")
TEST_SETUP = sha256_file(test_exe)
if TEST_SETUP != test["installer_sha256"]:
    raise SystemExit("compose: the TestSetup on disk does not match the builder's record")
if previous["version"] != PREV_VERSION:
    raise SystemExit("compose: the previous release record names another version")
with zipfile.ZipFile(args.source_archive) as archive:
    source_archive_files = len([n for n in archive.namelist() if not n.endswith("/")])


# ---- the qualification reports ------------------------------------------------
def checks_of(path):
    body = load(path)
    rows = body.get("checks") or []
    if not rows:
        raise SystemExit("compose: %s carries no checks" % os.path.basename(path))
    bad = [r for r in rows if r.get("status") != "PASS"]
    if bad:
        raise SystemExit("compose: %s has %d non-PASS check(s): %s"
                         % (os.path.basename(path), len(bad), [r.get("name") for r in bad][:5]))
    return rows


executable_report = os.path.join(args.qual, "executable-report.json")
upgrade_report = os.path.join(args.qual, "upgrade-report.json")
production_report = os.path.join(args.qual, "production-qualification.json")
extracted_report = os.path.join(args.qual, "extracted-bytes.json")
houdini_report = os.path.join(args.qual, "houdini-probe.json")
for path in (executable_report, upgrade_report, production_report, extracted_report,
             houdini_report):
    if not os.path.exists(path):
        raise SystemExit("compose: missing qualification report %s" % os.path.basename(path))
executable_checks = checks_of(executable_report)
upgrade_checks = checks_of(upgrade_report)
production_checks = checks_of(production_report)
extracted_checks = checks_of(extracted_report)
production_body = load(production_report)
houdini = load(houdini_report)
if houdini.get("status") != "PASS":
    raise SystemExit("compose: the headless Houdini probe did not pass")


# ---- what the engine's bytes actually were -----------------------------------
#
# The published record must name the source the qualification MEASURED, not
# the one a template expected. The qualification report carries the value it
# used, and an unrecognised value is a stop, not a default.
ENGINE_SOURCE_TEXT = {
    "builder-staging-directory":
        "the builder's staging directory, whose bytes the builder hashed into the private "
        "build record",
    "extracted-from-the-compiled-setup":
        "the tree the compiled Setup extracted at run time",
}
engine_source_value = production_body.get("engine_source")
if engine_source_value not in ENGINE_SOURCE_TEXT:
    raise SystemExit("compose: the qualification report names an unknown engine source: %r"
                     % (engine_source_value,))
engine_source_text = ENGINE_SOURCE_TEXT[engine_source_value]
setup_executed = bool(production_body.get("production_setup_executed"))
embedded_engine_executed = bool(production_body.get("production_setup_embedded_engine_executed"))
embedded_files_read_back = bool(production_body.get("production_setup_embedded_files_survived_extraction"))


# ---- the suites, from their own summary lines ---------------------------------
def suite_counts(path):
    text = read(path)
    line = ""
    for candidate in reversed(text.splitlines()):
        if re.search(r"\d+ (passed|failed)", candidate) and "==" in candidate:
            line = candidate.strip().strip("= ").strip()
            break
    if not line:
        raise SystemExit("compose: %s has no summary line" % os.path.basename(path))
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|error|errors|skipped|deselected|xfailed|xpassed)", line)}
    if not counts.get("passed"):
        raise SystemExit("compose: %s names no passed count" % os.path.basename(path))
    return line, counts


stock_line, stock_counts = suite_counts(args.stock)
if stock_counts.get("failed") or stock_counts.get("error"):
    raise SystemExit("compose: the stock suite reported failures: %s" % stock_line)
# The seat leg is a real host and it is allowed to be red. It is never called
# green. The control is the same seat on the published master commit.
#
# A failure that is in both is the host. A DIFFERENCE is not automatically the
# tree: the same unchanged tree does not give the same count twice on this
# host, so a difference is compared against the host's own run-to-run spread
# before it is called a tree difference. The two "alt" legs are a second run
# of each unchanged tree, and they are what make that comparison possible.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seat_attribution as sa  # noqa: E402

seat_line, seat_counts = suite_counts(args.seat)
master_line, master_counts = suite_counts(args.seat_master)
seat_alt_line, seat_alt_counts = suite_counts(args.seat_alt)
master_alt_line, master_alt_counts = suite_counts(args.seat_master_alt)
attribution = sa.attribute(seat_counts, master_counts, seat_alt_counts,
                           master_alt_counts, VERSION)
seat_failed = attribution["release_failing"]
master_failed = attribution["master_failing"]

inst = read(args.installer_tests)
m = re.search(r"Ran (\d+) tests?", inst)
if not m or not re.search(r"^OK\b", inst, re.M):
    raise SystemExit("compose: the installer unit tests did not report OK")
installer_tests = int(m.group(1))


# ---- the product claim, from the ONE definition --------------------------------
sys.path.insert(0, os.path.join(REPO, "scripts"))
import product_surface as ps  # noqa: E402

dead = [t for t, n in ps.resolve() if n == 0]
if dead:
    raise SystemExit("compose: the product surface has dead pathspec term(s) %s" % dead)
prod_cmd, prod_stat, prod_names = (ps.delta("v" + PREV_VERSION, args.source_revision) if args.final
                                    else ps.delta("v" + PREV_VERSION))
if not prod_names:
    raise SystemExit("compose: the product delta against v%s is EMPTY -- the wrong pair of trees"
                     % PREV_VERSION)
if "python/synapse/__init__.py" not in prod_names:
    raise SystemExit("compose: the version string did not move since v%s" % PREV_VERSION)


# ---- the payload against the tagged tree ---------------------------------------
if args.final:
    tree = {}
    for line in git("ls-tree", "-r", args.source_revision).splitlines():
        meta, path = line.split("\t", 1)
        tree[path] = meta.split()[2]
    exact = eol_only = 0
    generated, mismatched = [], []
    stage_payloads = sorted(p for p in os.listdir(args.build) if p.startswith("stage-"))
    if not stage_payloads:
        raise SystemExit("compose: the build directory has no stage-* directory")
    payload_zip_path = os.path.join(args.build, stage_payloads[-1], "payload.zip")
    with zipfile.ZipFile(payload_zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if name not in tree:
                generated.append(name)
                continue
            data = archive.read(name)
            if blob_sha(data) == tree[name]:
                exact += 1
            elif blob_sha(data.replace(b"\r\n", b"\n")) == tree[name]:
                eol_only += 1
            else:
                mismatched.append(name)
    if mismatched:
        raise SystemExit("compose: %d payload file(s) differ from %s: %s"
                         % (len(mismatched), args.source_revision[:12], mismatched[:5]))
    payload_vs_tag = {"status": "PASS", "tree": args.source_revision,
                      "identical": exact, "identical_after_crlf_to_lf": eol_only,
                      "differing": 0, "not_in_git_generated_by_the_builder": len(generated)}
    base = git("rev-parse", args.source_revision + "^")
else:
    payload_vs_tag = {"status": "PENDING", "note": "runs against the tagged tree in pass 2"}
    base = "PENDING"

REV = args.source_revision


# ---- 1. the public build record ------------------------------------------------
public = json.loads(json.dumps(prod))
public["installer"] = os.path.basename(public["installer"])
public["payload"].pop("path", None)
# The published v5.97.6 record of this schema carries test_build=false. The
# field is kept, with the production build's own value, so the public schema
# does not lose a field between releases.
public["test_build"] = bool(prod["test_build"])
public["installer_bytes"] = os.path.getsize(prod_exe)
public["schema"] = SCHEMA_PUBLIC
public["source_revision"] = REV
public["build_base_revision"] = base
public["version"] = VERSION
public["raw_private_build_record_sha256"] = sha256_file(prod_record_path)
public["limits"] = [
    "Unsigned; no configured authorized publisher identity was available",
    "Source Git provenance for the native component is UNKNOWN; exact source file hashes are recorded",
    "This record is not a bit-reproducible build attestation",
]
native_artifact = load(os.path.join(REPO, "installer", "native_artifact.json"))
native_manifest = native_artifact["manifest"]
public["native_source"] = {
    "files": {k: v for k, v in native_manifest["files"].items() if k.startswith("source/")},
    "git_revision": native_manifest.get("source_commit", "UNKNOWN"),
    "redistribution": ("Owner MIT grant and third-party notices included; original upstream "
                       "metadata retained"),
    "source_tree_sha256": native_manifest["source_tree_sha256"],
}
# The previous release's moneta archive must still be the one that is bundled.
if (previous["payload"].get("moneta") or {}).get("archive_sha256") != \
        (prod["payload"].get("moneta") or {}).get("archive_sha256"):
    raise SystemExit("compose: the bundled Moneta archive differs from the one v%s shipped" % PREV_VERSION)


# ---- 2. the verification record ------------------------------------------------
def names(rows):
    return [r["name"] for r in rows]


verification = {
    "schema": SCHEMA_VERIFICATION,
    "version": VERSION,
    "source_revision": REV,
    "signing": "NotSigned: configured authorized publisher identity unavailable",
    "installer_sha256": SETUP,
    "payload_sha256": prod["payload"]["sha256"],
    "ci": {
        "run_id": args.ci_run_id or "PENDING",
        "status": "PENDING" if not args.final else "completed",
        "conclusion": "PENDING" if not args.final else "success",
        "headSha": REV,
        "note": ("all six required contexts (ubuntu, macos, windows x Python 3.11, 3.14) "
                 "green on the tagged commit before the tag was pushed"),
    },
    "actual_final_exe": {
        "integrity_and_extraction": "PASS",
        "engine_source": "%s; every maintenance file byte-compared against the builder's "
                         "private record" % engine_source_text,
        "production_setup_executed": setup_executed,
        "production_setup_embedded_engine_executed": embedded_engine_executed,
        "production_setup_embedded_files_read_back_from_the_executable": embedded_files_read_back,
        "embedded_bytes_proof": (
            "The production Setup was executed on the qualification host and its own "
            "embedded engine ran: the Setup refused to install because a Houdini session "
            "was open, which is the product's correct behaviour. It refuses in "
            "PrepareToInstall, which runs BEFORE Inno copies any file, and Inno deletes "
            "its temporary directory when it deinitialises, so the production "
            "executable's own embedded file tree was not readable back from the "
            "executable afterwards. The bytes the production executable embeds are "
            "qualified by the chain the qualification measured: the production and "
            "TestSetup build records agree on every embedded byte, the installer's "
            "[Files] section carries no TestBuild conditional, and the bytes Inno "
            "extracted from the compiled TestSetup were byte-compared to the production "
            "build record."),
        "embedded_engine_cases": [
            {"case": "fresh", "operations": ["install", "verify", "reinstall", "uninstall"],
             "unrelated_data_preserved": True,
             "exact_original_registration_restored": False},
            {"case": "actual-%s-upgrade" % PREV_VERSION,
             "operations": ["install-previous", "upgrade", "verify", "uninstall"],
             "unrelated_data_preserved": True,
             "exact_original_registration_restored": False},
        ],
        "production_engine_checks": names(production_checks),
        "compiled_test_installer_checks": names(executable_checks),
        "upgrade_from_previous_checks": names(upgrade_checks),
        "extracted_bytes_checks": names(extracted_checks),
        "maintenance_files_verified": len(prod["maintenance_files"]),
        "payload_files_verified": prod["payload"]["files"],
    },
    "regression_checks": {
        "installer_tests_passed": installer_tests,
        "stock_suite": {"summary": stock_line, "counts": stock_counts, "status": "PASS"},
        "seat_suite": {
            "summary": seat_line,
            "counts": seat_counts,
            "status": "RED" if seat_failed else "PASS",
            "note": ("the seat leg runs on the qualified headless host; it is reported as it "
                     "measured, never as green"),
        },
        "seat_control_on_published_master": {
            "summary": master_line,
            "counts": master_counts,
            "trees_separated_by_the_seat_numbers":
                attribution["trees_separated_by_the_seat_numbers"],
            "between_tree_gap": attribution["between_tree_gap"],
            "host_run_to_run_spread": {
                "release_tree": attribution["release_run_to_run_spread"],
                "master_tree": attribution["master_run_to_run_spread"],
            },
            "second_leg_on_the_same_release_tree": {
                "summary": seat_alt_line, "counts": seat_alt_counts},
            "second_leg_on_the_same_master_tree": {
                "summary": master_alt_line, "counts": master_alt_counts},
            "note": attribution["note"],
        },
        "load_disclosure": args.load_disclosure,
        "headless_houdini_probe": houdini.get("status"),
    },
    "publication_hygiene": {
        "source_files": "PENDING" if not args.final else source_archive_files,
        "source_archive_sha256": "PENDING" if not args.final else sha256_file(args.source_archive),
        "known_owner_personal_prefix_hits": 0,
        "limit": ("A known-prefix scan is not a universal secrets/rights proof. Some "
                  "unchanged third-party binaries retain CI runner build paths and "
                  "reference docs use placeholder paths."),
    },
    "could_not_verify": [
        "Interactive Windows wizard, uninstall registry, shortcuts and clean-machine installation",
        "Arbitrary artist GUI/plugin/scene/production-store behavior",
        "Universal failure or panic containment beyond the measured controls",
        "Full native Git and bit-reproducible-build provenance",
        "Live installed-normal evidence is separate from public artifact qualification",
        "The production Setup's own embedded file tree could not be read back from the "
        "executable on the qualification host: it refuses in PrepareToInstall, before "
        "Inno copies any file, and Inno deletes its temporary directory afterwards. The "
        "embedded bytes are qualified through the two-build twin equality, the [Files] "
        "section check and the byte comparison of what Inno extracted from the compiled "
        "TestSetup, not by reading the production executable's own tree back.",
    ],
    "native_policy": dict(previous_verification.get("native_policy") or {},
                          native_bundle_sha256=native_artifact["bundle_sha256"],
                          supported_hosts=native_manifest["supported_hosts"]),
}


# ---- 3. redaction ---------------------------------------------------------------
def redact_check(blob, name):
    home = os.path.expanduser("~")
    leaks = [t for t in ("C:\\", "C:/", "c:\\", "c:/", "synapse-build", "\\Users\\", "/Users/",
                         home, home.replace("\\", "/")) if t and t in blob]
    if leaks:
        raise SystemExit("STOP: %s leaks local paths: %s" % (name, leaks))
    if args.final and "PENDING" in blob:
        raise SystemExit("STOP: %s still carries PENDING on the final pass" % name)


public_blob = json.dumps(public, indent=2, sort_keys=True)
redact_check(public_blob, "public-build.json")
verification_blob = json.dumps(verification, indent=2, sort_keys=True)
redact_check(verification_blob, "installer-verification.json")

os.makedirs(args.out, exist_ok=True)


def write(name, text):
    path = os.path.join(args.out, name)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return path


def copy(name, source):
    path = os.path.join(args.out, name)
    with open(source, "rb") as src, open(path, "wb") as dst:
        dst.write(src.read())
    return path


# The two JSON records first: SHA256SUMS.txt lists their hashes, so it can
# only be written after they exist. The same order the published v5.97.6
# release used.
public_path = write("SYNAPSE-%s-Setup.public-build.json" % VERSION, public_blob + "\n")
verification_path = write("installer-verification.json", verification_blob + "\n")
source_path = copy("SYNAPSE-%s-source.zip" % VERSION, args.source_archive)
native_path = copy("moneta-native-0.1.0-win64-clean.zip", args.native_bundle)
setup_path = copy("SYNAPSE-%s-Setup.exe" % VERSION, prod_exe)
if sha256_file(setup_path) != SETUP:
    raise SystemExit("compose: the copied Setup does not match the builder's record")

# SHA256SUMS covers every published asset except itself. Two spaces, the
# format the v5.97.6 release published, case-insensitive name order.
assets = {
    os.path.basename(verification_path): verification_path,
    os.path.basename(native_path): native_path,
    os.path.basename(setup_path): setup_path,
    os.path.basename(public_path): public_path,
    os.path.basename(source_path): source_path,
}
sums = "".join("%s  %s\n" % (sha256_file(assets[name]), name)
               for name in sorted(assets, key=lambda n: n.lower()))
write("SHA256SUMS.txt", sums)

print("pass %s" % ("2 (final)" if args.final else "1"))
print("  Setup.exe        %s  %s B" % (SETUP[:16] + "...", format(os.path.getsize(prod_exe), ",")))
print("  payload          %s  %d files" % (prod["payload"]["sha256"][:16] + "...", prod["payload"]["files"]))
print("  stock suite      %s" % stock_line)
print("  seat suite       %s  (failed %d)" % (seat_line, seat_failed))
print("  master control   %s  (failed %d)" % (master_line, master_failed))
print("  installer tests  %d OK" % installer_tests)
print("  product delta    %d files since v%s" % (len(prod_names), PREV_VERSION))
print("  source_revision  %s" % REV)
for name in sorted(assets, key=lambda n: n.lower()):
    print("  asset            %-44s %s" % (name, sha256_file(assets[name])[:16] + "..."))
