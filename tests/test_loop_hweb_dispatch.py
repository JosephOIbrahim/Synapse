"""Exercise the actual native receive coroutine without starting a server."""
import ast
import asyncio
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.host import memory_loop


def receive_function(handler):
    source = Path(__file__).parents[1] / 'python/synapse/server/hwebserver_adapter.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'receive')
    namespace = {'__name__':'synapse.server.hwebserver_adapter', '__package__':'synapse.server',
                 'json':json, 'SynapseCommand':SynapseCommand, 'SynapseResponse':SynapseResponse,
                 '_get_handler':lambda:handler, '_rate_limiter':None, '_circuit_breaker':None}
    exec(compile(ast.Module(body=[node],type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['receive']


@pytest.mark.parametrize('enabled,command,off_main', [
    (True,'execute_python',True), (True,'context',True),
    (False,'execute_python',False), (True,'get_parm',False),
])
def test_native_receive_thread_choice_and_single_dispatch(monkeypatch,enabled,command,off_main):
    monkeypatch.setattr(memory_loop,'enabled',lambda:enabled)
    calls=[]
    def handle(cmd):
        calls.append(threading.current_thread() is not threading.main_thread())
        return SynapseResponse(id=cmd.id,success=True,data={'executed':True})
    receive=receive_function(SimpleNamespace(handle=handle))
    messages=[]
    async def send(message,**kwargs):
        messages.append(json.loads(message))
    ws=SimpleNamespace(_authenticated=True,_auth_key=None,_session_id='existing',send=send)
    asyncio.run(receive(ws,json.dumps({'id':'one','type':command,'payload':{}})))
    assert calls == [off_main]
    assert len(messages)==1 and messages[0]['success'] is True


def test_native_receive_yields_ui_loop_while_handler_waits(monkeypatch):
    monkeypatch.setattr(memory_loop,'enabled',lambda:True)
    waiting=threading.Event()
    release=threading.Event()
    def handle(cmd):
        assert threading.current_thread() is not threading.main_thread()
        waiting.set()
        assert release.wait(2), 'UI loop did not remain available to release worker'
        return SynapseResponse(id=cmd.id,success=True,data={})
    receive=receive_function(SimpleNamespace(handle=handle))
    messages=[]
    async def send(message,**kwargs):
        messages.append(json.loads(message))
    ws=SimpleNamespace(_authenticated=True,_auth_key=None,_session_id='existing',send=send)
    async def run():
        task=asyncio.create_task(receive(ws,json.dumps({'id':'one','type':'execute_python','payload':{}})))
        try:
            for _ in range(100):
                await asyncio.sleep(.005)
                if waiting.is_set():
                    break
            assert waiting.is_set()
        finally:
            release.set()
        await task
    asyncio.run(run())
    assert len(messages)==1 and messages[0]['success'] is True
