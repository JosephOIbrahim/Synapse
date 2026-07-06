"""Pins the v6-track checks (harness/verify/checks.py: blueprints_present,
v6_skeleton_conformance, v6_spec_bp09/bp10, v6_kb_roundtrip, v6_tests_green) plus the
tasks.json conformance surface. Loaded by path like test_phantom_guardrail.py — the harness
verify layer isn't a package. Every case is hermetic: tmp_path worktrees, no git, no hou,
no subprocess (the kb_roundtrip/tests_green cases exercised here stop at the disk check).

Caveat for future tests/v6 authors (pinned below): in the FULL CI suite a sibling test
file's module-level fake `hou` may be resident in sys.modules when v6 tests run — v6 tests
must never assert "import hou raises" nor branch on hou importability, and must never plant
sys.modules fakes themselves (monkeypatch or nothing).
"""
import importlib.util
import json
import pathlib
import re

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_spec = importlib.util.spec_from_file_location("harness_checks_v6", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

V6_CHECKS = {"blueprints_present", "v6_skeleton_conformance", "v6_spec_bp09",
             "v6_spec_bp10", "v6_kb_roundtrip", "v6_tests_green"}


def _wt(root, files):
    """Materialize a fake worktree: {relpath: content} → ctx dict for the checks."""
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return {"wt": str(root)}


BP00_OK = (
    "# BP00 — v6 manifest\n\n"
    "## Module Manifest\n\n"
    "| path | layer | notes |\n"
    "|---|---|---|\n"
    "| python/synapse/v6/foo.py | pure | stub |\n\n"
    "## Next\n"
)

STUB_OK = "def foo():\n    pass\n"


# ---------- blueprints_present ----------

def test_blueprints_present_missing_dir(tmp_path):
    res = checks.check_blueprints_present({"wt": str(tmp_path)})
    assert res["ok"] is False
    assert "BP00_manifest.md" in res["detail"]


def test_blueprints_present_bp00_arms_and_detail_enumerates(tmp_path):
    ctx = _wt(tmp_path, {
        "docs/v6/BP00_manifest.md": BP00_OK,
        "docs/v6/BP01_perception.md": "# BP01\n",
        "docs/v6/BP09_iteration_controller.md": "# BP09\n",
    })
    res = checks.check_blueprints_present(ctx)
    assert res["ok"] is True
    assert "BP01_perception.md" in res["detail"]
    assert "BP09_iteration_controller.md" in res["detail"]
    assert "BP10_knowledge_base.md" in res["detail"]  # enumerated as missing


# ---------- v6_skeleton_conformance ----------

def test_skeleton_no_manifest_section_points_at_intake(tmp_path):
    ctx = _wt(tmp_path, {"docs/v6/BP00_manifest.md": "# BP00\n\nno table here\n"})
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "INTAKE" in res["detail"]


def test_skeleton_hollow_table_is_not_a_pass(tmp_path):
    # header + separator, zero data rows: 'every listed path' over the empty set must NOT
    # vacuously green-light the skeleton.
    hollow = ("# BP00\n\n## Module Manifest\n\n"
              "| path | layer | notes |\n|---|---|---|\n\n## Next\n")
    ctx = _wt(tmp_path, {"docs/v6/BP00_manifest.md": hollow})
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "INTAKE" in res["detail"]


def test_skeleton_existing_compiling_stub_passes(tmp_path):
    ctx = _wt(tmp_path, {
        "docs/v6/BP00_manifest.md": BP00_OK,
        "python/synapse/v6/foo.py": STUB_OK,
    })
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is True


def test_skeleton_missing_listed_path_fails_named(tmp_path):
    ctx = _wt(tmp_path, {"docs/v6/BP00_manifest.md": BP00_OK})
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "python/synapse/v6/foo.py" in res["detail"]


def test_skeleton_broken_stub_fails(tmp_path):
    ctx = _wt(tmp_path, {
        "docs/v6/BP00_manifest.md": BP00_OK,
        "python/synapse/v6/foo.py": "def foo(:\n",
    })
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "compile" in res["detail"]


def test_skeleton_pure_layer_top_import_hou_fails(tmp_path):
    ctx = _wt(tmp_path, {
        "docs/v6/BP00_manifest.md": BP00_OK,
        "python/synapse/v6/foo.py": "import hou\n\ndef foo():\n    pass\n",
    })
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "hou" in res["detail"]


def test_skeleton_pure_layer_function_level_import_hou_fails(tmp_path):
    # pure means pure: V.1's 'zero hou imports in pure layers' — a function-level import is
    # still a hou dependency, so the AST scan covers ALL depths, not just module top.
    ctx = _wt(tmp_path, {
        "docs/v6/BP00_manifest.md": BP00_OK,
        "python/synapse/v6/foo.py": "def foo():\n    import hou\n    return hou.pwd()\n",
    })
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "hou" in res["detail"]


def test_skeleton_row_escaping_worktree_fails(tmp_path):
    # A manifest row that joins OUTSIDE the worktree (absolute / drive / ..) must fail even
    # when the target exists and compiles — pathlib join silently replaces the base, so an
    # unguarded check would judge foreign disk instead of the tree it gates.
    outside = tmp_path / "outside.py"
    outside.write_text(STUB_OK, encoding="utf-8")
    doc = BP00_OK.replace("python/synapse/v6/foo.py", str(outside).replace("\\", "/"))
    ctx = _wt(tmp_path / "wt", {"docs/v6/BP00_manifest.md": doc})
    res = checks.check_v6_skeleton_conformance(ctx)
    assert res["ok"] is False
    assert "repo-relative" in res["detail"]


def test_skeleton_bom_crlf_drop_tolerated(tmp_path):
    # Windows-authored drops arrive BOM'd + CRLF. A BOM survives a plain utf-8 decode: it
    # breaks the manifest-heading regex and is a SyntaxError to compile() — the utf-8-sig
    # read must tolerate both. Bytes written raw so no platform newline translation.
    bp = tmp_path / "docs" / "v6"
    bp.mkdir(parents=True)
    (bp / "BP00_manifest.md").write_bytes(b"\xef\xbb\xbf" + BP00_OK.replace("\n", "\r\n").encode("utf-8"))
    stub = tmp_path / "python" / "synapse" / "v6"
    stub.mkdir(parents=True)
    (stub / "foo.py").write_bytes(b"\xef\xbb\xbf" + STUB_OK.encode("utf-8"))
    res = checks.check_v6_skeleton_conformance({"wt": str(tmp_path)})
    assert res["ok"] is True


# ---------- v6_spec_bp09 / v6_spec_bp10 ----------

BP09_OK = (
    "# BP09 — Iteration Controller\n\n"
    "## Loop Orchestration\nx\n"
    "## Convergence & Stop Logic\nx\n"
    "## Max-Iteration Handling\nx\n"
    "## Strategy Pull (BP07)\nx\n"
    "## H22 Dependencies\nx\n"
    "## Tests\nx\n"
)


def test_spec_bp09_missing_file(tmp_path):
    res = checks.check_v6_spec_bp09({"wt": str(tmp_path)})
    assert res["ok"] is False
    assert "BP09_iteration_controller.md" in res["detail"]


def test_spec_bp09_all_headings_pass(tmp_path):
    # 'Convergence & Stop Logic' is ONE heading satisfying both the Convergence and Stop terms.
    ctx = _wt(tmp_path, {"docs/v6/BP09_iteration_controller.md": BP09_OK})
    assert checks.check_v6_spec_bp09(ctx)["ok"] is True


def test_spec_bp09_missing_heading_named(tmp_path):
    ctx = _wt(tmp_path, {"docs/v6/BP09_iteration_controller.md":
                         BP09_OK.replace("## Max-Iteration Handling\nx\n", "")})
    res = checks.check_v6_spec_bp09(ctx)
    assert res["ok"] is False
    assert "Max-Iteration" in res["detail"]


def test_spec_term_in_body_text_does_not_count(tmp_path):
    # 'Tests' appears only in prose, never in a heading line — must NOT satisfy the check.
    doc = BP09_OK.replace("## Tests\nx\n", "we will add tests later\n")
    ctx = _wt(tmp_path, {"docs/v6/BP09_iteration_controller.md": doc})
    res = checks.check_v6_spec_bp09(ctx)
    assert res["ok"] is False
    assert "Tests" in res["detail"]


def test_spec_bp10_pass_and_missing_heading(tmp_path):
    ok_doc = ("# BP10\n\n## Recipe Store\nx\n## Failure DB\nx\n"
              "## Vector Schema\nx\n## Query API\nx\n## Tests\nx\n")
    ctx = _wt(tmp_path / "a", {"docs/v6/BP10_knowledge_base.md": ok_doc})
    assert checks.check_v6_spec_bp10(ctx)["ok"] is True
    ctx2 = _wt(tmp_path / "b", {"docs/v6/BP10_knowledge_base.md":
                                ok_doc.replace("## Vector Schema\nx\n", "")})
    res = checks.check_v6_spec_bp10(ctx2)
    assert res["ok"] is False
    assert "Vector Schema" in res["detail"]


# ---------- v6_kb_roundtrip / v6_tests_green ----------

def test_kb_roundtrip_module_absent_mentions_v3(tmp_path):
    # Disk check first — hermetic even after v6/ merges to the main repo (an in-process
    # import would resolve `synapse` to the repo, not this tmp worktree).
    res = checks.check_v6_kb_roundtrip({"wt": str(tmp_path)})
    assert res["ok"] is False
    assert "V.3" in res["detail"]


def test_tests_green_absent_dir_is_test_first(tmp_path):
    res = checks.check_v6_tests_green({"wt": str(tmp_path)})
    assert res["ok"] is False
    assert "test-first" in res["detail"]


# ---------- conformance: dispatch, vocabulary, tasks.json ----------

def test_v6_checks_registered_in_dispatch():
    assert V6_CHECKS <= set(checks.DISPATCH)


def test_v6_tasks_conform_to_contract():
    # Correct against the FINAL contract: validates whatever V-tasks tasks.json carries.
    # BUILDER-A lands the V entries concurrently — skip loudly (not vacuous-pass) until then.
    doc = json.loads((_REPO / "harness" / "tasks.json").read_text(encoding="utf-8"))
    v_tasks = [t for t in doc["tasks"] if str(t.get("id", "")).startswith("V.")]
    if not v_tasks:
        pytest.skip("no V-tasks in tasks.json yet (BUILDER-A pending)")
    vocab = set(doc.get("checks_vocabulary", []))
    assert {t["id"] for t in v_tasks} == {f"V.{n}" for n in range(1, 8)}
    for t in v_tasks:
        assert re.fullmatch(r"V\.\d", t["id"]), t["id"]
        assert t.get("blocked_on") == "blueprints", t["id"]
        for name in t.get("verify", []):
            assert name in checks.DISPATCH, f"{t['id']}: verify '{name}' not in DISPATCH"
            assert name in vocab, f"{t['id']}: verify '{name}' not in checks_vocabulary"


def test_tests_v6_sources_never_plant_sys_modules_fakes():
    # The repo trap: module-level sys.modules fakes leak across the whole pytest run
    # (alphabetically-first planter wins). tests/v6 is the scoped honest gate for
    # v6_tests_green — one planted fake would change what that gate proves. Vacuous while
    # tests/v6 doesn't exist; guards every future v6 test file.
    v6_dir = _REPO / "tests" / "v6"
    planters = []
    if v6_dir.is_dir():
        for f in v6_dir.rglob("*.py"):
            src = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"sys\.modules\[[^\]]+\]\s*=", src):
                planters.append(str(f.relative_to(_REPO)))
    assert not planters, f"sys.modules fake planted in: {planters} (use monkeypatch)"
