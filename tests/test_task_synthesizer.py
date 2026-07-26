"""
Tests for task_synthesizer.py (v8-DSA)

Covers: generates requested count, diversity enforced, all complexity
levels, failure modes, deterministic with seed.
"""

import sys
import os

_SYNAPSE_ROOT = os.path.join(os.path.dirname(__file__), "..", "python")
if _SYNAPSE_ROOT not in sys.path:
    sys.path.insert(0, _SYNAPSE_ROOT)

import pytest

from synapse.agent.task_synthesizer import (
    Complexity,
    ConstraintType,
    FailureMode,
    SuccessCriterion,
    TaskConstraint,
    TaskEnvironment,
    TaskSynthesizer,
)


# ---------------------------------------------------------------------------
# Tests: Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_complexity_values(self):
        assert len(Complexity) == 5
        assert Complexity.MINIMAL.value == "minimal"
        assert Complexity.PRODUCTION.value == "production"

    def test_constraint_types(self):
        assert len(ConstraintType) >= 6

    def test_failure_modes(self):
        assert len(FailureMode) == 7
        assert FailureMode.NONE.value == "none"


# ---------------------------------------------------------------------------
# Tests: Data Models
# ---------------------------------------------------------------------------

class TestTaskConstraint:
    def test_to_dict(self):
        tc = TaskConstraint(
            ConstraintType.TIME_BUDGET, 30, "Complete in 30s"
        )
        d = tc.to_dict()
        assert d["type"] == "time_budget"
        assert d["value"] == 30


class TestSuccessCriterion:
    def test_to_dict_rounds_weight(self):
        sc = SuccessCriterion("test", "exists", "/obj/geo", weight=0.333333333)
        d = sc.to_dict()
        assert d["weight"] == 0.3333


class TestTaskEnvironment:
    def test_to_dict(self):
        env = TaskEnvironment(
            task_id="t1",
            description="Test task",
            complexity=Complexity.SIMPLE,
            expected_tool_chain=["create_node", "set_parm"],
            failure_mode=FailureMode.NONE,
            domain="scene",
        )
        d = env.to_dict()
        assert d["task_id"] == "t1"
        assert d["complexity"] == "simple"
        assert d["failure_mode"] == "none"
        assert len(d["expected_tool_chain"]) == 2


# ---------------------------------------------------------------------------
# Tests: TaskSynthesizer
# ---------------------------------------------------------------------------

class TestTaskSynthesizer:
    def test_generate_requested_count(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=7)
        assert len(tasks) == 7

    def test_generate_count_one(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=1)
        assert len(tasks) == 1

    def test_generated_count_tracking(self):
        synth = TaskSynthesizer(seed=42)
        synth.generate(n=3)
        assert synth.generated_count == 3
        synth.generate(n=2)
        assert synth.generated_count == 5

    def test_deterministic_with_same_seed(self):
        s1 = TaskSynthesizer(seed=123)
        s2 = TaskSynthesizer(seed=123)
        t1 = s1.generate(n=5)
        t2 = s2.generate(n=5)

        ids1 = [t.task_id for t in t1]
        ids2 = [t.task_id for t in t2]
        assert ids1 == ids2

    def test_different_seeds_different_output(self):
        s1 = TaskSynthesizer(seed=42)
        s2 = TaskSynthesizer(seed=99)
        t1 = s1.generate(n=5)
        t2 = s2.generate(n=5)

        # At least some tasks should differ (descriptions may overlap
        # but failure modes will differ due to random selection)
        descs1 = [t.description for t in t1]
        descs2 = [t.description for t in t2]
        # With different seeds, the template selection should differ
        assert descs1 != descs2 or [t.failure_mode for t in t1] != [t.failure_mode for t in t2]

    def test_filter_by_complexity(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5, complexity=Complexity.MINIMAL)
        assert all(t.complexity == Complexity.MINIMAL for t in tasks)

    def test_filter_by_domain(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5, domain="lighting")
        assert all(t.domain == "lighting" for t in tasks)

    def test_filter_by_failure_mode(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5, failure_mode=FailureMode.TIMEOUT)
        assert all(t.failure_mode == FailureMode.TIMEOUT for t in tasks)

    def test_all_complexity_levels_available(self):
        """Each complexity level has at least one template."""
        synth = TaskSynthesizer(seed=42)
        for complexity in Complexity:
            tasks = synth.generate(n=1, complexity=complexity)
            assert len(tasks) == 1
            assert tasks[0].complexity == complexity

    def test_failure_suite(self):
        synth = TaskSynthesizer(seed=42)
        suite = synth.generate_failure_suite()
        modes = {t.failure_mode for t in suite}
        # Should have one task per failure mode
        assert len(suite) == len(FailureMode)
        assert modes == set(FailureMode)

    def test_constraints_attached(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=3, complexity=Complexity.COMPLEX)
        for t in tasks:
            assert len(t.constraints) > 0

    def test_success_criteria_attached(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5)
        # At least some tasks should have success criteria
        with_criteria = [t for t in tasks if len(t.success_criteria) > 0]
        assert len(with_criteria) > 0

    def test_expected_tool_chain(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5)
        for t in tasks:
            assert len(t.expected_tool_chain) > 0

    def test_diversity_threshold(self):
        """High diversity threshold should encourage template variation."""
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=10, diversity_threshold=0.9)
        descriptions = [t.description for t in tasks]
        unique = set(descriptions)
        # With high diversity, we should see multiple unique descriptions
        assert len(unique) >= 2

    def test_reset(self):
        synth = TaskSynthesizer(seed=42)
        t1 = synth.generate(n=3)
        synth.reset()
        t2 = synth.generate(n=3)
        assert [t.task_id for t in t1] == [t.task_id for t in t2]
        assert synth.generated_count == 3  # reset clears count

    def test_reset_with_new_seed(self):
        synth = TaskSynthesizer(seed=42)
        synth.generate(n=3)
        synth.reset(seed=99)
        assert synth.seed == 99
        assert synth.generated_count == 0

    def test_generate_for_complexity(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate_for_complexity(Complexity.SIMPLE, n=3)
        assert len(tasks) == 3
        assert all(t.complexity == Complexity.SIMPLE for t in tasks)

    def test_task_ids_are_deterministic(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=3)
        # All task IDs should be non-empty hex strings
        for t in tasks:
            assert len(t.task_id) == 16
            assert all(c in "0123456789abcdef" for c in t.task_id)

    def test_each_task_has_unique_seed(self):
        synth = TaskSynthesizer(seed=42)
        tasks = synth.generate(n=5)
        seeds = [t.seed for t in tasks]
        assert len(set(seeds)) == 5
