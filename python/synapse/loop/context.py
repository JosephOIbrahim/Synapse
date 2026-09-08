"""A bounded data view, not a general USD sanitizer or an instruction channel."""
from __future__ import annotations

import math
import re

_PATH = re.compile(r"^/[A-Za-z0-9_./:-]{0,255}$")
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def sanitize_context(value):
    """Drop every field not named here, including arbitrary scene metadata."""
    def safe(text, pattern):
        return isinstance(text, str) and pattern.fullmatch(text) is not None

    frame = value.get("frame")
    result = {"schema": 1, "selection": [], "nodes": [], "recall_refs": []}
    if isinstance(frame, (int, float)) and not isinstance(frame, bool) and math.isfinite(frame):
        result["frame"] = frame
    version = value.get("houdini_build", "")
    if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version):
        result["houdini_build"] = version
    for path in value.get("selection", [])[:32]:
        if safe(path, _PATH):
            result["selection"].append(path)
    for node in value.get("nodes", [])[:64]:
        if isinstance(node, dict) and safe(node.get("path"), _PATH) and safe(node.get("type"), _ID):
            result["nodes"].append({"path": node["path"], "type": node["type"]})
    for ref in value.get("recall_refs", [])[:8]:
        if safe(ref, _ID):
            result["recall_refs"].append(ref)
    return result
