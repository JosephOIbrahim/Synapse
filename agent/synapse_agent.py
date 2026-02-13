"""
synapse_agent.py -- Synapse VFX Co-Pilot Agent

Entry point for the autonomous agent. Connects to Houdini via Synapse,
registers custom tools, and runs a plan-iterate-checkpoint loop with
Opus 4.6 that can inspect, execute, verify, and self-heal.

Sprint C adds: multi-goal planning, checkpoint/resume, self-healing retries.

Uses the anthropic SDK (0.75.0) with standard tool-use message loop.

USAGE:
    cd C:/Users/User/.synapse/agent
    python synapse_agent.py "Set up three-point lighting for the cave scene"
    python synapse_agent.py --no-resume "Start fresh on lighting"
    python synapse_agent.py --list-checkpoints
"""

import argparse
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
MAX_AGENT_TURNS = 30  # Safety limit for entire session
MAX_SUBGOAL_TURNS = 10  # Tighter limit per sub-goal


def _load_system_prompt() -> str:
    """Build the system prompt from CLAUDE.md + inline essentials."""
    agent_dir = Path(__file__).parent
    claude_md = agent_dir / "CLAUDE.md"

    personality = ""
    if claude_md.exists():
        personality = claude_md.read_text(encoding="utf-8")

    return (
        "You are the Synapse VFX Co-Pilot -- an AI assistant embedded in a "
        "professional VFX artist's Houdini workflow. You have direct access to "
        "their live Houdini scene via custom tools. Your communication style "
        "is that of a supportive senior artist -- encouraging, specific, and "
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


# ---------------------------------------------------------------------------
# Core tool-use loop (extracted for reuse by sub-goal runner)
# ---------------------------------------------------------------------------

async def _run_tool_loop(
    anthropic_client,
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    validate_hook,
    tops_hook,
    max_turns: int = MAX_AGENT_TURNS,
) -> list[dict]:
    """Run the inner tool-use loop. Returns updated messages list.

    Processes tool calls until the model stops calling tools or max_turns is hit.
    """
    from synapse_tools import execute_tool

    for turn in range(max_turns):
        logger.info("  Turn %d/%d", turn + 1, max_turns)

        response = anthropic_client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
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

        messages.append({"role": "assistant", "content": assistant_content})

        if not tool_uses:
            logger.info("  No more tool calls -- sub-goal complete")
            break

        # Execute all tool calls
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            logger.info("  Tool: %s(%s)", tool_name, json.dumps(tool_input)[:200])

            # Pre-validation hooks
            if tool_name == "synapse_execute" and "code" in tool_input:
                warning = validate_hook(tool_input["code"])
                if warning:
                    logger.warning("  Pre-validation: %s", warning)

            if tool_name == "synapse_tops_cook":
                warning = tops_hook(tool_input)
                if warning:
                    logger.warning("  TOPS advisory: %s", warning)

            result_str = await execute_tool(tool_name, tool_input)
            logger.info("  Result: %s", result_str[:300])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    return messages


# ---------------------------------------------------------------------------
# Sub-goal runners
# ---------------------------------------------------------------------------

async def run_subgoal(
    anthropic_client,
    subgoal,
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    validate_hook,
    tops_hook,
    max_turns: int = MAX_SUBGOAL_TURNS,
) -> tuple[bool, list[dict]]:
    """Execute a single sub-goal using the tool-use loop.

    Returns (success: bool, updated_messages: list).
    """
    goal_msg = (
        f"SUB-GOAL: {subgoal.description}\n"
        f"VERIFICATION: {subgoal.verification}\n\n"
        "Work on this sub-goal. When done, summarize what you accomplished."
    )
    messages.append({"role": "user", "content": goal_msg})

    len_before = len(messages)
    messages = await _run_tool_loop(
        anthropic_client, system_prompt, messages, tools,
        validate_hook, tops_hook, max_turns=max_turns,
    )

    # Consider it successful if the model produced any output
    made_progress = len(messages) > len_before
    return made_progress, messages


async def run_subgoal_with_healing(
    anthropic_client,
    subgoal,
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    validate_hook,
    tops_hook,
) -> tuple[bool, list[dict]]:
    """Execute sub-goal with retry on failure."""
    total_attempts = subgoal.max_retries + 1

    for attempt in range(1, total_attempts + 1):
        subgoal.status = "running"
        subgoal.attempts = attempt

        logger.info(
            "Sub-goal '%s' attempt %d/%d",
            subgoal.description[:50], attempt, total_attempts,
        )

        success, messages = await run_subgoal(
            anthropic_client, subgoal, messages, system_prompt,
            tools, validate_hook, tops_hook,
        )

        if success:
            subgoal.status = "completed"
            return True, messages

        if attempt < total_attempts:
            retry_msg = (
                f"The previous attempt at this sub-goal didn't fully succeed "
                f"(attempt {attempt}/{total_attempts}). "
                f"Let's try a different approach."
            )
            messages.append({"role": "user", "content": retry_msg})
            logger.info("  Retrying sub-goal with different approach...")

    subgoal.status = "failed"
    subgoal.error = "Exhausted retries"
    return False, messages


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

async def run_agent(goal: str, no_resume: bool = False):
    """
    Plan-iterate-checkpoint agent loop.

    1. Connect to Houdini, get scene context
    2. Check for existing checkpoint (unless --no-resume)
    3. Create or resume a plan
    4. Execute sub-goals in topological order with self-healing
    5. Checkpoint after each sub-goal
    """
    from anthropic import Anthropic
    from synapse_ws import SynapseClient
    from synapse_tools import set_client, TOOL_DEFINITIONS
    from synapse_hooks import validate_execute_code, validate_tops_cook
    from synapse_planner import (
        create_plan, topological_order, goal_hash as compute_goal_hash,
    )
    from synapse_checkpoint import (
        save_checkpoint, resume_from_checkpoint, Checkpoint,
    )

    # --- Step 1: Connect to Houdini ---
    logger.info("Connecting to Synapse...")
    synapse = SynapseClient()
    await synapse.connect()
    set_client(synapse)

    ping_result = await synapse.ping()
    logger.info("Synapse connected: %s", ping_result)

    scene = await synapse.scene_info()
    logger.info("Scene: %s", scene)

    # --- Step 2: Create Anthropic client ---
    client = Anthropic()
    system_prompt = _load_system_prompt()

    print(f"\n{'='*60}")
    print(f"  SYNAPSE AGENT -- Goal: {goal}")
    print(f"{'='*60}\n")

    # --- Step 3: Check for checkpoint or create plan ---
    gh = compute_goal_hash(goal)
    plan = None
    messages = []

    if not no_resume:
        resumed = resume_from_checkpoint(gh)
        if resumed:
            plan, messages = resumed
            completed = [sg for sg in plan.sub_goals if sg.status == "completed"]
            print(f"  Resuming from checkpoint ({len(completed)}/{len(plan.sub_goals)} sub-goals done)")
            logger.info("Resumed checkpoint: %d/%d sub-goals", len(completed), len(plan.sub_goals))

    if plan is None:
        print("  Creating plan...")
        plan = await create_plan(client, goal, scene)
        ordered = topological_order(plan.sub_goals)
        plan.sub_goals = ordered
        logger.info("Plan created: %d sub-goals", len(plan.sub_goals))

        # Initial context message
        user_message = (
            f"GOAL: {goal}\n\n"
            f"SCENE CONTEXT: Connected to Synapse at ws://localhost:9999. "
            f"Scene info: {json.dumps(scene, default=str)}\n\n"
            f"PLAN ({len(plan.sub_goals)} sub-goals):\n"
        )
        for i, sg in enumerate(plan.sub_goals, 1):
            user_message += f"  {i}. {sg.description}\n"
        user_message += "\nI'll work through each sub-goal in order."

        messages = [{"role": "user", "content": user_message}]

    # Print plan
    print(f"\n  Plan ({len(plan.sub_goals)} sub-goals):")
    for i, sg in enumerate(plan.sub_goals, 1):
        status_icon = {
            "completed": "+", "running": "~",
            "failed": "!", "pending": " ",
        }.get(sg.status, " ")
        print(f"  [{status_icon}] {i}. {sg.description}")
    print()

    # --- Step 4: Execute sub-goals ---
    for sg in plan.sub_goals:
        if sg.status == "completed":
            continue
        if sg.status == "failed":
            logger.info("Skipping failed sub-goal: %s", sg.description[:50])
            continue

        # Check dependencies
        completed_ids = {s.id for s in plan.sub_goals if s.status == "completed"}
        unmet = [dep for dep in sg.depends_on if dep not in completed_ids]
        if unmet:
            logger.warning(
                "Sub-goal '%s' has unmet dependencies, skipping",
                sg.description[:50],
            )
            sg.status = "failed"
            sg.error = "Unmet dependencies"
            continue

        print(f"\n{'─'*40}")
        print(f"  Sub-goal: {sg.description}")
        print(f"{'─'*40}\n")

        success, messages = await run_subgoal_with_healing(
            client, sg, messages, system_prompt,
            TOOL_DEFINITIONS, validate_execute_code, validate_tops_cook,
        )

        # Checkpoint after each sub-goal
        cp = Checkpoint(
            plan=plan,
            messages=messages,
            completed_goals=[s.id for s in plan.sub_goals if s.status == "completed"],
            scene_snapshot=scene,
        )
        save_checkpoint(cp)

        if not success:
            print(f"\n  Sub-goal failed after {sg.attempts} attempts: {sg.description}")
            logger.warning("Sub-goal failed: %s", sg.description[:50])
            # Continue with remaining sub-goals that don't depend on this one

    # --- Step 5: Summary ---
    completed = [sg for sg in plan.sub_goals if sg.status == "completed"]
    failed = [sg for sg in plan.sub_goals if sg.status == "failed"]

    await synapse.disconnect()
    logger.info("Disconnected from Synapse")

    print(f"\n{'='*60}")
    print(f"  SYNAPSE AGENT -- Complete")
    print(f"  {len(completed)}/{len(plan.sub_goals)} sub-goals completed")
    if failed:
        print(f"  {len(failed)} sub-goals failed:")
        for sg in failed:
            print(f"    - {sg.description} ({sg.error})")
    print(f"{'='*60}\n")


def main():
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(
        description="Synapse VFX Co-Pilot -- autonomous Houdini agent",
    )
    parser.add_argument(
        "goal", nargs="*", help="Goal to accomplish in the Houdini scene",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Start fresh, ignoring any saved checkpoints",
    )
    parser.add_argument(
        "--list-checkpoints", action="store_true",
        help="List saved checkpoints and exit",
    )
    args = parser.parse_args()

    if args.list_checkpoints:
        from synapse_checkpoint import list_checkpoints
        cps = list_checkpoints()
        if not cps:
            print("No checkpoints saved.")
        else:
            print(f"  {len(cps)} checkpoint(s):")
            for cp in cps:
                print(f"    {cp['goal_hash']}  {cp['size_bytes']:>8}b  {cp['path']}")
        return

    goal = " ".join(args.goal)
    if not goal:
        parser.print_help()
        sys.exit(1)

    asyncio.run(run_agent(goal, no_resume=args.no_resume))


if __name__ == "__main__":
    main()
