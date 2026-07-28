#!/usr/bin/env python3
"""E1 - decompose the preloaded tool surface, per tool, per component.

READ-ONLY. No hython, no running Houdini, no network. Writes one artifact under
harness/notes/econ/ and nothing else.

T.0 (scripts/token_baseline.py) measured a TOTAL: mcp_http = 17,310 tokens for
115 tools. A total is not a plan. This producer decomposes the SAME payload,
built through the SAME public entry point, into the cost centres that compress
differently:

    name          untouchable - renaming breaks every caller
    description   prose the model reads to decide WHEN to call. The only
                  component where cutting risks correctness.
    inputSchema   JSON Schema. Safe to compress: a shorter schema changes how
                  arguments are stated, never whether the tool is reached.
    annotations   auto-DERIVED metadata (title + 4 hint booleans). The E1 brief
                  names three components; the mcp_http wire carries four.
                  Reported separately because every byte of it is recomputable
                  from the tool name and three registry booleans.

WIRE FIDELITY. The live surface is emitted by protocol._dumps, which is
orjson.dumps(obj, OPT_SORT_KEYS) when orjson is importable - compact separators
AND alphabetically sorted keys. Tool objects therefore appear on the wire as
{annotations, description, inputSchema, name}, not in registry insertion order.
This producer serialises each tool the same way, so the per-tool fragments are
literally the bytes that ship.

CALIBRATION (R60), and it can fail (Law 1). Two independent gates:

  G1 historical  Reconstruct the registry AS OF T.0's commit (d92bb4b), run
                 this exact reader over it, and require 115 tools / 17,310
                 tokens. FAILS if this reader's serialisation, tokenizer, or
                 fragment maths differs from T.0's in any respect.
  G2 live        Require the HEAD measurement to be self-consistent: the four
                 fragments must rebuild the wire object byte-for-byte.

G1 is the load-bearing one: a reader that cannot reproduce the published number
from the published input is not measuring the same thing.

KNOWN DEFECT IN T.0's ARTIFACT, verified here: token_baseline.json records
registry_blake2b over the WORKING-TREE bytes, which on a core.autocrlf=true
checkout are CRLF. The same commit checked out LF hashes differently, so that
staleness field can raise a false alarm across machines. This producer digests
LF-normalised content instead, and reports both.

Emits: harness/notes/econ/E1_surface_census.json
Usage: python harness/notes/econ/econ_surface_census.py
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT_FP = Path(__file__).resolve().parent / "E1_surface_census.json"

# --- what T.0 published, and where -----------------------------------------
T0_COMMIT = "d92bb4b"                 # receipts/T0.json commit_after
T0_ARTIFACT = "harness/notes/token_baseline.json"
T0_MCP_HTTP_TOKENS = 17310
T0_TOOL_COUNT = 115
T0_METHOD = "tiktoken/cl100k_base (proxy BPE, not Claude's tokenizer)"
REGISTRY_REL = "python/synapse/mcp/_tool_registry.py"


def _tokenizer():
    """Return (method, count_fn). Must equal T.0's method to be comparable.

    T.0 silently falls back to chars/4 when tiktoken is missing. E1 does NOT:
    this leg's whole output is a comparison against a tiktoken-derived number,
    and a silently different unit produces a table that looks right and is not.
    Absent tiktoken this producer raises rather than emitting.
    """
    import tiktoken  # hard requirement - see docstring

    enc = tiktoken.get_encoding("cl100k_base")
    return T0_METHOD, (lambda s: len(enc.encode(s)))


# --- wire serialisation, identical to synapse.mcp.protocol._dumps ------------
try:
    import orjson

    def _wire(obj) -> str:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode("utf-8")

    _WIRE_IMPL = "orjson.dumps(OPT_SORT_KEYS)"
except ImportError:  # pragma: no cover - matches protocol.py's own fallback

    def _wire(obj) -> str:
        return json.dumps(obj, sort_keys=True)

    _WIRE_IMPL = "json.dumps(sort_keys=True)"


def _frag(key: str, value) -> str:
    """The literal wire fragment for one key of a tool object."""
    return _wire(key) + ":" + _wire(value)


def _walk_depths(node, depth=0):
    if isinstance(node, dict):
        yield depth
        for k, v in node.items():
            if k in ("properties", "$defs", "definitions") and isinstance(v, dict):
                for sub in v.values():
                    yield from _walk_depths(sub, depth + 1)
            elif k in ("items", "additionalProperties"):
                if isinstance(v, dict):
                    yield from _walk_depths(v, depth + 1)
                elif isinstance(v, list):
                    for sub in v:
                        yield from _walk_depths(sub, depth + 1)


def _schema_shape(schema: dict) -> dict:
    """Structural metrics for one inputSchema - what makes it heavy."""
    props = schema.get("properties", {}) or {}
    required = schema.get("required", []) or []
    acc = {"enum_fields": 0, "enum_members": 0, "described": 0,
           "nested": 0, "arrays": 0, "desc_chars": 0}

    def _scan(p):
        if not isinstance(p, dict):
            return
        if isinstance(p.get("enum"), list):
            acc["enum_fields"] += 1
            acc["enum_members"] += len(p["enum"])
        d = p.get("description")
        if d:
            acc["described"] += 1
            acc["desc_chars"] += len(d)
        if p.get("type") == "object" or "properties" in p:
            acc["nested"] += 1
            for sub in (p.get("properties") or {}).values():
                _scan(sub)
        if p.get("type") == "array":
            acc["arrays"] += 1
            if isinstance(p.get("items"), dict):
                _scan(p["items"])

    for p in props.values():
        _scan(p)

    depths = list(_walk_depths(schema)) or [0]
    return {
        "property_count": len(props),
        "required_count": len(required),
        "described_property_count": acc["described"],
        "property_description_chars": acc["desc_chars"],
        "enum_field_count": acc["enum_fields"],
        "enum_member_total": acc["enum_members"],
        "nested_object_count": acc["nested"],
        "array_property_count": acc["arrays"],
        "max_depth": max(depths),
        "is_empty_schema": (not props and not required),
    }


def _measure_tools(tools: list[dict], count) -> tuple[list[dict], dict]:
    """Decompose a tool list. Returns (rows, aggregate-fragment totals)."""
    rows = []
    for t in tools:
        name = t["name"]
        desc = t.get("description", "")
        schema = t.get("inputSchema", {})
        ann = t.get("annotations", {})

        obj = _wire(t)
        total_t = count(obj)

        frags = {
            "annotations": _frag("annotations", ann),
            "description": _frag("description", desc),
            "inputSchema": _frag("inputSchema", schema),
            "name": _frag("name", name),
        }
        # G2: the four fragments in sorted-key order must rebuild the wire
        # object byte-for-byte. A fifth key would break this loudly instead of
        # dumping its mass silently into the structural residual.
        rebuilt = "{" + ",".join(frags[k] for k in sorted(frags)) + "}"
        shape_ok = rebuilt == obj

        w = {k: count(v) for k, v in frags.items()}
        struct = total_t - sum(w.values())

        rows.append({
            "name": name,
            "family": name.split("_", 1)[0],
            "total_tokens": total_t,
            "wire": {
                "name_tokens": w["name"],
                "description_tokens": w["description"],
                "schema_tokens": w["inputSchema"],
                "annotations_tokens": w["annotations"],
                "structural_residual_tokens": struct,
            },
            "content": {
                "name_tokens": count(name),
                "description_tokens": count(desc),
                "schema_tokens": count(_wire(schema)),
                "annotations_tokens": count(_wire(ann)),
            },
            "chars": {
                "total": len(obj),
                "description": len(desc),
                "schema": len(_wire(schema)),
            },
            "schema_shape": _schema_shape(schema),
            "flags": {
                "read_only": ann.get("readOnlyHint"),
                "destructive": ann.get("destructiveHint"),
                "idempotent": ann.get("idempotentHint"),
            },
            "four_key_shape_ok": shape_ok,
        })

    rows.sort(key=lambda r: r["total_tokens"], reverse=True)
    totals = {
        k: sum(r["wire"][k] for r in rows)
        for k in ("name_tokens", "description_tokens", "schema_tokens",
                  "annotations_tokens", "structural_residual_tokens")
    }
    return rows, totals


def _historical_tools(commit: str) -> list[dict] | None:
    """Rebuild TOOLS_LIST_CACHE from the registry as committed at `commit`.

    The registry is pure python (json + typing only, optional orjson) with no
    synapse imports by design, so exec-ing the historical blob is side-effect
    free and yields the exact historical wire shape.
    """
    blob = subprocess.run(
        ["git", "show", f"{commit}:{REGISTRY_REL}"],
        capture_output=True, cwd=str(REPO_ROOT),
    ).stdout
    if not blob:
        return None
    ns: dict = {"__name__": "_t0_registry"}
    exec(compile(blob.decode("utf-8"), f"<{commit}:{REGISTRY_REL}>", "exec"), ns)
    return ns.get("TOOLS_LIST_CACHE")


def _pareto(sorted_totals: list[int], fractions=(0.5, 0.8, 0.9)) -> dict:
    grand = sum(sorted_totals)
    out = {"grand_total": grand, "n_tools": len(sorted_totals), "points": {}}
    for f in fractions:
        target = grand * f
        run = 0
        for i, v in enumerate(sorted_totals, 1):
            run += v
            if run >= target:
                out["points"][f"{int(f * 100)}pct"] = {
                    "tools_needed": i,
                    "share_of_tools": round(i / len(sorted_totals), 4),
                    "tokens_covered": run,
                    "share_of_tokens": round(run / grand, 4),
                }
                break
    out["top_n"] = {}
    for n in (5, 10, 20, 24, 30, 50):
        if n <= len(sorted_totals):
            cov = sum(sorted_totals[:n])
            out["top_n"][str(n)] = {"tokens": cov,
                                    "share_of_tokens": round(cov / grand, 4)}
    return out


def _dist(vals: list[int]) -> dict:
    vals = sorted(vals)
    n = len(vals)
    return {
        "n": n, "min": vals[0], "p25": vals[int(n * 0.25)],
        "median": int(statistics.median(vals)),
        "mean": round(statistics.mean(vals), 2),
        "p75": vals[int(n * 0.75)], "p90": vals[int(n * 0.90)],
        "max": vals[-1], "total": sum(vals),
    }


def main() -> int:
    method, count = _tokenizer()

    from synapse.mcp.protocol import jsonrpc_result
    from synapse.mcp.tools import get_tools

    # ================= LIVE (HEAD) ==========================================
    tools = get_tools()
    wire = jsonrpc_result(1, {"tools": tools})
    if isinstance(wire, bytes):
        wire = wire.decode("utf-8")
    surface_tokens = count(wire)

    rows, comp_totals = _measure_tools(tools, count)
    sum_tool_objects = sum(r["total_tokens"] for r in rows)

    # Explain the surface-vs-sum delta instead of asserting it away.
    array_only = _wire({"tools": tools})
    array_tokens = count(array_only)
    framing_tokens = surface_tokens - array_tokens
    concat_effect = array_tokens - sum_tool_objects

    # ================= G1: historical calibration ===========================
    hist_tools = _historical_tools(T0_COMMIT)
    if hist_tools is None:
        g1 = {"ran": False, "reason": f"could not read {REGISTRY_REL} at {T0_COMMIT}"}
    else:
        hist_wire = jsonrpc_result(1, {"tools": hist_tools})
        if isinstance(hist_wire, bytes):
            hist_wire = hist_wire.decode("utf-8")
        hist_tokens = count(hist_wire)
        g1 = {
            "ran": True,
            "commit": T0_COMMIT,
            "expected_tools": T0_TOOL_COUNT,
            "measured_tools": len(hist_tools),
            "tools_match": len(hist_tools) == T0_TOOL_COUNT,
            "expected_tokens": T0_MCP_HTTP_TOKENS,
            "measured_tokens": hist_tokens,
            "tokens_match": hist_tokens == T0_MCP_HTTP_TOKENS,
            "how_this_fails": (
                "Fails if this reader's serialisation (orjson sorted-key compact), "
                "tokenizer (cl100k_base), or entry point differs from T.0's in any "
                "respect. Reproducing 17,310 from T.0's own input is the only "
                "evidence that E1's per-tool numbers decompose the same quantity."
            ),
        }

    g2_ok = all(r["four_key_shape_ok"] for r in rows)
    calibrated = bool(g1.get("tokens_match")) and bool(g1.get("tools_match")) and g2_ok

    # ================= drift vs the governing number ========================
    hist_names = {t["name"] for t in (hist_tools or [])}
    live_names = {t["name"] for t in tools}
    added = sorted(live_names - hist_names)
    removed = sorted(hist_names - live_names)
    by_name = {r["name"]: r for r in rows}

    reg_fp = REPO_ROOT / REGISTRY_REL
    reg_bytes = reg_fp.read_bytes()
    reg_lf = reg_bytes.replace(b"\r\n", b"\n")

    drift = {
        "governing_number": T0_MCP_HTTP_TOKENS,
        "governing_source": f"{T0_ARTIFACT} (stats.surfaces.mcp_http.preload_tokens)",
        "governing_tool_count": T0_TOOL_COUNT,
        "live_number": surface_tokens,
        "live_tool_count": len(tools),
        "token_delta": surface_tokens - T0_MCP_HTTP_TOKENS,
        "tool_delta": len(tools) - T0_TOOL_COUNT,
        "tools_added_since_t0": [
            {"name": n, "total_tokens": by_name[n]["total_tokens"]} for n in added
        ],
        "tools_removed_since_t0": removed,
        "added_token_mass": sum(by_name[n]["total_tokens"] for n in added),
        "commits_touching_registry_since_t0": subprocess.run(
            ["git", "log", "--oneline", f"{T0_COMMIT}..HEAD", "--", REGISTRY_REL],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        ).stdout.strip().splitlines(),
        "registry_blake2b_lf": hashlib.blake2b(reg_lf, digest_size=16).hexdigest(),
        "registry_blake2b_worktree_bytes": hashlib.blake2b(reg_bytes, digest_size=16).hexdigest(),
        "t0_recorded_registry_blake2b": "c0cd3db16c293e38a3f18a35ed51870f",
        "t0_digest_defect": (
            "T.0 hashed working-tree bytes. That digest equals the d92bb4b blob "
            "ONLY when checked out CRLF; this LF checkout of the same commit "
            "hashes 047a5acec5c49bf99cad30c095514c54. The staleness field is "
            "therefore checkout-dependent and can false-alarm across machines. "
            "Content drift here is established independently, by tool count and "
            "by the two named registry commits - not by the digest."
        ),
    }

    # ================= aggregate ============================================
    agg = {
        "n_tools": len(rows),
        "surface_tokens": surface_tokens,
        "sum_of_tool_objects": sum_tool_objects,
        "tools_array_tokens": array_tokens,
        "jsonrpc_framing_tokens": framing_tokens,
        "concatenation_effect_tokens": concat_effect,
        "delta_note": (
            "surface = sum_of_tool_objects + concatenation_effect + framing. "
            "concatenation_effect is NEGATIVE because adjacent objects share BPE "
            "merges across the '},{' seam that independent tokenisation cannot "
            "see. Per-tool totals are therefore very slightly PESSIMISTIC; the "
            "surface total is exact. Both are reported, neither is estimated."
        ),
        "component_totals_wire": comp_totals,
        "component_totals_content": {
            k: sum(r["content"][k] for r in rows)
            for k in ("name_tokens", "description_tokens", "schema_tokens",
                      "annotations_tokens")
        },
        "component_share_of_surface": {
            k: round(v / surface_tokens, 4) for k, v in comp_totals.items()
        },
        "all_four_key_shape_ok": g2_ok,
        "wire_impl": _WIRE_IMPL,
    }

    # ================= distributions ========================================
    distributions = {
        "description_tokens_content": _dist([r["content"]["description_tokens"] for r in rows]),
        "schema_tokens_content": _dist([r["content"]["schema_tokens"] for r in rows]),
        "annotations_tokens_content": _dist([r["content"]["annotations_tokens"] for r in rows]),
        "total_tokens": _dist([r["total_tokens"] for r in rows]),
    }
    bins = [(0, 10), (10, 20), (20, 40), (40, 80), (80, 160), (160, 10 ** 6)]
    distributions["description_histogram"] = [
        {
            "range": f"{lo}-{hi if hi < 10 ** 6 else 'inf'}",
            "count": sum(1 for r in rows if lo <= r["content"]["description_tokens"] < hi),
            "tokens": sum(r["content"]["description_tokens"] for r in rows
                          if lo <= r["content"]["description_tokens"] < hi),
            "examples": [r["name"] for r in rows
                         if lo <= r["content"]["description_tokens"] < hi][:3],
        }
        for lo, hi in bins
    ]

    # ================= pareto ===============================================
    pareto = _pareto([r["total_tokens"] for r in rows])
    pareto["heaviest_25"] = [
        {"name": r["name"], "total_tokens": r["total_tokens"],
         "description_tokens": r["content"]["description_tokens"],
         "schema_tokens": r["content"]["schema_tokens"],
         "annotations_tokens": r["content"]["annotations_tokens"],
         "property_count": r["schema_shape"]["property_count"]}
        for r in rows[:25]
    ]
    pareto["lightest_10"] = [
        {"name": r["name"], "total_tokens": r["total_tokens"]} for r in rows[-10:]
    ]

    # ================= family rollup ========================================
    families: dict[str, dict] = {}
    for r in rows:
        f = families.setdefault(r["family"], {
            "n_tools": 0, "total_tokens": 0, "description_tokens": 0,
            "schema_tokens": 0, "annotations_tokens": 0})
        f["n_tools"] += 1
        f["total_tokens"] += r["total_tokens"]
        for k in ("description_tokens", "schema_tokens", "annotations_tokens"):
            f[k] += r["content"][k]
    for f in families.values():
        f["share_of_surface"] = round(f["total_tokens"] / surface_tokens, 4)
        f["mean_tokens_per_tool"] = round(f["total_tokens"] / f["n_tools"], 1)

    empty_schema = [r["name"] for r in rows if r["schema_shape"]["is_empty_schema"]]

    stats = {
        "calibration": {
            "method": method, "method_matches_t0": method == T0_METHOD,
            "G1_historical": g1,
            "G2_fragment_rebuild": {
                "all_tools_rebuild_exactly": g2_ok,
                "how_this_fails": "Fails if a tool object carries a key other "
                                  "than the four decomposed here.",
            },
            "calibrated": calibrated,
        },
        "drift_vs_governing_number": drift,
        "aggregate": agg,
        "distributions": distributions,
        "pareto": pareto,
        "families": dict(sorted(families.items(), key=lambda kv: -kv[1]["total_tokens"])),
        "empty_schema_tools": {"count": len(empty_schema), "names": empty_schema},
        "tools": rows,
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16).hexdigest()

    out = {
        "schema": "e1_surface_census/v1",
        "producer": "harness/notes/econ/econ_surface_census.py",
        "surface": "mcp_http (synapse.mcp.protocol.jsonrpc_result(1, {'tools': get_tools()}))",
        "stats": stats,
        "blake2b": digest,
    }
    OUT_FP.parent.mkdir(parents=True, exist_ok=True)
    OUT_FP.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[econ_surface_census] wrote {OUT_FP}")
    print(json.dumps({
        "calibration": stats["calibration"],
        "drift": {k: v for k, v in drift.items() if k != "t0_digest_defect"},
        "aggregate": {k: v for k, v in agg.items() if k != "delta_note"},
        "pareto_points": pareto["points"],
        "pareto_top_n": pareto["top_n"],
        "families": {k: (v["n_tools"], v["total_tokens"]) for k, v in stats["families"].items()},
    }, indent=2))

    if not calibrated:
        print("[econ_surface_census] CALIBRATION FAILED - this reader cannot "
              "reproduce T.0's published number from T.0's own input. Do not "
              "quote this artifact.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
