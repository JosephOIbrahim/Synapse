#!/usr/bin/env python3
"""
Phase 1: Parameter Schema Extraction (CRITICAL PATH)

Walks all expanded HDAs in SideFXLabs/otls/ and extracts parameter
definitions from DialogScript files into structured JSON.

This directly addresses SYNAPSE's dominant friction pattern: parameter confusion.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

OTLS_ROOT = STAGING_ROOT / "otls"
OUTPUT = CORPUS_ROOT / "param_schemas"


# ──────────────────────────────────────────────────────────────
# DialogScript Parser
# ──────────────────────────────────────────────────────────────

def parse_dialog_script(filepath: Path) -> dict:
    """
    Parse Houdini DialogScript format into structured parameter data.

    DialogScript is a nested brace-delimited format:
    {
        name    "tool_name"
        label   "Tool Label"
        parmtag { string "..." }
        group {
            name "folder_name"
            label "Folder Label"
            parm {
                name    "param_name"
                label   "Param Label"
                type    float
                default { 1.0 }
                range   { 0! 10 }
                help    "Description"
            }
        }
    }
    """
    try:
        content = filepath.read_text(errors="replace")
    except Exception as e:
        return {"error": str(e), "source_file": str(filepath)}

    schema = {
        "source_file": str(filepath),
        "hda_name": "",
        "operator_label": "",
        "parameters": [],
        "folders": [],
        "raw_param_count": 0,
    }

    # Extract HDA name from path structure
    # Path: otls/tool.hda/namespace/DialogScript
    parts = filepath.relative_to(OTLS_ROOT).parts
    if len(parts) >= 1:
        schema["hda_name"] = parts[0].replace(".hda", "")

    # Extract operator name/label from header
    name_match = re.search(r'^\s*name\s+"([^"]+)"', content, re.MULTILINE)
    if name_match:
        schema["operator_label"] = name_match.group(1)

    # Extract all parm blocks
    # We use a state-machine approach for nested braces
    parameters = _extract_parm_blocks(content)
    schema["parameters"] = parameters
    schema["raw_param_count"] = len(parameters)

    # Extract folder structure
    folders = _extract_folders(content)
    schema["folders"] = folders

    return schema


def _extract_parm_blocks(content: str) -> list:
    """Extract parameter definitions using brace-matching."""
    params = []

    # Find all 'parm {' blocks at any nesting level
    # We need to handle nested braces properly
    parm_starts = [m.start() for m in re.finditer(r'\bparm\s*\{', content)]

    for start in parm_starts:
        # Find matching closing brace
        block = _extract_brace_block(content, start + content[start:].index("{"))
        if block:
            param = _parse_single_parm(block)
            if param and param.get("name"):
                params.append(param)

    return params


def _extract_brace_block(content: str, open_pos: int) -> str | None:
    """Extract content between matched braces starting at open_pos."""
    if content[open_pos] != "{":
        return None

    depth = 0
    i = open_pos
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[open_pos + 1 : i]
        i += 1

    return None  # Unmatched brace


def _parse_single_parm(block: str) -> dict:
    """Parse the contents of a single parm { ... } block."""
    param = {}

    # Name (internal token)
    m = re.search(r'\bname\s+"([^"]+)"', block)
    if m:
        param["name"] = m.group(1)

    # Label (artist-facing)
    m = re.search(r'\blabel\s+"([^"]*)"', block)
    if m:
        param["label"] = m.group(1)

    # Type
    m = re.search(r'\btype\s+(\w+)', block)
    if m:
        param["type"] = m.group(1)

    # Size (for vector params)
    m = re.search(r'\bsize\s+(\d+)', block)
    if m:
        param["size"] = int(m.group(1))

    # Default value(s)
    m = re.search(r'\bdefault\s*\{([^}]*)\}', block)
    if m:
        param["default"] = m.group(1).strip()

    # Range
    m = re.search(r'\brange\s*\{([^}]*)\}', block)
    if m:
        param["range"] = m.group(1).strip()

    # Help string
    m = re.search(r'\bhelp\s+"([^"]*)"', block)
    if m:
        param["help"] = m.group(1)

    # Hide when condition
    m = re.search(r'\bhidewhen\s+"([^"]*)"', block)
    if m:
        param["hidewhen"] = m.group(1)

    # Disable when condition
    m = re.search(r'\bdisablewhen\s+"([^"]*)"', block)
    if m:
        param["disablewhen"] = m.group(1)

    # Menu items
    menu_match = re.search(r'\bmenu\s*\{([^}]*)\}', block)
    if menu_match:
        menu_content = menu_match.group(1)
        items = re.findall(r'"([^"]+)"', menu_content)
        # Menu items come in pairs: token, label, token, label
        if len(items) >= 2:
            param["menu_items"] = [
                {"token": items[i], "label": items[i + 1]}
                for i in range(0, len(items) - 1, 2)
            ]

    # Parm tags (e.g., script_callback, autoscope)
    tags = re.findall(r'\bparmtag\s*\{\s*string\s+"([^"]+)"\s+"([^"]*)"\s*\}', block)
    if tags:
        param["tags"] = {k: v for k, v in tags}

    return param


def _extract_folders(content: str) -> list:
    """Extract folder/tab group structure."""
    folders = []

    for m in re.finditer(r'\bgroup\s*\{', content):
        block = _extract_brace_block(content, m.start() + content[m.start():].index("{"))
        if block:
            name_m = re.search(r'\bname\s+"([^"]+)"', block)
            label_m = re.search(r'\blabel\s+"([^"]*)"', block)
            if name_m:
                folders.append({
                    "name": name_m.group(1),
                    "label": label_m.group(1) if label_m else "",
                })

    return folders


# ──────────────────────────────────────────────────────────────
# Convention Analysis
# ──────────────────────────────────────────────────────────────

def analyze_conventions(all_schemas: list) -> dict:
    """Derive naming conventions from extracted parameters."""
    type_dist = defaultdict(int)
    name_prefixes = defaultdict(int)
    name_suffixes = defaultdict(int)
    folder_names = defaultdict(int)
    default_by_type = defaultdict(lambda: defaultdict(int))
    hidewhen_patterns = defaultdict(int)
    all_names = []

    for schema in all_schemas:
        for folder in schema.get("folders", []):
            folder_names[folder.get("label", folder.get("name", ""))] += 1

        for param in schema.get("parameters", []):
            ptype = param.get("type", "unknown")
            pname = param.get("name", "")
            type_dist[ptype] += 1
            all_names.append(pname)

            # Prefix analysis (use_, enable_, do_, etc.)
            prefix_m = re.match(r'^([a-z]+)_', pname)
            if prefix_m:
                name_prefixes[prefix_m.group(1) + "_*"] += 1

            # Suffix analysis (*_file, *_path, *_color, etc.)
            suffix_m = re.search(r'_([a-z]+)$', pname)
            if suffix_m:
                name_suffixes["*_" + suffix_m.group(1)] += 1

            # Default value distribution
            default = param.get("default", "")
            if default:
                default_by_type[ptype][default] += 1

            # Hidewhen pattern accumulation
            hw = param.get("hidewhen", "")
            if hw:
                # Generalize: replace specific param names with wildcards
                generalized = re.sub(r'\b\w+\b', '*', hw)
                hidewhen_patterns[generalized] += 1

    # Sort by frequency
    conventions = {
        "type_distribution": dict(sorted(type_dist.items(), key=lambda x: -x[1])),
        "name_prefixes_top30": dict(
            sorted(name_prefixes.items(), key=lambda x: -x[1])[:30]
        ),
        "name_suffixes_top30": dict(
            sorted(name_suffixes.items(), key=lambda x: -x[1])[:30]
        ),
        "folder_names_top20": dict(
            sorted(folder_names.items(), key=lambda x: -x[1])[:20]
        ),
        "common_defaults": {
            ptype: dict(sorted(defaults.items(), key=lambda x: -x[1])[:10])
            for ptype, defaults in default_by_type.items()
        },
        "hidewhen_patterns_top10": dict(
            sorted(hidewhen_patterns.items(), key=lambda x: -x[1])[:10]
        ),
        "total_unique_param_names": len(set(all_names)),
        "total_parameters": len(all_names),
    }

    return conventions


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if not OTLS_ROOT.exists():
        print(f"ERROR: otls directory not found at {OTLS_ROOT}")
        print("Run Phase 0 first.")
        raise SystemExit(1)

    all_schemas = []
    errors = []

    hda_dirs = sorted(d for d in OTLS_ROOT.glob("*.hda") if d.is_dir())
    print(f"Found {len(hda_dirs)} expanded HDAs")

    for hda_dir in hda_dirs:
        # Find all DialogScript files within this HDA
        ds_files = list(hda_dir.rglob("DialogScript"))

        for ds_file in ds_files:
            schema = parse_dialog_script(ds_file)
            if "error" in schema:
                errors.append(schema)
                continue
            all_schemas.append(schema)

            # Write individual schema
            safe_name = hda_dir.stem.replace(".", "_")
            out_file = OUTPUT / f"{safe_name}.json"
            out_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    # Write master index
    total_params = sum(len(s["parameters"]) for s in all_schemas)
    index = {
        "total_hdas": len(all_schemas),
        "total_parameters": total_params,
        "errors": len(errors),
        "hdas": [
            {
                "name": s["hda_name"],
                "label": s["operator_label"],
                "param_count": len(s["parameters"]),
                "param_names": [p["name"] for p in s["parameters"]],
                "param_types": list(set(p.get("type", "?") for p in s["parameters"])),
                "folders": [f.get("label", f.get("name", "")) for f in s["folders"]],
            }
            for s in all_schemas
        ],
    }
    (OUTPUT / "_INDEX.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    # Analyze conventions
    conventions = analyze_conventions(all_schemas)
    (OUTPUT / "_CONVENTIONS.json").write_text(
        json.dumps(conventions, indent=2), encoding="utf-8"
    )

    print(f"Extracted {total_params} parameters from {len(all_schemas)} HDAs")
    print(f"Parse errors: {len(errors)}")
    print(f"Top param types: {dict(list(conventions['type_distribution'].items())[:5])}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
