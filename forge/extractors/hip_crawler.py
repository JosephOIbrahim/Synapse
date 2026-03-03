"""
FORGE Hip Crawler -- Discover Houdini example files containing Solaris networks.

Scans $HFS/houdini/help/examples/ for .hip/.hipnc files,
opens each one, checks if /stage exists with children,
and builds a manifest of extraction targets.

Run inside Houdini's Python shell or via hython.

Data structures:
    HipEntry: Metadata for a single discovered .hip file, including path,
        category (parent folder name like "lop", "sop", "dop"), whether it
        contains a /stage network, child node count, and LOP node types found.

    HipManifest: Collection of all discovered HipEntry records with scan
        metadata (timestamp, HFS path, counts). Serializes to
        forge/extraction_data/hip_manifest.json via .to_dict().
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class HipEntry:
    """Metadata for a discovered .hip file."""
    path: str
    filename: str
    category: str          # Parent folder name (e.g., "lop", "sop", "dop")
    has_stage: bool        # Does /stage exist?
    stage_child_count: int # Number of children in /stage
    lop_node_types: List[str]  # Types of LOP nodes found
    file_size_kb: int
    error: Optional[str] = None


@dataclass
class HipManifest:
    """Collection of discovered .hip files."""
    scan_time: str
    hfs_path: str
    total_scanned: int = 0
    solaris_count: int = 0
    entries: List[HipEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "scan_time": self.scan_time,
            "hfs_path": self.hfs_path,
            "total_scanned": self.total_scanned,
            "solaris_count": self.solaris_count,
            "entries": [asdict(e) for e in self.entries],
        }


def crawl_examples(
    output_path: str = "forge/extraction_data/hip_manifest.json",
    examples_subdir: str = "houdini/help/examples",
    include_non_solaris: bool = False,
) -> HipManifest:
    """Crawl Houdini example directory for .hip files with Solaris content.

    Must be run inside Houdini (needs hou module).

    Args:
        output_path: Where to write the manifest JSON.
        examples_subdir: Subdirectory under $HFS to scan.
        include_non_solaris: If True, include .hip files without /stage.

    Returns:
        HipManifest with discovered files.
    """
    import hou

    hfs = hou.expandString("$HFS")
    examples_root = os.path.join(hfs, examples_subdir)

    manifest = HipManifest(
        scan_time=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        hfs_path=hfs,
    )

    if not os.path.isdir(examples_root):
        # Also check alternative locations
        alt_paths = [
            os.path.join(hfs, "houdini", "help", "examples"),
            os.path.join(hfs, "help", "examples"),
            os.path.join(hfs, "houdini", "examples"),
        ]
        for alt in alt_paths:
            if os.path.isdir(alt):
                examples_root = alt
                break
        else:
            print(f"ERROR: No examples directory found under {hfs}")
            return manifest

    print(f"Scanning: {examples_root}")

    # Find all .hip and .hipnc files
    hip_files = []
    for root, dirs, files in os.walk(examples_root):
        for f in files:
            if f.endswith((".hip", ".hipnc")):
                hip_files.append(os.path.join(root, f))

    print(f"Found {len(hip_files)} .hip files to scan")

    for i, hip_path in enumerate(hip_files):
        if (i + 1) % 10 == 0:
            print(f"  Scanning {i+1}/{len(hip_files)}...")

        entry = _scan_hip_file(hip_path, examples_root)
        manifest.total_scanned += 1

        if entry.has_stage and entry.stage_child_count > 0:
            manifest.solaris_count += 1
            manifest.entries.append(entry)
        elif include_non_solaris:
            manifest.entries.append(entry)

    # Sort by category then filename
    manifest.entries.sort(key=lambda e: (e.category, e.filename))

    # Save manifest
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, sort_keys=False)

    print(f"\nCrawl complete:")
    print(f"  Scanned: {manifest.total_scanned}")
    print(f"  With Solaris: {manifest.solaris_count}")
    print(f"  Manifest: {output_path}")

    return manifest


def _scan_hip_file(hip_path: str, examples_root: str) -> HipEntry:
    """Open a .hip file and check for Solaris content."""
    import hou

    filename = os.path.basename(hip_path)
    rel_path = os.path.relpath(hip_path, examples_root)
    category = rel_path.split(os.sep)[0] if os.sep in rel_path else "root"

    try:
        hou.hipFile.load(hip_path, suppress_save_prompt=True, ignore_load_warnings=True)

        stage = hou.node("/stage")
        if stage is None:
            # Check for lopnet anywhere in the scene
            for child in hou.node("/").children():
                if child.type().name() == "lopnet":
                    stage = child
                    break

        has_stage = stage is not None
        children = stage.children() if stage else []
        lop_types = sorted(set(c.type().name() for c in children))

        return HipEntry(
            path=hip_path,
            filename=filename,
            category=category,
            has_stage=has_stage,
            stage_child_count=len(children),
            lop_node_types=lop_types,
            file_size_kb=os.path.getsize(hip_path) // 1024,
        )

    except Exception as e:
        return HipEntry(
            path=hip_path,
            filename=filename,
            category=category,
            has_stage=False,
            stage_child_count=0,
            lop_node_types=[],
            file_size_kb=os.path.getsize(hip_path) // 1024,
            error=str(e)[:200],
        )
