"""Compose the four v5.86.0 release assets.

Runs TWICE (the v5.70.1 lesson, kept from the v5.75.2 composer):
  pass 1, before the release commit -- checks every input and writes the assets with
          PENDING in the fields that need the release sha, the tag and the CI run.
  pass 2, after the tag exists     -- names the release sha and CI run, audits every
          payload file against the tagged tree, and raises if any PENDING survives.

What differs from the v5.75.2 composer, and why:

  * The product DID change. v5.75.2 raised on any product change beyond the version
    string; this cut lists the changed product files instead (scripts/product_surface.py,
    the one definition) and raises only on an EMPTY delta, which means the wrong pair of
    trees, not an unchanged product.
  * Two previous releases, two questions. The product delta is against v5.85.6, the last
    release. The installer comparison is against v5.75.2, the last Setup: its maintenance
    files are diffed from the two build reports, never assumed byte-identical.
  * The full suite DID run, so its figures are published from its own summary line
    (suite-summary.txt), with the command and platform that produced them.
  * Six required CI contexts (3 OS x 2 Python), not four.
  * The EXE was built from the working tree that became the release commit. Pass 2
    therefore audits every payload file against the TAGGED tree (git blob hashes), so
    "this Setup is that commit" is measured rather than asserted.

Usage:
  python harness/notes/release-5.86.0/compose_assets.py                        # pass 1
  python harness/notes/release-5.86.0/compose_assets.py --final \
      --source-revision <sha> --ci-run-id N                                   # pass 2
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

VERSION = "5.86.0"
PREV_PRODUCT = "v5.85.6"
PREV_SETUP = "5.75.2"
MONETA_SHA256 = "81a3d8735c7da49ca81302725acab6a3324311091e850c34afcea92e87ea31f7"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUTDIR = r"C:\synapse-build\output"
NOTES = os.path.join(REPO, "harness", "notes", "release-" + VERSION)
PREV_PUBLIC = os.path.join(REPO, "harness", "notes", "release-" + PREV_SETUP,
                           "SYNAPSE-%s-Setup.public-build.json" % PREV_SETUP)

ap = argparse.ArgumentParser()
ap.add_argument("--final", action="store_true")
ap.add_argument("--source-revision", default="PENDING")
ap.add_argument("--ci-run-id")
args = ap.parse_args()
if args.final and (args.source_revision == "PENDING" or not args.ci_run_id):
    raise SystemExit("compose: --final needs --source-revision and --ci-run-id")


def read(p):
    return io.open(p, encoding="utf-8").read()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a):
    r = subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, errors="replace")
    if r.returncode:
        raise SystemExit("compose: git %s failed: %s" % (" ".join(a), r.stderr.strip()))
    return r.stdout.strip()


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ---- build inputs, every one measured rather than asserted ----------------------
prod_report = os.path.join(OUTDIR, "SYNAPSE-%s-Setup.build.json" % VERSION)
test_report = os.path.join(OUTDIR, "SYNAPSE-%s-TestSetup.build.json" % VERSION)
setup_exe = os.path.join(OUTDIR, "SYNAPSE-%s-Setup.exe" % VERSION)
for p in (prod_report, test_report, setup_exe, PREV_PUBLIC):
    if not os.path.exists(p):
        raise SystemExit("compose: missing input %s" % os.path.basename(p))
prod = json.loads(read(prod_report))
test = json.loads(read(test_report))
prev_pub = json.loads(read(PREV_PUBLIC))

SETUP = sha256_file(setup_exe)
if SETUP != prod["installer_sha256"]:
    raise SystemExit("compose: Setup.exe on disk does not match the builder's report -- "
                     "disk %s vs report %s" % (SETUP[:16], prod["installer_sha256"][:16]))
SETUP_BYTES = os.path.getsize(setup_exe)
if prod["payload"]["version"] != VERSION or test["payload"]["version"] != VERSION:
    raise SystemExit("compose: a build report names another version")
if prod["payload"]["sha256"] != test["payload"]["sha256"]:
    raise SystemExit("compose: Setup and TestSetup carry different payloads")
moneta = prod["payload"].get("moneta") or {}
if moneta.get("archive_sha256") != MONETA_SHA256:
    raise SystemExit("compose: the Moneta archive is not the one v%s shipped (81a3...)" % PREV_SETUP)
if (prev_pub["payload"].get("moneta") or {}).get("archive_sha256") != MONETA_SHA256:
    raise SystemExit("compose: v%s's report does not name the same Moneta archive" % PREV_SETUP)

# ---- the qualification, parsed from its own raw log ----------------------------
qual_lines = [l for l in read(os.path.join(NOTES, "qual-raw.txt")).splitlines() if ": " in l]
qual_pass = [l for l in qual_lines if l.rstrip().endswith("PASS")]
qual_fail = [l for l in qual_lines if not l.rstrip().endswith("PASS")]
if not qual_lines:
    raise SystemExit("compose: qualification produced no check lines -- it did not run")
if qual_fail:
    raise SystemExit("compose: qualification has %d line(s) that are not PASS: %r"
                     % (len(qual_fail), qual_fail[:3]))

# ---- the suites, from their own summary lines ----------------------------------
suite_line = read(os.path.join(NOTES, "suite-summary.txt")).strip().strip("= ")
if re.search(r"\b\d+ (failed|error|errors)\b", suite_line):
    raise SystemExit("compose: the suite summary reports failures: %s" % suite_line)
suite = {k: int(v) for v, k in re.findall(r"(\d+) (passed|skipped|deselected|xfailed|xpassed)", suite_line)}
if not suite.get("passed"):
    raise SystemExit("compose: the suite summary names no passed count")
inst = read(os.path.join(NOTES, "installer-tests.txt"))
m = re.search(r"Ran (\d+) tests?", inst)
if not m or not re.search(r"^OK\b", inst, re.M):
    raise SystemExit("compose: the installer unit tests did not report OK")
installer_tests = int(m.group(1))

# ---- the product claim, from the ONE definition ---------------------------------
sys.path.insert(0, os.path.join(REPO, "scripts"))
import product_surface as ps  # noqa: E402

dead = [t for t, n in ps.resolve() if n == 0]
if dead:
    raise SystemExit("compose: product surface has dead pathspec term(s) %s" % dead)
prod_cmd, prod_stat, prod_names = (ps.delta(PREV_PRODUCT, args.source_revision) if args.final
                                   else ps.delta(PREV_PRODUCT))
if not prod_names:
    raise SystemExit("compose: product delta against %s is EMPTY -- the wrong pair of trees"
                     % PREV_PRODUCT)
if "python/synapse/__init__.py" not in prod_names:
    raise SystemExit("compose: the version string did not move since %s" % PREV_PRODUCT)

# ---- the installer against the last Setup ---------------------------------------
cur_m, prev_m = prod.get("maintenance_files", {}), prev_pub.get("maintenance_files", {})
m_diff = sorted(k for k in set(cur_m) | set(prev_m) if cur_m.get(k) != prev_m.get(k))

# ---- pass 2: every payload file against the tagged tree -------------------------
if args.final:
    tree = {}
    for line in git("ls-tree", "-r", args.source_revision).splitlines():
        meta, path = line.split("\t", 1)
        tree[path] = meta.split()[2]
    exact = eol_only = 0
    generated, mismatched = [], []
    with zipfile.ZipFile(prod["payload"]["path"]) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            if name not in tree:
                generated.append(name)
                continue
            data = z.read(name)
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
                      "differing": 0, "not_in_git_generated_by_the_builder": len(generated),
                      "generated_examples": sorted(generated)[:12]}
    base = git("rev-parse", args.source_revision + "^")
else:
    payload_vs_tag = {"status": "PENDING", "note": "runs against the tagged tree in pass 2"}
    base = "PENDING"

REV = args.source_revision

# ---- 1. SHA256SUMS.txt ----------------------------------------------------------
sums = "%s *SYNAPSE-%s-Setup.exe\n" % (SETUP, VERSION)

# ---- 2. public-build.json -------------------------------------------------------
pub = json.loads(json.dumps(prod))
pub["installer"] = os.path.basename(pub["installer"])
pub["payload"].pop("path", None)
pub.pop("test_build", None)
pub["installer_bytes"] = SETUP_BYTES
pub["qualification_report"] = "installer-verification.json"
pub["schema"] = "synapse-public-build-1"
pub["source_revision"] = REV
pub["build_base_revision"] = base
pub["build_note"] = ("Built from the working tree that became the release commit, on top of "
                     "build_base_revision. installer-verification.json audits every payload "
                     "file against the tagged tree.")
pub["version"] = VERSION

# ---- 3. installer-verification.json ---------------------------------------------
report = {
    "schema": "synapse-release-verification-1",
    "version": VERSION,
    "source_revision": REV,
    "build_base_revision": base,
    "status": "PASS",
    "ci": {"run_id": args.ci_run_id or "PENDING",
           "note": "all six required contexts (ubuntu, macos, windows x Python 3.11, 3.14) "
                   "green on the tagged commit before the tag was pushed"},
    "compiled_installer": {
        "status": "PASS",
        "checks_passed": len(qual_pass),
        "checks_total": len(qual_lines),
        "houdini": "22.0.400",
        "note": ("real install / repeat / upgrade / uninstall / reinstall cycle against an "
                 "installed Houdini, in a new isolated test root, with the compiled TestSetup. "
                 "HOUDINI_PACKAGE_DIR was sandboxed to an empty directory for the "
                 "qualification process only -- the dev machine registers the source tree "
                 "there, which Setup correctly refuses. The upgrade step used the synthetic "
                 "0.0.1 fixture, not v%s." % PREV_SETUP),
        "checks": [l.rsplit(":", 1)[0].strip() for l in qual_lines],
    },
    "installer_unit_tests": {"status": "PASS", "tests": installer_tests,
                             "command": "python -B -m unittest discover -s installer/tests"},
    "payload_audit": {
        "status": "PASS" if args.final else "PENDING",
        "payload_sha256": prod["payload"]["sha256"],
        "payload_id": prod["payload"]["payload_id"],
        "payload_files": prod["payload"]["files"],
        "moneta_archive_sha256": MONETA_SHA256,
        "moneta_note": "the same archive v%s shipped" % PREV_SETUP,
        "builds": [
            {"name": "SYNAPSE-%s-Setup.exe" % VERSION, "sha256": SETUP, "bytes": SETUP_BYTES},
            {"name": "SYNAPSE-%s-TestSetup.exe" % VERSION, "sha256": test["installer_sha256"]},
        ],
        "payload_vs_tagged_tree": payload_vs_tag,
    },
    ("installer_vs_v" + PREV_SETUP): {
        "maintenance_files_compared": len(set(cur_m) | set(prev_m)),
        "maintenance_files_differing": len(m_diff),
        "differing": m_diff,
        "note": "diffed from the two build reports' maintenance_files maps",
    },
    ("product_change_since_" + PREV_PRODUCT): {
        "check": prod_cmd,
        "definition": "scripts/product_surface.py (PRODUCT_PATHSPEC)",
        "files_changed": len(prod_names),
        "files": prod_names,
        "result": prod_stat,
    },
    "suites": {
        "status": "PASS",
        "summary": suite_line,
        "counts": suite,
        "command": 'python -m pytest -m "not needs_houdini" -q -p no:cacheprovider',
        "platform": "Windows, stock Python 3.14, tests that need a Houdini runtime deselected",
    },
    "known": [
        ("The upgrade check used a synthetic earlier installer, not v%s; an upgrade from "
         "v%s itself has not been run." % (PREV_SETUP, PREV_SETUP)),
        ("The Setup is unsigned. The qualification does not cover the wizard's look, a clean "
         "machine, a full artist session in the Houdini GUI or model access."),
        ("The final code was not opened in the Houdini GUI. The Identify overlay was checked "
         "live when it was built; the help-path and library changes were not. The 202 reply "
         "was proven on a private hwebserver under hython. Read-only mode has unit tests only."),
        ("CI runs stock Python on Linux, macOS and Windows. It has no Houdini leg and no "
         "scheduled run, so the qualification above is a human-triggered act."),
    ],
}


def redact_check(blob, name):
    home = os.path.expanduser("~")
    leaks = [t for t in ("C:\\", "C:/", "c:\\", "c:/", "synapse-build", "\\Users\\", "/Users/",
                         home, home.replace("\\", "/")) if t and t in blob]
    if leaks:
        raise SystemExit("STOP: %s leaks local paths: %s" % (name, leaks))
    if args.final and "PENDING" in blob:
        raise SystemExit("STOP: %s still carries PENDING on the final pass" % name)


pub_blob = json.dumps(pub, indent=2, sort_keys=True)
redact_check(pub_blob, "public-build.json")
rep_blob = json.dumps(report, indent=2, sort_keys=True)
redact_check(rep_blob, "installer-verification.json")

io.open(os.path.join(NOTES, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n").write(sums)
io.open(os.path.join(NOTES, "SYNAPSE-%s-Setup.public-build.json" % VERSION), "w",
        encoding="utf-8", newline="\n").write(pub_blob + "\n")
io.open(os.path.join(NOTES, "installer-verification.json"), "w",
        encoding="utf-8", newline="\n").write(rep_blob + "\n")

print("pass %s" % ("2 (final)" if args.final else "1"))
print("  Setup.exe       %s  %s B" % (SETUP[:16] + "...", format(SETUP_BYTES, ",")))
print("  payload         %s  %d files" % (prod["payload"]["sha256"][:16] + "...", prod["payload"]["files"]))
print("  qualification   %d/%d PASS, Houdini 22.0.400" % (len(qual_pass), len(qual_lines)))
print("  installer tests %d OK" % installer_tests)
print("  suite           %s" % suite_line)
print("  vs v%s        %d of %d maintenance files differ" % (PREV_SETUP, len(m_diff), len(set(cur_m) | set(prev_m))))
print("  product delta   %d files since %s" % (len(prod_names), PREV_PRODUCT))
print("  payload vs tag  %s" % json.dumps(payload_vs_tag)[:160])
print("  source_revision %s" % REV)
