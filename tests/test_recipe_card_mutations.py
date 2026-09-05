"""Re-runnable mutation evidence; executes only as a script, never during collection.

Each child loads changed product source into its real module namespace BEFORE
loading the control. No repository source is edited, no fake host is installed.
Exit zero means all selected controls were observed red; it is not a host pass.
"""
from pathlib import Path
import subprocess
import sys


CONTROLS = (
    ("reason validator removed", "synapse.recipes.receipt",
     'receipt.verdict != TerminalVerdict.VERIFIED and not receipt.reason.strip()',
     'False', "test_recipe_receipt.ReceiptTests.test_reason_required"),
    ("atomic publish replaced with direct write", "synapse.recipes.receipt",
     'os.replace(tmp, self.path)', 'self.path.write_bytes(tmp.read_bytes())',
     "test_recipe_receipt.ReceiptTests.test_atomic_replace_failure_preserves_old_ledger"),
    ("immutable evidence mappings made mutable", "synapse.recipes.receipt",
     'MappingProxyType({key: freeze(item) for key, item in value.items()})',
     '{key: freeze(item) for key, item in value.items()}',
     "test_recipe_receipt.ReceiptTests.test_helper_detaches_and_freezes_nested_evidence"),
    ("fingerprint comparison always current", "synapse.recipes.freshness",
     'current == receipt.fingerprint_after', 'True',
     "test_recipe_card.FreshnessTests.test_last_committed_baseline_is_not_live_fingerprint"),
    ("invalidation history ignored", "synapse.recipes.freshness",
     'event.at >= completed', 'False',
     "test_recipe_card.FreshnessTests.test_t12_all_events_invalidate_even_unchanged_fingerprint"),
    ("incomplete tracking ignored", "synapse.recipes.freshness",
     'not self._complete or self._since > completed', 'False',
     "test_recipe_card.FreshnessTests.test_current_requires_current_observation_and_complete_tracking"),
    ("periodic observation throttle removed", "synapse.recipes.freshness",
     'now - self._last_recheck < self._interval', 'False',
     "test_recipe_card.FreshnessTests.test_periodic_minimum_and_failure_throttle"),
    ("scope approval bypassed", "synapse.recipes.card",
     'requires_gate and not (scope_is_live and approval_scope.matches(binding))', 'False',
     "test_recipe_card.CardTests.test_t12_each_approval_scope_change_requires_reapproval"),
    ("spec outcome validation removed", "synapse.recipes.card",
     'digest != spec_digest(spec)', 'type(spec) is not RecipeSpec and digest != spec_digest(spec)',
     "test_recipe_card.SpecCacheTests.test_no_verdict_in_cache_negative_control"),
    ("retry returns another execution permit", "synapse.recipes.card",
     'DedupDecision(False, job)', 'DedupDecision(True, job)',
     "test_recipe_card.DedupTests.test_concurrent_retries_reserve_one_effect"),
)


def run_controls() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = 0
    for label, module_name, original, replacement, test_name in CONTROLS:
        program = f'''
import importlib, pathlib, sys, unittest
sys.path[:0] = [str(pathlib.Path.cwd() / "python"), str(pathlib.Path.cwd() / "tests")]
module = importlib.import_module({module_name!r})
source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
assert {original!r} in source, "mutation target missing"
exec(compile(source.replace({original!r}, {replacement!r}), module.__file__, "exec"), module.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromName({test_name!r})
result = unittest.TextTestRunner(verbosity=0).run(suite)
# A control failure counts; import errors and unexpected exceptions do not.
sys.exit(7 if result.failures and not result.errors else 9)
'''
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                                capture_output=True, text=True, timeout=30)
        observed = result.returncode == 7
        print(f"{'RED_OBSERVED' if observed else 'CONTROL_FAILED'}: {label} -> {test_name}")
        print("\n".join(line for line in result.stderr.splitlines()
                        if line.startswith(("FAIL:", "FAILED (", "AssertionError:"))))
        if not observed:
            print(result.stderr)
        if not observed:
            failures += 1
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(run_controls())
