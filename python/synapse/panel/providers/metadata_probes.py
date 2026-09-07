"""Bounded metadata transport. No generation, redirects, retries or proxy env.

Only the selected model identifier is sent to Ollama's details endpoint; setup
never sends conversation, scene, tool or image content.
"""
from __future__ import annotations

import http.client
import json
import math
import time

MAX_RESPONSE_BYTES = 2_000_000
MAX_TIMEOUT_S = 10.0


class MetadataError(Exception):
    """A controlled message without credentials or a service response body."""

    def __init__(self, message, reason="unreachable"):
        super().__init__(message)
        self.reason = reason


def request_json(endpoint, path, headers=None, *, method="GET", body=None, timeout=3.0):
    """One metadata request with a size bound and elapsed-time read deadline."""
    # Local import avoids a module cycle: connections is the identity owner.
    from ..connections import is_loopback, validate_endpoint

    p = validate_endpoint(endpoint)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
            or any(ord(c) < 32 for c in path) or "\\" in path):
        raise MetadataError("The metadata path is invalid.", "invalid_path")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise MetadataError("The connection check timeout is invalid.", "invalid_timeout")
    timeout = min(timeout, MAX_TIMEOUT_S)
    headers = dict(headers or {})
    secret_headers = {"authorization", "x-api-key", "x-goog-api-key", "proxy-authorization"}
    if p.scheme == "http" and not is_loopback(endpoint) and any(
            str(key).lower() in secret_headers and value for key, value in headers.items()):
        raise MetadataError("Use HTTPS before sending a key to a remote service.", "insecure_credentials")
    if method == "POST":
        if (not path.endswith("/api/show") or not isinstance(body, dict) or set(body) != {"model"}
                or not isinstance(body["model"], str) or not body["model"] or len(body["model"]) > 512
                or any(ord(c) < 32 for c in body["model"])):
            raise MetadataError("Only model details may be requested during setup.", "invalid_request")
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif method == "GET" and body is None:
        encoded = None
    else:
        raise MetadataError("Only model metadata may be requested during setup.", "invalid_request")
    headers.setdefault("Accept", "application/json")
    cls = http.client.HTTPSConnection if p.scheme == "https" else http.client.HTTPConnection
    conn = cls(p.netloc, timeout=timeout)
    deadline = time.monotonic() + timeout
    try:
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        if response.status in (401, 403):
            raise MetadataError("The service rejected this key. Check the key and account access.", "unauthorized")
        if response.status != 200:
            reason = "rate_limited" if response.status == 429 else "http_%d" % response.status
            raise MetadataError("Model metadata is unavailable (HTTP %d). Check the service address and access." % response.status, reason)
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MetadataError("The connection check timed out. Try again when the service is ready.", "timeout")
            if conn.sock is not None:
                conn.sock.settimeout(remaining)
            chunk = response.read1(min(16384, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise MetadataError("The service returned model metadata too large to check.", "response_too_large")
            chunks.append(chunk)
        try:
            data = json.loads(b"".join(chunks))
        except (ValueError, UnicodeError):
            raise MetadataError("The service returned unreadable model metadata.", "unparseable_response") from None
        if not isinstance(data, dict):
            raise MetadataError("The service returned unreadable model metadata.", "unparseable_response")
        return data
    finally:
        conn.close()


def ollama_show(spec, headers=None, *, timeout=3.0):
    from ..connections import validate_endpoint

    p = validate_endpoint(spec.endpoint)
    path = p.path.removesuffix("/v1/chat/completions").rstrip("/") + "/api/show"
    return request_json(spec.endpoint, path, headers, method="POST", body={"model": spec.model}, timeout=timeout)
