#!/usr/bin/env python3
"""E0 Q5 - what a turn costs once prompt caching is priced in.  [REVISION 2]

Read-only, offline arithmetic over E0_segments.json and E0_gaps.json. No new
measurement happens here.

REVISION 2 rewrites revision 1 after an adversarial pass upheld three
showstoppers against it. The two that changed conclusions:

  1. UNIT SUBSTITUTION. Revision 1 compared a COST figure (billed-token-
     equivalents) against harness/verify/token_ceiling.json's 2,000, which is a
     max_preload_tokens budget - CONTEXT-WINDOW OCCUPANCY, not price. A cache
     read changes what a token COSTS, not whether it OCCUPIES the window. The
     two quantities are now computed and reported separately and never compared.
     The brief itself makes this substitution, which is why it matters.

  2. PER-CALL vs PER-TURN. Revision 1 charged every span exactly once per user
     turn. The shipped panel makes one FULL request per tool-loop iteration - up
     to 25 (claude_worker.py:34,153) - each carrying the same tools array and the
     same frozen system string (claude_worker.py:85). Those requests are seconds
     apart and byte-identical, so iterations 2..k are near-certain cache reads.
     Charging once made caching look far worse than it is and manufactured a
     "cache written but never read" penalty that the intra-turn loop refutes.

Usage:
    python harness/notes/econ/econ_effective.py
Writes:
    harness/notes/econ/E0_effective.json
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEG = json.loads((HERE / "E0_segments.json").read_text(encoding="utf-8"))
GAPS_FP = HERE / "E0_gaps.json"
GAPS = json.loads(GAPS_FP.read_text(encoding="utf-8")) if GAPS_FP.exists() else None
OUT = HERE / "E0_effective.json"

W_WRITE, W_READ, W_PLAIN = 1.25, 0.10, 1.0
CEILING_PRELOAD_TOKENS = 2000   # harness/verify/token_ceiling.json:max_preload_tokens

TS = SEG["q1_tool_surface"]
T3 = SEG["q3_q4_turns"][2]

TOOLS_PANEL = TS["panel"]["wire_actual"]["tok_cl100k"]
TOOLS_PANEL_T0 = TS["panel"]["t0_method"]["tok_cl100k"]
TOOLS_MCP = TS["mcp_http"]["wire_actual"]["tok_cl100k"]

SYS_TOTAL = T3["system"]["tok_cl100k"]
SYS_VOLATILE = T3["system_scene_context_block"]["tok_cl100k"]
SYS_STATIC = T3["system_minus_scene_context"]["tok_cl100k"]
CHAT_T3 = T3["history_chat_only"]["tok_cl100k"]

GROUND = SEG["grounding_reference"]["curve"]


def _curve_tokens(curve):
    """C1's measured grounding cost, read from the committed artifact (Law 2).

    C1 emits TWO token columns per rung and revision 1 silently took the smaller.
    Both are returned and the choice is stated: 'tokens' is what the tool
    returns; 'tokens_model_visible' is what the model is charged after the double
    JSON encode (C1-F8). The model-visible column is the right one for a COST
    model, and taking the smaller understated grounding inside the very argument
    that grounding dominates.
    """
    pts = curve["points"]
    raw = [p["tokens"] for p in pts]
    vis = [p.get("tokens_model_visible") for p in pts]
    rungs = [p["rung"] for p in pts]
    if any(t is None for t in raw):
        raise RuntimeError("C1 curve points carry no 'tokens' field - refusing to "
                           "substitute a remembered figure.")
    vis = [v if v is not None else r for v, r in zip(vis, raw)]
    return raw, vis, rungs


G_RAW, G_VIS, G_RUNGS = _curve_tokens(GROUND)
GROUND_MIN, GROUND_MAX = min(G_VIS), max(G_VIS)
GROUND_MIN_RUNG = G_RUNGS[G_VIS.index(GROUND_MIN)]
GROUND_MAX_RUNG = G_RUNGS[G_VIS.index(GROUND_MAX)]

STAB_BY_SESSION = SEG["q4_stability_by_session"]


def stability(session):
    s = STAB_BY_SESSION[session]
    return {
        "tools": s["tools"]["stable_across_3_turns"],
        "system_whole": s["system_whole"]["stable_across_3_turns"],
        "system_static": s["system_minus_scene_context"]["stable_across_3_turns"],
    }


def ttl_evidence():
    if not GAPS or GAPS.get("status") != "MEASURED":
        return {"status": "UNMEASURED",
                "note": "econ_gaps.py has not run; WARM/COLD are bounds only."}
    sweep = GAPS["sweep"]
    pct = {k: (v["pct_over_ttl"] if v else None) for k, v in sweep.items()}
    return {
        "status": "MEASURED",
        "producer": "harness/notes/econ/econ_gaps.py -> E0_gaps.json",
        "entries": GAPS["diagnostics"]["parsed"],
        "span": GAPS["span"],
        "pct_of_inter_burst_gaps_exceeding_300s_TTL": pct,
        "reading": "Revision 1 asserted artist think-time 'routinely exceeds 5 minutes' with "
                   "NO producer, and used it to argue the cache would usually be cold. "
                   "Measured on this machine's audit log, at a 30s burst threshold 36.8% of "
                   "inter-burst gaps exceed the TTL - so the majority fall INSIDE it. The "
                   "assertion is not supported; COLD is a real regime but not the common one.",
        "bias": GAPS["bias_direction"],
    }


ASSUMPTIONS = [
    {"id": "A1",
     "assumption": "Cache WRITE = 1.25x base input rate, cache READ = 0.1x, default 5-minute "
                   "ephemeral TTL.",
     "status": "TAKEN FROM THE BRIEF, NOT RE-VERIFIED against current pricing.",
     "falsified_by": "pricing docs showing different multipliers, or adoption of the 1h TTL "
                     "(2.0x write).",
     "sensitivity": "linear - every BTE figure scales directly with these two numbers."},
    {"id": "A2",
     "assumption": "Token counts are the tiktoken/cl100k_base proxy from econ_segments.py.",
     "status": "DECLARED PROXY - Claude's tokenizer is not public and the API is credit-blocked.",
     "falsified_by": "a funded account running messages.count_tokens.",
     "sensitivity": "RATIOS between programmes are far more robust than absolute magnitudes."},
    {"id": "A3",
     "assumption": "A cache hit needs byte-identity AND the request inside the TTL.",
     "status": "NOW PARTLY MEASURED (op-burst proxy, econ_gaps.py), not asserted.",
     "falsified_by": "instrumented CHAT-turn timings, which would beat this op-burst proxy.",
     "sensitivity": "decides how much weight the COLD column deserves."},
    {"id": "A4",
     "assumption": "Billed input tokens are computed on Anthropic's canonical rendering of the "
                   "tool definitions, not the client's JSON bytes.",
     "status": "STRUCTURAL LIMIT ON ANY LOCAL ESTIMATE.",
     "falsified_by": "a funded count_tokens call on the same tools array.",
     "sensitivity": "the panel's two serializations differ 24% on an identical tool set."},
    {"id": "A5",
     "assumption": "The reconstructed sessions are representative in SHAPE, not recordings.",
     "status": "RECONSTRUCTED FROM SHIPPED CODE. The brief's oracle asked for 3 REAL turns; "
               "none exist. This is a NAMED ORACLE MISS, not a satisfied requirement.",
     "falsified_by": "a captured transcript of real panel turns.",
     "sensitivity": "affects history/grounding accumulation only."},
    {"id": "A6",
     "assumption": "A changed SYSTEM block still leaves the TOOLS breakpoint hittable, because "
                   "prefix order is tools -> system -> messages and matching is longest-prefix.",
     "status": "NOT OBSERVED LIVE. Follows from documented ordering; no live request was made.",
     "falsified_by": "a live request showing cache_read_input_tokens = 0 when only the system "
                     "block changed.",
     "sensitivity": "LOAD-BEARING. If false, tools become a 1.25x write on every first call "
                    "and every cached row gets materially worse."},
    {"id": "A7",
     "assumption": "Within one user turn, tool-loop iterations 2..k hit the cache: seconds "
                   "apart, byte-identical tools array, frozen system string.",
     "status": "CODE-VERIFIED for byte-identity (claude_worker.py:85 stores the system string "
               "once; :157 passes the same self._tools every iteration). The cache behaviour "
               "itself is NOT observed live.",
     "falsified_by": "the same live request A6 needs.",
     "sensitivity": "LOAD-BEARING and it INVERTS revision 1's conclusion. At k=1 caching can "
                    "be a net penalty; at k>=2 it wins decisively."},
]


def span_cost(n, cached, content_stable, warm, first_call_of_turn, first_turn):
    """Cost of one prefix span on ONE API call, in billed-token-equivalents.

    Three independent ways a cached span fails to pay off, all modelled:
      COLD START - nothing cached yet (first call of the session)
      TTL        - the entry expired between turns
      CONTENT    - a byte inside the span changed, so no entry can match
    Any of them forces a 1.25x write, 25% worse than not marking the span.
    """
    if not cached:
        return n * W_PLAIN
    if first_turn and first_call_of_turn:
        return n * W_WRITE
    if first_call_of_turn:
        if not warm or not content_stable:
            return n * W_WRITE
        return n * W_READ
    return n * W_READ          # iterations 2..k of the SAME turn (A7)


def turn_cost(tools, sys_static, sys_volatile, chat, grounding_per_call, k,
              cache_tools, cache_system, warm, first_turn,
              system_span_content_stable, turn_index):
    """Billed-token-equivalents for ONE USER TURN of k API calls.

    Grounding ACCUMULATES. A tool_result produced at iteration i is re-sent on
    every later call in the turn and on every call of every later turn, because
    nothing compacts history. That is E0's own Q3 correction, now implemented
    rather than merely stated.
    """
    system_span = sys_static + sys_volatile
    parts = {"tools": 0.0, "system": 0.0, "chat": 0.0, "grounding": 0.0}
    for call in range(k):
        first = (call == 0)
        parts["tools"] += span_cost(tools, cache_tools, True, warm, first, first_turn)
        parts["system"] += span_cost(system_span, cache_system,
                                     system_span_content_stable, warm, first, first_turn)
        parts["chat"] += chat * W_PLAIN
        parts["grounding"] += grounding_per_call * (turn_index * k + call) * W_PLAIN
    return {**{a: round(b, 1) for a, b in parts.items()},
            "total": round(sum(parts.values()), 1)}


SCENARIOS = [
    ("S1_as_shipped",
     "Today: breakpoints on the last tool and on the WHOLE system prompt "
     "(anthropic_provider.py:64,69). No breakpoint on history.",
     "PANEL", True, True, False),
    ("S2_no_caching_at_all",
     "The premise T.1 is argued from: nothing cached.",
     "PANEL", False, False, False),
    ("S3_T1_reduction_no_caching",
     "T.1 delivered (tool surface cut to 2,000), caching off.",
     "CEILING", False, False, False),
    ("S4_T1_reduction_plus_caching",
     "T.1 delivered AND caching on, volatile block still inside the cached span.",
     "CEILING", True, True, False),
    ("S5_caching_plus_volatile_moved",
     "No tool reduction. Caching on, volatile scene block moved OUT of the cached span.",
     "PANEL", True, True, True),
    ("S6_T1_plus_caching_plus_volatile_moved",
     "BOTH programmes plus the volatile fix. The row revision 1 omitted - and the natural "
     "combination, since nobody would ship T.1 and switch caching off.",
     "CEILING", True, True, True),
]


def build_table(session, k, warm):
    rows = {}
    stab = stability(session)
    for name, desc, tool_kind, c_tools, c_sys, moved in SCENARIOS:
        tools = CEILING_PRELOAD_TOKENS if tool_kind == "CEILING" else TOOLS_PANEL
        vol_in = 0 if moved else SYS_VOLATILE
        vol_out = SYS_VOLATILE if moved else 0
        sys_stable = stab["system_static"] if moved else stab["system_whole"]
        cells = {}
        for scene_label, g in ((f"small_{GROUND_MIN_RUNG}", GROUND_MIN),
                               (f"large_{GROUND_MAX_RUNG}", GROUND_MAX)):
            for turn_label, ti, ft in (("turn_1", 0, True), ("turn_3_steady", 2, False)):
                cells[f"{scene_label}|{turn_label}"] = turn_cost(
                    tools, SYS_STATIC, vol_in, CHAT_T3 + vol_out, g, k,
                    c_tools, c_sys, warm, ft, sys_stable, ti)
        rows[name] = {"description": desc, "cells": cells}
    return rows


TABLE = {}
for _session in ("stationary", "navigating"):
    for _k in (1, 2, 5):
        for _wl, _warm in (("WARM", True), ("COLD", False)):
            TABLE[f"{_session}|k={_k}|{_wl}"] = build_table(_session, _k, _warm)


def cell(regime, scenario, scene_prefix, turn="turn_3_steady"):
    cells = TABLE[regime][scenario]["cells"]
    key = next(kk for kk in cells if kk.startswith(scene_prefix) and kk.endswith(turn))
    return cells[key]["total"]


preload = {
    "_what_this_is": "CONTEXT-WINDOW OCCUPANCY in tokens. This is what "
                     "harness/verify/token_ceiling.json:max_preload_tokens budgets, and it is "
                     "the quantity T.1 reduces.",
    "_caching_does_not_change_it": "A cache read changes what a token COSTS. The tokens still "
                                   "occupy the window, still consume attention, and still count "
                                   "against the ceiling. Revision 1 compared a cost figure to "
                                   "this budget; that was a unit substitution, corrected here.",
    "ceiling": CEILING_PRELOAD_TOKENS,
    "panel_wire_cl100k": TOOLS_PANEL,
    "panel_t0_cl100k": TOOLS_PANEL_T0,
    "mcp_http_cl100k": TOOLS_MCP,
    "panel_multiple_of_ceiling": round(TOOLS_PANEL / CEILING_PRELOAD_TOKENS, 2),
    "mcp_multiple_of_ceiling": round(TOOLS_MCP / CEILING_PRELOAD_TOKENS, 2),
    "verdict": "OVER the ceiling on every surface under every reading. Caching does NOTHING "
               "for this quantity. On preload tokens, T.1 is the ONLY lever.",
}

cost = {
    "_what_this_is": "PRICE in billed-token-equivalents (BTE) = input tokens x multiplier. "
                     "A cost unit, never comparable to a preload-token ceiling.",
    "tool_span_per_api_call": {
        "uncached": round(TOOLS_PANEL * W_PLAIN, 1),
        "cache_read": round(TOOLS_PANEL * W_READ, 1),
        "cache_write": round(TOOLS_PANEL * W_WRITE, 1),
        "read_saving_vs_uncached_pct": round(100 * (1 - W_READ), 1),
    },
    "verdict": "Caching cuts the PRICE of the tool span by 90% per cache-read call. It does "
               "not cut its SIZE at all.",
}

verdict = {
    "the_question": "Is T.1 the right first mile, or is a cache-control change?",
    "the_answer": "They are NOT alternatives - they optimise DIFFERENT QUANTITIES. T.1 reduces "
                  "context-window occupancy (preload tokens); caching reduces price (BTE). The "
                  "brief poses them as 'opposite engineering programmes' and that framing is "
                  "the error: a cache read cannot put anything under a preload-token ceiling, "
                  "and a tool-surface reduction cannot make a cached token cheaper. Measured, "
                  "BOTH are worth doing, and S6 - both plus the volatile fix - is the cheapest "
                  "row in every regime measured.",
    "preload_tokens": preload,
    "cost_BTE": cost,
    "ttl_evidence": ttl_evidence(),
    "best_scenario_per_regime": {},
    "segment_ranking": {},
    "large_scene_spread": {},
}

for _regime in TABLE:
    for _scene in ("small_", "large_"):
        _best = min(((n, cell(_regime, n, _scene)) for n, *_ in SCENARIOS), key=lambda x: x[1])
        verdict["best_scenario_per_regime"][f"{_regime}|{_scene.rstrip('_')}"] = {
            "scenario": _best[0], "BTE": _best[1]}

# Revision 1 claimed large-scene scenarios land "within 3%" of each other. Compute
# the actual spread instead of asserting a band.
_large = [cell(r, n, "large_") for r in TABLE for n, *_ in SCENARIOS]
verdict["large_scene_spread"] = {
    "min_BTE": round(min(_large), 1), "max_BTE": round(max(_large), 1),
    "ratio_max_over_min": round(max(_large) / min(_large), 2),
    "note": "Revision 1 asserted 'every scenario lands within 3% of ~119k BTE'. Computed "
            "rather than asserted, the spread is far wider. The surviving claim is the "
            "RANKING (grounding dominates), not a narrow band.",
}

for _label, _g in (("small_scene", GROUND_MIN), ("large_scene", GROUND_MAX)):
    _k = 2
    _raw = {"tool_definitions": TOOLS_PANEL, "system_prompt": SYS_TOTAL,
            "conversation_chat": CHAT_T3, "scene_grounding_resident": _g * _k}
    _total = sum(_raw.values())
    verdict["segment_ranking"][_label] = {
        "note": "Per-API-CALL occupancy at turn 3 with k=2 calls/turn, grounding RESIDENT in "
                "history rather than a separate transient line. The four rows are DISJOINT: "
                "conversation_chat excludes grounding, so the shares are a real partition. "
                "Revision 1's rows overlapped and its shares were not a partition.",
        "raw_tokens": _raw,
        "ranked": sorted(_raw.items(), key=lambda kv: -kv[1]),
        "total": _total,
        "pct": {a: round(100.0 * b / _total, 1) for a, b in _raw.items()},
    }

band = {
    "panel_tools_cl100k_t0_serialization": TOOLS_PANEL_T0,
    "panel_tools_cl100k_wire_serialization": TOOLS_PANEL,
    "panel_tools_o200k_wire_serialization": TS["panel"]["wire_actual"]["tok_o200k"],
    "spread_pct_between_the_two_serializations": round(
        100.0 * (TOOLS_PANEL - TOOLS_PANEL_T0) / TOOLS_PANEL_T0, 1),
    "why": "Same tool set, two defensible local serializations, 24% apart. Anthropic "
           "re-renders tool definitions canonically (A4), so neither is the billed number.",
}

out = {
    "schema": "e0_effective/v2",
    "revision": "2 - rewritten after an adversarial pass upheld three showstoppers against "
                "revision 1: unit substitution (BTE vs preload ceiling), per-call vs per-turn "
                "modelling, and the omitted S6 row.",
    "produced_by": "harness/notes/econ/econ_effective.py",
    "inputs_from": ["harness/notes/econ/E0_segments.json", "harness/notes/econ/E0_gaps.json"],
    "cost_unit": "BTE = billed-token-equivalent = input tokens x price multiplier "
                 "(1.0 plain / 1.25 write / 0.1 read). A COST unit. NEVER compared to a "
                 "preload-token budget.",
    "assumptions": ASSUMPTIONS,
    "grounding_source": {
        "artifact": "harness/notes/token_bench/summary.json:curve.A_inspect_scene_d3.points",
        "rungs": G_RUNGS, "tokens_payload": G_RAW, "tokens_model_visible": G_VIS,
        "column_used": "tokens_model_visible - what the model is charged after the double JSON "
                       "encode (C1-F8). Revision 1 used the smaller 'tokens' column without "
                       "stating the choice.",
        "min_rung": GROUND_MIN_RUNG, "max_rung": GROUND_MAX_RUNG},
    "stability_by_session": {s: stability(s) for s in STAB_BY_SESSION},
    "table": TABLE,
    "verdict": verdict,
    "tokenizer_and_serialization_band": band,
}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"[econ_effective] wrote {OUT}  (revision 2)\n")
print("TWO QUANTITIES, KEPT APART")
print(f"  PRELOAD TOKENS (occupancy)   panel {TOOLS_PANEL:,} = "
      f"{preload['panel_multiple_of_ceiling']}x the {CEILING_PRELOAD_TOKENS} ceiling."
      f"  Caching does not change this.")
print(f"  COST (BTE) per API call      uncached {cost['tool_span_per_api_call']['uncached']:,}"
      f" -> cache read {cost['tool_span_per_api_call']['cache_read']:,}  (-90%)\n")
_t = ttl_evidence()
if _t["status"] == "MEASURED":
    print(f"TTL EVIDENCE (econ_gaps.py, {_t['entries']:,} audit entries)")
    for _kk, _v in _t["pct_of_inter_burst_gaps_exceeding_300s_TTL"].items():
        print(f"  {_kk:<28} {_v}% of gaps exceed the 5-min TTL")
    print()
print("STEADY-STATE TURN COST (BTE), turn 3, small scene")
print(f"  {'scenario':<44}{'stat k=1 WARM':>15}{'stat k=2 WARM':>15}"
      f"{'stat k=2 COLD':>15}{'nav k=2 WARM':>15}")
for _n, *_ in SCENARIOS:
    print(f"  {_n:<44}"
          f"{cell('stationary|k=1|WARM', _n, 'small_'):>15,.0f}"
          f"{cell('stationary|k=2|WARM', _n, 'small_'):>15,.0f}"
          f"{cell('stationary|k=2|COLD', _n, 'small_'):>15,.0f}"
          f"{cell('navigating|k=2|WARM', _n, 'small_'):>15,.0f}")
print("\nSEGMENT RANKING (per API call, turn 3, k=2, grounding resident, rows disjoint)")
for _label in verdict["segment_ranking"]:
    print(f"  {_label}:")
    for _a, _b in verdict["segment_ranking"][_label]["ranked"]:
        print(f"     {_a:<30}{_b:>9,}  {verdict['segment_ranking'][_label]['pct'][_a]:>5}%")
print(f"\nLARGE-SCENE SPREAD  min {verdict['large_scene_spread']['min_BTE']:,.0f}  "
      f"max {verdict['large_scene_spread']['max_BTE']:,.0f}  "
      f"ratio {verdict['large_scene_spread']['ratio_max_over_min']}x")
print("\nCHEAPEST SCENARIO PER REGIME (small scene)")
for _kk, _v in verdict["best_scenario_per_regime"].items():
    if _kk.endswith("small"):
        print(f"  {_kk:<28} {_v['scenario']:<44} {_v['BTE']:>12,.0f}")
