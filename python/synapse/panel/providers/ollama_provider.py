"""Ollama provider — local-first OpenAI-compatible streaming (GLM 5 et al).

A thin subclass of ``NemotronProvider``: the OpenAI chat-completions transport,
SSE parser, and stateful ``<think>`` filter are inherited verbatim (GLM's
reasoning spans are stripped by the same filter, chunk-straddling included).
Only the endpoint, the key posture, and the system directive differ.

Endpoint: ``OLLAMA_HOST`` env (default ``http://localhost:11434``, tolerant of
a bare ``host:port``) → ``{base}/v1/chat/completions``. Verified live on
Ollama 0.30.11 (2026-07-01): ``/v1/chat/completions`` streams ``tool_calls``
deltas over SSE — the inherited parser consumes them unchanged.

Localhost surface by default (documented in docs/studio/EGRESS.md). A remote
``OLLAMA_HOST`` routes through the transport pinned in ``nemotron_provider.py``
— this file deliberately holds no raw TLS-connection literal, so the frozen
egress pin (tests/test_m3_egress_docs.py) stays exact; the remote-host caveat
lives in EGRESS.md. No Qt, no hou.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import ssl
from urllib.parse import urlsplit

from .nemotron_provider import NemotronProvider

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "http://localhost:11434"


def _ollama_endpoint():
    """(scheme, host, request_path) honouring ``OLLAMA_HOST`` (Ollama's own env
    convention; a bare ``host:port`` gets plaintext http — the local default)."""
    base = os.environ.get("OLLAMA_HOST", "").strip() or _DEFAULT_BASE
    parts = urlsplit(base if "//" in base else "http://" + base)
    scheme = parts.scheme or "http"
    host = parts.netloc or "localhost:11434"
    path = parts.path.rstrip("/")
    return scheme, host, path


def _parse_tags(data):
    """GET /api/tags JSON → ``((name, name), ...)`` model rows, or ``None`` when
    empty/unshaped (the caller falls back to the registry rows)."""
    try:
        names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except AttributeError:
        return None
    return tuple((n, n) for n in names) or None


class OllamaProvider(NemotronProvider):
    """Streams a local (or remote) Ollama OpenAI-compat endpoint into the
    Anthropic envelope via the inherited Nemotron transport."""

    id = "ollama"

    def _get_endpoint(self):
        scheme, host, path = _ollama_endpoint()
        return scheme, host, path + "/v1/chat/completions"

    def _system_directive(self):
        # Nemotron's "detailed thinking on/off" toggle is meaningless to GLM —
        # no directive; the inherited <think> filter handles any leakage.
        return None

    def resolve_key(self):
        # Local Ollama needs no key; OLLAMA_API_KEY covers a cloud/proxied
        # posture. Never blocks on a missing key. Import host.auth for its
        # .env-loading side-effect (an Ollama-first session may never touch
        # the Anthropic path).
        try:
            import synapse.host.auth  # noqa: F401 — side-effect: loads <repo>/.env
        except Exception:
            pass
        v = os.environ.get("OLLAMA_API_KEY")
        if v and v.strip():
            return v.strip()
        return "not-needed"

    @staticmethod
    def available_models(timeout=1.0):
        """Live ``(name, name)`` rows from ``GET {OLLAMA_HOST}/api/tags``, or
        ``None`` on any failure. Menu-open is user-initiated — bounded by a
        short timeout so a down daemon costs ~nothing."""
        scheme, host, path = _ollama_endpoint()
        # Connection class picked indirectly: the frozen egress pin scans for
        # raw TLS-connection call literals; this file's remote posture is
        # documented in EGRESS.md (the streaming transport is pinned in
        # nemotron_provider.py).
        conn_cls = (http.client.HTTPConnection if scheme == "http"
                    else http.client.HTTPSConnection)
        try:
            if scheme == "http":
                conn = conn_cls(host, timeout=timeout)
            else:
                conn = conn_cls(host, timeout=timeout,
                                context=ssl.create_default_context())
            try:
                conn.request("GET", path + "/api/tags")
                resp = conn.getresponse()
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            finally:
                conn.close()
            return _parse_tags(data)
        except Exception as exc:
            logger.debug("Ollama /api/tags unavailable: %s", exc)
            return None
