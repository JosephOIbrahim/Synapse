"""hython_verbs.py -- verifier for the hython-verbs contract.

Pure Python. No hou, no hython, no PySide. Stock `python` runs it as a REAL
assertion, so it cannot false-green via skip.

It does NOT re-run the sweep. It reads the evidence artifact that
tools/hy_verbs_sweep.py produced under hython and asserts the table has not
drifted from the frozen baseline.

Staleness is the failure class this guards hardest. An artifact that is
complete and internally consistent but was produced against a DIFFERENT build,
or by an OLDER version of the sweep script, is exactly the apex_probes.py
H21-stamp defect wearing new clothes. --check freshness fails on both.

Script drift is detected by CONTENT, not mtime. tools/hy_verbs_sweep.py stamps
a sha256 of its own source into the artifact; this file re-hashes the source on
disk and compares. Git does not preserve mtimes, so the old timestamp
comparison was checkout-order roulette on a clean clone and in CI -- a gate
that fails for a reason unrelated to what it guards. An artifact carrying no
stamp is UNVERIFIABLE and therefore FAILS: a gate that cannot see is not an
open gate.

Usage:
    python harness/verify/hython_verbs.py --check all
    python harness/verify/hython_verbs.py --check freshness|ok|ui-bound|tops-defect|no-mutation
    python harness/verify/hython_verbs.py --freeze     # regenerate the baseline
"""

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SWEEP = os.path.join(REPO, "tools", "_hy_verbs_sweep.json")
SWEEP_SRC = os.path.join(REPO, "tools", "hy_verbs_sweep.py")
LAUNCHER = os.path.join(REPO, "tools", "hy.ps1")
BASELINE = os.path.join(REPO, "tools", "hy_verbs_baseline.json")

UI_BOUND = "capture_viewport"

# Must match tools/hy_verbs_sweep.py. Spelled as byte values so no escape
# survives a copy/paste round trip.
_CRLF = bytes((13, 10))
_LF = bytes((10,))


FAILURES = []


def fail(check, msg):
    FAILURES.append("[%s] %s" % (check, msg))


def load(path, what):
    if not os.path.exists(path):
        print("FATAL: %s missing: %s" % (what, path))
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pinned_build():
    """The build tools/hy.ps1 pins. Source of truth for the freshness check."""
    with open(LAUNCHER, encoding="utf-8") as f:
        m = re.search(r"^\$Build\s*=\s*'([^']+)'", f.read(), re.M)
    return m.group(1) if m else None


def sweep_src_sha256():
    """sha256 of the sweep script's CONTENT as it exists on disk right now.

    Normalizes CRLF to LF exactly as tools/hy_verbs_sweep.py does when it
    stamps itself. Both sides must agree or the gate false-fails on a working
    tree whose line endings drifted from the .gitattributes `eol=lf` pin --
    which has already happened to this very file (`git ls-files --eol` reports
    `i/lf w/crlf` for it).
    """
    with open(SWEEP_SRC, "rb") as f:
        return hashlib.sha256(f.read().replace(_CRLF, _LF)).hexdigest()


def statuses(sweep):
    return {r["verb"]: r["status"] for r in sweep.get("results", [])}


def check_freshness(sweep, base):
    if not sweep.get("complete"):
        fail("freshness", "sweep did not complete -- the watchdog may have killed "
                          "it mid-run; in_flight=%r" % sweep.get("in_flight"))
    pin = pinned_build()
    if pin and sweep.get("build") != pin:
        fail("freshness", "artifact build %r != launcher pin %r -- re-run the sweep"
             % (sweep.get("build"), pin))
    if sweep.get("ui_available"):
        fail("freshness", "artifact was produced WITH a UI; it is not a headless result")
    stamped = sweep.get("sweep_src_sha256")
    if not stamped:
        fail("freshness", "artifact carries no sweep_src_sha256 stamp -- WHICH script "
                          "produced it is UNVERIFIABLE, and unverifiable is not a pass; "
                          "re-run the sweep")
    else:
        current = sweep_src_sha256()
        if stamped != current:
            fail("freshness", "hy_verbs_sweep.py CHANGED since it produced this artifact "
                              "-- sha256 mismatch: artifact stamped %s, source on disk "
                              "is %s; re-run the sweep" % (stamped, current))


def check_ok(sweep, base):
    st = statuses(sweep)
    for verb in base["ok_verbs"]:
        got = st.get(verb, "<absent>")
        if got != "ok":
            fail("ok", "%s regressed: expected ok, got %s" % (verb, got))


def check_ui_bound(sweep, base):
    """capture_viewport is PERMANENTLY UI-bound. Correct behaviour, never a defect.

    Asserted in both directions: if it ever starts passing headless, something
    changed that we should look at, not silently accept.
    """
    st = statuses(sweep)
    got = st.get(UI_BOUND, "<absent>")
    if got != "headless_fail":
        fail("ui-bound", "%s expected headless_fail (UI-bound by design), got %s"
             % (UI_BOUND, got))


def check_tops_defect(sweep, base):
    """The TOPS six are a LIVE DEFECT, recorded not fixed.

    Cause: a bare `import hdefereval` in each handler body, which raises at
    import outside a graphical Houdini before run_on_main is ever reached.
    Sites pinned in the baseline. Set equality both ways -- a new member is a
    regression, a missing member means someone fixed it and the baseline plus
    the defect note must be updated deliberately.
    """
    st = statuses(sweep)
    observed = {v for v, s in st.items() if s == "headless_fail" and v != UI_BOUND}
    expected = set(base["tops_defect"])
    for v in sorted(observed - expected):
        fail("tops-defect", "NEW headless failure not in baseline: %s" % v)
    for v in sorted(expected - observed):
        fail("tops-defect", "%s no longer fails headless -- if fixed, re-freeze the "
                            "baseline and close the defect note" % v)


def check_no_mutation(sweep, base):
    if sweep.get("scene_moved") is not False:
        fail("no-mutation", "scene fingerprint moved during a READ-ONLY sweep: "
                            "before=%r after=%r" % (sweep.get("fingerprint_before"),
                                                    sweep.get("fingerprint_after")))


CHECKS = {
    "freshness": check_freshness,
    "ok": check_ok,
    "ui-bound": check_ui_bound,
    "tops-defect": check_tops_defect,
    "no-mutation": check_no_mutation,
}


def freeze():
    sweep = load(SWEEP, "sweep artifact")
    if not sweep.get("complete"):
        print("REFUSING to freeze an incomplete sweep.")
        sys.exit(2)
    st = statuses(sweep)
    base = {
        "frozen_from_build": sweep.get("build"),
        "python": sweep.get("python"),
        "ok_verbs": sorted(v for v, s in st.items() if s == "ok"),
        "ui_bound": [UI_BOUND],
        "tops_defect": sorted(v for v, s in st.items()
                              if s == "headless_fail" and v != UI_BOUND),
        "defect_note": {
            "cause": "bare `import hdefereval` in the handler body raises at import "
                     "outside a graphical Houdini, before run_on_main is reached",
            "sites": ["python/synapse/server/handlers_tops/diagnostics.py:248",
                      "python/synapse/server/handlers_tops/work_items.py:40"],
            "marshal": "python/synapse/server/handlers_tops/_common.py -- wraps "
                       "hdefereval.executeInMainThreadWithResult, the pre-migration "
                       "pattern main_thread.py replaced; no timeout, no stall "
                       "detector, no C4 zombie-kill, no C6 telemetry",
            "status": "RECORDED, not fixed -- this contract does not touch handlers_tops",
        },
    }
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=2)
    print("froze baseline from build %s: %d ok, %d ui-bound, %d tops-defect -> %s"
          % (base["frozen_from_build"], len(base["ok_verbs"]),
             len(base["ui_bound"]), len(base["tops_defect"]), BASELINE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="all", choices=sorted(CHECKS) + ["all"])
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()

    if a.freeze:
        return freeze()

    sweep = load(SWEEP, "sweep artifact")
    base = load(BASELINE, "baseline")
    names = sorted(CHECKS) if a.check == "all" else [a.check]
    for n in names:
        CHECKS[n](sweep, base)

    if FAILURES:
        print("FAIL (%d)" % len(FAILURES))
        for f_ in FAILURES:
            print("  " + f_)
        sys.exit(1)
    print("PASS: %s (build %s, %d verbs swept)"
          % (", ".join(names), sweep.get("build"), len(sweep.get("results", []))))


if __name__ == "__main__":
    main()
