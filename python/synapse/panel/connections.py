"""Panel connection evidence and task-bound transports. No Qt or Houdini.

Setup requests metadata only. Task permission belongs to the panel; this module
does not imply that independent host/MCP traffic is governed by that permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
import http.client
import ipaddress
import math
import time
from types import MappingProxyType
from urllib.parse import urlsplit

from .providers.metadata_probes import MetadataError, ollama_show, request_json

CHECK_TTL_S = 180.0


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
        if (not isinstance(self.provider, str) or not self.provider
                or any(ord(c) < 32 for c in self.provider)):
            raise ValueError("Choose an available model service.")
        if (not isinstance(self.model, str) or not self.model or len(self.model) > 512
                or any(ord(c) < 32 for c in self.model)):
            raise ValueError("Choose a model first.")

    @property
    def identity(self):
        # Requested identifier; a server may resolve an alias internally.
        return "%s/%s" % (self.provider, self.model)


def _freeze_metadata(value, depth=0, memo=None):
    """Detach JSON-like input, retaining no mutable aliases or opaque objects."""
    if depth > 32:
        return None
    if memo is None:
        memo = {}
    if isinstance(value, (Mapping, list, tuple)):
        if id(value) in memo:
            return memo[id(value)]
        # Cycles are not JSON evidence. Shared subtrees reuse the immutable
        # copy, avoiding exponential expansion of caller-supplied aliases.
        memo[id(value)] = None
    if isinstance(value, Mapping):
        frozen = MappingProxyType({key: _freeze_metadata(item, depth + 1, memo)
                                   for key, item in value.items() if isinstance(key, str)})
        memo[id(value)] = frozen
        return frozen
    if isinstance(value, (list, tuple)):
        frozen = tuple(_freeze_metadata(item, depth + 1, memo) for item in value)
        memo[id(value)] = frozen
        return frozen
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


def _positive_int(value):
    return value if type(value) is int and value > 0 else None


@dataclass(frozen=True)
class ConnectionFacts:
    spec: ConnectionSpec
    metadata: Mapping = field(default_factory=dict, repr=False, compare=False)
    checked_at: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "metadata", _freeze_metadata(
            self.metadata if isinstance(self.metadata, Mapping) else {}))

    def __deepcopy__(self, memo):
        # The spec and recursively detached metadata are immutable.
        return self

    def fresh(self, now=None):
        stamp = self.checked_at
        now = time.time() if now is None else now
        try:
            return (type(stamp) in (int, float) and math.isfinite(stamp) and stamp > 0
                    and type(now) in (int, float) and math.isfinite(now)
                    and 0 <= now - stamp <= CHECK_TTL_S)
        except OverflowError:
            return False

    @property
    def capabilities(self):
        show = self.metadata.get("show")
        source = show if isinstance(show, Mapping) and "capabilities" in show else self.metadata
        caps = source.get("capabilities")
        if (not isinstance(caps, (list, tuple)) or any(
                not isinstance(cap, str) or not cap or any(ord(c) < 32 for c in cap) for cap in caps)):
            return None
        return frozenset(caps)

    @property
    def context_window(self):
        show = self.metadata.get("show")
        if not isinstance(show, Mapping):
            return None
        limits = []
        info = show.get("model_info")
        if isinstance(info, Mapping):
            limits.extend(value for key, value in info.items()
                          if key.endswith(".context_length") and _positive_int(value) is not None)
        params = show.get("parameters")
        if isinstance(params, str):
            for line in params.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] == "num_ctx":
                    try:
                        value = _positive_int(int(parts[1]))
                    except ValueError:
                        value = None
                    if value is not None:
                        limits.append(value)
        return min(limits) if limits else None

    @property
    def location(self):
        return self.location_at()

    def location_at(self, now=None):
        if self.spec.provider in ("claude", "gemini"):
            return "Cloud"
        if self.spec.provider == "ollama" and (":cloud" in self.spec.model.lower() or self.spec.model.lower().endswith("-cloud")):
            return "Cloud relay"
        show = self.metadata.get("show")
        show = show if isinstance(show, Mapping) else {}
        if any(value is not None and not isinstance(value, str)
               for source in (self.metadata, show) for key in ("remote_host", "remote_model")
               if key in source for value in (source[key],)):
            return "Unverified"
        if (self.metadata.get("remote_host") or self.metadata.get("remote_model")
                or show.get("remote_host") or show.get("remote_model")):
            return "Cloud relay"
        if not is_loopback(self.spec.endpoint):
            return "Remote"
        if self.spec.provider == "ollama" and self.fresh(now):
            # Positive weight-file metadata, not merely absence of remote_host.
            size = self.metadata.get("size")
            details = self.metadata.get("details")
            name = self.metadata.get("name") or self.metadata.get("model")
            if (_positive_int(size) is not None and isinstance(details, Mapping)
                    and details.get("format") == "gguf" and (name is None or name == self.spec.model)):
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
        caps = self.capabilities
        text += "\nReported capabilities: " + (", ".join(sorted(caps)) if caps else "unknown" if caps is None else "none")
        text += "\nReported context: " + (str(self.context_window) if self.context_window is not None else "unknown")
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
    _revoked: bool = field(default=False, repr=False)

    def revoke(self):
        """Stop future requests immediately, retaining an in-flight secret."""
        if self._revoked:
            return
        self._revoked = True
        grant = getattr(self.provider, "_model_grant", None)
        if grant is not None:
            grant.release()
        scope = getattr(self.provider, "_model_scope", None)
        if scope is not None:
            scope.active = False

    def release(self):
        self.revoke()
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
        from synapse.model_access import ModelAccessDenied, ModelRequestFailed
        try:
            return original_stream(**kwargs)
        except (ModelAccessDenied, ModelRequestFailed):
            raise
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


def _get_json(endpoint, path, headers, timeout=3.0):
    return request_json(endpoint, path, headers, timeout=timeout)


def _show_json(spec, headers, timeout=3.0):
    return ollama_show(spec, headers, timeout=timeout)


def _model_rows(payload, collection, provider):
    items = payload.get(collection)
    if not isinstance(items, list):
        raise MetadataError("The service returned an unreadable model list.")
    rows = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("id") or item.get("name") or item.get("model")
        if isinstance(name, str):
            if provider == "gemini":
                name = name.removeprefix("models/")
            if name and not any(ord(c) < 32 for c in name):
                rows[name] = item
    return rows


def list_ollama_models(endpoint):
    """List-only discovery: bounded metadata, no credentials, prompts or grants."""
    p = validate_endpoint(endpoint)
    path = p.path.removesuffix("/v1/chat/completions").rstrip("/") + "/api/tags"
    payload = _get_json(endpoint, path, {}, timeout=2.0)
    return tuple(_model_rows(payload, "models", "ollama"))


def check_connection(spec, key):
    """A bounded metadata check. Never sends prompts or claims inference works."""
    try:
        if spec.provider not in ("claude", "gemini", "ollama", "nemotron", "custom"):
            raise MetadataError("This engine is unavailable. Choose an available model service.")
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
        rows = _model_rows(payload, collection, spec.provider)
        if spec.model not in rows:
            return ConnectionCheck(False, "Service reached. This model was not listed; choose a listed model and check again.", tuple(rows))
        metadata = dict(rows[spec.model])
        if spec.provider == "ollama":
            try:
                metadata["show"] = _show_json(spec, headers)
            except Exception:
                # A failed detail check cannot erase a successful list check or
                # turn unknown capabilities into evidence from a model name.
                metadata["show"] = {"capabilities": None}
        facts = ConnectionFacts(spec, metadata, time.time())
        detail = " Capabilities unknown." if facts.capabilities is None else " Reported capabilities: " + (", ".join(sorted(facts.capabilities)) or "none") + "."
        return ConnectionCheck(True, "Service reached · model listed · generation untested. " + facts.location + detail,
                               tuple(rows), facts)
    except MetadataError as exc:
        return ConnectionCheck(False, str(exc))
    except Exception:
        # Do not echo response bodies, transport errors, or entered secrets.
        return ConnectionCheck(False, "Could not check the service. Check the address, key, and whether it is running.")
