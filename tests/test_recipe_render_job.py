"""Render job controls use local bytes, not a claimed EXR or fake Houdini."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest

from test_recipe_instance import Scene
from synapse.recipes.contracts import (ApprovalBinding, OperationState, RecoveryVerdict,
                                      Refusal, RefusalKind, TerminalVerdict)
from synapse.recipes.render_job import (BoundedRenderAdapter, RenderJob, RenderJobRegistry,
                                       RenderPlan)


class Renderer:
    def __init__(self):
        self.settings = {"artist_output": "keep.$F4.exr"}
        self.starts = self.restores = self.applies = 0
        self.foreign = 0
        self.fail = False
        self.write = True
        self.apply_hook = self.render_hook = None
        self.restore_fail = False
        self.response = {"status": "done", "logs": ["in-memory renderer terminated"]}
        self.native_terminal = True

    def capture_overrides(self, plan):
        return deepcopy(self.settings)

    def apply_overrides(self, plan):
        self.applies += 1
        self.settings = {"engine": plan.engine, "resolution": plan.resolution,
                         "samples": plan.samples, "output_path": plan.output_path}
        if self.apply_hook:
            self.apply_hook()

    def effective_scope(self, plan):
        return deepcopy(self.settings)

    def foreign_epoch(self):
        return self.foreign

    def render_terminated(self, plan):
        return self.native_terminal

    def start(self, plan):
        self.starts += 1
        if self.render_hook:
            self.render_hook()
        if self.write:
            Path(plan.output_path).write_bytes(b"test renderer bytes; image predicate NOT_RUN")
        if self.fail:
            raise RuntimeError("render failed")
        return deepcopy(self.response)

    def restore_overrides(self, plan, before):
        self.restores += 1
        if self.restore_fail:
            raise RuntimeError("injected restore failure")
        self.settings = deepcopy(before)

    def cancel(self):
        return False


class RenderJobTests(unittest.TestCase):
    def setUp(self):
        # Test artifacts stay inside this worktree and are removed on completion.
        self.temp = tempfile.TemporaryDirectory(prefix="test_recipe_render_job_", dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.scene = Scene()
        self.instance = self.scene.committed()
        self.renderer = Renderer()
        self.plan = RenderPlan.prepare(output_root=self.temp.name, node_path="/stage/render",
                                       engine="karma_cpu", resolution=(64, 64), samples=1)
        self.approval = ApprovalBinding(self.instance.instance_id, self.instance.graph_revision,
                                        self.plan.engine, self.plan.resolution, self.plan.samples,
                                        self.plan.output_path, "trusted artist", "2026-09-04T12:00:00Z")
        self.check_calls = 0

    def recheck(self, binding, instance, plan):
        self.check_calls += 1

    def job(self, **changes):
        args = dict(request_id="render-one", plan=self.plan, approval=self.approval,
                    current_instance=lambda: self.instance, recheck_approval=self.recheck,
                    backend=self.renderer, dispatch=lambda fn: fn())
        args.update(changes)
        return RenderJob(**args)

    def test_no_approval_means_no_render_or_overrides(self):
        result = self.job(approval=None).start()
        self.assertEqual((self.renderer.starts, self.renderer.applies), (0, 0))
        self.assertEqual(result.refusal.kind, RefusalKind.APPROVAL_REQUIRED)

    def test_authority_rechecked_after_overrides_immediately_before_start(self):
        self.renderer.apply_hook = lambda: setattr(self.instance, "graph_revision", 2)
        result = self.job().start()
        self.assertEqual(result.refusal.kind, RefusalKind.STALE)
        self.assertEqual(self.renderer.starts, 0)
        self.assertEqual(result.recovery, RecoveryVerdict.RESTORED)

    def test_authority_callback_can_refuse_final_boundary(self):
        def recheck(*args):
            self.check_calls += 1
            if self.check_calls == 2:
                return Refusal(RefusalKind.APPROVAL_MISMATCH, "revoked")
        result = self.job(recheck_approval=recheck).start()
        self.assertEqual(result.refusal.reason, "revoked")
        self.assertEqual(self.renderer.starts, 0)

    def test_success_records_fresh_identity_but_does_not_claim_image_verification(self):
        result = self.job().start()
        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.state, OperationState.TERMINAL)
        self.assertTrue(result.render_terminated)
        self.assertEqual(result.verdict, TerminalVerdict.UNKNOWN)
        self.assertEqual(len(result.output_identity["sha256"]), 64)
        self.assertEqual(self.check_calls, 2)
        self.assertEqual(self.renderer.settings, {"artist_output": "keep.$F4.exr"})

    def test_render_failure_restores_overrides_and_preserves_build(self):
        self.renderer.fail = True
        before = deepcopy(self.scene.nodes)
        result = self.job().start()
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.recovery, RecoveryVerdict.RESTORED)
        self.assertEqual(self.scene.nodes, before)
        self.assertTrue(result.output_identity)  # partial external effect remains recorded

    def test_missing_file_cannot_succeed_on_clean_backend_return(self):
        self.renderer.write = False
        result = self.job().start()
        self.assertEqual(result.outcome, "failed")
        self.assertFalse(result.output_identity)

    def test_stale_output_refused_before_mutation(self):
        path = Path(self.plan.output_path)
        path.parent.mkdir()
        path.write_bytes(b"old image")
        result = self.job().start()
        self.assertIn("stale", result.reason)
        self.assertEqual(self.renderer.starts, 0)
        self.assertEqual(path.read_bytes(), b"old image")

    def test_foreground_guard_refusal_is_preserved_without_force_override(self):
        guard_calls = []
        def deny(*args, **kwargs):
            guard_calls.append(kwargs)
            return {"allow": False, "reason": "cold XPU"}
        result = self.job(guard=deny).start()
        self.assertEqual(result.refusal.kind, RefusalKind.PROFILE_CONFLICT)
        self.assertFalse(guard_calls[0]["force"])
        self.assertEqual(self.renderer.starts, 0)

    def test_timeout_cancel_and_lost_response_do_not_restore_or_restart_inflight_render(self):
        entered, release = threading.Event(), threading.Event()
        workers = []
        def hold():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test render release missing")
        self.renderer.render_hook = hold
        def dispatcher(fn):
            worker = threading.Thread(target=fn)
            workers.append(worker)
            worker.start()
            self.assertTrue(entered.wait(2))
            raise TimeoutError("UI wait elapsed")
        registry = RenderJobRegistry()
        job = registry.get_or_create("id", {"render": 1}, lambda: self.job(dispatch=dispatcher))
        try:
            result = job.start()
            self.assertEqual(result.state, OperationState.RUNNING)
            self.assertFalse(result.render_terminated)
            self.assertIsNone(job.await_terminal(0))
            with self.assertRaisesRegex(RuntimeError, "terminal"):
                job.restore()
            self.assertFalse(job.cancel())
            retry = registry.get_or_create("id", {"render": 1}, lambda: self.fail("duplicate factory"))
            self.assertIs(retry, job)
            retry.start()
            self.assertEqual((self.renderer.starts, self.renderer.restores), (1, 0))
        finally:
            release.set()
            for worker in workers:
                worker.join(2)
        job.dispatch = lambda fn: fn()
        self.assertIsNotNone(job.await_terminal(1))
        self.assertEqual(self.renderer.restores, 1)

    def test_restore_failure_reports_residue_without_repeating_writes(self):
        self.renderer.restore_fail = True
        job = self.job()
        result = job.start()
        self.assertEqual(result.recovery, RecoveryVerdict.RESIDUE)
        self.assertTrue(result.residual_diff)
        job.restore()
        self.assertEqual(self.renderer.restores, 1)

    def test_intervening_artist_edit_refuses_override_restore(self):
        def artist_edit():
            self.renderer.settings["samples"] = 13
            self.renderer.foreign += 1
        self.renderer.render_hook = artist_edit
        result = self.job().start()
        self.assertEqual(result.recovery, RecoveryVerdict.RESIDUE)
        self.assertEqual(self.renderer.restores, 0)
        self.assertEqual(self.renderer.settings["samples"], 13)

    def test_registry_retains_terminal_request_and_creates_new_run_for_new_request(self):
        registry = RenderJobRegistry()
        first = registry.get_or_create("id", "payload", self.job)
        first.start()
        self.assertIs(registry.get_or_create("id", "payload", self.job), first)
        mismatch = registry.get_or_create("id", "changed", self.job)
        self.assertEqual(mismatch.kind, RefusalKind.DUPLICATE_REQUEST)
        new_plan = RenderPlan.prepare(output_root=self.temp.name, node_path="/stage/render",
                                     engine="karma_cpu", resolution=(64, 64), samples=1)
        new_approval = replace(self.approval, output_path=new_plan.output_path)
        second = registry.get_or_create("id2", "payload", lambda: self.job(
            request_id="id2", plan=new_plan, approval=new_approval))
        self.assertNotEqual(first.plan.run_id, second.plan.run_id)
        self.assertEqual(second.start().outcome, "succeeded")
        self.assertEqual(self.renderer.starts, 2)

    def test_in_progress_backend_return_never_certifies_termination_or_restores(self):
        self.renderer.response = {"status": "render_in_progress", "render_token": "unknown-session"}
        job = self.job()
        result = job.start()
        self.assertFalse(result.render_terminated)
        self.assertEqual(result.state, OperationState.RUNNING)
        self.assertEqual(self.renderer.restores, 0)
        self.assertIsNone(job.await_terminal(0))

    def test_bounded_adapter_wraps_existing_handler_payload(self):
        class Handler:
            def _handle_render_bounded(inner, payload):
                self.assertEqual(payload["node"], self.plan.node_path)
                self.assertFalse(payload["force_new"])
                self.assertFalse(payload["force_foreground"])
                return {"status": "done"}
        adapter = BoundedRenderAdapter(Handler(), self.renderer)
        self.assertEqual(adapter.start(self.plan), {"status": "done"})

    def test_python_return_without_native_termination_cannot_restore(self):
        self.renderer.native_terminal = None
        job = self.job()
        result = job.start()
        self.assertEqual(result.state, OperationState.RUNNING)
        self.assertFalse(result.render_terminated)
        self.assertEqual(self.renderer.restores, 0)
        self.renderer.native_terminal = True
        self.assertEqual(job.poll().state, OperationState.TERMINAL)
        self.assertEqual(self.renderer.starts, 1)
        self.assertEqual(self.renderer.restores, 1)

    def test_background_output_may_arrive_after_python_return(self):
        self.renderer.native_terminal = None
        self.renderer.write = False
        job = self.job()
        self.assertEqual(job.start().state, OperationState.RUNNING)
        Path(self.plan.output_path).write_bytes(b"fresh native output after Python return")
        self.renderer.native_terminal = True
        result = job.poll()
        self.assertEqual(result.state, OperationState.TERMINAL)
        self.assertEqual(result.outcome, "succeeded")
        self.assertTrue(result.output_identity)
        self.assertEqual((self.renderer.starts, self.renderer.restores), (1, 1))
