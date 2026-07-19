# Quick Start

**The short version:** install the package, add your key, restart Houdini, open the panel, type "make a box". No command line beyond one copy-paste, no `pip install`, no MCP client.

> Not installed yet? Do [README ▸ Install](../../README.md#-install--5-minutes) first (~5 minutes), then come back here.

---

## 1. Open the panel

In Houdini: **New Pane Tab ▸ Synapse**.

*(The shelf tool does the same thing -- it opens the panel. It does **not** start any server.)*

> ✅ **You should see** the SYNAPSE panel dock, with a chat field, a rail across the top, and a connection strip along the footer.
> **If you see** no `Synapse` entry in the menu -- Houdini loads packages only at launch. Fully restart Houdini, then run `python scripts/install_synapse_package.py --verify` to confirm the package is wired.

## 2. Type what you want

```
make a box
```

> ✅ **You should see** a real `box` geo node appear in your scene -- and **Ctrl+Z** takes it back. Everything the panel does is an ordinary Houdini action.

That's the whole loop. The agent runs **inside** Houdini's own Python, so tools are direct `hou.*` calls -- there is no bridge to start and nothing to connect for normal chat use.

Try a bigger one:

```
create a solaris network ending with rendersettings using karma xpu
```

The panel proposes the network, validates it against your live scene *and* against probe-verified wiring truth, then builds it in a single undo group.

## 3. Pick your engine (optional)

The rail's **author token** switches between **Claude · Gemini · NVIDIA Nemotron · Ollama (local) · Custom**. Keys for the first three go in the repo-root `.env`; Ollama needs no key; Custom is configured in the panel (base URL · model · key).

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
NVIDIA_API_KEY=nvapi-...
```

> The `.env` is read **at Houdini startup**. Add a key to a Houdini that's already open and it won't be seen -- relaunch from scratch.

---

## Connecting an external client (optional)

Everything above runs in-process and needs no server. You only need the bridge if you want **an outside tool** -- Claude Code, Cursor, a custom agent -- to drive Houdini.

**Start it:** click **Connect** in the SYNAPSE panel footer. It never starts automatically. Once up, the button reads **Bridge ✓**.

That one server serves both surfaces on **one port (default 9999)**: a WebSocket at `/synapse` and an HTTP MCP endpoint at `/mcp`. The real bound port is published to `~/.synapse/bridge.json` -- read that rather than assuming.

**Then point your client at it.** Full configuration for Claude Code, Cursor, VS Code and custom agents: [`docs/mcp/SETUP.md`](../mcp/SETUP.md).

> ⚠️ The repo also ships a **stdio** bridge at [`.mcp.json`](../../.mcp.json) (`python mcp_server.py` from the repo root). That path runs in *your* Python, not Houdini's, and needs `pip install mcp websockets` -- neither is vendored. The in-Houdini panel path needs neither.

## Tools

SYNAPSE registers **115 tools** -- 40 `houdini_*`, 37 `synapse_*`, 21 `cops_*`, 17 `tops_*` -- spanning scene and node ops, USD/Solaris, materials, Copernicus, PDG/TOPs, render orchestration and project memory.

Call `tools/list` for the authoritative list with schemas, or read [`docs/tools.md`](../tools.md).

## Authentication (optional)

Bearer-token auth for the bridge is opt-in. Set an API key via environment variable:

```bash
export SYNAPSE_API_KEY="your-secret-key"
```

Or create `~/.synapse/auth.key`:

```
# Lines starting with # are comments
your-secret-key
```

When enabled, the first WebSocket message must be an `authenticate` command, and `/mcp` requires an `Authorization: Bearer <token>` header.

> **Security posture — local-first, single-user.** On the live `/synapse` handler path, `execute_python` / `execute_vex` run **ungated** — no per-command permission check. Keeping both surfaces on a single-user local machine is what contains arbitrary code execution. Because both ride one port, exposing that port exposes **both**. Do not put either on an untrusted network; a multi-user deployment needs a handler-layer auth gate that is not yet shipped. Details in [`docs/mcp/SETUP.md`](../mcp/SETUP.md#authentication).
