"""Runner controls. Synthetic observations qualify the runner, never product rows.

unittest compatibility lets these controls run when pytest itself is unavailable.
The subprocess integration controls always use real pytest and no repo conftest.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import solaris_v3_accept as accept


class AcceptanceControls(unittest.TestCase):
    def setUp(self):
        # Keep even ephemeral test artifacts inside this worktree.
        runs = accept.ROOT / accept.RUNS_PATH
        runs.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="acceptance-control-", dir=runs)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.gates = accept.read_json(accept.ROOT / accept.GATES_PATH)
        self.row = next(copy.deepcopy(r) for r in self.gates["rows"] if r["id"] == "T4")
        self.nodeid = "tests/test_control.py::test_path"
        self.specs = [{"nodeid": self.nodeid, "intended_path": "synthetic-real-dispatch"}]
        artifact = self.directory / "control.json"
        artifact.write_text('{"observed": true}', encoding="utf-8")
        self.artifact = artifact
        self.test = {"reports": [{"when": stage, "outcome": "passed", "wasxfail": False}
                                 for stage in ("setup", "call", "teardown")],
                     "evidence": [{"row_id": "T4", "receipt_id": "synthetic:test",
                                   "intended_path": "synthetic-real-dispatch",
                                   "artifact_hashes": {str(artifact): accept.sha256(artifact)}}]}
        self.tier = {"tier": "pure", "ran": True, "status": "PASS", "exit_code": 0,
                     "reason": "", "runner_command": ["python", "-m", "pytest"],
                     "log_path": str(artifact), "artifact_hashes": {str(artifact): accept.sha256(artifact)},
                     "observation": {"identity": {"commit": "a" * 40, "build": "UNAVAILABLE: pure",
                                                  "module_path": "synthetic"},
                                     "tests": {self.nodeid: self.test}}}

    def assess(self):
        return accept.assess_row(self.row, self.specs, self.tier, "synthetic")

    def test_gate_schema_and_independent_page_coverage(self):
        accept.validate_gates(self.gates)
        # Parse the actual row labels in the blueprint, not a copied numerical oracle.
        import re
        text = (accept.ROOT / "docs/SOLARIS_RECIPES_H22_BLUEPRINT_V3.md").read_text(encoding="utf-8")
        pages = text.split("## Page 10")[1].split("## Page 12")[0]
        expected = set(re.findall(r"^(G\d+|T\d+) ·", pages, flags=re.MULTILINE))
        self.assertEqual({r["id"] for r in self.gates["rows"]}, expected)
        for row in self.gates["rows"]:
            self.assertIn(row["goalpost"], pages)

    def test_initial_unbound_rows_never_claim_product_pass(self):
        for row in self.gates["rows"]:
            if row["id"] not in self.gates["promotion_rule"]["bindings"]:
                self.assertEqual(row["status"], "NOT_RUN")
                self.assertIsNone(row["evidence"])

    def test_gate_schema_rejects_duplicate_missing_and_false_green(self):
        for change in (lambda g: g["rows"].append(copy.deepcopy(g["rows"][0])),
                       lambda g: g["rows"][0].update(status="PASS"),
                       lambda g: g["promotion_rule"].update(required_evidence=[]),
                       lambda g: g["promotion_rule"].update(bindings={"T4": [{"nodeid": "tests/../outside.py::test_x", "intended_path": "x"}]})):
            with self.subTest(change=change):
                gates = copy.deepcopy(self.gates)
                change(gates)
                with self.assertRaises(ValueError):
                    accept.validate_gates(gates)

    def test_empty_provenance_and_invalid_timestamp_cannot_validate_green(self):
        for key in accept.EVIDENCE_KEYS | {"module_path"}:
            with self.subTest(key=key):
                evidence = self.assess()["evidence"]
                evidence[key] = None
                with self.assertRaises(ValueError):
                    accept.validate_evidence(evidence, "pure")
        gates = copy.deepcopy(self.gates)
        row = self.assess()
        row["last_run"] = "not-a-timestamp"
        gates["rows"] = [row if r["id"] == row["id"] else r for r in gates["rows"]]
        with self.assertRaises(ValueError):
            accept.validate_gates(gates)

    def test_exact_bound_completed_control_can_promote(self):
        measured = self.assess()
        self.assertEqual(measured["status"], "PASS")
        self.assertTrue(accept.EVIDENCE_KEYS <= measured["evidence"].keys())
        self.assertEqual(measured["evidence"]["commit"], "a" * 40)

    def test_skipped_phase_never_promotes_even_with_evidence(self):
        for phase in range(3):
            with self.subTest(phase=phase):
                self.test["reports"][phase]["outcome"] = "skipped"
                self.assertEqual(self.assess()["status"], "NOT_RUN")
                self.assertIsNone(self.assess()["evidence"])
                self.test["reports"][phase]["outcome"] = "passed"

    def test_xfail_and_xpass_are_not_product_passes(self):
        self.test["reports"][1]["wasxfail"] = True
        self.assertEqual(self.assess()["status"], "NOT_RUN")

    def test_a_missing_teardown_cannot_promote(self):
        self.test["reports"].pop()
        self.assertEqual(self.assess()["status"], "UNKNOWN")

    def test_skip_does_not_hide_an_actual_failure(self):
        self.test["reports"][0]["outcome"] = "skipped"
        self.test["reports"][2]["outcome"] = "failed"
        self.assertEqual(self.assess()["status"], "FAIL")

    def test_wrong_path_missing_receipt_and_changed_artifact_are_unknown(self):
        self.test["evidence"][0]["intended_path"] = "wrong-path"
        self.assertEqual(self.assess()["status"], "UNKNOWN")
        self.test["evidence"][0]["intended_path"] = "synthetic-real-dispatch"
        self.artifact.write_text("changed after receipt", encoding="utf-8")
        self.assertEqual(self.assess()["status"], "UNKNOWN")
        self.test["evidence"] = []
        self.assertEqual(self.assess()["status"], "UNKNOWN")

    def test_a_missing_bound_test_cannot_promote(self):
        self.specs.append({"nodeid": "tests/test_control.py::test_missing", "intended_path": "missing"})
        self.assertEqual(self.assess()["status"], "NOT_RUN")

    def test_suite_green_without_binding_never_promotes(self):
        self.specs = []
        self.assertEqual(self.assess()["status"], "NOT_RUN")

    def test_tier_that_did_not_run_stays_not_run(self):
        self.tier.update(ran=False, reason="no host")
        self.assertEqual(self.assess()["status"], "NOT_RUN")
        self.assertIsNone(self.assess()["last_run"])

    def test_empty_collection_is_an_unrun_tier_even_with_identity(self):
        def run_logged(command, root, env, log, timeout):
            Path(log).write_text("no tests ran", encoding="utf-8")
            context = accept.read_json(env[accept.CONTEXT_ENV])
            accept.write_json(context["result_file"], {"identity": self.tier["observation"]["identity"], "tests": {}})
            return 5, None
        with patch.object(accept, "run_logged", run_logged):
            result = accept.run_tier("pure", sys.executable, ["tests/empty.py"],
                                     accept.ROOT, self.directory, self.gates, 10)
        self.assertFalse(result["ran"])
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertIn("no tests collected", result["reason"])

    def test_second_run_skip_clears_prior_pass_only_in_executed_tier(self):
        gates = copy.deepcopy(self.gates)
        first = self.assess()
        gates["rows"] = [first if r["id"] == "T4" else r for r in gates["rows"]]
        self.test["reports"][1]["outcome"] = "skipped"
        current = [self.assess() if r["id"] == "T4" else copy.deepcopy(r) for r in gates["rows"]]
        updated = accept.update_gates(gates, current, [self.tier])
        self.assertEqual(next(r for r in updated["rows"] if r["id"] == "T4")["status"], "NOT_RUN")
        # Selecting GUI alone cannot overwrite a historical pure-tier receipt.
        untouched = accept.update_gates(gates, current, [{"tier": "gui", "ran": False}])
        self.assertEqual(untouched, gates)

    def test_wrong_checkout_refuses_before_git_lookup(self):
        sibling = accept.ROOT.parent / (accept.ROOT.name + "-sibling") / "python/synapse/__init__.py"
        with patch.object(accept, "git") as git:
            with self.assertRaisesRegex(accept.BindingError, "wrong checkout"):
                accept.checkout_identity(accept.ROOT, sibling)
            git.assert_not_called()

    def test_collected_file_must_match_actual_loaded_test_module(self):
        source = accept.ROOT / "tests/test_solaris_v3_acceptance_runner.py"
        expected = {source.relative_to(accept.ROOT).as_posix(): accept.sha256(source)}
        self.assertEqual(accept.bind_test_source(accept.ROOT, source, source, expected),
                         (str(source), accept.sha256(source)))
        with self.assertRaisesRegex(accept.BindingError, "wrong test module"):
            accept.bind_test_source(accept.ROOT, source, accept.ROOT / "tests/test_solaris_v3_acceptance_bench.py", expected)
        with self.assertRaisesRegex(accept.BindingError, "selected source"):
            accept.bind_test_source(accept.ROOT, source, source, {next(iter(expected)): "0" * 64})

    def test_commit_is_read_at_actual_imported_checkout(self):
        calls = []
        def git(root, *args):
            calls.append((Path(root), args))
            return str(accept.ROOT) if args[-1] == "--show-toplevel" else "b" * 40 if args[-1] == "HEAD" else ""
        with patch.object(accept, "git", git):
            identity = accept.checkout_identity(accept.ROOT, accept.ROOT / "python/synapse/__init__.py")
        self.assertEqual(identity["commit"], "b" * 40)
        self.assertIn((accept.ROOT, ("rev-parse", "HEAD")), calls)

    def test_untracked_source_is_bound_and_marks_identity_dirty(self):
        source = accept.ROOT / "scripts/solaris_v3_accept.py"
        def git(root, *args):
            if args[-1] == "--show-toplevel":
                return str(accept.ROOT)
            if args[0] == "ls-files":
                return "scripts/solaris_v3_accept.py"
            return "a" * 40 if args[-1] == "HEAD" else ""
        with patch.object(accept, "git", git):
            identity = accept.checkout_identity(accept.ROOT, accept.ROOT / "python/synapse/__init__.py")
        self.assertTrue(identity["dirty"])
        self.assertEqual(identity["untracked_source_hashes"], {"scripts/solaris_v3_accept.py": accept.sha256(source)})

    def test_failed_report_cannot_be_masked_by_zero_process_exit(self):
        self.test["reports"][1]["outcome"] = "failed"
        def run_logged(command, root, env, log, timeout):
            Path(log).write_text("pytest custom hook forced exit zero", encoding="utf-8")
            context = accept.read_json(env[accept.CONTEXT_ENV])
            accept.write_json(context["result_file"], self.tier["observation"])
            return 0, None
        with patch.object(accept, "run_logged", run_logged):
            result = accept.run_tier("pure", sys.executable, ["tests/control.py"],
                                     accept.ROOT, self.directory, self.gates, 10)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(accept.exit_code([result], []), 1)

    def test_absent_globs_are_explicit_not_run(self):
        files, reasons = accept.discover(self.directory)
        self.assertEqual(files, [])
        self.assertEqual(reasons, [f"NOT_RUN: no tests collected for {g}" for g in accept.PURE_GLOBS])

    def test_explicit_hython_is_not_replaced_by_newest(self):
        self.assertEqual(accept.hython_candidates(accept.ROOT, {"SYNAPSE_HYTHON": "pin-does-not-exist"}), ["pin-does-not-exist"])

    def test_existing_shim_candidates_are_filtered_to_pinned_build(self):
        candidates = accept.hython_candidates(accept.ROOT, {})
        self.assertTrue(all("22.0.400" in p for p in candidates))
        self.assertFalse(any("22.0.429" in p for p in candidates))
        # A substring check alone is fake-green: a stringified (path, reason)
        # tuple still contains "22.0.400" but is not an executable path
        # (B10 repair, 2026-09-05). Each candidate must be a plain hython path.
        for p in candidates:
            self.assertFalse(p.startswith("("), f"candidate is not a plain path: {p!r}")
            self.assertTrue(p.replace("\\", "/").endswith(("/bin/hython.exe", "/bin/hython")),
                            f"candidate is not a hython path: {p!r}")

    def test_exit_semantics(self):
        self.assertEqual(accept.exit_code([self.tier], [self.assess()]), 0)
        for code in (1, 2, 3, 4, 124, 127):
            with self.subTest(code=code):
                tier = {**self.tier, "exit_code": code, "status": "FAIL"}
                self.assertNotEqual(accept.exit_code([tier], []), 0)
        self.assertEqual(accept.exit_code([{"status": "NOT_RUN", "exit_code": 5}], []), 0)
        self.assertEqual(accept.exit_code([{"status": "NOT_RUN", "exit_code": None}], []), 0)
        self.assertEqual(accept.exit_code([], [{"status": "FAIL"}]), 1)

    def test_ledger_schema_and_unrun_promotion_rejection(self):
        rows = [self.assess() if r["id"] == "T4" else {**r, "reason": "not selected"} for r in self.gates["rows"]]
        ledger = {"schema_version": 1, "run_id": "synthetic", "runner_command": ["python"],
                  "tiers": [self.tier], "rows": rows, "exit_code": 0}
        accept.validate_ledger(ledger)
        ledger["tiers"][0]["ran"] = False
        with self.assertRaisesRegex(ValueError, "unbound or unrun"):
            accept.validate_ledger(ledger)

    def test_emitter_rejects_old_external_artifacts(self):
        plugin = accept.AcceptancePlugin({"run_id": "synthetic", "evidence_dir": str(self.directory / "fresh")})
        with self.assertRaisesRegex(ValueError, "this run"):
            plugin.emit(self.nodeid, "T4", "path", [self.artifact])

    def test_invalid_timeout_refuses(self):
        for value in ("0", "-1", "nan", "inf"):
            self.assertEqual(accept.main(["--timeout", value]), 2)

    @unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest is not installed; subprocess integration NOT_RUN")
    def test_real_pytest_reports_skip_fail_wrong_path_and_evidence(self):
        # Isolated conftest-free tests exercise plugin mechanics with real pytest.
        # They cannot run a product gate or touch hou/pxr.
        context = {"run_id": "synthetic", "root": str(accept.ROOT), "tier": "pure",
                   "result_file": str(self.directory / "observations.json"),
                   "evidence_dir": str(self.directory / "fresh")}
        Path(context["evidence_dir"]).mkdir()
        config = self.directory / "pytest.ini"
        config.write_text("[pytest]\n", encoding="utf-8")
        tests = self.directory / "test_control.py"
        tests.write_text('''import pytest
def test_pass(solaris_acceptance_evidence):
    path = solaris_acceptance_evidence.directory / "proof.json"
    path.write_text('{"observed": true}')
    solaris_acceptance_evidence("T4", "observed-dispatch", [path])
@pytest.mark.skip(reason="missing host")
def test_skip():
    assert False
def test_fail():
    assert False, "deliberate negative control"
''', encoding="utf-8")
        context_path = self.directory / "context.json"
        accept.write_json(context_path, context)
        env = accept.subprocess_env(accept.ROOT)
        env[accept.CONTEXT_ENV] = str(context_path)
        proc = subprocess.run([sys.executable, "-m", "pytest", str(tests), "--noconftest",
                               "-c", str(config), "-p", "no:cacheprovider", "-p", "scripts.solaris_v3_accept"],
                              cwd=accept.ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        observed = accept.read_json(context["result_file"])
        self.assertIsNone(observed["binding_error"], observed)
        outcomes = {node.split("::")[-1]: accept.phase_status(test) for node, test in observed["tests"].items()}
        self.assertEqual(outcomes, {"test_pass": "PASS", "test_skip": "NOT_RUN", "test_fail": "FAIL"})
        test = next(test for node, test in observed["tests"].items() if node.endswith("::test_pass"))
        self.assertEqual(test["evidence"][0]["intended_path"], "observed-dispatch")

    @unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest is not installed; subprocess integration NOT_RUN")
    def test_real_pytest_refuses_actual_wrong_checkout(self):
        context = {"run_id": "synthetic-wrong-tree", "root": str(self.directory), "tier": "pure",
                   "result_file": str(self.directory / "observations.json")}
        context_path = self.directory / "context.json"
        accept.write_json(context_path, context)
        config = self.directory / "pytest.ini"
        config.write_text("[pytest]\n", encoding="utf-8")
        tests = self.directory / "test_binding.py"
        tests.write_text("def test_must_never_run():\n    assert False\n", encoding="utf-8")
        env = accept.subprocess_env(accept.ROOT)
        env[accept.CONTEXT_ENV] = str(context_path)
        proc = subprocess.run([sys.executable, "-m", "pytest", str(tests), "--noconftest", "-c", str(config),
                               "-p", "no:cacheprovider", "-p", "scripts.solaris_v3_accept"],
                              cwd=accept.ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        observed = accept.read_json(context["result_file"])
        self.assertIn("wrong checkout", observed["binding_error"])
        self.assertFalse(observed["tests"])


if __name__ == "__main__":
    unittest.main()
