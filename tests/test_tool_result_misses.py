"""TT-1 / TT-3 / TT-5: a tool that succeeds and still reports misses.

v5.95.0 taught 17 tools to report what did not land, but most report it INSIDE
a success payload (``cook_error`` next to a created node, a non-empty
``parms_missed``). ``result_misses`` names those misses so the worker can mark
the call 'warn' instead of a clean 'done'. These pins are pure Python.
"""
from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.core.tool_results import result_misses  # noqa: E402


# ---------------------------------------------------------------------------
# result_misses truth table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    None, "OK", 3, ["cook_error"], {},
    {"created_node": "/stage/x"},
    # Truthiness, not presence: an empty parms_missed is the claim that every
    # guarded write landed (core/parm_report.py).
    {"parms_missed": [], "inputs_missed": []},
    {"cook_error": None, "cook_error_detail": "x"},
    {"cook_error": ""},
    {"settings_error": None, "background_error": "", "callback_error": None},
    {"handler_removal_errors": []},
    {"error": None}, {"error": ""}, {"error": "   "},
    {"error": {"code": 1}},          # only a top-level STRING counts
    {"status": "ok"}, {"status": "failed"},   # only status == "error" counts
    # synapse_batch's envelope: a clean batch carries errors [None, None].
    {"results": [{"node": "/a"}, None], "statuses": ["ok", "ok"], "errors": [None, None]},
    {"results": "not a list"},
    {"events": [{"type": "cook_error", "message": "x"}]},   # an event, not a miss key
])
def test_clean_results_have_no_misses(payload):
    assert result_misses(payload) == []


def test_cook_error_inside_a_success_is_a_miss():
    misses = result_misses({"created_node": "/stage/x", "cook_error": "No prim at /a"})
    assert misses == ["No prim at /a"]


@pytest.mark.parametrize("key", ["settings_error", "background_error", "callback_error"])
def test_text_error_keys_are_misses(key):
    assert result_misses({key: "it broke"}) == ["it broke"]


def test_parms_and_inputs_missed_are_named():
    misses = result_misses({"path": "/img/x",
                            "parms_missed": ["karmamaterial.resx", "scatter.seed|seed"],
                            "inputs_missed": ["input2"]})
    assert misses == ["parms missed: karmamaterial.resx, scatter.seed|seed",
                      "inputs missed: input2"]


def test_handler_removal_errors_are_a_miss():
    misses = result_misses({"handler_removal_errors": ["removeEventHandler failed: X"]})
    assert misses == ["handler removal errors: removeEventHandler failed: X"]


def test_top_level_error_string_is_a_miss():
    assert result_misses({"error": "Couldn't find the camera"}) == ["Couldn't find the camera"]


def test_status_error_names_its_message():
    assert result_misses({"status": "error", "message": "no node"}) == ["status error: no node"]
    assert result_misses({"status": "error"}) == ["status error"]


def test_status_error_with_an_error_string_is_one_miss():
    assert result_misses({"status": "error", "error": "boom"}) == ["boom"]


def test_nested_results_are_scanned_and_indexed():
    payload = {"batch_name": "b", "results": [
        {"node": "/img/a", "status": "ok", "errors": []},
        None,
        {"node": "/img/b", "status": "error", "message": "Couldn't find node '/img/b'"},
        {"node": "/img/c", "status": "error", "errors": ["bad input", "no res"]},
    ]}
    assert result_misses(payload) == [
        "results[2]: status error: Couldn't find node '/img/b'",
        "results[3]: status error: bad input, no res",
    ]


def test_nested_passes_carry_settings_error():
    """The progressive render's settings_error lives inside passes[], not at top level."""
    payload = {"passes": [{"quality": "test", "status": "passed"},
                          {"quality": "preview", "status": "passed",
                           "settings_error": "Couldn't apply render settings: X"}],
               "success": True}
    assert result_misses(payload) == ["passes[1]: Couldn't apply render settings: X"]


def test_own_and_nested_misses_both_reported():
    payload = {"cook_error": "top", "results": [{"parms_missed": ["a.b"]}]}
    assert result_misses(payload) == ["top", "results[0]: parms missed: a.b"]


# ---------------------------------------------------------------------------
# activity.tool_status wording (TT-3)
# ---------------------------------------------------------------------------

def test_warn_status_line_names_the_misses():
    from synapse.panel.activity import tool_status, tool_label
    line = tool_status("houdini_set_usd_attribute", "warn", "No prim at /a")
    assert line == "Finished with misses: %s - No prim at /a" % tool_label(
        "houdini_set_usd_attribute")


def test_warn_without_detail_is_bare():
    from synapse.panel.activity import tool_status, tool_label
    assert tool_status("houdini_set_parm", "warn", "") == (
        "Finished with misses: %s" % tool_label("houdini_set_parm"))


def test_done_line_is_unchanged():
    from synapse.panel.activity import tool_status, tool_label
    assert tool_status("houdini_set_parm", "done", "{...}") == (
        "Finished: %s" % tool_label("houdini_set_parm"))


# ---------------------------------------------------------------------------
# System prompt (TT-5)
# ---------------------------------------------------------------------------

def test_prompt_asks_for_every_miss_on_every_tool():
    from synapse.panel import system_prompt
    g = system_prompt._TOOL_GUIDANCE
    assert "A tool can succeed and still report misses" in g
    bullet = g[g.index("A tool can succeed and still report misses"):]
    bullet = bullet[:bullet.index("\n- ")]
    for key in ("every tool", "cook_error", "parms_missed", "inputs_missed",
                "settings_error", "background_error", "callback_error",
                "Name each miss to the artist"):
        assert key in bullet, key


def test_prompt_bullet_reaches_the_built_prompt():
    from synapse.panel import system_prompt
    built = system_prompt.build_system_prompt({"network": "/stage"})
    assert "A tool can succeed and still report misses" in built
