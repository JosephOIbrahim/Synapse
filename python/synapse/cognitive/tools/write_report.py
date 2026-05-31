"""Cognitive tool: write_report — pure-Python local file write.

Writing a report to a local directory is pure file I/O: it touches no ``hou``
API, so it must NOT be marshaled onto Houdini's main thread. Today reports get
written by shipping a Python snippet through ``houdini_execute_python``, which
wraps the whole script in ``run_on_main`` + an undo group and hops to
``hdefereval`` — so a modal dialog or an in-progress cook on the main thread
blocks the write until the 30s timeout fires and then *fails*. This tool runs on
the calling (daemon / WS-handler) thread directly and cannot be blocked that way.

Zero ``hou`` imports — enforced by ``tests/test_cognitive_boundary.py``. Writes
are confined under a caller-provided base directory (no traversal, no absolute
escape) and committed atomically (tmp + fsync + ``os.replace``).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

WRITE_REPORT_SCHEMA: Dict[str, Any] = {
    "description": (
        "Write a UTF-8 text report/file to a confined local reports directory. "
        "Pure local file I/O — does not touch the Houdini scene, and is safe to "
        "call while Houdini is mid-cook or showing a modal dialog (it never "
        "waits on the main thread). The path is confined under the reports base "
        "directory; '..' traversal and absolute paths are rejected."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relative_path": {
                "type": "string",
                "description": "Destination path under the reports base dir "
                               "(e.g. 'audit/report.md'). No '..', no absolute paths.",
            },
            "content": {"type": "string", "description": "UTF-8 text to write."},
            "overwrite": {"type": "boolean", "default": True},
        },
        "required": ["relative_path", "content"],
    },
}


class ReportPathError(ValueError):
    """The requested path escaped the confined base dir, or was malformed."""


def _confine(base: Path, relative_path: str) -> Path:
    if not relative_path or os.path.isabs(relative_path):
        raise ReportPathError(f"relative_path must be relative, got {relative_path!r}")
    base_resolved = base.resolve()
    candidate = (base_resolved / relative_path).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ReportPathError(
            f"relative_path {relative_path!r} escapes base {base_resolved} (traversal rejected)"
        )
    return candidate


def write_report(
    relative_path: str,
    content: str,
    *,
    overwrite: bool = True,
    base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Atomically write ``content`` to ``base_dir/relative_path``.

    Returns a JSON-serializable dict describing the write. Raises
    :class:`ReportPathError` on a path that escapes ``base_dir``.
    """
    if base_dir is None:
        raise ReportPathError("No reports base_dir configured.")
    base = Path(base_dir)
    target = _confine(base, relative_path)
    if target.exists() and not overwrite:
        raise ReportPathError(f"{target} exists and overwrite=False")

    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic: write a tmp file in the same dir, fsync, then os.replace.
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {
        "ok": True,
        "path": str(target),
        "bytes_written": len(content.encode("utf-8")),
    }
