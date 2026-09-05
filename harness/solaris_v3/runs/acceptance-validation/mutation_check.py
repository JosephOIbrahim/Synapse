"""Replay runner/bench negative controls without editing the live source tree."""
import importlib.util
import inspect
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tests"))
if sys.argv[1] == "skip":
    import test_solaris_v3_acceptance_runner as tests
    from scripts import solaris_v3_accept as accept
    mutated = inspect.getsource(accept.phase_status).replace('return "NOT_RUN"', 'return "PASS"')
    exec(compile(mutated, "<mutation:skip-becomes-pass>", "exec"), accept.__dict__)
    suite = unittest.TestSuite([tests.AcceptanceControls("test_skipped_phase_never_promotes_even_with_evidence")])
else:
    import test_solaris_v3_acceptance_bench as tests
    from harness.solaris_v3 import bench
    mutated = inspect.getsource(bench.distribution).replace("statistics.median(values)", "values[0]")
    exec(compile(mutated, "<mutation:median-becomes-min>", "exec"), bench.__dict__)
    suite = unittest.TestSuite([unittest.FunctionTestCase(tests.test_distribution_is_independently_hand_computed)])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
