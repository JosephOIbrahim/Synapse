"""Independent composed lifecycle falsifications; no Houdini impersonation."""
from contextlib import contextmanager
from copy import deepcopy
import unittest
from uuid import uuid4

from test_recipe_instance import Scene
from test_recipe_transaction import Backend
from synapse.recipes.contracts import ActionId, RecoveryVerdict, RefusalKind
from synapse.recipes.instance import LifecycleUnavailable, MemoryInstanceStore
from synapse.recipes.transaction import PreparedOperation


class UndoableStore(MemoryInstanceStore):
    """A HIP-like metadata store whose writes join an active undo group."""
    def __init__(self, scene):
        super().__init__()
        self.scene = scene

    def save(self, token, instance):
        before = self.scene.snapshot()
        super().save(token, instance)
        if not self.scene.group_active and self.scene.snapshot() != before:
            self.scene.stack.append(("instance metadata", before))


class UndoableMetadataBackend(Backend):
    def __init__(self):
        super().__init__()
        self.group_active = False
        self.store = UndoableStore(self)
        self.lifecycle.store = self.store

    def snapshot(self):
        state = super().snapshot()
        state["metadata"] = deepcopy(self.store._records)
        return state

    @contextmanager
    def undo_group(self, label):
        before = self.snapshot()
        self.groups += 1
        self.group_active = True
        try:
            yield
        finally:
            self.group_active = False
            if self.snapshot() != before:
                self.stack.append((label, before))

    def perform_undo(self):
        self.undo_calls += 1
        _, before = self.stack.pop()
        self.nodes, self.box = before["nodes"], before["box"]
        self.store._records = deepcopy(before["metadata"])


def light_edit(scene, value):
    current = scene.lifecycle.discover()
    op = PreparedOperation("set_parm", "/stage/key", value, "exposure",
                           (("nodes", "/stage/key", "parms", "exposure"),))
    return scene.transaction(current, action=ActionId.LIGHT, approved=True,
                             slots={"exposure": value}, operations=(op,)).execute()


class TransactionReviewTests(unittest.TestCase):
    def test_failed_semantic_noop_restores_session_metadata_too(self):
        scene = Backend()
        self.assertEqual(scene.transaction().execute().outcome, "committed")
        before = scene.lifecycle.discover()
        op = PreparedOperation("set_parm", "/stage/key", 0.0, "exposure",
                               (("nodes", "/stage/key", "parms", "exposure"),))
        original_group = scene.undo_group

        @contextmanager
        def fail_after_metadata_save(label):
            with original_group(label):
                yield
            raise RuntimeError("injected group-close failure after metadata save")

        scene.undo_group = fail_after_metadata_save
        txn = scene.transaction(before, action=ActionId.LIGHT, approved=True,
                                slots={"exposure": 0.0}, operations=(op,))
        result = txn.execute()
        self.assertEqual(result.outcome, "failed")
        self.assertIn("injected group-close failure", result.reason)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.lifecycle.discover(), before,
                         "RESTORED must include identity after metadata was saved")

    def test_metadata_and_graph_share_the_single_artist_undo_item(self):
        scene = UndoableMetadataBackend()
        before = scene.snapshot()
        txn = scene.transaction()
        result = txn.execute()
        self.assertEqual(result.outcome, "committed", result.reason)
        # Undo exactly once, independently of the transaction's claimed labels.
        scene.perform_undo()
        self.assertEqual(scene.snapshot(), before,
                         "one undo must restore graph AND committed identity")

    def test_stale_instance_roundtrip_cannot_return_an_old_noop_revision(self):
        scene = Backend()
        self.assertEqual(scene.transaction().execute().outcome, "committed")
        stale = scene.lifecycle.discover()
        self.assertEqual(light_edit(scene, 2.0).outcome, "committed")
        self.assertEqual(light_edit(scene, 0.0).outcome, "committed")
        current = scene.lifecycle.discover()
        self.assertEqual(current.authored_baseline, stale.authored_baseline)
        self.assertGreater(current.graph_revision, stale.graph_revision)
        result = scene.transaction(stale, expected_revision=current.graph_revision).execute()
        self.assertIsNotNone(result.refusal,
                             "a current expected revision cannot authorize stale instance data")
        self.assertEqual(result.refusal.kind, RefusalKind.STALE)

    def test_fingerprint_cannot_certify_a_replaced_instance(self):
        scene = Scene()
        stale = scene.committed()
        scene.box = None
        scene.lifetime = uuid4().hex
        current = scene.committed()
        self.assertNotEqual(stale.instance_id, current.instance_id)
        with self.assertRaises(LifecycleUnavailable):
            scene.lifecycle.fingerprint(stale)

    def test_cancellation_during_verification_is_observed_before_commit(self):
        scene = Backend()
        before = scene.snapshot()
        txn = scene.transaction()
        original_verify = scene.verify

        def verify_then_cancel(action, instance):
            checks = original_verify(action, instance)
            txn.cancel()
            return checks

        scene.verify = verify_then_cancel
        result = txn.execute()
        self.assertEqual(result.outcome, "cancelled")
        self.assertIsNone(result.revision_after)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
