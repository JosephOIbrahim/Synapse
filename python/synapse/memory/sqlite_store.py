"""
SQLite-backed Memory Store

Drop-in replacement for MemoryStore that uses SQLite instead of JSONL.
Advantages for multi-artist workflows:
- WAL mode for concurrent readers + serialized writes
- FTS5 full-text search (faster than linear scan)
- ACID transactions for data integrity
- No append-only file corruption risk

Selection: set SYNAPSE_MEMORY_BACKEND=sqlite (default: jsonl)

Schema version: 1
"""

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult,
)

logger = logging.getLogger("synapse.memory.sqlite")

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    summary TEXT DEFAULT '',
    keywords_json TEXT DEFAULT '[]',
    tags_json TEXT DEFAULT '[]',
    hip_file TEXT DEFAULT '',
    hip_version INTEGER DEFAULT 0,
    frame INTEGER,
    frame_range_json TEXT,
    node_paths_json TEXT DEFAULT '[]',
    source TEXT DEFAULT 'user',
    agent_id TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    embedding_json TEXT,
    is_consolidated INTEGER DEFAULT 0,
    consolidated_into TEXT
);

CREATE TABLE IF NOT EXISTS memory_links (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    bidirectional INTEGER DEFAULT 0,
    PRIMARY KEY (source_id, target_id, link_type),
    FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(tier);
CREATE INDEX IF NOT EXISTS idx_links_source ON memory_links(source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON memory_links(target_id);

CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (memory_id, tag),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_keywords (
    memory_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    PRIMARY KEY (memory_id, keyword),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON memory_tags(tag);
CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON memory_keywords(keyword);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    content,
    summary,
    tokenize='porter'
);
"""


class SQLiteMemoryStore:
    """
    SQLite-backed memory storage — same public API as MemoryStore.

    Uses WAL mode for concurrent readers, a threading.Lock for write
    serialization, and FTS5 for fast text search.
    """

    def __init__(self, storage_dir: Path, background_load: bool = True):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = self.storage_dir / "memory.db"
        self._write_lock = threading.Lock()
        self._loaded = threading.Event()
        self._fts_available = False
        self._local = threading.local()  # per-thread connection reuse

        if background_load:
            loader = threading.Thread(
                target=self._init_db,
                daemon=True,
                name="Synapse-SQLiteInit",
            )
            loader.start()
        else:
            self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a per-thread connection (thread-local reuse).

        Connections are cached in threading.local() so each thread reuses
        a single connection instead of creating one per call.  WAL/pragma
        setup runs only on the first call per thread.
        """
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.ProgrammingError:
                # Connection was closed — fall through and create a new one
                pass

        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
        return conn

    def _init_db(self):
        """Initialize schema and FTS table."""
        try:
            conn = self._get_conn()
            conn.executescript(_SCHEMA_SQL)

            # Check schema version
            cur = conn.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            )
            row = cur.fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES ('version', ?)",
                    (str(SCHEMA_VERSION),),
                )
                conn.commit()

            # Try FTS5 (may not be available on all builds)
            try:
                conn.executescript(_FTS_SQL)
                self._fts_available = True
            except sqlite3.OperationalError:
                logger.info("FTS5 not available, using fallback text search")
                self._fts_available = False

            conn.close()
            self._local.conn = None  # clear thread-local after init close
            logger.info(
                "SQLite memory store ready at %s (FTS5=%s)",
                self._db_path,
                self._fts_available,
            )
        except Exception as e:
            logger.error("SQLite init error: %s", e)
        finally:
            self._loaded.set()

    def _wait_loaded(self, timeout: float = 5.0):
        """Block until background init completes."""
        if self._loaded.is_set():
            return
        self._loaded.wait(timeout=timeout)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _memory_to_row(m: Memory) -> dict:
        """Convert Memory to a dict of column values."""
        return {
            "id": m.id,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "content": m.content,
            "memory_type": m.memory_type.value,
            "tier": m.tier.value,
            "summary": m.summary,
            "keywords_json": json.dumps(sorted(m.keywords), sort_keys=True),
            "tags_json": json.dumps(sorted(m.tags), sort_keys=True),
            "hip_file": m.hip_file,
            "hip_version": m.hip_version,
            "frame": m.frame,
            "frame_range_json": (
                json.dumps(list(m.frame_range)) if m.frame_range else None
            ),
            "node_paths_json": json.dumps(m.node_paths, sort_keys=True),
            "source": m.source,
            "agent_id": m.agent_id,
            "confidence": m.confidence,
            "embedding_json": (
                json.dumps(m.embedding) if m.embedding else None
            ),
            "is_consolidated": 1 if m.is_consolidated else 0,
            "consolidated_into": m.consolidated_into,
        }

    @staticmethod
    def _row_to_memory(row: sqlite3.Row, links: List[MemoryLink] = None) -> Memory:
        """Convert a DB row to a Memory object."""
        frame_range_raw = row["frame_range_json"]
        frame_range = tuple(json.loads(frame_range_raw)) if frame_range_raw else None

        embedding_raw = row["embedding_json"]
        embedding = json.loads(embedding_raw) if embedding_raw else None

        return Memory(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            tier=MemoryTier(row["tier"]),
            summary=row["summary"],
            keywords=json.loads(row["keywords_json"]),
            tags=json.loads(row["tags_json"]),
            links=links or [],
            hip_file=row["hip_file"],
            hip_version=row["hip_version"],
            frame=row["frame"],
            frame_range=frame_range,
            node_paths=json.loads(row["node_paths_json"]),
            source=row["source"],
            agent_id=row["agent_id"],
            confidence=row["confidence"],
            embedding=embedding,
            is_consolidated=bool(row["is_consolidated"]),
            consolidated_into=row["consolidated_into"],
        )

    def _load_links(self, conn: sqlite3.Connection, memory_id: str) -> List[MemoryLink]:
        """Load links for a given memory."""
        cur = conn.execute(
            "SELECT target_id, link_type, reason, created_at, bidirectional "
            "FROM memory_links WHERE source_id = ? ORDER BY target_id",
            (memory_id,),
        )
        return [
            MemoryLink(
                target_id=r["target_id"],
                link_type=LinkType(r["link_type"]),
                reason=r["reason"],
                created_at=r["created_at"],
                bidirectional=bool(r["bidirectional"]),
            )
            for r in cur.fetchall()
        ]

    def _save_links(self, conn: sqlite3.Connection, memory: Memory):
        """Save links for a memory (replaces existing)."""
        conn.execute("DELETE FROM memory_links WHERE source_id = ?", (memory.id,))
        for link in memory.links:
            conn.execute(
                "INSERT OR REPLACE INTO memory_links "
                "(source_id, target_id, link_type, reason, created_at, bidirectional) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    memory.id,
                    link.target_id,
                    link.link_type.value,
                    link.reason,
                    link.created_at,
                    1 if link.bidirectional else 0,
                ),
            )

    def _save_tags(self, conn: sqlite3.Connection, memory: Memory):
        """Save tags for a memory (replaces existing)."""
        conn.execute("DELETE FROM memory_tags WHERE memory_id = ?", (memory.id,))
        for tag in sorted(set(memory.tags)):
            conn.execute(
                "INSERT OR REPLACE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                (memory.id, tag),
            )

    def _save_keywords(self, conn: sqlite3.Connection, memory: Memory):
        """Save keywords for a memory (replaces existing)."""
        conn.execute("DELETE FROM memory_keywords WHERE memory_id = ?", (memory.id,))
        for kw in sorted(set(memory.keywords)):
            conn.execute(
                "INSERT OR REPLACE INTO memory_keywords (memory_id, keyword) VALUES (?, ?)",
                (memory.id, kw),
            )

    def _update_fts(self, conn: sqlite3.Connection, memory: Memory, delete_first: bool = False):
        """Update FTS index for a memory."""
        if not self._fts_available:
            return
        if delete_first:
            conn.execute("DELETE FROM memory_fts WHERE id = ?", (memory.id,))
        conn.execute(
            "INSERT INTO memory_fts (id, content, summary) VALUES (?, ?, ?)",
            (memory.id, memory.content, memory.summary),
        )

    # ------------------------------------------------------------------
    # Public API (matches MemoryStore)
    # ------------------------------------------------------------------

    def flush(self):
        """No-op for SQLite (writes are immediate)."""
        pass

    def save(self):
        """No-op for SQLite (writes are immediate via autocommit transactions)."""
        pass

    def add(self, memory: Memory) -> str:
        """Add a memory to the store."""
        self._wait_loaded()
        row = self._memory_to_row(memory)

        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO memories "
                    "(id, created_at, updated_at, content, memory_type, tier, "
                    "summary, keywords_json, tags_json, hip_file, hip_version, "
                    "frame, frame_range_json, node_paths_json, source, agent_id, "
                    "confidence, embedding_json, is_consolidated, consolidated_into) "
                    "VALUES (:id, :created_at, :updated_at, :content, :memory_type, "
                    ":tier, :summary, :keywords_json, :tags_json, :hip_file, "
                    ":hip_version, :frame, :frame_range_json, :node_paths_json, "
                    ":source, :agent_id, :confidence, :embedding_json, "
                    ":is_consolidated, :consolidated_into)",
                    row,
                )
                self._save_links(conn, memory)
                self._save_tags(conn, memory)
                self._save_keywords(conn, memory)
                self._update_fts(conn, memory, delete_first=True)
                conn.commit()
            finally:
                pass  # thread-local conn reused, not closed

        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
            if row is None:
                return None
            links = self._load_links(conn, memory_id)
            return self._row_to_memory(row, links)
        finally:
            pass  # thread-local conn reused, not closed

    def update(self, memory: Memory):
        """Update an existing memory."""
        self._wait_loaded()
        memory.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        row = self._memory_to_row(memory)

        with self._write_lock:
            conn = self._get_conn()
            try:
                # Check exists
                cur = conn.execute(
                    "SELECT id FROM memories WHERE id = ?", (memory.id,)
                )
                if cur.fetchone() is None:
                    return

                conn.execute(
                    "UPDATE memories SET "
                    "created_at=:created_at, updated_at=:updated_at, "
                    "content=:content, memory_type=:memory_type, tier=:tier, "
                    "summary=:summary, keywords_json=:keywords_json, "
                    "tags_json=:tags_json, hip_file=:hip_file, "
                    "hip_version=:hip_version, frame=:frame, "
                    "frame_range_json=:frame_range_json, "
                    "node_paths_json=:node_paths_json, source=:source, "
                    "agent_id=:agent_id, confidence=:confidence, "
                    "embedding_json=:embedding_json, "
                    "is_consolidated=:is_consolidated, "
                    "consolidated_into=:consolidated_into "
                    "WHERE id=:id",
                    row,
                )
                self._save_links(conn, memory)
                self._save_tags(conn, memory)
                self._save_keywords(conn, memory)
                self._update_fts(conn, memory, delete_first=True)
                conn.commit()
            finally:
                pass  # thread-local conn reused, not closed

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        self._wait_loaded()
        with self._write_lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "SELECT id FROM memories WHERE id = ?", (memory_id,)
                )
                if cur.fetchone() is None:
                    return False

                if self._fts_available:
                    conn.execute(
                        "DELETE FROM memory_fts WHERE id = ?", (memory_id,)
                    )
                conn.execute(
                    "DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,)
                )
                conn.execute(
                    "DELETE FROM memory_keywords WHERE memory_id = ?", (memory_id,)
                )
                conn.execute(
                    "DELETE FROM memory_links WHERE source_id = ?", (memory_id,)
                )
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
                return True
            finally:
                pass  # thread-local conn reused, not closed

    def all(self) -> List[Memory]:
        """Get all memories."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM memories ORDER BY id")
            rows = cur.fetchall()
            return [
                self._row_to_memory(r, self._load_links(conn, r["id"]))
                for r in rows
            ]
        finally:
            pass  # thread-local conn reused, not closed

    def count(self) -> int:
        """Get total memory count."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT COUNT(*) as cnt FROM memories")
            return cur.fetchone()["cnt"]
        finally:
            pass  # thread-local conn reused, not closed

    def clear(self):
        """Clear all memories."""
        self._wait_loaded()
        with self._write_lock:
            conn = self._get_conn()
            try:
                if self._fts_available:
                    conn.execute("DELETE FROM memory_fts")
                conn.execute("DELETE FROM memory_tags")
                conn.execute("DELETE FROM memory_keywords")
                conn.execute("DELETE FROM memory_links")
                conn.execute("DELETE FROM memories")
                conn.commit()
            finally:
                pass  # thread-local conn reused, not closed

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """Search memories based on query parameters."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            return self._search_impl(conn, query)
        finally:
            pass  # thread-local conn reused, not closed

    def _search_impl(
        self, conn: sqlite3.Connection, query: MemoryQuery
    ) -> List[MemorySearchResult]:
        """Core search implementation."""
        # Build candidate set via SQL
        conditions = []
        params: list = []

        if query.memory_types:
            placeholders = ",".join("?" for _ in query.memory_types)
            conditions.append(f"m.memory_type IN ({placeholders})")
            params.extend(mt.value for mt in query.memory_types)

        if query.tier:
            conditions.append("m.tier = ?")
            params.append(query.tier.value)

        if query.source:
            conditions.append("m.source = ?")
            params.append(query.source)

        if query.since:
            conditions.append("m.created_at >= ?")
            params.append(query.since)

        if query.until:
            conditions.append("m.created_at <= ?")
            params.append(query.until)

        if not query.include_consolidated:
            conditions.append("m.is_consolidated = 0")

        # Tag filter via join
        if query.tags:
            tag_placeholders = ",".join("?" for _ in query.tags)
            conditions.append(
                f"m.id IN (SELECT memory_id FROM memory_tags WHERE tag IN ({tag_placeholders}))"
            )
            params.extend(query.tags)

        # Keyword filter via join
        if query.keywords:
            kw_placeholders = ",".join("?" for _ in query.keywords)
            conditions.append(
                f"m.id IN (SELECT memory_id FROM memory_keywords WHERE keyword IN ({kw_placeholders}))"
            )
            params.extend(query.keywords)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM memories m WHERE {where_clause}"
        cur = conn.execute(sql, params)
        rows = cur.fetchall()

        # FTS text search for ranking
        fts_ids: set = set()
        if query.text and self._fts_available:
            try:
                # Escape FTS query (basic: wrap each word in quotes)
                words = query.text.strip().split()
                fts_query = " OR ".join(f'"{w}"' for w in words if w)
                if fts_query:
                    fts_cur = conn.execute(
                        "SELECT id FROM memory_fts WHERE memory_fts MATCH ?",
                        (fts_query,),
                    )
                    fts_ids = {r["id"] for r in fts_cur.fetchall()}
            except sqlite3.OperationalError:
                pass  # Malformed FTS query — fall back to LIKE

        # Score candidates (same logic as JSONL store for consistency)
        results = []
        for row in rows:
            score = 0.0
            match_reasons = []

            # Tag scoring
            if query.tags:
                mem_tags = set(json.loads(row["tags_json"]))
                matching_tags = set(query.tags) & mem_tags
                if matching_tags:
                    score += len(matching_tags) * 0.2
                    match_reasons.append(f"tags: {', '.join(sorted(matching_tags))}")

            # Keyword scoring
            if query.keywords:
                mem_kws = set(json.loads(row["keywords_json"]))
                matching_kws = set(query.keywords) & mem_kws
                if matching_kws:
                    score += len(matching_kws) * 0.2
                    match_reasons.append(f"keywords: {', '.join(sorted(matching_kws))}")

            # Text scoring
            if query.text:
                text_lower = query.text.lower()
                content_lower = row["content"].lower()
                summary_lower = row["summary"].lower()

                # FTS match bonus
                if row["id"] in fts_ids:
                    score += 0.4
                    match_reasons.append("FTS match")

                if text_lower in content_lower:
                    score += 0.5
                    match_reasons.append("content match")
                if text_lower in summary_lower:
                    score += 0.3
                    match_reasons.append("summary match")

                words = text_lower.split()
                word_matches = sum(
                    1 for w in words if w in content_lower or w in summary_lower
                )
                if word_matches > 0:
                    score += word_matches * 0.1
                    match_reasons.append(f"{word_matches} word matches")

            # No criteria = return all with base score
            if not query.text and not query.tags and not query.keywords:
                score = 0.5

            if score > 0:
                links = self._load_links(conn, row["id"])
                memory = self._row_to_memory(row, links)
                results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=min(1.0, score),
                        match_reasons=match_reasons,
                    )
                )

        # He2025: stable sort with ID tiebreaker for deterministic ordering
        results.sort(key=lambda r: (-r.score, r.memory.id))

        if query.limit > 0:
            results = results[:query.limit]

        return results

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        """Get all memories of a specific type."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM memories WHERE memory_type = ? ORDER BY id",
                (memory_type.value,),
            )
            return [
                self._row_to_memory(r, self._load_links(conn, r["id"]))
                for r in cur.fetchall()
            ]
        finally:
            pass  # thread-local conn reused, not closed

    def get_by_tag(self, tag: str) -> List[Memory]:
        """Get all memories with a specific tag."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT m.* FROM memories m "
                "JOIN memory_tags t ON m.id = t.memory_id "
                "WHERE t.tag = ? ORDER BY m.id",
                (tag.lower(),),
            )
            return [
                self._row_to_memory(r, self._load_links(conn, r["id"]))
                for r in cur.fetchall()
            ]
        finally:
            pass  # thread-local conn reused, not closed

    def get_linked(self, memory_id: str) -> List[Memory]:
        """Get all memories linked to a specific memory."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT m.* FROM memories m "
                "JOIN memory_links l ON m.id = l.target_id "
                "WHERE l.source_id = ? ORDER BY m.id",
                (memory_id,),
            )
            return [
                self._row_to_memory(r, self._load_links(conn, r["id"]))
                for r in cur.fetchall()
            ]
        finally:
            pass  # thread-local conn reused, not closed

    def get_recent(self, limit: int = 10) -> List[Memory]:
        """Get most recent memories."""
        self._wait_loaded()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [
                self._row_to_memory(r, self._load_links(conn, r["id"]))
                for r in cur.fetchall()
            ]
        finally:
            pass  # thread-local conn reused, not closed


# =============================================================================
# FACTORY
# =============================================================================

def create_memory_store(storage_dir: Path, background_load: bool = True):
    """
    Create the appropriate memory store based on SYNAPSE_MEMORY_BACKEND env var.

    Values:
    - "sqlite" -> SQLiteMemoryStore
    - "jsonl" (default) -> MemoryStore (JSONL)
    """
    backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").lower().strip()
    if backend == "sqlite":
        logger.info("Using SQLite memory backend")
        return SQLiteMemoryStore(storage_dir, background_load=background_load)
    else:
        from .store import MemoryStore
        return MemoryStore(storage_dir, background_load=background_load)
