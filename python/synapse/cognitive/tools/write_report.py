"""Cognitive tool: write_report — pure-Python local file write (the harness write-path).

Writing a report/ledger/provenance file to a local directory is pure file I/O: it
touches no ``hou`` API, so it must NOT be marshaled onto Houdini's main thread. Today
reports get written by shipping a Python snippet through ``houdini_execute_python``,
which wraps the whole script in ``run_on_main`` + an undo group and hops to
``hdefereval`` — so a modal dialog or an in-progress cook on the main thread blocks the
write until the 30s timeout fires and then *fails*. This tool runs on the calling
(daemon / WS-handler) thread directly and cannot be blocked that way.

Zero ``hou`` imports — enforced by ``tests/test_cognitive_boundary.py``. Writes are
confined under a caller-provided base directory (no traversal, no absolute escape),
committed **atomically** (tmp + fsync + ``os.replace``), and — Phase 0a — optionally
**generationally backed up** (``<name>.bak.1..N`` before an overwrite) and **binary**
(base64 content). This is the durable write-path for the harness Ledger / provenance
(§2 durability + MEM-2 + the DR finding: a corrupting crash must not destroy the only copy).
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

WRITE_REPORT_SCHEMA: Dict[str, Any] = {
    "description": (
        "Write a UTF-8 text (or base64 binary) report/file to a confined local reports "
        "directory. Pure local file I/O — does not touch the Houdini scene, and is safe "
        "to call while Houdini is mid-cook or showing a modal dialog (it never waits on "
        "the main thread). Atomic (tmp + os.replace); optional generational backups. The "
        "path is confined under the reports base directory; '..' traversal and absolute "
        "paths are rejected."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relative_path": {
                "type": "string",
                "description": "Destination path under the reports base dir "
                               "(e.g. 'audit/report.md'). No '..', no absolute paths.",
            },
            "content": {
                "type": "string",
                "description": "UTF-8 text to write (or base64-encoded bytes when binary=true).",
            },
            "overwrite": {"type": "boolean", "default": True},
            "backups": {
                "type": "integer",
                "default": 0,
                "description": "Keep up to N generational backups (<name>.bak.1..N) of the "
                               "prior file before overwriting. 0 = no backup.",
            },
            "binary": {
                "type": "boolean",
                "default": False,
                "description": "If true, `content` is base64-encoded bytes, written verbatim.",
            },
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


def _rotate_backups(target: Path, keep: int) -> str:
    """Snapshot the existing file before an overwrite: current content -> <name>.bak.1,
    shifting older generations down (.bak.1 -> .bak.2 ...) and dropping anything beyond
    ``keep``. Snapshot is a copy (target stays put for the atomic replace). Returns the
    newest backup path."""
    def bak(i: int) -> Path:
        return target.with_name(f"{target.name}.bak.{i}")

    # Shift existing generations down; the oldest beyond `keep` is overwritten/dropped.
    for i in range(keep - 1, 0, -1):
        src, dst = bak(i), bak(i + 1)
        if src.exists():
            os.replace(str(src), str(dst))
    shutil.copy2(str(target), str(bak(1)))
    return str(bak(1))


def write_report(
    relative_path: str,
    content: str,
    *,
    overwrite: bool = True,
    base_dir: Optional[str] = None,
    backups: int = 0,
    binary: bool = False,
) -> Dict[str, Any]:
    """Atomically write ``content`` to ``base_dir/relative_path``.

    Atomic (tmp + fsync + os.replace). When ``backups > 0`` and the target exists, the
    prior content is rotated into ``<name>.bak.1..N`` first. When ``binary`` is true,
    ``content`` is base64-decoded and written as bytes.

    Returns a JSON-serializable dict describing the write. Raises :class:`ReportPathError`
    on a path that escapes ``base_dir``.
    """
    if base_dir is None:
        raise ReportPathError("No reports base_dir configured.")
    base = Path(base_dir)
    target = _confine(base, relative_path)
    if target.exists() and not overwrite:
        raise ReportPathError(f"{target} exists and overwrite=False")

    target.parent.mkdir(parents=True, exist_ok=True)

    # Generational backup BEFORE the overwrite (DR: keep a recovery point).
    backed_up: Optional[str] = None
    if backups and backups > 0 and target.exists():
        backed_up = _rotate_backups(target, int(backups))

    # Atomic: write a tmp file in the same dir, fsync, then os.replace.
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        if binary:
            data = base64.b64decode(content)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            bytes_written = len(data)
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            bytes_written = len(content.encode("utf-8"))
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
        "bytes_written": bytes_written,
        "binary": bool(binary),
        "backup": backed_up,
    }
