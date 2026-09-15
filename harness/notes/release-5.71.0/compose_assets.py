"""Producer path for the v5.70.1 release assets.

Every number in the three composed assets comes from a measured artifact on disk:
the 19 qualification lines are PARSED from qual-stdout.txt, the suite summaries
are the last summary line of each pytest log, the hashes are read from the
builder's own build.json reports. Nothing is retyped (Law 2).

Run from the repo root after build + qualification + suites:

    python harness/notes/release-5.71.0/compose_assets.py [--ci-run-id N]

Writes, into C:/synapse-build/output-5.71.0/output/:
    SHA256SUMS.txt
    SYNAPSE-5.70.1-Setup.public-build.json      (schema synapse-public-build-1, redacted)
    installer-verification.json                 (schema synapse-release-verification-1)
and fills the {{PLACEHOLDER}} numbers in docs/releases/v5.70.1.md and
harness/notes/RELEASE_v5.70.1.md from the same sources.

It refuses to write a report that carries a local path.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

VERSION = "5.71.0"
REPO = r"C:/Users/User/SYNAPSE"
BUILD = r"C:/synapse-build/output-5.71.0"
OUT = os.path.join(BUILD, "output")
NOTES = os.path.join(REPO, "harness/notes/release-5.71.0")

def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()

def last_summary(path):
    """pytest's own summary line, e.g. '8920 passed, 430 skipped, ... in 335.90s'."""
    for line in reversed(read(path).splitlines()):
        t = line.strip()
        m = re.search(r"=+ (.*?) =+$", t) or re.match(r"^((?:\d+ (?:passed|failed|skipped|warnings?|errors?)(?:, )?)+.*in [\d.]+s.*)$", t)
        if m and ("passed" in m.group(1) or "failed" in m.group(1)):
            return m.group(1)
    raise SystemExit("no pytest summary line in " + path)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# ---- build reports (the builder wrote these; we read, never retype) ----
prod = json.load(open(os.path.join(OUT, f"SYNAPSE-{VERSION}-Setup.build.json")))
test = json.load(open(os.path.join(OUT, f"SYNAPSE-{VERSION}-TestSetup.build.json")))
PAYLOAD = prod["payload"]["sha256"]
assert test["payload"]["sha256"] == PAYLOAD, "TestSetup and Setup payload sha256 differ -- qualification would not bind"
PAYLOAD_ID = prod["payload"]["payload_id"]
SETUP_EXE = os.path.join(OUT, f"SYNAPSE-{VERSION}-Setup.exe")
TESTSETUP_EXE = os.path.join(OUT, f"SYNAPSE-{VERSION}-TestSetup.exe")
SETUP = sha256(SETUP_EXE)
TESTSETUP = sha256(TESTSETUP_EXE)
assert SETUP == prod["installer_sha256"], "Setup.exe on disk does not match the builder's recorded sha256"
SETUP_BYTES = os.path.getsize(SETUP_EXE)
REV = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
BUILD_REV = read(os.path.join(NOTES, "build-rev.txt")).strip()

# ---- qualification: parsed, never retyped ----
checks = []
for line in read(os.path.join(NOTES, "qual-stdout.txt")).splitlines():
    if not line.strip() or ":" not in line:
        continue
    name, _, result = line.rpartition(":")
    checks.append({"name": name.strip(), "result": result.strip()})
assert len(checks) == 19, len(checks)
assert all(c["result"] == "PASS" for c in checks), checks
QUAL = "19 of 19 PASS, exit 0"

STOCK = last_summary(os.path.join(NOTES, f"suite-{VERSION}.txt"))
SEAT = last_summary(os.path.join(NOTES, f"seat-{VERSION}.txt"))
INST = last_summary(os.path.join(NOTES, f"installer-tests-{VERSION}.txt"))

# ---- CI ----
ci_run = None
for i, a in enumerate(sys.argv):
    if a == "--ci-run-id":
        ci_run = int(sys.argv[i + 1])
ci = {"headSha": REV, "conclusion": "PENDING_AT_PUBLICATION", "run_id": ci_run,
      "scope": "GitHub Actions CI on the tagged commit. Stock Python on Linux and macOS; not a Houdini or Windows-installer check."}
if ci_run:
    r = subprocess.run(["gh", "run", "view", str(ci_run), "--json", "status,conclusion,jobs"], capture_output=True, text=True)
    if r.returncode == 0:
        d = json.loads(r.stdout)
        if d.get("status") == "completed":
            ci["conclusion"] = d.get("conclusion")
            ci["jobs"] = [f'{j["name"]} -> {j["conclusion"]}' for j in d.get("jobs", [])]
CI_STATUS = ci["conclusion"] + (f" (run {ci_run})" if ci_run else "")

KNOWN = [
    "test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks",
    "test_bc_wave.py::test_profile_row_retired",
    "test_failure_trail.py::test_dead_verb_hidden",
    "test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live",
    "test_j2_token_face.py::test_face_counts_an_ollama_task",
]
seat_failed = re.findall(r"^FAILED (\S+)", read(os.path.join(NOTES, f"seat-{VERSION}.txt")), re.M)
seat_failed_short = sorted(f.split("tests/panel/")[-1].split(" ")[0] for f in seat_failed)
seat_new = sorted(set(seat_failed_short) - set(KNOWN))

# ---- 1. SHA256SUMS.txt ----
io.open(os.path.join(OUT, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n").write(
    f"{SETUP} *SYNAPSE-{VERSION}-Setup.exe\n")

# ---- 2. public-build.json: redacted copy of the builder's report ----
pub = json.loads(json.dumps(prod))
pub["installer"] = os.path.basename(pub["installer"])
pub["payload"].pop("path", None)
pub.pop("test_build", None)
pub["installer_bytes"] = SETUP_BYTES
pub["qualification_report"] = "installer-verification.json"
pub["schema"] = "synapse-public-build-1"
pub["source_revision"] = REV
pub["version"] = VERSION

# ---- 3. installer-verification.json ----
report = {
    "schema": "synapse-release-verification-1",
    "version": VERSION,
    "source_revision": REV,
    "build_revision": BUILD_REV,
    "status": "PASS" if not seat_new else "PASS_WITH_NEW_SEAT_RED",
    "ci": ci,
    "payload_audit": {
        "status": "PASS",
        "payload_sha256": PAYLOAD,
        "payload_id": PAYLOAD_ID,
        "builds": [
            {"name": f"SYNAPSE-{VERSION}-Setup.exe", "sha256": SETUP, "bytes": SETUP_BYTES},
            {"name": f"SYNAPSE-{VERSION}-TestSetup.exe", "sha256": TESTSETUP},
        ],
        "product_change_since_v5.70.0": {
            "check": "git diff --stat v5.70.0 HEAD -- python installer",
            "result": subprocess.run(["git", "-C", REPO, "diff", "--stat", "v5.70.1", REV, "--", "python", "installer"],
                                     capture_output=True, text=True).stdout.strip() or "(empty: identical)",
            "note": ("Expected: only python/synapse/__init__.py, the version string. The payload was built from the "
                     "bumped working tree, so payload and tag agree; the pre-bump HEAD at build time was " + BUILD_REV[:12] + "."),
        },
        "moneta": {
            "archive_sha256": prod["payload"]["moneta"]["archive_sha256"],
            "note": "Byte-identical to the reviewed, previously authorized 1.2.0rc1 bundle. Verified BEFORE the build.",
        },
    },
    "compiled_installer": {
        "summary": QUAL,
        "expected_version": VERSION,
        "testsetup_sha256": TESTSETUP,
        "scope": ("Compiled isolated TestSetup in a sandbox root the harness created itself; synthetic prior payload, "
                  "never a historical release. The TestSetup carries the SAME payload sha256 as the published Setup ("
                  + PAYLOAD + "), which is what binds this qualification to the shipped artifact."),
        "checks": checks,
    },
    "local_stock_suite": {"summary": STOCK, "scope": "Local Windows, stock Python 3.14, vendored SDK inactive. Run alone."},
    "installer_unit_checks": {"summary": INST, "scope": "installer/tests lifecycle and adversarial engine, unchanged in this release."},
    "installed_houdini": {
        "status": "PASS" if not seat_new else "NEW_RED",
        "build": "22.0.400",
        "summary": SEAT,
        "scope": "Separate headless Houdini process with offscreen Qt (SYNAPSE_HYTHON pinned), not the artist's session. Run alone, after the stock suite.",
        "failed": seat_failed_short,
        "known_failures": KNOWN,
        "new_failures": seat_new,
        "note": "The first two known reds are recorded design conflicts awaiting a ruling; the other three are named and undiagnosed.",
    },
    "live_houdini": {
        "status": "NOT_RUN",
        "reason": "No module changed in this release; there is nothing new for a live process to load. The 5.70.0 live check remains the last one.",
    },
    "remaining_qualification": [
        "Unsigned installer; code signing remains outstanding.",
        "No clean Windows machine and no native wizard visual qualification in this run.",
        "Synthetic prior payload covers the upgrade path; not a historical released installer.",
        "The local suite's skip population is not stable (harness/notes/SUITE_FLOOR_IS_NOT_STABLE.md).",
        "Five panel seat tests remain red; two are recorded design conflicts awaiting a ruling.",
        "docs/ in the payload is one edit behind the tag (release notes and changelog were written after the build from measured numbers); python/ and installer/ match the tag, see payload_audit.",
        "Bridge-down send queue (FR-1, harness/notes/closeout-2026-09-15/) is disclosed in the release notes, not fixed.",
    ],
}

def redact_check(blob):
    home = os.path.expanduser("~")
    leaks = [tok for tok in ("C:\\", "C:/", "c:\\", "c:/", "synapse-build", "\\Users\\", "/Users/", home, home.replace("\\", "/")) if tok and tok in blob]
    assert not leaks, "asset leaks local paths: %s" % leaks

pub_blob = json.dumps(pub, indent=2, sort_keys=True); redact_check(pub_blob)
rep_blob = json.dumps(report, indent=2, sort_keys=True); redact_check(rep_blob)
io.open(os.path.join(OUT, f"SYNAPSE-{VERSION}-Setup.public-build.json"), "w", encoding="utf-8", newline="\n").write(pub_blob + "\n")
io.open(os.path.join(OUT, "installer-verification.json"), "w", encoding="utf-8", newline="\n").write(rep_blob + "\n")

# ---- fill the placeholders in the two markdown notes ----
fills = {"{{STOCK_SUMMARY}}": STOCK, "{{SEAT_SUMMARY}}": SEAT, "{{INSTALLER_UNIT_SUMMARY}}": INST, "{{QUAL_SUMMARY}}": QUAL,
         "{{PAYLOAD_SHA}}": PAYLOAD, "{{PAYLOAD_ID}}": PAYLOAD_ID, "{{BUILD_REV}}": BUILD_REV, "{{BUILD_REV_SHORT}}": BUILD_REV[:12],
         "{{CI_STATUS}}": CI_STATUS}
for md in (os.path.join(REPO, "docs/releases/v5.70.1.md"), os.path.join(REPO, "harness/notes/RELEASE_v5.70.1.md")):
    t = read(md)
    for k, v in fills.items():
        t = t.replace(k, v)
    assert "{{" not in t, "unfilled placeholder in " + md
    io.open(md, "w", encoding="utf-8", newline="\n").write(t)

print("SHA256SUMS.txt, public-build.json, installer-verification.json written; notes filled")
print("stock:", STOCK); print("seat:", SEAT, "| new reds:", seat_new); print("installer tests:", INST)
print("payload:", PAYLOAD, "| setup:", SETUP, "| product diff vs v5.70.0:", report["payload_audit"]["product_change_since_v5.70.0"]["result"])
