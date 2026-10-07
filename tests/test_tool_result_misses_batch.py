"""result_misses covers the two nested shapes the tool-truth review found reading green.

- tops_batch_cook returns its per-node entries under "nodes" (handlers_tops/cook.py), not "results".
- synapse_batch keeps one error slot per step under "errors": [None, None] is clean, a string is a failed step.
"""

from synapse.core.tool_results import result_misses


def test_tops_batch_cook_failed_node_is_a_miss():
    payload = {"status": "ok", "nodes": [{"node": "/tasks/a", "status": "ok"},
                                          {"node": "/tasks/b", "status": "error", "error": "boom"}]}
    misses = result_misses(payload)
    assert misses and any("boom" in m for m in misses)


def test_tops_batch_cook_all_clean_is_not_a_miss():
    assert result_misses({"nodes": [{"node": "/tasks/a", "status": "ok"}]}) == []


def test_batch_failed_step_is_a_miss():
    payload = {"results": [{"ok": True}, None], "statuses": ["ok", "error"],
               "errors": [None, "Step 1: unknown command x"]}
    misses = result_misses(payload)
    assert any("unknown command x" in m for m in misses)


def test_clean_batch_errors_slots_are_not_a_miss():
    assert result_misses({"results": [{"ok": True}, {"ok": True}], "errors": [None, None]}) == []
    assert result_misses({"errors": [None, "  "]}) == []
