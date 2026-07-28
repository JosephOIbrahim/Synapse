#!/usr/bin/env python3
"""E1 - duplicated schema fragments across the tool surface.

READ-ONLY. Writes one artifact under harness/notes/econ/.

Duplication is the only reduction that costs no capability. A property
definition written 60 times is 60 copies of one idea; collapsing it changes
nothing about when a tool is called or what arguments it accepts. That makes it
categorically different from trimming a description, which risks correctness.

This producer finds four kinds of repetition, and prices each one HONESTLY -
that is, against a real replacement mechanism, not against zero:

  1. property fragments   the whole "name":{...} blob, repeated verbatim
  2. property descriptions the prose inside a property, repeated verbatim
  3. enum bodies          identical value lists
  4. annotations          not duplication - DERIVATION. Every annotations block
                          is recomputable from the tool name and three registry
                          booleans, so its entire mass is removable without a
                          dictionary of any kind.

PRICING. The naive figure - (n-1) x tokens(fragment) - is the ceiling and it is
not achievable, because the replacement is not free. Extraction in JSON Schema
means $defs + {"$ref":"#/$defs/x"}, and a $ref costs real tokens. So each
candidate is priced three ways:

  ceiling_saving   (n-1) x fragment_tokens          - what dedup would save if
                                                      references were free
  ref_saving       n x (fragment - ref) - def_cost  - what $defs/$ref actually
                                                      saves, def_cost included
  strip_saving     for descriptions only: delete outright

RISK, stated because it decides whether ref_saving is real: $ref inside a tool
input_schema is not uniformly supported by MCP clients or by the Anthropic tool
API. This producer reports the number; it does not assert the mechanism is
available. Verifying $ref support is a separate probe and is named as such.

Emits: harness/notes/econ/E1_schema_dupes.json
Usage: python harness/notes/econ/econ_schema_dupes.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "python"))

OUT_FP = Path(__file__).resolve().parent / "E1_schema_dupes.json"

# A representative $ref, used to price extraction against a real mechanism.
REF_TEMPLATE = '{"$ref":"#/$defs/xxxxxxxx"}'

try:
    import orjson

    def _wire(obj) -> str:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode("utf-8")
except ImportError:  # pragma: no cover

    def _wire(obj) -> str:
        return json.dumps(obj, sort_keys=True)


def _tokenizer():
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    return "tiktoken/cl100k_base (proxy BPE, not Claude's tokenizer)", (
        lambda s: len(enc.encode(s)))


def _iter_properties(schema: dict, path: str = ""):
    """Yield (dotted_path, prop_name, prop_schema) for every property, nested included."""
    props = schema.get("properties") or {}
    for name, body in props.items():
        here = f"{path}.{name}" if path else name
        yield here, name, body
        if isinstance(body, dict):
            if isinstance(body.get("properties"), dict):
                yield from _iter_properties(body, here)
            items = body.get("items")
            if isinstance(items, dict) and isinstance(items.get("properties"), dict):
                yield from _iter_properties(items, f"{here}[]")


def main() -> int:
    method, count = _tokenizer()
    from synapse.mcp.tools import get_tools

    tools = get_tools()
    ref_tokens = count(REF_TEMPLATE)

    # ---- collect ----------------------------------------------------------
    frag_index: dict[str, dict] = defaultdict(
        lambda: {"tools": [], "prop_names": set(), "paths": set()})
    desc_index: dict[str, dict] = defaultdict(
        lambda: {"tools": [], "prop_names": set()})
    enum_index: dict[str, dict] = defaultdict(
        lambda: {"tools": [], "prop_names": set(), "members": 0})
    name_only_index: dict[str, set] = defaultdict(set)

    total_property_instances = 0
    total_property_tokens = 0
    total_property_desc_tokens = 0

    for t in tools:
        tname = t["name"]
        schema = t.get("inputSchema") or {}
        for path, pname, body in _iter_properties(schema):
            total_property_instances += 1
            frag = _wire(pname) + ":" + _wire(body)
            total_property_tokens += count(frag)
            e = frag_index[frag]
            e["tools"].append(tname)
            e["prop_names"].add(pname)
            e["paths"].add(path)

            name_only_index[pname].add(tname)

            if isinstance(body, dict):
                d = body.get("description")
                if isinstance(d, str) and d:
                    total_property_desc_tokens += count(d)
                    de = desc_index[d]
                    de["tools"].append(tname)
                    de["prop_names"].add(pname)
                en = body.get("enum")
                if isinstance(en, list) and en:
                    key = _wire(en)
                    ee = enum_index[key]
                    ee["tools"].append(tname)
                    ee["prop_names"].add(pname)
                    ee["members"] = len(en)

    # ---- price ------------------------------------------------------------
    def _price_fragments(index, tok_of_key, kind):
        out = []
        ceiling = 0
        ref_real = 0
        for key, e in index.items():
            n = len(e["tools"])
            if n < 2:
                continue
            ft = tok_of_key(key)
            c = (n - 1) * ft
            # $defs holds one copy; each of n sites becomes a $ref.
            r = n * (ft - ref_tokens) - ft
            ceiling += c
            ref_real += max(r, 0)
            out.append({
                "kind": kind,
                "repeat_count": n,
                "distinct_tools": len(set(e["tools"])),
                "fragment_tokens": ft,
                "ceiling_saving_tokens": c,
                "ref_saving_tokens": r,
                "property_names": sorted(e["prop_names"]),
                "sample_tools": sorted(set(e["tools"]))[:6],
                "fragment": key if len(key) <= 400 else key[:400] + "...",
            })
        out.sort(key=lambda r: -r["ceiling_saving_tokens"])
        return out, ceiling, ref_real

    frags, frag_ceiling, frag_ref = _price_fragments(
        frag_index, lambda k: count(k), "property_fragment")

    descs, desc_ceiling, desc_ref = _price_fragments(
        desc_index, lambda k: count(_wire("description") + ":" + _wire(k)),
        "property_description")
    # descriptions can also simply be deleted - price that separately
    desc_strip = sum(
        len(e["tools"]) * count(_wire("description") + ":" + _wire(k) + ",")
        for k, e in desc_index.items())

    enums, enum_ceiling, enum_ref = _price_fragments(
        enum_index, lambda k: count(_wire("enum") + ":" + k), "enum_body")

    # ---- annotations: derivation, not duplication -------------------------
    ann_tokens = 0
    ann_distinct = set()
    for t in tools:
        ann = t.get("annotations") or {}
        frag = _wire("annotations") + ":" + _wire(ann) + ","
        ann_tokens += count(frag)
        ann_distinct.add(_wire(ann))
    annotations_block = {
        "total_wire_tokens": ann_tokens,
        "distinct_annotation_bodies": len(ann_distinct),
        "n_tools": len(tools),
        "derivable": True,
        "derivation": (
            "title = name.replace('_',' ').replace('houdini ','')"
            ".replace('synapse ','').title(); readOnlyHint/destructiveHint/"
            "idempotentHint are TOOL_DEFS tuple slots 5/6/7; openWorldHint is "
            "the constant False. _tool_registry.py:1543-1552."
        ),
        "note": (
            "Not duplication - derivation. Every byte is recomputable from data "
            "the caller already has, so removal needs no dictionary, no $ref, "
            "and no client support. The mcp_stdio surface already drops it, "
            "which is why stdio measured lower than http at T.0."
        ),
    }

    # ---- shared property NAMES (the 'node_path written 60 times' shape) ----
    shared_names = sorted(
        (
            {"property": p, "tool_count": len(ts), "sample_tools": sorted(ts)[:5]}
            for p, ts in name_only_index.items() if len(ts) >= 5
        ),
        key=lambda r: -r["tool_count"],
    )

    # ---- normalisation potential ------------------------------------------
    # Verbatim dedup underperforms here for a specific, findable reason: the
    # same property name carries MANY different definitions ('node' appears in
    # 40 tools under 6+ distinct bodies). Nothing can dedup what was never
    # written identically. This block prices the prior step - converge each
    # property name on one canonical body FIRST, then dedup - and is explicit
    # that it is NOT free: collapsing 'LOP node path' and 'TOP node path' onto
    # one string removes context the model currently reads.
    by_prop_name: dict[str, list[str]] = defaultdict(list)
    for frag, e in frag_index.items():
        for pname in e["prop_names"]:
            by_prop_name[pname].extend([frag] * len(e["tools"]))

    norm_rows = []
    norm_only = norm_dedup_ceiling = norm_ref_real = 0
    for pname, frags_for_name in by_prop_name.items():
        n = len(frags_for_name)
        if n < 2:
            continue
        toks = [count(f) for f in frags_for_name]
        variants = sorted(set(frags_for_name), key=count)
        if len(variants) < 2 and len(set(toks)) == 1:
            canonical_only = 0          # already uniform - dedup alone covers it
        else:
            canonical_only = sum(toks) - len(toks) * count(variants[0])
        actual = sum(toks)
        canon_tok = count(variants[0])
        ceiling = actual - canon_tok
        ref_real = actual - canon_tok - n * ref_tokens
        norm_only += canonical_only
        norm_dedup_ceiling += ceiling
        norm_ref_real += max(ref_real, 0)
        longest = variants[-1]
        norm_rows.append({
            "property": pname,
            "instances": n,
            "distinct_bodies": len(variants),
            "actual_tokens": actual,
            "canonical_tokens": canon_tok,
            "normalise_only_saving": canonical_only,
            "normalise_then_dedup_ceiling": ceiling,
            "normalise_then_ref_saving": ref_real,
            "canonical_body": variants[0][:200],
            "longest_body": longest[:200],
            "information_lost_tokens": count(longest) - canon_tok,
        })
    norm_rows.sort(key=lambda r: -r["normalise_then_dedup_ceiling"])

    normalisation = {
        "normalise_only_saving_tokens": norm_only,
        "normalise_then_dedup_ceiling_tokens": norm_dedup_ceiling,
        "normalise_then_ref_realistic_tokens": norm_ref_real,
        "distinct_property_names_with_repeats": len(norm_rows),
        "not_free": (
            "Normalisation is NOT capability-neutral the way annotations removal "
            "is. Converging 'LOP node path', 'TOP node path' and 'COP node path' "
            "onto one string deletes the context that currently tells the model "
            "which network the argument belongs to. information_lost_tokens per "
            "row is the size of what is discarded, and is the number to argue "
            "over - not the saving."
        ),
        "top": norm_rows[:20],
    }

    stats = {
        "method": method,
        "surface": "mcp_http get_tools()",
        "n_tools": len(tools),
        "ref_template": REF_TEMPLATE,
        "ref_tokens": ref_tokens,
        "property_totals": {
            "property_instances": total_property_instances,
            "property_fragment_tokens": total_property_tokens,
            "property_description_tokens": total_property_desc_tokens,
            "description_share_of_property_mass": (
                round(total_property_desc_tokens / total_property_tokens, 4)
                if total_property_tokens else None),
        },
        "duplication": {
            "property_fragments": {
                "distinct_repeated": len(frags),
                "ceiling_saving_tokens": frag_ceiling,
                "ref_saving_tokens": frag_ref,
                "top": frags[:30],
            },
            "property_descriptions": {
                "distinct_repeated": len(descs),
                "ceiling_saving_tokens": desc_ceiling,
                "ref_saving_tokens": desc_ref,
                "strip_all_saving_tokens": desc_strip,
                "strip_note": (
                    "strip_all removes EVERY property description, unique ones "
                    "included. It is an upper bound on a lossy edit, not a free "
                    "one: per-argument prose is what stops the model inventing "
                    "argument values. Reported for scale, not recommended."
                ),
                "top": descs[:30],
            },
            "enum_bodies": {
                "distinct_repeated": len(enums),
                "ceiling_saving_tokens": enum_ceiling,
                "ref_saving_tokens": enum_ref,
                "top": enums[:20],
            },
        },
        "annotations_derivable": annotations_block,
        "shared_property_names": shared_names[:40],
        "normalisation_potential": normalisation,
        "free_reduction_summary": {
            "annotations_removal_tokens": ann_tokens,
            "fragment_dedup_ceiling_tokens": frag_ceiling,
            "fragment_dedup_ref_realistic_tokens": frag_ref,
            "combined_ceiling_tokens": ann_tokens + frag_ceiling,
            "capability_lost": "none - no tool description or argument set changes",
            "mechanism_risk": (
                "annotations removal needs no mechanism. $ref extraction DOES: "
                "$ref support in MCP inputSchema / Anthropic tool input_schema "
                "is UNVERIFIED here and must be probed before ref_saving is "
                "counted as bankable."
            ),
        },
    }

    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"),
        digest_size=16).hexdigest()
    out = {
        "schema": "e1_schema_dupes/v1",
        "producer": "harness/notes/econ/econ_schema_dupes.py",
        "stats": stats,
        "blake2b": digest,
    }
    OUT_FP.parent.mkdir(parents=True, exist_ok=True)
    OUT_FP.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                      encoding="utf-8")

    print(f"[econ_schema_dupes] wrote {OUT_FP}")
    print(json.dumps({
        "property_totals": stats["property_totals"],
        "fragments": {k: v for k, v in stats["duplication"]["property_fragments"].items()
                      if k != "top"},
        "descriptions": {k: v for k, v in stats["duplication"]["property_descriptions"].items()
                         if k not in ("top", "strip_note")},
        "enums": {k: v for k, v in stats["duplication"]["enum_bodies"].items() if k != "top"},
        "annotations": {k: v for k, v in annotations_block.items()
                        if k not in ("derivation", "note")},
        "free_reduction_summary": {k: v for k, v in stats["free_reduction_summary"].items()
                                   if k != "mechanism_risk"},
        "top_repeated_fragments": [
            {"prop": f["property_names"], "n": f["repeat_count"],
             "tokens": f["fragment_tokens"], "ceiling": f["ceiling_saving_tokens"]}
            for f in frags[:12]
        ],
        "most_shared_property_names": shared_names[:10],
        "normalisation_potential": {k: v for k, v in normalisation.items()
                                    if k not in ("top", "not_free")},
        "top_normalisation_targets": [
            {"prop": r["property"], "instances": r["instances"],
             "bodies": r["distinct_bodies"], "ceiling": r["normalise_then_dedup_ceiling"],
             "info_lost": r["information_lost_tokens"]}
            for r in normalisation["top"][:8]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
