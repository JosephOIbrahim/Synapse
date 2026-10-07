"""TT-7: a failed tool reads as failed on every engine, not only Anthropic.

The worker marks a failed call with ``is_error: True`` on the Anthropic
``tool_result`` block. The OpenAI-shaped engines (Nemotron, and Ollama and
Custom, which inherit its translator) and Gemini translated that block without
the flag, so the model on those engines read a failure as a success.

A call that ran but reported misses (core/tool_results.result_misses) is
``is_error: False`` on the Anthropic path, with the misses note leading the
payload. It must arrive the same way elsewhere: not flagged as an error, the
note intact. On Gemini that needs care, because a ``functionResponse.response``
with a top-level ``error`` key is read as the call's error.

Qt-free, hou-free, network-free.
"""
import json

from synapse.core.tool_results import result_misses
from synapse.panel.providers import gemini_translate as gt
from synapse.panel.providers.nemotron_provider import _to_openai_messages

# Mirrors claude_worker._result_content / MISSES_NOTE_KEY (TT-1).
_NOTE_KEY = "synapse_reported_misses"


def _misses_content(payload):
    misses = result_misses(payload)
    assert misses, "fixture must carry a miss"
    noted = {_NOTE_KEY: {"note": "This call ran but reported misses. Name each one to the artist.",
                         "misses": list(misses)}}
    noted.update(payload)
    return json.dumps(noted)


def _history(result_block):
    return [
        {"role": "user", "content": "set it"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "c1", "name": "houdini_set_parm", "input": {"node": "/obj/a"}},
        ]},
        {"role": "user", "content": [dict({"type": "tool_result", "tool_use_id": "c1"}, **result_block)]},
    ]


def _tool_message(result_block):
    msgs = _to_openai_messages(_history(result_block), "sys", directive=None)
    tool_msgs = [m for m in msgs if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    return tool_msgs[0]


def _function_response(result_block):
    contents = gt.translate_messages(_history(result_block))
    return contents[-1]["parts"][0]["functionResponse"]


# -- OpenAI-shaped engines (Nemotron / Ollama / Custom) -----------------------

def test_openai_failed_tool_says_it_failed():
    msg = _tool_message({"content": "Node /obj/a not found", "is_error": True})
    assert msg["content"].startswith("ERROR")
    assert "failed" in msg["content"].split("\n", 1)[0]
    assert msg["content"].endswith("Node /obj/a not found")


def test_openai_failed_tool_with_list_content_says_it_failed():
    msg = _tool_message({"content": [{"type": "text", "text": "timed out"}], "is_error": True})
    assert msg["content"].startswith("ERROR")
    assert msg["content"].endswith("timed out")


def test_openai_success_is_not_marked():
    msg = _tool_message({"content": '{"path": "/obj/a"}', "is_error": False})
    assert msg["content"] == '{"path": "/obj/a"}'


def test_openai_misses_arrive_unflagged_with_note_first():
    """Parity pin (passes before TT-7 too): misses are not an error."""
    content = _misses_content({"node": "/obj/a", "parms_missed": ["tx"], "error": "tx is locked"})
    msg = _tool_message({"content": content, "is_error": False})
    assert msg["content"] == content
    assert next(iter(json.loads(msg["content"]))) == _NOTE_KEY


# -- Gemini -------------------------------------------------------------------

def test_gemini_failed_tool_goes_under_error():
    fr = _function_response({"content": "Node /obj/a not found", "is_error": True})
    assert fr["response"] == {"error": "Node /obj/a not found"}


def test_gemini_failed_tool_json_payload_goes_under_error():
    fr = _function_response({"content": '{"code": 404, "detail": "missing"}', "is_error": True})
    assert fr["response"] == {"error": {"code": 404, "detail": "missing"}}


def test_gemini_misses_with_error_key_are_output_not_error():
    content = _misses_content({"node": "/obj/a", "error": "tx is locked"})
    fr = _function_response({"content": content, "is_error": False})
    assert set(fr["response"]) == {"output"}
    out = fr["response"]["output"]
    assert next(iter(out)) == _NOTE_KEY
    assert out["error"] == "tx is locked"


def test_gemini_success_with_output_key_is_not_reinterpreted():
    fr = _function_response({"content": '{"output": "/tmp/a.exr"}'})
    assert fr["response"] == {"output": {"output": "/tmp/a.exr"}}


def test_gemini_misses_without_error_key_keep_note_first():
    """Parity pin (passes before TT-7 too): plain dict stays the response."""
    content = _misses_content({"node": "/obj/a", "parms_missed": ["tx"]})
    fr = _function_response({"content": content, "is_error": False})
    assert next(iter(fr["response"])) == _NOTE_KEY
    assert "error" not in fr["response"]


def test_gemini_plain_success_unchanged():
    fr = _function_response({"content": '{"path": "/obj/a"}'})
    assert fr["response"] == {"path": "/obj/a"}
