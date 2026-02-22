"""
shared_state.py — Lightweight inter-agent state sharing via SYNAPSE memory.

Agents in a team use the Synapse memory system (add_memory + search handlers)
to share state, broadcast status updates, and coordinate work.

All state is scoped with memory_type="agent_team" and tagged with the
agent's role for filtering.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("synapse.shared_state")


async def write_agent_state(
    client,
    role: str,
    status: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write agent state to shared memory.

    Args:
        client: SynapseClient instance (connected).
        role: Agent role name (e.g., "render", "scene", "qa").
        status: Current status (e.g., "working", "done", "blocked", "error").
        data: Optional additional data to include.

    Returns:
        Response from the memory system.
    """
    content = json.dumps(
        {
            "role": role,
            "status": status,
            "timestamp": time.time(),
            "data": data or {},
        },
        sort_keys=True,
    )

    result = await client.send_command(
        "add_memory",
        {
            "content": content,
            "memory_type": "agent_team",
            "tags": [f"agent:{role}", f"status:{status}", "team"],
        },
    )

    logger.info("Wrote state for [%s]: %s", role, status)
    return result


async def read_agent_state(
    client,
    role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read agent team state from shared memory.

    Args:
        client: SynapseClient instance (connected).
        role: Filter to a specific agent role. None returns all team state.

    Returns:
        List of state entries, newest first.
    """
    tags = ["team"]
    if role:
        tags.append(f"agent:{role}")

    result = await client.send_command(
        "search",
        {
            "query": "agent team state",
            "memory_type": "agent_team",
            "tags": tags,
        },
    )

    # Parse state entries from results
    entries = []
    if isinstance(result, dict) and "results" in result:
        for item in result["results"]:
            try:
                content = item.get("content", "")
                if isinstance(content, str):
                    parsed = json.loads(content)
                    entries.append(parsed)
                else:
                    entries.append(content)
            except (json.JSONDecodeError, TypeError):
                entries.append({"raw": item})

    return entries


async def broadcast_status(
    client,
    role: str,
    message: str,
) -> Dict[str, Any]:
    """Share a status update with the team.

    A convenience wrapper around write_agent_state for simple messages.

    Args:
        client: SynapseClient instance.
        role: Agent role name.
        message: Human-readable status message.

    Returns:
        Response from the memory system.
    """
    return await write_agent_state(
        client,
        role=role,
        status="update",
        data={"message": message},
    )
