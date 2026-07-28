#!/usr/bin/env python3
"""E1 - is 2,000 tokens reachable at the current tool count?

READ-ONLY. Writes one artifact under harness/notes/econ/.

harness/verify/token_ceiling.json declares max_preload_tokens = 2000, set by
CTO ruling 2026-07-23, ratchet down-only, not self-writable by a sprint. The
live mcp_http surface is 18,962 tokens across 120 tools. The E1 brief asks the
honest counter-question: is that ceiling reachable at this tool count, or is
the real decision FEWER tools rather than smaller ones?

That question cannot be answered by opinion, so this producer BUILDS the
degenerate surfaces and measures them. Each floor is a real payload serialised
through the real wire function, not an estimate:

  F0  as shipped                       everything
  F1  annotations dropped              the mcp_stdio shape - already in
                                       production on the other transport
  F2  F1 + property descriptions gone  schema keeps names/types/required
  F3  F1 + schemas emptied             name + description only
  F4  descriptions AND schemas gone    name + empty schema. The floor of a
                                       CATALOG: a legal MCP tool list that
                                       says nothing about any tool.
  F5  bare name array                  not a legal tool list. Absolute lower
                                       bound on 120 identifiers on the wire.

F4 is the load-bearing one. It is the cheapest thing that is still an MCP
tools/list response for 120 tools. If F4 exceeds the ceiling, then NO amount of
description or schema editing can reach 2,000 while 120 tools remain in
context, and the ceiling is a statement about tool COUNT, not tool SIZE.

The producer also inverts the question: given F4's cost per tool, how many
tools fit under 2,000? And it prices the alternative the ceiling was actually
calibrated for - a 3-verb deferred surface - so the comparison is like for like.

Emits: harness/notes/econ/E1_floor.json
Usage: python harness/notes/econ/econ_floor.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT_FP = Path(__file__).resolve().parent / "E1_floor.json"

CEILING_FP = REPO_ROOT / "harness" / "verify" / "token_ceiling.json"


def _tokenizer():
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    return "tiktoken/cl100k_base (proxy BPE, not Claude's tokenizer)", (
        lambda s: len(enc.encode(s)))


def _strip_prop_descriptions(node):
    """Recursively drop 'description' from schema property bodies."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "description":
                continue
            out[k] = _strip_prop_descriptions(v)
        return out
    if isinstance(node, list):
        return [_strip_prop_descriptions(v) for v in node]
    return node


def main() -> int:
    method, count = _tokenizer()

    from synapse.mcp.protocol import jsonrpc_result
    from synapse.mcp.tools import get_tools

    tools = get_tools()
    n = len(tools)

    def wire_tokens(tool_list) -> int:
        w = jsonrpc_result(1, {"tools": tool_list})
        if isinstance(w, bytes):
            w = w.decode("utf-8")
        return count(w)

    EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": []}

    f0 = list(tools)

    f1 = [{"name": t["name"], "description": t["description"],
           "inputSchema": t["inputSchema"]} for t in tools]

    f2 = []
    for t in tools:
        s = copy.deepcopy(t["inputSchema"])
        props = s.get("properties") or {}
        s["properties"] = {k: _strip_prop_descriptions(v) for k, v in props.items()}
        f2.append({"name": t["name"], "description": t["description"], "inputSchema": s})

    f3 = [{"name": t["name"], "description": t["description"],
           "inputSchema": copy.deepcopy(EMPTY_SCHEMA)} for t in tools]

    f4 = [{"name": t["name"], "description": "",
           "inputSchema": copy.deepcopy(EMPTY_SCHEMA)} for t in tools]

    f5_payload = json.dumps([t["name"] for t in tools],
                            separators=(",", ":"), ensure_ascii=False)

    floors = {
        "F0_as_shipped": {
            "tokens": wire_tokens(f0),
            "what": "everything: name + description + inputSchema + annotations",
            "legal_mcp_tools_list": True,
            "capability_note": "the shipped surface",
        },
        "F1_no_annotations": {
            "tokens": wire_tokens(f1),
            "what": "annotations dropped (the mcp_stdio shape)",
            "legal_mcp_tools_list": True,
            "capability_note": (
                "annotations are OPTIONAL in the MCP Tool object and the stdio "
                "transport already ships without them. Zero capability change."),
        },
        "F2_no_property_descriptions": {
            "tokens": wire_tokens(f2),
            "what": "F1 + every per-argument description removed; names/types/required kept",
            "legal_mcp_tools_list": True,
            "capability_note": (
                "LOSSY. Per-argument prose is what stops the model inventing "
                "argument values. Measured as a bound, not proposed."),
        },
        "F3_empty_schemas": {
            "tokens": wire_tokens(f3),
            "what": "F1 + inputSchema emptied; tool descriptions kept",
            "legal_mcp_tools_list": True,
            "capability_note": "LOSSY - the model no longer knows any argument exists.",
        },
        "F4_names_only_legal": {
            "tokens": wire_tokens(f4),
            "what": "name + empty description + empty schema",
            "legal_mcp_tools_list": True,
            "capability_note": (
                "THE CATALOG FLOOR. Cheapest legal tools/list for 120 tools. "
                "Says nothing about any tool - the model would have to route on "
                "the name alone."),
        },
        "F5_bare_name_array": {
            "tokens": count(f5_payload),
            "what": "a JSON array of the 120 names, nothing else",
            "legal_mcp_tools_list": False,
            "capability_note": (
                "NOT a tools/list response. Absolute lower bound on putting 120 "
                "identifiers on the wire in any form."),
        },
    }

    ceiling_doc = json.loads(CEILING_FP.read_text(encoding="utf-8"))
    ceiling = ceiling_doc["max_preload_tokens"]

    for k, v in floors.items():
        v["over_ceiling_by"] = v["tokens"] - ceiling
        v["ratio_to_ceiling"] = round(v["tokens"] / ceiling, 2)
        v["fits_under_ceiling"] = v["tokens"] <= ceiling

    # ---- invert: how many tools fit under the ceiling? --------------------
    f4_tokens = floors["F4_names_only_legal"]["tokens"]
    per_tool_floor = f4_tokens / n
    # measure directly rather than dividing - BPE is not linear
    probe = []
    for k in (10, 20, 30, 40, 60, 80, 100, 120):
        probe.append({"n_tools": k, "F4_tokens": wire_tokens(f4[:k])})
    # largest k whose F4 cost fits
    max_fit = None
    lo, hi = 1, n
    while lo <= hi:
        mid = (lo + hi) // 2
        if wire_tokens(f4[:mid]) <= ceiling:
            max_fit = mid
            lo = mid + 1
        else:
            hi = mid - 1

    # same question for the CURRENT average tool (F0 shape)
    max_fit_f0 = None
    lo, hi = 1, n
    while lo <= hi:
        mid = (lo + hi) // 2
        if wire_tokens(f0[:mid]) <= ceiling:
            max_fit_f0 = mid
            lo = mid + 1
        else:
            hi = mid - 1

    # ---- the alternative the ceiling was calibrated for -------------------
    # Three verbs, described well enough to route 120 tools. Descriptions here
    # are E1's own construction, sized to be realistic rather than optimistic.
    deferred = [
        {
            "name": "tool_search",
            "description": (
                "Find SYNAPSE tools by capability. Query in plain language "
                "(e.g. 'create a karma render node', 'read USD prim attributes'). "
                "Returns matching tool names with one-line summaries. Families: "
                "houdini_* (scene/USD/render), synapse_* (memory/routing/solaris), "
                "cops_* (Copernicus 2D), tops_* (PDG orchestration). Call this "
                "before tool_describe when you do not already know the tool name."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Plain-language capability description"},
                    "limit": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "tool_describe",
            "description": (
                "Return the full definition - description and JSON Schema - for "
                "one or more SYNAPSE tools by exact name. Call before tool_execute "
                "so arguments are built against the real schema rather than guessed."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "names": {"type": "array", "items": {"type": "string"},
                              "description": "Exact tool names from tool_search"},
                },
                "required": ["names"],
            },
        },
        {
            "name": "tool_execute",
            "description": (
                "Invoke a SYNAPSE tool by exact name with arguments matching the "
                "schema from tool_describe. Same dispatch spine as the flat "
                "surface: undo-wrapped, consent-gated, ledger-recorded."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact tool name"},
                    "arguments": {"type": "object", "description": "Arguments per the tool's schema"},
                },
                "required": ["name", "arguments"],
            },
        },
    ]
    deferred_tokens = wire_tokens(deferred)

    verdict = {
        "ceiling": ceiling,
        "ceiling_source": "harness/verify/token_ceiling.json (CTO ruling 2026-07-23)",
        "live_surface_tokens": floors["F0_as_shipped"]["tokens"],
        "live_tool_count": n,
        "catalog_floor_tokens": f4_tokens,
        "catalog_floor_over_ceiling_by": f4_tokens - ceiling,
        "reachable_as_flat_catalog": f4_tokens <= ceiling,
        "max_tools_under_ceiling_at_floor_shape": max_fit,
        "max_tools_under_ceiling_at_current_shape": max_fit_f0,
        "mean_floor_tokens_per_tool": round(per_tool_floor, 2),
        "scaling_probe": probe,
        "deferred_three_verb_tokens": deferred_tokens,
        "deferred_fits": deferred_tokens <= ceiling,
        "deferred_headroom": ceiling - deferred_tokens,
        "statement": None,  # filled below
    }

    if not verdict["reachable_as_flat_catalog"]:
        verdict["statement"] = (
            f"2,000 is NOT reachable as a flat catalog at {n} tools. The cheapest "
            f"LEGAL tools/list for {n} tools - every description empty, every "
            f"schema empty, nothing but names - costs {f4_tokens} tokens, which is "
            f"{f4_tokens - ceiling} OVER the ceiling before a single word of "
            f"description is written. At the floor shape only {max_fit} tools fit "
            f"under 2,000; at the current average tool shape only {max_fit_f0} do. "
            "The ceiling is therefore a statement about tool COUNT, not tool SIZE, "
            "and no description- or schema-editing programme can satisfy it while "
            f"all {n} definitions stay in context. The ceiling IS satisfiable by "
            f"the deferred surface it was calibrated for: three verbs measure "
            f"{deferred_tokens} tokens with {ceiling - deferred_tokens} to spare."
        )
    else:
        verdict["statement"] = (
            f"2,000 is reachable as a flat catalog at {n} tools: the catalog floor "
            f"is {f4_tokens}, under the {ceiling} ceiling. Reduction is then a "
            "question of how much description and schema fits in the remainder."
        )

    stats = {
        "method": method,
        "surface": "mcp_http jsonrpc_result(1, {'tools': ...})",
        "n_tools": n,
        "floors": floors,
        "verdict": verdict,
        "deferred_surface_definition": deferred,
        "deferred_note": (
            "The three verbs are E1's own construction, written to be realistic "
            "rather than flattering - full routing hints in tool_search. They are "
            "NOT a proposal (that is E2's call, and it needs E0's cache answer "
            "first); they exist so the ceiling is compared against the shape it "
            "was actually calibrated for."
        ),
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16).hexdigest()

    out = {
        "schema": "e1_floor/v1",
        "producer": "harness/notes/econ/econ_floor.py",
        "stats": stats,
        "blake2b": digest,
    }
    OUT_FP.parent.mkdir(parents=True, exist_ok=True)
    OUT_FP.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[econ_floor] wrote {OUT_FP}")
    print(json.dumps({
        "floors": {k: {"tokens": v["tokens"], "ratio_to_ceiling": v["ratio_to_ceiling"],
                       "fits": v["fits_under_ceiling"]} for k, v in floors.items()},
        "verdict": {k: v for k, v in verdict.items() if k != "scaling_probe"},
        "scaling_probe": probe,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
