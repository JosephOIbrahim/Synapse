# Routing Cascade

## Overview

The routing cascade selects the cheapest computation path that can handle a given request. Each tier is tried in order; the first successful match short-circuits.

## Tiers

| Tier | Name | Latency | Method |
|------|------|---------|--------|
| Cache | Deterministic cache | O(1) | Exact match on input hash |
| Recipe | Pattern recipes | O(1) | Regex pattern match |
| Planner | Workflow planner | O(1) | Multi-step composition |
| 0 | Regex | O(n) | Pattern matching on input text |
| 1 | RAG Knowledge | O(log n) | Semantic index lookup |
| 2 | Haiku LLM | ~5s | Claude Haiku classification |
| 3 | Agent | ~15s | Full agent loop |

## Tier Pinning

Same input + same context always routes to the same tier. Implemented via LRU cache (max 1,000 pins). Stale pins (>2 epochs old) are evicted on access.

## Epoch Adaptation

Outcomes are recorded during each epoch (fixed size: 100 commands). At epoch boundaries:

1. Success rates are aggregated per tier using Kahan summation
2. Tier confidence thresholds are adjusted
3. Stale pins are evicted
4. New epoch begins

This allows the system to learn from outcomes without violating determinism for existing inputs.

## API

::: synapse.routing.router.TieredRouter
    options:
      members:
        - route
        - get_stats

::: synapse.routing.adaptation.TierEpoch
