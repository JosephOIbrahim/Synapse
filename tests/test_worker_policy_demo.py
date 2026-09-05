"""C3/T5 dispatch wall; unittest-compatible and pytest-collectable."""
import os
import unittest
from unittest.mock import patch

from synapse.mcp._tool_registry import TOOL_DEFS
from synapse.panel import worker_policy as policy
from synapse.recipes.contracts import RUN_RECIPE_TOOL_NAME


class DemoPolicyTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"SYNAPSE_WORKER_TOOL_MODE": "demo"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        os.environ.pop("SYNAPSE_WORKER_TOOL_PROFILE", None)

    def test_groups_setters_aliases_and_unknown_denied(self):
        for name in ("synapse_group_scene", "synapse_group_render", "synapse_group_unknown",
                     "synapse_solaris_assemble_all", "execute_python", "execute_vex", "unknown",
                     "houdini_set_parm", "houdini_set_usd_attribute"):
            with self.subTest(name=name):
                self.assertFalse(policy.is_tool_allowed_for_worker(name)[0])

    def test_recipe_proposal_allowed(self):
        self.assertTrue(policy.is_tool_allowed_for_worker(RUN_RECIPE_TOOL_NAME)[0])

    def test_demo_provider_advertises_reads_and_recipe_exactly(self):
        tools = policy.demo_tool_definitions()
        expected = {entry[0] for entry in TOOL_DEFS if entry[5] and not entry[0].startswith("synapse_group_")}
        self.assertEqual({tool["name"] for tool in tools}, expected | {RUN_RECIPE_TOOL_NAME})
        self.assertEqual(len(tools), len(expected | {RUN_RECIPE_TOOL_NAME}))
        tools[-1]["input_schema"]["properties"].clear()
        self.assertTrue(policy.demo_tool_definitions()[-1]["input_schema"]["properties"])

    def test_advertisement_uses_same_wall(self):
        from synapse.panel.tool_bridge import get_anthropic_tools_for_worker
        advertised = {tool["name"] for tool in get_anthropic_tools_for_worker()}
        reads = {entry[0] for entry in TOOL_DEFS if entry[5]}
        self.assertEqual(advertised - {RUN_RECIPE_TOOL_NAME}, reads)
        # Registration is an integrator hookup, outside this exclusive write set.

    def test_invalid_mode_never_falls_through(self):
        for mode in ("", " ", "bogus_mode", "dem0", "demo,unrestricted"):
            with self.subTest(mode=mode), patch.dict(os.environ, {policy._ENV_VAR: mode}):
                self.assertEqual(policy.resolve_mode(), "strict")
                self.assertFalse(policy.is_tool_allowed_for_worker("houdini_create_node")[0])

    def test_profile_conflict_cannot_loosen_demo(self):
        for mode in ("strict", "standard", "unrestricted"):
            with self.subTest(mode=mode), patch.dict(os.environ, {
                    policy._ENV_VAR: mode, policy._PROFILE_ENV_VAR: "demo"}):
                self.assertEqual(policy.resolve_mode(), "strict")
                self.assertFalse(policy.is_tool_allowed_for_worker("houdini_execute_python")[0])

    def test_invalid_profile_fails_closed(self):
        for profile in ("", " ", "unknown"):
            with patch.dict(os.environ, {policy._ENV_VAR: "unrestricted", policy._PROFILE_ENV_VAR: profile}):
                self.assertEqual(policy.resolve_mode(), "strict")

    def test_explicit_host_profile_beats_unrestricted_environment(self):
        os.environ[policy._ENV_VAR] = "unrestricted"
        self.assertEqual(policy.resolve_mode("demo"), "strict")
        self.assertFalse(policy.is_tool_allowed_for_worker("houdini_create_node", profile="demo")[0])

    def test_absent_settings_keep_legacy_default(self):
        os.environ.pop(policy._ENV_VAR)
        self.assertEqual(policy.resolve_mode(), "standard")

    def test_legacy_valid_modes_preserved(self):
        for mode, allow in (("standard", True), ("strict", False), ("unrestricted", True)):
            with patch.dict(os.environ, {policy._ENV_VAR: mode}):
                self.assertEqual(policy.resolve_mode(), mode)
                self.assertEqual(policy.is_tool_allowed_for_worker("houdini_create_node")[0], allow)
                self.assertTrue(policy.is_tool_allowed_for_worker("synapse_group_scene")[0])

    def test_environment_is_rechecked_between_calls(self):
        self.assertFalse(policy.is_tool_allowed_for_worker("houdini_create_node")[0])
        os.environ[policy._ENV_VAR] = "unrestricted"
        os.environ[policy._PROFILE_ENV_VAR] = "demo"
        self.assertFalse(policy.is_tool_allowed_for_worker("houdini_create_node")[0])


# Every actual registry entry gets its own direct dispatch test. The oracle
# comes from the registry effect declaration, not from the policy's index.
def _registry_test(name, read_only):
    def test(self):
        allowed, reason = policy.is_tool_allowed_for_worker(name)
        self.assertEqual(allowed, read_only or name == RUN_RECIPE_TOOL_NAME, name)
        self.assertTrue(reason)
    return test


for _entry in TOOL_DEFS:
    setattr(DemoPolicyTests, "test_t5_dispatch_" + _entry[0], _registry_test(_entry[0], bool(_entry[5])))


if __name__ == "__main__":
    unittest.main()
