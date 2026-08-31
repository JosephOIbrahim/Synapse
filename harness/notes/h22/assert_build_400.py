# assert_build_400.py - Section B build-ownership assert (2026-08-31)
# CTO call on record: 22.0.400 owns demo week. Known finding: five builds
# share one prefs dir and nothing pins the default - this probe is the
# enforcement. Run anywhere (GUI Python Shell, Source Editor, hython).
# Touches no ports; safe off-main. Unmeasured renders UNKNOWN, never zero.
import json, os, sys

EXPECT = (22, 0, 400)

try:
    import hou
    ver = tuple(hou.applicationVersion()[:3])
    hfs = os.environ.get("HFS", "")
    # v2: HFS can arrive as an 8.3 short path (C:/PROGRA~1/SIDEEF~1/HOUDIN~1.400)
    # which false-FAILs a naive substring match. Resolve to the long path first;
    # sys.executable is the fallback authority. Probe-side false negative,
    # same class as BP1 G4 - corrected 2026-08-31 evening.
    hfs_real = os.path.realpath(hfs) if hfs else ""
    ok = ver == EXPECT and ("22.0.400" in hfs_real or "22.0.400" in sys.executable)
    print(json.dumps({
        "probe": "assert_build_400",
        "verdict": "PASS" if ok else "FAIL",
        "version": ".".join(map(str, ver)),
        "expect": "22.0.400",
        "HFS": hfs,
        "HFS_resolved": hfs_real,
        "prefs": os.environ.get("HOUDINI_USER_PREF_DIR", ""),
        "exe": sys.executable,
    }, indent=2))
except ImportError:
    print(json.dumps({
        "probe": "assert_build_400",
        "verdict": "UNKNOWN",
        "detail": "no hou in this interpreter - run inside Houdini or hython",
    }, indent=2))
