"""Custom provider — a user-configured OpenAI-compatible endpoint (id="custom").

A thin subclass of ``NemotronProvider`` (like Ollama): the chat-completions
transport, SSE parser, and stateful ``<think>`` filter are inherited verbatim.
Configuration — base URL, model id, optional key env-var name — lives in
``<repo>/.synapse/panel_settings.json`` (``panel/settings.py``); the registry
injects it at construction. An UNCONFIGURED Custom engine is surfaced through
the worker's ``resolve_key`` → ``key_error_message`` path — never a silent
Claude switch (D3).

Endpoint follows the ``NVIDIA_BASE_URL`` semantics: scheme preserved (http and
https both work), a bare host defaults to https, an empty/all-slash path
collapses to ``/v1``. This file deliberately holds no raw TLS-connection
literal — the streaming transport is pinned in ``nemotron_provider.py``
(tests/test_m3_egress_docs.py); the user-configured-endpoint posture is
documented in docs/studio/EGRESS.md. No Qt, no hou.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from .nemotron_provider import NemotronProvider

_DEFAULT_BASE_PATH = "/v1"


class CustomProvider(NemotronProvider):
    """Streams a user-configured OpenAI-compat endpoint into the Anthropic
    envelope via the inherited Nemotron transport."""

    id = "custom"

    def __init__(self, base_url: str = "", model: str = "", key_env: str = "",
                 max_tokens: int = 4096) -> None:
        super().__init__(model=model, max_tokens=max_tokens)
        self._base_url = (base_url or "").strip()
        self._key_env = (key_env or "").strip()

    def _configured(self) -> bool:
        return bool(self._base_url and self._model)

    def _get_endpoint(self):
        parts = urlsplit(self._base_url if "//" in self._base_url
                         else "https://" + self._base_url)
        scheme = parts.scheme or "https"
        host = parts.netloc
        # rstrip FIRST so '/' collapses to '' → falls back to /v1 (the
        # nemotron ``_endpoint`` idiom — a trailing slash must not drop /v1).
        path = parts.path.rstrip("/") or _DEFAULT_BASE_PATH
        return scheme, host, path + "/chat/completions"

    def _system_directive(self):
        # Nemotron's "detailed thinking on/off" toggle is meaningless to an
        # arbitrary backend — no directive; the inherited <think> filter
        # handles any reasoning leakage.
        return None

    def resolve_key(self):
        if not self._configured():
            return None   # surfaced via key_error_message — no silent switch
        if not self._key_env:
            return "not-needed"   # keyless endpoint (local vLLM/Ollama posture)
        # Ensure the project .env is loaded into os.environ — a Custom-first
        # session may never touch the Anthropic path. Side-effect import,
        # never raise (the nemotron/ollama idiom).
        try:
            import synapse.host.auth  # noqa: F401 — side-effect: loads <repo>/.env
        except Exception:
            pass
        v = os.environ.get(self._key_env)
        if v and v.strip():
            return v.strip()
        return None

    def key_error_message(self) -> str:
        if not self._configured():
            return ("Custom engine not configured — set Base URL and model "
                    "(model chip → Configure…).")
        return ("No key found in %s. Set it at the SYSTEM level so Houdini "
                "inherits it, then relaunch Houdini — or clear the key env in "
                "the Configure… dialog for a keyless endpoint." % self._key_env)
