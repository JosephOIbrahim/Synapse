"""H3b mutation harness (R34) — the producer for the leg's mutation evidence.

Applies ONE deliberate defect at a time to the SHIPPED source, runs the H3b
pins, and records which go red. A pin that stays green under its own mutation
is a decoration; this script is the evidence that these are not.

Named WITHOUT a leading underscore on purpose: `.gitignore:50 _*.py` makes
underscore-prefixed producer scripts uncommittable (R132), and a number whose
producer cannot be committed has no producer path (Law 2).

Run:  python harness/notes/h3b_mutate.py
Restores every mutated file and asserts the restore before exiting.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RS = ROOT / "python" / "synapse" / "server" / "render_stop.py"
DT = ROOT / "python" / "synapse" / "panel" / "direct_tool.py"

MUTATIONS = [
    ("M1 drop dead-row guard from resolve_rop_pids", RS,
     'return [r["pid"] for r in rows\n            if r.get("alive") and token in (r.get("command") or "")]',
     'return [r["pid"] for r in rows\n            if token in (r.get("command") or "")]'),

    ("M2 drop houdini-pid scoping from rop_token", RS,
     'return "usdrender_%d_%d_" % (int(houdini_pid), int(session_id))',
     'return "_%d_" % (int(session_id),)'),

    ("M3 declare mantra partial output SAFE", RS,
     '"renderer": RENDERER_MANTRA,\n            "declared_output_safe": False,',
     '"renderer": RENDERER_MANTRA,\n            "declared_output_safe": True,'),

    ("M4 assume unmeasured renderer is safe", RS,
     '"renderer": renderer,\n        "declared_output_safe": None,',
     '"renderer": renderer,\n        "declared_output_safe": True,'),

    ("M5 reader loses its truncation fallback", DT,
     "    # 2. Truncated fragment -- recover by key name.\n    m = _NODE_RE.search(text)",
     "    return None\n    m = _NODE_RE.search(text)"),

    # M6's first form silently proved nothing: its anchor went stale when the
    # reader was repaired, and the harness reported "anchor not found" rather
    # than a green. That report is the reason this mutation is now correct.
    ("M6 reader guesses a default target instead of None", DT,
     "        if not _looks_like_a_file(candidate):\n            return candidate\n    return None",
     "        if not _looks_like_a_file(candidate):\n            return candidate\n    return '/tasks/topnet1'"),

    ("M7 reader accepts a FILE path as a node target", DT,
     "    tail = path.rsplit(\"/\", 1)[-1]\n    return \".\" in tail",
     "    tail = path.rsplit(\"/\", 1)[-1]\n    return False"),
]

PINS = ["tests/test_h3b_render_stop.py", "tests/test_h3b_panel_cancel.py"]


def run_pins():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *PINS, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    failed = sorted({ln.split("::")[1].split()[0]
                     for ln in r.stdout.splitlines() if ln.startswith("FAILED")})
    tail = [ln for ln in r.stdout.strip().splitlines() if "passed" in ln or "failed" in ln]
    return failed, (tail[-1] if tail else "")


def main():
    results = []
    failed, line = run_pins()
    results.append({"mutation": "BASELINE (unmutated)", "failed_count": len(failed),
                    "failed": failed, "summary": line})

    for name, path, old, new in MUTATIONS:
        src = path.read_text(encoding="utf-8")
        if old not in src:
            results.append({"mutation": name,
                            "ERROR": "anchor not found -- mutation NOT applied; "
                                     "this result proves nothing"})
            continue
        try:
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            f, l = run_pins()
            results.append({"mutation": name, "failed_count": len(f),
                            "failed": f, "summary": l})
        finally:
            path.write_text(src, encoding="utf-8")
            assert path.read_text(encoding="utf-8") == src, "RESTORE FAILED: %s" % path

    failed, line = run_pins()
    results.append({"mutation": "AFTER RESTORE", "failed_count": len(failed),
                    "failed": failed, "summary": line})
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
