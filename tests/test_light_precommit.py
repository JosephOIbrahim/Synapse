"""Attack the provisional seam using the existing independently authored backend."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from test_recipe_transaction import Backend
from synapse.recipes.contracts import ActionId, RecoveryVerdict
from synapse.recipes.transaction import PreparedOperation, ProvisionalDecision


class ProvisionalLightTests(unittest.TestCase):
    def prepared(self, callback):
        scene = Backend()
        self.assertEqual(scene.transaction().execute().outcome, "committed")
        instance = scene.lifecycle.discover()
        op = PreparedOperation("set_parm", "/stage/key", 2.0, "exposure",
                               (("nodes", "/stage/key", "parms", "exposure"),))
        txn = scene.transaction(instance, action=ActionId.LIGHT, approved=True,
                                slots={"exposure": 2.0}, operations=(op,), precommit=callback)
        return scene, txn

    def test_accept_is_provisional_and_inputs_are_detached(self):
        seen = []
        def evaluate(before, after):
            self.assertTrue(txn._owned)
            self.assertEqual(scene.lifecycle.discover().graph_revision, 1)
            self.assertEqual(after["nodes"]["/stage/key"]["parms"]["exposure"], 2.0)
            seen.append(deepcopy(after))
            before.clear()
            after.clear()
            return ProvisionalDecision(True, "measured local objective met")
        scene, txn = self.prepared(evaluate)
        self.assertEqual(txn.execute().outcome, "committed")
        self.assertEqual(len(seen), 1)
        self.assertEqual(scene.lifecycle.discover().graph_revision, 2)
        self.assertFalse(txn._owned)

    def test_reject_restores_before_second_composed_action(self):
        scene, txn = self.prepared(lambda *_: ProvisionalDecision(False, "measured tension rejected"))
        before = scene.snapshot()
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertEqual(scene.lifecycle.discover().graph_revision, 1)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.undo_calls, 1)
        self.assertEqual(scene.snapshot(), before)
        instance = scene.lifecycle.discover()
        second = scene.transaction(instance, action=ActionId.LIGHT, approved=True,
                                   slots={"exposure": 2.0}, operations=txn.operations,
                                   precommit=lambda *_: ProvisionalDecision(True, "second measured candidate"))
        self.assertEqual(second.execute().outcome, "committed")
        self.assertEqual(scene.lifecycle.discover().graph_revision, 2)

    def test_truthy_or_missing_decision_never_commits(self):
        for value in (True, {"accepted": True}, None):
            with self.subTest(value=value):
                scene, txn = self.prepared(lambda *_: value)
                before = scene.snapshot()
                self.assertEqual(txn.execute().outcome, "failed")
                self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
                self.assertEqual(scene.snapshot(), before)

    def test_evaluator_exception_is_recoverable_rejection(self):
        def unavailable(*_):
            raise TimeoutError("local evaluator did not finish")
        scene, txn = self.prepared(unavailable)
        before = scene.snapshot()
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.snapshot(), before)

    def test_unexplained_candidate_change_quarantines_without_undo(self):
        def changed(*_):
            scene.nodes["/stage/key"]["parms"]["exposure"] = 7
            return ProvisionalDecision(True, "stale measurement")
        scene, txn = self.prepared(changed)
        self.assertEqual(txn.execute().outcome, "failed")
        current = scene.snapshot()
        self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
        self.assertEqual(scene.undo_calls, 0)
        self.assertEqual(scene.snapshot(), current)

    def test_foreign_edit_during_evaluation_quarantines_without_undo(self):
        def foreign(*_):
            scene.nodes["/stage/artist"]["parms"]["note"] = "foreign edit survives"
            scene.foreign += 1
            return ProvisionalDecision(True, "measurement predates foreign edit")
        scene, txn = self.prepared(foreign)
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
        self.assertEqual(scene.undo_calls, 0)
        self.assertEqual(scene.nodes["/stage/artist"]["parms"]["note"], "foreign edit survives")
        self.assertTrue(txn._owned)

    def test_cancel_during_evaluation_recovers(self):
        def cancel(*_):
            txn.cancel()
            return ProvisionalDecision(True, "result arrived after cancellation")
        scene, txn = self.prepared(cancel)
        before = scene.snapshot()
        self.assertEqual(txn.execute().outcome, "cancelled")
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.snapshot(), before)

    def test_dependency_drift_during_evaluation_rejects(self):
        def drift(*_):
            scene.deps["asset"] = "changed"
            return ProvisionalDecision(True, "dependencies became stale")
        scene, txn = self.prepared(drift)
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
        self.assertEqual(scene.undo_calls, 0)

    def test_hook_cannot_remove_existing_approval_or_extend_other_actions(self):
        scene, txn = self.prepared(lambda *_: ProvisionalDecision(True, "local only"))
        txn.approved = False
        self.assertEqual(txn.execute().outcome, "failed")
        self.assertEqual(scene.apply_calls, 1)  # the original fixture BUILD only
        with self.assertRaisesRegex(ValueError, "only for LIGHT"):
            scene.transaction(scene.lifecycle.discover(),
                              precommit=lambda *_: ProvisionalDecision(True, "not LIGHT"))

    def test_rejected_or_throwing_callback_cannot_skip_dependency_or_revision_custody(self):
        for drift in ('dependency', 'revision'):
            for ending in ('reject', 'raise'):
                with self.subTest(drift=drift, ending=ending):
                    def changed(*_):
                        if drift == 'dependency':
                            scene.deps['asset'] = 'changed-during-rejected-callback'
                        else:
                            current = scene.lifecycle.discover()
                            token = scene.lifecycle._tokens[current.instance_id]
                            scene.lifecycle.store.save(token, replace(current, graph_revision=current.graph_revision + 1))
                        if ending == 'raise':
                            raise TimeoutError('evaluator unavailable after foreign policy change')
                        return ProvisionalDecision(False, 'candidate rejected after foreign policy change')
                    scene, txn = self.prepared(changed)
                    self.assertEqual(txn.execute().outcome, 'failed')
                    after = scene.snapshot()
                    self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
                    self.assertEqual(scene.undo_calls, 0)
                    self.assertEqual(scene.snapshot(), after)

    def test_cancellation_after_metadata_commit_decision_cannot_claim_it_stopped(self):
        scene, txn = self.prepared(lambda *_: ProvisionalDecision(True, 'measured acceptance'))
        commit = scene.lifecycle.commit
        late = []
        def cancel_after_decision(*args, **kwargs):
            late.append(txn.cancel())
            return commit(*args, **kwargs)
        scene.lifecycle.commit = cancel_after_decision
        self.assertEqual(txn.execute().outcome, 'committed')
        self.assertEqual(scene.lifecycle.discover().graph_revision, 2)
        self.assertEqual(late, [False])

    def test_deadline_crossed_during_callback_refuses_commit_and_restores(self):
        clock = [10]
        def late(*_):
            clock[0] = 100
            return ProvisionalDecision(True, 'acceptance arrived after deadline')
        scene, txn = self.prepared(late)
        before = scene.snapshot()
        txn.deadline_ns = 50
        with patch('time.perf_counter_ns', lambda: clock[0]):
            self.assertEqual(txn.execute().outcome, 'failed')
        self.assertIn('deadline', txn.result.reason)
        self.assertEqual(txn.recover(), RecoveryVerdict.RESTORED)
        self.assertEqual(scene.snapshot(), before)
        self.assertEqual(scene.lifecycle.discover().graph_revision, 1)

    def test_expired_provisional_deadline_refuses_before_mutation(self):
        scene, txn = self.prepared(lambda *_: ProvisionalDecision(True, 'too late'))
        before = scene.snapshot()
        txn.deadline_ns = 1
        with patch('time.perf_counter_ns', lambda: 2):
            self.assertEqual(txn.execute().outcome, 'failed')
        self.assertEqual(scene.apply_calls, 1)  # fixture BUILD only
        self.assertEqual(scene.snapshot(), before)
        self.assertEqual(scene.lifecycle.discover().graph_revision, 1)

    def test_late_dependency_or_metadata_change_quarantines_before_recovery(self):
        for drift in ('dependency', 'revision'):
            with self.subTest(drift=drift):
                scene, txn = self.prepared(lambda *_: ProvisionalDecision(False, 'restore candidate'))
                self.assertEqual(txn.execute().outcome, 'failed')
                candidate = scene.snapshot()
                expected_metadata = deepcopy(scene.lifecycle.discover())
                expected_dependencies = deepcopy(scene.deps)
                if drift == 'dependency':
                    scene.deps['asset'] = 'changed-after-terminal-before-recovery'
                    expected_dependencies['asset'] = 'changed-after-terminal-before-recovery'
                else:
                    live = scene.lifecycle.discover()
                    token = scene.lifecycle._tokens[live.instance_id]
                    expected_metadata = replace(expected_metadata, graph_revision=expected_metadata.graph_revision + 1)
                    scene.lifecycle.store.save(token, deepcopy(expected_metadata))
                self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
                self.assertEqual(scene.undo_calls, 0)
                self.assertEqual(scene.snapshot(), candidate)
                self.assertTrue(txn._owned)
                self.assertEqual(scene.lifecycle.discover(), expected_metadata)
                self.assertEqual(scene.deps, expected_dependencies)

    def test_dependency_or_metadata_drift_during_undo_cannot_release_quarantine(self):
        for drift in ('dependency', 'revision'):
            with self.subTest(drift=drift):
                scene, txn = self.prepared(lambda *_: ProvisionalDecision(False, 'restore candidate'))
                before = scene.snapshot()
                expected = {'metadata': deepcopy(scene.lifecycle.discover()), 'dependencies': deepcopy(scene.deps)}
                self.assertEqual(txn.execute().outcome, 'failed')
                real_undo = scene.perform_undo
                def undo_then_drift():
                    real_undo()
                    if drift == 'dependency':
                        scene.deps['asset'] = 'changed-during-undo'
                        expected['dependencies']['asset'] = 'changed-during-undo'
                    else:
                        live = scene.lifecycle.discover()
                        token = scene.lifecycle._tokens[live.instance_id]
                        original = expected['metadata']
                        expected['metadata'] = replace(original, graph_revision=original.graph_revision + 1)
                        scene.lifecycle.store.save(token, deepcopy(expected['metadata']))
                scene.perform_undo = undo_then_drift
                self.assertEqual(txn.recover(), RecoveryVerdict.RESIDUE)
                self.assertEqual(scene.undo_calls, 1)
                self.assertEqual(scene.snapshot(), before)
                self.assertTrue(txn._owned)
                self.assertEqual(scene.lifecycle.discover(), expected['metadata'])
                self.assertEqual(scene.deps, expected['dependencies'])



if __name__ == "__main__":
    unittest.main()
