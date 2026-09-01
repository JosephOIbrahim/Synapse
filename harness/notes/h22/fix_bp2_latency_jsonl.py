# fix_bp2_latency_jsonl.py - the latency artifacts are JSON Lines by contract; give them the
# extension that says so, so test_lint_all_harness_json_parses stops (rightly) refusing them.
import re, subprocess
from pathlib import Path
WT = Path(r"C:\Users\User\SYNAPSE\.claude\worktrees\bp2-latency")
runs = WT / "harness" / "battleplan" / "runs" / "2026-09-01"
for old in ("memory_latency_hython.json", "memory_latency_hython_provisioned.json"):
    subprocess.run(["git", "-C", str(WT), "mv", f"harness/battleplan/runs/2026-09-01/{old}",
                    f"harness/battleplan/runs/2026-09-01/{old[:-5]}.jsonl"], check=True)
edits = {
    WT / "harness/battleplan/notes/memory_latency_probe.py": [
        (r'"memory_latency_%s%s\.json"', '"memory_latency_%s%s.jsonl"'),
        (r"memory_latency_hython\.json", "memory_latency_hython.jsonl"),
        (r"memory_latency_gui\.json", "memory_latency_gui.jsonl"),
        (r"memory_latency_<env>\.json", "memory_latency_<env>.jsonl"),
    ],
    WT / ".synapse/contracts/memory-latency-receipt.yaml": [
        (r"memory_latency_hython\.json\b", "memory_latency_hython.jsonl"),
        (r"memory_latency_hython_provisioned\.json\b", "memory_latency_hython_provisioned.jsonl"),
        (r"memory_latency_gui\.json\b", "memory_latency_gui.jsonl"),
        (r"memory_latency_<env>\.json\b", "memory_latency_<env>.jsonl"),
    ],
}
for path, subs in edits.items():
    s = path.read_text(encoding="utf-8"); n = 0
    for pat, rep in subs:
        s, k = re.subn(pat, rep, s); n += k
    path.write_text(s, encoding="utf-8")
    print(f"{path.relative_to(WT)}: {n} replacements")
for p in runs.glob("memory_latency_*.jsonl"):
    print("now:", p.name)
