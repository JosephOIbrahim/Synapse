"""
Synapse Memory Store

Persistent storage for project memories.
Stores data in $HIP/.synapse/ alongside the Houdini project file.

Storage format:
- memory.jsonl: Append-only memory log (one JSON per line)
- index.json: Search index and metadata
- context.md: Human-readable project context
- decisions.md: Human-readable decision log
- tasks.md: Human-readable task history

Migration: Automatically migrates .nexus/ or .engram/ to .synapse/ if needed.
"""

import os
import json
import time
import shutil
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

try:
    from ..core.crypto import CryptoEngine, ENCRYPTION_AVAILABLE
except ImportError:
    ENCRYPTION_AVAILABLE = False

from .models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult
)


# =============================================================================
# MEMORY STORE
# =============================================================================

class MemoryStore:
    """
    Low-level memory storage and retrieval.

    Handles:
    - Persisting memories to disk
    - Loading memories on startup
    - Basic search and filtering
    """

    def __init__(self, storage_dir: Path, background_load: bool = True):
        self.storage_dir = Path(storage_dir)
        self.memory_file = self.storage_dir / "memory.jsonl"
        self.index_file = self.storage_dir / "index.json"

        self._memories: Dict[str, Memory] = {}
        self._index: Dict[str, Any] = {
            "by_type": {},
            "by_tag": {},
            "by_keyword": {},
            "links": {},
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated": "",
            "version": 1
        }
        self._lock = threading.RLock()
        self._dirty = False
        self._loaded = threading.Event()

        # Write buffer — defers disk I/O to background thread (saves 1-5ms per add)
        self._write_buffer: list = []
        self._write_lock = threading.Lock()
        self._flush_interval = 2.0  # seconds
        self._flush_max = 50  # items
        self._flusher = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="Synapse-MemoryFlush",
        )
        self._flusher_running = True
        self._flusher.start()

        self._ensure_storage_dir()

        if background_load:
            loader = threading.Thread(
                target=self._load,
                daemon=True,
                name="Synapse-MemoryLoad",
            )
            loader.start()
        else:
            self._load()

    def _flush_loop(self):
        """Background thread: flush buffered writes to disk periodically."""
        while self._flusher_running:
            time.sleep(self._flush_interval)
            self._flush_writes()

    def _flush_writes(self):
        """Flush buffered memory lines to disk."""
        with self._write_lock:
            if not self._write_buffer:
                return
            lines = self._write_buffer[:]
            self._write_buffer.clear()

        try:
            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write("".join(lines))
        except Exception as e:
            print(f"[Synapse] Write flush error: {e}")

    def flush(self):
        """Force-flush any buffered writes (call on shutdown)."""
        self._flush_writes()

    def _ensure_storage_dir(self):
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load memories from disk."""
        if not self.memory_file.exists():
            self._loaded.set()
            return

        crypto = CryptoEngine.get_instance() if ENCRYPTION_AVAILABLE else None

        with self._lock:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        if crypto:
                            line = crypto.decrypt_line(line)
                        data = json.loads(line)
                        memory = Memory.from_dict(data)
                        self._memories[memory.id] = memory
                        self._index_memory(memory)
                    except json.JSONDecodeError as e:
                        print(f"[Synapse] Warning: Invalid JSON on line {line_num}: {e}")
                    except Exception as e:
                        print(f"[Synapse] Warning: Failed to load memory on line {line_num}: {e}")

            # Load index if exists
            if self.index_file.exists():
                try:
                    with open(self.index_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if crypto:
                        content = crypto.decrypt_file_content(content)
                    self._index = json.loads(content)
                except Exception as e:
                    print(f"[Synapse] Warning: Failed to load index: {e}")

        print(f"[Synapse] Loaded {len(self._memories)} memories from {self.storage_dir}")
        self._loaded.set()

    def _index_memory(self, memory: Memory):
        """Add memory to in-memory indices."""
        # Index by type
        type_key = memory.memory_type.value
        if type_key not in self._index["by_type"]:
            self._index["by_type"][type_key] = []
        if memory.id not in self._index["by_type"][type_key]:
            self._index["by_type"][type_key].append(memory.id)

        # Index by tags
        for tag in memory.tags:
            if tag not in self._index["by_tag"]:
                self._index["by_tag"][tag] = []
            if memory.id not in self._index["by_tag"][tag]:
                self._index["by_tag"][tag].append(memory.id)

        # Index by keywords
        for keyword in memory.keywords:
            if keyword not in self._index["by_keyword"]:
                self._index["by_keyword"][keyword] = []
            if memory.id not in self._index["by_keyword"][keyword]:
                self._index["by_keyword"][keyword].append(memory.id)

        # Index links
        for link in memory.links:
            if memory.id not in self._index["links"]:
                self._index["links"][memory.id] = []
            link_entry = {"target": link.target_id, "type": link.link_type.value}
            if link_entry not in self._index["links"][memory.id]:
                self._index["links"][memory.id].append(link_entry)

    def _wait_loaded(self, timeout: float = 10.0):
        """Block until background load completes (max timeout seconds)."""
        self._loaded.wait(timeout=timeout)

    def save(self):
        """Persist all memories to disk."""
        crypto = CryptoEngine.get_instance() if ENCRYPTION_AVAILABLE else None

        with self._lock:
            # Write memories (append-only format, but we rewrite for consistency)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                for memory in self._memories.values():
                    line = memory.to_json()
                    if crypto:
                        line = crypto.encrypt_line(line)
                    f.write(line + "\n")

            # Write index
            self._index["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            index_content = json.dumps(self._index, indent=2)
            if crypto:
                index_content = crypto.encrypt_file_content(index_content)
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write(index_content)

            self._dirty = False

    def add(self, memory: Memory) -> str:
        """Add a memory to the store.

        Buffers disk write for background flush (saves 1-5ms per call).
        In-memory state is updated immediately for read consistency.
        """
        with self._lock:
            self._memories[memory.id] = memory
            self._index_memory(memory)
            self._dirty = True

        # Buffer the disk write — flushed by background thread
        crypto = CryptoEngine.get_instance() if ENCRYPTION_AVAILABLE else None
        line = memory.to_json()
        if crypto:
            line = crypto.encrypt_line(line)

        with self._write_lock:
            self._write_buffer.append(line + "\n")
            # Auto-flush if buffer is full
            if len(self._write_buffer) >= self._flush_max:
                self._flush_writes()

        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        self._wait_loaded()
        with self._lock:
            return self._memories.get(memory_id)

    def update(self, memory: Memory):
        """Update an existing memory."""
        with self._lock:
            if memory.id in self._memories:
                memory.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._memories[memory.id] = memory
                self._index_memory(memory)
                self._dirty = True

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                self._dirty = True
                return True
            return False

    def all(self) -> List[Memory]:
        """Get all memories."""
        self._wait_loaded()
        with self._lock:
            return list(self._memories.values())

    def count(self) -> int:
        """Get total memory count."""
        self._wait_loaded()
        with self._lock:
            return len(self._memories)

    def clear(self):
        """Clear all memories."""
        with self._lock:
            self._memories.clear()
            self._index = {
                "by_type": {},
                "by_tag": {},
                "by_keyword": {},
                "links": {},
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated": "",
                "version": 1
            }
            self._dirty = True
            self.save()

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """Search memories based on query parameters."""
        self._wait_loaded()
        with self._lock:
            results = []

            for memory in self._memories.values():
                # Skip consolidated unless requested
                if memory.is_consolidated and not query.include_consolidated:
                    continue

                score = 0.0
                match_reasons = []

                # Filter by type
                if query.memory_types:
                    if memory.memory_type not in query.memory_types:
                        continue

                # Filter by tier
                if query.tier and memory.tier != query.tier:
                    continue

                # Filter by source
                if query.source and memory.source != query.source:
                    continue

                # Filter by time range
                if query.since and memory.created_at < query.since:
                    continue
                if query.until and memory.created_at > query.until:
                    continue

                # Tag matching
                if query.tags:
                    matching_tags = set(query.tags) & set(memory.tags)
                    if matching_tags:
                        score += len(matching_tags) * 0.2
                        match_reasons.append(f"tags: {', '.join(matching_tags)}")

                # Keyword matching
                if query.keywords:
                    matching_keywords = set(query.keywords) & set(memory.keywords)
                    if matching_keywords:
                        score += len(matching_keywords) * 0.2
                        match_reasons.append(f"keywords: {', '.join(matching_keywords)}")

                # Text search
                if query.text:
                    text_lower = query.text.lower()
                    content_lower = memory.content.lower()
                    summary_lower = memory.summary.lower()

                    if text_lower in content_lower:
                        score += 0.5
                        match_reasons.append("content match")
                    if text_lower in summary_lower:
                        score += 0.3
                        match_reasons.append("summary match")

                    # Check individual words
                    words = text_lower.split()
                    word_matches = sum(1 for w in words if w in content_lower or w in summary_lower)
                    if word_matches > 0:
                        score += word_matches * 0.1
                        match_reasons.append(f"{word_matches} word matches")

                # If no specific criteria, include all with base score
                if not query.text and not query.tags and not query.keywords:
                    score = 0.5

                if score > 0:
                    results.append(MemorySearchResult(
                        memory=memory,
                        score=min(1.0, score),
                        match_reasons=match_reasons
                    ))

            # Sort by score descending
            results.sort(key=lambda r: r.score, reverse=True)

            # Apply limit
            if query.limit > 0:
                results = results[:query.limit]

            return results

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        """Get all memories of a specific type."""
        self._wait_loaded()
        with self._lock:
            ids = self._index["by_type"].get(memory_type.value, [])
            return [self._memories[id] for id in ids if id in self._memories]

    def get_by_tag(self, tag: str) -> List[Memory]:
        """Get all memories with a specific tag."""
        self._wait_loaded()
        with self._lock:
            ids = self._index["by_tag"].get(tag.lower(), [])
            return [self._memories[id] for id in ids if id in self._memories]

    def get_linked(self, memory_id: str) -> List[Memory]:
        """Get all memories linked to a specific memory."""
        self._wait_loaded()
        with self._lock:
            links = self._index["links"].get(memory_id, [])
            return [
                self._memories[link["target"]]
                for link in links
                if link["target"] in self._memories
            ]

    def get_recent(self, limit: int = 10) -> List[Memory]:
        """Get most recent memories."""
        self._wait_loaded()
        with self._lock:
            sorted_memories = sorted(
                self._memories.values(),
                key=lambda m: m.created_at,
                reverse=True
            )
            return sorted_memories[:limit]


# =============================================================================
# SYNAPSE MEMORY - HIGH-LEVEL API
# =============================================================================

class SynapseMemory:
    """
    High-level API for Synapse memory system.

    Automatically detects current Houdini project and manages memory storage.
    Provides convenient methods for common operations.

    Migration: Automatically migrates .nexus/ or .engram/ to .synapse/ if needed.
    """

    def __init__(self, project_path: Optional[str] = None):
        """
        Initialize Synapse for a project.

        Args:
            project_path: Optional path to .hip file or project directory.
                         If None, uses current Houdini project.
        """
        self.project_path = self._resolve_project_path(project_path)
        self.storage_dir = self._get_storage_dir()
        self.store = MemoryStore(self.storage_dir)

        # Callbacks
        self._on_memory_added: List[Callable[[Memory], None]] = []
        self._on_memory_updated: List[Callable[[Memory], None]] = []

        print(f"[Synapse] Initialized for project: {self.project_path}")
        print(f"[Synapse] Storage: {self.storage_dir}")

    def _resolve_project_path(self, path: Optional[str]) -> Path:
        """Resolve the project path."""
        if path:
            return Path(path)

        if HOU_AVAILABLE:
            hip_path = hou.hipFile.path()
            if hip_path and hip_path != "untitled.hip":
                return Path(hip_path)
            else:
                # Use temp directory for unsaved projects
                return Path(hou.text.expandString("$HOUDINI_TEMP_DIR")) / "untitled"

        # Fallback
        return Path.cwd() / "untitled.hip"

    def _get_storage_dir(self) -> Path:
        """
        Get the storage directory for this project.

        3-tier migration logic:
        1. If .synapse/ exists -> use it
        2. If .nexus/ exists -> copy to .synapse/, leave marker
        3. If .engram/ exists -> copy to .synapse/, leave marker
        4. Otherwise -> create .synapse/
        """
        if self.project_path.is_file():
            base_dir = self.project_path.parent
        else:
            base_dir = self.project_path

        synapse_dir = base_dir / ".synapse"
        nexus_dir = base_dir / ".nexus"
        engram_dir = base_dir / ".engram"

        # Priority 1: Use existing .synapse/
        if synapse_dir.exists():
            return synapse_dir

        # Priority 2: Migrate from .nexus/
        if nexus_dir.exists():
            try:
                print(f"[Synapse] Migrating from .nexus/ to .synapse/")
                shutil.copytree(nexus_dir, synapse_dir)
                migration_marker = nexus_dir / ".migrated_to_synapse"
                migration_marker.write_text(
                    f"Migrated to .synapse/ on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"This directory is kept for backwards compatibility.\n"
                    f"You can safely delete it."
                )
                print(f"[Synapse] Migration complete: {nexus_dir} -> {synapse_dir}")
                return synapse_dir
            except Exception as e:
                print(f"[Synapse] Migration failed: {e}. Using .nexus/ directly.")
                return nexus_dir

        # Priority 3: Migrate from .engram/
        if engram_dir.exists():
            try:
                print(f"[Synapse] Migrating from .engram/ to .synapse/")
                shutil.copytree(engram_dir, synapse_dir)
                migration_marker = engram_dir / ".migrated_to_synapse"
                migration_marker.write_text(
                    f"Migrated to .synapse/ on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"This directory is kept for backwards compatibility.\n"
                    f"You can safely delete it."
                )
                print(f"[Synapse] Migration complete: {engram_dir} -> {synapse_dir}")
                return synapse_dir
            except Exception as e:
                print(f"[Synapse] Migration failed: {e}. Using .engram/ directly.")
                return engram_dir

        # Priority 4: Create new .synapse/
        return synapse_dir

    def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.NOTE,
        tags: List[str] = None,
        keywords: List[str] = None,
        source: str = "user",
        node_paths: List[str] = None,
        links: List[Dict] = None
    ) -> Memory:
        """
        Add a new memory.

        Args:
            content: The memory content
            memory_type: Type of memory
            tags: Categorical tags
            keywords: Key concepts
            source: Who created this ("user", "ai", "auto")
            node_paths: Related Houdini node paths
            links: Links to other memories [{"target_id": "...", "type": "...", "reason": "..."}]

        Returns:
            The created Memory object
        """
        # Get Houdini context if available
        hip_file = ""
        hip_version = 0
        frame = None

        if HOU_AVAILABLE:
            hip_file = hou.hipFile.name()
            # Try to extract version from filename
            try:
                import re
                version_match = re.search(r'_v(\d+)', hip_file)
                if version_match:
                    hip_version = int(version_match.group(1))
            except:
                pass
            frame = int(hou.frame())

        # Create memory
        memory = Memory(
            content=content,
            memory_type=memory_type,
            tier=MemoryTier.SHOT,
            tags=tags or [],
            keywords=keywords or [],
            source=source,
            hip_file=hip_file,
            hip_version=hip_version,
            frame=frame,
            node_paths=node_paths or []
        )

        # Add links
        if links:
            for link_data in links:
                memory.add_link(
                    target_id=link_data["target_id"],
                    link_type=LinkType(link_data.get("type", "related")),
                    reason=link_data.get("reason", "")
                )

        # Store
        self.store.add(memory)

        # Notify callbacks
        for callback in self._on_memory_added:
            try:
                callback(memory)
            except Exception as e:
                print(f"[Synapse] Callback error: {e}")

        return memory

    def decision(
        self,
        decision: str,
        reasoning: str,
        alternatives: List[str] = None,
        tags: List[str] = None
    ) -> Memory:
        """
        Record a decision with reasoning.

        Args:
            decision: What was decided
            reasoning: Why this was chosen
            alternatives: Other options considered
            tags: Categorical tags
        """
        content_lines = [
            f"**Decision:** {decision}",
            f"**Reasoning:** {reasoning}"
        ]
        if alternatives:
            content_lines.append("**Alternatives Considered:**")
            for alt in alternatives:
                content_lines.append(f"- {alt}")

        return self.add(
            content="\n".join(content_lines),
            memory_type=MemoryType.DECISION,
            tags=tags or ["decision"],
            keywords=self._extract_keywords(decision + " " + reasoning),
            source="user"
        )

    def action(
        self,
        action: str,
        node_paths: List[str] = None,
        tags: List[str] = None
    ) -> Memory:
        """
        Record an action taken.

        Args:
            action: What was done
            node_paths: Affected node paths
            tags: Categorical tags
        """
        return self.add(
            content=action,
            memory_type=MemoryType.ACTION,
            tags=tags or ["action"],
            node_paths=node_paths,
            source="auto"
        )

    def note(self, content: str, tags: List[str] = None) -> Memory:
        """Add a simple note."""
        return self.add(content, MemoryType.NOTE, tags=tags)

    def search(self, query: str, limit: int = 20) -> List[MemorySearchResult]:
        """Search memories by text."""
        return self.store.search(MemoryQuery(text=query, limit=limit))

    def get_decisions(self) -> List[Memory]:
        """Get all decision memories."""
        return self.store.get_by_type(MemoryType.DECISION)

    def get_recent(self, limit: int = 10) -> List[Memory]:
        """Get most recent memories."""
        return self.store.get_recent(limit)

    def get_context_summary(self) -> str:
        """
        Generate a context summary for AI consumption.

        Returns a markdown-formatted summary of key project memories.
        """
        lines = ["# Project Memory Context", ""]

        # Recent decisions
        decisions = self.get_decisions()
        if decisions:
            lines.append("## Key Decisions")
            for d in decisions[-5:]:  # Last 5 decisions
                lines.append(f"- {d.summary}")
            lines.append("")

        # Recent activity
        recent = self.get_recent(5)
        if recent:
            lines.append("## Recent Activity")
            for m in recent:
                type_name = m.memory_type.value
                lines.append(f"- [{type_name}] {m.summary}")
            lines.append("")

        # Common tags
        all_tags = set()
        for m in self.store.all():
            all_tags.update(m.tags)
        if all_tags:
            lines.append(f"## Tags: {', '.join(sorted(all_tags)[:10])}")
            lines.append("")

        return "\n".join(lines)

    def save(self):
        """Persist all changes to disk."""
        self.store.save()

    def on_memory_added(self, callback: Callable[[Memory], None]):
        """Register callback for when memories are added."""
        self._on_memory_added.append(callback)

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Simple keyword extraction from text."""
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
            'neither', 'not', 'only', 'same', 'than', 'too', 'very',
            'just', 'also', 'now', 'here', 'there', 'when', 'where',
            'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'any', 'this', 'that',
            'these', 'those', 'what', 'which', 'who', 'whom', 'whose'
        }

        # Tokenize and filter
        words = text.lower().split()
        words = [w.strip('.,!?;:()[]{}"\'-') for w in words]
        words = [w for w in words if w and len(w) > 2 and w not in stop_words]

        # Count frequencies
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        # Return top keywords
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:max_keywords]]


# =============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# =============================================================================

NexusMemory = SynapseMemory
EngramMemory = SynapseMemory


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_global_synapse: Optional[SynapseMemory] = None


def get_synapse_memory() -> SynapseMemory:
    """Get or create the global SynapseMemory instance."""
    global _global_synapse
    if _global_synapse is None:
        _global_synapse = SynapseMemory()
    return _global_synapse


def reset_synapse_memory():
    """Reset the global SynapseMemory instance (e.g., when opening new project)."""
    global _global_synapse
    if _global_synapse:
        _global_synapse.save()
    _global_synapse = None


# Backwards compatibility aliases
def get_nexus_memory() -> SynapseMemory:
    """Get or create the global memory instance (backwards compatible)."""
    return get_synapse_memory()


def get_engram() -> SynapseMemory:
    """Get or create the global memory instance (backwards compatible)."""
    return get_synapse_memory()


def reset_nexus_memory():
    """Reset the global memory instance (backwards compatible)."""
    reset_synapse_memory()


def reset_engram():
    """Reset the global memory instance (backwards compatible)."""
    reset_synapse_memory()
