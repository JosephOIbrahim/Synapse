# tests/test_rails_none_tier.py - BP9-NONETIER (ruling 2): the 'none' probe tier.
#
# A tier-none leg launches NO model: the orchestrator runs the row's probe_cmd itself and
# writes the receipt from stdout/stderr/exit code. This pins the four seams:
#   1. rails_exec.json carries 'none' with routable:false
#   2. mission_schema accepts tier none ONLY with a probe_cmd
#   3. compile_wave passes tier none + probe_cmd through byte-identical (JEV invariant 2)
#   4. jev_route's Choice criteria exclude 'none', and decide() refuses it if Jev names it
#   5. probe_receipt (the pure-Python parser orchestrate.ps1 calls) turns two ACCEPT lines
#      into two acceptance rows; a missing probe_cmd is a fail receipt
#   6. orchestrate.ps1 branches on 'none' before the claude launch line and guards probe_cmd
# Pure Python, stock pytest, zero hou, no network (jev_route is only asked for its table).
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAILS_EXEC = REPO / "harness" / "rails_exec.json"
ORCH = REPO / "harness" / "orchestrate.ps1"


def _load(name, rel):
    # by file path under a unique name: several harnesses ship a mission_schema.py /
    # compile_wave.py and a bare import returns whichever one pytest cached first.
    spec = importlib.util.spec_from_file_location(name, REPO / "harness" / "battleplan" / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ms = _load("bp9_mission_schema", "mission_schema.py")
_prev = sys.modules.get("mission_schema")
sys.modules["mission_schema"] = ms
try:
    cw = _load("bp9_compile_wave", "compile_wave.py")
finally:
    if _prev is None:
        sys.modules.pop("mission_schema", None)
    else:
        sys.modules["mission_schema"] = _prev
pr = _load("bp9_probe_receipt", "probe_receipt.py")

JEV_DIR = REPO / "harness" / "jev"
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))
import jev_client as jc  # noqa: E402
import jev_route  # noqa: E402

BASE = {
    "id": "BP9-PROBE", "name": "n", "band": "BUILD",
    "source": {"doc": "docs/BATTLEPLAN.md", "anchor": "sec.6"},
    "targets": ["T1"], "acceptance": [{"predicate": "p", "evidence": "probe"}],
    "deps": [], "readonly": False, "touches": ["harness/"],
    "crucible_criteria": ["c"],
}
PROBE = "python -c \"print('ACCEPT: x :: pass :: y')\""


# --------------------------------------------------------------------------- #
# 1. rails_exec.json
# --------------------------------------------------------------------------- #
def test_rails_exec_carries_none_tier_unroutable():
    t = json.loads(RAILS_EXEC.read_text(encoding="utf-8"))["tiers"]
    assert "none" in t
    assert t["none"].get("routable") is False
    assert "no model" in t["none"]["why"].lower()


# --------------------------------------------------------------------------- #
# 2. mission_schema
# --------------------------------------------------------------------------- #
def test_schema_accepts_none_only_with_probe_cmd():
    assert ms.validate_mission({**BASE, "tier": "none", "probe_cmd": PROBE}) == []
    errs = ms.validate_mission({**BASE, "tier": "none"})
    assert any("probe_cmd" in e for e in errs), errs
    errs = ms.validate_mission({**BASE, "tier": "none", "probe_cmd": "   "})
    assert any("probe_cmd" in e for e in errs), errs


def test_schema_refuses_probe_cmd_on_a_model_tier():
    errs = ms.validate_mission({**BASE, "tier": "reasoning", "probe_cmd": PROBE})
    assert any("only valid with tier 'none'" in e for e in errs), errs
    errs = ms.validate_mission({**BASE, "probe_cmd": PROBE})  # no tier at all
    assert any("only valid with tier 'none'" in e for e in errs), errs


def test_schema_refuses_none_as_subagent_tier():
    errs = ms.validate_mission({**BASE, "tier": "reasoning",
                                "team": {"max_subagents": 2, "subagent_tier": "none"}})
    assert any("subagent_tier cannot be 'none'" in e for e in errs), errs


# --------------------------------------------------------------------------- #
# 3. compile_wave pass-through
# --------------------------------------------------------------------------- #
def test_compile_wave_passes_none_and_probe_cmd_through_untouched():
    row = cw.leg_row({**BASE, "tier": "none", "probe_cmd": PROBE, "probe_timeout": 42})
    assert row["tier"] == "none"
    assert row["probe_cmd"] == PROBE            # byte-identical, no rewriting
    assert row["probe_timeout"] == 42


def test_compile_wave_other_literal_tiers_unchanged_and_no_probe_key():
    """JEV invariant 2: a literal tier other than none compiles exactly as before - same tier
    string, and no probe_cmd/probe_timeout key leaks onto the row."""
    for tier in ("mechanical", "reasoning", "referee"):
        row = cw.leg_row({**BASE, "tier": tier})
        assert row["tier"] == tier
        assert "probe_cmd" not in row and "probe_timeout" not in row
    assert "tier" not in cw.leg_row(dict(BASE))
    assert "probe_cmd" not in cw.leg_row(dict(BASE))


# --------------------------------------------------------------------------- #
# 4. jev_route never offers or honours 'none'
# --------------------------------------------------------------------------- #
def test_jev_route_tier_criteria_exclude_none():
    assert "none" in jc.rails_tiers()                 # it IS a rails tier ...
    assert "none" not in jev_route.routable_tiers()   # ... but never a routable one
    crit = jev_route._tier_descriptions()
    assert "none" not in crit
    assert "none" not in jev_route.route_spec(crit)["tier"]["criteria"]
    assert {"mechanical", "reasoning", "referee"} <= set(crit)


def test_jev_route_decide_refuses_none_even_if_jev_names_it():
    """Mutation: make decide() check jc.rails_tiers() instead of routable_tiers() -> a Jev
    answer of 'none' at 0.99 would be honoured and a model-less leg dispatched -> RED."""
    policy = jc.load_questions()["guards"]["route"]["policy"]
    answers = {"choices": {"tier": {"choice": "none", "confidence": 0.99, "probabilities": {"none": 0.99}}},
               "scores": {"novelty": {"score": 0.1}, "blast_radius": {"score": 0.1}}, "nouls": {}}
    d = jev_route.decide(dict(BASE), answers, policy)
    assert d["tier"] == policy["fallback_tier"]
    assert d["tier"] != "none"
    assert "unknown tier 'none'" in d["reason"]


# --------------------------------------------------------------------------- #
# 5. probe_receipt - the parser the ps1 calls
# --------------------------------------------------------------------------- #
def test_probe_two_accept_lines_yield_two_acceptance_rows(tmp_path):
    cmd = (f'"{sys.executable}" -c "import sys; '
           "print('ACCEPT: schema accepts none :: pass :: validate_mission returned []'); "
           "print('chatter line the parser must ignore'); "
           "print('ACCEPT: ps1 guarded :: fail :: grep found 0 lines'); "
           "sys.stderr.write('one finding on stderr\\n')\"")
    code, out, err, timed_out = pr.run_probe(cmd, timeout=60)
    r = pr.build_receipt("BP9-PROBE", cmd, code, out, err, timed_out=timed_out, timeout=60)
    assert r["status"] == "pass" and r["exit_code"] == 0 and r["tier"] == "none"
    assert len(r["acceptance"]) == 2
    assert r["acceptance"][0] == {"predicate": "schema accepts none", "verdict": "pass",
                                  "evidence": "validate_mission returned []"}
    assert r["acceptance"][1]["verdict"] == "fail"
    assert r["findings"] == ["one finding on stderr"]
    assert r["for_ruling"] == []
    # the CLI writes the same shape to --out (what orchestrate.ps1 invokes)
    out_path = tmp_path / "BP9-PROBE.json"
    rc = pr.main(["run", "--leg", "BP9-PROBE", "--cmd", cmd, "--timeout", "60", "--out", str(out_path)])
    assert rc == 0
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(on_disk["acceptance"]) == 2 and on_disk["status"] == "pass"


def test_probe_nonzero_exit_is_fail_and_missing_cmd_is_fail(tmp_path):
    cmd = f'"{sys.executable}" -c "import sys; print(\'ACCEPT: p :: pass :: e\'); sys.exit(3)"'
    code, out, err, to = pr.run_probe(cmd, timeout=60)
    r = pr.build_receipt("BP9-PROBE", cmd, code, out, err, timed_out=to)
    assert r["status"] == "fail" and r["exit_code"] == 3
    assert len(r["acceptance"]) == 1           # rows still parsed; status comes from the exit code
    miss = pr.missing_receipt("BP9-PROBE")
    assert miss["status"] == "fail" and miss["acceptance"] == [] and miss["exit_code"] is None
    assert any("no probe_cmd" in f for f in miss["findings"])
    out_path = tmp_path / "m.json"
    assert pr.main(["missing", "--leg", "BP9-PROBE", "--out", str(out_path)]) == 1
    assert json.loads(out_path.read_text(encoding="utf-8"))["status"] == "fail"


def test_probe_timeout_is_fail():
    cmd = f'"{sys.executable}" -c "import time; time.sleep(30)"'
    code, out, err, to = pr.run_probe(cmd, timeout=1)
    r = pr.build_receipt("BP9-PROBE", cmd, code, out, err, timed_out=to, timeout=1)
    assert to is True and r["status"] == "fail" and r["exit_code"] is None
    assert any("timed out" in f for f in r["findings"])


# --------------------------------------------------------------------------- #
# 6. orchestrate.ps1 wiring (static: the ps1 is not executed here)
# --------------------------------------------------------------------------- #
def test_ps1_branches_on_none_before_launch_and_guards_probe_cmd():
    src = ORCH.read_text(encoding="utf-8")
    guard = src.index("if ($leg.tier -eq 'none') { Run-ProbeLeg $leg; return }")
    launch = src.index("claude --settings '$safeProfile'")
    assert guard < launch                       # the branch precedes the only claude launch line
    fn = src[src.index("function Run-ProbeLeg"):src.index("function Start-Leg")]
    assert "probe_receipt.py" in fn
    assert "-not $leg.probe_cmd" in fn          # missing probe_cmd is refused ...
    assert "missing --leg" in fn                # ... with a fail receipt ...
    assert "claude --" not in fn and "Start-Process" not in fn  # ... and never a session


def test_ps1_parses_clean():
    """The edit must not break PowerShell parsing; the harness has no ps1 tests otherwise."""
    pwsh = "powershell"
    script = ("$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('"
              + str(ORCH).replace("\\", "/") + "',[ref]$t,[ref]$e)|Out-Null; "
              "if($e.Count){$e|%{$_.Message};exit 1}else{'PARSE-OK'}")
    try:
        p = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        import pytest
        pytest.skip("powershell not available on this host")
    assert "PARSE-OK" in p.stdout, p.stdout + p.stderr
