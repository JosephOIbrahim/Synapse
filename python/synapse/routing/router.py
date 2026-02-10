"""
Synapse Tiered Router

Dispatches each input to the fastest capable handler.
LLM calls are reserved for the ~20% that genuinely need reasoning.

Cascade: Cache → Recipe → Tier0 → Tier1 → Tier2 → Tier3
"""

import hashlib
import json
import time
import threading
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

from ..core.protocol import SynapseCommand, SynapseResponse
from ..core.gates import HumanGate, GateLevel
from ..core.determinism import deterministic_uuid
from ..memory.store import SynapseMemory

from .parser import CommandParser, ParseResult
from .knowledge import KnowledgeIndex, KnowledgeLookupResult
from .recipes import RecipeRegistry, Recipe
from .cache import ResponseCache

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class RoutingTier(Enum):
    """Which tier handled the request."""
    CACHE = "cache"
    RECIPE = "recipe"
    INSTANT = "instant"    # Tier 0
    FAST = "fast"          # Tier 1
    STANDARD = "standard"  # Tier 2
    DEEP = "deep"          # Tier 3


@dataclass
class RoutingResult:
    """Result of routing a request through the cascade."""
    success: bool
    tier: RoutingTier
    answer: str = ""
    commands: List[SynapseCommand] = field(default_factory=list)
    responses: List[SynapseResponse] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False
    async_handle: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """Configuration for the tiered router."""
    # Tier toggles
    enable_tier0: bool = True
    enable_tier1: bool = True
    enable_tier2: bool = True
    enable_tier3: bool = True
    enable_recipes: bool = True
    enable_cache: bool = True

    # Knowledge
    rag_root: Optional[str] = None

    # Confidence thresholds
    tier0_confidence: float = 0.8
    tier1_confidence: float = 0.5

    # LLM config
    llm_api_key: Optional[str] = None
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_deep: str = "claude-sonnet-4-5-20250929"
    tier2_timeout: float = 5.0
    tier3_timeout: float = 15.0
    tier3_async: bool = True

    # Cache config
    cache_max_size: int = 500
    cache_ttl: int = 3600

    # Float precision for canonicalization
    float_precision: int = 6


# Fixed system prompt for Tier 2 (enables Anthropic prefix caching)
_TIER2_SYSTEM_PROMPT = """\
You are Synapse, an AI assistant for Houdini VFX artists.
You help with node creation, parameter adjustment, scene setup, and workflow optimization.

Respond in structured JSON with these fields:
- action: "command" | "answer" | "clarify"
- command_type: CommandType value if action is "command" (e.g. "create_node", "set_parm")
- payload: command payload dict if action is "command"
- answer: text answer if action is "answer" or "clarify"
- confidence: 0.0-1.0
- reasoning: brief explanation of your approach
"""


_MAX_TIER_PINS = 1000

# Shared pool for speculative T0+T1 parallelism (avoids per-call thread creation)
_tier_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synapse-tier")


class TieredRouter:
    """
    Tiered routing cascade.

    Routes artist input through increasingly capable (and slower) tiers
    until one handles it with sufficient confidence.
    """

    def __init__(
        self,
        command_fn: Optional[Callable[[SynapseCommand], SynapseResponse]] = None,
        memory: Optional[SynapseMemory] = None,
        gate: Optional[HumanGate] = None,
        config: Optional[RoutingConfig] = None,
    ):
        self._command_fn = command_fn
        self._memory = memory
        self._gate = gate
        self._config = config or RoutingConfig()

        # Initialize tiers
        self._parser = CommandParser()
        self._knowledge = KnowledgeIndex(
            rag_root=self._config.rag_root,
            memory=memory,
        )
        self._recipes = RecipeRegistry()
        self._cache = ResponseCache(
            max_size=self._config.cache_max_size,
            ttl_seconds=self._config.cache_ttl,
        )

        # Tier-pinning cache: canonical_key → tier value (He2025 consistency)
        self._tier_pins: Dict[str, str] = {}

        # Metrics
        self._tier_counts: Dict[str, int] = {t.value: 0 for t in RoutingTier}
        self._tier_latencies: Dict[str, List[float]] = {t.value: [] for t in RoutingTier}
        self._total_routes = 0

        # Async handles for Tier 3
        self._async_results: Dict[str, RoutingResult] = {}
        self._async_lock = threading.Lock()

        # LLM client (lazy-initialized)
        self._llm_client = None

    def route(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoutingResult:
        """
        Route input through the tier cascade.

        Args:
            input_text: Artist's natural language input.
            context: Optional context dict (scene state, shot info, etc.)

        Returns:
            RoutingResult with the tier that handled the request.
        """
        start = time.monotonic()
        context = context or {}
        context_hash = self._hash_context(context)

        # ---------------------------------------------------------------
        # -1. Tier-pin check (He2025 consistency)
        # ---------------------------------------------------------------
        pin_key = f"{input_text}|{context_hash}"
        pinned_tier = self._tier_pins.get(pin_key)

        # ---------------------------------------------------------------
        # 0. Cache check (He2025)
        # ---------------------------------------------------------------
        if self._config.enable_cache:
            for tier_name in ("recipe", "instant", "fast", "standard", "deep"):
                cached = self._cache.get(tier_name, input_text, context_hash)
                if cached is not None:
                    result = RoutingResult(
                        success=cached.success,
                        tier=cached.tier,
                        answer=cached.answer,
                        commands=cached.commands,
                        responses=cached.responses,
                        confidence=cached.confidence,
                        latency_ms=(time.monotonic() - start) * 1000,
                        cached=True,
                        metadata={"original_tier": cached.tier.value},
                    )
                    self._record_metric(RoutingTier.CACHE, result.latency_ms)
                    return result

        # ---------------------------------------------------------------
        # 0.5. Pinned-tier fast path (He2025: same input → same tier)
        # ---------------------------------------------------------------
        if pinned_tier:
            result = self._try_pinned_tier(
                pinned_tier, input_text, context, context_hash, start
            )
            if result:
                return result
            # Stale pin — tier returned None; delete and fall through
            self._tier_pins.pop(pin_key, None)

        # ---------------------------------------------------------------
        # 1. Recipe match
        # ---------------------------------------------------------------
        if self._config.enable_recipes:
            result = self._try_recipe(input_text, context_hash, start)
            if result:
                return result

        # ---------------------------------------------------------------
        # 2+3. Tier 0 (regex) + Tier 1 (knowledge) — speculative parallel
        # ---------------------------------------------------------------
        tier1_hint: Optional[KnowledgeLookupResult] = None
        need_knowledge = (
            self._config.enable_tier1
            or self._config.enable_tier2
            or self._config.enable_tier3
        )

        if self._config.enable_tier0 and need_knowledge:
            # Run T0 and knowledge lookup concurrently
            t0_future = _tier_pool.submit(self._try_tier0, input_text, context_hash, start)
            t1_lookup_future = _tier_pool.submit(self._knowledge.lookup, input_text)

            t0_result = t0_future.result()
            tier1_hint = t1_lookup_future.result()

            if t0_result:
                return t0_result
        elif self._config.enable_tier0:
            result = self._try_tier0(input_text, context_hash, start)
            if result:
                return result
        elif need_knowledge:
            tier1_hint = self._knowledge.lookup(input_text)

        if self._config.enable_tier1 and tier1_hint:
            result = self._try_tier1(tier1_hint, input_text, context_hash, start)
            if result:
                return result

        # ---------------------------------------------------------------
        # 4. Tier 2: Haiku LLM (with Tier 1 partial context)
        # ---------------------------------------------------------------
        if self._config.enable_tier2 and self._config.llm_api_key:
            result = self._try_tier2(
                input_text, context, context_hash, start, tier1_hint
            )
            if result:
                return result

        # ---------------------------------------------------------------
        # 5. Tier 3: Full agent (with Tier 1 partial context)
        # ---------------------------------------------------------------
        if self._config.enable_tier3 and self._config.llm_api_key:
            result = self._try_tier3(
                input_text, context, context_hash, start, tier1_hint
            )
            if result:
                return result

        # ---------------------------------------------------------------
        # Fallback: nothing handled it
        # ---------------------------------------------------------------
        return RoutingResult(
            success=False,
            tier=RoutingTier.DEEP,
            answer="I couldn't understand that request. Could you rephrase?",
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={"reason": "no_tier_matched"},
        )

    # ------------------------------------------------------------------
    # Tier implementations
    # ------------------------------------------------------------------

    def _try_recipe(
        self, text: str, context_hash: str, start: float
    ) -> Optional[RoutingResult]:
        """Try recipe match."""
        match = self._recipes.match(text)
        if match is None:
            return None

        recipe, params = match
        commands = recipe.instantiate(params)

        # Execute if command_fn available
        responses = []
        if self._command_fn:
            for cmd in commands:
                try:
                    resp = self._command_fn(cmd)
                    responses.append(resp)
                except Exception as e:
                    responses.append(SynapseResponse(
                        id=cmd.id, success=False, error=str(e),
                    ))

        result = RoutingResult(
            success=True,
            tier=RoutingTier.RECIPE,
            answer=f"Executed recipe '{recipe.name}' ({len(commands)} steps)",
            commands=commands,
            responses=responses,
            confidence=0.95,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={"recipe": recipe.name, "params": params},
        )

        self._cache_result("recipe", text, context_hash, result)
        self._pin_tier(text, context_hash, RoutingTier.RECIPE.value)
        self._record_metric(RoutingTier.RECIPE, result.latency_ms)
        return result

    def _try_tier0(
        self, text: str, context_hash: str, start: float
    ) -> Optional[RoutingResult]:
        """Try Tier 0 regex parse."""
        parse = self._parser.parse(text)
        if not parse.matched or parse.confidence < self._config.tier0_confidence:
            return None

        # Execute if command_fn available
        responses = []
        if self._command_fn and parse.command:
            try:
                resp = self._command_fn(parse.command)
                responses.append(resp)
            except Exception as e:
                responses.append(SynapseResponse(
                    id=parse.command.id, success=False, error=str(e),
                ))

        result = RoutingResult(
            success=True,
            tier=RoutingTier.INSTANT,
            answer=f"Parsed as {parse.pattern_name}",
            commands=[parse.command] if parse.command else [],
            responses=responses,
            confidence=parse.confidence,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={
                "pattern": parse.pattern_name,
                "extracted": parse.extracted,
            },
        )

        self._cache_result("instant", text, context_hash, result)
        self._pin_tier(text, context_hash, RoutingTier.INSTANT.value)
        self._record_metric(RoutingTier.INSTANT, result.latency_ms)
        return result

    def _try_tier1(
        self,
        lookup: KnowledgeLookupResult,
        text: str,
        context_hash: str,
        start: float,
    ) -> Optional[RoutingResult]:
        """Try Tier 1 knowledge lookup (uses pre-computed result)."""
        if not lookup.found or lookup.confidence < self._config.tier1_confidence:
            return None

        result = RoutingResult(
            success=True,
            tier=RoutingTier.FAST,
            answer=lookup.answer,
            confidence=lookup.confidence,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={
                "topic": lookup.topic,
                "sources": lookup.sources,
                "agent_hint": lookup.agent_hint,
            },
        )

        self._cache_result("fast", text, context_hash, result)
        self._pin_tier(text, context_hash, RoutingTier.FAST.value)
        self._record_metric(RoutingTier.FAST, result.latency_ms)
        return result

    def _pin_tier(self, input_text: str, context_hash: str, tier_value: str):
        """Record a tier pin for future consistency."""
        pin_key = f"{input_text}|{context_hash}"
        self._tier_pins[pin_key] = tier_value
        if len(self._tier_pins) > _MAX_TIER_PINS:
            # Evict oldest (dict is insertion-ordered in Python 3.7+)
            self._tier_pins.pop(next(iter(self._tier_pins)))

    def _try_pinned_tier(
        self,
        tier_value: str,
        text: str,
        context: Dict,
        context_hash: str,
        start: float,
    ) -> Optional[RoutingResult]:
        """Re-execute the pinned tier directly."""
        if tier_value == RoutingTier.RECIPE.value and self._config.enable_recipes:
            return self._try_recipe(text, context_hash, start)
        if tier_value == RoutingTier.INSTANT.value and self._config.enable_tier0:
            return self._try_tier0(text, context_hash, start)
        if tier_value == RoutingTier.FAST.value and self._config.enable_tier1:
            hint = self._knowledge.lookup(text)
            if hint:
                return self._try_tier1(hint, text, context_hash, start)
        if tier_value == RoutingTier.STANDARD.value and self._config.enable_tier2:
            hint = self._knowledge.lookup(text)
            return self._try_tier2(text, context, context_hash, start, hint)
        if tier_value == RoutingTier.DEEP.value and self._config.enable_tier3:
            hint = self._knowledge.lookup(text)
            return self._try_tier3(text, context, context_hash, start, hint)
        return None

    def _try_tier2(
        self,
        text: str,
        context: Dict,
        context_hash: str,
        start: float,
        tier1_hint: Optional[KnowledgeLookupResult] = None,
    ) -> Optional[RoutingResult]:
        """Try Tier 2: Haiku LLM with fixed system prompt."""
        try:
            client = self._get_llm_client()
            if client is None:
                return None

            # Build user message with optional RAG context
            user_parts = []

            # Include Tier 1 knowledge as enrichment (even if below T1 threshold)
            if tier1_hint and tier1_hint.found:
                user_parts.append(
                    f"<context source=\"tier1\" confidence=\"{tier1_hint.confidence:.2f}\">\n"
                    f"{tier1_hint.answer}\n</context>\n"
                )

            # Include memory context
            if self._memory:
                try:
                    recent = self._memory.search(text=text, limit=3)
                    if recent:
                        mem_parts = [
                            f"- {r.memory.summary or r.memory.content[:100]}"
                            for r in recent
                        ]
                        user_parts.append(
                            f"<memory>\n" + "\n".join(mem_parts) + "\n</memory>\n"
                        )
                except Exception:
                    pass

            user_parts.append(text)
            user_message = "\n".join(user_parts)

            response = client.messages.create(
                model=self._config.llm_model_fast,
                max_tokens=1024,
                system=_TIER2_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Parse structured response
            raw_text = response.content[0].text
            parsed = self._parse_llm_response(raw_text)

            commands = []
            responses = []
            answer = parsed.get("answer", raw_text)

            if parsed.get("action") == "command" and parsed.get("command_type"):
                cmd = SynapseCommand(
                    type=parsed["command_type"],
                    id=uuid.uuid4().hex[:16],
                    payload=parsed.get("payload", {}),
                )
                commands.append(cmd)
                if self._command_fn:
                    try:
                        resp = self._command_fn(cmd)
                        responses.append(resp)
                    except Exception as e:
                        responses.append(SynapseResponse(
                            id=cmd.id, success=False, error=str(e),
                        ))

            tier2_meta = {
                "model": self._config.llm_model_fast,
                "reasoning": parsed.get("reasoning", ""),
                "action": parsed.get("action", "answer"),
            }
            if tier1_hint and tier1_hint.found:
                tier2_meta["tier1_enrichment"] = {
                    "topic": tier1_hint.topic,
                    "confidence": tier1_hint.confidence,
                    "sources": tier1_hint.sources,
                }

            result = RoutingResult(
                success=True,
                tier=RoutingTier.STANDARD,
                answer=answer,
                commands=commands,
                responses=responses,
                confidence=parsed.get("confidence", 0.7),
                latency_ms=(time.monotonic() - start) * 1000,
                metadata=tier2_meta,
            )

            self._cache_result("standard", text, context_hash, result)
            self._pin_tier(text, context_hash, RoutingTier.STANDARD.value)
            self._record_metric(RoutingTier.STANDARD, result.latency_ms)
            return result

        except Exception as e:
            logger.warning("Tier 2 failed: %s", e)
            return None

    def _try_tier3(
        self,
        text: str,
        context: Dict,
        context_hash: str,
        start: float,
        tier1_hint: Optional[KnowledgeLookupResult] = None,
    ) -> Optional[RoutingResult]:
        """Try Tier 3: Full agent loop (async or sync)."""
        handle = uuid.uuid4().hex[:16]

        if self._config.tier3_async:
            # Launch in background thread
            thread = threading.Thread(
                target=self._tier3_worker,
                args=(handle, text, context, context_hash, tier1_hint),
                daemon=True,
            )
            thread.start()

            result = RoutingResult(
                success=True,
                tier=RoutingTier.DEEP,
                answer="Processing in background...",
                confidence=0.5,
                latency_ms=(time.monotonic() - start) * 1000,
                async_handle=handle,
                metadata={"async": True},
            )
            self._record_metric(RoutingTier.DEEP, result.latency_ms)
            return result
        else:
            # Synchronous execution
            return self._tier3_sync(text, context, context_hash, start, tier1_hint)

    def _tier3_worker(
        self,
        handle: str,
        text: str,
        context: Dict,
        context_hash: str,
        tier1_hint: Optional[KnowledgeLookupResult] = None,
    ):
        """Background worker for Tier 3 agent execution."""
        start = time.monotonic()
        try:
            result = self._tier3_sync(text, context, context_hash, start, tier1_hint)
            if result:
                with self._async_lock:
                    self._async_results[handle] = result
        except Exception as e:
            logger.error("Tier 3 worker failed: %s", e)
            with self._async_lock:
                self._async_results[handle] = RoutingResult(
                    success=False,
                    tier=RoutingTier.DEEP,
                    answer=f"Agent execution failed: {e}",
                    latency_ms=(time.monotonic() - start) * 1000,
                )

    def _tier3_sync(
        self,
        text: str,
        context: Dict,
        context_hash: str,
        start: float,
        tier1_hint: Optional[KnowledgeLookupResult] = None,
    ) -> Optional[RoutingResult]:
        """Synchronous Tier 3 agent execution."""
        try:
            client = self._get_llm_client()
            if client is None:
                return None

            # Build user message with Tier 1 enrichment
            user_parts = []
            if tier1_hint and tier1_hint.found:
                user_parts.append(
                    f"<context source=\"tier1\" confidence=\"{tier1_hint.confidence:.2f}\">\n"
                    f"{tier1_hint.answer}\n</context>\n"
                )
            user_parts.append(text)
            user_message = "\n".join(user_parts)

            # Use deeper model for planning
            response = client.messages.create(
                model=self._config.llm_model_deep,
                max_tokens=4096,
                system=_TIER2_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text
            parsed = self._parse_llm_response(raw_text)

            result = RoutingResult(
                success=True,
                tier=RoutingTier.DEEP,
                answer=parsed.get("answer", raw_text),
                confidence=parsed.get("confidence", 0.6),
                latency_ms=(time.monotonic() - start) * 1000,
                metadata={
                    "model": self._config.llm_model_deep,
                    "reasoning": parsed.get("reasoning", ""),
                },
            )

            self._cache_result("deep", text, context_hash, result)
            self._pin_tier(text, context_hash, RoutingTier.DEEP.value)
            self._record_metric(RoutingTier.DEEP, result.latency_ms)
            return result

        except Exception as e:
            logger.warning("Tier 3 sync failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Async result retrieval
    # ------------------------------------------------------------------

    def get_async_result(self, handle: str) -> Optional[RoutingResult]:
        """
        Poll for async Tier 3 result.

        Returns None if still processing, RoutingResult when done.
        """
        with self._async_lock:
            return self._async_results.pop(handle, None)

    # ------------------------------------------------------------------
    # LLM client
    # ------------------------------------------------------------------

    def _get_llm_client(self):
        """Lazy-initialize Anthropic client."""
        if self._llm_client is not None:
            return self._llm_client

        if not self._config.llm_api_key:
            return None

        try:
            import anthropic
            self._llm_client = anthropic.Anthropic(
                api_key=self._config.llm_api_key,
            )
            return self._llm_client
        except ImportError:
            logger.warning("anthropic package not installed — Tier 2/3 disabled")
            return None

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        """Parse structured JSON from LLM response."""
        # Try to extract JSON from markdown code blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except (json.JSONDecodeError, ValueError):
                    continue

        # Try direct JSON parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: treat as plain text answer
        return {"action": "answer", "answer": text, "confidence": 0.6}

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------

    def _cache_result(
        self, tier: str, text: str, context_hash: str, result: RoutingResult
    ):
        """Store result in cache if enabled."""
        if self._config.enable_cache:
            self._cache.put(tier, text, context_hash, result)

    def _hash_context(self, context: Dict) -> str:
        """Hash context dict for cache keying."""
        if not context:
            return ""
        raw = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _record_metric(self, tier: RoutingTier, latency_ms: float):
        """Record routing metric."""
        self._tier_counts[tier.value] = self._tier_counts.get(tier.value, 0) + 1
        if tier.value not in self._tier_latencies:
            self._tier_latencies[tier.value] = []
        self._tier_latencies[tier.value].append(latency_ms)
        self._total_routes += 1

    def stats(self) -> Dict[str, Any]:
        """Return routing statistics."""
        tier_stats = {}
        for tier_name in self._tier_counts:
            count = self._tier_counts[tier_name]
            latencies = self._tier_latencies.get(tier_name, [])
            tier_stats[tier_name] = {
                "count": count,
                "avg_ms": sum(latencies) / len(latencies) if latencies else 0,
                "max_ms": max(latencies) if latencies else 0,
            }

        return {
            "total_routes": self._total_routes,
            "tiers": tier_stats,
            "cache": self._cache.stats(),
            "knowledge": self._knowledge.stats(),
        }

    # ------------------------------------------------------------------
    # Drop-in compatibility
    # ------------------------------------------------------------------

    def as_command_fn(self) -> Callable[[SynapseCommand], SynapseResponse]:
        """
        Return a command_fn-compatible wrapper.

        Allows the router to be used anywhere command_fn is expected.
        The command's payload must include a 'text' field for routing.
        """
        def wrapper(cmd: SynapseCommand) -> SynapseResponse:
            text = cmd.payload.get("text", cmd.payload.get("query", ""))
            if not text:
                return SynapseResponse(
                    id=cmd.id,
                    success=False,
                    error="No 'text' or 'query' field in payload",
                )

            result = self.route(text, context=cmd.payload.get("context"))
            return SynapseResponse(
                id=cmd.id,
                success=result.success,
                data={
                    "answer": result.answer,
                    "tier": result.tier.value,
                    "confidence": result.confidence,
                    "latency_ms": result.latency_ms,
                    "cached": result.cached,
                    "async_handle": result.async_handle,
                },
            )

        return wrapper

    @property
    def parser(self) -> CommandParser:
        """Access the Tier 0 parser."""
        return self._parser

    @property
    def knowledge(self) -> KnowledgeIndex:
        """Access the Tier 1 knowledge index."""
        return self._knowledge

    @property
    def recipe_registry(self) -> RecipeRegistry:
        """Access the recipe registry."""
        return self._recipes

    @property
    def cache(self) -> ResponseCache:
        """Access the response cache."""
        return self._cache
