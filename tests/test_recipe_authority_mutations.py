"""Reproducible mutation receipt producer, run with python -m ... .

Mutations exist only in memory under unittest.mock.patch. Each selected real
test must go RED. This is a producer script, not a second copy of those tests.
"""
import json
import unittest
from unittest.mock import patch


def main():
    from synapse.panel import worker_policy
    from synapse.recipes import authority, phrases
    from synapse.recipes.contracts import PermissionCategory, Refusal
    from synapse.server import handlers_recipe

    original_validate = authority.validate_request
    original_match = phrases.match_phrase

    def bypass_validation(req, spec):
        result = original_validate(req, spec)
        return req if isinstance(result, Refusal) else result

    mutations = (
        (worker_policy, "resolve_mode", lambda *args, **kwargs: "standard",
         "test_worker_policy_demo.DemoPolicyTests.test_t5_dispatch_synapse_solaris_build_graph"),
        (authority, "validate_request", bypass_validation,
         "test_recipe_authority.AuthorityTests.test_numeric_bounds_finiteness_and_types"),
        (phrases, "match_phrase", lambda text, *args, **kwargs: original_match(text.split(" and ", 1)[0], *args, **kwargs),
         "test_recipe_authority.AuthorityTests.test_t4_entire_request_refused_before_dispatch"),
        (authority, "recheck_approval", lambda *args: True,
         "test_recipe_authority.AuthorityTests.test_each_bound_field_mismatch_denied"),
        (handlers_recipe, "effective_permission", lambda *args: PermissionCategory.INFORM,
         "test_recipe_authority.HandlerTests.test_t6_render_awaits_trusted_approval"),
        (handlers_recipe, "_same_request", lambda *args: True,
         "test_recipe_authority.HandlerTests.test_changed_payload_cannot_reuse_request_id"),
        (authority.MutationBudget, "consume", lambda *args, **kwargs: None,
         "test_recipe_authority.HandlerTests.test_second_action_requires_new_host_turn"),
    )
    survived = 0
    for target, symbol, mutant, name in mutations:
        with patch.object(target, symbol, mutant):
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromName(name).run(result)
        killed = bool(result.failures) and not result.errors
        survived += not killed
        print(json.dumps({"mutation": symbol, "test": name, "tests_run": result.testsRun,
                          "failures": len(result.failures), "errors": len(result.errors),
                          "verdict": "RED_EXPECTED" if killed else "SURVIVED_OR_ERROR"}, sort_keys=True))
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
