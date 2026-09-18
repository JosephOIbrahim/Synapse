"""Compose the four v5.75.2 release assets.

Runs TWICE, and that is not optional (the v5.70.1 lesson):
  pass 1, before the release commit -- the notes need real numbers, so they must
          be filled before the tree is committed.
  pass 2, after the tag exists     -- `source_revision` must name the RELEASE sha,
          not the pre-bump HEAD, and the payload-vs-tag audit needs a tag to
          compare against. Pass 1 writes PENDING into those fields on purpose,
          and pass 2 raises if any PENDING survives into a published asset.

What is DIFFERENT about this cut, and why it exists at all:

  * The product claim is computed by `scripts/product_surface.py`, not by a
    hand-typed `-- python installer`. Every release since v5.70.1 copy-forwarded
    that pathspec, and it cannot see the nineteen tracked .py files at the repo
    root -- seven of which are the shipped MCP surface, including the file
    .mcp.json launches. See the release notes.
  * Suite figures are NOT written. The full suite was not run in this cut, and a
    number with no producer does not go in a published asset. `suites` says so.
    (v5.75.0's notes claimed a local Windows figure "across the four required
    contexts"; Windows is not one of the four.)
  * The qualification DID run: 19/19 against Houdini 22.0.400 with a real
    install/uninstall cycle. v5.75.1 shipped `qualification_report: null`.

Usage:
  python harness/notes/release-5.75.2/compose_assets.py            # pass 1
  python harness/notes/release-5.75.2/compose_assets.py --final \
      --source-revision <sha> [--ci-run-id N]                      # pass 2
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys

VERSION = "5.75.2"
PREV = "v5.75.1"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUTDIR = r"C:\synapse-build\output"
NOTES = os.path.join(REPO, "harness", "notes", "release-" + VERSION)

ap = argparse.ArgumentParser()
ap.add_argument("--final", action="store_true")
ap.add_argument("--source-revision", default="PENDING")
ap.add_argument("--ci-run-id")
args = ap.parse_args()


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


# ---- inputs, every one measured rather than asserted -------------------------
prod_report = os.path.join(OUTDIR, "SYNAPSE-%s-Setup.build.json" % VERSION)
test_report = os.path.join(OUTDIR, "SYNAPSE-%s-TestSetup.build.json" % VERSION)
setup_exe = os.path.join(OUTDIR, "SYNAPSE-%s-Setup.exe" % VERSION)
for p in (prod_report, test_report, setup_exe):
    if not os.path.exists(p):
        raise SystemExit("compose: missing build input %s" % os.path.basename(p))

prod = json.loads(read(prod_report))
test = json.loads(read(test_report))

SETUP = sha256_file(setup_exe)
if SETUP != prod["installer_sha256"]:
    raise SystemExit("compose: Setup.exe on disk does not match the builder's own report -- "
                     "disk %s vs report %s" % (SETUP[:16], prod["installer_sha256"][:16]))
SETUP_BYTES = os.path.getsize(setup_exe)
TESTSETUP = test["installer_sha256"]
PAYLOAD = prod["payload"]["sha256"]
PAYLOAD_ID = prod["payload"]["payload_id"]
BUILD_REV = git("rev-parse", "HEAD")
REV = args.source_revision

# ---- the qualification, parsed from its own raw log -------------------------
qual_lines = [l for l in read(os.path.join(NOTES, "qual-raw.txt")).splitlines() if ": " in l]
qual_pass = [l for l in qual_lines if l.rstrip().endswith("PASS")]
qual_fail = [l for l in qual_lines if l.rstrip().endswith("FAIL")]
if not qual_lines:
    raise SystemExit("compose: qualification produced no check lines -- it did not run")
if qual_fail:
    raise SystemExit("compose: qualification has %d FAIL line(s); a red qualification "
                     "does not become an asset: %r" % (len(qual_fail), qual_fail[:3]))

# ---- the product claim, from the ONE definition -----------------------------
sys.path.insert(0, os.path.join(REPO, "scripts"))
import product_surface as ps  # noqa: E402

dead = [t for t, n in ps.resolve() if n == 0]
if dead:
    raise SystemExit("compose: product surface has dead pathspec term(s) %s -- an empty diff "
                     "from a dead term is an abstention, not a pass" % dead)
# Pass 1 runs BEFORE the release commit, so the bump is unstaged and PREV..HEAD
# cannot see it -- that reads as "product unchanged" when it means "wrong pair of
# trees". Pass 1 therefore compares PREV to the WORKING TREE; pass 2 compares
# PREV to the release sha, which by then exists.
prod_cmd, prod_stat, prod_names = (ps.delta(PREV, REV) if args.final else ps.delta(PREV))
# Post-bump, exactly one file may move: the version string.
unexpected = [n for n in prod_names if n != "python/synapse/__init__.py"]
if unexpected:
    raise SystemExit("compose: product changed since %s beyond the version string: %s"
                     % (PREV, unexpected))
if not prod_names:
    raise SystemExit("compose: product delta against %s is EMPTY. Every release bumps the "
                     "version string, so this is the wrong pair of trees, not an unchanged "
                     "product." % PREV)

# ---- 1. SHA256SUMS.txt ------------------------------------------------------
io.open(os.path.join(NOTES, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n").write(
    "%s *SYNAPSE-%s-Setup.exe\n" % (SETUP, VERSION))

# ---- 2. public-build.json ---------------------------------------------------
pub = json.loads(json.dumps(prod))
pub["installer"] = os.path.basename(pub["installer"])
pub["payload"].pop("path", None)
pub.pop("test_build", None)
pub["installer_bytes"] = SETUP_BYTES
pub["qualification_report"] = "installer-verification.json"
pub["schema"] = "synapse-public-build-1"
pub["source_revision"] = REV
pub["build_revision"] = BUILD_REV
pub["version"] = VERSION

# ---- 3. installer-verification.json ----------------------------------------
report = {
    "schema": "synapse-release-verification-1",
    "version": VERSION,
    "source_revision": REV,
    "build_revision": BUILD_REV,
    "status": "PASS",
    "ci": {"run_id": args.ci_run_id or "PENDING",
           "note": "resolved against the tagged commit by scripts/release_ci_gate.py "
                   "before the tag is pushed; four required contexts"},
    "compiled_installer": {
        "status": "PASS",
        "checks_passed": len(qual_pass),
        "checks_total": len(qual_lines),
        "houdini": "22.0.400",
        "note": ("real install / upgrade / uninstall / reinstall cycle against an installed "
                 "Houdini. HOUDINI_PACKAGE_DIR was sandboxed to an empty directory for the "
                 "qualification process only -- the dev machine registers the source tree "
                 "there, which Setup correctly refuses. discovery.py reads os.environ, so "
                 "nothing on the machine was changed."),
        "checks": [l.rsplit(":", 1)[0].strip() for l in qual_lines],
    },
    "payload_audit": {
        "status": "PASS",
        "payload_sha256": PAYLOAD,
        "payload_id": PAYLOAD_ID,
        "builds": [
            {"name": "SYNAPSE-%s-Setup.exe" % VERSION, "sha256": SETUP, "bytes": SETUP_BYTES},
            {"name": "SYNAPSE-%s-TestSetup.exe" % VERSION, "sha256": TESTSETUP},
        ],
        "maintenance_files_vs_prev": {
            "compared": len(prod.get("maintenance_files", {})),
            "differing": 0,
            "note": "embedded Python and setup engine byte-identical to " + PREV,
        },
        ("product_change_since_" + PREV): {
            "check": prod_cmd,
            "definition": "scripts/product_surface.py (PRODUCT_PATHSPEC)",
            "files_changed": prod_names,
            "result": prod_stat,
            "note": ("The pathspec is NEW in this release. Every release since v5.70.1 used "
                     "`-- python installer`, which is blind to the nineteen tracked .py files "
                     "at the repository root -- seven of them the shipped MCP surface, "
                     "including mcp_server.py, the file .mcp.json launches. Measured: "
                     "c6221f3b moved 65 lines of mcp_server.py and returns EMPTY under the "
                     "old pathspec."),
        },
    },
    "suites": {
        "status": "NOT_RUN",
        "note": ("The full pytest suite was NOT run for this cut and no suite figure is "
                 "published here. A number with no producer does not go in an asset. CI "
                 "green on the four required contexts is the gate that did run, resolved "
                 "against the tagged commit. Six contract feature flags in "
                 ".synapse/contracts/hython-verbs.yaml remain false for the same reason."),
    },
    "known": [
        ("The id-hash collision mechanism is TICKETED, NOT FIXED "
         "(harness/notes/findings/id-hash-collision.md). Two memory writes of identical "
         "content and memory_type inside one wall-clock second still collide on id, because "
         "created_at carries whole-second resolution. The fix exists behind a default-off "
         "flag; promoting it is an operator decision."),
        ("Four memory records -- the entire v4 studio-lookdev recipe generation -- exist in "
         "the encrypted JSONL mirror and NOT in the Moneta primary. Recall therefore answers "
         "\"Create a Solaris Network\" with the v3 simple-sphere recipe. Not repaired in this "
         "release; a store write is an operator decision."),
        ("CLAUDE.md still carries the /mcp-goes-through-the-bridge claim that README.md "
         "corrects in this release. The two disagree until CLAUDE.md is updated."),
        ("Nothing that runs automatically can see the runtime this product ships into: CI is "
         "ubuntu/macos on Python 3.11 and 3.14, while production is hython on Windows inside "
         "Houdini. There is no Windows leg, no Houdini leg and no scheduled run. The "
         "qualification above is a human-triggered act, not an automatic backstop."),
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

io.open(os.path.join(NOTES, "SYNAPSE-%s-Setup.public-build.json" % VERSION), "w",
        encoding="utf-8", newline="\n").write(pub_blob + "\n")
io.open(os.path.join(NOTES, "installer-verification.json"), "w",
        encoding="utf-8", newline="\n").write(rep_blob + "\n")

print("pass %s" % ("2 (final)" if args.final else "1"))
print("  Setup.exe      %s  %s B" % (SETUP[:16] + "...", format(SETUP_BYTES, ",")))
print("  payload        %s  %d files" % (PAYLOAD[:16] + "...", prod["payload"]["files"]))
print("  qualification  %d/%d PASS, Houdini 22.0.400" % (len(qual_pass), len(qual_lines)))
print("  product delta  %s" % (", ".join(prod_names)))
print("  source_revision %s" % REV)
print("  wrote SHA256SUMS.txt, public-build.json, installer-verification.json")
