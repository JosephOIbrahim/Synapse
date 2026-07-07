"""Pins the S-track (studio-readiness hardening graft) — harness/verify/checks.py's eight
S-checks (posture_declared, policy_single_source, consent_enforced, rbac_at_dispatch,
memory_provenance, eval_backbone, farm_headless, studio_readiness_review), plus the
tasks.json conformance surface, the guardrail freeze, and harness/state/posture.json.example.

Load-by-path like test_phantom_guardrail.py — the harness verify layer isn't a package. Seam
discipline follows the two siblings verbatim:
  - the FINGERPRINT checks (consent_enforced / eval_backbone / policy_single_source) read
    SOURCE relative to the worktree, so we drive them with SYNTHETIC tmp sources planted under
    tmp_path and ctx['wt']=tmp_path — the test_ctx_track _plant precedent. No sys.modules fakes,
    ever (the known repo trap); no monkeypatch of Path.read_text — the seam is the worktree tree.
  - posture_declared reads a MACHINE-level path (spec §3: NOT worktree state), so it can only be
    tested by redirecting that path — we monkeypatch the module's posture-path seam
    (checks._POSTURE_PATH) to a tmp file. BUILDER-B must expose it as that module constant.
  - the studio_readiness_review CAPSTONE aggregates the other checks; we monkeypatch the
    sub-check functions AND their DISPATCH rows to stubs (belt + suspenders — the capstone must
    resolve sub-checks by NAME at call time, never via a module-load-time captured list).

Assertion discipline (spec-S §6, binding): SUBSTRING matches on detail prose — BUILDER-B words
the messages, the spec only freezes what they must name. Exact equality is reserved for the
non-prose frozen surfaces (verify lists, the guardrail 4-name list, the READY/NOT READY verdict
enum, the findings_live check-name list).

Landing order (this file is BUILDER-C; A/B land concurrently):
  - the guardrail freeze + posture.json.example cases are PURE-CONTRACT / own-fixture → green now;
  - the tasks.json conformance case SKIPS loudly until BUILDER-A's S-entries exist;
  - every DISPATCH-backed case FAILS loud ('BUILDER-B not landed') until BUILDER-B registers the
    eight checks — same sibling pattern (a clean, self-classifying failure, never a silent pass).
"""
import importlib.util
import json
import pathlib
import re

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_s", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

# The eight NEW checks the S-track registers (context_review_clean already exists from C).
S_NEW_CHECKS = {"posture_declared", "policy_single_source", "consent_enforced",
                "rbac_at_dispatch", "memory_provenance", "eval_backbone", "farm_headless",
                "studio_readiness_review"}

# The frozen per-id verify lists (spec-S §2 — a non-prose frozen surface, so exact equality).
S_VERIFY = {
    "S.0": ["posture_declared"],
    "S.1": ["policy_single_source"],
    "S.2": ["consent_enforced"],
    "S.3": ["rbac_at_dispatch"],
    "S.4": ["memory_provenance"],
    "S.5": ["eval_backbone"],
    "S.6": ["farm_headless", "context_review_clean"],
    "S.R": ["studio_readiness_review"],
}
S_BLOCKED = {"S.1", "S.2", "S.3"}          # blocked_on:"posture" (S.0 writes it, can't gate itself)
S_HUMAN_GATE = {"S.0", "S.1", "S.2", "S.3"}  # security-critical clusters carry the human gate
# The critical set the capstone requires green (spec-S §3 studio_readiness_review).
S_CRITICAL_CHECKS = ["posture_declared", "policy_single_source", "consent_enforced",
                     "rbac_at_dispatch"]

# guardrails.checks as of the graft's start — the S track adds TASK verifies, NEVER guardrails,
# so this list is frozen byte-for-byte (spec-S §6 "guardrails.checks unchanged").
GUARDRAILS_FROZEN = ["scout_no_apex_corpus", "no_rigging_drift",
                     "provenance_not_bypassed", "phantom_clean"]

_CTX_KEYS = {"hython": "", "mode": "A"}


def _ctx(wt):
    return {"wt": str(wt), **_CTX_KEYS}


def _plant(wt, rel, text):
    """Plant a synthetic source file into the tmp worktree (test_ctx_track precedent)."""
    p = pathlib.Path(wt) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _run(name, ctx):
    """Reach a check through DISPATCH by name — the frozen surface, same as run_one. Pre-B the
    row is absent → fail LOUD + self-classifying (never a KeyError buried in a traceback)."""
    fn = checks.DISPATCH.get(name)
    if fn is None:
        pytest.fail(f"DISPATCH lacks '{name}' — BUILDER-B has not landed the S-checks yet")
    return fn(ctx)


def _redirect_posture(monkeypatch, p):
    """Redirect the machine-level posture path to a tmp file. posture_declared reads a fixed
    MAIN-repo path through the module seam _posture_path() (spec §3: NOT worktree state), so the
    hermetic seam is that function — patch it to return the tmp path (fallback: a path constant,
    if a future refactor chooses one). Fail loud naming the seam if neither exists — an
    integration gap to surface, not to paper over."""
    if callable(getattr(checks, "_posture_path", None)):
        monkeypatch.setattr(checks, "_posture_path", lambda: p)
        return
    for name in ("_POSTURE_PATH", "POSTURE_PATH", "_POSTURE_JSON"):
        if hasattr(checks, name):
            monkeypatch.setattr(checks, name, p)
            return
    pytest.fail("no monkeypatchable posture seam on checks (expected checks._posture_path()) "
                "— BUILDER-B pending / seam not aligned")


# ---------------- conformance: guardrails frozen, DISPATCH rows, tasks.json ----------------

def test_guardrails_untouched_by_graft():
    # PURE CONTRACT — green from day one. The S track must not perturb the guardrail wall.
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    assert doc["guardrails"]["checks"] == GUARDRAILS_FROZEN


def test_s_checks_registered_in_dispatch():
    # Awaiting BUILDER-B: the eight new rows must land under the DISPATCH S-comment.
    assert S_NEW_CHECKS <= set(checks.DISPATCH)


def test_s_tasks_conform_to_contract():
    # Correct against the FINAL frozen contract; BUILDER-A lands the S entries concurrently —
    # skip loudly (not vacuous-pass) until then, exactly like test_ctx_track's C-task case.
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    s_tasks = [t for t in doc["tasks"] if str(t.get("id", "")).startswith("S.")]
    if not s_tasks:
        pytest.skip("no S-tasks in tasks.json yet (BUILDER-A pending)")
    vocab = set(doc.get("checks_vocabulary", []))
    ids = {t["id"] for t in s_tasks}
    assert ids == set(S_VERIFY), ids  # S.0-S.6 + S.R, exactly
    for t in s_tasks:
        tid = t["id"]
        assert re.fullmatch(r"S\.(\d|R)", tid), tid
        assert t.get("verify") == S_VERIFY[tid], tid  # frozen verify list, exact
        # blocked_on: only S.1-S.3 gate on the posture declaration; the rest never do.
        if tid in S_BLOCKED:
            assert t.get("blocked_on") == "posture", tid
        else:
            assert t.get("blocked_on") != "posture", tid
        # human_gate: the security-critical clusters carry it (harness must NOT self-author auth).
        if tid in S_HUMAN_GATE:
            assert t.get("human_gate"), f"{tid} must carry a human_gate"
        # every verify name must be a real check AND vocabulary-declared.
        for name in t.get("verify", []):
            assert name in checks.DISPATCH, f"{tid}: verify '{name}' not in DISPATCH"
            assert name in vocab, f"{tid}: verify '{name}' not in checks_vocabulary"


# ---------------- posture.json.example (BUILDER-C's own deliverable — green now) ----------------

def test_posture_example_present_and_valid():
    p = _REPO / "harness" / "state" / "posture.json.example"
    assert p.is_file(), "harness/state/posture.json.example missing"
    doc = json.loads(p.read_text(encoding="utf-8"))  # must be valid JSON (mirrors drop.json.example)
    assert isinstance(doc.get("_doc"), list) and doc["_doc"], "expected a _doc block like drop.json.example"
    assert doc["mode"] in ("solo", "studio", "farm")
    assert isinstance(doc["identity_model"], str) and doc["identity_model"].strip()
    assert isinstance(doc["auto_approve"], bool)


def test_posture_example_documents_all_modes():
    # The .example must carry a commented example per mode (spec §4 "commented example per mode").
    p = _REPO / "harness" / "state" / "posture.json.example"
    blob = " ".join(json.loads(p.read_text(encoding="utf-8"))["_doc"]).lower()
    for mode in ("solo", "studio", "farm"):
        assert mode in blob, f"posture.json.example _doc must mention the '{mode}' mode"


# ---------------- posture_declared (posture path monkeypatched to a tmp file) ----------------

def test_posture_declared_missing_names_template(tmp_path, monkeypatch):
    # No posture.json on the machine → ok:false carrying the template (the fields to write).
    _redirect_posture(monkeypatch, tmp_path / "posture.json")  # does NOT exist
    res = _run("posture_declared", _ctx(tmp_path))
    assert res["ok"] is False
    assert "identity_model" in res["detail"]  # the template must name the fields to author


def test_posture_declared_malformed_mode(tmp_path, monkeypatch):
    p = tmp_path / "posture.json"
    p.write_text(json.dumps({"mode": "cluster", "identity_model": "x", "auto_approve": True}),
                 encoding="utf-8")
    _redirect_posture(monkeypatch, p)
    res = _run("posture_declared", _ctx(tmp_path))
    assert res["ok"] is False
    assert "mode" in res["detail"].lower()  # the failure must name the offending field


def test_posture_declared_valid(tmp_path, monkeypatch):
    p = tmp_path / "posture.json"
    p.write_text(json.dumps({"mode": "studio",
                             "identity_model": "per-user SSO at the dispatch boundary",
                             "auto_approve": False}), encoding="utf-8")
    _redirect_posture(monkeypatch, p)
    res = _run("posture_declared", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- consent_enforced (FINGERPRINT — synthetic tmp bridge_adapter) ----------------

# The _gate = None disarm literal is the fingerprint the check reads RED. We hold every OTHER
# sub-condition CLEARED (mcp/tools.py does not import the disarmed singleton; a HumanGate.propose
# producer exists in more than one non-executor file) so the ONLY toggled variable is the disarm.
_GATES_SRC = ("class HumanGate:\n"
              "    @staticmethod\n"
              "    def propose(op):\n"
              "        return op\n")
_TOOLS_CLEAN = ("from synapse.core.gates import HumanGate\n"
                "def call_tool(op):\n"
                "    return HumanGate.propose(op)  # armed producer, not the disarmed singleton\n")
_BRIDGE_PRODUCER = ("from synapse.core.gates import HumanGate\n"
                    "def arm_consent(op):\n"
                    "    return HumanGate.propose(op)\n")


def _plant_consent_tree(wt, disarmed):
    _plant(wt, "python/synapse/core/gates.py", _GATES_SRC)
    _plant(wt, "python/synapse/mcp/tools.py", _TOOLS_CLEAN)
    _plant(wt, "shared/bridge.py", _BRIDGE_PRODUCER)
    gate_line = "_gate = None  # DISARMED\n" if disarmed else "_gate = HumanGate()  # armed\n"
    _plant(wt, "python/synapse/panel/bridge_adapter.py",
           "from synapse.core.gates import HumanGate\n" + gate_line +
           "def execute_through_bridge(op):\n    return op\n")


def test_consent_enforced_red_with_disarm(tmp_path):
    _plant_consent_tree(tmp_path, disarmed=True)
    res = _run("consent_enforced", _ctx(tmp_path))
    assert res["ok"] is False
    assert "_gate" in res["detail"]  # the fingerprint the spec freezes


def test_consent_enforced_green_without_disarm(tmp_path):
    _plant_consent_tree(tmp_path, disarmed=False)
    res = _run("consent_enforced", _ctx(tmp_path))
    assert res["ok"] is True


# ---------------- eval_backbone (PRESENCE gate — synthetic worktree checks.py + guard) --------

_CHECKS_WITH_VALIDATE = ("def check_render(ctx):\n"
                         "    # real eval backbone: the frame is scored by validate_frame\n"
                         "    verdict = validate_frame(out_img)\n"
                         "    return {'ok': verdict.ok, 'detail': verdict.detail}\n")
_CHECKS_SIZE_ONLY = ("def check_render(ctx):\n"
                     "    return {'ok': img.stat().st_size > 1024, 'detail': 'byte-size only'}\n")
# B's eval_backbone scans tests/ for the EXACT marker `# FAKE_HOU_RESIDENCY_GUARD`.
_RESIDENCY_GUARD = ("# FAKE_HOU_RESIDENCY_GUARD — exactly one module may plant sys.modules['hou'].\n"
                    "import sys\n"
                    "def test_single_hou_planter():\n"
                    "    assert list(sys.modules).count('hou') <= 1, 'fake-hou collision'\n")


def test_eval_backbone_green_with_validate_frame_and_guard(tmp_path):
    _plant(tmp_path, "harness/verify/checks.py", _CHECKS_WITH_VALIDATE)
    _plant(tmp_path, "tests/conftest.py", _RESIDENCY_GUARD)
    _plant(tmp_path, "tests/test_fake_hou_residency.py", _RESIDENCY_GUARD)
    res = _run("eval_backbone", _ctx(tmp_path))
    assert res["ok"] is True


def test_eval_backbone_red_without(tmp_path):
    # check_render scores byte-size only + no residency guard → ok:false naming what's missing.
    _plant(tmp_path, "harness/verify/checks.py", _CHECKS_SIZE_ONLY)
    res = _run("eval_backbone", _ctx(tmp_path))
    assert res["ok"] is False
    assert "validate_frame" in res["detail"]  # the missing wiring the spec freezes


# ---------------- policy_single_source (SENTINEL gate — synthetic tmp sources) ----------------

def test_policy_single_source_green_with_sentinel(tmp_path):
    # A single-source policy module with the sentinel marker present, and a bridge.py whose
    # default-open fallback site is gone (benign body, no fallback pattern).
    _plant(tmp_path, "python/synapse/core/policy.py",
           "# POLICY_SINGLE_SOURCE\n"
           "POLICY = {'capability': {}, 'gate': {}, 'read_only': set(), 'disk': set()}\n")
    _plant(tmp_path, "shared/bridge.py",
           "def gate_level(op):\n    return POLICY['gate'].get(op)  # authoritative, no default-open\n")
    res = _run("policy_single_source", _ctx(tmp_path))
    assert res["ok"] is True


def test_policy_single_source_red_without_sentinel(tmp_path):
    # No policy module / no sentinel → the divergent taxonomy stands → ok:false naming a source.
    _plant(tmp_path, "shared/bridge.py", "GATE = {}\n")
    _plant(tmp_path, "python/synapse/mcp/_tool_registry.py", "GATE = {}\n")
    _plant(tmp_path, "python/synapse/server/handlers.py", "GATE = {}\n")
    _plant(tmp_path, "python/synapse/panel/worker_policy.py", "GATE = {}\n")
    res = _run("policy_single_source", _ctx(tmp_path))
    assert res["ok"] is False
    assert "bridge" in res["detail"].lower()  # names at least one divergent taxonomy file


# ---------------- studio_readiness_review (CAPSTONE aggregate — sub-checks stubbed) ----------

_CAPSTONE_SUBCHECKS = S_CRITICAL_CHECKS + ["memory_provenance", "eval_backbone",
                                           "farm_headless", "context_review_clean"]


def _stub_subchecks(monkeypatch, red=None):
    """Force every capstone sub-check to a deterministic verdict. Patch BOTH the module global
    check_<name> AND the DISPATCH row — the capstone must look sub-checks up by NAME at call
    time (globals or DISPATCH), and patching both covers either resolution without a captured
    module-load list (the anti-pattern that would make the capstone untestable)."""
    def _verdict(name):
        ok = name != red
        return {"ok": ok, "detail": ("stub green" if ok else f"{name} red stub")}
    for name in _CAPSTONE_SUBCHECKS:
        stub = (lambda n: (lambda ctx: _verdict(n)))(name)
        monkeypatch.setattr(checks, f"check_{name}", stub, raising=False)
        if name in checks.DISPATCH:
            monkeypatch.setitem(checks.DISPATCH, name, stub)
        else:
            # pre-B the row is absent; still register the stub so the capstone (once landed)
            # can resolve it. monkeypatch.setitem records the sentinel + reverts on teardown.
            monkeypatch.setitem(checks.DISPATCH, name, stub)


def _verdict_artifact(wt):
    return pathlib.Path(wt) / "harness" / "state" / "studio_readiness_verdict.json"


def test_studio_review_all_green_ready(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, red=None)
    res = _run("studio_readiness_review", _ctx(tmp_path))
    assert res["ok"] is True
    art = _verdict_artifact(tmp_path)
    assert art.is_file(), "capstone must emit studio_readiness_verdict.json into the worktree"
    doc = json.loads(art.read_text(encoding="utf-8"))
    assert doc["verdict"] == "READY"          # frozen enum
    assert doc["criticals_green"] is True
    assert doc.get("findings_live") == []      # nothing red


def test_studio_review_one_critical_red_not_ready(tmp_path, monkeypatch):
    _stub_subchecks(monkeypatch, red="consent_enforced")  # a security-critical goes red
    res = _run("studio_readiness_review", _ctx(tmp_path))
    assert res["ok"] is False
    art = _verdict_artifact(tmp_path)
    assert art.is_file()
    doc = json.loads(art.read_text(encoding="utf-8"))
    assert doc["verdict"] == "NOT READY"                    # frozen enum
    assert doc["criticals_green"] is False
    assert "consent_enforced" in doc["findings_live"]        # the capstone names the live finding
