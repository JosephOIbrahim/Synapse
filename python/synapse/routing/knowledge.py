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
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# W4-KNOW Target 3: default result count for the node/disambiguation path. Mirrors
# the MCP tool schema default so lookup(query, k=...) and the tool agree.
DEFAULT_K = 6

# W4-KNOW Target 6: similarity floor on the fuzzy ("dense") retrieval paths. Below
# it, a weak section/keyword/memory match is NOT served as a confident answer -
# lookup returns found=False instead of confident-wrong. The exact-match node path
# is exempt (it is not a similarity match). Overridable per call via
# lookup(min_similarity=...). Calibrated so the shipped keyword topics (>=0.55) and
# the COMMON_QUERIES suite clear it, while single-header section hits (0.45) and
# weak memory hits do not.
DENSE_MATCH_FLOOR = 0.5

# W4-KNOW Target 7: the running Houdini build, host-injected when hou is importable
# (mirrors scout.EXPECTED_HOUDINI_VERSION). None => fall back to the HOUDINI_VERSION
# environment variable. Used to compare the served corpus build stamp against the
# build the process is actually running on, and to stamp the agent_hint - so the
# hint reports the corpus's OWN build, never a hardcoded literal.
EXPECTED_HOUDINI_VERSION: Optional[str] = None


@dataclass
class KnowledgeLookupResult:
    """Result of Tier 1 knowledge lookup."""
    found: bool
    answer: str = ""
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    topic: str = ""
    agent_hint: str = ""
    summary: str = ""
    reference_file: str = ""
    # W4-KNOW Target 2: bare-type queries that span >1 context return the
    # candidates here instead of a silent _CONTEXT_RANK pick. Each item is
    # {"context", "type", "label"}. Empty on an unambiguous answer.
    disambiguation: List[Dict[str, str]] = field(default_factory=list)
    # W4-KNOW Target 5: the full, UNCAPPED parameter surface for a node answer -
    # each item carries the internal name(s) and channel(s) needed to actually set
    # the parm: {"label", "ids": [...], "channels": [...], "description"}.
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    # The corpus context this answer came from ("cop"/"lop"/...); "" for prose.
    context: str = ""
    # W4-KNOW Target 5 (serve-size honesty): the measured byte size of this
    # response's answer + parameters payload. Reported, never estimated.
    serve_bytes: int = 0


class KnowledgeIndex:
    """
    Tier 1 knowledge lookup engine.

    Loads RAG semantic index + reference files at init time.
    Provides fast in-memory lookup without LLM calls.
    """

    # Which context sorts FIRST when one node-type name exists in several.
    # cop is Copernicus (current); cop2 is the legacy image context it replaced.
    # W4-KNOW Target 2: this rank NO LONGER makes a silent pick. A bare-type query
    # that spans >1 context returns a DISAMBIGUATION list; the rank only orders
    # that list so the current context is presented first. Unranked => 0 => last.
    _CONTEXT_RANK = {"cop": 3, "lop": 3, "sop": 3, "out": 2, "top": 2, "cop2": 1}

    # W4-KNOW Target 4: intent markers that promote a longer, sentence-shaped
    # query to the node path. The 2-token bail this replaces sent every node
    # QUESTION (>2 tokens) to the H21 prose index, which answered found=True from
    # five-year-old material (40/40 wrong in the recon). A query routes to the
    # node path when it names a live node type AND carries node intent: the literal
    # word "node", or a context word alongside an interrogative. When it does route
    # and finds nothing, it returns honest not-found - it never falls through to
    # prose. A bare type name (<=2 tokens) still routes, as before.
    _NODE_MARKERS = frozenset({"node", "nodes"})
    _CONTEXT_WORDS = frozenset({
        "cop", "cops", "copernicus", "sop", "sops", "lop", "lops", "solaris",
        "vop", "vops", "chop", "chops", "top", "tops", "dop", "dops",
        "rop", "rops", "out",
    })
    # Checked against the RAW (pre-stopword) query words - the tokenizer strips
    # most of these, and a node QUESTION is exactly what carries them.
    _INTERROGATIVE = frozenset({
        "how", "what", "which", "where", "why", "when", "who",
        "does", "do", "is", "are", "can", "should", "will",
    })
    # A context word in the query (or an explicit context= param) resolves to a
    # corpus context. "copernicus" is the artist's word for the cop context.
    _CONTEXT_WORD_TO_CTX = {
        "copernicus": "cop", "cop": "cop", "cops": "cop", "cop2": "cop2",
        "solaris": "lop", "lop": "lop", "lops": "lop",
        "sop": "sop", "sops": "sop", "vop": "vop", "vops": "vop",
        "chop": "chop", "chops": "chop", "top": "top", "tops": "top",
        "dop": "dop", "dops": "dop", "rop": "rop", "rops": "rop", "out": "out",
    }

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
        # H22 node corpus, keyed (context, type) - W4-KNOW Target 2. First entry
        # wins per pair (9 same-context pyro dupes in the source).
        self._h22_nodes: Dict[Tuple[str, str], Any] = {}
        # type name -> [(context, entry), ...] ordered current-context-first, for
        # bare-type disambiguation and single-context resolution.
        self._h22_by_type: Dict[str, List[Tuple[str, Any]]] = {}
        # The build stamp the served node corpus was extracted against (Target 7).
        self._corpus_build: Optional[str] = None
        # (corpus_build, live_build) when they disagree; None when they match or
        # no live build is known. Exposed via stats() for the release gate.
        self._corpus_build_mismatch: Optional[Tuple[str, str]] = None

        if self._rag_root:
            self._load_semantic_index()
            self._load_reference_files()
            self._load_agent_relevance()
            self._load_h22_nodes()

    def _load_h22_nodes(self):
        """Load the H22 node corpus, keyed (context, type) - W4-KNOW Target 2.

        The prose corpus under skills/ is Houdini 21 material (R119) - accurate,
        labelled, and predating Copernicus, which is why COP grounding measured
        6.2% against a subsystem that barely existed then.

        This corpus is different in kind. Every entry was extracted from
        nodes.zip - the reference that SHIPS WITH THE BUILD, version-pinned by
        construction (the `build` field) - and then validated by probing its
        documented type against the running catalogue. Only matched entries are
        written to the artifact, so a phantom type cannot be served because it
        was never stored (see rag/corpus/h22_nodes.json's `gate` field).

        The OLD key was the bare type name, deduped by _CONTEXT_RANK so cop won
        over cop2 - a SILENT pick that hid the legacy entry entirely. 42 types
        span >1 context. Keying (context, type) keeps every context's entry, and
        _match_h22_node returns a disambiguation list rather than picking one.

        Target 7: the corpus carries a build stamp; on load we compare it to the
        build this process is running on and warn LOUDLY on a mismatch (scout is
        loud on the same drift; this closes the silent-staleness gap). We still
        load - this is the graceful tier - but the mismatch is recorded and the
        agent_hint reports the corpus's own build, not a hardcoded literal.

        Never raises: a missing or malformed corpus leaves the maps empty and
        every other retrieval strategy is unaffected.
        """
        path = self._rag_root / "corpus" / "h22_nodes.json"
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return

        self._corpus_build = blob.get("build")
        self._check_corpus_build_stamp(path)

        for entry in blob.get("entries") or []:
            t = entry.get("type")
            if not t:
                continue
            ntype = str(t).lower()
            ctx = str(entry.get("context") or "")
            key = (ctx, ntype)
            if key not in self._h22_nodes:            # first wins per (context, type)
                self._h22_nodes[key] = entry
                self._h22_by_type.setdefault(ntype, []).append((ctx, entry))

        # Order each type's contexts current-first, so a disambiguation list and
        # a single-context resolution both present the live context ahead of legacy.
        for ntype, cands in self._h22_by_type.items():
            cands.sort(key=lambda ce: self._CONTEXT_RANK.get(ce[0], 0), reverse=True)

    def _check_corpus_build_stamp(self, path) -> None:
        """W4-KNOW Target 7: warn loudly when the served corpus was extracted
        against a different build than the one this process is running on.

        Defines the build-stamp contract W4-GUARD's release gate consumes: the
        corpus `build` field vs the live build (host-injected EXPECTED_HOUDINI_VERSION,
        else the HOUDINI_VERSION env). No live build known (CI / stock python) =>
        nothing to compare against => silent, never a false alarm. This is the
        runtime half; the release-blocking half lives in harness/verify/checks.py."""
        live = self._live_build()
        stamp = self._corpus_build
        if not live or not stamp or stamp == live:
            return
        self._corpus_build_mismatch = (str(stamp), str(live))
        warnings.warn(
            "SYNAPSE knowledge corpus build mismatch: %s was extracted against "
            "Houdini %s but this process is running Houdini %s. Node datasheets "
            "may be stale (renamed/removed types, drifted parms). Regenerate the "
            "corpus on the target build via harness/notes/rag_promote_h22.py."
            % (path, stamp, live),
            RuntimeWarning, stacklevel=2,
        )

    @staticmethod
    def _live_build() -> str:
        """The running Houdini build: host-injected first, then the HOUDINI_VERSION
        env (host-agnostic, mirrors scout._env_running_build). "" outside Houdini."""
        return (str(EXPECTED_HOUDINI_VERSION or "").strip()
                or str(os.environ.get("HOUDINI_VERSION") or "").strip())

    def _node_type_tokens(self, query_words) -> List[str]:
        """The query words that name a live node type in the corpus."""
        return [w for w in query_words if w in self._h22_by_type]

    def _has_node_intent(self, type_tokens, query_words, raw_query,
                         context) -> bool:
        """W4-KNOW Target 4: does this query WANT the node path?

        Requires a live type token (else there is nothing to answer from the node
        corpus). Given one, node intent fires when any hold:
          * the caller passed an explicit context (they are asking about a node),
          * the query is short (<=2 meaningful tokens) - the bare-type case,
          * the literal word "node"/"nodes" appears, or
          * a context word appears AND the query is interrogative.
        A keyword-bag topic query that merely CONTAINS a type name ("vex attribute
        wrangle", "tops wedge parameter sweep") matches none of these and falls
        through to the topic index unchanged."""
        if not type_tokens:
            return False
        if context:
            return True
        if len(query_words) <= 2:
            return True
        raw_words = set(raw_query.lower().split())
        if raw_words & self._NODE_MARKERS:
            return True
        if (raw_words & self._CONTEXT_WORDS) and (raw_words & self._INTERROGATIVE):
            return True
        return False

    def _normalize_context(self, value) -> Optional[str]:
        """Normalize a caller-supplied context to a corpus context id, mapping
        the artist word ("copernicus" -> cop). An unrecognized value passes
        through lowercased (so a future context filters itself); "" -> None."""
        v = str(value or "").lower().strip()
        if not v:
            return None
        return self._CONTEXT_WORD_TO_CTX.get(v, v)

    def _infer_context(self, raw_query, type_tokens) -> Optional[str]:
        """Infer a single context from a context word in the query ("...in
        copernicus" -> cop). Returns that context even when it does NOT hold the
        named type - so a Copernicus question about a type that only exists in the
        legacy cop2 context resolves to honest not-found, NOT to the legacy node
        (the exact confident-wrong case the recon caught). Zero or >1 distinct
        context words -> None (bare-type disambiguation)."""
        raw_words = set(raw_query.lower().split())
        ctxs = {self._CONTEXT_WORD_TO_CTX[w] for w in raw_words
                if w in self._CONTEXT_WORD_TO_CTX}
        return next(iter(ctxs)) if len(ctxs) == 1 else None

    def _match_h22_node(self, query_words, raw_query, context, k):
        """The node path. Returns:
          * a datasheet result   - an unambiguous node answer,
          * a disambiguation result - a bare type spanning >1 context,
          * a found=False result - node intent fired but nothing matched
                                    (honest not-found; caller must NOT fall
                                     through to prose - Target 4), or
          * None - not a node query; fall through to the topic index.
        """
        type_tokens = self._node_type_tokens(query_words)
        if not self._has_node_intent(type_tokens, query_words, raw_query, context):
            return None

        # Resolve the context filter: an explicit context= param (normalized -
        # "copernicus" -> cop) wins; otherwise infer it from a context word in the
        # query ("...in copernicus" -> cop) so a named node question resolves to
        # one datasheet instead of a disambiguation. Inference only narrows among
        # the named type's own contexts and only runs after node intent fired, so
        # it can never redirect a topic query.
        ctx = self._normalize_context(context) if context else None
        if ctx is None:
            ctx = self._infer_context(raw_query, type_tokens)

        # Gather candidate (context, type, entry) across every named type,
        # filtered by an explicit/inferred context when one was resolved.
        matched: List[Tuple[str, str, Any]] = []
        seen_keys = set()
        for ntype in type_tokens:
            for cand_ctx, entry in self._h22_by_type.get(ntype, []):
                if ctx and cand_ctx != ctx:
                    continue
                key = (cand_ctx, ntype)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                matched.append((cand_ctx, ntype, entry))

        if not matched:
            # Node intent, but no entry (e.g. context=cop for a cop2-only type,
            # or a type absent on this build). Honest not-found - do NOT let the
            # sentence fall through to five-year-old prose (Target 4).
            return KnowledgeLookupResult(found=False)

        if len(matched) == 1:
            cand_ctx, ntype, entry = matched[0]
            return self._node_datasheet(entry, cand_ctx)

        return self._disambiguation_result(matched, k)

    def _node_datasheet(self, entry, ctx) -> KnowledgeLookupResult:
        """A single node's datasheet with UNCAPPED internal parm names + channels
        (W4-KNOW Target 5). The old path returned only the first 12 LABELS - 51%
        of entries exceed 12 params, and a label alone cannot set a parm. Here
        every parameter carries its internal id(s) and channel(s)."""
        params: List[Dict[str, Any]] = []
        for p in (entry.get("parameters") or []):
            if not isinstance(p, dict):
                continue
            ids = [str(x) for x in (p.get("ids") or []) if x]
            channels = [str(x) for x in (p.get("channels") or []) if x]
            params.append({
                "label": p.get("label") or p.get("name") or "",
                "ids": ids,
                "channels": channels,
                "description": p.get("description") or "",
            })

        lines = []
        for p in params:
            setter = ", ".join(p["ids"]) if p["ids"] else "(no internal name)"
            line = "- %s -> set: %s" % (p["label"] or "(unlabelled)", setter)
            if p["channels"]:
                line += "  channels: %s" % ", ".join(p["channels"])
            lines.append(line)

        summary = entry.get("summary") or ""
        answer = summary
        if params:
            answer = "%s\n\nParameters (%d) - internal name(s) to set each:\n%s" % (
                summary, len(params), "\n".join(lines))

        build = self._corpus_build or "?"
        result = KnowledgeLookupResult(
            found=True,
            answer=answer,
            confidence=0.95,
            topic=entry.get("label") or entry.get("type") or "",
            sources=[entry.get("source") or entry.get("help_key") or ""],
            agent_hint="VERIFIED-DOC, Houdini %s, %s context" % (build, ctx or "?"),
            summary=summary,
            reference_file=entry.get("help_key") or "",
            parameters=params,
            context=ctx or "",
        )
        result.serve_bytes = self._measure_serve_bytes(result)
        return result

    def _disambiguation_result(self, matched, k) -> KnowledgeLookupResult:
        """W4-KNOW Target 2: a bare type spanning >1 context returns the candidates
        to choose from - never a silent pick. Ordered current-context-first."""
        matched = matched[:max(1, int(k or DEFAULT_K))]
        disambiguation = [{
            "context": c,
            "type": t,
            "label": str(e.get("label") or t),
        } for (c, t, e) in matched]
        ntype = matched[0][1]
        contexts = ", ".join(d["context"] for d in disambiguation)
        answer = (
            "'%s' names a node in more than one context: %s. Re-ask with "
            "context=<one of these> to get its datasheet. Candidates:\n%s" % (
                ntype, contexts,
                "\n".join("- %s/%s  (%s)" % (d["context"], d["type"], d["label"])
                          for d in disambiguation)))
        result = KnowledgeLookupResult(
            found=True,
            answer=answer,
            confidence=0.6,
            topic=ntype,
            sources=[],
            agent_hint="DISAMBIGUATION - bare type '%s' spans %d contexts (%s)"
                       % (ntype, len(disambiguation), contexts),
            summary=answer.split("\n", 1)[0],
            disambiguation=disambiguation,
        )
        result.serve_bytes = self._measure_serve_bytes(result)
        return result

    @staticmethod
    def _measure_serve_bytes(result) -> int:
        """Measured (not estimated) byte size of the answer + parameters payload
        this response carries - Target 5 serve-size honesty."""
        payload = json.dumps({
            "answer": result.answer,
            "parameters": result.parameters,
            "disambiguation": result.disambiguation,
        }, ensure_ascii=False)
        return len(payload.encode("utf-8"))

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

        # Pre-compute IDF values (avoids per-query division)
        self._keyword_idf: Dict[str, float] = {
            word: 1.0 / len(topics) if topics else 0.0
            for word, topics in self._keyword_to_topics.items()
        }

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

    def lookup(self, query: str, context: Optional[str] = None,
               k: int = DEFAULT_K,
               min_similarity: Optional[float] = None) -> KnowledgeLookupResult:
        """
        Look up knowledge for a query.

        Args (W4-KNOW Target 3):
            query:   natural-language need or a node type to look up.
            context: restrict the node path to one context ("cop"/"lop"/...). When
                     given, a bare type resolves to exactly that context's entry.
            k:       max candidates in a disambiguation list.
            min_similarity: override the fuzzy-path floor (default DENSE_MATCH_FLOOR).

        Strategy (first match wins):
        0. Node path (exclusive): if the query wants a node (Target 4), answer it
           from the (context, type) corpus, return a disambiguation list for an
           ambiguous bare type (Target 2), or return honest not-found - it NEVER
           falls through to prose.
        1. Keyword match against inverted index → topic → answer
        2. Section header match in reference files
        3. VEX symptom diagnosis
        4. Memory search fallback
        5. Not found (escalate)

        A fuzzy match below the similarity floor is dropped rather than served as
        confident-wrong (Target 6): out-of-corpus → found=False, not a weak guess.
        """
        if not query or not query.strip():
            return KnowledgeLookupResult(found=False)

        query_lower = query.lower().strip()
        query_words = set(self._tokenize(query_lower))
        floor = DENSE_MATCH_FLOOR if min_similarity is None else float(min_similarity)

        # Strategy 0: the node path. EXCLUSIVE - when it owns the query it returns
        # its verdict (answer, disambiguation, or honest not-found) and the
        # sentence never falls through to H21 prose. None means "not a node query".
        node = self._match_h22_node(query_words, query_lower, context, k)
        if node is not None:
            return node

        # Strategies 1-4: fuzzy retrieval, each gated by the similarity floor.
        result = self._match_keywords(query_words)
        if result and result.confidence >= floor:
            return result

        result = self._match_reference_sections(query_lower, query_words)
        if result and result.confidence >= floor:
            return result

        result = self._match_vex_symptoms(query_lower)
        if result and result.confidence >= floor:
            return result

        result = self._match_memory(query)
        if result and result.confidence >= floor:
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
            idf = self._keyword_idf.get(word, 0.0)
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

        # Extract discrete metadata for structured response
        summary = ""
        ref_file = ""
        if isinstance(topic_data, dict):
            summary = topic_data.get("summary", "")
            ref_file = topic_data.get("reference_file", "")

        return KnowledgeLookupResult(
            found=True,
            answer=answer,
            sources=sources,
            confidence=confidence,
            topic=best_topic,
            agent_hint=agent_hint if isinstance(agent_hint, str) else "",
            summary=summary,
            reference_file=ref_file,
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
            reference_file=file_stem,
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
        """Return index statistics.

        ``corpus_build`` + ``corpus_build_mismatch`` are the build-stamp contract
        W4-GUARD's release gate reads (Target 7): mismatch is (corpus_build,
        live_build) when they disagree, else None."""
        return {
            "topics": self.topic_count,
            "keywords": len(self._keyword_to_topics),
            "references": self.reference_count,
            "has_memory": self._memory is not None,
            "has_rag": self._rag_root is not None,
            "h22_nodes": len(self._h22_nodes),
            "h22_types": len(self._h22_by_type),
            "corpus_build": self._corpus_build,
            "corpus_build_mismatch": self._corpus_build_mismatch,
        }
