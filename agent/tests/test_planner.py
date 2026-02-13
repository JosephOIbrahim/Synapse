"""Tests for synapse_planner.py -- multi-goal planner."""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_planner import (
    SubGoal,
    Plan,
    deterministic_uuid,
    goal_hash,
    validate_dag,
    topological_order,
    parse_plan_response,
    create_plan,
    PLANNING_SYSTEM_PROMPT,
)


# -- deterministic_uuid tests ------------------------------------------------


def test_deterministic_uuid_same_input():
    """Same content produces same ID."""
    a = deterministic_uuid("test content")
    b = deterministic_uuid("test content")
    assert a == b
    assert len(a) == 32


def test_deterministic_uuid_different_input():
    """Different content produces different ID."""
    a = deterministic_uuid("content A")
    b = deterministic_uuid("content B")
    assert a != b


def test_deterministic_uuid_with_namespace():
    """Namespace changes the output."""
    a = deterministic_uuid("test", namespace="ns1")
    b = deterministic_uuid("test", namespace="ns2")
    assert a != b


# -- SubGoal tests -----------------------------------------------------------


def test_subgoal_deterministic_id():
    """Same description produces same SubGoal ID."""
    id_a = deterministic_uuid("Create a sphere", namespace="subgoal")
    id_b = deterministic_uuid("Create a sphere", namespace="subgoal")
    assert id_a == id_b


def test_subgoal_to_dict_sorted():
    """Output dict keys are sorted (He2025)."""
    sg = SubGoal(id="abc123", description="Test", tools_hint=["b", "a"])
    d = sg.to_dict()
    keys = list(d.keys())
    assert keys == sorted(keys)
    # tools_hint should also be sorted
    assert d["tools_hint"] == ["a", "b"]


def test_subgoal_roundtrip():
    """to_dict -> from_dict preserves all fields."""
    sg = SubGoal(
        id="test_id",
        description="Create key light",
        tools_hint=["synapse_execute"],
        depends_on=["dep1"],
        verification="Light exists",
        max_retries=3,
        status="running",
        error="timeout",
        attempts=2,
    )
    d = sg.to_dict()
    restored = SubGoal.from_dict(d)
    assert restored.id == sg.id
    assert restored.description == sg.description
    assert restored.tools_hint == sorted(sg.tools_hint)
    assert restored.depends_on == sorted(sg.depends_on)
    assert restored.verification == sg.verification
    assert restored.max_retries == sg.max_retries
    assert restored.status == sg.status
    assert restored.error == sg.error
    assert restored.attempts == sg.attempts


def test_subgoal_from_dict_defaults():
    """from_dict fills defaults for missing optional fields."""
    sg = SubGoal.from_dict({"id": "x", "description": "test"})
    assert sg.tools_hint == []
    assert sg.depends_on == []
    assert sg.status == "pending"
    assert sg.max_retries == 2
    assert sg.attempts == 0


# -- Plan tests --------------------------------------------------------------


def test_plan_to_dict_roundtrip():
    """Plan serialization/deserialization preserves all fields."""
    plan = Plan(
        goal="Set up lighting",
        sub_goals=[
            SubGoal(id="a", description="Inspect scene"),
            SubGoal(id="b", description="Create light", depends_on=["a"]),
        ],
        created_at=12345.0,
    )
    d = plan.to_dict()
    restored = Plan.from_dict(d)
    assert restored.goal == plan.goal
    assert restored.goal_hash == plan.goal_hash
    assert len(restored.sub_goals) == 2
    assert restored.created_at == 12345.0


def test_plan_goal_hash_auto():
    """Plan auto-computes goal_hash on init."""
    plan = Plan(goal="Test Goal", sub_goals=[])
    assert plan.goal_hash == goal_hash("Test Goal")
    assert len(plan.goal_hash) == 32


def test_plan_pending_goals():
    """pending_goals filters by status."""
    plan = Plan(
        goal="test",
        sub_goals=[
            SubGoal(id="a", description="A", status="completed"),
            SubGoal(id="b", description="B", status="pending"),
            SubGoal(id="c", description="C", status="failed"),
            SubGoal(id="d", description="D", status="pending"),
        ],
    )
    pending = plan.pending_goals()
    assert len(pending) == 2
    assert all(sg.status == "pending" for sg in pending)


def test_plan_next_ready():
    """next_ready respects dependency completion."""
    plan = Plan(
        goal="test",
        sub_goals=[
            SubGoal(id="a", description="A", status="completed"),
            SubGoal(id="b", description="B", depends_on=["a"], status="pending"),
            SubGoal(id="c", description="C", depends_on=["b"], status="pending"),
        ],
    )
    ready = plan.next_ready()
    assert ready is not None
    assert ready.id == "b"


def test_plan_next_ready_blocked():
    """Returns None if all pending sub-goals are blocked."""
    plan = Plan(
        goal="test",
        sub_goals=[
            SubGoal(id="a", description="A", status="pending"),
            SubGoal(id="b", description="B", depends_on=["a"], status="pending"),
        ],
    )
    # "a" has no deps, so it should be ready
    ready = plan.next_ready()
    assert ready is not None
    assert ready.id == "a"


def test_plan_next_ready_all_blocked():
    """Returns None when every pending goal has unmet dependencies."""
    plan = Plan(
        goal="test",
        sub_goals=[
            SubGoal(id="a", description="A", status="running"),
            SubGoal(id="b", description="B", depends_on=["a"], status="pending"),
        ],
    )
    ready = plan.next_ready()
    assert ready is None


# -- goal_hash tests ---------------------------------------------------------


def test_goal_hash_deterministic():
    """Same goal produces same hash."""
    a = goal_hash("Set up three-point lighting")
    b = goal_hash("Set up three-point lighting")
    assert a == b


def test_goal_hash_case_insensitive():
    """Goal hash is case-insensitive."""
    a = goal_hash("Set Up Lighting")
    b = goal_hash("set up lighting")
    assert a == b


def test_goal_hash_strips_whitespace():
    """Goal hash strips leading/trailing whitespace."""
    a = goal_hash("  test goal  ")
    b = goal_hash("test goal")
    assert a == b


# -- validate_dag tests ------------------------------------------------------


def test_validate_dag_valid():
    """Linear chain A->B->C passes validation."""
    goals = [
        SubGoal(id="a", description="A"),
        SubGoal(id="b", description="B", depends_on=["a"]),
        SubGoal(id="c", description="C", depends_on=["b"]),
    ]
    assert validate_dag(goals) is True


def test_validate_dag_cycle():
    """A->B->A raises ValueError."""
    goals = [
        SubGoal(id="a", description="A", depends_on=["b"]),
        SubGoal(id="b", description="B", depends_on=["a"]),
    ]
    with pytest.raises(ValueError, match="cycle"):
        validate_dag(goals)


def test_validate_dag_self_ref():
    """A->A raises ValueError."""
    goals = [SubGoal(id="a", description="A", depends_on=["a"])]
    with pytest.raises(ValueError, match="self-reference"):
        validate_dag(goals)


def test_validate_dag_empty():
    """Empty list passes validation."""
    assert validate_dag([]) is True


def test_validate_dag_unknown_dep():
    """Dependency on non-existent ID raises ValueError."""
    goals = [SubGoal(id="a", description="A", depends_on=["nonexistent"])]
    with pytest.raises(ValueError, match="unknown ID"):
        validate_dag(goals)


# -- topological_order tests --------------------------------------------------


def test_topological_order_linear():
    """A->B->C returns [A, B, C]."""
    goals = [
        SubGoal(id="c", description="C", depends_on=["b"]),
        SubGoal(id="a", description="A"),
        SubGoal(id="b", description="B", depends_on=["a"]),
    ]
    ordered = topological_order(goals)
    ids = [sg.id for sg in ordered]
    assert ids.index("a") < ids.index("b")
    assert ids.index("b") < ids.index("c")


def test_topological_order_diamond():
    """A->{B,C}->D returns valid order."""
    goals = [
        SubGoal(id="d", description="D", depends_on=["b", "c"]),
        SubGoal(id="b", description="B", depends_on=["a"]),
        SubGoal(id="c", description="C", depends_on=["a"]),
        SubGoal(id="a", description="A"),
    ]
    ordered = topological_order(goals)
    ids = [sg.id for sg in ordered]
    assert ids[0] == "a"  # must be first
    assert ids[-1] == "d"  # must be last
    assert ids.index("b") < ids.index("d")
    assert ids.index("c") < ids.index("d")


def test_topological_order_parallel():
    """No deps: stable sort by ID."""
    goals = [
        SubGoal(id="c", description="C"),
        SubGoal(id="a", description="A"),
        SubGoal(id="b", description="B"),
    ]
    ordered = topological_order(goals)
    ids = [sg.id for sg in ordered]
    assert ids == sorted(ids)


def test_topological_order_empty():
    """Empty input returns empty list."""
    assert topological_order([]) == []


# -- parse_plan_response tests -----------------------------------------------


def test_parse_plan_response_json():
    """Bare JSON array parses correctly."""
    response = json.dumps([
        {"description": "Step 1", "tools_hint": ["synapse_execute"], "depends_on": [], "verification": "done"},
        {"description": "Step 2", "tools_hint": [], "depends_on": [0], "verification": "check"},
    ])
    plan = parse_plan_response(response, "Test goal")
    assert len(plan.sub_goals) == 2
    assert plan.goal == "Test goal"
    # Second sub-goal depends on first
    assert plan.sub_goals[1].depends_on == [plan.sub_goals[0].id]


def test_parse_plan_response_fenced():
    """Markdown-fenced JSON parses correctly."""
    response = (
        "Here's the plan:\n"
        "```json\n"
        '[{"description": "Inspect", "tools_hint": [], "depends_on": [], "verification": "ok"}]\n'
        "```\n"
        "Let me know if you want changes."
    )
    plan = parse_plan_response(response, "Test")
    assert len(plan.sub_goals) == 1


def test_parse_plan_response_invalid():
    """Bad JSON raises ValueError."""
    with pytest.raises(ValueError):
        parse_plan_response("not valid [stuff} at all]", "Test")


def test_parse_plan_response_no_array():
    """Response without array raises ValueError."""
    with pytest.raises(ValueError, match="Couldn't find"):
        parse_plan_response("No JSON here at all", "Test")


def test_parse_plan_response_empty_array():
    """Empty array raises ValueError."""
    with pytest.raises(ValueError, match="non-empty"):
        parse_plan_response("[]", "Test")


# -- create_plan tests (mocked) ---------------------------------------------


@pytest.mark.asyncio
async def test_create_plan_mock():
    """Mocked Anthropic client returns valid Plan."""
    plan_json = json.dumps([
        {"description": "Inspect scene", "tools_hint": ["synapse_inspect_scene"], "depends_on": [], "verification": "Got scene tree"},
        {"description": "Create light", "tools_hint": ["synapse_execute"], "depends_on": [0], "verification": "Light exists"},
        {"description": "Verify render", "tools_hint": ["synapse_render_preview"], "depends_on": [1], "verification": "Render completes"},
    ])

    mock_block = MagicMock()
    mock_block.text = plan_json
    mock_block.type = "text"

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    plan = await create_plan(mock_client, "Set up lighting", {"hip_file": "test.hip"})

    assert isinstance(plan, Plan)
    assert len(plan.sub_goals) == 3
    assert plan.goal == "Set up lighting"
    assert plan.sub_goals[0].description == "Inspect scene"
    # Dependencies resolved correctly
    assert plan.sub_goals[1].depends_on == [plan.sub_goals[0].id]
    assert plan.sub_goals[2].depends_on == [plan.sub_goals[1].id]


# -- PLANNING_SYSTEM_PROMPT tests -------------------------------------------


def test_planning_prompt_mentions_tops_tools():
    """Planning prompt includes TOPS tools for agent awareness."""
    assert "synapse_tops_cook" in PLANNING_SYSTEM_PROMPT
    assert "synapse_batch" in PLANNING_SYSTEM_PROMPT
    assert "synapse_capture_viewport" in PLANNING_SYSTEM_PROMPT
