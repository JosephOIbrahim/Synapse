"""Raw and MCP tool replies preserve evidence and failure state."""
import json
import pytest
from synapse.core.tool_results import unpack_tool_result


@pytest.mark.parametrize('mode', ['raw', 'text', 'structured'])
def test_payload_and_receipts_survive(mode):
    payload = {'found': True, '_memory_loop': {'status': 'DEPOSITED'}, '_integrity': {'fidelity': 1}}
    value = payload
    if mode == 'text':
        value = {'content': [{'type': 'text', 'text': json.dumps(payload, sort_keys=True)}]}
    elif mode == 'structured':
        value = {'structuredContent': payload, 'content': [{'type': 'text', 'text': 'summary'}]}
    assert unpack_tool_result(value) == (payload, False)


def test_error_is_not_downgraded_by_structured_success_looking_data():
    assert unpack_tool_result({'structuredContent': {'success': True}, 'isError': True}) == ({'success': True}, True)


@pytest.mark.parametrize('value', [
    {'content': [], 'isError': 'false'}, {'structuredContent': []},
    {'isError': False}, {'content': [{'type': 'text', 'text': None}]},
])
def test_malformed_envelope_never_claims_success(value):
    with pytest.raises(RuntimeError):
        unpack_tool_result(value)


def test_other_content_is_preserved_and_direct_content_is_not_reinterpreted():
    blocks = {'content': [{'type': 'text', 'text': 'first'}, {'type': 'image', 'data': 'synthetic'}]}
    assert unpack_tool_result(blocks) == (blocks, False)
    direct = {'content': 'A stored memory', 'found': True}
    assert unpack_tool_result(direct) == (direct, False)
