"""ApexMCPProvider — H22's native APEX MCP behind the truth contract (D-H22-1).

The provider is a thin adapter: every ``call_tool`` returns a truth-contract
**envelope** recording what was actually observed
(docs/SYNAPSE_H22_PROVIDER_APEX.md §2). The provider itself NEVER sets
``claimed`` — a handler that asserts beyond ``observed`` must satisfy
:func:`assert_no_overclaim` (the rule ``check_mcp_truth_contract`` enforces).

Endpoint seam (the ONLY ADAPT point for task 2.7):
    ``SYNAPSE_APEX_MCP_ENDPOINT`` env — pre-drop default ``"mock"`` resolves
    the in-process :class:`~synapse.science.mcp_mock.MockApexMCP`; the shipped
    H22 transport (stdio vs HTTP unknown until task 1.7) lands HERE, nowhere
    else. Unknown endpoints fail loud — never a silent mock fallback.

``validator_verdict`` → ``agent.usd`` placement is deliberately NOT wired —
blocked on the open Gold RFC (boundary §10.2). The envelope carries it;
landing it is a small post-RFC change.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Optional

from synapse.providers import ProviderError

ENDPOINT_ENV = "SYNAPSE_APEX_MCP_ENDPOINT"
DEFAULT_ENDPOINT = "mock"
SOURCE_ID = "apex_mcp"


def args_digest(args: Optional[dict]) -> str:
    """sha256 of the sorted-key JSON args — stable provenance for the envelope."""
    canon = json.dumps(args or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def assert_no_overclaim(envelope: dict) -> None:
    """Truth contract: ``claimed`` (if a handler set one) must equal ``observed``.

    The provider never sets ``claimed``; this export is for any handler that
    does (D-H22-1's "no overclaiming an MCP result" non-goal).
    """
    if "claimed" in envelope and envelope["claimed"] != envelope.get("observed"):
        raise ProviderError(
            "truth-contract violation: 'claimed' != 'observed' — a handler may "
            "not claim an outcome it did not observe (D-H22-1).")


class ApexMCPProvider:
    """Truth-contract-wrapped adapter over the APEX MCP transport."""

    id = SOURCE_ID

    def __init__(self, transport: Any = None):
        self._transport = transport if transport is not None else self._resolve_transport()

    @staticmethod
    def _resolve_transport() -> Any:
        endpoint = (os.environ.get(ENDPOINT_ENV) or DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT
        if endpoint == "mock":
            from synapse.science.mcp_mock import MockApexMCP   # in-process Mode-A stand-in
            return MockApexMCP()
        # Post-drop (task 2.7): resolve the SHIPPED transport here. Until that
        # lands, an unknown endpoint fails loud — no silent fallback.
        raise ProviderError(
            f"unsupported APEX MCP endpoint '{endpoint}' — the shipped H22 "
            f"transport is the task-2.7 ADAPT point (synapse/providers/apex_mcp.py).")

    def list_tools(self) -> list:
        """The MCP's live tool surface: ``[{name, input_schema}]``."""
        try:
            return self._transport.list_tools()
        except Exception as e:
            raise ProviderError(
                f"apex_mcp transport failure listing tools: {e}") from e

    def call_tool(self, name: str, args: Optional[dict] = None) -> dict:
        """Call one MCP tool; return the truth-contract envelope."""
        args = args or {}
        try:
            observed = self._transport.call_tool(name, args)
        except Exception as e:
            raise ProviderError(
                f"apex_mcp transport failure calling '{name}': {e}") from e
        envelope: dict = {
            "observed": observed,          # the raw MCP result — never synthesized
            "source": SOURCE_ID,
            "tool": name,
            "args_digest": args_digest(args),
            "ts": time.time(),
        }
        # Present iff the tool result itself carried one. A provenance INPUT,
        # never restated as a SYNAPSE judgment (boundary §4 two-question rule).
        if isinstance(observed, dict) and "validator_verdict" in observed:
            envelope["validator_verdict"] = observed["validator_verdict"]
        return envelope
