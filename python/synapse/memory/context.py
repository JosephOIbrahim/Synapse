"""
Synapse Context Management

Handles project context that persists with the Houdini project.
Context is stored in $HIP/.synapse/context.md and is human-editable.
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from .markdown import ShotContext, load_context, save_context, parse_context_md


# Re-export from markdown module
__all__ = [
    'ShotContext',
    'load_context',
    'save_context',
    'parse_context_md',
    'get_current_context',
    'update_context'
]


def get_current_context(storage_dir: Path) -> ShotContext:
    """
    Get the current project context.

    Args:
        storage_dir: Path to .synapse directory

    Returns:
        ShotContext object with project information
    """
    return load_context(storage_dir)


def update_context(
    storage_dir: Path,
    overview: str = None,
    goals: str = None,
    constraints: str = None,
    assets: list = None,
    client_notes: list = None
):
    """
    Update project context with new information.

    Only updates fields that are provided (not None).
    """
    current = load_context(storage_dir)

    if overview is not None:
        current.overview = overview
    if goals is not None:
        current.goals = goals
    if constraints is not None:
        current.constraints = constraints
    if assets is not None:
        current.assets = assets
    if client_notes is not None:
        current.client_notes = client_notes

    save_context(current, storage_dir)
    return current
