#!/usr/bin/env python3
"""T.0 - measure the PRELOADED tool-definition cost on every surface.

Read-only probe. No hython, no running Houdini, no network. Serializes each
surface exactly as it puts tool definitions on the wire and counts the EMITTED
payload - it never estimates from source.

Surfaces measured:
  mcp_http    python/synapse/mcp/server.py -> jsonrpc_result(id, {"tools": get_tools()})
              The literal bytes hwebserver writes for a tools/list response.
  mcp_stdio   mcp_server.py -> MCP Tool() objects built from the same TOOL_DEFS.
              Payload-identical to mcp_http by construction; framing differs.
  panel       python/synapse/panel/tool_bridge.get_anthropic_tools()
              The tools=[...] array handed to client.messages.create().

The BEFORE number for the T-track. The AFTER is harness/verify/token_ceiling.json.
This script judges nothing - check_token_baseline_fresh surfaces the number.

Usage:
    python scripts/token_baseline.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))


def _tokenizer() -> tuple[str, object]:
    """Return (method_name, count_fn). Deterministic and offline, always.

    Rung 1 is a real BPE used as a declared PROXY - Claude's tokenizer is not
    public, so no local method is exact. Rung 2 is a character ratio. Either
    way the artifact also carries exact bytes/chars, which need no caveat and
    let anyone re-derive the number with a better tokenizer later.
    """
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return "tiktoken/cl100k_base (proxy BPE, not Claude's tokenizer)", (
            lambda s: len(enc.encode(s))
        )
    except Exception:
        return "chars_div_4 (proxy ratio - install tiktoken to sharpen)", (
            lambda s: round(len(s) / 4.0)
        )


def _measure(payload: bytes | str, n_tools: int, source: str, count) -> dict:
    """Exact size of one emitted payload, plus a declared token estimate."""
    raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    return {
        "tools": n_tools,
        "bytes": len(raw.encode("utf-8")),
        "chars": len(raw),
        "preload_tokens": count(raw),
        "source": source,
    }


def main() -> int:
    method, count = _tokenizer()
    surfaces: dict[str, dict] = {}

    # --- mcp_http: the literal bytes of a tools/list JSON-RPC response --------
    from synapse.mcp.protocol import jsonrpc_result
    from synapse.mcp.tools import get_tools

    http_tools = get_tools()
    http_wire = jsonrpc_result(1, {"tools": http_tools})
    surfaces["mcp_http"] = _measure(
        http_wire, len(http_tools),
        "synapse.mcp.protocol.jsonrpc_result(id, {'tools': tools.get_tools()})", count)

    # --- mcp_stdio: same registry, MCP Tool() shape, stdio framing ------------
    # mcp_server.py imports TOOL_DEFS and emits MCP-spec tool objects. Importing
    # that module standalone starts a WebSocket client, so the payload is rebuilt
    # from the identical source and labelled as such - the shape is the contract.
    stdio_tools = [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in http_tools
    ]
    stdio_wire = json.dumps({"tools": stdio_tools}, separators=(",", ":"), ensure_ascii=False)
    surfaces["mcp_stdio"] = _measure(
        stdio_wire, len(stdio_tools),
        "mcp_server.py Tool() shape rebuilt from shared TOOL_DEFS (annotations dropped)", count)

    # --- panel: the tools=[...] array passed to messages.create() -------------
    from synapse.panel.tool_bridge import get_anthropic_tools, get_anthropic_tools_for_worker

    panel_tools = list(get_anthropic_tools())
    panel_wire = json.dumps(panel_tools, separators=(",", ":"), ensure_ascii=False)
    surfaces["panel"] = _measure(
        panel_wire, len(panel_tools),
        "synapse.panel.tool_bridge.get_anthropic_tools()", count)

    worker_tools = list(get_anthropic_tools_for_worker())
    worker_wire = json.dumps(worker_tools, separators=(",", ":"), ensure_ascii=False)
    surfaces["panel_worker"] = _measure(
        worker_wire, len(worker_tools),
        "synapse.panel.tool_bridge.get_anthropic_tools_for_worker()", count)


    # --- boundary: the 6 synapse_group_* tools live only on the panel ---------
    registry_names = {t["name"] for t in http_tools}
    group_only = sorted({t["name"] for t in panel_tools} - registry_names)

    # --- staleness: digest the registry so a drifted baseline is loud ---------
    registry_fp = REPO_ROOT / "python" / "synapse" / "mcp" / "_tool_registry.py"
    registry_digest = hashlib.blake2b(registry_fp.read_bytes(), digest_size=16).hexdigest()

    stats = {
        "method": method,
        "surfaces": surfaces,
        "preload_tokens_total": {k: v["preload_tokens"] for k, v in surfaces.items()},
        "registry_tools": len(http_tools),
        "group_only_tools": group_only,
        "group_only_count": len(group_only),
        "boundary": (
            "MCP surfaces carry the 115 registry tools. The panel additionally carries "
            "the 6 synapse_group_* knowledge tools (121). panel_worker is the RBAC-"
            "narrowed subset and is reported for contrast, not as a fourth surface."
        ),
        "registry_blake2b": registry_digest,
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()

    out = {"schema": "token_baseline/v1", "stats": stats, "blake2b": digest}
    out_fp = REPO_ROOT / "harness" / "notes" / "token_baseline.json"
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[token_baseline] wrote {out_fp}")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
