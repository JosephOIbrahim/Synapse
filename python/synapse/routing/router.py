"""
Synapse Tiered Router

Dispatches each input to the fastest capable handler.
LLM calls are reserved for the ~20% that genuinely need reasoning.

Cascade: Cache → Recipe → Tier0 → Tier1 → Tier2 → Tier3
"""

import collections
import hashlib
import json
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Deque, Dict, List, Optional, Any, Union

from ..core.protocol import SynapseCommand, SynapseResponse
from ..core.gates import HumanGate, GateLevel
from ..core.determinism import deterministic_uuid, kahan_sum, round_float
from ..memory.store import SynapseMemory, ReadWriteLock

from .parser import CommandParser, ParseResult
from .knowledge import KnowledgeIndex, KnowledgeLookupResult
from .recipes import RecipeRegistry, Recipe
from .planner import WorkflowPlanner
from .cache import ResponseCache
from .adaptation import EpochAdapter
from .context_enrichment import enrich_context

logger = logging.getLogger(__name__)

# =============================================================================
# Conversational patterns (pre-cascade, O(1))
# =============================================================================

import re as _re

_GREETING_RE = _re.compile(
    r"^(?:h(?:i|ello|ey|owdy)|yo|sup|good\s+(?:morning|afternoon|evening)"
    r"|what'?s?\s+up|gm|greetings)[\s!.,?]*$",
    _re.IGNORECASE,
)
_THANKS_RE = _re.compile(
    r"^(?:thanks?(?:\s+you)?|ty|cheers|appreciate\s+it|thx)[\s!.,]*$",
    _re.IGNORECASE,
)
_BYE_RE = _re.compile(
    r"^(?:bye|goodbye|see\s+ya|later|cya|peace|good\s*night)[\s!.,]*$",
    _re.IGNORECASE,
)

_CONVERSATIONAL = [
    (_GREETING_RE, "Hey -- ready when you are. What are we building?"),
    (_THANKS_RE, "Anytime. What's next?"),
    (_BYE_RE, "See you next session. Save your scene!"),
]


# =============================================================================
# Data Models
# =============================================================================

# Reserved metric key for outcomes that belong to NO tier: the cascade ran to
# the end and nothing handled the request. Deliberately NOT a RoutingTier member
# — it names the absence of a tier, and adding it to the enum would let it be
# returned as if a tier had handled something. EpochAdapter.record() takes a
# bare str key, so the sample can carry it.
NO_TIER_KEY = "no_tier"


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
    llm_model_deep: str = "claude-sonnet-4-6"
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

    _instance: Optional["TieredRouter"] = None

    @classmethod
    def get_instance(cls, **kwargs: object) -> "TieredRouter":
        """Return the singleton router, creating one if needed."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)  # type: ignore[arg-type]
        return cls._instance

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
        self._planner = WorkflowPlanner()
        self._cache = ResponseCache(
            max_size=self._config.cache_max_size,
            ttl_seconds=self._config.cache_ttl,
        )

        # Tier-pinning cache: canonical_key → tier value (He2025 consistency)
        # RWLock: reads vastly outnumber writes in steady state
        self._tier_pins: Dict[str, str] = {}
        self._tier_pins_lock = ReadWriteLock()

        # Metrics (deque with maxlen keeps only the last 1000 measurements per tier)
        self._tier_counts: Dict[str, int] = {t.value: 0 for t in RoutingTier}
        self._tier_latencies: Dict[str, Deque[float]] = {
            t.value: collections.deque(maxlen=1000) for t in RoutingTier
        }
        self._total_routes = 0

        # Epoch-based adaptation (Phase 2A)
        self._epoch = EpochAdapter()

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
        # Conversational short-circuit (greetings, thanks, bye)
        # No commands, no cascade — just a friendly response.
        # ---------------------------------------------------------------
        text_stripped = input_text.strip()
        for pattern, reply in _CONVERSATIONAL:
            if pattern.match(text_stripped):
                # This return records NO metric and caches nothing — it is not
                # in the reward sample at all, so it cannot pin any series. The
                # reply is a constant from the _CONVERSATIONAL table; nothing
                # executes, so nothing can fail. success=True is the truth.
                return RoutingResult(
                    success=True,
                    tier=RoutingTier.INSTANT,
                    answer=reply,
                    confidence=1.0,
                    latency_ms=(time.monotonic() - start) * 1000,
                    metadata={"conversational": True},
                )

        # ---------------------------------------------------------------
        # -1. Tier-pin check (He2025 consistency)
        # ---------------------------------------------------------------
        pin_key = f"{input_text.strip().lower()}|{context_hash}"
        with self._tier_pins_lock.read_lock():
            pinned_tier = self._tier_pins.get(pin_key)

        # ---------------------------------------------------------------
        # 0. Pinned-tier fast path (He2025: same input → same tier)
        # ---------------------------------------------------------------
        if pinned_tier:
            result = self._try_pinned_tier(
                pinned_tier, input_text, context, context_hash, start
            )
            if result:
                return result
            # Stale pin — tier returned None; delete ONLY if value unchanged
            with self._tier_pins_lock.write_lock():
                if self._tier_pins.get(pin_key) == pinned_tier:
                    self._tier_pins.pop(pin_key, None)

        # ---------------------------------------------------------------
        # 0.5. Cache check (He2025)
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
                    self._record_metric(RoutingTier.CACHE, result.latency_ms, result.success)
                    return result

        # ---------------------------------------------------------------
        # 1. Recipe match
        # ---------------------------------------------------------------
        if self._config.enable_recipes:
            result = self._try_recipe(input_text, context_hash, start)
            if result:
                return result

        # ---------------------------------------------------------------
        # 1.5. Workflow planner (composite intent decomposition)
        # ---------------------------------------------------------------
        result = self._try_plan(input_text, context_hash, start)
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

            try:
                t0_result = t0_future.result(timeout=2.0)
            except Exception:
                logger.warning("Tier 0 lookup failed, falling through")
                t0_result = None

            try:
                tier1_hint = t1_lookup_future.result(timeout=2.0)
            except Exception:
                logger.warning("Knowledge lookup failed, falling through")
                tier1_hint = None

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
        result = RoutingResult(
            success=False,
            tier=RoutingTier.DEEP,
            answer="I couldn't understand that request. Could you rephrase?",
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={"reason": "no_tier_matched"},
        )
        # A genuine routing failure. Recorded under NO_TIER_KEY rather than
        # RoutingTier.DEEP: charging it to deep would defame a tier that never
        # ran. Recorded at all because a sample that only sees the successes is
        # not a sample — this is the root defect of RSI loop A1.
        self._record_metric(NO_TIER_KEY, result.latency_ms, False)
        return result

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

        # Execute if command_fn available — otherwise this is a PROPOSAL only
        responses = []
        executed = self._command_fn is not None
        if self._command_fn:
            for cmd in commands:
                try:
                    resp = self._command_fn(cmd)
                except Exception as e:
                    resp = SynapseResponse(id=cmd.id, success=False, error=str(e))
                responses.append(resp)
                if not resp.success:
                    # M2-H: stop on first failure — later steps must not run
                    # against a broken precondition (half-build containment).
                    break

        if not executed:
            success = True
            answer = (
                f"Proposed recipe '{recipe.name}' ({len(commands)} steps) — "
                f"not executed (no command channel wired); steps returned as commands"
            )
            failed_step = None
        else:
            failed = [(i, r) for i, r in enumerate(responses) if not r.success]
            success = not failed
            if success:
                answer = f"Executed recipe '{recipe.name}' ({len(commands)} steps)"
                failed_step = None
            else:
                i, r = failed[0]
                failed_step = i + 1
                answer = (
                    f"Recipe '{recipe.name}' failed at step {i + 1}/{len(commands)}: "
                    f"{r.error or 'step returned failure'} — "
                    f"{i} step(s) applied, {len(commands) - i - 1} not run; "
                    "use houdini_undo to roll back the applied steps"
                )

        result = RoutingResult(
            success=success,
            tier=RoutingTier.RECIPE,
            answer=answer,
            commands=commands,
            responses=responses,
            confidence=0.95,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={
                "recipe": recipe.name,
                "params": params,
                "executed": executed,
                "failed_step": failed_step,
                "steps_skipped": (len(commands) - len(responses)) if executed else 0,
            },
        )

        self._cache_result("recipe", text, context_hash, result)
        self._pin_tier(text, context_hash, RoutingTier.RECIPE.value,
                       pin_key=f"{text.strip().lower()}|{context_hash}")
        self._record_metric(RoutingTier.RECIPE, result.latency_ms, result.success)
        return result

    def _try_plan(
        self, text: str, context_hash: str, start: float
    ) -> Optional[RoutingResult]:
        """Try workflow planner for composite intents."""
        plan = self._planner.plan(text)
        if plan is None:
            return None

        # Execute plan steps if command_fn available — otherwise PROPOSAL only.
        # M2-H: same truth contract as _try_recipe — success tracks real step
        # outcomes, stop on first failure, honest step accounting.
        responses = []
        executed = self._command_fn is not None
        if self._command_fn:
            for cmd in plan.steps:
                try:
                    resp = self._command_fn(cmd)
                except Exception as e:
                    resp = SynapseResponse(id=cmd.id, success=False, error=str(e))
                responses.append(resp)
                if not resp.success:
                    break

        failed = [(i, r) for i, r in enumerate(responses) if not r.success]
        success = not failed
        failed_step = None
        if not executed:
            answer = (
                f"Planned workflow '{plan.name}' ({len(plan.steps)} steps) — "
                f"not executed (no command channel wired); steps returned as commands"
            )
        elif success:
            answer = plan.description
        else:
            i, r = failed[0]
            failed_step = i + 1
            answer = (
                f"Workflow '{plan.name}' failed at step {i + 1}/{len(plan.steps)}: "
                f"{r.error or 'step returned failure'} — "
                f"{i} step(s) applied, {len(plan.steps) - i - 1} not run; "
                "use houdini_undo to roll back the applied steps"
            )

        result = RoutingResult(
            success=success,
            tier=RoutingTier.RECIPE,  # Plans run at recipe speed
            answer=answer,
            commands=plan.steps,
            responses=responses,
            confidence=0.9,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={
                "planned": True,
                "workflow": plan.name,
                "executed": executed,
                "failed_step": failed_step,
                "steps_skipped": (len(plan.steps) - len(responses)) if executed else 0,
                **plan.metadata,
            },
        )

        self._cache_result("recipe", text, context_hash, result)
        self._pin_tier(text, context_hash, RoutingTier.RECIPE.value,
                       pin_key=f"{text.strip().lower()}|{context_hash}")
        self._record_metric(RoutingTier.RECIPE, result.latency_ms, result.success)
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

        # Same truth contract as _try_recipe / _try_plan: success describes what
        # HAPPENED, not what was attempted. No responses (nothing executed, or no
        # command channel wired) means nothing failed — the parse itself is the
        # outcome. Any failed response makes this a failure.
        success = all(r.success for r in responses)

        result = RoutingResult(
            success=success,
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
        self._pin_tier(text, context_hash, RoutingTier.INSTANT.value,
                       pin_key=f"{text.strip().lower()}|{context_hash}")
        self._record_metric(RoutingTier.INSTANT, result.latency_ms, result.success)
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
            # Truth contract for tier 1 — the literal True is CORRECT here, and
            # deriving it would be theatre. Tier 1 never touches self._command_fn
            # and never populates `responses`, so `all(r.success for r in
            # responses)` is `all([])` — a literal True wearing a costume.
            #
            # The FAST success series IS pinned at 1.0, but not because of this
            # line: tier 1 only reaches _record_metric on its success path. The
            # not-found / low-confidence exit above is `return None`, which is a
            # CASCADE decision, not a tier-1 failure — the request continues to
            # tier 2 and may well succeed there. Recording it as a FAST failure
            # would score one request twice, in two different series. Total
            # routing failure is already sampled: NO_TIER_KEY, see route().
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
        self._pin_tier(text, context_hash, RoutingTier.FAST.value,
                       pin_key=f"{text.strip().lower()}|{context_hash}")
        self._record_metric(RoutingTier.FAST, result.latency_ms, result.success)
        return result

    def _pin_tier(self, input_text: str, context_hash: str, tier_value: str,
                  pin_key: Optional[str] = None):
        """Record a tier pin for future consistency."""
        if pin_key is None:
            pin_key = f"{input_text.strip().lower()}|{context_hash}"
        with self._tier_pins_lock.write_lock():
            # LRU eviction: remove oldest 10% when at capacity
            if len(self._tier_pins) >= _MAX_TIER_PINS and pin_key not in self._tier_pins:
                evict_count = max(1, len(self._tier_pins) // 10)
                for old_key in list(self._tier_pins.keys())[:evict_count]:
                    del self._tier_pins[old_key]
            self._tier_pins[pin_key] = tier_value

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

            # Build enriched user message via context_enrichment module
            user_message = enrich_context(
                message=text,
                tier1_hint=tier1_hint,
                memory=self._memory,
            )

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
                    id=deterministic_uuid(
                        f"tier2:{parsed['command_type']}:{json.dumps(parsed.get('payload', {}), sort_keys=True)}",
                        "cmd",
                    ),
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
                # Same truth contract as tier 0 / recipes / plans: an executed
                # command that came back failed is a failed route, not a
                # successful one that happens to carry an error.
                success=all(r.success for r in responses),
                tier=RoutingTier.STANDARD,
                answer=answer,
                commands=commands,
                responses=responses,
                confidence=parsed.get("confidence", 0.7),
                latency_ms=(time.monotonic() - start) * 1000,
                metadata=tier2_meta,
            )

            self._cache_result("standard", text, context_hash, result)
            self._pin_tier(text, context_hash, RoutingTier.STANDARD.value,
                           pin_key=f"{text.strip().lower()}|{context_hash}")
            self._record_metric(RoutingTier.STANDARD, result.latency_ms, result.success)
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
        handle = deterministic_uuid(f"tier3:{text}:{context_hash}", "handle")

        if self._config.tier3_async:
            # Launch in background thread
            thread = threading.Thread(
                target=self._tier3_worker,
                args=(handle, text, context, context_hash, tier1_hint),
                daemon=True,
            )
            thread.start()

            # success=True here means "the launch succeeded" — the thread
            # started and `handle` is claimable. It is an acknowledgement, not
            # an outcome: at this instant no outcome exists yet.
            #
            # RSI A1 / rung L1: this site used to ALSO call _record_metric,
            # which fed the EpochAdapter a guaranteed True at launch time and
            # left the worker's real verdict — arriving milliseconds to minutes
            # later — permanently outside the sample. Every async DEEP route
            # scored 1.0 no matter how it ended.
            #
            # Design call (option c of defer / provisional-then-amend / do-not-
            # record-at-launch): DO NOT RECORD HERE. The outcome is recorded by
            # _tier3_worker, which is the only place it is actually known.
            #   - deferring to get_async_result() was rejected: that method
            #     POPs, so a handle nobody polls would never be sampled at all,
            #     and the timing would attribute worker latency to the poller.
            #   - record-then-amend was rejected: EpochAdapter.record()
            #     (adaptation.py:138-143) appends into a fixed-size deque and
            #     rotates the epoch when full. There is no amend API, and a
            #     provisional True can be rotated out of the epoch — and
            #     already aggregated into a threshold — before its correction
            #     arrives. Amending would need new adapter machinery, which is
            #     more than an honest-signal fix should smuggle in.
            return RoutingResult(
                success=True,
                tier=RoutingTier.DEEP,
                answer="Processing in background...",
                confidence=0.5,
                latency_ms=(time.monotonic() - start) * 1000,
                async_handle=handle,
                metadata={"async": True},
            )
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
        """Background worker for Tier 3 agent execution.

        RSI A1 / rung L1 — this worker is where an async DEEP route's outcome
        actually becomes known, so this is where it is recorded. `_try_tier3`
        deliberately records nothing at launch (see the note there).

        Recording contract, exactly one DEEP sample per async route:
          - success  → `_tier3_sync` already recorded True at its own return.
                       Do NOT record again here or one route counts twice.
          - None     → `_tier3_sync` bailed (no LLM client, or it swallowed an
                       exception into a warning). For an async route that is
                       terminal: there is no cascade left to fall through to.
                       Record False.
          - raised   → terminal too. Record False.
        Both failure paths also STORE a result, so a poller gets a verdict
        instead of a handle that never resolves.
        """
        start = time.monotonic()
        try:
            result = self._tier3_sync(text, context, context_hash, start, tier1_hint)
            if result:
                with self._async_lock:
                    self._async_results[handle] = result
            else:
                latency_ms = (time.monotonic() - start) * 1000
                failure = RoutingResult(
                    success=False,
                    tier=RoutingTier.DEEP,
                    answer="Agent execution produced no result.",
                    latency_ms=latency_ms,
                    metadata={"async": True, "reason": "tier3_sync_returned_none"},
                )
                with self._async_lock:
                    self._async_results[handle] = failure
                self._record_metric(RoutingTier.DEEP, latency_ms, failure.success)
        except Exception as e:
            logger.error("Tier 3 worker failed: %s", e)
            latency_ms = (time.monotonic() - start) * 1000
            failure = RoutingResult(
                success=False,
                tier=RoutingTier.DEEP,
                answer=f"Agent execution failed: {e}",
                latency_ms=latency_ms,
                metadata={"async": True, "reason": "tier3_worker_raised"},
            )
            with self._async_lock:
                self._async_results[handle] = failure
            self._record_metric(RoutingTier.DEEP, latency_ms, failure.success)

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

            # Build enriched user message via context_enrichment module
            user_message = enrich_context(
                message=text,
                tier1_hint=tier1_hint,
            )

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
                # Same truth contract as tier 1: no command channel, no
                # `responses` to derive from. Unlike tier 2, _tier3_sync never
                # builds a SynapseCommand — it answers. Reaching this line means
                # the model replied and _parse_llm_response returned (it cannot
                # fail: its last branch is a plain-text fallback, see :884-905).
                # Every failure path above is `return None`.
                #
                # The DEEP series is no longer constant, but the correction is
                # in _tier3_worker, not here — an async route that dies now
                # records False. See _try_tier3 / _tier3_worker.
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
            self._pin_tier(text, context_hash, RoutingTier.DEEP.value,
                           pin_key=f"{text.strip().lower()}|{context_hash}")
            self._record_metric(RoutingTier.DEEP, result.latency_ms, result.success)
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
        """Hash context dict for cache keying.

        Uses xxhash (~100x faster than SHA-256) when available.
        """
        if not context:
            return ""
        try:
            import orjson
            raw = orjson.dumps(context, option=orjson.OPT_SORT_KEYS, default=str)
        except (ImportError, TypeError):
            raw = json.dumps(context, sort_keys=True, default=str).encode()
        try:
            import xxhash
            return xxhash.xxh64(raw).hexdigest()[:16]
        except ImportError:
            return hashlib.sha256(raw).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _record_metric(
        self,
        tier: Union[RoutingTier, str],
        latency_ms: float,
        success: bool,
    ):
        """Record routing metric and epoch outcome.

        `success` is REQUIRED — not defaulted. The reward signal this feeds is
        only worth reading if it can represent failure, and a default of True is
        exactly how it stopped being able to (RSI loop A1). A future call site
        that forgets the outcome is now a TypeError, not a silent 1.0.

        `tier` accepts a RoutingTier or a bare string key so outcomes that
        belong to no tier (the no-tier-matched fallback, NO_TIER_KEY) can still
        enter the sample. A failure the sample cannot see is not a sample.
        """
        key = tier.value if isinstance(tier, RoutingTier) else str(tier)
        self._tier_counts[key] = self._tier_counts.get(key, 0) + 1
        if key not in self._tier_latencies:
            self._tier_latencies[key] = collections.deque(maxlen=1000)
        self._tier_latencies[key].append(latency_ms)
        self._total_routes += 1

        # Feed epoch adapter for adaptive threshold adjustment
        self._epoch.record(key, success, latency_ms)

    def stats(self) -> Dict[str, Any]:
        """Return routing statistics."""
        tier_stats = {}
        for tier_name in sorted(self._tier_counts):  # sorted: He2025
            count = self._tier_counts[tier_name]
            latencies = self._tier_latencies.get(tier_name, [])
            tier_stats[tier_name] = {
                "count": count,
                "avg_ms": round_float(kahan_sum(latencies) / len(latencies)) if latencies else 0,
                "max_ms": round_float(max(latencies)) if latencies else 0,
            }

        return {
            "total_routes": self._total_routes,
            "tiers": tier_stats,
            "cache": self._cache.stats(),
            "knowledge": self._knowledge.stats(),
            "epoch": self._epoch.stats(),
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
