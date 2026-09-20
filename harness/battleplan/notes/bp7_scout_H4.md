# SCOUT VERDICT: H4 — Router Cached State

**VERDICT: UNKNOWN**

---

## Mechanism

The cached TieredRouter instance (`self._router` in `_handle_route_chat`) carries persistent state across chat turns: the lazy-initialized `_llm_client`, response cache, tier pins, and async result dictionary. These attributes are written during turn 1's `route()` call and survive into turn 2. The tier2_timeout and tier3_timeout values are defined in RoutingConfig but never enforced in the route() method itself, meaning an LLM call that hangs on turn 2 would block indefinitely until the server's 30s slow-op timeout kills the handler. Whether actual code execution blocks on turn 2 cannot be determined without live runtime inspection.

---

## Evidence

**State persistence — attributes written during route() calls:**

| Attribute | Written At | Survives |
|-----------|-----------|----------|
| `self._llm_client` | router.py:968 (lazy init in `_get_llm_client`) | Yes — reused across all turns |
| `self._cache` | router.py:746, 1008 (in tier result handlers + `_cache_result`) | Yes — ResponseCache stores all tier results |
| `self._tier_pins` | router.py:637 (in `_pin_tier` method) | Yes — tier consistency dictionary (He2025) |
| `self._async_results` | router.py:845, 856 (in `_tier3_worker` thread) | Yes — until polled via `get_async_result()` |
| `self._tier_latencies` | router.py:1053 (in `_record_metric`) | Yes — deque with maxlen=1000 |

**Router cached on handler:**
- handlers.py:1759-1777: `if not hasattr(self, "_router"):` → TieredRouter created once, then `self._router = TieredRouter(config=config, memory=owner)`
- handlers.py:1787: `result = self._router.route(message, context=context)` — same instance reused every turn

**Timeout configuration but no enforcement:**
- router.py:124-125: `tier2_timeout: float = 5.0` and `tier3_timeout: float = 15.0` defined in RoutingConfig
- router.py:685 (Tier 2) and 893 (Tier 3): `guarded_create(client, ...)` called WITHOUT timeout parameter — timeouts defined but never passed to LLM call
- router.py:334, 340: Only Tier 0/1 lookups have explicit `timeout=2.0` in `.result(timeout=...)`

**Alias mapping verified:**
- aliases.py:44: `"content": ["content", "text", "message", "body"]` — resolve_param(payload, "content") correctly maps payload["message"]
- handlers.py:1750: `message = resolve_param(payload, "content")` uses alias system ✓

**No explicit exception handling around route() call:**
- handlers.py:1787-1805: `result = self._router.route(...)` has no try/except — if route() raises, exception propagates up the handler stack

---

## Reproduction

**To test H4 hypothesis in Houdini GUI (<2 minutes):**

1. **Send turn 1 message:** Type a query into SYNAPSE chat (e.g., "create a cube")
   - Observable: Chat responds with answer + typing indicator clears
2. **Send turn 2 message immediately:** Type a follow-up query (e.g., "make it red")
   - Observable A (H4 true): Chat shows typing indicator, then stalls silently for >5s, eventually timeout or no response appears
   - Observable B (H4 false): Chat responds normally within <2s
3. **If stall observed:** Check panel logs at `~/.synapse/logs/synapse.log` for timeout errors or blocked-in-tier messages
   - Evidence: If log shows handler timeout (server-side 30s kill), route() was blocked. If log shows route() returned but panel error filtered, verify response was received but not displayed.

---

## Smallest Fix Shape

If H4 is CONFIRMED by runtime testing, the fix is straightforward: enforce the tier timeouts by passing them to guarded_create() calls OR wrap the LLM calls in Python's concurrent.futures.ThreadPoolExecutor.submit(..., timeout=tier2_timeout) to interrupt hangs. Alternatively, wrap the entire route() method in a timeout context at the handler level to ensure _handle_route_chat() cannot block past the server's 30s slow-op timeout. The state persistence itself (cached router, _llm_client reuse) is architectural and not the primary defect — the defect is the absence of timeout enforcement on LLM tier calls. A secondary check: verify that the _llm_client connection state doesn't degrade across turns (inspect SDK client.__dict__ before and after first route() call to detect accumulated errors or connection pool exhaustion).

---

## Notes

- Tests pass: `pytest tests/test_router_internals.py -q` → 30/30 ✓ (tests do not exercise multi-turn scenarios)
- The tier timeouts configuration suggests they were INTENDED to be enforced but implementation was incomplete
- The 30s slow-op timeout on `/synapse` path (harness/CLAUDE.md Identity) is the server-side kill switch; route() must complete inside it
- Router singleton is shared for process lifetime, so any state degradation from turn 1 affects all subsequent turns
