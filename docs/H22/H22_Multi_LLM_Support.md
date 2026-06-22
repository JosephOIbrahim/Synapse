# H22 PREP — Multi-LLM Support Strategy
**Document:** LLM-002  
**Label:** H22  
**Author:** SYNAPSE / Houdini AI Co-Pilot  
**Date:** 2026-06-22  
**Status:** Pre-Release Research  

---

## Executive Summary

SYNAPSE currently operates as a single-LLM system: one model, one context window, one tool surface. As the LLM landscape matures and Houdini 22 raises the complexity ceiling (APEX, larger USD stages, longer TOPS pipelines), a multi-LLM architecture becomes both technically justified and practically necessary. This document defines the strategy for supporting multiple LLMs as first-class backends — including model routing, context management, capability tiering, and safety boundaries.

---

## 1. Why Multi-LLM Now

### 1.1 The Single-Model Bottleneck
The current architecture assumes one LLM processes all tool calls sequentially. This works for simple sessions but breaks down when:
- Context windows fill during long TOPS pipeline runs (48+ frame renders with per-frame validation)
- A complex USD scene with 500+ prims requires simultaneous reasoning about composition, materials, and lighting
- The artist wants to run an autonomous render loop *while* discussing a different creative problem
- Different tasks need different model strengths (code generation vs. creative description vs. structured reasoning)

### 1.2 The Model Diversity Opportunity
By mid-2026, multiple frontier models are capable of driving Houdini through SYNAPSE's tool surface:
- **Claude 3.x / 4.x (Anthropic)** — strong structured reasoning, tool use, long context
- **GPT-4o / o1 / o3 (OpenAI)** — strong code generation, fast iteration
- **Gemini 1.5 Pro / 2.x (Google)** — very long context (1M+ tokens), good for full-session replay
- **Mistral / Codestral (Mistral AI)** — fast, locally deployable, good for VEX/Python generation
- **LLaMA 3.x / Qwen 2.x (Meta / Alibaba)** — studio-deployable on local hardware, no data egress
- **DeepSeek R2 (DeepSeek)** — strong at code and structured output at low cost

No single model dominates all tasks. A routing layer transforms this diversity into a strength.

---

## 2. Architecture: Model Router

### 2.1 Router Position in the Stack
```
Artist Input
     │
     ▼
┌─────────────────────────────────┐
│         SYNAPSE Router          │  ← new layer
│  (intent classifier + dispatcher)│
└─────────────────────────────────┘
     │           │           │
     ▼           ▼           ▼
 Primary LLM  Code LLM   Local LLM
 (reasoning)  (VEX/Py)  (offline/NDA)
     │           │           │
     └─────┬─────┘           │
           ▼                 ▼
    ┌─────────────┐   ┌─────────────┐
    │  Tool Layer │   │  Tool Layer │
    │  (MCP/ws)   │   │  (MCP/ws)   │
    └─────────────┘   └─────────────┘
           │                 │
           └────────┬────────┘
                    ▼
             Houdini 22 / SYNAPSE Bridge
```

### 2.2 Router Responsibilities
1. **Intent classification** — is this a creative question, a code generation task, a USD authoring task, or an autonomous pipeline run?
2. **Model selection** — route to the best-fit model based on intent, latency budget, and availability
3. **Context packaging** — each model gets a tailored context slice (not the full conversation) appropriate to its task
4. **Result aggregation** — merge responses from parallel model calls into a single coherent reply
5. **Fallback handling** — if primary model is unavailable or rate-limited, transparently fall back

### 2.3 Intent Classification Schema
```json
{
  "intent_type": "code_generation | creative | usd_authoring | pipeline | question | render",
  "complexity": "simple | moderate | complex",
  "requires_history": true,
  "latency_budget": "interactive | batch",
  "data_sensitivity": "none | studio_nda | personal"
}
```

---

## 3. Model Capability Tiers

### Tier 1 — Primary Reasoning Model
**Role:** Main conversational partner, scene orchestration, multi-step planning  
**Requirements:** Strong tool use, >128K context, reliable JSON output  
**Candidates:** Claude 4, GPT-o3, Gemini 2.x Pro  
**SYNAPSE integration:** Full tool surface access, memory read/write, undo group authority

### Tier 2 — Code Specialist
**Role:** VEX generation, Python scripts, OpenCL kernels, HDA callback code  
**Requirements:** Strong code quality, fast latency, minimal hallucination on Houdini API  
**Candidates:** Codestral, DeepSeek R2, GPT-4o  
**SYNAPSE integration:** Sandboxed — can only call `houdini_execute_python`, `houdini_execute_vex`, `cops_set_opencl`. No scene mutation authority. All outputs reviewed by Tier 1 before execution.

### Tier 3 — Local / Studio Model
**Role:** NDA-sensitive scenes, air-gapped studios, offline sessions  
**Requirements:** Deployable on studio hardware (A100/H100 cluster), Houdini API knowledge  
**Candidates:** LLaMA 3.1 70B fine-tuned, Qwen 2.5 72B, local Mistral  
**SYNAPSE integration:** Full tool surface but no external API calls. Memory is session-local only. No telemetry.

### Tier 4 — Specialist Micro-Models (future)
**Role:** Narrow, fast tasks — material parameter suggestion, light rig classification, USD prim naming  
**Requirements:** <1B parameters, <100ms latency, deterministic output  
**Candidates:** Fine-tuned distillation from Tier 1 model on SYNAPSE telemetry  
**SYNAPSE integration:** Called as sub-tools by Tier 1, not directly by artist

---

## 4. Protocol Compatibility

### 4.1 MCP (Model Context Protocol) as the Lingua Franca
SYNAPSE's tool surface is already defined in MCP-compatible JSON schema. All tools have:
- Typed input parameters
- Structured JSON responses
- Error codes and recovery suggestions

This means any MCP-compatible model can drive SYNAPSE without modification to the bridge. The work is in the router, not the tool layer.

### 4.2 Tool Surface Subset per Model
Not all models should have access to all tools. Define capability masks:

```json
{
  "tier_1": ["*"],
  "tier_2": ["houdini_execute_python", "houdini_execute_vex", "cops_set_opencl", "synapse_knowledge_lookup"],
  "tier_3": ["*"],
  "tier_4": ["synapse_knowledge_lookup", "houdini_get_parm", "houdini_get_usd_attribute"]
}
```

### 4.3 Context Protocol per Model
Different models have different context window strategies:

| Model Family | Context Strategy |
|---|---|
| Claude | Full conversation + tool results; summarize memory at 80% context fill |
| GPT-4o | Sliding window; eject tool results older than 10 turns |
| Gemini 1.5 Pro | Full session replay possible; use for "what happened in this session" queries |
| Local LLaMA | Short context (8K-32K); aggressive summarization; stateless tool calls |

SYNAPSE memory system (project.md, scene memory.md) must be packaged differently per model. Add `synapse_package_context(model_tier)` that returns a model-appropriate context string.

### 4.4 OpenAI-Compatible API Surface
Studios using OpenAI-compatible inference servers (vLLM, Ollama, LM Studio) can route Tier 3 models through the same interface. The router should accept an `api_base` override so any OpenAI-API-compatible endpoint works without code changes.

---

## 5. Memory Architecture for Multi-LLM

### 5.1 The Problem
If Claude authors a memory entry and then Gemini reads the project, does Gemini understand the SYNAPSE memory schema? Does it make consistent decisions?

### 5.2 Solution: Model-Agnostic Memory Format
- Memory files (project.md, scene memory.md) must be written in plain, schema-annotated markdown — no model-specific idioms
- Every memory entry includes a `source_model` tag for auditability
- The memory evolution system (Charmander → Charmeleon → Charizard) must be model-agnostic: any model can trigger evolution, not just the model that created the entries

### 5.3 Shared Decision Log
Add a `decisions.jsonl` alongside project.md:
```jsonl
{"ts": "2026-06-22T13:00:00Z", "model": "claude-4", "decision": "use Karma XPU", "reasoning": "..."}
{"ts": "2026-06-22T13:05:00Z", "model": "codestral", "decision": "use @P += noise()", "reasoning": "..."}
```
This log lets any model understand what prior models decided without re-reasoning from scratch.

---

## 6. Safety and Governance

### 6.1 Mutation Authority
Only Tier 1 models should have unrestricted mutation authority (create nodes, delete nodes, set parameters). Tier 2 and Tier 4 are read-only or sandboxed.

Rule: **Any tool call that mutates the Houdini scene must pass through the Tier 1 model for approval if it originated from a lower tier.**

### 6.2 Undo Group Attribution
Every undo group should carry a `model_id` tag so the artist can see (in the Houdini undo history) which model made which change:
```
Undo: [claude-4] Create SOPCreate + MaterialLibrary chain
Undo: [codestral] Execute VEX snippet
```

### 6.3 Data Egress Control
- Tier 3 (local) models: hard block on external network calls from the bridge
- Tier 1/2 (cloud) models: scene geometry is never sent to the LLM — only text descriptions, parameter values, and USD prim paths
- PII scrubbing: project.md should not contain file paths that leak studio infrastructure details when sent to external models

### 6.4 Rate Limiting and Cost Guards
- Router tracks per-model token consumption and cost estimate
- Budget alerts: warn artist when session cost exceeds threshold
- Auto-downgrade to Tier 3 if Tier 1 API is unavailable

---

## 7. Studio Deployment Scenarios

### Scenario A: Solo Artist (Current)
- One cloud LLM (Claude/GPT)
- Full tool surface
- No router needed
- Continue current architecture

### Scenario B: Mid-Size Studio (6 months post-H22)
- Tier 1 cloud model for creative sessions
- Tier 3 local model for render farm automation (no data egress)
- Router selects based on `data_sensitivity` flag
- Shared project memory on NFS mount

### Scenario C: Large Studio (12 months post-H22)
- Tier 1 + Tier 2 + Tier 3 all active
- Per-department capability masks (lighting TDs get full tool surface, look-dev artists get material tools only)
- Decisions log stored in production tracking system (ShotGrid/Flow)
- Model outputs reviewed by lead TD before scene commit (human-in-the-loop mode)

---

## 8. Implementation Roadmap

### Phase 1 — Foundation (Weeks 1–2, pre-H22 launch)
- [ ] Define `ModelCapabilityMask` schema
- [ ] Add `source_model` tag to all memory writes
- [ ] Add `api_base` override to bridge configuration
- [ ] Write `synapse_package_context(model_tier)` tool
- [ ] Test full tool surface against GPT-4o and Gemini 1.5 Pro in parallel

### Phase 2 — Router (Weeks 3–4, H22 launch window)
- [ ] Build intent classifier (can be a lightweight prompt, not a separate model)
- [ ] Implement model selection logic
- [ ] Add `model_id` attribution to undo groups
- [ ] Add `decisions.jsonl` to memory system

### Phase 3 — Local Model Support (Post-H22, Month 2)
- [ ] Test LLaMA 3.1 70B / Qwen 2.5 72B against SYNAPSE tool surface via Ollama
- [ ] Build Houdini-specific fine-tuning dataset from anonymized telemetry
- [ ] Publish capability benchmark: which models pass SYNAPSE smoke tests

### Phase 4 — Tier 4 Micro-Models (Month 3+)
- [ ] Identify top 5 tasks that don't need a frontier model (parameter lookup, prim naming, etc.)
- [ ] Fine-tune 1B distillation model
- [ ] Integrate as sub-tool calls with <100ms latency target

---

## 9. Recommended First Steps (This Week)

1. **Run the full SYNAPSE tool surface against GPT-4o** — document which tools fail or produce wrong parameter names. This baseline is essential before H22.
2. **Add `api_base` to `bridge.json`** — one config change that unlocks all OpenAI-compatible endpoints.
3. **Write `synapse_package_context`** — start with a 2K-token summary version for Tier 3 models.
4. **Tag all existing memory entries with `source_model: claude`** retroactively.

---

*End of document LLM-002*
