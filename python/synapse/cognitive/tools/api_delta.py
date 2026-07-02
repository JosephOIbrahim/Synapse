"""
H22 API-delta diff engine (task 0.2, deliverable C) — PURE, zero-``hou``.

This module is the hou-free core of ``scripts/h22_api_delta.py``: it takes
already-materialized probe artifacts (symbol tables from
``host/introspect_runtime.build_table()``, node-type catalogs from
``host/introspect_nodetypes.build_catalog()``, live punycode maps) and
computes the drop-day delta report. Living under ``python/synapse/`` means
the stock-3.14 suite exercises every diff path with fixture tables
(``tests/test_h22_api_delta.py``) — no Houdini required.

Report contract (consumed by ``harness/verify/checks.py::check_probe_clean``):

    {"schema": "h22_probe_delta/v1", "baseline_build", "live_build",
     "symbols": {...}, "node_types": {...}, "punycode": {...},
     "unpatched": [...]}

``unpatched`` is the flat triage list; on H21 with the committed baselines it
MUST be empty (the Mode-A identity proof).

Punycode decoding
-----------------
Houdini's ``xn__`` parm-name encoding is RFC 3492 bootstring with two
deviations, discovered against the 27 live-probed pairs in
``harness/notes/verified_usdlux_encodings_21.0.671.json`` (all 27 round-trip):

* delimiter ``_`` instead of ``-`` and prefix ``xn__`` instead of ``xn--``;
* ``initial_n = 1`` instead of 128 (parm names must encode ASCII ``:``,
  which vanilla punycode cannot represent; code point 0 is never valid, so
  the extended range starts at 1).

If H22 changes this variant, the byte-match check in
``host/introspect_nodetypes.py`` fails loudly — it never guesses.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


REPORT_SCHEMA = "h22_probe_delta/v1"

# ---------------------------------------------------------------------------
# Punycode (Houdini xn__ variant) decoding
# ---------------------------------------------------------------------------

_BOOTSTRING_BASE = 36
_TMIN = 1
_TMAX = 26
_SKEW = 38
_DAMP = 700
_INITIAL_BIAS = 72
_INITIAL_N = 1  # Houdini deviation: vanilla RFC 3492 uses 128


def _adapt(delta: int, numpoints: int, firsttime: bool) -> int:
    delta = delta // _DAMP if firsttime else delta // 2
    delta += delta // numpoints
    k = 0
    while delta > ((_BOOTSTRING_BASE - _TMIN) * _TMAX) // 2:
        delta //= _BOOTSTRING_BASE - _TMIN
        k += _BOOTSTRING_BASE
    return k + (((_BOOTSTRING_BASE - _TMIN + 1) * delta) // (delta + _SKEW))


def _digit(ch: str) -> int:
    o = ord(ch)
    if 0x61 <= o <= 0x7A:  # a-z -> 0..25
        return o - 0x61
    if 0x41 <= o <= 0x5A:  # A-Z -> 0..25 (case-insensitive digits)
        return o - 0x41
    if 0x30 <= o <= 0x39:  # 0-9 -> 26..35
        return o - 0x30 + 26
    raise ValueError(f"invalid bootstring digit {ch!r}")


def decode_parm_name(encoded: str) -> str:
    """Decode a Houdini ``xn__`` parm name back to the raw property string.

    ``xn__inputsintensity_i0a`` -> ``inputs:intensity``. Raises ``ValueError``
    on a malformed extension. Non-``xn__`` names are returned unchanged.
    """
    if not encoded.startswith("xn__"):
        return encoded
    body = encoded[4:]
    base, sep, ext = body.rpartition("_")
    if not sep:
        base, ext = "", body
    out = list(base)
    i, n, bias = 0, _INITIAL_N, _INITIAL_BIAS
    pos, first = 0, True
    while pos < len(ext):
        oldi, w, k = i, 1, _BOOTSTRING_BASE
        while True:
            if pos >= len(ext):
                raise ValueError(f"truncated bootstring extension in {encoded!r}")
            d = _digit(ext[pos])
            pos += 1
            i += d * w
            t = _TMIN if k <= bias else (_TMAX if k >= bias + _TMAX else k - bias)
            if d < t:
                break
            w *= _BOOTSTRING_BASE - t
            k += _BOOTSTRING_BASE
        bias = _adapt(i - oldi, len(out) + 1, first)
        first = False
        n += i // (len(out) + 1)
        i %= len(out) + 1
        out.insert(i, chr(n))
        i += 1
    return "".join(out)


_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def alias_from_raw(raw: str) -> str:
    """Derive the friendly alias key from a raw USD property string.

    ``inputs:colorTemperature_control`` -> ``color_temperature_control``;
    ``inputs:shaping:cone:angle`` -> ``shaping_cone_angle``. This is the rule
    that reproduces the alias vocabulary of
    ``harness/notes/verified_usdlux_encodings_21.0.671.json``.
    """
    body = raw[len("inputs:"):] if raw.startswith("inputs:") else raw
    body = body.replace(":", "_")
    return _CAMEL_SPLIT.sub("_", body).lower()


def raw_for_alias(alias: str, usd_attr_names: Mapping[str, str]) -> Optional[str]:
    """Expected raw property for a ``PUNYCODE_PARMS`` alias, or ``None``.

    Resolves through ``USD_ATTR_NAMES`` (the schema-stable side of
    ``synapse.core.usd_punycode``), including the ``*_control`` companions
    (``inputs:<attr-leaf>_control``). This absorbs alias-vocabulary quirks
    such as ``enable_temperature`` -> ``inputs:enableColorTemperature``.
    """
    if alias in usd_attr_names:
        return usd_attr_names[alias]
    if alias.endswith("_control"):
        base = alias[: -len("_control")]
        if base in usd_attr_names:
            return usd_attr_names[base] + "_control"
    return None


# ---------------------------------------------------------------------------
# SYNAPSE call-site index (ranks 33k-symbol noise for triage)
# ---------------------------------------------------------------------------

_CHAIN = re.compile(r"\b(?:hou|pdg|pxr)(?:\.[A-Za-z_][A-Za-z0-9_]*)+")


def build_callsite_index(pkg_root: Path) -> Dict[str, List[str]]:
    """Scan ``*.py`` under ``pkg_root`` for ``hou.``/``pdg.``/``pxr.``
    attribute chains. Returns ``{chain: sorted relative files}``.

    Heuristic by design: dynamically-constructed references (``getattr``
    chains, hscript strings) are invisible — the report says so.
    """
    index: Dict[str, set] = {}
    for py in sorted(pkg_root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = py.relative_to(pkg_root).as_posix()
        for m in _CHAIN.finditer(text):
            index.setdefault(m.group(0), set()).add(rel)
    return {chain: sorted(files) for chain, files in sorted(index.items())}


def symbol_usage(symbol: str, index: Mapping[str, Sequence[str]]) -> List[str]:
    """Files that reference ``symbol`` exactly or through a deeper chain."""
    files: set = set()
    for chain, chain_files in index.items():
        if chain == symbol or chain.startswith(symbol + "."):
            files.update(chain_files)
    return sorted(files)


# ---------------------------------------------------------------------------
# Symbol diff
# ---------------------------------------------------------------------------

def diff_symbols(
    baseline: Iterable[str],
    live: Iterable[str],
    callsite_index: Optional[Mapping[str, Sequence[str]]] = None,
    max_moved_candidates: int = 5,
) -> dict:
    """Diff two introspected symbol tables (lists of dotted symbols)."""
    base_set, live_set = set(baseline), set(live)
    added = sorted(live_set - base_set)
    removed_syms = sorted(base_set - live_set)
    index = callsite_index or {}

    removed = []
    for sym in removed_syms:
        removed.append({"symbol": sym, "used_in": symbol_usage(sym, index)})
    # used-in-SYNAPSE first — that is the triage order.
    removed.sort(key=lambda r: (not r["used_in"], r["symbol"]))

    added_by_leaf: Dict[str, List[str]] = {}
    for sym in added:
        added_by_leaf.setdefault(sym.rsplit(".", 1)[-1], []).append(sym)
    moved = []
    for entry in removed:
        leaf = entry["symbol"].rsplit(".", 1)[-1]
        candidates = added_by_leaf.get(leaf, [])
        if candidates:
            moved.append({
                "removed": entry["symbol"],
                "candidates": candidates[:max_moved_candidates],
            })
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "added": added,
        "removed": removed,
        "moved_candidates": moved,
    }


# ---------------------------------------------------------------------------
# Node-type catalog diff
# ---------------------------------------------------------------------------

def _entries_by_type(catalog: Mapping) -> Dict[str, dict]:
    return {e["type_name"]: e for e in catalog.get("entries", [])}


def _resolved_by_full_name(entry: Mapping) -> Dict[str, dict]:
    return {
        f"{r['category']}/{r['full_name']}": r
        for r in entry.get("resolved", [])
    }


def diff_node_catalogs(baseline: Mapping, live: Mapping) -> dict:
    """Diff two ``verified_nodetype_catalog`` payloads.

    Reports emitted types that stopped resolving, resolved matches that
    vanished, and per-parm renames / template-type changes / default changes
    on matches present in both.
    """
    base_entries, live_entries = _entries_by_type(baseline), _entries_by_type(live)
    missing_types: List[dict] = []
    parm_changes: List[dict] = []

    for type_name, base_entry in base_entries.items():
        live_entry = live_entries.get(type_name)
        if live_entry is None or not live_entry.get("exists"):
            if base_entry.get("exists"):
                missing_types.append({
                    "type_name": type_name,
                    "source_files": base_entry.get("source_files", []),
                })
            continue
        base_resolved = _resolved_by_full_name(base_entry)
        live_resolved = _resolved_by_full_name(live_entry)
        for key, base_match in base_resolved.items():
            live_match = live_resolved.get(key)
            if live_match is None:
                # exact category/full-name match vanished but the emitted
                # type still resolves somewhere -> version bump, not missing.
                parm_changes.append({
                    "type_name": type_name, "match": key,
                    "change": "resolution_moved",
                    "now_resolves": sorted(live_resolved),
                })
                continue
            base_parms = {p[0]: p for p in base_match.get("parms", [])}
            live_parms = {p[0]: p for p in live_match.get("parms", [])}
            for name in sorted(set(base_parms) - set(live_parms)):
                parm_changes.append({
                    "type_name": type_name, "match": key,
                    "change": "parm_removed", "parm": name,
                })
            for name in sorted(set(live_parms) - set(base_parms)):
                parm_changes.append({
                    "type_name": type_name, "match": key,
                    "change": "parm_added", "parm": name,
                })
            for name in sorted(set(base_parms) & set(live_parms)):
                b, l = base_parms[name], live_parms[name]
                if b[1] != l[1]:
                    parm_changes.append({
                        "type_name": type_name, "match": key,
                        "change": "parm_template_type_changed", "parm": name,
                        "before": b[1], "after": l[1],
                    })
                elif b[2] != l[2]:
                    parm_changes.append({
                        "type_name": type_name, "match": key,
                        "change": "parm_default_changed", "parm": name,
                        "before": b[2], "after": l[2],
                    })

    new_types = sorted(
        t for t, e in live_entries.items()
        if e.get("exists") and t not in base_entries
    )
    return {
        "missing_types": missing_types,
        "parm_changes": parm_changes,
        "new_types": new_types,
    }


# ---------------------------------------------------------------------------
# Punycode diff
# ---------------------------------------------------------------------------

def flatten_verified_encodings(verified: Mapping) -> Dict[str, str]:
    """Flatten the curated ``verified_usdlux_encodings_*.json`` sections to a
    single ``{alias: encoded}`` map (tuples contribute their tuple base)."""
    flat: Dict[str, str] = {}
    for section, payload in verified.items():
        if not section.endswith("_verified") or not isinstance(payload, Mapping):
            continue
        for alias, value in payload.items():
            if isinstance(value, str):
                flat[alias] = value
            elif isinstance(value, Mapping) and "tuple_base" in value:
                flat[alias] = value["tuple_base"]
    return flat


def diff_punycode(
    pinned: Mapping[str, str],
    live_raw_map: Mapping[str, str],
    baseline_verified: Mapping[str, str],
    usd_attr_names: Mapping[str, str],
) -> dict:
    """Diff the pinned ``PUNYCODE_PARMS`` against the live re-probe.

    * ``changed``   — probed live under a different encoding -> unpatched.
    * ``vanished``  — H21-probe-verified (value appears in the baseline
      verified JSON) but absent from the live probe -> unpatched.
    * ``unverified_unprobed`` — pinned but never probe-verified and not seen
      live -> informational, NOT unpatched. (Empty today: the six camera
      entries were de-phantomed 2026-07-01 — camera parms are plain camelCase
      and live in ``USD_ATTR_NAMES``, not ``PUNYCODE_PARMS``.)
    * ``new``       — live raw properties with no pinned alias -> info.
    """
    live_by_alias = {alias_from_raw(raw): (raw, enc) for raw, enc in live_raw_map.items()}
    baseline_values = set(baseline_verified.values())

    matches: Dict[str, str] = {}
    changed: List[dict] = []
    vanished: List[dict] = []
    unverified: List[str] = []
    for alias, pinned_enc in pinned.items():
        raw = raw_for_alias(alias, usd_attr_names)
        live_hit = None
        if raw is not None and raw in live_raw_map:
            live_hit = (raw, live_raw_map[raw])
        elif alias in live_by_alias:
            live_hit = live_by_alias[alias]
        if live_hit is not None:
            live_raw, live_enc = live_hit
            if live_enc == pinned_enc:
                matches[alias] = pinned_enc
            else:
                changed.append({
                    "alias": alias, "raw": live_raw,
                    "pinned": pinned_enc, "live": live_enc,
                })
        elif pinned_enc in baseline_values:
            vanished.append({"alias": alias, "pinned": pinned_enc})
        else:
            unverified.append(alias)

    pinned_values = set(pinned.values())
    new = sorted(
        raw for raw, enc in live_raw_map.items()
        if enc not in pinned_values and alias_from_raw(raw) not in pinned
    )
    return {
        "matches": len(matches),
        "changed": changed,
        "vanished": vanished,
        "unverified_unprobed": sorted(unverified),
        "new": new,
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def flatten_unpatched(symbols: Mapping, node_types: Mapping, punycode: Mapping) -> List[dict]:
    """The flat triage list ``check_probe_clean`` counts. Empty on an
    identity (H21 vs H21) run."""
    unpatched: List[dict] = []
    for entry in symbols.get("removed", []):
        if entry["used_in"]:
            unpatched.append({
                "kind": "symbol_removed_used",
                "symbol": entry["symbol"],
                "used_in": entry["used_in"],
            })
    for entry in node_types.get("missing_types", []):
        unpatched.append({"kind": "node_type_missing", **entry})
    for entry in node_types.get("parm_changes", []):
        unpatched.append({"kind": entry["change"], **{k: v for k, v in entry.items() if k != "change"}})
    for entry in punycode.get("changed", []):
        unpatched.append({"kind": "punycode_changed", **entry})
    for entry in punycode.get("vanished", []):
        unpatched.append({"kind": "punycode_vanished", **entry})
    return unpatched


def build_delta(
    baseline_build: str,
    live_build: str,
    symbols: Mapping,
    node_types: Mapping,
    punycode: Mapping,
) -> dict:
    return {
        "schema": REPORT_SCHEMA,
        "baseline_build": baseline_build,
        "live_build": live_build,
        "symbols": dict(symbols),
        "node_types": dict(node_types),
        "punycode": dict(punycode),
        "unpatched": flatten_unpatched(symbols, node_types, punycode),
    }


def proposed_punycode_block(
    pinned: Mapping[str, str],
    live_raw_map: Mapping[str, str],
    usd_attr_names: Mapping[str, str],
) -> str:
    """Ready-to-paste ``PUNYCODE_PARMS`` body from the live probe, keeping the
    pinned alias vocabulary/order. Unresolved aliases become comments — the
    human decides (probe truth > pinned constants, but a human pastes it)."""
    live_by_alias = {alias_from_raw(raw): enc for raw, enc in live_raw_map.items()}
    lines = ["PUNYCODE_PARMS: Dict[str, str] = {"]
    for alias, pinned_enc in pinned.items():
        raw = raw_for_alias(alias, usd_attr_names)
        enc = live_raw_map.get(raw) if raw is not None else None
        if enc is None:
            enc = live_by_alias.get(alias)
        if enc is not None:
            lines.append(f'    "{alias}": "{enc}",')
        else:
            lines.append(f'    # UNRESOLVED by live probe: "{alias}" (pinned: "{pinned_enc}")')
    extra = sorted(
        (alias, enc) for alias, enc in live_by_alias.items() if alias not in pinned
    )
    if extra:
        lines.append("    # --- newly probed, not in the pinned registry ---")
        for alias, enc in extra:
            lines.append(f'    "{alias}": "{enc}",')
    lines.append("}")
    return "\n".join(lines)


def render_markdown(report: Mapping, proposed_block: str = "") -> str:
    """The human triage doc (``.claude/probe_delta.md``), grouped by consumer."""
    sym, nt, pc = report["symbols"], report["node_types"], report["punycode"]
    unpatched = report["unpatched"]
    lines = [
        "# H22 API-delta triage",
        "",
        f"Baseline build: `{report['baseline_build']}` -> live build: `{report['live_build']}`",
        f"Unpatched drift items: **{len(unpatched)}**"
        + (" — identity-clean." if not unpatched else " — triage below, probe truth > pinned constants."),
        "",
        "## Consumer: scout symbol table (`h*_symbol_table.json`)",
        "",
        f"- added: {sym['added_count']} symbols; removed: {sym['removed_count']}",
        f"- removed AND referenced in SYNAPSE call-sites: "
        f"{sum(1 for r in sym['removed'] if r['used_in'])} (triage first)",
    ]
    for entry in sym["removed"]:
        if entry["used_in"]:
            lines.append(f"  - `{entry['symbol']}` used in: {', '.join(entry['used_in'][:4])}")
    if sym["moved_candidates"]:
        lines.append("- moved candidates (leaf reappears elsewhere — heuristic, human-triaged):")
        for m in sym["moved_candidates"]:
            lines.append(f"  - `{m['removed']}` -> {', '.join('`%s`' % c for c in m['candidates'])}")
    lines += [
        "- action on real drift: regenerate the per-major symbol table "
        "(`hython host/introspect_runtime.py`) and commit; scout's stamp check does the rest.",
        "- caveat: call-site ranking is a static grep — getattr chains and "
        "hscript strings are invisible to it.",
        "",
        "## Consumer: usd_punycode (`synapse/core/usd_punycode.py`)",
        "",
        f"- matches: {pc['matches']}; changed: {len(pc['changed'])}; "
        f"vanished: {len(pc['vanished'])}; new: {len(pc['new'])}",
    ]
    for c in pc["changed"]:
        lines.append(f"  - CHANGED `{c['alias']}`: `{c['pinned']}` -> `{c['live']}`")
    for v in pc["vanished"]:
        lines.append(f"  - VANISHED `{v['alias']}` (was `{v['pinned']}`)")
    if pc["unverified_unprobed"]:
        lines.append(
            "- pinned-but-never-verified, not seen live: "
            + ", ".join(f"`{a}`" for a in pc["unverified_unprobed"])
        )
    lines += [
        "- action on real drift: paste the proposed block below into "
        "`PUNYCODE_PARMS`; update `tests/test_usd_punycode_single_source.py` + "
        "`tests/test_corpus_encoding_conformance.py` in the SAME commit (lockstep rule).",
        "",
        "## Consumer: recipes / handlers (emitted node types)",
        "",
        f"- missing types: {len(nt['missing_types'])}; parm-level changes: "
        f"{len(nt['parm_changes'])}; new types: {len(nt['new_types'])}",
    ]
    for m in nt["missing_types"]:
        lines.append(f"  - MISSING `{m['type_name']}` emitted by: {', '.join(m['source_files'][:4])}")
    for p in nt["parm_changes"][:40]:
        detail = {k: v for k, v in p.items() if k not in ("type_name", "match")}
        lines.append(f"  - `{p['type_name']}` [{p['match']}]: {detail}")
    if len(nt["parm_changes"]) > 40:
        lines.append(f"  - … {len(nt['parm_changes']) - 40} more in probe_delta.json")
    lines += [
        "",
        "## Consumer: rag corpus",
        "",
        "- any changed/vanished encoding above must be scrubbed from `rag/` in "
        "the same pass — `tests/test_corpus_encoding_conformance.py` is the "
        "guard against phantom re-teaching.",
        "- new H22 symbols/node types seed `rag/skills/houdini22-reference/` "
        "(post-drop item, see the release plan §3).",
    ]
    if proposed_block:
        lines += ["", "## Proposed PUNYCODE_PARMS (probe-generated)", "", "```python",
                  proposed_block, "```"]
    lines.append("")
    return "\n".join(lines)
