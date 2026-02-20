#!/usr/bin/env python3
"""
Phase 2: VEX Pattern Extraction

Extracts VEX functions from:
- vex/include/ header files
- Inline wrangle snippets inside expanded HDAs
"""

import json
import os
import re
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

VEX_ROOT = STAGING_ROOT / "vex" / "include"
OTLS_ROOT = STAGING_ROOT / "otls"
INLINECPP_ROOT = STAGING_ROOT / "inlinecpp"
OUTPUT = CORPUS_ROOT / "vex_includes"


def parse_vex_functions(filepath: Path) -> list:
    """Extract function signatures and documentation from a VEX file."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return []

    functions = []

    # Match function definitions with optional preceding comment blocks
    pattern = re.compile(
        r'((?:\s*//[^\n]*\n)*'       # preceding // comments
        r'|(?:/\*.*?\*/\s*)?)'        # or /* */ comments
        r'(\w+(?:\[\])?)\s+'          # return type
        r'(\w+)\s*'                   # function name
        r'\(([^)]*)\)\s*'             # parameters
        r'\{',                        # opening brace
        re.DOTALL,
    )

    skip_keywords = {"if", "for", "while", "foreach", "else", "do", "switch"}

    for match in pattern.finditer(content):
        comment = match.group(1).strip() if match.group(1) else ""
        ret_type = match.group(2)
        func_name = match.group(3)
        params = match.group(4).strip()

        if func_name in skip_keywords:
            continue

        # Clean up comment
        comment = re.sub(r'^//\s*', '', comment, flags=re.MULTILINE)
        comment = re.sub(r'^/\*|\*/$', '', comment).strip()

        functions.append({
            "name": func_name,
            "return_type": ret_type,
            "parameters": params,
            "documentation": comment[:500],
            "source_file": str(filepath.name),
            "source": "SideFXLabs",
        })

    return functions


def extract_inline_vex_patterns(otls_root: Path) -> list:
    """
    Extract VEX wrangle patterns from inside HDA contents.

    Looks for snippet/code files that contain VEX code, capturing
    common patterns like:
    - Attribute read/write (v@P, f@pscale, etc.)
    - chs()/chf()/chi() parameter references
    - Point cloud operations
    - Group operations
    """
    patterns = []

    # Search for files that likely contain VEX snippets
    vex_indicators = ["snippet", "code", "vexcode", "vexpression"]

    for hda_dir in otls_root.glob("*.hda"):
        if not hda_dir.is_dir():
            continue

        for f in hda_dir.rglob("*"):
            if not f.is_file():
                continue

            name_lower = f.name.lower()
            is_vex = any(ind in name_lower for ind in vex_indicators)

            # Also check files with no extension that might be VEX
            if not is_vex and f.suffix == "":
                try:
                    head = f.read_text(errors="replace")[:200]
                    if any(kw in head for kw in ["@P", "v@", "f@", "i@", "s@", "addpoint", "setattrib"]):
                        is_vex = True
                except Exception:
                    continue

            if not is_vex:
                continue

            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue

            if len(content.strip()) < 10:
                continue

            # Extract pattern features
            pattern_entry = {
                "hda": hda_dir.stem,
                "file": f.name,
                "source": "SideFXLabs",
                "length": len(content),
                "features": [],
            }

            # Detect attribute patterns
            attr_reads = set(re.findall(r'[vfis4]@\w+', content))
            if attr_reads:
                pattern_entry["features"].append({
                    "type": "attribute_access",
                    "attributes": sorted(attr_reads),
                })

            # Detect channel reference patterns
            ch_calls = set(re.findall(r'ch[sfi]?\s*\(\s*"[^"]+"\s*\)', content))
            if ch_calls:
                pattern_entry["features"].append({
                    "type": "channel_reference",
                    "calls": sorted(ch_calls)[:20],
                })

            # Detect point cloud operations
            pc_ops = set(re.findall(r'\b(pcopen|pcfilter|pcfind|pcfind_radius|pcclose|pcnumfound)\b', content))
            if pc_ops:
                pattern_entry["features"].append({
                    "type": "point_cloud",
                    "operations": sorted(pc_ops),
                })

            # Detect group operations
            group_ops = set(re.findall(r'\b(ingroup|setgroup|expandgroup|npointsgroup)\b', content))
            if group_ops:
                pattern_entry["features"].append({
                    "type": "group_operations",
                    "operations": sorted(group_ops),
                })

            # Detect intrinsic/detail access
            intrinsic = set(re.findall(r'\b(detail|prim|point|vertex)(?:attrib|intrinsic)?\s*\(', content))
            if intrinsic:
                pattern_entry["features"].append({
                    "type": "geometry_access",
                    "calls": sorted(intrinsic),
                })

            if pattern_entry["features"]:
                # Include a sanitized snippet (first 300 chars, no binary)
                clean = content.strip()[:300]
                if clean.isprintable():
                    pattern_entry["snippet_preview"] = clean
                patterns.append(pattern_entry)

    return patterns


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # 1. Extract VEX include functions
    all_functions = []

    if VEX_ROOT.exists():
        for vex_file in VEX_ROOT.rglob("*"):
            if vex_file.suffix in (".h", ".vfl", ".vex") and vex_file.is_file():
                funcs = parse_vex_functions(vex_file)
                all_functions.extend(funcs)
        print(f"Extracted {len(all_functions)} VEX functions from includes")
    else:
        print(f"WARNING: VEX include directory not found at {VEX_ROOT}")

    # Also check inlinecpp
    if INLINECPP_ROOT.exists():
        for cpp_file in INLINECPP_ROOT.rglob("*"):
            if cpp_file.is_file():
                funcs = parse_vex_functions(cpp_file)
                for f in funcs:
                    f["context"] = "inlinecpp"
                all_functions.extend(funcs)
        print(f"Total with inlinecpp: {len(all_functions)}")

    (OUTPUT / "vex_functions.json").write_text(
        json.dumps(all_functions, indent=2), encoding="utf-8"
    )

    # 2. Extract inline VEX patterns from HDAs
    inline_patterns = []
    if OTLS_ROOT.exists():
        inline_patterns = extract_inline_vex_patterns(OTLS_ROOT)
        print(f"Extracted {len(inline_patterns)} inline VEX pattern entries")
    else:
        print(f"WARNING: otls directory not found at {OTLS_ROOT}")

    (OUTPUT / "inline_patterns.json").write_text(
        json.dumps(inline_patterns, indent=2), encoding="utf-8"
    )

    # Summary
    total_attr_patterns = sum(
        1 for p in inline_patterns
        for f in p.get("features", [])
        if f["type"] == "attribute_access"
    )
    total_ch_patterns = sum(
        1 for p in inline_patterns
        for f in p.get("features", [])
        if f["type"] == "channel_reference"
    )
    print(f"Attribute access patterns: {total_attr_patterns}")
    print(f"Channel reference patterns: {total_ch_patterns}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
