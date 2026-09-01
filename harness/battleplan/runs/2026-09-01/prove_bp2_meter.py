# prove_bp2_meter.py - BP2-METER acceptance #1 (measured ledger) + #4 (halt).
#
# Drives the rails.py CLI (the exact surface orchestrate.ps1's Rails-Settle uses)
# to produce three receipts under harness/battleplan/runs/2026-09-01/:
#   A) ledger_bp2-meter-settle.json   - a leg settled from the COMMITTED fixture
#      transcript -> integer tokens_in/out/wall_ms, traceable to a named JSONL
#      (reproducible; acceptance #1).
#   B) ledger_bp2-meter-halt.json     - a tiny tokens ceiling: a settle whose
#      MEASURED spend crosses it -> status blocked, reason budget, enforced tokens
#      (acceptance #4).
#   C) bp2_meter_proof.json           - a proof summary that ALSO settles this
#      METER leg's OWN live session transcript (the strongest, real evidence: the
#      real token spend of a real Claude Code session), recorded point-in-time.
#
# Pure stdlib. Writes only under runs/2026-09-01/. Re-runnable: A + B are
# deterministic; C records whatever the live transcript measures now.
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                        # worktree root
RAILS = ROOT / "harness" / "rails.py"
RUNS = ROOT / "harness" / "battleplan" / "runs"
DATE = "2026-09-01"
FIX = ROOT / "tests" / "fixtures" / "transcript_with_usage.jsonl"
sys.path.insert(0, str(ROOT / "harness"))
import rails  # noqa: E402


def cli(sub, *a):
    # the subcommand comes FIRST; --date/--runs-dir are subparser flags, so they
    # must follow the subcommand, not precede it.
    return subprocess.run([sys.executable, str(RAILS), sub, "--date", DATE,
                           "--runs-dir", str(RUNS), *map(str, a)],
                          capture_output=True, text=True)


def ledger(run):
    return json.loads((RUNS / DATE / f"ledger_{run}.json").read_text(encoding="utf-8"))


def leg_of(led, leg):
    return [e for e in led["legs"] if e["leg"] == leg][0]


# ---- A) measured ledger from the committed fixture (acceptance #1) -----------
cli("open", "--run", "bp2-meter-settle", "--cap", "10turns,500000tokens")
cli("charge", "--run", "bp2-meter-settle", "--leg", "BP2-METER", "--tier", "reasoning")
cli("settle", "--run", "bp2-meter-settle", "--leg", "BP2-METER",
    "--transcript", str(FIX), "--wall_ms", "8482")
A = ledger("bp2-meter-settle")
la = leg_of(A, "BP2-METER")
assert isinstance(la["tokens_in"], int) and isinstance(la["tokens_out"], int)
assert isinstance(la["wall_ms"], int) and la["transcript"].endswith("transcript_with_usage.jsonl")

# ---- B) tiny ceiling -> halt after settle (acceptance #4) --------------------
cli("open", "--run", "bp2-meter-halt", "--cap", "10turns,100tokens")
cli("charge", "--run", "bp2-meter-halt", "--leg", "BP2-METER", "--tier", "reasoning")
b = cli("settle", "--run", "bp2-meter-halt", "--leg", "BP2-METER", "--transcript", str(FIX))
B = ledger("bp2-meter-halt")
assert B["status"] == "blocked" and B["reason"] == "budget" and B["enforced_unit"] == "tokens"
assert b.returncode == rails.EXIT_BLOCKED

# ---- C) settle this METER leg's OWN live session transcript (real evidence) --
# The worktree path -> Claude Code projects slug (every :\/. -> '-'); the newest
# *.jsonl there is this leg's real session. Measured, never estimated.
wt = ROOT  # this leg runs in the worktree that IS ROOT
slug = "".join("-" if c in ":\\/." else c for c in str(wt))
projdir = Path(os.environ["USERPROFILE"]) / ".claude" / "projects" / slug
real = None
if projdir.exists():
    js = sorted(projdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    real = str(js[0]) if js else None
real_measure = None
if real:
    ti, to = rails.measure_transcript_tokens(real)
    real_measure = {"transcript": real, "tokens_in": ti, "tokens_out": to,
                    "measured_int": isinstance(ti, int) and isinstance(to, int)}

summary = {
    "leg": "BP2-METER", "date": DATE,
    "acceptance_1_fixture": {
        "ledger": "runs/2026-09-01/ledger_bp2-meter-settle.json",
        "tokens_in": la["tokens_in"], "tokens_out": la["tokens_out"],
        "wall_ms": la["wall_ms"], "transcript": la["transcript"],
        "enforced_unit": A["enforced_unit"], "token_meter": A["token_meter"],
        "status": A["status"],
        "note": "integer tokens measured from a named transcript JSONL; status 'open' = live (REFEREE honesty)",
    },
    "acceptance_4_halt": {
        "ledger": "runs/2026-09-01/ledger_bp2-meter-halt.json",
        "status": B["status"], "reason": B["reason"],
        "enforced_unit": B["enforced_unit"], "cap": B["cap"],
        "settle_exit_code": b.returncode,
        "note": "measured spend crossed a 100-token ceiling at settle -> halt",
    },
    "real_leg_transcript_measurement": real_measure or {
        "note": "this METER leg's live transcript not resolvable at proof time; would settle UNKNOWN"},
    "generated_by": "prove_bp2_meter.py",
}
(HERE / "bp2_meter_proof.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
