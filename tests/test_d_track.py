"""Pins the D-track (diagnostic-truth graft) — harness/verify/checks.py's eight D-checks
(cook_api_confirmed, cook_truth_fresh, cook_review_clean, cook_golden_{sop,lop,cop,dop},
tops_path_untouched), the tasks.json D.1-D.5 conformance surface, the guardrail freeze, and
the flywheel D.0 candidate entry (fields + evidence — NEVER the ratified value: flipping it
is the human's act and must not redden this suite).

Frozen contract: harness/notes/spec-D-diagnostic-truth.md (intake per
harness/notes/SYNAPSE_ODFORCE_HARNESS.md). The graft is DORMANT scaffolding: every check is
honest-false until its mile's artifact exists, and no D task enters the queue until a human
flips D.0's ratified flag (COOK_RATIFIED) and merges the cook_truth catalog (COOK).

Discipline (the test_ctx_track/test_s_track siblings, verbatim): load checks by path (the
harness verify layer isn't a package); hermetic tmp_path worktrees with ctx['wt']=tmp_path;
monkeypatch the checks.sh / checks.hython seams — NEVER sys.modules fakes (the known repo
trap); SUBSTRING matches on detail prose, exact equality only on frozen non-prose surfaces.
Commandment 7 (spec §6, binding): a golden that starts failing is a bug to fix forward,
never an assertion to soften.

Landing order: this file MUST land in the same commit as the checks.py/tasks.json/run.ts
edits — the fail-loud DISPATCH lookups plus the suite_baseline ratchet redden a staged landing.
"""
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_d", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

D_CHECKS = {"cook_api_confirmed", "cook_truth_fresh", "cook_review_clean",
            "cook_golden_sop", "cook_golden_lop", "cook_golden_cop", "cook_golden_dop",
            "tops_path_untouched"}

# The frozen per-id verify lists (spec-D mile split — non-prose frozen surface, exact equality).
D_VERIFY = {
    "D.1": ["cook_api_confirmed", "tops_path_untouched"],
    "D.2": ["cook_api_confirmed", "cook_truth_fresh", "tops_path_untouched"],
    "D.3": ["cook_truth_fresh", "cook_review_clean", "cook_golden_sop", "cook_golden_lop",
            "cook_golden_cop", "cook_golden_dop", "tops_path_untouched"],
    "D.4": ["cook_review_clean", "cook_golden_sop", "cook_golden_lop", "cook_golden_cop",
            "cook_golden_dop", "tops_path_untouched"],
    "D.5": ["cook_review_clean", "cook_golden_sop", "cook_golden_lop", "cook_golden_cop",
            "cook_golden_dop", "tops_path_untouched"],
}

# guardrails.checks stays frozen — the D track adds TASK verifies, NEVER guardrails.
GUARDRAILS_FROZEN = ["scout_no_apex_corpus", "no_rigging_drift",
                     "provenance_not_bypassed", "phantom_clean",
                     "suite_baseline"]


def _ctx(wt, hython=""):
    return {"wt": str(wt), "hython": hython, "mode": "A"}


def _run(name, ctx):
    fn = checks.DISPATCH.get(name)
    if fn is None:
        pytest.fail(f"D check '{name}' not registered in DISPATCH — graft not landed")
    return fn(ctx)


def _plant(wt, rel, doc):
    p = pathlib.Path(wt) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _cook_truth_doc(stamp="21.0.671", trials=None):
    trials = trials if trials is not None else [
        {"context": "sop", "graph_fingerprint": "box-scatter", "perturbation": "parm:box1/scale",
         "expected_dirty": ["/obj/geo1/scatter1"], "observed_dirty": ["/obj/geo1/scatter1"],
         "cookcount_deltas": {"/obj/geo1/scatter1": 1}, "time_dependent": []}]
    digest = hashlib.blake2b(json.dumps(trials, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                             digest_size=16).hexdigest()
    return {"schema": "cook_truth/v1", "houdini_version": stamp, "blake2b": digest, "trials": trials}


def _cook_api_doc(stamp="21.0.671", confirmed=None, absent=None):
    confirmed = confirmed if confirmed is not None else ["hou.Node.cookCount", "hou.Node.cook"]
    absent = absent if absent is not None else ["hou.updateGraphTick"]
    digest = hashlib.blake2b(json.dumps({"confirmed": confirmed, "absent": absent},
                                        sort_keys=True, ensure_ascii=False).encode("utf-8"),
                             digest_size=16).hexdigest()
    return {"schema": "cook_api/v1", "houdini_version": stamp,
            "confirmed": confirmed, "absent": absent, "blake2b": digest}


# ---------------------------------------------------------------------------
# conformance — registration, vocabulary, task rows, guardrail freeze
# ---------------------------------------------------------------------------

def test_guardrails_untouched_by_graft():
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    assert doc["guardrails"]["checks"] == GUARDRAILS_FROZEN


def test_d_checks_registered():
    assert D_CHECKS <= set(checks.DISPATCH)
    vocab = set(json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))["checks_vocabulary"])
    assert D_CHECKS <= vocab


def test_d_tasks_conform_to_contract():
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    d_tasks = [t for t in doc["tasks"] if str(t.get("id", "")).startswith("D.")]
    if not d_tasks:
        pytest.skip("no D-tasks in tasks.json yet (graft pending)")
    vocab = set(doc.get("checks_vocabulary", []))
    assert {t["id"] for t in d_tasks} == set(D_VERIFY), sorted(t["id"] for t in d_tasks)
    for t in d_tasks:
        tid = t["id"]
        assert re.fullmatch(r"D\.\d", tid), tid
        assert t.get("phase") == "diagnostic", tid   # never 'studio' — protects the S red-driver join
        assert t.get("mode") == "A", tid
        assert not t.get("human_gate"), tid          # ratification IS the human gate; merge is the second
        # two-stage gating: probes on the ratification flag; sweep/goldens/handlers on the catalog
        assert t.get("blocked_on") == ("cook_ratified" if tid in ("D.1", "D.2") else "cook_truth"), tid
        assert t.get("verify") == D_VERIFY[tid], tid
        for name in t["verify"]:
            assert name in checks.DISPATCH, f"{tid} verify '{name}' unregistered"
            assert name in vocab, f"{tid} verify '{name}' not in checks_vocabulary"


def test_d0_flywheel_candidate_is_legal():
    # Pins the entry's SHAPE + evidence (the schema's own law: evidence-free entries are
    # invalid) — deliberately NOT the ratified value, which is the human's to flip.
    doc = json.loads((_REPO / "harness" / "state" / "flywheel_queue.json").read_text(encoding="utf-8"))
    d0 = next((cy for cy in doc.get("cycles", []) if cy.get("id") == "D.0"), None)
    assert d0 is not None, "D.0 missing from flywheel_queue.json"
    for field in ("title", "status", "evidence", "note"):
        assert d0.get(field), f"D.0 lacks {field}"
    assert isinstance(d0.get("ratified"), bool)
    assert d0["status"] in ("building", "candidate", "done")
    assert isinstance(d0["evidence"], list) and d0["evidence"], "evidence-free entries are invalid"
    for ev in d0["evidence"]:
        assert (_REPO / ev).exists(), f"D.0 evidence path missing on disk: {ev}"


def _cook_ratified(doc):
    """Pure-data mirror of run.ts's COOK_RATIFIED predicate (the TS itself has no test harness)."""
    cycles = doc.get("cycles")
    if not isinstance(cycles, list):
        return False
    return any(isinstance(cy, dict) and cy.get("id") == "D.0" and cy.get("ratified") is True
               for cy in cycles)


def test_cook_ratified_predicate_mirror():
    assert _cook_ratified({"cycles": [{"id": "D.0", "ratified": True}]}) is True
    assert _cook_ratified({"cycles": [{"id": "D.0", "ratified": False}]}) is False
    assert _cook_ratified({"cycles": [{"id": "U.5", "ratified": True}]}) is False
    assert _cook_ratified({"cycles": "corrupt"}) is False
    assert _cook_ratified({}) is False


def test_spec_docs_committed_verbatim_home():
    # The evidence rule: the spec note IS the queue entry's legality. Both intake docs live
    # in harness/notes/ (the spec-C/spec-S precedent home).
    assert (_REPO / "harness" / "notes" / "spec-D-diagnostic-truth.md").is_file()
    assert (_REPO / "harness" / "notes" / "SYNAPSE_ODFORCE_HARNESS.md").is_file()


# ---------------------------------------------------------------------------
# cook_truth_fresh — RED/GREEN + the H22 major-agnostic pin
# ---------------------------------------------------------------------------

def test_cook_truth_missing_names_arming_task(tmp_path):
    res = _run("cook_truth_fresh", _ctx(tmp_path))
    assert res["ok"] is False
    assert "D.2" in res["detail"]


def test_cook_truth_wrong_schema_red(tmp_path):
    doc = _cook_truth_doc()
    doc["schema"] = "cook_truth/v0"
    _plant(tmp_path, "harness/notes/cook_truth_21.json", doc)
    res = _run("cook_truth_fresh", _ctx(tmp_path))
    assert res["ok"] is False and "cook_truth/v1" in res["detail"]


def test_cook_truth_digest_mismatch_red(tmp_path):
    doc = _cook_truth_doc()
    doc["blake2b"] = "0" * 32
    _plant(tmp_path, "harness/notes/cook_truth_21.json", doc)
    res = _run("cook_truth_fresh", _ctx(tmp_path))
    assert res["ok"] is False and "blake2b" in res["detail"]


def test_cook_truth_valid_no_hython_green(tmp_path):
    _plant(tmp_path, "harness/notes/cook_truth_21.json", _cook_truth_doc())
    res = _run("cook_truth_fresh", _ctx(tmp_path))
    assert res["ok"] is True and "skipped" in res["detail"]


def test_cook_truth_h22_catalog_resolves_with_zero_check_edits(tmp_path, monkeypatch):
    # THE H22 pin: drop a 22-stamped catalog next to nothing else, fake a live H22 build —
    # the check resolves cook_truth_22.json and greens. No check edit on the H22 drop.
    _plant(tmp_path, "harness/notes/cook_truth_22.json", _cook_truth_doc(stamp="22.0.100"))
    monkeypatch.setattr(checks, "hython",
                        lambda hy, script, cwd: (0, "BUILD 22.0.100\n", ""))
    res = _run("cook_truth_fresh", _ctx(tmp_path, hython="fake-hython"))
    assert res["ok"] is True, res["detail"]


def test_cook_truth_stale_stamp_vs_live_red(tmp_path, monkeypatch):
    # A 21-stamped catalog under a live H22 build must go STALE-loud — the re-probe duty.
    _plant(tmp_path, "harness/notes/cook_truth_21.json", _cook_truth_doc(stamp="21.0.671"))
    monkeypatch.setattr(checks, "hython",
                        lambda hy, script, cwd: (0, "BUILD 22.0.100\n", ""))
    res = _run("cook_truth_fresh", _ctx(tmp_path, hython="fake-hython"))
    assert res["ok"] is False and ("STALE" in res["detail"] or "no cook_truth artifact" in res["detail"])


def test_cook_truth_multiple_majors_no_hython_picks_highest(tmp_path):
    _plant(tmp_path, "harness/notes/cook_truth_21.json", _cook_truth_doc(stamp="21.0.671"))
    _plant(tmp_path, "harness/notes/cook_truth_22.json", _cook_truth_doc(stamp="22.0.100"))
    res = _run("cook_truth_fresh", _ctx(tmp_path))
    assert res["ok"] is True and "22" in res["detail"] and "multiple majors" in res["detail"]


# ---------------------------------------------------------------------------
# cook_api_confirmed — RED/GREEN + the own-authority design law
# ---------------------------------------------------------------------------

def test_cook_api_missing_names_arming_task(tmp_path):
    res = _run("cook_api_confirmed", _ctx(tmp_path))
    assert res["ok"] is False and "D.1" in res["detail"]


def test_cook_api_valid_green(tmp_path):
    _plant(tmp_path, "harness/notes/verified_cook_api_21.0.671.json", _cook_api_doc())
    res = _run("cook_api_confirmed", _ctx(tmp_path))
    assert res["ok"] is True, res["detail"]


def test_cook_api_overlap_red(tmp_path):
    _plant(tmp_path, "harness/notes/verified_cook_api_21.0.671.json",
           _cook_api_doc(confirmed=["hou.Node.cook"], absent=["hou.Node.cook"]))
    res = _run("cook_api_confirmed", _ctx(tmp_path))
    assert res["ok"] is False and "overlap" in res["detail"]


def test_cook_api_empty_confirmed_red(tmp_path):
    _plant(tmp_path, "harness/notes/verified_cook_api_21.0.671.json",
           _cook_api_doc(confirmed=[], absent=["hou.x"]))
    res = _run("cook_api_confirmed", _ctx(tmp_path))
    assert res["ok"] is False and "confirmed" in res["detail"]


def test_cook_api_never_touches_the_phantom_symbol_table():
    # DESIGN LAW: verified_cook_api_* is this check's OWN authority. Splicing it into
    # h21_symbol_table.json would break that table's blake2b + dir()-membership invariant —
    # so the check source must never reference the table.
    src = _CHECKS.read_text(encoding="utf-8")
    m = re.search(r"def check_cook_api_confirmed\(ctx\):(.*?)(?=\ndef )", src, re.S)
    assert m, "check_cook_api_confirmed body not found"
    # judge FUNCTIONAL code only — the design-law comment inside the check legitimately
    # names the table it must never open, so strip comments before pinning.
    code_only = "\n".join(l.split("#", 1)[0] for l in m.group(1).splitlines())
    assert "symbol_table" not in code_only


# ---------------------------------------------------------------------------
# cook_review_clean — dormant honest-false + rc/critical judgment
# ---------------------------------------------------------------------------

def test_cook_review_dormant_names_deliverable(tmp_path):
    res = _run("cook_review_clean", _ctx(tmp_path))
    assert res["ok"] is False and "D.3" in res["detail"]


def _plant_sweep(wt, critical):
    script = (wt / "scripts")
    script.mkdir(parents=True, exist_ok=True)
    (script / "flywheel_review_cook.py").write_text(
        "import json, os\n"
        "os.makedirs('.claude', exist_ok=True)\n"
        "json.dump({'summary': {'critical': %d}}, open('.claude/flywheel_cook_findings.json', 'w'))\n"
        "print('sweep ok')\n" % critical,
        encoding="utf-8")


def test_cook_review_clean_green_on_zero_critical(tmp_path):
    _plant_sweep(tmp_path, critical=0)
    res = _run("cook_review_clean", _ctx(tmp_path))
    assert res["ok"] is True, res["detail"]


def test_cook_review_red_on_critical_findings(tmp_path):
    _plant_sweep(tmp_path, critical=2)
    res = _run("cook_review_clean", _ctx(tmp_path))
    assert res["ok"] is False and "critical=2" in res["detail"]


# ---------------------------------------------------------------------------
# cook goldens — HYTHON law, dormant paths, exact-reproduction verdicts
# ---------------------------------------------------------------------------

def test_cook_golden_requires_hython(tmp_path):
    res = _run("cook_golden_sop", _ctx(tmp_path, hython=""))
    assert res["ok"] is False          # ok:False, NEVER None — an unrun golden is unverified
    assert "HYTHON" in res["detail"]


def test_cook_golden_dormant_names_probe(tmp_path):
    res = _run("cook_golden_sop", _ctx(tmp_path, hython="fake-hython"))
    assert res["ok"] is False and "introspect_cook_truth" in res["detail"]


def _golden_harness(tmp_path, monkeypatch, live_observed):
    """Fake the git + probe seams: committed catalog holds one sop trial; the 'probe' writes
    an artifact whose observed_dirty is `live_observed`."""
    (tmp_path / "host").mkdir(parents=True, exist_ok=True)
    (tmp_path / "host" / "introspect_cook_truth.py").write_text("# placeholder probe\n", encoding="utf-8")
    committed = _cook_truth_doc()
    _plant(tmp_path, "harness/notes/cook_truth_21.json", committed)
    real_sh = checks.sh

    def fake_sh(cmd, cwd=None, timeout=900, env=None):
        joined = " ".join(str(a) for a in cmd)
        if "merge-base" in joined:
            return 0, "abc123\n", ""
        if "show" in joined and "cook_truth_21.json" in joined:
            return 0, json.dumps(committed), ""
        if "introspect_cook_truth.py" in joined:
            artifact = {"schema": "cook_truth/v1",
                        "trials": [{"context": "sop", "graph_fingerprint": "box-scatter",
                                    "perturbation": "parm:box1/scale",
                                    "observed_dirty": live_observed}]}
            out = pathlib.Path(cwd) / cmd[cmd.index("--out") + 1]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(artifact), encoding="utf-8")
            return 0, "banner noise\n", ""
        return real_sh(cmd, cwd=cwd, timeout=timeout, env=env)

    monkeypatch.setattr(checks, "sh", fake_sh)
    monkeypatch.setattr(checks, "hython", lambda hy, script, cwd: (0, "BUILD 21.0.671\n", ""))


def test_cook_golden_reproduction_green(tmp_path, monkeypatch):
    _golden_harness(tmp_path, monkeypatch, live_observed=["/obj/geo1/scatter1"])
    res = _run("cook_golden_sop", _ctx(tmp_path, hython="fake-hython"))
    assert res["ok"] is True, res["detail"]


def test_cook_golden_divergence_red_fix_forward(tmp_path, monkeypatch):
    _golden_harness(tmp_path, monkeypatch, live_observed=["/obj/geo1/UNEXPECTED"])
    res = _run("cook_golden_sop", _ctx(tmp_path, hython="fake-hython"))
    assert res["ok"] is False and "divergence" in res["detail"]


# ---------------------------------------------------------------------------
# tops_path_untouched — the structural quarantine
# ---------------------------------------------------------------------------

def test_tops_path_untouched_green_at_head():
    res = _run("tops_path_untouched", _ctx(str(_REPO)))
    assert res["ok"] is True, res["detail"]


def test_tops_path_touched_red(tmp_path):
    guard = tmp_path / "python" / "synapse" / "server" / "handlers_tops"
    guard.mkdir(parents=True)
    f = guard / "cook.py"
    f.write_text("original\n", encoding="utf-8")
    def git(*args):
        subprocess.run(["git", *args], cwd=str(tmp_path), capture_output=True, text=True, check=True)
    git("init", "-b", "master")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("add", "-A")
    git("commit", "-m", "base")
    f.write_text("modified — quarantine breach\n", encoding="utf-8")
    res = _run("tops_path_untouched", _ctx(tmp_path))
    assert res["ok"] is False and "cook.py" in res["detail"]
