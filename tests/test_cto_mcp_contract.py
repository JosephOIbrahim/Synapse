"""CTO review probes: actual worker/client, recording transport, no live requests."""
import base64
import http.client
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

QtCore = pytest.importorskip('PySide6.QtCore', reason='Native Qt worker contract')
if not isinstance(getattr(QtCore, 'QThread', None), type):
    pytest.skip('Native Qt worker contract; generic Qt doubles are insufficient', allow_module_level=True)
pytestmark = pytest.mark.needs_houdini

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'python'))
sys.path.insert(0, str(SOURCE))
from synapse.panel import tool_executor as executor
from synapse.panel import claude_worker as worker_module


@pytest.fixture
def worker(monkeypatch):
    integrity = ModuleType('synapse.panel.session_integrity')
    integrity.get_tracker = lambda: SimpleNamespace(record_tool_call=lambda *args: None)
    monkeypatch.setitem(sys.modules, integrity.__name__, integrity)
    journal = ModuleType('synapse.panel.session_journal')
    journal.get_journal = lambda: SimpleNamespace(log_tool=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, journal.__name__, journal)
    provider = SimpleNamespace(model_identity='synthetic-model',
                               _model_scope=SimpleNamespace(active=True))
    value = worker_module.ClaudeWorker([], tools=[], enforce_worker_policy=False, provider=provider)
    value._track_integrity = lambda *args: None
    value._emit_render_receipt = lambda *args: None
    return value


@pytest.mark.parametrize('failure', ['before_send', 'remote_disconnect', 'timeout', 'incomplete_read', 'malformed_reply', 'null_reply', 'list_reply', 'scalar_reply', 'success'])
def test_one_mutation_per_tool_call(worker, monkeypatch, failure, record_property):
    mutations = []
    adapter = SimpleNamespace(_running=True, _port=54321)
    monkeypatch.setitem(sys.modules, 'synapse.server.hwebserver_adapter', adapter)
    client = executor._MCPLocalClient()
    client._port, client._session_id = 54321, 'synthetic-session'
    monkeypatch.setattr(executor, '_mcp_client', client)

    class Response:
        def read(self):
            if failure == 'incomplete_read':
                raise http.client.IncompleteRead(b'{', 20)
            if failure == 'malformed_reply':
                return b'not a JSON-RPC reply'
            if failure == 'null_reply':
                return b'{"jsonrpc":"2.0","id":"synthetic","result":null}'
            if failure == 'list_reply':
                return b'{"jsonrpc":"2.0","id":"synthetic","result":[]}'
            if failure == 'scalar_reply':
                return b'{"jsonrpc":"2.0","id":"synthetic","result":true}'
            return b'{"jsonrpc":"2.0","id":"synthetic","result":{"created":true}}'
        def getheader(self, name):
            return None

    class Connection:
        def __init__(self, *args, **kwargs):
            self.connected = False
        def connect(self):
            if failure == 'before_send':
                raise ConnectionRefusedError('synthetic refusal before dispatch')
            self.connected = True
        def request(self, method, path, *, body, headers):
            if not self.connected:
                self.connect()  # HTTPConnection's implicit-connect behavior
            request = json.loads(body)
            assert request['method'] == 'tools/call'
            mutations.append('mcp')
        def getresponse(self):
            if failure == 'remote_disconnect':
                raise http.client.RemoteDisconnected('synthetic reply lost after dispatch')
            if failure == 'timeout':
                raise TimeoutError('synthetic reply timeout after dispatch')
            return Response()
        def close(self):
            pass

    monkeypatch.setattr(executor.http.client, 'HTTPConnection', Connection)
    def fallback(request):
        mutations.append('fallback')
        request.result = {'created': True}
        request.done.set()
    worker._dispatch_off_main = fallback
    result = worker._execute_tool_block({'id':'synthetic-call', 'name':'houdini_create_node',
                                        'input':{'parent_path':'/obj','node_type':'geo'}})
    record_property('mutations', json.dumps(mutations))
    record_property('result_is_error', str(result['is_error']))
    assert len(mutations) == 1, f'A single tool call dispatched {mutations}'
    if failure not in ('before_send', 'success'):
        assert result['is_error'] is True
    else:
        assert result['is_error'] is False
    assert mutations == (['fallback'] if failure == 'before_send' else ['mcp'])


@pytest.mark.parametrize('route', ['mcp', 'fallback'])
@pytest.mark.parametrize('capabilities,model,expected_image', [
    (frozenset({'tools'}), 'gpt-4-text-only-synthetic', False),
    (frozenset({'tools','vision'}), 'synthetic-capable-model', True),
])
def test_capture_respects_checked_capabilities(worker, monkeypatch, tmp_path,
                                              route, capabilities, model, expected_image,
                                              record_property):
    png = tmp_path / 'synthetic.png'
    png.write_bytes(base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGkQAAAAASUVORK5CYII='))
    raw = {'image_path': str(png)}
    worker._provider.model_identity = model
    worker._provider._connection_facts = SimpleNamespace(capabilities=capabilities, fresh=lambda: True)
    monkeypatch.setattr(worker_module, 'try_mcp_tool_call', lambda *args: raw if route == 'mcp' else None)
    def fallback(request):
        request.result = raw
        request.done.set()
    worker._dispatch_off_main = fallback
    result = worker._execute_tool_block({'id':'synthetic-capture', 'name':'houdini_capture_viewport', 'input':{}})
    content = result['content']
    has_image = isinstance(content, list) and any(block.get('type') == 'image' for block in content)
    record_property('has_image', str(has_image))
    assert has_image is expected_image


@pytest.mark.parametrize('route', ['mcp', 'fallback'])
def test_actual_mcp_capture_envelope_preserves_image(worker, monkeypatch, tmp_path, route, record_property):
    from synapse.mcp.tools import dispatch_tool
    from synapse.panel import bridge_adapter
    from synapse.core.protocol import SynapseResponse
    png = tmp_path / 'synthetic.png'
    png.write_bytes(base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGkQAAAAASUVORK5CYII='))
    raw = {'image_path': str(png)}
    handler = SimpleNamespace(handle=lambda cmd: SynapseResponse(id=cmd.id, success=True, data=raw))
    monkeypatch.setattr(bridge_adapter, 'execute_through_bridge', lambda name, handler, cmd: handler.handle(cmd))
    # Serialization is production dispatch_tool, not a hand-written MCP fixture.
    envelope = dispatch_tool(handler, 'houdini_capture_viewport', {})
    assert json.loads(envelope['content'][0]['text']) == raw
    worker._provider.model_identity = 'gpt-4-synthetic'
    worker._provider._connection_facts = SimpleNamespace(capabilities=frozenset({'completion','tools','vision'}), fresh=lambda: True)
    monkeypatch.setitem(sys.modules, 'synapse.server.hwebserver_adapter', SimpleNamespace(_running=route=='mcp', _port=54321))
    client = executor._MCPLocalClient()
    client._port, client._session_id = 54321, 'synthetic-session'
    monkeypatch.setattr(executor, '_mcp_client', client)
    class Response:
        def read(self):
            return json.dumps({'jsonrpc':'2.0', 'id':'synthetic', 'result':envelope}).encode()
        def getheader(self, name):
            return None
    class Connection:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self):
            pass
        def request(self, method, path, **kwargs):
            assert json.loads(kwargs['body'])['method'] == 'tools/call'
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(executor.http.client, 'HTTPConnection', Connection)
    def fallback(request):
        request.result = raw
        request.done.set()
    worker._dispatch_off_main = fallback
    result = worker._execute_tool_block({'id':'synthetic-capture', 'name':'houdini_capture_viewport', 'input':{}})
    content = result['content']
    has_image = isinstance(content, list) and any(block.get('type') == 'image' for block in content)
    record_property('mcp_envelope_keys', json.dumps(list(envelope)))
    record_property('has_image', str(has_image))
    assert has_image, f'{route} capture lost the image; content={type(content).__name__}'


@pytest.mark.parametrize('route', ['mcp', 'fallback'])
def test_actual_mcp_recall_envelope_preserves_hit(worker, monkeypatch, route, record_property):
    from synapse.mcp.tools import dispatch_tool
    from synapse.panel import bridge_adapter
    from synapse.panel.recall_card import latest_recall_result, recall_view
    from synapse.core.protocol import SynapseResponse
    raw = {'found': True, 'matches': [{'content': 'Clearly synthetic review memory'}]}
    handler = SimpleNamespace(handle=lambda cmd: SynapseResponse(id=cmd.id, success=True, data=raw))
    monkeypatch.setattr(bridge_adapter, 'execute_through_bridge', lambda name, handler, cmd: handler.handle(cmd))
    envelope = dispatch_tool(handler, 'synapse_recall', {'query':'synthetic'})
    assert json.loads(envelope['content'][0]['text']) == raw
    monkeypatch.setattr(worker_module, 'try_mcp_tool_call', lambda *args: envelope if route=='mcp' else None)
    def fallback(request):
        request.result = raw
        request.done.set()
    worker._dispatch_off_main = fallback
    tool = {'type':'tool_use', 'id':'recall-review', 'name':'synapse_recall', 'input':{'query':'synthetic'}}
    result = worker._execute_tool_block(tool)
    messages = [{'role':'assistant', 'content':[tool]}, {'role':'user','content':[result]}]
    view = recall_view(latest_recall_result(messages))
    record_property('recall_view', json.dumps(view))
    assert view == {'status':'HIT', 'deposit':'Clearly synthetic review memory'}, view


def test_tool_error_envelope_remains_an_error(worker, monkeypatch):
    envelope = {'content': [{'type': 'text', 'text': 'Synthetic handler refused'}], 'isError': True}
    monkeypatch.setattr(worker_module, 'try_mcp_tool_call', lambda *a: envelope)
    worker._dispatch_off_main = lambda *a: pytest.fail('A tool failure must not dispatch again')
    result = worker._execute_tool_block({'id': 'refused', 'name': 'houdini_create_node', 'input': {}})
    assert result['is_error'] is True
    assert result['content'] == 'Synthetic handler refused'


def test_result_processing_failure_never_replays_tool(worker, monkeypatch):
    dispatches = []
    def returned(*args):
        dispatches.append('mcp')
        return {'created': True}
    monkeypatch.setattr(worker_module, 'try_mcp_tool_call', returned)
    worker._track_integrity = lambda *a: (_ for _ in ()).throw(ValueError('Synthetic receipt read failed'))
    worker._dispatch_off_main = lambda *a: dispatches.append('fallback')
    result = worker._execute_tool_block({'id': 'read-failed', 'name': 'houdini_create_node', 'input': {}})
    assert result['is_error'] is True
    assert dispatches == ['mcp']
