# Agent Teams — Usage Guide

Synapse agent teams let multiple specialist AI agents collaborate on complex VFX tasks in parallel. Each agent connects to the same Houdini session via WebSocket, operates on a filtered tool subset defined by its profile, and coordinates through shared memory.

## Architecture

```
                          spawner.py (CLI)
                               |
                      tmux session: synapse-team
                     /       |        |       \
              [orch]     [scene]   [render]   [qa]
                |           |         |         |
                +-----+-----+---------+---------+
                      |
               ws://localhost:9999/synapse
                      |
              SynapseServer (in Houdini)
                      |
               hou.* Python API
                      |
              Houdini USD Stage
```

Each agent runs `synapse_agent.py` with a specialist profile that:
- Shapes the system prompt with domain knowledge
- Filters the tool set to only relevant tools
- Sets a max-turn limit appropriate to the role

Agents share state through Synapse's memory system (`memory_type="agent_team"`), allowing the orchestrator to track progress and coordinate work.

## Quick Start

### Spawn a team

```bash
cd agent/
python spawner.py --goal "Build and render a turntable of the hero asset"
```

This launches the default team (orchestrator, scene, render, qa) in a tmux session.

### Specify team composition

```bash
python spawner.py --goal "Set up lighting" --team scene,render
```

### Monitor agents

Attach to the tmux session to watch agents work in real time:

```bash
tmux attach -t synapse-agents
```

Or check status without attaching:

```bash
python spawner.py --status
```

### Stop agents

```bash
python spawner.py --stop
```

This sends Ctrl-C to all panes and kills the tmux session.

## Available Profiles

| Profile | File | Max Turns | Tools | Domain |
|---------|------|-----------|-------|--------|
| **orchestrator** | `profiles/orchestrator.md` | 40 | ping, scene_info, inspect_scene, knowledge_lookup | Task decomposition, delegation, progress monitoring |
| **scene** | `profiles/scene.md` | 30 | execute, inspect_scene, inspect_node, scene_info, knowledge_lookup, inspect_selection | USD/Solaris scene assembly, materials, lighting |
| **render** | `profiles/render.md` | 30 | execute, inspect_node, render_preview, scene_info, knowledge_lookup, inspect_scene | Karma rendering, progressive validation |
| **qa** | `profiles/qa.md` | 20 | inspect_scene, inspect_node, scene_info, knowledge_lookup, render_preview | Render validation, frame quality checks |

### Profile tool filtering

Each profile has a `## Tools` section listing allowed tool names (comma-separated). The agent loader reads this section and filters `TOOL_DEFINITIONS` so the LLM only sees tools relevant to its role.

## How Teams Coordinate

### Shared State via Synapse Memory

Agents use `shared_state.py` to read/write coordination data through the Synapse memory system:

```python
from shared_state import write_agent_state, read_agent_state, broadcast_status

# Write agent status
await write_agent_state(client, role="render", status="working", data={"frame": 24})

# Read all team state
entries = await read_agent_state(client)

# Read a specific agent's state
entries = await read_agent_state(client, role="scene")

# Broadcast a message
await broadcast_status(client, role="orchestrator", message="Scene setup complete")
```

State is stored with `memory_type="agent_team"` and tagged with `agent:<role>` and `status:<status>` for filtering.

### Health Checks

Each agent emits a heartbeat every 5 turns via shared state:

```python
# Automatic in the agent loop
write_agent_state(client, role=role, status="active", data={"turn": turn_count})
```

The orchestrator or external monitoring can query these heartbeats to detect stalled agents.

## Adding a New Specialist Profile

1. Create `agent/profiles/<name>.md` with the following structure:

```markdown
# <Name> Specialist Profile

{% include base.md %}

## Domain: <Domain Description>

<Domain-specific instructions, conventions, and rules>

## Tools

tool_a, tool_b, tool_c
```

2. Register the profile in `spawner.py`:

```python
AGENT_PROFILES["my_specialist"] = {
    "profile": "profiles/my_specialist.md",
    "max_turns": 30,
    "description": "What this specialist does",
}
```

3. Use it:

```bash
python spawner.py --goal "Do the thing" --team orchestrator,my_specialist
```

## File Reference

| File | Purpose |
|------|---------|
| `agent/spawner.py` | CLI to spawn, monitor, and stop agent teams via tmux |
| `agent/synapse_agent.py` | Main agent entry point (Opus 4.6 tool-use loop) |
| `agent/synapse_tools.py` | Tool definitions and dispatch for the agent |
| `agent/synapse_ws.py` | WebSocket client for Houdini connection |
| `agent/shared_state.py` | Inter-agent state sharing via Synapse memory |
| `agent/synapse_hooks.py` | Pre/post-execution validation hooks (advisory) |
| `agent/synapse_tone.py` | Coaching tone validation utilities |
| `agent/profiles/` | Specialist profile markdown files |
| `agent/capabilities/` | Autonomy pipeline wrappers for agent tools |
| `agent/tests/` | Unit tests for all agent components |

## Troubleshooting

**"tmux is not installed"** — Install tmux: `sudo apt install tmux` (WSL) or `brew install tmux` (macOS).

**Agents can't connect** — Ensure Synapse is running inside Houdini on `ws://localhost:9999/synapse`. Check with `python spawner.py --status`.

**Agent hits max turns** — Increase `max_turns` in `AGENT_PROFILES` or pass `--max-turns` when running a single agent directly.

**Stale state** — Agent memory entries persist across sessions. The orchestrator should check timestamps when reading team state to ignore stale entries.
