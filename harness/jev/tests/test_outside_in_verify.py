"""Outside-in verify.py + run.py gate tests (BP10-BENCH acceptance 4 & 5). Pure Python: the
pass/fail logic runs against an injected fake accessor (no hou), and independence is proven by
code inspection -- verify.py's only inputs are the scene path and the check block."""
from __future__ import annotations

import json
import sys
from pathlib import Path

OI = Path(__file__).resolve().parents[2] / "outside_in"  # harness/outside_in
sys.path.insert(0, str(OI))
import verify as V  # noqa: E402


class FakeAcc:
    """Same surface as verify.HouAccessor, driven by plain dicts -- no Houdini needed."""

    def __init__(self, types=None, parms=None, attribs=None, cookable=None):
        self.types = types or {}
        self.parms = parms or {}
        self.attribs = attribs or {}
        self.cookable = cookable or set()

    def count_type(self, t, under=None):
        return self.types.get(t, 0)

    def parm_on_type(self, t, name):
        v = self.parms.get((t, name))
        return (v is not None, v)

    def cook_type(self, t):
        if self.types.get(t, 0) == 0:
            return (False, False, "no node")
        return (True, t in self.cookable, "")

    def attrib_on_type(self, t, cls, name):
        if self.types.get(t, 0) == 0:
            return (False, False, "no node")
        return (True, name in self.attribs.get((t, cls), set()), "")


def test_pass_when_scene_satisfies_check():
    acc = FakeAcc(types={"sphere": 1}, cookable={"sphere"})
    out = V.evaluate_check({"nodes": [{"type": "sphere", "min": 1}], "cook": {"type": "sphere"}}, acc)
    assert out["verdict"] == "PASS"


def test_fail_when_node_missing_even_if_arm_claims_success():
    # The arm's "Task complete." never reaches verify; an empty scene FAILs on its own merits.
    acc = FakeAcc(types={})
    out = V.evaluate_check({"nodes": [{"type": "sphere", "min": 1}]}, acc)
    assert out["verdict"] == "FAIL"


def test_parm_and_attrib_kinds():
    acc = FakeAcc(types={"xform": 1, "attribwrangle": 1},
                  parms={("xform", "ty"): 2.0},
                  attribs={("attribwrangle", "point"): {"Cd"}},
                  cookable={"attribwrangle"})
    good = V.evaluate_check({"parm": {"type": "xform", "name": "ty", "equals": 2.0, "tol": 0.001},
                             "attrib": {"type": "attribwrangle", "class": "point", "name": "Cd"},
                             "cook": {"type": "attribwrangle"}}, acc)
    assert good["verdict"] == "PASS"
    bad = V.evaluate_check({"parm": {"type": "xform", "name": "ty", "equals": 9.0, "tol": 0.001}}, acc)
    assert bad["verdict"] == "FAIL"


def test_empty_check_block_is_error_not_pass():
    assert V.evaluate_check({}, FakeAcc())["verdict"] == "ERROR"


def test_verify_reads_no_arm_text_code_inspection():
    # Inspect the CODE (ast excludes docstrings/comments, which legitimately explain the guarantee).
    import ast
    src = (OI / "verify.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # (1) verify.py imports no arm module -- it cannot reach an arm's transcript.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("arms", "_agent")), f"verify imports {node.module}"
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith(("arms", "_agent")), f"verify imports {a.name}"
    # (2) no arm-output identifier is used anywhere in the code.
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.arg):
            used.add(node.arg)
    for forbidden in ("final_text", "transcript", "arm_report", "success_text", "tool_names"):
        assert forbidden not in used, f"verify.py code references arm output: {forbidden}"
    # (3) its ONLY CLI inputs are the scene, the check block, and the search root.
    opts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                    opts.add(arg.value)
    assert opts == {"--scene", "--check", "--root"}, f"unexpected verify.py inputs: {opts}"


def test_run_large_gate_refuses_and_estimates(monkeypatch, tmp_path, capsys):
    import run as R
    stats = tmp_path / "turn_stats.json"
    stats.write_text(json.dumps({"per_turn_tokens": [100, 200, 300]}), encoding="utf-8")
    monkeypatch.setattr(R, "STATS", stats)
    code = R.spend_gate("large", runs=3, n_arms=2, n_prompts=24, confirm=False)
    out = capsys.readouterr().out
    assert code == 2
    assert "REFUSED" in out and "confirm-spend" in out
    assert "200" in out          # recorded median of [100,200,300]
    assert "144" in out          # 24 prompts x 3 runs x 2 arms
    # with confirm, not refused; empty scene never gated
    assert R.spend_gate("large", runs=3, n_arms=2, n_prompts=24, confirm=True) is None
    assert R.spend_gate("empty", runs=1, n_arms=2, n_prompts=1, confirm=False) is None


def test_run_large_gate_unknown_median_is_honest(monkeypatch, tmp_path, capsys):
    import run as R
    monkeypatch.setattr(R, "STATS", tmp_path / "absent.json")  # no recorded run
    code = R.spend_gate("large", 3, 2, 24, False)
    out = capsys.readouterr().out
    assert code == 2 and "UNKNOWN" in out  # median UNKNOWN, never a fabricated number
