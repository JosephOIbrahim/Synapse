#!/usr/bin/env python3
"""
Phase 5: HDA Structural Convention Extraction

Analyzes how SideFX structures HDAs — namespace conventions, versioning,
section inventory, internal node types, input/output counts.
Informs HDA-from-prompt and MCP tool organization.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

OTLS_ROOT = STAGING_ROOT / "otls"
OUTPUT = CORPUS_ROOT / "hda_conventions"


def analyze_hda(hda_dir: Path) -> dict:
    """Analyze the structure of a single expanded HDA."""
    structure = {
        "name": hda_dir.stem,
        "context": "unknown",
        "namespace": "",
        "version": "",
        "sections": [],
        "has_python_module": False,
        "has_help": False,
        "has_guide": False,
        "has_on_created": False,
        "has_on_loaded": False,
        "has_on_updated": False,
        "has_on_deleted": False,
        "has_on_input_changed": False,
        "internal_file_count": 0,
        "total_size_bytes": 0,
    }

    # Parse INDEX__SECTION for metadata
    for idx_file in hda_dir.rglob("INDEX__SECTION"):
        try:
            content = idx_file.read_text(errors="replace")
        except Exception:
            continue

        # Extract operator path
        path_match = re.search(r'(?:oplib:/|Definition\s+)(.+?)[\s\n]', content)
        if path_match:
            op_path = path_match.group(1).strip()
            structure["namespace"] = op_path

            for ctx in ["Sop", "Lop", "Cop2", "Top", "Object", "Driver", "Vop", "Dop"]:
                if f"/{ctx}/" in op_path or f"::{ctx}/" in op_path.replace(" ", ""):
                    structure["context"] = ctx.lower()
                    break

            ver_match = re.search(r"::(\d+\.?\d*)", op_path)
            if ver_match:
                structure["version"] = ver_match.group(1)

    # Inventory all sections/files
    section_names = set()
    for item in hda_dir.rglob("*"):
        if item.is_file():
            name = item.name
            section_names.add(name)
            structure["internal_file_count"] += 1
            try:
                structure["total_size_bytes"] += item.stat().st_size
            except OSError:
                pass

            # Check for specific sections
            nl = name.lower()
            if name == "PythonModule":
                structure["has_python_module"] = True
            elif "Help" in name:
                structure["has_help"] = True
            elif "Guide" in name:
                structure["has_guide"] = True
            elif "OnCreated" in name:
                structure["has_on_created"] = True
            elif "OnLoaded" in name:
                structure["has_on_loaded"] = True
            elif "OnUpdated" in name:
                structure["has_on_updated"] = True
            elif "OnDeleted" in name:
                structure["has_on_deleted"] = True
            elif "OnInputChanged" in name:
                structure["has_on_input_changed"] = True

    structure["sections"] = sorted(section_names)

    return structure


def derive_conventions(all_structures: list) -> dict:
    """Aggregate patterns across all HDAs into convention rules."""
    context_dist = defaultdict(int)
    version_dist = defaultdict(int)
    section_freq = defaultdict(int)
    callback_usage = defaultdict(int)

    for s in all_structures:
        context_dist[s["context"]] += 1
        if s["version"]:
            version_dist[s["version"]] += 1

        for section in s["sections"]:
            section_freq[section] += 1

        for key in ["has_python_module", "has_help", "has_guide",
                     "has_on_created", "has_on_loaded", "has_on_updated",
                     "has_on_deleted", "has_on_input_changed"]:
            if s[key]:
                callback_usage[key.replace("has_", "")] += 1

    total = max(len(all_structures), 1)

    return {
        "total_hdas": len(all_structures),
        "namespace_pattern": "labs::<Context>/<tool_name>::<version>",
        "context_distribution": dict(sorted(context_dist.items(), key=lambda x: -x[1])),
        "version_distribution": dict(sorted(version_dist.items(), key=lambda x: -x[1])),
        "common_sections_top25": dict(
            sorted(section_freq.items(), key=lambda x: -x[1])[:25]
        ),
        "callback_usage": dict(sorted(callback_usage.items(), key=lambda x: -x[1])),
        "percentages": {
            "python_module": round(callback_usage.get("python_module", 0) / total * 100, 1),
            "help": round(callback_usage.get("help", 0) / total * 100, 1),
            "on_created": round(callback_usage.get("on_created", 0) / total * 100, 1),
            "on_loaded": round(callback_usage.get("on_loaded", 0) / total * 100, 1),
            "on_input_changed": round(callback_usage.get("on_input_changed", 0) / total * 100, 1),
        },
        "avg_internal_files": round(
            sum(s["internal_file_count"] for s in all_structures) / total, 1
        ),
        "avg_size_kb": round(
            sum(s["total_size_bytes"] for s in all_structures) / total / 1024, 1
        ),
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if not OTLS_ROOT.exists():
        print(f"ERROR: otls directory not found at {OTLS_ROOT}")
        raise SystemExit(1)

    all_structures = []

    hda_dirs = sorted(d for d in OTLS_ROOT.glob("*.hda") if d.is_dir())
    print(f"Analyzing {len(hda_dirs)} expanded HDAs")

    for hda_dir in hda_dirs:
        structure = analyze_hda(hda_dir)
        all_structures.append(structure)

    # Write per-HDA structures
    (OUTPUT / "hda_structures.json").write_text(
        json.dumps(all_structures, indent=2), encoding="utf-8"
    )

    # Write conventions summary
    conventions = derive_conventions(all_structures)
    (OUTPUT / "conventions_summary.json").write_text(
        json.dumps(conventions, indent=2), encoding="utf-8"
    )

    # Summary
    print(f"Context distribution: {conventions['context_distribution']}")
    print(f"Python module usage: {conventions['percentages']['python_module']}%")
    print(f"Help coverage: {conventions['percentages']['help']}%")
    print(f"Avg internal files per HDA: {conventions['avg_internal_files']}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
