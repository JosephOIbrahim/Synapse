"""9/30 413 fix: bounded array attributes at the source and bounded tool results before chat history."""
import json

from synapse.core.tool_results import _MAX_TOOL_RESULT_CHARS, cap_history, cap_tool_results
from synapse.server.handlers_usd import _ARRAY_RETURN_LIMIT, _bound_array


def test_small_values_pass_through():
    assert _bound_array([1.0, 2.0]) == {}
    assert _bound_array([[0.0, 1.0, 2.0]] * _ARRAY_RETURN_LIMIT) == {}
    assert _bound_array("text") == {} and _bound_array(3.0) == {}


def test_large_vector_array_returns_sample_length_and_bounds():
    points = [[float(i), -float(i), 0.5] for i in range(500_000)]
    out = _bound_array(points)
    assert out["truncated"] is True and out["length"] == 500_000 and len(out["value"]) == 16
    assert out["bounds"] == {"min": [0.0, -499_999.0, 0.5], "max": [499_999.0, 0.0, 0.5]}
    assert len(json.dumps(out)) < 2_000


def test_large_scalar_array_bounds():
    out = _bound_array(list(range(1000)))
    assert out["bounds"] == {"min": 0, "max": 999} and out["length"] == 1000


def test_cap_tool_results_cuts_only_oversized_string_results():
    big = {"type": "tool_result", "tool_use_id": "a", "content": "x" * (_MAX_TOOL_RESULT_CHARS + 5000), "is_error": False}
    small = {"type": "tool_result", "tool_use_id": "b", "content": "ok"}
    image = {"type": "tool_result", "tool_use_id": "c", "content": [{"type": "image", "source": {"data": "y" * 200_000}}]}
    out = cap_tool_results([big, small, image])
    assert out[0]["content"].startswith("x" * 100) and "SYNAPSE kept the first 96000" in out[0]["content"]
    assert len(out[0]["content"]) < _MAX_TOOL_RESULT_CHARS + 300
    assert out[0]["tool_use_id"] == "a" and out[0]["is_error"] is False
    assert out[1] is small and out[2] is image
    assert len(big["content"]) == _MAX_TOOL_RESULT_CHARS + 5000  # the original block is not mutated


def test_cap_history_sanitizes_a_restored_poisoned_conversation():
    poisoned = [{"role": "user", "content": "hi"},
                {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "houdini_get_usd_attribute", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "[" + "1," * 5_000_000 + "1]"}]}]
    clean = cap_history(poisoned)
    assert clean[0] == poisoned[0] and clean[1] == poisoned[1]
    assert sum(len(json.dumps(m)) for m in clean) < 120_000
    assert cap_history(None) == []
