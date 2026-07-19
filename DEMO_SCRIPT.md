# Synapse Demo Script — 2026-07-19 (H22.0.368 · v5.32.x)

## What Is Synapse?

Synapse is an AI-Houdini bridge — Claude (panel chat, Claude Code, or Claude Desktop) drives SideFX Houdini through **115 MCP tools**. Real-time, bidirectional, with persistent project memory and build-probed Houdini knowledge (no phantom APIs).

**Key stats:** 115 MCP tools | 4,275-test ratchet floor (0 fail / 87 skip) | Karma CPU/XPU rendering | MaterialX | USD/Solaris native | TOPs/wedging | Bounded render path (60s wait budget + poll token) | 5 engines: Claude · Gemini · Nemotron · Ollama · Custom | Per-build probe-verified parm knowledge

---

## Pre-Demo Checklist

*Do all of this BEFORE hitting record.*

1. **Package installed** (once): `python scripts/install_synapse_package.py`
2. **Keys** in repo-root `.env` — `ANTHROPIC_API_KEY` (+ Gemini/NVIDIA if switching engines; Ollama is keyless)
3. **OCIO set** in the launch environment — your real color config (ACES or studio), not a barebones one
4. **Preflight:** `node harness/run.ts --task 0.5` → `hip_opens` ✓ `shot_login` ✓
5. **[GUI]** Launch graphical Houdini 22.0.368 (Indie) → open `demo/synapse_demo.hip` — minimal `/stage` LOP entry point; the demo builds everything live from prompts
6. **[GUI]** Open the panel: **New Pane Tab ▸ SYNAPSE** (or the Synapse shelf button)
7. **[GUI]** Click **Connect** in the panel footer — the bridge does **NOT** auto-start. This starts the hwebserver on **:9999** (`/synapse` WS + `/mcp` HTTP). Button flips to **Bridge ✓**
8. **[GUI]** Optional: click **Corpus** in the footer — grounds Solaris builds in real docs
9. **[GUI]** **Warm the XPU cache** — a cold cache makes the render guard REFUSE in Act 3 (~2 min kernel compile). Menu-independent path (the H22 menu name isn't repo-verified): fire **one tiny off-camera render with `force_foreground=true`** during setup — the kernel compile happens then and the cache is warm regardless of menu naming. Alternates: Render ▸ Pre-compile Karma XPU Render Kernels if present; last resort `engine=cpu`
10. **Second terminal:** start `scripts/render_watch.ps1` — the freeze classifier; its output is itself demo-able
11. **Claude Code hookup** (for the bonus): repo `.mcp.json` already registers the stdio bridge (`python mcp_server.py`)
12. **Captures** land in `demo/captures/`

---

## Demo Flow (15-20 min)

### Act 1: "Hello Houdini" (3 min)

**Show:** Claude can see and talk to Houdini.

```
"What's the current scene info?"          → houdini_scene_info
"What nodes are selected?"                → houdini_get_selection
"Is Synapse healthy?"                     → synapse_health
```

**Talking point:** Claude discovers Houdini's state through natural language. No scripting, no plugins beyond Synapse. (`synapse_ping` is the truth-check if anything looks stale — "connected" label alone isn't proof.)

### Act 2: "Build Me a Scene" (5 min)

**Show:** Claude set-dresses the `/stage` LOP network live, from one prompt.

```
"Create a Solaris scene with a sphere on a ground plane,
two MaterialX shaders (blue metallic sphere, warm grey ground),
a dome light, a key light, and a render camera."
```

Synapse composes the LOP graph: geometry, MaterialX materials, lights, camera, `karmarendersettings` (the `engine` parm takes `cpu`/`xpu`).

**[GUI]** Show the network editor filling in. These are real nodes — **Ctrl+Z works** on them.

**Talking point:** This is AI doing VFX technical direction, not text generation. It knows USD, Solaris node graphs, and MaterialX — and it looks up parm names instead of guessing them (Act 5 proves it).

### Act 3: "Render It" (3 min)

**Show:** The bounded render path — honest semantics, not magic.

```
"Render this scene with Karma XPU at 512x512"
```

**What actually happens (say this out loud):**

- A **foreground guard** probes first: engine, resolution, samples, XPU cache warmth. Cold cache → it **refuses** (that's the ~2 min kernel-compile trap; you prewarmed in the checklist). Small-and-warm → allowed
- The render itself runs **in-process on Houdini's main thread** — on Indie that's the working path by design (out-of-process husk can't load the Karma delegate here). **The UI freezes for the render's duration. Expected.** Point at `render_watch.ps1`: **FROZEN/GPU-BUSY = rendering**, not hung
- **From an external client** (Claude Code), the bridge joins the render for a **60s wait budget**. Fast render → result inside the turn. Slow render → `render_in_progress` + a **render token**; follow up with `{"poll": token}`. The bridge staying responsive during a main-thread render **is** the release-week story
- **Success returns:** `image_path` (color-managed JPEG preview) + `output_file` (the disk EXR) + engine + a retina receipt block

**Talking point:** Full render loop — describe, render, see the image, iterate. Bounded, guarded, single-flight: a second render request while one is running gets the active token back instead of stacking freezes.

### Act 4: "Remember This" (3 min)

**Show:** Persistent project memory across sessions.

```
"Record a decision: We chose blue metallic for the hero sphere
because it shows specular highlights and environment reflections well."

"What decisions have been made on this project?"

"Search memories for 'lighting'"
```

→ `synapse_decide`, `synapse_context`, `synapse_search`

**Talking point:** AI doesn't forget between sessions. Memory lives in human-readable layers next to your work — scene layer at `$HIP/claude/` (memory.md/.usd), project layer at `$JOB/claude/` — and opening a shot hydrates both (that's the `shot_login` the preflight verified). Artists can read and edit it.

### Act 5: "Ask Houdini" (2 min)

**Show:** Grounded Houdini knowledge — no hallucinated parameter names.

```
"What's the correct parameter name for dome light intensity?"
→ synapse_knowledge_lookup
```

The answer is a punycode-encoded LOP parm name (`xn__...` — probe-verified on 22.0.368 by `h22_api_delta.py`; ground truth committed at `harness/notes/verified_usdlux_encodings_22.0.368.json`). **Don't sell it as a constant** — the feature is the *discipline*: these encodings are runtime-specific and re-probed per build. The hand-maintained map shipped multiple phantom encodings — `color`, `color_temperature`, `diffuse` among them; probing killed that.

One caveat worth saying on camera: the `xn__` name is the **LOP parm interface** (for `set_parm`); `set_usd_attribute` takes the raw `inputs:intensity`.

**Optional beat:** ask `synapse_scout` about a symbol that *doesn't* exist (e.g. `hou.lopNetworks`) — it returns `exists_in_runtime=false` from an introspected `dir()` symbol table. Phantom APIs get caught before code is written.

**Talking point:** Claude doesn't guess Houdini parameter names — it looks them up, and the lookup is gated by the live runtime's own symbol table.

### Act 6: "Iterate" (3 min)

**Show:** The loop closes — modify from feedback, re-render.

```
"The sphere is too dark — increase the key light intensity to 5.0
and add a warm fill light from the right"

"Change the sphere material to a deep red with 0.3 roughness"

"Render again"
```

Same bounded render semantics as Act 3 — warm cache now, so it's the fast path.

**[GUI]** If a change reads wrong, Ctrl+Z it on camera — the mutations are real Houdini nodes.

**Talking point:** This is the core loop — describe what you want, AI makes it happen, render to verify, iterate. Same workflow a lighting TD runs, accessible to anyone who can describe what they want.

---

## Architecture Slide (if needed)

```
SYNAPSE panel (in Houdini · v9.1 single-CHAT · Ctrl+K tool palette)
Claude Code / Claude Desktop
    ↓ MCP — stdio (.mcp.json → python mcp_server.py)  or  Streamable HTTP /mcp
hwebserver  (started by the panel's Connect button · port 9999, published to ~/.synapse/bridge.json)
    ├── ws://localhost:9999/synapse   (live WS handlers)
    └── /mcp                          (Lossless Execution Bridge — audited path)
    ↓ main-thread marshalling (hdefereval / run_on_main)
Houdini Python API (hou.*)
    ↓
USD Stage / Solaris / Karma CPU·XPU
```

**Key architecture decisions:**
- **One tool registry** — 115 tools served from a single source (`TOOL_DEFS`), doc-count pinned by test
- **Bounded render** — foreground guard + single-flight session registry + 60s wait budget + poll token
- **Path-qualified integrity** — the `/mcp` path is undo-wrapped, consent-gated, scene-hashed; the live WS path is RBAC-guarded with main-thread safety and observe-only integrity envelopes
- **Discoverable endpoint** — hwebserver binds the requested port (9999 by default) and publishes the real bound port to `~/.synapse/bridge.json` for clients to find. Note: it does **not** fail over on conflict (`hwebserver_adapter.py:357-358`) — automatic failover exists only on the legacy `websocket.py` path (`:101`), which the panel does not use
- **5 engines** behind one panel — Claude, Gemini, Nemotron, Ollama, Custom

---

## If Something Goes Wrong

- **Bridge not up:** it never auto-starts — **[GUI]** panel footer ▸ **Connect**. Trust `synapse_ping`, not the label.
- **"Foreground render refused":** cold XPU cache or over-budget resolution. Prewarm (checklist #9), drop to 512×512, switch `engine=cpu`, or pass `force_foreground=true` (downgrades refusal to a carried warning).
- **Render looks hung:** read the watcher line. **FROZEN/GPU-BUSY** = XPU rendering, keep talking. **FROZEN/IDLE** = real hang. From Claude Code: `{"poll": token}` or `synapse_render_farm_status`.
- **Preview is a viewport flipbook:** result carries `flipbook_fallback=true` — the usdrender ROP wrote nothing (husk can't load Karma on Indie). The in-process render path is the working one; check the ROP/engine.
- **Port taken:** the hwebserver does **not** fail over — Connect will fail. Free 9999 (or set `SYNAPSE_PORT`), then Connect again. The bound port is published to `~/.synapse/bridge.json`.

---

## Numbers to Drop

- **115 MCP tools** — canonical registry count (the stdio surface lists 123 = 115 + 8 stdio-local helpers; 115 is THE number)
- **4,275 / 0 / 87** — test ratchet floor, human-promoted advances only (last full run passed higher — verify live before quoting a bigger number)
- **v5.32.0** on **Houdini 22.0.368** (embedded Python **3.13.10** — not the dev-box 3.14)
- **60s** default render wait budget; **~2 min** cold-XPU kernel compile (the trap the guard exists for — the original freeze incident was a 64×64 sphere)
- **5 engines** in one panel — Claude · Gemini · Nemotron · Ollama · Custom
- **Port 9999** default; bound port published to `~/.synapse/bridge.json` (no failover on the hwebserver path — free the port first)

---

## Claude Code Terminal Demo (bonus)

Synapse is already registered for this repo via `.mcp.json` (stdio → `python mcp_server.py`).

Show git log:
```bash
cd C:\Users\User\SYNAPSE
git log --oneline -10
```

Show a slice of the suite (the full `pytest tests/` run is the real gate — too long for camera):
```bash
python -m pytest tests/test_phase0c_doc1_toolcount.py -v
```

Show Claude Code driving the same live scene:
```
"Add a torus next to the sphere with a gold material"
```

Then render from the terminal side and let the **token flow** land on camera — bridge responsive while Houdini's main thread renders.

---

*Verified against feature-freeze commit `963d715` (Leg-1 demo-preflight, 2026-07-19). Facts are code-read at the freeze tree; anything not re-confirmed in a live H22 GUI session this week — prewarm script path, live `/mcp` port serving, exact menu token spellings — verify live before quoting on camera.*
