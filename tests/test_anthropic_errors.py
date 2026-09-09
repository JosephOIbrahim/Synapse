"""Bounded, sanitized service diagnostics; no network or credentials."""
import io
import json
from types import SimpleNamespace

import pytest

from synapse.model_access import ModelRequestFailed
from synapse.panel.providers import anthropic_provider as module


@pytest.mark.parametrize('transport', ['http', 'sse'])
@pytest.mark.parametrize('kind,message,expected', [
    ('invalid_request_error', 'Your credit balance is too low to access the API.', 'credit balance'),
    ('invalid_request_error', 'You have reached your workspace spend limit.', 'spend limit'),
    ('invalid_request_error', 'messages.5.content.0: thinking blocks cannot be modified', 'reasoning history'),
    ('invalid_request_error', 'prompt is too long: 200001 tokens', 'conversation is too long'),
    ('invalid_request_error', 'tool_use ids were found without tool_result blocks', 'tool history'),
    ('overloaded_error', 'Overloaded', 'temporarily overloaded'),
    ('rate_limit_error', 'Rate limit reached', 'rate limit'),
    ('authentication_error', 'Invalid x-api-key', 'API key'),
    ('permission_error', 'Not allowed', 'permission'),
    ('invalid_request_error', 'Unknown shape', 'request format'),
])
def test_service_error_category_reaches_caller_without_raw_body(monkeypatch, transport, kind, message, expected):
    sentinel=' PRIVATE_SCENE_DATA sk-ant-never-display-this <img src=bad>'
    data={'type':'error','error':{'type':kind,'message':message+sentinel}}
    provider=module.AnthropicProvider(model='fixture',max_tokens=1)
    if transport=='sse':
        response=io.BytesIO(('event: error\ndata: '+json.dumps(data)+'\n\n').encode())
        invoke=lambda:provider._parse_sse_stream(response,lambda _:None,lambda:False)
    else:
        response=io.BytesIO(json.dumps(data).encode())
        response.status=400
        connection=SimpleNamespace(request=lambda *a,**kw:None,getresponse=lambda:response,close=lambda:None)
        monkeypatch.setattr(module.http.client,'HTTPSConnection',lambda *a,**kw:connection)
        monkeypatch.setattr(module,'stream_spec',lambda _:SimpleNamespace(model='fixture'))
        monkeypatch.setattr(module,'before_stream_send',lambda *a:None)
        invoke=lambda:provider.stream.__wrapped__(provider,messages=[],tools=[],system='',api_key='fixture',emit_token=lambda _:None,should_abort=lambda:False)
    with pytest.raises(ModelRequestFailed) as caught:
        invoke()
    text=str(caught.value)
    assert expected in text
    assert 'Anthropic' in text
    assert sentinel not in text and 'PRIVATE_SCENE_DATA' not in text and 'sk-ant-' not in text


@pytest.mark.parametrize('body',[b'not json',b'null',b'[]',b'{"error": []}',b'{"error":{"message":[]}}',b'x'*20000],
                         ids=['text','null','list','error-list','message-list','oversize'])
def test_http_diagnostic_is_bounded_and_malformed_safe(body):
    class Response:
        def read(self,n):
            assert 0<n<=8193
            return body[:n]
    detail=module._read_error_detail(Response())
    assert isinstance(detail,str) and len(detail)<300
    assert 'not json' not in detail and 'xxxxxxxx' not in detail


def test_error_body_read_failure_cannot_replace_original_error():
    class Response:
        def read(self,n):
            raise TimeoutError('private endpoint details')
    assert 'private' not in module._read_error_detail(Response())
