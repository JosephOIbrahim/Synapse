"""
Synapse Session Summary Generation

Generates human-readable session summaries from session activity data.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import SynapseSession


def generate_session_summary(session: 'SynapseSession') -> str:
    """
    Generate a human-readable session summary.

    Args:
        session: The SynapseSession to summarize

    Returns:
        Markdown-formatted summary string
    """
    duration = session.duration_seconds()
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

    lines = [
        f"## Session Summary",
        f"**Duration:** {duration_str}",
        f"**Commands:** {session.commands_executed}",
        ""
    ]

    if session.nodes_created:
        lines.append("**Nodes Created:**")
        for node in session.nodes_created[:10]:  # Limit to 10
            lines.append(f"- {node}")
        if len(session.nodes_created) > 10:
            lines.append(f"- ... and {len(session.nodes_created) - 10} more")
        lines.append("")

    if session.decisions_made:
        lines.append("**Decisions Made:**")
        for decision in session.decisions_made:
            lines.append(f"- {decision}")
        lines.append("")

    if session.errors_encountered:
        lines.append("**Errors Encountered:**")
        for error in session.errors_encountered[:5]:
            lines.append(f"- {error}")
        lines.append("")

    if session.notable_exchanges:
        lines.append("**Notable Exchanges:**")
        for exchange in session.notable_exchanges[:3]:
            query = exchange.get("query", "")
            response = exchange.get("response", "")
            if query:
                lines.append(f"- Q: {query[:100]}...")
            if response:
                lines.append(f"  A: {response[:100]}...")
        lines.append("")

    return "\n".join(lines)


def format_session_for_ai(session: 'SynapseSession') -> str:
    """
    Format session context for AI prompt injection.

    More compact format suitable for context window.
    """
    lines = [
        f"[Session: {session.session_id}]",
        f"Duration: {int(session.duration_seconds())}s | Commands: {session.commands_executed}"
    ]

    if session.nodes_created:
        lines.append(f"Nodes created: {', '.join(session.nodes_created[:5])}")

    if session.decisions_made:
        lines.append(f"Decisions: {len(session.decisions_made)}")

    if session.errors_encountered:
        lines.append(f"Errors: {len(session.errors_encountered)}")

    return " | ".join(lines)
