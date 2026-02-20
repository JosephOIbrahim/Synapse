#!/usr/bin/env python3
"""
Phase 6: PDG/TOP Pattern Extraction

Finds all PDG/TOP-related content in Labs — TOP-context HDAs,
WorkItem patterns, file dependency conventions, scheduler interactions.
Directly feeds PDG Superpowers milestone.
"""

import json
import os
import re
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

OTLS_ROOT = STAGING_ROOT / "otls"
SCRIPTS_ROOT = STAGING_ROOT / "scripts"
OUTPUT = CORPUS_ROOT / "pdg_patterns"

# Keywords indicating PDG/TOP relevance
PDG_KEYWORDS = [
    "pdg", "workitem", "work_item", "topnet", "topnode",
    "scheduler", "pdg_output", "pdg_input", "pdg_tag",
    "pdg_result", "file_tag", "batch", "wedge", "wedging",
]


def scan_for_pdg_content(root: Path) -> list:
    """Scan all files under root for PDG-related content."""
    results = []

    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.stat().st_size > 1_000_000:  # Skip huge files
            continue

        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue

        content_lower = content.lower()
        hits = [kw for kw in PDG_KEYWORDS if kw in content_lower]

        if not hits:
            continue

        results.append({
            "file": str(f.relative_to(root)),
            "size": f.stat().st_size,
            "keywords_found": hits,
            "keyword_count": sum(content_lower.count(kw) for kw in hits),
        })

    return results


def analyze_top_hdas(otls_root: Path) -> list:
    """Find and analyze TOP-context HDAs specifically."""
    top_hdas = []

    for hda_dir in otls_root.glob("*.hda"):
        if not hda_dir.is_dir():
            continue

        # Check INDEX__SECTION for TOP context
        is_top = False
        namespace = ""

        for idx in hda_dir.rglob("INDEX__SECTION"):
            try:
                content = idx.read_text(errors="replace")
                if "/Top/" in content or "::Top/" in content:
                    is_top = True
                    path_match = re.search(r'(?:oplib:/|Definition\s+)(.+?)[\s\n]', content)
                    if path_match:
                        namespace = path_match.group(1).strip()
            except Exception:
                pass

        # Also check if any content mentions PDG heavily
        if not is_top:
            pdg_density = 0
            for f in hda_dir.rglob("*"):
                if f.is_file():
                    try:
                        c = f.read_text(errors="replace").lower()
                        pdg_density += sum(c.count(kw) for kw in PDG_KEYWORDS)
                    except Exception:
                        pass

            if pdg_density > 10:
                is_top = True  # PDG-heavy even if not TOP context

        if not is_top:
            continue

        # Analyze the HDA's PDG patterns
        hda_entry = {
            "name": hda_dir.stem,
            "namespace": namespace,
            "is_top_context": "/Top/" in namespace if namespace else False,
            "patterns": [],
        }

        for f in hda_dir.rglob("*"):
            if not f.is_file():
                continue
            try:
                content = f.read_text(errors="replace")
            except Exception:
                continue

            # Work item attribute patterns
            wi_attrs = set(re.findall(r'@pdg_\w+', content))
            if wi_attrs:
                hda_entry["patterns"].append({
                    "type": "work_item_attributes",
                    "file": f.name,
                    "attributes": sorted(wi_attrs),
                })

            # File tag patterns
            file_tags = set(re.findall(r'file/?\w*(?:tag|result|output)', content, re.IGNORECASE))
            if file_tags:
                hda_entry["patterns"].append({
                    "type": "file_tags",
                    "file": f.name,
                    "tags": sorted(file_tags),
                })

            # Scheduler references
            sched_refs = set(re.findall(r'(?:local|hqueue|deadline|tractor)_?scheduler', content, re.IGNORECASE))
            if sched_refs:
                hda_entry["patterns"].append({
                    "type": "scheduler_reference",
                    "file": f.name,
                    "schedulers": sorted(sched_refs),
                })

            # PDG Python API calls
            pdg_calls = set(re.findall(r'pdg\.\w+', content))
            if pdg_calls:
                hda_entry["patterns"].append({
                    "type": "pdg_api_calls",
                    "file": f.name,
                    "calls": sorted(pdg_calls),
                })

        top_hdas.append(hda_entry)

    return top_hdas


def extract_work_item_patterns(root: Path) -> dict:
    """
    Extract canonical work item data flow patterns.
    Focus on how SideFX bridges PDG work items back to SOPs.
    """
    patterns = {
        "attribute_conventions": [],
        "file_dependency_patterns": [],
        "data_flow_examples": [],
    }

    for f in root.rglob("*"):
        if not f.is_file():
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue

        # @pdg_ attribute patterns
        pdg_attrs = re.findall(r'@pdg_(\w+)', content)
        for attr in set(pdg_attrs):
            patterns["attribute_conventions"].append({
                "attribute": f"@pdg_{attr}",
                "file": str(f.relative_to(root)),
                "count": pdg_attrs.count(attr),
            })

        # File result patterns (how work items reference output files)
        file_patterns = re.findall(
            r'(?:resultData|addResultData|setResultData|outputFile)\s*\([^)]*\)',
            content,
        )
        for fp in file_patterns:
            patterns["file_dependency_patterns"].append({
                "pattern": fp[:200],
                "file": str(f.relative_to(root)),
            })

    # Deduplicate attribute conventions
    seen = set()
    deduped = []
    for p in patterns["attribute_conventions"]:
        if p["attribute"] not in seen:
            seen.add(p["attribute"])
            deduped.append(p)
    patterns["attribute_conventions"] = sorted(deduped, key=lambda x: -x["count"])

    return patterns


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # 1. Broad scan for PDG-related content
    pdg_scan = []
    if OTLS_ROOT.exists():
        pdg_scan.extend(scan_for_pdg_content(OTLS_ROOT))
    if SCRIPTS_ROOT.exists():
        pdg_scan.extend(scan_for_pdg_content(SCRIPTS_ROOT))

    pdg_scan.sort(key=lambda x: -x["keyword_count"])
    (OUTPUT / "pdg_content_scan.json").write_text(
        json.dumps(pdg_scan, indent=2), encoding="utf-8"
    )
    print(f"Found {len(pdg_scan)} files with PDG-related content")

    # 2. Analyze TOP-context HDAs
    top_hdas = []
    if OTLS_ROOT.exists():
        top_hdas = analyze_top_hdas(OTLS_ROOT)
    (OUTPUT / "top_hdas.json").write_text(
        json.dumps(top_hdas, indent=2), encoding="utf-8"
    )
    print(f"Found {len(top_hdas)} TOP/PDG-related HDAs")

    # 3. Extract work item patterns
    wi_patterns = {"attribute_conventions": [], "file_dependency_patterns": [], "data_flow_examples": []}
    if OTLS_ROOT.exists():
        wi_patterns = extract_work_item_patterns(OTLS_ROOT)
    (OUTPUT / "work_item_patterns.json").write_text(
        json.dumps(wi_patterns, indent=2), encoding="utf-8"
    )
    print(f"Work item attribute conventions: {len(wi_patterns['attribute_conventions'])}")
    print(f"File dependency patterns: {len(wi_patterns['file_dependency_patterns'])}")

    # Note about Labs' PDG coverage
    if len(top_hdas) < 5:
        print("\nNOTE: Labs has thin PDG/TOP coverage (SOP-heavy repo).")
        print("For comprehensive PDG patterns, supplement with Houdini docs.")

    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
