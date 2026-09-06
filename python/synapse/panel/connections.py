"""Panel connection evidence and task-bound transports. No Qt or Houdini.

Setup requests metadata only. Task permission belongs to the panel; this module
does not imply that independent host/MCP traffic is governed by that permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import ipaddress
import json
import time
from urllib.parse import urlsplit


def validate_endpoint(endpoint):
    """Accept a transport URL, never credentials or query strings in a URL."""
    if not isinstance(endpoint, str) or any(ord(c) < 32 for c in endpoint):
        raise ValueError("Enter a valid HTTP or HTTPS service address.")
    p = urlsplit(endpoint)
    try:
        port = p.port
    except ValueError:
        raise ValueError("The service port is invalid.") from None
    if (p.scheme not in ("http", "https") or not p.hostname or p.username
            or p.password or p.query or p.fragment or "\\" in endpoint):
        raise ValueError("Use an HTTP or HTTPS address without a password, query, or fragment.")
    return p


def is_loopback(endpoint):
    host = validate_endpoint(endpoint).hostname.lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class ConnectionSpec:
    provider: str
    model: str
    endpoint: str

    def __post_init__(self):
        validate_endpoint(self.endpoint)
        if not self.model or any(ord(c) < 32 for c in self.model):
            raise ValueError("Choose a model first.")

    @property
    def identity(self):
        # Requested identifier; a server may resolve an alias internally.
        return "%s/%s" % (self.provider, self.model)


@dataclass(frozen=True)
class ConnectionFacts:
    spec: ConnectionSpec
    metadata: dict = field(default_factory=dict, repr=False, compare=False)
    checked_at: float = 0.0

    @property
    def location(self):
        if self.spec.provider in ("claude", "gemini"):
            return "Cloud"
        if self.spec.provider == "ollama" and (":cloud" in self.spec.model.lower() or self.spec.model.lower().endswith("-cloud")):
            return "Cloud relay"
        fresh = 0 <= time.time() - self.checked_at <= 180
        if fresh and (self.metadata.get("remote_host") or self.metadata.get("remote_model")):
            return "Cloud relay"
        if not is_loopback(self.spec.endpoint):
            return "Remote"
        if self.spec.provider == "ollama" and fresh:
            # Positive weight-file metadata, not merely absence of remote_host.
            size = self.metadata.get("size")
            details = self.metadata.get("details") or {}
            if (isinstance(size, int) and not isinstance(size, bool) and size > 0
                    and details.get("format") == "gguf"):
                return "Local"
        return "Unverified"

    @property
    def description(self):
        text = "%s\nRequested model: %s\nService: %s" % (
            self.location, self.spec.identity, self.spec.endpoint)
        if self.location == "Local":
            text += "\nLocal weights reported by the loopback Ollama service; checked within three minutes."
        elif self.location == "Unverified":
            text += "\nWhere inference runs has not been verified."
        text += "\nA provider may resolve model aliases internally."
        return text


def provider_spec(provider):
    if provider.id == "claude":
        endpoint = "https://api.anthropic.com/v1/messages"
    elif provider.id == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
    elif provider.id in ("ollama", "nemotron", "custom"):
        scheme, host, path = provider._get_endpoint()
        endpoint = "%s://%s%s" % (scheme, host, path)
    else:
        raise ValueError("This engine is unavailable. Open Connect models to choose another.")
    return ConnectionSpec(provider.id, provider.model_identity, endpoint)


@dataclass
class BoundConnection:
    spec: ConnectionSpec
    provider: object = field(repr=False)
    facts: ConnectionFacts

    def release(self):
        self.provider._panel_session_key = None


_UNSET = object()


def bind_provider(provider, key=_UNSET, facts=None):
    """Freeze credentials and every endpoint used by this provider instance."""
    # Resolve legacy .env configuration BEFORE taking the endpoint snapshot.
    secret = provider.resolve_key() if key is _UNSET else key
    spec = provider_spec(provider)
    p = validate_endpoint(spec.endpoint)
    if p.scheme == "http" and not is_loopback(spec.endpoint) and secret not in (None, "", "not-needed"):
        raise ValueError("Use HTTPS to send an API key to a remote service.")
    provider._panel_session_key = secret
    provider.resolve_key = lambda: provider._panel_session_key
    original_stream = provider.stream

    def safe_stream(**kwargs):
        try:
            return original_stream(**kwargs)
        except Exception:
            # A service can echo Authorization in its error body. Suppress the
            # body and chained exception before worker logging or UI display.
            raise RuntimeError("The model request failed. Check the connection, model access, and service limits.") from None

    provider.stream = safe_stream
    if hasattr(provider, "_get_endpoint"):
        frozen_endpoint = (p.scheme, p.netloc, p.path)
        provider._get_endpoint = lambda: frozen_endpoint
    if provider.id == "ollama":
        provider._panel_ollama_base = (p.scheme, p.netloc,
                                      p.path.removesuffix("/v1/chat/completions"))
    return BoundConnection(spec, provider,
                           facts if facts and facts.spec == spec else ConnectionFacts(spec))


@dataclass(frozen=True)
class ConnectionCheck:
    ok: bool
    message: str
    models: tuple = ()
    facts: ConnectionFacts | None = None


class MetadataError(Exception):
    """Only controlled, credential-free messages may be surfaced."""


def _get_json(endpoint, path, headers, timeout=3.0):
    p = validate_endpoint(endpoint)
    cls = http.client.HTTPSConnection if p.scheme == "https" else http.client.HTTPConnection
    conn = cls(p.netloc, timeout=timeout)
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        if response.status in (401, 403):
            raise MetadataError("The service rejected this key. Check the key and account access.")
        if response.status != 200:
            raise MetadataError("The model list is unavailable (HTTP %d). Check the service address and access." % response.status)
        deadline = time.monotonic() + timeout
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise MetadataError("The connection check timed out. Try again when the service is ready.")
            chunk = response.read1(16384)
            if not chunk:
                break
            size += len(chunk)
            if size > 2_000_000:
                raise MetadataError("The service returned a model list too large to check.")
            chunks.append(chunk)
        data = json.loads(b"".join(chunks))
        if not isinstance(data, dict):
            raise MetadataError("The service returned an unreadable model list.")
        return data
    finally:
        conn.close()


def check_connection(spec, key):
    """A bounded metadata check. Never sends prompts or claims inference works."""
    try:
        p = validate_endpoint(spec.endpoint)
        if key and key != "not-needed" and p.scheme == "http" and not is_loopback(spec.endpoint):
            raise MetadataError("Use HTTPS before sending a key to a remote service.")
        headers = {}
        if spec.provider == "claude":
            headers = {"x-api-key": key or "", "anthropic-version": "2023-06-01"}
            path, collection = "/v1/models?limit=1000", "data"
        elif spec.provider == "gemini":
            headers = {"x-goog-api-key": key or ""}
            path, collection = "/v1beta/models?pageSize=1000", "models"
        else:
            if key and key != "not-needed":
                headers = {"Authorization": "Bearer " + key}
            if spec.provider == "ollama":
                path = p.path.removesuffix("/v1/chat/completions") + "/api/tags"
                collection = "models"
            else:
                path = p.path.removesuffix("/chat/completions") + "/models"
                collection = "data"
        payload = _get_json(spec.endpoint, path, headers)
        items = payload.get(collection)
        if not isinstance(items, list):
            raise MetadataError("The service returned an unreadable model list.")
        rows = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("id") or item.get("name") or item.get("model")
            if isinstance(name, str):
                if spec.provider == "gemini":
                    name = name.removeprefix("models/")
                if name and not any(ord(c) < 32 for c in name):
                    rows[name] = item
        if spec.model not in rows:
            return ConnectionCheck(False, "Service reached. This model was not listed; choose a listed model and check again.", tuple(rows))
        facts = ConnectionFacts(spec, rows[spec.model], time.time())
        return ConnectionCheck(True, "Service reached · model listed · generation untested. " + facts.location,
                               tuple(rows), facts)
    except MetadataError as exc:
        return ConnectionCheck(False, str(exc))
    except Exception:
        # Do not echo response bodies, transport errors, or entered secrets.
        return ConnectionCheck(False, "Could not check the service. Check the address, key, and whether it is running.")
