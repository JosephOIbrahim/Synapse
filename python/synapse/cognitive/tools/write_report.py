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
    fsync: bool = True,
) -> Dict[str, Any]:
    """Atomically write ``content`` to ``base_dir/relative_path``.

    Atomic (tmp + fsync + os.replace). When ``backups > 0`` and the target exists, the
    prior content is rotated into ``<name>.bak.1..N`` first. When ``binary`` is true,
    ``content`` is base64-decoded and written as bytes.

    ``fsync`` (default True) controls power-loss durability. With ``fsync=True`` the tmp
    file is fsync'd BEFORE the ``os.replace``, so the bytes are on stable storage before
    the final name appears — full durability before this call returns. With ``fsync=False``
    the content is still flushed to the OS and ``os.replace``'d (so the final filename
    exists with complete content and survives a *process* crash), but the fsync is skipped;
    the caller is responsible for committing power-loss durability later via
    :func:`fsync_path`. This split lets a hot path move the ~3.5ms fsync off-thread while
    keeping process-crash durability synchronous.

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

    # Atomic: write a tmp file in the same dir, (optionally) fsync, then os.replace.
    # The fsync inside the ``with`` flushes to stable storage BEFORE the rename; when
    # ``fsync=False`` we only flush to the OS cache (process-crash durable) and defer
    # the stable-storage fsync to a later :func:`fsync_path` on the final target.
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        if binary:
            data = base64.b64decode(content)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                if fsync:
                    os.fsync(fh.fileno())
            bytes_written = len(data)
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                if fsync:
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


def fsync_path(path: str) -> None:
    """Commit a previously-written file to stable storage (power-loss durability).

    Companion to ``write_report(..., fsync=False)``: opens ``path`` and ``os.fsync``'s it,
    flushing the OS page cache to disk so the record survives a power loss / kernel panic.

    Best-effort by construction — a file that was rotated/removed in the meantime
    (``FileNotFoundError`` / delete-pending) or is otherwise inaccessible is ignored: a
    missed fsync only weakens power-loss durability, it never corrupts the already-committed
    content or the live operation.

    On Windows the handle is opened with ``FILE_SHARE_DELETE`` (via ``CreateFileW``) so a
    concurrent FIFO-rotation ``os.unlink`` of this same provenance file is NOT blocked while
    we flush it — a plain ``os.open`` handle there denies deletion of the open file and would
    silently defeat retention. ``GENERIC_WRITE`` is required because ``os.fsync`` maps to
    ``FlushFileBuffers``, which needs write access. POSIX allows unlink-while-open natively,
    so it just uses ``os.open`` (read-only is sufficient for ``fsync`` there).
    """
    fd = _open_for_fsync(path)
    if fd is None:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


if os.name == "nt":  # pragma: no cover - exercised only on Windows
    import ctypes as _ctypes
    import msvcrt as _msvcrt
    from ctypes import wintypes as _wintypes

    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _FILE_SHARE_READ = 0x1
    _FILE_SHARE_WRITE = 0x2
    _FILE_SHARE_DELETE = 0x4
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x80
    _INVALID_HANDLE_VALUE = _ctypes.c_void_p(-1).value

    _CreateFileW = _ctypes.windll.kernel32.CreateFileW
    _CreateFileW.restype = _wintypes.HANDLE
    _CreateFileW.argtypes = [
        _wintypes.LPCWSTR, _wintypes.DWORD, _wintypes.DWORD,
        _ctypes.c_void_p, _wintypes.DWORD, _wintypes.DWORD, _wintypes.HANDLE,
    ]

    def _open_for_fsync(path: str) -> Optional[int]:
        """Open ``path`` share-delete and wrap it in a C fd, or None if unavailable."""
        handle = _CreateFileW(
            os.path.abspath(path),
            _GENERIC_READ | _GENERIC_WRITE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None, _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None,
        )
        if not handle or handle == _INVALID_HANDLE_VALUE:
            return None
        try:
            # open_osfhandle transfers ownership: os.close(fd) closes the handle.
            return _msvcrt.open_osfhandle(handle, os.O_RDWR)
        except OSError:
            _ctypes.windll.kernel32.CloseHandle(handle)
            return None
else:
    def _open_for_fsync(path: str) -> Optional[int]:
        try:
            return os.open(path, os.O_RDONLY)
        except OSError:
            return None
