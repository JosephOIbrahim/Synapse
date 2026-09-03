# preflight_bp4.py - BP4 pre-arm proof: each rails tier's model alias resolves under --effort max
# on the installed Claude Code. Demonstrated, not inferred: one real `claude -p` ping per tier.
# Writes runs/<today>/preflight_bp4.json (the receipt rails_exec.json referee.why points at).
# Exit 0 = every tier resolved; exit 1 = at least one did not (the JSON says which; fix rails, re-run).
import datetime, json, subprocess, sys, time
from pathlib import Path

AF = Path(__file__).resolve().parent
TODAY = datetime.date.today().isoformat()
OUT = AF / "runs" / TODAY
OUT.mkdir(parents=True, exist_ok=True)
CHECKS = [("referee", "claude-fable-5-1"), ("reasoning", "claude-opus-4-8"), ("mechanical", "claude-haiku-4-5-20251001")]
EFFORT = "max"

def sh(cmd, timeout=150):
    return subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)

rows = []
for tier, model in CHECKS:
    cmd = f'claude --model {model} --effort {EFFORT} -p "Reply with exactly the word: ok"'
    t0 = time.time()
    try:
        r = sh(cmd)
        reply = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        rows.append({"tier": tier, "model": model, "effort": EFFORT, "check": cmd,
                     "resolved": bool(reply) and r.returncode == 0, "reply_observed": bool(reply),
                     "reply_head": reply[:80], "exit_code": r.returncode, "stderr_head": err[:240],
                     "wall_ms": int((time.time() - t0) * 1000)})
    except Exception as e:
        rows.append({"tier": tier, "model": model, "effort": EFFORT, "check": cmd, "resolved": False,
                     "error": repr(e), "wall_ms": int((time.time() - t0) * 1000)})

help_txt = sh("claude --help").stdout or ""
ver = (sh("claude --version").stdout or "").strip()
doc = {"run": "bp4-preflight", "date": TODAY, "claude_code_version": ver, "checks": rows,
       "effort_levels_in_help": ("max" in help_txt and "xhigh" in help_txt),
       "max_turns_flag_present": ("--max-turns" in help_txt),
       "unmeasured": {"tokens_per_ping": "UNKNOWN"},
       "generated_by": "Fable 5.1 CTO seat, DC session " + TODAY}
(OUT / "preflight_bp4.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
print(json.dumps(doc, indent=2))
sys.exit(0 if all(c.get("resolved") for c in rows) else 1)
