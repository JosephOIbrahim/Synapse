"""BLOCKS canonicalizer -- the ONE source of truth for c2 canonicalization.

Lifted here from ``harness/autoresearch/probes.py`` (commit 1e13629f) so the
product reconciler and the evidence harness cannot drift apart. probes.py now
imports these names rather than defining them; there is exactly one filter
list in the tree and ``tests/test_blocks_reconciler.py`` pins that fact.

Why it matters: a fixture's committed baseline sha256 is only meaningful
against a named canonicalizer. Two copies of the filter list = two silently
different oracles, and the first divergence would read as a reconciler bug.

Pure Python. No ``hou``, no ``pxr``, no I/O.

Canonicalization rules (version c2)
-----------------------------------
1. ``strip_comment_lines``           -- leading '#': headers and tool chatter
2. ``strip_iso_timestamp_lines``     -- session metadata
3. ``strip_anon_identifier_lines``   -- per-process anonymous layer handles
4. ``strip_houdini_node_provenance`` -- HoudiniCreatorNode / HoudiniEditorNodes /
   HoudiniPrimEditorNodes customData: session node IDs, same class as anon:

A change to any rule is a RE-BASELINE EVENT for every fixture in the tree.
Bump ``CANONICALIZER_VERSION`` in the same commit.

Known limitation (VERIFIED-RUNTIME 2026-08-06, build 22.0.368)
-------------------------------------------------------------
c2 does NOT strip ``$HIP``-expanded absolute paths. ``karmarendersettings``
authors ``$HIP/render/<hipname>.<node>.####.exr`` into the composed stage, and
``$HIP`` resolves to the process working directory for an unsaved scene. A
fixture baseline therefore pins the machine and the launch directory it was
cut in. See ``harness/blocks/invariants_m5.py`` (``--hip``), which pins $HIP
rather than pretending the hash is environment-free.
"""

from __future__ import annotations

import re

CANONICALIZER_VERSION = "c2"

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
# c2 (evidence-driven, run solaris_basic_20260805_181026): Houdini embeds
# session node IDs as provenance customData (HoudiniCreatorNode,
# HoudiniEditorNodes, HoudiniPrimEditorNodes). Session state, never scene
# content -- same class as anon:.
_HOUDINI_PROV_RE = re.compile(r"\bHoudini\w*Nodes?\s*=")

C1_RULES = (
    "strip_comment_lines",
    "strip_iso_timestamp_lines",
    "strip_anon_identifier_lines",
    "strip_houdini_node_provenance",
)


def canonicalize_usda(text: str) -> str:
    """c2 canonicalization -- see ``C1_RULES``.

    Trailing whitespace stripped, LF-joined, single trailing newline.
    Deterministic scene content in, deterministic bytes out.

    Args:
        text: A flattened USD stage exported with ``ExportToString()``.

    Returns:
        The canonical text whose sha256 is the fixture baseline.
    """
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if _TS_RE.search(line):
            continue
        if "anon:" in line:
            continue
        if _HOUDINI_PROV_RE.search(line):
            continue
        keep.append(line.rstrip())
    return "\n".join(keep) + "\n"
