"""
spawner.py — tmux-based multi-agent spawner for Synapse agent teams.

Launches multiple specialist agents in a tmux session, each with its own
profile and role. Provides status monitoring and team shutdown.

USAGE:
    python agent/spawner.py --goal "Build and render a turntable" --team render,scene,qa
    python agent/spawner.py --status
    python agent/spawner.py --stop
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

AGENT_DIR = Path(__file__).parent
TMUX_SESSION = "synapse-team"

# Profile registry: role -> (profile path relative to agent/, max_turns)
AGENT_PROFILES: Dict[str, Dict] = {
    "render": {
        "profile": "profiles/render.md",
        "max_turns": 30,
        "description": "Karma rendering specialist",
    },
    "scene": {
        "profile": "profiles/scene.md",
        "max_turns": 30,
        "description": "USD/Solaris scene assembly",
    },
    "qa": {
        "profile": "profiles/qa.md",
        "max_turns": 20,
        "description": "Render validation & QA",
    },
    "orchestrator": {
        "profile": "profiles/orchestrator.md",
        "max_turns": 40,
        "description": "Task routing & delegation",
    },
}

DEFAULT_TEAM = ["orchestrator", "scene", "render", "qa"]


def _check_tmux() -> bool:
    """Check if tmux is available."""
    return shutil.which("tmux") is not None


def build_agent_command(role: str, goal: str, profile: Optional[str] = None) -> str:
    """Construct the CLI command to launch a specialist agent.

    Args:
        role: Agent role name (maps to AGENT_PROFILES).
        goal: Task goal string.
        profile: Override profile path. If None, uses AGENT_PROFILES lookup.

    Returns:
        Shell command string to launch the agent.
    """
    agent_script = str(AGENT_DIR / "synapse_agent.py")

    if profile is None:
        profile_info = AGENT_PROFILES.get(role, {})
        profile = profile_info.get("profile")

    max_turns = AGENT_PROFILES.get(role, {}).get("max_turns", 30)

    parts = [sys.executable, agent_script]

    if profile:
        parts.extend(["--profile", str(AGENT_DIR / profile)])

    parts.extend(["--role", role])
    parts.extend(["--max-turns", str(max_turns)])
    parts.append(f'"{goal}"')

    return " ".join(parts)


def spawn_team(goal: str, team: Optional[List[str]] = None) -> bool:
    """Create a tmux session with one pane per agent.

    Args:
        goal: Shared goal for all agents.
        team: List of role names. Defaults to DEFAULT_TEAM.

    Returns:
        True if the session was created successfully.
    """
    if not _check_tmux():
        print("tmux is not installed. Install it to use multi-agent teams.")
        return False

    roles = team or DEFAULT_TEAM

    # Kill existing session if any
    subprocess.run(
        ["tmux", "kill-session", "-t", TMUX_SESSION],
        capture_output=True,
    )

    # Create new session with first agent
    first_role = roles[0]
    first_cmd = build_agent_command(first_role, goal)

    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", TMUX_SESSION, "-n", first_role, first_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to create tmux session: {result.stderr}")
        return False

    # Add remaining agents as new panes
    for role in roles[1:]:
        cmd = build_agent_command(role, goal)
        subprocess.run(
            ["tmux", "split-window", "-t", TMUX_SESSION, "-h", cmd],
            capture_output=True,
        )

    # Tile the panes evenly
    subprocess.run(
        ["tmux", "select-layout", "-t", TMUX_SESSION, "tiled"],
        capture_output=True,
    )

    print(f"Spawned {len(roles)} agents in tmux session '{TMUX_SESSION}':")
    for role in roles:
        desc = AGENT_PROFILES.get(role, {}).get("description", role)
        print(f"  [{role}] {desc}")
    print(f"\nAttach with: tmux attach -t {TMUX_SESSION}")

    return True


def get_status() -> List[Dict]:
    """Query tmux for pane info on the agent session.

    Returns:
        List of dicts with pane info (index, title, command, active).
    """
    if not _check_tmux():
        return []

    result = subprocess.run(
        [
            "tmux", "list-panes", "-t", TMUX_SESSION,
            "-F", "#{pane_index}|#{pane_title}|#{pane_current_command}|#{pane_active}",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    panes = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            panes.append({
                "index": parts[0],
                "title": parts[1],
                "command": parts[2],
                "active": parts[3] == "1",
            })

    return panes


def stop_team() -> bool:
    """Stop all agents by sending C-c to all panes, then kill the session.

    Returns:
        True if the session was stopped.
    """
    if not _check_tmux():
        return False

    # Send Ctrl-C to all panes
    panes = get_status()
    for pane in panes:
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{TMUX_SESSION}:{pane['index']}", "C-c", ""],
            capture_output=True,
        )

    # Kill the session
    result = subprocess.run(
        ["tmux", "kill-session", "-t", TMUX_SESSION],
        capture_output=True,
    )

    if result.returncode == 0:
        print(f"Stopped tmux session '{TMUX_SESSION}'")
        return True

    print(f"No active session '{TMUX_SESSION}' found")
    return False


def main():
    """CLI entry point for the spawner."""
    parser = argparse.ArgumentParser(
        description="Synapse multi-agent team spawner (tmux-based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python spawner.py --goal "Render turntable" --team render,scene,qa\n'
            "  python spawner.py --status\n"
            "  python spawner.py --stop\n"
        ),
    )
    parser.add_argument(
        "--goal", type=str, default=None,
        help="Shared goal for the agent team",
    )
    parser.add_argument(
        "--team", type=str, default=None,
        help="Comma-separated role names (default: orchestrator,scene,render,qa)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show status of running agent team",
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="Stop all agents in the team",
    )

    args = parser.parse_args()

    if args.status:
        panes = get_status()
        if not panes:
            print("No active agent team found.")
        else:
            print(f"Agent team ({len(panes)} agents):")
            for pane in panes:
                status = "active" if pane["active"] else "running"
                print(f"  Pane {pane['index']}: {pane['command']} [{status}]")
        return

    if args.stop:
        stop_team()
        return

    if not args.goal:
        parser.print_help()
        sys.exit(1)

    team = args.team.split(",") if args.team else None
    spawn_team(args.goal, team)


if __name__ == "__main__":
    main()
