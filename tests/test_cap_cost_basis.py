# test_cap_cost_basis.py - BP9-CAPBASIS (ruling 5): the 70M wave cap is enforced
# COST-WEIGHTED; the ledger shows the raw fields, the rails total (1x, unchanged),
# the cost-weighted total and max_ctx.
#
# Every test BITES:
#   (a) a synthetic transcript with known counts pins the exact weighted arithmetic
#   (b) the cap halts at the ceiling on the COST basis and NOT on the rails basis,
#       in both directions (rails over / cost under -> admitted; rails under /
#       cost over -> refused)
#   (c) the three BP8 transcripts, replayed if present, pin the rails total at
#       79.8M +/- 1% (regression: the rails basis is unchanged) and put the
#       cost-weighted total inside 10M..14M
#   (d) jev_client.ask records the prompt token count when the SDK response
#       exposes usage, and None stays None
# No model is named anywhere in this file (invariant 1).
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "harness"
for p in (HARNESS, HARNESS / "jev", HARNESS / "battleplan"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import rails  # noqa: E402
from rails import (  # noqa: E402
    DEFAULT_COST_WEIGHTS, UNKNOWN, BudgetExceeded, Rails, cost_weighted,
    load_cost_weights, measure_transcript_tokens, measure_transcript_usage,
)
import meter_transcript  # noqa: E402
import jev_client as jc  # noqa: E402

SEAM = HARNESS / "rails_exec.json"
BP8_RUNS = Path(os.environ.get("SYNAPSE_BP8_RUNS_DIR") or (HARNESS / "battleplan" / "runs" / "2026-09-20"))


def _write(path: Path, records) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _usage(i, cc, cr, o):
    return {"input_tokens": i, "cache_creation_input_tokens": cc,
            "cache_read_input_tokens": cr, "output_tokens": o}


# --------------------------------------------------------------- the weights table
def test_cost_weights_table_is_the_seam():
    """rails_exec.json carries the four weights and load_cost_weights reads them.
    Mutation: drop a key from the table or hard-code weights in rails.py -> RED."""
    table = json.loads(SEAM.read_text(encoding="utf-8"))["cost_weights"]
    assert {k: table[k] for k in ("input", "cache_create", "cache_read", "output")} == \
        {"input": 1.0, "cache_create": 1.25, "cache_read": 0.1, "output": 5.0}
    assert load_cost_weights(SEAM) == DEFAULT_COST_WEIGHTS


def test_load_cost_weights_missing_table_falls_back_to_defaults(tmp_path):
    seam = tmp_path / "seam.json"
    seam.write_text(json.dumps({"tiers": {}}), encoding="utf-8")
    assert load_cost_weights(seam) == DEFAULT_COST_WEIGHTS
    seam.write_text(json.dumps({"cost_weights": {"output": 7}}), encoding="utf-8")
    assert load_cost_weights(seam) == {**DEFAULT_COST_WEIGHTS, "output": 7.0}


# ------------------------------------------------------ (a) exact weighted arithmetic
def test_synthetic_transcript_exact_weighted_arithmetic(tmp_path):
    """Known counts -> exact raw fields, rails total, cost-weighted total, max_ctx.
    Mutation: any weight, any field, or max_ctx computed as a sum -> RED."""
    p = _write(tmp_path / "t.jsonl", [
        {"message": {"usage": _usage(100, 200, 1000, 10)}},
        {"type": "noise"},
        {"message": {"usage": {"input_tokens": 50, "cache_read_input_tokens": 4000,
                               "output_tokens": 20}}},  # cache_creation absent -> 0
    ])
    raw = measure_transcript_usage(p)
    assert raw["input_tokens"] == 150
    assert raw["cache_creation_input_tokens"] == 200
    assert raw["cache_read_input_tokens"] == 5000
    assert raw["output_tokens"] == 30
    assert raw["rails_total"] == 150 + 200 + 5000 + 30 == 5380
    assert raw["max_ctx"] == max(100 + 200 + 1000, 50 + 0 + 4000) == 4050
    assert raw["messages_with_usage"] == 2
    # cost = 150*1.0 + 200*1.25 + 5000*0.1 + 30*5.0 = 150 + 250 + 500 + 150
    assert cost_weighted(raw, DEFAULT_COST_WEIGHTS) == 1050
    # the rails pair is unchanged (regression on the pre-ruling-5 basis)
    assert measure_transcript_tokens(p) == (5350, 30)
    # the meter script prints both bases from the same numbers
    m = meter_transcript.meter(p, DEFAULT_COST_WEIGHTS)
    assert (m["rails_total"], m["cost_weighted"], m["max_ctx"]) == (5380, 1050, 4050)


def test_meter_absent_transcript_is_unknown_never_zero(tmp_path):
    m = meter_transcript.meter(tmp_path / "nope.jsonl")
    assert m["rails_total"] == UNKNOWN and m["cost_weighted"] == UNKNOWN and m["max_ctx"] == UNKNOWN


# ------------------------------------------- (b) the cap halts on COST, not on rails
def test_settle_halts_on_cost_weighted_not_on_rails(tmp_path):
    """Two legs whose RAILS total crosses the ceiling on the first settle but whose
    COST-weighted total only crosses on the second. Mutation: compare tokens_spent
    (rails) instead of cost_spent in settle -> the first settle halts -> RED."""
    r = Rails(run="costhalt", cap="5turns,1000tokens", runs_dir=tmp_path, seam_path=SEAM)
    u = _usage(100, 0, 1850, 50)  # rails 2000 (> cap); cost 100 + 0 + 185 + 250 = 535 (< cap)
    r.charge("L1", "m")
    e1 = r.settle("L1", "m", tokens_in=1950, tokens_out=50, usage=u, max_ctx=1950, wall_ms=1)
    assert e1["cost_weighted"] == 535 and e1["cost_basis"] == "weighted"
    assert e1["tokens_in"] + e1["tokens_out"] == 2000          # rails recorded, unchanged
    assert r.status == "open", "rails 2000 > 1000 must NOT halt: the cap is cost-weighted"
    assert e1["remaining"]["cost_weighted"] == 1000 - 535
    assert e1["remaining"]["enforced_on"] == "cost_weighted"
    r.charge("L2", "m")
    e2 = r.settle("L2", "m", tokens_in=1950, tokens_out=50, usage=u, max_ctx=1950, wall_ms=1)
    assert r.status == "blocked" and r.reason == "budget" and r.blocked_on == "tokens"
    assert r.cost_spent == 1070 and r.tokens_spent == 4000
    assert "cost-weighted spend 1070" in e2["note"]
    led = r.to_dict()
    assert led["totals"]["rails_total"] == 4000
    assert led["totals"]["cost_weighted"] == 1070
    assert led["totals"]["max_ctx"] == 1950
    assert led["totals"]["usage"] == _usage(200, 0, 3700, 100)
    assert led["totals"]["enforced_on"] == "cost_weighted"


def test_charge_refuses_on_cost_weighted_even_when_rails_is_under(tmp_path):
    """The other direction: output-heavy usage whose rails total is UNDER the ceiling
    but whose cost-weighted total is OVER. Mutation: compare rails in charge -> the
    charge is admitted -> RED."""
    r = Rails(run="costrefuse", cap="5turns,1000tokens", runs_dir=tmp_path, seam_path=SEAM)
    u = _usage(10, 0, 0, 300)  # rails 310 (< cap); cost 10 + 1500 = 1510 (> cap)
    with pytest.raises(BudgetExceeded) as ei:
        r.charge("L1", "m", tokens_in=10, tokens_out=300, usage=u, max_ctx=10, wall_ms=1)
    refused = ei.value.ledger["legs"][-1]
    assert refused["admitted"] is False and refused["cost_weighted"] == 1510
    assert "1510 cost-weighted tokens > 1000" in refused["note"]


def test_cli_settle_halts_on_cost_not_rails(tmp_path):
    """Through the CLI the orchestrator drives: a transcript whose rails total is over
    a tiny ceiling but whose cost is under settles with exit 0 and status open."""
    import subprocess
    t = _write(tmp_path / "t.jsonl", [{"message": {"usage": _usage(100, 0, 1850, 50)}}])
    runs = tmp_path / "runs"

    def cli(*a):
        return subprocess.run([sys.executable, str(HARNESS / "rails.py"), *a],
                              capture_output=True, text=True, cwd=tmp_path)

    cli("open", "--run", "cc", "--date", "2026-09-21", "--runs-dir", str(runs),
        "--seam", str(SEAM), "--cap", "5turns,1000tokens")
    cli("charge", "--run", "cc", "--date", "2026-09-21", "--runs-dir", str(runs),
        "--seam", str(SEAM), "--leg", "L1", "--model", "m")
    s = cli("settle", "--run", "cc", "--date", "2026-09-21", "--runs-dir", str(runs),
            "--seam", str(SEAM), "--leg", "L1", "--transcript", str(t))
    assert s.returncode == rails.EXIT_OK, (s.returncode, s.stdout, s.stderr)
    assert "cost_weighted=535" in s.stdout and "rails_total=2000" in s.stdout
    led = json.loads((runs / "2026-09-21" / "ledger_cc.json").read_text(encoding="utf-8"))
    assert led["status"] == "open"
    assert led["totals"]["tokens_in"] == 1950 and led["totals"]["tokens_out"] == 50
    assert led["totals"]["cost_weighted"] == 535 and led["totals"]["max_ctx"] == 1950
    assert led["legs"][0]["usage"] == _usage(100, 0, 1850, 50)


def test_explicit_tokens_without_raw_usage_are_labelled_rails_basis(tmp_path):
    """A charge with only --tokens-in/out (no transcript) has no raw fields, so the
    enforced spend is the rails sum, labelled 'rails' - never silently weighted."""
    r = Rails(run="railsbasis", cap="5turns,1000tokens", runs_dir=tmp_path, seam_path=SEAM)
    e = r.charge("L1", "m", tokens_in=400, tokens_out=100, wall_ms=1)
    assert e["cost_basis"] == "rails" and e["cost_weighted"] == 500 and e["usage"] == UNKNOWN
    assert r.to_dict()["totals"]["cost_basis"] == "rails"


# --------------------------------------------------- (c) the BP8 replay regression pin
def _bp8_ledger_and_transcripts():
    ledgers = sorted(BP8_RUNS.glob("ledger_orch_*.json")) if BP8_RUNS.exists() else []
    for lp in reversed(ledgers):
        led = json.loads(lp.read_text(encoding="utf-8"))
        legs = [l for l in led.get("legs", []) if l.get("admitted") and l.get("transcript")]
        if len(legs) == 3:
            return led, legs
    return None, []


def test_bp8_replay_rails_total_unchanged_and_cost_weighted_in_band():
    """Replays the three BP8 transcripts: rails total 79.8M +/- 1% (the pre-ruling-5
    basis is unchanged; the ledger settled 79,818,201) and the cost-weighted total
    pinned to what the weights MEASURE. Skips with a reason when the ledger or any
    transcript is absent (they live outside the repo; set SYNAPSE_BP8_RUNS_DIR).

    REFUTED BRIEF FIGURE (BP9-CAPBASIS, measured 2026-09-21): the brief expected
    cost-weighted inside 10M..14M. Under the ruling-5 weights the three transcripts
    decompose to input 4,354 x 1.0 + cache_creation 3,562,469 x 1.25 +
    cache_read 74,611,466 x 0.1 + output 1,639,912 x 5.0 = 20,118,147. A control
    pinned to the brief's band would go red on the real numbers and green only
    while skipping, so the pin below is the measured value +/- 1%, not the band."""
    led, legs = _bp8_ledger_and_transcripts()
    if led is None:
        pytest.skip(f"no BP8 orch ledger with 3 settled legs under {BP8_RUNS}")
    missing = [l["transcript"] for l in legs if not Path(l["transcript"]).exists()]
    if missing:
        pytest.skip(f"BP8 transcript(s) absent on this machine: {missing}")
    w = load_cost_weights(SEAM)
    rails_total = cost_total = 0
    max_ctx = 0
    for l in legs:
        raw = measure_transcript_usage(l["transcript"])
        assert raw is not None
        # per-leg regression pin: the rails basis reproduces what the BP8 ledger settled
        assert raw["rails_total"] == l["tokens_in"] + l["tokens_out"]
        rails_total += raw["rails_total"]
        cost_total += cost_weighted(raw, w)
        max_ctx = max(max_ctx, raw["max_ctx"])
    assert abs(rails_total - 79_800_000) <= 0.01 * 79_800_000, rails_total
    assert rails_total == led["totals"]["tokens_in"] + led["totals"]["tokens_out"]
    assert abs(cost_total - 20_118_147) <= 0.01 * 20_118_147, cost_total
    assert 0 < max_ctx < rails_total
    # the ruling's consequence, on the real numbers: 70M halts on rails, not on cost
    assert rails_total > 70_000_000 and cost_total < 70_000_000


# ------------------------------------------- (d) jev ledger rows carry prompt tokens
class _Resp:
    def __init__(self, usage):
        self.choices, self.scores, self.nouls = {}, {}, {}
        self.request_id = "req-1"
        if usage is not None:
            self.usage = usage


class _Usage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o


def _client_returning(resp):
    class _C:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def system_one(self, **kw):
            return resp
    return _C


@pytest.mark.parametrize("usage,expect_in,expect_out", [
    (_Usage(120, 7), 120, 7),
    (None, None, None),
])
def test_jev_ask_records_prompt_tokens_when_exposed(tmp_path, monkeypatch, usage, expect_in, expect_out):
    """ask() writes input_tokens from resp.usage.input_tokens; absent usage stays None.
    Mutation: drop the usage read in ask() or default it to 0 -> RED."""
    monkeypatch.setattr(jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setenv("SYNAPSE_JEV", "on")
    monkeypatch.setattr(jc, "api_key", lambda: "test-key")
    _mk = lambda **kw: dict(kw)  # noqa: E731
    monkeypatch.setattr(jc, "_sdk", lambda: (_client_returning(_Resp(usage)), _mk, _mk, _mk))
    res = jc.ask({"x": 1}, {"q": {"type": "noul", "instructions": "?"}},
                 wave="t", guard="route", leg="T")
    assert res is not None and res["request_id"] == "req-1"
    rows = [json.loads(x) for x in (tmp_path / "t.route.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    row = rows[-1]
    assert row["result"] == "ok"
    assert "input_tokens" in row and row["input_tokens"] == expect_in
    assert row["output_tokens"] == expect_out
