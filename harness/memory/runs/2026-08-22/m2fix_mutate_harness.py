"""Mutation harness for the PG-DRM kernel — M2 FIX leg (2026-08-22).

Applies one mutation at a time to pgdrm.py, runs the kernel test file, records
which tests went red, reverts, and byte-compares the restored source.

Supersedes harness/memory/runs/2026-08-21/m2_mutate_harness.py (16 mutations).
This set is 28: the original M1..M16 plus X17..X28 for the branches the
independent 26-mutation crucible harness found uncovered — including X25, the
mutation that SURVIVED the whole suite on e4730869.

NOTE ON SCOPE: each mutation runs tests/test_pgdrm_kernel.py, not the full
suite. pgdrm.py is imported by exactly one test module (it is deliberately not
wired into any port), so a mutation confined to pgdrm.py cannot reach any other
test. Verified: `grep -rl pgdrm --include="*.py" tests/ python/` returns exactly two
paths: tests/test_pgdrm_kernel.py and python/synapse/loop/pgdrm.py.
"""
import json
import subprocess
import sys
from pathlib import Path

WT = Path(r"C:\Users\User\synapse-m2-pgdrm-wt")
SRC = WT / "python" / "synapse" / "loop" / "pgdrm.py"
TEST = "tests/test_pgdrm_kernel.py"
ORIGINAL = SRC.read_text(encoding="utf-8")

# --- multi-line anchors ----------------------------------------------------
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
STR_GUARD = (
    '    if isinstance(tokens, str) or not isinstance(tokens, Iterable):\n'
    '        raise TypeError(f"{name} must be an iterable of str, got {tokens!r}")\n'
)
REC_GUARD = (
    "    if not isinstance(record, MemoryRecord):\n"
    '        raise TypeError(f"record must be a MemoryRecord, got {record!r}")\n'
)
RECORDS_GUARD = (
    "    if not isinstance(records, Iterable):\n"
    '        raise TypeError(f"records must be an iterable, got {records!r}")\n'
)
INF_BLOCK = (
    "    if math.isinf(lam) or math.isinf(age):\n"
    "        raw = 0.0 if (lam > 0.0 and age > 0.0) else 1.0\n"
    "    else:\n"
    "        raw = math.exp(-lam * age)\n"
)
POST_INIT = (
    "    def __post_init__(self) -> None:\n"
    "        # Materialize ONCE, at the entry point, before any decision logic can\n"
    "        # read the field. Without this a record built from a generator is a\n"
    "        # different value on its second read, and `filter_records` returns\n"
    "        # DROP then ALLOW for the SAME record inside a SINGLE call.\n"
    '        object.__setattr__(self, "tokens",\n'
    '                           _token_set("MemoryRecord.tokens", self.tokens))\n'
)
NAN_GUARD = (
    "    if math.isnan(v):\n"
    '        raise ValueError(f"{name} must be a real number, got NaN")\n'
)

MUTATIONS = [
    # ---- the 16 from the builder's original campaign (2026-08-21) ---------
    ("M1  decay sign flipped", "raw = math.exp(-lam * age)", "raw = math.exp(lam * age)"),
    ("M2  protected_floor clamp removed", "return max(raw, floor)", "return raw"),
    ("M3  floor becomes a ceiling (min)", "return max(raw, floor)", "return min(raw, floor)"),
    ("M4  floor read as eviction (D6 Reading B)", DECAY_LINE, READING_B),
    ("M5  contamination direction reversed", "foreign = rec_tokens - task_tokens", "foreign = task_tokens - rec_tokens"),
    ("M6  exact match becomes fuzzy substring", "    foreign = rec_tokens - task_tokens", FUZZY),
    ("M7  unmeasured distance passes", "        if distance is None:", "        if False:"),
    ("M8  distance comparison flipped", "if distance > d_threshold:", "if distance < d_threshold:"),
    ("M9  utility boundary made exclusive",
     "    if utility < u_threshold:\n        return Verdict(\n            key=record.key, decision=DROP, reason=REASON_DECAYED,",
     "    if utility <= u_threshold:\n        return Verdict(\n            key=record.key, decision=DROP, reason=REASON_DECAYED,"),
    ("M10 precedence: decay runs first", CONTAM_HDR, DECAY_FIRST),
    ("M11 impure import added", "import math\n", "import math\nimport time\n"),
    ("M12 filter order not preserved", "        for r in materialized\n", "        for r in reversed(materialized)\n"),
    ("M13 non-str tokens accepted", "    if bad:\n", "    if False:\n"),
    ("M14 bool guard removed",
     "    if isinstance(value, bool) or not isinstance(value, (int, float)):",
     "    if not isinstance(value, (int, float)):"),
    ("M15 NaN guard removed", NAN_GUARD, ""),
    ("M16 describe drops the reason",
     'return (f"{verdict.key}: {verdict.decision} ({verdict.reason}) "',
     'return (f"{verdict.key}: {verdict.decision} "'),

    # ---- the M2 FIX leg: one per branch the crucible found uncovered ------
    ("X17 one-shot guard removed from _token_set",
     "    _reiterable(name, tokens)\n    out = frozenset(tokens)",
     "    out = frozenset(tokens)"),
    ("X18 one-shot guard removed from filter_records(records)",
     '    materialized = tuple(_reiterable("records", records))',
     "    materialized = tuple(records)"),
    ("X19 MemoryRecord.__post_init__ deleted", POST_INIT, ""),
    ("X20 non-Iterable half of the str guard dropped",
     "    if isinstance(tokens, str) or not isinstance(tokens, Iterable):",
     "    if isinstance(tokens, str):"),
    ("X21 infinity branch deleted", INF_BLOCK, "    raw = math.exp(-lam * age)\n"),
    ("X22 MemoryRecord type guard deleted", REC_GUARD, ""),
    ("X23 records-iterable guard deleted", RECORDS_GUARD, ""),
    ("X24 one-shot detection inverted", "    if iter(value) is value:", "    if iter(value) is not value:"),
    ("X25 str guard deleted (SURVIVED on e4730869)", STR_GUARD, ""),
    ("X26 __post_init__ stores the raw value, never freezes it",
     '        object.__setattr__(self, "tokens",\n'
     '                           _token_set("MemoryRecord.tokens", self.tokens))',
     '        object.__setattr__(self, "tokens", self.tokens)'),
    ("X27 a single foreign token no longer contaminates", "    if foreign:", "    if len(foreign) > 1:"),
    ("X28 distance boundary made exclusive", "if distance > d_threshold:", "if distance >= d_threshold:"),
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
    results.append({"mutation": name,
                    "status": "RED" if (red or err) else "SURVIVED",
                    "n_red": len(red),
                    "summary": summary[-1] if summary else "",
                    "red_tests": red[:6], "errors": err[:2]})
    SRC.write_text(ORIGINAL, encoding="utf-8")

SRC.write_text(ORIGINAL, encoding="utf-8")
assert SRC.read_text(encoding="utf-8") == ORIGINAL, "REVERT FAILED"

survivors = [r for r in results if r["status"] != "RED"]
print(json.dumps({
    "total": len(results),
    "red": sum(1 for r in results if r["status"] == "RED"),
    "survivors": [r["mutation"] for r in survivors],
    "results": results,
}, indent=2))
