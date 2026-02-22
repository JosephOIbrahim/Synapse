# Synapse Demo Script — 2026-02-08

## What Is Synapse?

Synapse is an AI-Houdini bridge — it lets Claude (via Claude Desktop or Claude Code terminal) directly control SideFX Houdini through 23 MCP tools over WebSocket. Real-time, bidirectional, with persistent project memory and RAG-grounded Houdini knowledge.

**Key stats:** 23 MCP tools | 376 tests | Karma XPU rendering | MaterialX shaders | USD/Solaris native | Animation keyframes | TOPs/wedging | Scene assembly | RAG knowledge index (13 topics, 11 reference files) | Project memory with decisions, context, search

---

## Pre-Demo Checklist

1. Houdini open with Synapse server running (Python Panel > Server tab > Start)
2. Claude Desktop connected (check with ping)
3. Claude Code terminal open in `C:\Users\User\Synapse\`
4. Fresh scene (`File > New`)

---

## Demo Flow (15-20 min)

### Act 1: "Hello Houdini" (3 min)

**Show:** Claude can see and talk to Houdini.

```
"What's the current scene info?"          → houdini_scene_info
"What nodes are selected?"                → houdini_get_selection
"Is Synapse healthy?"                     → synapse_health
```

**Talking point:** Zero setup needed — Claude discovers Houdini's state through natural language. No scripting, no plugins beyond Synapse.

### Act 2: "Build Me a Scene" (5 min)

**Show:** Claude builds a full Solaris scene from a prompt.

```
"Create a Solaris scene with a sphere on a ground plane,
two MaterialX shaders (blue metallic sphere, warm grey ground),
a dome light, a key light, and a render camera."
```

Claude will use `execute_python` to create:
- Sphere + Cube (ground) geometry
- MaterialLibrary with mtlxstandard_surface shaders
- AssignMaterial nodes
- DomeLight + DistantLight
- Camera positioned for composition
- KarmaRenderSettings + USD Render ROP

**Talking point:** This is AI doing VFX technical direction — not just text generation. It knows USD, Solaris node graphs, MaterialX shader parameters, and Karma render settings.

### Act 3: "Render It" (3 min)

**Show:** Claude renders via Karma XPU and gets the image back.

```
"Render this scene with Karma XPU at 960x540"
```

→ `houdini_render` returns a JPEG preview image directly in the chat.

**Talking point:** Full render loop — AI can iterate on lighting, materials, camera without human intervention. Karma XPU on RTX 4090 gives near-instant feedback.

### Act 4: "Remember This" (3 min)

**Show:** Persistent project memory across sessions.

```
"Record a decision: We chose blue metallic for the hero sphere
because it shows specular highlights and environment reflections well."

"What decisions have been made on this project?"

"Search memories for 'lighting'"
```

→ `synapse_decide`, `synapse_context`, `synapse_search`

**Talking point:** AI doesn't forget between sessions. Decisions, context, and activity are stored in `$HIP/.synapse/` as human-readable markdown + JSONL. Artists can review and edit.

### Act 5: "Ask Houdini" (2 min)

**Show:** Claude has grounded Houdini knowledge — no hallucination on parameter names.

```
"What's the correct parameter name for dome light intensity?"
→ synapse_knowledge_lookup → "xn__inputsintensity_i0a"

"How do I set up a pyro simulation?"
→ synapse_knowledge_lookup → full SOP chain with parm names
```

**Talking point:** Claude doesn't guess Houdini parameter names — it looks them up from a curated reference index. 13 topics covering Solaris, Karma, MaterialX, Pyro, FLIP, RBD, TOPs, SOPs, cameras, lighting, and scene assembly. Sub-500ms, no LLM call needed.

### Act 6: "Iterate" (3 min)

**Show:** Claude can modify the scene based on feedback.

```
"The sphere is too dark — increase the key light intensity to 5.0
and add a warm fill light from the right"

"Change the sphere material to a deep red with 0.3 roughness"

"Render again"
```

**Talking point:** This is the core loop — describe what you want, AI makes it happen, render to verify, iterate. Same workflow a lighting TD does, but accessible to anyone who can describe what they want.

---

## Architecture Slide (if needed)

```
Claude Desktop / Claude Code
    ↓ MCP (Model Context Protocol)
mcp_server.py (23 tools, async Python)
    ↓ WebSocket (ws://localhost:9999)
SynapseServer (inside Houdini)
    ↓ hdefereval (main thread dispatch)
Houdini Python API (hou.*)
    ↓
USD Stage / Solaris / Karma XPU
```

**Key architecture decisions:**
- WebSocket over hwebserver (100-10,000x faster for reads/pings)
- hdefereval for thread safety (Houdini's scene graph is single-threaded)
- EMA latency tracking feeding into backpressure controller
- Circuit breaker prevents cascading failures
- repr() escaping on all USD prim paths (injection prevention)

---

## If Something Goes Wrong

- **Server won't start:** Check Python Panel > Server tab. Kill zombies: `gc.get_objects()` search for SynapseServer.
- **Render fails silently:** Karma XPU has ~5s file flush delay. The handler polls for up to 5s.
- **MCP disconnects:** Auto-reconnects on next command. One transparent retry built in.
- **MaterialLibrary createNode returns None:** Cook the matlib first (`matlib.cook(force=True)`) before creating child nodes.

---

## Numbers to Drop

- **23 MCP tools** (node CRUD, USD/Solaris, render, viewport capture, keyframes, TOPs/wedging, scene assembly, render settings, RAG knowledge, memory, search)
- **376 tests**, 5 skipped (hwebserver integration)
- **<1ms** ping RTT (WebSocket, localhost)
- **~5s** Karma XPU render (simple scene, 960x540)
- **61 memories** stored in current project
- **5 critical hardening fixes** shipped today (injection prevention, race conditions, resource leaks, latency tracking)
- **He2025 consistency score: 93/100** (application-layer determinism)

---

## Claude Code Terminal Demo (bonus)

Show the test suite running:
```bash
cd C:\Users\User\Synapse
python -m pytest tests/ -v --tb=short
```

Show git log:
```bash
git log --oneline -10
```

Show Claude Code building features live:
```
"Add a torus next to the sphere with a gold material"
```
