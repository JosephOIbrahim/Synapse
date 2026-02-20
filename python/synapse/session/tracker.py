"""
Synapse Session Tracker

Tracks AI sessions and integrates with the memory system.
Handles session lifecycle, action logging, and context provision.
"""

import logging
import os
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..memory.store import SynapseMemory, get_synapse_memory, reset_synapse_memory
from ..memory.models import Memory, MemoryType, MemoryQuery
from ..memory.markdown import MarkdownSync, load_context
from .summary import generate_session_summary

logger = logging.getLogger("synapse.session")


# =============================================================================
# SESSION DATACLASS
# =============================================================================

@dataclass
class SynapseSession:
    """Tracks a single AI session for memory purposes."""
    session_id: str
    client_id: str
    started_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ended_at: Optional[str] = None

    # Session activity
    commands_executed: int = 0
    nodes_created: List[str] = field(default_factory=list)
    nodes_modified: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)

    # Conversation excerpts worth preserving
    notable_exchanges: List[Dict[str, str]] = field(default_factory=list)

    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        if self.ended_at:
            end = time.mktime(time.strptime(self.ended_at, "%Y-%m-%dT%H:%M:%SZ"))
        else:
            end = time.time()
        start = time.mktime(time.strptime(self.started_at, "%Y-%m-%dT%H:%M:%SZ"))
        return end - start

    def to_summary(self) -> str:
        """Generate a human-readable session summary."""
        return generate_session_summary(self)


# Backwards compatibility
NexusSession = SynapseSession


# =============================================================================
# SYNAPSE BRIDGE
# =============================================================================

class SynapseBridge:
    """
    Bridges Synapse communication with memory system.

    Responsibilities:
    - Provide project context to AI on connect
    - Log significant actions to memory
    - Handle memory-related commands
    - Generate session summaries
    """

    def __init__(self):
        self._sessions: Dict[str, SynapseSession] = {}
        self._synapse: Optional[SynapseMemory] = None
        self._markdown_sync: Optional[MarkdownSync] = None
        self._lock = threading.Lock()

        # Auto-logging settings
        self.log_node_creation = True
        self.log_node_modification = True
        self.log_parameter_changes = False  # Too noisy by default
        self.log_errors = True

        self._context_cache = None
        self._context_cache_time = 0.0
        self._context_cache_ttl = 30.0  # seconds — stale-while-revalidate

        self._init_synapse()

    def _init_synapse(self):
        """Initialize Synapse memory for current project."""
        try:
            self._synapse = get_synapse_memory()
            if self._synapse:
                self._markdown_sync = MarkdownSync(self._synapse.storage_dir)
                self._markdown_sync.ensure_files()
                logger.info("Connected to memory at %s", self._synapse.storage_dir)
        except Exception as e:
            logger.error("Failed to initialize memory: %s", e)

    def reload_synapse(self):
        """Reload memory (e.g., when project changes)."""
        reset_synapse_memory()
        self._init_synapse()

    # Backwards compatibility
    def reload_nexus(self):
        """Reload memory (backwards compatible)."""
        self.reload_synapse()

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def start_session(self, client_id: str) -> str:
        """
        Start a new session when AI connects.

        Returns:
            Session ID
        """
        session_id = f"sess_{int(time.time())}_{client_id}"

        session = SynapseSession(
            session_id=session_id,
            client_id=str(client_id)
        )

        with self._lock:
            self._sessions[session_id] = session

        # Log session start to memory
        if self._synapse:
            self._synapse.add(
                content=f"AI session started (client: {client_id})",
                memory_type=MemoryType.NOTE,
                tags=["session", "start"],
                source="auto"
            )

        return session_id

    def end_session(self, session_id: str) -> Optional[str]:
        """
        End a session and generate summary.

        Returns:
            Session summary string
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)

        if not session:
            return None

        session.ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        summary = session.to_summary()

        # Log session summary to memory
        if self._synapse and session.commands_executed > 0:
            self._synapse.add(
                content=summary,
                memory_type=MemoryType.SUMMARY,
                tags=["session", "summary"],
                source="auto"
            )

        return summary

    def get_session(self, session_id: str) -> Optional[SynapseSession]:
        """Get a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    # =========================================================================
    # CONTEXT LOADING
    # =========================================================================

    def get_connection_context(self) -> Dict[str, Any]:
        """
        Get full project context for AI on connection.

        This is sent to AI immediately when it connects, giving it
        full awareness of the project state.

        Cached with TTL to avoid re-parsing disk/IPC on rapid calls.
        """
        import time as _time
        now = _time.monotonic()
        if self._context_cache is not None and (now - self._context_cache_time) < self._context_cache_ttl:
            return self._context_cache

        context: dict = {
            "project": {},
            "recent_decisions": [],
            "recent_activity": [],
            "current_state": {},
            "memory_stats": {}
        }

        if not self._synapse:
            context["warning"] = "Memory not available"
            return context

        # Project context from context.md
        try:
            shot_context = load_context(self._synapse.storage_dir)
            context["project"] = {
                "overview": shot_context.overview,
                "goals": shot_context.goals,
                "constraints": shot_context.constraints,
                "assets": shot_context.assets,
                "client_notes": shot_context.client_notes
            }
        except Exception as e:
            context["project"]["error"] = str(e)

        # Recent decisions
        try:
            decisions = self._synapse.get_decisions()
            context["recent_decisions"] = [
                {
                    "date": d.created_at.split("T")[0] if d.created_at else "",
                    "summary": d.summary,
                    "id": d.id
                }
                for d in decisions[-5:]  # Last 5
            ]
        except Exception as e:
            context["recent_decisions"] = []

        # Recent activity
        try:
            recent = self._synapse.get_recent(10)
            context["recent_activity"] = [
                {
                    "type": m.memory_type.value,
                    "summary": m.summary,
                    "timestamp": m.created_at
                }
                for m in recent
            ]
        except Exception as e:
            context["recent_activity"] = []

        # Current Houdini state
        if HOU_AVAILABLE:
            try:
                context["current_state"] = {
                    "hip_file": hou.hipFile.name(),
                    "frame": int(hou.frame()),
                    "fps": hou.fps(),
                    "selection": [n.path() for n in hou.selectedNodes()[:5]]
                }
            except:
                pass

        # Memory stats
        context["memory_stats"] = {
            "total_memories": self._synapse.store.count(),
            "storage_dir": str(self._synapse.storage_dir)
        }

        # Cache for TTL
        self._context_cache = context
        self._context_cache_time = now

        return context

    def invalidate_context_cache(self):
        """Invalidate cached context after mutations."""
        self._context_cache = None

    def get_context_markdown(self) -> str:
        """Get project context as markdown (for AI prompt injection)."""
        if not self._markdown_sync:
            return "# No project context available\n"
        return self._markdown_sync.get_context_for_ai()

    # =========================================================================
    # ACTION LOGGING
    # =========================================================================

    def log_action(
        self,
        action: str,
        session_id: str = None,
        node_paths: List[str] = None,
        details: Dict[str, Any] = None
    ):
        """Log an action to memory."""
        if not self._synapse:
            return

        # Update session stats
        if session_id:
            session = self.get_session(session_id)
            if session:
                session.commands_executed += 1
                if node_paths:
                    session.nodes_modified.extend(node_paths)

        # Log to memory
        self._synapse.add(
            content=action,
            memory_type=MemoryType.ACTION,
            tags=["action", "ai"],
            node_paths=node_paths or [],
            source="ai"
        )
        self.invalidate_context_cache()

    def log_node_created(self, node_path: str, node_type: str, session_id: str = None):
        """Log node creation."""
        if not self.log_node_creation:
            return

        if session_id:
            session = self.get_session(session_id)
            if session:
                session.nodes_created.append(node_path)

        self.log_action(
            f"Created {node_type} node: {node_path}",
            session_id=session_id,
            node_paths=[node_path]
        )

    def log_decision(
        self,
        decision: str,
        reasoning: str,
        session_id: str = None,
        alternatives: List[str] = None
    ):
        """Log a decision with reasoning."""
        if not self._synapse:
            return

        memory = self._synapse.decision(
            decision=decision,
            reasoning=reasoning,
            alternatives=alternatives,
            tags=["ai_decision"]
        )

        # Update session
        if session_id:
            session = self.get_session(session_id)
            if session:
                session.decisions_made.append(decision)

        # Sync to markdown
        if self._markdown_sync:
            self._markdown_sync.append_decision(memory)

    def log_error(self, error: str, session_id: str = None):
        """Log an error."""
        if not self.log_errors or not self._synapse:
            return

        if session_id:
            session = self.get_session(session_id)
            if session:
                session.errors_encountered.append(error)

        self._synapse.add(
            content=error,
            memory_type=MemoryType.ERROR,
            tags=["error", "ai"],
            source="auto"
        )

    # =========================================================================
    # MEMORY COMMANDS (for handler integration)
    # =========================================================================

    def handle_memory_search(self, payload: Dict) -> Dict:
        """Handle memory search command."""
        if not self._synapse:
            return {"error": "Memory not available", "results": []}

        query_text = payload.get("query", "")
        limit = payload.get("limit", 20)
        memory_types = payload.get("types", [])

        # Convert type strings to enums
        type_enums = []
        for t in memory_types:
            try:
                type_enums.append(MemoryType(t))
            except ValueError:
                pass

        results = self._synapse.search(query_text, limit=limit)

        return {
            "query": query_text,
            "count": len(results),
            "results": [
                {
                    "id": r.memory.id,
                    "type": r.memory.memory_type.value,
                    "summary": r.memory.summary,
                    "content": r.memory.content,
                    "score": r.score,
                    "tags": r.memory.tags,
                    "created_at": r.memory.created_at
                }
                for r in results
            ]
        }

    def handle_memory_add(self, payload: Dict) -> Dict:
        """Handle memory add command."""
        if not self._synapse:
            return {"error": "Memory not available"}

        content = payload.get("content", "")
        memory_type_str = payload.get("type", "note")
        tags = payload.get("tags", [])
        keywords = payload.get("keywords", [])

        try:
            memory_type = MemoryType(memory_type_str)
        except ValueError:
            memory_type = MemoryType.NOTE

        memory = self._synapse.add(
            content=content,
            memory_type=memory_type,
            tags=tags,
            keywords=keywords,
            source="ai"
        )

        # Living Memory: dual-write to file-based scene memory
        try:
            from ..memory.scene_memory import write_memory_entry, ensure_scene_structure
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                paths = ensure_scene_structure(hip_path, job_path)
                write_memory_entry(paths["scene_dir"], {"content": content}, "note")
        except Exception as e:
            logger.warning("Scene memory dual-write failed: %s", e)

        return {
            "id": memory.id,
            "summary": memory.summary,
            "created": True
        }

    def handle_memory_decide(self, payload: Dict) -> Dict:
        """Handle decision recording."""
        if not self._synapse:
            return {"error": "Memory not available"}

        decision = payload.get("decision", "")
        reasoning = payload.get("reasoning", "")
        alternatives = payload.get("alternatives", [])
        tags = payload.get("tags", [])

        memory = self._synapse.decision(
            decision=decision,
            reasoning=reasoning,
            alternatives=alternatives,
            tags=tags + ["ai_decision"]
        )

        # Sync to markdown
        if self._markdown_sync:
            self._markdown_sync.append_decision(memory)

        # Living Memory: dual-write to file-based scene memory
        try:
            from ..memory.scene_memory import write_decision, ensure_scene_structure
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                paths = ensure_scene_structure(hip_path, job_path)
                scope = "both" if "project" in tags else "scene"
                write_decision(paths["scene_dir"], {
                    "name": decision,
                    "choice": decision,
                    "reasoning": reasoning,
                    "alternatives": alternatives,
                }, scope=scope)
        except Exception as e:
            logger.warning("Scene memory dual-write failed: %s", e)

        return {
            "id": memory.id,
            "summary": memory.summary,
            "recorded": True
        }

    def handle_memory_context(self, payload: Dict) -> Dict:
        """Handle context request -- now includes file-based scene memory."""
        format_type = payload.get("format", "json")

        # Living Memory: merge file-based memory
        file_context = {}
        try:
            from ..memory.scene_memory import load_full_context
            if HOU_AVAILABLE:
                hip_path = hou.hipFile.path()
                hip_dir = os.path.dirname(hip_path)
                job_path = hou.getenv("JOB", hip_dir)
                file_context = load_full_context(hip_dir, job_path)
        except Exception as e:
            logger.warning("Scene memory load failed: %s", e)

        if format_type == "markdown":
            md = self.get_context_markdown()
            if file_context.get("summary"):
                md += "\n\n" + file_context["summary"]
            return {"format": "markdown", "context": md}
        else:
            base_context = self.get_connection_context()
            if file_context:
                base_context["scene_memory"] = file_context.get("summary", "")
                base_context["evolution_stage"] = file_context.get("scene", {}).get("evolution", "none")
            return {"format": "json", "context": base_context}

    def handle_memory_recall(self, payload: Dict) -> Dict:
        """
        Handle recall request - check if we've decided on something before.

        This is for questions like "Did we already decide on rim light color?"
        """
        if not self._synapse:
            return {"error": "Memory not available", "found": False}

        query = payload.get("query", "")

        # Search specifically in decisions
        decisions = self._synapse.get_decisions()

        # Simple keyword matching
        query_lower = query.lower()
        matches = []

        for d in decisions:
            content_lower = d.content.lower()
            summary_lower = d.summary.lower()

            if query_lower in content_lower or query_lower in summary_lower:
                matches.append({
                    "id": d.id,
                    "summary": d.summary,
                    "content": d.content,
                    "date": d.created_at.split("T")[0] if d.created_at else ""
                })

        return {
            "query": query,
            "found": len(matches) > 0,
            "count": len(matches),
            "matches": matches[:5]  # Top 5 matches
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_bridge: Optional[SynapseBridge] = None


def get_bridge() -> SynapseBridge:
    """Get or create the global SynapseBridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = SynapseBridge()
    return _bridge


def reset_bridge():
    """Reset the bridge (e.g., when project changes)."""
    global _bridge
    _bridge = None


# Backwards compatibility
NexusBridge = SynapseBridge
EngramBridge = SynapseBridge
