"""RETINA render receipt — the T0 (file-truth) compute seam for the panel.

Pure-python: **zero Qt, zero hou.** The worker calls ``compute_receipt`` on its
background thread — the correct place for the manifest + EXR-header file I/O the
T0 checker performs — and emits the returned perception event to the Review
face. Keeping the compute in this Qt-free module makes it a real CI signal
(``claude_worker`` hard-imports PySide, so a test that imported the worker would
SKIP under stock CPython).

The panel is **read-only, gate-free**: it never calls ``retina.events.emit_verdict``
(that writes the sidecar JSONL — the host/server side's job, §7). Here we only
READ: load the host-exported manifest and compare it against disk, producing the
same versioned perception event ``retina.t0`` emits elsewhere.

Extraction is dual-shaped by construction: the render's ``retina`` block arrives
either at the top level of the direct handler dict (the Qt fallback path) or
nested as JSON inside an MCP ``content`` text block (the MCP path) — mirroring
``ClaudeWorker._track_integrity``'s dual-location dig.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_t0() -> Optional[Callable[..., Dict[str, Any]]]:
    """Import ``retina.t0.check_manifest_against_disk``, adding the repo root to
    ``sys.path`` only if the package isn't already importable — ``retina/`` lives
    at the repo root, one level above the ``python/`` dir that carries
    ``synapse``. Returns the callable, or ``None`` when retina is unavailable
    (the receipt then degrades honestly to ``None``)."""
    try:
        from retina.t0 import check_manifest_against_disk
        return check_manifest_against_disk
    except ImportError:
        # render_receipt.py -> panel -> synapse -> python -> <repo root>
        root = str(Path(__file__).resolve().parents[3])
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from retina.t0 import check_manifest_against_disk
            return check_manifest_against_disk
        except Exception:
            return None


def extract_retina(result: Any) -> Optional[Dict[str, Any]]:
    """Pull the render's ``retina`` block from a tool result.

    Handles both shapes: the direct handler dict (``result["retina"]``, the Qt
    fallback path) and the MCP ``CallToolResult`` (JSON nested inside a
    ``content`` text block, the MCP path). Returns the block dict or ``None``.
    """
    if not isinstance(result, dict):
        return None
    block = result.get("retina")
    if isinstance(block, dict):
        return block
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "text" in item:
                try:
                    parsed = json.loads(item["text"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("retina"), dict):
                    return parsed["retina"]
    return None


def compute_receipt(
    tool_name: str,
    result: Any,
    *,
    now: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Run RETINA T0 for a render tool's result and return the perception event.

    Returns ``None`` — an honest 'no receipt' — for any of: a non-render tool, a
    result with no ``retina`` block, a ``retina`` block whose ``manifest_path``
    is absent or unwritten, a manifest file that is not on disk or unreadable, or
    a retina import failure. It NEVER fabricates a pass, and NEVER writes a
    sidecar (no ``emit_verdict``).
    """
    if "render" not in (tool_name or "").lower():
        return None
    retina = extract_retina(result)
    if not retina:
        return None
    manifest_path = retina.get("manifest_path")
    if not manifest_path or not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    check = _load_t0()
    if check is None:
        return None
    try:
        return check(manifest, now=now or _now_iso())
    except Exception:
        return None
