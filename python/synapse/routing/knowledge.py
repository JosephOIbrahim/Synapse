"""
Synapse Tier 1: Knowledge Index

In-memory knowledge lookup from RAG metadata, reference files, and memory.
No LLM. Runs in <500ms.

Degrades gracefully:
  - With RAG + memory: full coverage
  - With RAG only: no memory search fallback
  - With memory only: no topic/reference lookup
  - With neither: returns not-found (escalates to Tier 2)
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class KnowledgeLookupResult:
    """Result of Tier 1 knowledge lookup."""
    found: bool
    answer: str = ""
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    topic: str = ""
    agent_hint: str = ""


class KnowledgeIndex:
    """
    Tier 1 knowledge lookup engine.

    Loads RAG semantic index + reference files at init time.
    Provides fast in-memory lookup without LLM calls.
    """

    def __init__(
        self,
        rag_root: Optional[str] = None,
        memory: Optional[Any] = None,  # SynapseMemory
    ):
        """
        Args:
            rag_root: Path to RAG system root directory.
            memory: Optional SynapseMemory instance for fallback search.
        """
        self._memory = memory
        self._rag_root = Path(rag_root) if rag_root else None

        # Data stores
        self._semantic_index: Dict[str, Any] = {}
        self._keyword_to_topics: Dict[str, List[str]] = {}
        self._reference_files: Dict[str, str] = {}
        self._agent_relevance: Dict[str, Any] = {}
        # Pre-indexed section headers: word -> [(file_stem, line_index, lines)]
        self._section_index: Dict[str, List[tuple]] = {}

        if self._rag_root:
            self._load_semantic_index()
            self._load_reference_files()
            self._load_agent_relevance()

    def _load_semantic_index(self):
        """Load semantic_index.json and build inverted keyword index.

        Supports two schema formats:
          - SYNAPSE flat: {"topic": {"summary": ..., "keywords": [...]}}
          - HOUDINI21_RAG nested: {"semantic_index": {"topics": {"topic": {...}}}}
        Nested format is auto-detected and normalized to flat.
        """
        assert self._rag_root is not None
        index_path = self._rag_root / "documentation" / "_metadata" / "semantic_index.json"
        if not index_path.exists():
            return

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        # Schema adapter: detect nested format and normalize
        self._semantic_index = self._normalize_semantic_index(raw)

        # Build inverted keyword index: word → [topic_names]
        for topic_name, topic_data in sorted(self._semantic_index.items()):
            keywords = []
            if isinstance(topic_data, dict):
                keywords = topic_data.get("keywords", [])
                # Also index the topic name itself
                keywords = list(keywords) + topic_name.lower().replace("_", " ").split()
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in self._keyword_to_topics:
                    self._keyword_to_topics[kw_lower] = []
                if topic_name not in self._keyword_to_topics[kw_lower]:
                    self._keyword_to_topics[kw_lower].append(topic_name)

    @staticmethod
    def _normalize_semantic_index(raw: dict) -> dict:
        """Normalize nested RAG schema to flat SYNAPSE format.

        Nested format (HOUDINI21_RAG):
            {"semantic_index": {"topics": {"topic_name": {"primary_doc": ..., ...}}}}

        Flat format (SYNAPSE):
            {"topic_name": {"summary": ..., "keywords": [...]}}

        If already flat, returns as-is.
        """
        # Detect nested format: has "semantic_index" key with "topics" inside
        if "semantic_index" in raw and isinstance(raw.get("semantic_index"), dict):
            nested = raw["semantic_index"]
            topics = nested.get("topics", {})
            if isinstance(topics, dict):
                flat: Dict[str, Any] = {}
                for topic_name, topic_data in sorted(topics.items()):
                    if not isinstance(topic_data, dict):
                        continue
                    entry: Dict[str, Any] = {}
                    # Map nested fields to flat equivalents
                    if "primary_doc" in topic_data:
                        entry["summary"] = topic_data["primary_doc"]
                    if "description" in topic_data:
                        entry["description"] = topic_data["description"]
                    elif "primary_doc" in topic_data:
                        entry["description"] = topic_data["primary_doc"]
                    if "keywords" in topic_data:
                        entry["keywords"] = topic_data["keywords"]
                    if "reference_file" in topic_data:
                        entry["reference_file"] = topic_data["reference_file"]
                    # Preserve common_queries for test fixtures
                    if "common_queries" in topic_data:
                        entry["common_queries"] = topic_data["common_queries"]
                    flat[topic_name] = entry
                return flat

        # Already flat format (or unrecognized) — return as-is
        return raw

    def _load_reference_files(self):
        """Load .md reference files from skills directory and pre-index headers."""
        if not self._rag_root:
            return
        ref_dir = self._rag_root / "skills" / "houdini21-reference"
        if not ref_dir.exists():
            return

        for md_file in ref_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                self._reference_files[md_file.stem] = content
            except OSError:
                continue

        # Pre-index section headers for O(1) word lookup
        for file_stem, content in self._reference_files.items():
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if not line.startswith("#"):
                    continue
                header_words = set(line.lstrip("#").strip().lower().split())
                for word in header_words:
                    if word not in self._section_index:
                        self._section_index[word] = []
                    self._section_index[word].append((file_stem, i, lines))

    def _load_agent_relevance(self):
        """Load agent_relevance_map.json if available."""
        if not self._rag_root:
            return
        rel_path = self._rag_root / "documentation" / "_metadata" / "agent_relevance_map.json"
        if not rel_path.exists():
            return
        try:
            with open(rel_path, "r", encoding="utf-8") as f:
                self._agent_relevance = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    def lookup(self, query: str) -> KnowledgeLookupResult:
        """
        Look up knowledge for a query.

        Strategy (first match wins):
        1. Keyword match against inverted index → topic → answer
        2. Section header match in reference files
        3. Memory search fallback
        4. Not found (escalate)
        """
        if not query or not query.strip():
            return KnowledgeLookupResult(found=False)

        query_lower = query.lower().strip()
        query_words = set(self._tokenize(query_lower))

        # Strategy 1: Keyword index match
        result = self._match_keywords(query_words)
        if result:
            return result

        # Strategy 2: Reference file section match
        result = self._match_reference_sections(query_lower, query_words)
        if result:
            return result

        # Strategy 3: VEX symptom diagnosis (natural-language)
        result = self._match_vex_symptoms(query_lower)
        if result:
            return result

        # Strategy 4: Memory fallback
        result = self._match_memory(query)
        if result:
            return result

        return KnowledgeLookupResult(found=False)

    # Module-level constant — avoids re-allocating on every call
    _STOPWORDS = frozenset({
        "what", "is", "the", "a", "an", "how", "do", "i", "to", "in",
        "on", "of", "for", "can", "you", "me", "my", "this", "that",
        "with", "from", "about", "does", "it", "get", "show",
    })

    def _tokenize(self, text: str) -> List[str]:
        """Extract meaningful words from text."""
        words = []
        for word in text.split():
            cleaned = word.strip("?!.,;:'\"")
            if cleaned and cleaned not in self._STOPWORDS and len(cleaned) > 1:
                words.append(cleaned)
        return words

    def _match_keywords(self, query_words: set) -> Optional[KnowledgeLookupResult]:
        """Match query words against inverted keyword index."""
        if not self._keyword_to_topics:
            return None

        # Score topics by keyword overlap with IDF tiebreaker
        # Each match contributes 1.0 (count) + IDF bonus (rare keywords score higher)
        # Count remains the primary signal; IDF disambiguates equal-count ties
        topic_scores: Dict[str, float] = {}
        for word in query_words:
            matching_topics = self._keyword_to_topics.get(word, [])
            idf = 1.0 / len(matching_topics) if matching_topics else 0.0
            for topic in matching_topics:
                topic_scores[topic] = topic_scores.get(topic, 0.0) + 1.0 + idf

        if not topic_scores:
            return None

        # Best topic by overlap count
        best_topic = max(topic_scores, key=lambda k: topic_scores[k])
        best_score = topic_scores[best_topic]

        # Require at least 1 keyword match; confidence scales with overlap
        if best_score < 1:
            return None

        confidence = min(0.9, 0.4 + 0.15 * best_score)
        topic_data = self._semantic_index.get(best_topic, {})

        # Build answer from topic metadata
        answer_parts = []
        if isinstance(topic_data, dict):
            if "summary" in topic_data:
                answer_parts.append(topic_data["summary"])
            if "description" in topic_data:
                answer_parts.append(topic_data["description"])

            # Enrich with reference file content if topic maps to one
            ref_key = topic_data.get("reference_file", best_topic)
            if ref_key in self._reference_files:
                # Include first section (up to 500 chars)
                ref_content = self._reference_files[ref_key][:500]
                answer_parts.append(f"\n---\nReference:\n{ref_content}")

        answer = "\n".join(answer_parts) if answer_parts else f"Topic: {best_topic}"

        # Get agent hint from relevance map
        agent_hint = ""
        if isinstance(self._agent_relevance, dict):
            agent_hint = self._agent_relevance.get(best_topic, "")

        sources = [f"semantic_index:{best_topic}"]

        return KnowledgeLookupResult(
            found=True,
            answer=answer,
            sources=sources,
            confidence=confidence,
            topic=best_topic,
            agent_hint=agent_hint if isinstance(agent_hint, str) else "",
        )

    def _match_reference_sections(
        self, query_lower: str, query_words: set
    ) -> Optional[KnowledgeLookupResult]:
        """Search reference files by section headers using pre-built index."""
        if not self._section_index:
            return None

        # Gather candidate headers from index (only headers with overlapping words)
        candidates: Dict[tuple, int] = {}  # (file_stem, line_idx) -> overlap count
        candidate_lines: Dict[tuple, list] = {}  # (file_stem, line_idx) -> lines ref

        for word in query_words:
            for file_stem, line_idx, lines in self._section_index.get(word, []):
                key = (file_stem, line_idx)
                candidates[key] = candidates.get(key, 0) + 1
                if key not in candidate_lines:
                    candidate_lines[key] = lines

        if not candidates:
            return None

        # Find best match
        best_key = max(candidates, key=lambda k: candidates[k])
        best_score = candidates[best_key]

        if best_score < 1:
            return None

        file_stem, line_idx = best_key
        lines = candidate_lines[best_key]

        # Extract section content (up to next header or 500 chars)
        section_lines = [lines[line_idx]]
        char_count = len(lines[line_idx])
        for j in range(line_idx + 1, len(lines)):
            if lines[j].startswith("#"):
                break
            section_lines.append(lines[j])
            char_count += len(lines[j])
            if char_count > 500:
                break

        confidence = min(0.7, 0.3 + 0.15 * best_score)
        return KnowledgeLookupResult(
            found=True,
            answer="\n".join(section_lines),
            sources=[f"reference:{file_stem}"],
            confidence=confidence,
            topic=file_stem,
        )

    def _match_vex_symptoms(self, query: str) -> Optional[KnowledgeLookupResult]:
        """Match natural-language VEX problem descriptions.

        Uses symptom patterns from vex_diagnostics to catch artist
        descriptions like 'my points aren't moving' or 'colors look wrong'.
        """
        # Quick gate: only try if the query mentions VEX-related concepts
        _VEX_SIGNALS = {
            "vex", "wrangle", "point", "points", "attrib", "attribute",
            "color", "cd", "orient", "pscale", "scale", "noise",
            "pcfind", "solver", "exploding", "slow", "moving",
        }
        query_words = set(query.lower().split())
        if not query_words & _VEX_SIGNALS:
            return None

        try:
            from synapse.routing.vex_diagnostics import (
                diagnose_vex_symptom,
                format_diagnosis,
            )
        except ImportError:
            return None

        diagnoses = diagnose_vex_symptom(query)
        if not diagnoses:
            return None

        formatted = format_diagnosis(diagnoses)
        best = diagnoses[0]
        return KnowledgeLookupResult(
            found=True,
            answer=formatted,
            sources=[f"vex_diagnostics:{best.reference_topic}"],
            confidence=best.confidence,
            topic=best.reference_topic,
            agent_hint=f"VEX symptom match ({best.category})",
        )

    def _match_memory(self, query: str) -> Optional[KnowledgeLookupResult]:
        """Search memory as final fallback."""
        if not self._memory:
            return None

        try:
            results = self._memory.search(text=query, limit=3)
        except Exception:
            return None

        if not results:
            return None

        # Use best result if above threshold
        best = results[0]
        if best.score < 0.4:
            return None

        answer_parts = [best.memory.content]
        if best.memory.summary:
            answer_parts.insert(0, best.memory.summary)

        sources = [f"memory:{best.memory.id}"]
        for r in results[1:]:
            if r.score >= 0.4:
                sources.append(f"memory:{r.memory.id}")

        return KnowledgeLookupResult(
            found=True,
            answer="\n".join(answer_parts),
            sources=sources,
            confidence=min(0.8, best.score),
            topic="memory",
            agent_hint="From project memory",
        )

    @property
    def topic_count(self) -> int:
        """Number of indexed topics."""
        return len(self._semantic_index)

    @property
    def reference_count(self) -> int:
        """Number of loaded reference files."""
        return len(self._reference_files)

    def stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            "topics": self.topic_count,
            "keywords": len(self._keyword_to_topics),
            "references": self.reference_count,
            "has_memory": self._memory is not None,
            "has_rag": self._rag_root is not None,
        }
