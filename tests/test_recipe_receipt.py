"""Receipt controls use measured inputs, never a golden-scene substitute."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys

import tempfile
import unittest
from unittest.mock import patch

from synapse.recipes.contracts import (
    ActionId, ApprovalBinding, CheckId, CheckResult, CheckStatus, OperationState,
    RecoveryVerdict, RunReceipt, TerminalVerdict,
)
from synapse.recipes.receipt import (
    ReceiptStore, from_dict, ledger_path, make_receipt, receipt_from_checks, to_dict,
)


def sample_receipt(**changes):
    # These four observations describe the synthetic build in this test only.
    fields = dict(
        run_id="run-1", request_id="req-1", recipe_id="solaris.spine", recipe_version="test",
        action_id=ActionId.BUILD, instance_id="instance-1", revision_before=0, revision_after=1,
        code_identity={"commit": "test", "module": __file__, "contract": "3.0.0"},
        build="unmeasured-test-host", engine=None, dependency_identity={"asset": "sha256:one"},
        validated_slots={"color": (0.1, 0.2, 0.3), "nested": [1, {"$tuple": [2]}]},
        approval=ApprovalBinding("instance-1", 1, "test-engine", (16, 24), 2,
                                 "test.exr", "trusted-test-control", "2026-09-04T12:00:00+00:00"),
        started_at="2026-09-04T12:00:00+00:00", completed_at="2026-09-04T12:00:01+00:00",
        checks=tuple(CheckResult(cid, CheckStatus.PASS, evidence={"observed": [cid.value]})
                     for cid in (CheckId.P1_GRAPH, CheckId.P2_USD, CheckId.P4_COMPOSITION, CheckId.P6_LOCALITY)),
        fingerprint_before="before", fingerprint_after="after", operation_state=OperationState.TERMINAL,
        verdict=TerminalVerdict.VERIFIED, recovery=RecoveryVerdict.NOT_NEEDED,
        render_job={"file": {"channels": ["R", "G", "B"]}}, reason="",
    )
    return RunReceipt(**{**fields, **changes})


class ReceiptTests(unittest.TestCase):
    def test_recovery_is_separate_and_never_promotes_a_failed_build(self):
        for recovery in (RecoveryVerdict.RESTORED, RecoveryVerdict.RESIDUE, RecoveryVerdict.UNKNOWN):
            with self.assertRaisesRegex(ValueError, "cannot be VERIFIED"):
                to_dict(sample_receipt(recovery=recovery))
            failed = sample_receipt(recovery=recovery, verdict=TerminalVerdict.BROKEN, reason="Mutation failed")
            self.assertEqual(from_dict(to_dict(failed)), failed)

    def test_timestamps_require_timezone_and_terminal_completion(self):
        for changes in ({"completed_at": None}, {"completed_at": "2026-09-04T12:00:01"},
                        {"completed_at": "2026-09-04T11:00:00Z"}):
            with self.assertRaises(ValueError):
                to_dict(sample_receipt(**changes))

    def test_nonterminal_runs_are_not_persisted_as_final_receipts(self):
        receipt = sample_receipt(operation_state=OperationState.RUNNING, completed_at=None,
                                 verdict=TerminalVerdict.UNKNOWN, reason="Still running")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            with self.assertRaisesRegex(ValueError, "only terminal"):
                ReceiptStore(Path(directory) / "receipts.jsonl").append(receipt)

    def test_invalid_wire_values_cannot_be_silently_stringified(self):
        for slots in ({"sample": float("nan")}, {"opaque": object()}, {1: "wrong key"}):
            with self.assertRaises(ValueError):
                to_dict(sample_receipt(validated_slots=slots))

    def test_roundtrip_exact_including_nested_tuple_list_and_reserved_key(self):
        original = sample_receipt()
        payload = to_dict(original)
        self.assertEqual(payload["verdict"], "VERIFIED")
        self.assertEqual(payload["checks"][0]["check"], "P1")
        restored = from_dict(json.loads(json.dumps(payload, sort_keys=True)))
        self.assertEqual(restored, original)
        self.assertEqual(to_dict(restored), payload)
        self.assertIsInstance(restored.validated_slots["color"], tuple)
        self.assertIsInstance(restored.validated_slots["nested"], list)

    def test_helper_detaches_and_freezes_nested_evidence(self):
        original = sample_receipt()
        snapshot = from_dict(to_dict(original))
        original.render_job["file"]["channels"].append("A")
        self.assertEqual(snapshot.render_job["file"]["channels"], ["R", "G", "B"])
        with self.assertRaises(FrozenInstanceError):
            snapshot.reason = "changed"
        with self.assertRaises(TypeError):
            snapshot.render_job["file"]["channels"].append("A")
        with self.assertRaises(TypeError):
            snapshot.code_identity["commit"] = "forged"

    def test_reason_required(self):
        for verdict in TerminalVerdict:
            if verdict == TerminalVerdict.VERIFIED:
                continue
            for reason in ("", " "):
                with self.subTest(verdict=verdict, reason=reason):
                    with self.assertRaisesRegex(ValueError, "reason is required"):
                        to_dict(sample_receipt(verdict=verdict, reason=reason))

    def test_nonpass_check_and_missing_predicate_cannot_certify(self):
        with self.assertRaisesRegex(ValueError, "predicates"):
            to_dict(sample_receipt(checks=()))
        with self.assertRaisesRegex(ValueError, "non-PASS"):
            to_dict(sample_receipt(checks=(CheckResult(CheckId.P1_GRAPH, CheckStatus.NOT_RUN),)))
        values = vars(sample_receipt(checks=(), reason="No host observations"))
        self.assertEqual(receipt_from_checks(**values).verdict, TerminalVerdict.UNKNOWN)
        self.assertEqual(make_receipt(**vars(sample_receipt())), sample_receipt())

    def test_store_never_changes_prior_bytes_and_rejects_rewritten_run(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = ReceiptStore(Path(directory) / "receipts.jsonl")
            first = sample_receipt()
            self.assertTrue(store.append(first))
            before = store.path.read_bytes()
            self.assertFalse(store.append(first))
            with self.assertRaisesRegex(ValueError, "immutable"):
                store.append(replace(first, reason="rewritten"))
            self.assertEqual(store.path.read_bytes(), before)
            self.assertTrue(store.append(replace(first, run_id="run-2", request_id="req-2")))
            self.assertTrue(store.path.read_bytes().startswith(before))
            self.assertEqual(len(store.read_all()), 2)

    def test_atomic_replace_failure_preserves_old_ledger(self):
        import synapse.recipes.receipt as module
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = ReceiptStore(Path(directory) / "receipts.jsonl")
            store.append(sample_receipt())
            before = store.path.read_bytes()
            real_fsync = module.os.fsync
            flushed = []

            def fsync(fd):
                real_fsync(fd)
                flushed.append(True)

            def fail_replace(source, destination):
                self.assertTrue(flushed)
                self.assertEqual(Path(source).suffix, ".tmp")
                self.assertEqual(Path(destination).read_bytes(), before)
                self.assertEqual(len(Path(source).read_bytes().splitlines()), 2)
                raise OSError("injected replace failure")

            with patch.object(module.os, "fsync", fsync), patch.object(module.os, "replace", fail_replace):
                with self.assertRaisesRegex(OSError, "injected"):
                    store.append(sample_receipt(run_id="run-2"))
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [store.path])

    def test_writer_contention_and_truncated_history_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = ReceiptStore(Path(directory) / "receipts.jsonl")
            lock = store.path.with_suffix(".jsonl.lock")
            lock.touch()
            with self.assertRaises(FileExistsError):
                store.append(sample_receipt())
            lock.unlink()
            store.path.write_bytes(b'{"partial":')
            with self.assertRaisesRegex(ValueError, "incomplete"):
                store.append(sample_receipt())
            self.assertEqual(store.path.read_bytes(), b'{"partial":')

    def test_ledger_default_is_this_checkout(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ledger_path(), Path(__file__).resolve().parents[1] / "harness/solaris_v3/ledger/receipts.jsonl")
        with patch.dict(os.environ, {"SYNAPSE_RECIPE_LEDGER_DIR": str(Path.cwd())}):
            self.assertEqual(ledger_path(), Path.cwd() / "receipts.jsonl")

    def test_headless_imports_do_not_load_host_or_qt(self):
        root = Path(__file__).resolve().parents[1]
        code = """
import sys
sys.path.insert(0, 'python')
from synapse.recipes import receipt, card, freshness
from synapse.panel import recipe_card
assert 'hou' not in sys.modules
assert 'pxr' not in sys.modules
assert not any(name.startswith(('PySide', 'PyQt')) for name in sys.modules)
print(receipt.__file__)
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(root), result.stdout)


if __name__ == "__main__":
    unittest.main()
