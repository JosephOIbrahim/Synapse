"""
Synapse Memory Data Structures

Core data models for the memory system, inspired by:
- A-MEM's note structure (keywords, tags, links)
- Zettelkasten's atomic notes and linking
- Mem0's memory tiers
"""

import time
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum


class MemoryType(Enum):
    """Types of memories stored in Synapse."""
    CONTEXT = "context"       # Shot/project context
    DECISION = "decision"     # Creative or technical decision with reasoning
    TASK = "task"            # Task started, completed, or blocked
    ACTION = "action"        # Specific action taken (node created, param changed)
    NOTE = "note"            # General note or observation
    REFERENCE = "reference"  # External reference (file, URL, asset)
    FEEDBACK = "feedback"    # Client or supervisor feedback
    ERROR = "error"          # Error or issue encountered
    SUMMARY = "summary"      # Auto-generated session or period summary


class MemoryTier(Enum):
    """Memory scope/lifetime tiers."""
    CONVERSATION = "conversation"  # Current session only (ephemeral)
    SHOT = "shot"                  # This specific .hip file
    SEQUENCE = "sequence"          # Related shots (shared context)
    SHOW = "show"                  # Entire project/show


class LinkType(Enum):
    """Types of relationships between memories."""
    RELATED = "related"          # Generally related
    SUPPORTS = "supports"        # Provides evidence/reasoning for
    CONTRADICTS = "contradicts"  # Conflicts with
    SUPERSEDES = "supersedes"    # Replaces/updates
    DEPENDS_ON = "depends_on"    # Requires this to be true
    CAUSED_BY = "caused_by"      # Was triggered by
    IMPLEMENTS = "implements"    # Is the implementation of


@dataclass
class MemoryLink:
    """A link between two memories (Zettelkasten-style)."""
    target_id: str
    link_type: LinkType
    reason: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    bidirectional: bool = False

    def to_dict(self) -> Dict:
        return {
            "target_id": self.target_id,
            "link_type": self.link_type.value,
            "reason": self.reason,
            "created_at": self.created_at,
            "bidirectional": self.bidirectional
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryLink':
        return cls(
            target_id=data["target_id"],
            link_type=LinkType(data["link_type"]),
            reason=data.get("reason", ""),
            created_at=data.get("created_at", ""),
            bidirectional=data.get("bidirectional", False)
        )


@dataclass
class Memory:
    """
    A single memory unit in Synapse.

    Inspired by A-MEM's note structure with:
    - Content and metadata
    - LLM-generated keywords and tags
    - Zettelkasten-style links to other memories
    - Provenance tracking
    """

    # Identity
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    # Content
    content: str = ""
    memory_type: MemoryType = MemoryType.NOTE
    tier: MemoryTier = MemoryTier.SHOT

    # Metadata (can be LLM-generated)
    summary: str = ""                           # One-line summary
    keywords: List[str] = field(default_factory=list)  # Key concepts
    tags: List[str] = field(default_factory=list)      # Categorical tags

    # Zettelkasten linking
    links: List[MemoryLink] = field(default_factory=list)

    # Houdini context
    hip_file: str = ""                          # Which .hip file
    hip_version: int = 0                        # Version when created
    frame: Optional[int] = None                 # Relevant frame
    frame_range: Optional[Tuple[int, int]] = None  # Relevant frame range
    node_paths: List[str] = field(default_factory=list)  # Related node paths

    # Provenance
    source: str = "user"                        # "user", "ai", "auto", "gate"
    agent_id: str = ""                          # Which AI agent (if applicable)
    confidence: float = 1.0                     # 0-1, certainty of this memory

    # Embedding (for semantic search)
    embedding: Optional[List[float]] = None

    # Consolidation
    is_consolidated: bool = False               # Has this been summarized into another?
    consolidated_into: Optional[str] = None     # ID of summary memory

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.summary and self.content:
            # Auto-generate summary from first line or truncated content
            first_line = self.content.split('\n')[0]
            self.summary = first_line[:100] + "..." if len(first_line) > 100 else first_line

    def _generate_id(self) -> str:
        """Generate a deterministic ID based on content and timestamp."""
        content_hash = hashlib.sha256(
            f"{self.content}:{self.created_at}:{self.memory_type.value}".encode()
        ).hexdigest()[:12]
        return f"mem_{content_hash}"

    def add_link(self, target_id: str, link_type: LinkType, reason: str = ""):
        """Add a link to another memory."""
        link = MemoryLink(
            target_id=target_id,
            link_type=link_type,
            reason=reason
        )
        self.links.append(link)
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_keyword(self, keyword: str):
        """Add a keyword if not already present."""
        keyword = keyword.lower().strip()
        if keyword and keyword not in self.keywords:
            self.keywords.append(keyword)
            self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add_tag(self, tag: str):
        """Add a tag if not already present."""
        tag = tag.lower().strip()
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "tier": self.tier.value,
            "summary": self.summary,
            "keywords": self.keywords,
            "tags": self.tags,
            "links": [link.to_dict() for link in self.links],
            "hip_file": self.hip_file,
            "hip_version": self.hip_version,
            "frame": self.frame,
            "frame_range": list(self.frame_range) if self.frame_range else None,
            "node_paths": self.node_paths,
            "source": self.source,
            "agent_id": self.agent_id,
            "confidence": self.confidence,
            "embedding": self.embedding,
            "is_consolidated": self.is_consolidated,
            "consolidated_into": self.consolidated_into
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """Deserialize from dictionary."""
        links = [MemoryLink.from_dict(l) for l in data.get("links", [])]
        frame_range = tuple(data["frame_range"]) if data.get("frame_range") else None

        return cls(
            id=data.get("id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            content=data.get("content", ""),
            memory_type=MemoryType(data.get("memory_type", "note")),
            tier=MemoryTier(data.get("tier", "shot")),
            summary=data.get("summary", ""),
            keywords=data.get("keywords", []),
            tags=data.get("tags", []),
            links=links,
            hip_file=data.get("hip_file", ""),
            hip_version=data.get("hip_version", 0),
            frame=data.get("frame"),
            frame_range=frame_range,
            node_paths=data.get("node_paths", []),
            source=data.get("source", "user"),
            agent_id=data.get("agent_id", ""),
            confidence=data.get("confidence", 1.0),
            embedding=data.get("embedding"),
            is_consolidated=data.get("is_consolidated", False),
            consolidated_into=data.get("consolidated_into")
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'Memory':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_markdown(self) -> str:
        """Render as markdown for human-readable display."""
        lines = []

        # Header
        type_emoji = {
            MemoryType.CONTEXT: "[CTX]",
            MemoryType.DECISION: "[DEC]",
            MemoryType.TASK: "[TSK]",
            MemoryType.ACTION: "[ACT]",
            MemoryType.NOTE: "[NOTE]",
            MemoryType.REFERENCE: "[REF]",
            MemoryType.FEEDBACK: "[FB]",
            MemoryType.ERROR: "[ERR]",
            MemoryType.SUMMARY: "[SUM]"
        }
        icon = type_emoji.get(self.memory_type, "[?]")
        lines.append(f"## {icon} {self.summary}")
        lines.append("")

        # Metadata
        date_str = self.created_at.split("T")[0] if self.created_at else "unknown"
        lines.append(f"**Date:** {date_str} | **Type:** {self.memory_type.value} | **Source:** {self.source}")

        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")

        if self.keywords:
            lines.append(f"**Keywords:** {', '.join(self.keywords)}")

        lines.append("")

        # Content
        lines.append(self.content)
        lines.append("")

        # Links
        if self.links:
            lines.append("**Related:**")
            for link in self.links:
                lines.append(f"- [{link.link_type.value}] -> {link.target_id}: {link.reason}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# MEMORY QUERY HELPERS
# =============================================================================

@dataclass
class MemoryQuery:
    """Query parameters for searching memories."""
    text: str = ""                              # Full-text search
    memory_types: List[MemoryType] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    tier: Optional[MemoryTier] = None
    source: Optional[str] = None
    since: Optional[str] = None                 # ISO timestamp
    until: Optional[str] = None                 # ISO timestamp
    limit: int = 50
    include_consolidated: bool = False


@dataclass
class MemorySearchResult:
    """A search result with relevance score."""
    memory: Memory
    score: float                                # 0-1 relevance
    match_reasons: List[str] = field(default_factory=list)  # Why it matched

    def to_dict(self) -> Dict:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "match_reasons": self.match_reasons
        }
