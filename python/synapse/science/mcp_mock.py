"""MockApexMCP — Mode-A stand-in for H22's native APEX MCP (D-H22-1/2/4).

Serves the tool surface recorded in ``apex_mcp_surface.json`` — the mock and
the surface probe share that ONE source of truth, so the Mode-A diff is empty
by construction and the probe machinery is proven before the drop. The shape
matches the confirmed intel: the APEX Script Comfort Package is a KNOWLEDGE
server (snippets + syntax rules + validator), NOT scene mutation.

Pure Python, ZERO ``hou`` — consistent with the science-package contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

SURFACE_PATH = Path(__file__).resolve().parent / "apex_mcp_surface.json"

# Benign knowledge-server payloads. The hou.node reference in the second
# snippet is DELIBERATE: it lets scout's federated exists_in_runtime grounding
# exercise a real dotted symbol against the introspected table.
_SNIPPETS: list = [
    {"id": "apex:snippet:pose_blend", "type": "apex_snippet",
     "text": "Blend two rig poses in an APEX graph: wire skeleton::SetPoseLocal "
             "into a Blend node and drive the bias parm. Pure APEX node types."},
    {"id": "apex:snippet:python_drive", "type": "apex_snippet",
     "text": "Drive an APEX rig pose from Python: fetch the graph with "
             "hou.node('/obj/apex_rig') and set the promoted pose parms."},
    {"id": "apex:rule:graph_eval", "type": "apex_rule",
     "text": "APEX graphs evaluate lazily: only nodes upstream of a requested "
             "output port cook. Order ports explicitly when a rig pose depends "
             "on side effects."},
]

_RULES: list = [
    "Edit APEX graphs through the graph API — never string-splice .apex files.",
    "Validate generated APEX with the validator tool before instantiating it on a rig.",
]


class MockApexMCP:
    """Same ``list_tools`` / ``call_tool`` duck-type the shipped MCP presents."""

    def __init__(self, surface_path: Path = SURFACE_PATH):
        raw = json.loads(Path(surface_path).read_text(encoding="utf-8"))
        self._tools: dict = {t["name"]: t.get("input_schema", {})
                             for t in raw["tools"]}

    def list_tools(self) -> list:
        return [{"name": name, "input_schema": schema}
                for name, schema in sorted(self._tools.items())]

    def call_tool(self, name: str, args: Optional[dict] = None) -> Any:
        args = args or {}
        if name not in self._tools:
            raise KeyError(f"MockApexMCP has no tool '{name}' "
                           f"(recorded surface: {sorted(self._tools)})")
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:   # on the recorded surface but unimplemented — fail loud
            raise NotImplementedError(
                f"mock handler missing for recorded tool '{name}'")
        return handler(args)

    # ── tool handlers (benign, deterministic) ────────────────────────────────

    def _tool_ping(self, args: dict) -> dict:
        return {"pong": True, "server": "mock_apex_mcp"}

    def _tool_validate(self, args: dict) -> dict:
        src = str(args.get("src", ""))
        return {"src_chars": len(src),
                "validator_verdict": {"valid": True, "errors": []}}

    def _tool_search_snippets(self, args: dict) -> dict:
        toks = {t.lower() for t in
                re.findall(r"[A-Za-z0-9_]+", str(args.get("query", "")))
                if len(t) > 1}
        k = int(args.get("k") or 6)
        scored = []
        for s in _SNIPPETS:
            overlap = len(toks & {t.lower() for t in
                                  re.findall(r"[A-Za-z0-9_]+", s["text"])})
            if overlap:
                scored.append((overlap, s))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        return {"snippets": [s for _, s in scored[:k]]}

    def _tool_get_rules(self, args: dict) -> dict:
        return {"rules": list(_RULES)}
