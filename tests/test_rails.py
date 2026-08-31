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
sys.path.insert(0, str(HARNESS))

import rails  # noqa: E402
from rails import (  # noqa: E402
    Cap, Rails, BudgetExceeded, UNKNOWN, parse_cap, resolve_model,
    measure_transcript_tokens,
)


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
