#!/usr/bin/env python3
"""
RAG Auto-Sync: Synapse <-> HOUDINI21_RAG_SYSTEM

Syncs reference markdown files from Synapse's rag/skills/houdini21-reference/
to G:\\HOUDINI21_RAG_SYSTEM\\documentation\\ with YAML frontmatter generation.

Usage:
    python scripts/rag_sync.py                 # Dry-run (show what would change)
    python scripts/rag_sync.py --apply         # Actually write files
    python scripts/rag_sync.py --validate      # Validate metadata integrity only
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SYNAPSE_ROOT = Path(__file__).resolve().parent.parent
_RAG_SKILLS = _SYNAPSE_ROOT / "rag" / "skills" / "houdini21-reference"
_METADATA_DIR = _SYNAPSE_ROOT / "rag" / "documentation" / "_metadata"
_SEMANTIC_INDEX = _METADATA_DIR / "semantic_index.json"
_AGENT_MAP = _METADATA_DIR / "agent_relevance_map.json"
_RAG_SYSTEM = Path("G:/HOUDINI21_RAG_SYSTEM/documentation")

# ---------------------------------------------------------------------------
# Category Mapping: filename stem -> destination subdirectory
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    # VEX reference
    "vex_functions": "vex_reference",
    "vex_fundamentals": "vex_reference",
    "vex_attributes": "vex_reference",
    "vex_types": "vex_reference",
    "vex_performance": "vex_reference",
    "vex_patterns": "vex_reference",
    # Solaris / rendering
    "usd_stage_composition": "solaris_reference",
    "karma_rendering_guide": "solaris_reference",
    "materialx_shaders": "solaris_reference",
    "camera_workflows": "solaris_reference",
    "solaris_nodes": "solaris_reference",
    "solaris_parameters": "solaris_reference",
    "lighting": "solaris_reference",
    "rendering": "solaris_reference",
    "karma_aov": "solaris_reference",
    "render_analysis": "solaris_reference",
    "scene_assembly": "solaris_reference",
    "usd_operations": "solaris_reference",
    "cops_compositing": "solaris_reference",
    # SOP / geometry
    "sop_basics": "geometry_reference",
    "common_attributes": "geometry_reference",
    "expressions": "geometry_reference",
    "sop_solver_loops": "geometry_reference",
    "uv_workflows": "geometry_reference",
    "kinefx_rigging": "geometry_reference",
    # FX / simulation
    "pyro_fx": "fx_reference",
    "flip_simulation": "fx_reference",
    "rbd_simulation": "fx_reference",
    "vellum_simulation": "fx_reference",
    "terrain_heightfields": "fx_reference",
    "ocean_fx": "fx_reference",
    "wire_dynamics": "fx_reference",
    # Developer / TD
    "hapi-reference": "hapi",
    "hdk-api": "hdk",
    "hydra-delegates": "api_reference",
    "usd-schema-registration": "api_reference",
    "pxr-pluginpath": "api_reference",
    "pipeline_integration": "api_reference",
    # Pipeline
    "tops_wedging": "tutorials",
    # Troubleshooting
    "common_errors": "troubleshooting",
}

# Agent name mapping for YAML frontmatter (G:\ uses different agent names)
_AGENT_SCORES = {
    "scene_builder": {"Librarian": 0.8, "GraphTracer": 0.6, "VexAuditor": 0.1},
    "parameter_resolver": {"Librarian": 0.9, "GraphTracer": 0.5, "VexAuditor": 0.2},
    "render_agent": {"Librarian": 0.9, "GraphTracer": 0.6, "VexAuditor": 0.2},
    "material_agent": {"Librarian": 0.95, "GraphTracer": 0.5, "VexAuditor": 0.1},
    "usd_agent": {"Librarian": 0.95, "GraphTracer": 0.8, "VexAuditor": 0.2},
    "fx_agent": {"Librarian": 0.8, "GraphTracer": 0.7, "VexAuditor": 0.5},
    "wedge_agent": {"Librarian": 0.7, "GraphTracer": 0.6, "VexAuditor": 0.3},
    "sop_agent": {"Librarian": 0.8, "GraphTracer": 0.5, "VexAuditor": 0.7},
    "assembly_agent": {"Librarian": 0.85, "GraphTracer": 0.7, "VexAuditor": 0.2},
    "camera_agent": {"Librarian": 0.9, "GraphTracer": 0.5, "VexAuditor": 0.1},
    "lighting_agent": {"Librarian": 0.9, "GraphTracer": 0.6, "VexAuditor": 0.1},
    "developer_agent": {"Librarian": 0.85, "GraphTracer": 0.4, "VexAuditor": 0.3},
}


def _extract_title(content: str, filename: str) -> str:
    """Extract title from H1 heading or derive from filename."""
    m = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return filename.replace("-", " ").replace("_", " ").title()


def _generate_frontmatter(
    filename: str,
    content: str,
    topic_data: dict,
    agent_name: str,
    category: str,
) -> str:
    """Generate YAML frontmatter block from metadata."""
    title = _extract_title(content, filename)
    subcategory = filename.replace("-", "_")

    keywords = topic_data.get("keywords", [])
    # Ensure keywords is a YAML list
    kw_str = "[" + ", ".join(keywords) + "]"

    # Agent relevance scores
    scores = _AGENT_SCORES.get(agent_name, {"Librarian": 0.8})

    lines = [
        "---",
        f"title: {title}",
        f"category: {category}",
        f"subcategory: {subcategory}",
        f"keywords: {kw_str}",
        "agent_relevance:",
    ]
    for agent, score in sorted(scores.items()):
        lines.append(f"  {agent}: {score}")

    # Common queries from description (first 4 sentences as questions)
    desc = topic_data.get("description", "")
    summary = topic_data.get("summary", "")
    if summary:
        lines.append("common_queries:")
        lines.append(f'  - "What is {summary.split(":")[0].lower().strip()}?"')
        lines.append(f'  - "How to {summary.split(",")[0].lower().strip()}?"')

    lines.append("prerequisites: []")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


# Explicit overrides where filename stem != topic key
_FILE_TO_TOPIC = {
    "pyro_fx": "pyro_simulation",
    "solaris_nodes": "solaris_node_types",
    "solaris_parameters": "solaris_parameter_names",
    "usd_operations": "usd_stage_operations",
    "lighting": "lighting_setup",
    "rendering": "karma_rendering",
    "expressions": "houdini_expressions",
    "sop_basics": "houdini_sop_basics",
}


def _find_topic_for_file(
    filename: str, index: dict
) -> tuple:
    """Find the semantic_index topic that references this file.

    Returns (topic_key, topic_data) or (None, None).
    """
    stem = filename

    # Explicit override
    if stem in _FILE_TO_TOPIC:
        key = _FILE_TO_TOPIC[stem]
        if key in index:
            return key, index[key]

    # Direct reference_file match
    for key, data in sorted(index.items()):
        ref = data.get("reference_file", "")
        if ref == stem:
            return key, data

    # Fuzzy: topic key contains filename or vice versa
    for key, data in sorted(index.items()):
        if stem in key or key in stem:
            return key, data

    return None, None


def load_metadata():
    """Load semantic index and agent relevance map."""
    with open(_SEMANTIC_INDEX, encoding="utf-8") as f:
        index = json.load(f)
    with open(_AGENT_MAP, encoding="utf-8") as f:
        agent_map = json.load(f)
    return index, agent_map


def validate(index: dict, agent_map: dict) -> list:
    """Validate metadata integrity. Returns list of issues."""
    issues = []

    # Every topic should have an agent mapping
    for topic in sorted(index):
        if topic not in agent_map:
            issues.append(f"MISSING AGENT: topic '{topic}' has no agent mapping")

    # Every agent mapping should have a topic
    for topic in sorted(agent_map):
        if topic not in index:
            issues.append(f"ORPHAN AGENT: agent mapping '{topic}' has no topic in index")

    # Reference files should exist
    for topic, data in sorted(index.items()):
        ref = data.get("reference_file")
        if ref and not (_RAG_SKILLS / f"{ref}.md").exists():
            issues.append(f"BROKEN REF: topic '{topic}' -> {ref}.md not found")

    # Source files should have a topic entry
    for md_file in sorted(_RAG_SKILLS.glob("*.md")):
        stem = md_file.stem
        topic_key, _ = _find_topic_for_file(stem, index)
        if topic_key is None:
            issues.append(f"UNMAPPED FILE: {stem}.md has no topic in semantic_index")

    # Source files should have a category mapping
    for md_file in sorted(_RAG_SKILLS.glob("*.md")):
        stem = md_file.stem
        if stem not in _CATEGORY_MAP:
            issues.append(f"NO CATEGORY: {stem}.md has no category mapping in rag_sync.py")

    return issues


def sync(index: dict, agent_map: dict, dry_run: bool = True) -> dict:
    """Sync source files to destination with frontmatter.

    Returns summary dict with counts.
    """
    created = []
    updated = []
    skipped = []
    errors = []

    source_files = sorted(_RAG_SKILLS.glob("*.md"))

    for src in source_files:
        stem = src.stem
        category = _CATEGORY_MAP.get(stem)
        if not category:
            skipped.append(f"{stem}.md (no category mapping)")
            continue

        # Find topic data
        topic_key, topic_data = _find_topic_for_file(stem, index)
        agent_name = agent_map.get(topic_key, "sop_agent") if topic_key else "sop_agent"

        if topic_data is None:
            topic_data = {
                "summary": _extract_title(src.read_text(encoding="utf-8"), stem),
                "keywords": [],
            }

        # Read source content
        content = src.read_text(encoding="utf-8")

        # Generate frontmatter
        frontmatter = _generate_frontmatter(
            stem, content, topic_data, agent_name, category
        )

        # Determine destination
        dest_dir = _RAG_SYSTEM / category
        dest_file = dest_dir / f"{stem}.md"

        # Check if destination exists and differs
        enriched = frontmatter + content
        if dest_file.exists():
            existing = dest_file.read_text(encoding="utf-8")
            if existing == enriched:
                skipped.append(f"{stem}.md (unchanged)")
                continue
            updated.append(str(dest_file))
        else:
            created.append(str(dest_file))

        if not dry_run:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(enriched, encoding="utf-8")
            except OSError as e:
                errors.append(f"{stem}.md: {e}")

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "source_count": len(source_files),
    }


def main():
    parser = argparse.ArgumentParser(description="RAG Auto-Sync: Synapse <-> HOUDINI21_RAG_SYSTEM")
    parser.add_argument("--apply", action="store_true", help="Actually write files (default: dry-run)")
    parser.add_argument("--validate", action="store_true", help="Validate metadata only")
    args = parser.parse_args()

    # Load metadata
    index, agent_map = load_metadata()

    # Always validate first
    issues = validate(index, agent_map)
    if issues:
        print(f"\n  Validation: {len(issues)} issue(s)")
        for issue in issues:
            print(f"    - {issue}")
        if args.validate:
            return 1
    else:
        print(f"\n  Validation: OK ({len(index)} topics, {len(agent_map)} agent mappings)")

    if args.validate:
        return 0

    # Check destination exists
    if not _RAG_SYSTEM.exists():
        print(f"\n  ERROR: Destination not found: {_RAG_SYSTEM}")
        print("  Is the G: drive mounted?")
        return 1

    # Sync
    dry_run = not args.apply
    mode = "DRY RUN" if dry_run else "APPLYING"
    print(f"\n  Sync mode: {mode}")

    result = sync(index, agent_map, dry_run=dry_run)

    print(f"  Source files: {result['source_count']}")
    if result["created"]:
        print(f"  Would create:" if dry_run else f"  Created:")
        for f in result["created"]:
            print(f"    + {f}")
    if result["updated"]:
        print(f"  Would update:" if dry_run else f"  Updated:")
        for f in result["updated"]:
            print(f"    ~ {f}")
    if result["skipped"]:
        print(f"  Skipped: {len(result['skipped'])}")
    if result["errors"]:
        print(f"  Errors:")
        for e in result["errors"]:
            print(f"    ! {e}")

    total_changes = len(result["created"]) + len(result["updated"])
    if total_changes == 0:
        print("\n  Everything in sync.")
    elif dry_run:
        print(f"\n  {total_changes} file(s) would change. Run with --apply to write.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
