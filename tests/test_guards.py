"""
Synapse Guard Function Tests

Tests for all 10 idempotent guard functions in server/guards.py.
Run without Houdini by mocking the hou module.

    python -m pytest tests/test_guards.py -v
"""

import sys
import os
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock the hou module BEFORE importing guards
# ---------------------------------------------------------------------------
_original_hou = sys.modules.get("hou", None)
hou_mock = MagicMock()
sys.modules["hou"] = hou_mock

# Import guards via importlib (same pattern as test_resilience.py)
import importlib.util

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
guards_path = os.path.join(
    package_root, "python", "synapse", "server", "guards.py"
)

spec = importlib.util.spec_from_file_location("guards", guards_path)
guards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guards)

ensure_node = guards.ensure_node
ensure_node_deleted = guards.ensure_node_deleted
node_exists = guards.node_exists
ensure_connection = guards.ensure_connection
ensure_disconnected = guards.ensure_disconnected
deduplicate_inputs = guards.deduplicate_inputs
ensure_parm = guards.ensure_parm
ensure_parm_tuple = guards.ensure_parm_tuple
describe_inputs = guards.describe_inputs
describe_node = guards.describe_node


# ---------------------------------------------------------------------------
# Helpers to build mock nodes and parms
# ---------------------------------------------------------------------------

def _make_node(path, node_type="null", inputs=None, outputs=None):
    """Return a MagicMock that behaves like a hou.Node.

    The mock is truthy by default (MagicMock.__bool__ returns True),
    which matches the guards' truthiness checks for present nodes.
    """
    node = MagicMock()
    node.path.return_value = path
    node.type.return_value.name.return_value = node_type
    node.inputs.return_value = inputs if inputs is not None else []
    node.outputs.return_value = outputs if outputs is not None else []
    return node


def _make_parm(current_value):
    """Return a MagicMock whose .eval() returns a real value (not MagicMock).

    This ensures arithmetic comparisons in guards work correctly.
    """
    parm = MagicMock()
    # hou.Parm.eval() -- Houdini API, not Python builtin
    parm.eval.return_value = current_value  # noqa: S307
    return parm


def _node_router(registry):
    """Return a side_effect callable for hou_mock.node.

    ``registry`` maps path -> mock_node (or None).
    Any path not in the registry returns None.
    """
    def _lookup(path):
        return registry.get(path)
    return _lookup


# ---------------------------------------------------------------------------
# Reset hou_mock before each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_hou():
    """Reset hou mock and default node() to return None."""
    hou_mock.reset_mock()
    # By default, hou.node(any_path) returns None (no node found).
    # Individual tests override via side_effect.
    hou_mock.node.return_value = None
    yield


# =============================================================================
# 1. ensure_node
# =============================================================================


class TestEnsureNode:
    """Tests for ensure_node(parent_path, node_type, node_name)."""

    def test_creates_node_when_missing(self):
        """When the target node does not exist, create it via parent."""
        parent = _make_node("/stage")
        created = _make_node("/stage/rim_light", "distantlight")
        parent.createNode.return_value = created

        hou_mock.node.side_effect = _node_router({
            "/stage/rim_light": None,  # does not exist yet
            "/stage": parent,
        })

        result = ensure_node("/stage", "distantlight", "rim_light")

        parent.createNode.assert_called_once_with("distantlight", "rim_light")
        assert result is created

    def test_returns_existing_node_idempotent(self):
        """When the target node already exists, return it without creating."""
        existing = _make_node("/stage/rim_light", "distantlight")

        hou_mock.node.side_effect = _node_router({
            "/stage/rim_light": existing,
        })

        result = ensure_node("/stage", "distantlight", "rim_light")

        assert result is existing

    def test_raises_for_missing_parent(self):
        """When the parent path does not resolve, raise ValueError."""
        hou_mock.node.side_effect = _node_router({})

        with pytest.raises(ValueError, match="Couldn't find the parent node"):
            ensure_node("/nonexistent", "null", "child")


# =============================================================================
# 2. ensure_node_deleted
# =============================================================================


class TestEnsureNodeDeleted:
    """Tests for ensure_node_deleted(node_path)."""

    def test_deletes_existing_node(self):
        """When node exists, destroy it and return True."""
        node = _make_node("/stage/old_light")
        hou_mock.node.side_effect = _node_router({
            "/stage/old_light": node,
        })

        result = ensure_node_deleted("/stage/old_light")

        assert result is True
        node.destroy.assert_called_once()

    def test_returns_true_when_already_gone(self):
        """When node does not exist, return True without error (idempotent)."""
        result = ensure_node_deleted("/stage/nonexistent")

        assert result is True


# =============================================================================
# 3. node_exists
# =============================================================================


class TestNodeExists:
    """Tests for node_exists(path)."""

    def test_returns_true_for_existing(self):
        hou_mock.node.side_effect = _node_router({
            "/obj/geo1": _make_node("/obj/geo1"),
        })
        assert node_exists("/obj/geo1") is True

    def test_returns_false_for_missing(self):
        assert node_exists("/obj/missing") is False


# =============================================================================
# 4. ensure_connection
# =============================================================================


class TestEnsureConnection:
    """Tests for ensure_connection(source, target, source_output, target_input)."""

    def test_creates_connection_when_not_connected(self):
        """When source is not in target's inputs, connect them."""
        source = _make_node("/stage/light")
        target = _make_node("/stage/merge")
        target.inputs.return_value = []

        hou_mock.node.side_effect = _node_router({
            "/stage/light": source,
            "/stage/merge": target,
        })

        result = ensure_connection("/stage/light", "/stage/merge")

        assert result is True
        target.setInput.assert_called_once_with(0, source, 0)

    def test_noops_when_already_connected(self):
        """When source is already in target's inputs, no-op."""
        source = _make_node("/stage/light")
        target = _make_node("/stage/merge", inputs=[source])

        hou_mock.node.side_effect = _node_router({
            "/stage/light": source,
            "/stage/merge": target,
        })

        result = ensure_connection("/stage/light", "/stage/merge")

        assert result is True
        target.setInput.assert_not_called()

    def test_uses_next_available_input_when_target_input_none(self):
        """When target_input is None, append at len(inputs)."""
        existing_input = _make_node("/stage/other")
        source = _make_node("/stage/light")
        target = _make_node("/stage/merge", inputs=[existing_input])

        hou_mock.node.side_effect = _node_router({
            "/stage/light": source,
            "/stage/merge": target,
        })

        result = ensure_connection("/stage/light", "/stage/merge")

        assert result is True
        target.setInput.assert_called_once_with(1, source, 0)

    def test_uses_exact_input_index_when_specified(self):
        """When target_input is given, use that index exactly."""
        source = _make_node("/stage/light")
        target = _make_node("/stage/merge")
        target.inputs.return_value = []

        hou_mock.node.side_effect = _node_router({
            "/stage/light": source,
            "/stage/merge": target,
        })

        result = ensure_connection(
            "/stage/light", "/stage/merge",
            source_output=1, target_input=3,
        )

        assert result is True
        target.setInput.assert_called_once_with(3, source, 1)

    def test_raises_for_missing_source(self):
        """ValueError when source node does not exist."""
        target = _make_node("/stage/merge")

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": target,
        })

        with pytest.raises(ValueError, match="Couldn't find a node"):
            ensure_connection("/stage/missing", "/stage/merge")

    def test_raises_for_missing_target(self):
        """ValueError when target node does not exist."""
        source = _make_node("/stage/light")

        hou_mock.node.side_effect = _node_router({
            "/stage/light": source,
        })

        with pytest.raises(ValueError, match="Couldn't find a node"):
            ensure_connection("/stage/light", "/stage/missing")


# =============================================================================
# 5. ensure_disconnected
# =============================================================================


class TestEnsureDisconnected:
    """Tests for ensure_disconnected(target_path, source_path)."""

    def test_disconnects_existing_connection(self):
        """When source is connected to target, disconnect it."""
        source = _make_node("/stage/light")
        target = _make_node("/stage/merge", inputs=[source])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": target,
        })

        result = ensure_disconnected("/stage/merge", "/stage/light")

        assert result is True
        target.setInput.assert_called_once_with(0, None)

    def test_noops_when_already_disconnected(self):
        """When source is not connected, no-op."""
        other = _make_node("/stage/other")
        target = _make_node("/stage/merge", inputs=[other])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": target,
        })

        result = ensure_disconnected("/stage/merge", "/stage/light")

        assert result is True
        target.setInput.assert_not_called()

    def test_returns_true_when_target_missing(self):
        """When target does not exist, return True (idempotent)."""
        result = ensure_disconnected("/stage/missing", "/stage/light")

        assert result is True


# =============================================================================
# 6. deduplicate_inputs
# =============================================================================


class TestDeduplicateInputs:
    """Tests for deduplicate_inputs(merge_path)."""

    def test_removes_duplicate_connections(self):
        """Two inputs pointing to the same node -- remove the duplicate."""
        node_a = _make_node("/stage/a")
        node_a_dup = _make_node("/stage/a")  # same path, duplicate connection
        merge = _make_node("/stage/merge", inputs=[node_a, node_a_dup])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": merge,
        })

        result = deduplicate_inputs("/stage/merge")

        assert result["removed"] == 1
        assert "/stage/a" in result["remaining"]
        merge.setInput.assert_called_once_with(1, None)

    def test_reports_correct_count(self):
        """Three connections to same node -- remove two."""
        node_a = _make_node("/stage/a")
        node_a2 = _make_node("/stage/a")
        node_a3 = _make_node("/stage/a")
        merge = _make_node("/stage/merge", inputs=[node_a, node_a2, node_a3])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": merge,
        })

        result = deduplicate_inputs("/stage/merge")

        assert result["removed"] == 2
        assert result["remaining"] == ["/stage/a"]

    def test_noops_when_no_duplicates(self):
        """All inputs are unique -- nothing to do."""
        node_a = _make_node("/stage/a")
        node_b = _make_node("/stage/b")
        merge = _make_node("/stage/merge", inputs=[node_a, node_b])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": merge,
        })

        result = deduplicate_inputs("/stage/merge")

        assert result["removed"] == 0
        assert set(result["remaining"]) == {"/stage/a", "/stage/b"}
        merge.setInput.assert_not_called()

    def test_handles_none_inputs(self):
        """None entries in inputs list should be skipped."""
        node_a = _make_node("/stage/a")
        node_a_dup = _make_node("/stage/a")
        merge = _make_node("/stage/merge", inputs=[node_a, None, node_a_dup])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": merge,
        })

        result = deduplicate_inputs("/stage/merge")

        assert result["removed"] == 1

    def test_raises_for_missing_node(self):
        """ValueError when merge node does not exist."""
        with pytest.raises(ValueError, match="Couldn't find a node"):
            deduplicate_inputs("/stage/nonexistent")


# =============================================================================
# 7. ensure_parm
# =============================================================================


class TestEnsureParm:
    """Tests for ensure_parm(node_path, parm_name, value)."""

    def _setup_node_with_parm(self, node_path, parm_name, current_value):
        """Create a node mock with a single parm returning current_value."""
        parm = _make_parm(current_value)
        node = _make_node(node_path)
        node.parm.side_effect = lambda name: parm if name == parm_name else None
        hou_mock.node.side_effect = _node_router({node_path: node})
        return node, parm

    def test_sets_parm_when_value_differs(self):
        """When current != desired, set the new value."""
        _node, parm = self._setup_node_with_parm("/stage/light", "intensity", 1.0)

        result = ensure_parm("/stage/light", "intensity", 5.0)

        assert result is True
        parm.set.assert_called_once_with(5.0)

    def test_noops_when_value_matches(self):
        """When current == desired, no-op."""
        _node, parm = self._setup_node_with_parm("/stage/light", "intensity", 5.0)

        result = ensure_parm("/stage/light", "intensity", 5.0)

        assert result is True
        parm.set.assert_not_called()

    def test_float_tolerance(self):
        """Values within 1e-7 are considered equal."""
        _node, parm = self._setup_node_with_parm("/stage/light", "intensity", 5.0)

        result = ensure_parm("/stage/light", "intensity", 5.000000001)

        assert result is True
        parm.set.assert_not_called()

    def test_float_outside_tolerance_sets(self):
        """Values differing by more than 1e-7 trigger a set."""
        _node, parm = self._setup_node_with_parm("/stage/light", "intensity", 5.0)

        result = ensure_parm("/stage/light", "intensity", 5.00001)

        assert result is True
        parm.set.assert_called_once_with(5.00001)

    def test_string_values(self):
        """String parameters use exact equality."""
        _node, parm = self._setup_node_with_parm("/stage/light", "file", "old_value")

        result = ensure_parm("/stage/light", "file", "new_value")

        assert result is True
        parm.set.assert_called_once_with("new_value")

    def test_string_values_match(self):
        """Matching string parameters are a no-op."""
        _node, parm = self._setup_node_with_parm("/stage/light", "file", "same_value")

        result = ensure_parm("/stage/light", "file", "same_value")

        assert result is True
        parm.set.assert_not_called()

    def test_int_values(self):
        """Integer parameters use exact equality."""
        _node, parm = self._setup_node_with_parm("/stage/light", "samples", 1)

        result = ensure_parm("/stage/light", "samples", 4)

        assert result is True
        parm.set.assert_called_once_with(4)

    def test_raises_for_missing_node(self):
        """ValueError when node does not exist."""
        with pytest.raises(ValueError, match="Couldn't find a node"):
            ensure_parm("/stage/nonexistent", "intensity", 1.0)

    def test_raises_for_missing_parm(self):
        """ValueError when parameter does not exist on node."""
        node = _make_node("/stage/light")
        node.parm.return_value = None

        hou_mock.node.side_effect = _node_router({
            "/stage/light": node,
        })

        with pytest.raises(ValueError, match="Couldn't find parameter"):
            ensure_parm("/stage/light", "nonexistent_parm", 1.0)


# =============================================================================
# 8. ensure_parm_tuple
# =============================================================================


class TestEnsureParmTuple:
    """Tests for ensure_parm_tuple(node_path, parm_names, values)."""

    def _setup_node_with_parms(self, node_path, parm_map):
        """Create a node with multiple parms.

        parm_map: dict of parm_name -> current_value
        Returns (node, dict_of_parm_mocks).
        """
        parm_mocks = {}
        for name, val in parm_map.items():
            parm_mocks[name] = _make_parm(val)

        node = _make_node(node_path)
        node.parm.side_effect = lambda name: parm_mocks.get(name)
        hou_mock.node.side_effect = _node_router({node_path: node})
        return node, parm_mocks

    def test_sets_all_parms_when_any_differ(self):
        """If any component differs, all components are written."""
        _node, parms = self._setup_node_with_parms(
            "/obj/geo1", {"tx": 0.0, "ty": 0.0, "tz": 0.0}
        )

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty", "tz"], [1.0, 2.0, 3.0]
        )

        assert result is True
        parms["tx"].set.assert_called_once_with(1.0)
        parms["ty"].set.assert_called_once_with(2.0)
        parms["tz"].set.assert_called_once_with(3.0)

    def test_noops_when_all_match(self):
        """When all current values match desired, no writes happen."""
        _node, parms = self._setup_node_with_parms(
            "/obj/geo1", {"tx": 1.0, "ty": 2.0, "tz": 3.0}
        )

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty", "tz"], [1.0, 2.0, 3.0]
        )

        assert result is True
        parms["tx"].set.assert_not_called()
        parms["ty"].set.assert_not_called()
        parms["tz"].set.assert_not_called()

    def test_float_tolerance_in_tuple_exact_match(self):
        """Exactly equal float components produce no writes."""
        _node, parms = self._setup_node_with_parms(
            "/obj/geo1", {"tx": 1.0, "ty": 2.0}
        )

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty"], [1.0, 2.0]
        )

        assert result is True
        parms["tx"].set.assert_not_called()
        parms["ty"].set.assert_not_called()

    def test_float_large_diff_triggers_update(self):
        """Float diff > 1e-7 triggers update via the isinstance branch."""
        _node, parms = self._setup_node_with_parms(
            "/obj/geo1", {"tx": 1.0, "ty": 2.0}
        )

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty"], [1.001, 2.0]
        )

        assert result is True
        parms["tx"].set.assert_called_once_with(1.001)
        parms["ty"].set.assert_called_once_with(2.0)

    def test_raises_for_missing_node(self):
        """ValueError when node does not exist."""
        with pytest.raises(ValueError, match="Couldn't find a node"):
            ensure_parm_tuple("/missing", ["tx"], [1.0])

    def test_skips_missing_parms(self):
        """If a parm name does not resolve, it is skipped (not an error)."""
        parm_tx = _make_parm(0.0)
        node = _make_node("/obj/geo1")
        node.parm.side_effect = lambda name: parm_tx if name == "tx" else None
        hou_mock.node.side_effect = _node_router({"/obj/geo1": node})

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty"], [1.0, 2.0]
        )

        assert result is True
        parm_tx.set.assert_called_once_with(1.0)

    def test_single_component_differs(self):
        """Only one component out of three differs -- all get written."""
        _node, parms = self._setup_node_with_parms(
            "/obj/geo1", {"tx": 1.0, "ty": 2.0, "tz": 0.0}
        )

        result = ensure_parm_tuple(
            "/obj/geo1", ["tx", "ty", "tz"], [1.0, 2.0, 3.0]
        )

        assert result is True
        parms["tx"].set.assert_called_once_with(1.0)
        parms["ty"].set.assert_called_once_with(2.0)
        parms["tz"].set.assert_called_once_with(3.0)


# =============================================================================
# 9. describe_inputs
# =============================================================================


class TestDescribeInputs:
    """Tests for describe_inputs(node_path)."""

    def test_returns_input_paths(self):
        """Returns list of paths for connected inputs."""
        inp_a = _make_node("/stage/a")
        inp_b = _make_node("/stage/b")
        node = _make_node("/stage/merge", inputs=[inp_a, inp_b])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": node,
        })

        result = describe_inputs("/stage/merge")

        assert result == ["/stage/a", "/stage/b"]

    def test_returns_none_for_empty_slots(self):
        """None entries in inputs are preserved as None."""
        inp_a = _make_node("/stage/a")
        node = _make_node("/stage/merge", inputs=[inp_a, None])

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": node,
        })

        result = describe_inputs("/stage/merge")

        assert result == ["/stage/a", None]

    def test_returns_empty_list_for_missing_node(self):
        """When node does not exist, return empty list."""
        result = describe_inputs("/stage/nonexistent")

        assert result == []

    def test_returns_empty_list_for_no_inputs(self):
        """Node with no inputs returns empty list."""
        node = _make_node("/stage/light", inputs=[])

        hou_mock.node.side_effect = _node_router({
            "/stage/light": node,
        })

        result = describe_inputs("/stage/light")

        assert result == []


# =============================================================================
# 10. describe_node
# =============================================================================


class TestDescribeNode:
    """Tests for describe_node(node_path)."""

    def test_returns_node_info_dict(self):
        """Returns dict with exists, path, type, inputs, outputs."""
        inp_a = _make_node("/stage/a")
        out_1 = _make_node("/stage/out1")
        out_2 = _make_node("/stage/out2")
        node = _make_node(
            "/stage/light",
            node_type="distantlight",
            inputs=[inp_a],
            outputs=[out_1, out_2],
        )

        hou_mock.node.side_effect = _node_router({
            "/stage/light": node,
        })

        result = describe_node("/stage/light")

        assert result["exists"] is True
        assert result["path"] == "/stage/light"
        assert result["type"] == "distantlight"
        assert result["inputs"] == 1
        assert result["outputs"] == 2

    def test_returns_exists_false_for_missing(self):
        """When node does not exist, return {'exists': False}."""
        result = describe_node("/stage/nonexistent")

        assert result == {"exists": False}

    def test_counts_only_connected_inputs(self):
        """Input count excludes None entries."""
        inp_a = _make_node("/stage/a")
        node = _make_node(
            "/stage/merge",
            node_type="merge",
            inputs=[inp_a, None, None],
            outputs=[],
        )

        hou_mock.node.side_effect = _node_router({
            "/stage/merge": node,
        })

        result = describe_node("/stage/merge")

        assert result["inputs"] == 1
        assert result["outputs"] == 0


# =============================================================================
# GUARD_FUNCTIONS registry
# =============================================================================


class TestGuardFunctionsRegistry:
    """Verify the GUARD_FUNCTIONS dict exposes all 10 functions."""

    def test_all_ten_present(self):
        expected = {
            "ensure_node",
            "ensure_node_deleted",
            "node_exists",
            "ensure_connection",
            "ensure_disconnected",
            "deduplicate_inputs",
            "ensure_parm",
            "ensure_parm_tuple",
            "describe_inputs",
            "describe_node",
        }
        assert set(guards.GUARD_FUNCTIONS.keys()) == expected

    def test_values_are_callable(self):
        for name, fn in guards.GUARD_FUNCTIONS.items():
            assert callable(fn), f"GUARD_FUNCTIONS['{name}'] is not callable"


# =============================================================================
# RUN
# =============================================================================

def teardown_module():
    if _original_hou is not None:
        sys.modules["hou"] = _original_hou


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
