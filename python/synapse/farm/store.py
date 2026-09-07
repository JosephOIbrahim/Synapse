"""One transactional authority per local journal URI; no connection leaves a call."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import threading
from typing import Callable
import json

from .models import FarmError, MAX_LIST_JOBS, canonical_json

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FarmStore:
    """Short FULL-durability transactions; backend calls never run inside them.

    Every instance for a URI shares admission serialization in-process. SQLite's
    BEGIN IMMEDIATE provides the same atomic request admission across processes.
    Records outlive the service; no age-based eviction can resubmit an old ID.
    The caller must select controller-local disk, outside synced folders/shares.
    """

    def __init__(self, root):
        raw = Path(root)
        if not raw.is_absolute() or str(raw).startswith(("\\\\", "//")) or raw.is_symlink():
            raise FarmError("invalid_journal", "The farm journal needs an absolute folder on local disk.")
        self.root = raw.resolve()
        if str(self.root).startswith(("\\\\", "//")):
            raise FarmError("invalid_journal", "The farm journal cannot live on a network share.")
        if os.name == "nt":
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(str(self.root.anchor)) == 4:
                raise FarmError("invalid_journal", "The farm journal cannot live on a mapped network drive.")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "farm.sqlite3"
        if self.path.is_symlink():
            raise FarmError("invalid_journal", "The farm journal cannot be a symbolic link.")
        key = os.path.normcase(str(self.path))
        with _LOCKS_LOCK:
            self._lock = _LOCKS.setdefault(key, threading.RLock())
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS jobs (request_id TEXT PRIMARY KEY, digest TEXT NOT NULL, created_at TEXT NOT NULL, record TEXT NOT NULL)")

    @contextmanager
    def _connection(self):
        with self._lock:
            conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
            try:
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute("PRAGMA busy_timeout=10000")
                yield conn
            finally:
                conn.close()

    @staticmethod
    def _decode(row):
        return json.loads(row[0]) if row else None

    def get(self, request_id: str) -> dict | None:
        with self._connection() as conn:
            return self._decode(conn.execute("SELECT record FROM jobs WHERE request_id=?", (request_id,)).fetchone())

    def list(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= MAX_LIST_JOBS:
            raise FarmError("invalid_limit", f"Choose a job limit from 1 to {MAX_LIST_JOBS}.")
        with self._connection() as conn:
            return [self._decode(row) for row in conn.execute(
                "SELECT record FROM jobs ORDER BY created_at DESC, request_id DESC LIMIT ?", (limit,))]

    def reserve(self, record: dict) -> tuple[dict, bool]:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                current = self._decode(conn.execute("SELECT record FROM jobs WHERE request_id=?", (record["request_id"],)).fetchone())
                if current:
                    if current["digest"] != record["digest"]:
                        raise FarmError("request_conflict", "This request ID already belongs to a different render plan. Use a new ID for a new render.")
                    conn.commit()
                    return current, False
                conn.execute("INSERT INTO jobs VALUES (?,?,?,?)", (record["request_id"], record["digest"], record["created_at"], canonical_json(record)))
                conn.commit()
                return deepcopy(record), True
            except BaseException:
                conn.rollback()
                raise

    def update(self, request_id: str, change: Callable[[dict], dict | None]) -> dict:
        """Apply a pure record mutation atomically, or leave it untouched."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                current = self._decode(conn.execute("SELECT record FROM jobs WHERE request_id=?", (request_id,)).fetchone())
                if current is None:
                    raise FarmError("job_not_found", "This render request is not in the farm journal.")
                updated = change(deepcopy(current))
                if updated is None:
                    conn.commit()
                    return current
                updated["revision"] = current["revision"] + 1
                updated["updated_at"] = now()
                conn.execute("UPDATE jobs SET record=? WHERE request_id=?", (canonical_json(updated), request_id))
                conn.commit()
                return updated
            except BaseException:
                conn.rollback()
                raise
