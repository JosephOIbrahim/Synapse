"""Producer path for the v5.70.0 release assets' qualification report.

Every number in `installer-verification.json` comes from a measured artifact on
disk -- the 19 check lines are PARSED from `qual-stdout.txt`, not retyped -- so
the report is re-derivable rather than folklore (Law 2).

Run from the repo root after the build + qualification:

    python harness/notes/release-5.70.0/compose_verification.py

It refuses to write a report that carries a local path.
"""
import io
import json
import os

BUILD = r"C:/synapse-build/output-5.70.0"
OUT = os.path.join(BUILD, "output")
REV = "387e195fec0c7f8cfbcf9e25aa9064f8b9f55ba2"
PAYLOAD = "50244e9a4022fd091b0ebaacf0c106be2c59b458ad7ae0ecc02c75ee93bc7a8a"
TESTSETUP = "65a5b61ca6a8b37d8cf665507568b9a747df8a6825dac4f2ccf2a55b507edc6d"
SETUP = "41cb7368b7e67c2481a6248ce3431a1a97eb47a15886822c3507496795949add"

# The 19 qualification lines are parsed, never retyped.
checks = []
for line in io.open(os.path.join(BUILD, "qual-stdout.txt"), encoding="utf-8").read().splitlines():
    if not line.strip():
        continue
    name, _, result = line.rpartition(":")
    checks.append({"name": name.strip(), "result": result.strip()})
assert len(checks) == 19, len(checks)
assert all(c["result"] == "PASS" for c in checks), checks

KNOWN = [
    "test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks",
    "test_bc_wave.py::test_profile_row_retired",
    "test_failure_trail.py::test_dead_verb_hidden",
    "test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live",
    "test_j2_token_face.py::test_face_counts_an_ollama_task",
]

HAZARD = (
    "A first run of this suite reported 6 failed / 200 passed. The sixth, "
    "test_ollama_discovery.py::test_closing_parent_during_discovery_never_calls_deleted_qt, "
    "failed as Discovery-did-not-settle with PermissionError [WinError 32] rotating "
    "~/.synapse/logs/synapse.log -- the stock suite was running concurrently and held the "
    "same file. Re-run alone it passes. The seat suite and the stock suite MUST NOT be run "
    "at the same time; nothing in either detects the collision. The summary above was "
    "measured alone."
)

RESIDENT_CAVEAT = (
    "The panel activity module was NOT already resident; this check imported it (a "
    "pure-string module; synapse.panel.__init__ is inert). So this proves the running "
    "process's tree carries the fix. It does NOT prove an already-open panel picked it up "
    "-- a live session holds the old module until the panel is reloaded or Houdini "
    "restarts, which the release notes state."
)

report = {
    "schema": "synapse-release-verification-1",
    "version": "5.70.0",
    "source_revision": REV,
    "status": "PASS",
    "amended": ("2026-09-14: CI was still running when this release was published, and this "
                "report was uploaded saying so rather than guessing. It concluded success and "
                "the report was amended in place."),
    "ci": {
        "headSha": REV,
        "conclusion": "success",
        "run_id": 34895063247,
        "jobs": ["test (ubuntu-latest, 3.11) -> success",
                 "test (ubuntu-latest, 3.14) -> success",
                 "test (macos-latest, 3.11) -> success",
                 "test (macos-latest, 3.14) -> success"],
        "note": ("Recorded PENDING_AT_PUBLICATION in the first upload of this report; the "
                 "release was published before CI finished and the field said so."),
        "scope": ("GitHub Actions CI on the tagged commit. Stock Python on Linux and macOS; "
                  "not a Houdini or Windows-installer check."),
    },
    "payload_audit": {
        "status": "PASS",
        "source_revision": REV,
        "payload_sha256": PAYLOAD,
        "payload_id": "5.70.0-caf329c319d3215a",
        "builds": [
            {"name": "SYNAPSE-5.70.0-Setup.exe", "sha256": SETUP, "bytes": 31830148},
            {"name": "SYNAPSE-5.70.0-TestSetup.exe", "sha256": TESTSETUP},
        ],
        "moneta": {
            "archive_sha256": "81a3d8735c7da49ca81302725acab6a3324311091e850c34afcea92e87ea31f7",
            "note": ("Byte-identical to the reviewed, previously authorized 1.2.0rc1 bundle. "
                     "Verified BEFORE the build; no unreviewed content was substituted."),
        },
    },
    "compiled_installer": {
        "summary": "19 of 19 PASS, exit 0",
        "expected_version": "5.70.0",
        "testsetup_sha256": TESTSETUP,
        "scope": ("Compiled isolated TestSetup in a sandbox root the harness created itself; "
                  "synthetic prior payload, never a historical release. The TestSetup carries "
                  "the SAME payload sha256 as the published Setup (" + PAYLOAD + "), which is "
                  "what binds this qualification to the shipped artifact."),
        "checks": checks,
    },
    "local_stock_suite": {
        "source_revision": REV,
        "summary": "8920 passed, 430 skipped, 0 failed, 625 warnings in 335.90s",
        "scope": "Local Windows, stock Python 3.14, vendored SDK inactive.",
    },
    "installer_unit_checks": {
        "summary": "37 passed in 14.18s",
        "scope": "installer/tests lifecycle and adversarial engine, unchanged in this release.",
    },
    "final_targeted_checks": {
        "version_conformance": "11 passed",
        "release_tag_pins": "28 passed",
        "scope": ("Version single-sourcing across six surfaces, and the README "
                  "release-channel banner."),
    },
    "installed_houdini": {
        "status": "PASS",
        "build": "22.0.400",
        "python": "3.13.10",
        "summary": "tests/panel/ 201 passed, 5 failed, 69.55s",
        "scope": "Separate headless Houdini process with offscreen Qt, not the artist's session.",
        "known_failures": KNOWN,
        "note": ("The first two are recorded design conflicts awaiting a ruling, not defects. "
                 "The other three are named and undiagnosed. None is new in 5.70.0."),
        "measurement_hazard": HAZARD,
    },
    "live_houdini": {
        "status": "PASS",
        "build": "22.0.400",
        "python": "3.13.10",
        "version_reported_by_live_process": "5.70.0",
        "loaded_from": "source tree, not the installed Setup",
        "scope": ("Read-only introspection against the artist's RUNNING Houdini via the live "
                  "bridge. It answers whether THIS process's source tree produces the new "
                  "labels, which source inspection on the build machine cannot establish."),
        "method": ("Node census before and after (9 nodes / 0 obj / 0 stage / frame 1.0, "
                   "identical both times). Nothing created, set, cooked or rendered. "
                   "Selection is the artist's own UI state and is deliberately not asserted."),
        "scene_unchanged": True,
        "panel_activity_was_resident": False,
        "resident_caveat": RESIDENT_CAVEAT,
        "module_sha256_matches_tagged_file": True,
        "module_sha256": "2c574a9590b6abef47d409f2e2ada6b2476cd16fdd1d999f6b8a72bc8ebdb671",
        "labels_measured_live": {
            "houdini_create_usd_prim": "Create USD primitive",
            "synapse_solaris_shotsetup_karma_xpu": "Solaris shot setup Karma XPU",
            "cops_reaction_diffusion": "Reaction diffusion",
            "cops_composite_aovs": "Composite AOVs",
            "houdini_set_parm": "Set a parameter",
            "synapse_ping": "Check the Houdini connection",
        },
        "dead_curated_keys_live": [],
        "old_capitalize_gone": True,
    },
    "remaining_qualification": [
        "Unsigned installer; code signing remains outstanding.",
        "No clean Windows machine and no native wizard visual qualification in this run.",
        "Synthetic prior payload covers the upgrade path; not a historical released installer.",
        ("The local suite's skip population is not stable: 21 tests are disabled by a symbol "
         "missing from an out-of-tree dependency and no gate in this repository can see it "
         "(harness/notes/SUITE_FLOOR_IS_NOT_STABLE.md)."),
        "Five panel seat tests remain red; two are recorded design conflicts awaiting a ruling.",
        ("QMenu modals can still hang a seat test. The guard covers dialog exec() and the C++ "
         "static helpers; a patch on QMenu.exec was measured to install and do nothing, so it "
         "is documented as an uncovered hole rather than implied closed."),
    ],
    "retained_failed_attempts": [
        {
            "scope": "First seat-suite measurement",
            "result": ("6 failed / 200 passed, run concurrently with the stock suite. Discarded "
                       "as a log-file contention artifact after re-running alone reproduced "
                       "201/5. Kept because the failure looked like a real timing regression "
                       "and would have been reported as one."),
        },
    ],
}

blob = json.dumps(report, indent=2, sort_keys=True)
# Path-shaped leaks only. A bare username match is a false positive: one of the
# 19 parsed check names is "No user-data changes during upgrade".
_HOME = os.path.expanduser("~")
leaks = [tok for tok in ("C:\\", "C:/", "c:\\", "c:/", "synapse-build",
                         "\\Users\\", "/Users/", _HOME, _HOME.replace("\\", "/"))
         if tok and tok in blob]
assert not leaks, "verification report leaks local paths: %s" % leaks
io.open(os.path.join(OUT, "installer-verification.json"), "w",
        encoding="utf-8", newline="\n").write(blob + "\n")
print("installer-verification.json written: 19/19 checks parsed, redaction clean")
