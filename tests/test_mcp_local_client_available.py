"""Pin the documented `available` semantics of the panel's local MCP client.

`_MCPLocalClient.available` (python/synapse/panel/tool_executor.py) is documented
to (1) replace a cached port with a newly detected one and drop the session id,
and (2) KEEP the cached port when discovery alone fails -- only a failed request
invalidates it. Master before the render/farm branch returned `port is not None`
and so lost the cached port on every discovery miss; this test pins the branch's
behaviour so the difference is a decision on file, not drift.
"""
from synapse.panel.tool_executor import _MCPLocalClient


def _client_with_detect(sequence):
    client = _MCPLocalClient()
    seq = list(sequence)
    client._detect_port = lambda: seq.pop(0) if seq else None  # type: ignore[assignment]
    return client


def test_detected_port_is_cached_and_reported():
    client = _client_with_detect([9999])
    assert client.available is True
    assert client._port == 9999


def test_discovery_miss_keeps_cached_port():
    client = _client_with_detect([9999, None, None])
    assert client.available is True
    client._session_id = "sess-1"
    assert client.available is True, "a discovery miss must not drop a cached port"
    assert client._port == 9999
    assert client._session_id == "sess-1", "a discovery miss must not drop the session"


def test_new_port_replaces_cache_and_drops_session():
    client = _client_with_detect([9999, 9000])
    assert client.available is True
    client._session_id = "sess-1"
    assert client.available is True
    assert client._port == 9000
    assert client._session_id is None, "a restarted endpoint cannot inherit the old session id"


def test_never_detected_is_unavailable():
    client = _client_with_detect([None])
    assert client.available is False
    assert client._port is None
