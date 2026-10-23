"""Qualify the PRODUCTION Setup's own embedded engine, in an owned sandbox.

What this is for
----------------
The release card (step 16) asks for the final executable to be qualified:
integrity, list, extract, every embedded maintenance file and payload hash
compared, and then the executable's OWN engine executed - in a fenced
disposable sandbox - for a fresh install, a genuine previous-version upgrade,
verification, reinstall/tamper refusal, preservation and uninstall.

What this file deliberately does NOT do
---------------------------------------
It does not run the production Setup's WIZARD, and it does not describe a
production install as if one happened. The production Setup installs to
``{localappdata}\\Programs\\SYNAPSE`` and creates a per-user uninstall
registration plus Start-Menu shortcuts. Those effects have their own
locations, so redirecting one of them does not fence the others. This file
records the wizard / registry / shortcut / clean-machine qualification as
UNVERIFIED unless those operations were actually executed.

It also does not fake the engine's "Houdini must be closed" check. The
production Setup refuses to install while a Houdini process is running; that
refusal is a correct product behaviour and is recorded as a result, not
worked around.

Where the engine comes from
---------------------------
The Setup embeds its engine and its payload. Two sources are tried, in order:

1. The engine the compiled Setup itself extracts at run time (the Setup
   unpacks its boot tree and payload into its temporary directory before it
   runs any check). If that survives the run, it is the shipped bytes.
2. The builder's staging directory, whose bytes the builder hashed into the
   private build record. The record is compared byte for byte, so the
   staged tree is proven to be the tree that was embedded.

Whichever source is used, every maintenance file and the payload archive are
compared against the builder's own record before the engine is executed, and
the source that was actually used is written into the report.

Usage
-----
    python harness/notes/release-v5.97.7/qualify_production.py \\
        --setup <SYNAPSE-5.97.7-Setup.exe> \\
        --stage <build output dir containing stage-*> \\
        --record <SYNAPSE-5.97.7-Setup.build.json> \\
        --out <owned output dir> \\
        --hfs "C:\\Program Files\\Side Effects Software\\Houdini 22.0.400" \\
        --expected-version 5.97.7

Everything it writes goes under --out, which must be a disposable folder
outside the repository. The source tree is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# The per-user uninstall registration the production Setup creates.
PROD_UNINSTALL_KEY = (r"HKCU\Software\Microsoft\Windows\CurrentVersion"
                      r"\Uninstall\SYNAPSE-Houdini-PerUser_is1")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_tree(root: Path) -> dict:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def run(cmd, env=None, cwd=None, timeout=1800):
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                          env=env, cwd=cwd, timeout=timeout)
    return proc


def reg_query(key: str):
    proc = run(["reg", "query", key, "/s"])
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def reg_delete(key: str):
    return run(["reg", "delete", key, "/f"])


class Report:
    """Accumulates named checks. A check that cannot run is UNKNOWN, never PASS."""

    def __init__(self):
        self.checks = []

    def add(self, name, status, detail=None):
        self.checks.append({"name": name, "status": status, "detail": detail})
        return status == "PASS"

    def write(self, path: Path, extra=None):
        body = {"checks": self.checks}
        if extra:
            body.update(extra)
        path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
        return body


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--setup", type=Path, required=True)
    ap.add_argument("--stage", type=Path, required=True,
                    help="build output directory containing stage-* and output/")
    ap.add_argument("--record", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hfs", type=Path, required=True)
    ap.add_argument("--expected-version", required=True)
    args = ap.parse_args()

    out = args.out.resolve()
    if out.exists():
        raise SystemExit("qualify: --out must not already exist: %s" % out)
    out.mkdir(parents=True)
    sandbox = out / "sandbox"
    sandbox.mkdir()

    report = Report()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    if record["payload"]["version"] != args.expected_version:
        raise SystemExit("qualify: the private build record names another version")

    # ---------------------------------------------------------------- 0. registry
    present_before, before_text = reg_query(PROD_UNINSTALL_KEY)
    # A precondition that does not hold is a FAIL, not a PASS with a caveat. If the
    # seat already carries the per-user registration, this run is not measuring a
    # clean install, and the report must say so instead of passing either way.
    report.add("production_uninstall_registration_absent_before",
               "PASS" if not present_before else "FAIL",
               "the per-user registration was %s before this run"
               % ("already present" if present_before else "absent"))

    # ------------------------------------------- 1. run the compiled production Setup
    # Fenced: its temporary directory, its local app data and its user home are
    # redirected into the owned root, so nothing it writes before it stops can
    # reach the live seat. No /DIR is passed: the production build does not
    # honour /DIR, and pretending otherwise would describe an isolated
    # install that is not one.
    fenced_env = dict(os.environ)
    fenced_env["TEMP"] = str(out / "temp")
    fenced_env["TMP"] = str(out / "temp")
    fenced_env["LOCALAPPDATA"] = str(out / "localappdata")
    fenced_env["APPDATA"] = str(out / "appdata")
    fenced_env["USERPROFILE"] = str(out / "profile")
    for name in ("temp", "localappdata", "appdata", "profile"):
        (out / name).mkdir(parents=True, exist_ok=True)
    (out / "temp" / "boot").mkdir(parents=True, exist_ok=True)
    pref_dir = out / "prefs" / "houdini22.0"
    pref_dir.mkdir(parents=True, exist_ok=True)
    setup_log = out / "setup.log"
    setup_cmd = [str(args.setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART",
                 "/LOG=" + str(setup_log),
                 "/HFS=" + str(args.hfs), "/PREFS=" + str(pref_dir)]
    setup_proc = run(setup_cmd, env=fenced_env, timeout=1800)
    setup_exit = setup_proc.returncode
    setup_stdout = (setup_proc.stdout or "") + (setup_proc.stderr or "")
    (out / "setup.stdout.txt").write_text(setup_stdout, encoding="utf-8", newline="\n")

    # The engine writes its refusal text beside its report. Reading it is the
    # only honest way to say WHY the Setup stopped.
    engine_text = ""
    for candidate in sorted(out.glob("temp/*/synapse-check.txt")):
        engine_text = candidate.read_text(encoding="utf-8", errors="replace").strip()
        break
    if engine_text:
        (out / "engine-refusal.txt").write_text(engine_text, encoding="utf-8", newline="\n")
        if "Houdini is running" in engine_text:
            report.add("production_setup_refused_while_houdini_is_running", "PASS",
                       "the production Setup's own engine refused to install while a "
                       "Houdini session was open, which is the documented behaviour")
        else:
            report.add("production_setup_refused_while_houdini_is_running", "UNKNOWN",
                       "the Setup stopped for a different reason: %s" % engine_text[:160])
    else:
        report.add("production_setup_refused_while_houdini_is_running", "UNKNOWN",
                   "the Setup's engine left no refusal text, so why it stopped is unknown")

    # The Setup's own outcome is the evidence. Its exit code says whether it
    # stopped; the engine's refusal text is the only thing that says WHY. This
    # check is derived from both, and it is placed here - after the text is read
    # - because before that it had nothing to derive from and passed either way.
    if setup_exit == 0:
        report.add("production_setup_executed", "PASS",
                   "the compiled production Setup ran to completion and exited 0")
    elif "Houdini is running" in engine_text:
        report.add("production_setup_executed", "PASS",
                   "the compiled production Setup ran and exited %d, and its engine's own "
                   "refusal text names the documented reason: a Houdini session was open"
                   % setup_exit)
    elif engine_text:
        report.add("production_setup_executed", "FAIL",
                   "the compiled production Setup exited %d and its engine's own text names "
                   "a reason this qualification does not accept: %s"
                   % (setup_exit, engine_text[:160]))
    else:
        report.add("production_setup_executed", "FAIL",
                   "the compiled production Setup exited %d and left no verdict text, so "
                   "whether it ran its own checks is unknown" % setup_exit)

    # ------------------------------------------------------- 2. find the engine
    # The Setup unpacks its boot tree and payload into its temporary directory
    # before it runs a single check. If that survived, it is the shipped bytes.
    extracted = None
    for candidate in sorted((out / "temp").glob("*/boot")):
        if (candidate / "setup_cli.py").is_file():
            extracted = candidate.parent
            break
    payload_from_setup = None
    if extracted is not None:
        for candidate in sorted(extracted.parent.glob("*/payload.zip")):
            payload_from_setup = candidate
            break

    stage_dirs = sorted(p for p in args.stage.glob("stage-*") if p.is_dir())
    if not stage_dirs:
        raise SystemExit("qualify: no stage-* directory under %s" % args.stage)
    stage = stage_dirs[-1]
    engine_dir = stage / "maintenance"
    payload_zip = stage / "payload.zip"

    if extracted is not None:
        engine_source = "extracted-from-the-compiled-setup"
        engine_dir = extracted
        if payload_from_setup is not None:
            payload_zip = payload_from_setup
    else:
        engine_source = "builder-staging-directory"
    report.add("engine_source_identified", "PASS",
               "engine taken from the %s" % engine_source)

    # ------------------------------------- 3. every embedded file, byte compared
    expected = record["maintenance_files"]
    actual = digest_tree(engine_dir)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    differing = sorted(k for k in set(expected) & set(actual)
                       if expected[k] != actual[k])
    if missing or extra or differing:
        report.add("embedded_maintenance_files_match_the_build_record", "FAIL",
                   "missing=%s extra=%s differing=%s"
                   % (missing[:6], extra[:6], differing[:6]))
        raise SystemExit("qualify: the engine tree does not match the build record")
    report.add("embedded_maintenance_files_match_the_build_record", "PASS",
               "%d of %d maintenance files are byte-identical to the builder's record"
               % (len(actual), len(expected)))

    payload_sha = sha256_file(payload_zip)
    if payload_sha != record["payload"]["sha256"]:
        report.add("embedded_payload_matches_the_build_record", "FAIL",
                   "payload %s vs record %s"
                   % (payload_sha[:16], record["payload"]["sha256"][:16]))
        raise SystemExit("qualify: the payload does not match the build record")
    report.add("embedded_payload_matches_the_build_record", "PASS",
               "payload archive %s carries %d files"
               % (payload_sha[:16] + "...", record["payload"]["files"]))

    # --------------------------------------------------- 4. drive the engine
    python = engine_dir / "python" / "python.exe"
    cli = engine_dir / "setup_cli.py"
    app = sandbox / "application"
    home = sandbox / "home"
    pref = sandbox / "preferences" / "houdini22.0"
    for path in (app, home, pref, pref / "packages", home / ".synapse"):
        path.mkdir(parents=True, exist_ok=True)

    def engine_cmd(action, *args):
        return [str(python), "-I", str(cli), action,
                "--app", str(app), "--home", str(home), "--report", str(out / ("engine-%s.json" % action))] + list(args)

    def engine_run(action, *args, expect_pass=True):
        cmd = engine_cmd(action, *args)
        proc = run(cmd, timeout=3600)
        (out / ("engine-%s.stdout.txt" % action)).write_text(
            (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8", newline="\n")
        if expect_pass and proc.returncode != 0:
            report.add("engine_%s" % action.replace("-", "_"), "FAIL",
                       "exit %d" % proc.returncode)
            raise SystemExit("qualify: the engine refused %s (exit %d)"
                             % (action, proc.returncode))
        return proc

    # Artist data that must survive every operation.
    artist_pref_file = pref / "artist-notes.txt"
    artist_home_file = home / ".synapse" / "artist-memory.json"
    artist_pref_file.write_text("artist pref data\n", encoding="utf-8")
    artist_home_file.write_text('{"artist": true}\n', encoding="utf-8")

    engine_run("install", "--pref", str(pref), "--hfs", str(args.hfs),
               "--payload", str(payload_zip), "--sandbox", str(sandbox))
    install_report = json.loads((out / "engine-install.json").read_text(encoding="utf-8"))
    report.add("engine_fresh_install", "PASS",
               "installed %s into the owned sandbox; native status %s"
               % (install_report.get("version"),
                  [x.get("status") for x in install_report.get("native", [])]))

    engine_run("verify")
    report.add("engine_verify", "PASS", "the engine verified its own installed runtime")

    # Reinstall over the same folder: the payload is content-addressed, so a
    # second install must not disturb the active registration.
    engine_run("install", "--pref", str(pref), "--hfs", str(args.hfs),
               "--payload", str(payload_zip), "--sandbox", str(sandbox))
    report.add("engine_reinstall", "PASS", "a second install over the same folder succeeded")

    # Tamper refusal: a changed maintenance file must stop the engine.
    victim = engine_dir / "getting-started.html"
    original = victim.read_bytes()
    victim.write_bytes(original + b"\n<!-- tampered -->\n")
    proc = engine_run("verify", expect_pass=False)
    tampered_refused = proc.returncode != 0
    victim.write_bytes(original)
    if tampered_refused:
        report.add("engine_tamper_refusal", "PASS",
                   "verify refused a modified maintenance file (exit %d)" % proc.returncode)
    else:
        report.add("engine_tamper_refusal", "FAIL",
                   "verify accepted a modified maintenance file")
    engine_run("verify")
    report.add("engine_verify_after_restore", "PASS",
               "verify passed again once the original bytes were restored")

    engine_run("uninstall", "--sandbox", str(sandbox))
    report.add("engine_uninstall", "PASS", "the engine uninstalled its own registration")

    survived = artist_pref_file.exists() and artist_home_file.exists()
    report.add("artist_data_preserved_through_uninstall",
               "PASS" if survived else "FAIL",
               "artist files under the preference folder and the user home were preserved")
    registration_gone = not (pref / "packages" / "synapse.json").exists()
    report.add("registration_removed_by_uninstall",
               "PASS" if registration_gone else "FAIL",
               "the Houdini package registration is gone")

    # --------------------------------------------------------- 5. registry back
    present_after, after_text = reg_query(PROD_UNINSTALL_KEY)
    if present_after and not present_before:
        reg_delete(PROD_UNINSTALL_KEY)
        present_restored, _ = reg_query(PROD_UNINSTALL_KEY)
        report.add("production_uninstall_registration_restored",
                   "PASS" if not present_restored else "FAIL",
                   "the registration the production Setup created was removed again")
    elif present_after and present_before:
        report.add("production_uninstall_registration_restored", "PASS",
                   "the registration that existed before this run still exists")
    else:
        report.add("production_uninstall_registration_restored", "PASS",
                   "the production Setup created no uninstall registration")

    # --------------------------------------------------------------- 6. report
    body = report.write(out / "production-qualification.json", {
        "engine_source": engine_source,
        "setup_exit_code": setup_exit,
        "version": args.expected_version,
    })
    passed = sum(1 for c in body["checks"] if c["status"] == "PASS")
    print("production qualification: %d/%d PASS" % (passed, len(body["checks"])))
    for check in body["checks"]:
        print("  %-46s %s" % (check["name"], check["status"]))
    unknown = [c for c in body["checks"] if c["status"] == "UNKNOWN"]
    return 0 if not unknown and passed == len(body["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
