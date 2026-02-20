#!/usr/bin/env python3
"""
Phase 7: RAG Integration & Semantic Index Merge

Converts all extracted corpus data into SYNAPSE RAG-compatible entries
and writes a merge-ready sub-index with manifest.

Current index: ~92 entries
Target: ~860+ entries after merge
"""

import hashlib
import json
import os
from pathlib import Path

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))
INDEX_ROOT = Path(os.environ.get("INDEX_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\semantic_index"))


def stable_id(prefix: str, name: str) -> str:
    """Generate a collision-safe, deterministic ID."""
    h = hashlib.sha256(f"{prefix}:{name}".encode()).hexdigest()[:12]
    return f"labs_{prefix}_{h}"


def load_json(path: Path) -> list | dict:
    """Load JSON file, return empty on failure."""
    if not path.exists():
        return [] if path.suffix == ".json" else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARN: Failed to load {path}: {e}")
        return []


def build_param_entries() -> list:
    """Convert parameter schemas into RAG entries."""
    entries = []
    param_dir = CORPUS_ROOT / "param_schemas"

    if not param_dir.exists():
        print("  SKIP: param_schemas/ not found")
        return entries

    for f in sorted(param_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue

        schema = load_json(f)
        if not schema or not schema.get("parameters"):
            continue

        hda_name = schema.get("hda_name", f.stem)

        entries.append({
            "id": stable_id("param", hda_name),
            "type": "parameter_schema",
            "source": "SideFXLabs",
            "hda_name": hda_name,
            "param_count": len(schema["parameters"]),
            "searchable_text": " ".join(
                f"{p.get('name', '')} {p.get('label', '')} {p.get('type', '')} {p.get('help', '')}"
                for p in schema["parameters"]
            ),
            "content": json.dumps(schema),
        })

    print(f"  Parameter schemas: {len(entries)} entries")
    return entries


def build_vex_entries() -> list:
    """Convert VEX functions into RAG entries."""
    entries = []
    vex_file = CORPUS_ROOT / "vex_includes" / "vex_functions.json"
    functions = load_json(vex_file)

    if not functions:
        print("  SKIP: vex_functions.json not found or empty")
        return entries

    for func in functions:
        name = func.get("name", "")
        if not name:
            continue

        entries.append({
            "id": stable_id("vex", name),
            "type": "vex_function",
            "source": "SideFXLabs",
            "function_name": name,
            "searchable_text": (
                f"{name} {func.get('return_type', '')} "
                f"{func.get('parameters', '')} "
                f"{func.get('documentation', '')}"
            ),
            "content": json.dumps(func),
        })

    # Also add inline pattern entries
    inline_file = CORPUS_ROOT / "vex_includes" / "inline_patterns.json"
    inline_patterns = load_json(inline_file)

    for pattern in inline_patterns:
        hda = pattern.get("hda", "unknown")
        entries.append({
            "id": stable_id("vex_inline", f"{hda}_{pattern.get('file', '')}"),
            "type": "vex_inline_pattern",
            "source": "SideFXLabs",
            "hda": hda,
            "searchable_text": " ".join(
                " ".join(str(v) for v in f.values())
                for f in pattern.get("features", [])
            ),
            "content": json.dumps(pattern),
        })

    print(f"  VEX entries: {len(entries)} (functions + inline patterns)")
    return entries


def build_python_entries() -> list:
    """Convert Python API patterns into RAG entries."""
    entries = []

    # API frequency as a reference doc
    freq_file = CORPUS_ROOT / "python_patterns" / "hou_api_frequency.json"
    freq = load_json(freq_file)
    if freq:
        entries.append({
            "id": stable_id("py", "api_frequency"),
            "type": "api_reference",
            "source": "SideFXLabs",
            "searchable_text": "hou python API usage frequency SideFXLabs",
            "content": json.dumps(freq),
        })

    # Node creation patterns
    nc_file = CORPUS_ROOT / "python_patterns" / "node_creation_patterns.json"
    nc_patterns = load_json(nc_file)
    if nc_patterns:
        entries.append({
            "id": stable_id("py", "node_creation"),
            "type": "python_pattern",
            "source": "SideFXLabs",
            "searchable_text": "createNode node creation python hou " + " ".join(
                p.get("node_type", "") for p in nc_patterns[:50]
            ),
            "content": json.dumps(nc_patterns[:100]),  # Cap at 100
        })

    # Parameter setting patterns
    ps_file = CORPUS_ROOT / "python_patterns" / "parm_setting_patterns.json"
    ps_patterns = load_json(ps_file)
    if ps_patterns:
        entries.append({
            "id": stable_id("py", "parm_setting"),
            "type": "python_pattern",
            "source": "SideFXLabs",
            "searchable_text": "parm set parameter value python hou",
            "content": json.dumps(ps_patterns[:100]),
        })

    # Viewer state patterns
    vs_file = CORPUS_ROOT / "python_patterns" / "viewer_state_patterns.json"
    vs_patterns = load_json(vs_file)
    if vs_patterns:
        entries.append({
            "id": stable_id("py", "viewer_states"),
            "type": "viewer_state_pattern",
            "source": "SideFXLabs",
            "searchable_text": "viewer state interactive tool mouse draw selection",
            "content": json.dumps(vs_patterns),
        })

    print(f"  Python entries: {len(entries)}")
    return entries


def build_intent_entries() -> list:
    """Convert intent pairs into RAG entries."""
    entries = []
    intent_file = CORPUS_ROOT / "intent_pairs" / "intent_pairs.json"
    pairs = load_json(intent_file)

    if not pairs:
        print("  SKIP: intent_pairs.json not found or empty")
        return entries

    for pair in pairs:
        title = pair.get("title", "")
        if not title:
            continue

        entry_type = pair.get("type", "intent_mapping")
        entries.append({
            "id": stable_id("intent", f"{title}_{pair.get('parameter', '')}"),
            "type": entry_type,
            "source": "SideFXLabs",
            "title": title,
            "context": pair.get("context", ""),
            "searchable_text": (
                f"{pair.get('intent', '')} {title} "
                f"{' '.join(pair.get('parameters', []))} "
                f"{pair.get('parameter_doc', '')}"
            ),
            "content": json.dumps(pair),
        })

    print(f"  Intent entries: {len(entries)}")
    return entries


def build_convention_entries() -> list:
    """Convert HDA conventions into RAG entries."""
    entries = []

    conv_file = CORPUS_ROOT / "hda_conventions" / "conventions_summary.json"
    conv = load_json(conv_file)
    if conv:
        entries.append({
            "id": stable_id("conv", "hda_summary"),
            "type": "convention_reference",
            "source": "SideFXLabs",
            "searchable_text": (
                "HDA naming convention namespace version structure "
                "labs SOP LOP TOP callback section"
            ),
            "content": json.dumps(conv),
        })

    param_conv_file = CORPUS_ROOT / "param_schemas" / "_CONVENTIONS.json"
    param_conv = load_json(param_conv_file)
    if param_conv:
        entries.append({
            "id": stable_id("conv", "param_naming"),
            "type": "convention_reference",
            "source": "SideFXLabs",
            "searchable_text": (
                "parameter naming convention prefix suffix type default "
                "toggle enable use file path color resolution"
            ),
            "content": json.dumps(param_conv),
        })

    print(f"  Convention entries: {len(entries)}")
    return entries


def build_pdg_entries() -> list:
    """Convert PDG patterns into RAG entries."""
    entries = []

    top_file = CORPUS_ROOT / "pdg_patterns" / "top_hdas.json"
    top_hdas = load_json(top_file)
    if top_hdas:
        entries.append({
            "id": stable_id("pdg", "top_hdas"),
            "type": "pdg_hda_reference",
            "source": "SideFXLabs",
            "searchable_text": "TOP PDG work item scheduler batch " + " ".join(
                h.get("name", "") for h in top_hdas
            ),
            "content": json.dumps(top_hdas),
        })

    wi_file = CORPUS_ROOT / "pdg_patterns" / "work_item_patterns.json"
    wi = load_json(wi_file)
    if wi and wi.get("attribute_conventions"):
        entries.append({
            "id": stable_id("pdg", "work_item_patterns"),
            "type": "pdg_pattern",
            "source": "SideFXLabs",
            "searchable_text": "PDG work item attribute file tag dependency " + " ".join(
                a.get("attribute", "") for a in wi["attribute_conventions"]
            ),
            "content": json.dumps(wi),
        })

    print(f"  PDG entries: {len(entries)}")
    return entries


def main():
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)

    print("Building RAG entries from extracted corpus...")

    all_entries = []
    all_entries.extend(build_param_entries())
    all_entries.extend(build_vex_entries())
    all_entries.extend(build_python_entries())
    all_entries.extend(build_intent_entries())
    all_entries.extend(build_convention_entries())
    all_entries.extend(build_pdg_entries())

    # Deduplicate by ID
    seen_ids = set()
    deduped = []
    for entry in all_entries:
        eid = entry["id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            deduped.append(entry)
        else:
            print(f"  DEDUP: Skipping duplicate ID {eid}")

    all_entries = deduped

    # Write Labs sub-index
    index_file = INDEX_ROOT / "sidefxlabs_entries.json"
    index_file.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")

    # Write manifest
    type_counts = {}
    for entry in all_entries:
        t = entry["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    manifest = {
        "source": "SideFXLabs",
        "entry_count": len(all_entries),
        "types": dict(sorted(type_counts.items(), key=lambda x: -x[1])),
        "unique_ids": len(seen_ids),
    }

    manifest_file = INDEX_ROOT / "sidefxlabs_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Summary
    print(f"\n{'='*50}")
    print(f"  Total entries: {len(all_entries)}")
    print(f"  Types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    print(f"\n  Index: {index_file}")
    print(f"  Manifest: {manifest_file}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
