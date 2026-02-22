"""
synapse_agent.py — Synapse VFX Co-Pilot Agent

Entry point for the autonomous agent. Connects to Houdini via Synapse,
registers custom tools, and runs an agentic loop with Opus 4.6 that can
inspect, execute, verify, and iterate on VFX tasks.

Uses the anthropic SDK (0.75.0) with standard tool-use message loop.

USAGE:
    cd C:/Users/User/.synapse/agent
    python synapse_agent.py "Set up three-point lighting for the cave scene"
"""

import asyncio
import json
import sys
import os
import logging
from pathlib import Path

# Setup logging
_log_dir = Path(__file__).parent / "logs"
_log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_dir / "agent.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("synapse.agent")

# Model configuration
MODEL = "claude-opus-4-6-20250929"
MAX_TOKENS = 16384
MAX_AGENT_TURNS = 30  # Safety limit on agentic loop iterations


def _load_system_prompt() -> str:
    """Build the system prompt from CLAUDE.md + inline essentials."""
    agent_dir = Path(__file__).parent
    claude_md = agent_dir / "CLAUDE.md"

    personality = ""
    if claude_md.exists():
        personality = claude_md.read_text(encoding="utf-8")

    return (
        "You are the Synapse VFX Co-Pilot — an AI assistant embedded in a "
        "professional VFX artist's Houdini workflow. You have direct access to "
        "their live Houdini scene via custom tools. Your communication style "
        "is that of a supportive senior artist — encouraging, specific, and "
        "forward-looking. Never blame. Always suggest next steps.\n\n"
        "WORKFLOW: Inspect scene -> Plan approach -> Execute (one mutation at a time) "
        "-> Verify result -> Iterate until goal is met.\n\n"
        "SAFETY: Every execute call is wrapped in an undo group. If something fails, "
        "the scene rolls back. Use guard functions (ensure_node, ensure_connection, "
        "ensure_parm) for idempotent operations.\n\n"
        "ONE MUTATION PER synapse_execute CALL. Never combine node creation + "
        "connection + parameter setting in one script.\n\n"
        f"{personality}"
    )


async def run_agent(goal: str):
    """
    Initialize Synapse connection, then run the agentic tool-use loop.
    """
    from anthropic import Anthropic
    from synapse_ws import SynapseClient
    from synapse_tools import set_client, execute_tool, TOOL_DEFINITIONS
    from synapse_hooks import validate_execute_code

    # --- Step 1: Connect to Houdini ---
    logger.info("Connecting to Synapse...")
    synapse = SynapseClient()
    await synapse.connect()
    set_client(synapse)

    # Verify connection
    ping_result = await synapse.ping()
    logger.info("Synapse connected: %s", ping_result)

    scene = await synapse.scene_info()
    logger.info("Scene: %s", scene)

    # --- Step 2: Create Anthropic client ---
    client = Anthropic()

    system_prompt = _load_system_prompt()

    # Initial message with goal and scene context
    user_message = (
        f"GOAL: {goal}\n\n"
        f"SCENE CONTEXT: Connected to Synapse at ws://localhost:9999. "
        f"Scene info: {json.dumps(scene, default=str, sort_keys=True)}\n\n"
        "START by inspecting the scene to understand what you're working with. "
        "Plan your approach, then execute step by step with verification."
    )

    messages = [{"role": "user", "content": user_message}]

    logger.info("Starting agent with goal: %s", goal)
    print(f"\n{'='*60}")
    print(f"  SYNAPSE AGENT — Goal: {goal}")
    print(f"{'='*60}\n")

    # --- Step 3: Agentic loop ---
    for turn in range(MAX_AGENT_TURNS):
        logger.info("Agent turn %d/%d", turn + 1, MAX_AGENT_TURNS)

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Process response content blocks
        assistant_content = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                print(block.text)
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_uses.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Add assistant message to history
        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls, the agent is done
        if not tool_uses:
            logger.info("Agent completed (no more tool calls)")
            break

        # If stop_reason is end_turn with no tool calls, done
        if response.stop_reason == "end_turn" and not tool_uses:
            logger.info("Agent completed (end_turn)")
            break

        # Execute all tool calls
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_input, sort_keys=True)[:200])

            # Pre-validation hook for execute
            if tool_name == "synapse_execute" and "code" in tool_input:
                warning = validate_execute_code(tool_input["code"])
                if warning:
                    logger.warning("Pre-validation: %s", warning)
                    # Inject warning as prefix to result (advisory only)

            # Execute the tool
            result_str = await execute_tool(tool_name, tool_input)
            logger.info("Tool result: %s", result_str[:300])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_str,
            })

        # Add tool results to history
        messages.append({"role": "user", "content": tool_results})

    else:
        logger.warning("Agent hit max turns (%d)", MAX_AGENT_TURNS)
        print(f"\n[Agent reached {MAX_AGENT_TURNS} turns — stopping to avoid runaway loops]")

    # --- Cleanup ---
    await synapse.disconnect()
    logger.info("Disconnected from Synapse")
    print(f"\n{'='*60}")
    print("  SYNAPSE AGENT — Complete")
    print(f"{'='*60}\n")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python synapse_agent.py \"<goal>\"")
        print('Example: python synapse_agent.py "Set up three-point lighting"')
        sys.exit(1)

    goal = " ".join(sys.argv[1:])
    asyncio.run(run_agent(goal))


if __name__ == "__main__":
    main()
