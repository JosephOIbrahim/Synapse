"""
Memory Pattern Detection

Surfaces repeated blockers, oscillating parameters, and decision reversals
from Living Memory markdown content.
"""

import re
from typing import List, Dict, Any


def detect_patterns(content: str) -> List[Dict[str, Any]]:
    """Detect actionable patterns in memory content.

    Returns list of patterns sorted by severity (highest first).
    Each pattern: {type, description, severity, count, evidence}
    """
    if not content:
        return []

    patterns: List[Dict[str, Any]] = []
    patterns.extend(_detect_repeated_blockers(content))
    patterns.extend(_detect_oscillating_parameters(content))

    patterns.sort(key=lambda p: (-p["severity"], p["type"]))
    return patterns


def _detect_repeated_blockers(content: str) -> List[Dict[str, Any]]:
    """Find blockers mentioned multiple times (similar titles)."""
    # Collect blocker titles from ## Blockers sections
    in_blockers = False
    blocker_titles: List[str] = []
    for line in content.split('\n'):
        if line.startswith('## Blockers'):
            in_blockers = True
            continue
        if line.startswith('## ') and not line.startswith('## Blockers'):
            in_blockers = False
            continue
        if in_blockers and line.startswith('### '):
            blocker_titles.append(line[4:].strip().lower())

    if len(blocker_titles) < 2:
        return []

    # Group similar titles (shared 2+ words)
    groups: Dict[str, List[str]] = {}
    for title in blocker_titles:
        words = set(re.findall(r'[a-z]+', title))
        matched = False
        for key in sorted(groups.keys()):  # sorted iteration for determinism
            key_words = set(re.findall(r'[a-z]+', key))
            if len(words & key_words) >= 2:
                groups[key].append(title)
                matched = True
                break
        if not matched:
            groups[title] = [title]

    results: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):  # sorted iteration for determinism
        members = groups[key]
        if len(members) >= 2:
            results.append({
                "type": "repeated_blocker",
                "description": f"Blocker '{key}' appeared {len(members)} times",
                "severity": len(members),
                "count": len(members),
                "evidence": sorted(members),
            })
    return results


def _detect_oscillating_parameters(content: str) -> List[Dict[str, Any]]:
    """Find parameters that oscillate (A->B->A pattern)."""
    # Extract parameter changes from ## Parameters sections
    in_params = False
    changes: List[tuple] = []
    for line in content.split('\n'):
        if line.startswith('## Parameters') or line.startswith('## Parameter'):
            in_params = True
            continue
        if line.startswith('## ') and 'Parameter' not in line:
            in_params = False
            continue
        if in_params:
            # Match "Before: X, After: Y" — capture value as first token
            # (handles decimal numbers like 5.0 without stopping at the dot)
            match = re.search(r'Before:\s*(\S+),\s*After:\s*(\S+)', line)
            if match:
                before_val = match.group(1).strip().rstrip('.,;')
                after_val = match.group(2).strip().rstrip('.,;')
                changes.append((before_val, after_val))

    if len(changes) < 3:
        return []

    # Detect A->B->A oscillation
    results: List[Dict[str, Any]] = []
    for i in range(len(changes) - 2):
        a_before, a_after = changes[i]
        b_before, b_after = changes[i + 1]
        c_before, c_after = changes[i + 2]
        # A->B then B->A then A->B = oscillation
        if a_after == b_before and b_after == c_before and a_after == c_after:
            results.append({
                "type": "oscillating_parameter",
                "description": f"Parameter oscillating between {a_before} and {a_after}",
                "severity": 1,
                "count": 3,
                "evidence": [
                    f"{a_before}->{a_after}",
                    f"{b_before}->{b_after}",
                    f"{c_before}->{c_after}",
                ],
            })
            break  # One oscillation per parameter sequence

    return results
