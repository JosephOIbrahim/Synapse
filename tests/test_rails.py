# tests/test_rails.py - pins harness/rails.py.
#
# Covers the three things Target 6 names - cap arithmetic, UNKNOWN propagation,
# hard stop - plus the two invariants the crucible attacks: no ledger field is an
# estimate (every token field is a measured int or the literal UNKNOWN), and the
# cap can never fall back to unlimited (a turns floor is mandatory and always
# enforced). Pure Python, stock pytest, zero hou.
import json
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1] / "harness"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(HARNESS))

import rails  # noqa: E402
from rails import (  # noqa: E402
    Cap, Rails, BudgetExceeded, UNKNOWN, parse_cap, resolve_model,
    measure_transcript_tokens,
)

# The committed BP2-METER transcript fixtures (tests/fixtures/): one carries real
# message.usage records (12700 in, 470 out), one carries none at all.
TRANSCRIPT_WITH_USAGE = FIXTURES / "transcript_with_usage.jsonl"
TRANSCRIPT_NO_USAGE = FIXTURES / "transcript_no_usage.jsonl"


# --------------------------------------------------------------------------- #
# Cap parsing
# --------------------------------------------------------------------------- #
def test_parse_cap_bare_int_is_turns():
    assert parse_cap(8) == Cap(turns=8, tokens=None)


def test_parse_cap_string_forms():
    assert parse_cap("8") == Cap(turns=8)
    assert parse_cap("8turns") == Cap(turns=8)
    assert parse_cap("8legs") == Cap(turns=8)
    assert parse_cap("8turns,50000tokens") == Cap(turns=8, tokens=50000)
    assert parse_cap("50000tokens,8turns") == Cap(turns=8, tokens=50000)


def test_parse_cap_dict():
    assert parse_cap({"turns": 5, "tokens": 100}) == Cap(turns=5, tokens=100)
    assert parse_cap({"turns": 5}) == Cap(turns=5, tokens=None)


def test_tokens_only_cap_is_refused():
    # A tokens-only cap has no floor to fall back to when tokens go UNKNOWN.
    # Refusing it at construction is the never-unlimited guarantee.
    with pytest.raises(ValueError):
        parse_cap("50000tokens")
    with pytest.raises(ValueError):
        parse_cap({"tokens": 50000})


def test_cap_rejects_bool_and_negative():
    with pytest.raises(ValueError):
        Cap(turns=True)          # a bool is not a turn count
    with pytest.raises(ValueError):
        Cap(turns=-1)
    with pytest.raises(ValueError):
        Cap(turns=3, tokens=-1)


# --------------------------------------------------------------------------- #
# Cap arithmetic
# --------------------------------------------------------------------------- #
def test_turns_arithmetic_decrements_remaining(tmp_path):
    r = Rails(run="arith", cap="3turns", runs_dir=tmp_path)
    e1 = r.charge("L1", "m", wall_ms=5)
    assert e1["remaining"]["turns"] == 2
    e2 = r.charge("L2", "m", wall_ms=5)
    assert e2["remaining"]["turns"] == 1
    e3 = r.charge("L3", "m", wall_ms=5)
    assert e3["remaining"]["turns"] == 0
    assert r.turns_spent == 3


def test_token_arithmetic_when_measured(tmp_path):
    r = Rails(run="tokarith", cap="5turns,1000tokens", runs_dir=tmp_path)
    e1 = r.charge("L1", "m", tokens_in=100, tokens_out=50, wall_ms=1)
    assert e1["remaining"]["tokens"] == 1000 - 150
    assert e1["enforced_unit"] == "tokens"
    e2 = r.charge("L2", "m", tokens_in=200, tokens_out=0, wall_ms=1)
    assert e2["remaining"]["tokens"] == 1000 - 350


# --------------------------------------------------------------------------- #
# Hard stop
# --------------------------------------------------------------------------- #
def test_hard_stop_on_turns(tmp_path):
    r = Rails(run="stopturns", cap="1turns", runs_dir=tmp_path)
    r.charge("L1", "m", wall_ms=1)
    with pytest.raises(BudgetExceeded) as ei:
        r.charge("L2", "m", wall_ms=1)
    ledger = ei.value.ledger
    assert ledger["status"] == "blocked"
    assert ledger["reason"] == "budget"
    # the receipt names the refused leg and did NOT admit it
    refused = [e for e in ledger["legs"] if e["leg"] == "L2"]
    assert refused and refused[0]["admitted"] is False
    # and it was actually written to disk
    assert r.ledger_path().exists()
    on_disk = json.loads(r.ledger_path().read_text(encoding="utf-8"))
    assert on_disk["status"] == "blocked" and on_disk["reason"] == "budget"


def test_hard_stop_on_tokens(tmp_path):
    r = Rails(run="stoptok", cap="10turns,300tokens", runs_dir=tmp_path)
    r.charge("L1", "m", tokens_in=200, tokens_out=50, wall_ms=1)  # 250 <= 300 ok
    with pytest.raises(BudgetExceeded) as ei:
        r.charge("L2", "m", tokens_in=100, tokens_out=0, wall_ms=1)  # 350 > 300
    ledger = ei.value.ledger
    assert ledger["status"] == "blocked"
    assert ledger["reason"] == "budget"
    assert "tokens" in ledger["legs"][-1]["note"]


def test_zero_turn_cap_blocks_first_charge(tmp_path):
    r = Rails(run="zero", cap="0turns", runs_dir=tmp_path)
    with pytest.raises(BudgetExceeded):
        r.charge("L1", "m", wall_ms=1)
    assert r.status == "blocked"


def test_blocked_run_refuses_further_charges(tmp_path):
    r = Rails(run="stay", cap="0turns", runs_dir=tmp_path)
    with pytest.raises(BudgetExceeded):
        r.charge("L1", "m")
    with pytest.raises(BudgetExceeded):
        r.charge("L2", "m")   # a halted run never silently resumes


# --------------------------------------------------------------------------- #
# UNKNOWN propagation
# --------------------------------------------------------------------------- #
def test_unknown_tokens_downgrade_meter_and_fall_back_to_turns(tmp_path):
    # A charge with no measured tokens must render the token field UNKNOWN, mark
    # the run's token meter UNKNOWN, and fall enforcement back to the turns floor
    # - NOT to unlimited.
    r = Rails(run="unk", cap="2turns,999999tokens", runs_dir=tmp_path)
    e1 = r.charge("L1", "m", tokens_in=None, tokens_out=None, wall_ms=7)
    assert e1["tokens_in"] == UNKNOWN and e1["tokens_out"] == UNKNOWN
    assert e1["enforced_unit"] == "turns"
    assert e1["remaining"]["tokens"] == UNKNOWN
    assert r.token_meter == UNKNOWN
    # turns floor still bites despite a huge token ceiling and UNKNOWN tokens
    r.charge("L2", "m")
    with pytest.raises(BudgetExceeded):
        r.charge("L3", "m")


def test_partial_unknown_poisons_token_meter(tmp_path):
    # One measured charge then one UNKNOWN charge: the token meter can no longer
    # be trusted for the run, so remaining tokens becomes UNKNOWN thereafter.
    r = Rails(run="poison", cap="5turns,1000tokens", runs_dir=tmp_path)
    e1 = r.charge("L1", "m", tokens_in=100, tokens_out=0, wall_ms=1)
    assert e1["remaining"]["tokens"] == 900
    e2 = r.charge("L2", "m", tokens_in=None, tokens_out=None, wall_ms=1)
    assert e2["remaining"]["tokens"] == UNKNOWN
    assert r.token_meter == UNKNOWN


def test_never_unlimited_all_unknown(tmp_path):
    # The worst case: a token ceiling is set but EVERY charge is UNKNOWN. The run
    # must still be capped by turns, never uncapped.
    r = Rails(run="allunk", cap="3turns,1tokens", runs_dir=tmp_path)
    for i in range(3):
        r.charge(f"L{i}", "m")
    with pytest.raises(BudgetExceeded):
        r.charge("L3", "m")


# --------------------------------------------------------------------------- #
# No estimate - every token field is a measured int or the literal UNKNOWN
# --------------------------------------------------------------------------- #
def test_ledger_fields_are_measured_or_unknown_never_estimate(tmp_path):
    r = Rails(run="fields", cap="3turns", runs_dir=tmp_path)
    r.charge("L1", "claude-opus-4-8", tokens_in=10, tokens_out=2, wall_ms=42)
    r.charge("L2", "claude-haiku-4-5-20251001")  # unmeasured
    r.charge("L3", "m", wall_ms=0.021)  # a real sub-ms measured duration
    ledger = r.close()
    for e in ledger["legs"]:
        # token counts: measured int or UNKNOWN, never an estimate
        for f in ("tokens_in", "tokens_out"):
            v = e[f]
            assert v == UNKNOWN or (isinstance(v, int) and not isinstance(v, bool)), (
                f"{f}={v!r} is neither a measured int count nor the literal UNKNOWN")
        # wall_ms: measured duration (int or float) or UNKNOWN
        w = e["wall_ms"]
        assert w == UNKNOWN or (isinstance(w, (int, float)) and not isinstance(w, bool)), (
            f"wall_ms={w!r} is neither a measured number nor the literal UNKNOWN")
        # required per-entry ledger fields (Target 2)
        for f in ("leg", "model", "tokens_in", "tokens_out", "wall_ms", "cap", "remaining"):
            assert f in e


def test_ledger_is_the_receipt(tmp_path):
    r = Rails(run="receipt", cap="2turns", runs_dir=tmp_path)
    r.charge("L1", "m", wall_ms=1)
    ledger = r.close()
    assert ledger["status"] == "complete"
    assert ledger["run"] == "receipt"
    assert ledger["cap"] == {"turns": 2, "tokens": None}
    assert r.ledger_path().exists()
    assert r.ledger_path().name == "ledger_receipt.json"


# --------------------------------------------------------------------------- #
# Transcript measurement - the real source of truth, not a proxy
# --------------------------------------------------------------------------- #
def test_measure_transcript_sums_usage(tmp_path):
    p = tmp_path / "t.jsonl"
    lines = [
        {"message": {"usage": {"input_tokens": 100, "output_tokens": 20,
                               "cache_creation_input_tokens": 5,
                               "cache_read_input_tokens": 3}}},
        {"type": "noise"},  # a line with no usage is skipped, not fatal
        {"message": {"usage": {"input_tokens": 10, "output_tokens": 4}}},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    ti, to = measure_transcript_tokens(p)
    assert ti == 100 + 5 + 3 + 10
    assert to == 20 + 4


def test_measure_transcript_missing_is_unknown(tmp_path):
    ti, to = measure_transcript_tokens(tmp_path / "does_not_exist.jsonl")
    assert ti == UNKNOWN and to == UNKNOWN


def test_measure_transcript_no_usage_is_unknown(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text('{"type":"summary"}\n{bad json\n', encoding="utf-8")
    ti, to = measure_transcript_tokens(p)
    assert ti == UNKNOWN and to == UNKNOWN


def test_measure_transcript_malformed_usage_value_never_crashes(tmp_path):
    # a JSON-VALID record whose usage value is non-integer must be tolerated, not
    # fatal (crucible #1: a torn transcript never crashes). The bad field counts
    # as 0 for that field; the record still measures what it can.
    p = tmp_path / "malformed.jsonl"
    p.write_text("\n".join([
        json.dumps({"message": {"usage": {"input_tokens": "oops", "output_tokens": 10}}}),
        json.dumps({"message": {"usage": {"input_tokens": [1, 2], "output_tokens": {}}}}),
        json.dumps({"message": {"usage": {"input_tokens": 100, "output_tokens": 20}}}),
    ]) + "\n", encoding="utf-8")
    ti, to = measure_transcript_tokens(p)      # must not raise
    assert ti == 100 and to == 30              # 0(bad)+0(bad)+100, 10+0(bad)+20


def test_measure_transcript_empty_usage_is_unknown_not_zero(tmp_path):
    # an empty/field-absent usage dict must render UNKNOWN, never a measured (0,0)
    # (crucible #1: an absent token is UNKNOWN, never a fabricated 0).
    p = tmp_path / "emptyusage.jsonl"
    p.write_text("\n".join([
        json.dumps({"message": {"usage": {}}}),
        json.dumps({"message": {"usage": {"cache_read_input_tokens": 8000}}}),  # cache-only, no primary
    ]) + "\n", encoding="utf-8")
    ti, to = measure_transcript_tokens(p)
    assert ti == UNKNOWN and to == UNKNOWN


def test_settle_twice_is_idempotent_no_double_turn(tmp_path):
    # a second settle for the same leg updates in place, never opens a new turn
    # (the docstring's 'turns are never double-charged' must hold literally).
    r = Rails(run="resettle", cap="5turns,50000tokens", runs_dir=tmp_path)
    r.charge("L1", "m")
    r.settle("L1", "m", tokens_in=400, tokens_out=100, wall_ms=1)
    r.settle("L1", "m", tokens_in=500, tokens_out=200, wall_ms=2)  # re-settle
    assert r.turns_spent == 1
    assert len([e for e in r.legs if e["leg"] == "L1"]) == 1
    assert r.tokens_spent == 700                      # reflects the latest settle
    leg = [e for e in r.legs if e["leg"] == "L1"][0]
    assert leg["tokens_in"] == 500 and leg["tokens_out"] == 200 and leg["wall_ms"] == 2


def test_measured_tokens_flow_into_the_cap(tmp_path):
    # end-to-end: a measured transcript charge counts against a token ceiling
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(
        {"message": {"usage": {"input_tokens": 400, "output_tokens": 100}}}) + "\n",
        encoding="utf-8")
    ti, to = measure_transcript_tokens(p)
    r = Rails(run="e2e", cap="9turns,600tokens", runs_dir=tmp_path)
    e = r.charge("L1", "m", tokens_in=ti, tokens_out=to, wall_ms=1)
    assert e["remaining"]["tokens"] == 100  # 600 - 500
    assert e["enforced_unit"] == "tokens"


# --------------------------------------------------------------------------- #
# Execution seam lookup
# --------------------------------------------------------------------------- #
def test_resolve_model_reads_the_real_table():
    assert resolve_model("mechanical") == "claude-haiku-4-5-20251001"
    assert resolve_model("reasoning") == "claude-opus-4-8"


def test_resolve_model_unknown_tier_raises():
    with pytest.raises(KeyError):
        resolve_model("nonexistent-tier")


def test_seam_is_a_flat_or_nested_table(tmp_path):
    flat = tmp_path / "flat.json"
    flat.write_text(json.dumps({"tiers": {"mechanical": "m-model", "reasoning": "r-model"}}),
                    encoding="utf-8")
    assert resolve_model("mechanical", flat) == "m-model"


# --------------------------------------------------------------------------- #
# CLI - the surface harness/orchestrate.ps1 drives
# --------------------------------------------------------------------------- #
def _cli(*args, cwd):
    return subprocess.run([sys.executable, str(HARNESS / "rails.py"), *args],
                          capture_output=True, text=True, cwd=cwd)


def test_cli_open_charge_close_under_cap(tmp_path):
    runs = tmp_path / "runs"
    o = _cli("open", "--run", "cliok", "--date", "2026-08-31",
             "--runs-dir", str(runs), "--cap", "3turns", cwd=tmp_path)
    assert o.returncode == 0, o.stderr
    c = _cli("charge", "--run", "cliok", "--date", "2026-08-31",
             "--runs-dir", str(runs), "--leg", "L1", "--tier", "reasoning", cwd=tmp_path)
    assert c.returncode == 0, c.stderr
    cl = _cli("close", "--run", "cliok", "--date", "2026-08-31",
              "--runs-dir", str(runs), cwd=tmp_path)
    assert cl.returncode == 0
    ledger = json.loads((runs / "2026-08-31" / "ledger_cliok.json").read_text(encoding="utf-8"))
    assert ledger["status"] == "complete"
    assert ledger["legs"][0]["model"] == "claude-opus-4-8"  # tier resolved via seam


def test_cli_charge_blocks_with_exit_7(tmp_path):
    runs = tmp_path / "runs"
    _cli("open", "--run", "cliblock", "--date", "2026-08-31",
         "--runs-dir", str(runs), "--cap", "0turns", cwd=tmp_path)
    c = _cli("charge", "--run", "cliblock", "--date", "2026-08-31",
             "--runs-dir", str(runs), "--leg", "L1", "--model", "m", cwd=tmp_path)
    assert c.returncode == 7, (c.returncode, c.stdout, c.stderr)
    ledger = json.loads((runs / "2026-08-31" / "ledger_cliblock.json").read_text(encoding="utf-8"))
    assert ledger["status"] == "blocked" and ledger["reason"] == "budget"


def test_cli_charge_before_open_fails_closed(tmp_path):
    runs = tmp_path / "runs"
    c = _cli("charge", "--run", "never", "--date", "2026-08-31",
             "--runs-dir", str(runs), "--leg", "L1", "--model", "m", cwd=tmp_path)
    assert c.returncode == rails.EXIT_USAGE  # not opened -> refuse, never assume unlimited


# --------------------------------------------------------------------------- #
# BP2-METER T2 - the referee tier resolves through the SAME lookup seam
# --------------------------------------------------------------------------- #
def test_resolve_referee_prints_fable5():
    # acceptance #7: rails_exec.json carries the referee tier and it resolves to
    # claude-fable-5 through resolve_model - a lookup, nothing else decides a model
    assert resolve_model("referee") == "claude-fable-5"


def test_cli_resolve_positional_referee(tmp_path):
    # `python harness/rails.py resolve referee` -> claude-fable-5 (the exact
    # command orchestrate.ps1:363 runs to turn a leg's tier into a model)
    c = _cli("resolve", "referee", cwd=tmp_path)
    assert c.returncode == 0, c.stderr
    assert c.stdout.strip() == "claude-fable-5"


def test_cli_resolve_reasoning_is_byte_default(tmp_path):
    c = _cli("resolve", "reasoning", cwd=tmp_path)
    assert c.returncode == 0 and c.stdout.strip() == "claude-opus-4-8"


# --------------------------------------------------------------------------- #
# BP2-METER T1 - the POST-CLOSE SETTLE: measure from the transcript, in place
# --------------------------------------------------------------------------- #
def test_settle_measures_transcript_into_integers(tmp_path):
    # acceptance #1 (mechanism): a settled leg shows integer tokens traceable to
    # the named transcript JSONL, and the measured spend counts against the cap.
    r = Rails(run="settleint", cap="5turns,50000tokens", runs_dir=tmp_path)
    r.charge("L1", "claude-opus-4-8")               # pre-dispatch reservation (UNKNOWN)
    e = r.settle("L1", "claude-opus-4-8", tokens_in=12700, tokens_out=470,
                 wall_ms=8482, transcript=str(TRANSCRIPT_WITH_USAGE))
    assert e["tokens_in"] == 12700 and e["tokens_out"] == 470
    assert e["wall_ms"] == 8482
    assert e["transcript"] == str(TRANSCRIPT_WITH_USAGE)   # traceable provenance
    assert e["enforced_unit"] == "tokens"
    assert e["remaining"]["tokens"] == 50000 - 13170
    # ONE turn: the settle updated the reservation in place, never double-charged
    assert r.turns_spent == 1
    assert len([x for x in r.legs if x["leg"] == "L1"]) == 1


def test_settle_heals_the_pre_dispatch_unknown(tmp_path):
    # the pre-dispatch charge records UNKNOWN and poisons the sticky meter; the
    # settle re-derives it to "measured" because UNKNOWN means "not yet known".
    r = Rails(run="heal", cap="5turns,50000tokens", runs_dir=tmp_path)
    r.charge("L1", "m")                     # UNKNOWN -> sticky meter poisoned
    assert r.token_meter == UNKNOWN
    r.settle("L1", "m", tokens_in=400, tokens_out=100, wall_ms=1)
    assert r.token_meter == "measured"      # healed by the real measurement
    assert r.tokens_spent == 500


def test_settle_no_transcript_is_unknown_enforced_turns(tmp_path):
    # acceptance #2 (negative control): a settled leg whose transcript cannot be
    # resolved renders EVERY token field the literal UNKNOWN and enforced_unit
    # stays turns - never zero, never an estimate, never a pass.
    r = Rails(run="neg", cap="5turns,50000tokens", runs_dir=tmp_path)
    r.charge("L1", "claude-opus-4-8")
    e = r.settle("L1", "claude-opus-4-8", tokens_in=None, tokens_out=None,
                 wall_ms=None, transcript=None)
    assert e["tokens_in"] == UNKNOWN and e["tokens_out"] == UNKNOWN
    assert e["wall_ms"] == UNKNOWN
    assert e["enforced_unit"] == "turns"
    ledger = r.close()
    assert ledger["enforced_unit"] == "turns"
    assert ledger["token_meter"] == UNKNOWN


def test_settle_no_transcript_from_unreadable_fixture_is_unknown(tmp_path):
    # the same negative control driven through measure_transcript_tokens on the
    # committed no-usage fixture (a torn line, no usage record anywhere).
    ti, to = measure_transcript_tokens(TRANSCRIPT_NO_USAGE)
    assert ti == UNKNOWN and to == UNKNOWN


def test_committed_fixture_with_usage_measures(tmp_path):
    # acceptance #3: the committed transcript fixture with usage -> integers.
    ti, to = measure_transcript_tokens(TRANSCRIPT_WITH_USAGE)
    assert ti == 12700 and to == 470


def test_settle_crossing_token_ceiling_halts(tmp_path):
    # acceptance #4 (mechanism): a settle whose MEASURED spend crosses a tiny
    # tokens ceiling HALTS the run - status blocked, reason budget, enforced_unit
    # tokens. The leg already ran; it is not retroactively refused.
    r = Rails(run="halt", cap="5turns,100tokens", runs_dir=tmp_path)
    r.charge("L1", "claude-opus-4-8")
    r.settle("L1", "claude-opus-4-8", tokens_in=12700, tokens_out=470,
             wall_ms=5, transcript=str(TRANSCRIPT_WITH_USAGE))
    assert r.status == "blocked"
    ledger = r.close()
    assert ledger["status"] == "blocked"
    assert ledger["reason"] == "budget"
    assert ledger["enforced_unit"] == "tokens"


def test_settle_over_turns_floor_blocks(tmp_path):
    # a standalone settle with no reservation opens the turn, so the turns floor
    # still bites: never a settle that silently exceeds the cap.
    r = Rails(run="settleturns", cap="1turns", runs_dir=tmp_path)
    r.settle("L1", "m", tokens_in=1, tokens_out=1, wall_ms=1)
    with pytest.raises(BudgetExceeded):
        r.settle("L2", "m", tokens_in=1, tokens_out=1, wall_ms=1)
    assert r.status == "blocked"


def test_enforced_unit_flips_to_tokens_only_when_ceiling_and_measured(tmp_path):
    # acceptance #3: enforced_unit is "tokens" ONLY when a ceiling is set AND a
    # leg was measured; a ceiling with no measured tokens, or no ceiling, is "turns".
    # (a) ceiling + measured settle -> tokens
    r1 = Rails(run="euA", cap="3turns,9999tokens", runs_dir=tmp_path)
    r1.charge("L1", "m")
    r1.settle("L1", "m", tokens_in=10, tokens_out=2, wall_ms=1)
    assert r1.to_dict()["enforced_unit"] == "tokens"
    # (b) ceiling + UNKNOWN settle -> turns
    r2 = Rails(run="euB", cap="3turns,9999tokens", runs_dir=tmp_path)
    r2.charge("L1", "m")
    r2.settle("L1", "m", transcript=None)
    assert r2.to_dict()["enforced_unit"] == "turns"
    # (c) ceiling set but ZERO measured legs (empty run) -> turns, not tokens
    r3 = Rails(run="euC", cap="3turns,9999tokens", runs_dir=tmp_path)
    assert r3.to_dict()["enforced_unit"] == "turns"
    # (d) no ceiling at all -> turns
    r4 = Rails(run="euD", cap="3turns", runs_dir=tmp_path)
    r4.charge("L1", "m")
    r4.settle("L1", "m", tokens_in=10, tokens_out=2, wall_ms=1)
    assert r4.to_dict()["enforced_unit"] == "turns"


# --------------------------------------------------------------------------- #
# BP2-METER T4 / REFEREE bus finding - STATUS HONESTY: a live wave is not "done"
# --------------------------------------------------------------------------- #
def test_live_run_reads_open_not_complete(tmp_path):
    # a run still accepting charges must read "open" - the REFEREE finding: the
    # live ledger read "complete" while legs were alive. _persist keeps it "open".
    r = Rails(run="live", cap="5turns,50000tokens", runs_dir=tmp_path)
    r.charge("L1", "m")
    assert r._persist()["status"] == "open"
    # only an explicit close finalises to "complete"
    assert r.close()["status"] == "complete"


def test_cli_open_charge_persists_open(tmp_path):
    runs = tmp_path / "runs"
    _cli("open", "--run", "liveopen", "--date", "2026-09-01",
         "--runs-dir", str(runs), "--cap", "5turns,50000tokens", cwd=tmp_path)
    opened = json.loads((runs / "2026-09-01" / "ledger_liveopen.json").read_text(encoding="utf-8"))
    assert opened["status"] == "open"     # an opened-but-empty run is live, not done
    _cli("charge", "--run", "liveopen", "--date", "2026-09-01",
         "--runs-dir", str(runs), "--leg", "L1", "--tier", "reasoning", cwd=tmp_path)
    charged = json.loads((runs / "2026-09-01" / "ledger_liveopen.json").read_text(encoding="utf-8"))
    assert charged["status"] == "open"    # still live after a charge, never "complete"


# --------------------------------------------------------------------------- #
# BP2-METER T1 - the CLI surface orchestrate.ps1 drives at settle time
# --------------------------------------------------------------------------- #
def test_cli_settle_from_transcript_under_ceiling(tmp_path):
    runs = tmp_path / "runs"
    _cli("open", "--run", "cs", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--cap", "5turns,50000tokens", cwd=tmp_path)
    _cli("charge", "--run", "cs", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--leg", "L1", "--tier", "reasoning", cwd=tmp_path)
    s = _cli("settle", "--run", "cs", "--date", "2026-09-01", "--runs-dir", str(runs),
             "--leg", "L1", "--transcript", str(TRANSCRIPT_WITH_USAGE),
             "--wall_ms", "8482", cwd=tmp_path)
    assert s.returncode == 0, s.stderr
    led = json.loads((runs / "2026-09-01" / "ledger_cs.json").read_text(encoding="utf-8"))
    leg = [e for e in led["legs"] if e["leg"] == "L1"][0]
    assert leg["tokens_in"] == 12700 and leg["tokens_out"] == 470 and leg["wall_ms"] == 8482
    assert leg["transcript"].endswith("transcript_with_usage.jsonl")
    assert led["totals"]["tokens_in"] == 12700 and led["totals"]["tokens_out"] == 470
    assert led["enforced_unit"] == "tokens" and led["token_meter"] == "measured"
    assert led["status"] == "open"    # a single measured leg does not finish the wave


def test_cli_settle_crossing_tiny_ceiling_exits_7(tmp_path):
    # acceptance #4 (CLI/receipt): a tiny tokens ceiling halts after settle -
    # exit 7, ledger status blocked, reason budget, enforced_unit tokens.
    runs = tmp_path / "runs"
    _cli("open", "--run", "ct", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--cap", "5turns,100tokens", cwd=tmp_path)
    _cli("charge", "--run", "ct", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--leg", "L1", "--tier", "reasoning", cwd=tmp_path)
    s = _cli("settle", "--run", "ct", "--date", "2026-09-01", "--runs-dir", str(runs),
             "--leg", "L1", "--transcript", str(TRANSCRIPT_WITH_USAGE), cwd=tmp_path)
    assert s.returncode == rails.EXIT_BLOCKED, (s.returncode, s.stdout, s.stderr)
    led = json.loads((runs / "2026-09-01" / "ledger_ct.json").read_text(encoding="utf-8"))
    assert led["status"] == "blocked" and led["reason"] == "budget"
    assert led["enforced_unit"] == "tokens"


def test_cli_settle_no_transcript_is_unknown(tmp_path):
    # acceptance #2 (CLI): settle with no --transcript -> every token field UNKNOWN
    runs = tmp_path / "runs"
    _cli("open", "--run", "cu", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--cap", "5turns,50000tokens", cwd=tmp_path)
    _cli("charge", "--run", "cu", "--date", "2026-09-01", "--runs-dir", str(runs),
         "--leg", "L1", "--tier", "reasoning", cwd=tmp_path)
    s = _cli("settle", "--run", "cu", "--date", "2026-09-01", "--runs-dir", str(runs),
             "--leg", "L1", "--model", "claude-opus-4-8", cwd=tmp_path)
    assert s.returncode == 0, s.stderr
    led = json.loads((runs / "2026-09-01" / "ledger_cu.json").read_text(encoding="utf-8"))
    leg = [e for e in led["legs"] if e["leg"] == "L1"][0]
    assert leg["tokens_in"] == UNKNOWN and leg["tokens_out"] == UNKNOWN and leg["wall_ms"] == UNKNOWN
    assert led["enforced_unit"] == "turns" and led["token_meter"] == UNKNOWN
