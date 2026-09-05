"""T1/T2/T10/T11 with a real in-memory graph and grouped undo stack."""
from contextlib import contextmanager
from copy import deepcopy
import threading
import unittest
from uuid import uuid4

from test_recipe_instance import Scene
from synapse.recipes.contracts import (ActionId, CheckResult, CheckStatus, RecoveryVerdict,
                                      RefusalKind, REQUIRED_CHECKS, TerminalVerdict)
from synapse.recipes.transaction import (BuildState, BuildTransaction, Ownership,
                                        PreparedOperation, TransactionRegistry)


class Backend(Scene):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.undo_calls = self.apply_calls = 0
        self.groups = 0
        self.foreign = 0
        self.deps = {"asset": "content-1"}
        self.fail = False
        self.hook = None
        self.preflight_hook = None
        self.enabled = True
        self.verify_status = CheckStatus.PASS

    def preflight(self, operations):
        if self.preflight_hook:
            self.preflight_hook()

    def dependencies(self):
        return deepcopy(self.deps)

    def snapshot(self):
        return deepcopy({"nodes": self.nodes, "box": self.box})

    def foreign_epoch(self):
        return self.foreign

    def undo_enabled(self):
        return self.enabled

    def undo_labels(self):
        return tuple(label for label, _ in reversed(self.stack))

    @contextmanager
    def undo_group(self, label):
        before = self.snapshot()
        self.groups += 1
        try:
            yield
        finally:
            if self.snapshot() != before:
                self.stack.append((label, before))

    def perform_undo(self):
        self.undo_calls += 1
        _, before = self.stack.pop()
        self.nodes, self.box = before["nodes"], before["box"]

    def apply(self, op):
        self.apply_calls += 1
        if op.kind == "create_scope":
            self.populate()
        else:
            self.nodes[op.target]["parms"][op.field] = deepcopy(op.value)
        if self.hook:
            self.hook()
        if self.fail:
            raise RuntimeError("injected partial mutation failure")

    def verify(self, action, instance):
        return [CheckResult(c, self.verify_status, "in-memory control") for c in REQUIRED_CHECKS[action]]

    def transaction(self, instance=None, **kwargs):
        if instance is None:
            instance = self.lifecycle.new_instance(self.ids)
        op = PreparedOperation("create_scope", self.lifecycle.box_name,
                               writes=(("box",), ("nodes", "/stage/key"),
                                       ("nodes", "/stage/material/hero")))
        defaults = dict(request_id=uuid4().hex, instance=instance, lifecycle=self.lifecycle,
                        backend=self, operations=(op,), expected_revision=instance.graph_revision,
                        dependencies=self.dependencies(), dispatch=lambda fn: fn(), ownership=Ownership())
        defaults.update(kwargs)
        return BuildTransaction(**defaults)


class TransactionTests(unittest.TestCase):
    def test_t1_build_twice_is_measured_noop(self):
        scene = Backend()
        build = scene.transaction()
        first = build.execute()
        self.assertEqual(first.outcome, "committed")
        self.assertEqual(build.history, list(BuildState))
        before = scene.snapshot()
        instance = scene.lifecycle.discover()
        repeat = scene.transaction(instance).execute()
        self.assertEqual(repeat.outcome, "noop")
        self.assertEqual(repeat.revision_after, first.revision_after)
        self.assertEqual(repeat.fingerprint_before, repeat.fingerprint_after)
        self.assertEqual(repeat.recovery, RecoveryVerdict.NOT_NEEDED)
        self.assertEqual(scene.snapshot(), before)
        self.assertEqual((scene.apply_calls, scene.groups), (1, 1))

    def test_t2_artist_change_conflicts_without_repair(self):
        scene = Backend()
        scene.transaction().execute()
        instance = scene.lifecycle.discover()
        scene.nodes["/stage/key"]["parms"]["exposure"] = 4
        scene.nodes["/stage/artist"]["authored_opinion"] = "survive"
        before = scene.snapshot()
        result = scene.transaction(instance).execute()
        self.assertEqual(result.refusal.kind, RefusalKind.CONFLICT)
        self.assertEqual(scene.snapshot(), before)
        self.assertEqual(scene.apply_calls, 1)

    def test_approved_edit_rebaselines_then_build_does_not_reset_it(self):
        scene = Backend()
        scene.transaction().execute()
        instance = scene.lifecycle.discover()
        op = PreparedOperation("set_parm", "/stage/key", 2.0, "exposure",
                               (("nodes", "/stage/key", "parms", "exposure"),))
        result = scene.transaction(instance, action=ActionId.LIGHT, approved=True,
                                   slots={"exposure": 2.0}, operations=(op,)).execute()
        self.assertEqual(result.outcome, "committed")
        current = scene.lifecycle.discover()
        self.assertEqual(current.graph_revision, instance.graph_revision + 1)
        self.assertEqual(current.committed_slots, {"exposure": 2.0})
        self.assertEqual(scene.transaction(current).execute().outcome, "noop")
        self.assertEqual(scene.nodes["/stage/key"]["parms"]["exposure"], 2.0)

    def test_revision_and_dependencies_rechecked_after_preflight(self):
        scene = Backend()
        scene.preflight_hook = lambda: scene.deps.update(asset="changed")
        result = scene.transaction().execute()
        self.assertEqual(result.refusal.kind, RefusalKind.STALE)
        self.assertEqual(scene.apply_calls, 0)

    def test_failure_is_terminal_before_single_clean_rollback(self):
        scene = Backend()
        before = scene.snapshot()
        scene.fail = True
        txn = scene.transaction()
        scene.hook = lambda: self.assertRaisesRegex(RuntimeError, "await_terminal", txn.recover)
        result = txn.execute()
        self.assertEqual(txn.state, BuildState.TERMINAL)
        self.assertTrue(result.residual_diff)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.undo_calls, 1)
        self.assertEqual(scene.snapshot(), before)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.verdict, TerminalVerdict.BROKEN)

    def test_another_undo_head_blocks_global_undo_and_quarantines_scope(self):
        scene = Backend()
        scene.fail = True
        owners = Ownership()
        txn = scene.transaction(ownership=owners)
        txn.execute()
        with scene.undo_group("artist"):
            scene.nodes["/stage/artist"]["parms"]["note"] = "new opinion"
        self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
        self.assertEqual(scene.undo_calls, 0)
        self.assertTrue(txn.result.residual_diff)
        retry = scene.transaction(txn.instance, ownership=owners).execute()
        self.assertEqual(retry.refusal.kind, RefusalKind.CONFLICT)

    def test_untracked_or_intervening_artist_edit_refuses_undo_even_same_head(self):
        for foreign in (None, 1):
            with self.subTest(foreign=foreign):
                scene = Backend()
                scene.fail = True
                txn = scene.transaction()
                txn.execute()
                scene.foreign = foreign
                self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
                self.assertEqual(scene.undo_calls, 0)

    def test_timeout_is_not_terminal_and_does_not_race_apply(self):
        scene = Backend()
        entered, release = threading.Event(), threading.Event()
        workers = []
        def hold():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test release did not arrive")
        scene.hook = hold
        scene.fail = True
        def dispatcher(fn):
            worker = threading.Thread(target=fn)
            workers.append(worker)
            worker.start()
            self.assertTrue(entered.wait(2))
            raise TimeoutError("UI wait expired")
        txn = scene.transaction(dispatch=dispatcher)
        try:
            txn.execute()
            self.assertEqual(txn.state, BuildState.MUTATING)
            self.assertIsNone(txn.await_terminal(0))
            with self.assertRaisesRegex(RuntimeError, "await_terminal"):
                txn.recover()
            txn.execute()  # response retry on same object must not re-dispatch
            self.assertEqual(scene.apply_calls, 1)
        finally:
            release.set()
            for worker in workers:
                worker.join(2)
        self.assertIsNotNone(txn.await_terminal(1))
        txn.dispatch = lambda fn: fn()
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)

    def test_queued_callback_is_fenced_after_dispatch_failure(self):
        scene = Backend()
        queued = []
        def dispatcher(fn):
            queued.append(fn)
            raise TimeoutError("not entered")
        txn = scene.transaction(dispatch=dispatcher)
        txn.execute()
        queued[0]()
        self.assertEqual(scene.apply_calls, 0)
        self.assertEqual(txn.state, BuildState.TERMINAL)

    def test_cancel_during_apply_is_acknowledged_only_after_apply_returns(self):
        scene = Backend()
        txn = scene.transaction()
        scene.hook = txn.cancel
        result = txn.execute()
        self.assertEqual(result.outcome, "cancelled")
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(result.verdict, TerminalVerdict.CANCELLED)

    def test_missing_undo_evidence_refuses_before_any_write(self):
        scene = Backend()
        scene.enabled = None
        result = scene.transaction().execute()
        self.assertIn("UNAVAILABLE", result.reason)
        self.assertEqual((scene.apply_calls, scene.groups), (0, 0))

    def test_t11_reset_new_request_rebuilds_same_request_never_duplicates(self):
        scene = Backend()
        registry = TransactionRegistry()
        first = registry.get_or_create("one", {"action": "build"}, scene.transaction)
        first.execute()
        self.assertIs(registry.get_or_create("one", {"action": "build"}, scene.transaction), first)
        scene.nodes = {"/stage/artist": scene.nodes["/stage/artist"]}
        scene.box = None
        scene.lifetime = uuid4().hex
        again = registry.get_or_create("two", {"action": "build"}, scene.transaction)
        self.assertNotEqual(again.result.run_id, first.result.run_id)
        self.assertEqual(again.execute().outcome, "committed")
        self.assertEqual(scene.apply_calls, 2)
        mismatch = registry.get_or_create("one", {"action": "edit"}, scene.transaction)
        self.assertEqual(mismatch.kind, RefusalKind.DUPLICATE_REQUEST)

    def test_unrelated_write_in_prepared_apply_is_detected(self):
        scene = Backend()
        scene.hook = lambda: scene.nodes["/stage/artist"].update(unwanted=True)
        txn = scene.transaction()
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertIn("escaped", txn.result.reason)

    def test_required_verification_failure_cannot_commit(self):
        scene = Backend()
        scene.verify_status = CheckStatus.NOT_RUN
        txn = scene.transaction()
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertIsNone(txn.result.revision_after)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)


class _FakeUndos:
    """Stands in for the hou.undos SWIG namespace (all four members live-verified
    on 22.0.400 and carried by the committed h22 symbol table)."""
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.labels = []
        self.performed = 0
        self.groups = []

    def areEnabled(self):
        return self.enabled

    def undoLabels(self):
        return tuple(reversed(self.labels))

    @contextmanager
    def group(self, label):
        self.groups.append(label)
        yield
        self.labels.append(label)

    def performUndo(self):
        self.performed += 1
        self.labels.pop()


class HoudiniUndoDriverTests(unittest.TestCase):
    """CTO B2: transaction.py is bound to hou.undos (its docstring refusal is gone)."""

    def test_driver_maps_every_backend_undo_method_onto_hou_undos(self):
        from synapse.recipes.transaction import HoudiniUndoDriver
        undos = _FakeUndos()
        driver = HoudiniUndoDriver(undos=undos)
        self.assertIs(driver.undo_enabled(), True)
        self.assertEqual(driver.undo_labels(), ())
        with driver.undo_group("SYNAPSE recipe x"):
            pass
        self.assertEqual(undos.groups, ["SYNAPSE recipe x"])
        self.assertEqual(driver.undo_labels(), ("SYNAPSE recipe x",))
        driver.perform_undo()
        self.assertEqual(undos.performed, 1)
        self.assertEqual(driver.undo_labels(), ())

    def test_driver_reports_unknown_not_false_when_hou_undos_is_absent(self):
        from synapse.recipes.transaction import HoudiniUndoDriver
        driver = HoudiniUndoDriver(resolve=lambda: None)   # no hou in this process
        self.assertIsNone(driver.undo_enabled())     # None => the transaction refuses before any write
        self.assertIsNone(driver.undo_labels())
        with self.assertRaises(RuntimeError):
            with driver.undo_group("x"):
                pass

    def test_driver_none_evidence_refuses_transaction_before_write(self):
        from synapse.recipes.transaction import HoudiniUndoDriver
        scene = Backend()
        driver = HoudiniUndoDriver(resolve=lambda: None)
        scene.undo_enabled = driver.undo_enabled
        scene.undo_labels = driver.undo_labels
        result = scene.transaction().execute()
        self.assertEqual(result.outcome, "failed")
        self.assertIn("UNAVAILABLE", result.reason)
        self.assertEqual(scene.apply_calls, 0)
