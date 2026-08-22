"""Mutation harness for the PG-DRM kernel. Applies one mutation at a time to
pgdrm.py, runs the kernel test file, records which tests went red, reverts."""
import json
import subprocess
import sys
from pathlib import Path

WT = Path(r"C:\Users\User\synapse-m2-pgdrm-wt")
SRC = WT / "python" / "synapse" / "loop" / "pgdrm.py"
TEST = "tests/test_pgdrm_kernel.py"
ORIGINAL = SRC.read_text(encoding="utf-8")

DECAY_LINE = "    utility = decay_utility(lam, age, floor)"
READING_B = (
    "    utility = decay_utility(lam, age, 0.0)\n"
    "    if utility < floor:\n"
    "        return Verdict(key=record.key, decision=DROP,\n"
    "                       reason=REASON_DECAYED, utility=utility, detail={})"
)
CONTAM_HDR = "    # 1 - contamination: exact set difference, no fuzzy match anywhere."
DECAY_FIRST = (
    "    if utility < u_threshold:\n"
    "        return Verdict(key=record.key, decision=DROP,\n"
    "                       reason=REASON_DECAYED, utility=utility, detail={})\n"
    "    # 1 - contamination"
)
FUZZY = (
    "    foreign = frozenset(t for t in rec_tokens if not any(\n"
    "        t.casefold() in o.casefold() or o.casefold() in t.casefold()\n"
    "        for o in task_tokens))"
)

MUTATIONS = [
    ("M1  decay sign flipped",            "raw = math.exp(-lam * age)", "raw = math.exp(lam * age)"),
    ("M2  protected_floor clamp removed", "return max(raw, floor)", "return raw"),
    ("M3  floor becomes a ceiling (min)", "return max(raw, floor)", "return min(raw, floor)"),
    ("M4  floor read as eviction (D6 Reading B)", DECAY_LINE, READING_B),
    ("M5  contamination direction reversed", "foreign = rec_tokens - task_tokens", "foreign = task_tokens - rec_tokens"),
    ("M6  exact match becomes fuzzy substring", "    foreign = rec_tokens - task_tokens", FUZZY),
    ("M7  unmeasured distance passes",     "        if distance is None:", "        if False:"),
    ("M8  distance comparison flipped",    "if distance > d_threshold:", "if distance < d_threshold:"),
    ("M9  utility boundary made exclusive",
     "    if utility < u_threshold:\n        return Verdict(\n            key=record.key, decision=DROP, reason=REASON_DECAYED,",
     "    if utility <= u_threshold:\n        return Verdict(\n            key=record.key, decision=DROP, reason=REASON_DECAYED,"),
    ("M10 precedence: decay runs first",   CONTAM_HDR, DECAY_FIRST),
    ("M11 impure import added",            "import math\n", "import math\nimport time\n"),
    ("M12 filter order not preserved",     "        for r in records\n", "        for r in reversed(records)\n"),
    ("M13 non-str tokens accepted",        "    if bad:\n", "    if False:\n"),
    ("M15 NaN guard removed",
     "    if math.isnan(v):\n        raise ValueError(f\"{name} must be a real number, got NaN\")\n",
     ""),
    ("M16 describe drops the reason",
     "return (f\"{verdict.key}: {verdict.decision} ({verdict.reason}) \"",
     "return (f\"{verdict.key}: {verdict.decision} \""),
    ("M14 bool guard removed",
     "    if isinstance(value, bool) or not isinstance(value, (int, float)):",
     "    if not isinstance(value, (int, float)):"),
]

results = []
for name, old, new in MUTATIONS:
    count = ORIGINAL.count(old)
    if count != 1:
        results.append({"mutation": name, "status": "PATCH_MISS",
                        "occurrences": count, "red_tests": []})
        continue
    SRC.write_text(ORIGINAL.replace(old, new, 1), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--no-header",
         "-p", "no:cacheprovider", "--tb=no"],
        cwd=WT, capture_output=True, text=True)
    red = sorted({ln.split(" - ")[0].replace("FAILED ", "").strip()
                  for ln in proc.stdout.splitlines() if ln.startswith("FAILED")})
    err = [ln for ln in proc.stdout.splitlines() if ln.startswith("ERROR")]
    summary = [ln for ln in proc.stdout.splitlines()
               if " passed" in ln or " failed" in ln or " error" in ln]
    results.append({"mutation": name, "status": "RED" if (red or err) else "SURVIVED",
                    "n_red": len(red), "summary": summary[-1] if summary else "",
                    "red_tests": red[:6], "errors": err[:2]})
    SRC.write_text(ORIGINAL, encoding="utf-8")

SRC.write_text(ORIGINAL, encoding="utf-8")
assert SRC.read_text(encoding="utf-8") == ORIGINAL, "REVERT FAILED"
print(json.dumps(results, indent=2))
