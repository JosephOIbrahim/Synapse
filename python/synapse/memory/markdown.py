"""
Synapse Markdown Sync

Keeps human-readable markdown files in sync with the memory store.
Inspired by Google Conductor's approach of using markdown files as
first-class artifacts that persist in the repo.

Files:
- context.md: Project/shot context (editable)
- decisions.md: Decision log with reasoning
- tasks.md: Task history and progress
"""

import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .models import Memory, MemoryType, MemoryTier


# =============================================================================
# MARKDOWN TEMPLATES
# =============================================================================

CONTEXT_TEMPLATE = '''# Shot Context

## Overview
<!-- Describe what this shot is about -->

## Goals
<!-- What are we trying to achieve? -->

## Constraints
<!-- Technical or creative constraints -->

## Assets
<!-- Key assets used in this shot -->

## Client Notes
<!-- Feedback and direction from client/supervisor -->

---
*Last updated: {timestamp}*
'''

DECISIONS_TEMPLATE = '''# Decision Log

> Track key decisions with reasoning so future-you (or collaborators) understand why.

---

'''

TASKS_TEMPLATE = '''# Task History

> Track completed and pending tasks for this shot.

## In Progress

## Completed

## Blocked

---
*Last updated: {timestamp}*
'''


# =============================================================================
# MARKDOWN PARSER/RENDERER
# =============================================================================

@dataclass
class ParsedDecision:
    """A decision parsed from markdown."""
    date: str
    title: str
    decision: str
    reasoning: str
    alternatives: List[str]
    related: List[str]
    raw_text: str


def parse_decisions_md(content: str) -> List[ParsedDecision]:
    """
    Parse decisions from a markdown file.

    Expected format:
    ## YYYY-MM-DD: Title
    **Decision:** What was decided
    **Reasoning:** Why this was chosen
    **Alternatives Considered:**
    - Option A
    - Option B
    **Related:** See memory #m_xxxx
    """
    decisions = []

    # Split by h2 headers
    sections = re.split(r'^## ', content, flags=re.MULTILINE)

    for section in sections[1:]:  # Skip header section
        lines = section.strip().split('\n')
        if not lines:
            continue

        # Parse header (date: title)
        header = lines[0]
        date_match = re.match(r'(\d{4}-\d{2}-\d{2}):\s*(.+)', header)
        if date_match:
            date = date_match.group(1)
            title = date_match.group(2)
        else:
            date = ""
            title = header

        # Parse body
        body = '\n'.join(lines[1:])

        # Extract fields
        decision = _extract_field(body, "Decision")
        reasoning = _extract_field(body, "Reasoning")
        alternatives = _extract_list(body, "Alternatives Considered")
        related = _extract_list(body, "Related")

        decisions.append(ParsedDecision(
            date=date,
            title=title,
            decision=decision,
            reasoning=reasoning,
            alternatives=alternatives,
            related=related,
            raw_text=section
        ))

    return decisions


def _extract_field(text: str, field_name: str) -> str:
    """Extract a **Field:** value from text."""
    pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?=\n\*\*|\n##|$)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _extract_list(text: str, field_name: str) -> List[str]:
    """Extract a list following **Field:** header."""
    pattern = rf'\*\*{field_name}:\*\*\s*\n((?:\s*-\s*.+\n?)+)'
    match = re.search(pattern, text)
    if match:
        items_text = match.group(1)
        items = re.findall(r'-\s*(.+)', items_text)
        return [item.strip() for item in items]
    return []


def render_decision_md(memory: Memory) -> str:
    """Render a decision memory as markdown."""
    date = memory.created_at.split('T')[0] if memory.created_at else 'unknown'

    lines = [f"## {date}: {memory.summary}", ""]

    # Parse content for decision/reasoning structure
    content = memory.content

    if "**Decision:**" in content:
        # Already formatted
        lines.append(content)
    else:
        # Wrap as decision
        lines.append(f"**Decision:** {content}")

    if memory.links:
        lines.append("")
        lines.append("**Related:**")
        for link in memory.links:
            lines.append(f"- {link.target_id}: {link.reason}")

    lines.append("")
    return '\n'.join(lines)


def render_decisions_md(decisions: List[Memory]) -> str:
    """Render all decision memories as a markdown file."""
    lines = [
        "# Decision Log",
        "",
        "> Track key decisions with reasoning so future-you (or collaborators) understand why.",
        "",
        "---",
        ""
    ]

    # Sort by date, newest first
    sorted_decisions = sorted(
        decisions,
        key=lambda m: m.created_at or "",
        reverse=True
    )

    for memory in sorted_decisions:
        lines.append(render_decision_md(memory))

    return '\n'.join(lines)


# =============================================================================
# MARKDOWN SYNC
# =============================================================================

class MarkdownSync:
    """
    Synchronizes markdown files with the memory store.

    Two-way sync:
    - Changes in memory store -> update markdown files
    - Changes in markdown files -> update memory store (for context.md)
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.context_file = self.storage_dir / "context.md"
        self.decisions_file = self.storage_dir / "decisions.md"
        self.tasks_file = self.storage_dir / "tasks.md"

        self._last_sync: Dict[str, float] = {}

    def ensure_files(self):
        """Create markdown files if they don't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M")

        if not self.context_file.exists():
            self.context_file.write_text(
                CONTEXT_TEMPLATE.format(timestamp=timestamp),
                encoding='utf-8'
            )

        if not self.decisions_file.exists():
            self.decisions_file.write_text(
                DECISIONS_TEMPLATE.format(timestamp=timestamp),
                encoding='utf-8'
            )

        if not self.tasks_file.exists():
            self.tasks_file.write_text(
                TASKS_TEMPLATE.format(timestamp=timestamp),
                encoding='utf-8'
            )

    def sync_decisions(self, decisions: List[Memory]):
        """Update decisions.md from memory store."""
        content = render_decisions_md(decisions)
        self.decisions_file.write_text(content, encoding='utf-8')
        self._last_sync['decisions'] = time.time()

    def read_context(self) -> str:
        """Read the current context.md content."""
        if self.context_file.exists():
            return self.context_file.read_text(encoding='utf-8')
        return ""

    def write_context(self, content: str):
        """Write to context.md."""
        self.context_file.write_text(content, encoding='utf-8')
        self._last_sync['context'] = time.time()

    def get_context_for_ai(self) -> str:
        """
        Get formatted context for AI consumption.

        Combines context.md content with recent decisions summary.
        """
        lines = []

        # Include context.md
        if self.context_file.exists():
            context = self.context_file.read_text(encoding='utf-8')
            lines.append(context)
            lines.append("")

        # Include recent decisions summary
        if self.decisions_file.exists():
            decisions_content = self.decisions_file.read_text(encoding='utf-8')
            # Extract just the decisions (first 5)
            parsed = parse_decisions_md(decisions_content)
            if parsed:
                lines.append("## Recent Decisions")
                for d in parsed[:5]:
                    lines.append(f"- **{d.title}**: {d.decision}")
                lines.append("")

        return '\n'.join(lines)

    def append_decision(self, memory: Memory):
        """Append a new decision to decisions.md."""
        if not self.decisions_file.exists():
            self.ensure_files()

        current = self.decisions_file.read_text(encoding='utf-8')

        # Find the end of the header section (after ---)
        header_end = current.find('---')
        if header_end > 0:
            # Find the end of the header block
            next_newline = current.find('\n', header_end + 3)
            if next_newline > 0:
                # Insert new decision after header
                new_decision = render_decision_md(memory)
                updated = (
                    current[:next_newline + 1] +
                    '\n' +
                    new_decision +
                    current[next_newline + 1:]
                )
                self.decisions_file.write_text(updated, encoding='utf-8')
                return

        # Fallback: just append
        with open(self.decisions_file, 'a', encoding='utf-8') as f:
            f.write('\n' + render_decision_md(memory))


# =============================================================================
# CONTEXT FILE PARSING
# =============================================================================

@dataclass
class ShotContext:
    """Parsed shot context from context.md."""
    overview: str = ""
    goals: str = ""
    constraints: str = ""
    assets: List[str] = None
    client_notes: List[str] = None
    raw_content: str = ""

    def __post_init__(self):
        if self.assets is None:
            self.assets = []
        if self.client_notes is None:
            self.client_notes = []


def parse_context_md(content: str) -> ShotContext:
    """Parse context.md into structured data."""
    ctx = ShotContext(raw_content=content)

    # Extract sections
    sections = {}
    current_section = None
    current_lines = []

    for line in content.split('\n'):
        if line.startswith('## '):
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            current_section = line[3:].strip().lower()
            current_lines = []
        elif current_section:
            # Skip HTML comments
            if not line.strip().startswith('<!--'):
                current_lines.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()

    # Map to fields
    ctx.overview = sections.get('overview', '')
    ctx.goals = sections.get('goals', '')
    ctx.constraints = sections.get('constraints', '')

    # Parse assets as list
    assets_text = sections.get('assets', '')
    if assets_text:
        ctx.assets = [
            line.strip().lstrip('- ')
            for line in assets_text.split('\n')
            if line.strip() and not line.strip().startswith('<!--')
        ]

    # Parse client notes as list
    notes_text = sections.get('client notes', '')
    if notes_text:
        ctx.client_notes = [
            line.strip().lstrip('- ').strip('"\'')
            for line in notes_text.split('\n')
            if line.strip() and not line.strip().startswith('<!--')
        ]

    return ctx


def load_context(storage_dir: Path) -> ShotContext:
    """Load context from storage directory."""
    context_file = storage_dir / "context.md"
    if context_file.exists():
        content = context_file.read_text(encoding='utf-8')
        return parse_context_md(content)
    return ShotContext()


def save_context(ctx: ShotContext, storage_dir: Path):
    """Save context to storage directory."""
    timestamp = time.strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Shot Context",
        "",
        "## Overview",
        ctx.overview or "<!-- Describe what this shot is about -->",
        "",
        "## Goals",
        ctx.goals or "<!-- What are we trying to achieve? -->",
        "",
        "## Constraints",
        ctx.constraints or "<!-- Technical or creative constraints -->",
        "",
        "## Assets",
    ]

    if ctx.assets:
        for asset in ctx.assets:
            lines.append(f"- {asset}")
    else:
        lines.append("<!-- Key assets used in this shot -->")

    lines.extend([
        "",
        "## Client Notes",
    ])

    if ctx.client_notes:
        for note in ctx.client_notes:
            lines.append(f"- \"{note}\"")
    else:
        lines.append("<!-- Feedback and direction from client/supervisor -->")

    lines.extend([
        "",
        "---",
        f"*Last updated: {timestamp}*",
    ])

    context_file = storage_dir / "context.md"
    context_file.write_text('\n'.join(lines), encoding='utf-8')
