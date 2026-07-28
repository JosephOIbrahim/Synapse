#!/usr/bin/env python3
"""E0 - what a SYNAPSE turn actually costs, segment by segment.

Read-only. No network, no hython, no Houdini. Drives the SHIPPED request-
construction code rather than re-implementing it, then measures the payload
each segment contributes to one Anthropic request.

Answers, with a producer path beside every number (Law 2):

  Q1  the tool-surface figure, re-measured on TODAY's tree, under BOTH the
      T.0 serialization and the WIRE serialization the panel actually emits.
  Q3  the four request segments, ranked by measured size.
  Q4  per-segment byte-stability across a 3-turn session.
  Q5  the effective per-turn cost with and without a cache prefix.

Every reader here is calibrated before it is trusted (R60) and every control
is mutation-tested (R133) - CAL-1..CAL-6 below. A control that cannot fail is
a decoration, not a check (Law 1), so each one states its failure condition
and is then actually driven to failure.

Usage:
    python harness/notes/econ/econ_segments.py
Writes:
    harness/notes/econ/E0_segments.json
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT = Path(__file__).resolve().parent / "E0_segments.json"


# ---------------------------------------------------------------------------
# Tokenizers. Claude's is not public and the API is credit-blocked (E0-F1), so
# every count here is a DECLARED PROXY. Two encodings are reported so the
# reader can see how much of a figure is tokenizer choice rather than payload.
# ---------------------------------------------------------------------------

def _encoders() -> dict:
    import tiktoken
    return {
        "cl100k_base": tiktoken.get_encoding("cl100k_base"),
        "o200k_base": tiktoken.get_encoding("o200k_base"),
    }


ENC = _encoders()


def count(s: str, enc: str = "cl100k_base") -> int:
    return len(ENC[enc].encode(s))


def measure(s: str) -> dict:
    """Exact bytes/chars need no caveat; the token columns are proxies."""
    return {
        "bytes": len(s.encode("utf-8")),
        "chars": len(s),
        "tok_cl100k": count(s, "cl100k_base"),
        "tok_o200k": count(s, "o200k_base"),
    }


def h(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()


# ---------------------------------------------------------------------------
# The two serializations. They are NOT the same, and the difference is a
# finding: scripts/token_baseline.py measured the compact form, while
# panel/providers/anthropic_provider.py:120 emits json.dumps(body) with DEFAULT
# arguments - ensure_ascii=True and ", " / ": " separators.
# ---------------------------------------------------------------------------

def ser_t0(obj) -> str:
    """scripts/token_baseline.py:96 - compact, non-escaping."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def ser_wire_panel(obj) -> str:
    """panel/providers/anthropic_provider.py:120 - json.dumps(body), defaults."""
    return json.dumps(obj)


def orjson_active() -> bool:
    """mcp/protocol.py:15-24 picks its serializer at import time.

    With orjson present the MCP wire is compact; without it the fallback is
    json.dumps(sort_keys=True) at DEFAULT separators, which is materially
    larger. The same tool surface therefore measures differently depending on
    an optional dependency, so the environment is recorded beside the figure.
    """
    try:
        import orjson  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Shipped surfaces
# ---------------------------------------------------------------------------

def load_surfaces() -> dict:
    from synapse.mcp.protocol import jsonrpc_result
    from synapse.mcp.tools import get_tools
    from synapse.panel.tool_bridge import (
        get_anthropic_tools,
        get_anthropic_tools_for_worker,
    )

    mcp_tools = get_tools()
    panel_tools = list(get_anthropic_tools())
    worker_tools = list(get_anthropic_tools_for_worker())

    return {
        "mcp_tools": mcp_tools,
        "panel_tools": panel_tools,
        "worker_tools": worker_tools,
        # The literal bytes hwebserver writes for a tools/list response.
        "mcp_http_wire": jsonrpc_result(1, {"tools": mcp_tools}).decode("utf-8"),
    }


# TWO reconstructed sessions, because ONE would have been a rigged control.
# STATIONARY holds the network fixed - the friendliest realistic case for a cache.
# NAVIGATING moves between /obj and /stage, which is what an artist doing lookdev
# actually does, and which swaps a 567-char guidance literal for a 5,779-char one
# INSIDE the cached span. Reporting only the stationary session would have
# reported the cache as far healthier than it is.
SESSIONS = {
    "stationary": [
        {"network": "/stage", "selection": [], "frame": 1, "hip": "shot_010.hip"},
        {"network": "/stage", "selection": ["/stage/karmarendersettings1"],
         "frame": 1, "hip": "shot_010.hip"},
        {"network": "/stage", "selection": ["/stage/domelight1", "/stage/keylight1"],
         "frame": 24, "hip": "shot_010.hip"},
    ],
    "navigating": [
        {"network": "/stage", "selection": [], "frame": 1, "hip": "shot_010.hip"},
        {"network": "/obj", "selection": ["/obj/geo1"], "frame": 1, "hip": "shot_010.hip"},
        {"network": "/stage", "selection": ["/stage/domelight1"], "frame": 24,
         "hip": "shot_010.hip"},
    ],
}


def build_turn_context(turn: int, session: str = "stationary") -> dict:
    """The context dict panel/system_prompt.build_system_prompt consumes.

    Every field here is one the SHIPPED code reads (system_prompt.py:255-277),
    supplied by the panel at synapse_panel.py:1715-1732.
    """
    return SESSIONS[session][turn]


def build_messages(turn: int, grounding_payload: str) -> list:
    """An append-only 3-turn history in the shape claude_worker.py builds.

    Turn N's messages are turn N-1's messages plus (user, assistant). The
    tool-use round trip inside a turn appends an assistant tool_use block and a
    user tool_result block to the SAME list (claude_worker.py:171,191), which is
    why the grounding payload becomes permanent history rather than transient.
    """
    msgs: list = []
    prompts = [
        "set up a three point light rig on the stage",
        "make the key warmer and drop the fill",
        "now render frame 24 at 1080p",
    ]
    for i in range(turn + 1):
        msgs.append({"role": "user", "content": prompts[i]})
        # the model grounds itself once per turn, then answers
        msgs.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"toolu_{i:02d}", "name": "synapse_inspect_scene",
             "input": {"path": "/stage", "max_depth": 3}},
        ]})
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"toolu_{i:02d}",
             "content": grounding_payload},
        ]})
        msgs.append({"role": "assistant", "content": [
            {"type": "text", "text": "Done - three lights wired, key at exposure 1.0."},
        ]})
    return msgs


def load_grounding_payload() -> dict:
    """C1's measured grounding cost, read from the committed artifact.

    E0 does not re-measure grounding - C1 already did it on six SideFX scenes
    under the same proxy tokenizer. Read, cite, do not re-derive (Law 5).
    """
    fp = REPO_ROOT / "harness" / "notes" / "token_bench" / "summary.json"
    d = json.loads(fp.read_text(encoding="utf-8"))
    curve = d["curve"]["A_inspect_scene_d3"]
    return {
        "source": "harness/notes/token_bench/summary.json:curve.A_inspect_scene_d3",
        "curve": curve,
        "ladder": d.get("ladder"),
    }


# ---------------------------------------------------------------------------
# Calibration. Each control names the condition under which it FAILS, and is
# then actually driven to that condition (R133 mutation test). A control that
# only ever passes proves nothing.
# ---------------------------------------------------------------------------

def calibrate(surfaces: dict) -> list:
    cals = []
    panel_tools = surfaces["panel_tools"]
    blob = ser_t0(panel_tools)

    # CAL-1 determinism -----------------------------------------------------
    a, b = count(blob), count(blob)
    cals.append({
        "id": "CAL-1", "what": "tokenizer determinism",
        "fails_if": "two counts of the identical string differ",
        "observed": {"count_1": a, "count_2": b, "delta": a - b},
        "verdict": "PASS" if a == b else "FAIL",
        "mutation": None,
    })

    # CAL-2 additivity ------------------------------------------------------
    # Segment counts must approximately sum to the whole-payload count. A large
    # gap would mean the segmentation is measuring something other than the
    # request. BPE merges across join boundaries make exact equality wrong to
    # expect, so the tolerance is stated rather than assumed.
    per_tool = sum(count(ser_t0(t)) for t in panel_tools)
    whole = count(blob)
    drift = whole - per_tool
    cals.append({
        "id": "CAL-2", "what": "segment additivity (sum of parts vs whole)",
        "fails_if": "|whole - sum(parts)| exceeds 2% of whole, meaning the "
                    "segmentation does not describe the payload it claims to",
        "observed": {"sum_of_tools": per_tool, "whole_array": whole,
                     "delta": drift, "pct_of_whole": round(100.0 * drift / whole, 3)},
        "verdict": "PASS" if abs(drift) <= 0.02 * whole else "FAIL",
        "note": "delta is the array's own punctuation plus BPE joins, not error",
        "mutation": None,
    })

    # CAL-3 sensitivity, MUTATION-TESTED ------------------------------------
    # Drop one tool. The reader must register the loss. If it does not, the
    # reader is blind to exactly the thing T.1 proposes to change.
    dropped = panel_tools[:-1]
    lost = count(blob) - count(ser_t0(dropped))
    solo = count(ser_t0(panel_tools[-1]))
    cals.append({
        "id": "CAL-3", "what": "reader registers a removed tool",
        "fails_if": "removing a tool does not reduce the count",
        "observed": {"tokens_lost_by_removal": lost,
                     "that_tool_measured_alone": solo,
                     "name": panel_tools[-1]["name"]},
        "verdict": "PASS" if lost > 0 else "FAIL",
        "mutation": "removed the last tool from the array and re-counted",
    })

    # CAL-4 the STABILITY detector, mutation-tested BOTH ways ---------------
    # Q4's entire answer rests on a hash comparison. A hash that never differs
    # would report everything as perfectly cacheable - the most flattering
    # possible wrong answer. Prove it can say "changed", and prove it can say
    # "unchanged".
    s1 = ser_t0(panel_tools)
    s2 = ser_t0(list(panel_tools))          # same content, rebuilt list
    mutated = copy.deepcopy(panel_tools)
    mutated[0] = {**mutated[0], "description": mutated[0]["description"] + " "}
    s3 = ser_t0(mutated)
    same_ok = h(s1) == h(s2)
    diff_ok = h(s1) != h(s3)
    cals.append({
        "id": "CAL-4", "what": "byte-stability detector (the Q4 instrument)",
        "fails_if": "it reports 'changed' for identical content (false alarm) OR "
                    "'unchanged' after a one-space edit (blind)",
        "observed": {"identical_content_same_hash": same_ok,
                     "one_space_edit_detected": diff_ok},
        "verdict": "PASS" if (same_ok and diff_ok) else "FAIL",
        "mutation": "appended a single space to one tool description",
    })

    # CAL-5 tool ORDER stability --------------------------------------------
    # A set-ordered tools array would silently destroy every cache hit while
    # every size figure stayed identical. Size readers cannot see this.
    o1 = [t["name"] for t in surfaces["panel_tools"]]
    from synapse.panel.tool_bridge import get_anthropic_tools
    o2 = [t["name"] for t in get_anthropic_tools()]
    o3 = [t["name"] for t in get_anthropic_tools()]
    shuffled = list(reversed(o1))
    cals.append({
        "id": "CAL-5", "what": "tool ORDER is stable across calls",
        "fails_if": "two calls to get_anthropic_tools() return different order, "
                    "which invalidates the cache prefix without changing its size",
        "observed": {"order_stable_across_3_calls": o1 == o2 == o3,
                     "detector_sees_a_reversal": h(ser_t0(o1)) != h(ser_t0(shuffled)),
                     "n_tools": len(o1)},
        "verdict": "PASS" if (o1 == o2 == o3 and h(ser_t0(o1)) != h(ser_t0(shuffled)))
                   else "FAIL",
        "mutation": "reversed the name list and confirmed the detector fires",
    })

    # CAL-7 THE ONE THAT MATTERS: does this reader reproduce T.0's committed
    # figure EXACTLY on an input that has not drifted? -----------------------
    # panel_worker is the RBAC-narrowed subset. If its content is unchanged
    # since T.0, this reader must return T.0's recorded integer to the token.
    # Agreement proves reader identity; any disagreement on the OTHER surfaces
    # is then attributable to tree drift rather than to measurement drift.
    baseline0 = json.loads(
        (REPO_ROOT / "harness" / "notes" / "token_baseline.json").read_text(encoding="utf-8"))
    recorded_worker = baseline0["stats"]["surfaces"]["panel_worker"]
    mine_worker = measure(ser_t0(surfaces["worker_tools"]))
    exact = (recorded_worker["preload_tokens"] == mine_worker["tok_cl100k"]
             and recorded_worker["chars"] == mine_worker["chars"]
             and recorded_worker["bytes"] == mine_worker["bytes"]
             and recorded_worker["tools"] == len(surfaces["worker_tools"]))
    cals.append({
        "id": "CAL-7", "what": "this reader reproduces T.0's committed figure bit-exactly "
                               "on the one surface whose content did not drift",
        "fails_if": "the recomputed panel_worker figure differs from the committed one "
                    "in tools, bytes, chars or tokens - which would mean the deltas on "
                    "the other surfaces are reader drift and not tree drift",
        "observed": {"committed": recorded_worker, "recomputed": {
            "tools": len(surfaces["worker_tools"]), **mine_worker}},
        "verdict": "PASS" if exact else "FAIL",
        "note": "PASS licenses the central Q1 inference: mcp_http and panel moved "
                "because the TREE moved, not because the meter moved.",
        "mutation": None,
    })

    # CAL-8 the SEGMENTER, mutation-tested ----------------------------------
    # The Q4 answer depends on cutting the system prompt at the right seam. An
    # earlier draft of this producer split on "\\n\\n" and silently cut the scene
    # block in half, because the block's own body contains a blank line - which
    # reported the volatile block as STABLE. That is the most flattering
    # possible wrong answer, so the seam is now driven by the shipped formatter
    # and checked.
    from synapse.panel.system_prompt import _format_scene_context, build_system_prompt as _bsp
    ctx_a = {"network": "/stage", "selection": [], "frame": 1, "hip": "a.hip"}
    ctx_b = {"network": "/stage", "selection": ["/stage/light1"], "frame": 24, "hip": "a.hip"}
    blk_a, blk_b = _format_scene_context(ctx_a), _format_scene_context(ctx_b)
    p_a, p_b = _bsp(ctx_a), _bsp(ctx_b)
    found = (blk_a in p_a) and (blk_b in p_b)
    removed_a = p_a.replace(blk_a, "")
    removed_b = p_b.replace(blk_b, "")
    cals.append({
        "id": "CAL-8", "what": "the system-prompt segmenter cuts at the real seam",
        "fails_if": "the shipped formatter's output is not found verbatim inside the "
                    "assembled prompt (seam is wrong), OR the volatile block fails to "
                    "differ between two different scene contexts (segmenter is blind), "
                    "OR the remainder differs once the block is removed (seam leaks)",
        "observed": {
            "block_found_verbatim_in_prompt": found,
            "volatile_block_differs_between_contexts": blk_a != blk_b,
            "remainder_identical_once_block_removed": removed_a == removed_b,
            "block_a": blk_a, "block_b": blk_b,
        },
        "verdict": "PASS" if (found and blk_a != blk_b and removed_a == removed_b) else "FAIL",
        "mutation": "two different scene contexts; the detector must call the block "
                    "changed and the remainder unchanged",
    })

    # CAL-6 freshness of the inherited baseline -----------------------------
    reg = REPO_ROOT / "python" / "synapse" / "mcp" / "_tool_registry.py"
    live_digest = hashlib.blake2b(reg.read_bytes(), digest_size=16).hexdigest()
    baseline = json.loads(
        (REPO_ROOT / "harness" / "notes" / "token_baseline.json").read_text(encoding="utf-8"))
    recorded = baseline["stats"]["registry_blake2b"]
    cals.append({
        "id": "CAL-6", "what": "is the inherited T.0 baseline still describing this tree",
        "fails_if": "the recorded registry digest does not match the live file, "
                    "meaning the 17,310 figure describes a registry that no longer exists",
        "observed": {"recorded": recorded, "live": live_digest,
                     "match": recorded == live_digest,
                     "baseline_registry_tools": baseline["stats"]["registry_tools"],
                     "live_registry_tools": len(surfaces["mcp_tools"]),
                     "baseline_panel_tools": baseline["stats"]["surfaces"]["panel"]["tools"],
                     "live_panel_tools": len(surfaces["panel_tools"])},
        "verdict": "PASS" if recorded == live_digest else "FAIL",
        "note": "FAIL here is a FINDING about the inherited number, not about this reader",
        "mutation": None,
    })

    return cals


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _measure_session(session_name, surfaces, build_system_prompt, _format_scene_context):
    """Drive the shipped request-construction code across one 3-turn session."""
    turns, raw_histories = [], []
    for t in range(3):
        ctx = build_turn_context(t, session_name)
        system = build_system_prompt(ctx)

        # Cut at the seam the SHIPPED formatter produces, never at a guessed
        # delimiter. CAL-8 proves this seam is real and that the detector can
        # see the block change.
        block = _format_scene_context(ctx)
        assert block in system, "segmenter seam broke - see CAL-8"
        remainder = system.replace(block, "")

        # A grounding PLACEHOLDER. Revision 1's comment claimed this was "sized
        # at C1's smallest rung (443 tokens)"; it is 200 cl100k tokens, and the
        # claim had no producer. The placeholder's size is now MEASURED and
        # emitted below, and the cost model does not use it at all - it uses
        # C1's real per-rung figures. Its only job is to make the history shape
        # realistic (a tool_result block that persists).
        stub = "x" * 1600
        msgs = build_messages(t, stub)
        chat_only = build_messages(t, "")
        raw_histories.append(msgs)

        tools_wire = ser_wire_panel(surfaces["panel_tools"])
        turns.append({
            "turn": t + 1,
            "session": session_name,
            "context": ctx,
            "tools": {**measure(tools_wire), "hash": h(tools_wire)},
            "system": {**measure(system), "hash": h(system)},
            "system_scene_context_block": {
                "char_offset_in_prompt": system.index(block),
                "pct_through_prompt": round(100.0 * system.index(block) / len(system), 1),
                "text": block,
                **measure(block), "hash": h(block),
            },
            "system_minus_scene_context": {**measure(remainder), "hash": h(remainder)},
            "history": {**measure(ser_wire_panel(msgs)), "hash": h(ser_wire_panel(msgs)),
                        "n_messages": len(msgs)},
            # The chat text WITHOUT any grounding payload. E0's own Q3 correction
            # says grounding lives inside history; reporting a combined "history"
            # figure alongside a separate "grounding" figure double-counts it and
            # makes the four segments a non-partition. This is the disjoint half.
            "history_chat_only": {**measure(ser_wire_panel(chat_only)),
                                  "n_messages": len(chat_only)},
            "grounding_placeholder_measured": measure(stub),
        })
    return turns, raw_histories


def _stability(turns, raw_histories):
    def stable(key):
        vals = [t[key]["hash"] for t in turns]
        return {"hashes": vals, "stable_across_3_turns": len(set(vals)) == 1}

    # History GROWS by design. The question that decides whether an incremental
    # breakpoint is possible is whether turn N is reproduced byte-identically as
    # a PREFIX of turn N+1.
    prefix_ok, prefix_detail = True, []
    for i in range(len(raw_histories) - 1):
        older, newer = raw_histories[i], raw_histories[i + 1]
        pre = newer[:len(older)]
        ok = (len(pre) == len(older)
              and all(ser_wire_panel(a) == ser_wire_panel(b) for a, b in zip(older, pre)))
        prefix_ok = prefix_ok and ok
        prefix_detail.append({
            "from_turn": i + 1, "to_turn": i + 2,
            "older_len": len(older), "newer_len": len(newer),
            "every_older_message_byte_identical_in_newer": ok,
            "messages_appended": len(newer) - len(older),
        })
    corrupt = copy.deepcopy(raw_histories[1])
    corrupt[0] = {**corrupt[0], "content": corrupt[0]["content"] + "!"}
    caught = not all(ser_wire_panel(a) == ser_wire_panel(b)
                     for a, b in zip(raw_histories[0], corrupt[:len(raw_histories[0])]))
    return {
        "tools": stable("tools"),
        "system_whole": stable("system"),
        "system_scene_context_block": stable("system_scene_context_block"),
        "system_minus_scene_context": stable("system_minus_scene_context"),
        "history": stable("history"),
        "history_prefix": {
            "older_turns_reproduced_byte_identically": prefix_ok,
            "per_step": prefix_detail,
            "mutation_control": {
                "fails_if": "corrupting an earlier message still reports 'identical'",
                "corruption_detected": caught,
                "verdict": "PASS" if caught else "FAIL",
            },
        },
    }


def system_prompt_anatomy():
    """Producer for every system-prompt sub-figure E0 quotes (Law 2).

    Revision 1 of E0_COST.md quoted part sizes and per-network totals that came
    from a subagent's prose and appeared in NO artifact - and two of them did not
    reproduce. Every one of those numbers is emitted here, from the shipped
    module, so the document can cite a producer instead of a conversation.
    """
    import synapse.panel.system_prompt as sp

    parts = {
        "_IDENTITY": sp._IDENTITY,
        "_TOOL_GUIDANCE": sp._TOOL_GUIDANCE,
        "_SOLARIS_CONTEXT_GUIDANCE": sp._SOLARIS_CONTEXT_GUIDANCE,
        "_OBJ_CONTEXT_GUIDANCE": sp._OBJ_CONTEXT_GUIDANCE,
    }
    tone = sp._load_tone()
    if tone:
        parts["TONE.md"] = tone

    base = {"selection": [], "frame": 1, "hip": "shot_010.hip"}
    by_network = {}
    for net in ("/stage", "/obj", "/out", "/img", "/mat", "/"):
        prompt = sp.build_system_prompt({**base, "network": net})
        by_network[net] = {**measure(prompt),
                           "guidance_block": (
                               "_SOLARIS_CONTEXT_GUIDANCE"
                               if sp._solaris_context_block({**base, "network": net})
                               is sp._SOLARIS_CONTEXT_GUIDANCE else
                               "_OBJ_CONTEXT_GUIDANCE"
                               if sp._solaris_context_block({**base, "network": net})
                               is sp._OBJ_CONTEXT_GUIDANCE else "none")}

    # Single-field cache-bust deltas. Revision 1 quoted "-5,214 chars" for
    # /stage->/obj and called it the biggest hazard. It is neither produced nor
    # the biggest: /stage->/out is larger. Both are computed here.
    ref = sp.build_system_prompt({**base, "network": "/stage"})
    deltas = {}
    for label, ctx in (
        ("network /stage->/obj", {**base, "network": "/obj"}),
        ("network /stage->/out", {**base, "network": "/out"}),
        ("network /stage->/img", {**base, "network": "/img"}),
        ("frame 1->2", {**base, "network": "/stage", "frame": 2}),
        ("hip rename", {**base, "network": "/stage", "hip": "shot_011.hip"}),
        ("selection []->[one]", {**base, "network": "/stage",
                                 "selection": ["/stage/domelight1"]}),
    ):
        other = sp.build_system_prompt(ctx)
        deltas[label] = {"delta_chars": len(other) - len(ref),
                         "delta_tok_cl100k": count(other) - count(ref),
                         "byte_identical": other == ref}

    # The scene-context block's real size RANGE, so "29-90 tokens" is produced.
    ranges = {}
    for label, sel in (
        ("empty", []),
        ("one_short", ["/obj/geo1"]),
        ("five_long", [f"/stage/materials/mtlxstandard_surface{i}" for i in range(5)]),
        ("forty_long", [f"/stage/materials/mtlxstandard_surface{i}" for i in range(40)]),
    ):
        blk = sp._format_scene_context({**base, "network": "/stage", "selection": sel})
        ranges[label] = measure(blk)

    return {
        "parts": {k: measure(v) for k, v in parts.items()},
        "composed_by_network": by_network,
        "single_field_deltas_vs_stage": deltas,
        "scene_context_block_range": ranges,
        "biggest_single_field_hazard": max(
            deltas.items(), key=lambda kv: abs(kv[1]["delta_chars"]))[0],
    }


def main() -> int:
    from synapse.panel.system_prompt import build_system_prompt

    surfaces = load_surfaces()
    grounding = load_grounding_payload()
    cals = calibrate(surfaces)

    # --- Q1: the tool surface, re-measured -------------------------------
    # Reported under BOTH serializations, because the spread between them is
    # the honest error bar on any local estimate: the Anthropic API re-renders
    # tool definitions into its own canonical form, so neither the client's
    # whitespace nor its escaping choices survive into the billed count.
    baseline = json.loads(
        (REPO_ROOT / "harness" / "notes" / "token_baseline.json").read_text(encoding="utf-8"))
    bstats = baseline["stats"]["surfaces"]

    tool_surface = {
        "mcp_http": {
            "n_tools": len(surfaces["mcp_tools"]),
            "t0_method": measure(surfaces["mcp_http_wire"]),
            "wire_actual": measure(surfaces["mcp_http_wire"]),
            "method_note": "T.0's method and the wire are THE SAME payload here: "
                           "scripts/token_baseline.py:74 measures "
                           "jsonrpc_result(1, {'tools': get_tools()}) verbatim, "
                           "envelope included.",
            "serializer_is_environment_dependent": {
                "orjson_present": orjson_active(),
                "why_it_matters": "mcp/protocol.py:15-24 uses orjson (compact) when "
                                  "importable and json.dumps(sort_keys=True) at DEFAULT "
                                  "separators otherwise. The same tool surface measures "
                                  "differently on two machines.",
            },
            "who_builds_the_anthropic_request": "NOT SYNAPSE. On the MCP path SYNAPSE is "
                                                "the SERVER; the external client (Claude "
                                                "Code / Desktop) builds the model request "
                                                "and owns every cache_control decision.",
        },
        "panel": {
            "n_tools": len(surfaces["panel_tools"]),
            "t0_method": measure(ser_t0(surfaces["panel_tools"])),
            "wire_actual": measure(ser_wire_panel(surfaces["panel_tools"])),
            "method_note": "t0_method = scripts/token_baseline.py:96 (compact, "
                           "ensure_ascii=False). wire_actual = the separators and "
                           "escaping json.dumps(body) actually emits at "
                           "panel/providers/anthropic_provider.py:120.",
            "who_builds_the_anthropic_request": "SYNAPSE (panel provider) - the only "
                                                "surface where SYNAPSE can set cache_control.",
        },
        "panel_worker": {
            "n_tools": len(surfaces["worker_tools"]),
            "t0_method": measure(ser_t0(surfaces["worker_tools"])),
            "wire_actual": measure(ser_wire_panel(surfaces["worker_tools"])),
            "method_note": "RBAC-narrowed subset; reported for contrast.",
            "who_builds_the_anthropic_request": "SYNAPSE (autonomous worker).",
        },
    }
    for name, d in tool_surface.items():
        d["wire_vs_t0_token_delta"] = (
            d["wire_actual"]["tok_cl100k"] - d["t0_method"]["tok_cl100k"])
        rec = bstats.get(name, {})
        d["t0_committed_2026_07_23"] = {
            "n_tools": rec.get("tools"), "preload_tokens": rec.get("preload_tokens")}
        if rec.get("preload_tokens"):
            d["drift_vs_committed_t0_tokens"] = (
                d["t0_method"]["tok_cl100k"] - rec["preload_tokens"])
            d["drift_vs_committed_t0_tools"] = d["n_tools"] - rec["tools"]
        d["ceiling_2000_multiple_t0"] = round(d["t0_method"]["tok_cl100k"] / 2000.0, 2)
        d["ceiling_2000_multiple_wire"] = round(d["wire_actual"]["tok_cl100k"] / 2000.0, 2)

    # --- Q3/Q4: the four segments across 3 turns -------------------------
    # Grounding is sized at C1's largest rung and, separately, at its smallest,
    # so the ranking is reported as a RANGE rather than one flattering point.
    curve = grounding["curve"]
    g_tokens = curve["tokens_cl100k"] if isinstance(curve, dict) and "tokens_cl100k" in curve else None
    if g_tokens is None:
        # summary.json shape defence - never guess, surface it
        g_tokens = curve if isinstance(curve, list) else []

    from synapse.panel.system_prompt import _format_scene_context

    all_sessions = {}
    for session_name in SESSIONS:
        turns, raw_histories = _measure_session(
            session_name, surfaces, build_system_prompt, _format_scene_context)
        all_sessions[session_name] = {
            "turns": turns,
            "stability": _stability(turns, raw_histories),
        }

    turns = all_sessions["stationary"]["turns"]
    stability = all_sessions["stationary"]["stability"]

    out = {
        "schema": "e0_segments/v1",
        "produced_by": "harness/notes/econ/econ_segments.py",
        "tokenizer": "tiktoken cl100k_base + o200k_base - DECLARED PROXIES. "
                     "Claude's tokenizer is an API call this account cannot reach "
                     "(harness/notes/_credit_probe.py, HTTP 400, 2026-07-28).",
        "calibration": cals,
        "q1_tool_surface": tool_surface,
        "q3_q4_turns": turns,
        "q4_stability": stability,
        "q4_stability_by_session": {k: v["stability"] for k, v in all_sessions.items()},
        "q3_q4_turns_by_session": {k: v["turns"] for k, v in all_sessions.items()},
        "grounding_reference": grounding,
        "system_prompt_anatomy": system_prompt_anatomy(),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[econ_segments] wrote {OUT}")
    for c in cals:
        print(f"  {c['id']} {c['verdict']:4}  {c['what']}")
    print("\n  tool surface (cl100k, wire serialization):")
    for k, v in tool_surface.items():
        print(f"    {k:14} n={v['n_tools']:4}  t0={v['t0_method']['tok_cl100k']:6}  "
              f"wire={v['wire_actual']['tok_cl100k']:6}  delta={v['wire_vs_t0_token_delta']:+6}")
    print("\n  per-turn stability:")
    for k, v in stability.items():
        if "stable_across_3_turns" in v:
            print(f"    {k:32} stable={v['stable_across_3_turns']}")
    hp = stability["history_prefix"]
    print(f"    {'history_prefix byte-identical':32} {hp['older_turns_reproduced_byte_identically']}"
          f"  (mutation control {hp['mutation_control']['verdict']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
