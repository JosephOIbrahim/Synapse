"""M5 probe #4: can $HIP be pinned so the fixture baseline stops depending
on the process working directory?

Established (probe #3): the committed baseline 8bb05761... embeds
$HIP-expanded absolute paths (karmarendersettings productName ->
"$HIP/render/untitled.render_settings.####.exr"). $HIP for an unsaved scene
resolves to the launch cwd, so the "deterministic" fixture hash is only
deterministic per working directory.

If $HIP can be set at runtime, the invariant harness can pin it and F-1
becomes a portable absolute check instead of a machine-local one.

Run:  hython harness/notes/_m5_hip_probe.py
"""
import hashlib
import json
import sys
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness" / "autoresearch"))
import probes  # noqa: E402

out = {"build": hou.applicationVersionString(), "cwd": str(Path.cwd())}
FX = json.loads((REPO / "fixtures" / "solaris.basic.json").read_text(encoding="utf-8"))
stage = hou.node("/stage")

out["hip_before"] = hou.expandString("$HIP")
out["has_putenv"] = callable(getattr(hou, "putenv", None))
out["has_hscript"] = callable(getattr(hou, "hscript", None))
out["has_setenv_module"] = sorted(
    a for a in dir(hou) if "env" in a.lower() and not a.startswith("_")
)

TARGET_HIP = "C:/Users/User/SYNAPSE"


def build_sha():
    res = probes._build_fixture_once(FX, stage)
    if "error" in res:
        return "ERROR: %s" % res
    return hashlib.sha256(res["canon_text"].encode("utf-8")).hexdigest()


out["sha_native_hip"] = build_sha()

# --- attempt 1: hou.putenv --------------------------------------------------
try:
    hou.putenv("HIP", TARGET_HIP)
    out["putenv_result"] = hou.expandString("$HIP")
except Exception as e:
    out["putenv_result"] = "%s: %s" % (type(e).__name__, e)

out["sha_after_putenv"] = build_sha()

# --- attempt 2: hscript setenv ---------------------------------------------
try:
    r = hou.hscript('setenv -g HIP = "%s"' % TARGET_HIP)
    out["hscript_setenv_result"] = r
    out["hip_after_hscript"] = hou.expandString("$HIP")
except Exception as e:
    out["hscript_setenv_result"] = "%s: %s" % (type(e).__name__, e)

out["sha_after_hscript"] = build_sha()
out["baseline_committed"] = FX["baseline"]["sha256"]
out["pinning_works"] = (out["sha_after_hscript"] == FX["baseline"]["sha256"]
                        or out["sha_after_putenv"] == FX["baseline"]["sha256"])

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps(out, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
