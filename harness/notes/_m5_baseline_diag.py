"""M5 diagnostic: why does the committed baseline not reproduce?

A faithful re-run of probes._build_fixture_once in this session yields
6552415d..., not the fixture's committed 8bb05761....  Either the baseline
is environment-dependent (in which case F-1 as written can never be a
stable oracle) or my re-implementation drifted.

This probe removes the guesswork: it calls the ACTUAL
probes._build_fixture_once, dumps the canonical text, and prints every
environment variable Houdini expands into default parms.

Run:  hython harness/notes/_m5_baseline_diag.py <out.txt>
"""
import hashlib
import json
import sys
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness" / "autoresearch"))

import probes  # noqa: E402

out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

FX = json.loads((REPO / "fixtures" / "solaris.basic.json").read_text(encoding="utf-8"))
stage = hou.node("/stage")

env = {}
for v in ("HIP", "HIPFILE", "HIPNAME", "JOB", "HOME", "OS", "HFS", "TEMP", "F", "OSTYPE"):
    try:
        env["$" + v] = hou.expandString("$" + v)
    except Exception as e:
        env["$" + v] = "ERR: %s" % e
env["cwd"] = str(Path.cwd())
env["build"] = hou.applicationVersionString()
env["hipFile"] = hou.hipFile.path()

res = probes._build_fixture_once(FX, stage)
canon = res.pop("canon_text", "")
res["sha256_recomputed"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
res["baseline_committed"] = FX["baseline"]["sha256"]
res["matches"] = (res["sha256_recomputed"] == FX["baseline"]["sha256"])

# Which canonical lines mention a machine-specific absolute path?
suspects = []
for i, line in enumerate(canon.splitlines()):
    low = line.lower()
    if ("c:/" in low or "c:\\" in low or "users" in low
            or "houdini2" in low or ".claude" in low or "worktree" in low):
        suspects.append({"line": i, "text": line.strip()[:200]})
res["env_dependent_lines"] = suspects[:20]
res["env_dependent_line_count"] = len(suspects)
res["canon_line_count"] = canon.count("\n")

if out_path is not None:
    out_path.write_text(canon, encoding="utf-8")
    res["canon_written_to"] = str(out_path)

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps({"env": env, "result": res}, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
