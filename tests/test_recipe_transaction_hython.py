"""NOT_RUN until an actual hython + captured golden scene driver is supplied.

The host factory (module:function in SYNAPSE_LIFECYCLE_HYTHON_FACTORY) returns
a fresh BuildTransaction bound to an empty isolated golden test scope. It must
use the qualified BLOCKS operations, complete capture and real undo backend;
no scene mutations occur merely by collecting these tests.
"""
import importlib
import os
from pathlib import Path
import sys
import unittest

from synapse.recipes.contracts import RecoveryVerdict
from synapse.recipes.transaction import BuildTransaction


class HythonLifecycleTests(unittest.TestCase):
    def setUp(self):
        if not Path(sys.executable).stem.lower().startswith("hython"):
            self.skipTest("NOT_RUN: requires isolated hython, never the live Houdini GUI")
        try:
            import hou
        except ImportError:
            self.skipTest("NOT_RUN: hou unavailable")
        if getattr(hou, "__synapse_canonical__", False):
            self.skipTest("NOT_RUN: suite hou double is not a Houdini runtime")
        factory_path = os.environ.get("SYNAPSE_LIFECYCLE_HYTHON_FACTORY")
        if not factory_path:
            self.skipTest("NOT_RUN: golden HIP/capture and qualified lifecycle backend factory absent")
        module, name = factory_path.rsplit(":", 1)
        self.factory = getattr(importlib.import_module(module), name)

    def test_golden_owned_scope_commits_with_measured_group(self):
        txn = self.factory()
        self.assertIsInstance(txn, BuildTransaction)
        result = txn.execute()
        self.assertIsNotNone(txn.await_terminal(30))
        self.assertEqual(result.outcome, "committed", result.reason)
        self.assertEqual(result.undo_evidence["labels_after"][0], txn.label)
        self.assertEqual(result.recovery, RecoveryVerdict.NOT_NEEDED)

    def test_golden_build_undo_matches_full_prestate(self):
        txn = self.factory()
        before = txn.dispatch(txn.backend.snapshot)
        self.assertEqual(txn.execute().outcome, "committed")
        # Isolated hython only: the actual driver must prove one artist undo.
        txn.dispatch(txn.backend.perform_undo)
        self.assertEqual(txn.dispatch(txn.backend.snapshot), before)
